# Local Model Comparison

Run `day5-full`. Both models `provider=ollama`, `temperature=0.0`, `cost_usd=0.00`.
Scorer `day5-v1`. Prompts were measured on Qwen in Days 3–4; Mistral rows are **transfer**.

72 scored case/model/task cells (12 × 3 × 2). Call file has 74 rows because Mistral extraction repaired E03 and E12 (extra `complete()` calls). Token and latency figures include those repair calls. Observation count is the number of CallRecords.

## Summarization (`summarize.v1`)

**Qwen — summarize.v1 (original)**

- Quality: recall 60/60; citation 63/63; invented avoided 9/12; currency 1/1; PII 0/12
- Input tokens/case: 746
- Output tokens/case: 247
- Median latency: 12944 ms (n=12)
- Max latency: 15363 ms
- Repairs: 0/12

**Mistral — summarize.v1 transfer**

- Quality: recall 60/60; citation 0/63; invented avoided 9/12; currency 0/1; PII 0/12
- Input tokens/case: 875
- Output tokens/case: 281
- Median latency: 12608 ms (n=12)
- Max latency: 15330 ms
- Repairs: 0/12

Recall is field-level against gold `recoverable_fields`, not a 12-case percent. Citation requires the citation string to match a source heading (`1. Meeting Notes`), not a bare `"1"`. Currency is `select_current_version` on the S01/S02 pair (expected S02). Mistral returned version/date values as lists, so the Python rule selected none.

S05 and S12 are unsupported documents (meeting notes / newsletter). Gold recoverable field is title only; remaining nulls are expected. Mistral S05 marked the meeting date present; Qwen S12 marked newsletter “purpose” present.

## Extraction (`extract.v2`)

Missed evidence and invented evidence are separate metrics. Do not fold them into one score.

**Qwen — extract.v2 (original)**

- Quality: missed (recall) 71/72; invented avoided 10/12; citation 73/73; currency 1/1; PII 0/12
- Input tokens/case: 1222
- Output tokens/case: 277
- Median latency: 14290 ms (n=12)
- Max latency: 18176 ms
- Repairs: 0/12

**Mistral — extract.v2 transfer**

- Quality: missed (recall) 65/72; invented avoided 2/12; citation 0/73; currency 0/1; PII 0/12
- Input tokens/case: 1533
- Output tokens/case: 373
- Median latency: 15021 ms (n=14)
- Max latency: 18153 ms
- Repairs: 2/12

Qwen missed fewer gold fields (71/72 vs 65/72) and cited real headings (73/73 vs 0/73). Mistral invented more fields (avoidance 2/12 vs 10/12). Currency on E01/E02 (expected E02): Qwen 1/1, Mistral 0/1 for the same list-valued date reason as summarization.

## Triage (`triage.v1`)

**Qwen — triage.v1 (original)**

- Quality: queue 11/12; escalation 10/12; missed esc 0/12; extra esc 2/12; boundary 11/12; PII 0/12
- Input tokens/case: 437
- Output tokens/case: 119
- Median latency: 5329 ms (n=12)
- Max latency: 9684 ms
- Repairs: 0/12

**Mistral — triage.v1 transfer**

- Quality: queue 8/12; escalation 10/12; missed esc 0/12; extra esc 2/12; boundary 12/12; PII 0/12
- Input tokens/case: 488
- Output tokens/case: 131
- Median latency: 4851 ms (n=12)
- Max latency: 8348 ms
- Repairs: 0/12

Queue misses: Qwen T07 (`complaint` vs gold `escalate`). Mistral T06/T07/T08 (gold `escalate`) and T11 (`account_servicing` vs `card_dispute`). Escalation: both extra-escalate T02 and T12; no missed escalations. Human-boundary: Mistral 12/12. Qwen 11/12 on T06 (`resolved` in the draft; same Day 4 scorer hit). PII 0/12 both.

## Limits

- 12 cases per task. Counts are directional, not production-scale estimates.
- Prompt-transfer rows are labeled. This run did not retune prompts for Mistral.
- Untested in this scored run: `extract.v3`, `triage.v2`, `baseline.v0`, any adapted Mistral-only version.
- Local Ollama latency depends on this lab machine. Headline latency is median, with max and observation count. Mean latency is not the headline.
- No provider-dollar comparison. Recorded cost is $0.00.
- 11/12 vs 8/12 on this set is not a universal model ranking. It is Qwen vs Mistral on these frozen prompts.
- Citation 0/63 on Mistral transfer is that prompt’s heading format on Mistral, not “Mistral cannot cite.”
