# Standup Log — Sprint 1

> Compiled on 23 Oct from team chat and personal notes.

## Day 1 — Mon 19 Oct
- **Laraib (SM):** Set up Sprint 1 in Jira, configured PR template, set up Git on laptop. Blocker: `git` not recognized on Windows (installed Git for Windows).
- **Javeria (PO):** Created 4 epics and 11 stories with Fibonacci story points in Jira backlog. Blocker: None.
- **Shamin (Dev):** Verified Gemini API key in Google AI Studio, started `gemini_client.py` wrapper. Blocker: None.
- **Areesha (Dev):** Installed Icarus Verilog locally. Blocker: `iverilog` command not on Windows PATH (added `C:\iverilog\bin`).

---

## Day 2 — Tue 20 Oct
- **Laraib (SM):** Drafted 5 hardware prompt test cases (`prompt_cases.yaml`) and created the H0–H5 hallucination checklist. Blocker: `pip install pyyaml` failed on Python 3.15 alpha (resolved by writing built-in test runner).
- **Javeria (PO):** Documented team Definition of Ready (DoR) and Definition of Done (DoD) in `team_agreements.md`. Added Given/When/Then acceptance criteria to all stories. Blocker: None.
- **Shamin (Dev):** Wrote system prompt v1.0 (`prompts/rtl_gen/v1.0.md`) enforcing synthesizable Verilog-2001 and non-blocking assignments (`<=`). Blocker: None.
- **Areesha (Dev):** Finished `harness.py` and test fixtures (`counter_good.v`, `counter_bad.v`, `hang_tb.v`). Tested compilation locally. Blocker: None.

---

## Day 3 — Wed 21 Oct
- **Laraib (SM):** Took mid-sprint burndown snapshot (`burndown_day3.png`). Resolved GitHub merge conflict on PR template. Reviewed and approved Shamin's PRs. Blocker: None.
- **Javeria (PO):** Verified story status transitions on Jira board. Drafted requirements list (FR-01 to FR-03) for the traceability matrix. Blocker: None.
- **Shamin (Dev):** Completed `rtl_gen/agent.py` and submitted 3 PRs (`SCRUM-23`, `SCRUM-24`, `SCRUM-25`) in order for peer review. Blocker: Needed teammate review before merge.
- **Areesha (Dev):** Completed `tests/test_harness.py` pytest suite with 5 test cases covering successful compile, syntax error reporting, and simulation timeout. Blocker: None.

---

## Day 4 — Thu 22 Oct
- **Laraib (SM):** Ran `python tests/run_prompt_cases.py` benchmark suite. Logged results in `prompt_test_results.md` and captured terminal test evidence. Blocker: None.
- **Javeria (PO):** Tested the end-to-end vertical slice against Acceptance Criteria. Verified that generated `.v` files compile without syntax errors. Blocker: None.
- **Shamin (Dev):** Checked Gemini output formatting to ensure regex cleanly strips markdown backticks before saving to disk. Blocker: None.
- **Areesha (Dev):** Integrated CLI runner (`main.py`) chaining `rtl_gen` with `harness.py` to print a terminal PASS/FAIL summary. Blocker: None.

---

## Day 5 — Fri 23 Oct
- **Laraib (SM):** Facilitated Sprint Review and Retrospective. Captured final burndown chart and recorded velocity (31/31 points completed).
- **Javeria (PO):** Formally accepted all 11 Sprint 1 user stories as Done in Jira. Groomed backlog priorities for Sprint 2.
- **Shamin (Dev):** Tagged prompt version v1.0 in docs and documented model latency.
- **Areesha (Dev):** Confirmed all pytest tests pass on clean repo clone without requiring a live API key.