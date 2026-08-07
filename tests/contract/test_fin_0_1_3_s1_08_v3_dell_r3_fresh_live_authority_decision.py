from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_binds_immutable_r2_v3_proof_and_catalog() -> None:
    decision = _load(DECISION_PATH)
    basis = decision["immutable_basis"]

    assert decision["decision_status"] == "approved_successor_entrypoint_required_before_issuance"
    assert decision["project_os_preflight"] == {
        "run_scope": "S1_08_V3_DELL_FRESH_LIVE_AUTHORITY_DECISION",
        "status": "pass",
        "allow_open_blockers": False,
        "open_full_chain_blocker_count": 0,
    }
    assert basis["DELL_R2_terminal"]["state"] == "complete_consumed_product_source_quality_failed"
    assert basis["DELL_R2_terminal"]["target_in_pool_recall"] == 0.0
    assert basis["v3_engineering_proof"]["state"] == "independently_proven"
    assert basis["v3_engineering_proof"]["tests_per_worker"] == 60
    assert basis["v3_engineering_proof"]["failed_per_worker"] == 0

    for binding in (
        basis["DELL_R2_terminal"],
        basis["post_R2_disposition"],
        basis["v3_engineering_proof"],
        basis["v3_catalog"],
    ):
        ref_key = "ref"
        if "result_ref" in binding:
            assert _sha256(ROOT / binding["result_ref"]) == binding["result_sha256"]
            assert _sha256(ROOT / binding["quality_evaluation_ref"]) == binding["quality_evaluation_sha256"]
            continue
        assert _sha256(ROOT / binding[ref_key]) == binding["sha256"]


def test_decision_approves_only_one_bounded_future_r3() -> None:
    decision = _load(DECISION_PATH)
    authority = decision["replacement_authority"]
    issuance = decision["issuance_state"]
    acceptance = decision["R3_live_acceptance"]

    assert authority["attempt_label"] == "R3"
    assert authority["maximum_fresh_admissions"] == 1
    assert authority["maximum_exact_live_executions"] == 1
    assert authority["network_calls_max"] == 16
    assert authority["maximum_document_fetches_per_attempt"] == 2
    assert authority["maximum_accepted_unique_documents_per_attempt"] == 1
    assert authority["model_calls"] == 0
    assert authority["provider_model_calls"] == 0
    assert authority["retry_calls"] == 0
    assert authority["automatic_R4"] is False
    assert sum(authority["slot_group_reservations"].values()) == 16

    assert issuance["currently_issuable"] is False
    assert issuance["old_R2_reuse_forbidden"] is True
    assert any("v2 catalog" in item for item in issuance["required_R3_successor"])
    assert acceptance["DELL_target_in_pool"] == 1.0
    assert acceptance["required_slot_recall_at_8"] == 1.0
    assert acceptance["qualified_unique_document_yield_min"] == 0.5
    assert acceptance["ranking_metrics_admitted_by_this_run"] is False
    assert acceptance["broad_external_search_claim_allowed"] is False


def test_decision_preserves_provider_truth_and_stops_after_candidate_ceiling_failure() -> None:
    decision = _load(DECISION_PATH)
    provider = decision["provider_capability_truth_at_decision"]
    serialized = json.dumps(decision, ensure_ascii=False)

    assert provider["official_ir_feed_discovery"] == "operational_replay_proven_live_unproven"
    assert provider["official_domain_bounded_search"] == "operational_replay_proven_live_unproven"
    assert provider["external_site_search"] == "declared_not_configured_not_operational"
    assert provider["runtime_SEC_contact_identity"] == "present_value_not_read_must_be_revalidated_before_issuance"
    assert decision["observed_calls"] == {
        "network": 0,
        "model": 0,
        "provider": 0,
        "retry": 0,
        "admission": 0,
        "live": 0,
    }
    assert any("provider-acquisition or product-source-scope decision" in rule for rule in decision["stop_rules"])
    assert any("no automatic retry" in rule for rule in decision["stop_rules"])
    assert re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", serialized) is None
    assert "sk-" not in serialized
    assert decision["current_next"] == "S1_08_V3_DELL_R3_SUCCESSOR_ENTRYPOINT_ZERO_CALL_IMPLEMENTATION"
