"""Repair Agent (SCRUM-44): faulty Verilog + failure report -> corrected Verilog.

The agent only returns code. Writing files, counting attempts and deciding when
to stop belong to the loop controller (agents/repair/loop.py). Errors from the
Gemini client (for example GeminiCallFailed) are deliberately not caught here,
so the loop can count them as a failed attempt.
"""
import logging
import re

from agents.gemini_client import GeminiClient
from agents.repair.prompt import PROMPT_VERSION, build_repair_prompt
from agents.rtl_gen.agent import RTLGenerationError, extract_verilog, validate_verilog

log = logging.getLogger(__name__)

HEADER_RE = re.compile(r"\bmodule\s+(\w+)\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;", re.S)
DIRECTIONS = {"input", "output", "inout"}


class RepairError(Exception):
    """Raised when the model reply is not a usable, port-preserving repair."""


def port_signature(code: str):
    """Return (module_name, [(direction, width, name), ...]) from the module header."""
    clean = re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.S)  # drop comments
    match = HEADER_RE.search(clean)
    if not match:
        raise RepairError("no module header found")
    ports, direction, width = [], "", ""
    for item in match.group(2).split(","):
        width_match = re.search(r"\[[^\]]*\]", item)
        words = re.sub(r"\[[^\]]*\]", " ", item).split()
        if not words:
            continue
        found = next((w for w in words if w in DIRECTIONS), None)
        if found:  # a new direction starts a new group; later names inherit it
            direction = found
            width = re.sub(r"\s+", "", width_match.group(0)) if width_match else ""
        ports.append((direction, width, words[-1]))
    return match.group(1), ports


def _safe_signature(code: str):
    try:
        return port_signature(code)
    except RepairError:
        return None  # the faulty header is itself broken, so there is nothing to compare


def repair_verilog(code: str, failure, spec: str = "", client=None, testbench: str = "") -> str:
    """Ask the model for a fix and return the corrected module text.

    Raises RepairError if the reply is not exactly one module, repeats the
    faulty code unchanged, or alters the module name or ports.
    """
    client = client or GeminiClient()
    raw = client.generate(build_repair_prompt(spec, code, failure, testbench))
    fixed = extract_verilog(raw)
    try:
        validate_verilog(fixed)  # exactly one module/endmodule
    except RTLGenerationError as exc:
        raise RepairError(f"unusable reply: {exc}") from exc
    if fixed.strip() == code.strip():
        raise RepairError("model returned the faulty code unchanged")
    original = _safe_signature(code)
    if original is not None and original != port_signature(fixed):
        raise RepairError("repair changed the module name or ports")
    log.info("repair ok prompt=%s kind=%s", PROMPT_VERSION,
             (failure or {}).get("kind", "unknown"))
    return fixed