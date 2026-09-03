"""Answer-free source-family inventory and compiler for the Dell vertical.

This module is deliberately a thin, zero-model boundary.  It does not search,
rank, call MCP, access storage, or infer a route from query text.  The host
supplies already-verified metadata and an explicit source-family catalog; the
compiler only proves that a semantic provider intent has a current, bounded,
physically executable target.

The important separation is preserved throughout:

* Reviewed Evidence is compiled against a reviewed metadata index;
* local retrieval is compiled into exact, co-occurring metadata scopes;
* external discovery is compiled into semantic external route targets.

No target can suppress or substitute another lane.  A rejected compilation is
a typed, answer-free correction with ``tool_call_authorized=False``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Literal, Sequence

from pydantic import Field, model_validator

from sec_agent.agent_runtime.dell_agentic_contracts import (
    BaselineSourcePlan,
    DELL_COVERAGE_OBLIGATION_IDS,
    ExternalSourceIntent,
    LocalEvidenceIntent,
    MinimumRouteObligation,
    ReviewedEvidenceIntent,
    RouteKind,
    canonical_digest,
)
from sec_agent.canonical_runtime.contracts_v1_2 import StrictFrozenModel


Digest = str
DocumentRouteKind = Literal[
    "reviewed_evidence",
    "local_candidate",
    "external_source",
]
LocalLane = Literal["prose_leaf", "table_leaf"]
AuthorityTier = Literal["reviewed", "primary"]
CompilationDisposition = Literal[
    "accepted",
    "accepted_with_residual_feedback",
    "rejected",
]

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,239}$"


# This is product-method authority, not an answer key.  It is intentionally
# independent of any retrieved passage or expected research conclusion.
DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE: tuple[
    tuple[str, tuple[str, ...]], ...
] = (
    ("Q1_ISSUER_TRUTH", ("F1_SEC_ISSUER_FACTS", "F2_DELL_IR_EARNINGS")),
    (
        "Q2_DEMAND_QUALITY",
        (
            "F2_DELL_IR_EARNINGS",
            "F4_CUSTOMER_CAPEX_DEPLOYMENT",
            "F5_PUBLIC_PROCUREMENT",
        ),
    ),
    (
        "Q3_UNITS_ASP_PVM",
        (
            "F2_DELL_IR_EARNINGS",
            "F3_DELL_PRODUCT_SUPPORT",
            "F5_PUBLIC_PROCUREMENT",
        ),
    ),
    (
        "Q4_ARCHITECTURE_RAMP",
        (
            "F3_DELL_PRODUCT_SUPPORT",
            "F6_COMPUTE_PLATFORM_SUPPLIERS",
            "F4_CUSTOMER_CAPEX_DEPLOYMENT",
        ),
    ),
    (
        "Q5_SUPPLY_AND_PRICE",
        (
            "F6_COMPUTE_PLATFORM_SUPPLIERS",
            "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
            "F2_DELL_IR_EARNINGS",
        ),
    ),
    (
        "Q6_MODEL_COMPUTE_DEMAND",
        (
            "F9_MODEL_COMPUTE_AND_BENCHMARKS",
            "F4_CUSTOMER_CAPEX_DEPLOYMENT",
            "F6_COMPUTE_PLATFORM_SUPPLIERS",
        ),
    ),
    (
        "Q7_EXPORT_CONTROL_CHINA",
        (
            "F10_EXPORT_CONTROL_AND_POLICY",
            "F1_SEC_ISSUER_FACTS",
            "F6_COMPUTE_PLATFORM_SUPPLIERS",
        ),
    ),
    (
        "Q8_COMPETITION_VALUE_POOL",
        (
            "F8_OEM_COMPETITION",
            "F6_COMPUTE_PLATFORM_SUPPLIERS",
            "F7_MEMORY_FOUNDRY_NETWORK_STORAGE",
        ),
    ),
    ("Q9_COUNTEREVIDENCE_WWC", ("F12_INDEPENDENT_COUNTEREVIDENCE",)),
)

_REQUIRED_FAMILY_MAP = dict(DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE)
_EXPECTED_SOURCE_FAMILY_REFS = frozenset(
    family_ref
    for _, family_refs in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE
    for family_ref in family_refs
)


class SourceFamilyCompilerError(ValueError):
    """Raised only for malformed host artifacts, never for a correctable intent."""


class _StrictFrozenModel(StrictFrozenModel):
    """One local alias keeps every durable object strict and frozen."""


def _without_digest(model: _StrictFrozenModel, field_name: str) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude={field_name})


def _verify_digest(model: _StrictFrozenModel, field_name: str, code: str) -> None:
    if canonical_digest(_without_digest(model, field_name)) != getattr(
        model, field_name
    ):
        raise ValueError(code)


def _require_unique(values: tuple[str, ...], code: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(code)


def _require_sorted_unique(values: tuple[str, ...], code: str) -> None:
    _require_unique(values, code)
    if values != tuple(sorted(values)):
        raise ValueError(f"{code}_not_canonical")


def _iso_date(value: str, code: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(code) from exc


def _document_route_kind(route_kind: RouteKind) -> DocumentRouteKind | None:
    if route_kind in {
        "reviewed_evidence",
        "local_candidate",
        "external_source",
    }:
        return route_kind
    return None


class SourceFamilyCatalogEntry(_StrictFrozenModel):
    """Explicit host-owned semantics for one source family.

    ``supported_route_kinds`` is a host-reviewed *policy allow-list*, not a
    claim that the current inventory contains an object for every listed
    lane.  Current availability is proved only by the inventory buckets.  The
    allow-list is never inferred from a route name, URL, query, issuer, or
    retrieved text.
    """

    source_family_ref: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=9)
    supported_route_kinds: tuple[DocumentRouteKind, ...] = Field(
        min_length=1, max_length=3
    )
    semantic_role_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    local_cardinality_ceiling: int | None = Field(default=None, ge=1, le=100_000)
    entry_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_entry(self) -> "SourceFamilyCatalogEntry":
        for name in (
            "coverage_obligation_ids",
            "supported_route_kinds",
            "semantic_role_refs",
            "authority_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"source_family_catalog_{name}_duplicate"
            )
        if not set(self.coverage_obligation_ids).issubset(
            DELL_COVERAGE_OBLIGATION_IDS
        ):
            raise ValueError("source_family_catalog_coverage_unknown")
        if (
            "local_candidate" in self.supported_route_kinds
        ) != (self.local_cardinality_ceiling is not None):
            raise ValueError("source_family_local_cardinality_contract_invalid")
        _verify_digest(self, "entry_digest", "source_family_catalog_entry_digest_mismatch")
        return self


class SourceFamilyCatalog(_StrictFrozenModel):
    """Answer-free, foundation-bound source-family catalog."""

    contract_version: Literal["1.2"] = "1.2"
    catalog_id: str = Field(pattern=_REF_PATTERN)
    case_id: str = Field(pattern=_REF_PATTERN)
    case_version: str = Field(min_length=1, max_length=80)
    research_as_of: str = Field(min_length=10, max_length=10)
    foundation_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    entries: tuple[SourceFamilyCatalogEntry, ...] = Field(min_length=1, max_length=64)
    answer_free: Literal[True] = True
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_catalog(self) -> "SourceFamilyCatalog":
        _iso_date(self.research_as_of, "source_family_catalog_research_as_of_invalid")
        refs = tuple(entry.source_family_ref for entry in self.entries)
        _require_sorted_unique(refs, "source_family_catalog_entry_duplicate")
        if set(refs) != _EXPECTED_SOURCE_FAMILY_REFS:
            raise ValueError("dell_source_family_catalog_incomplete")
        actual_by_coverage = {
            coverage_id: tuple(
                entry.source_family_ref
                for entry in self.entries
                if coverage_id in entry.coverage_obligation_ids
            )
            for coverage_id in DELL_COVERAGE_OBLIGATION_IDS
        }
        for coverage_id, expected in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE:
            if set(actual_by_coverage[coverage_id]) != set(expected):
                raise ValueError(
                    f"dell_source_family_catalog_coverage_mismatch:{coverage_id}"
                )
        _verify_digest(self, "catalog_digest", "source_family_catalog_digest_mismatch")
        return self


class CapabilityArtifactBinding(_StrictFrozenModel):
    """Proof that one inventory input was validated outside this pure module."""

    capability_kind: Literal[
        "local_candidate",
        "reviewed_evidence",
        "s2_numeric_fact",
        "external_source",
    ]
    artifact_ref: str = Field(pattern=_REF_PATTERN)
    artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    validated_object_count: int = Field(ge=0, le=10_000_000)
    validation_receipt_ref: str = Field(pattern=_REF_PATTERN)
    validation_receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    binding_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_binding(self) -> "CapabilityArtifactBinding":
        _verify_digest(self, "binding_digest", "capability_artifact_binding_digest_mismatch")
        return self


class LocalInventoryRecord(_StrictFrozenModel):
    """One verified, answer-free local leaf metadata row.

    The producer must explicitly attach ``source_family_ref``.  This module
    intentionally has no route-name heuristic or route-to-family fallback.
    """

    object_ref: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    branch_refs: tuple[str, ...] = Field(min_length=1, max_length=9)
    entity_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    canonical_issuer_id: str = Field(pattern=_REF_PATTERN)
    period_refs: tuple[str, ...] = Field(default=(), max_length=16)
    fiscal_period: str | None = Field(default=None, pattern=_REF_PATTERN)
    semantic_role_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    source_role: str = Field(pattern=_REF_PATTERN)
    route_id: str = Field(pattern=_REF_PATTERN)
    lane: LocalLane
    content_surface_refs: tuple[
        Literal["prose", "table", "image", "footnote"], ...
    ] = Field(min_length=1, max_length=4)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    source_artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    source_object_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    metadata_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_record(self) -> "LocalInventoryRecord":
        for name in (
            "branch_refs",
            "entity_refs",
            "period_refs",
            "semantic_role_refs",
            "content_surface_refs",
            "authority_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"local_inventory_record_{name}_duplicate"
            )
        if not set(self.branch_refs).issubset(DELL_COVERAGE_OBLIGATION_IDS):
            raise ValueError("local_inventory_record_branch_unknown")
        if self.lane == "prose_leaf" and not set(self.content_surface_refs).intersection(
            {"prose", "image", "footnote"}
        ):
            raise ValueError("local_inventory_record_prose_surface_missing")
        if self.lane == "table_leaf" and "table" not in self.content_surface_refs:
            raise ValueError("local_inventory_record_table_surface_missing")
        _verify_digest(self, "metadata_digest", "local_inventory_record_digest_mismatch")
        return self


class LocalInventoryBucket(_StrictFrozenModel):
    """A real co-occurring selector tuple, never a Cartesian product of sets."""

    bucket_id: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    branch_refs: tuple[str, ...] = Field(min_length=1, max_length=9)
    entity_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    canonical_issuer_id: str = Field(pattern=_REF_PATTERN)
    period_refs: tuple[str, ...] = Field(default=(), max_length=16)
    fiscal_period: str | None = Field(default=None, pattern=_REF_PATTERN)
    semantic_role_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    source_role: str = Field(pattern=_REF_PATTERN)
    route_id: str = Field(pattern=_REF_PATTERN)
    lane: LocalLane
    content_surface_refs: tuple[
        Literal["prose", "table", "image", "footnote"], ...
    ] = Field(min_length=1, max_length=4)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    source_artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    eligible_object_count: int = Field(ge=1, le=10_000_000)
    object_identity_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    bucket_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_bucket(self) -> "LocalInventoryBucket":
        for name in (
            "branch_refs",
            "entity_refs",
            "period_refs",
            "semantic_role_refs",
            "content_surface_refs",
            "authority_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"local_inventory_bucket_{name}_duplicate"
            )
        _verify_digest(self, "bucket_digest", "local_inventory_bucket_digest_mismatch")
        return self


class ReviewedEvidenceIndexRowV1_2(_StrictFrozenModel):
    """Comparable metadata for one existing Reviewed Evidence item.

    ``source_family_ref`` is the provenance family of the source owner/type.
    ``coverage_obligation_ids`` is only the topic-selector surface on which the
    row may be recalled.  A row closes a baseline family obligation only when
    that branch is also listed in ``minimum_route_eligible_branch_ids``.  This
    prevents a useful supplemental filing from being relabelled merely because
    its topic is relevant to another branch.
    """

    case_key: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=9)
    minimum_route_eligible_branch_ids: tuple[str, ...] = Field(
        default=(), max_length=9
    )
    entity_ids: tuple[str, ...] = Field(default=(), max_length=16)
    target_id: str = Field(pattern=_REF_PATTERN)
    topic_refs: tuple[str, ...] = Field(default=(), max_length=32)
    evidence_role: str = Field(pattern=_REF_PATTERN)
    authority_tier: AuthorityTier
    publication_date: str = Field(min_length=10, max_length=10)
    period_refs: tuple[str, ...] = Field(default=(), max_length=16)
    source_reporting_period_end: str | None = Field(
        default=None, min_length=10, max_length=10
    )
    source_type: str = Field(pattern=_REF_PATTERN)
    source_tier: str = Field(pattern=_REF_PATTERN)
    evidence_id: str = Field(pattern=_REF_PATTERN)
    locator: str = Field(min_length=1, max_length=4_000)
    locator_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    item_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    metadata_state: Literal["complete", "legacy_query_only_locator"]
    row_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_row(self) -> "ReviewedEvidenceIndexRowV1_2":
        for name in (
            "coverage_obligation_ids",
            "minimum_route_eligible_branch_ids",
            "entity_ids",
            "topic_refs",
            "period_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"reviewed_index_row_{name}_duplicate"
            )
        _iso_date(self.publication_date, "reviewed_index_publication_date_invalid")
        if not set(self.coverage_obligation_ids).issubset(
            DELL_COVERAGE_OBLIGATION_IDS
        ):
            raise ValueError("reviewed_index_selector_branch_unknown")
        if not set(self.minimum_route_eligible_branch_ids).issubset(
            self.coverage_obligation_ids
        ):
            raise ValueError("reviewed_index_minimum_route_not_selector_eligible")
        for branch_id in self.minimum_route_eligible_branch_ids:
            if self.source_family_ref not in _REQUIRED_FAMILY_MAP[branch_id]:
                raise ValueError("reviewed_index_minimum_route_family_mismatch")
        if self.source_reporting_period_end is not None:
            _iso_date(
                self.source_reporting_period_end,
                "reviewed_index_reporting_period_end_invalid",
            )
        if canonical_digest({"locator": self.locator}) != self.locator_digest:
            raise ValueError("reviewed_index_locator_digest_mismatch")
        # Timeless policy, product and relationship evidence can be fully
        # comparable without a reporting period.  Period metadata is required
        # only when the compiled intent asks for a period constraint.
        if self.metadata_state == "complete" and (
            not self.entity_ids or not self.topic_refs
        ):
            raise ValueError("reviewed_index_complete_metadata_missing")
        _verify_digest(self, "row_digest", "reviewed_index_row_digest_mismatch")
        return self


class ReviewedEvidenceIndexV1_2(_StrictFrozenModel):
    """Thin metadata index over the existing Reviewed Evidence store."""

    contract_version: Literal["1.2"] = "1.2"
    index_id: str = Field(pattern=_REF_PATTERN)
    case_key: str = Field(pattern=_REF_PATTERN)
    research_as_of: str = Field(min_length=10, max_length=10)
    source_pack_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    rows: tuple[ReviewedEvidenceIndexRowV1_2, ...]
    indexed_item_count: int = Field(ge=0, le=1_000_000)
    answer_free: Literal[True] = True
    index_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_index(self) -> "ReviewedEvidenceIndexV1_2":
        cutoff = _iso_date(
            self.research_as_of, "reviewed_index_research_as_of_invalid"
        )
        evidence_ids = tuple(row.evidence_id for row in self.rows)
        _require_sorted_unique(evidence_ids, "reviewed_index_evidence_id_duplicate")
        if self.indexed_item_count != len(self.rows):
            raise ValueError("reviewed_index_item_count_mismatch")
        if any(row.case_key != self.case_key for row in self.rows):
            raise ValueError("reviewed_index_case_mismatch")
        if any(_iso_date(row.publication_date, "invalid") > cutoff for row in self.rows):
            raise ValueError("reviewed_index_future_item_forbidden")
        _verify_digest(self, "index_digest", "reviewed_index_digest_mismatch")
        return self


class S2CapabilityBucket(_StrictFrozenModel):
    """Answer-free availability metadata for the existing S2 fact mart."""

    bucket_id: str = Field(pattern=_REF_PATTERN)
    entity_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    metric_refs: tuple[str, ...] = Field(min_length=1, max_length=256)
    period_refs: tuple[str, ...] = Field(min_length=1, max_length=512)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    source_artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    eligible_observation_count: int = Field(ge=1, le=10_000_000)
    bucket_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_bucket(self) -> "S2CapabilityBucket":
        for name in ("entity_refs", "metric_refs", "period_refs", "authority_refs"):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"s2_inventory_bucket_{name}_duplicate"
            )
        _verify_digest(self, "bucket_digest", "s2_inventory_bucket_digest_mismatch")
        return self


class ExternalInventoryBucket(_StrictFrozenModel):
    """One explicitly configured external discovery route."""

    bucket_id: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=9)
    external_route_ref: str = Field(pattern=_REF_PATTERN)
    canonical_entity_id: str = Field(pattern=_REF_PATTERN)
    entity_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    # Fiscal/reporting-period metadata is deliberately separate from publication
    # availability.  An empty tuple means the route can be used as a bounded
    # discovery candidate, while the requested period remains unresolved until
    # the captured source is validated.
    period_refs: tuple[str, ...] = Field(default=(), max_length=32)
    domain_allowlist: tuple[str, ...] = Field(default=(), max_length=64)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    available_not_before: str | None = Field(default=None, min_length=10, max_length=10)
    available_not_after: str | None = Field(default=None, min_length=10, max_length=10)
    source_artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    eligible_object_count: int = Field(ge=1, le=1_000_000)
    foundation_required_family_match: bool = True
    bucket_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_bucket(self) -> "ExternalInventoryBucket":
        for name in (
            "coverage_obligation_ids",
            "entity_refs",
            "period_refs",
            "domain_allowlist",
            "authority_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"external_inventory_bucket_{name}_duplicate"
            )
        start = (
            _iso_date(self.available_not_before, "external_inventory_start_invalid")
            if self.available_not_before is not None
            else None
        )
        end = (
            _iso_date(self.available_not_after, "external_inventory_end_invalid")
            if self.available_not_after is not None
            else None
        )
        if start is not None and end is not None and start > end:
            raise ValueError("external_inventory_date_range_invalid")
        _verify_digest(self, "bucket_digest", "external_inventory_bucket_digest_mismatch")
        return self


class CapabilityInventorySnapshot(_StrictFrozenModel):
    """Current immutable, answer-free capability inventory."""

    contract_version: Literal["1.2"] = "1.2"
    snapshot_id: str = Field(pattern=_REF_PATTERN)
    case_id: str = Field(pattern=_REF_PATTERN)
    case_version: str = Field(min_length=1, max_length=80)
    research_as_of: str = Field(min_length=10, max_length=10)
    foundation_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    source_family_catalog: SourceFamilyCatalog
    component_bindings: tuple[CapabilityArtifactBinding, ...] = Field(
        min_length=4, max_length=4
    )
    local_buckets: tuple[LocalInventoryBucket, ...]
    reviewed_evidence_index: ReviewedEvidenceIndexV1_2
    s2_buckets: tuple[S2CapabilityBucket, ...]
    external_buckets: tuple[ExternalInventoryBucket, ...]
    local_candidate_count: int = Field(ge=0, le=10_000_000)
    reviewed_evidence_count: int = Field(ge=0, le=1_000_000)
    s2_observation_count: int = Field(ge=0, le=10_000_000)
    external_object_count: int = Field(ge=0, le=1_000_000)
    answer_free: Literal[True] = True
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "CapabilityInventorySnapshot":
        _iso_date(self.research_as_of, "capability_inventory_research_as_of_invalid")
        catalog = self.source_family_catalog
        if (
            catalog.case_id != self.case_id
            or catalog.case_version != self.case_version
            or catalog.research_as_of != self.research_as_of
            or catalog.foundation_digest != self.foundation_digest
        ):
            raise ValueError("capability_inventory_catalog_binding_mismatch")

        bindings = {row.capability_kind: row for row in self.component_bindings}
        expected_kinds = {
            "local_candidate",
            "reviewed_evidence",
            "s2_numeric_fact",
            "external_source",
        }
        if set(bindings) != expected_kinds:
            raise ValueError("capability_inventory_component_binding_incomplete")

        counts = {
            "local_candidate": sum(row.eligible_object_count for row in self.local_buckets),
            "reviewed_evidence": self.reviewed_evidence_index.indexed_item_count,
            "s2_numeric_fact": sum(
                row.eligible_observation_count for row in self.s2_buckets
            ),
            "external_source": sum(
                row.eligible_object_count for row in self.external_buckets
            ),
        }
        declared = {
            "local_candidate": self.local_candidate_count,
            "reviewed_evidence": self.reviewed_evidence_count,
            "s2_numeric_fact": self.s2_observation_count,
            "external_source": self.external_object_count,
        }
        if counts != declared:
            raise ValueError("capability_inventory_declared_count_mismatch")
        if any(
            bindings[kind].validated_object_count != count
            for kind, count in counts.items()
        ):
            raise ValueError("capability_inventory_component_count_mismatch")
        if (
            self.reviewed_evidence_index.source_pack_digest
            != bindings["reviewed_evidence"].artifact_digest
        ):
            raise ValueError("capability_inventory_reviewed_digest_mismatch")

        local_digest = bindings["local_candidate"].artifact_digest
        s2_digest = bindings["s2_numeric_fact"].artifact_digest
        external_digest = bindings["external_source"].artifact_digest
        if any(row.source_artifact_digest != local_digest for row in self.local_buckets):
            raise ValueError("capability_inventory_local_digest_mismatch")
        if any(row.source_artifact_digest != s2_digest for row in self.s2_buckets):
            raise ValueError("capability_inventory_s2_digest_mismatch")
        if any(
            row.source_artifact_digest != external_digest for row in self.external_buckets
        ):
            raise ValueError("capability_inventory_external_digest_mismatch")

        entries = {row.source_family_ref: row for row in catalog.entries}
        for bucket in self.local_buckets:
            entry = entries.get(bucket.source_family_ref)
            if entry is None or "local_candidate" not in entry.supported_route_kinds:
                raise ValueError("capability_inventory_local_family_not_supported")
            if not set(bucket.branch_refs).issubset(entry.coverage_obligation_ids):
                raise ValueError("capability_inventory_local_branch_family_mismatch")
            if not set(bucket.authority_refs).intersection(entry.authority_refs):
                raise ValueError("capability_inventory_local_authority_mismatch")
            if not set(bucket.semantic_role_refs).issubset(entry.semantic_role_refs):
                raise ValueError("capability_inventory_local_semantic_role_mismatch")
        for row in self.reviewed_evidence_index.rows:
            entry = entries.get(row.source_family_ref)
            if entry is None or "reviewed_evidence" not in entry.supported_route_kinds:
                raise ValueError("capability_inventory_reviewed_family_not_supported")
            if not set(row.minimum_route_eligible_branch_ids).issubset(
                entry.coverage_obligation_ids
            ):
                raise ValueError("capability_inventory_reviewed_branch_family_mismatch")
        for bucket in self.external_buckets:
            entry = entries.get(bucket.source_family_ref)
            if entry is None or "external_source" not in entry.supported_route_kinds:
                raise ValueError("capability_inventory_external_family_not_supported")
            if bucket.foundation_required_family_match and not set(
                bucket.coverage_obligation_ids
            ).issubset(entry.coverage_obligation_ids):
                raise ValueError("capability_inventory_external_branch_family_mismatch")

        bucket_ids = tuple(
            row.bucket_id
            for row in (*self.local_buckets, *self.s2_buckets, *self.external_buckets)
        )
        _require_unique(bucket_ids, "capability_inventory_bucket_id_duplicate")
        _verify_digest(
            self,
            "inventory_snapshot_digest",
            "capability_inventory_snapshot_digest_mismatch",
        )
        return self


def _bucket_body(records: Sequence[LocalInventoryRecord]) -> dict[str, Any]:
    first = records[0]
    object_refs = tuple(sorted(record.object_ref for record in records))
    return {
        "bucket_id": f"local-bucket/{canonical_digest(object_refs)[:24]}",
        "source_family_ref": first.source_family_ref,
        "branch_refs": first.branch_refs,
        "entity_refs": first.entity_refs,
        "canonical_issuer_id": first.canonical_issuer_id,
        "period_refs": first.period_refs,
        "fiscal_period": first.fiscal_period,
        "semantic_role_refs": first.semantic_role_refs,
        "source_role": first.source_role,
        "route_id": first.route_id,
        "lane": first.lane,
        "content_surface_refs": first.content_surface_refs,
        "authority_refs": first.authority_refs,
        "source_artifact_digest": first.source_artifact_digest,
        "eligible_object_count": len(records),
        "object_identity_digest": canonical_digest({"object_refs": object_refs}),
    }


def build_local_inventory_buckets(
    records: Sequence[LocalInventoryRecord],
    *,
    catalog: SourceFamilyCatalog,
    expected_source_artifact_digest: Digest,
) -> tuple[LocalInventoryBucket, ...]:
    """Group exact co-occurring metadata rows without constructing cross-products."""

    validated_catalog = SourceFamilyCatalog.model_validate(catalog.model_dump(mode="python"))
    entries = {row.source_family_ref: row for row in validated_catalog.entries}
    groups: dict[tuple[Any, ...], list[LocalInventoryRecord]] = defaultdict(list)
    seen_objects: set[str] = set()
    for raw in records:
        record = LocalInventoryRecord.model_validate(raw.model_dump(mode="python"))
        if record.object_ref in seen_objects:
            raise SourceFamilyCompilerError("local_inventory_object_duplicate")
        seen_objects.add(record.object_ref)
        if record.source_artifact_digest != expected_source_artifact_digest:
            raise SourceFamilyCompilerError("local_inventory_source_digest_mismatch")
        entry = entries.get(record.source_family_ref)
        if entry is None or "local_candidate" not in entry.supported_route_kinds:
            raise SourceFamilyCompilerError("local_inventory_source_family_unmapped")
        if not set(record.branch_refs).issubset(entry.coverage_obligation_ids):
            raise SourceFamilyCompilerError("local_inventory_branch_family_mismatch")
        key = (
            record.source_family_ref,
            record.branch_refs,
            record.entity_refs,
            record.canonical_issuer_id,
            record.period_refs,
            record.fiscal_period,
            record.semantic_role_refs,
            record.source_role,
            record.route_id,
            record.lane,
            record.content_surface_refs,
            record.authority_refs,
            record.source_artifact_digest,
        )
        groups[key].append(record)

    buckets: list[LocalInventoryBucket] = []
    for key in sorted(groups, key=repr):
        body = _bucket_body(groups[key])
        buckets.append(
            LocalInventoryBucket(
                **body,
                bucket_digest=canonical_digest(body),
            )
        )
    return tuple(sorted(buckets, key=lambda item: item.bucket_id))


def build_capability_inventory_snapshot(
    *,
    snapshot_id: str,
    catalog: SourceFamilyCatalog,
    component_bindings: Sequence[CapabilityArtifactBinding],
    local_records: Sequence[LocalInventoryRecord],
    reviewed_evidence_index: ReviewedEvidenceIndexV1_2,
    s2_buckets: Sequence[S2CapabilityBucket],
    external_buckets: Sequence[ExternalInventoryBucket],
) -> CapabilityInventorySnapshot:
    """Build a snapshot only from explicit, previously verified metadata inputs."""

    validated_catalog = SourceFamilyCatalog.model_validate(catalog.model_dump(mode="python"))
    bindings = tuple(
        sorted(
            (
                CapabilityArtifactBinding.model_validate(row.model_dump(mode="python"))
                for row in component_bindings
            ),
            key=lambda row: row.capability_kind,
        )
    )
    binding_by_kind = {row.capability_kind: row for row in bindings}
    if set(binding_by_kind) != {
        "local_candidate",
        "reviewed_evidence",
        "s2_numeric_fact",
        "external_source",
    }:
        raise SourceFamilyCompilerError("capability_inventory_component_binding_incomplete")
    local_buckets = build_local_inventory_buckets(
        local_records,
        catalog=validated_catalog,
        expected_source_artifact_digest=binding_by_kind[
            "local_candidate"
        ].artifact_digest,
    )
    reviewed_index = ReviewedEvidenceIndexV1_2.model_validate(
        reviewed_evidence_index.model_dump(mode="python")
    )
    s2_rows = tuple(sorted(s2_buckets, key=lambda row: row.bucket_id))
    external_rows = tuple(sorted(external_buckets, key=lambda row: row.bucket_id))
    body = {
        "contract_version": "1.2",
        "snapshot_id": snapshot_id,
        "case_id": validated_catalog.case_id,
        "case_version": validated_catalog.case_version,
        "research_as_of": validated_catalog.research_as_of,
        "foundation_digest": validated_catalog.foundation_digest,
        "source_family_catalog": validated_catalog,
        "component_bindings": bindings,
        "local_buckets": local_buckets,
        "reviewed_evidence_index": reviewed_index,
        "s2_buckets": s2_rows,
        "external_buckets": external_rows,
        "local_candidate_count": sum(
            row.eligible_object_count for row in local_buckets
        ),
        "reviewed_evidence_count": reviewed_index.indexed_item_count,
        "s2_observation_count": sum(
            row.eligible_observation_count for row in s2_rows
        ),
        "external_object_count": sum(
            row.eligible_object_count for row in external_rows
        ),
        "answer_free": True,
    }
    return CapabilityInventorySnapshot(
        **body,
        inventory_snapshot_digest=canonical_digest(body),
    )


class CoverageSourceFamilyRequirement(_StrictFrozenModel):
    coverage_obligation_id: str = Field(pattern=_REF_PATTERN)
    required_source_family_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    requirement_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_requirement(self) -> "CoverageSourceFamilyRequirement":
        _require_unique(
            self.required_source_family_refs,
            "baseline_source_family_requirement_duplicate",
        )
        expected = _REQUIRED_FAMILY_MAP.get(self.coverage_obligation_id)
        if expected is None or self.required_source_family_refs != expected:
            raise ValueError("baseline_source_family_requirement_authority_mismatch")
        _verify_digest(
            self,
            "requirement_digest",
            "baseline_source_family_requirement_digest_mismatch",
        )
        return self


class HostOwnedBaselineSourcePlan(_StrictFrozenModel):
    """Authority wrapper that BaselineSourcePlan cannot self-issue."""

    contract_version: Literal["1.2"] = "1.2"
    authority_ref: str = Field(pattern=_REF_PATTERN)
    foundation_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    source_family_requirements: tuple[CoverageSourceFamilyRequirement, ...] = Field(
        min_length=9, max_length=9
    )
    source_plan: BaselineSourcePlan
    authority_binding_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_authority(self) -> "HostOwnedBaselineSourcePlan":
        coverage = tuple(
            row.coverage_obligation_id for row in self.source_family_requirements
        )
        if coverage != DELL_COVERAGE_OBLIGATION_IDS:
            raise ValueError("host_baseline_coverage_order_mismatch")
        plan = self.source_plan
        if plan.inventory_snapshot_digest != self.inventory_snapshot_digest:
            raise ValueError("host_baseline_inventory_binding_mismatch")
        _validate_exact_required_source_families(plan.route_obligations)
        _verify_digest(
            self,
            "authority_binding_digest",
            "host_baseline_authority_binding_digest_mismatch",
        )
        return self


def _validate_exact_required_source_families(
    route_obligations: Sequence[MinimumRouteObligation],
) -> None:
    actual: dict[str, set[str]] = {
        coverage_id: set() for coverage_id in DELL_COVERAGE_OBLIGATION_IDS
    }
    for route in route_obligations:
        if route.requirement != "required":
            continue
        if _document_route_kind(route.route_kind) is None:
            continue
        actual[route.coverage_obligation_id].update(route.semantic_source_family_refs)
    for coverage_id, expected in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE:
        if actual[coverage_id] != set(expected):
            raise SourceFamilyCompilerError(
                f"baseline_required_source_family_mismatch:{coverage_id}"
            )


def _build_coverage_requirements() -> tuple[CoverageSourceFamilyRequirement, ...]:
    rows: list[CoverageSourceFamilyRequirement] = []
    for coverage_id, family_refs in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE:
        body = {
            "coverage_obligation_id": coverage_id,
            "required_source_family_refs": family_refs,
        }
        rows.append(
            CoverageSourceFamilyRequirement(
                **body, requirement_digest=canonical_digest(body)
            )
        )
    return tuple(rows)


def build_host_owned_baseline_source_plan(
    *,
    authority_ref: str,
    source_plan_id: str,
    inventory: CapabilityInventorySnapshot,
    route_obligations: Sequence[MinimumRouteObligation],
    policy_digest: Digest,
) -> HostOwnedBaselineSourcePlan:
    """Build and authority-bind the exact Dell Q1-Q9 answer-free source plan."""

    current = CapabilityInventorySnapshot.model_validate(
        inventory.model_dump(mode="python")
    )
    routes = tuple(route_obligations)
    _validate_exact_required_source_families(routes)
    entries = {
        row.source_family_ref: row for row in current.source_family_catalog.entries
    }
    for route in routes:
        kind = _document_route_kind(route.route_kind)
        if kind is None:
            continue
        for family_ref in route.semantic_source_family_refs:
            entry = entries.get(family_ref)
            if (
                entry is None
                or route.coverage_obligation_id not in entry.coverage_obligation_ids
                or kind not in entry.supported_route_kinds
            ):
                raise SourceFamilyCompilerError(
                    "baseline_route_not_supported_by_current_catalog"
                )

    plan_body = {
        "contract_version": "1.2",
        "source_plan_id": source_plan_id,
        "case_id": current.case_id,
        "case_version": current.case_version,
        "research_as_of": current.research_as_of,
        "coverage_obligation_ids": DELL_COVERAGE_OBLIGATION_IDS,
        "route_obligations": routes,
        "inventory_snapshot_digest": current.inventory_snapshot_digest,
        "catalog_digest": current.source_family_catalog.catalog_digest,
        "policy_digest": policy_digest,
        "answer_free": True,
    }
    plan = BaselineSourcePlan(
        **plan_body,
        source_plan_digest=canonical_digest(plan_body),
    )
    requirements = _build_coverage_requirements()
    authority_body = {
        "contract_version": "1.2",
        "authority_ref": authority_ref,
        "foundation_digest": current.foundation_digest,
        "inventory_snapshot_digest": current.inventory_snapshot_digest,
        "source_family_requirements": requirements,
        "source_plan": plan,
    }
    return HostOwnedBaselineSourcePlan(
        **authority_body,
        authority_binding_digest=canonical_digest(authority_body),
    )


def validate_host_owned_baseline_source_plan(
    authority: HostOwnedBaselineSourcePlan,
    *,
    current_inventory: CapabilityInventorySnapshot,
    expected_foundation_digest: Digest,
) -> HostOwnedBaselineSourcePlan:
    """Reject a self-signed, stale, or differently sourced baseline plan."""

    resolved = HostOwnedBaselineSourcePlan.model_validate(
        authority.model_dump(mode="python")
    )
    current = CapabilityInventorySnapshot.model_validate(
        current_inventory.model_dump(mode="python")
    )
    if (
        resolved.foundation_digest != expected_foundation_digest
        or current.foundation_digest != expected_foundation_digest
    ):
        raise SourceFamilyCompilerError("host_baseline_foundation_digest_stale")
    if resolved.inventory_snapshot_digest != current.inventory_snapshot_digest:
        raise SourceFamilyCompilerError("host_baseline_inventory_digest_stale")
    if (
        resolved.source_plan.case_id != current.case_id
        or resolved.source_plan.case_version != current.case_version
        or resolved.source_plan.research_as_of != current.research_as_of
    ):
        raise SourceFamilyCompilerError("host_baseline_case_binding_stale")
    if (
        resolved.source_plan.catalog_digest
        != current.source_family_catalog.catalog_digest
    ):
        raise SourceFamilyCompilerError("host_baseline_catalog_digest_stale")
    return resolved


class LocalCandidateRetrievalScope(_StrictFrozenModel):
    """One exact executable local scope derived from one co-occurrence bucket."""

    contract_version: Literal["1.2"] = "1.2"
    scope_id: str = Field(pattern=_REF_PATTERN)
    branch_id: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_id: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    query: str = Field(min_length=3, max_length=4_000)
    purpose: str = Field(min_length=8, max_length=2_000)
    search_limit: int = Field(ge=1, le=32)
    matched_entity_refs: tuple[str, ...] = Field(default=(), max_length=16)
    issuer_ids: tuple[str, ...] = Field(min_length=1, max_length=8)
    fiscal_periods: tuple[str, ...] = Field(default=(), max_length=8)
    source_roles: tuple[str, ...] = Field(min_length=1, max_length=8)
    route_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    lanes: tuple[LocalLane, ...] = Field(min_length=1, max_length=2)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    eligible_object_count: int = Field(ge=1, le=10_000_000)
    source_bucket_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    candidate_is_not_evidence: Literal[True] = True
    tool_call_authorized: Literal[True] = True
    scope_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_scope(self) -> "LocalCandidateRetrievalScope":
        for name in (
            "matched_entity_refs",
            "issuer_ids",
            "fiscal_periods",
            "source_roles",
            "route_ids",
            "lanes",
            "authority_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"compiled_local_scope_{name}_duplicate"
            )
        _verify_digest(self, "scope_digest", "compiled_local_scope_digest_mismatch")
        return self


class CompiledReviewedEvidenceTarget(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    target_ref: str = Field(pattern=_REF_PATTERN)
    case_key: str = Field(pattern=_REF_PATTERN)
    branch_id: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_id: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    query: str = Field(min_length=3, max_length=4_000)
    purpose: str = Field(min_length=8, max_length=2_000)
    entity_refs: tuple[str, ...] = Field(default=(), max_length=16)
    period_intents: tuple[str, ...] = Field(default=(), max_length=16)
    topic_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    evidence_role_refs: tuple[str, ...] = Field(default=(), max_length=16)
    minimum_authority_tier: Literal["reviewed", "primary", "any_reviewed"]
    search_limit: int = Field(ge=1, le=32)
    strict_eligible_item_count: int = Field(ge=1, le=1_000_000)
    reviewed_index_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    tool_call_authorized: Literal[True] = True
    target_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_target(self) -> "CompiledReviewedEvidenceTarget":
        for name in (
            "entity_refs",
            "period_intents",
            "topic_refs",
            "evidence_role_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"compiled_reviewed_{name}_duplicate"
            )
        _verify_digest(self, "target_digest", "compiled_reviewed_target_digest_mismatch")
        return self


class CompiledExternalSourceTarget(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    target_ref: str = Field(pattern=_REF_PATTERN)
    branch_id: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_id: str = Field(pattern=_REF_PATTERN)
    source_family_ref: str = Field(pattern=_REF_PATTERN)
    external_route_ref: str = Field(pattern=_REF_PATTERN)
    query: str = Field(min_length=3, max_length=4_000)
    purpose: str = Field(min_length=8, max_length=2_000)
    entity_refs: tuple[str, ...] = Field(default=(), max_length=16)
    period_intents: tuple[str, ...] = Field(default=(), max_length=16)
    domain_allowlist: tuple[str, ...] = Field(default=(), max_length=64)
    published_not_before: str | None = Field(default=None, min_length=10, max_length=10)
    published_not_after: str | None = Field(default=None, min_length=10, max_length=10)
    authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    eligible_object_count: int = Field(ge=1, le=1_000_000)
    source_bucket_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    tool_call_authorized: Literal[True] = True
    target_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_target(self) -> "CompiledExternalSourceTarget":
        for name in (
            "entity_refs",
            "period_intents",
            "domain_allowlist",
            "authority_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"compiled_external_{name}_duplicate"
            )
        _verify_digest(self, "target_digest", "compiled_external_target_digest_mismatch")
        return self


class SourceFamilyCompilationCorrection(_StrictFrozenModel):
    severity: Literal["blocking", "residual"]
    correction_code: str = Field(pattern=_REF_PATTERN)
    message: str = Field(min_length=8, max_length=1_000)
    source_family_refs: tuple[str, ...] = Field(default=(), max_length=32)
    entity_refs: tuple[str, ...] = Field(default=(), max_length=16)
    period_intents: tuple[str, ...] = Field(default=(), max_length=16)
    available_refs: tuple[str, ...] = Field(default=(), max_length=64)
    next_action: Literal[
        "request_data_inventory",
        "request_deeper_inventory",
        "correct_period_intent",
        "replace_source_family_ref",
        "choose_qualified_alternative_route",
        "submit_plan_delta",
        "pause",
    ]
    answer_free: Literal[True] = True
    correction_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_correction(self) -> "SourceFamilyCompilationCorrection":
        for name in (
            "source_family_refs",
            "entity_refs",
            "period_intents",
            "available_refs",
        ):
            _require_sorted_unique(
                tuple(getattr(self, name)), f"source_compilation_{name}_duplicate"
            )
        _verify_digest(
            self, "correction_digest", "source_compilation_correction_digest_mismatch"
        )
        return self


class SourceFamilyCompilationReceipt(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    compilation_receipt_id: str = Field(pattern=_REF_PATTERN)
    intent_kind: Literal["reviewed_evidence", "local_evidence", "external_source"]
    disposition: CompilationDisposition
    branch_id: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_id: str = Field(pattern=_REF_PATTERN)
    minimum_route_obligation_id: str = Field(pattern=_REF_PATTERN)
    minimum_route_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    baseline_source_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    expected_inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    intent_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    task_authority_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    local_scopes: tuple[LocalCandidateRetrievalScope, ...] = Field(
        default=(), max_length=256
    )
    reviewed_targets: tuple[CompiledReviewedEvidenceTarget, ...] = Field(
        default=(), max_length=64
    )
    external_targets: tuple[CompiledExternalSourceTarget, ...] = Field(
        default=(), max_length=64
    )
    corrections: tuple[SourceFamilyCompilationCorrection, ...] = Field(
        default=(), max_length=64
    )
    eligible_object_count: int = Field(ge=0, le=10_000_000)
    tool_call_authorized: bool
    answer_free: Literal[True] = True
    receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> "SourceFamilyCompilationReceipt":
        _require_sorted_unique(
            self.task_authority_refs, "source_compilation_task_authority_duplicate"
        )
        target_groups = (
            bool(self.local_scopes),
            bool(self.reviewed_targets),
            bool(self.external_targets),
        )
        expected_group = {
            "local_evidence": 0,
            "reviewed_evidence": 1,
            "external_source": 2,
        }[self.intent_kind]
        if any(value for index, value in enumerate(target_groups) if index != expected_group):
            raise ValueError("source_compilation_lane_mixing_forbidden")
        calculated_count = (
            sum(row.eligible_object_count for row in self.local_scopes)
            + sum(row.strict_eligible_item_count for row in self.reviewed_targets)
            + sum(row.eligible_object_count for row in self.external_targets)
        )
        if calculated_count != self.eligible_object_count:
            raise ValueError("source_compilation_eligible_count_mismatch")
        if self.disposition == "rejected":
            if self.tool_call_authorized or calculated_count or any(target_groups):
                raise ValueError("rejected_compilation_authorized_tool_call")
            if not self.corrections or any(
                row.severity != "blocking" for row in self.corrections
            ):
                raise ValueError("rejected_compilation_blocking_correction_required")
        else:
            if not self.tool_call_authorized or calculated_count < 1:
                raise ValueError("accepted_compilation_requires_nonzero_authorized_target")
            if not target_groups[expected_group]:
                raise ValueError("accepted_compilation_target_missing")
            has_residual = any(row.severity == "residual" for row in self.corrections)
            if (self.disposition == "accepted_with_residual_feedback") != has_residual:
                raise ValueError("source_compilation_residual_disposition_mismatch")
            if any(row.severity == "blocking" for row in self.corrections):
                raise ValueError("accepted_compilation_has_blocking_correction")
        _verify_digest(self, "receipt_digest", "source_compilation_receipt_digest_mismatch")
        return self


def _correction(
    *,
    severity: Literal["blocking", "residual"],
    code: str,
    message: str,
    next_action: Literal[
        "request_data_inventory",
        "request_deeper_inventory",
        "correct_period_intent",
        "replace_source_family_ref",
        "choose_qualified_alternative_route",
        "submit_plan_delta",
        "pause",
    ],
    source_family_refs: Iterable[str] = (),
    entity_refs: Iterable[str] = (),
    period_intents: Iterable[str] = (),
    available_refs: Iterable[str] = (),
) -> SourceFamilyCompilationCorrection:
    body = {
        "severity": severity,
        "correction_code": code,
        "message": message,
        "source_family_refs": tuple(sorted(set(source_family_refs))),
        "entity_refs": tuple(sorted(set(entity_refs))),
        "period_intents": tuple(sorted(set(period_intents))),
        "available_refs": tuple(sorted(set(available_refs))),
        "next_action": next_action,
        "answer_free": True,
    }
    return SourceFamilyCompilationCorrection(
        **body, correction_digest=canonical_digest(body)
    )


def _receipt(
    *,
    compilation_receipt_id: str,
    intent_kind: Literal["reviewed_evidence", "local_evidence", "external_source"],
    disposition: CompilationDisposition,
    branch_id: str,
    route: MinimumRouteObligation,
    baseline: HostOwnedBaselineSourcePlan,
    expected_inventory_snapshot_digest: Digest,
    inventory: CapabilityInventorySnapshot,
    intent_digest: Digest,
    task_authority_refs: tuple[str, ...],
    local_scopes: tuple[LocalCandidateRetrievalScope, ...] = (),
    reviewed_targets: tuple[CompiledReviewedEvidenceTarget, ...] = (),
    external_targets: tuple[CompiledExternalSourceTarget, ...] = (),
    corrections: tuple[SourceFamilyCompilationCorrection, ...] = (),
) -> SourceFamilyCompilationReceipt:
    eligible_count = (
        sum(row.eligible_object_count for row in local_scopes)
        + sum(row.strict_eligible_item_count for row in reviewed_targets)
        + sum(row.eligible_object_count for row in external_targets)
    )
    body = {
        "contract_version": "1.2",
        "compilation_receipt_id": compilation_receipt_id,
        "intent_kind": intent_kind,
        "disposition": disposition,
        "branch_id": branch_id,
        "coverage_obligation_id": route.coverage_obligation_id,
        "minimum_route_obligation_id": route.route_obligation_id,
        "minimum_route_digest": route.route_digest,
        "baseline_source_plan_digest": baseline.source_plan.source_plan_digest,
        "expected_inventory_snapshot_digest": expected_inventory_snapshot_digest,
        "inventory_snapshot_digest": inventory.inventory_snapshot_digest,
        "intent_digest": intent_digest,
        "task_authority_refs": tuple(sorted(set(task_authority_refs))),
        "local_scopes": local_scopes,
        "reviewed_targets": reviewed_targets,
        "external_targets": external_targets,
        "corrections": corrections,
        "eligible_object_count": eligible_count,
        "tool_call_authorized": disposition != "rejected",
        "answer_free": True,
    }
    return SourceFamilyCompilationReceipt(
        **body, receipt_digest=canonical_digest(body)
    )


def _intent_kind(
    intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent,
) -> Literal["reviewed_evidence", "local_evidence", "external_source"]:
    return intent.intent_kind


def _route_kind_for_intent(
    intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent,
) -> DocumentRouteKind:
    if isinstance(intent, ReviewedEvidenceIntent):
        return "reviewed_evidence"
    if isinstance(intent, LocalEvidenceIntent):
        return "local_candidate"
    return "external_source"


def _row_matches_reviewed_target(
    row: ReviewedEvidenceIndexRowV1_2,
    target: CompiledReviewedEvidenceTarget,
) -> bool:
    if row.metadata_state != "complete":
        return False
    if (
        row.case_key != target.case_key
        or target.coverage_obligation_id
        not in row.minimum_route_eligible_branch_ids
        or row.source_family_ref != target.source_family_ref
    ):
        return False
    if target.entity_refs and not set(target.entity_refs).intersection(row.entity_ids):
        return False
    if target.period_intents and not set(target.period_intents).intersection(
        row.period_refs
    ):
        return False
    if not set(target.topic_refs).intersection(row.topic_refs):
        return False
    if target.evidence_role_refs and row.evidence_role not in target.evidence_role_refs:
        return False
    if not _reviewed_authority_satisfies(
        actual=row.authority_tier,
        minimum=target.minimum_authority_tier,
    ):
        return False
    return True


def _reviewed_authority_satisfies(
    *,
    actual: AuthorityTier,
    minimum: Literal["reviewed", "primary", "any_reviewed"],
) -> bool:
    """Treat primary material as satisfying a reviewed-or-better request."""

    if minimum == "primary":
        return actual == "primary"
    return actual in {"reviewed", "primary"}


class SourceFamilyCompiler:
    """Immutable facade over pure source-family compilation functions."""

    __slots__ = ("_baseline", "_inventory", "_routes")

    def __init__(
        self,
        *,
        inventory: CapabilityInventorySnapshot,
        baseline: HostOwnedBaselineSourcePlan,
    ) -> None:
        self._inventory = CapabilityInventorySnapshot.model_validate(
            inventory.model_dump(mode="python")
        )
        self._baseline = HostOwnedBaselineSourcePlan.model_validate(
            baseline.model_dump(mode="python")
        )
        self._routes = {
            row.route_obligation_id: row
            for row in self._baseline.source_plan.route_obligations
        }

    @property
    def inventory_snapshot_digest(self) -> str:
        return self._inventory.inventory_snapshot_digest

    def compile(
        self,
        intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent,
        *,
        minimum_route_obligation_id: str,
        branch_id: str,
        task_authority_refs: Sequence[str],
        expected_inventory_snapshot_digest: Digest,
        compilation_receipt_id: str,
        maximum_total_eligible_count: int = 2_000,
    ) -> SourceFamilyCompilationReceipt:
        return compile_source_intent(
            intent,
            inventory=self._inventory,
            baseline=self._baseline,
            minimum_route_obligation_id=minimum_route_obligation_id,
            branch_id=branch_id,
            task_authority_refs=task_authority_refs,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            compilation_receipt_id=compilation_receipt_id,
            maximum_total_eligible_count=maximum_total_eligible_count,
        )


def compile_source_intent(
    intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent,
    *,
    inventory: CapabilityInventorySnapshot,
    baseline: HostOwnedBaselineSourcePlan,
    minimum_route_obligation_id: str,
    branch_id: str,
    task_authority_refs: Sequence[str],
    expected_inventory_snapshot_digest: Digest,
    compilation_receipt_id: str,
    maximum_total_eligible_count: int = 2_000,
) -> SourceFamilyCompilationReceipt:
    """Compile one semantic intent or return an answer-free typed correction."""

    current = CapabilityInventorySnapshot.model_validate(
        inventory.model_dump(mode="python")
    )
    authority = HostOwnedBaselineSourcePlan.model_validate(
        baseline.model_dump(mode="python")
    )
    task_authorities = tuple(sorted(set(task_authority_refs)))
    if not task_authorities:
        raise SourceFamilyCompilerError("source_compilation_task_authority_missing")
    if maximum_total_eligible_count < 1:
        raise SourceFamilyCompilerError("source_compilation_cardinality_ceiling_invalid")

    if isinstance(intent, ReviewedEvidenceIntent):
        validated_intent: ReviewedEvidenceIntent | LocalEvidenceIntent | ExternalSourceIntent = (
            ReviewedEvidenceIntent.model_validate(intent.model_dump(mode="python"))
        )
    elif isinstance(intent, LocalEvidenceIntent):
        validated_intent = LocalEvidenceIntent.model_validate(intent.model_dump(mode="python"))
    elif isinstance(intent, ExternalSourceIntent):
        validated_intent = ExternalSourceIntent.model_validate(intent.model_dump(mode="python"))
    else:
        raise SourceFamilyCompilerError("source_compilation_intent_type_invalid")
    kind = _intent_kind(validated_intent)
    intent_digest = canonical_digest(validated_intent)

    route_map = {
        row.route_obligation_id: row
        for row in authority.source_plan.route_obligations
    }
    route = route_map.get(minimum_route_obligation_id)
    if route is None:
        # A structurally valid placeholder is needed only to bind a rejected
        # receipt.  Unknown route IDs are host programming defects, not a model
        # correction, so do not fabricate one.
        raise SourceFamilyCompilerError("minimum_route_obligation_unknown")

    def reject(correction: SourceFamilyCompilationCorrection) -> SourceFamilyCompilationReceipt:
        return _receipt(
            compilation_receipt_id=compilation_receipt_id,
            intent_kind=kind,
            disposition="rejected",
            branch_id=branch_id,
            route=route,
            baseline=authority,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            inventory=current,
            intent_digest=intent_digest,
            task_authority_refs=task_authorities,
            corrections=(correction,),
        )

    if expected_inventory_snapshot_digest != current.inventory_snapshot_digest:
        return reject(
            _correction(
                severity="blocking",
                code="inventory_snapshot_stale",
                message="The requested inventory digest is not the current host snapshot.",
                next_action="request_data_inventory",
            )
        )
    if (
        authority.inventory_snapshot_digest != current.inventory_snapshot_digest
        or authority.foundation_digest != current.foundation_digest
        or authority.source_plan.catalog_digest
        != current.source_family_catalog.catalog_digest
        or authority.source_plan.case_id != current.case_id
        or authority.source_plan.case_version != current.case_version
        or authority.source_plan.research_as_of != current.research_as_of
    ):
        return reject(
            _correction(
                severity="blocking",
                code="baseline_source_plan_stale",
                message="The baseline plan is not bound to the current inventory and foundation.",
                next_action="pause",
            )
        )
    if branch_id != route.coverage_obligation_id:
        return reject(
            _correction(
                severity="blocking",
                code="source_family_branch_mismatch",
                message="The selected minimum route belongs to a different coverage branch.",
                next_action="submit_plan_delta",
                source_family_refs=route.semantic_source_family_refs,
            )
        )
    expected_route_kind = _route_kind_for_intent(validated_intent)
    if route.route_kind != expected_route_kind:
        return reject(
            _correction(
                severity="blocking",
                code="source_lane_mismatch",
                message="The semantic intent and minimum route use different evidence lanes.",
                next_action="choose_qualified_alternative_route",
                source_family_refs=route.semantic_source_family_refs,
            )
        )
    if not set(route.required_authority_refs).issubset(task_authorities):
        return reject(
            _correction(
                severity="blocking",
                code="task_authority_insufficient",
                message="The task lacks the authority required by the minimum source route.",
                next_action="pause",
                available_refs=task_authorities,
            )
        )
    if isinstance(validated_intent, (LocalEvidenceIntent, ExternalSourceIntent)) and (
        set(validated_intent.semantic_source_family_refs)
        != set(route.semantic_source_family_refs)
    ):
        return reject(
            _correction(
                severity="blocking",
                code="minimum_route_source_family_mismatch",
                message="The intent does not preserve every source family required by the route.",
                next_action="replace_source_family_ref",
                source_family_refs=validated_intent.semantic_source_family_refs,
                available_refs=route.semantic_source_family_refs,
            )
        )

    if isinstance(validated_intent, LocalEvidenceIntent):
        return _compile_local(
            validated_intent,
            inventory=current,
            baseline=authority,
            route=route,
            branch_id=branch_id,
            task_authority_refs=task_authorities,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            compilation_receipt_id=compilation_receipt_id,
            maximum_total_eligible_count=maximum_total_eligible_count,
        )
    if isinstance(validated_intent, ReviewedEvidenceIntent):
        return _compile_reviewed(
            validated_intent,
            inventory=current,
            baseline=authority,
            route=route,
            branch_id=branch_id,
            task_authority_refs=task_authorities,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            compilation_receipt_id=compilation_receipt_id,
        )
    return _compile_external(
        validated_intent,
        inventory=current,
        baseline=authority,
        route=route,
        branch_id=branch_id,
        task_authority_refs=task_authorities,
        expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
        compilation_receipt_id=compilation_receipt_id,
        maximum_total_eligible_count=maximum_total_eligible_count,
    )


def _compile_local(
    intent: LocalEvidenceIntent,
    *,
    inventory: CapabilityInventorySnapshot,
    baseline: HostOwnedBaselineSourcePlan,
    route: MinimumRouteObligation,
    branch_id: str,
    task_authority_refs: tuple[str, ...],
    expected_inventory_snapshot_digest: Digest,
    compilation_receipt_id: str,
    maximum_total_eligible_count: int,
) -> SourceFamilyCompilationReceipt:
    required_families = set(route.semantic_source_family_refs)
    required_authorities = set(route.required_authority_refs)
    entries = {
        row.source_family_ref: row for row in inventory.source_family_catalog.entries
    }
    corrections: list[SourceFamilyCompilationCorrection] = []
    selected: list[LocalInventoryBucket] = []
    missing_families: set[str] = set()

    for family_ref in sorted(required_families):
        entry = entries.get(family_ref)
        family_rows = [
            row
            for row in inventory.local_buckets
            if row.source_family_ref == family_ref and branch_id in row.branch_refs
        ]
        if (
            entry is None
            or "local_candidate" not in entry.supported_route_kinds
            or not family_rows
        ):
            missing_families.add(family_ref)
            continue
        authority_rows = [
            row
            for row in family_rows
            if required_authorities.issubset(row.authority_refs)
        ]
        if not authority_rows:
            missing_families.add(family_ref)
            continue

        rows = authority_rows
        if intent.entity_refs:
            requested = set(intent.entity_refs)
            rows = [row for row in rows if requested.intersection(row.entity_refs)]
        if intent.period_intents:
            requested_periods = set(intent.period_intents)
            rows = [
                row for row in rows if requested_periods.intersection(row.period_refs)
            ]
        if intent.source_role_intents:
            # Provider-visible values are semantic source-role intents.
            # Physical source_role and access authority remain separate host
            # outputs and must never be overloaded to satisfy this filter.
            requested_roles = set(intent.source_role_intents)
            rows = [
                row
                for row in rows
                if requested_roles.intersection(row.semantic_role_refs)
            ]
        requested_surfaces = set(intent.content_surface_intents)
        rows = [
            row
            for row in rows
            if requested_surfaces.intersection(row.content_surface_refs)
        ]
        if not rows:
            missing_families.add(family_ref)
            continue
        family_count = sum(row.eligible_object_count for row in rows)
        ceiling = entry.local_cardinality_ceiling
        if ceiling is None or family_count > ceiling:
            return _receipt(
                compilation_receipt_id=compilation_receipt_id,
                intent_kind="local_evidence",
                disposition="rejected",
                branch_id=branch_id,
                route=route,
                baseline=baseline,
                expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
                inventory=inventory,
                intent_digest=canonical_digest(intent),
                task_authority_refs=task_authority_refs,
                corrections=(
                    _correction(
                        severity="blocking",
                        code="local_scope_cardinality_exceeded",
                        message="The compiled family scope exceeds its frozen cardinality ceiling.",
                        next_action="request_deeper_inventory",
                        source_family_refs=(family_ref,),
                    ),
                ),
            )
        selected.extend(rows)

    # Residuals are calculated across all retained families.  This matters for
    # requests such as F4 comparators: one entity may be absent from one family
    # bucket but present in another valid retained scope.
    unmatched_entities = set(intent.entity_refs) - {
        ref for row in selected for ref in set(intent.entity_refs).intersection(row.entity_refs)
    }
    unmatched_periods = set(intent.period_intents) - {
        ref
        for row in selected
        for ref in set(intent.period_intents).intersection(row.period_refs)
    }
    unmatched_roles = set(intent.source_role_intents) - {
        ref
        for row in selected
        for ref in set(intent.source_role_intents).intersection(
            row.semantic_role_refs
        )
    }
    unmatched_surfaces = set(intent.content_surface_intents) - {
        ref
        for row in selected
        for ref in set(intent.content_surface_intents).intersection(
            row.content_surface_refs
        )
    }

    if not selected:
        if unmatched_entities:
            code, action = "local_entity_scope_zero", "request_data_inventory"
        elif unmatched_periods:
            code, action = "local_period_scope_zero", "correct_period_intent"
        elif unmatched_roles:
            code, action = "local_source_role_scope_zero", "request_data_inventory"
        elif unmatched_surfaces:
            code, action = "local_content_surface_scope_zero", "request_deeper_inventory"
        else:
            code, action = "local_source_family_scope_zero", "replace_source_family_ref"
        return _receipt(
            compilation_receipt_id=compilation_receipt_id,
            intent_kind="local_evidence",
            disposition="rejected",
            branch_id=branch_id,
            route=route,
            baseline=baseline,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            inventory=inventory,
            intent_digest=canonical_digest(intent),
            task_authority_refs=task_authority_refs,
            corrections=(
                _correction(
                    severity="blocking",
                    code=code,
                    message="No current local object satisfies the exact compiled metadata scope.",
                    next_action=action,
                    source_family_refs=required_families,
                    entity_refs=unmatched_entities,
                    period_intents=unmatched_periods,
                ),
            ),
        )

    selected_count = sum(row.eligible_object_count for row in selected)
    if selected_count > maximum_total_eligible_count:
        return _receipt(
            compilation_receipt_id=compilation_receipt_id,
            intent_kind="local_evidence",
            disposition="rejected",
            branch_id=branch_id,
            route=route,
            baseline=baseline,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            inventory=inventory,
            intent_digest=canonical_digest(intent),
            task_authority_refs=task_authority_refs,
            corrections=(
                _correction(
                    severity="blocking",
                    code="local_total_cardinality_exceeded",
                    message="The compiled local scope exceeds the task cardinality ceiling.",
                    next_action="request_deeper_inventory",
                    source_family_refs=required_families,
                ),
            ),
        )

    inventory_families = {row.source_family_ref for row in inventory.local_buckets}
    unbounded_intent = not (
        intent.entity_refs or intent.period_intents or intent.source_role_intents
    )
    if (
        unbounded_intent
        and required_families == inventory_families
        and selected_count == inventory.local_candidate_count
        and len(inventory_families) > 1
    ):
        return _receipt(
            compilation_receipt_id=compilation_receipt_id,
            intent_kind="local_evidence",
            disposition="rejected",
            branch_id=branch_id,
            route=route,
            baseline=baseline,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            inventory=inventory,
            intent_digest=canonical_digest(intent),
            task_authority_refs=task_authority_refs,
            corrections=(
                _correction(
                    severity="blocking",
                    code="whole_corpus_selector_forbidden",
                    message="An unbounded selector that resolves to the whole corpus is forbidden.",
                    next_action="request_deeper_inventory",
                    source_family_refs=required_families,
                ),
            ),
        )

    scopes: list[LocalCandidateRetrievalScope] = []
    for index, bucket in enumerate(sorted(selected, key=lambda row: row.bucket_id), start=1):
        body = {
            "contract_version": "1.2",
            "scope_id": f"{compilation_receipt_id}/local/{index}",
            "branch_id": branch_id,
            "coverage_obligation_id": route.coverage_obligation_id,
            "source_family_ref": bucket.source_family_ref,
            "query": intent.query,
            "purpose": intent.purpose,
            "search_limit": intent.limit,
            "matched_entity_refs": tuple(
                sorted(set(intent.entity_refs).intersection(bucket.entity_refs))
            ),
            "issuer_ids": (bucket.canonical_issuer_id,),
            "fiscal_periods": (
                (bucket.fiscal_period,) if bucket.fiscal_period is not None else ()
            ),
            "source_roles": (bucket.source_role,),
            "route_ids": (bucket.route_id,),
            "lanes": (bucket.lane,),
            "authority_refs": tuple(sorted(required_authorities)),
            "eligible_object_count": bucket.eligible_object_count,
            "source_bucket_digest": bucket.bucket_digest,
            "inventory_snapshot_digest": inventory.inventory_snapshot_digest,
            "candidate_is_not_evidence": True,
            "tool_call_authorized": True,
        }
        scopes.append(
            LocalCandidateRetrievalScope(
                **body, scope_digest=canonical_digest(body)
            )
        )

    if missing_families:
        corrections.append(
            _correction(
                severity="residual",
                code="local_source_family_residual",
                message="Some required source families have no compatible current local scope.",
                next_action="choose_qualified_alternative_route",
                source_family_refs=missing_families,
            )
        )
    if unmatched_entities:
        corrections.append(
            _correction(
                severity="residual",
                code="local_entity_residual",
                message="Some requested entities are absent while other requested entities remain executable.",
                next_action="choose_qualified_alternative_route",
                entity_refs=unmatched_entities,
            )
        )
    if unmatched_periods:
        corrections.append(
            _correction(
                severity="residual",
                code="local_period_residual",
                message="Some requested periods are absent while another requested period remains executable.",
                next_action="correct_period_intent",
                period_intents=unmatched_periods,
            )
        )
    if unmatched_roles or unmatched_surfaces:
        corrections.append(
            _correction(
                severity="residual",
                code="local_role_or_surface_residual",
                message="Some requested roles or content surfaces are unavailable in the retained scopes.",
                next_action="request_deeper_inventory",
                available_refs=unmatched_roles | unmatched_surfaces,
            )
        )
    disposition: CompilationDisposition = (
        "accepted_with_residual_feedback" if corrections else "accepted"
    )
    return _receipt(
        compilation_receipt_id=compilation_receipt_id,
        intent_kind="local_evidence",
        disposition=disposition,
        branch_id=branch_id,
        route=route,
        baseline=baseline,
        expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
        inventory=inventory,
        intent_digest=canonical_digest(intent),
        task_authority_refs=task_authority_refs,
        local_scopes=tuple(scopes),
        corrections=tuple(corrections),
    )


def _compile_reviewed(
    intent: ReviewedEvidenceIntent,
    *,
    inventory: CapabilityInventorySnapshot,
    baseline: HostOwnedBaselineSourcePlan,
    route: MinimumRouteObligation,
    branch_id: str,
    task_authority_refs: tuple[str, ...],
    expected_inventory_snapshot_digest: Digest,
    compilation_receipt_id: str,
) -> SourceFamilyCompilationReceipt:
    index = inventory.reviewed_evidence_index
    targets: list[CompiledReviewedEvidenceTarget] = []
    missing_families: set[str] = set()
    unmatched_entities: set[str] = set(intent.entity_refs)
    unmatched_periods: set[str] = set(intent.period_intents)
    for family_ref in sorted(route.semantic_source_family_refs):
        rows = [
            row
            for row in index.rows
            if row.metadata_state == "complete"
            and row.source_family_ref == family_ref
            and branch_id in row.minimum_route_eligible_branch_ids
            and (
                not intent.entity_refs
                or set(intent.entity_refs).intersection(row.entity_ids)
            )
            and (
                not intent.period_intents
                or set(intent.period_intents).intersection(row.period_refs)
            )
            and set(intent.topic_refs).intersection(row.topic_refs)
            and (
                not intent.evidence_role_refs
                or row.evidence_role in intent.evidence_role_refs
            )
            and (
                _reviewed_authority_satisfies(
                    actual=row.authority_tier,
                    minimum=intent.minimum_authority_tier,
                )
            )
        ]
        if not rows:
            missing_families.add(family_ref)
            continue
        for row in rows:
            unmatched_entities.difference_update(row.entity_ids)
            unmatched_periods.difference_update(row.period_refs)
        body = {
            "contract_version": "1.2",
            "target_ref": f"{compilation_receipt_id}/reviewed/{len(targets) + 1}",
            "case_key": index.case_key,
            "branch_id": branch_id,
            "coverage_obligation_id": route.coverage_obligation_id,
            "source_family_ref": family_ref,
            "query": intent.query,
            "purpose": intent.purpose,
            "entity_refs": tuple(sorted(intent.entity_refs)),
            "period_intents": tuple(sorted(intent.period_intents)),
            "topic_refs": tuple(sorted(intent.topic_refs)),
            "evidence_role_refs": tuple(sorted(intent.evidence_role_refs)),
            "minimum_authority_tier": intent.minimum_authority_tier,
            # The existing Reviewed Evidence MCP reader currently accepts at
            # most 12 hits.  Keep this physical transport bound host-owned;
            # the provider may still request a larger semantic limit without
            # producing an invalid MCP call.
            "search_limit": min(intent.limit, 12),
            "strict_eligible_item_count": len(rows),
            "reviewed_index_digest": index.index_digest,
            "tool_call_authorized": True,
        }
        targets.append(
            CompiledReviewedEvidenceTarget(
                **body, target_digest=canonical_digest(body)
            )
        )

    if not targets:
        correction = _correction(
            severity="blocking",
            code="reviewed_exact_metadata_scope_zero",
            message="No Reviewed Evidence row has complete metadata satisfying the exact intent.",
            next_action="choose_qualified_alternative_route",
            source_family_refs=missing_families or route.semantic_source_family_refs,
            entity_refs=unmatched_entities,
            period_intents=unmatched_periods,
        )
        return _receipt(
            compilation_receipt_id=compilation_receipt_id,
            intent_kind="reviewed_evidence",
            disposition="rejected",
            branch_id=branch_id,
            route=route,
            baseline=baseline,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            inventory=inventory,
            intent_digest=canonical_digest(intent),
            task_authority_refs=task_authority_refs,
            corrections=(correction,),
        )
    corrections: list[SourceFamilyCompilationCorrection] = []
    if missing_families:
        corrections.append(
            _correction(
                severity="residual",
                code="reviewed_source_family_residual",
                message="Some required source families lack strict comparable Reviewed Evidence metadata.",
                next_action="choose_qualified_alternative_route",
                source_family_refs=missing_families,
            )
        )
    if unmatched_entities or unmatched_periods:
        corrections.append(
            _correction(
                severity="residual",
                code="reviewed_entity_or_period_residual",
                message="Some requested entity or period constraints remain unsupported by indexed Evidence.",
                next_action="choose_qualified_alternative_route",
                entity_refs=unmatched_entities,
                period_intents=unmatched_periods,
            )
        )
    return _receipt(
        compilation_receipt_id=compilation_receipt_id,
        intent_kind="reviewed_evidence",
        disposition=(
            "accepted_with_residual_feedback" if corrections else "accepted"
        ),
        branch_id=branch_id,
        route=route,
        baseline=baseline,
        expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
        inventory=inventory,
        intent_digest=canonical_digest(intent),
        task_authority_refs=task_authority_refs,
        reviewed_targets=tuple(targets),
        corrections=tuple(corrections),
    )


def _compile_external(
    intent: ExternalSourceIntent,
    *,
    inventory: CapabilityInventorySnapshot,
    baseline: HostOwnedBaselineSourcePlan,
    route: MinimumRouteObligation,
    branch_id: str,
    task_authority_refs: tuple[str, ...],
    expected_inventory_snapshot_digest: Digest,
    compilation_receipt_id: str,
    maximum_total_eligible_count: int,
) -> SourceFamilyCompilationReceipt:
    required_families = set(route.semantic_source_family_refs)
    required_authorities = set(route.required_authority_refs)
    targets: list[CompiledExternalSourceTarget] = []
    missing_families: set[str] = set()
    matched_domains: set[str] = set()
    unmatched_entities: set[str] = set(intent.entity_refs)
    unmatched_periods: set[str] = set(intent.period_intents)
    requested_domains = set(intent.domain_allowlist)
    requested_entities = set(intent.entity_refs)
    requested_start = (
        _iso_date(intent.published_not_before, "external_intent_start_invalid")
        if intent.published_not_before is not None
        else None
    )
    requested_end = (
        _iso_date(intent.published_not_after, "external_intent_end_invalid")
        if intent.published_not_after is not None
        else None
    )
    for family_ref in sorted(required_families):
        rows = [
            row
            for row in inventory.external_buckets
            if row.source_family_ref == family_ref
            and branch_id in row.coverage_obligation_ids
            and row.foundation_required_family_match
            and required_authorities.issubset(row.authority_refs)
            and (
                not requested_entities
                or requested_entities.intersection(row.entity_refs)
            )
            and (
                not intent.period_intents
                or not row.period_refs
                or set(intent.period_intents).intersection(row.period_refs)
            )
            and (
                requested_start is None
                or row.available_not_after is None
                or _iso_date(row.available_not_after, "external_inventory_end_invalid")
                >= requested_start
            )
            and (
                requested_end is None
                or row.available_not_before is None
                or _iso_date(row.available_not_before, "external_inventory_start_invalid")
                <= requested_end
            )
        ]
        if not rows:
            missing_families.add(family_ref)
            continue
        family_had_target = False
        for row in rows:
            domains = (
                tuple(sorted(requested_domains.intersection(row.domain_allowlist)))
                if requested_domains
                else row.domain_allowlist
            )
            if requested_domains and not domains:
                continue
            unmatched_entities.difference_update(row.entity_refs)
            unmatched_periods.difference_update(row.period_refs)
            matched_domains.update(domains)
            matched_entities = (
                tuple(sorted(requested_entities.intersection(row.entity_refs)))
                if requested_entities
                else row.entity_refs
            )
            body = {
                "contract_version": "1.2",
                "target_ref": f"{compilation_receipt_id}/external/{len(targets) + 1}",
                "branch_id": branch_id,
                "coverage_obligation_id": route.coverage_obligation_id,
                "source_family_ref": family_ref,
                "external_route_ref": row.external_route_ref,
                "query": intent.query,
                "purpose": intent.purpose,
                "entity_refs": matched_entities,
                "period_intents": tuple(sorted(intent.period_intents)),
                "domain_allowlist": domains,
                "published_not_before": intent.published_not_before,
                "published_not_after": intent.published_not_after,
                "authority_refs": tuple(sorted(required_authorities)),
                "eligible_object_count": row.eligible_object_count,
                "source_bucket_digest": row.bucket_digest,
                "inventory_snapshot_digest": inventory.inventory_snapshot_digest,
                "tool_call_authorized": True,
            }
            targets.append(
                CompiledExternalSourceTarget(
                    **body, target_digest=canonical_digest(body)
                )
            )
            family_had_target = True
        if not family_had_target:
            missing_families.add(family_ref)

    unmatched_domains = requested_domains - matched_domains

    eligible_count = sum(row.eligible_object_count for row in targets)
    if not targets or eligible_count > maximum_total_eligible_count:
        return _receipt(
            compilation_receipt_id=compilation_receipt_id,
            intent_kind="external_source",
            disposition="rejected",
            branch_id=branch_id,
            route=route,
            baseline=baseline,
            expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
            inventory=inventory,
            intent_digest=canonical_digest(intent),
            task_authority_refs=task_authority_refs,
            corrections=(
                _correction(
                    severity="blocking",
                    code=(
                        "external_scope_cardinality_exceeded"
                        if targets
                        else "external_source_family_scope_zero"
                    ),
                    message=(
                        "The external target exceeds the current cardinality ceiling."
                        if targets
                        else "No current external route satisfies the semantic intent."
                    ),
                    next_action="choose_qualified_alternative_route",
                    source_family_refs=missing_families or required_families,
                    entity_refs=unmatched_entities,
                    period_intents=unmatched_periods,
                    available_refs=unmatched_domains,
                ),
            ),
        )
    corrections: list[SourceFamilyCompilationCorrection] = []
    if missing_families or unmatched_domains or unmatched_entities or unmatched_periods:
        corrections.append(
            _correction(
                severity="residual",
                code="external_route_residual",
                message="Some requested external families or domains remain unavailable.",
                next_action="choose_qualified_alternative_route",
                source_family_refs=missing_families,
                entity_refs=unmatched_entities,
                period_intents=unmatched_periods,
                available_refs=unmatched_domains,
            )
        )
    return _receipt(
        compilation_receipt_id=compilation_receipt_id,
        intent_kind="external_source",
        disposition=(
            "accepted_with_residual_feedback" if corrections else "accepted"
        ),
        branch_id=branch_id,
        route=route,
        baseline=baseline,
        expected_inventory_snapshot_digest=expected_inventory_snapshot_digest,
        inventory=inventory,
        intent_digest=canonical_digest(intent),
        task_authority_refs=task_authority_refs,
        external_targets=tuple(targets),
        corrections=tuple(corrections),
    )


class ReviewedEvidenceRereadMetadata(_StrictFrozenModel):
    """Metadata returned by the mandatory evidence-ID re-read."""

    evidence_id: str = Field(pattern=_REF_PATTERN)
    item_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    locator_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_tier: AuthorityTier
    source_reporting_period_end: str | None = Field(
        default=None, min_length=10, max_length=10
    )
    reviewed_index_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    reread_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_reread(self) -> "ReviewedEvidenceRereadMetadata":
        if self.source_reporting_period_end is not None:
            _iso_date(
                self.source_reporting_period_end,
                "reviewed_reread_reporting_period_invalid",
            )
        _verify_digest(self, "reread_digest", "reviewed_reread_digest_mismatch")
        return self


class ReviewedEvidenceFilterRejection(_StrictFrozenModel):
    evidence_id: str = Field(pattern=_REF_PATTERN)
    reason: Literal[
        "not_indexed",
        "metadata_insufficient",
        "entity_mismatch",
        "period_mismatch",
        "topic_mismatch",
        "role_mismatch",
        "authority_mismatch",
        "family_or_branch_mismatch",
        "reread_missing",
        "reread_digest_mismatch",
        "reread_locator_mismatch",
        "reread_authority_mismatch",
        "reread_period_mismatch",
        "reread_index_stale",
    ]
    rejection_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_rejection(self) -> "ReviewedEvidenceFilterRejection":
        _verify_digest(
            self, "rejection_digest", "reviewed_filter_rejection_digest_mismatch"
        )
        return self


class ReviewedEvidenceFilterReceipt(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    filter_receipt_id: str = Field(pattern=_REF_PATTERN)
    compiled_target_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    reviewed_index_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    search_hit_ids: tuple[str, ...] = Field(default=(), max_length=256)
    accepted_evidence_ids: tuple[str, ...] = Field(default=(), max_length=256)
    rejections: tuple[ReviewedEvidenceFilterRejection, ...] = Field(
        default=(), max_length=256
    )
    strict_route_satisfied: bool
    legacy_query_only_locator_is_not_strict_evidence: Literal[True] = True
    receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> "ReviewedEvidenceFilterReceipt":
        _require_unique(self.search_hit_ids, "reviewed_filter_search_hit_duplicate")
        _require_sorted_unique(
            self.accepted_evidence_ids, "reviewed_filter_accepted_id_duplicate"
        )
        rejected_ids = tuple(row.evidence_id for row in self.rejections)
        _require_unique(rejected_ids, "reviewed_filter_rejection_id_duplicate")
        if set(self.accepted_evidence_ids).intersection(rejected_ids):
            raise ValueError("reviewed_filter_accept_reject_overlap")
        if self.strict_route_satisfied != bool(self.accepted_evidence_ids):
            raise ValueError("reviewed_filter_satisfaction_mismatch")
        _verify_digest(self, "receipt_digest", "reviewed_filter_receipt_digest_mismatch")
        return self


def _filter_rejection(
    evidence_id: str,
    reason: Literal[
        "not_indexed",
        "metadata_insufficient",
        "entity_mismatch",
        "period_mismatch",
        "topic_mismatch",
        "role_mismatch",
        "authority_mismatch",
        "family_or_branch_mismatch",
        "reread_missing",
        "reread_digest_mismatch",
        "reread_locator_mismatch",
        "reread_authority_mismatch",
        "reread_period_mismatch",
        "reread_index_stale",
    ],
) -> ReviewedEvidenceFilterRejection:
    body = {"evidence_id": evidence_id, "reason": reason}
    return ReviewedEvidenceFilterRejection(
        **body, rejection_digest=canonical_digest(body)
    )


def _reviewed_mismatch_reason(
    row: ReviewedEvidenceIndexRowV1_2,
    target: CompiledReviewedEvidenceTarget,
) -> Literal[
    "metadata_insufficient",
    "entity_mismatch",
    "period_mismatch",
    "topic_mismatch",
    "role_mismatch",
    "authority_mismatch",
    "family_or_branch_mismatch",
]:
    if row.metadata_state != "complete":
        return "metadata_insufficient"
    if (
        row.case_key != target.case_key
        or target.coverage_obligation_id
        not in row.minimum_route_eligible_branch_ids
        or row.source_family_ref != target.source_family_ref
    ):
        return "family_or_branch_mismatch"
    if target.entity_refs and not set(target.entity_refs).intersection(row.entity_ids):
        return "entity_mismatch"
    if target.period_intents and not set(target.period_intents).intersection(
        row.period_refs
    ):
        return "period_mismatch"
    if not set(target.topic_refs).intersection(row.topic_refs):
        return "topic_mismatch"
    if target.evidence_role_refs and row.evidence_role not in target.evidence_role_refs:
        return "role_mismatch"
    return "authority_mismatch"


def filter_reviewed_evidence_hits(
    *,
    compiled_target: CompiledReviewedEvidenceTarget,
    reviewed_index: ReviewedEvidenceIndexV1_2,
    search_hit_ids: Sequence[str],
    reread_metadata: Sequence[ReviewedEvidenceRereadMetadata],
    expected_index_digest: Digest,
    filter_receipt_id: str,
) -> ReviewedEvidenceFilterReceipt:
    """Exact host post-filter plus mandatory ID re-read integrity checks."""

    target = CompiledReviewedEvidenceTarget.model_validate(
        compiled_target.model_dump(mode="python")
    )
    index = ReviewedEvidenceIndexV1_2.model_validate(
        reviewed_index.model_dump(mode="python")
    )
    if (
        expected_index_digest != index.index_digest
        or target.reviewed_index_digest != index.index_digest
    ):
        raise SourceFamilyCompilerError("reviewed_filter_index_digest_stale")
    hit_ids = tuple(search_hit_ids)
    if len(hit_ids) != len(set(hit_ids)):
        raise SourceFamilyCompilerError("reviewed_filter_search_hit_duplicate")
    rereads = {
        row.evidence_id: ReviewedEvidenceRereadMetadata.model_validate(
            row.model_dump(mode="python")
        )
        for row in reread_metadata
    }
    if len(rereads) != len(reread_metadata):
        raise SourceFamilyCompilerError("reviewed_filter_reread_duplicate")
    rows = {row.evidence_id: row for row in index.rows}
    accepted: list[str] = []
    rejections: list[ReviewedEvidenceFilterRejection] = []
    for evidence_id in hit_ids:
        row = rows.get(evidence_id)
        if row is None:
            rejections.append(_filter_rejection(evidence_id, "not_indexed"))
            continue
        if not _row_matches_reviewed_target(row, target):
            rejections.append(
                _filter_rejection(
                    evidence_id, _reviewed_mismatch_reason(row, target)
                )
            )
            continue
        reread = rereads.get(evidence_id)
        if reread is None:
            rejections.append(_filter_rejection(evidence_id, "reread_missing"))
        elif reread.reviewed_index_digest != index.index_digest:
            rejections.append(_filter_rejection(evidence_id, "reread_index_stale"))
        elif reread.item_digest != row.item_digest:
            rejections.append(_filter_rejection(evidence_id, "reread_digest_mismatch"))
        elif reread.locator_digest != row.locator_digest:
            rejections.append(_filter_rejection(evidence_id, "reread_locator_mismatch"))
        elif reread.authority_tier != row.authority_tier:
            rejections.append(_filter_rejection(evidence_id, "reread_authority_mismatch"))
        elif (
            reread.source_reporting_period_end
            != row.source_reporting_period_end
        ):
            rejections.append(_filter_rejection(evidence_id, "reread_period_mismatch"))
        else:
            accepted.append(evidence_id)
    body = {
        "contract_version": "1.2",
        "filter_receipt_id": filter_receipt_id,
        "compiled_target_digest": target.target_digest,
        "reviewed_index_digest": index.index_digest,
        "search_hit_ids": hit_ids,
        "accepted_evidence_ids": tuple(sorted(accepted)),
        "rejections": tuple(rejections),
        "strict_route_satisfied": bool(accepted),
        "legacy_query_only_locator_is_not_strict_evidence": True,
    }
    return ReviewedEvidenceFilterReceipt(
        **body, receipt_digest=canonical_digest(body)
    )


__all__ = [
    "CapabilityArtifactBinding",
    "CapabilityInventorySnapshot",
    "CompiledExternalSourceTarget",
    "CompiledReviewedEvidenceTarget",
    "CoverageSourceFamilyRequirement",
    "DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE",
    "ExternalInventoryBucket",
    "HostOwnedBaselineSourcePlan",
    "LocalCandidateRetrievalScope",
    "LocalInventoryBucket",
    "LocalInventoryRecord",
    "ReviewedEvidenceFilterReceipt",
    "ReviewedEvidenceIndexRowV1_2",
    "ReviewedEvidenceIndexV1_2",
    "ReviewedEvidenceRereadMetadata",
    "S2CapabilityBucket",
    "SourceFamilyCatalog",
    "SourceFamilyCatalogEntry",
    "SourceFamilyCompilationCorrection",
    "SourceFamilyCompilationReceipt",
    "SourceFamilyCompiler",
    "SourceFamilyCompilerError",
    "build_capability_inventory_snapshot",
    "build_host_owned_baseline_source_plan",
    "build_local_inventory_buckets",
    "compile_source_intent",
    "filter_reviewed_evidence_hits",
    "validate_host_owned_baseline_source_plan",
]
