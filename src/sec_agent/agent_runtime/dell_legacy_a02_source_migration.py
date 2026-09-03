"""Strict zero-call projection of the immutable Dell A02 planner outcome.

The sole public factory accepts the exact raw outcome bytes.  Private helpers
exist only so the checked-in fixture can qualify deterministic projection;
none authorizes compilation, execution, resume, or a successor attempt.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from sec_agent.canonical_runtime.contracts_v1_2 import (
    LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
    StrictFrozenModel,
    canonical_json_sha256,
)
from .dell_agentic_contracts import (
    ExternalSourceIntent,
    LocalEvidenceIntent,
    ProviderEvidenceIntent,
    ReviewedEvidenceIntent,
)
from .dell_source_family_compiler import DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE


_SHA = r"^[0-9a-f]{64}$"
LEGACY_A02_PLANNER_OUTCOME_REF = "qualification://dell-reference-vertical/A02/planner-outcome"
LEGACY_A02_PLANNER_OUTCOME_SHA256 = "234b64c3b03b39d8b76f7277dfdb4f64c2686802df5dc5c254304523d71e10d7"
LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256 = "bdeec49fb9bf75aa8101ce9ccc928d45c4f7d80b8b8378fe2a411339aa99c0fd"
_EXECUTION_REF = f"legacy-a02://paid-full-chain-execution/{LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID}"

# ordinal, task index, branch, request index, source route, exact family order.
_BINDINGS = (
    (1, 0, "Q1_ISSUER_TRUTH", 0, "reviewed_first", ("F2_DELL_IR_EARNINGS",)),
    (2, 0, "Q1_ISSUER_TRUTH", 1, "reviewed_first", ("F2_DELL_IR_EARNINGS",)),
    (3, 1, "Q2_DEMAND_QUALITY", 0, "reviewed_first", ("F2_DELL_IR_EARNINGS",)),
    (4, 1, "Q2_DEMAND_QUALITY", 1, "reviewed_first", ("F4_CUSTOMER_CAPEX_DEPLOYMENT",)),
    (5, 2, "Q3_UNITS_ASP_PVM", 0, "reviewed_first", ("F2_DELL_IR_EARNINGS",)),
    (6, 2, "Q3_UNITS_ASP_PVM", 1, "reviewed_first", ("F3_DELL_PRODUCT_SUPPORT",)),
    (7, 3, "Q4_ARCHITECTURE_RAMP", 0, "reviewed_first", ("F3_DELL_PRODUCT_SUPPORT",)),
    (8, 3, "Q4_ARCHITECTURE_RAMP", 1, "reviewed_first", ("F6_COMPUTE_PLATFORM_SUPPLIERS",)),
    (9, 4, "Q5_SUPPLY_AND_PRICE", 0, "reviewed_first", ("F7_MEMORY_FOUNDRY_NETWORK_STORAGE",)),
    (10, 4, "Q5_SUPPLY_AND_PRICE", 1, "reviewed_first", ("F2_DELL_IR_EARNINGS",)),
    (11, 5, "Q6_MODEL_COMPUTE_DEMAND", 0, "reviewed_first", ("F9_MODEL_COMPUTE_AND_BENCHMARKS",)),
    (12, 5, "Q6_MODEL_COMPUTE_DEMAND", 1, "reviewed_first", ("F4_CUSTOMER_CAPEX_DEPLOYMENT",)),
    (13, 6, "Q7_EXPORT_CONTROL_CHINA", 0, "reviewed_first", ("F10_EXPORT_CONTROL_AND_POLICY",)),
    (14, 6, "Q7_EXPORT_CONTROL_CHINA", 1, "reviewed_first", ("F1_SEC_ISSUER_FACTS",)),
    (15, 7, "Q8_COMPETITION_VALUE_POOL", 0, "reviewed_first", ("F8_OEM_COMPETITION",)),
    (16, 7, "Q8_COMPETITION_VALUE_POOL", 1, "reviewed_first", ("F6_COMPUTE_PLATFORM_SUPPLIERS", "F7_MEMORY_FOUNDRY_NETWORK_STORAGE")),
    (17, 8, "Q9_COUNTEREVIDENCE_WWC", 0, "external_required", ("F12_INDEPENDENT_COUNTEREVIDENCE",)),
)
_TOPICS = {
    "Q1_ISSUER_TRUTH": ("capital_allocation_and_valuation", "cash_conversion_balance_sheet", "management_outlook", "operating_performance"),
    "Q2_DEMAND_QUALITY": ("demand_volume_quality", "management_outlook", "relationship_attribution"),
    "Q3_UNITS_ASP_PVM": ("demand_volume_quality", "pricing_mix_value_capture"),
    "Q4_ARCHITECTURE_RAMP": ("capacity_inputs_execution", "relationship_attribution"),
    "Q5_SUPPLY_AND_PRICE": ("capacity_inputs_execution", "relationship_attribution"),
    "Q6_MODEL_COMPUTE_DEMAND": ("capacity_inputs_execution", "demand_volume_quality", "relationship_attribution"),
    "Q7_EXPORT_CONTROL_CHINA": ("regulatory_policy_exposure",),
    "Q8_COMPETITION_VALUE_POOL": ("operating_performance", "pricing_mix_value_capture"),
    "Q9_COUNTEREVIDENCE_WWC": ("counterevidence_and_what_would_change",),
}
_ROLES = {
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
_ALIASES = {"AMZN": "AMAZON", "MSFT": "MICROSOFT", "MU": "MICRON", "NVDA": "NVIDIA", "TSM": "TSMC"}
_CANONICAL = frozenset({"AMD", "DELL", "GOOGL", "HPE", "META", "SK_HYNIX", "SMCI", *_ALIASES.values()})
_Q8 = {
    "F6_COMPUTE_PLATFORM_SUPPLIERS": (frozenset({"AMD", "INTC", "NVDA"}), ("NVIDIA", "AMD", "INTC")),
    "F7_MEMORY_FOUNDRY_NETWORK_STORAGE": (frozenset({"AVGO", "MU", "TSM"}), ("MICRON", "TSMC", "AVGO")),
}
_REQUEST_KEYS = frozenset({
    "capture_limit", "include_domains", "issuer_ids", "fiscal_periods", "limit",
    "purpose", "query", "retrieval_lanes", "route_ids", "source_roles", "source_route",
})


def _tuple(value: Any) -> Any:
    return tuple(value) if isinstance(value, list) else value


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _verify_digest(model: StrictFrozenModel, field: str, code: str) -> None:
    if getattr(model, field) != canonical_json_sha256(
        model.model_dump(mode="json", exclude={field})
    ):
        raise ValueError(code)


def _binding(ordinal: int) -> tuple[Any, ...]:
    if not 1 <= ordinal <= 17 or _BINDINGS[ordinal - 1][0] != ordinal:
        raise ValueError("legacy_a02_source_request_ordinal_invalid")
    return _BINDINGS[ordinal - 1]


def _path(binding: tuple[Any, ...]) -> str:
    return f"parsed_payload.tasks[{binding[1]}].evidence_requests[{binding[3]}]"


def _leg_id(ordinal: int, family: str, kind: str) -> str:
    suffix = f"-{family.split('_', 1)[0]}" if len(_binding(ordinal)[5]) > 1 else ""
    label = {"reviewed_evidence": "REVIEWED", "local_evidence": "LOCAL", "external_source": "EXTERNAL"}[kind]
    return f"A02-E{ordinal:02d}{suffix}-{label}"


def _expected_occurrences(task: int) -> tuple[str, ...]:
    return tuple(family for row in _BINDINGS if row[1] == task for family in row[5])


def _audit_parts(required: tuple[str, ...], occurrences: tuple[str, ...]) -> tuple[Any, ...]:
    counts, unique = Counter(occurrences), _unique(occurrences)
    missing = tuple(family for family in required if family not in counts)
    duplicates = tuple(family for family in unique if counts[family] > 1)
    extras = tuple(sorted(set(unique) - set(required)))
    return unique, missing, duplicates, extras


class _Leg(StrictFrozenModel):
    leg_id: str
    source_request_ordinal: int = Field(ge=1, le=17)
    source_request_path: str
    branch_id: str
    semantic_source_family_ref: str
    provider_intent_kind: Literal["reviewed_evidence", "local_evidence", "external_source"]
    intent: ProviderEvidenceIntent
    legacy_capture_limit: int = Field(ge=1, le=3)
    migration_notes: tuple[str, ...]
    blocking_correction_code: Literal["reviewed_enrichment_required"] | None
    source_request_digest: str = Field(pattern=_SHA)
    execution_authorized: Literal[False] = False
    leg_digest: str = Field(pattern=_SHA)

    @field_validator("migration_notes", mode="before")
    @classmethod
    def tuple_notes(cls, value: Any) -> Any:
        return _tuple(value)

    @model_validator(mode="after")
    def validate_leg(self) -> "_Leg":
        binding = _binding(self.source_request_ordinal)
        _, _, branch, _, route, families = binding
        if self.branch_id != branch or self.source_request_path != _path(binding):
            raise ValueError("legacy_a02_leg_source_path_binding_mismatch")
        if self.semantic_source_family_ref not in families:
            raise ValueError("legacy_a02_leg_family_binding_mismatch")
        allowed = {"external_source"} if route == "external_required" else {"reviewed_evidence", "local_evidence"}
        if self.provider_intent_kind not in allowed or self.intent.intent_kind != self.provider_intent_kind:
            raise ValueError("legacy_a02_leg_cross_kind_mismatch")
        if self.leg_id != _leg_id(
            self.source_request_ordinal,
            self.semantic_source_family_ref,
            self.provider_intent_kind,
        ):
            raise ValueError("legacy_a02_leg_identity_mismatch")
        family = self.semantic_source_family_ref
        if isinstance(
            self.intent, (LocalEvidenceIntent, ExternalSourceIntent)
        ) and self.intent.semantic_source_family_refs != (family,):
            raise ValueError("legacy_a02_leg_intent_family_mismatch")
        if isinstance(self.intent, LocalEvidenceIntent) and self.intent.source_role_intents != (_ROLES[family],):
            raise ValueError("legacy_a02_leg_local_role_family_mismatch")
        correction = "reviewed_enrichment_required" if isinstance(self.intent, ReviewedEvidenceIntent) else None
        if self.blocking_correction_code != correction:
            raise ValueError("legacy_a02_leg_blocking_correction_mismatch")
        if isinstance(self.intent, ReviewedEvidenceIntent) and self.intent.evidence_role_refs:
            raise ValueError("legacy_a02_leg_reviewed_enrichment_state_mismatch")
        if isinstance(self.intent, ExternalSourceIntent):
            external_selectors = (
                self.intent.entity_refs,
                self.intent.period_intents,
                self.intent.domain_allowlist,
                self.intent.published_not_before,
                self.intent.published_not_after,
            )
            if any(external_selectors):
                raise ValueError("legacy_a02_leg_external_selector_clearance_mismatch")
        if self.source_request_ordinal == 16 and self.intent.entity_refs != _Q8[family][1]:
            raise ValueError("legacy_a02_leg_q8_entity_family_mismatch")
        if len(self.migration_notes) != len(set(self.migration_notes)):
            raise ValueError("legacy_a02_leg_migration_note_duplicate")
        _verify_digest(self, "leg_digest", "legacy_a02_leg_digest_mismatch")
        return self


class _BranchAudit(StrictFrozenModel):
    branch_id: str
    required: tuple[str, ...]
    occurrences: tuple[str, ...]
    unique: tuple[str, ...]
    missing: tuple[str, ...]
    duplicates: tuple[str, ...]
    extras: tuple[str, ...]
    complete: bool
    audit_digest: str = Field(pattern=_SHA)

    @field_validator("required", "occurrences", "unique", "missing", "duplicates", "extras", mode="before")
    @classmethod
    def tuple_fields(cls, value: Any) -> Any:
        return _tuple(value)

    @model_validator(mode="after")
    def validate_audit(self) -> "_BranchAudit":
        foundation = dict(DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE)
        if self.branch_id not in foundation:
            raise ValueError("legacy_a02_branch_unknown")
        task = tuple(foundation).index(self.branch_id)
        parts = _audit_parts(foundation[self.branch_id], _expected_occurrences(task))
        actual = (
            self.required, self.occurrences, self.unique, self.missing,
            self.duplicates, self.extras, self.complete,
        )
        expected = (
            foundation[self.branch_id], _expected_occurrences(task),
            *parts, not any(parts[1:]),
        )
        if actual != expected:
            raise ValueError("legacy_a02_branch_audit_derived_mismatch")
        _verify_digest(self, "audit_digest", "legacy_a02_branch_audit_digest_mismatch")
        return self


class _BatchAudit(StrictFrozenModel):
    branch_audits: tuple[_BranchAudit, ...]
    required_count: int
    occurrence_count: int
    unique_count: int
    missing_keys: tuple[str, ...]
    duplicate_keys: tuple[str, ...]
    extra_keys: tuple[str, ...]
    complete: bool
    execution_authorized: Literal[False] = False
    receipt_digest: str = Field(pattern=_SHA)

    @field_validator("branch_audits", "missing_keys", "duplicate_keys", "extra_keys", mode="before")
    @classmethod
    def tuple_fields(cls, value: Any) -> Any:
        return _tuple(value)

    @model_validator(mode="after")
    def validate_audit(self) -> "_BatchAudit":
        branches = tuple(branch for branch, _ in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE)
        if tuple(row.branch_id for row in self.branch_audits) != branches:
            raise ValueError("legacy_a02_batch_branch_order_mismatch")
        missing = tuple(f"{row.branch_id}/{family}" for row in self.branch_audits for family in row.missing)
        duplicates = tuple(f"{row.branch_id}/{family}" for row in self.branch_audits for family in row.duplicates)
        extras = tuple(f"{row.branch_id}/{family}" for row in self.branch_audits for family in row.extras)
        derived = (
            sum(len(row.required) for row in self.branch_audits),
            sum(len(row.occurrences) for row in self.branch_audits),
            sum(len(row.unique) for row in self.branch_audits),
            missing, duplicates, extras, not (missing or duplicates or extras),
        )
        actual = (
            self.required_count, self.occurrence_count, self.unique_count,
            self.missing_keys, self.duplicate_keys, self.extra_keys, self.complete,
        )
        if actual != derived or derived[:3] != (24, 18, 17) or tuple(map(len, derived[3:6])) != (7, 1, 0):
            raise ValueError("legacy_a02_batch_derived_mismatch")
        _verify_digest(self, "receipt_digest", "legacy_a02_batch_digest_mismatch")
        return self


class LegacyA02SourceMigrationReceipt(StrictFrozenModel):
    migration_receipt_id: Literal["legacy-a02-source-migration:planner-outcome"]
    legacy_execution_ref: str
    source_artifact_ref: str
    source_artifact_sha256: str = Field(pattern=_SHA)
    parsed_payload_digest: str = Field(pattern=_SHA)
    task_count: int
    source_request_count: int
    fact_request_count: int
    provider_intent_leg_count: int
    reviewed_leg_count: int
    local_leg_count: int
    external_leg_count: int
    intent_legs: tuple[_Leg, ...]
    batch_family_audit: _BatchAudit
    authority_mode: Literal["immutable_audit_only"]
    compiler_dispatch_performed: Literal[False]
    resume_allowed: Literal[False]
    successor_authorized: Literal[False]
    model_calls: Literal[0]
    network_calls: Literal[0]
    provider_calls: Literal[0]
    receipt_digest: str = Field(pattern=_SHA)

    @field_validator("intent_legs", mode="before")
    @classmethod
    def tuple_legs(cls, value: Any) -> Any:
        return _tuple(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> "LegacyA02SourceMigrationReceipt":
        identity = (
            self.legacy_execution_ref, self.source_artifact_ref,
            self.source_artifact_sha256, self.parsed_payload_digest,
        )
        if identity != (
            _EXECUTION_REF,
            LEGACY_A02_PLANNER_OUTCOME_REF,
            LEGACY_A02_PLANNER_OUTCOME_SHA256,
            LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256,
        ):
            raise ValueError("legacy_a02_source_identity_mismatch")
        counts = Counter(leg.provider_intent_kind for leg in self.intent_legs)
        derived_counts = (
            9, 17, 2, len(self.intent_legs), counts["reviewed_evidence"],
            counts["local_evidence"], counts["external_source"],
        )
        actual_counts = (
            self.task_count, self.source_request_count, self.fact_request_count,
            self.provider_intent_leg_count, self.reviewed_leg_count,
            self.local_leg_count, self.external_leg_count,
        )
        if actual_counts != derived_counts or derived_counts != (9, 17, 2, 35, 17, 17, 1):
            raise ValueError("legacy_a02_source_receipt_count_mismatch")
        expected = []
        for ordinal, _, _, _, route, families in _BINDINGS:
            kinds = ("external_source",) if route == "external_required" else ("reviewed_evidence", "local_evidence")
            expected.extend((ordinal, family, kind) for family in families for kind in kinds)
        actual = [
            (
                leg.source_request_ordinal,
                leg.semantic_source_family_ref,
                leg.provider_intent_kind,
            )
            for leg in self.intent_legs
        ]
        if actual != expected:
            raise ValueError("legacy_a02_source_receipt_topology_mismatch")
        for ordinal, _, _, _, route, families in _BINDINGS:
            bound = [leg for leg in self.intent_legs if leg.source_request_ordinal == ordinal]
            if len({leg.source_request_digest for leg in bound}) != 1:
                raise ValueError("legacy_a02_source_receipt_request_digest_split")
            if route == "external_required":
                continue
            for family in families:
                reviewed, local = [leg.intent for leg in bound if leg.semantic_source_family_ref == family]
                shared = ("query", "purpose", "entity_refs", "period_intents", "expected_information_gain", "limit")
                if any(getattr(reviewed, name) != getattr(local, name) for name in shared):
                    raise ValueError("legacy_a02_source_receipt_cross_kind_split")
        _verify_digest(self, "receipt_digest", "legacy_a02_source_receipt_digest_mismatch")
        return self


def _strings(request: Mapping[str, Any], name: str) -> tuple[str, ...]:
    raw = request.get(name, ())
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise TypeError(f"legacy_a02_{name}_sequence_required")
    if any(not isinstance(value, str) or not value.strip() for value in raw):
        raise TypeError(f"legacy_a02_{name}_string_required")
    values = tuple(value.strip() for value in raw)
    if len(values) != len(set(values)):
        raise ValueError(f"legacy_a02_{name}_duplicate")
    return values


def _request(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) - _REQUEST_KEYS:
        raise ValueError("legacy_a02_request_shape_invalid")
    query, purpose, route = (raw.get(key) for key in ("query", "purpose", "source_route"))
    if not isinstance(query, str) or len(query.strip()) < 3 or not isinstance(purpose, str) or len(purpose.strip()) < 8:
        raise ValueError("legacy_a02_request_text_invalid")
    limit, capture = raw.get("limit", 6), raw.get("capture_limit", 2)
    if route not in {"reviewed_first", "external_required"} or type(limit) is not int or not 1 <= limit <= 6 or type(capture) is not int or not 1 <= capture <= 3:
        raise ValueError("legacy_a02_request_control_invalid")
    result = {"query": query.strip(), "purpose": purpose.strip(), "source_route": route, "limit": limit, "capture_limit": capture}
    for name in ("include_domains", "issuer_ids", "fiscal_periods", "source_roles", "route_ids", "retrieval_lanes"):
        result[name] = _strings(raw, name)
    if not result["route_ids"]:
        raise ValueError("legacy_a02_route_ids_missing")
    return result


def _entities(values: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    result, notes = [], []
    for raw in values:
        token, mapped = raw.upper(), _ALIASES.get(raw.upper(), raw.upper())
        result.append(mapped)
        if mapped != token:
            notes.append(f"explicit_entity_alias:{token}->{mapped}")
        elif token not in _CANONICAL:
            notes.append(f"unmapped_entity_alias_preserved:{token}")
    return _unique(result), _unique(notes)


def _partition(request: Mapping[str, Any], ordinal: int, family: str) -> tuple[Any, ...]:
    if len(request["route_ids"]) == 1:
        if request["source_roles"] != (_ROLES[family],):
            raise ValueError("legacy_a02_family_role_binding_invalid")
        entities, notes = _entities(request["issuer_ids"])
        return entities, request["source_roles"], notes
    raw_entities, known = tuple(value.upper() for value in request["issuer_ids"]), set().union(*(row[0] for row in _Q8.values()))
    if ordinal != 16 or any(value not in known for value in raw_entities):
        raise ValueError("legacy_a02_multi_family_entity_unassigned")
    selected = tuple(value for value in raw_entities if value in _Q8[family][0])
    if not selected or _ROLES[family] not in request["source_roles"]:
        raise ValueError("legacy_a02_q8_family_entity_partition_empty")
    entities, notes = _entities(selected)
    return entities, (_ROLES[family],), notes + ("multi_family_entity_partition_explicit_not_cartesian",)


def _seal_leg(body: dict[str, Any]) -> _Leg:
    return _Leg(**body, leg_digest=canonical_json_sha256(body))


def _project_request(task: int, branch: str, index: int, ordinal: int, raw: Mapping[str, Any]) -> tuple[_Leg, ...]:
    binding = _binding(ordinal)
    if (task, branch, index) != binding[1:4]:
        raise ValueError("legacy_a02_request_exact_path_binding_mismatch")
    request = _request(raw)
    if (request["source_route"], request["route_ids"]) != binding[4:6]:
        raise ValueError("legacy_a02_request_route_binding_mismatch")
    common = dict(source_request_ordinal=ordinal, source_request_path=_path(binding), branch_id=branch, legacy_capture_limit=request["capture_limit"], source_request_digest=canonical_json_sha256(request), execution_authorized=False)
    if binding[4] == "external_required":
        family = binding[5][0]
        removed = tuple(name for name in ("issuer_ids", "fiscal_periods", "source_roles", "retrieval_lanes") if request[name])
        notes = ["legacy_route_ids_projected_to_semantic_source_family_refs"]
        if removed:
            notes.append("legacy_external_local_selectors_removed:" + ",".join(removed))
        intent = ExternalSourceIntent(intent_kind="external_source", query=request["query"], purpose=request["purpose"], entity_refs=(), period_intents=(), expected_information_gain=request["purpose"], limit=request["limit"], semantic_source_family_refs=(family,), domain_allowlist=request["include_domains"])
        return (_seal_leg(dict(**common, leg_id=_leg_id(ordinal, family, intent.intent_kind), semantic_source_family_ref=family, provider_intent_kind=intent.intent_kind, intent=intent, migration_notes=tuple(notes), blocking_correction_code=None)),)
    surfaces = _unique(tuple({"prose_leaf": "prose", "table_leaf": "table"}.get(lane, "") for lane in request["retrieval_lanes"]))
    if not surfaces or "" in surfaces:
        raise ValueError("legacy_a02_local_surface_invalid")
    legs = []
    for family in binding[5]:
        entities, roles, notes = _partition(request, ordinal, family)
        notes = _unique(("legacy_route_ids_projected_to_semantic_source_family_refs", "reviewed_and_local_are_independent_no_fallback", "reviewed_enrichment_required_before_compilation", *notes))
        shared = dict(query=request["query"], purpose=request["purpose"], entity_refs=entities, period_intents=request["fiscal_periods"], expected_information_gain=request["purpose"], limit=request["limit"])
        intents = (
            ReviewedEvidenceIntent(intent_kind="reviewed_evidence", **shared, topic_refs=_TOPICS[branch], evidence_role_refs=(), minimum_authority_tier="reviewed"),
            LocalEvidenceIntent(intent_kind="local_evidence", **shared, semantic_source_family_refs=(family,), source_role_intents=roles, content_surface_intents=surfaces),
        )
        for intent in intents:
            correction = "reviewed_enrichment_required" if isinstance(intent, ReviewedEvidenceIntent) else None
            legs.append(_seal_leg(dict(**common, leg_id=_leg_id(ordinal, family, intent.intent_kind), semantic_source_family_ref=family, provider_intent_kind=intent.intent_kind, intent=intent, migration_notes=notes, blocking_correction_code=correction)))
    return tuple(legs)


def _make_batch() -> _BatchAudit:
    audits = []
    for task, (branch, required) in enumerate(DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE):
        occurrences = _expected_occurrences(task)
        unique, missing, duplicates, extras = _audit_parts(required, occurrences)
        body = dict(branch_id=branch, required=required, occurrences=occurrences, unique=unique, missing=missing, duplicates=duplicates, extras=extras, complete=not (missing or duplicates or extras))
        audits.append(_BranchAudit(**body, audit_digest=canonical_json_sha256(body)))
    missing = tuple(f"{row.branch_id}/{family}" for row in audits for family in row.missing)
    duplicates = tuple(f"{row.branch_id}/{family}" for row in audits for family in row.duplicates)
    extras = tuple(f"{row.branch_id}/{family}" for row in audits for family in row.extras)
    body = dict(branch_audits=tuple(audits), required_count=sum(len(row.required) for row in audits), occurrence_count=sum(len(row.occurrences) for row in audits), unique_count=sum(len(row.unique) for row in audits), missing_keys=missing, duplicate_keys=duplicates, extra_keys=extras, complete=not (missing or duplicates or extras), execution_authorized=False)
    return _BatchAudit(**body, receipt_digest=canonical_json_sha256(body))


def _migrate_payload(parsed_payload: Mapping[str, Any]) -> LegacyA02SourceMigrationReceipt:
    if not isinstance(parsed_payload, Mapping) or canonical_json_sha256(parsed_payload) != LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256:
        raise ValueError("legacy_a02_migration_parsed_payload_not_exact_source")
    tasks = parsed_payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 9:
        raise ValueError("legacy_a02_migration_task_shape_invalid")
    legs, ordinal, facts = [], 0, 0
    for task, raw_task in enumerate(tasks):
        branch = DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE[task][0]
        bindings = [row for row in _BINDINGS if row[1] == task]
        if not isinstance(raw_task, Mapping) or raw_task.get("branch_id") != branch:
            raise ValueError("legacy_a02_migration_branch_order_mismatch")
        requests, fact_requests = raw_task.get("evidence_requests"), raw_task.get("fact_requests", [])
        if not isinstance(requests, list) or len(requests) != len(bindings) or not isinstance(fact_requests, list):
            raise ValueError("legacy_a02_migration_task_payload_shape_invalid")
        for index, request in enumerate(requests):
            ordinal += 1
            legs.extend(_project_request(task, branch, index, ordinal, request))
        facts += len(fact_requests)
    if ordinal != 17 or facts != 2 or len(legs) != 35:
        raise ValueError("legacy_a02_migration_saved_payload_shape_mismatch")
    batch, counts = _make_batch(), Counter(leg.provider_intent_kind for leg in legs)
    body = dict(
        migration_receipt_id="legacy-a02-source-migration:planner-outcome",
        legacy_execution_ref=_EXECUTION_REF,
        source_artifact_ref=LEGACY_A02_PLANNER_OUTCOME_REF,
        source_artifact_sha256=LEGACY_A02_PLANNER_OUTCOME_SHA256,
        parsed_payload_digest=LEGACY_A02_PLANNER_PARSED_PAYLOAD_SHA256,
        task_count=9,
        source_request_count=17,
        fact_request_count=2,
        provider_intent_leg_count=len(legs),
        reviewed_leg_count=counts["reviewed_evidence"],
        local_leg_count=counts["local_evidence"],
        external_leg_count=counts["external_source"],
        intent_legs=tuple(legs),
        batch_family_audit=batch,
        authority_mode="immutable_audit_only",
        compiler_dispatch_performed=False,
        resume_allowed=False,
        successor_authorized=False,
        model_calls=0,
        network_calls=0,
        provider_calls=0,
    )
    return LegacyA02SourceMigrationReceipt(**body, receipt_digest=canonical_json_sha256(body))


def migrate_legacy_a02_planner_outcome_bytes(outcome_bytes: bytes) -> LegacyA02SourceMigrationReceipt:
    """Verify and project only the exact immutable raw A02 outcome."""

    if not isinstance(outcome_bytes, bytes):
        raise TypeError("legacy_a02_migration_outcome_bytes_required")
    if hashlib.sha256(outcome_bytes).hexdigest() != LEGACY_A02_PLANNER_OUTCOME_SHA256:
        raise ValueError("legacy_a02_migration_source_artifact_digest_mismatch")
    try:
        outcome = json.loads(outcome_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("legacy_a02_migration_outcome_json_invalid") from exc
    shape = ("outcome", "planner", "host_payload_validation_failed", "model_structured_payload_invalid")
    if not isinstance(outcome, Mapping) or tuple(outcome.get(key) for key in ("event", "role", "status", "error_message")) != shape:
        raise ValueError("legacy_a02_migration_outcome_shape_mismatch")
    return _migrate_payload(outcome.get("parsed_payload"))


__all__ = ("LegacyA02SourceMigrationReceipt", "migrate_legacy_a02_planner_outcome_bytes")
