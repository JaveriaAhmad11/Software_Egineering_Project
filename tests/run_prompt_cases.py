"""Prompt test runner (S1-09, SCRUM-29) - Laraib Samreen.

Sends each request in prompt_cases.json to the rtl_gen agent, checks the
Verilog against the hallucination checklist (H0-H5) and compiles it with the
verifier harness. Each run is appended to docs/sprint1/prompt_test_results.md

The H0-H3/H5 rules live in agents/verifier/lint.py (SCRUM-51); this script
imports them and keeps no copy of the rules. H4 is the compile step below.

Usage (repo root, venv active):
    set RUN_BY=Laraib
    python -m tests.run_prompt_cases
"""
import json
import os
from datetime import datetime
from pathlib import Path

from agents.verifier.harness import run_verification
from agents.verifier.lint import check_rtl, format_finding
from agents.rtl_gen.agent import generate_rtl

CASES_FILE = Path("tests/prompt_cases.json")
OUT_FILE = Path("docs/sprint1/prompt_test_results.md")
PROMPT_VERSION = "v1.0"  # change when a new prompt version is used


def get_code(result):
    """The agent returns the path of the saved .v file (or the code itself)."""
    p = Path(str(result))
    if len(str(result)) < 260 and p.suffix == ".v" and p.exists():
        return p.read_text(), p
    return str(result), None


def write_results(rows):
    """Append this run as a new section; earlier runs are kept."""
    run_by = os.getenv("RUN_BY", "unknown")
    model = os.getenv("GEMINI_MODEL", "default (gemini-3.8-flash)")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    passed = sum(1 for r in rows if r[2] == "PASS")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT_FILE.exists()
    with open(OUT_FILE, "a", encoding="utf-8") as f:
        if new_file:
            f.write("# Prompt Test Results (golden set, 5 cases)\n")
        f.write(f"\n## Run {stamp} | prompt {PROMPT_VERSION} | model {model} | run by {run_by}\n\n")
        f.write(f"Result: {passed}/{len(rows)} passed\n\n")
        f.write("| Case | Name | Status | Issues |\n|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n")


def main():
    cases = json.loads(CASES_FILE.read_text())
    rows = []
    for c in cases:
        print(f"Running {c['id']} {c['name']} ...")
        try:
            code, path = get_code(generate_rtl(c["request"]))
        except Exception as e:  # API errors, timeouts, agent validation
            msg = str(e)[:80]
            print("  -> ERROR:", msg)
            rows.append((c["id"], c["name"], "ERROR", msg))
            continue
        issues = [format_finding(f) for f in check_rtl(code, c["ports"])]
        # H4: compile only (no testbench in Sprint 1)
        tmp = path or Path("tmp_case.v")
        if path is None:
            tmp.write_text(code)
        res = run_verification(tmp)
        if path is None:
            tmp.unlink()
        if not res["compiled"]:
            msg = res["errors"][0]["message"] if res["errors"] else "unknown"
            issues.append(f"H4 compile failed: {msg[:50]}")
        status = "PASS" if not issues else "FAIL"
        rows.append((c["id"], c["name"], status, "; ".join(issues) or "none"))
        print("  ->", status)

    write_results(rows)
    print("Results appended to", OUT_FILE)


if __name__ == "__main__":
    main()