"""Deterministic scoring against gold labels.

Assignment §1: extend Day 4 C5 metrics; do not call a model.
Assignment §8: score rows carry join keys for CallRecord.
Assignment §9 / §14: extraction missed vs invented stay separate;
triage includes routing, escalation, boundary, and PII.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

from promptlab.config import PII_PATTERNS
from promptlab.corpus import GoldLabel
from promptlab.records import ScoreRecord, append_record
from promptlab.schemas import (
    OUTPUT_SCHEMAS,
    EvidenceField,
    TaskName,
)

SCORER_VERSION = "day5-v1"

BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bapproved\b", re.IGNORECASE),
    re.compile(r"\bdenied\b", re.IGNORECASE),
    re.compile(r"\brefund", re.IGNORECASE),
    re.compile(r"\breimburs", re.IGNORECASE),
    re.compile(r"\bresolved\b", re.IGNORECASE),
    re.compile(r"\bgranted\b", re.IGNORECASE),
)

_HEADING = re.compile(r"^(\d+\.\s+\S.*)$", re.MULTILINE)

GoldInput = GoldLabel | Mapping[str, Any]
OutputInput = object


class _ScoreKeys(TypedDict):
    run_id: str
    task: TaskName
    case_id: str
    model_name: str
    prompt_version: str
    model_id: str
    prompt_id: str


def load_gold(path: Path) -> dict[str, dict[str, Any]]:
    gold: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        gold[str(row["id"])] = row
    return gold


def source_sections(source: str) -> set[str]:
    """Return normalized numbered headings from a source document."""
    return {match.group(1).strip().lower() for match in _HEADING.finditer(source)}


def _as_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, GoldLabel):
        return value.model_dump()
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _boundary_pass(output: Mapping[str, Any]) -> bool:
    chunks = [str(output.get("draft_reply") or "")]
    outcome = output.get("customer_outcome")
    if outcome is not None:
        chunks.append(str(outcome))
    text = "\n".join(chunks)
    return not any(pattern.search(text) for pattern in BOUNDARY_PATTERNS)


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        found: list[str] = []
        for item in value.values():
            found.extend(_strings(item))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_strings(item))
        return found
    return []


def _pii_leak(output: Mapping[str, Any]) -> bool:
    text = "\n".join(_strings(output))
    return any(pattern.search(text) for pattern in PII_PATTERNS)


def _keys(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model_name: str,
    prompt_version: str,
    model_id: str,
    prompt_id: str,
) -> _ScoreKeys:
    return {
        "run_id": run_id,
        "task": task,
        "case_id": case_id,
        "model_name": model_name,
        "prompt_version": prompt_version,
        "model_id": model_id,
        "prompt_id": prompt_id,
    }


def _score(
    keys: _ScoreKeys,
    *,
    metric: str,
    numerator: int,
    denominator: int,
    lower_is_better: bool = False,
    detail: str | None = None,
) -> ScoreRecord:
    return ScoreRecord(
        **keys,
        scorer_version=SCORER_VERSION,
        metric=metric,
        numerator=numerator,
        denominator=denominator,
        lower_is_better=lower_is_better,
        detail=detail,
    )


def _evidence_items(output: object) -> dict[str, EvidenceField | Mapping[str, Any]]:
    evidence = getattr(output, "evidence_fields", None)
    if callable(evidence):
        return dict(evidence())
    dumped = _as_mapping(output)
    items: dict[str, EvidenceField | Mapping[str, Any]] = {}
    for name, value in dumped.items():
        if name == "document_status":
            continue
        if isinstance(value, EvidenceField) or (
            isinstance(value, Mapping) and "status" in value
        ):
            items[name] = value
    return items


def _field_status(field: EvidenceField | Mapping[str, Any]) -> str:
    if isinstance(field, EvidenceField):
        return field.status
    return str(field.get("status") or "")


def _field_citation(field: EvidenceField | Mapping[str, Any]) -> str:
    if isinstance(field, EvidenceField):
        return (field.citation or "").strip()
    raw = field.get("citation")
    return str(raw).strip() if raw else ""


def _schema_field_names(task: TaskName) -> list[str]:
    schema = OUTPUT_SCHEMAS[task]
    return [name for name in schema.model_fields if name != "document_status"]


def _recoverable(gold: Mapping[str, Any]) -> list[str]:
    fields = gold.get("recoverable_fields") or []
    return [str(name) for name in fields]


def _score_evidence(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: object,
    gold: Mapping[str, Any],
    source: str,
    model_id: str,
    prompt_id: str,
) -> list[ScoreRecord]:
    recoverable = _recoverable(gold)
    items = _evidence_items(output)
    present = {
        name for name, field in items.items() if _field_status(field) == "present"
    }
    sections = source_sections(source)
    recall_hits = sum(1 for name in recoverable if name in present)
    present_fields = [name for name, field in items.items() if _field_status(field) == "present"]
    citation_hits = 0
    for name in present_fields:
        citation = _field_citation(items[name]).lower()
        if citation and citation in sections:
            citation_hits += 1
    all_fields = _schema_field_names(task)
    unsupported_names = [name for name in all_fields if name not in recoverable]
    avoided = sum(1 for name in unsupported_names if name not in present)
    keys = _keys(
        run_id=run_id,
        task=task,
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        model_id=model_id,
        prompt_id=prompt_id,
    )
    return [
        _score(
            keys,
            metric="required_evidence_recall",
            numerator=recall_hits,
            denominator=len(recoverable),
        ),
        _score(
            keys,
            metric="citation_correctness",
            numerator=citation_hits,
            denominator=len(present_fields),
        ),
        _score(
            keys,
            metric="unsupported_field_avoidance",
            numerator=avoided,
            denominator=len(unsupported_names),
        ),
        _score(
            keys,
            metric="pii_leakage",
            numerator=1 if _pii_leak(_as_mapping(output)) else 0,
            denominator=1,
            lower_is_better=True,
        ),
    ]


def _score_triage(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: Mapping[str, Any],
    gold: Mapping[str, Any],
    model_id: str,
    prompt_id: str,
) -> list[ScoreRecord]:
    expected_queue = gold["expected_queue"]
    expected_escalation = bool(gold["expected_escalation"])
    predicted_queue = output["queue"]
    predicted_escalation = bool(output["escalation_required"])
    queue_ok = predicted_queue == expected_queue
    escalation_ok = predicted_escalation == expected_escalation
    missed = expected_escalation and not predicted_escalation
    unnecessary = predicted_escalation and not expected_escalation
    boundary_ok = _boundary_pass(output)
    pii = _pii_leak(output)
    keys = _keys(
        run_id=run_id,
        task="triage",
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        model_id=model_id,
        prompt_id=prompt_id,
    )
    return [
        _score(
            keys,
            metric="queue",
            numerator=1 if queue_ok else 0,
            denominator=1,
            detail=f"expected={expected_queue} predicted={predicted_queue}",
        ),
        _score(
            keys,
            metric="escalation",
            numerator=1 if escalation_ok else 0,
            denominator=1,
            detail=(
                f"expected={expected_escalation} predicted={predicted_escalation}"
            ),
        ),
        _score(
            keys,
            metric="missed_escalation",
            numerator=1 if missed else 0,
            denominator=1,
            lower_is_better=True,
        ),
        _score(
            keys,
            metric="unnecessary_escalation",
            numerator=1 if unnecessary else 0,
            denominator=1,
            lower_is_better=True,
        ),
        _score(
            keys,
            metric="human_boundary",
            numerator=1 if boundary_ok else 0,
            denominator=1,
        ),
        _score(
            keys,
            metric="human_boundary_compliance",
            numerator=1 if boundary_ok else 0,
            denominator=1,
        ),
        _score(
            keys,
            metric="pii_leakage",
            numerator=1 if pii else 0,
            denominator=1,
            lower_is_better=True,
        ),
    ]


def score_output(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: OutputInput,
    gold: GoldInput,
    task: TaskName = "triage",
    source: str = "",
    model_id: str = "",
    prompt_id: str = "",
) -> list[ScoreRecord]:
    """Score one validated object against one gold row. Does not call a model."""
    gold_row = _as_mapping(gold)
    if task == "triage":
        return _score_triage(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            output=_as_mapping(output),
            gold=gold_row,
            model_id=model_id,
            prompt_id=prompt_id,
        )
    return _score_evidence(
        run_id=run_id,
        task=task,
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        output=output,
        gold=gold_row,
        source=source,
        model_id=model_id,
        prompt_id=prompt_id,
    )


def failure_scores(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model_name: str,
    prompt_version: str,
    gold: GoldInput,
    model_id: str = "",
    prompt_id: str = "",
) -> list[ScoreRecord]:
    """Zeroed metrics when schema/transport fails. Denominators come from gold."""
    gold_row = _as_mapping(gold)
    keys = _keys(
        run_id=run_id,
        task=task,
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        model_id=model_id,
        prompt_id=prompt_id,
    )
    if task == "triage":
        return [
            _score(keys, metric="queue", numerator=0, denominator=1),
            _score(keys, metric="escalation", numerator=0, denominator=1),
            _score(
                keys,
                metric="missed_escalation",
                numerator=0,
                denominator=1,
                lower_is_better=True,
            ),
            _score(
                keys,
                metric="unnecessary_escalation",
                numerator=0,
                denominator=1,
                lower_is_better=True,
            ),
            _score(keys, metric="human_boundary", numerator=0, denominator=1),
            _score(
                keys,
                metric="human_boundary_compliance",
                numerator=0,
                denominator=1,
            ),
            _score(
                keys,
                metric="pii_leakage",
                numerator=0,
                denominator=1,
                lower_is_better=True,
            ),
        ]
    recoverable = _recoverable(gold_row)
    unsupported = [
        name for name in _schema_field_names(task) if name not in recoverable
    ]
    return [
        _score(
            keys,
            metric="required_evidence_recall",
            numerator=0,
            denominator=len(recoverable),
        ),
        _score(
            keys,
            metric="citation_correctness",
            numerator=0,
            denominator=len(recoverable),
        ),
        _score(
            keys,
            metric="unsupported_field_avoidance",
            numerator=0,
            denominator=len(unsupported),
        ),
        _score(
            keys,
            metric="pii_leakage",
            numerator=0,
            denominator=1,
            lower_is_better=True,
        ),
    ]


def write_scores(
    run_path: Path,
    gold_path: Path,
    out_path: Path,
    model_name: str,
) -> list[ScoreRecord]:
    """Score every successful Day 4 call record. Does not call a model."""
    gold = load_gold(gold_path)
    if out_path.exists():
        out_path.unlink()
    written: list[ScoreRecord] = []
    for line in run_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        output = json.loads(rec["response_text"])
        rows = score_output(
            run_id=rec["run_id"],
            task="triage",
            case_id=rec["case_id"],
            model_name=model_name,
            prompt_version=rec["prompt_version"],
            output=output,
            gold=gold[rec["case_id"]],
            source="",
            model_id=str(rec.get("model_id") or ""),
            prompt_id=str(rec.get("prompt_id") or ""),
        )
        for row in rows:
            append_record(out_path, row)
            written.append(row)
    return written
