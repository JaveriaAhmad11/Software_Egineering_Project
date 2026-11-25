"""Testbench validation (S2-07): a testbench is trusted only if it passes the known-good
reference and fails the known-bad mutant. Needs iverilog, no API key."""
from pathlib import Path

import pytest

from agents.testbench.agent import check_testbench, validate_testbench
from agents.verifier.harness import _find_tool, classify_failure, run_verification

FIX = Path(__file__).parent / "fixtures"
GOOD, MUTANT = FIX / "counter_good.v", FIX / "counter_mutant.v"
REF_TB, BROKEN_TB, HANG_TB = FIX / "counter_ref_tb.v", FIX / "counter_tb_broken.v", FIX / "hang_tb.v"

pytestmark = pytest.mark.skipif(
    _find_tool("iverilog") is None or _find_tool("vvp") is None, reason="iverilog/vvp not installed"
)


def kind(design, testbench, timeout=10):
    return classify_failure(run_verification(design, testbench, timeout=timeout), testbench)["kind"]


# ---- AC1: against the known-good reference it prints PASS ----------------------------------
def test_reference_passes_the_known_good_design():
    result = run_verification(GOOD, REF_TB)
    assert result["simulated"] and "PASS" in result["log"] and "FAIL" not in result["log"]
    assert kind(GOOD, REF_TB) == "ok"


# ---- AC2: against the functionally wrong mutant it prints FAIL -----------------------------
def test_mutant_is_caught():
    result = run_verification(MUTANT, REF_TB)
    assert result["compiled"] and result["simulated"] and "FAIL" in result["log"]
    assert kind(MUTANT, REF_TB) == "assertion_failure"


# ---- AC3: a testbench that does not compile or hangs is a testbench problem ----------------
def test_broken_testbench_is_a_testbench_error_not_an_rtl_bug():
    assert kind(GOOD, BROKEN_TB) == "testbench_error"


def test_hanging_testbench_is_reported_as_timeout():
    assert kind(GOOD, HANG_TB, timeout=2) == "timeout"


def test_silent_testbench_proves_nothing(tmp_path):
    silent = tmp_path / "silent_tb.v"
    silent.write_text("module silent_tb; initial $finish; endmodule\n")
    assert kind(GOOD, silent) == "testbench_error"


def test_neither_testbench_problem_would_reach_the_repair_agent():
    repairable = {"compile_error", "assertion_failure"}  # same set the loop controller uses
    assert kind(GOOD, BROKEN_TB) not in repairable
    assert kind(GOOD, HANG_TB, timeout=2) not in repairable


# ---- check_testbench: the trust decision ---------------------------------------------------
def test_reference_testbench_is_trusted():
    out = check_testbench(REF_TB, GOOD, MUTANT)
    assert out == {"trusted": True, "reference": "ok", "mutant": "assertion_failure", "reason": out["reason"]}


def test_testbench_that_cannot_catch_the_mutant_is_not_trusted():
    out = check_testbench(FIX / "counter_tb.v", GOOD, GOOD)  # "mutant" is really the good design
    assert not out["trusted"] and "too weak" in out["reason"]


def test_testbench_that_fails_the_reference_is_not_trusted():
    out = check_testbench(REF_TB, MUTANT, MUTANT)  # reference is actually wrong
    assert not out["trusted"] and "testbench is wrong" in out["reason"]


def test_broken_testbench_is_not_trusted_and_is_called_a_testbench_problem():
    out = check_testbench(BROKEN_TB, GOOD, MUTANT)
    assert not out["trusted"] and "testbench problem" in out["reason"]


def test_fixture_satisfies_the_generator_rules():
    assert validate_testbench(REF_TB.read_text(), "counter8") == "counter8_tb"
