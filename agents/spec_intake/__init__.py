"""Spec intake package: extract, validate, render and check a structured spec."""

from .schema import SpecError, validate_spec, render_spec, check_ports
from .agent import extract_spec, PROMPT_VERSION

__all__ = [
    "SpecError",
    "validate_spec",
    "render_spec",
    "check_ports",
    "extract_spec",
    "PROMPT_VERSION",
]