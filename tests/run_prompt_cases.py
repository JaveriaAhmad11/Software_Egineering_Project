"""Prompt test runner (S1-09 / SCRUM-29, pipeline mode SCRUM-53) - Laraib Samreen.

Default mode (Sprint 1): sends each request in prompt_cases.json to the rtl_gen agent, checks the
Verilog against the hallucination checklist (H-rules from the shared lint module) and compiles it
with the verifier harness. Each run is appended to docs/sprint1/prompt_test_results.md

Pipeline mode (Sprint 3): runs every case through agents.pipeline.run_pipeline (spec, RTL,
testbench, verify and repair, lint, report) and appends a dated section to
docs/sprint3/pipeline_results.md

Usage (repo root, venv active):
    set RUN_BY=Laraib
    python -m tests.run_prompt_cases                         Sprint 1 mode, all cases
    python -m tests.run_prompt_cases --only PC-01,PC-03      a subset of the cases
    python -m tests.run_prompt_cases --pipeline              Sprint 3 mode, all cases
    python -m tests.run_prompt_cases --pipeline --only PC-07
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from agents.gemini_client import GeminiConfigError
from agents.rtl_gen.agent import generate_rtl
from agents.verifier.harness import run_verification
from agents.verifier.lint import as_text, check_rtl

CASES_FILE = Path("tests/prompt_cases.json")
OUT_FILE = Path("docs/sprint1/prompt_test_results.md")
PIPELINE_OUT_FILE = Path("docs/sprint3/pipeline_results.md")
PROMPT_VERSION = "v1.0"  # rtl_gen prompt used by the Sprint 1 mode; change with a new version


# ---- shared helpers ------------------------------------------------------------------------

def load_cases(only=None, path=CASES_FILE):
    """Read the golden set; `only` is a comma-separated list of case ids (e.g. 'PC-01,PC-03')."""
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if only:
        wanted = {x.strip().upper() for x in only.split(",") if x.strip()}
        unknown = sorted(wanted - {c["id"].upper() for c in cases})
        if unknown:
            raise ValueError(f"unknown case id(s): {', '.join(unknown)}")
        cases = [c for c in cases if c["id"].upper() in wanted]
    return cases


def get_code(result):
    """The agent returns the path of the saved .v file (or the code itself)."""
    p = Path(str(result))
    if len(str(result)) < 260 and p.suffix == ".v" and p.exists():
        return p.read_text(), p
    return str(result), None


def check_rules(code, ports):
    """Sprint 1 hallucination checks (H-rules). L1 latch warnings are advisory and not listed here."""
    return [as_text(f) for f in check_rtl(code, ports) if f["code"].startswith("H")]


def _cell(value) -> str:
    """Make a value safe for one Markdown table cell."""
    return str(value).replace("|", "/").replace("\n", " ").strip()


# ---- Sprint 1 mode: rtl_gen + hallucination checks + compile ---------------------------------

def write_results(rows):
    """Append this run as a new section; earlier runs are kept."""
    run_by = os.getenv("RUN_BY", "unknown")
    model = os.getenv("GEMINI_MODEL", "default (see .env.example)")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    passed = sum(1 for r in rows if r[2] == "PASS")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT_FILE.exists()
    with open(OUT_FILE, "a", encoding="utf-8") as f:
        if new_file:
            f.write("# Prompt Test Results (golden set)\n")
        f.write(f"\n## Run {stamp} | prompt {PROMPT_VERSION} | model {model} | run by {run_by}\n\n")
        f.write(f"Result: {passed}/{len(rows)} passed\n\n")
        f.write("| Case | Name | Status | Issues |\n|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r[0]} | {r[1]} | {r[2]} | {_cell(r[3])} |\n")


def run_prompt_mode(cases):
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
        issues = check_rules(code, c["ports"])
        # H4: compile only (no testbench in this mode)
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


# ---- Sprint 3 mode: every case through the full pipeline -------------------------------------

def spec_fidelity(result, expected_ports):
    """Compare the port names in the extracted spec with the ports the request asked for."""
    spec = result.get("spec") or {}
    got = {p.get("name") for p in spec.get("ports", []) if isinstance(p, dict)}
    if not got:
        return "no spec"
    missing = sorted(set(expected_ports) - got)
    extra = sorted(got - set(expected_ports))
    if not missing and not extra:
        return "exact"
    parts = []
    if missing:
        parts.append("missing " + ",".join(missing))
    if extra:
        parts.append("extra " + ",".join(extra))
    return "; ".join(parts)


def _testbench_check(result):
    check = result.get("testbench_check")
    if not check:
        return "-"
    return "trusted" if check.get("trusted") else f"rejected: {check.get('reason', 'unknown')}"


def pipeline_row(case, result, stats):
    """One results row. `stats` are the client's per-attempt records for this case only."""
    ok = [s for s in stats if s.get("ok")]
    tokens = [s["total_tokens"] for s in ok if isinstance(s.get("total_tokens"), int)]
    verification = result.get("verification") or {}
    return {
        "id": case["id"],
        "name": case["name"],
        "status": result.get("status", "ERROR"),
        "stage": result.get("stage") or "-",
        "repairs": verification.get("iterations", "-"),
        "testbench": _testbench_check(result),
        "lint": len(result.get("lint") or []),
        "spec": spec_fidelity(result, case["ports"]),
        "calls": len(stats),
        "failed_calls": len(stats) - len(ok),
        "avg_latency": sum(s["latency_s"] for s in ok) / len(ok) if ok else None,
        "tokens": sum(tokens) if tokens else None,
        "message": result.get("message") or "",
    }


def run_pipeline_case(case, client, pipeline):
    """Run one case. An unexpected crash is recorded as an ERROR row, never hidden."""
    before = len(client.stats)
    try:
        result = pipeline(case["request"], client=client)
    except Exception as exc:
        result = {"status": "ERROR", "stage": "pipeline",
                  "message": f"{type(exc).__name__}: {exc}"[:120]}
    return pipeline_row(case, result, client.stats[before:]), result


def write_pipeline_results(rows, results, client, total_cases, out_file=PIPELINE_OUT_FILE,
                           now=None, run_by=None):
    """Append one dated section to the pipeline results file; earlier runs are kept."""
    now = now or datetime.now()
    run_by = run_by or os.getenv("RUN_BY", "unknown")
    versions = next((r["versions"] for r in results if r.get("versions")), {})
    version_text = ", ".join(f"{k} {v}" for k, v in sorted(versions.items())) or "not reported"
    count = lambda status: sum(1 for r in rows if r["status"] == status)
    calls = sum(r["calls"] for r in rows)
    failed = sum(r["failed_calls"] for r in rows)
    latencies = [r["avg_latency"] for r in rows if r["avg_latency"] is not None]
    tokens = [r["tokens"] for r in rows if r["tokens"] is not None]
    avg = f"{sum(latencies) / len(latencies):.1f} s" if latencies else "n/a"
    exact = sum(1 for r in rows if r["spec"] == "exact")
    partial = "" if len(rows) == total_cases else f" | PARTIAL: {len(rows)} of {total_cases} cases"

    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out_file.exists()
    with open(out_file, "a", encoding="utf-8") as f:
        if new_file:
            f.write("# Pipeline Results (golden set through run_pipeline)\n")
        f.write(f"\n## Run {now:%Y-%m-%d %H:%M} | model {getattr(client, 'model', 'unknown')} "
                f"| run by {run_by}{partial}\n\n")
        f.write(f"* **Prompt versions:** {version_text}\n")
        f.write(f"* **Cases:** {len(rows)} | **PASS:** {count('PASS')} | **FAIL:** {count('FAIL')} "
                f"| **ERROR:** {count('ERROR')}\n")
        f.write(f"* **Spec ports exactly as requested:** {exact} of {len(rows)}\n")
        f.write(f"* **Gemini calls:** {calls} (failed: {failed}) | **Average latency per "
                f"successful call:** {avg} | **Tokens:** {sum(tokens) if tokens else 'n/a'}\n\n")
        f.write("| Case | Status | Stage | Repairs | Testbench check | Lint findings | Spec ports "
                "| Calls | Avg latency (s) |\n|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            lat = f"{r['avg_latency']:.1f}" if r["avg_latency"] is not None else "-"
            f.write(f"| {r['id']} {_cell(r['name'])} | {r['status']} | {_cell(r['stage'])} "
                    f"| {r['repairs']} | {_cell(r['testbench'])} | {r['lint']} | {_cell(r['spec'])} "
                    f"| {r['calls']} | {lat} |\n")
        problems = [r for r in rows if r["status"] != "PASS"]
        if problems:
            f.write("\nNot passed (recorded, not hidden):\n\n")
            for r in problems:
                f.write(f"* {r['id']} {r['status']} at {_cell(r['stage'])}: "
                        f"{_cell(r['message']) or 'no message'}\n")


def run_pipeline_mode(cases, client_factory=None, pipeline=None, out_file=PIPELINE_OUT_FILE,
                      now=None, progress=print):
    """Run the cases through the pipeline and record the run. Returns an exit code."""
    try:
        if client_factory is None:
            from agents.gemini_client import GeminiClient as client_factory
        client = client_factory()
    except GeminiConfigError as exc:
        progress(f"ERROR: {exc}")
        return 2
    if pipeline is None:
        try:
            from agents.pipeline import run_pipeline as pipeline
        except ImportError:
            progress("ERROR: agents.pipeline is not available yet (the orchestrator story is not merged).")
            return 2

    rows, results, interrupted = [], [], False
    try:
        for case in cases:
            progress(f"Running {case['id']} {case['name']} ...")
            row, result = run_pipeline_case(case, client, pipeline)
            rows.append(row)
            results.append(result)
            progress(f"  -> {row['status']} (stage {row['stage']}, repairs {row['repairs']})")
    except KeyboardInterrupt:
        interrupted = True
        progress("Interrupted: recording the cases finished so far.")
    if rows:
        write_pipeline_results(rows, results, client, len(cases), out_file=out_file, now=now)
        progress(f"Results appended to {out_file}")
    return 2 if interrupted else 0


# ---- entry point ---------------------------------------------------------------------------

def main(argv=None, client_factory=None, pipeline=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tests.run_prompt_cases",
        description="Run the golden prompt set (Sprint 1 mode) or through the full pipeline (--pipeline).")
    parser.add_argument("--pipeline", action="store_true",
                        help="run each case through the full pipeline and record docs/sprint3/pipeline_results.md")
    parser.add_argument("--only", metavar="IDS", help="comma-separated case ids, e.g. PC-01,PC-03")
    args = parser.parse_args(argv)
    try:
        cases = load_cases(args.only)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    if args.pipeline:
        return run_pipeline_mode(cases, client_factory, pipeline)
    run_prompt_mode(cases)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())