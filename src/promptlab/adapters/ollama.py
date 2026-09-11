"""Ollama ModelAdapter with classified retries."""

from __future__ import annotations

import random
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from promptlab.adapters.base import CompletionRequest, CompletionResult
from promptlab.config import Settings
from promptlab.errors import (
    PermanentProviderError,
    TransientProviderError,
    TruncatedResponseError,
    UnknownModelError,
)
from promptlab.usage import CallRecord, append_record, compute_cost

_TRANSIENT_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_BACKOFF_BASE_SECONDS = 0.25


class OllamaAdapter:
    provider: Literal["ollama"] = "ollama"

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self._settings = Settings.from_env()

    def complete(self, request: CompletionRequest, run_id: str) -> CompletionResult:
        records: list[CallRecord] = []
        if not self._is_configured_model():
            record = self._build_record(
                request=request,
                run_id=run_id,
                attempt=1,
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                stop_reason=None,
                error_type=UnknownModelError.__name__,
                response_text=None,
            )
            append_record(record, run_id)
            records.append(record)
            return CompletionResult(
                succeeded=False,
                text=None,
                error_type=UnknownModelError.__name__,
                records=records,
            )

        max_attempts = self._settings.max_retries + 1
        last_text: str | None = None
        last_error: str | None = None

        for attempt in range(1, max_attempts + 1):
            outcome = self._attempt_once(request)
            record = self._build_record(
                request=request,
                run_id=run_id,
                attempt=attempt,
                latency_ms=outcome["latency_ms"],
                input_tokens=outcome["input_tokens"],
                output_tokens=outcome["output_tokens"],
                stop_reason=outcome["stop_reason"],
                error_type=outcome["error_type"],
                response_text=outcome["text"],
            )
            append_record(record, run_id)
            records.append(record)
            last_text = outcome["text"]
            last_error = outcome["error_type"]

            if last_error is None:
                return CompletionResult(
                    succeeded=True,
                    text=last_text,
                    error_type=None,
                    records=records,
                )
            if last_error != TransientProviderError.__name__ or attempt >= max_attempts:
                return CompletionResult(
                    succeeded=False,
                    text=last_text,
                    error_type=last_error,
                    records=records,
                )
            time.sleep(_backoff_seconds(attempt))

        return CompletionResult(
            succeeded=False,
            text=last_text,
            error_type=last_error,
            records=records,
        )

    def _is_configured_model(self) -> bool:
        return any(model.model_id == self.model_id for model in self._settings.models.values())

    def _attempt_once(self, request: CompletionRequest) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._settings.ollama_base_url}/api/generate",
                json={
                    "model": self.model_id,
                    "prompt": _compose_prompt(request),
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_output_tokens,
                    },
                },
                timeout=180.0,
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError):
            return _failed_attempt(
                latency_ms=int((time.perf_counter() - started) * 1000),
                error_type=TransientProviderError.__name__,
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        status_code = int(getattr(response, "status_code", 200))
        if status_code in _TRANSIENT_HTTP_STATUSES or status_code >= 500:
            return _failed_attempt(
                latency_ms=latency_ms,
                error_type=TransientProviderError.__name__,
            )
        if status_code >= 400:
            return _failed_attempt(
                latency_ms=latency_ms,
                error_type=PermanentProviderError.__name__,
            )

        payload: dict[str, Any] = response.json()
        text = _response_text(payload)
        stop_reason = payload.get("done_reason")
        stop_reason_text = str(stop_reason) if stop_reason is not None else None
        input_tokens = int(payload.get("prompt_eval_count") or 0)
        output_tokens = int(payload.get("eval_count") or 0)
        error_type = (
            TruncatedResponseError.__name__ if stop_reason_text == "length" else None
        )
        return {
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "stop_reason": stop_reason_text,
            "error_type": error_type,
            "text": text,
        }

    def _build_record(
        self,
        *,
        request: CompletionRequest,
        run_id: str,
        attempt: int,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        stop_reason: str | None,
        error_type: str | None,
        response_text: str | None,
    ) -> CallRecord:
        cost_usd = 0.0
        if self._is_configured_model():
            cost_usd = compute_cost(self.model_id, input_tokens, output_tokens)
        return CallRecord(
            record_id=str(uuid.uuid4()),
            run_id=run_id,
            timestamp=datetime.now(UTC),
            provider="ollama",
            model_id=self.model_id,
            task=request.task,
            case_id=request.case_id,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            attempt=attempt,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=None,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            stop_reason=stop_reason,
            error_type=error_type,
            response_text=response_text,
        )


def _compose_prompt(request: CompletionRequest) -> str:
    if request.system.strip():
        return f"{request.system}\n\n{request.user_content}"
    return request.user_content


def _failed_attempt(*, latency_ms: int, error_type: str) -> dict[str, Any]:
    return {
        "latency_ms": latency_ms,
        "input_tokens": 0,
        "output_tokens": 0,
        "stop_reason": None,
        "error_type": error_type,
        "text": None,
    }


def _response_text(payload: dict[str, Any]) -> str | None:
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    response = payload.get("response")
    return response if isinstance(response, str) else None


def _backoff_seconds(failed_attempt: int) -> float:
    exponential = _BACKOFF_BASE_SECONDS * (2 ** (failed_attempt - 1))
    jitter = random.uniform(0, _BACKOFF_BASE_SECONDS)
    return float(exponential + jitter)
