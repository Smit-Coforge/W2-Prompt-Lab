"""Day 1 local Mistral extraction run."""

from __future__ import annotations

import json
from typing import Any

from promptlab.config import PROJECT_ROOT

DAY1_CASE_IDS: tuple[str, ...] = ("E12", "E07", "E11")
EXTRACTION_CASES_PATH = PROJECT_ROOT / "cases" / "extraction.jsonl"


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


def main() -> None:
    cases = load_day1_cases()
    print("selected cases:", ", ".join(case["id"] for case in cases))


if __name__ == "__main__":
    main()
