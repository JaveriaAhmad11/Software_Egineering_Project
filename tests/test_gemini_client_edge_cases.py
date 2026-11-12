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


def test_default_model_and_timeout_are_the_audited_ones(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_TIMEOUT_S", raising=False)
    client = _client(monkeypatch)
    assert client.model == "gemini-3.5-flash-lite"
    assert client.timeout_s == 45


import logging
from types import SimpleNamespace


class _GoodReply:
    output_text = "OK"
    usage = SimpleNamespace(total_input_tokens=8, total_output_tokens=1,
                            total_thought_tokens=0, total_tokens=9)


class _GoodInteractions:
    def create(self, model, input):
        return _GoodReply()


def test_success_logs_token_counts_and_records_stats(monkeypatch, caplog):
    client = _client(monkeypatch)
    client._client.interactions = _GoodInteractions()
    caplog.set_level(logging.INFO, logger="gemini_client")
    assert client.generate("hi") == "OK"
    assert "input_tokens=8" in caplog.text and "output_tokens=1" in caplog.text
    stat = client.stats[-1]
    assert stat["ok"] is True and stat["attempt"] == 1
    assert stat["total_tokens"] == 9 and stat["latency_s"] >= 0


def test_missing_usage_does_not_break_the_call(monkeypatch):
    class _NoUsage:
        output_text = "OK"

    class _I:
        def create(self, model, input):
            return _NoUsage()

    client = _client(monkeypatch)
    client._client.interactions = _I()
    assert client.generate("hi") == "OK"
    assert client.stats[-1]["total_tokens"] is None


def test_failed_attempts_are_recorded(monkeypatch):
    client = _client(monkeypatch, max_retries=2)
    with pytest.raises(gc.GeminiCallFailed):
        client.generate("hi")
    assert [s["ok"] for s in client.stats] == [False, False]


import logging
from types import SimpleNamespace


class _GoodReply:
    output_text = "OK"
    usage = SimpleNamespace(total_input_tokens=8, total_output_tokens=1,
                            total_thought_tokens=0, total_tokens=9)


class _GoodInteractions:
    def create(self, model, input):
        return _GoodReply()


def test_success_logs_token_counts_and_records_stats(monkeypatch, caplog):
    client = _client(monkeypatch)
    client._client.interactions = _GoodInteractions()
    caplog.set_level(logging.INFO, logger="gemini_client")
    assert client.generate("hi") == "OK"
    assert "input_tokens=8" in caplog.text and "output_tokens=1" in caplog.text
    stat = client.stats[-1]
    assert stat["ok"] is True and stat["attempt"] == 1
    assert stat["total_tokens"] == 9 and stat["latency_s"] >= 0


def test_missing_usage_does_not_break_the_call(monkeypatch):
    class _NoUsage:
        output_text = "OK"

    class _I:
        def create(self, model, input):
            return _NoUsage()

    client = _client(monkeypatch)
    client._client.interactions = _I()
    assert client.generate("hi") == "OK"
    assert client.stats[-1]["total_tokens"] is None


def test_failed_attempts_are_recorded(monkeypatch):
    client = _client(monkeypatch, max_retries=2)
    with pytest.raises(gc.GeminiCallFailed):
        client.generate("hi")
    assert [s["ok"] for s in client.stats] == [False, False]
