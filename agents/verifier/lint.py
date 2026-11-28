"""RTL lint rules (SCRUM-51 / S3-05): cheap, rule-based checks for common mistakes in generated Verilog.

These are text heuristics, not a Verilog parser. They run on code that may compile cleanly, so
they report what iverilog does not. This is the only place the rules live: the prompt runner, the
pipeline and the report import it, and no other file keeps a copy.

Rules (each reports once per module, at its first occurrence; H1 reports every missing port):
    H0  missing module/endmodule (checking stops: nothing else can be judged)
    H1  a requested port is missing from the module header
    H2  #delay used (not synthesizable)
    H3  blocking '=' inside a clocked always block
    H5  markdown fences left in the code
    L1  possible latch: if without else, or case without default, in a combinational always block
        (H4, "does not compile", is the verifier harness, not a lint rule.)

Known limits:
    * H3 also flags a legitimate blocking assignment to a temporary variable in a clocked block.
    * L1 is skipped when the block assigns a default before its first if/case. That also hides a
      latch when only some of the signals have defaults. A case that lists every value without a
      default is reported although it is complete.
    * Width mismatches and multiple drivers are not checked.
    * Comments are ignored; text inside string literals is not.
Findings are advisory in Sprint 3: they never change PASS or FAIL.
"""
from __future__ import annotations

import re

MESSAGES = {
    "H0": "missing module/endmodule",
    "H2": "#delay used",
    "H3": "blocking '=' in clocked block",
    "H5": "markdown fences in output",
    "L1_IF": "possible latch: if without else in a combinational always block",
    "L1_CASE": "possible latch: case without default in a combinational always block",
}

_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_ALWAYS = re.compile(r"\balways\b\s*@\s*(\([^)]*\)|\*)")
_EDGE = re.compile(r"\b(?:posedge|negedge)\b")
_BEGIN_END = re.compile(r"\b(begin|end)\b")
_NEXT_ITEM = re.compile(
    r"\b(?:always|assign|initial|endmodule|module|wire|reg|integer|parameter|localparam)\b")
_FOR_HEADER = re.compile(r"\bfor\s*\((?:[^()]|\([^()]*\))*\)")
_DELAY = re.compile(r"#\s*\d+")
_BLOCKING = re.compile(r"\w\s*=\s*[\w(~!{'\-]")
_ASSIGN = re.compile(r"\w\s*<?=\s*[\w(~!{'\-]")
_CONTROL = re.compile(r"\b(?:if|case[xz]?)\b")


def _blank(text: str) -> str:
    """Replace every character except newlines with a space (keeps offsets and line numbers)."""
    return re.sub(r"[^\n]", " ", text)


def strip_comments(code: str) -> str:
    """Blank out comments without changing length or line numbers."""
    return _COMMENT.sub(lambda m: _blank(m.group(0)), code)


def _line(code: str, pos: int) -> int:
    return code.count("\n", 0, pos) + 1


def _finding(code: str, line, message: str) -> dict:
    return {"code": code, "line": line, "message": message}


def _always_blocks(clean: str):
    """Yield (clocked, start, body_start, body_end) for every always block in comment-free code."""
    for m in _ALWAYS.finditer(clean):
        body_start = m.end()
        rest = clean[body_start:]
        if re.match(r"\s*begin\b", rest):
            depth, body_end = 0, len(clean)
            for token in _BEGIN_END.finditer(rest):
                depth += 1 if token.group(1) == "begin" else -1
                if depth == 0:
                    body_end = body_start + token.end()
                    break
        else:  # single statement: runs until the next module item
            nxt = _NEXT_ITEM.search(rest)
            body_end = body_start + (nxt.start() if nxt else len(rest))
        yield bool(_EDGE.search(m.group(1))), m.start(), body_start, body_end


def _blocking_in(clean: str, body_start: int, body_end: int):
    """Offset of the first blocking assignment in a clocked block, or None."""
    body = _FOR_HEADER.sub(lambda m: _blank(m.group(0)), clean[body_start:body_end])
    # '<=', '==', '!=', '>=' and '===' never match: the pattern needs a word character before '='.
    match = _BLOCKING.search(body)
    return body_start + match.start() if match else None


def _latch_message(body: str):
    """Message if a combinational block can leave a signal unassigned, else None."""
    control = _CONTROL.search(body)
    if not control:
        return None
    if _ASSIGN.search(body[:control.start()]):
        return None  # a default value is assigned first (the usual way to avoid latches)
    if len(re.findall(r"\bif\b", body)) > len(re.findall(r"\belse\b", body)):
        return MESSAGES["L1_IF"]
    if len(re.findall(r"\bcase[xz]?\b", body)) > len(re.findall(r"\bdefault\b", body)):
        return MESSAGES["L1_CASE"]
    return None


def check_rtl(code: str, expected_ports=None) -> list:
    """Lint Verilog text. Returns [{"code", "line", "message"}, ...]; empty when nothing is found.

    `expected_ports` is an optional list of port names that must appear in the module header.
    """
    findings = []
    clean = strip_comments(code)

    fence = code.find("```")
    if fence != -1:
        findings.append(_finding("H5", _line(code, fence), MESSAGES["H5"]))
    if not re.search(r"\bmodule\b", clean) or not re.search(r"\bendmodule\b", clean):
        findings.append(_finding("H0", None, MESSAGES["H0"]))
        return findings

    delay = _DELAY.search(clean)
    if delay:
        findings.append(_finding("H2", _line(clean, delay.start()), MESSAGES["H2"]))

    blocks = list(_always_blocks(clean))
    for clocked, start, body_start, body_end in blocks:
        if clocked:
            pos = _blocking_in(clean, body_start, body_end)
            if pos is not None:
                findings.append(_finding("H3", _line(clean, pos), MESSAGES["H3"]))
                break

    if expected_ports:
        header = clean.split(");")[0]
        module_line = _line(clean, re.search(r"\bmodule\b", clean).start())
        for port in expected_ports:
            if not re.search(r"\b" + re.escape(port) + r"\b", header):
                findings.append(_finding("H1", module_line, f"missing port {port}"))

    for clocked, start, body_start, body_end in blocks:
        if not clocked:
            message = _latch_message(clean[body_start:body_end])
            if message:
                findings.append(_finding("L1", _line(clean, start), message))
                break
    return findings


def as_text(finding: dict) -> str:
    """One-line text of a finding, e.g. 'H2 #delay used'."""
    return f"{finding['code']} {finding['message']}"