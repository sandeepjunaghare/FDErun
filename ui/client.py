"""HTTP client for the API: POST /chat as server-sent events, GET /recent, and the /chat probe."""

import json
from collections.abc import Iterable, Iterator
from typing import Any

import httpx
from pydantic import ValidationError

from models import ChatRequest, RecentCondition

ChatEvent = tuple[str, dict[str, Any]]

# An answerable briefing takes 6.5–8 s before the first token; leave plenty of room.
CHAT_TIMEOUT = httpx.Timeout(60, connect=5)
SHORT_TIMEOUT = httpx.Timeout(10)


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
