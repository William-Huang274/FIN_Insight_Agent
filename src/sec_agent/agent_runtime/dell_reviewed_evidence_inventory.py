"""Thin, answer-free Reviewed Evidence inventory and approved runtime view.

This adapter validates the exact 55-item base pack, 6-item case overlay and
current physical catalog, then emits metadata-only audit rows.  A separately
pinned Owner decision can project exactly 56 non-ambiguous rows into a transient
runtime view without modifying or promoting either source artifact.  It does
not infer provenance from narrative content or retrieval prompts.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, Mapping
from urllib.parse import urlparse

from pydantic import Field, model_validator

from sec_agent.agent_runtime.dell_agentic_contracts import canonical_digest
from sec_agent.agent_runtime.dell_source_family_compiler import (
    DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE,
    ReviewedEvidenceIndexV1_2,
    ReviewedEvidenceIndexRowV1_2,
)
from sec_agent.agent_runtime.dell_owner_data_gate import (
    DellOwnerDataGateDecision,
    DellOwnerDataGateError,
    load_dell_owner_data_gate_decision,
    validate_trusted_dell_owner_data_gate_decision,
)
from sec_agent.canonical_runtime.contracts_v1_2 import StrictFrozenModel
from sec_agent.research_foundation.data_ports import reviewed_evidence_id
from sec_agent.research.reviewed_evidence_pack import (
    ReviewedEvidencePackError,
    validate_reviewed_evidence_pack,
)


Digest = str
MappingState = Literal[
    "mechanical_metadata_mapping",
    "f12_independent_source_rule_candidate_owner_review_required",
    "item_level_family_ambiguity_owner_review_required",
]
RouteRelation = Literal["minimum_route_eligible", "supplemental_only", "unresolved"]
EntityResolutionState = Literal[
    "resolved_alias_and_domain",
    "unresolved_alias_domain_conflict_owner_review_required",
]
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs/research/fin_ia_0_1_3_dell_reviewed_evidence_enrichment_v1_0.json"
DEFAULT_BASE_PACK_PATH = _REPO_ROOT / "data/workbench_private/fin_0_1_3_s1_dell_direct_source_evidence/r4/successor/pack.json"
DEFAULT_OVERLAY_PATH = Path(
    "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/evidence_overlay/"
    "attempts/20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01/"
    "reviewed-evidence-case-projection.json"
)
DEFAULT_PHYSICAL_CATALOG_PATH = _REPO_ROOT / "configs/research/fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json"
# These are trust anchors compiled into the loader, not values learned from the
# candidate being loaded.  They are updated only when the checked-in candidate
# is deliberately re-issued.
DEFAULT_EXPECTED_CONFIG_SHA256 = "1604eea6e7b7b832b081c86c3a97a54abf96b706c49dee5b7cccd6fc6768960a"
DEFAULT_EXPECTED_ENRICHMENT_DIGEST = "365a65744a58d03092dd16aedffcc0e78df9a20a8ed63c546529afa1a04e78e3"

_EXPECTED_STATES = {
    "mechanical_metadata_mapping": 43,
    "f12_independent_source_rule_candidate_owner_review_required": 13,
    "item_level_family_ambiguity_owner_review_required": 5,
}
_FAMILY_AUTHORITY = {
    "F1_SEC_ISSUER_FACTS": "issuer_numeric_and_filing_identity",
    "F2_DELL_IR_EARNINGS": "issuer_narrative_and_company_defined_metrics",
    "F3_DELL_PRODUCT_SUPPORT": "product_configuration_and_integration_state",
    "F4_CUSTOMER_CAPEX_DEPLOYMENT": "industry_demand_context_or_named_customer_relationship",
    "F5_PUBLIC_PROCUREMENT": "transaction_observation_not_company_total",
    "F6_COMPUTE_PLATFORM_SUPPLIERS": "platform_and_supplier_state",
    "F7_MEMORY_FOUNDRY_NETWORK_STORAGE": "supplier_reported_direction_and_capacity_state",
    "F12_INDEPENDENT_COUNTEREVIDENCE": "candidate_or_independent_context_not_numeric_authority",
}
_EXPECTED_F12_DOMAINS = (
    "fortune.com",
    "www.idc.com",
    "www.nextplatform.com",
    "www.trendforce.com",
)
_ANSWER_LIKE_KEYS = {
    "answer",
    "claim",
    "claim_text",
    "expected_answer",
    "numeric_value",
    "query",
    "retrieval_query",
    "reviewed_source_excerpt",
    "source_text",
}
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "status",
    "recorded_at",
    "case_id",
    "case_key",
    "research_as_of",
    "purpose",
    "authority",
    "digest_contract",
    "input_bindings",
    "classification_contract",
    "expected_counts",
    "item_enrichments",
    "enrichment_digest",
}
_AUTHORITY_FIELDS = {
    "answer_free",
    "owner_review_required",
    "owner_review_receipt",
    "execution_authority",
    "executable_reviewed_evidence_index_authorized",
    "model_or_provider_calls_authorized",
    "network_calls_authorized",
    "evidence_admission_authority",
    "numeric_fact_authority",
    "research_answer_fields_forbidden",
    "text_or_query_inference_forbidden",
    "physical_catalog_candidate_cannot_self_authorize",
}
_CLASSIFICATION_FIELDS = {
    "key_field",
    "metadata_only_fields",
    "forbidden_inference_inputs",
    "mechanical_rule_basis",
    "f12_rule_candidate_domains",
    "ambiguous_item_digests",
    "topic_branch_mapping_source",
    "topic_mapping_is_selector_only",
    "route_relation_does_not_prove_claim_relevance",
    "entity_alias_registry_source",
    "entity_aliases_are_reviewed_selector_refs",
    "canonical_domain_match_required",
    "owner_review_domain_conflicts",
}
_DOMAIN_CONFLICT_FIELDS = {
    "evidence_item_digest",
    "raw_evidence_owner_id",
    "canonical_evidence_owner_id",
    "observed_domain",
    "approved_canonical_domains",
    "state",
    "execution_authority",
}
_ENTRY_FIELDS = {
    "origin",
    "source_material_ref",
    "source_record_id",
    "target_id",
    "evidence_owner_id",
    "research_subject_ids",
    "topic_refs",
    "coverage_obligation_ids",
    "period_refs",
    "provenance_mapping_state",
    "source_family_ref",
    "candidate_source_family_refs",
    "route_relation",
    "proposed_minimum_route_eligible_branch_ids",
    "authority_tier_candidate",
    "authority_scope_refs",
}


class ReviewedEvidenceEnrichmentError(ValueError):
    """Fail-closed error at the enrichment boundary."""


class ReviewedEvidenceAuditRow(StrictFrozenModel):
    evidence_item_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    origin: Literal["base", "overlay"]
    source_material_ref: str
    source_record_id: str
    target_id: str
    evidence_owner_id: str
    canonical_evidence_owner_id: str
    research_subject_ids: tuple[str, ...]
    entity_ids: tuple[str, ...]
    entity_alias_refs: tuple[str, ...]
    canonical_domain_refs: tuple[str, ...]
    entity_resolution_state: EntityResolutionState
    source_type: str
    source_tier: str
    source_domain: str
    publication_date: str
    source_reporting_period_end: str | None
    period_refs: tuple[str, ...]
    source_evidence_role: str
    disposition: str
    causal_attribution_authorized: bool
    writer_citable: bool
    numeric_use_boundary: str
    relationship_directions: tuple[str, ...]
    topic_refs: tuple[str, ...]
    coverage_obligation_ids: tuple[str, ...]
    provenance_mapping_state: MappingState
    source_family_ref: str | None
    candidate_source_family_refs: tuple[str, ...]
    route_relation: RouteRelation
    proposed_minimum_route_eligible_branch_ids: tuple[str, ...]
    authority_tier_candidate: Literal["reviewed", "primary"] | None
    authority_scope_refs: tuple[str, ...]
    locator: str
    row_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_digest(self) -> "ReviewedEvidenceAuditRow":
        body = self.model_dump(mode="python", exclude={"row_digest"})
        if canonical_digest(body) != self.row_digest:
            raise ValueError("reviewed_evidence_audit_row_digest_mismatch")
        return self


class ReviewedEvidenceAuditProjection(StrictFrozenModel):
    schema_version: Literal["fin_ia_dell_reviewed_evidence_enrichment_audit_projection_v1_0"]
    case_key: Literal["DELL"]
    research_as_of: str
    enrichment_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    base_pack_payload_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    overlay_projection_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    composite_identity_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    legacy_active_projection_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    physical_catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    rows: tuple[ReviewedEvidenceAuditRow, ...]
    item_count: Literal[61] = 61
    mechanical_mapping_count: Literal[43] = 43
    f12_rule_candidate_count: Literal[13] = 13
    item_level_ambiguity_count: Literal[5] = 5
    entity_domain_conflict_count: Literal[1] = 1
    answer_free: Literal[True] = True
    owner_review_required: Literal[True] = True
    execution_authority: Literal[False] = False
    executable_reviewed_evidence_index_authorized: Literal[False] = False
    projection_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_projection(self) -> "ReviewedEvidenceAuditProjection":
        body = self.model_dump(mode="python", exclude={"projection_digest"})
        if canonical_digest(body) != self.projection_digest:
            raise ValueError("reviewed_evidence_audit_projection_digest_mismatch")
        if len(self.rows) != 61 or len({row.evidence_item_digest for row in self.rows}) != 61:
            raise ValueError("reviewed_evidence_audit_projection_identity_mismatch")
        return self


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewedEvidenceEnrichmentError(f"{label}_unreadable") from exc
    if not isinstance(value, dict):
        raise ReviewedEvidenceEnrichmentError(f"{label}_must_be_object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_file(path: Path, expected: Any, label: str) -> None:
    if not path.is_file():
        raise ReviewedEvidenceEnrichmentError(f"{label}_missing")
    if not isinstance(expected, str) or _sha256_file(path) != expected:
        raise ReviewedEvidenceEnrichmentError(f"{label}_sha256_mismatch")


def _verify_self_digest(payload: Mapping[str, Any], field: str, label: str) -> str:
    body = dict(payload)
    claimed = body.pop(field, None)
    if not isinstance(claimed, str) or canonical_digest(body) != claimed:
        raise ReviewedEvidenceEnrichmentError(f"{label}_{field}_mismatch")
    return claimed


def _require_exact_keys(value: Any, expected: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReviewedEvidenceEnrichmentError(f"{label}_closed_schema_mismatch")
    return value


def _reject_answer_like_fields(value: Any, label: str = "reviewed_enrichment_config") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ReviewedEvidenceEnrichmentError(f"{label}_non_string_key")
            if key.casefold() in _ANSWER_LIKE_KEYS:
                raise ReviewedEvidenceEnrichmentError(f"{label}_answer_like_field_forbidden")
            _reject_answer_like_fields(child, label)
    elif isinstance(value, list):
        for child in value:
            _reject_answer_like_fields(child, label)


def _as_sorted_strings(value: Any, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ReviewedEvidenceEnrichmentError(f"{label}_invalid")
    result = tuple(value)
    if result != tuple(sorted(set(result))) or (not allow_empty and not result):
        raise ReviewedEvidenceEnrichmentError(f"{label}_not_sorted_unique")
    return result


def _iso_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise ReviewedEvidenceEnrichmentError(f"{label}_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReviewedEvidenceEnrichmentError(f"{label}_invalid") from exc


def _validate_candidate(
    raw: dict[str, Any],
    expected_enrichment_digest: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Mapping[str, Any]]]:
    _reject_answer_like_fields(raw)
    _require_exact_keys(raw, _TOP_LEVEL_FIELDS, "reviewed_enrichment_config")
    claimed_digest = _verify_self_digest(raw, "enrichment_digest", "reviewed_enrichment_config")
    if claimed_digest != expected_enrichment_digest:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_config_untrusted_digest")
    if not (
        raw.get("schema_version") == "fin_ia_dell_reviewed_evidence_enrichment_v1_0"
        and raw.get("status") == "owner_review_candidate_answer_free_not_execution_authority"
        and raw.get("case_id") == "DELL_AI_INFRA_REFERENCE_VERTICAL"
        and raw.get("case_key") == "DELL"
        and raw.get("research_as_of") == "2026-09-02"
        and isinstance(raw.get("recorded_at"), str)
        and isinstance(raw.get("purpose"), str)
        and bool(raw["purpose"])
    ):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_config_identity_invalid")

    authority = _require_exact_keys(
        raw.get("authority"), _AUTHORITY_FIELDS, "reviewed_enrichment_authority"
    )
    if authority != {
        "answer_free": True,
        "owner_review_required": True,
        "owner_review_receipt": None,
        "execution_authority": False,
        "executable_reviewed_evidence_index_authorized": False,
        "model_or_provider_calls_authorized": False,
        "network_calls_authorized": False,
        "evidence_admission_authority": False,
        "numeric_fact_authority": False,
        "research_answer_fields_forbidden": True,
        "text_or_query_inference_forbidden": True,
        "physical_catalog_candidate_cannot_self_authorize": True,
    }:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_authority_invalid")

    digest_contract = _require_exact_keys(
        raw.get("digest_contract"),
        {
            "algorithm",
            "canonicalization",
            "self_digest_field",
            "self_digest_field_excluded_from_digest",
        },
        "reviewed_enrichment_digest_contract",
    )
    if digest_contract != {
        "algorithm": "sha256",
        "canonicalization": "utf8_json_ensure_ascii_false_sort_keys_true_separators_comma_colon",
        "self_digest_field": "enrichment_digest",
        "self_digest_field_excluded_from_digest": True,
    }:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_digest_contract_invalid")

    bindings = _require_exact_keys(
        raw.get("input_bindings"),
        {"base_pack", "overlay_projection", "composite", "physical_catalog"},
        "reviewed_enrichment_input_bindings",
    )
    _require_exact_keys(
        bindings.get("base_pack"),
        {"ref", "sha256", "payload_digest", "expected_item_count"},
        "reviewed_enrichment_base_binding",
    )
    _require_exact_keys(
        bindings.get("overlay_projection"),
        {"ref", "sha256", "projection_digest", "expected_item_count"},
        "reviewed_enrichment_overlay_binding",
    )
    _require_exact_keys(
        bindings.get("composite"),
        {
            "digest_basis",
            "composite_digest",
            "legacy_active_projection_digest",
            "expected_item_count",
        },
        "reviewed_enrichment_composite_binding",
    )
    _require_exact_keys(
        bindings.get("physical_catalog"),
        {"ref", "sha256", "catalog_digest", "required_status", "execution_authority"},
        "reviewed_enrichment_catalog_binding",
    )

    counts = _require_exact_keys(
        raw.get("expected_counts"),
        {
            "composite_item_count",
            "mechanical_mapping_count",
            "f12_rule_candidate_count",
            "item_level_ambiguity_count",
            "entity_domain_conflict_count",
        },
        "reviewed_enrichment_expected_counts",
    )
    if counts != {
        "composite_item_count": 61,
        "mechanical_mapping_count": 43,
        "f12_rule_candidate_count": 13,
        "item_level_ambiguity_count": 5,
        "entity_domain_conflict_count": 1,
    }:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_expected_counts_invalid")

    classification = _require_exact_keys(
        raw.get("classification_contract"),
        _CLASSIFICATION_FIELDS,
        "reviewed_enrichment_classification",
    )
    if not (
        classification.get("key_field") == "evidence_item_digest"
        and classification.get("metadata_only_fields")
        == [
            "evidence_owner_id",
            "source_type",
            "source_tier",
            "source_material_ref",
            "source_record_id",
            "target_id",
            "topic_refs",
            "relationship_directions",
            "publication_date",
            "source_reporting_period_end",
        ]
        and classification.get("forbidden_inference_inputs")
        == [
            "claim_or_source_text",
            "retrieval_query",
            "expected_answer",
            "numeric_value",
        ]
        and classification.get("mechanical_rule_basis")
        == "explicit owner/source-type allowlist"
        and classification.get("topic_branch_mapping_source")
        == "physical_catalog.reviewed_topic_branch_mapping"
        and classification.get("topic_mapping_is_selector_only") is True
        and classification.get("route_relation_does_not_prove_claim_relevance") is True
        and classification.get("entity_alias_registry_source")
        == "physical_catalog.entity_aliases"
        and classification.get("entity_aliases_are_reviewed_selector_refs") is True
        and classification.get("canonical_domain_match_required") is True
    ):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_classification_invalid")
    f12_domains = _as_sorted_strings(
        classification.get("f12_rule_candidate_domains"),
        "reviewed_enrichment_f12_domains",
    )
    if f12_domains != _EXPECTED_F12_DOMAINS:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_f12_domain_registry_mismatch")
    ambiguous = _as_sorted_strings(
        classification.get("ambiguous_item_digests"),
        "reviewed_enrichment_ambiguous_digests",
    )

    raw_conflicts = classification.get("owner_review_domain_conflicts")
    if not isinstance(raw_conflicts, list) or len(raw_conflicts) != 1:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_domain_conflicts_invalid")
    conflicts: dict[str, Mapping[str, Any]] = {}
    for conflict in raw_conflicts:
        conflict = _require_exact_keys(
            conflict, _DOMAIN_CONFLICT_FIELDS, "reviewed_enrichment_domain_conflict"
        )
        digest = conflict.get("evidence_item_digest")
        domains = _as_sorted_strings(
            conflict.get("approved_canonical_domains"),
            "reviewed_enrichment_domain_conflict_domains",
        )
        if not (
            isinstance(digest, str)
            and len(digest) == 64
            and set(digest).issubset(set("0123456789abcdef"))
            and isinstance(conflict.get("raw_evidence_owner_id"), str)
            and isinstance(conflict.get("canonical_evidence_owner_id"), str)
            and isinstance(conflict.get("observed_domain"), str)
            and conflict.get("state")
            == "unresolved_alias_domain_conflict_owner_review_required"
            and conflict.get("execution_authority") is False
            and domains
            and digest not in conflicts
        ):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_domain_conflict_invalid")
        conflicts[digest] = conflict

    entries = raw.get("item_enrichments")
    if not isinstance(entries, dict) or len(entries) != 61:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_entries_invalid")
    state_counts = {state: 0 for state in _EXPECTED_STATES}
    for digest, entry in entries.items():
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_item_key_not_full_digest")
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_entry_shape_invalid")
        state = entry.get("provenance_mapping_state")
        if state not in state_counts:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_mapping_state_invalid")
        state_counts[state] += 1
        family = entry.get("source_family_ref")
        candidates = _as_sorted_strings(entry.get("candidate_source_family_refs"), "reviewed_enrichment_family_candidates")
        if any(candidate not in _FAMILY_AUTHORITY for candidate in candidates):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_family_candidate_unknown")
        minimum = _as_sorted_strings(entry.get("proposed_minimum_route_eligible_branch_ids"), "reviewed_enrichment_minimum_routes", allow_empty=True)
        coverage = _as_sorted_strings(entry.get("coverage_obligation_ids"), "reviewed_enrichment_coverage")
        _as_sorted_strings(entry.get("topic_refs"), "reviewed_enrichment_topics")
        _as_sorted_strings(entry.get("period_refs"), "reviewed_enrichment_periods", allow_empty=True)
        scopes = _as_sorted_strings(entry.get("authority_scope_refs"), "reviewed_enrichment_authority_scopes")
        is_ambiguous = state == "item_level_family_ambiguity_owner_review_required"
        if (digest in ambiguous) != is_ambiguous:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_ambiguity_registry_mismatch")
        if is_ambiguous:
            if family is not None or len(candidates) < 2 or entry.get("route_relation") != "unresolved" or minimum or entry.get("authority_tier_candidate") is not None:
                raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_ambiguity_not_preserved")
        elif not (
            isinstance(family, str)
            and candidates == (family,)
            and entry.get("route_relation") in {"minimum_route_eligible", "supplemental_only"}
            and entry.get("authority_tier_candidate")
            == ("reviewed" if state.startswith("f12_") else "primary")
        ):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_resolved_candidate_invalid")
        expected_scopes = tuple(sorted(_FAMILY_AUTHORITY[candidate] for candidate in candidates))
        if scopes != expected_scopes or not set(minimum).issubset(coverage):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_authority_or_route_invalid")
        if (entry.get("route_relation") == "minimum_route_eligible") != bool(minimum):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_route_relation_invalid")
    if state_counts != _EXPECTED_STATES or set(conflicts) - set(entries):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_state_or_conflict_counts_mismatch")
    return raw, entries, conflicts


def _source_materials(pack: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = pack.get("source_materials")
    if not isinstance(rows, list):
        raise ReviewedEvidenceEnrichmentError("base_pack_source_materials_invalid")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("material_ref"), str) or row["material_ref"] in result:
            raise ReviewedEvidenceEnrichmentError("base_pack_source_material_invalid")
        result[row["material_ref"]] = row
    return result


def _safe_live_metadata(item: Mapping[str, Any], origin: Literal["base", "overlay"], materials: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    material_ref = item.get("source_material_ref")
    material = materials.get(material_ref) if origin == "base" else item.get("source")
    if not isinstance(material_ref, str) or not isinstance(material, Mapping) or material.get("material_ref") != material_ref:
        raise ReviewedEvidenceEnrichmentError("reviewed_item_material_binding_invalid")
    bindings = item.get("slot_bindings")
    if not isinstance(bindings, list) or not bindings or any(not isinstance(row, Mapping) or not isinstance(row.get("slot_id"), str) for row in bindings):
        raise ReviewedEvidenceEnrichmentError("reviewed_item_topic_bindings_invalid")
    relationships = item.get("relationship_directions")
    if isinstance(relationships, str):
        relationship_directions = (relationships,)
    elif isinstance(relationships, list) and all(isinstance(value, str) for value in relationships):
        relationship_directions = tuple(sorted(set(relationships)))
    else:
        raise ReviewedEvidenceEnrichmentError("reviewed_item_relationship_invalid")
    source_url = material.get("source_url")
    source_domain = urlparse(source_url).hostname if isinstance(source_url, str) else None
    live = {
        "evidence_item_digest": item.get("evidence_item_digest"),
        "origin": origin,
        "source_material_ref": material_ref,
        "source_record_id": material.get("source_record_id"),
        "target_id": item.get("target_id"),
        "evidence_owner_id": material.get("evidence_owner_ticker"),
        "source_type": material.get("source_type"),
        "source_tier": material.get("source_tier"),
        "source_domain": source_domain.lower() if source_domain else None,
        "publication_date": item.get("publication_date"),
        "source_reporting_period_end": item.get("source_reporting_period_end"),
        "source_evidence_role": item.get("evidence_role"),
        "disposition": item.get("disposition"),
        "causal_attribution_authorized": item.get("causal_attribution_authorized"),
        "writer_citable": item.get("writer_citable"),
        "numeric_use_boundary": item.get("numeric_use_boundary"),
        "relationship_directions": relationship_directions,
        "topic_refs": tuple(sorted({row["slot_id"] for row in bindings})),
    }
    required = ("evidence_item_digest", "source_record_id", "target_id", "evidence_owner_id", "source_type", "source_tier", "source_domain", "publication_date", "source_evidence_role", "disposition", "numeric_use_boundary")
    if any(not isinstance(live[field], str) or not live[field] for field in required):
        raise ReviewedEvidenceEnrichmentError("reviewed_item_required_metadata_missing")
    if not isinstance(live["causal_attribution_authorized"], bool) or not isinstance(live["writer_citable"], bool):
        raise ReviewedEvidenceEnrichmentError("reviewed_item_authority_flags_invalid")
    _iso_date(live["publication_date"], "reviewed_item_publication_date")
    if live["source_reporting_period_end"] is not None:
        _iso_date(live["source_reporting_period_end"], "reviewed_item_period_end")
    return live


def _mechanical_family(live: Mapping[str, Any]) -> str:
    owner, source_type = live["evidence_owner_id"], live["source_type"]
    if owner == "DELL" and source_type in {"10-K", "10-Q"}:
        return "F1_SEC_ISSUER_FACTS"
    if owner == "DELL" and source_type in {"8-K", "EARNINGS_CALL_TRANSCRIPT"}:
        return "F2_DELL_IR_EARNINGS"
    if owner == "DELL" and source_type == "PUBLIC_WEB":
        return "F3_DELL_PRODUCT_SUPPORT"
    if owner == "MSFT":
        return "F4_CUSTOMER_CAPEX_DEPLOYMENT"
    if owner == "ORG::88D1082A31CB2777":
        return "F5_PUBLIC_PROCUREMENT"
    if owner == "NVDA":
        return "F6_COMPUTE_PLATFORM_SUPPLIERS"
    if owner in {"MU", "TSM"}:
        return "F7_MEMORY_FOUNDRY_NETWORK_STORAGE"
    raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_mechanical_rule_unmatched")


def _derived_period_refs(live: Mapping[str, Any]) -> tuple[str, ...]:
    """Derive the finite Dell-slice period labels from non-narrative metadata."""

    if live["origin"] == "overlay":
        if not (
            live["evidence_owner_id"] == "DELL"
            and live["source_type"] == "8-K"
            and live["source_reporting_period_end"] == "2026-07-31"
        ):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_overlay_period_rule_unmatched")
        return ("FY2027_Q2",)
    key = (
        live["evidence_owner_id"],
        live["source_type"],
        live["source_reporting_period_end"],
    )
    exact_periods = {
        ("DELL", "10-K", "2026-01-30"): ("FY2026",),
        ("DELL", "10-Q", "2025-10-31"): ("FY2026_Q3",),
        ("DELL", "8-K", "2026-05-28"): ("FY2027_Q1",),
        ("DELL", "EARNINGS_CALL_TRANSCRIPT", "2026-05-01"): ("FY2027_Q1",),
        ("MSFT", "10-Q", "2026-03-31"): ("FY2026_Q3",),
        ("MU", "8-K", "2026-06-24"): ("FY2026_Q3",),
        ("NVDA", "10-Q", "2025-10-26"): ("FY2026_Q3",),
        ("NVDA", "10-Q", "2026-04-26"): ("FY2027_Q1",),
        ("NVDA", "8-K", "2026-05-20"): ("FY2027_Q1",),
        ("TSM", "6-K", "2026-06-30"): ("CY2026_Q2",),
        ("TSM", "EARNINGS_CALL_TRANSCRIPT", "2026-06-30"): ("CY2026_Q2",),
    }
    if key in exact_periods:
        return exact_periods[key]
    if live["source_reporting_period_end"] is None and live["source_type"] in {
        "PUBLIC_PDF",
        "PUBLIC_WEB",
    }:
        return ()
    raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_period_rule_unmatched")


def _composite_identity_digest(
    base: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> str:
    base_items, overlay_items = base.get("evidence_items"), overlay.get("evidence_items")
    if not isinstance(base_items, list) or not isinstance(overlay_items, list):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_composite_items_invalid")

    def item_digests(items: list[Any], label: str) -> tuple[str, ...]:
        values: list[str] = []
        for item in items:
            digest = item.get("evidence_item_digest") if isinstance(item, Mapping) else None
            if not (
                isinstance(digest, str)
                and len(digest) == 64
                and set(digest).issubset(set("0123456789abcdef"))
            ):
                raise ReviewedEvidenceEnrichmentError(f"{label}_item_digest_invalid")
            values.append(digest)
        result = tuple(sorted(values))
        if len(result) != len(set(result)):
            raise ReviewedEvidenceEnrichmentError(f"{label}_item_digest_duplicate")
        return result

    base_digests = item_digests(base_items, "base_pack")
    overlay_digests = item_digests(overlay_items, "overlay_projection")
    composite_digests = tuple(sorted((*base_digests, *overlay_digests)))
    if len(base_digests) != 55 or len(overlay_digests) != 6 or len(set(composite_digests)) != 61:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_composite_identity_invalid")
    body = {
        "schema_version": "fin_ia_dell_reviewed_evidence_composite_identity_v1_0",
        "case_key": "DELL",
        "base_pack_payload_digest": base.get("pack_payload_digest"),
        "overlay_projection_digest": overlay.get("projection_digest"),
        "base_evidence_item_digests": base_digests,
        "overlay_evidence_item_digests": overlay_digests,
        "composite_evidence_item_digests": composite_digests,
        "base_item_count": len(base_digests),
        "overlay_item_count": len(overlay_digests),
        "composite_item_count": len(composite_digests),
    }
    return canonical_digest(body)


def _entity_registry(
    catalog: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    rows = catalog.get("entity_aliases")
    if not isinstance(rows, list) or not rows:
        raise ReviewedEvidenceEnrichmentError("physical_catalog_entity_aliases_invalid")
    by_alias: dict[str, Mapping[str, Any]] = {}
    by_canonical: dict[str, Mapping[str, Any]] = {}
    for raw_row in rows:
        row = _require_exact_keys(
            raw_row,
            {"canonical_entity_id", "entity_kind", "aliases", "canonical_domains"},
            "physical_catalog_entity_alias",
        )
        canonical = row.get("canonical_entity_id")
        entity_kind = row.get("entity_kind")
        aliases_value, domains_value = row.get("aliases"), row.get("canonical_domains")
        if not (
            isinstance(canonical, str)
            and canonical
            and isinstance(entity_kind, str)
            and entity_kind
            and isinstance(aliases_value, list)
            and all(isinstance(alias, str) and alias for alias in aliases_value)
            and len(aliases_value) == len(set(aliases_value))
            and isinstance(domains_value, list)
            and all(isinstance(domain, str) and domain == domain.lower() for domain in domains_value)
            and len(domains_value) == len(set(domains_value))
            and domains_value
            and canonical not in by_canonical
        ):
            raise ReviewedEvidenceEnrichmentError("physical_catalog_entity_alias_invalid")
        aliases = tuple(sorted({canonical, *aliases_value}))
        domains = tuple(sorted(domains_value))
        normalized = {
            "canonical_entity_id": canonical,
            "entity_kind": entity_kind,
            "aliases": aliases,
            "canonical_domains": domains,
        }
        by_canonical[canonical] = normalized
        for alias in aliases:
            if alias in by_alias:
                raise ReviewedEvidenceEnrichmentError("physical_catalog_entity_alias_collision")
            by_alias[alias] = normalized
    return by_alias, by_canonical


def _resolve_entity(
    *,
    digest: str,
    raw_owner_id: str,
    source_domain: str,
    by_alias: Mapping[str, Mapping[str, Any]],
    conflicts: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], EntityResolutionState]:
    entity = by_alias.get(raw_owner_id)
    if entity is None:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_owner_alias_unresolved")
    canonical = entity["canonical_entity_id"]
    domains = tuple(entity["canonical_domains"])
    conflict = conflicts.get(digest)
    if source_domain in domains:
        if conflict is not None:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_spurious_domain_conflict")
        return entity, "resolved_alias_and_domain"
    if conflict is None:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_unapproved_domain_mismatch")
    if not (
        conflict.get("raw_evidence_owner_id") == raw_owner_id
        and conflict.get("canonical_evidence_owner_id") == canonical
        and conflict.get("observed_domain") == source_domain
        and tuple(conflict.get("approved_canonical_domains", ())) == domains
        and conflict.get("state")
        == "unresolved_alias_domain_conflict_owner_review_required"
        and conflict.get("execution_authority") is False
    ):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_domain_conflict_binding_mismatch")
    return entity, "unresolved_alias_domain_conflict_owner_review_required"


def _topic_mapping(catalog: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    rows = catalog.get("reviewed_topic_branch_mapping")
    if not isinstance(rows, list):
        raise ReviewedEvidenceEnrichmentError("physical_catalog_topic_mapping_invalid")
    result: dict[str, tuple[str, ...]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("topic_id"), str):
            raise ReviewedEvidenceEnrichmentError("physical_catalog_topic_mapping_invalid")
        topic = row["topic_id"]
        branches = _as_sorted_strings(row.get("branch_ids"), "physical_catalog_topic_branches")
        if topic in result:
            raise ReviewedEvidenceEnrichmentError("physical_catalog_topic_duplicate")
        result[topic] = branches
    return result


def load_reviewed_evidence_enrichment_candidate(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    base_pack_path: Path = DEFAULT_BASE_PACK_PATH,
    overlay_path: Path = DEFAULT_OVERLAY_PATH,
    physical_catalog_path: Path = DEFAULT_PHYSICAL_CATALOG_PATH,
    expected_config_sha256: str = DEFAULT_EXPECTED_CONFIG_SHA256,
    expected_enrichment_digest: str = DEFAULT_EXPECTED_ENRICHMENT_DIGEST,
) -> ReviewedEvidenceAuditProjection:
    """Return the current non-executable, metadata-only audit projection."""

    _verify_file(config_path, expected_config_sha256, "reviewed_enrichment_config")
    config, entries, conflicts = _validate_candidate(
        _read_json(config_path, "reviewed_enrichment_config"),
        expected_enrichment_digest,
    )
    bindings = config.get("input_bindings")
    assert isinstance(bindings, Mapping)  # closed-schema validation above
    base_binding, overlay_binding, catalog_binding = bindings.get("base_pack"), bindings.get("overlay_projection"), bindings.get("physical_catalog")
    composite_binding = bindings.get("composite")
    assert all(isinstance(value, Mapping) for value in (base_binding, overlay_binding, catalog_binding, composite_binding))
    _verify_file(base_pack_path, base_binding.get("sha256"), "base_pack")
    _verify_file(overlay_path, overlay_binding.get("sha256"), "overlay_projection")
    _verify_file(physical_catalog_path, catalog_binding.get("sha256"), "physical_catalog")
    base, overlay, catalog = _read_json(base_pack_path, "base_pack"), _read_json(overlay_path, "overlay_projection"), _read_json(physical_catalog_path, "physical_catalog")
    _verify_self_digest(base, "pack_payload_digest", "base_pack")
    _verify_self_digest(overlay, "projection_digest", "overlay_projection")
    _verify_self_digest(catalog, "catalog_digest", "physical_catalog")
    if not (
        base.get("pack_payload_digest") == base_binding.get("payload_digest")
        and overlay.get("projection_digest") == overlay_binding.get("projection_digest")
        and catalog.get("catalog_digest") == catalog_binding.get("catalog_digest")
        and catalog.get("status") == catalog_binding.get("required_status") == "owner_review_candidate_answer_free_not_execution_authority"
        and catalog_binding.get("execution_authority") is False
        and isinstance(catalog.get("authority"), dict)
        and catalog["authority"].get("execution_authority") is False
        and base_binding.get("expected_item_count") == 55
        and overlay_binding.get("expected_item_count") == 6
        and composite_binding.get("digest_basis")
        == "canonical_evidence_item_digest_union_v1"
        and composite_binding.get("expected_item_count") == 61
        and composite_binding.get("legacy_active_projection_digest")
        == "c91d5c588f2ed2142c0bb7f079614f758cb8a92fc9149126d418cdbbafa87e7d"
    ):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_input_binding_invalid")
    base_items, overlay_items = base.get("evidence_items"), overlay.get("evidence_items")
    if not isinstance(base_items, list) or len(base_items) != 55 or not isinstance(overlay_items, list) or len(overlay_items) != 6:
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_input_count_mismatch")
    materials = _source_materials(base)
    live_rows = [*(_safe_live_metadata(item, "base", materials) for item in base_items), *(_safe_live_metadata(item, "overlay", materials) for item in overlay_items)]
    live_by_digest = {row["evidence_item_digest"]: row for row in live_rows}
    if len(live_by_digest) != 61 or set(live_by_digest) != set(entries):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_item_universe_mismatch")
    composite_identity_digest = _composite_identity_digest(base, overlay)
    if composite_identity_digest != composite_binding.get("composite_digest"):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_composite_digest_mismatch")

    topic_mapping = _topic_mapping(catalog)
    entity_by_alias, entity_by_canonical = _entity_registry(catalog)
    catalog_domains = {
        domain
        for entity in entity_by_canonical.values()
        for domain in entity["canonical_domains"]
    }
    if not set(_EXPECTED_F12_DOMAINS).issubset(catalog_domains):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_f12_catalog_domain_missing")
    required_by_branch = dict(DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE)
    f12_domains = set(_EXPECTED_F12_DOMAINS)
    ambiguous_digests = set(config["classification_contract"]["ambiguous_item_digests"])
    cutoff = _iso_date(config.get("research_as_of"), "reviewed_enrichment_research_as_of")
    audit_rows: list[ReviewedEvidenceAuditRow] = []
    observed_conflicts: set[str] = set()
    for digest in sorted(entries):
        entry, live = entries[digest], live_by_digest[digest]
        for field in ("origin", "source_material_ref", "source_record_id", "target_id", "evidence_owner_id", "topic_refs"):
            expected = tuple(entry[field]) if field == "topic_refs" else entry[field]
            if live[field] != expected:
                raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_live_metadata_mismatch")
        state, family = entry["provenance_mapping_state"], entry["source_family_ref"]
        derived_state: MappingState
        if digest in ambiguous_digests:
            derived_state = "item_level_family_ambiguity_owner_review_required"
        elif live["source_domain"] in f12_domains:
            derived_state = "f12_independent_source_rule_candidate_owner_review_required"
        else:
            derived_state = "mechanical_metadata_mapping"
        if state != derived_state:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_classification_derivation_mismatch")
        if state == "mechanical_metadata_mapping" and family != _mechanical_family(live):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_mechanical_family_mismatch")
        if state.startswith("f12_") and (family != "F12_INDEPENDENT_COUNTEREVIDENCE" or live["source_domain"] not in f12_domains):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_f12_rule_mismatch")
        derived_tier = (
            None
            if state == "item_level_family_ambiguity_owner_review_required"
            else "reviewed"
            if state.startswith("f12_")
            else "primary"
        )
        if entry["authority_tier_candidate"] != derived_tier:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_authority_tier_mismatch")
        periods = _derived_period_refs(live)
        if periods != tuple(entry["period_refs"]):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_period_refs_mismatch")
        coverage = tuple(sorted({branch for topic in live["topic_refs"] for branch in topic_mapping.get(topic, ())}))
        if any(topic not in topic_mapping for topic in live["topic_refs"]) or coverage != tuple(entry["coverage_obligation_ids"]):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_topic_branch_mismatch")
        minimum = () if family is None else tuple(branch for branch in coverage if family in required_by_branch.get(branch, ()))
        if minimum != tuple(entry["proposed_minimum_route_eligible_branch_ids"]):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_minimum_route_mismatch")
        if _iso_date(live["publication_date"], "reviewed_item_publication_date") > cutoff:
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_future_item")
        research_subjects = tuple(entry["research_subject_ids"])
        if research_subjects != ("DELL",):
            raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_research_subject_mismatch")
        entity, entity_resolution_state = _resolve_entity(
            digest=digest,
            raw_owner_id=live["evidence_owner_id"],
            source_domain=live["source_domain"],
            by_alias=entity_by_alias,
            conflicts=conflicts,
        )
        if entity_resolution_state.startswith("unresolved_"):
            observed_conflicts.add(digest)
        locator_ref = base_binding["ref"] if entry["origin"] == "base" else overlay_binding["ref"]
        row_body = {
            "evidence_item_digest": digest,
            **live,
            "canonical_evidence_owner_id": entity["canonical_entity_id"],
            "research_subject_ids": research_subjects,
            "entity_ids": tuple(sorted({*entity["aliases"], *research_subjects})),
            "entity_alias_refs": tuple(entity["aliases"]),
            "canonical_domain_refs": tuple(entity["canonical_domains"]),
            "entity_resolution_state": entity_resolution_state,
            "period_refs": periods,
            "coverage_obligation_ids": coverage,
            "provenance_mapping_state": state,
            "source_family_ref": family,
            "candidate_source_family_refs": tuple(entry["candidate_source_family_refs"]),
            "route_relation": entry["route_relation"],
            "proposed_minimum_route_eligible_branch_ids": minimum,
            "authority_tier_candidate": entry["authority_tier_candidate"],
            "authority_scope_refs": tuple(entry["authority_scope_refs"]),
            "locator": f"{locator_ref}#evidence_item_digest={digest}",
        }
        audit_rows.append(ReviewedEvidenceAuditRow(**row_body, row_digest=canonical_digest(row_body)))
    if observed_conflicts != set(conflicts):
        raise ReviewedEvidenceEnrichmentError("reviewed_enrichment_domain_conflict_not_observed")
    projection_body = {
        "schema_version": "fin_ia_dell_reviewed_evidence_enrichment_audit_projection_v1_0",
        "case_key": "DELL",
        "research_as_of": config["research_as_of"],
        "enrichment_digest": config["enrichment_digest"],
        "base_pack_payload_digest": base_binding["payload_digest"],
        "overlay_projection_digest": overlay_binding["projection_digest"],
        "composite_identity_digest": composite_identity_digest,
        "legacy_active_projection_digest": composite_binding["legacy_active_projection_digest"],
        "physical_catalog_digest": catalog_binding["catalog_digest"],
        "rows": tuple(audit_rows),
        "item_count": 61,
        "mechanical_mapping_count": 43,
        "f12_rule_candidate_count": 13,
        "item_level_ambiguity_count": 5,
        "entity_domain_conflict_count": 1,
        "answer_free": True,
        "owner_review_required": True,
        "execution_authority": False,
        "executable_reviewed_evidence_index_authorized": False,
    }
    return ReviewedEvidenceAuditProjection(**projection_body, projection_digest=canonical_digest(projection_body))


def load_executable_reviewed_evidence_index_v1_2(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    base_pack_path: Path = DEFAULT_BASE_PACK_PATH,
    overlay_path: Path = DEFAULT_OVERLAY_PATH,
    physical_catalog_path: Path = DEFAULT_PHYSICAL_CATALOG_PATH,
    expected_config_sha256: str = DEFAULT_EXPECTED_CONFIG_SHA256,
    expected_enrichment_digest: str = DEFAULT_EXPECTED_ENRICHMENT_DIGEST,
    owner_decision: DellOwnerDataGateDecision | None = None,
) -> ReviewedEvidenceIndexV1_2:
    """Materialize the exact 56-row Owner-approved executable metadata view.

    The five ambiguous rows are omitted only from this executable index.  They
    remain byte-for-byte present in the 61-row candidate and audit projection.
    """

    projection = load_reviewed_evidence_enrichment_candidate(
        config_path=config_path,
        base_pack_path=base_pack_path,
        overlay_path=overlay_path,
        physical_catalog_path=physical_catalog_path,
        expected_config_sha256=expected_config_sha256,
        expected_enrichment_digest=expected_enrichment_digest,
    )
    try:
        decision = validate_trusted_dell_owner_data_gate_decision(
            owner_decision or load_dell_owner_data_gate_decision()
        )
    except DellOwnerDataGateError as exc:
        raise ReviewedEvidenceEnrichmentError(str(exc)) from exc
    _validate_owner_decision_for_reviewed_projection(
        decision=decision,
        projection=projection,
        config_path=config_path,
        base_pack_path=base_pack_path,
        physical_catalog_path=physical_catalog_path,
    )

    excluded = set(
        decision.reviewed_evidence_decision.ambiguous_item_digests
    )
    rows: list[ReviewedEvidenceIndexRowV1_2] = []
    included_digests: list[str] = []
    for audit_row in projection.rows:
        if audit_row.evidence_item_digest in excluded:
            continue
        if (
            audit_row.source_family_ref is None
            or audit_row.authority_tier_candidate is None
            or audit_row.route_relation == "unresolved"
        ):
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_reviewed_row_still_ambiguous"
            )
        evidence_id = reviewed_evidence_id(
            case_key=projection.case_key,
            target_id=audit_row.target_id,
            evidence_item_digest=audit_row.evidence_item_digest,
        )
        locator = _runtime_logical_locator(audit_row, projection)
        row_body = {
            "case_key": projection.case_key,
            "source_family_ref": audit_row.source_family_ref,
            "coverage_obligation_ids": audit_row.coverage_obligation_ids,
            "minimum_route_eligible_branch_ids": (
                audit_row.proposed_minimum_route_eligible_branch_ids
            ),
            "entity_ids": audit_row.entity_ids,
            "target_id": audit_row.target_id,
            "topic_refs": audit_row.topic_refs,
            "evidence_role": audit_row.source_evidence_role,
            "authority_tier": audit_row.authority_tier_candidate,
            "publication_date": audit_row.publication_date,
            "period_refs": audit_row.period_refs,
            "source_reporting_period_end": (
                audit_row.source_reporting_period_end
            ),
            "source_type": audit_row.source_type,
            "source_tier": audit_row.source_tier,
            "evidence_id": evidence_id,
            "locator": locator,
            "locator_digest": canonical_digest({"locator": locator}),
            "item_digest": audit_row.evidence_item_digest,
            "metadata_state": "complete",
        }
        rows.append(
            ReviewedEvidenceIndexRowV1_2(
                **row_body,
                row_digest=canonical_digest(row_body),
            )
        )
        included_digests.append(audit_row.evidence_item_digest)

    rows.sort(key=lambda row: row.evidence_id)
    included = tuple(sorted(included_digests))
    if (
        len(rows)
        != decision.reviewed_evidence_decision.executable_item_count
        or len(included) != len(set(included))
        or set(included).intersection(excluded)
    ):
        raise ReviewedEvidenceEnrichmentError(
            "owner_approved_reviewed_index_population_mismatch"
        )
    source_pack_digest = canonical_digest(
        {
            "schema_version": (
                "fin_ia_dell_owner_approved_reviewed_evidence_view_v1_0"
            ),
            "base_pack_payload_digest": projection.base_pack_payload_digest,
            "overlay_projection_digest": projection.overlay_projection_digest,
            "composite_identity_digest": projection.composite_identity_digest,
            "enrichment_digest": projection.enrichment_digest,
            "owner_data_gate_decision_digest": decision.decision_digest,
            "included_evidence_item_digests": included,
            "excluded_audit_only_item_digests": tuple(sorted(excluded)),
        }
    )
    index_body = {
        "contract_version": "1.2",
        "index_id": (
            "reviewed-index:dell:owner-data-gate:"
            f"{decision.decision_digest[:24]}"
        ),
        "case_key": projection.case_key,
        "research_as_of": projection.research_as_of,
        "source_pack_digest": source_pack_digest,
        "rows": tuple(rows),
        "indexed_item_count": len(rows),
        "answer_free": True,
    }
    return ReviewedEvidenceIndexV1_2(
        **index_body,
        index_digest=canonical_digest(index_body),
    )


def _runtime_logical_locator(
    row: ReviewedEvidenceAuditRow,
    projection: ReviewedEvidenceAuditProjection,
) -> str:
    """Build a host-independent, content-addressed locator for runtime traces."""

    if row.origin == "base":
        artifact_kind = "reviewed-pack-payload"
        artifact_digest = projection.base_pack_payload_digest
    else:
        artifact_kind = "reviewed-overlay-projection"
        artifact_digest = projection.overlay_projection_digest
    return (
        f"{artifact_kind}:sha256:{artifact_digest}"
        f"#evidence_item_digest={row.evidence_item_digest}"
    )


def _validate_owner_decision_for_reviewed_projection(
    *,
    decision: DellOwnerDataGateDecision,
    projection: ReviewedEvidenceAuditProjection,
    config_path: Path,
    base_pack_path: Path,
    physical_catalog_path: Path,
) -> None:
    bound = decision.bound_inputs
    reviewed = decision.reviewed_evidence_decision
    if not (
        decision.authority.reviewed_index_runtime_consumption_authorized
        and decision.authority.capability_inventory_composition_authorized
        and _sha256_file(Path(config_path)) == bound.reviewed_enrichment_sha256
        and projection.enrichment_digest == bound.reviewed_enrichment_digest
        and projection.projection_digest == bound.reviewed_audit_projection_digest
        and projection.composite_identity_digest
        == bound.reviewed_composite_identity_digest
        and _sha256_file(Path(physical_catalog_path))
        == bound.physical_catalog_sha256
        and projection.physical_catalog_digest == bound.physical_catalog_digest
        and projection.item_count == reviewed.audited_item_count
    ):
        raise ReviewedEvidenceEnrichmentError(
            "owner_data_gate_reviewed_input_binding_mismatch"
        )

    ambiguous = {
        row.evidence_item_digest
        for row in projection.rows
        if row.provenance_mapping_state
        == "item_level_family_ambiguity_owner_review_required"
    }
    if ambiguous != set(reviewed.ambiguous_item_digests):
        raise ReviewedEvidenceEnrichmentError(
            "owner_data_gate_ambiguity_population_mismatch"
        )
    _validate_micron_sec_identity_binding(
        decision=decision,
        projection=projection,
        base_pack_path=Path(base_pack_path),
    )


def _validate_micron_sec_identity_binding(
    *,
    decision: DellOwnerDataGateDecision,
    projection: ReviewedEvidenceAuditProjection,
    base_pack_path: Path,
) -> None:
    binding = decision.reviewed_evidence_decision.micron_sec_filing_identity_binding
    audit = next(
        (
            row
            for row in projection.rows
            if row.evidence_item_digest == binding.evidence_item_digest
        ),
        None,
    )
    if audit is None or not (
        audit.evidence_owner_id == binding.raw_evidence_owner_id
        and audit.canonical_evidence_owner_id
        == binding.canonical_evidence_owner_id
        and audit.source_record_id == binding.source_record_id
        and audit.source_domain == binding.observed_domain
        and audit.entity_resolution_state
        == "unresolved_alias_domain_conflict_owner_review_required"
        and binding.observed_domain not in audit.canonical_domain_refs
        and binding.adds_sec_domain_to_canonical_domain_registry is False
    ):
        raise ReviewedEvidenceEnrichmentError(
            "owner_data_gate_micron_audit_binding_mismatch"
        )

    pack = _read_json(base_pack_path, "base_pack")
    items = pack.get("evidence_items")
    materials = _source_materials(pack)
    item = next(
        (
            row
            for row in items
            if isinstance(row, Mapping)
            and row.get("evidence_item_digest") == binding.evidence_item_digest
        ),
        None,
    ) if isinstance(items, list) else None
    material = (
        materials.get(item.get("source_material_ref"))
        if isinstance(item, Mapping)
        else None
    )
    if not isinstance(material, Mapping):
        raise ReviewedEvidenceEnrichmentError(
            "owner_data_gate_micron_source_material_missing"
        )
    source_record_id = material.get("source_record_id")
    source_url = material.get("source_url")
    record_match = re.fullmatch(
        r"SUPP::MU::([0-9]{18})::CHUNK_[0-9]{4}",
        str(source_record_id or ""),
    )
    url_match = re.fullmatch(
        r"https://www[.]sec[.]gov/Archives/edgar/data/([0-9]+)/"
        r"([0-9]{18})/[^/?#]+",
        str(source_url or ""),
    )
    accession_digits = binding.sec_accession.replace("-", "")
    if record_match is None or url_match is None or not (
        source_record_id == binding.source_record_id
        and source_url == binding.sec_archive_url
        and material.get("evidence_owner_ticker") == binding.raw_evidence_owner_id
        and record_match.group(1) == accession_digits
        and url_match.group(2) == accession_digits
        and url_match.group(1).zfill(10) == binding.sec_cik
        and accession_digits[:10] == binding.sec_cik
    ):
        raise ReviewedEvidenceEnrichmentError(
            "owner_data_gate_micron_cik_accession_binding_mismatch"
        )


_RUNTIME_ITEM_FIELDS = (
    "case_key",
    "target_id",
    "source_record_id",
    "disposition",
    "evidence_role",
    "publication_date",
    "source_reporting_period_end",
    "research_as_of",
    "numeric_use_boundary",
    "causal_attribution_authorized",
    "writer_citable",
    "evidence_item_digest",
    "source_content_digest",
)
_RUNTIME_SOURCE_FIELDS = (
    "material_ref",
    "source_record_id",
    "evidence_owner_ticker",
    "source_tier",
    "source_type",
    "source_url",
    "publication_date",
    "period_end",
    "license_scope",
    "redistributable",
    "source_text_digest",
)


def _project_runtime_reviewed_item(
    *,
    item: Mapping[str, Any],
    source: Mapping[str, Any],
    index_row: ReviewedEvidenceIndexRowV1_2,
    maximum_excerpt_characters: int,
    raw_source_text: str | None,
) -> dict[str, Any]:
    """Project one already-validated item without source bytes or host paths."""

    if raw_source_text is not None:
        source_text_digest = hashlib.sha256(
            raw_source_text.encode("utf-8")
        ).hexdigest()
        excerpt_source = raw_source_text.strip()
    else:
        source_text_digest = str(source.get("source_text_digest") or "")
        excerpt_source = str(source.get("reviewed_source_excerpt") or "").strip()
    item_digest = str(item.get("evidence_item_digest") or "")
    source_content_digest = str(item.get("source_content_digest") or "")
    source_record_id = str(item.get("source_record_id") or "")
    source_url = str(source.get("source_url") or "")
    if not (
        item_digest == index_row.item_digest
        and str(item.get("target_id") or "") == index_row.target_id
        and reviewed_evidence_id(
            case_key=index_row.case_key,
            target_id=item.get("target_id"),
            evidence_item_digest=item_digest,
        )
        == index_row.evidence_id
        and str(source.get("material_ref") or "")
        == str(item.get("source_material_ref") or "")
        and str(source.get("source_record_id") or "") == source_record_id
        and source_text_digest == str(source.get("source_text_digest") or "")
        and source_text_digest == source_content_digest
        and excerpt_source
        and urlparse(source_url).scheme == "https"
        and bool(urlparse(source_url).hostname)
        and item.get("writer_citable") is True
        and item.get("causal_attribution_authorized") is False
        and (
            item.get("disposition"),
            item.get("evidence_role"),
        )
        in {
            ("accepted_direct_source_evidence", "issuer_direct_source"),
            (
                "accepted_bounded_context_evidence",
                "counterparty_or_ecosystem_readthrough",
            ),
        }
    ):
        raise ReviewedEvidenceEnrichmentError(
            "owner_approved_reviewed_runtime_item_binding_mismatch"
        )

    bounded_excerpt = excerpt_source[:maximum_excerpt_characters]
    projected = {
        key: deepcopy(item.get(key))
        for key in _RUNTIME_ITEM_FIELDS
    }
    projected["source"] = {
        key: deepcopy(source.get(key))
        for key in _RUNTIME_SOURCE_FIELDS
    }
    projected["source"].update(
        {
            "reviewed_source_excerpt": bounded_excerpt,
            "excerpt_truncated": (
                len(excerpt_source) > maximum_excerpt_characters
                or bool(source.get("excerpt_truncated"))
            ),
            "excerpt_use_boundary": (
                "Authenticated internal review only; never auto-promote the "
                "excerpt into a deliverable or financial-truth store."
            ),
            "source_locator": {
                "locator_kind": "owner_approved_reviewed_item",
                "logical_ref": index_row.locator,
                "locator_digest": index_row.locator_digest,
            },
        }
    )
    return projected


def load_owner_approved_reviewed_case(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    base_pack_path: Path = DEFAULT_BASE_PACK_PATH,
    overlay_path: Path = DEFAULT_OVERLAY_PATH,
    physical_catalog_path: Path = DEFAULT_PHYSICAL_CATALOG_PATH,
    expected_config_sha256: str = DEFAULT_EXPECTED_CONFIG_SHA256,
    expected_enrichment_digest: str = DEFAULT_EXPECTED_ENRICHMENT_DIGEST,
    owner_decision: DellOwnerDataGateDecision | None = None,
    maximum_excerpt_characters: int = 1_200,
) -> dict[str, Any]:
    """Return the transient 56-item case consumed by the existing reader.

    This is not a Workbench-current promotion.  It is a read-only composite of
    the exact base and overlay bytes authorized by the pinned Owner decision.
    """

    if not 200 <= maximum_excerpt_characters <= 4_000:
        raise ReviewedEvidenceEnrichmentError(
            "owner_approved_reviewed_excerpt_limit_invalid"
        )
    decision = owner_decision or load_dell_owner_data_gate_decision()
    index = load_executable_reviewed_evidence_index_v1_2(
        config_path=config_path,
        base_pack_path=base_pack_path,
        overlay_path=overlay_path,
        physical_catalog_path=physical_catalog_path,
        expected_config_sha256=expected_config_sha256,
        expected_enrichment_digest=expected_enrichment_digest,
        owner_decision=decision,
    )
    base = _read_json(Path(base_pack_path), "base_pack")
    overlay = _read_json(Path(overlay_path), "overlay_projection")
    try:
        validate_reviewed_evidence_pack(base)
    except (ReviewedEvidencePackError, TypeError, ValueError) as exc:
        raise ReviewedEvidenceEnrichmentError(
            "owner_approved_base_pack_contract_invalid"
        ) from exc
    base_items = base.get("evidence_items")
    overlay_items = overlay.get("evidence_items")
    if not isinstance(base_items, list) or not isinstance(overlay_items, list):
        raise ReviewedEvidenceEnrichmentError(
            "owner_approved_reviewed_case_items_invalid"
        )
    materials = _source_materials(base)
    source_items: dict[str, tuple[Mapping[str, Any], Mapping[str, Any], str | None]] = {}
    for item in base_items:
        if not isinstance(item, Mapping):
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_base_item_invalid"
            )
        source = materials.get(str(item.get("source_material_ref") or ""))
        if not isinstance(source, Mapping):
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_base_source_missing"
            )
        raw_source_text = source.get("source_text")
        if not isinstance(raw_source_text, str):
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_base_source_text_invalid"
            )
        digest = str(item.get("evidence_item_digest") or "")
        if digest in source_items:
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_reviewed_item_duplicate"
            )
        source_items[digest] = (item, source, raw_source_text)
    for item in overlay_items:
        if not isinstance(item, Mapping) or not isinstance(
            item.get("source"), Mapping
        ):
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_overlay_item_invalid"
            )
        digest = str(item.get("evidence_item_digest") or "")
        if digest in source_items:
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_reviewed_item_duplicate"
            )
        source_items[digest] = (item, item["source"], None)

    projected: list[dict[str, Any]] = []
    for index_row in index.rows:
        bound = source_items.get(index_row.item_digest)
        if bound is None:
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_reviewed_index_item_missing"
            )
        item, source, raw_source_text = bound
        projected.append(
            _project_runtime_reviewed_item(
                item=item,
                source=source,
                index_row=index_row,
                maximum_excerpt_characters=maximum_excerpt_characters,
                raw_source_text=raw_source_text,
            )
        )
    projected_ids = {
        reviewed_evidence_id(
            case_key=index.case_key,
            target_id=item["target_id"],
            evidence_item_digest=item["evidence_item_digest"],
        )
        for item in projected
    }
    if (
        len(projected) != index.indexed_item_count
        or projected_ids != {row.evidence_id for row in index.rows}
        or set(decision.reviewed_evidence_decision.ambiguous_item_digests)
        .intersection(item["evidence_item_digest"] for item in projected)
    ):
        raise ReviewedEvidenceEnrichmentError(
            "owner_approved_reviewed_case_population_mismatch"
        )
    return {
        "schema_version": "fin_ia_dell_owner_approved_reviewed_case_v1_0",
        "status": "owner_approved_transient_composite_not_workbench_current",
        "case_key": index.case_key,
        "projection_digest": index.source_pack_digest,
        "reviewed_index_digest": index.index_digest,
        "owner_data_gate_decision_digest": decision.decision_digest,
        "evidence_items": projected,
        "item_count": len(projected),
        "candidate_artifacts_mutated": False,
    }


@dataclass(frozen=True)
class OwnerApprovedReviewedCaseReader:
    """Callable case source for ``CurrentReviewedEvidenceReader``."""

    config_path: Path = DEFAULT_CONFIG_PATH
    base_pack_path: Path = DEFAULT_BASE_PACK_PATH
    overlay_path: Path = DEFAULT_OVERLAY_PATH
    physical_catalog_path: Path = DEFAULT_PHYSICAL_CATALOG_PATH
    owner_decision: DellOwnerDataGateDecision | None = None
    maximum_excerpt_characters: int = 1_200

    def __call__(self, case_key: str) -> Mapping[str, Any]:
        if str(case_key).strip().upper() != "DELL":
            raise ReviewedEvidenceEnrichmentError(
                "owner_approved_reviewed_case_key_invalid"
            )
        return load_owner_approved_reviewed_case(
            config_path=self.config_path,
            base_pack_path=self.base_pack_path,
            overlay_path=self.overlay_path,
            physical_catalog_path=self.physical_catalog_path,
            owner_decision=self.owner_decision,
            maximum_excerpt_characters=self.maximum_excerpt_characters,
        )


__all__ = [
    "DEFAULT_BASE_PACK_PATH",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_EXPECTED_CONFIG_SHA256",
    "DEFAULT_EXPECTED_ENRICHMENT_DIGEST",
    "DEFAULT_OVERLAY_PATH",
    "DEFAULT_PHYSICAL_CATALOG_PATH",
    "OwnerApprovedReviewedCaseReader",
    "ReviewedEvidenceAuditProjection",
    "ReviewedEvidenceAuditRow",
    "ReviewedEvidenceEnrichmentError",
    "load_executable_reviewed_evidence_index_v1_2",
    "load_owner_approved_reviewed_case",
    "load_reviewed_evidence_enrichment_candidate",
]
