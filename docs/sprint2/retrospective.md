# Sprint 2 - Retrospective & Review Notes

## What Went Well
* **Automated & Closed-Loop Repair:** The closed-loop repair engine is fully functional. Both syntax errors and runtime functional assertion failures are self-healed by Gemini in $\le 2$ iterations without human input.
* **Rigorous Testing & Review Ring:** The review ring with Javeria, Shamin, Laraib, and Areesha worked effectively, and unit tests caught real bugs. All 137 unit tests pass project-wide.
* **Guardrails & Classification:** The port-invariance guard successfully prevents the LLM from mutating module interfaces or port names during repairs. `classify_failure` covers all six failure conditions cleanly.
* **Offline Mocking:** All modular tests run offline using mocked clients without requiring active API keys.

## What Could Be Improved / Honest Findings
* **Sprint Timeline Slipped:** Sprint 2 took longer than planned due to model audit testing, dependency alignments (Python 3.12 vs 3.15 wheel constraints), and exam week shifts.
* **Placeholder Test Runner Artifacts:** Placeholder results initially went into the results file and tests wrote directly into the live logs before Javeria refactored `tests/run_repair_cases.py`.
* **Duplication & Wiring Gaps:** 
  * `classify_failure` was temporarily duplicated by a loop controller stand-in until fully swapped.
  * Generated testbenches in `--repair full-generate` mode remain unvalidated against a golden reference (a risk if the testbench itself has bugs).
  * `check_testbench` has not yet been wired into the live pipeline.

## Team Retro Inputs Summary
* **Shamin:** Review ring worked well; tests caught real bugs; placeholder log writes and exam week caused delays. Tag commits with correct Jira IDs (e.g., SCRUM-36).
* **Javeria:** Closed-loop engine works smoothly under audit model (`gemini-3.5-flash-lite`); benchmark runner refactored to call live loop; unvalidated testbench generation needs a dedicated Sprint 3 story.
* **Laraib:** Review ring PR approvals kept code quality high; board setup enabled smooth tracking after exam delays.
* **Areesha:** Harness classification handles all six failure categories cleanly (`ok`, `compile_error`, `testbench_error`, `assertion_failure`, `timeout`, `tool_missing`), but requires swapping into the main loop during Sprint 3.