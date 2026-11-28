"""Tests for agents/pipeline.py (SCRUM-49). Every stage is a fake: no API key, no simulator."""
from agents.gemini_client import GeminiCallFailed, GeminiConfigError
from agents.pipeline import run_pipeline
from agents.rtl_gen.agent import RTLGenerationError
from agents.testbench.agent import InvalidTestbenchError

GOOD = """module counter(input clk, input rst, output reg [7:0] q);
always @(posedge clk) begin
  if (rst) q <= 8'd0;
  else q <= q + 1;
end
endmodule
"""
BLOCKING = GOOD.replace("q <= q + 1", "q = q + 1")  # lint H3, but the design still "passes"
MISSING_PORT = "module counter(input clk, input rst);\nendmodule\n"

SPEC = {
    "module_name": "counter",
    "summary": "8-bit counter with synchronous reset",
    "ports": [
        {"name": "clk", "direction": "input", "width": 1},
        {"name": "rst", "direction": "input", "width": 1},
        {"name": "q", "direction": "output", "width": 8},
    ],
    "behaviour": ["q increments on every rising clock edge", "rst clears q"],
    "test_scenarios": ["reset then count 3 cycles"],
}


def make_stages(tmp_path, design_text=GOOD, loop_result=None):
    """Return (stage kwargs for run_pipeline, list that records which stages were called)."""
    calls = []
    design = tmp_path / "counter.v"
    design.write_text(design_text)
    tb = tmp_path / "counter_tb.v"
    tb.write_text('module tb; initial $display("PASS"); endmodule\n')

    def extract(request):
        calls.append("extract")
        return dict(SPEC)

    def generate(spec_text):
        calls.append("generate")
        return design

    def make_testbench(code, spec_text):
        calls.append("testbench")
        return tb

    def repair_loop(design_path, tb_path, spec_text, **kwargs):
        calls.append("loop")
        return loop_result or {"success": True, "iterations": 0, "final_file": design_path,
                               "history": [{"kind": "ok", "attempt": 0, "errors": [], "log": "PASS"}]}

    def report(result):
        calls.append("report")
        return tmp_path / "counter_report.md"

    return dict(extract=extract, generate=generate, make_testbench=make_testbench,
                repair_loop=repair_loop, report=report), calls


def test_happy_path_passes_and_returns_report(tmp_path):
    stages, calls = make_stages(tmp_path)
    result = run_pipeline("8-bit counter", **stages)
    assert result["status"] == "PASS" and result["stage"] == "done"
    assert result["report"].endswith("counter_report.md")
    assert result["spec"]["module_name"] == "counter"
    assert calls == ["extract", "generate", "testbench", "loop", "report"]


def test_progress_reports_each_stage_in_order(tmp_path):
    stages, _ = make_stages(tmp_path)
    seen = []
    run_pipeline("x", progress=lambda stage, message="": seen.append(stage), **stages)
    assert seen == ["spec_intake", "rtl_gen", "port_check", "testbench", "verify", "lint", "report"]


def test_invalid_spec_fails_before_generation(tmp_path):
    stages, calls = make_stages(tmp_path)
    stages["extract"] = lambda request: {"module_name": "counter"}  # required keys missing
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("FAIL", "spec_intake")
    assert "generate" not in calls


def test_api_error_in_spec_intake_is_an_error_not_a_fail(tmp_path):
    stages, _ = make_stages(tmp_path)

    def extract(request):
        raise GeminiConfigError("GEMINI_API_KEY not found")

    stages["extract"] = extract
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("ERROR", "spec_intake")


def test_generation_failure_stops_the_run(tmp_path):
    stages, calls = make_stages(tmp_path)

    def generate(spec_text):
        raise RTLGenerationError("no module in reply")

    stages["generate"] = generate
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("FAIL", "rtl_gen")
    assert "testbench" not in calls


def test_port_mismatch_stops_before_testbench(tmp_path):
    stages, calls = make_stages(tmp_path, design_text=MISSING_PORT)
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("FAIL", "port_check")
    assert "'q'" in result["message"] and "testbench" not in calls


def test_testbench_failure_stops_the_run(tmp_path):
    stages, calls = make_stages(tmp_path)

    def make_testbench(code, spec_text):
        raise InvalidTestbenchError("no PASS print")

    stages["make_testbench"] = make_testbench
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("FAIL", "testbench")
    assert "loop" not in calls


def test_repair_that_succeeds_is_a_pass_and_counts_repairs(tmp_path):
    stages, _ = make_stages(tmp_path)
    stages["repair_loop"] = lambda d, t, s, **kw: {
        "success": True, "iterations": 2, "final_file": d,
        "history": [{"kind": "compile_error"}, {"kind": "assertion_failure"}, {"kind": "ok"}]}
    result = run_pipeline("x", **stages)
    assert result["status"] == "PASS" and result["repairs"] == 2
    assert "2 repair" in result["message"]


def test_repair_exhausted_is_a_fail(tmp_path):
    stages, _ = make_stages(tmp_path)
    stages["repair_loop"] = lambda d, t, s, **kw: {
        "success": False, "iterations": 3, "final_file": d,
        "history": [{"kind": "assertion_failure"}, {"kind": "assertion_failure"}]}
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("FAIL", "verify")
    assert "manual review" in result["message"] and result["report"] is None


def test_rejected_repair_is_reported_as_such(tmp_path):
    stages, _ = make_stages(tmp_path)
    stages["repair_loop"] = lambda d, t, s, **kw: {
        "success": False, "iterations": 1, "final_file": d,
        "history": [{"kind": "compile_error"}, {"kind": "repair_error", "log": "bad ports"}]}
    result = run_pipeline("x", **stages)
    assert "repair rejected" in result["message"]


def test_gemini_error_during_repair_is_an_error(tmp_path):
    stages, _ = make_stages(tmp_path)

    def repair(code, failure, spec, testbench=""):
        raise GeminiCallFailed("quota exceeded")

    def loop(design, tb, spec, repair, verify, outdir):
        try:
            repair("code", {}, spec)  # the real loop records the exception and carries on
        except Exception:
            pass
        return {"success": False, "iterations": 0, "final_file": design,
                "history": [{"kind": "repair_error", "log": "quota exceeded"}]}

    stages["repair"], stages["repair_loop"] = repair, loop
    result = run_pipeline("x", **stages)
    assert (result["status"], result["stage"]) == ("ERROR", "verify")


def test_lint_findings_are_advisory_and_do_not_change_the_verdict(tmp_path):
    stages, _ = make_stages(tmp_path, design_text=BLOCKING)
    result = run_pipeline("x", **stages)
    assert result["status"] == "PASS"
    assert any(f["code"] == "H3" for f in result["lint"])


def test_report_failure_does_not_break_a_verified_run(tmp_path):
    stages, _ = make_stages(tmp_path)

    def report(result):
        raise RuntimeError("disk full")

    stages["report"] = report
    result = run_pipeline("x", **stages)
    assert result["status"] == "PASS" and result["report"] is None
    assert any("report failed" in n for n in result["notes"])


class FakeClient:
    model = "fake-model"

    def __init__(self):
        self.stats = [{"ok": True, "attempt": 1, "latency_s": 0.5,
                       "input_tokens": 10, "output_tokens": 20, "total_tokens": 30}]


def test_result_records_model_prompt_versions_and_gemini_calls(tmp_path):
    stages, _ = make_stages(tmp_path)
    result = run_pipeline("x", client=FakeClient(), **stages)
    assert result["model"] == "fake-model"
    assert result["gemini_calls"][0]["total_tokens"] == 30
    assert set(result["prompt_versions"]) == {"spec_intake", "rtl_gen", "testbench", "repair"}
    assert all(v.startswith("v") for v in result["prompt_versions"].values())


def test_missing_api_key_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = run_pipeline("x")  # no stages injected, so the real client is requested
    assert (result["status"], result["stage"]) == ("ERROR", "spec_intake")