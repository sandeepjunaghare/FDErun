"""Scope: resolve the condition in code; refuse what the planner can't ground in the corpus."""

import re

from schemas import Condition, PlannerOutput, RefuseReason


def match_condition(text: str, conditions: list[Condition]) -> Condition | None:
    """Find a condition named in the text by name or alias, whole-word, longest term first."""
    terms = sorted(
        ((term, c) for c in conditions for term in [c.name, *c.aliases] if term.strip()),
        key=lambda tc: len(tc[0]),
        reverse=True,
    )
    for term, condition in terms:
        if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.I):
            return condition
    return None


def check_scope(
    plan: PlannerOutput, conditions: list[Condition], has_briefing: bool
) -> RefuseReason | None:
    """Return why to refuse, or None. The planner can't invent a condition id or a follow-up."""
    if plan.intent == "out_of_scope":
        return plan.refuse_reason or "unrelated"
    if plan.intent == "follow_up":
        return None if has_briefing else "unknown_condition"
    if plan.condition_id not in {c.id for c in conditions}:
        return "unknown_condition"
    return None
