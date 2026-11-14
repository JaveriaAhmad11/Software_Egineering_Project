
## Benchmark Run - 2026-11-11 23:25:41
> NOTE (added 14 Nov 2026): this run came from the placeholder runner, which wrote fixed values and never called run_repair_loop or Gemini. It is not a real result. Real runs follow below.
* **Model Used:** default-gemini-model
* **Total Cases Tested:** 5

| Fault Fixture | Initial Status | Repairs Used | Final Status |
| :--- | :--- | :--- | :--- |
| functional_mutant.v | assertion_failure | 2 | PASS |
| port_fault.v | compile_error | 2 | PASS |
| syntax_fault_1.v | compile_error | 1 | PASS |
| syntax_fault_2.v | compile_error | 1 | PASS |
| syntax_fault_3.v | compile_error | 1 | PASS |

## Benchmark Run - 2026-11-14 13:15:01
* **Model Used:** gemini-3.5-flash-lite
* **Total Cases Tested:** 5
* **Repaired (PASS):** 4
* **Not repaired (recorded as failures):** 1
* **Gemini attempts:** 4 (failed attempts: 0)
* **Average latency per successful call:** 3.5 s

| Fault Fixture | Initial Status | Repairs Used | Final Status | Gemini attempts | Failed attempts | Avg latency (s) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| functional_mutant.v | assertion_failure | 1 | PASS | 1 | 0 | 5.4 |
| port_fault.v | testbench_error | 0 | FAIL (testbench_error) | 0 | 0 | - |
| syntax_fault_1.v | compile_error | 1 | PASS | 1 | 0 | 2.3 |
| syntax_fault_2.v | compile_error | 1 | PASS | 1 | 0 | 3.5 |
| syntax_fault_3.v | compile_error | 1 | PASS | 1 | 0 | 2.9 |

