"""Day 2 two-model summarization run through OllamaAdapter."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from promptlab.adapters.base import CompletionRequest
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings
from promptlab.usage import CallRecord

SUMMARIZATION_CASES_PATH = PROJECT_ROOT / "cases" / "summarization.jsonl"
BASELINE_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "baseline.v0.md"
DAY2_RUN_PATH = PROJECT_ROOT / "docs" / "day2-run.jsonl"
MAX_OUTPUT_TOKENS = 256


def load_summarization_cases() -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line in SUMMARIZATION_CASES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload: dict[str, Any] = json.loads(line)
        cases.append(
            {
                "id": str(payload["id"]),
                "task": str(payload["task"]),
                "source": str(payload["source"]),
            }
        )
    return cases


def make_summarization_request(
    case: dict[str, str], template: str, temperature: float
) -> CompletionRequest:
    return CompletionRequest(
        task="summarization",
        case_id=case["id"],
        prompt_id="baseline",
        prompt_version="v0",
        system="",
        user_content=template.replace("{document_text}", case["source"]),
        temperature=temperature,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def write_run_file(records: list[CallRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(record.model_dump_json() + "\n" for record in records)
    path.write_text(body, encoding="utf-8")


def main() -> None:
    settings = Settings.from_env()
    template = BASELINE_PROMPT_PATH.read_text(encoding="utf-8")
    cases = load_summarization_cases()
    run_id = str(uuid.uuid4())
    adapters = [
        OllamaAdapter(model_id=model.model_id) for model in settings.models.values()
    ]
    records: list[CallRecord] = []

    for case in cases:
        request = make_summarization_request(case, template, settings.temperature)
        for adapter in adapters:
            result = adapter.complete(request, run_id)
            records.extend(result.records)
            last = result.records[-1]
            print(
                f"{last.model_id} {last.case_id} attempt={last.attempt} "
                f"ok={result.succeeded} in={last.input_tokens} "
                f"out={last.output_tokens} ms={last.latency_ms}"
            )

    write_run_file(records, DAY2_RUN_PATH)
    print(f"wrote {DAY2_RUN_PATH}")


if __name__ == "__main__":
    main()
