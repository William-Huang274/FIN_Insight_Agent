from __future__ import annotations

import json
from pathlib import Path

from sec_agent.canonical_runtime.candidate_bundle import CandidateMetadata
from sec_agent.canonical_runtime.evidence_gate import EvidenceGatePolicy
from sec_agent.canonical_runtime.parser_numeric import NumericFixtureObservation, ParserNumericPolicy


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt2_three_cell_integrity_workpaper_contract_v1_0.json"
)
POINT03_PATH = REPO_ROOT / "configs" / "releases" / "point03_vt1_evidence_workbench_contract_v1_0.json"


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_vt2_scope_is_one_three_cell_vertical_increment() -> None:
    contract = _contract()

    assert contract["schema_version"] == "fin_ia_0_1_vt2_three_cell_integrity_workpaper_contract_v1_0"
    assert contract["status"] == "active_fixture_shadow_internal_development"
    assert contract["consumes"]["active_cell_roles"] == [
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    ]
    assert contract["current_scope"]["included_execution_points"] == [
        "P03.4_fixture_repair_subset",
        "P04.0-P04.4_three_cell_numeric_subset",
        "P05.0-P05.4_three_cell_workpaper_subset",
    ]
    assert "P02.6_10_to_20_cell_calibration" in contract["current_scope"]["deferred_execution_points"]
    assert "P05.5_same_case_follow_up" in contract["current_scope"]["deferred_execution_points"]


def test_vt2_routes_cover_repair_numeric_workpaper_and_exact_lead_review() -> None:
    routes = {(row["method"], row["operation"], row["permission"]) for row in _contract()["routes"]}

    assert routes == {
        ("POST", "executeEvidenceRepairFixture", "evidence:repair"),
        ("GET", "getNumericWorkbench", "numeric:read"),
        ("POST", "compileNumericFixture", "numeric:write"),
        ("GET", "getWorkpaper", "workpaper:read"),
        ("POST", "compileWorkpaperFixture", "workpaper:write"),
        ("POST", "completeLeadReviewFixture", "lead_review:decide"),
    }
    version_contract = _contract()["version_contract"]
    assert version_contract["lead_review"] == "append_only_exact_workpaper_version_and_content_digest"
    assert version_contract["idempotency"] == "required_on_every_mutation"


def test_vt2_repair_and_numeric_fixture_reuse_strict_canonical_models() -> None:
    contract = _contract()
    point03 = json.loads(POINT03_PATH.read_text(encoding="utf-8"))
    repair = contract["repair_fixture"]
    numeric = contract["numeric_fixture"]

    candidate = CandidateMetadata.model_validate(repair["candidate"]["metadata"])
    parser_policy = ParserNumericPolicy.model_validate(numeric["parser_policy"])
    observation = NumericFixtureObservation.model_validate(numeric["observation"])
    gate_policy = EvidenceGatePolicy.model_validate(numeric["evidence_gate_policy"])

    assert repair["target_evidence_role"] == "thesis_counterevidence"
    assert candidate.source_policy_ref == point03["evidence_request_policy"]["role_rules"][
        "thesis_counterevidence"
    ]["allowed_source_policy_refs"][0]
    assert observation.candidate_id == numeric["source_candidate_id"]
    assert observation.unit in parser_policy.allowed_units
    assert gate_policy.minimum_source_authority_rank_by_evidence_role["revenue_candidate"] == 4


def test_vt2_fixture_promotion_cannot_become_writer_or_release_authority() -> None:
    contract = _contract()
    promotion = contract["numeric_fixture"]["internal_promotion"]
    boundaries = contract["hard_boundaries"]

    assert promotion == {
        "decision": "accepted_for_internal_fixture_judgment",
        "scope": "internal_fixture_judgment_only",
        "runtime_promotion_authorized": False,
        "writer_citable": False,
        "release_evidence": False,
    }
    for key in (
        "network_calls",
        "tool_invocations",
        "model_calls",
        "provider_calls",
        "paid_full_chain",
        "writer_execution",
        "runtime_promotion",
        "release_evidence",
    ):
        assert boundaries[key] == 0
    assert boundaries["real_business_case_mutation"] == "forbidden"
    assert boundaries["production_cutover"] == "forbidden"


def test_vt2_workpaper_requires_exact_repair_numeric_and_counter_thesis_sections() -> None:
    workpaper = _contract()["workpaper_fixture"]

    assert workpaper["required_judgment_roles"] == [
        "demand_signal",
        "revenue_capture",
        "thesis_counterevidence",
    ]
    assert set(workpaper["required_sections"]) == {
        "judgment",
        "supporting_evidence",
        "numeric_trace",
        "counter_thesis",
        "what_would_change",
        "remaining_gaps",
    }
    assert workpaper["lead_review_decisions"] == [
        "admit_fixture_writer_preview",
        "return_for_repair",
    ]
    assert workpaper["writer_admission_boundary"] == "fixture_preview_only_no_writer_execution"
