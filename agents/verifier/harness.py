"""Verifier harness (SCRUM-26): compile Verilog with Icarus and run the simulation.

The harness is the ground truth: model output is never trusted without a real compile/run.
Returns a structured dict so the Sprint 2-3 repair agent can feed errors back to the LLM.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT = 10  # seconds, applies to compile and to simulation separately

_WINDOWS_DIRS = [
    r"C:\iverilog\bin",
    r"C:\Program Files\Icarus Verilog\bin",
    r"C:\Program Files (x86)\Icarus Verilog\bin",
]
_ERR_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):\s*(?P<message>.*)$")


def _find_tool(name: str) -> str | None:
    """Find iverilog/vvp on PATH, falling back to common Windows install folders."""
    path = shutil.which(name)
    if path:
        return path
    for folder in _WINDOWS_DIRS:
        for ext in (".exe", ""):
            candidate = Path(folder) / (name + ext)
            if candidate.exists():
                return str(candidate)
    return None


def _to_text(data) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _run(cmd: list[str], cwd: str, timeout: float):
    """Run a command; returns (returncode, stdout, stderr, timed_out). Never uses a shell."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        return -1, _to_text(e.stdout), _to_text(e.stderr), True


def _parse_errors(stderr: str) -> list[dict]:
    errors = []
    for line in stderr.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _ERR_RE.match(line)
        if m:
            errors.append({"file": m["file"], "line": int(m["line"]), "message": m["message"]})
        else:
            errors.append({"file": None, "line": None, "message": line})
    return errors


def run_verification(design_file, testbench_file=None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Compile (and simulate, if a testbench is given) a Verilog design.

    Returns {compiled, simulated, timed_out, errors, log}.
    simulated is True only if vvp exited cleanly without hitting the timeout.
    """
    result = {"compiled": False, "simulated": False, "timed_out": False, "errors": [], "log": ""}

    iverilog, vvp = _find_tool("iverilog"), _find_tool("vvp")
    if not iverilog or not vvp:
        result["errors"].append({"file": None, "line": None,
                                 "message": "iverilog/vvp not found. Install Icarus Verilog and add it to PATH."})
        return result

    sources = [Path(design_file)] + ([Path(testbench_file)] if testbench_file else [])
    for s in sources:
        if not s.is_file():
            result["errors"].append({"file": str(s), "line": None, "message": "file not found"})
            return result

    with tempfile.TemporaryDirectory() as tmp:  # isolated working dir; sim.out never pollutes the repo
        names = []
        for s in sources:
            shutil.copy(s, Path(tmp) / s.name)
            names.append(s.name)

        rc, out, err, timed_out = _run([iverilog, "-o", "sim.out", *names], tmp, timeout)
        result["log"] += out + err
        if timed_out:
            result["timed_out"] = True
            result["errors"].append({"file": None, "line": None, "message": f"compile timed out after {timeout}s"})
            return result
        if rc != 0:
            result["errors"] = _parse_errors(err)
            return result
        result["compiled"] = True

        if not testbench_file:  # compile-only (syntax check)
            return result

        rc, out, err, timed_out = _run([vvp, "sim.out"], tmp, timeout)
        result["log"] += out + err
        if timed_out:
            result["timed_out"] = True
            result["errors"].append({"file": None, "line": None, "message": f"simulation timed out after {timeout}s"})
        elif rc != 0:
            result["errors"] = _parse_errors(err) or [{"file": None, "line": None, "message": f"vvp exited with code {rc}"}]
        else:
            result["simulated"] = True
    return result


if __name__ == "__main__":  # python -m agents.verifier.harness design.v [testbench.v]
    if len(sys.argv) < 2:
        sys.exit("usage: python -m agents.verifier.harness design.v [testbench.v]")
    print(json.dumps(run_verification(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), indent=2))
