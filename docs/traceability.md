# Traceability Matrix — Sprint 1

| Req ID | Description | Story (Jira) | Branch / PR | Prompt Ver. | Test / Verification Evidence |
| **FR-01** | Natural language hardware request input via CLI | **SCRUM-27** | `feature/SCRUM-27-cli-runner`<br>(PR #5) | v1.0 | Terminal screenshot running `python main.py "8-bit counter"` |

| **FR-02** | Generate synthesizable Verilog-2001 using Gemini | **SCRUM-25**<br>(Prompt: SCRUM-24) | `feature/SCRUM-25-rtl-gen-agent`<br>(PR #2) | v1.0 | `docs/sprint1/prompt_test_results.md` (5 test cases benchmarked) |

| **FR-03** | Compile and verify hardware output using Icarus Verilog | **SCRUM-26** | `feature/SCRUM-26-verifier-harness`<br>(PR #4) | n/a | Terminal output showing `pytest tests/test_harness.py` (5 tests passed) |

| **NFR-01**| Secret Hygiene (No plain API keys or secrets in repo) | **SCRUM-21** | `feature/SCRUM-21-pr-template`<br>(PR #1) | n/a | `.gitignore` and `.env.example` committed to repo |

| **NFR-02**| Code Quality & PR Review Gate before merging to `main` | **SCRUM-21** / **SCRUM-30** | `feature/SCRUM-30-sprint-tracking`<br>(PR #3) | n/a | GitHub branch protection ruleset screenshot (`branch_protection.png`) |

| **AI-01** | Prompt Versioning and Hallucination Checklist | **SCRUM-29** | `feature/SCRUM-29-prompt-suite`<br>(PR #3) | v1.0 | `docs/sprint1/hallucination_checklist.md` (H0–H5 failure tags) |