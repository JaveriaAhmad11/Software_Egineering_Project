# Sprint 2 - Impediment Log

| Date | Owner | Impediment / Blocked Task | Resolution Status & Details |
| :--- | :--- | :--- | :--- |
| [Date] | Javeria | [Description of problem] | [Resolved / Pending - how it was fixed] |
| Nov 11, 2026 | Shamin / Javeria | `gemini-3.8-flash` model endpoint occasionally hung or timed out during live repair runs (SCRUM-47). | **Resolved.** Switched default model configuration to audited `gemini-3.5-flash-lite` with a 45s timeout and 3 retries in `.env.example`. Live repair latencies dropped to 3.7s–4.1s. |
| Nov 12, 2026 | Team Member 3 | Python 3.15 environment could not install `google-genai` due to missing `pydantic` binary wheels. | **Resolved.** Created a localized project `.venv` using Python 3.12, allowing all dependencies and tests to install and execute successfully. |
| Nov 12, 2026 | Team Member 3 | Rebuilding team repo history caused git rebase conflicts on an old commit (`SCRUM-21`) when updating Sprint 1 branch. | **Resolved.** Aborted the rebase operation and directly cherry-picked the relevant commits onto the updated `main` branch. |
| Nov 13, 2026 | Team Member 3 | Missing GitHub collaborator invitation resulted in a `403 Forbidden` error on initial direct branch push. | **Resolved.** Initially pushed changes through a fork; direct pushing permissions were restored once team collaborator access was confirmed. |
| Nov 14, 2026 | Shamin | Git pull merge conflict encountered on `docs/traceability.md` during branch sync. | **Resolved.** Discarded uncommitted local working draft via `git restore` and pulled the latest merged matrix directly from `main`. |
| Nov 14, 2026 | Team Member 3 | `SCRUM-37` (`classify_failure`) was not yet merged into `main` when the loop controller shipped (`SCRUM-46`), creating temporary logic duplication. | **Resolved.** Loop controller implemented a temporary `_classify` stand-in sharing identical rules. Wire swap scheduled immediately following `SCRUM-37` PR merge. |
