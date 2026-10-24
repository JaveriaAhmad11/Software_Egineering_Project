# VLSI Design Assistant

An agentic software system that uses LLM-assisted generation to produce Verilog RTL modules from natural-language hardware specifications, verified through deterministic simulation (Icarus Verilog / Verilator) before any output is accepted.

## Problem

Unlike most agentic AI applications, RTL design has a deterministic, non-LLM ground truth: a Verilog module either compiles and passes simulation, or it doesn't. This project uses that property to build a verification-first agent pipeline, where an LLM's generated output is always treated as a hypothesis to be tested — never as a final answer.

## Architecture — Six Agents

1. **Spec Intake Agent** — Converts a natural-language hardware requirement into a structured design spec (I/O ports, timing constraints, target FSM behavior).
2. **RTL Generation Agent** — Uses the Gemini API to generate a Verilog module from the structured spec.
3. **Testbench Agent** — Generates or selects a testbench for the module under test.
4. **Verifier Agent** — Runs Icarus Verilog / Verilator against the generated RTL and testbench, returning a structured pass/fail report.
5. **Repair Agent** — Takes the Verifier's structured failure report and produces a patched RTL version, looping back to the Verifier (bounded retries).
6. **Report & Commit Agent** — Produces a design rationale document for the verified module and prepares the final commit.
Spec Intake → RTL Generation → Testbench → Verifier ⇄ Repair (loop until pass) → Report & Commit

## Tech Stack

- Python
- Google GenAI SDK 2.0 (Gemini API, `gemini-3.8-flash` via the Interactions API)
- Icarus Verilog / Verilator (RTL simulation and verification)

## Project Structure
agents/
spec_intake/ rtl_gen/ testbench/ verifier/ repair/ report/
test_gemini_connection.py # Sprint 1: verifies the Gemini API connection
requirements.txt
.env # local only — holds GEMINI_API_KEY, never committed

## Setup

1. `pip install -r requirements.txt`
2. Create a `.env` file with `GEMINI_API_KEY=<your key>` (get one at https://aistudio.google.com/apikey)
3. Run `python test_gemini_connection.py` to verify the connection

## Status

**Sprint 1 (current):** repository scaffolding and a working Gemini API connection.
Later sprints implement each agent, the Verilog simulation loop, and the end-to-end pipeline.
## Verifier and CLI (Sprint 1)

### Install Icarus Verilog (`iverilog`, `vvp`)

The verifier harness (`agents/verifier/harness.py`) needs Icarus Verilog 12 or newer.

**Windows**
1. `winget install Icarus.Verilog` (if the download is blocked on your network, use a mobile hotspot for the install).
2. If `iverilog` is not recognised, add it to PATH: `[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\iverilog\bin", "User")`
3. Restart your terminal and VS Code.

**Ubuntu / WSL:** `sudo apt install iverilog`

Check the install with `iverilog -V` and `vvp -V`. The harness also looks in `C:\iverilog\bin` and the usual Program Files folders if PATH is not set.

### Run the CLI

```
pip install -r requirements.txt            # on Windows: py -m pip install -r requirements.txt
python main.py "8-bit counter"             # generate with Gemini, then compile with iverilog
python main.py "8-bit counter" --tb tb.v   # also simulate with a testbench
python main.py --verify design.v --tb tb.v # verify an existing file, no API call
```

The CLI prints a PASS/FAIL summary and exits 0 (PASS), 1 (FAIL) or 2 (error, e.g. missing `GEMINI_API_KEY`). A testbench reports a mismatch by printing the word `FAIL`.

### Run the tests

```
python -m pytest -v        # on Windows: py -m pytest -v
```

All tests run without an API key: the LLM is mocked, and the iverilog tests skip themselves if iverilog is not installed.
