"""Day 4 structured triage run."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from promptlab.adapters.base import CompletionRequest, ModelAdapter
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings
from promptlab.prompts import load, render_user
from promptlab.schemas import TriageOutput, TriageOutputWithAnalysis
from promptlab.structured import complete_structured
from promptlab.usage import CallRecord

CASES_PATH = PROJECT_ROOT / "cases" / "triage.jsonl"
DAY4_RUN_PATH = PROJECT_ROOT / "docs" / "day4-run.jsonl"
ADAPTER_RUNS_DIR = Path("runs")
MAX_OUTPUT_TOKENS = 512
TEMPERATURE = 0.0
PROMPT_VERSIONS = ("v2",)
SCHEMAS: dict[str, type[BaseModel]] = {
    "v1": TriageOutput,
    "v2": TriageOutputWithAnalysis,
}


def load_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
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


def resolve_run_id() -> str:
    if DAY4_RUN_PATH.exists():
        for line in DAY4_RUN_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                return CallRecord.model_validate_json(line).run_id
    return str(uuid.uuid4())


def write_run_file(records: list[CallRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(record.model_dump_json() + "\n" for record in records)
    path.write_text(body, encoding="utf-8")


def load_run_records(run_id: str) -> list[CallRecord]:
    path = ADAPTER_RUNS_DIR / f"{run_id}.jsonl"
    if not path.exists():
        return []
    records: list[CallRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(CallRecord.model_validate_json(line))
    return records


def run_version(
    *,
    adapter: ModelAdapter,
    run_id: str,
    cases: list[dict[str, str]],
    prompt_version: str,
    max_repairs: int,
) -> None:
    template = load("triage", prompt_version)
    schema = SCHEMAS[prompt_version]
    for case in cases:
        request = CompletionRequest(
            task="triage",
            case_id=case["id"],
            prompt_id="triage",
            prompt_version=prompt_version,
            system=template.system,
            user_content=render_user(template, {}, case["source"]),
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        try:
            complete_structured(
                adapter, request, schema, run_id, max_repairs=max_repairs
            )
            print(f"{adapter.model_id} triage.{prompt_version} {case['id']} validated")
        except (json.JSONDecodeError, ValidationError) as exc:
            print(f"{adapter.model_id} triage.{prompt_version} {case['id']} failed: {exc}")


def main() -> None:
    settings = Settings.from_env()
    model = settings.models["qwen"]
    adapter = cast(ModelAdapter, OllamaAdapter(model_id=model.model_id))
    run_id = resolve_run_id()
    cases = load_cases(CASES_PATH)
    print(f"run_id={run_id} model={adapter.model_id} versions={PROMPT_VERSIONS}")

    for prompt_version in PROMPT_VERSIONS:
        run_version(
            adapter=adapter,
            run_id=run_id,
            cases=cases,
            prompt_version=prompt_version,
            max_repairs=settings.max_schema_repairs,
        )

    records = load_run_records(run_id)
    write_run_file(records, DAY4_RUN_PATH)
    print(f"wrote {DAY4_RUN_PATH} ({len(records)} records)")


if __name__ == "__main__":
    main()
