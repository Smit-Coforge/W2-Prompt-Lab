# Day 3 notes

Scored run: `840a16c3-3929-4da4-bed0-b75691a4c7ad` (`qwen3:8b`, temperature 0.0, `max_output_tokens` 512). Twelve summarization cases used `summarize.v1.md`; twelve extraction cases used `extract.v2.md`. Every case validated on attempt 1.

- Summarization repair rate: 0 / 12
- Extraction repair rate: 0 / 12
- Example leakage count: 0
- Citation-existence failure count: 0

Leakage: extraction `response_text` was searched for distinctive strings that appear in the two `extract.v2.md` example documents (Northglass, Norwyn, Bellwater, Redhaven, East Kestrel, Article A/B/C, Part I/II, Schedule Z, 18 percent, 24 percent) and not in `cases/extraction.jsonl`. None of those strings appeared in the twelve extraction outputs.

Citation-existence: every evidence field with `status: "present"` used `citation` (not `section`). Each citation matched a numbered or titled heading in that case's source document (136 present fields, 0 misses).

Passing schema checks is not the same as getting the document right. S01's source says version 1.0 was superseded by 2.0, but the model still set `document_status` to `"valid"`. That is a legal value, so `complete_structured` accepted it and the citation check passed too. E01 has the same kind of sentence and got `"superseded"`. That looks like the model being inconsistent, not a JSON/schema failure.

`response_text` in the JSONL is a string on purpose. Day 1's `CallRecord` stores the raw model output as text, and we were not supposed to change `usage.py`. `complete_structured` parses that string into the Pydantic object in memory; the log just keeps the original text.

The most common validation error on the first live pass was a JSON decode failure after `TruncatedResponseError`. The model copied the JSON Schema `$defs` block until it hit the 256-token limit, so we never got a real filled object. After I shortened `schema_description` to a field map, turned thinking off, and raised the output cap to 512, the scored run did not need a semantic repair.
