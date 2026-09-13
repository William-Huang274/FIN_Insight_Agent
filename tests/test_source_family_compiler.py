from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import TypeAdapter, ValidationError

from sec_agent.agent_runtime.research_contracts import (
    COVERAGE_OBLIGATION_IDS,
    ExternalSourceIntent,
    LocalEvidenceIntent,
    MinimumRouteObligation,
    ProviderEvidenceIntent,
    ReviewedEvidenceIntent,
    canonical_digest,
    payload_without,
)
from sec_agent.agent_runtime.source_family_compiler import (
    CapabilityArtifactBinding,
    CapabilityInventorySnapshot,
    REQUIRED_SOURCE_FAMILIES_BY_COVERAGE,
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


def _source_family_catalog() -> SourceFamilyCatalog:
    memberships: dict[str, set[str]] = {}
    for coverage_id, family_refs in REQUIRED_SOURCE_FAMILIES_BY_COVERAGE:
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


def _correction_codes(receipt: Any) -> set[str]:
    return {row.correction_code for row in receipt.corrections}


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
