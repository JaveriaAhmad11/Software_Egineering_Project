"""Tests for the repair loop controller (SCRUM-46 / S2-11).

No API key and no Icarus needed: verify and repair are replaced by fakes.
"""
from pathlib import Path

from agents.repair.loop import run_repair_loop

ORIGINAL = "module m; // original\nendmodule\n"


def ok():
    return {"compiled": True, "simulated": True, "timed_out": False, "errors": [], "log": "PASS\n"}


def compile_fail(file="design.v"):
    return {"compiled": False, "simulated": False, "timed_out": False,
            "errors": [{"file": file, "line": 3, "message": "syntax error"}], "log": ""}


def assertion_fail():
    return {"compiled": True, "simulated": True, "timed_out": False,
            "errors": [], "log": "FAIL: expected 5 got 4\n"}


class FakeVerify:
    """Returns the prepared results in order; repeats the last one if called more often."""
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, design, testbench=None, timeout=10):
        self.calls.append(Path(design))
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


class FakeRepair:
    def __init__(self):
        self.kinds = []

    def __call__(self, code, failure, spec):
        self.kinds.append(failure["kind"])
        return f"module m; // repair {len(self.kinds)}\nendmodule\n"


def run(tmp_path, results, max_repairs=3):
    design = tmp_path / "design.v"
    design.write_text(ORIGINAL)
    tb = tmp_path / "design_tb.v"
    tb.write_text("// testbench\n")
    verify, repair = FakeVerify(results), FakeRepair()
    out = run_repair_loop(design, tb, "a spec", max_repairs=max_repairs,
                          repair=repair, verify=verify, outdir=tmp_path / "attempts")
    return out, verify, repair, design


def test_passes_first_time_without_calling_repair(tmp_path):
    out, verify, repair, _ = run(tmp_path, [ok()])
    assert out["success"] is True
    assert out["iterations"] == 0
    assert repair.kinds == []


def test_compile_error_is_repaired_then_passes(tmp_path):
    out, verify, repair, _ = run(tmp_path, [compile_fail(), ok()])
    assert out["success"] is True
    assert out["iterations"] == 1
    assert repair.kinds == ["compile_error"]
    assert len(out["history"]) == 2


def test_assertion_failure_is_repaired(tmp_path):
    out, _, repair, _ = run(tmp_path, [assertion_fail(), ok()])
    assert out["success"] is True
    assert repair.kinds == ["assertion_failure"]


def test_stops_after_three_failed_repairs(tmp_path):
    out, verify, repair, _ = run(tmp_path, [compile_fail()])  # always fails
    assert out["success"] is False
    assert out["iterations"] == 3
    assert len(repair.kinds) == 3
    assert out["manual_review"] is True
    assert len(out["history"]) == 4  # original + 3 repairs


def test_fail_print_is_never_success(tmp_path):
    out, _, _, _ = run(tmp_path, [assertion_fail()], max_repairs=0)
    assert out["success"] is False


def test_silent_testbench_is_not_success_and_not_repaired(tmp_path):
    silent = {"compiled": True, "simulated": True, "timed_out": False, "errors": [], "log": ""}
    out, _, repair, _ = run(tmp_path, [silent])
    assert out["success"] is False
    assert repair.kinds == []


def test_testbench_error_is_not_sent_to_repair(tmp_path):
    out, _, repair, _ = run(tmp_path, [compile_fail("design_tb.v")])
    assert out["success"] is False
    assert repair.kinds == []
    assert out["history"][0]["kind"] == "testbench_error"


def test_every_attempt_is_saved_separately(tmp_path):
    out, verify, _, design = run(tmp_path, [compile_fail(), compile_fail(), ok()])
    files = [Path(h["file"]) for h in out["history"]]
    assert len(set(files)) == 3 and all(f.exists() for f in files)
    assert design.read_text() == ORIGINAL          # original never overwritten
    assert Path(out["final_file"]) == files[-1]