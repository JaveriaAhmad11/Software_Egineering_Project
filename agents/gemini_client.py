"""Gemini client wrapper (SCRUM-23): config, timeout, bounded retries, logging.

SCRUM-47: every attempt is logged with model, latency, attempt count and token
counts, and recorded in `client.stats` so a benchmark can summarise real calls.
"""
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

log = logging.getLogger("gemini_client")
if not log.handlers:
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(),
                    logging.FileHandler(LOG_DIR / "gemini.log", encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)


class GeminiConfigError(Exception):
    """Raised when required configuration (the API key) is missing."""


class GeminiCallFailed(Exception):
    """Raised when every retry attempt has failed."""


def _tokens(interaction) -> dict:
    """Read token counts from the response; any missing field becomes None.

    A missing statistic must never turn a successful generation into a failure.
    """
    usage = getattr(interaction, "usage", None)

    def pick(name):
        value = getattr(usage, name, None)
        return value if isinstance(value, int) else None

    return {"input_tokens": pick("total_input_tokens"),
            "output_tokens": pick("total_output_tokens"),
            "total_tokens": pick("total_tokens")}


class GeminiClient:
    def __init__(self, model=None, timeout_s=None, max_retries=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigError("GEMINI_API_KEY not found. Check your .env file.")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.timeout_s = timeout_s or int(os.getenv("GEMINI_TIMEOUT_S", "45"))
        self.max_retries = max_retries or int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        self.stats = []  # one entry per attempt: ok, attempt, latency_s, tokens
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=self.timeout_s * 1000),
        )

    def generate(self, prompt: str) -> str:
        for attempt in range(1, self.max_retries + 1):
            start = time.time()
            try:
                interaction = self._client.interactions.create(
                    model=self.model,
                    input=prompt,
                )
                text = interaction.output_text
                if not text or not text.strip():
                    raise ValueError("empty reply from model")
                latency = time.time() - start
                tokens = _tokens(interaction)
                self.stats.append({"ok": True, "attempt": attempt, "model": self.model,
                                   "latency_s": latency, **tokens})
                log.info(
                    "OK model=%s attempt=%d/%d latency=%.1fs prompt_chars=%d reply_chars=%d "
                    "input_tokens=%s output_tokens=%s total_tokens=%s",
                    self.model, attempt, self.max_retries, latency, len(prompt), len(text),
                    tokens["input_tokens"], tokens["output_tokens"], tokens["total_tokens"]
                )
                return text
            except Exception as exc:
                latency = time.time() - start
                self.stats.append({"ok": False, "attempt": attempt, "model": self.model,
                                   "latency_s": latency, "error": type(exc).__name__,
                                   "input_tokens": None, "output_tokens": None,
                                   "total_tokens": None})
                log.warning(
                    "FAILED model=%s attempt=%d/%d after %.1fs: %s",
                    self.model, attempt, self.max_retries, latency, type(exc).__name__
                )
                if attempt == self.max_retries:
                    raise GeminiCallFailed(
                        f"Gemini call failed after {self.max_retries} attempts"
                    ) from exc
                time.sleep(2 * attempt)
