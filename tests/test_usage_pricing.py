"""Frozen historical price boundaries used by the report API."""
import pytest
from sec_agent.agent_runtime.usage_pricing import peak_multiplier, dated_public_cost

@pytest.mark.parametrize("timestamp,expected", [
    ("2026-09-05T19:00:00Z", 1),  # Sunday Beijing
    ("2026-09-07T01:00:00Z", 2),
    ("2026-09-07T04:00:00Z", 1),
    ("2026-09-07T06:00:00Z", 2),
    ("2026-09-07T10:00:00Z", 1),
])
def test_peak_schedule(timestamp, expected):
    assert peak_multiplier(timestamp) == expected


def test_dated_alias_prices_preserve_old_runs_and_provider_cutover():
    counts = (0, 1_000_000, 0)
    assert dated_public_cost("deepseek-v4-flash", *counts, "2026-09-07T04:00:00Z") == 1.5
    assert dated_public_cost("deepseek-flash", *counts, "2026-09-11T04:00:00Z") == 1.0
    assert dated_public_cost("deepseek-v4-flash", *counts, "2026-09-11T06:00:00Z") == 2.0
    assert dated_public_cost("deepseek-v4-pro", *counts, "2026-09-14T03:59:59Z") == 9.0
    assert dated_public_cost("deepseek-v4-pro", *counts, "2026-09-14T04:00:00Z") == 1.0
    assert dated_public_cost("unknown", *counts, "2026-09-11T04:00:00Z") is None
