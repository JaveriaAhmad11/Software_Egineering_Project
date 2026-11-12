"""Testbench generation agent (S2-06) and testbench validation (S2-07).

generate_testbench: RTL + specification -> saved <module>_tb.v (the reply is validated before
anything is written). check_testbench: a testbench is trusted only if it passes a known-good
reference design and fails a known-bad mutant, so a wrong testbench never "repairs" correct RTL.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from agents.gemini_client import GeminiCallFailed, GeminiClient, GeminiConfigError
from agents.rtl_gen.agent import RTLGenerationError, extract_verilog, validate_verilog
from agents.verifier.harness import classify_failure, run_verification

ROOT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = "v1.0"
PROMPT_PATH = ROOT / "prompts" / "testbench" / PROMPT_VERSION / "system_prompt.md"
OUTPUT_DIR = ROOT / "outputs"


class InvalidTestbenchError(Exception):
    """Raised when the model reply is not a usable testbench."""


def load_system_prompt(path=PROMPT_PATH) -> str:
    return Path(path).read_text(encoding="utf-8")


def build_prompt(code: str, spec: str, dut_name: str) -> str:
    return (
        f"{load_system_prompt()}\n\n---\nSPECIFICATION:\n{spec}\n\n"
        f"DESIGN UNDER TEST (module {dut_name}):\n```verilog\n{code}\n```"
    )


def validate_testbench(tb: str, dut_name: str) -> str:
    """Cheap guard against bad LLM output. Returns the testbench module name or raises."""
    try:
        tb_name = validate_verilog(tb)  # exactly one module / endmodule
    except RTLGenerationError as exc:
        raise InvalidTestbenchError(f"Reply is not exactly one testbench module: {exc}") from exc
    problems = []
    if tb_name == dut_name:
        problems.append("testbench module has the same name as the design")
    if "`timescale" not in tb:
        problems.append("no `timescale")
    if not re.search(rf"\b{re.escape(dut_name)}\b\s*(#\s*\([^;]*?\)\s*)?\w+\s*\(", tb):
        problems.append(f"no instance of {dut_name}")
    if "$finish" not in tb:
        problems.append("no $finish")
    if not re.search(r"\bPASS\b", tb):
        problems.append("no PASS message")
    if not re.search(r"\bFAIL\b", tb):
        problems.append("no FAIL message")
    if problems:
        raise InvalidTestbenchError("Testbench rejected: " + "; ".join(problems))
    return tb_name


def generate_testbench(code: str, spec: str, client=None, out_dir=OUTPUT_DIR) -> Path:
    """Generate <module>_tb.v for `code`. Returns the saved path; writes nothing on failure."""
    dut_name = validate_verilog(code)  # fail early, before spending an API call
    client = client or GeminiClient()
    raw = client.generate(build_prompt(code, spec, dut_name))
    tb = extract_verilog(raw)
    validate_testbench(tb, dut_name)  # reject before writing anything to disk
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{dut_name}_tb.v"
    path.write_text(tb + "\n", encoding="utf-8")
    return path


def check_testbench(testbench, reference, mutant, timeout: float = 10) -> dict:
    """S2-07: trust a testbench only if it passes `reference` and fails `mutant`.

    Returns {"trusted": bool, "reference": kind, "mutant": kind, "reason": str}.
    A testbench that does not compile, hangs, or stays silent is reported as a testbench
    problem, never as an RTL bug.
    """
    ref = classify_failure(run_verification(reference, testbench, timeout=timeout), testbench)["kind"]
    mut = classify_failure(run_verification(mutant, testbench, timeout=timeout), testbench)["kind"]
    if "tool_missing" in (ref, mut):
        reason = "iverilog/vvp not found"
    elif ref in ("testbench_error", "timeout"):
        reason = f"testbench problem: {ref} on the known-good reference (not an RTL bug)"
    elif ref == "compile_error":
        reason = "the reference design does not compile (bad reference file)"
    elif ref == "assertion_failure":
        reason = "testbench fails the known-good reference, so the testbench is wrong"
    elif mut == "compile_error":
        reason = "the mutant does not compile (bad mutant file)"
    elif mut in ("testbench_error", "timeout"):
        reason = f"testbench problem: {mut} on the mutant"
    elif mut == "ok":
        reason = "testbench passes the mutant, so it is too weak to catch bugs"
    else:
        reason = "passes the reference and fails the mutant"
    trusted = ref == "ok" and mut == "assertion_failure"
    return {"trusted": trusted, "reference": ref, "mutant": mut, "reason": reason}


def _cli(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agents.testbench.agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("generate", help="generate <module>_tb.v for a design")
    gen.add_argument("design", help="path to the design .v file")
    gen.add_argument("spec", nargs="+", help="plain-English specification of the design")
    chk = sub.add_parser("check", help="trust a testbench only if it passes the reference and fails the mutant")
    chk.add_argument("testbench")
    chk.add_argument("reference")
    chk.add_argument("mutant")
    args = parser.parse_args(argv)

    if args.cmd == "generate":
        try:
            code = Path(args.design).read_text(encoding="utf-8")
            print("Saved:", generate_testbench(code, " ".join(args.spec)))
            return 0
        except GeminiConfigError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        except GeminiCallFailed as exc:
            print(f"ERROR: {exc}. Check quota/network and logs/gemini.log.", file=sys.stderr)
            return 2
        except (InvalidTestbenchError, RTLGenerationError) as exc:
            print(f"RESULT: FAIL (generation): {exc}")
            return 1

    out = check_testbench(args.testbench, args.reference, args.mutant)
    print(f"Testbench : {args.testbench}")
    print(f"Reference : {Path(args.reference).name:<20} -> {out['reference']}  (expected: ok)")
    print(f"Mutant    : {Path(args.mutant).name:<20} -> {out['mutant']}  (expected: assertion_failure)")
    print(f"Reason    : {out['reason']}")
    print(f"RESULT: {'TRUSTED' if out['trusted'] else 'NOT TRUSTED'}")
    return 0 if out["trusted"] else 1


if __name__ == "__main__":
    sys.exit(_cli())
