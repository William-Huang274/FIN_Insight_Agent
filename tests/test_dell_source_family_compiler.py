from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import TypeAdapter, ValidationError

from sec_agent.agent_runtime.dell_agentic_contracts import (
    DELL_COVERAGE_OBLIGATION_IDS,
    ExternalSourceIntent,
    LocalEvidenceIntent,
    MinimumRouteObligation,
    ProviderEvidenceIntent,
    ReviewedEvidenceIntent,
    canonical_digest,
    payload_without,
)
from sec_agent.agent_runtime.dell_source_family_compiler import (
    CapabilityArtifactBinding,
    CapabilityInventorySnapshot,
    DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE,
    ExternalInventoryBucket,
    LocalInventoryBucket,
    ReviewedEvidenceIndexRowV1_2,
    ReviewedEvidenceIndexV1_2,
    ReviewedEvidenceRereadMetadata,
    S2CapabilityBucket,
    SourceFamilyCatalog,
    SourceFamilyCatalogEntry,
    SourceFamilyCompiler,
    SourceFamilyCompilerError,
    build_host_owned_baseline_source_plan,
    compile_source_intent,
    filter_reviewed_evidence_hits,
    validate_host_owned_baseline_source_plan,
)


M = TypeVar("M")
ZERO = "0" * 64
FOUNDATION_DIGEST = "1" * 64
LOCAL_ARTIFACT_DIGEST = (
    "f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817"
)
REVIEWED_PACK_DIGEST = "2" * 64
S2_ARTIFACT_DIGEST = "3" * 64
EXTERNAL_ARTIFACT_DIGEST = (
    "db7eae9aaa8108faadbe7ff07404dd25414e0191b7f62af0c7a42b85a0938b94"
)
POLICY_DIGEST = "4" * 64

SEMANTIC_ROLE_BY_FAMILY = {
    "F1_SEC_ISSUER_FACTS": "issuer_numeric_and_filing_identity",
    "F2_DELL_IR_EARNINGS": "issuer_narrative_and_company_defined_metrics",
    "F3_DELL_PRODUCT_SUPPORT": "product_configuration_and_integration_state",
    "F4_CUSTOMER_CAPEX_DEPLOYMENT": "industry_demand_context_or_named_customer_relationship",
    "F5_PUBLIC_PROCUREMENT": "transaction_observation_not_company_total",
    "F6_COMPUTE_PLATFORM_SUPPLIERS": "platform_and_supplier_state",
    "F7_MEMORY_FOUNDRY_NETWORK_STORAGE": "supplier_reported_direction_and_capacity_state",
    "F8_OEM_COMPETITION": "peer_context_and_counterevidence",
    "F9_MODEL_COMPUTE_AND_BENCHMARKS": "workload_and_benchmark_context",
    "F10_EXPORT_CONTROL_AND_POLICY": "regulatory_text_and_effective_state",
    "F12_INDEPENDENT_COUNTEREVIDENCE": "candidate_or_independent_context_not_numeric_authority",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
PHYSICAL_CATALOG_PATH = (
    REPO_ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json"
)


def _signed(model: type[M], digest_field: str, **values: Any) -> M:
    provisional = model.model_construct(**values, **{digest_field: ZERO})
    digest = canonical_digest(payload_without(provisional, digest_field))
    return model(**values, **{digest_field: digest})


def _model_values(model: Any, *excluded: str) -> dict[str, Any]:
    return {
        field_name: getattr(model, field_name)
        for field_name in type(model).model_fields
        if field_name not in excluded
    }


def _physical_catalog() -> dict[str, Any]:
    return json.loads(PHYSICAL_CATALOG_PATH.read_text(encoding="utf-8"))


def _source_family_catalog() -> SourceFamilyCatalog:
    memberships: dict[str, set[str]] = {}
    for coverage_id, family_refs in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE:
        for family_ref in family_refs:
            memberships.setdefault(family_ref, set()).add(coverage_id)

    entries = []
    for family_ref in sorted(memberships):
        entries.append(
            _signed(
                SourceFamilyCatalogEntry,
                "entry_digest",
                source_family_ref=family_ref,
                coverage_obligation_ids=tuple(sorted(memberships[family_ref])),
                supported_route_kinds=(
                    "external_source",
                    "local_candidate",
                    "reviewed_evidence",
                ),
                semantic_role_refs=(SEMANTIC_ROLE_BY_FAMILY[family_ref],),
                authority_refs=(
                    "authority:primary-read",
                    "authority:reviewed-read",
                ),
                local_cardinality_ceiling=1_000,
            )
        )
    return _signed(
        SourceFamilyCatalog,
        "catalog_digest",
        contract_version="1.2",
        catalog_id="catalog:dell:test:v1",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN-0.1.3",
        research_as_of="2026-09-02",
        foundation_digest=FOUNDATION_DIGEST,
        entries=tuple(entries),
        answer_free=True,
    )


def _local_bucket(route: dict[str, Any]) -> LocalInventoryBucket:
    periods = tuple(sorted(route["fiscal_periods"]))
    values = {
        "bucket_id": f"local:{route['route_id']}",
        "source_family_ref": route["source_family_refs"][0],
        "branch_refs": tuple(sorted(route["branch_ids"])),
        "entity_refs": (route["canonical_issuer_id"],),
        "canonical_issuer_id": route["canonical_issuer_id"],
        "period_refs": periods,
        "fiscal_period": periods[0] if len(periods) == 1 else None,
        "semantic_role_refs": (
            SEMANTIC_ROLE_BY_FAMILY[route["source_family_refs"][0]],
        ),
        "source_role": route["source_role"],
        "route_id": route["route_id"],
        "lane": "prose_leaf",
        "content_surface_refs": ("prose",),
        "authority_refs": ("authority:primary-read",),
        "source_artifact_digest": LOCAL_ARTIFACT_DIGEST,
        "eligible_object_count": route["searchable_leaf_count"],
        "object_identity_digest": canonical_digest(
            {
                "route_id": route["route_id"],
                "searchable_leaf_count": route["searchable_leaf_count"],
            }
        ),
    }
    return _signed(LocalInventoryBucket, "bucket_digest", **values)


def _reviewed_row(
    index: int,
    *,
    family: str = "F2_DELL_IR_EARNINGS",
    topic: str = "cash_conversion_balance_sheet",
    metadata_state: str = "complete",
    minimum_route_eligible: bool = True,
) -> ReviewedEvidenceIndexRowV1_2:
    evidence_id = f"evidence:{index:03d}"
    locator = f"pack.json#{evidence_id}"
    complete = metadata_state == "complete"
    values = {
        "case_key": "DELL",
        "source_family_ref": family,
        "coverage_obligation_ids": ("Q1_ISSUER_TRUTH",),
        "minimum_route_eligible_branch_ids": (
            ("Q1_ISSUER_TRUTH",) if minimum_route_eligible else ()
        ),
        "entity_ids": ("DELL",) if complete else (),
        "target_id": "DELL",
        "topic_refs": (topic,) if complete else (),
        "evidence_role": "issuer_management_disclosure",
        "authority_tier": "reviewed",
        "publication_date": "2026-08-28",
        "period_refs": ("FY2027_Q2",) if complete else (),
        "source_reporting_period_end": "2026-07-31" if complete else None,
        "source_type": "issuer_filing",
        "source_tier": "primary",
        "evidence_id": evidence_id,
        "locator": locator,
        "locator_digest": canonical_digest({"locator": locator}),
        "item_digest": canonical_digest({"evidence_id": evidence_id}),
        "metadata_state": metadata_state,
    }
    return _signed(ReviewedEvidenceIndexRowV1_2, "row_digest", **values)


def _reviewed_index() -> ReviewedEvidenceIndexV1_2:
    rows = [
        _reviewed_row(0, topic="operating_performance"),
        _reviewed_row(1, topic="operating_performance"),
        _reviewed_row(2, topic="cash_conversion_balance_sheet"),
        _reviewed_row(3, metadata_state="legacy_query_only_locator"),
        _reviewed_row(4, family="F1_SEC_ISSUER_FACTS", topic="issuer_truth"),
    ]
    rows.extend(_reviewed_row(index) for index in range(5, 60))
    rows.append(
        _reviewed_row(
            60,
            topic="supplemental_only",
            minimum_route_eligible=False,
        )
    )
    return _signed(
        ReviewedEvidenceIndexV1_2,
        "index_digest",
        contract_version="1.2",
        index_id="reviewed-index:dell:test:v1",
        case_key="DELL",
        research_as_of="2026-09-02",
        source_pack_digest=REVIEWED_PACK_DIGEST,
        rows=tuple(rows),
        indexed_item_count=61,
        answer_free=True,
    )


def _s2_bucket() -> S2CapabilityBucket:
    return _signed(
        S2CapabilityBucket,
        "bucket_digest",
        bucket_id="s2:dell-mu-nvda:test",
        entity_refs=("DELL", "MICRON", "NVIDIA"),
        metric_refs=tuple(f"metric:{index:02d}" for index in range(12)),
        period_refs=("FY2026", "FY2027_Q1", "FY2027_Q2"),
        authority_refs=("authority:s2-read",),
        source_artifact_digest=S2_ARTIFACT_DIGEST,
        eligible_observation_count=1_319,
    )


def _external_buckets() -> tuple[ExternalInventoryBucket, ...]:
    rows = []
    for index in range(12):
        rows.append(
            _signed(
                ExternalInventoryBucket,
                "bucket_digest",
                bucket_id=f"external:bis:{index:02d}",
                source_family_ref="F10_EXPORT_CONTROL_AND_POLICY",
                coverage_obligation_ids=("Q7_EXPORT_CONTROL_CHINA",),
                external_route_ref=f"external-route:bis:{index:02d}",
                canonical_entity_id="US_BIS",
                entity_refs=("BIS", "US_BIS"),
                domain_allowlist=("www.bis.gov",),
                authority_refs=("authority:primary-read",),
                available_not_before="2026-01-01",
                available_not_after="2026-09-02",
                source_artifact_digest=EXTERNAL_ARTIFACT_DIGEST,
                eligible_object_count=1,
                foundation_required_family_match=True,
            )
        )
    return tuple(rows)


def _binding(kind: str, digest: str, count: int) -> CapabilityArtifactBinding:
    return _signed(
        CapabilityArtifactBinding,
        "binding_digest",
        capability_kind=kind,
        artifact_ref=f"artifact:{kind}:test",
        artifact_digest=digest,
        validated_object_count=count,
        validation_receipt_ref=f"receipt:{kind}:test",
        validation_receipt_digest=canonical_digest(
            {"capability_kind": kind, "validated_object_count": count}
        ),
    )


@pytest.fixture(scope="module")
def inventory() -> CapabilityInventorySnapshot:
    local_buckets = tuple(
        _local_bucket(row)
        for row in sorted(_physical_catalog()["local_routes"], key=lambda row: row["route_id"])
    )
    reviewed_index = _reviewed_index()
    s2_buckets = (_s2_bucket(),)
    external_buckets = _external_buckets()
    bindings = (
        _binding("external_source", EXTERNAL_ARTIFACT_DIGEST, 12),
        _binding("local_candidate", LOCAL_ARTIFACT_DIGEST, 890),
        _binding("reviewed_evidence", REVIEWED_PACK_DIGEST, 61),
        _binding("s2_numeric_fact", S2_ARTIFACT_DIGEST, 1_319),
    )
    return _signed(
        CapabilityInventorySnapshot,
        "inventory_snapshot_digest",
        contract_version="1.2",
        snapshot_id="inventory:dell:test:v1",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN-0.1.3",
        research_as_of="2026-09-02",
        foundation_digest=FOUNDATION_DIGEST,
        source_family_catalog=_source_family_catalog(),
        component_bindings=bindings,
        local_buckets=local_buckets,
        reviewed_evidence_index=reviewed_index,
        s2_buckets=s2_buckets,
        external_buckets=external_buckets,
        local_candidate_count=890,
        reviewed_evidence_count=61,
        s2_observation_count=1_319,
        external_object_count=12,
        answer_free=True,
    )


def _route(
    route_id: str,
    branch_id: str,
    route_kind: str,
    families: tuple[str, ...],
    authority: str,
    *,
    requirement: str = "optional",
) -> MinimumRouteObligation:
    return _signed(
        MinimumRouteObligation,
        "route_digest",
        route_obligation_id=route_id,
        coverage_obligation_id=branch_id,
        requirement=requirement,
        route_kind=route_kind,
        semantic_source_family_refs=families,
        entity_refs=(),
        period_intents=(),
        metric_refs=(),
        required_authority_refs=(authority,),
        substitution_policy="none",
        acceptable_replacement_route_kinds=(),
        replacement_conditions=(),
        answer_free=True,
    )


@pytest.fixture(scope="module")
def baseline(inventory: CapabilityInventorySnapshot):
    routes = [
        _route(
            f"route:{branch_id}:required-reviewed",
            branch_id,
            "reviewed_evidence",
            family_refs,
            "authority:reviewed-read",
            requirement="required",
        )
        for branch_id, family_refs in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE
    ]
    routes.extend(
        (
            _route(
                "route:Q2:F4:local",
                "Q2_DEMAND_QUALITY",
                "local_candidate",
                ("F4_CUSTOMER_CAPEX_DEPLOYMENT",),
                "authority:primary-read",
            ),
            _route(
                "route:Q3:F3:local",
                "Q3_UNITS_ASP_PVM",
                "local_candidate",
                ("F3_DELL_PRODUCT_SUPPORT",),
                "authority:primary-read",
            ),
            _route(
                "route:Q4:F3:local",
                "Q4_ARCHITECTURE_RAMP",
                "local_candidate",
                ("F3_DELL_PRODUCT_SUPPORT",),
                "authority:primary-read",
            ),
            _route(
                "route:Q6:F9:local",
                "Q6_MODEL_COMPUTE_DEMAND",
                "local_candidate",
                ("F9_MODEL_COMPUTE_AND_BENCHMARKS",),
                "authority:primary-read",
            ),
            _route(
                "route:Q7:F10:local",
                "Q7_EXPORT_CONTROL_CHINA",
                "local_candidate",
                ("F10_EXPORT_CONTROL_AND_POLICY",),
                "authority:primary-read",
            ),
            _route(
                "route:Q8:F6-F7:local",
                "Q8_COMPETITION_VALUE_POOL",
                "local_candidate",
                (
                    "F6_COMPUTE_PLATFORM_SUPPLIERS",
                    "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
                ),
                "authority:primary-read",
            ),
            _route(
                "route:Q7:F10:external",
                "Q7_EXPORT_CONTROL_CHINA",
                "external_source",
                ("F10_EXPORT_CONTROL_AND_POLICY",),
                "authority:primary-read",
            ),
        )
    )
    return build_host_owned_baseline_source_plan(
        authority_ref="authority:host-owned-baseline:test",
        source_plan_id="source-plan:dell:test:v1",
        inventory=inventory,
        route_obligations=tuple(routes),
        policy_digest=POLICY_DIGEST,
    )


def _local_intent(
    family_refs: tuple[str, ...],
    *,
    entities: tuple[str, ...] = (),
    periods: tuple[str, ...] = (),
    roles: tuple[str, ...] = (),
    surfaces: tuple[str, ...] = ("prose",),
) -> LocalEvidenceIntent:
    return LocalEvidenceIntent(
        intent_kind="local_evidence",
        query="Find the bounded local source set",
        purpose="Resolve one explicit answer-free local research scope.",
        entity_refs=entities,
        period_intents=periods,
        expected_information_gain="Determine whether the requested source family is locally reachable.",
        limit=6,
        semantic_source_family_refs=family_refs,
        source_role_intents=roles,
        content_surface_intents=surfaces,
    )


def _compile(
    intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent,
    *,
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
    route_id: str,
    branch_id: str,
    authorities: tuple[str, ...] = ("authority:primary-read",),
    expected_digest: str | None = None,
    maximum: int = 2_000,
    receipt_id: str = "compilation:test:001",
):
    return compile_source_intent(
        intent,
        inventory=inventory,
        baseline=baseline,
        minimum_route_obligation_id=route_id,
        branch_id=branch_id,
        task_authority_refs=authorities,
        expected_inventory_snapshot_digest=(
            expected_digest or inventory.inventory_snapshot_digest
        ),
        compilation_receipt_id=receipt_id,
        maximum_total_eligible_count=maximum,
    )


def _correction_codes(receipt: Any) -> set[str]:
    return {row.correction_code for row in receipt.corrections}


@pytest.mark.fast_contract
def test_physical_catalog_self_digest_and_frozen_counts_are_exact() -> None:
    payload = _physical_catalog()
    stated_digest = payload.pop("catalog_digest")

    assert canonical_digest(payload) == stated_digest
    assert payload["catalog_counts"] == {
        "local_route_count": 20,
        "external_route_count": 12,
        "total_route_count": 32,
        "local_physical_node_count": 1025,
        "local_searchable_leaf_count": 890,
        "reviewed_topic_count": 10,
        "entity_alias_record_count": 22,
    }
    assert sum(row["physical_node_count"] for row in payload["local_routes"]) == 1025
    assert sum(row["searchable_leaf_count"] for row in payload["local_routes"]) == 890
    assert 1025 - 890 == 135
    assert payload["input_bindings"]["reviewed_evidence_topic_inventory"][
        "composite_item_count"
    ] == 61


@pytest.mark.fast_contract
def test_inventory_snapshot_binds_current_component_counts_and_digests(
    inventory: CapabilityInventorySnapshot,
) -> None:
    assert inventory.local_candidate_count == 890
    assert inventory.reviewed_evidence_count == 61
    assert inventory.s2_observation_count == 1_319
    assert inventory.external_object_count == 12
    assert len(inventory.local_buckets) == 20
    assert len(inventory.external_buckets) == 12
    assert (
        sum(row.eligible_object_count for row in inventory.local_buckets) == 890
    )
    assert canonical_digest(
        inventory.model_dump(mode="json", exclude={"inventory_snapshot_digest"})
    ) == inventory.inventory_snapshot_digest


@pytest.mark.fast_contract
def test_strict_provider_union_rejects_physical_or_cross_lane_selectors() -> None:
    adapter = TypeAdapter(ProviderEvidenceIntent)
    common = {
        "query": "Locate bounded Dell source material",
        "purpose": "Exercise strict provider-visible evidence intent validation.",
        "entity_refs": [],
        "period_intents": [],
        "expected_information_gain": "Prove that physical selectors remain host-owned.",
        "limit": 8,
    }

    with pytest.raises(ValidationError, match="extra_forbidden"):
        adapter.validate_python(
            {
                **common,
                "intent_kind": "local_evidence",
                "semantic_source_family_refs": ["F2_DELL_IR_EARNINGS"],
                "source_role_intents": [],
                "content_surface_intents": ["prose"],
                "route_ids": ["dell_fy2027_q2_sec_exhibit_99_1"],
            }
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        adapter.validate_python(
            {
                **common,
                "intent_kind": "reviewed_evidence",
                "topic_refs": ["operating_performance"],
                "evidence_role_refs": [],
                "minimum_authority_tier": "reviewed",
                "issuer_ids": ["DELL"],
            }
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        adapter.validate_python(
            {
                **common,
                "intent_kind": "external_source",
                "semantic_source_family_refs": ["F10_EXPORT_CONTROL_AND_POLICY"],
                "domain_allowlist": ["www.bis.gov"],
                "source_roles": ["regulator_primary"],
            }
        )


@pytest.mark.fast_contract
def test_tampered_digest_and_component_count_are_rejected(
    inventory: CapabilityInventorySnapshot,
) -> None:
    catalog_payload = inventory.source_family_catalog.model_dump(mode="python")
    catalog_payload["catalog_digest"] = ZERO
    with pytest.raises(ValidationError, match="source_family_catalog_digest_mismatch"):
        SourceFamilyCatalog.model_validate(catalog_payload)

    snapshot_payload = _model_values(inventory, "inventory_snapshot_digest")
    bindings = list(inventory.component_bindings)
    local = next(row for row in bindings if row.capability_kind == "local_candidate")
    bindings[bindings.index(local)] = _binding(
        "local_candidate", LOCAL_ARTIFACT_DIGEST, 889
    )
    snapshot_payload["component_bindings"] = tuple(bindings)
    with pytest.raises(ValidationError, match="component_count_mismatch"):
        _signed(
            CapabilityInventorySnapshot,
            "inventory_snapshot_digest",
            **snapshot_payload,
        )


@pytest.mark.fast_contract
def test_host_owned_baseline_rejects_fake_same_family_for_every_branch(
    inventory: CapabilityInventorySnapshot,
) -> None:
    fake_routes = tuple(
        _route(
            f"route:{branch_id}:fake",
            branch_id,
            "reviewed_evidence",
            ("F1_SEC_ISSUER_FACTS",),
            "authority:reviewed-read",
            requirement="required",
        )
        for branch_id in DELL_COVERAGE_OBLIGATION_IDS
    )
    with pytest.raises(
        SourceFamilyCompilerError,
        match="baseline_required_source_family_mismatch",
    ):
        build_host_owned_baseline_source_plan(
            authority_ref="authority:host-owned-baseline:fake",
            source_plan_id="source-plan:dell:fake",
            inventory=inventory,
            route_obligations=fake_routes,
            policy_digest=POLICY_DIGEST,
        )


@pytest.mark.fast_contract
def test_stale_inventory_and_baseline_bindings_never_authorize_a_tool_call(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    intent = _local_intent(("F9_MODEL_COMPUTE_AND_BENCHMARKS",))
    stale_request = _compile(
        intent,
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q6:F9:local",
        branch_id="Q6_MODEL_COMPUTE_DEMAND",
        expected_digest="9" * 64,
    )
    assert stale_request.disposition == "rejected"
    assert stale_request.tool_call_authorized is False
    assert _correction_codes(stale_request) == {"inventory_snapshot_stale"}

    successor_payload = _model_values(inventory, "inventory_snapshot_digest")
    successor_payload["snapshot_id"] = "inventory:dell:test:v2"
    successor = _signed(
        CapabilityInventorySnapshot,
        "inventory_snapshot_digest",
        **successor_payload,
    )
    stale_baseline = _compile(
        intent,
        inventory=successor,
        baseline=baseline,
        route_id="route:Q6:F9:local",
        branch_id="Q6_MODEL_COMPUTE_DEMAND",
    )
    assert stale_baseline.tool_call_authorized is False
    assert _correction_codes(stale_baseline) == {"baseline_source_plan_stale"}

    with pytest.raises(
        SourceFamilyCompilerError, match="host_baseline_foundation_digest_stale"
    ):
        validate_host_owned_baseline_source_plan(
            baseline,
            current_inventory=inventory,
            expected_foundation_digest="8" * 64,
        )


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("branch_id", "route_id", "family", "expected_count"),
    (
        (
            "Q6_MODEL_COMPUTE_DEMAND",
            "route:Q6:F9:local",
            "F9_MODEL_COMPUTE_AND_BENCHMARKS",
            19,
        ),
        (
            "Q7_EXPORT_CONTROL_CHINA",
            "route:Q7:F10:local",
            "F10_EXPORT_CONTROL_AND_POLICY",
            1,
        ),
    ),
)
def test_family_bounded_f9_and_f10_allow_empty_entity_intent(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
    branch_id: str,
    route_id: str,
    family: str,
    expected_count: int,
) -> None:
    receipt = _compile(
        _local_intent((family,)),
        inventory=inventory,
        baseline=baseline,
        route_id=route_id,
        branch_id=branch_id,
    )

    assert receipt.disposition == "accepted"
    assert receipt.tool_call_authorized is True
    assert receipt.eligible_object_count == expected_count
    assert {row.source_family_ref for row in receipt.local_scopes} == {family}
    assert {row.query for row in receipt.local_scopes} == {
        "Find the bounded local source set"
    }
    assert {row.search_limit for row in receipt.local_scopes} == {6}


@pytest.mark.fast_contract
def test_f4_partial_entity_coverage_is_retained_with_explicit_residual(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    receipt = _compile(
        _local_intent(
            ("F4_CUSTOMER_CAPEX_DEPLOYMENT",),
            entities=("AMAZON", "GOOGL", "META", "MICROSOFT"),
        ),
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q2:F4:local",
        branch_id="Q2_DEMAND_QUALITY",
    )

    assert receipt.disposition == "accepted_with_residual_feedback"
    assert receipt.tool_call_authorized is True
    assert {scope.issuer_ids[0] for scope in receipt.local_scopes} == {
        "AMAZON",
        "META",
        "MICROSOFT",
    }
    residual = next(
        row for row in receipt.corrections if row.correction_code == "local_entity_residual"
    )
    assert residual.entity_refs == ("GOOGL",)


@pytest.mark.fast_contract
def test_q8_multi_family_intent_compiles_to_separate_cooccurring_scopes(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    receipt = _compile(
        _local_intent(
            (
                "F6_COMPUTE_PLATFORM_SUPPLIERS",
                "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
            ),
            entities=("MICRON", "NVIDIA"),
        ),
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q8:F6-F7:local",
        branch_id="Q8_COMPETITION_VALUE_POOL",
    )

    assert receipt.disposition == "accepted"
    assert receipt.eligible_object_count == 48
    assert {scope.source_family_ref for scope in receipt.local_scopes} == {
        "F6_COMPUTE_PLATFORM_SUPPLIERS",
        "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
    }
    assert all(len(scope.issuer_ids) == 1 for scope in receipt.local_scopes)
    assert all(len(scope.route_ids) == 1 for scope in receipt.local_scopes)
    assert all(
        scope.matched_entity_refs in {("MICRON",), ("NVIDIA",)}
        for scope in receipt.local_scopes
    )


@pytest.mark.fast_contract
def test_q3_f3_current_branch_gap_is_a_correction_without_mcp_authority(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    receipt = _compile(
        _local_intent(("F3_DELL_PRODUCT_SUPPORT",), entities=("DELL",)),
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q3:F3:local",
        branch_id="Q3_UNITS_ASP_PVM",
    )

    assert receipt.disposition == "rejected"
    assert receipt.tool_call_authorized is False
    assert receipt.local_scopes == ()
    assert _correction_codes(receipt) == {"local_entity_scope_zero"}


@pytest.mark.fast_contract
def test_semantic_source_role_compiles_but_physical_role_is_not_a_semantic_alias(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    semantic = _compile(
        _local_intent(
            ("F9_MODEL_COMPUTE_AND_BENCHMARKS",),
            roles=("workload_and_benchmark_context",),
        ),
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q6:F9:local",
        branch_id="Q6_MODEL_COMPUTE_DEMAND",
    )
    physical = _compile(
        _local_intent(
            ("F9_MODEL_COMPUTE_AND_BENCHMARKS",),
            roles=("model_provider_primary",),
        ),
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q6:F9:local",
        branch_id="Q6_MODEL_COMPUTE_DEMAND",
    )

    assert semantic.disposition == "accepted"
    assert semantic.tool_call_authorized is True
    assert physical.disposition == "rejected"
    assert physical.tool_call_authorized is False
    assert _correction_codes(physical) == {"local_source_role_scope_zero"}


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("case", "expected_code"),
    (
        ("wrong_branch", "source_family_branch_mismatch"),
        ("wrong_family", "minimum_route_source_family_mismatch"),
        ("wrong_period", "local_period_scope_zero"),
        ("wrong_role", "local_source_role_scope_zero"),
        ("wrong_surface", "local_content_surface_scope_zero"),
        ("wrong_lane", "source_lane_mismatch"),
        ("wrong_authority", "task_authority_insufficient"),
        ("overwide", "local_total_cardinality_exceeded"),
    ),
)
def test_invalid_branch_family_period_role_lane_authority_or_width_is_typed(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
    case: str,
    expected_code: str,
) -> None:
    route_id = "route:Q6:F9:local"
    branch_id = "Q6_MODEL_COMPUTE_DEMAND"
    intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent
    intent = _local_intent(("F9_MODEL_COMPUTE_AND_BENCHMARKS",))
    authorities = ("authority:primary-read",)
    maximum = 2_000

    if case == "wrong_branch":
        branch_id = "Q7_EXPORT_CONTROL_CHINA"
    elif case == "wrong_family":
        intent = _local_intent(("F10_EXPORT_CONTROL_AND_POLICY",))
    elif case == "wrong_period":
        intent = _local_intent(
            ("F9_MODEL_COMPUTE_AND_BENCHMARKS",), periods=("FY2099",)
        )
    elif case == "wrong_role":
        intent = _local_intent(
            ("F9_MODEL_COMPUTE_AND_BENCHMARKS",),
            roles=("issuer_management_disclosure",),
        )
    elif case == "wrong_surface":
        intent = _local_intent(
            ("F9_MODEL_COMPUTE_AND_BENCHMARKS",), surfaces=("table",)
        )
    elif case == "wrong_lane":
        intent = ExternalSourceIntent(
            intent_kind="external_source",
            query="Locate external model-compute material",
            purpose="Exercise strict separation between local and external lanes.",
            entity_refs=(),
            period_intents=(),
            expected_information_gain="Prove that cross-lane requests fail before any tool call.",
            limit=8,
            semantic_source_family_refs=("F9_MODEL_COMPUTE_AND_BENCHMARKS",),
            domain_allowlist=(),
        )
    elif case == "wrong_authority":
        authorities = ("authority:reviewed-read",)
    elif case == "overwide":
        maximum = 18

    receipt = _compile(
        intent,
        inventory=inventory,
        baseline=baseline,
        route_id=route_id,
        branch_id=branch_id,
        authorities=authorities,
        maximum=maximum,
    )
    assert receipt.disposition == "rejected"
    assert receipt.tool_call_authorized is False
    assert _correction_codes(receipt) == {expected_code}


@pytest.mark.fast_contract
def test_pure_external_intent_compiles_without_local_selectors(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    intent = ExternalSourceIntent(
        intent_kind="external_source",
        query="Find the current official export-control publications",
        purpose="Compile a pure external route without leaking local physical selectors.",
        entity_refs=("US_BIS",),
        period_intents=(),
        expected_information_gain="Confirm the bounded official-policy discovery surface.",
        limit=8,
        semantic_source_family_refs=("F10_EXPORT_CONTROL_AND_POLICY",),
        domain_allowlist=("www.bis.gov",),
        published_not_before="2026-01-01",
        published_not_after="2026-09-02",
    )
    receipt = _compile(
        intent,
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q7:F10:external",
        branch_id="Q7_EXPORT_CONTROL_CHINA",
    )

    assert receipt.disposition == "accepted"
    assert receipt.local_scopes == ()
    assert receipt.reviewed_targets == ()
    assert len(receipt.external_targets) == 12
    assert receipt.eligible_object_count == 12
    assert all(target.domain_allowlist == ("www.bis.gov",) for target in receipt.external_targets)


@pytest.mark.fast_contract
def test_external_entity_mismatch_rejects_before_any_tool_call(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    intent = ExternalSourceIntent(
        intent_kind="external_source",
        query="Find the current official export-control publications",
        purpose="Prove that an unrelated requested entity cannot inherit a policy route.",
        entity_refs=("DELL",),
        period_intents=(),
        expected_information_gain="Reject an external route whose configured entity does not match.",
        limit=8,
        semantic_source_family_refs=("F10_EXPORT_CONTROL_AND_POLICY",),
        domain_allowlist=("www.bis.gov",),
    )
    receipt = _compile(
        intent,
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q7:F10:external",
        branch_id="Q7_EXPORT_CONTROL_CHINA",
    )

    assert receipt.disposition == "rejected"
    assert receipt.tool_call_authorized is False
    assert receipt.external_targets == ()
    assert _correction_codes(receipt) == {"external_source_family_scope_zero"}


@pytest.mark.fast_contract
def test_external_unknown_fiscal_period_remains_explicit_capture_time_residual(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    intent = ExternalSourceIntent(
        intent_kind="external_source",
        query="Find the current official export-control publications",
        purpose="Keep fiscal-period intent unresolved when route metadata only has publication dates.",
        entity_refs=("US_BIS",),
        period_intents=("FY2027_Q2",),
        expected_information_gain="Retain a bounded candidate without pretending publication date proves fiscal scope.",
        limit=8,
        semantic_source_family_refs=("F10_EXPORT_CONTROL_AND_POLICY",),
        domain_allowlist=("www.bis.gov",),
    )
    receipt = _compile(
        intent,
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q7:F10:external",
        branch_id="Q7_EXPORT_CONTROL_CHINA",
    )

    assert receipt.disposition == "accepted_with_residual_feedback"
    assert receipt.tool_call_authorized is True
    residual = next(
        row for row in receipt.corrections if row.correction_code == "external_route_residual"
    )
    assert residual.period_intents == ("FY2027_Q2",)


def _reviewed_intent() -> ReviewedEvidenceIntent:
    return ReviewedEvidenceIntent(
        intent_kind="reviewed_evidence",
        query="Find reviewed Dell operating-performance evidence",
        purpose="Compile and then exactly post-filter comparable reviewed evidence.",
        entity_refs=("DELL",),
        period_intents=("FY2027_Q2",),
        expected_information_gain="Confirm that indexed candidates survive exact metadata and reread checks.",
        limit=8,
        topic_refs=("operating_performance",),
        evidence_role_refs=("issuer_management_disclosure",),
        minimum_authority_tier="reviewed",
    )


@pytest.mark.fast_contract
def test_topic_relevant_supplemental_row_cannot_close_a_minimum_route(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    intent = ReviewedEvidenceIntent(
        intent_kind="reviewed_evidence",
        query="Find a topic-relevant supplemental item",
        purpose="Prove that selector relevance alone cannot close a source-family obligation.",
        entity_refs=("DELL",),
        period_intents=("FY2027_Q2",),
        expected_information_gain="Keep supplemental recall distinct from minimum-route satisfaction.",
        limit=6,
        topic_refs=("supplemental_only",),
        evidence_role_refs=("issuer_management_disclosure",),
        minimum_authority_tier="reviewed",
    )
    receipt = _compile(
        intent,
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q1_ISSUER_TRUTH:required-reviewed",
        branch_id="Q1_ISSUER_TRUTH",
        authorities=("authority:reviewed-read",),
    )

    assert receipt.disposition == "rejected"
    assert receipt.tool_call_authorized is False
    assert _correction_codes(receipt) == {"reviewed_exact_metadata_scope_zero"}


@pytest.mark.fast_contract
def test_reviewed_hits_require_exact_postfilter_and_integrity_reread(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    compilation = _compile(
        _reviewed_intent(),
        inventory=inventory,
        baseline=baseline,
        route_id="route:Q1_ISSUER_TRUTH:required-reviewed",
        branch_id="Q1_ISSUER_TRUTH",
        authorities=("authority:reviewed-read",),
    )
    assert compilation.disposition == "accepted_with_residual_feedback"
    assert len(compilation.reviewed_targets) == 1
    target = compilation.reviewed_targets[0]
    index = inventory.reviewed_evidence_index
    by_id = {row.evidence_id: row for row in index.rows}

    def reread(row: ReviewedEvidenceIndexRowV1_2, *, digest: str | None = None):
        return _signed(
            ReviewedEvidenceRereadMetadata,
            "reread_digest",
            evidence_id=row.evidence_id,
            item_digest=digest or row.item_digest,
            locator_digest=row.locator_digest,
            authority_tier=row.authority_tier,
            source_reporting_period_end=row.source_reporting_period_end,
            reviewed_index_digest=index.index_digest,
        )

    receipt = filter_reviewed_evidence_hits(
        compiled_target=target,
        reviewed_index=index,
        search_hit_ids=(
            "evidence:000",
            "evidence:001",
            "evidence:002",
            "evidence:003",
            "evidence:004",
            "evidence:999",
        ),
        reread_metadata=(
            reread(by_id["evidence:000"]),
            reread(by_id["evidence:001"], digest="9" * 64),
        ),
        expected_index_digest=index.index_digest,
        filter_receipt_id="reviewed-filter:test:001",
    )

    assert receipt.accepted_evidence_ids == ("evidence:000",)
    assert receipt.strict_route_satisfied is True
    assert {row.evidence_id: row.reason for row in receipt.rejections} == {
        "evidence:001": "reread_digest_mismatch",
        "evidence:002": "topic_mismatch",
        "evidence:003": "metadata_insufficient",
        "evidence:004": "family_or_branch_mismatch",
        "evidence:999": "not_indexed",
    }

    drift_only = filter_reviewed_evidence_hits(
        compiled_target=target,
        reviewed_index=index,
        search_hit_ids=("evidence:001",),
        reread_metadata=(
            reread(by_id["evidence:001"], digest="9" * 64),
        ),
        expected_index_digest=index.index_digest,
        filter_receipt_id="reviewed-filter:test:002",
    )
    assert drift_only.accepted_evidence_ids == ()
    assert drift_only.strict_route_satisfied is False

    with pytest.raises(SourceFamilyCompilerError, match="reviewed_filter_index_digest_stale"):
        filter_reviewed_evidence_hits(
            compiled_target=target,
            reviewed_index=index,
            search_hit_ids=(),
            reread_metadata=(),
            expected_index_digest="8" * 64,
            filter_receipt_id="reviewed-filter:test:stale",
        )


@pytest.mark.fast_contract
def test_compiler_facade_is_deterministic_for_same_bound_inputs(
    inventory: CapabilityInventorySnapshot,
    baseline: Any,
) -> None:
    compiler = SourceFamilyCompiler(inventory=inventory, baseline=baseline)
    kwargs = {
        "minimum_route_obligation_id": "route:Q6:F9:local",
        "branch_id": "Q6_MODEL_COMPUTE_DEMAND",
        "task_authority_refs": ("authority:primary-read",),
        "expected_inventory_snapshot_digest": inventory.inventory_snapshot_digest,
        "compilation_receipt_id": "compilation:test:deterministic",
    }
    first = compiler.compile(
        _local_intent(("F9_MODEL_COMPUTE_AND_BENCHMARKS",)), **kwargs
    )
    second = compiler.compile(
        _local_intent(("F9_MODEL_COMPUTE_AND_BENCHMARKS",)), **kwargs
    )

    assert compiler.inventory_snapshot_digest == inventory.inventory_snapshot_digest
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.receipt_digest == second.receipt_digest
