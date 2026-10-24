"""Unit tests for main.py (SCRUM-27). The LLM is never called: generate/verify are injected fakes."""
from pathlib import Path

import pytest

import main as cli
from agents.gemini_client import GeminiCallFailed, GeminiConfigError
from agents.rtl_gen.agent import RTLGenerationError
from agents.verifier.harness import _find_tool

FIX = Path(__file__).parent / "fixtures"
needs_iverilog = pytest.mark.skipif(
    _find_tool("iverilog") is None or _find_tool("vvp") is None, reason="iverilog/vvp not installed"
)


def ok_result(**kw):
    base = {"compiled": True, "simulated": False, "timed_out": False, "errors": [], "log": ""}
    return {**base, **kw}


def fake_generate(request):
    return Path("outputs/counter_8bit.v")


def test_pass_when_design_compiles(capsys):
    code = cli.main(["8-bit counter"], generate=fake_generate, verify=lambda *a, **k: ok_result())
    out = capsys.readouterr().out
    assert code == 0 and "RESULT: PASS" in out and "rtl_gen v1.0" in out


def test_fail_prints_error_lines(capsys):
    bad = ok_result(compiled=False, errors=[{"file": "x.v", "line": 3, "message": "syntax error"}])
    code = cli.main(["counter"], generate=fake_generate, verify=lambda *a, **k: bad)
    out = capsys.readouterr().out
    assert code == 1 and "RESULT: FAIL" in out and "x.v:3: syntax error" in out


def test_missing_api_key_is_one_clear_line(capsys):
    def boom(request):
        raise GeminiConfigError("GEMINI_API_KEY not found. Check your .env file.")

    code = cli.main(["counter"], generate=boom)
    captured = capsys.readouterr()
    assert code == 2 and "GEMINI_API_KEY" in captured.err
    assert "Traceback" not in captured.out + captured.err


def test_api_failure_is_reported_not_raised(capsys):
    def boom(request):
        raise GeminiCallFailed("Gemini call failed after 3 attempts")

    assert cli.main(["counter"], generate=boom) == 2
    assert "failed after 3 attempts" in capsys.readouterr().err


def test_unusable_model_output_is_a_fail(capsys):
    def boom(request):
        raise RTLGenerationError("Expected exactly one module/endmodule, found 0/0")

    assert cli.main(["counter"], generate=boom) == 1
    assert "FAIL (generation)" in capsys.readouterr().out


def test_testbench_printing_fail_word_is_a_fail():
    r = ok_result(simulated=True, log="FAIL count=3\n")
    code = cli.main(["counter", "--tb", "tb.v"], generate=fake_generate, verify=lambda *a, **k: r)
    assert code == 1


def test_verify_mode_never_calls_the_model():
    def must_not_run(request):
        raise AssertionError("generate was called")

    code = cli.main(["--verify", "d.v"], generate=must_not_run, verify=lambda *a, **k: ok_result())
    assert code == 0


def test_needs_request_or_verify():
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


@needs_iverilog
def test_real_good_design_passes(capsys):
    code = cli.main(["--verify", str(FIX / "counter_good.v"), "--tb", str(FIX / "counter_tb.v")])
    assert code == 0 and "RESULT: PASS" in capsys.readouterr().out


@needs_iverilog
def test_real_broken_design_fails_with_error_line(capsys):
    code = cli.main(["--verify", str(FIX / "counter_bad.v"), "--tb", str(FIX / "counter_tb.v")])
    out = capsys.readouterr().out
    assert code == 1 and "RESULT: FAIL" in out and "error" in out
