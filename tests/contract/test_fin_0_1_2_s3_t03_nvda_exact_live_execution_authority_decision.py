from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    compile_fin_0_1_2_s3_production_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_product_input import (
    assert_fin_0_1_2_s3_exact_input_matches_manifest,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s3_three_cell_bounded_agent_exact_input,
)
from test_fin_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair import (
    _admission,
    _create_accepted_case,
    _principal,
)


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_"
    "execution_authority_decision_v1_0.json"
)
PROJECTION = ROOT / (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_23.json"
)
BACKLOG = ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
FRESH_IDENTITY = "fin012-s3-t03-nvda-primary-r1"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_authority_binds_immutable_stage_input_and_v13_assets() -> None:
    authority = _load(AUTHORITY)
    stable_roles = {
        "S3_stage_budget_failure_and_stop_contract",
        "T02_engineering_and_current_full_fake_evidence",
        "tracked_current_NVDA_exact_input",
        "current_S3_production_contract_source",
        "current_S3_production_contract_binding",
        "content_addressed_runtime_resource_authority",
    }
    rows = [row for row in authority["bindings"] if row["role"] in stable_roles]
    assert {row["role"] for row in rows} == stable_roles
    for row in rows:
        path = ROOT / row["ref"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
        assert path.stat().st_size == row["bytes"]


def test_tracked_input_recompiles_twice_under_proposed_fresh_identity(
    tmp_path: Path,
) -> None:
    _, local_service, evidence_service, case, accepted = _create_accepted_case(
        tmp_path
    )
    kwargs = {
        "decision_surface_contract_ref": str(accepted["contract_version_id"]),
        "execution_identity": FRESH_IDENTITY,
    }
    first = prepare_s3_three_cell_bounded_agent_exact_input(
        local_service,
        evidence_service,
        str(case["case_id"]),
        _principal(),
        **kwargs,
    )
    second = prepare_s3_three_cell_bounded_agent_exact_input(
        local_service,
        evidence_service,
        str(case["case_id"]),
        _principal(),
        **kwargs,
    )
    assert first == second
    assert first.execution_identity == FRESH_IDENTITY
    assert first.input_digest == (
        "b9cc749d0d2351e228750343a61d3fc03abfc8a70870fa96d12c8a03f118e085"
    )
    with pytest.raises(
        ValueError, match="fin012_s3_exact_product_input_manifest_mismatch"
    ):
        assert_fin_0_1_2_s3_exact_input_matches_manifest(
            first.input_pack,
            source_digest=first.preparation_digest,
        )


def test_only_disabled_prospective_admission_is_valid_in_authority_turn(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    _, local_service, evidence_service, case, accepted = _create_accepted_case(
        tmp_path
    )
    prepared = prepare_s3_three_cell_bounded_agent_exact_input(
        local_service,
        evidence_service,
        str(case["case_id"]),
        _principal(),
        decision_surface_contract_ref=str(accepted["contract_version_id"]),
        execution_identity=FRESH_IDENTITY,
    )
    source = _admission(prepared).model_copy(
        update={"execution_enabled": False}
    )
    prospective = compile_fin_0_1_2_s3_production_admission(
        source,
        updates={
            "admission_id": "prospective-fin012-s3-t03-nvda-primary-r1",
            "execution_mode": "zero_call_authority_review_only",
        },
    )
    assert prospective.execution_enabled is False
    assert prospective.max_semantic_model_calls == 0
    assert prospective.max_provider_calls == 0
    assert prospective.max_network_calls == 0
    assert prospective.max_total_cost_usd == 0.0


def test_authority_is_conditional_budgeted_and_does_not_claim_execution() -> None:
    authority = _load(AUTHORITY)
    permission = authority["authority"]
    budget = authority["hard_budget"]

    assert permission["future_one_primary_NVDA_exact_live_authorized"]
    assert permission[
        "authorization_effective_only_after_fresh_identity_input_boundary_bound_runner_atomic_capture_and_zero_call_preflight_pass"
    ]
    assert permission[
        "fresh_identity_input_boundary_runner_and_atomic_capture_minimum_implementation_authorized_next"
    ]
    assert not permission["current_turn_credential_read_or_probe_authorized"]
    assert not permission["current_turn_admission_issue_or_persist_authorized"]
    assert not permission["current_turn_model_provider_or_execution_network_authorized"]
    assert not permission["automatic_exact_execution_after_preflight_authorized"]
    assert not permission["automatic_repair_replacement_or_second_attempt_authorized"]
    assert set(authority["current_turn_observed_counts"].values()) == {0}
    assert budget["primary_formal_attempts"] == 1
    assert budget["semantic_model_calls"] == 9
    assert budget["maximum_transport_attempts_per_call"] == 1
    assert budget["retry_budget"] == 0
    assert budget["maximum_total_cost_usd"] == 0.06


def test_preexecution_gap_is_owned_by_t03_and_not_misclassified() -> None:
    authority = _load(AUTHORITY)
    gap = authority["preexecution_gap"]
    assert gap["issue_id"].startswith("RC-P36-106-")
    assert gap["owned_by_stage"] == "S3-T03"
    assert gap["not_a_model_failure"]
    assert gap["not_a_provider_failure"]
    assert gap["not_an_input_or_financial_truth_failure"]
    assert gap["not_a_reason_to_reopen_S0_S1_or_S2"]
    assert len(gap["required_minimum_fix"]) == 8
    assert not gap["evidence"][
        "exact_match_and_fresh_identity_contracts_currently_compatible"
    ]
    assert authority["stage_acceptance"]["S3_T03_execution"] == "not_started"


def test_projection_backlog_and_project_os_route_only_to_zero_call_preflight() -> None:
    authority = _load(AUTHORITY)
    projection = _load(PROJECTION)
    backlog = _load(BACKLOG)["next_action"]
    authority_sha = hashlib.sha256(AUTHORITY.read_bytes()).hexdigest()
    projection_sha = hashlib.sha256(PROJECTION.read_bytes()).hexdigest()

    assert projection["decision_binding"]["sha256"] == authority_sha
    assert projection["current_truth"]["current_next_action"] == (
        authority["next_action"]
    )
    assert backlog["item_id"] == authority["next_action"]
    assert backlog["current_projection_ref"] == PROJECTION.relative_to(
        ROOT
    ).as_posix()
    assert backlog["current_projection_sha256"] == projection_sha
    assert backlog["S3_T03_authority_sha256"] == authority_sha
    assert backlog["S3_T03_execution_started"] is False

    capability = (ROOT / "docs/project_os/capability_status_ledger.jsonl").read_text(
        encoding="utf-8"
    )
    root_cause = (ROOT / "docs/project_os/root_cause_issue_ledger.jsonl").read_text(
        encoding="utf-8"
    )
    gap_id = authority["preexecution_gap"]["issue_id"]
    assert gap_id
    assert gap_id in capability
    assert gap_id in root_cause
