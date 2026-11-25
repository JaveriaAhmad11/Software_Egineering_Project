# Javeria — Sprint 3 notes (SCRUM-48, SCRUM-56, SCRUM-58)

## Decisions confirmed on 25 Nov
- Package path: agents/spec_intake/ (underscore; the PDF's "spec intake" with a space is a typo).
- Prompt version exposure: module constant `PROMPT_VERSION` in agent.py; run_pipeline reads it. Agreed with Shamin: <yes/no>.
- --pipeline stage output: `progress(stage, message)` callback. Agreed with Shamin: <yes/no>.
- port_signature import path: DOES NOT EXIST YET. Must be created in agents/verifier/port_signature.py during SCRUM-56.
- port_signature returns: TBD (will implement to return {name: (direction, width)}).
- Open question for team: Plan says "existing port_signature" but it does not exist in main. Will create it as a shared helper.
- Jira: SCRUM-48 = Spec intake agent (S3-03, 5 pts)
         SCRUM-56 = Spec schema/render/port contract (S3-04, 3 pts)
         SCRUM-58 = CLI --pipeline (S3-11, 2 pts)
- Open question for PO (Laraib): SCRUM-58 tagged EPIC-4 Repair Loop; confirm tag
  before traceability (S3-10).
- Order agreed: SCRUM-56 first (unblocks S3-07/S3-09), then SCRUM-48, then SCRUM-58.

## Day plan
- 26 Nov: SCRUM-56 schema.py + tests + PR (request Areesha).
- 27 Nov: SCRUM-48 prompt v1.0 + agent.py + mocked tests + one real run + PR.
- 28 Nov: SCRUM-58 main.py --pipeline + fake-pipeline tests + PR.
- 29 Nov: merge, full-suite evidence, Jira evidence comments, hand-off to Shamin.

## Evidence for PO acceptance
- SCRUM-48: tests/test_spec_intake.py green; real spec dict for
  "8-bit counter with enable" pasted in the Jira comment.
- SCRUM-56: tests/test_spec_schema.py green; check_ports flags the port_fault.v case.
- SCRUM-58: tests/test_cli_pipeline.py green; `python main.py "8-bit counter" --pipeline`
  output attached (real if S3-09 merged, else clearly labelled fake).