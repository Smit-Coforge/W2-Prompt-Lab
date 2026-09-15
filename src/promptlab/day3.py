"""Day 3 structured summarization and extraction run."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ValidationError

from promptlab.adapters.base import CompletionRequest, ModelAdapter
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings
from promptlab.schemas import PolicyExtraction, SummarizationOutput, schema_description
from promptlab.structured import complete_structured
from promptlab.usage import CallRecord

SUMMARIZATION_CASES_PATH = PROJECT_ROOT / "cases" / "summarization.jsonl"
EXTRACTION_CASES_PATH = PROJECT_ROOT / "cases" / "extraction.jsonl"
SUMMARIZE_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "summarize.v1.md"
EXTRACT_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "extract.v2.md"
DAY3_RUN_PATH = PROJECT_ROOT / "docs" / "day3-run.jsonl"
ADAPTER_RUNS_DIR = Path("runs")
MAX_OUTPUT_TOKENS = 512
TEMPERATURE = 0.0


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


def render_prompt(template: str, source: str, schema: type[BaseModel]) -> str:
    return template.replace("{schema_description}", schema_description(schema)).replace(
        "{document_text}", source
    )


def make_request(
    *,
    task: Literal["triage", "summarization", "extraction"],
    case: dict[str, str],
    prompt_id: str,
    prompt_version: str,
    user_content: str,
) -> CompletionRequest:
    return CompletionRequest(
        task=task,
        case_id=case["id"],
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        system="",
        user_content=user_content,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


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


def run_cases(
    *,
    adapter: ModelAdapter,
    run_id: str,
    cases: list[dict[str, str]],
    template: str,
    schema: type[BaseModel],
    task: Literal["triage", "summarization", "extraction"],
    prompt_id: str,
    prompt_version: str,
    max_repairs: int,
) -> None:
    for case in cases:
        request = make_request(
            task=task,
            case=case,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            user_content=render_prompt(template, case["source"], schema),
        )
        try:
            complete_structured(
                adapter, request, schema, run_id, max_repairs=max_repairs
            )
            print(f"{adapter.model_id} {case['id']} validated")
        except (json.JSONDecodeError, ValidationError) as exc:
            print(f"{adapter.model_id} {case['id']} failed: {exc}")


def main() -> None:
    settings = Settings.from_env()
    model = settings.models["qwen"]
    adapter = cast(ModelAdapter, OllamaAdapter(model_id=model.model_id))
    run_id = str(uuid.uuid4())
    print(f"run_id={run_id} model={adapter.model_id}")

    run_cases(
        adapter=adapter,
        run_id=run_id,
        cases=load_cases(SUMMARIZATION_CASES_PATH),
        template=SUMMARIZE_PROMPT_PATH.read_text(encoding="utf-8"),
        schema=SummarizationOutput,
        task="summarization",
        prompt_id="summarize",
        prompt_version="v1",
        max_repairs=settings.max_schema_repairs,
    )
    run_cases(
        adapter=adapter,
        run_id=run_id,
        cases=load_cases(EXTRACTION_CASES_PATH),
        template=EXTRACT_PROMPT_PATH.read_text(encoding="utf-8"),
        schema=PolicyExtraction,
        task="extraction",
        prompt_id="extract",
        prompt_version="v2",
        max_repairs=settings.max_schema_repairs,
    )

    records = load_run_records(run_id)
    write_run_file(records, DAY3_RUN_PATH)
    print(f"wrote {DAY3_RUN_PATH} ({len(records)} records)")


if __name__ == "__main__":
    main()
