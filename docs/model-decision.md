# Model Decision Record

Evidence from run `day5-full`, scorer `day5-v1`, `cost_usd=0.00`.
Prompts were measured on Qwen in Days 3–4. Mistral used the same files (transfer). Frozen files were not edited after the run.

## Summarization

- Evidence (summarize.v1): Qwen recall 60/60, citation 63/63, invented avoided 9/12, currency 1/1, PII 0/12, repairs 0/12, median latency 12944 ms (n=12). Mistral transfer recall 60/60, citation 0/63, invented avoided 9/12, currency 0/1, PII 0/12, repairs 0/12, median latency 12608 ms (n=12).
- Decision: Qwen with `summarize.v1`.
- Reason: same recall, Qwen citations match source headings; Mistral transfer cited `"1"` and the currency rule could not read list-valued dates.
- Rejected alternatives: Mistral + summarize.v1 transfer (citation 0/63); writing a new Mistral prompt without measuring it; `baseline.v0`.
- Reopen if: a Mistral-adapted prompt version records citation close to 63/63 on the same 12 cases, or the case set grows past this 12-row sample.

## Extraction

- Evidence (extract.v2): Qwen missed-field recall 71/72, invented avoided 10/12, citation 73/73, currency 1/1, PII 0/12, repairs 0/12, median latency 14290 ms (n=12). Mistral transfer recall 65/72, invented avoided 2/12, citation 0/73, currency 0/1, PII 0/12, repairs 2/12, median latency 15021 ms (n=14).
- Decision: Qwen with `extract.v2`.
- Reason: fewer missed gold fields and citations that name real headings. Mistral invented more (avoidance 2/12) and did not produce usable heading citations on this prompt.
- Rejected alternatives: Mistral + extract.v2 transfer; `extract.v3` (not in this scored run); collapsing missed and invented into one number.
- Reopen if: an adapted Mistral extract version is measured with heading citations and recall at least 71/72 on these cases, or gold field mix changes.

## Triage

- Evidence (triage.v1): Qwen queue 11/12, escalation 10/12, missed escalation 0/12, extra escalation 2/12, human-boundary 11/12, PII 0/12, median latency 5329 ms (n=12). Mistral transfer queue 8/12, escalation 10/12, missed 0/12, extra 2/12, human-boundary 12/12, PII 0/12, median latency 4851 ms (n=12).
- Decision: Qwen with `triage.v1`.
- Reason: routing 11/12 vs 8/12 on the same frozen prompt. Escalation extras match (T02, T12). Boundary: Mistral 12/12; Qwen 11/12 on T06 (`resolved` in a draft that still goes to a human — same Day 4 hit). That is recorded, not hidden. `triage.v1.md` was not edited after scoring.
- Rejected alternatives: Mistral + triage.v1 transfer (queue 8/12); `triage.v2` (Day 4 did not improve queue and is not in this Day 5 run); editing `triage.v1.md` after seeing scores.
- Reopen if: a new prompt version (not an edit of v1) gets Qwen T06 past the boundary scorer without dropping queue below 11/12, or Mistral transfer queue reaches 11/12 on these 12 cases.

## Review triggers

- Gold labels or case set change.
- Either model is swapped or `temperature` is not 0.0.
- A new prompt version is recorded for one model (must be labeled adapted, not transfer).
- Hardware change that would invalidate latency comparisons (quality counts would still stand).
