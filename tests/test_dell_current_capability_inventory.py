from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from sec_agent.agent_runtime.dell_agentic_contracts import canonical_digest
from sec_agent.agent_runtime.dell_current_capability_inventory import (
    CurrentCapabilityInventoryError,
    EXPECTED_EXTERNAL_MANIFEST_DIGEST,
    EXPECTED_EXTERNAL_MANIFEST_SHA256,
    EXPECTED_LOCAL_NODES_SHA256,
    EXPECTED_PHYSICAL_ROUTE_CATALOG_DIGEST,
    EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256,
    EXPECTED_S2_RESULT_DIGEST,
    EXPECTED_S2_RESULT_SHA256,
    build_current_capability_inventory,
    build_current_host_owned_baseline_source_plan,
    build_external_inventory_buckets_from_manifest,
    build_local_inventory_buckets_from_nodes,
    build_s2_capability_bucket_from_verified_result,
    build_source_family_catalog,
    load_physical_route_catalog,
)
from sec_agent.agent_runtime.planner_tool_capabilities import (
    derive_planner_tool_capabilities,
)
from sec_agent.agent_runtime.dell_owner_data_gate import (
    load_dell_owner_data_gate_decision,
)
from sec_agent.agent_runtime.dell_reviewed_evidence_inventory import (
    DEFAULT_BASE_PACK_PATH,
    DEFAULT_CONFIG_PATH,
    DEFAULT_OVERLAY_PATH,
    load_executable_reviewed_evidence_index_v1_2,
)
from sec_agent.agent_runtime.dell_source_family_compiler import SourceFamilyCompiler


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json"
)
FOUNDATION_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)
LOCAL_NODES_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
    "rag_mature_stack/retrieval_qualification/"
    "dell_rag_full_stack_preview_attempt_20260902_03/retrieval_nodes.jsonl"
)
EXTERNAL_MANIFEST_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
    "external_exact_url_qualification/"
    "dell_external_exact_url_zero_model_20260902_r12/manifest.json"
)
S2_DIR = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
    "s2_exact_period_contract_successor_20260902_r1"
)
S2_RESULT_PATH = S2_DIR / "company_financial_fact_mart_result.json"
S2_SQLITE_PATH = S2_DIR / "company_financial_facts.sqlite"
S2_SQLITE_SHA256 = (
    "363780c076d0f8766c0ceaafdb8b93d308d339636504b2a263127bb6ca365ac4"
)


def _raw_foundation() -> dict[str, Any]:
    return json.loads(FOUNDATION_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def physical_catalog():
    return load_physical_route_catalog(
        CATALOG_PATH,
        expected_file_sha256=EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256,
        expected_catalog_digest=EXPECTED_PHYSICAL_ROUTE_CATALOG_DIGEST,
    )


@pytest.fixture(scope="module")
def family_catalog(physical_catalog):
    foundation = _raw_foundation()
    return build_source_family_catalog(
        physical_catalog,
        foundation_source_families=foundation["source_families"],
        foundation_question_branches=foundation["question_branches"],
    )


def test_current_catalog_binds_exact_artifacts_and_preserves_review_gate(
    physical_catalog,
) -> None:
    assert physical_catalog.file_sha256 == EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256
    assert physical_catalog.catalog_digest == EXPECTED_PHYSICAL_ROUTE_CATALOG_DIGEST
    assert physical_catalog.local_nodes_sha256 == EXPECTED_LOCAL_NODES_SHA256
    assert physical_catalog.external_manifest_sha256 == EXPECTED_EXTERNAL_MANIFEST_SHA256
    assert physical_catalog.external_manifest_digest == EXPECTED_EXTERNAL_MANIFEST_DIGEST
    assert len(physical_catalog.local_routes) == 20
    assert len(physical_catalog.external_routes) == 12
    assert physical_catalog.expected_physical_node_count == 1_025
    assert physical_catalog.expected_searchable_leaf_count == 890
    assert physical_catalog.expected_parent_section_count == 135
    assert physical_catalog.execution_authority is False
    assert physical_catalog.blocking_owner_review_ids == (
        "OR-001-Q9-FAMILY-MISMATCH",
        "OR-004-TOPIC-MAPPING-PRECEDENCE",
    )


def test_catalog_file_hash_and_self_digest_fail_closed(tmp_path: Path) -> None:
    tampered = tmp_path / "catalog.json"
    tampered.write_bytes(CATALOG_PATH.read_bytes() + b"\n")
    with pytest.raises(
        CurrentCapabilityInventoryError, match="physical_catalog_file_sha256_mismatch"
    ):
        load_physical_route_catalog(
            tampered,
            expected_file_sha256=EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256,
        )

    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    raw["purpose"] += " tampered"
    tampered.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    actual_file_sha = sha256(tampered.read_bytes()).hexdigest()
    with pytest.raises(
        CurrentCapabilityInventoryError, match="physical_catalog_self_digest_mismatch"
    ):
        load_physical_route_catalog(tampered, expected_file_sha256=actual_file_sha)


def test_catalog_forbids_source_body_fields_even_with_valid_digests(
    tmp_path: Path,
) -> None:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    raw["owner_review_items"][0]["content"] = "must never be catalogued"
    raw["catalog_digest"] = canonical_digest(
        {key: value for key, value in raw.items() if key != "catalog_digest"}
    )
    candidate = tmp_path / "catalog-with-body.json"
    candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(
        CurrentCapabilityInventoryError, match="physical_catalog_forbidden_field"
    ):
        load_physical_route_catalog(
            candidate,
            expected_file_sha256=sha256(candidate.read_bytes()).hexdigest(),
        )


def test_family_catalog_uses_policy_allowlist_and_keeps_unavailable_baseline_families(
    family_catalog,
) -> None:
    entries = {entry.source_family_ref: entry for entry in family_catalog.entries}
    assert len(entries) == 11
    for family in ("F5_PUBLIC_PROCUREMENT", "F12_INDEPENDENT_COUNTEREVIDENCE"):
        assert entries[family].supported_route_kinds == (
            "external_source",
            "local_candidate",
            "reviewed_evidence",
        )
        assert entries[family].local_cardinality_ceiling == 100_000
        assert entries[family].semantic_role_refs
        assert entries[family].authority_refs == (
            "authority:primary-read",
            "authority:reviewed-read",
        )


def test_changed_foundation_requirement_is_rejected(physical_catalog) -> None:
    foundation = _raw_foundation()
    foundation["question_branches"][0]["required_source_families"] = [
        "F2_DELL_IR_EARNINGS"
    ]
    with pytest.raises(CurrentCapabilityInventoryError, match="foundation_mapping_mismatch"):
        build_source_family_catalog(
            physical_catalog,
            foundation_source_families=foundation["source_families"],
            foundation_question_branches=foundation["question_branches"],
        )


@pytest.mark.skipif(not LOCAL_NODES_PATH.exists(), reason="real Z: S1 artifact absent")
def test_real_local_nodes_build_only_890_cooccurring_leaf_buckets(
    physical_catalog,
    family_catalog,
) -> None:
    foundation = _raw_foundation()
    semantic_roles = {
        row["source_family_id"]: row["authority"]
        for row in foundation["source_families"]
    }
    first = build_local_inventory_buckets_from_nodes(
        nodes_path=LOCAL_NODES_PATH,
        catalog=physical_catalog,
        source_family_catalog=family_catalog,
        semantic_role_by_source_family=semantic_roles,
    )
    second = build_local_inventory_buckets_from_nodes(
        nodes_path=LOCAL_NODES_PATH,
        catalog=physical_catalog,
        source_family_catalog=family_catalog,
        semantic_role_by_source_family=semantic_roles,
    )
    assert len(first) == 28
    assert sum(row.eligible_object_count for row in first) == 890
    assert sum(row.eligible_object_count for row in first if row.lane == "prose_leaf") == 656
    assert sum(row.eligible_object_count for row in first if row.lane == "table_leaf") == 234
    assert {row.route_id for row in first} == {
        row.route_id for row in physical_catalog.local_routes
    }
    assert [row.bucket_digest for row in first] == [row.bucket_digest for row in second]
    projected = json.dumps([row.model_dump(mode="json") for row in first])
    assert '"content":' not in projected
    assert '"model_text":' not in projected
    assert '"value":' not in projected


@pytest.mark.skipif(
    not EXTERNAL_MANIFEST_PATH.exists(), reason="real Z: external manifest absent"
)
def test_real_r12_builds_12_entity_bound_external_buckets(
    physical_catalog,
    family_catalog,
) -> None:
    buckets = build_external_inventory_buckets_from_manifest(
        manifest_path=EXTERNAL_MANIFEST_PATH,
        catalog=physical_catalog,
        source_family_catalog=family_catalog,
    )
    by_route = {row.external_route_ref: row for row in buckets}
    assert len(by_route) == 12
    assert by_route["E02_TSMC_2Q26_TRANSCRIPT"].canonical_entity_id == "TSMC"
    assert "TSM" in by_route["E02_TSMC_2Q26_TRANSCRIPT"].entity_refs
    assert by_route["E05_DELL_Q2_FY27_SEC_EXHIBIT"].period_refs == ("FY2027 Q2",)
    assert by_route["E11_SMCI_Q4_FY26_RESULTS"].foundation_required_family_match is False
    projected = json.dumps([row.model_dump(mode="json") for row in buckets])
    assert "matched_content_markers" not in projected
    assert "bounded_text" not in projected


@pytest.mark.skipif(
    not (S2_RESULT_PATH.exists() and S2_SQLITE_PATH.exists()),
    reason="real Z: S2 artifacts absent",
)
def test_real_s2_result_reuses_existing_capability_projection(physical_catalog) -> None:
    planner = derive_planner_tool_capabilities(
        sqlite_path=S2_SQLITE_PATH,
        expected_mart_sha256=S2_SQLITE_SHA256,
        snapshot_id="s2:current-inventory:test",
    )
    bucket = build_s2_capability_bucket_from_verified_result(
        result_path=S2_RESULT_PATH,
        expected_result_sha256=EXPECTED_S2_RESULT_SHA256,
        planner_capabilities=planner,
        catalog=physical_catalog,
    )
    result = json.loads(S2_RESULT_PATH.read_text(encoding="utf-8"))
    assert result["result_digest"] == EXPECTED_S2_RESULT_DIGEST
    assert bucket.eligible_observation_count == 1_319
    assert bucket.entity_refs == ("DELL", "MICRON", "NVIDIA")
    assert len(bucket.metric_refs) == 12
    assert all(ref.startswith("period_role:") for ref in bucket.period_refs)


def test_total_inventory_refuses_candidate_catalog_before_touching_other_inputs() -> None:
    with pytest.raises(
        CurrentCapabilityInventoryError,
        match="physical_catalog_not_execution_authority:.*OR-001.*OR-004",
    ):
        build_current_capability_inventory(
            physical_catalog_path=CATALOG_PATH,
            expected_physical_catalog_sha256=EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256,
            foundation_source_families=[],
            foundation_question_branches=[],
            local_nodes_path="does-not-exist",
            external_manifest_path="does-not-exist",
            s2_result_path="does-not-exist",
            expected_s2_result_sha256=EXPECTED_S2_RESULT_SHA256,
            planner_capabilities=None,  # type: ignore[arg-type]
            reviewed_index=None,  # type: ignore[arg-type]
            snapshot_id="inventory:must-not-exist",
        )


@pytest.mark.skipif(
    not all(
        path.is_file()
        for path in (
            LOCAL_NODES_PATH,
            EXTERNAL_MANIFEST_PATH,
            S2_RESULT_PATH,
            S2_SQLITE_PATH,
            DEFAULT_CONFIG_PATH,
            DEFAULT_BASE_PACK_PATH,
            DEFAULT_OVERLAY_PATH,
        )
    ),
    reason="exact Dell Owner-gated runtime artifacts unavailable",
)
def test_owner_decision_composes_exact_56_and_frozen_s2_inventory() -> None:
    decision = load_dell_owner_data_gate_decision()
    foundation = _raw_foundation()
    planner = derive_planner_tool_capabilities(
        sqlite_path=S2_SQLITE_PATH,
        expected_mart_sha256=decision.bound_inputs.s2_mart_sha256,
        snapshot_id="s2:owner-data-gate:test",
    )
    reviewed = load_executable_reviewed_evidence_index_v1_2(
        owner_decision=decision
    )
    snapshot = build_current_capability_inventory(
        physical_catalog_path=CATALOG_PATH,
        expected_physical_catalog_sha256=(
            decision.bound_inputs.physical_catalog_sha256
        ),
        foundation_source_families=foundation["source_families"],
        foundation_question_branches=foundation["question_branches"],
        local_nodes_path=LOCAL_NODES_PATH,
        external_manifest_path=EXTERNAL_MANIFEST_PATH,
        s2_result_path=S2_RESULT_PATH,
        expected_s2_result_sha256=decision.bound_inputs.s2_result_sha256,
        planner_capabilities=planner,
        reviewed_index=reviewed,
        snapshot_id="inventory:owner-data-gate:test",
        owner_data_gate_decision=decision,
    )

    assert snapshot.reviewed_evidence_count == 56
    assert snapshot.s2_observation_count == 1_319
    assert snapshot.owner_data_gate_decision_digest == decision.decision_digest
    assert {
        row.capability_kind: row.validated_object_count
        for row in snapshot.component_bindings
    } == {
        "external_source": 12,
        "local_candidate": 890,
        "reviewed_evidence": 56,
        "s2_numeric_fact": 1_319,
    }
    baseline = build_current_host_owned_baseline_source_plan(
        inventory=snapshot,
        owner_data_gate_decision=decision,
    )
    compiler = SourceFamilyCompiler(inventory=snapshot, baseline=baseline)
    provider_catalog = compiler.provider_route_catalog()
    route_ids = {
        row["minimum_route_obligation_id"] for row in provider_catalog["routes"]
    }
    assert "route:Q3_UNITS_ASP_PVM:F3_DELL_PRODUCT_SUPPORT:local" not in route_ids
    assert "route:Q4_ARCHITECTURE_RAMP:F4_CUSTOMER_CAPEX_DEPLOYMENT:local" not in route_ids
    assert not any(
        row["coverage_obligation_id"] == "Q9_COUNTEREVIDENCE_WWC"
        and row["intent_kind"] == "external_source"
        for row in provider_catalog["routes"]
    )
    serialized_catalog = json.dumps(provider_catalog)
    for physical_key in (
        "issuer_ids",
        "route_ids",
        "lanes",
        "domain_allowlist",
        "external_route_ref",
    ):
        assert physical_key not in serialized_catalog

    with pytest.raises(
        CurrentCapabilityInventoryError,
        match="owner_data_gate_s2_runtime_binding_mismatch",
    ):
        build_current_capability_inventory(
            physical_catalog_path=CATALOG_PATH,
            expected_physical_catalog_sha256=(
                decision.bound_inputs.physical_catalog_sha256
            ),
            foundation_source_families=foundation["source_families"],
            foundation_question_branches=foundation["question_branches"],
            local_nodes_path=LOCAL_NODES_PATH,
            external_manifest_path=EXTERNAL_MANIFEST_PATH,
            s2_result_path=S2_RESULT_PATH,
            expected_s2_result_sha256="0" * 64,
            planner_capabilities=planner,
            reviewed_index=reviewed,
            snapshot_id="inventory:owner-data-gate:forged-s2",
            owner_data_gate_decision=decision,
        )
