"""Repair loop controller (SCRUM-46 / S2-11).

Verify -> classify -> repair -> verify again, at most `max_repairs` times.
The harness is the only judge: success needs a clean compile AND a PASS from the
testbench. Every attempt is saved to its own file so each repair can be audited.

Design-first check: when the testbench run does not compile, the design is compiled
alone. A missing endmodule or semicolon makes compiler errors spill into the testbench
file, so without this check a broken design would be blamed on the testbench.
"""
from __future__ import annotations

import logging
from pathlib import Path

from agents.verifier.harness import classify_failure, run_verification

log = logging.getLogger(__name__)

REPAIRABLE = {"compile_error", "assertion_failure"}  # only real RTL problems go to repair


def _classify(path, testbench, verify) -> dict:
    result = verify(path, testbench)
    failure = classify_failure(result, testbench)
    if failure["kind"] == "testbench_error" and not result.get("compiled"):
        alone = verify(path, None)                   # does the design compile on its own?
        if not alone.get("compiled"):
            failure = {"kind": "compile_error", "errors": alone.get("errors", []),
                       "log": alone.get("log", "")}
    return failure


def run_repair_loop(design, testbench, spec, max_repairs=3, repair=None,
                    verify=None, outdir=None) -> dict:
    """Verify `design`; on repairable failure ask `repair` for a fix, up to max_repairs times.

    Returns {"success", "iterations", "final_file", "history", "manual_review"}.
    `verify` and `outdir` are optional so tests can run without Icarus or an API key.
    """
    design = Path(design)
    verify = verify or run_verification
    if repair is None:
        from agents.repair.agent import repair_verilog  # repair agent (S2-09)
        tb_text = Path(testbench).read_text(encoding="utf-8")

        def repair(code, failure, spec):  # the testbench tells the model what is expected
            return repair_verilog(code, failure, spec, testbench=tb_text)
    outdir = Path(outdir) if outdir else design.parent / f"{design.stem}_attempts"
    outdir.mkdir(parents=True, exist_ok=True)

    code = design.read_text(encoding="utf-8")
    history, repairs_used, success = [], 0, False

    while True:
        path = outdir / f"{design.stem}_attempt{repairs_used}{design.suffix}"
        path.write_text(code, encoding="utf-8")          # original file is never overwritten
        failure = _classify(path, testbench, verify)
        history.append({"attempt": repairs_used, "file": str(path), **failure})
        log.info("attempt %d: %s", repairs_used, failure["kind"])

        if failure["kind"] == "ok":
            success = True
            break
        if failure["kind"] not in REPAIRABLE or repairs_used >= max_repairs:
            break
        try:
            code = repair(code, failure, spec)
        except Exception as exc:                          # unusable reply, API failure, ...
            history.append({"attempt": repairs_used + 1, "file": None,
                            "kind": "repair_error", "errors": [], "log": str(exc)})
            break
        repairs_used += 1

    final = next((h["file"] for h in reversed(history) if h["file"]), str(path))
    return {"success": success, "iterations": repairs_used, "final_file": final,
            "history": history, "manual_review": not success}
