"""Contract parity script smoke test."""

from __future__ import annotations

from tools.verify_contracts import verify_all


def test_verify_contracts_passes() -> None:
    summary = verify_all()
    assert "34 routes" in summary
    assert "19 error codes" in summary
    assert "25 refs targeting 14 unique $defs" in summary
    assert "4 fixtures valid" in summary
    assert "40/40 normative env vars" in summary
