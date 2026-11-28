"""
Sprint 0 / Sprint 2 smoke test: verify that the shared Gemini client
works with the audited default model and timeout.

Uses the same GeminiClient that the rest of the system uses, so the
model, timeout and retries come from .env / .env.example (SCRUM-47).
"""

from agents.gemini_client import GeminiClient


def main() -> None:
    client = GeminiClient()          # reads GEMINI_API_KEY + defaults from env
    print(f"Using model: {client.model}")
    print(f"Timeout:     {client.timeout_s}s")
    print("Sending a short test prompt...")

    reply = client.generate(
        "Reply with exactly one short sentence: Gemini connection OK."
    )

    print("\nGemini connection successful!")
    print(f"Model used:  {client.model}")
    print(f"Reply:       {reply.strip()}")


if __name__ == "__main__":
    main()
