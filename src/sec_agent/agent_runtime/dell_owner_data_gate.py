"""Content-addressed Owner decision for the Dell RC-S3-105 data gate.

The physical-route catalog and Reviewed Evidence enrichment remain immutable,
non-executable candidates.  This module validates the separate Owner decision
that may authorize those exact candidate bytes for answer-free runtime
composition.  It grants no model, provider, network, paid, Evidence-admission,
numeric-fact or public-information-gap authority.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from sec_agent.agent_runtime.dell_agentic_contracts import canonical_digest
from sec_agent.canonical_runtime.contracts_v1_2 import StrictFrozenModel


Digest = str
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OWNER_DATA_GATE_DECISION_PATH = (
    _REPO_ROOT
    / "configs/research/fin_ia_0_1_3_dell_owner_data_gate_decision_v1_0.json"
)
# Trust anchors compiled into the consumer.  A modified and re-signed decision
# cannot authorize itself merely by changing values inside the JSON document.
DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_SHA256 = (
    "399efd449c5d627e6a7f96fbc7074734cda304b5634971fd9fb7122a5f9f00b3"
)
DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST = (
    "739df0f5d2880af8e27a08b5f9e31e10e894f4900fb72681e7b02e065e89b204"
)


class DellOwnerDataGateError(ValueError):
    """The checked-in Owner decision is missing, stale, or out of scope."""


class DataGateAuthority(StrictFrozenModel):
    answer_free: Literal[True]
    physical_catalog_runtime_consumption_authorized: Literal[True]
    reviewed_index_runtime_consumption_authorized: Literal[True]
    capability_inventory_composition_authorized: Literal[True]
    granted_data_authority_refs: tuple[
        Literal["authority:primary-read", "authority:reviewed-read"], ...
    ] = Field(min_length=2, max_length=2)
    candidate_artifact_mutation_authorized: Literal[False]
    model_or_provider_calls_authorized: Literal[False]
    network_calls_authorized: Literal[False]
    paid_calls_authorized: Literal[False]
    evidence_admission_authority: Literal[False]
    numeric_fact_authority: Literal[False]
    public_information_gap_authority: Literal[False]


class DataGateBoundInputs(StrictFrozenModel):
    physical_catalog_ref: Literal[
        "configs/research/fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json"
    ]
    physical_catalog_sha256: Digest = Field(pattern=_DIGEST_PATTERN)
    physical_catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    reviewed_enrichment_ref: Literal[
        "configs/research/fin_ia_0_1_3_dell_reviewed_evidence_enrichment_v1_0.json"
    ]
    reviewed_enrichment_sha256: Digest = Field(pattern=_DIGEST_PATTERN)
    reviewed_enrichment_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    reviewed_audit_projection_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    reviewed_composite_identity_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    s2_result_ref: Literal[
        "qualification/dell_reference_vertical/s2/"
        "s2_exact_period_contract_successor_20260902_r1/"
        "company_financial_fact_mart_result.json"
    ]
    s2_result_sha256: Digest = Field(pattern=_DIGEST_PATTERN)
    s2_result_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    s2_mart_ref: Literal[
        "qualification/dell_reference_vertical/s2/"
        "s2_exact_period_contract_successor_20260902_r1/"
        "company_financial_facts.sqlite"
    ]
    s2_mart_sha256: Digest = Field(pattern=_DIGEST_PATTERN)
    s2_observation_count: Literal[1319]
    s2_entity_count: Literal[3]
    s2_metric_count: Literal[12]


class SmciQ9SupplementalDecision(StrictFrozenModel):
    route_id: Literal["E11_SMCI_Q4_FY26_RESULTS"]
    canonical_issuer_id: Literal["SMCI"]
    branch_id: Literal["Q9_COUNTEREVIDENCE_WWC"]
    source_family_ref: Literal["F8_OEM_COMPETITION"]
    approved_route_relation: Literal["supplemental_only"]
    foundation_required_family_match: Literal[False]
    may_satisfy_f12_minimum_route: Literal[False]
    f12_minimum_route_status: Literal["unmet_must_remain_typed_gap"]


class LocalZeroBoundaryDecision(StrictFrozenModel):
    branch_id: Literal["Q3_UNITS_ASP_PVM", "Q4_ARCHITECTURE_RAMP"]
    source_family_ref: Literal[
        "F3_DELL_PRODUCT_SUPPORT", "F4_CUSTOMER_CAPEX_DEPLOYMENT"
    ]
    eligible_local_route_count: Literal[0]
    eligible_local_searchable_leaf_count: Literal[0]
    boundary_action: Literal["preserve_typed_local_insufficiency"]


class TopicMappingDecision(StrictFrozenModel):
    accepted_topic_mapping_count: Literal[10]
    topic_mapping_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    mapping_semantics: Literal["selector_only"]
    proves_claim_relevance: Literal[False]
    proves_branch_coverage: Literal[False]
    may_suppress_reviewed_lane: Literal[False]


class RouteCatalogDecision(StrictFrozenModel):
    accepted_owner_review_ids: tuple[str, ...] = Field(min_length=4, max_length=4)
    accepted_route_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    accepted_local_route_count: Literal[20]
    accepted_external_route_count: Literal[12]
    accepted_total_route_count: Literal[32]
    candidate_routes_remain_candidates_not_evidence: Literal[True]
    route_registration_is_not_branch_coverage: Literal[True]
    route_registration_is_not_source_family_satisfaction: Literal[True]
    smci_q9_supplemental_decision: SmciQ9SupplementalDecision
    local_zero_boundaries: tuple[LocalZeroBoundaryDecision, ...] = Field(
        min_length=2, max_length=2
    )
    topic_mapping_decision: TopicMappingDecision


class MicronSecFilingIdentityBinding(StrictFrozenModel):
    evidence_item_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    raw_evidence_owner_id: Literal["MU"]
    canonical_evidence_owner_id: Literal["MICRON"]
    sec_cik: Literal["0000723125"]
    sec_accession: Literal["0000723125-26-000013"]
    source_record_id: Literal["SUPP::MU::000072312526000013::CHUNK_0003"]
    observed_domain: Literal["www.sec.gov"]
    sec_archive_url: Literal[
        "https://www.sec.gov/Archives/edgar/data/723125/000072312526000013/a2026q3ex991-pressrelease.htm"
    ]
    binding_rule: Literal[
        "raw_alias_and_canonical_issuer_plus_sec_cik_and_accession"
    ]
    binding_scope: Literal["this_evidence_item_only"]
    adds_sec_domain_to_canonical_domain_registry: Literal[False]


class ReviewedEvidenceDecision(StrictFrozenModel):
    audited_item_count: Literal[61]
    non_ambiguous_candidate_mappings_accepted: Literal[True]
    executable_item_count: Literal[56]
    ambiguous_audit_only_item_count: Literal[5]
    ambiguity_operation: Literal[
        "exclude_from_executable_index_preserve_in_audit_projection"
    ]
    ambiguous_items_deleted: Literal[False]
    ambiguous_item_digests: tuple[Digest, ...] = Field(
        min_length=5, max_length=5
    )
    micron_sec_filing_identity_binding: MicronSecFilingIdentityBinding


class DellOwnerDataGateDecision(StrictFrozenModel):
    schema_version: Literal["fin_ia_dell_owner_data_gate_decision_v1_0"]
    decision_id: Literal[
        "FIN-0.1.3-S3-RC-S3-105-OWNER-DATA-GATE-20260903"
    ]
    recorded_at: Literal["2026-09-03"]
    status: Literal["owner_accepted_data_composition_successor_only"]
    case_id: Literal["DELL_AI_INFRA_REFERENCE_VERTICAL"]
    case_key: Literal["DELL"]
    product_version: Literal["FIN-0.1.3"]
    s_stage: Literal["S3_RC-S3-105_SUCCESSOR"]
    authority: DataGateAuthority
    bound_inputs: DataGateBoundInputs
    route_catalog_decision: RouteCatalogDecision
    reviewed_evidence_decision: ReviewedEvidenceDecision
    known_boundaries: tuple[str, ...] = Field(min_length=4, max_length=4)
    digest_contract: dict[str, object]
    decision_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_decision(self) -> "DellOwnerDataGateDecision":
        body = self.model_dump(mode="json", exclude={"decision_digest"})
        if canonical_digest(body) != self.decision_digest:
            raise ValueError("owner_data_gate_decision_digest_mismatch")
        if self.digest_contract != {
            "algorithm": "sha256",
            "canonicalization": (
                "utf8_json_ensure_ascii_false_sort_keys_true_separators_comma_colon"
            ),
            "self_digest_field": "decision_digest",
            "self_digest_field_excluded_from_digest": True,
        }:
            raise ValueError("owner_data_gate_digest_contract_mismatch")
        if self.authority.granted_data_authority_refs != (
            "authority:primary-read",
            "authority:reviewed-read",
        ):
            raise ValueError("owner_data_gate_authority_refs_mismatch")
        route = self.route_catalog_decision
        if route.accepted_owner_review_ids != (
            "OR-001-Q9-FAMILY-MISMATCH",
            "OR-002-Q3-F3-LOCAL-ZERO",
            "OR-003-F4-Q4-LOCAL-ZERO",
            "OR-004-TOPIC-MAPPING-PRECEDENCE",
        ):
            raise ValueError("owner_data_gate_review_ids_mismatch")
        if route.accepted_route_ids != tuple(sorted(route.accepted_route_ids)):
            raise ValueError("owner_data_gate_route_ids_not_canonical")
        zeros = tuple(
            (row.branch_id, row.source_family_ref)
            for row in route.local_zero_boundaries
        )
        if zeros != (
            ("Q3_UNITS_ASP_PVM", "F3_DELL_PRODUCT_SUPPORT"),
            ("Q4_ARCHITECTURE_RAMP", "F4_CUSTOMER_CAPEX_DEPLOYMENT"),
        ):
            raise ValueError("owner_data_gate_local_zero_boundaries_mismatch")
        reviewed = self.reviewed_evidence_decision
        if reviewed.ambiguous_item_digests != tuple(
            sorted(reviewed.ambiguous_item_digests)
        ):
            raise ValueError("owner_data_gate_ambiguity_ids_not_canonical")
        if self.known_boundaries != tuple(sorted(self.known_boundaries)):
            raise ValueError("owner_data_gate_known_boundaries_not_canonical")
        return self


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dell_owner_data_gate_decision(
    path: str | Path = DEFAULT_OWNER_DATA_GATE_DECISION_PATH,
    *,
    expected_file_sha256: str = DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_SHA256,
    expected_decision_digest: str = DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
) -> DellOwnerDataGateDecision:
    """Load only the externally anchored, exact Owner decision bytes."""

    decision_path = Path(path).expanduser().resolve(strict=True)
    if _file_sha256(decision_path) != expected_file_sha256:
        raise DellOwnerDataGateError("owner_data_gate_decision_file_sha256_mismatch")
    try:
        decision = DellOwnerDataGateDecision.model_validate_json(
            decision_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise DellOwnerDataGateError("owner_data_gate_decision_invalid") from exc
    if decision.decision_digest != expected_decision_digest:
        raise DellOwnerDataGateError("owner_data_gate_decision_untrusted_digest")
    return decision


def validate_trusted_dell_owner_data_gate_decision(
    decision: DellOwnerDataGateDecision,
) -> DellOwnerDataGateDecision:
    """Reject schema-valid decisions that are not the pinned Owner bytes.

    Runtime factories may pass an already-loaded object to several adapters.
    Rechecking the external digest anchor at every authority-bearing seam keeps
    a caller-created Pydantic object from becoming its own data authority.
    """

    validated = DellOwnerDataGateDecision.model_validate(
        decision.model_dump(mode="python")
    )
    if validated.decision_digest != DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST:
        raise DellOwnerDataGateError("owner_data_gate_decision_untrusted_digest")
    return validated


__all__ = [
    "DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST",
    "DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_SHA256",
    "DEFAULT_OWNER_DATA_GATE_DECISION_PATH",
    "DellOwnerDataGateDecision",
    "DellOwnerDataGateError",
    "load_dell_owner_data_gate_decision",
    "validate_trusted_dell_owner_data_gate_decision",
]
