# Team Agreements & Governance Policies (VeriLoop)

## Definition of Ready (DoR)
A user story is considered "Ready" for sprint backlog intake only when:
1. It follows the standard format: As a <role>, I want <feature>, so that <benefit>.
2. Fibonacci story points have been estimated and assigned.
3. At least 2 testable Acceptance Criteria (Given/When/Then format) are explicitly stated.
4. All external code and module dependencies are resolved.
5. An individual team owner is assigned.

## Definition of Done (DoD)
A user story is considered "Done" only when:
1. Code is merged into `main` via a Pull Request (PR) approved by at least 1 teammate.
2. Commit messages and PR titles reference the exact Jira ticket ID (e.g., `SCRUM-25`).
3. Unit test coverage passes via `pytest`.
4. Acceptance Criteria are validated and signed off by the PO (Javeria).
5. Environment secrets (`.env`) are excluded from Git tracked files.
6. Associated documentation and traceability entries are updated.
7. Jira ticket status is updated to "Done".