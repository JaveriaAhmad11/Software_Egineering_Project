"""CLI entrypoint (SCRUM-27, SCRUM-45): natural-language request -> Verilog -> Icarus check -> PASS/FAIL.

Usage:
    python main.py "8-bit counter"                        generate with Gemini, then compile
    python main.py "8-bit counter" --tb tb.v              ...and also simulate with a testbench
    python main.py "8-bit counter" --repair               ...generate a testbench, repair on failure
    python main.py "8-bit counter" --repair --tb tb.v     ...repair against your own testbench
    python main.py --verify design.v [--tb tb.v]          verify an existing file (no API call)
    python main.py --verify design.v --tb tb.v --repair   verify an existing file, repair on failure

Exit codes: 0 = PASS, 1 = FAIL (compile / simulation / unusable model output / not repaired),
2 = error (missing API key, API failure, bad usage). Errors are printed as one clear line, no stack trace.

Testbench convention: a testbench prints PASS on success and the word FAIL on a mismatch.
Repair attempts are saved under outputs/repair/<name>_attempts/; the original file is never overwritten.
"""
from __future__ import annotations

import argparse
import re
import sys
from functools import partial
from pathlib import Path

from agents.verifier.harness import run_verification

PASS, FAIL, ERROR = 0, 1, 2
_FAIL_WORD = re.compile(r"\bFAIL\b")
REPAIR_DIR = Path(__file__).resolve().parent / "outputs" / "repair"  # gitignored


def _api_error(exc) -> str:
    """One clear line for Gemini configuration and API errors."""
    # Imported here so --verify keeps working even if the Gemini SDK is not installed.
    from agents.gemini_client import GeminiCallFailed

    if isinstance(exc, GeminiCallFailed):
        return f"ERROR: {exc}. Check quota/network and logs/gemini.log."
    return f"ERROR: {exc}"


def _generate(request, generate=None, total=2):
    """Run the rtl_gen agent. Returns (path, exit_code, message); path is None on failure."""
    from agents.gemini_client import GeminiCallFailed, GeminiConfigError
    from agents.rtl_gen.agent import PROMPT_VERSION, RTLGenerationError, generate_rtl

    print(f"Prompt   : rtl_gen {PROMPT_VERSION}")
    print(f"Step 1/{total} : generating Verilog with Gemini ...")
    try:
        return Path((generate or generate_rtl)(request)), None, None
    except (GeminiConfigError, GeminiCallFailed) as exc:
        return None, ERROR, _api_error(exc)
    except RTLGenerationError as exc:
        return None, FAIL, f"RESULT: FAIL (generation): {exc}"


def _make_testbench(design, spec, generate_tb=None):
    """Run the testbench agent. Returns (path, exit_code, message); path is None on failure."""
    from agents.gemini_client import GeminiCallFailed, GeminiConfigError
    from agents.rtl_gen.agent import RTLGenerationError
    from agents.testbench.agent import InvalidTestbenchError, generate_testbench

    try:
        code = Path(design).read_text(encoding="utf-8")
        return Path((generate_tb or generate_testbench)(code, spec)), None, None
    except (GeminiConfigError, GeminiCallFailed) as exc:
        return None, ERROR, _api_error(exc)
    except (InvalidTestbenchError, RTLGenerationError) as exc:
        return None, FAIL, f"RESULT: FAIL (testbench generation): {exc}"


def _repair_callable(testbench_text, repair=None):
    """Adapt repair_verilog to the loop's repair(code, failure, spec).

    The loop records any exception from repair as a failed attempt. Gemini config and API errors
    are remembered here so the CLI can report them as errors (exit 2) instead of a failed repair.
    """
    from agents.gemini_client import GeminiCallFailed, GeminiConfigError

    if repair is None:
        from agents.repair.agent import repair_verilog

        repair = repair_verilog
    api_errors = []

    def call(code, failure, spec):
        try:
            return repair(code, failure, spec, testbench=testbench_text)
        except (GeminiConfigError, GeminiCallFailed) as exc:
            api_errors.append(exc)
            raise

    return call, api_errors


def _passed(result, testbench) -> bool:
    if not result["compiled"]:
        return False
    if testbench:
        return result["simulated"] and not _FAIL_WORD.search(result["log"])
    return True


def _format_error(err) -> str:
    where = f"{err['file']}:{err['line']}: " if err.get("line") else ""
    return f"{where}{err['message']}"


def _print_result(result, testbench) -> None:
    print(f"  compiled  : {'yes' if result['compiled'] else 'NO'}")
    if testbench:
        print(f"  simulated : {'yes' if result['simulated'] else 'NO'}")
    else:
        print("  simulated : skipped (no testbench given)")
    if result["timed_out"]:
        print("  timed out : yes")
    for err in result["errors"]:
        print(f"  error     : {_format_error(err)}")
    if testbench and result["compiled"] and result["log"].strip():
        for line in result["log"].strip().splitlines()[:10]:
            print(f"  sim output: {line}")


def _detail(step) -> str:
    """First error, or else the first log line, of one verification attempt."""
    if step["errors"]:
        return _format_error(step["errors"][0])
    lines = [ln.strip() for ln in step["log"].splitlines() if ln.strip()]
    return lines[0][:80] if lines else ""


def _print_attempts(history) -> None:
    for step in history:
        if step["kind"] == "repair_error":
            print(f"  repair    : stopped - {step['log'][:100]}")
            continue
        label = "original" if step["attempt"] == 0 else f"repair {step['attempt']}"
        detail = _detail(step)
        print(f"  {label:<9} : {step['kind']}" + (f" - {detail}" if detail else ""))


def _run_repair(design, spec, args, total, verify=None, repair=None, generate_tb=None) -> int:
    """Verify `design`; on a repairable failure the loop controller repairs and re-verifies it."""
    from agents.repair.loop import run_repair_loop  # SCRUM-46

    testbench = args.tb
    if not testbench:
        print(f"Step 2/{total} : generating a testbench with Gemini ...")
        testbench, code, message = _make_testbench(design, spec, generate_tb)
        if testbench is None:
            print(message, file=sys.stderr if code == ERROR else sys.stdout)
            return code
        print(f"           saved -> {testbench}")
        print("  note      : the testbench is model-generated and not validated against a reference design")
    try:
        testbench_text = Path(testbench).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read testbench {testbench}: {exc}", file=sys.stderr)
        return ERROR

    print(f"Step {total}/{total} : verifying, repairing on failure ...")
    repair_fn, api_errors = _repair_callable(testbench_text, repair)
    outcome = run_repair_loop(
        design,
        testbench,
        spec,
        repair=repair_fn,
        verify=partial(verify or run_verification, timeout=args.timeout),
        outdir=REPAIR_DIR / f"{Path(design).stem}_attempts",
    )
    if api_errors:
        print(_api_error(api_errors[0]), file=sys.stderr)
        return ERROR

    _print_attempts(outcome["history"])
    print(f"  final file: {outcome['final_file']}")
    repairs = outcome["iterations"]
    plural = "" if repairs == 1 else "s"
    if outcome["success"]:
        note = "no repair needed" if repairs == 0 else f"repaired with {repairs} repair{plural}"
        print(f"RESULT: PASS ({note})")
        return PASS
    last = outcome["history"][-1]["kind"]
    reason = "repair rejected" if last == "repair_error" else last
    print(f"RESULT: FAIL ({reason}; {repairs} repair{plural} applied; manual review needed)")
    return FAIL


def main(argv=None, generate=None, verify=None, repair=None, generate_tb=None) -> int:
    parser = argparse.ArgumentParser(
        prog="main.py", description="Generate Verilog from plain English and verify it with Icarus."
    )
    parser.add_argument("request", nargs="?", help='e.g. "8-bit counter"')
    parser.add_argument("--verify", metavar="FILE", help="verify an existing .v file instead of generating")
    parser.add_argument("--tb", metavar="FILE", help="testbench .v file to simulate with")
    parser.add_argument("--repair", action="store_true",
                        help="on failure, ask Gemini to repair the design and re-verify (bounded retries)")
    parser.add_argument("--timeout", type=float, default=10, help="seconds for compile and for simulation")
    args = parser.parse_args(argv)
    if bool(args.request) == bool(args.verify):
        parser.error("give either a request or --verify FILE (not both)")
    if args.repair and args.verify and not args.tb:
        parser.error("--repair needs a testbench: add --tb FILE")

    if args.verify:
        design, spec, total = Path(args.verify), "", 1
        print(f"Verify   : {design}")
    else:
        spec = args.request
        total = 3 if args.repair and not args.tb else 2
        print(f"Request  : {args.request}")
        design, code, message = _generate(args.request, generate, total)
        if design is None:
            print(message, file=sys.stderr if code == ERROR else sys.stdout)
            return code
        print(f"           saved -> {design}")

    if args.repair:
        return _run_repair(design, spec, args, total, verify, repair, generate_tb)

    if not args.verify:
        print("Step 2/2 : verifying with Icarus Verilog ...")
    result = (verify or run_verification)(design, args.tb, timeout=args.timeout)
    _print_result(result, args.tb)
    ok = _passed(result, args.tb)
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return PASS if ok else FAIL


if __name__ == "__main__":
    sys.exit(main())