"""Shared RTL lint (SCRUM-51): static hallucination and style checks on generated Verilog.

check_rtl(code, expected_ports) returns a list of findings, each a dict
{"code": "H3", "line": 12, "message": "..."}, ordered H5, H0, H2, H3, H1, L1.

Rules
  H0  no module ... endmodule pair
  H1  an expected port does not appear in the module header
  H2  #delay used (not synthesizable)
  H3  blocking '=' inside a clocked always @(posedge ...) block
  H5  markdown code fences left in the output
  L1  possible latch: if without else, or case without default, in a combinational always block
(H4 is the compile check, done by the verifier harness, not here.)

Comments are blanked out before the checks (newlines kept, so line numbers stay correct),
and for-loop headers are ignored by H3.

Limitations: these are text heuristics, not a Verilog parser.
  - Comment stripping does not understand strings, so "//" inside a string literal is treated as a comment.
  - H1 only checks that the port name appears in the text before the first ");" (not direction or width).
  - H2 flags any "#<number>", including delays inside code that is never synthesized.
  - H3 only looks at always @(posedge ...) blocks. A block without begin/end is read only up to
    its first ";", and nested parentheses inside a for header are handled to one level only.
    H3 reports at most one finding per file.
  - L1 counts "if" against "else" (and "case" against "default") per block. It cannot see a default
    assignment at the top of the block, so it can false-alarm, and it can miss a latch built other ways.
    A block without begin/end is read up to the next always/assign/initial/endmodule.
  - Only Verilog-2001 style always blocks are analysed (not always_ff / always_comb).
"""
from __future__ import annotations

import re

FENCE = "`" * 3
_ALWAYS = re.compile(r"\balways\s*@\s*(\([^)]*\)|\*)")
_FOR_HEADER = re.compile(r"\bfor\s*\((?:[^()]|\([^()]*\))*\)")
_COMPARE_OPS = ("<=", "==", "!=", ">=")
_BLOCK_END = re.compile(r"\b(?:always|assign|initial|endmodule)\b")


def _blank(match) -> str:
    """Replace matched text with spaces, keeping newlines so line numbers do not move."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_comments(code: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", _blank, code, flags=re.S)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _finding(code: str, line: int, message: str) -> dict:
    return {"code": code, "line": line, "message": message}


def format_finding(finding: dict) -> str:
    """'H3 blocking ...' - the exact text format run_prompt_cases has always printed."""
    return f"{finding['code']} {finding['message']}"


def _begin_end_span(src: str, start: int):
    """(start, end) of the begin..end block that starts at `start`, or None."""
    if not re.match(r"\s*begin\b", src[start:]):
        return None
    depth = 0
    for t in re.finditer(r"\b(begin|end)\b", src[start:]):
        depth += 1 if t.group(1) == "begin" else -1
        if depth == 0:
            return start, start + t.end()
    return None


def _always_blocks(src: str):
    """Yield (kind, offset, text) for each always block; kind is 'clocked' or 'comb'."""
    for m in _ALWAYS.finditer(src):
        sens = m.group(1)
        if "posedge" in sens:
            kind = "clocked"
        elif "negedge" in sens:
            continue
        else:
            kind = "comb"
        start = m.end()
        span = _begin_end_span(src, start)
        if span:
            begin, end = span
        elif kind == "clocked":
            semi = src.find(";", start)
            begin, end = start, (len(src) if semi == -1 else semi + 1)
        else:
            nxt = _BLOCK_END.search(src, start)
            begin, end = start, (nxt.start() if nxt else len(src))
        yield kind, begin, src[begin:end]


def check_rtl(code: str, expected_ports=None) -> list[dict]:
    findings = []
    if FENCE in code:
        findings.append(_finding("H5", _line(code, code.index(FENCE)), "markdown fences in output"))

    src = strip_comments(code)
    if not re.search(r"\bmodule\b", src) or not re.search(r"\bendmodule\b", src):
        findings.append(_finding("H0", 1, "missing module/endmodule"))
        return findings

    delay = re.search(r"#\s*\d+", src)
    if delay:
        findings.append(_finding("H2", _line(src, delay.start()), "#delay used"))

    blocks = list(_always_blocks(src))
    for kind, offset, text in blocks:
        if kind != "clocked":
            continue
        cleaned = _FOR_HEADER.sub(_blank, text)  # ignore for-loop headers
        for op in _COMPARE_OPS:
            cleaned = cleaned.replace(op, " " * len(op))
        hit = re.search(r"\w\s*=\s*[\w(~!{]", cleaned)
        if hit:
            findings.append(_finding("H3", _line(src, offset + hit.start()),
                                     "blocking '=' in clocked block"))
            break

    module_line = _line(src, re.search(r"\bmodule\b", src).start())
    header = src.split(");")[0]
    for port in expected_ports or ():
        if not re.search(r"\b" + re.escape(port) + r"\b", header):
            findings.append(_finding("H1", module_line, f"missing port {port}"))

    for kind, offset, text in blocks:
        if kind != "comb":
            continue
        if len(re.findall(r"\bif\b", text)) > len(re.findall(r"\belse\b", text)):
            first = re.search(r"\bif\b", text)
            findings.append(_finding("L1", _line(src, offset + first.start()),
                                     "possible latch: if without else in combinational block"))
        elif len(re.findall(r"\bcase[xz]?\b", text)) > len(re.findall(r"\bdefault\b", text)):
            first = re.search(r"\bcase[xz]?\b", text)
            findings.append(_finding("L1", _line(src, offset + first.start()),
                                     "possible latch: case without default in combinational block"))
    return findings