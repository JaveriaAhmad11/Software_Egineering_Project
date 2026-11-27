"""Tests for agents/verifier/lint.py (SCRUM-51): one positive and one negative case per rule."""
from agents.verifier.lint import FENCE, check_rtl, format_finding

GOOD = """module counter(input clk, input rst, output reg [7:0] q);
always @(posedge clk) begin
  if (rst) q <= 8'd0;
  else q <= q + 1;
end
endmodule
"""


def codes(code, ports=()):
    return [f["code"] for f in check_rtl(code, ports)]


# H0 - module/endmodule
def test_h0_positive():
    assert "H0" in codes("assign x = 1;")

def test_h0_negative():
    assert "H0" not in codes(GOOD)


# H1 - expected ports
def test_h1_positive():
    findings = check_rtl(GOOD, ["clk", "en"])
    assert [f["message"] for f in findings if f["code"] == "H1"] == ["missing port en"]

def test_h1_negative():
    assert "H1" not in codes(GOOD, ["clk", "rst", "q"])

def test_h1_port_only_in_comment_is_missing():
    code = GOOD.replace("module counter(", "module counter(/* en */ ")
    assert "H1" in codes(code, ["en"])


# H2 - #delay
def test_h2_positive():
    code = "module m(input clk, output reg q);\nalways @(posedge clk) #5 q <= 1'b1;\nendmodule\n"
    assert "H2" in codes(code)

def test_h2_negative():
    assert "H2" not in codes(GOOD)


# H3 - blocking assignment in clocked block
def test_h3_positive_with_line_number():
    code = ("module m(input clk, output reg [7:0] q);\n"
            "always @(posedge clk) begin\n"
            "  q = q + 1;\n"
            "end\nendmodule\n")
    h3 = [f for f in check_rtl(code) if f["code"] == "H3"]
    assert len(h3) == 1 and h3[0]["line"] == 3

def test_h3_negative():
    assert "H3" not in codes(GOOD)


# H5 - markdown fences
def test_h5_positive():
    assert "H5" in codes(FENCE + "verilog\n" + GOOD + FENCE)

def test_h5_negative():
    assert "H5" not in codes(GOOD)


# L1 - latch heuristic
LATCH_IF = """module m(input a, input b, output reg y);
always @(*) begin
  if (a) y = b;
end
endmodule
"""
NO_LATCH_IF = LATCH_IF.replace("if (a) y = b;", "if (a) y = b; else y = 1'b0;")
LATCH_CASE = """module m(input [1:0] s, input a, input b, output reg y);
always @(*) begin
  case (s)
    2'b00: y = a;
    2'b01: y = b;
  endcase
end
endmodule
"""
NO_LATCH_CASE = LATCH_CASE.replace("endcase", "default: y = 1'b0;\n  endcase")

def test_l1_positive_if_without_else():
    assert "L1" in codes(LATCH_IF)

def test_l1_negative_if_with_else():
    assert "L1" not in codes(NO_LATCH_IF)

def test_l1_positive_case_without_default():
    assert "L1" in codes(LATCH_CASE)

def test_l1_negative_case_with_default():
    assert "L1" not in codes(NO_LATCH_CASE)

def test_l1_ignores_clocked_blocks():
    assert "L1" not in codes(GOOD)


# AC2 - comments and for-loop headers are not flagged
def test_comments_are_not_flagged():
    code = GOOD.replace("endmodule", "// q = q + 1; #10 delay\n/* q = 0; */\nendmodule")
    assert codes(code) == []

def test_for_loop_header_not_flagged():
    code = ("module m(input clk, input [7:0] d, output reg [7:0] q);\n"
            "integer i;\n"
            "always @(posedge clk) begin\n"
            "  for (i = 0; i < 8; i = i + 1) q[i] <= d[i];\n"
            "end\nendmodule\n")
    assert "H3" not in codes(code)


# AC3 - the runner keeps the old text format
def test_format_finding_matches_old_runner_format():
    assert format_finding({"code": "H2", "line": 1, "message": "#delay used"}) == "H2 #delay used"