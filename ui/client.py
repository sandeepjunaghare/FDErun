"""HTTP client for the API: POST /chat as server-sent events, GET /recent, and the /chat probe."""

import json
import time
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import httpx
from pydantic import ValidationError

from models import ChatRequest, RecentCondition

ChatEvent = tuple[str, dict[str, Any]]

# A briefing took up to 41 s on Render, plus ~33 s if the API was asleep; leave room for both.
CHAT_TIMEOUT = httpx.Timeout(120, connect=5)
SHORT_TIMEOUT = httpx.Timeout(10)
# Render's free plan sleeps when idle; while it wakes, its proxy answers 502/503/504 at once.
WAKE_WAIT_S = 90
WAKING_STATUSES = {502, 503, 504}


class UiApiError(Exception):
    """A call to the API failed; the message is the underlying error class name only."""


def parse_sse(lines: Iterable[str]) -> Iterator[ChatEvent]:
    """Parse SSE lines into (event, JSON data) pairs; an unterminated trailing event is dropped."""
    event, data = "message", []
    for line in lines:
        if line == "":
            if data:
                try:
                    payload = json.loads("\n".join(data))
                except json.JSONDecodeError as e:
                    raise UiApiError(type(e).__name__) from e
                yield event, payload if isinstance(payload, dict) else {"value": payload}
            event, data = "message", []
        elif line.startswith(":"):
            continue
        else:
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)


def stream_chat(
    api_url: str, req: ChatRequest, *, client: httpx.Client | None = None
) -> Iterator[ChatEvent]:
    """POST /chat and yield its events. Raises UiApiError on any transport or HTTP error."""
    http = client or httpx.Client(timeout=CHAT_TIMEOUT)
    try:
        with http.stream("POST", f"{api_url}/chat", json=req.model_dump(exclude_none=True)) as r:
            r.raise_for_status()
            yield from parse_sse(r.iter_lines())
    except httpx.HTTPError as e:
        raise UiApiError(type(e).__name__) from e
    finally:
        if client is None:
            http.close()


def chat_available(api_url: str, *, client: httpx.Client | None = None) -> bool:
    """True if the API exposes POST /chat (read from FastAPI's OpenAPI schema)."""
    http = client or httpx.Client(timeout=SHORT_TIMEOUT)
    try:
        r = http.get(f"{api_url}/openapi.json")
        return r.is_success and "/chat" in r.json().get("paths", {})
    except (httpx.HTTPError, ValueError):
        return False
    finally:
        if client is None:
            http.close()


def get_recent(
    api_url: str, user_id: str, *, client: httpx.Client | None = None
) -> list[RecentCondition]:
    """GET /recent for a user, newest first. Any failure (incl. a pre-merge 404) → []."""
    http = client or httpx.Client(timeout=SHORT_TIMEOUT)
    try:
        r = http.get(f"{api_url}/recent", params={"user_id": user_id})
        if not r.is_success:
            return []
        body = r.json()
        rows = body.get("conditions", []) if isinstance(body, dict) else body
        return [RecentCondition.model_validate(row) for row in rows]
    except (httpx.HTTPError, ValueError, ValidationError):
        return []
    finally:
        if client is None:
            http.close()


def wake_api(
    api_url: str,
    *,
    wait_s: float = WAKE_WAIT_S,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Poll GET /health until it answers 200 or `wait_s` passes; True if the API is up.

    Retries on Render's waking statuses and on transport errors; any other status stops early.
    """
    http = client or httpx.Client(timeout=SHORT_TIMEOUT)
    deadline = clock() + wait_s
    try:
        while True:
            try:
                r = http.get(f"{api_url}/health")
                if r.is_success:
                    return True
                if r.status_code not in WAKING_STATUSES:
                    return False
            except httpx.HTTPError:
                pass
            if clock() >= deadline:
                return False
            sleep(2)
    finally:
        if client is None:
            http.close()
