# Sprint 2 - Model, Token and Latency Audit (SCRUM-47)

Owner: Shamin (PO). Started 12 Nov 2026.
Status: AC1 and AC2 done. AC3 (benchmark summary) is pending the S2-04 benchmark runner.
Rule: only real runs are recorded here, including failures.

## 1. Default model decision (AC1)

Test: 3 calls per model, prompt "Reply with the single word OK.", 30 s timeout, 3 retries, one machine, 11 Nov 2026.

| Model | Calls succeeded | What happened |
|---|---|---|
| gemini-3.8-flash | 0 of 3 | All 9 attempts ended in APITimeoutError (one attempt took 77.5 s) |
| gemini-3.5-flash-lite | 3 of 3 | Latencies 5.4 s, 9.4 s, 10.2 s. One call needed a second attempt after a 31.7 s timeout |

Limits of this evidence: small sample, one machine, one evening. Each teammate should repeat the same test before the sprint review.

Decision (documented in .env.example and set in agents/gemini_client.py):
- Default model: gemini-3.5-flash-lite
- Timeout: 45 s per attempt (30 s was too tight for the good model)
- Retries: 3

Finding: the 30 s timeout is not a hard cap. The SDK retries inside an attempt, so single attempts ran for 62.9 s and 77.5 s. One generate() call can take several minutes before it fails.

## 2. Per-call logging (AC2)

Each attempt is logged and stored in client.stats with model, attempt number, latency, and token counts (input, output, total). A missing usage field never fails a call. Covered by 3 unit tests.

Real log line (copied from logs/gemini.log, not edited):

2026-11-12 22:24:20,774 INFO OK model=gemini-3.5-flash-lite attempt=1/3 latency=16.0s prompt_chars=60 reply_chars=21 input_tokens=12 output_tokens=5 total_tokens=17

## 3. Other findings

- A stale GEMINI_API_KEY environment variable in the terminal overrode the key in .env and caused a 401 error. Fixed by removing the variable. python-dotenv does not replace variables that are already set.
- Unit tests were writing fake lines into the real logs/gemini.log (test red run: file grew from 16690 to 16851 bytes). Fixed with tests/conftest.py.
- test_gemini_connection.py (Sprint 0 script) hardcoded gemini-3.8-flash and failed for everyone. It now uses the shared GeminiClient and the audited defaults; verified with a real call on 14 Nov 2026 (model=gemini-3.5-flash-lite, latency 5.9 s).

## 4. AC3 benchmark summary (real run, 14 Nov 2026 13:15)

Source: python -m tests.run_repair_cases, results in docs/sprint2/repair_results.md. Model: gemini-3.5-flash-lite, 45 s timeout.

| Measure | Value |
|---|---|
| Cases run | 5 |
| Repaired (PASS) | 4 |
| Not repaired | 1 (port_fault.v: testbench_error, the port guard forbids the only fix, so Gemini was never called) |
| Gemini calls | 4 (1 per repaired case), 0 failed |
| Average latency per call | 3.5 s (5.4, 2.3, 3.5, 2.9) |
| Tokens per call | 735 to 792 total (about 660 to 716 in, 76 out) |

Limits: 5 small cases on one counter design, single run, one machine. The first live attempt crashed because the benchmark branch did not yet have the client's stats field (unit tests used a fake client); fixed by merging the SCRUM-47 branch.
