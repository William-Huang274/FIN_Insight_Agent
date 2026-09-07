from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.data_retrieval.run_s1d_source_intake import (  # noqa: E402
    SourceIntakeRunnerError,
    validate_authority,
)


POLICY_REF = "configs/retrieval/fin_ia_0_1_3_s1d_source_intake_policy_v1_0.json"
RUNNER_REF = "scripts/data_retrieval/run_s1d_source_intake.py"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    fixture = tmp_path / "repo"
    for relative in (POLICY_REF, RUNNER_REF):
        target = fixture / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    authority: dict[str, object] = {
        "schema_version": "fin_ia_s1d_source_intake_execution_authority_v1_0",
        "authority_id": "TEST-AUTHORITY",
        "recorded_at": "2026-08-13",
        "status": "fresh_bounded_source_intake_automatic_execution_authorized",
        "clean_implementation": {
            "git_commit": "a" * 40,
            "branch": "codex/test",
            "working_tree_required_clean_before_execution": True,
        },
        "bound_inputs": {
            "source_intake_policy_ref": POLICY_REF,
            "source_intake_policy_sha256": _digest(fixture / POLICY_REF),
            "runner_ref": RUNNER_REF,
            "runner_sha256": _digest(fixture / RUNNER_REF),
        },
        "execution_budget": {
            "route_attempts": [
                {
                    "route_id": "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT",
                    "attempt_id": "source-intake-auto-dell-r1",
                },
                {
                    "route_id": "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
                    "attempt_id": "source-intake-auto-tsm-r1",
                },
            ],
            "network_attempts_maximum": 2,
            "retries": 0,
            "model_calls": 0,
            "credentials": "forbidden",
        },
        "result_contract": {
            "result_id": "TEST-RESULT",
            "public_result_ref": "configs/retrieval/test_result.json",
        },
    }
    return fixture, authority


def test_authority_binds_exact_policy_routes_runner_and_zero_retry(
    tmp_path: Path,
) -> None:
    fixture, authority = _fixture(tmp_path)
    validated = validate_authority(authority, repository_root=fixture)
    assert validated["execution_budget"]["network_attempts_maximum"] == 2


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("retry", "budget_invalid"),
        ("route", "routes_not_policy_exact"),
        ("digest", "digest_mismatch"),
        ("result", "public_result_already_exists"),
    ],
)
def test_authority_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
    error: str,
) -> None:
    fixture, authority = _fixture(tmp_path)
    if mutation == "retry":
        authority["execution_budget"]["retries"] = 1
    elif mutation == "route":
        authority["execution_budget"]["route_attempts"][1]["route_id"] = "NVDA"
    elif mutation == "digest":
        authority["bound_inputs"]["runner_sha256"] = "0" * 64
    else:
        result_path = fixture / authority["result_contract"]["public_result_ref"]
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({"existing": True}), encoding="utf-8")
    with pytest.raises(SourceIntakeRunnerError, match=error):
        validate_authority(authority, repository_root=fixture)
