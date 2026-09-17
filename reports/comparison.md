# Local Model Comparison

Run `day5-full`. Both models `provider=ollama`, `temperature=0.0`, `cost_usd=0.00`.
Scorer `day5-v1`. Prompts were measured on Qwen in Days 3–4; Mistral rows are prompt-transfer.

72 scored case/model/task cells (12 × 3 × 2). Call file has 74 rows because Mistral extraction repaired E03 and E12. Token and latency figures include those repair calls. Observation count is the CallRecord count (`n`).

## Summarization

| Model | Prompt | Quality | Input tokens/case | Output tokens/case | Median latency | Max latency | Repairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen | summarize.v1 | recall 60/60; citation 63/63; invented avoided 9/12; currency 1/1; PII 0/12 | 746 | 247 | 12944 ms (n=12) | 15363 ms | 0/12 |
| Mistral | summarize.v1 transfer | recall 60/60; citation 0/63; invented avoided 9/12; currency 0/1; PII 0/12 | 875 | 281 | 12608 ms (n=12) | 15330 ms | 0/12 |

Recall is field-level against gold `recoverable_fields`. Citation must match a source heading, not a bare `"1"`. Currency is `select_current_version` on S01/S02 (expected S02).

## Extraction

Missed gold fields (`required_evidence_recall`) and invented fields (`unsupported_field_avoidance`) stay separate.

| Model | Prompt | Quality | Input tokens/case | Output tokens/case | Median latency | Max latency | Repairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen | extract.v2 | missed 71/72; invented avoided 10/12; citation 73/73; currency 1/1; PII 0/12 | 1222 | 277 | 14290 ms (n=12) | 18176 ms | 0/12 |
| Mistral | extract.v2 transfer | missed 65/72; invented avoided 2/12; citation 0/73; currency 0/1; PII 0/12 | 1533 | 373 | 15021 ms (n=14) | 18153 ms | 2/12 |

## Triage

Quality includes routing, escalation, missed escalations, unnecessary escalations, human-boundary compliance, and PII leakage.

| Model | Prompt | Quality | Input tokens/case | Output tokens/case | Median latency | Max latency | Repairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen | triage.v1 | queue 11/12; escalation 10/12; missed esc 0/12; extra esc 2/12; boundary 11/12; PII 0/12 | 437 | 119 | 5329 ms (n=12) | 9684 ms | 0/12 |
| Mistral | triage.v1 transfer | queue 8/12; escalation 10/12; missed esc 0/12; extra esc 2/12; boundary 12/12; PII 0/12 | 488 | 131 | 4851 ms (n=12) | 8348 ms | 0/12 |

Queue misses: Qwen T07; Mistral T06, T07, T08, T11. Extra escalation: T02 and T12 on both models. Qwen T06 fails human-boundary (`resolved` in the draft).

## Limits

- 12 cases per task. Counts are directional, not production-scale estimates.
- Prompt-transfer rows are labeled. This run did not retune prompts for Mistral.
- Untested in this scored run: `extract.v3`, `triage.v2`, `baseline.v0`, any adapted Mistral-only version.
- Local Ollama latency depends on this lab machine. Headline latency is median, with max and observation count.
- No provider-dollar comparison. Recorded cost is $0.00.
- These n/d counts are not a universal model ranking. They are these frozen prompts on this 12-case set.
