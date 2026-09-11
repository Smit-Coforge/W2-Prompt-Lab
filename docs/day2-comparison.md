# Day 2 local model comparison

Both models ran locally through Ollama, so the configured provider charge is 0.0 for every record. This comparison uses success counts, token totals, and latency only; it does not invent a dollar price.

## mistral:7b

- Successful cases: 12
- Truncated cases: 0
- Attempts recorded: 12
- Total input tokens: 2787
- Total output tokens: 1142
- Median latency_ms: 5768.0
- Max latency_ms: 8438
- Mean latency_ms: 6056.2

## qwen3:8b

- Successful cases: 0
- Truncated cases: 12
- Attempts recorded: 12
- Total input tokens: 2427
- Total output tokens: 3072
- Median latency_ms: 14326.5
- Max latency_ms: 14908
- Mean latency_ms: 14295.7

## Observation

mistral:7b completed all 12 cases under the 256-token ceiling (median 5768.0 ms, max 8438 ms). qwen3:8b returned TruncatedResponseError on every case, always using 256 output tokens, with higher median and max latency (14326.5 ms and 14908 ms). A short successful Mistral run therefore underestimates Qwen workload: thinking-style generation consumed the fixed output budget before a usable answer appeared. Both models have a provider charge of 0.0; the useful comparison is tokens and latency, not dollars.
