"""Tests for S3-04: schema validation, rendering and port contract."""

import pytest

from agents.spec_intake.schema import (
    SpecError,
    check_ports,
    render_spec,
    validate_spec,
)


def good_spec():
    return {
        "module_name": "counter8",
        "summary": "8-bit counter with enable.",
        "ports": [
            {"name": "clk", "direction": "input", "width": 1},
            {"name": "rst", "direction": "input", "width": 1},
            {"name": "en", "direction": "input", "width": 1},
            {"name": "count", "direction": "output", "width": 8},
        ],
        "behaviour": ["increment on rising edge when en is high"],
        "test_scenarios": ["reset clears the count", "enable increments"],
    }


def test_valid_spec_passes():
    assert validate_spec(good_spec()) == good_spec()


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda s: s.update(module_name="1bad"), "module_name"),
        (lambda s: s["ports"].append(dict(s["ports"][0])), "duplicate port"),
        (lambda s: s["ports"][0].update(direction="sideways"), "direction"),
        (lambda s: s["ports"][0].update(width=0), "width"),
        (lambda s: s["ports"][0].update(width=65), "width"),
        (lambda s: s.update(behaviour=[]), "behaviour"),
    ],
)
def test_validate_rejects(mutate, match):
    spec = good_spec()
    mutate(spec)
    with pytest.raises(SpecError, match=match):
        validate_spec(spec)


def test_missing_key_rejected():
    spec = good_spec()
    del spec["summary"]
    with pytest.raises(SpecError, match="missing"):
        validate_spec(spec)


def test_render_lists_every_port_with_direction_and_width():
    text = render_spec(good_spec())
    assert "counter8" in text
    for port in good_spec()["ports"]:
        assert port["name"] in text
        assert port["direction"] in text
        assert str(port["width"]) in text


def test_render_is_deterministic():
    spec = good_spec()
    assert render_spec(spec) == render_spec(spec)


def test_check_ports_ok():
    code = """
    module counter8(
        input clk,
        input rst,
        input en,
        output [7:0] count
    );
    endmodule
    """
    assert check_ports(code, good_spec()) == []


def test_check_ports_flags_port_fault():
    # Mirrors the port_fault.v situation: width/direction mismatch.
    code = """
    module counter8(
        input clk,
        input rst,
        input en,
        output [3:0] count
    );
    endmodule
    """
    messages = check_ports(code, good_spec())
    assert any("count" in m and "width" in m for m in messages)