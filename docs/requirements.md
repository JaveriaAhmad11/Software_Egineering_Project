# Sprint 2 - System Requirements & Constraints

## Functional Requirements
* **FR-01:** The verification harness must automatically classify simulation outputs into distinct categories (`ok`, `compile_error`, `testbench_error`, `assertion_failure`, `timeout`, `tool_missing`).
* **FR-02:** The repair loop must invoke the repair agent and re-verify code up to a maximum bound of 3 repair attempts.
* **FR-03:** The repair agent must enforce a port-invariance guard ensuring module names and port lists remain completely identical to the original design.

## Non-Functional Requirements
* **NFR-01:** Unit tests for components must execute successfully offline using mocked clients without requiring active API keys.

## AI Constraints
* **AIR-01:** Repair prompt generation must strictly enforce Verilog-2001 standards, prohibit `#delay` primitives, and output a single code block.