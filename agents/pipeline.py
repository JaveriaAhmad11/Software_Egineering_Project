"""Pipeline orchestrator (SCRUM-49): request -> spec -> RTL -> port check -> testbench -> verify/repair -> lint -> report.

run_pipeline(request, progress=None, ...) runs the stages in order and returns one result dict:
    status   "PASS" | "FAIL" | "ERROR"   (the CLI maps these to exit codes 0 / 1 / 2)
    stage    the stage that decided the outcome ("done" on PASS)
    message  one-line reason (empty on a clean PASS)
    report   path of the report file, or None
plus the artefacts: request, spec, spec_text, design, testbench, final_file, repairs, history, lint, notes.

Design rules
  * The simulator is the only judge. Model output is a hypothesis: the spec is validated, the ports are
    compared with the spec, and the design must pass a real simulation before the run is a PASS.
  * FAIL means the pipeline ran and the design (or a model reply) could not be trusted.
    ERROR means the pipeline could not run (missing API key, API failure).
  * Lint is advisory. Its rules are text heuristics (L1 can false-alarm), so findings are recorded in the
    result and the report but never override the simulation verdict.
  * Every stage is a parameter, so tests run the whole pipeline with fakes and no API key.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path

from agents.gemini_client import GeminiCallFailed, GeminiClient, GeminiConfigError
from agents.repair.agent import repair_verilog
from agents.repair.loop import run_repair_loop
from agents.repair.prompt import PROMPT_VERSION as REPAIR_PROMPT
from agents.rtl_gen.agent import PROMPT_VERSION as RTL_GEN_PROMPT
from agents.rtl_gen.agent import RTLGenerationError, generate_rtl
from agents.spec_intake.agent import PROMPT_VERSION as SPEC_INTAKE_PROMPT
from agents.spec_intake.agent import extract_spec
from agents.spec_intake.schema import SpecError, check_ports, render_spec, validate_spec
from agents.testbench.agent import PROMPT_VERSION as TESTBENCH_PROMPT
from agents.testbench.agent import InvalidTestbenchError, generate_testbench
from agents.verifier.harness import run_verification
from agents.verifier.lint import as_text, check_rtl

PASS, FAIL, ERROR = "PASS", "FAIL", "ERROR"
API_ERRORS = (GeminiConfigError, GeminiCallFailed)
REPAIR_DIR = Path(__file__).resolve().parent.parent / "outputs" / "repair"  # gitignored


def _no_progress(stage, message=""):
    """Default progress callback: print nothing."""


def _default_report(result):
    """Report agent (SCRUM-50). Imported late so the pipeline works before that agent exists."""
    from agents.report.agent import generate_report

    return generate_report(result)


def _repair_adapter(testbench_text, repair, api_errors):
    """Adapt repair_verilog to the loop's repair(code, failure, spec).

    The loop records any exception from repair as a failed attempt. Gemini config and API errors are
    remembered here so the pipeline can report them as ERROR instead of a failed repair.
    """

    def call(code, failure, spec):
        try:
            return repair(code, failure, spec, testbench=testbench_text)
        except API_ERRORS as exc:
            api_errors.append(exc)
            raise

    return call


def _version(label):
    """'spec_intake/v1.0' and 'v1.0' both become 'v1.0'."""
    return str(label).split("/")[-1]


def run_pipeline(request, progress=None, *, extract=None, generate=None, make_testbench=None,
                 verify=None, repair=None, repair_loop=None, report=None, client=None,
                 timeout=10) -> dict:
    progress = progress or _no_progress

    ctx = {"request": request, "spec": None, "spec_text": None, "design": None, "testbench": None,
           "final_file": None, "repairs": 0, "history": [], "lint": [], "report": None, "notes": [],
           "model": None, "gemini_calls": [],
           "prompt_versions": {"spec_intake": _version(SPEC_INTAKE_PROMPT),
                               "rtl_gen": _version(RTL_GEN_PROMPT),
                               "testbench": _version(TESTBENCH_PROMPT),
                               "repair": _version(REPAIR_PROMPT)}}

    def finish(status, stage, message=""):
        if client is not None:  # run data for the report: the model and every Gemini call
            ctx["model"] = client.model
            ctx["gemini_calls"] = [dict(call) for call in client.stats]
        return {**ctx, "status": status, "stage": stage, "message": message}

    # A real run shares one Gemini client, so every call (latency, tokens) lands in client.stats.
    # When stages are injected (tests) no client is created and none is needed.
    if client is None and extract is None:
        try:
            client = GeminiClient()
        except GeminiConfigError as exc:
            return finish(ERROR, "spec_intake", str(exc))

    def bind(stage, default):
        if stage is not None:
            return stage
        return default if client is None else partial(default, client=client)

    extract = bind(extract, extract_spec)
    generate = bind(generate, generate_rtl)
    make_testbench = bind(make_testbench, generate_testbench)
    repair = bind(repair, repair_verilog)

    # 1. Spec intake: the model reply is validated before anything trusts it
    progress("spec_intake", "extracting a structured spec")
    try:
        spec = validate_spec(extract(request))
    except SpecError as exc:
        return finish(FAIL, "spec_intake", f"spec rejected: {exc}")
    except API_ERRORS as exc:
        return finish(ERROR, "spec_intake", str(exc))
    spec_text = render_spec(spec)
    ctx.update(spec=spec, spec_text=spec_text)

    # 2. RTL generation
    progress("rtl_gen", "generating Verilog from the spec")
    try:
        design = Path(generate(spec_text))
    except RTLGenerationError as exc:
        return finish(FAIL, "rtl_gen", f"generation failed: {exc}")
    except API_ERRORS as exc:
        return finish(ERROR, "rtl_gen", str(exc))
    ctx["design"] = str(design)
    code = design.read_text(encoding="utf-8")

    # 3. Port contract: the design must expose exactly the ports the spec lists
    progress("port_check", "comparing the design's ports with the spec")
    mismatches = check_ports(code, spec)
    if mismatches:
        return finish(FAIL, "port_check", "; ".join(mismatches))

    # 4. Testbench
    progress("testbench", "generating a testbench")
    try:
        testbench = Path(make_testbench(code, spec_text))
    except (InvalidTestbenchError, RTLGenerationError) as exc:
        return finish(FAIL, "testbench", f"testbench generation failed: {exc}")
    except API_ERRORS as exc:
        return finish(ERROR, "testbench", str(exc))
    ctx["testbench"] = str(testbench)
    ctx["notes"].append("the testbench is model-generated and not validated against a reference design")
    testbench_text = testbench.read_text(encoding="utf-8")

    # 5. Verify, and repair on failure (bounded retries live in the loop controller)
    progress("verify", "verifying, repairing on failure")
    api_errors = []
    outcome = (repair_loop or run_repair_loop)(
        design,
        testbench,
        spec_text,
                repair=_repair_adapter(testbench_text, repair, api_errors),
        verify=partial(verify or run_verification, timeout=timeout),
        outdir=REPAIR_DIR / f"{design.stem}_attempts",
    )
    if api_errors:
        return finish(ERROR, "verify", str(api_errors[0]))
    repairs = outcome["iterations"]
    ctx.update(repairs=repairs, history=outcome["history"], final_file=str(outcome["final_file"]))
    if not outcome["success"]:
        last = outcome["history"][-1]["kind"] if outcome["history"] else "unknown"
        reason = "repair rejected" if last == "repair_error" else last
        return finish(FAIL, "verify", f"{reason}; {repairs} repair(s) applied; manual review needed")

    # 6. Lint the final design (advisory: recorded, never changes the verdict)
    progress("lint", "checking the final design")
    final_code = Path(ctx["final_file"]).read_text(encoding="utf-8")
    findings = check_rtl(final_code, [p["name"] for p in spec["ports"]])
    ctx["lint"] = findings
    if findings:
        progress("lint", f"{len(findings)} advisory finding(s): " + "; ".join(as_text(f) for f in findings))

    # 7. Report (only for a verified design)
    result = finish(PASS, "done", "" if repairs == 0 else f"repaired with {repairs} repair(s)")
    progress("report", "writing the design rationale")
    try:
        result["report"] = str((report or _default_report)(result))
    except ImportError:
        result["notes"].append("report agent not available yet (SCRUM-50)")
    except Exception as exc:  # a failed report must not turn a verified design into a failure
        result["notes"].append(f"report failed: {exc}")
    return result