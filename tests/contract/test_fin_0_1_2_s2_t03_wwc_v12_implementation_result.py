from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s2_t03_wwc_contract_parity_and_"
    "row_local_binding_consolidated_zero_call_implementation_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_15.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
V11_SOURCE = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "source_v1_1.json"
)
V11_BINDING = ROOT / (
    "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
    "binding_v1_1.json"
)
ROOT_CAUSE_LEDGER = ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
CAPABILITY_LEDGER = ROOT / "docs/project_os/capability_status_ledger.jsonl"
PATTERN_LEDGER = ROOT / "docs/project_os/external_pattern_registry.jsonl"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_implementation_result_is_bound_to_current_files() -> None:
    result = _load(RESULT)

    assert result["status"].startswith("engineering_pass")
    assert result["versioned_contract"]["scope"] == "S2_paired_canary_only"
    assert result["versioned_contract"][
        "historical_v1_1_source_and_binding_rewritten"
    ] is False
    for binding in result["implementation_bindings"]:
        path = ROOT / binding["ref"]
        assert path.stat().st_size == binding["bytes"]
        assert _sha256(path) == binding["sha256"]


def test_engineering_pass_does_not_claim_proof_or_replacement_authority() -> None:
    result = _load(RESULT)

    assert result["issue_disposition"]["issues_closed_now"] == 0
    assert result["observed_counts"]["model_provider_network_calls"] == [0, 0, 0]
    assert result["observed_counts"]["replacement_pair_calls"] == 0
    assert result["stage_acceptance"]["S2_T03_engineering"] == "pass"
    assert result["stage_acceptance"]["S2_T03_independent_proof"] == "pending"
    assert result["stage_acceptance"]["S2_T04"] == "not_entered"
    assert result["next_action_authorized"] is False
    assert result["authority"]["replacement_pair_authorized"] is False


def test_current_projection_and_backlog_bind_the_implementation() -> None:
    result = _load(RESULT)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)
    result_ref = RESULT.relative_to(ROOT).as_posix()
    result_sha = _sha256(RESULT)
    projection_ref = PROJECTION.relative_to(ROOT).as_posix()
    projection_sha = _sha256(PROJECTION)

    assert projection["implementation_binding"]["ref"] == result_ref
    assert projection["implementation_binding"]["sha256"] == result_sha
    assert projection["current_truth"]["current_next_action"] == result["next_action"]
    assert projection["current_truth"]["WWC_v2_engineering_passed"] is True
    assert projection["current_truth"]["WWC_v2_independent_proof_passed"] is False
    assert projection["execution_authority"]["replacement_pair_authorized"] is False

    current = backlog["next_action"]
    assert current["item_id"] != result["next_action"]
    assert current["current_projection_ref"] != projection_ref
    assert current["current_projection_sha256"] != projection_sha
    assert current["S2_T03_consolidated_zero_call_implementation_ref"] == result_ref
    assert current["S2_T03_consolidated_zero_call_implementation_sha256"] == result_sha
    assert current["S2_T03_independent_zero_call_proof_authorized"] is True
    assert current["S2_T03_future_WWC_replacement_pair_authorized"] is True
    assert current["S2_T03_replacement_pair_execution_authorized_now"] is False


def test_history_and_project_os_state_remain_honest() -> None:
    assert _sha256(V11_SOURCE) == (
        "15c4be902cebc72ea8ef24008de0b2177eb1259a5aded0c78e758e8e91ce7501"
    )
    assert _sha256(V11_BINDING) == (
        "2e233d2a58449398774f2b1a21c84b215a82a81b4ef8552d3b86f9876408b420"
    )

    root_causes = _load_jsonl(ROOT_CAUSE_LEDGER)
    latest_102 = [row for row in root_causes if "RC-P36-102" in row["issue_id"]][-1]
    latest_103 = [row for row in root_causes if "RC-P36-103" in row["issue_id"]][-1]
    assert latest_102["status"] == "open"
    assert latest_103["status"] == "open"
    assert latest_102["verification"]["independent_zero_call_proof"] is True
    assert latest_103["verification"]["row_local_claim_authority_matrix"] == "pass"

    capabilities = _load_jsonl(CAPABILITY_LEDGER)
    assert capabilities[-1]["status"].startswith("independent_proof_pass")
    assert capabilities[-1]["authority"][
        "future_replacement_pair_conditionally_authorized"
    ] is True
    assert capabilities[-1]["authority"][
        "replacement_execution_authorized_now"
    ] is False
    patterns = _load_jsonl(PATTERN_LEDGER)
    assert patterns[-1]["verification"]["fresh_processes"] == 2
    assert patterns[-1]["verification"]["replacement_calls_executed"] == 0
