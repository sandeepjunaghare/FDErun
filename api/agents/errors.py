"""The one exception class the pipeline raises to the routes."""


class PipelineError(Exception):
    """A request couldn't be completed (LLM or data layer). Routes return 503 + class name."""


class LLMError(PipelineError):
    """The Anthropic API failed or returned no structured output."""


class LLMRefusal(Exception):
    """The model declined (stop_reason == "refusal"); the pipeline answers action="refuse"."""
