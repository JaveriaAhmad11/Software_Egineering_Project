import pytest
from agents import gemini_client as gc


class _Response:
    output_text = "ok"


class _Interactions:
    def __init__(self, fails):
        self.fails = fails
        self.calls = 0

    def create(self, model, input):
        self.calls += 1
        if self.calls <= self.fails:
            raise RuntimeError("503 high demand")
        return _Response()


class _FakeSDK:
    def __init__(self, fails):
        self.interactions = _Interactions(fails)


def make_client(monkeypatch, fails):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(gc.time, "sleep", lambda s: None)
    client = gc.GeminiClient(max_retries=3)
    client._client = _FakeSDK(fails)
    return client


def test_retries_then_succeeds(monkeypatch):
    client = make_client(monkeypatch, fails=2)
    assert client.generate("hi") == "ok"
    assert client._client.interactions.calls == 3


def test_gives_up_after_max_retries(monkeypatch):
    client = make_client(monkeypatch, fails=5)
    with pytest.raises(gc.GeminiCallFailed):
        client.generate("hi")
    assert client._client.interactions.calls == 3


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(gc.GeminiConfigError):
        gc.GeminiClient()