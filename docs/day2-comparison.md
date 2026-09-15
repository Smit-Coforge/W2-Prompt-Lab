# Day 2 local model comparison

## mistral:7b

- Successful cases: 12 / 12
- Token totals: 2787 input, 1142 output
- Median latency: 5768 ms
- Max latency: 8438 ms

## qwen3:8b

- Successful cases: 0 / 12
- Token totals: 2427 input, 3072 output
- Median latency: 14326.5 ms
- Max latency: 14908 ms

## Observation

Mistral finished every case under the 256-token ceiling (`stop_reason` `stop`, 67–126 output tokens). Qwen hit `TruncatedResponseError` on every case: `stop_reason` `length`, exactly 256 output tokens, and almost no usable `response_text`. On S01, the shared prompt produced a finished Mistral answer in 8438 ms (124 output tokens) while Qwen used the full 256-token budget in 14908 ms and still returned empty visible text. A short successful Mistral run therefore underestimates Qwen workload: thinking-style generation consumed the fixed output budget before an answer appeared. The useful comparison is tokens and latency, not dollars.
