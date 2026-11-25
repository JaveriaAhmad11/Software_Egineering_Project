"""Unit tests for main.py (SCRUM-27). The LLM is never called: generate/verify are injected fakes."""
from pathlib import Path
from agents.repair.agent import RepairError
from agents.testbench.agent import InvalidTestbenchError
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
# ---- --repair (SCRUM-45): real loop controller; harness, repair and testbench agent are fakes ----

RUN_PASS = {"compiled": True, "simulated": True, "timed_out": False, "errors": [], "log": "PASS count=10\n"}
RUN_SYNTAX = {"compiled": False, "simulated": False, "timed_out": False,
              "errors": [{"file": "d.v", "line": 3, "message": "syntax error"}], "log": ""}
RUN_COMPILES_ALONE = {"compiled": True, "simulated": False, "timed_out": False, "errors": [], "log": ""}


def verify_by_content(path, testbench=None, **kw):
    """Fake harness: a design that contains BROKEN fails to compile, anything else passes."""
    return RUN_SYNTAX if "BROKEN" in Path(path).read_text(encoding="utf-8") else RUN_PASS


class FakeRepair:
    """Stands in for repair_verilog: counts calls and records the testbench text it was given."""

    def __init__(self, reply="module d; endmodule\n"):
        self.reply, self.calls, self.testbenches = reply, 0, []

    def __call__(self, code, failure, spec, testbench=""):
        self.calls += 1
        self.testbenches.append(testbench)
        return self.reply(self.calls) if callable(self.reply) else self.reply


@pytest.fixture
def repair_files(tmp_path, monkeypatch):
    """A broken design and a testbench in tmp_path; repair attempts are written there too."""
    monkeypatch.setattr(cli, "REPAIR_DIR", tmp_path / "attempts")
    design = tmp_path / "d.v"
    design.write_text("module d; BROKEN endmodule\n", encoding="utf-8")
    tb = tmp_path / "tb.v"
    tb.write_text("module tb; endmodule\n", encoding="utf-8")
    return design, tb


def repair_args(design, tb):
    return ["--verify", str(design), "--tb", str(tb), "--repair"]


def test_repair_fixes_a_failing_design(repair_files, capsys):
    design, tb = repair_files
    repair = FakeRepair()
    code = cli.main(repair_args(design, tb), verify=verify_by_content, repair=repair)
    out = capsys.readouterr().out
    assert code == 0 and "RESULT: PASS (repaired with 1 repair)" in out
    assert "original  : compile_error" in out and "repair 1  : ok" in out
    assert "BROKEN" in design.read_text(encoding="utf-8")             # the original is never overwritten
    assert repair.calls == 1 and "module tb" in repair.testbenches[0]  # the model saw the testbench


def test_repair_is_not_called_for_a_passing_design(repair_files, capsys):
    design, tb = repair_files
    design.write_text("module d; endmodule\n", encoding="utf-8")
    repair = FakeRepair()
    code = cli.main(repair_args(design, tb), verify=verify_by_content, repair=repair)
    assert code == 0 and "no repair needed" in capsys.readouterr().out
    assert repair.calls == 0


def test_repair_gives_up_after_three_repairs(repair_files, capsys):
    design, tb = repair_files
    repair = FakeRepair(reply=lambda n: f"module d; BROKEN {n} endmodule\n")
    code = cli.main(repair_args(design, tb), verify=verify_by_content, repair=repair)
    out = capsys.readouterr().out
    assert code == 1 and repair.calls == 3
    assert "RESULT: FAIL (compile_error; 3 repairs applied; manual review needed)" in out


def test_without_the_flag_nothing_is_repaired(repair_files, capsys):
    design, tb = repair_files
    repair = FakeRepair()
    code = cli.main(["--verify", str(design), "--tb", str(tb)], verify=verify_by_content, repair=repair)
    assert code == 1 and repair.calls == 0
    assert "RESULT: FAIL" in capsys.readouterr().out


def test_repair_on_an_existing_file_needs_a_testbench(repair_files):
    design, _ = repair_files
    with pytest.raises(SystemExit) as exc:
        cli.main(["--verify", str(design), "--repair"])
    assert exc.value.code == 2


def test_repair_generates_a_testbench_when_none_is_given(repair_files, capsys):
    design, tb = repair_files
    specs = []

    def fake_tb(code, spec):
        specs.append(spec)
        return tb

    code = cli.main(["counter", "--repair"], generate=lambda request: design,
                    verify=verify_by_content, repair=FakeRepair(), generate_tb=fake_tb)
    out = capsys.readouterr().out
    assert code == 0 and specs == ["counter"]
    assert "Step 2/3 : generating a testbench" in out and "Step 3/3" in out
    assert "not validated" in out


def test_testbench_generation_failure_is_a_fail(repair_files, capsys):
    design, _ = repair_files

    def bad_tb(code, spec):
        raise InvalidTestbenchError("no $finish")

    code = cli.main(["counter", "--repair"], generate=lambda request: design, generate_tb=bad_tb)
    assert code == 1 and "FAIL (testbench generation)" in capsys.readouterr().out


def test_missing_api_key_during_repair_is_one_clear_line(repair_files, capsys):
    design, tb = repair_files

    def no_key(code, failure, spec, testbench=""):
        raise GeminiConfigError("GEMINI_API_KEY not found. Check your .env file.")

    code = cli.main(repair_args(design, tb), verify=verify_by_content, repair=no_key)
    captured = capsys.readouterr()
    assert code == 2 and "GEMINI_API_KEY" in captured.err
    assert "Traceback" not in captured.out + captured.err


def test_api_failure_during_repair_is_an_error(repair_files, capsys):
    design, tb = repair_files

    def down(code, failure, spec, testbench=""):
        raise GeminiCallFailed("Gemini call failed after 3 attempts")

    code = cli.main(repair_args(design, tb), verify=verify_by_content, repair=down)
    assert code == 2 and "failed after 3 attempts" in capsys.readouterr().err


def test_unusable_repair_reply_is_a_fail_not_an_error(repair_files, capsys):
    design, tb = repair_files

    def bad_reply(code, failure, spec, testbench=""):
        raise RepairError("repair changed the module name or ports")

    code = cli.main(repair_args(design, tb), verify=verify_by_content, repair=bad_reply)
    out = capsys.readouterr().out
    assert code == 1 and "stopped - repair changed the module name or ports" in out
    assert "RESULT: FAIL (repair rejected; 0 repairs applied" in out


def test_testbench_problem_is_not_sent_to_repair(repair_files, capsys):
    design, tb = repair_files
    tb_broken = {**RUN_SYNTAX, "errors": [{"file": str(tb), "line": 2, "message": "syntax error"}]}

    def verify(path, testbench=None, **kw):
        return tb_broken if testbench else RUN_COMPILES_ALONE  # the design compiles on its own

    repair = FakeRepair()
    code = cli.main(repair_args(design, tb), verify=verify, repair=repair)
    out = capsys.readouterr().out
    assert code == 1 and repair.calls == 0
    assert "RESULT: FAIL (testbench_error; 0 repairs applied" in out


@needs_iverilog
def test_real_broken_fixture_is_repaired_by_the_loop(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "REPAIR_DIR", tmp_path)
    good = (FIX / "counter_good.v").read_text(encoding="utf-8")
    code = cli.main(
        ["--verify", str(FIX / "counter_bad.v"), "--tb", str(FIX / "counter_tb.v"), "--repair"],
        repair=lambda src, failure, spec, testbench="": good,
    )
    assert code == 0 and "RESULT: PASS (repaired with 1 repair)" in capsys.readouterr().out