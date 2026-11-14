"""Tests for classify_failure (SCRUM S2-05). No API key needed."""
from pathlib import Path

import pytest

from agents.verifier.harness import KINDS, _find_tool, classify_failure, run_verification

FIX = Path(__file__).parent / "fixtures"
needs_iverilog = pytest.mark.skipif(
    _find_tool("iverilog") is None or _find_tool("vvp") is None, reason="iverilog/vvp not installed"
)


def result(**kw):
    base = {"compiled": True, "simulated": True, "timed_out": False, "errors": [], "log": "PASS\n"}
    return {**base, **kw}


def err(file, line=3, message="syntax error"):
    return {"file": file, "line": line, "message": message}


# ---- AC1: returns one of the six kinds, in the agreed shape -------------------------------
def test_shape_and_kinds():
    out = classify_failure(result(), "tb.v")
    assert set(out) == {"kind", "errors", "log"} and out["kind"] in KINDS
    assert set(KINDS) == {"ok", "compile_error", "testbench_error", "assertion_failure", "timeout", "tool_missing"}


def test_ok_needs_clean_compile_simulation_and_pass():
    assert classify_failure(result(), "tb.v")["kind"] == "ok"


def test_design_compile_error():
    out = classify_failure(result(compiled=False, simulated=False, errors=[err("design.v")], log=""), "tb.v")
    assert out["kind"] == "compile_error" and out["errors"][0]["file"] == "design.v"


def test_timeout():
    assert classify_failure(result(simulated=False, timed_out=True, log=""), "tb.v")["kind"] == "timeout"


def test_tool_missing():
    r = result(compiled=False, simulated=False,
               errors=[{"file": None, "line": None, "message": "iverilog/vvp not found. Install Icarus Verilog and add it to PATH."}])
    assert classify_failure(r, "tb.v")["kind"] == "tool_missing"


# ---- AC2: a clean exit that prints FAIL is never ok ---------------------------------------
def test_clean_exit_with_fail_print_is_assertion_failure():
    out = classify_failure(result(log="FAIL: expected 5 got 4\n"), "tb.v")
    assert out["kind"] == "assertion_failure"


def test_fail_wins_even_if_pass_is_also_printed():
    assert classify_failure(result(log="PASS\nFAIL: late mismatch\n"), "tb.v")["kind"] == "assertion_failure"


def test_words_inside_other_words_do_not_count():
    # PASSED / FAILURE are not the agreed PASS / FAIL markers
    assert classify_failure(result(log="PASSED\n"), "tb.v")["kind"] == "testbench_error"
    assert classify_failure(result(log="PASS\nno FAILURE seen\n"), "tb.v")["kind"] == "ok"


# ---- AC3: a compile error in the testbench is not the design's fault ----------------------
def test_compile_error_in_testbench_file_is_testbench_error():
    r = result(compiled=False, simulated=False, errors=[err("counter_tb.v")], log="")
    assert classify_failure(r, "outputs/counter_tb.v")["kind"] == "testbench_error"


def test_same_error_without_testbench_path_is_compile_error():
    r = result(compiled=False, simulated=False, errors=[err("counter_tb.v")], log="")
    assert classify_failure(r)["kind"] == "compile_error"


def test_unattributed_message_is_compile_error():
    r = result(compiled=False, simulated=False, errors=[{"file": None, "line": None, "message": "I give up."}], log="")
    assert classify_failure(r, "tb.v")["kind"] == "compile_error"


def test_vvp_crash_is_testbench_error():
    assert classify_failure(result(simulated=False, log=""), "tb.v")["kind"] == "testbench_error"


def test_silent_testbench_proves_nothing():
    assert classify_failure(result(log="done\n"), "tb.v")["kind"] == "testbench_error"


def test_compile_only_run_is_never_ok():
    r = result(simulated=False, log="")
    assert classify_failure(r)["kind"] == "testbench_error"


# ---- real harness runs (skipped if iverilog is not installed) -----------------------------
@needs_iverilog
def test_real_good_run_is_ok():
    tb = FIX / "counter_tb.v"
    assert classify_failure(run_verification(FIX / "counter_good.v", tb), tb)["kind"] == "ok"


@needs_iverilog
def test_real_broken_design_is_compile_error():
    tb = FIX / "counter_tb.v"
    assert classify_failure(run_verification(FIX / "counter_bad.v", tb), tb)["kind"] == "compile_error"


@needs_iverilog
def test_real_hanging_testbench_is_timeout():
    tb = FIX / "hang_tb.v"
    out = classify_failure(run_verification(FIX / "counter_good.v", tb, timeout=2), tb)
    assert out["kind"] == "timeout"


# ---- AC4 is covered by the rest of the suite staying green --------------------------------
