"""Repair benchmark (SCRUM-36 / S2-04): every fault fixture goes through the real loop.

Usage:  python -m tests.run_repair_cases
Makes real Gemini calls. Appends a dated section to docs/sprint2/repair_results.md with
the numbers the loop and the client actually produced. Nothing is hard-coded, and a case
that is not repaired is recorded as a failure.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from agents.repair.loop import run_repair_loop

FAULTS = Path("tests/fixtures/faults")
TESTBENCH = Path("tests/fixtures/counter_tb.v")
RESULTS = Path("docs/sprint2/repair_results.md")
RUNS = Path("outputs/repair_runs")  # git-ignored: every attempt file is kept here
SPEC = ("8-bit synchronous up-counter. Module counter8 with ports clk, rst_n "
        "(active-low synchronous reset) and count[7:0]; count increments by 1 on every "
        "rising clock edge and is cleared to 0 while rst_n is low.")


def _say(text):
    print(text, flush=True)


def run_case(fault, testbench, client, loop=run_repair_loop, outdir=None, spec=SPEC) -> dict:
    fault, testbench = Path(fault), Path(testbench)
    tb_text = testbench.read_text(encoding="utf-8")
    before = len(client.stats)
    started = time.time()

    def repair(code, failure, spec_text):
        from agents.repair.agent import repair_verilog
        return repair_verilog(code, failure, spec_text, client=client, testbench=tb_text)

    try:
        out = loop(fault, testbench, spec, repair=repair, outdir=outdir)
        initial = out["history"][0]["kind"]
        repairs = out["iterations"]
        final = "PASS" if out["success"] else f"FAIL ({out['history'][-1]['kind']})"
    except Exception as exc:  # recorded honestly, never hidden
        initial, repairs, final = "-", 0, f"ERROR ({type(exc).__name__})"
    calls = client.stats[before:]
    latencies = [c["latency_s"] for c in calls if c["ok"]]
    return {"fixture": fault.name, "initial": initial, "repairs": repairs, "final": final,
            "calls": len(calls), "failed_calls": sum(1 for c in calls if not c["ok"]),
            "latencies": latencies,
            "avg_latency": (sum(latencies) / len(latencies)) if latencies else None,
            "seconds": time.time() - started}


def format_section(rows, model, stamp) -> str:
    passed = sum(1 for r in rows if r["final"] == "PASS")
    calls = sum(r["calls"] for r in rows)
    failed = sum(r["failed_calls"] for r in rows)
    every = [x for r in rows for x in r["latencies"]]
    average = f"{sum(every) / len(every):.1f} s" if every else "n/a"
    lines = [f"\n## Benchmark Run - {stamp}",
             f"* **Model Used:** {model}",
             f"* **Total Cases Tested:** {len(rows)}",
             f"* **Repaired (PASS):** {passed}",
             f"* **Not repaired (recorded as failures):** {len(rows) - passed}",
             f"* **Gemini attempts:** {calls} (failed attempts: {failed})",
             f"* **Average latency per successful call:** {average}",
             "",
             "| Fault Fixture | Initial Status | Repairs Used | Final Status | Gemini attempts | Failed attempts | Avg latency (s) |",
             "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
    for r in rows:
        avg = f"{r['avg_latency']:.1f}" if r["avg_latency"] is not None else "-"
        lines.append(f"| {r['fixture']} | {r['initial']} | {r['repairs']} | {r['final']} "
                     f"| {r['calls']} | {r['failed_calls']} | {avg} |")
    return "\n".join(lines) + "\n"


def run_benchmark(client, faults_dir=FAULTS, testbench=TESTBENCH, results_file=RESULTS,
                  loop=run_repair_loop, runs_dir=RUNS, now=None, progress=_say) -> list:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    run_folder = Path(runs_dir) / stamp.replace(":", "-").replace(" ", "_")
    faults = sorted(Path(faults_dir).glob("*.v"))
    rows = []
    for i, fault in enumerate(faults, 1):
        progress(f"[{i}/{len(faults)}] {fault.name} ...")
        row = run_case(fault, testbench, client, loop=loop, outdir=run_folder / fault.stem)
        progress(f"    -> {row['final']} | repairs: {row['repairs']} | "
                 f"Gemini attempts: {row['calls']} | {row['seconds']:.0f}s")
        rows.append(row)
    results_file = Path(results_file)
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(format_section(rows, client.model, stamp))
    progress(f"Results appended to {results_file}")
    return rows


def main(argv=None, client_factory=None) -> int:
    from agents.gemini_client import GeminiClient, GeminiConfigError
    try:
        client = (client_factory or GeminiClient)()
    except GeminiConfigError as exc:
        print(f"ERROR: {exc}")
        return 2
    run_benchmark(client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
