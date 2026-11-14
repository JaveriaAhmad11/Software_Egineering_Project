"""Tests for the repair benchmark runner (SCRUM-36 / S2-04): no API key, no Icarus."""
import importlib.util
from datetime import datetime
from pathlib import Path

from agents.gemini_client import GeminiConfigError

_spec = importlib.util.spec_from_file_location(
    "run_repair_cases", Path(__file__).with_name("run_repair_cases.py"))
rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rc)

OK = {"ok": True, "latency_s": 4.0}
BAD = {"ok": False, "latency_s": 30.0}


class FakeClient:
    model = "fake-model"

    def __init__(self):
        self.stats = []


class FakeLoop:
    def __init__(self, outcomes, client):
        self.outcomes, self.client, self.called = outcomes, client, []

    def __call__(self, fault, testbench, spec, repair=None, outdir=None):
        name = Path(fault).name
        self.called.append(name)
        o = self.outcomes[name]
        self.client.stats.extend(o["stats"])
        return {"success": o["success"], "iterations": o["iterations"],
                "history": [{"kind": o["first"]}, {"kind": o["last"]}]}


def go(tmp_path, outcomes, existing=""):
    client = FakeClient()
    faults = tmp_path / "faults"
    faults.mkdir()
    for name in outcomes:
        (faults / name).write_text("module x; endmodule\n")
    tb = tmp_path / "tb.v"
    tb.write_text("// tb\n")
    results = tmp_path / "docs" / "repair_results.md"
    results.parent.mkdir()
    results.write_text(existing)
    loop = FakeLoop(outcomes, client)
    rows = rc.run_benchmark(client, faults, tb, results, loop=loop, runs_dir=tmp_path / "runs",
                            now=datetime(2026, 11, 14, 12, 0, 0), progress=lambda s: None)
    return rows, loop, results.read_text()


def outcome(success, iterations, first, last, stats=()):
    return {"success": success, "iterations": iterations, "first": first, "last": last,
            "stats": list(stats)}


def test_every_fixture_goes_through_the_loop(tmp_path):
    outs = {"a.v": outcome(True, 1, "compile_error", "ok"),
            "b.v": outcome(True, 2, "assertion_failure", "ok")}
    _, loop, _ = go(tmp_path, outs)
    assert loop.called == ["a.v", "b.v"]


def test_unrepaired_case_is_recorded_as_failure(tmp_path):
    outs = {"a.v": outcome(False, 3, "compile_error", "compile_error"),
            "b.v": outcome(True, 1, "compile_error", "ok")}
    rows, _, text = go(tmp_path, outs)
    assert rows[0]["final"] == "FAIL (compile_error)"
    assert rows[1]["final"] == "PASS"
    assert "Not repaired (recorded as failures):** 1" in text


def test_results_are_appended_and_the_model_is_named(tmp_path):
    outs = {"a.v": outcome(True, 1, "compile_error", "ok")}
    _, _, text = go(tmp_path, outs, existing="OLD CONTENT\n")
    assert text.startswith("OLD CONTENT\n")
    assert "fake-model" in text and "2026-11-14 12:00:00" in text


def test_calls_and_latency_come_from_the_client(tmp_path):
    outs = {"a.v": outcome(True, 1, "compile_error", "ok", [OK, BAD, OK])}
    rows, _, _ = go(tmp_path, outs)
    assert rows[0]["calls"] == 3 and rows[0]["failed_calls"] == 1
    assert rows[0]["avg_latency"] == 4.0


def test_a_crashing_case_is_recorded_not_hidden(tmp_path):
    client = FakeClient()
    tb = tmp_path / "tb.v"
    tb.write_text("// tb\n")
    fault = tmp_path / "boom.v"
    fault.write_text("module x; endmodule\n")

    def boom(*args, **kwargs):
        raise RuntimeError("loop exploded")

    row = rc.run_case(fault, tb, client, loop=boom, outdir=tmp_path / "o")
    assert row["final"] == "ERROR (RuntimeError)"


def test_missing_key_is_one_clear_line(capsys):
    def no_key():
        raise GeminiConfigError("GEMINI_API_KEY not found. Check your .env file.")

    assert rc.main(client_factory=no_key) == 2
    assert "ERROR: GEMINI_API_KEY not found" in capsys.readouterr().out
