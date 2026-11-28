"""Spec intake agent: plain-English request -> structured spec (S3-03)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agents.gemini_client import GeminiClient
from .schema import SpecError, validate_spec

PROMPT_VERSION = "spec_intake/v1.0"

_PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts" / "spec_intake" / "v1.0"
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _load_system_prompt() -> str:
    path = _PROMPT_DIR / "system_prompt.md"
    if not path.exists():
        raise SpecError(f"missing system prompt: {path}")
    return path.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def extract_spec(request: str, client=None) -> dict:
    """Turn a plain-English request into a validated spec dict.

    Raises SpecError on prose replies, invalid JSON or missing fields,
    and writes nothing in that case (S3-03 AC2).
    """
    if not isinstance(request, str) or not request.strip():
        raise SpecError("request must be a non-empty string")

    if client is None:
        client = GeminiClient()

    prompt = f"{_load_system_prompt()}\n\nRequest:\n{request.strip()}\n"
    raw = client.generate(prompt)
    if not isinstance(raw, str):
        raise SpecError(f"model returned non-string reply: {type(raw).__name__}")

    cleaned = _strip_fences(raw)
    try:
        spec = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SpecError(
            f"model reply is not valid JSON ({exc}); raw reply: {raw[:200]!r}"
        ) from exc

    if not isinstance(spec, dict):
        raise SpecError(f"model reply is not a JSON object: {type(spec).__name__}")

    # validate_spec raises SpecError on missing fields / bad values.
    return validate_spec(spec)