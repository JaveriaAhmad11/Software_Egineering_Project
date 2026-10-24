"""Extra mocked-LLM tests for the Gemini client wrapper (SCRUM-28): empty replies and model config."""
import pytest

from agents import gemini_client as gc


class _EmptyReply:
    output_text = "   "


class _Interactions:
    def __init__(self):
        self.calls = 0

    def create(self, model, input):
        self.calls += 1
        return _EmptyReply()


class _FakeSDK:
    def __init__(self):
        self.interactions = _Interactions()


def _client(monkeypatch, **kwargs):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gc.time, "sleep", lambda s: None)
    client = gc.GeminiClient(**kwargs)
    client._client = _FakeSDK()
    return client


def test_empty_reply_is_retried_then_fails(monkeypatch):
    client = _client(monkeypatch, max_retries=3)
    with pytest.raises(gc.GeminiCallFailed):
        client.generate("hi")
    assert client._client.interactions.calls == 3


def test_model_name_comes_from_config_not_code(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "model-from-env")
    assert _client(monkeypatch).model == "model-from-env"


def test_explicit_model_overrides_env(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "model-from-env")
    assert _client(monkeypatch, model="explicit-model").model == "explicit-model"
