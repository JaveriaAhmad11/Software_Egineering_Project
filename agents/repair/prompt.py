"""Repair prompt loading and assembly (SCRUM-43)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = "v1.0"
PROMPT_PATH = ROOT / "prompts" / "repair" / PROMPT_VERSION / "system_prompt.md"
MAX_LOG_CHARS = 2000  # keep only the tail of long simulator logs (saves tokens)
MAX_ERRORS = 10


def load_repair_prompt(path=PROMPT_PATH) -> str:
    return Path(path).read_text(encoding="utf-8")


def _describe(err) -> str:
    if not isinstance(err, dict):
        return str(err)
    name = Path(err["file"]).name if err.get("file") else ""
    line = err.get("line")
    if name and line:
        place = f"{name}:{line}: "
    elif line:
        place = f"line {line}: "
    else:
        place = ""
    return f"{place}{err.get('message', '')}"


def format_failure(failure) -> str:
    """Turn a harness failure dict into the text block the model sees."""
    failure = failure or {}
    lines = [f"kind: {failure.get('kind', 'unknown')}"]
    errors = failure.get("errors") or []
    for err in errors[:MAX_ERRORS]:
        lines.append("- " + _describe(err))
    if not errors:
        lines.append("- (no diagnostics provided)")
    elif len(errors) > MAX_ERRORS:
        lines.append(f"- ... {len(errors) - MAX_ERRORS} more not shown")
    log = (failure.get("log") or "").strip()
    if log:
        if len(log) > MAX_LOG_CHARS:
            log = "..." + log[-MAX_LOG_CHARS:]
        lines.append("simulator log:")
        lines.append(log)
    return "\n".join(lines)


def build_repair_prompt(spec: str, code: str, failure, testbench: str = "") -> str:
    tb_section = (
        f"TESTBENCH (reference only, do not modify):\n{testbench}\n\n" if testbench else ""
    )
    return (
        f"{load_repair_prompt()}\n\n---\n"
        f"SPECIFICATION:\n{spec or '(not provided)'}\n\n"
        f"FAULTY CODE:\n{code}\n\n"
        f"{tb_section}"
        f"FAILURE:\n{format_failure(failure)}\n"
    )