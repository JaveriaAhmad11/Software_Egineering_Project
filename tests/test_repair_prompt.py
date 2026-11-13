from agents.repair.prompt import (MAX_LOG_CHARS, PROMPT_PATH, PROMPT_VERSION,
                                  build_repair_prompt, format_failure)

CODE = "module m (input clk, output y);\nendmodule"
FAILURE = {"kind": "compile_error",
           "errors": [{"file": "/tmp/x/counter8.v", "line": 3, "message": "syntax error"}],
           "log": ""}


def test_prompt_contains_spec_code_and_failure():
    p = build_repair_prompt("8-bit counter", CODE, FAILURE)
    assert "8-bit counter" in p and CODE in p
    assert "kind: compile_error" in p
    assert "counter8.v:3: syntax error" in p


def test_missing_spec_is_marked():
    assert "(not provided)" in build_repair_prompt("", CODE, FAILURE)


def test_empty_diagnostics_are_handled():
    text = format_failure({"kind": "compile_error", "errors": [], "log": ""})
    assert "no diagnostics provided" in text


def test_none_failure_is_handled():
    assert "kind: unknown" in format_failure(None)


def test_multiline_log_is_kept():
    text = format_failure({"kind": "assertion_failure", "errors": [],
                           "log": "FAIL count=3\nexpected count=10"})
    assert "FAIL count=3" in text and "expected count=10" in text


def test_long_log_keeps_the_tail():
    log = "start " + "x" * 5000 + " FAIL count=3"
    text = format_failure({"kind": "timeout", "errors": [], "log": log})
    assert "FAIL count=3" in text and "start" not in text
    assert len(text) < MAX_LOG_CHARS + 200


def test_error_without_file_uses_line_only():
    text = format_failure({"errors": [{"file": None, "line": 7, "message": "bad"}]})
    assert "line 7: bad" in text


def test_plain_string_errors_are_accepted():
    assert "- tool crashed" in format_failure({"errors": ["tool crashed"]})


def test_error_list_is_capped():
    errs = [{"file": None, "line": i, "message": f"e{i}"} for i in range(1, 30)]
    text = format_failure({"errors": errs})
    assert "e10" in text and "e11" not in text


def test_testbench_section_only_when_given():
    assert "TESTBENCH (reference only" not in build_repair_prompt("s", CODE, FAILURE)
    assert "module tb;" in build_repair_prompt("s", CODE, FAILURE, testbench="module tb;")


def test_prompt_file_states_the_key_rules():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    for needle in ("Verilog-2001", "port list", "#delay", "non-blocking"):
        assert needle in text


def test_prompt_is_versioned_with_a_changelog():
    assert PROMPT_PATH.parent.name == PROMPT_VERSION
    changelog = (PROMPT_PATH.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    assert PROMPT_VERSION in changelog