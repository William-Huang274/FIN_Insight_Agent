from __future__ import annotations

import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.canonical_runtime.evidence_request import EvidenceRequestRoleRule


CONTRACT_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_p36_candidate_profile_v1_0.json"
)

LEGACY_CELL_KEYS = [
    "demand_reality",
    "value_profit_capture",
    "bottleneck_counterevidence",
]
ACTIVE_ROLES = [
    "demand_signal",
    "revenue_capture",
    "thesis_counterevidence",
    "server_oem_orders",
    "server_oem_margin_cash",
    "advanced_packaging_capacity",
    "hbm_supply_pricing",
    "semicap_capex_cycle",
    "export_policy_risk",
    "customer_concentration",
]
NEW_ROLES = ACTIVE_ROLES[3:]
REQUIRED_FAMILIES = {
    "accelerator_demand_value_capture_concentration",
    "server_oem_revenue_margin_cash_conversion",
    "foundry_advanced_packaging_capacity_bottleneck_rent",
    "hbm_demand_supply_pricing_concentration",
    "semicap_capex_readthrough_cycle_export_policy",
    "cross_chain_counterthesis_price_in_what_would_change",
}


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_vt4_profile_parses_and_retains_fixture_only_authority_and_history() -> None:
    contract = _contract()

    assert contract["schema_version"] == "fin_ia_0_1_vt4_p36_candidate_profile_v1_0"
    assert contract["release_id"] == "REL-PROD-001"
    assert contract["authority"] == {
        "development_mode": "fixture_shadow_internal_only",
        "runtime_admission": "not_granted",
        "production_readiness": "not_admitted",
        "legacy_global_authority": "retained",
    }
    assert contract["supersedes"]["scope"] == "active_candidate_profile_topology_only"
    assert contract["supersedes"]["historical_artifacts"] == "retained_immutable_not_modified"
    assert contract["supersedes"]["does_not_supersede_historical_artifacts"] is True
    assert contract["extends"]["historical_artifact_mutation"] == "forbidden"
    assert len(contract["extends"]["contract_paths"]) == 3


def test_vt4_planning_profile_has_ten_unique_roles_slots_and_required_families() -> None:
    planning = _contract()["planning_profile"]
    cells = planning["cells"]

    assert planning["compiler_policy_ref"] == "fixture:p36-ten-cell-v1"
    assert planning["pack_selection_ref"] == "fixture:p36-ai-infrastructure-v2"
    assert planning["exact_cell_count"] == 10
    assert len(cells) == 10
    assert planning["active_cell_roles"] == ACTIVE_ROLES
    assert [cell["cell_key"] for cell in cells[:3]] == LEGACY_CELL_KEYS
    assert [cell["active_role"] for cell in cells[:3]] == ACTIVE_ROLES[:3]
    assert all(cell["legacy_chain_compatibility"].strip() for cell in cells[:3])
    assert [cell["active_role"] for cell in cells] == ACTIVE_ROLES
    assert len({cell["active_role"] for cell in cells}) == 10

    covered_families = set()
    slot_roles = []
    for cell in cells:
        for field in ("decision_question", "owner_role", "materiality", "stop_rule", "what_would_change"):
            assert cell[field].strip(), field
        assert cell["evidence_slots"]
        covered_families.update(cell["feature_scope_families"])
        for slot in cell["evidence_slots"]:
            assert slot["entity_scope"]
            assert slot["period_scope"].strip()
            assert slot["source_policy_ref"].strip()
            assert slot["acceptance_role"].strip()
            assert slot["required"] is True
            slot_roles.append(slot["evidence_role"])

    assert set(planning["required_feature_scope_families"]) == REQUIRED_FAMILIES
    assert REQUIRED_FAMILIES <= covered_families
    assert slot_roles == ACTIVE_ROLES
    assert len(set(slot_roles)) == 10


def test_vt4_new_role_extensions_are_single_fixture_candidates_without_facts() -> None:
    extensions = _contract()["evidence_role_extensions"]
    candidate_ids: list[str] = []
    document_ids: list[str] = []
    content_refs: list[str] = []
    required_metadata_fields = {
        "candidate_id",
        "document_id",
        "document_version",
        "source_snapshot_ref",
        "source_policy_ref",
        "route_id",
        "source_role",
        "source_authority_rank",
        "entity_ref",
        "period_ref",
        "candidate_kind",
        "section_or_table_ref",
        "metadata_rank",
        "content_ref",
    }
    required_display_fields = {
        "title",
        "source_name",
        "source_type",
        "published_at",
        "citation",
        "excerpt",
        "authority_label",
        "applicability_boundary",
    }
    forbidden_fact_fields = {
        "raw_value",
        "numeric_value",
        "reported_value",
        "actual_value",
        "fact_value",
        "amount",
        "percentage",
        "currency",
        "unit",
        "scale",
        "ranking",
        "company_rank",
    }

    assert set(extensions) == set(NEW_ROLES)
    for role in NEW_ROLES:
        extension = extensions[role]
        policy = extension["request_policy"]
        candidates = extension["fixture_candidates"]

        assert extension["promotion_boundary"] == "not_in_this_contract"
        assert len(candidates) == 1
        EvidenceRequestRoleRule.model_validate(policy)
        assert policy["allowed_acceptance_roles"]

        if role == "export_policy_risk":
            assert policy["accepted_evidence_role"] == "counterevidence_candidate"
            assert policy["allowed_source_policy_refs"] == ["fixture:issuer_and_policy_first"]
            assert policy["preferred_routes"] == ["fixture_policy_counterevidence_metadata_route"]
        else:
            assert policy["accepted_evidence_role"] == "revenue_candidate"
            assert policy["allowed_source_policy_refs"] == ["fixture:issuer_filing_first"]
            assert policy["preferred_routes"] == ["fixture_issuer_filing_metadata_route"]

        candidate = candidates[0]
        metadata = candidate["metadata"]
        display = candidate["display"]
        assert required_metadata_fields <= set(metadata)
        assert required_display_fields <= set(display)
        assert forbidden_fact_fields.isdisjoint(metadata)
        assert forbidden_fact_fields.isdisjoint(display)
        assert metadata["candidate_id"].startswith("p36_vt4_fixture_")
        assert metadata["document_id"].startswith("fixture_p36_vt4_")
        assert metadata["source_policy_ref"] in policy["allowed_source_policy_refs"]
        assert metadata["route_id"] in policy["preferred_routes"]
        assert "fixture structural context only" in display["excerpt"].lower()
        assert "promotion boundary is not in this contract" in display["applicability_boundary"].lower()
        candidate_ids.append(metadata["candidate_id"])
        document_ids.append(metadata["document_id"])
        content_refs.append(metadata["content_ref"])

    assert len(set(candidate_ids)) == len(NEW_ROLES)
    assert len(set(document_ids)) == len(NEW_ROLES)
    assert len(set(content_refs)) == len(NEW_ROLES)


def test_vt4_workpaper_and_deliverable_keep_all_roles_fixture_structural() -> None:
    contract = _contract()
    workpaper = contract["workpaper_profile"]
    deliverable = contract["deliverable_profile"]

    assert workpaper["required_judgment_roles"] == ACTIVE_ROLES
    assert list(workpaper["judgment_status_by_role"]) == ACTIVE_ROLES
    assert list(workpaper["judgment_templates"]) == ACTIVE_ROLES
    for role, template in workpaper["judgment_templates"].items():
        assert set(template) == {"judgment", "counter_thesis", "remaining_gaps", "confidence"}
        assert template["judgment"].strip()
        assert template["counter_thesis"].strip()
        assert template["confidence"].strip()
        assert isinstance(template["remaining_gaps"], list)
        assert template["remaining_gaps"] and all(
            isinstance(value, str) and value.strip()
            for value in template["remaining_gaps"]
        )
        if role in NEW_ROLES:
            assert workpaper["judgment_status_by_role"][role] == "structural_fixture_only_explicit_gap"
            assert "structural fixture judgment only" in template["judgment"].lower()
            assert "explicit gap" in template["remaining_gaps"][0].lower()
            assert template["confidence"] == "fixture_structural_only_not_sector_research_validity"

    assert "P36 ten-cell fixture" in deliverable["title"]
    assert "P36 ten-cell fixture" in deliverable["executive_line"]
    assert deliverable["active_cell_roles"] == ACTIVE_ROLES


def test_vt4_saas_and_us_banks_regressions_are_structural_only() -> None:
    regressions = _contract()["structural_regressions"]

    assert regressions["status"] == "structural_only_not_sector_research_validity"
    cases = {case["case_key"]: case for case in regressions["cases"]}
    assert set(cases) == {"saas", "us_banks"}
    for case in cases.values():
        assert set(case["expected_cell_families"]) == REQUIRED_FAMILIES
        for field in (
            "forbidden_inherited_facts",
            "forbidden_inherited_numbers",
            "forbidden_inherited_rankings",
            "forbidden_inherited_source_refs",
        ):
            assert case[field]
        assert set(case["required_observations"]) == {"typed_gaps_required", "no_stale_P36_facts"}
        assert case["status"] == "structural_only_not_sector_research_validity"


def test_vt4_evaluation_boundaries_and_rg1_block_are_explicit() -> None:
    contract = _contract()
    evaluation = contract["evaluation_profile"]
    expected_metrics = {
        "time_to_workpaper",
        "review_burden",
        "repeated_work",
        "external_tool_model_cost",
        "browser_performance",
        "accessibility",
    }

    assert set(evaluation["metrics"]) == expected_metrics
    for metric in evaluation["metrics"].values():
        assert metric["definition"].strip()
        assert metric["collection_point"].strip()
    assert evaluation["p07_5"] == {
        "status": "blocked_by_RG1_debt",
        "blocking_debt": "RG1",
        "reason": "P07.5 release admission remains blocked until separately authorized RG1 operational qualification is closed.",
    }
    assert evaluation["rollback"] == {
        "target_release_id": "REL-FND-001",
        "legacy_global_authority": "retained",
    }

    for key in (
        "network_calls",
        "model_calls",
        "provider_calls",
        "tool_invocations",
        "paid_full_chain",
        "full_chain",
        "real_business_case_write",
        "release_admission",
    ):
        assert contract["hard_boundaries"][key] == 0
    for key in (
        "runtime_writes",
        "report_writes",
        "gate_family_creation",
        "package_family_creation",
        "historical_artifact_mutation",
    ):
        assert contract["scope_boundaries"][key] == 0
