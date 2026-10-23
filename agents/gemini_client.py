"""Gemini client wrapper (SCRUM-23): config, timeout, bounded retries, logging."""
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


class GeminiClient:
    def __init__(self, model=None, timeout_s=None, max_retries=None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiConfigError("GEMINI_API_KEY not found. Check your .env file.")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self.timeout_s = timeout_s or int(os.getenv("GEMINI_TIMEOUT_S", "60"))
        self.max_retries = max_retries or int(os.getenv("GEMINI_MAX_RETRIES", "3"))
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
                log.info(
                    "OK model=%s attempt=%d/%d latency=%.1fs prompt_chars=%d reply_chars=%d",
                    self.model, attempt, self.max_retries,
                    time.time() - start, len(prompt), len(text)
                )
                return text
            except Exception as exc:
                log.warning(
                    "FAILED model=%s attempt=%d/%d after %.1fs: %s",
                    self.model, attempt, self.max_retries,
                    time.time() - start, type(exc).__name__
                )
                if attempt == self.max_retries:
                    raise GeminiCallFailed(
                        f"Gemini call failed after {self.max_retries} attempts"
                    ) from exc
                time.sleep(2 * attempt)