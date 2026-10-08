"""Shared Anthropic helper: one structured-output call shape for every agent."""

from typing import Any, Protocol

import anthropic
from pydantic import BaseModel

from agents.errors import LLMError, LLMRefusal
from config import Settings

# Answerer settings from the dry run: low effort, server-side fallback on overload.
ANSWERER_EXTRA: dict[str, Any] = {
    "output_config": {"effort": "low"},
    "betas": ["server-side-fallback-2026-07-01"],
    "fallbacks": "default",
}


class LLM(Protocol):
    async def parse[T: BaseModel](
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        output_format: type[T],
        max_tokens: int = 1024,
        extra: dict[str, Any] | None = None,
    ) -> T: ...


class ClaudeLLM:
    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None):
        self._settings = settings
        self._client = client

    def _get_client(self) -> anthropic.AsyncAnthropic:
        # Lazy: the app (and its health routes) start without ANTHROPIC_API_KEY.
        if self._client is None:
            if not self._settings.anthropic_api_key:
                raise LLMError("ANTHROPIC_API_KEY is not set")
            self._client = anthropic.AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    async def parse[T: BaseModel](
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        output_format: type[T],
        max_tokens: int = 1024,
        extra: dict[str, Any] | None = None,
    ) -> T:
        client = self._get_client()
        try:
            response = await client.beta.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output_format,
                **(extra or {}),
            )
        except anthropic.APIStatusError as e:
            raise LLMError(f"{type(e).__name__} {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("APIConnectionError") from e
        if response.stop_reason == "refusal":
            raise LLMRefusal(model)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"no structured output (stop_reason={response.stop_reason})")
        return parsed
