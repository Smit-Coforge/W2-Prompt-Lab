from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from promptlab.adapters.base import CompletionRequest, ModelAdapter


def complete_structured[T: BaseModel](
    adapter: ModelAdapter,
    request: CompletionRequest,
    schema: type[T],
    run_id: str,
    max_repairs: int = 1,
) -> T:
    """Return a schema-validated completion with a bounded semantic repair loop.

    Transport retry remains inside the adapter.
    Schema/content repair belongs here.

    On validation failure, send the validation error text back to the model and
    instruct it to correct only what the error concerns. Do not perform more
    than max_repairs semantic repair attempts.
    """

    current = request
    repairs_used = 0
    while True:
        result = adapter.complete(current, run_id)
        try:
            return schema.model_validate(_parse_object(result.text))
        except (json.JSONDecodeError, ValidationError) as exc:
            if repairs_used >= max_repairs:
                raise
            repairs_used += 1
            current = request.model_copy(
                update={"user_content": _repair_user_content(exc, result.text)}
            )


def _parse_object(text: str | None) -> Any:
    if text is None or not text.strip():
        raise json.JSONDecodeError("Expecting value", "", 0)
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        if lines and lines[0].strip().lower() == "json":
            lines = lines[1:]
        candidate = "\n".join(lines)
    return json.loads(candidate)


def _repair_user_content(exc: Exception, previous_text: str | None) -> str:
    previous = previous_text if previous_text is not None else ""
    return (
        "The previous response failed validation. "
        "Correct only what the validation error concerns. "
        "Do not change fields that are already valid.\n\n"
        f"Validation error:\n{exc}\n\n"
        f"Previous response:\n{previous}"
    )
