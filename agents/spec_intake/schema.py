"""Spec schema, validation, rendering and port-contract checks (S3-04)."""

from __future__ import annotations
import re
from typing import Any
from agents.verifier.port_signature import port_signature

class SpecError(ValueError):
    """Raised when a spec is invalid or a model reply cannot be trusted."""

VALID_DIRECTIONS = ("input", "output", "inout")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REQUIRED_SPEC_KEYS = (
    "module_name", "summary", "ports", "behaviour", "test_scenarios",
)

def _check_identifier(value: Any, what: str) -> None:
    if not isinstance(value, str) or not IDENTIFIER_RE.match(value):
        raise SpecError(f"{what} is not a valid identifier: {value!r}")

def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise SpecError(f"spec must be a dict, got {type(spec).__name__}")

    missing = [k for k in REQUIRED_SPEC_KEYS if k not in spec]
    if missing:
        raise SpecError(f"spec is missing required keys: {missing}")

    _check_identifier(spec["module_name"], "module_name")

    ports = spec["ports"]
    if not isinstance(ports, list) or not ports:
        raise SpecError("ports must be a non-empty list")

    seen: set[str] = set()
    for i, port in enumerate(ports):
        if not isinstance(port, dict):
            raise SpecError(f"ports[{i}] must be a dict")
        for key in ("name", "direction", "width"):
            if key not in port:
                raise SpecError(f"ports[{i}] is missing '{key}'")
        _check_identifier(port["name"], f"ports[{i}].name")
        if port["name"] in seen:
            raise SpecError(f"duplicate port name: {port['name']!r}")
        seen.add(port["name"])
        if port["direction"] not in VALID_DIRECTIONS:
            raise SpecError(f"ports[{i}] has unknown direction {port['direction']!r}")
        
        width = port["width"]
        if not isinstance(width, int) or isinstance(width, bool):
            raise SpecError(f"ports[{i}].width must be an int, got {width!r}")
        if not (1 <= width <= 64):
            raise SpecError(f"ports[{i}].width must be between 1 and 64, got {width}")

    if not isinstance(spec["behaviour"], list) or not spec["behaviour"]:
        raise SpecError("behaviour must be a non-empty list")

    if not isinstance(spec["test_scenarios"], list):
        raise SpecError("test_scenarios must be a list")

    return spec

def render_spec(spec: dict) -> str:
    spec = validate_spec(spec)
    lines = [
        f"Module: {spec['module_name']}",
        f"Summary: {spec['summary']}",
        "Ports:",
    ]
    for port in spec["ports"]:
        lines.append(f"  - {port['name']}: {port['direction']} width {port['width']}")
    lines.append("Behaviour:")
    for item in spec["behaviour"]:
        lines.append(f"  - {item}")
    if spec["test_scenarios"]:
        lines.append("Test scenarios:")
        for item in spec["test_scenarios"]:
            lines.append(f"  - {item}")
    return "\n".join(lines) + "\n"

def check_ports(code: str, spec: dict) -> list[str]:
    spec = validate_spec(spec)
    try:
        actual = port_signature(code)
    except Exception as exc:
        return [f"could not parse RTL header: {exc}"]

    expected = {p["name"]: (p["direction"], p["width"]) for p in spec["ports"]}
    messages: list[str] = []
    
    for name, (direction, width) in expected.items():
        if name not in actual:
            messages.append(f"port '{name}' is missing from the design")
            continue
        act_dir, act_width = actual[name]
        if act_dir != direction:
            messages.append(f"port '{name}' direction is {act_dir}, spec says {direction}")
        if act_width != width:
            messages.append(f"port '{name}' width is {act_width}, spec says {width}")
            
    for name in actual:
        if name not in expected:
            messages.append(f"unexpected port '{name}' in the design")
            
    return messages