"""Prompt test runner (S1-09) - Laraib Samreen.

Sends each request in prompt_cases.json to the rtl_gen agent, then checks the
Verilog against our hallucination checklist (H0-H5) and compiles it with the
verifier harness. Results go to docs/sprint1/prompt_test_results.md.
"""
import json
import re
from pathlib import Path

from agents.verifier.harness import run_verification
# TODO: 
from agents.rtl_gen.agent import generate_rtl

CASES_FILE = Path("tests/prompt_cases.json")
OUT_FILE = Path("docs/sprint1/prompt_test_results.md")
PROMPT_VERSION = "v1.0"


def get_code(result):
    """The agent may return the code or a path to the saved .v file."""
    p = Path(str(result))
    if len(str(result)) < 260 and p.suffix == ".v" and p.exists():
        return p.read_text(), p
    return str(result), None


def check_rules(code, ports):
    issues = []
    if "```" in code:
        issues.append("H5 markdown fences in output")
    if "module" not in code or "endmodule" not in code:
        issues.append("H0 missing module/endmodule")
        return issues
    if re.search(r"#\s*\d+", code):
        issues.append("H2 #delay used")
    # H3: blocking assignment inside a clocked always block (rough check)
    for block in re.findall(r"always\s*@\s*\(\s*posedge.*?endmodule|always\s*@\s*\(\s*posedge.*?\bend\b", code, re.S):
        cleaned = block.replace("<=", "").replace("==", "").replace("!=", "").replace(">=", "")
        if re.search(r"\w\s*=\s*[\w(~!{]", cleaned):
            issues.append("H3 blocking '=' in clocked block")
            break
    # H1: every requested port must appear in the module header
    header = code.split(");")[0]
    for p in ports:
        if not re.search(r"\b" + re.escape(p) + r"\b", header):
            issues.append(f"H1 missing port {p}")
    return issues


def main():
    cases = json.loads(CASES_FILE.read_text())
    rows = []
    for c in cases:
        print(f"Running {c['id']} {c['name']} ...")
        try:
            code, path = get_code(generate_rtl(c["request"]))
        except Exception as e:  # API errors, quota etc
            rows.append((c["id"], c["name"], "ERROR", str(e)[:80]))
            continue
        issues = check_rules(code, c["ports"])
        # H4: compile only (no testbench yet in Sprint 1)
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

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w") as f:
        f.write(f"# Sprint 1 Prompt Test Results (prompt {PROMPT_VERSION})\n\n")
        f.write("| Case | Name | Status | Issues |\n|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |\n")
    print("Results written to", OUT_FILE)


if __name__ == "__main__":
    main()