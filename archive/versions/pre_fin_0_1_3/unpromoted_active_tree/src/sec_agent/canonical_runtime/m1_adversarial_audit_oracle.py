"""Independent post-execution oracle for Point 01 M1-A1.

The oracle intentionally does not import the actual probe module.  It receives
already-generated result records and compares them against an immutable policy
artifact after the actual path has completed.
"""

from __future__ import annotations

from typing import Any

from sec_agent.canonical_runtime.models import canonical_digest


def evaluate(actual_by_probe: dict[str, dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    required = dict(policy["required_actual_assertions"])
    checks: list[dict[str, Any]] = []
    for probe_id, assertions in sorted(required.items()):
        actual = actual_by_probe.get(probe_id, {})
        failures: list[str] = []
        for field, expected in dict(assertions).items():
            value = actual.get(field)
            if isinstance(expected, str):
                if expected not in str(value):
                    failures.append(field)
            elif value != expected:
                failures.append(field)
        checks.append(
            {
                "probe_id": probe_id,
                "status": "pass" if not failures else "oracle_mismatch",
                "failed_fields": tuple(failures),
                "actual_digest": actual.get("actual_digest"),
            }
        )
    return {
        "oracle_version": policy["schema_version"],
        "oracle_policy_digest": canonical_digest(policy),
        "checks": checks,
        "status": "pass" if all(row["status"] == "pass" for row in checks) else "fail_closed",
    }
