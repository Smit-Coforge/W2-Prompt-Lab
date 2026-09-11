"""Errors used by the Week 2 local model lab."""


class TransientProviderError(ValueError):
    """Raised on timeout, connection failure, or temporary Ollama/server failure."""


class PermanentProviderError(ValueError):
    """Raised on a malformed request, unavailable model, or other non-retryable failure."""


class TruncatedResponseError(ValueError):
    """Raised when Ollama reports that the output token ceiling was reached."""


class UnknownModelError(ValueError):
    """Raised when a model identifier is not present in the configured model table."""
