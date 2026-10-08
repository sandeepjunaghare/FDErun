import asyncio
import json
from datetime import date
from pathlib import Path

import httpx2
import pytest

import run
from contract import AskResponse, GoldenSet, RetrievedChunk
from golden import load_golden
from judge import Faithfulness, JudgeError
from targets import FakeTarget, HttpTarget

EXAMPLE = Path(__file__).resolve().parents[1] / "golden" / "example.yaml"


class StubJudge:
    """Scores 1.0 unless the answer mentions a word in `unsupported`; raises if `fail` is set."""

    model = "stub"

    def __init__(self, unsupported: str | None = None, fail: bool = False):
        self.unsupported, self.fail, self.calls = unsupported, fail, 0

    async def faithfulness(self, question, answer, context) -> Faithfulness:
        self.calls += 1
        if self.fail:
            raise JudgeError("AuthenticationError 401")
        if self.unsupported and self.unsupported in answer:
            return Faithfulness(score=0.5, unsupported_claims=[self.unsupported], reasoning="")
        return Faithfulness(score=1.0, unsupported_claims=[], reasoning="")


def run_main(tmp_path, *args, judge=None) -> int:
    argv = [str(EXAMPLE), "--target", "fake", "--results-dir", str(tmp_path), *args]
    return run.main(argv, judge=judge)


def test_example_passes_on_fake_target_with_judge(tmp_path, capsys):
    judge = StubJudge()
    assert run_main(tmp_path, judge=judge) == 0
    out = capsys.readouterr().out
    assert "RESULT: PASS  (4/4 cases passed)" in out
    assert "faithfulness  1.00 (n=2)" in out
    assert judge.calls == 2  # only the two answered cases are judged
    saved = json.loads(next(tmp_path.glob("*-example.json")).read_text())
    assert saved["summary"]["pass"] is True
    assert saved["meta"]["judge_model"] == "stub"


def test_unfaithful_answer_fails_with_the_claim(tmp_path, capsys):
    assert run_main(tmp_path, judge=StubJudge(unsupported="$250")) == 1
    out = capsys.readouterr().out
    assert "faithfulness 0.50: unsupported: $250" in out
    assert "RESULT: FAIL" in out


def test_judge_errors_fail_the_run_and_say_why(tmp_path, capsys):
    assert run_main(tmp_path, judge=StubJudge(fail=True)) == 1
    out = capsys.readouterr().out
    assert "judge error (AuthenticationError 401)" in out
    assert "judge errors  2 (credentials? or use --no-judge)" in out


def test_no_judge_skips_faithfulness(tmp_path, capsys):
    assert run_main(tmp_path, "--no-judge", judge=StubJudge(fail=True)) == 0
    assert "faithfulness  skipped (--no-judge)" in capsys.readouterr().out


def test_only_runs_selected_cases(tmp_path, capsys):
    assert run_main(tmp_path, "--no-judge", "--only", "weather") == 0
    assert "RESULT: PASS  (1/1 cases passed)" in capsys.readouterr().out


def test_unknown_only_id_is_bad_input(tmp_path):
    assert run_main(tmp_path, "--no-judge", "--only", "nope") == 2


def test_retrieval_miss_and_compare_show_the_fix(tmp_path, capsys):
    golden = tmp_path / "g.yaml"
    golden.write_text(
        EXAMPLE.read_text().replace("contains: specialist visits", "contains: specialist referral")
    )
    broken = run.main(
        [str(golden), "--target", "fake", "--no-judge", "--results-dir", str(tmp_path)]
    )
    assert broken == 1
    assert 'plan-gold.md "specialist referral" not in top-5' in capsys.readouterr().out
    before = next(tmp_path.glob("*-example.json"))  # name comes from the YAML

    golden.write_text(EXAMPLE.read_text())  # the "fix"
    args = [str(golden), "--target", "fake", "--no-judge", "--no-save", "--compare", str(before)]
    assert run.main(args) == 0
    out = capsys.readouterr().out
    assert "hit_rate      0.50 → 1.00  (+0.50)" in out
    assert "fixed: specialist-copay" in out


def test_target_errors_fail_the_run(tmp_path, capsys):
    class Down:
        name = "down"

        async def ask(self, question, user_id, session_id=None):
            raise ConnectionError("refused")

    golden = load_golden(EXAMPLE)
    results = asyncio.run(run.evaluate(golden, Down(), None, k=5))
    summary = run.summarize(results, golden.thresholds, judged=False)
    assert summary["errors"] == 4
    assert summary["pass"] is False


def test_session_cases_run_in_order_with_one_session_id():
    calls: list[tuple[str, str | None]] = []

    class Recorder:
        name = "recorder"

        async def ask(self, question, user_id, session_id=None):
            await asyncio.sleep(0.01 if question == "first" else 0)
            calls.append((question, session_id))
            return AskResponse(answer="a", action="refuse")

    golden = GoldenSet.model_validate(
        {
            "name": "s",
            "cases": [
                {"id": "a", "question": "first", "type": "out_of_scope", "session": "hf"},
                {"id": "b", "question": "alone", "type": "out_of_scope"},
                {"id": "c", "question": "second", "type": "out_of_scope", "session": "hf"},
            ],
        }
    )
    results = asyncio.run(run.evaluate(golden, Recorder(), None, k=5, run_id="r1"))
    assert [r.id for r in results] == ["a", "b", "c"]
    session_calls = [c for c in calls if c[1] is not None]
    assert session_calls == [("first", "eval-r1-hf"), ("second", "eval-r1-hf")]
    assert ("alone", None) in calls


def test_http_target_sends_session_id_only_when_set():
    bodies = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json={"answer": "a"})

    async def go() -> None:
        target = HttpTarget("http://api.test/", transport=httpx2.MockTransport(handler))
        try:
            await target.ask("q?", "u1", session_id="s1")
            await target.ask("q?", "u1")
        finally:
            await target.aclose()

    asyncio.run(go())
    assert bodies == [
        {"question": "q?", "user_id": "u1", "session_id": "s1"},
        {"question": "q?", "user_id": "u1"},
    ]


def test_retrieved_chunk_accepts_labels():
    chunk = RetrievedChunk.model_validate(
        {
            "chunk_id": "heart-failure-standard_of_care-0",
            "doc": "heart-failure/standard_of_care.md",
            "text": "t",
            "section": "standard_of_care",
            "source_label": "Synthetic guideline summary",
            "as_of": "2026-05-20",
        }
    )
    assert chunk.as_of == date(2026, 5, 20)
    assert RetrievedChunk(chunk_id="c", doc="d", text="t").section is None


def test_http_target_posts_to_ask_and_validates_the_contract():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"], seen["body"] = request.url.path, json.loads(request.content)
        chunk = {"chunk_id": "c1", "doc": "d.md", "text": "t"}
        return httpx2.Response(200, json={"answer": "a", "citations": ["c1"], "retrieved": [chunk]})

    async def go() -> AskResponse:
        target = HttpTarget("http://api.test/", transport=httpx2.MockTransport(handler))
        try:
            return await target.ask("q?", "u1")
        finally:
            await target.aclose()

    resp = asyncio.run(go())
    assert seen == {"path": "/ask", "body": {"question": "q?", "user_id": "u1"}}
    assert resp.retrieved == [RetrievedChunk(chunk_id="c1", doc="d.md", text="t")]
    assert resp.action == "answer"


def test_fake_target_refuses_medical_advice():
    resp = asyncio.run(FakeTarget().ask("Should I stop taking my pills?", "u"))
    assert resp.action == "refuse"


@pytest.mark.integration
def test_real_judge_flags_an_unsupported_claim():
    """Calls Claude. Skips when no Anthropic credentials are available."""
    import anthropic

    from judge import ClaudeJudge

    run.load_dotenv(run.ROOT / ".env")
    context = [RetrievedChunk(chunk_id="c1", doc="d.md", text="Urgent care visits cost $50.")]
    try:
        verdict = asyncio.run(
            ClaudeJudge().faithfulness(
                "How much is urgent care?",
                "Urgent care costs $50 and is open 24 hours a day.",
                context,
            )
        )
    except (anthropic.AuthenticationError, JudgeError) as e:
        pytest.skip(f"no usable Anthropic credentials: {e}")
    assert verdict.score < 1.0
    assert any("24" in claim for claim in verdict.unsupported_claims)
