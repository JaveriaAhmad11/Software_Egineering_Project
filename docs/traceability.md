# Traceability Matrix - Sprint 1

| Req ID | Description | Jira | PR (org repo) | Prompt ver. | Test / evidence |
|---|---|---|---|---|---|
| FR-01 | Natural-language request via CLI | SCRUM-27, SCRUM-28 | #8 | v1.0 | `tests/test_cli.py` (10 tests), screenshots `cli_pass.png` and `cli_fail.png` |
| FR-02 | Generate Verilog-2001 with Gemini using a versioned prompt | SCRUM-23, SCRUM-24, SCRUM-25 | #2, #3, #4 | v1.0 | `tests/test_rtl_gen.py` (8 tests), `tests/test_gemini_client.py` and `tests/test_gemini_client_edge_cases.py` (6 tests), `docs/sprint1/prompt_test_results.md` |
| FR-03 | Compile and simulate with Icarus Verilog | SCRUM-26 | #7 | n/a | `tests/test_harness.py` (5 tests), `pytest_harness.png` |
| NFR-01 | No secrets in the repo | SCRUM-30 | #5 | n/a | `.gitignore`, `.env.example` |
| NFR-02 | PR review gate before merge | SCRUM-30 | #5, #7 | n/a | `branch_protection.png`, "Review required" block on PR #7 |
| NFR-03 | Timeout and bounded retry on LLM calls | SCRUM-13 | #1 | n/a | `tests/test_gemini_client.py` (retry and give-up tests) |
| AI-01 | Prompt versioning and hallucination checks | SCRUM-29 | #5 | v1.0 | `docs/sprint1/hallucination_checklist.md`, `tests/prompt_cases.json`, `tests/run_prompt_cases.py` |
| PM-01 | DoR and DoD, project requirements | SCRUM-22 | #6 | n/a | `docs/team_agreements.md`, `docs/requirements.md` |

All 29 tests pass: `python -m pytest tests -v` on Python 3.13.