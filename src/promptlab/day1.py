"""Day 1 local Mistral extraction run."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from promptlab.config import PROJECT_ROOT, Settings
from promptlab.usage import CallRecord, append_record, compute_cost

DAY1_CASE_IDS: tuple[str, ...] = ("E12", "E07", "E11")
EXTRACTION_CASES_PATH = PROJECT_ROOT / "cases" / "extraction.jsonl"
BASELINE_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "baseline.v0.md"
DEFAULT_NUM_PREDICT = 256
TRUNCATION_NUM_PREDICT = 8
TEMPERATURE = 0.0


def load_day1_cases() -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for line in EXTRACTION_CASES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload: dict[str, Any] = json.loads(line)
        case_id = str(payload["id"])
        by_id[case_id] = {
            "id": case_id,
            "task": str(payload["task"]),
            "source": str(payload["source"]),
        }
    return [by_id[case_id] for case_id in DAY1_CASE_IDS]


def call_mistral(
    settings: Settings, prompt: str, num_predict: int
) -> tuple[dict[str, Any], int]:
    model = settings.models["mistral"]
    started = time.perf_counter()
    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": model.model_id,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": num_predict,
            },
        },
        timeout=180.0,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload, latency_ms


def build_record(
    *,
    run_id: str,
    settings: Settings,
    case: dict[str, str],
    payload: dict[str, Any],
    latency_ms: int,
    num_predict: int,
    error_type: str | None = None,
) -> CallRecord:
    model_id = settings.models["mistral"].model_id
    input_tokens = int(payload["prompt_eval_count"])
    output_tokens = int(payload["eval_count"])
    stop_reason = payload.get("done_reason")
    stop_reason_text = str(stop_reason) if stop_reason is not None else None
    timestamp = datetime.now(UTC)
    return CallRecord(
        record_id=str(uuid.uuid4()),
        run_id=run_id,
        timestamp=timestamp,
        provider="ollama",
        model_id=model_id,
        task="extraction",
        case_id=case["id"],
        prompt_id="baseline",
        prompt_version="v0",
        attempt=1,
        temperature=TEMPERATURE,
        max_output_tokens=num_predict,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=None,
        latency_ms=latency_ms,
        cost_usd=compute_cost(model_id, input_tokens, output_tokens),
        stop_reason=stop_reason_text,
        error_type=error_type,
        response_text=payload.get("response"),
    )


def print_record_summary(title: str, record: CallRecord) -> None:
    print(f"=== {title} ===")
    print(f"input_tokens={record.input_tokens}")
    print(f"output_tokens={record.output_tokens}")
    print(f"latency_ms={record.latency_ms}")
    print(f"stop_reason={record.stop_reason}")
    print(f"error_type={record.error_type}")
    print(f"timestamp={record.timestamp.isoformat()}")
    print(f"tzinfo={record.timestamp.tzinfo}")
    print(record.response_text)
    print()


def demonstrate_truncation(
    settings: Settings, template: str, case: dict[str, str], run_id: str
) -> CallRecord:
    prompt = template.replace("{document_text}", case["source"])
    payload, latency_ms = call_mistral(settings, prompt, TRUNCATION_NUM_PREDICT)
    error_type = (
        "TruncatedResponseError" if payload.get("done_reason") == "length" else None
    )
    return build_record(
        run_id=run_id,
        settings=settings,
        case=case,
        payload=payload,
        latency_ms=latency_ms,
        num_predict=TRUNCATION_NUM_PREDICT,
        error_type=error_type,
    )


def main() -> None:
    settings = Settings.from_env()
    template = BASELINE_PROMPT_PATH.read_text(encoding="utf-8")
    cases = load_day1_cases()
    run_id = str(uuid.uuid4())
    case_e11 = next(case for case in cases if case["id"] == "E11")

    truncation = demonstrate_truncation(settings, template, case_e11, run_id)
    print_record_summary("E11 truncation demo (not in evidence file)", truncation)

    for case in cases:
        prompt = template.replace("{document_text}", case["source"])
        payload, latency_ms = call_mistral(settings, prompt, DEFAULT_NUM_PREDICT)
        record = build_record(
            run_id=run_id,
            settings=settings,
            case=case,
            payload=payload,
            latency_ms=latency_ms,
            num_predict=DEFAULT_NUM_PREDICT,
        )
        append_record(record, run_id)
        print_record_summary(case["id"], record)

    print(f"wrote runs/{run_id}.jsonl")


if __name__ == "__main__":
    main()
