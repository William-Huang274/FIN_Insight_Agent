from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.releases.prepare_fin_ia_0_1_2_s2_t03_wwc_replacement_pair_runner_preflight import (
    build_result,
)


RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_wwc_v12_replacement_pair_"
    "bound_runner_atomic_capture_zero_call_preflight_minimum_"
    "implementation_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_17.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_jsonl(path: Path, key: str, value: str) -> dict:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [row for row in rows if row.get(key) == value][-1]


def test_persisted_result_matches_current_zero_call_preflight() -> None:
    result = _load(RESULT)

    assert result == build_result()
    assert result["status"].startswith("pass_engineering_and_zero_call")
    assert result["zero_call_preflight"]["exact_call_count"] == 2
    assert result["observed_counts"] == {
        "credential_reads": 0,
        "model_provider_network_calls": [0, 0, 0],
        "replacement_pair_calls": 0,
        "Fact_or_Claim_calls": 0,
        "business_Run_or_Artifact_writes": 0,
    }
    assert result["next_action_authorized"] is False


def test_result_bindings_and_historical_compiler_are_byte_exact() -> None:
    result = _load(RESULT)

    for binding in result["implementation_bindings"]:
        path = ROOT / binding["ref"]
        assert path.stat().st_size == binding["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
    history = result["historical_immutability"]
    assert history["shared_compiler_sha256"] == history[
        "shared_compiler_expected_sha256"
    ]
    assert history["historical_six_call_authority_rewritten"] is False
    assert history["historical_six_call_runner_rewritten"] is False


def test_projection_and_backlog_advance_only_to_exact_pair_execution() -> None:
    result = _load(RESULT)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    result_ref = RESULT.relative_to(ROOT).as_posix()
    result_sha = hashlib.sha256(RESULT.read_bytes()).hexdigest()
    projection_ref = PROJECTION.relative_to(ROOT).as_posix()
    projection_sha = hashlib.sha256(PROJECTION.read_bytes()).hexdigest()

    assert projection["implementation_binding"] == {
        "ref": result_ref,
        "sha256": result_sha,
        "binding_role": (
            "S2_T03_WWC_v1_2_replacement_pair_bound_runner_atomic_capture_"
            "zero_call_preflight_pass"
        ),
    }
    assert projection["current_truth"]["current_next_action"] == result[
        "next_action"
    ]
    assert projection["execution_authority"][
        "replacement_pair_execution_started"
    ] is False
    assert projection["execution_authority"][
        "new_user_continuation_required_before_exact_execution"
    ] is True
    current = backlog["next_action"]
    assert current["item_id"] == result["next_action"]
    assert current["current_projection_ref"] == projection_ref
    assert current["current_projection_sha256"] == projection_sha
    assert current["S2_T03_replacement_pair_runner_preflight_ref"] == result_ref
    assert current["S2_T03_replacement_pair_runner_preflight_sha256"] == result_sha
    assert current["S2_T03_replacement_pair_execution_started"] is False
    assert current["S2_T03_replacement_pair_execution_authorized_now"] is False
    assert current["S2_T03_T04_entered"] is False
    assert current["S2_T03_model_selected"] is False


def test_project_os_keeps_both_measurement_issues_open_for_exact_pair() -> None:
    capability = _latest_jsonl(
        CAPABILITY_LEDGER,
        "capability_id",
        "fin_0_1_2_S2_T03_WWC_v1_2_replacement_pair_bound_runner_atomic_capture_zero_call_preflight",
    )
    assert capability["status"].endswith("execution_not_started")
    assert capability["verification"]["replacement_calls_executed"] == 0

    for issue_id in (
        "RC-P36-102-fin-0-1-2-s2-t03-wwc-review-cadence-date-alias-model-visible-contract-parity-gap",
        "RC-P36-103-fin-0-1-2-s2-t03-wwc-selected-task-claim-binding-loop-state-leak",
    ):
        issue = _latest_jsonl(ROOT_CAUSE_LEDGER, "issue_id", issue_id)
        assert issue["status"] == "open"
        assert issue["allowed_run_scopes"][0] == build_result()["next_action"]
        assert issue["verification"]["replacement_execution_started"] is False
