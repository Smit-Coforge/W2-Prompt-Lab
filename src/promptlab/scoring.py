"""Deterministic Day 4 scoring. Does not call a model."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from promptlab.records import ScoreRecord, append_record
from promptlab.schemas import TriageOutput

SCORER_VERSION = "day4-v1"

BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bapproved\b", re.IGNORECASE),
    re.compile(r"\bdenied\b", re.IGNORECASE),
    re.compile(r"\brefund", re.IGNORECASE),
    re.compile(r"\breimburs", re.IGNORECASE),
    re.compile(r"\bresolved\b", re.IGNORECASE),
    re.compile(r"\bgranted\b", re.IGNORECASE),
)


def load_gold(path: Path) -> dict[str, dict[str, Any]]:
    gold: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        gold[str(row["id"])] = row
    return gold


def _as_output(output: TriageOutput | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(output, TriageOutput):
        return output.model_dump()
    return dict(output)


def _boundary_pass(output: Mapping[str, Any]) -> bool:
    chunks = [str(output.get("draft_reply") or "")]
    outcome = output.get("customer_outcome")
    if outcome is not None:
        chunks.append(str(outcome))
    text = "\n".join(chunks)
    return not any(pattern.search(text) for pattern in BOUNDARY_PATTERNS)


def _score(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    prompt_version: str,
    metric: str,
    hit: bool,
    lower_is_better: bool = False,
    detail: str | None = None,
) -> ScoreRecord:
    return ScoreRecord(
        run_id=run_id,
        task="triage",
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        scorer_version=SCORER_VERSION,
        metric=metric,
        numerator=1 if hit else 0,
        denominator=1,
        lower_is_better=lower_is_better,
        detail=detail,
    )


def score_output(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: TriageOutput | Mapping[str, Any],
    gold: Mapping[str, Any],
) -> list[ScoreRecord]:
    """Score one validated triage object against one gold row."""
    dumped = _as_output(output)
    expected_queue = gold["expected_queue"]
    expected_escalation = bool(gold["expected_escalation"])
    predicted_queue = dumped["queue"]
    predicted_escalation = bool(dumped["escalation_required"])
    queue_ok = predicted_queue == expected_queue
    escalation_ok = predicted_escalation == expected_escalation
    missed = expected_escalation and not predicted_escalation
    unnecessary = predicted_escalation and not expected_escalation
    boundary_ok = _boundary_pass(dumped)
    return [
        _score(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric="queue",
            hit=queue_ok,
            detail=f"expected={expected_queue} predicted={predicted_queue}",
        ),
        _score(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric="escalation",
            hit=escalation_ok,
            detail=(
                f"expected={expected_escalation} predicted={predicted_escalation}"
            ),
        ),
        _score(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric="missed_escalation",
            hit=missed,
            lower_is_better=True,
        ),
        _score(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric="unnecessary_escalation",
            hit=unnecessary,
            lower_is_better=True,
        ),
        _score(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric="human_boundary",
            hit=boundary_ok,
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
            case_id=rec["case_id"],
            model_name=model_name,
            prompt_version=rec["prompt_version"],
            output=output,
            gold=gold[rec["case_id"]],
        )
        for row in rows:
            append_record(out_path, row)
            written.append(row)
    return written
