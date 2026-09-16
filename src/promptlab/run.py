"""Day 5 harness: three tasks, two configured models, deterministic scores.

Assignment Instructions 4-8: run.py -> prompt registry -> complete_structured
-> ModelAdapter -> OllamaAdapter. No direct HTTP here. Scores join CallRecords.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from promptlab.adapters.base import CompletionRequest, ModelAdapter
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings
from promptlab.corpus import GoldLabel, load_cases, validate_corpus
from promptlab.prompts import TASK_PROMPTS, render_task_user
from promptlab.records import ScoreRecord
from promptlab.rules import VersionCandidate, select_current_version
from promptlab.schemas import (
    OUTPUT_SCHEMAS,
    PolicyExtraction,
    StrictModel,
    SummarizationOutput,
    TaskName,
)
from promptlab.scoring import SCORER_VERSION, failure_scores, score_output
from promptlab.structured import complete_structured
from promptlab.usage import CallRecord

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ADAPTER_RUNS_DIR = Path("runs")
DAY5_RUN_PATH = PROJECT_ROOT / "docs" / "day5-run.jsonl"
DAY5_SCORES_PATH = PROJECT_ROOT / "docs" / "day5-scores.jsonl"
MAX_OUTPUT_TOKENS = 512
TASKS: tuple[TaskName, ...] = ("summarization", "extraction", "triage")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local two-model prompt comparison")
    parser.add_argument("--run-id", help="Stable identifier for this run")
    parser.add_argument("--task", choices=["triage", "summarization", "extraction"])
    parser.add_argument("--model", choices=["mistral", "qwen"])
    parser.add_argument("--limit", type=int, help="Limit cases per task for a smoke run")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration and corpus without calling Ollama",
    )
    return parser


def _adapter_run_path(run_id: str) -> Path:
    return ADAPTER_RUNS_DIR / f"{run_id}.jsonl"


def _load_call_records(run_id: str) -> list[CallRecord]:
    path = _adapter_run_path(run_id)
    if not path.exists():
        return []
    records: list[CallRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(CallRecord.model_validate_json(line))
    return records


def _write_jsonl(path: Path, records: list[CallRecord] | list[ScoreRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(record.model_dump_json() + "\n" for record in records)
    path.write_text(body, encoding="utf-8")


def _version_fields(output: StrictModel) -> tuple[str, str] | None:
    if isinstance(output, SummarizationOutput | PolicyExtraction):
        version = output.version
        effective = output.effective_date
        if (
            version.status == "present"
            and effective.status == "present"
            and isinstance(version.value, str)
            and isinstance(effective.value, str)
        ):
            return version.value, effective.value
    return None


def _add_version_scores(
    *,
    run_id: str,
    task: TaskName,
    model_name: str,
    model_id: str,
    labels: list[GoldLabel],
    outputs: dict[str, StrictModel],
    all_scores: list[ScoreRecord],
) -> None:
    # Instruction 2-3: currency is select_current_version, not a model opinion.
    prompt_id, version = TASK_PROMPTS[task]
    grouped: dict[str, list[GoldLabel]] = defaultdict(list)
    for label in labels:
        if label.version_group:
            grouped[label.version_group].append(label)

    for group_name, group_labels in grouped.items():
        if len(group_labels) < 2:
            continue
        expected = next(
            (
                label.expected_current_case_id
                for label in group_labels
                if label.expected_current_case_id
            ),
            None,
        )
        as_of_raw = next((label.as_of for label in group_labels if label.as_of), None)
        if expected is None or as_of_raw is None:
            continue
        candidates: list[VersionCandidate] = []
        for label in group_labels:
            output = outputs.get(label.id)
            if output is None:
                continue
            extracted = _version_fields(output)
            if extracted is None:
                continue
            extracted_version, effective_raw = extracted
            try:
                effective = date.fromisoformat(effective_raw)
            except ValueError:
                continue
            candidates.append(
                VersionCandidate(
                    case_id=label.id,
                    version=extracted_version,
                    effective_date=effective,
                )
            )
        selected = select_current_version(candidates, date.fromisoformat(as_of_raw))
        all_scores.append(
            ScoreRecord(
                run_id=run_id,
                task=task,
                case_id=f"version:{group_name}",
                model_name=model_name,
                model_id=model_id,
                prompt_id=prompt_id,
                prompt_version=version,
                scorer_version=SCORER_VERSION,
                metric="version_selection_accuracy",
                numerator=int(selected is not None and selected.case_id == expected),
                denominator=1,
                detail=f"expected={expected}; selected={selected.case_id if selected else 'none'}",
            )
        )


def main() -> None:
    args = _parser().parse_args()
    counts = validate_corpus()
    if args.validate_only:
        print("Corpus valid: " + ", ".join(f"{task}={count}" for task, count in counts.items()))
        return

    run_id = cast(str | None, args.run_id)
    if run_id is None or not RUN_ID_PATTERN.fullmatch(run_id):
        raise SystemExit("--run-id is required and must use letters, numbers, '.', '_' or '-'")
    limit = cast(int | None, args.limit)
    if limit is not None and limit < 1:
        raise SystemExit("--limit must be at least 1")

    adapter_path = _adapter_run_path(run_id)
    if adapter_path.exists():
        raise SystemExit(f"Run file already exists: {adapter_path}")

    selected_tasks: list[TaskName] = (
        [cast(TaskName, args.task)] if args.task else list(TASKS)
    )

    settings = Settings.from_env()
    selected_models = [cast(str, args.model)] if args.model else list(settings.models)
    adapters: dict[str, ModelAdapter] = {
        name: cast(ModelAdapter, OllamaAdapter(model_id=settings.models[name].model_id))
        for name in selected_models
    }

    all_scores: list[ScoreRecord] = []
    validated_by_task_model: dict[tuple[TaskName, str], dict[str, StrictModel]] = defaultdict(dict)
    labels_by_task: dict[TaskName, list[GoldLabel]] = defaultdict(list)

    for task in selected_tasks:
        pairs = load_cases(task)
        if limit is not None:
            pairs = pairs[:limit]
        labels_by_task[task] = [gold for _case, gold in pairs]
        prompt_id, version = TASK_PROMPTS[task]
        schema = OUTPUT_SCHEMAS[task]
        for model_name in selected_models:
            model = settings.models[model_name]
            adapter = adapters[model_name]
            for case, gold in pairs:
                system, user_content = render_task_user(task, case.document_text)
                request = CompletionRequest(
                    task=task,
                    case_id=case.id,
                    prompt_id=prompt_id,
                    prompt_version=version,
                    system=system,
                    user_content=user_content,
                    temperature=settings.temperature,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                )
                try:
                    output = complete_structured(
                        adapter,
                        request,
                        schema,
                        run_id,
                        max_repairs=settings.max_schema_repairs,
                    )
                    validated_by_task_model[(task, model_name)][case.id] = output
                    case_scores = score_output(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model_name=model_name,
                        prompt_version=version,
                        output=output,
                        gold=gold,
                        source=case.document_text,
                        model_id=model.model_id,
                        prompt_id=prompt_id,
                    )
                    status = "ok"
                except (json.JSONDecodeError, ValidationError) as exc:
                    case_scores = failure_scores(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model_name=model_name,
                        prompt_version=version,
                        gold=gold,
                        model_id=model.model_id,
                        prompt_id=prompt_id,
                    )
                    status = f"failed: {exc}"
                all_scores.extend(case_scores)
                print(f"{task:13} {model_name:8} {case.id:5} {status}")

    for task in selected_tasks:
        if task == "triage":
            continue
        for model_name in selected_models:
            _add_version_scores(
                run_id=run_id,
                task=task,
                model_name=model_name,
                model_id=settings.models[model_name].model_id,
                labels=labels_by_task[task],
                outputs=validated_by_task_model[(task, model_name)],
                all_scores=all_scores,
            )

    calls = _load_call_records(run_id)
    _write_jsonl(DAY5_RUN_PATH, calls)
    _write_jsonl(DAY5_SCORES_PATH, all_scores)
    print(f"wrote {DAY5_RUN_PATH} ({len(calls)} call records)")
    print(f"wrote {DAY5_SCORES_PATH} ({len(all_scores)} scores)")
    print(f"run_id={run_id} provider=ollama cost_usd=0.0")


if __name__ == "__main__":
    main()
