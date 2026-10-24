# Sprint 1 Planning Notes

- **Date:** Monday 19 Oct 2026
- **Attendees:** Laraib (SM), Javeria (PO), Shamin (Dev), Areesha (Dev)
- **Sprint dates:** 19 Oct - 23 Oct 2026
- **Committed points:** 31 Story Points

## Sprint goal
A user types a hardware request in plain English. The system calls Gemini
with a versioned prompt, saves a Verilog module, compiles it with Icarus
Verilog and reports PASS/FAIL, with Jira-GitHub traceability.

## Decisions
1. Only two agents this sprint: `rtl_gen` and `verifier`. The other four
   stay in the backlog for Sprints 2-4.
2. Nobody pushes to `main`. Work goes through `feature/SCRUM-xx` branches,
   PR title starts with the Jira ID, one reviewer must approve.
3. Standup every day at [time], 10 minutes.
4. Late start: the sprint began on 19 Oct, not 12 Oct. Noted as a lesson.

## Allocation
| Member | Stories | Points |
|---|---|---|
| Javeria | Backlog grooming, DoR/DoD + AC | 5 |
| Shamin | Gemini client, prompt v1.0, rtl_gen agent | 10 |
| Areesha | Verifier harness, CLI, pytest tests | 9 |
| Laraib | Prompt tests, sprint tracking, traceability | 7 |