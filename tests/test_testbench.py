"""Tests for the testbench generator (S2-06). The LLM is mocked: no API key needed."""
from pathlib import Path

import pytest

from agents.rtl_gen.agent import RTLGenerationError
from agents.testbench import agent as tb

DUT = "module counter8 (input clk, input rst_n, output reg [7:0] count);\n" \
      "  always @(posedge clk) if (!rst_n) count <= 8'd0; else count <= count + 8'd1;\nendmodule\n"

GOOD_TB = """`timescale 1ns/1ps
module counter8_tb;
  reg clk = 0, rst_n = 0;
  wire [7:0] count;
  integer errors = 0;
  counter8 dut (.clk(clk), .rst_n(rst_n), .count(count));
  always #5 clk = ~clk;
  initial begin
    #1000000; $display("FAIL: watchdog timeout"); $finish;
  end
  initial begin
    repeat (3) @(negedge clk);
    if (count !== 8'd0) errors = errors + 1;
    if (errors == 0) $display("PASS"); else $display("FAIL: %0d mismatches", errors);
    $finish;
  end
endmodule"""


class FakeClient:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.reply


def fenced(code):
    return f"```verilog\n{code}\n```"


# ---- AC1: <module>_tb.v is written with the agreed pieces ---------------------------------
def test_saves_module_tb_with_required_pieces(tmp_path):
    path = tb.generate_testbench(DUT, "8-bit counter", client=FakeClient(fenced(GOOD_TB)), out_dir=tmp_path)
    text = path.read_text()
    assert path.name == "counter8_tb.v" and path.parent == tmp_path
    for piece in ("`timescale", "counter8 dut", "always #5 clk", "rst_n", "PASS", "FAIL", "$finish"):
        assert piece in text


def test_prompt_contains_spec_and_design(tmp_path):
    client = FakeClient(fenced(GOOD_TB))
    tb.generate_testbench(DUT, "counts up by one, wraps at 255", client=client, out_dir=tmp_path)
    prompt = client.prompts[0]
    assert "counts up by one, wraps at 255" in prompt and "module counter8" in prompt
    assert "Testbench Generation System Prompt - v1.0" in prompt


# ---- AC2: fences and prose are handled, exactly one testbench module is validated ----------
def test_prose_around_the_fence_is_ignored(tmp_path):
    reply = "Sure! Here is your testbench:\n" + fenced(GOOD_TB) + "\nHope it helps."
    path = tb.generate_testbench(DUT, "counter", client=FakeClient(reply), out_dir=tmp_path)
    assert path.read_text().startswith("`timescale")


def test_reply_without_fence_still_works(tmp_path):
    assert tb.generate_testbench(DUT, "counter", client=FakeClient(GOOD_TB), out_dir=tmp_path).exists()


@pytest.mark.parametrize(
    "reply, why",
    [
        ("I cannot write that.", "no module"),
        (fenced(GOOD_TB + "\nmodule extra; endmodule"), "two modules"),
        (fenced(GOOD_TB.replace("$finish", "")), "no $finish"),
        (fenced(GOOD_TB.replace("counter8 dut", "other_unit dut")), "no DUT instance"),
        (fenced(GOOD_TB.replace('$display("PASS")', '$display("ok")')), "no PASS"),
        (fenced(GOOD_TB.replace("FAIL", "BAD")), "no FAIL"),
        (fenced(GOOD_TB.replace("`timescale 1ns/1ps\n", "")), "no timescale"),
        (fenced(GOOD_TB.replace("module counter8_tb", "module counter8")), "same name as design"),
    ],
)
def test_bad_replies_are_rejected_and_nothing_is_written(tmp_path, reply, why):
    with pytest.raises(tb.InvalidTestbenchError):
        tb.generate_testbench(DUT, "counter", client=FakeClient(reply), out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == [], why


def test_design_with_two_modules_fails_before_the_model_is_called(tmp_path):
    client = FakeClient(fenced(GOOD_TB))
    with pytest.raises(RTLGenerationError):
        tb.generate_testbench("module a(); endmodule\nmodule b(); endmodule", "x", client=client, out_dir=tmp_path)
    assert client.prompts == []


# ---- AC3: runs with a mocked client; AC4: prompt folder is complete and versioned ----------
def test_prompt_folder_has_prompt_and_changelog():
    folder = Path(tb.PROMPT_PATH).parent
    assert folder.name == "v1.0" and (folder / "system_prompt.md").is_file() and (folder / "CHANGELOG.md").is_file()
    assert "v1.0" in (folder / "CHANGELOG.md").read_text()
    assert "v1.0" in tb.load_system_prompt()


def test_missing_api_key_is_a_clear_error(monkeypatch, capsys):
    from agents.gemini_client import GeminiConfigError  # noqa: F401  (documented behaviour of the client)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(tb, "GeminiClient", lambda: (_ for _ in ()).throw(GeminiConfigError("GEMINI_API_KEY not found.")))
    design = Path(__file__).parent / "fixtures" / "counter_good.v"
    assert tb._cli(["generate", str(design), "8-bit", "counter"]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err
