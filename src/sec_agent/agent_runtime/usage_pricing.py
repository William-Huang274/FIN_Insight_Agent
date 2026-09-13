"""Dated public-price estimates for reported usage, never provider invoices.

This preserves the FIN 0.1.3 price schedule. Historical research audits retain
their own frozen implementation; product serving does not import experiment code.
"""
from datetime import datetime, timedelta, timezone


OFF_PEAK = {
    "deepseek-v4-pro": (0.15, 4.5, 13.5),
    "deepseek-v4-flash": (0.05, 1.5, 4.5),
    "deepseek-v4-flash-vision-exp": (0.05, 1.5, 4.5),
}


def peak_multiplier(timestamp):
    local = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(
        timezone(timedelta(hours=8)))
    return 2 if local.weekday() < 5 and (9 <= local.hour < 12 or 14 <= local.hour < 18) else 1


def dated_public_cost(model, hit, miss, output, timestamp):
    """Estimate CNY using the recorded request date and the frozen schedule."""
    local = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8)))
    if local.date().isoformat() >= "2026-09-11":
        if model in {"deepseek-flash", "deepseek-v4-flash", "deepseek-v4-flash-vision-exp"}:
            rates = (0.02, 1.0, 4.0)
        elif model == "deepseek-v4-pro":
            rates = (0.02, 1.0, 4.0) if local.isoformat() >= "2026-09-14T12:00:00+08:00" else (0.15, 4.5, 13.5)
        else:
            return None
        return sum(count * rate for count, rate in zip((hit, miss, output), rates)) * peak_multiplier(timestamp) / 1_000_000
    if model in OFF_PEAK:
        return sum(count * rate * peak_multiplier(timestamp) / 1_000_000
                   for count, rate in zip((hit, miss, output), OFF_PEAK[model]))
    return None
