"""Tests for the shared lint module (SCRUM-51). No API key and no Icarus needed."""
import pytest

from agents.verifier.lint import as_text, check_rtl, strip_comments
from tests import run_prompt_cases as runner

GOOD = (
    "module counter8 (input clk, input rst_n, output reg [7:0] count);\n"
    "always @(posedge clk) begin\n"
    "  if (!rst_n) count <= 8'd0;\n"
    "  else count <= count + 8'd1;\n"
    "end\n"
    "endmodule"
)


def codes(code, ports=None):
    return [f["code"] for f in check_rtl(code, ports)]


# ---- clean code ---------------------------------------------------------------------------

def test_clean_module_has_no_findings():
    assert check_rtl(GOOD, ["clk", "rst_n", "count"]) == []


def test_findings_have_code_line_and_message():
    finding = check_rtl(GOOD.replace("count <= 8'd0;", "#5 count <= 8'd0;"))[0]
    assert set(finding) == {"code", "line", "message"}


# ---- H0 / H5 ------------------------------------------------------------------------------

def test_h0_missing_endmodule_stops_further_checks():
    assert codes("module m (input a);\nalways @(posedge a) #5 a = 1;\n") == ["H0"]


def test_h0_prose_reply():
    assert codes("Sorry, I cannot write that module.") == ["H0"]


def test_h0_endmodule_alone_is_not_a_module():
    assert codes("endmodule") == ["H0"]


def test_h5_fences_are_reported_before_h0():
    assert codes("```verilog\nmodule m;\n```") == ["H5", "H0"]


def test_h5_fences_around_a_good_module():
    assert codes("```verilog\n" + GOOD + "\n```") == ["H5"]


# ---- H2 -----------------------------------------------------------------------------------

def test_h2_delay_is_flagged_with_its_line():
    code = GOOD.replace("count <= 8'd0;", "#5 count <= 8'd0;")
    finding = check_rtl(code)[0]
    assert finding["code"] == "H2" and finding["line"] == 3


def test_h2_delay_in_comments_is_ignored():
    code = GOOD.replace("module counter8", "// wait #10 cycles\n/* #5\n#7 */\nmodule counter8")
    assert check_rtl(code) == []


def test_h2_reports_only_the_first_delay():
    code = GOOD.replace("count <= 8'd0;", "#5 count <= 8'd0;").replace("count + 8'd1;", "#9 count + 8'd1;")
    assert codes(code) == ["H2"]


# ---- H3 -----------------------------------------------------------------------------------

def test_h3_blocking_in_posedge_block():
    code = GOOD.replace("else count <= count + 8'd1;", "else count = count + 8'd1;")
    finding = check_rtl(code)[0]
    assert finding["code"] == "H3" and finding["line"] == 4


def test_h3_blocking_in_negedge_block():
    code = GOOD.replace("posedge", "negedge").replace("count <= count", "count = count")
    assert codes(code) == ["H3"]


def test_h3_single_statement_block_without_begin():
    code = "module m (input clk, input d, output reg q);\nalways @(posedge clk) q = d;\nendmodule"
    assert codes(code) == ["H3"]


def test_h3_nonblocking_is_fine():
    assert "H3" not in codes(GOOD)


def test_h3_blocking_in_combinational_block_is_fine():
    code = "module m (input a, input b, output reg y);\nalways @(*) begin\n  y = a & b;\nend\nendmodule"
    assert check_rtl(code) == []


def test_h3_for_loop_header_is_not_flagged():
    code = ("module m (input clk, output reg [3:0] q);\ninteger i;\n"
            "always @(posedge clk) begin\n  for (i = 0; i < 4; i = i + 1) q[i] <= 1'b0;\nend\nendmodule")
    assert check_rtl(code) == []


def test_h3_for_header_with_nested_parentheses():
    code = ("module m (input clk, output reg [3:0] q);\ninteger i;\n"
            "always @(posedge clk) begin\n  for (i = 0; i < (2 + 2); i = i + 1) q[i] <= 1'b0;\nend\nendmodule")
    assert check_rtl(code) == []


def test_h3_comparison_operators_are_not_assignments():
    code = ("module m (input clk, input a, input b, output reg q);\n"
            "always @(posedge clk) begin\n  if (a === b) q <= 1'b1;\n  else if (a !== b) q <= 1'b0;\n"
            "  else if (a >= b) q <= 1'b1;\nend\nendmodule")
    assert check_rtl(code) == []


def test_h3_block_ends_at_its_own_end():
    code = ("module m (input clk, input a, output reg q, output reg y);\n"
            "always @(posedge clk) begin\n  q <= a;\nend\n"
            "always @(*) begin\n  y = a;\nend\nendmodule")
    assert check_rtl(code) == []


# ---- H1 -----------------------------------------------------------------------------------

def test_h1_missing_port_is_reported():
    findings = check_rtl(GOOD, ["clk", "en"])
    assert [(f["code"], f["message"]) for f in findings] == [("H1", "missing port en")]


def test_h1_every_missing_port_is_reported():
    assert codes(GOOD, ["en", "valid"]) == ["H1", "H1"]


def test_h1_not_checked_without_expected_ports():
    assert "H1" not in codes(GOOD)


def test_h1_port_named_only_in_a_comment_does_not_count():
    code = GOOD.replace("module counter8 (", "module counter8 ( // en is optional\n")
    assert codes(code, ["en"]) == ["H1"]


# ---- L1 -----------------------------------------------------------------------------------

LATCH_IF = ("module m (input a, input b, output reg y);\nalways @(*) begin\n  if (a) y = b;\nend\nendmodule")


def test_l1_if_without_else():
    finding = check_rtl(LATCH_IF)[0]
    assert finding["code"] == "L1" and "if without else" in finding["message"] and finding["line"] == 2


def test_l1_if_with_else_is_fine():
    assert check_rtl(LATCH_IF.replace("y = b;", "y = b; else y = 1'b0;")) == []


def test_l1_else_if_chain_without_final_else():
    code = ("module m (input a, input b, output reg y);\nalways @(*) begin\n"
            "  if (a) y = 1'b1;\n  else if (b) y = 1'b0;\nend\nendmodule")
    assert codes(code) == ["L1"]


def test_l1_case_without_default():
    code = ("module m (input [1:0] s, output reg y);\nalways @(*) begin\n  case (s)\n"
            "    2'd0: y = 1'b1;\n    2'd1: y = 1'b0;\n  endcase\nend\nendmodule")
    finding = check_rtl(code)[0]
    assert finding["code"] == "L1" and "case without default" in finding["message"]


def test_l1_case_with_default_is_fine():
    code = ("module m (input [1:0] s, output reg y);\nalways @(*) begin\n  case (s)\n"
            "    2'd0: y = 1'b1;\n    default: y = 1'b0;\n  endcase\nend\nendmodule")
    assert check_rtl(code) == []


def test_l1_default_assigned_first_is_fine():
    code = ("module m (input a, output reg y);\nalways @(*) begin\n  y = 1'b0;\n  if (a) y = 1'b1;\nend\nendmodule")
    assert check_rtl(code) == []


def test_l1_old_style_sensitivity_list_counts_as_combinational():
    assert codes(LATCH_IF.replace("@(*)", "@(a or b)")) == ["L1"]


def test_l1_single_statement_if_else_is_fine():
    code = "module m (input a, output reg y);\nalways @* if (a) y = 1'b1; else y = 1'b0;\nendmodule"
    assert check_rtl(code) == []


def test_l1_clocked_if_without_else_is_not_a_latch():
    code = GOOD.replace("\n  else count <= count + 8'd1;", "")
    assert check_rtl(code) == []


# ---- helpers ------------------------------------------------------------------------------

def test_strip_comments_keeps_length_and_lines():
    src = "a // x\nb /* y\nz */ c\n"
    out = strip_comments(src)
    assert len(out) == len(src) and out.count("\n") == src.count("\n")
    assert "x" not in out and "y" not in out and "a" in out and "c" in out


def test_as_text_is_code_and_message():
    assert as_text({"code": "H2", "line": 3, "message": "#delay used"}) == "H2 #delay used"


# ---- the prompt runner uses this module and keeps its Sprint 1 output ------------------------

def test_runner_keeps_no_copy_of_the_rules():
    assert not hasattr(runner, "clocked_blocks")


@pytest.mark.parametrize("code, ports, expected", [
    (GOOD, ["clk", "rst_n", "count"], []),
    ("```verilog\n" + GOOD + "\n```", ["clk"], ["H5 markdown fences in output"]),
    (GOOD.replace("count <= 8'd0;", "#5 count <= 8'd0;"), ["clk"], ["H2 #delay used"]),
    (GOOD.replace("else count <= count + 8'd1;", "else count = count + 8'd1;"), ["clk"],
     ["H3 blocking '=' in clocked block"]),
    (GOOD, ["clk", "en"], ["H1 missing port en"]),
    ("no module here", ["clk"], ["H0 missing module/endmodule"]),
])
def test_runner_check_rules_output_is_unchanged(code, ports, expected):
    assert runner.check_rules(code, ports) == expected


def test_runner_does_not_list_advisory_latch_warnings():
    assert runner.check_rules(LATCH_IF, ["a", "b", "y"]) == []
    assert codes(LATCH_IF) == ["L1"]