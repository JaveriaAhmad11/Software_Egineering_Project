"""Repair loop controller (SCRUM-46 / S2-11).

Verify -> classify -> repair -> verify again, at most `max_repairs` times.
The harness is the only judge: success needs a clean compile AND a PASS from the
testbench. Every attempt is saved to its own file so each repair can be audited.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from agents.verifier.harness import run_verification

log = logging.getLogger(__name__)

_FAIL = re.compile(r"\bFAIL\b")
_PASS = re.compile(r"\bPASS\b")
REPAIRABLE = {"compile_error", "assertion_failure"}  # only real RTL problems go to repair


def _classify(result: dict, testbench) -> dict:
    """Turn a run_verification result into {"kind", "errors", "log"}.

    Temporary stand-in for Areesha's classify_failure (S2-05); swap it in once merged.
    """
    errors = result.get("errors", [])
    text = result.get("log", "")
    tb_name = Path(testbench).name if testbench else None

    if any("iverilog/vvp not found" in (e.get("message") or "") for e in errors):
        kind = "tool_missing"
    elif result.get("timed_out"):
        kind = "timeout"
    elif not result.get("compiled"):
        in_tb = any(e.get("file") and Path(e["file"]).name == tb_name for e in errors)
        kind = "testbench_error" if in_tb else "compile_error"
    elif not result.get("simulated"):
        kind = "testbench_error"          # vvp crashed: not the RTL's fault
    elif _FAIL.search(text):
        kind = "assertion_failure"        # a FAIL print is never success
    elif _PASS.search(text):
        kind = "ok"
    else:
        kind = "testbench_error"          # silent testbench proves nothing
    return {"kind": kind, "errors": errors, "log": text}


def run_repair_loop(design, testbench, spec, max_repairs=3, repair=None,
                    verify=None, outdir=None) -> dict:
    """Verify `design`; on repairable failure ask `repair` for a fix, up to max_repairs times.

    Returns {"success", "iterations", "final_file", "history", "manual_review"}.
    `verify` and `outdir` are optional so tests can run without Icarus or an API key.
    """
    design = Path(design)
    verify = verify or run_verification
    if repair is None:
        from agents.repair.agent import repair_verilog  # Laraib's agent (S2-09)
        repair = repair_verilog
    outdir = Path(outdir) if outdir else design.parent / f"{design.stem}_attempts"
    outdir.mkdir(parents=True, exist_ok=True)

    code = design.read_text(encoding="utf-8")
    history, repairs_used, success = [], 0, False

    while True:
        path = outdir / f"{design.stem}_attempt{repairs_used}{design.suffix}"
        path.write_text(code, encoding="utf-8")          # original file is never overwritten
        failure = _classify(verify(path, testbench), testbench)
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

    return {"success": success, "iterations": repairs_used, "final_file": history[-1]["file"]
            if history[-1]["file"] else str(path), "history": history,
            "manual_review": not success}