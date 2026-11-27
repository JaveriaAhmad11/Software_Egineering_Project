"""Tests for S3-03: spec intake agent with a mocked client (no API key)."""

import json
import pytest

from agents.spec_intake import agent as intake
from agents.spec_intake.schema import SpecError


class FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return self.reply


def valid_reply():
    return json.dumps(
        {
            "module_name": "counter8",
            "summary": "8-bit counter with enable.",
            "ports": [
                {"name": "clk", "direction": "input", "width": 1},
                {"name": "en", "direction": "input", "width": 1},
                {"name": "count", "direction": "output", "width": 8},
            ],
            "behaviour": ["increment on rising edge when en is high"],
            "test_scenarios": ["enable increments"],
        }
    )


def test_extract_valid_json():
    client = FakeClient(valid_reply())
    spec = intake.extract_spec("8-bit counter with enable", client=client)
    assert spec["module_name"] == "counter8"
    assert len(spec["ports"]) == 3
    assert client.calls == 1


def test_extract_accepts_fenced_json():
    client = FakeClient("```json\n" + valid_reply() + "\n```")
    assert intake.extract_spec("counter", client=client)["module_name"] == "counter8"


def test_prose_reply_raises():
    client = FakeClient("Sure! Here is your spec: it is a counter.")
    with pytest.raises(SpecError, match="not valid JSON"):
        intake.extract_spec("counter", client=client)


def test_invalid_json_raises():
    client = FakeClient("{not json")
    with pytest.raises(SpecError):
        intake.extract_spec("counter", client=client)


def test_missing_field_raises():
    payload = json.loads(valid_reply())
    del payload["behaviour"]
    with pytest.raises(SpecError, match="behaviour"):
        intake.extract_spec("counter", client=FakeClient(json.dumps(payload)))


def test_failure_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeClient("not json")
    with pytest.raises(SpecError):
        intake.extract_spec("counter", client=client)
    assert list(tmp_path.iterdir()) == []


def test_prompt_version_recorded():
    assert intake.PROMPT_VERSION == "spec_intake/v1.0"