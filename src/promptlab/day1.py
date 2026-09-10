"""Day 1 local Mistral extraction run."""

from __future__ import annotations

import json
from typing import Any

import httpx

from promptlab.config import PROJECT_ROOT, Settings

DAY1_CASE_IDS: tuple[str, ...] = ("E12", "E07", "E11")
EXTRACTION_CASES_PATH = PROJECT_ROOT / "cases" / "extraction.jsonl"
BASELINE_PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "baseline.v0.md"
DEFAULT_NUM_PREDICT = 256


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


def call_mistral(settings: Settings, prompt: str, num_predict: int) -> dict[str, Any]:
    model = settings.models["mistral"]
    response = httpx.post(
        f"{settings.ollama_base_url}/api/generate",
        json={
            "model": model.model_id,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": num_predict,
            },
        },
        timeout=180.0,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


def main() -> None:
    settings = Settings.from_env()
    template = BASELINE_PROMPT_PATH.read_text(encoding="utf-8")
    cases = load_day1_cases()

    for case in cases:
        prompt = template.replace("{document_text}", case["source"])
        payload = call_mistral(settings, prompt, DEFAULT_NUM_PREDICT)
        print(f"=== {case['id']} ===")
        print(payload.get("response"))
        print()


if __name__ == "__main__":
    main()
