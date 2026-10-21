import pytest
from agents.rtl_gen.agent import (
    RTLGenerationError,
    extract_verilog,
    generate_rtl,
    load_system_prompt,
    validate_verilog,
)

GOOD = """```verilog
module counter_8bit(input clk, input rst_n, output reg [7:0] q);
  always @(posedge clk) if (!rst_n) q <= 8'd0; else q <= q + 1'b1;
endmodule
```"""


class FakeClient:
    def __init__(self, reply):
        self.reply = reply

    def generate(self, prompt):
        return self.reply


def test_extract_removes_fence():
    assert extract_verilog(GOOD).startswith("module counter_8bit")


def test_validate_returns_module_name():
    assert validate_verilog(extract_verilog(GOOD)) == "counter_8bit"


def test_rejects_prose_reply():
    with pytest.raises(RTLGenerationError):
        validate_verilog("Sure! Here is a counter for you.")


def test_rejects_missing_endmodule():
    with pytest.raises(RTLGenerationError):
        validate_verilog("module foo(input a, output b);\nassign b = a;")


def test_rejects_two_modules():
    two = "module a(); endmodule\nmodule b(); endmodule"
    with pytest.raises(RTLGenerationError):
        validate_verilog(two)


def test_generate_saves_file(tmp_path):
    path = generate_rtl("8-bit counter", client=FakeClient(GOOD), out_dir=tmp_path)
    assert path.name == "counter_8bit.v" and path.exists()


def test_bad_reply_saves_nothing(tmp_path):
    with pytest.raises(RTLGenerationError):
        generate_rtl("counter", client=FakeClient("I cannot do that."), out_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_prompt_is_versioned():
    assert "v1.0" in load_system_prompt()