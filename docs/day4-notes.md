# Day 4 notes

Scored run: `e9131960-374e-483b-86fb-5119e9c3ed3c` (`qwen3:8b`, temperature 0.0, `max_output_tokens` 512). Both prompt versions used the same 12 rows in `cases/triage.jsonl`. Provider/API cost is $0.00.

## triage.v1

- queue correct: 11/12
- escalation correct: 10/12
- missed escalations: 0
- unnecessary escalations: 2
- human-boundary passes: 11/12

T07 went to `complaint` instead of gold `escalate`. T02 and T12 set `escalation_required` true on clear fraud cases. T06's draft said the issue would be "resolved properly"; the scorer treats `resolved` as a final-outcome word, so that case fails the boundary check even though the reply still sends it to a human.

## triage.v2

- queue correct: 11/12
- escalation correct: 9/12
- missed escalations: 0
- unnecessary escalations: 3
- human-boundary passes: 12/12

Same T07 queue miss. Same extra escalations on T02 and T12, plus T09. No draft hit the boundary phrases.

## Comparison

- changed-queue count: 0/12
- observation count: 24 model calls (12 cases × 2 prompts)
- output tokens per case (v1 / v2): T01 136/171, T02 94/176, T03 106/170, T04 122/183, T05 140/176, T06 127/165, T07 131/183, T08 127/182, T09 122/184, T10 109/171, T11 108/166, T12 107/173
- output-token total: v1 1429, v2 2100, difference +671
- median latency: v1 5368.5 ms, v2 7771 ms
- max latency: v1 10378 ms, v2 11103 ms

The analysis field did not change any queue. Escalation got one more false positive. Tokens and wait time both went up. A 12-case set cannot prove v2 is better or worse in general. For this run, the extra field did not earn the extra overhead.
