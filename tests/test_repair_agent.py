from pathlib import Path

import pytest

from agents.repair.agent import RepairError, port_signature, repair_verilog
from agents.verifier.harness import _find_tool, run_verification

FIX = Path(__file__).parent / "fixtures"

GOOD = (
    "module counter8 (input clk, input rst_n, output reg [7:0] count);\n"
    "always @(posedge clk) begin\n"
    "  if (!rst_n) count <= 8'd0;\n"
    "  else count <= count + 8'd1;\n"
    "end\n"
    "endmodule"
)
BROKEN = GOOD.replace("count <= 8'd0;", "count <= 8'd0")  # missing semicolon
FAILURE = {"kind": "compile_error",
           "errors": [{"file": "counter8.v", "line": 3, "message": "syntax error"}],
           "log": ""}

needs_iverilog = pytest.mark.skipif(
    _find_tool("iverilog") is None or _find_tool("vvp") is None,
    reason="iverilog/vvp not installed",
)


class FakeClient:
    """Stands in for GeminiClient: records prompts and returns a canned reply."""

    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.reply


def fenced(code):
    return "```verilog\n" + code + "\n```"


# ---- port signature -------------------------------------------------------

def test_signature_ignores_comments_and_spacing():
    a = "module m ( input  clk, // clock\n output y );\nendmodule"
    b = "module m (input clk, output y);\nendmodule"
    assert port_signature(a) == port_signature(b)


def test_direction_and_width_are_inherited():
    _, ports = port_signature("module m (input [7:0] a, b, output y);\nendmodule")
    assert ports == [("input", "[7:0]", "a"), ("input", "[7:0]", "b"), ("output", "", "y")]


def test_parameterised_header_is_parsed():
    name, ports = port_signature(
        "module m #(parameter W = 8) (input [W-1:0] a, output y);\nendmodule")
    assert name == "m"
    assert ports == [("input", "[W-1:0]", "a"), ("output", "", "y")]


def test_unparsable_header_raises():
    with pytest.raises(RepairError):
        port_signature("module m (input clk)\nendmodule")


# ---- repair behaviour -----------------------------------------------------

def test_returns_code_from_fenced_reply():
    client = FakeClient(fenced(GOOD))
    assert repair_verilog(BROKEN, FAILURE, "8-bit counter", client=client) == GOOD


def test_unfenced_reply_is_accepted():
    assert repair_verilog(BROKEN, FAILURE, client=FakeClient(GOOD)) == GOOD


def test_failure_and_spec_reach_the_model():
    client = FakeClient(fenced(GOOD))
    repair_verilog(BROKEN, FAILURE, "8-bit counter", client=client)
    prompt = client.prompts[0]
    assert "syntax error" in prompt and "8-bit counter" in prompt and BROKEN in prompt


def test_testbench_is_forwarded_when_given():
    client = FakeClient(fenced(GOOD))
    repair_verilog(BROKEN, FAILURE, client=client, testbench="module counter_tb; endmodule")
    assert "module counter_tb; endmodule" in client.prompts[0]


@pytest.mark.parametrize("changed", [
    GOOD.replace("[7:0]", "[3:0]"),                                   # width changed
    GOOD.replace("counter8", "counter9"),                             # module renamed
    GOOD.replace("input rst_n, ", ""),                                # port removed
    GOOD.replace("output reg [7:0] count", "output reg [7:0] count, output extra"),  # port added
    GOOD.replace("input clk, input rst_n", "input rst_n, input clk"),  # order changed
])
def test_interface_changes_are_rejected(changed):
    with pytest.raises(RepairError):
        repair_verilog(BROKEN, FAILURE, client=FakeClient(fenced(changed)))


def test_prose_reply_is_rejected():
    with pytest.raises(RepairError):
        repair_verilog(BROKEN, FAILURE, client=FakeClient("I could not fix this module."))


def test_two_modules_are_rejected():
    two = GOOD + "\n" + GOOD.replace("counter8", "other")
    with pytest.raises(RepairError):
        repair_verilog(BROKEN, FAILURE, client=FakeClient(fenced(two)))


def test_unchanged_code_is_rejected():
    with pytest.raises(RepairError):
        repair_verilog(GOOD, FAILURE, client=FakeClient(fenced(GOOD)))


def test_unparsable_original_header_skips_the_guard():
    broken_header = GOOD.replace("count);", "count)")
    assert repair_verilog(broken_header, FAILURE, client=FakeClient(fenced(GOOD))) == GOOD


def test_repair_never_writes_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repair_verilog(BROKEN, FAILURE, client=FakeClient(fenced(GOOD)))
    assert list(tmp_path.iterdir()) == []


@needs_iverilog
def test_broken_design_fails_and_repaired_design_passes_the_real_harness(tmp_path):
    tb = FIX / "counter_tb.v"
    broken = tmp_path / "broken.v"
    broken.write_text(BROKEN + "\n", encoding="utf-8")
    assert not run_verification(broken, tb)["compiled"]

    fixed = repair_verilog(BROKEN, FAILURE, client=FakeClient(fenced(GOOD)))
    repaired = tmp_path / "repaired.v"
    repaired.write_text(fixed + "\n", encoding="utf-8")
    result = run_verification(repaired, tb)
    assert result["compiled"] and result["simulated"] and "PASS" in result["log"]