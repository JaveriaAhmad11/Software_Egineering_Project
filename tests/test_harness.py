from pathlib import Path

import pytest

from agents.verifier.harness import _find_tool, run_verification

FIX = Path(__file__).parent / "fixtures"
needs_iverilog = pytest.mark.skipif(
    _find_tool("iverilog") is None or _find_tool("vvp") is None,
    reason="iverilog/vvp not installed",
)


@needs_iverilog
def test_good_design_compiles_and_passes():
    r = run_verification(FIX / "counter_good.v", FIX / "counter_tb.v")
    assert r["compiled"] and r["simulated"] and not r["errors"]
    assert "PASS" in r["log"]


@needs_iverilog
def test_syntax_error_is_reported():
    r = run_verification(FIX / "counter_bad.v", FIX / "counter_tb.v")
    assert not r["compiled"] and not r["simulated"]
    assert r["errors"] and r["errors"][0]["line"] is not None


@needs_iverilog
def test_hanging_testbench_times_out():
    r = run_verification(FIX / "counter_good.v", FIX / "hang_tb.v", timeout=2)
    assert r["compiled"] and not r["simulated"] and r["timed_out"]


def test_missing_file_is_reported():
    r = run_verification(FIX / "does_not_exist.v")
    assert not r["compiled"] and r["errors"]


def test_missing_tools_reported_without_iverilog(monkeypatch):
    monkeypatch.setattr("agents.verifier.harness._find_tool", lambda name: None)
    r = run_verification(FIX / "counter_good.v")
    assert not r["compiled"] and "not found" in r["errors"][0]["message"]
