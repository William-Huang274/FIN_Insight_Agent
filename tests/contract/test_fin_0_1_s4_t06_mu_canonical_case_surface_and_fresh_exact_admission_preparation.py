from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PACK = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_source_grounded_input_pack_v1_0.json"
)
PLANNING_PROFILE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_canonical_planning_profile_v1_0.json"
)
DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_canonical_case_surface_and_fresh_exact_"
    "admission_preparation_zero_call_proof_v1_0.json"
)
PROSPECTIVE_ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_fresh_exact_admission_r1.json"
)
ISSUANCE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_fresh_exact_admission_issuance_v1_0.json"
)
CANONICAL_DATABASE = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
    / "canonical-runtime"
    / "canonical.sqlite"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(table: str, case_id: str) -> list[dict]:
    connection = sqlite3.connect(CANONICAL_DATABASE)
    try:
        return [
            json.loads(payload_json)
            for (payload_json,) in connection.execute(
                f"select payload_json from {table}"
            )
            if json.loads(payload_json).get("case_id") == case_id
        ]
    finally:
        connection.close()


def test_mu_planning_profile_is_case_local_and_contract_derived() -> None:
    profile = _load(PLANNING_PROFILE)["planning_profile"]
    assert profile["compiler_policy_ref"] == "fin01.s4.mu_three_cell:v1"
    assert profile["pack_selection_ref"] == (
        "fin01.s4.mu_hbm_source_grounded:v1"
    )
    assert profile["exact_cell_count"] == 3
    assert len(profile["cells"]) == 3
    assert all(
        slot["entity_scope"] == ["MU"]
        and slot["required"] is True
        and "cross_issuer_fact" in slot["forbidden_substitutions"]
        for cell in profile["cells"]
        for slot in cell["evidence_slots"]
    )


def test_mu_canonical_case_surface_and_input_are_materialized_without_run() -> None:
    decision = _load(DECISION)
    materialized = decision["canonical_materialization"]
    case_id = materialized["case_id"]
    counts = materialized["logical_counts"]
    assert decision["status"] == (
        "pass_MU_canonical_case_surface_exact_input_materialized_"
        "fresh_admission_frozen_unissued_zero_call"
    )
    assert materialized["planning_checkpoint_status"] == "accepted"
    assert materialized["planning_cell_count"] == 3
    assert materialized["idempotent_second_materialization"] is True
    assert (
        materialized["logical_digest_after_first_materialization"]
        == materialized["logical_digest_after_second_materialization"]
    )
    assert len(_rows("canonical_research_cases", case_id)) == 1
    assert len(
        _rows("canonical_decision_surface_contract_versions", case_id)
    ) == 1
    assert len(
        _rows("canonical_decision_surface_cell_versions", case_id)
    ) == 3
    assert counts["canonical_work_units"] == 0
    assert counts["canonical_attempts"] == 0
    assert counts["canonical_research_run_versions"] == 0
    assert counts["canonical_artifact_versions"] == 0


def test_fresh_deepseek_pro_admission_is_frozen_but_not_issued() -> None:
    decision = _load(DECISION)
    proof = decision["fresh_agent_proof"]
    prospective = proof["prospective_admission"]
    payload = prospective["payload"]
    assert decision["selected_mainline"] == {
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "model_tier": "pro_not_flash",
        "base_url": "https://api.deepseek.com/beta",
        "api_key_env": "DEEPSEEK_API_KEY",
    }
    assert proof["decision"] == "frozen_unissued_unconsumed"
    assert proof["double_prepare_parity"] is True
    assert all(proof["freshness_and_nonreuse"].values())
    assert payload["company"] == "MU"
    assert payload["case_id"] == decision[
        "canonical_materialization"
    ]["case_id"]
    assert payload["input_digest"] == proof["input_digest"]
    assert payload["provider"] == "deepseek"
    assert payload["model"] == "deepseek-v4-pro"
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False
    assert prospective["prospective_admission_file_absent"] is True
    if PROSPECTIVE_ADMISSION.exists():
        issuance = _load(ISSUANCE)
        assert issuance["issued_admission"]["admission_digest"] == (
            prospective["digest"]
        )
        assert issuance["issued_admission"]["consumed"] is False
        assert issuance["issued_admission"]["execution_started"] is False
    else:
        assert ISSUANCE.exists() is False


def test_prospective_admission_digest_survives_json_roundtrip() -> None:
    prospective = _load(DECISION)["fresh_agent_proof"][
        "prospective_admission"
    ]
    payload = prospective["payload"]
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(payload)
    assert canonical_digest(payload) == prospective["digest"]
    assert canonical_digest(admission.digest_payload()) == prospective[
        "digest"
    ]
    assert all(
        key not in payload
        for key in (
            "task_claim_link_policy_ref",
            "wwc_judgment_atom_policy_ref",
            "case_numeric_authority_policy_ref",
            "case_delivery_identity_policy_ref",
            "strict_truth_kernel_policy_ref",
            "provider_capability_ref",
            "non_authoritative_narrative_shell_ref",
        )
    )


def test_source_profile_and_zero_call_boundaries_are_frozen() -> None:
    decision = _load(DECISION)
    assert decision["source_execution"]["source_pack_sha256"] == _sha256(
        SOURCE_PACK
    )
    assert decision["planning_profile"]["sha256"] == _sha256(
        PLANNING_PROFILE
    )
    assert decision["truth_and_scope_boundaries"] == {
        "HBM_specific_revenue_or_profit_inferred": False,
        "customer_concentration_or_identity_inferred": False,
        "forward_demand_or_capacity_realized_as_fact": False,
        "graph_promoted_to_direct_evidence": False,
        "strict_schema_transport_reactivated": False,
    }
    assert set(decision["hard_boundaries"].values()) == {False, 0}
    assert decision["stage_acceptance"]["MU_R2"] == "not_started"
    assert decision["next_action"] == (
        "S4-T06-MU-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
