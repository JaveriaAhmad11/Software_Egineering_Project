"""CLI entrypoint (SCRUM-27): natural-language request -> Verilog -> Icarus check -> PASS/FAIL.

Usage:
    python main.py "8-bit counter"                     full slice: generate with Gemini, then compile
    python main.py "8-bit counter" --tb tb.v           ...and also simulate with a testbench
    python main.py --verify design.v [--tb tb.v]       verify an existing file (no API call)

Exit codes: 0 = PASS, 1 = FAIL (compile / simulation / unusable model output), 2 = error
(missing API key, API failure, bad usage). Errors are printed as one clear line, no stack trace.

Testbench convention: a testbench reports a mismatch by printing the word FAIL.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from agents.verifier.harness import run_verification

PASS, FAIL, ERROR = 0, 1, 2
_FAIL_WORD = re.compile(r"\bFAIL\b")


def _generate(request, generate=None):
    """Run the rtl_gen agent. Returns (path, exit_code, message); path is None on failure."""
    # Imported here so --verify keeps working even if the Gemini SDK is not installed.
    from agents.gemini_client import GeminiCallFailed, GeminiConfigError
    from agents.rtl_gen.agent import PROMPT_VERSION, RTLGenerationError, generate_rtl

    print(f"Prompt   : rtl_gen {PROMPT_VERSION}")
    print("Step 1/2 : generating Verilog with Gemini ...")
    try:
        return Path((generate or generate_rtl)(request)), None, None
    except GeminiConfigError as exc:
        return None, ERROR, f"ERROR: {exc}"
    except GeminiCallFailed as exc:
        return None, ERROR, f"ERROR: {exc}. Check quota/network and logs/gemini.log."
    except RTLGenerationError as exc:
        return None, FAIL, f"RESULT: FAIL (generation): {exc}"


def _passed(result, testbench) -> bool:
    if not result["compiled"]:
        return False
    if testbench:
        return result["simulated"] and not _FAIL_WORD.search(result["log"])
    return True


def _print_result(result, testbench) -> None:
    print(f"  compiled  : {'yes' if result['compiled'] else 'NO'}")
    if testbench:
        print(f"  simulated : {'yes' if result['simulated'] else 'NO'}")
    else:
        print("  simulated : skipped (no testbench given)")
    if result["timed_out"]:
        print("  timed out : yes")
    for err in result["errors"]:
        where = f"{err['file']}:{err['line']}: " if err.get("line") else ""
        print(f"  error     : {where}{err['message']}")
    if testbench and result["compiled"] and result["log"].strip():
        for line in result["log"].strip().splitlines()[:10]:
            print(f"  sim output: {line}")


def main(argv=None, generate=None, verify=None) -> int:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Generate Verilog from plain English and verify it with Icarus."
    )
    parser.add_argument("request", nargs="?", help='e.g. "8-bit counter"')
    parser.add_argument("--verify", metavar="FILE", help="verify an existing .v file instead of generating")
    parser.add_argument("--tb", metavar="FILE", help="testbench .v file to simulate with")
    parser.add_argument("--timeout", type=float, default=10, help="seconds for compile and for simulation")
    args = parser.parse_args(argv)
    if bool(args.request) == bool(args.verify):
        parser.error("give either a request or --verify FILE (not both)")

    if args.verify:
        design = Path(args.verify)
        print(f"Verify   : {design}")
    else:
        print(f"Request  : {args.request}")
        design, code, message = _generate(args.request, generate)
        if design is None:
            print(message, file=sys.stderr if code == ERROR else sys.stdout)
            return code
        print(f"           saved -> {design}")
        print("Step 2/2 : verifying with Icarus Verilog ...")

    result = (verify or run_verification)(design, args.tb, timeout=args.timeout)
    _print_result(result, args.tb)
    ok = _passed(result, args.tb)
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return PASS if ok else FAIL


if __name__ == "__main__":
    sys.exit(main())
