from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import (
    read_registered_runtime_bytes,
    read_registered_runtime_json,
)


S4_CASE_RUNTIME_CONTRACT_REF = "fin01.s4.case_runtime_binding:v1"
S4_CASE_RUNTIME_RESEARCH_PROFILE_OVERLAY_REF = (
    "fin01.s4.case_runtime_research_profile_overlay:v1"
)
S4_CASE_LOCAL_JUDGMENT_ATOM_REF = "fin01.s4.case_local_judgment_atom:v1"
S4_METHOD_CONTRACT_REF = "fin01.s4.financial_method_to_runtime.dell_mu:v1"
S4_SOURCE_GROUNDED_INPUT_CONTRACT_REF = (
    "fin01.s4.source_grounded_case_input:v1"
)
S4_CASE_EVIDENCE_ROLE_GROUP_MAPPING_REF = (
    "fin01.s4.case_evidence_role_group_mapping:v1"
)
S4_CASE_EVIDENCE_SLOT_ALIGNMENT_REF = (
    "fin01.s4.case_evidence_slot_alignment:v1"
)
S4_PROGRAM_CELL_IDS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
S4_RUNTIME_CONSUMER_IDS = (
    "evidence_route_plan",
    "financial_numeric_pack",
    "bounded_graph_pack",
    "specialist_and_research_lead",
    "bounded_agent_input_and_execution",
    "writer_verifier_and_review_surface",
    "workbench_projection",
)


class S4CaseRuntimeError(ValueError):
    """Closed error for S4 Case Pack loading, identity, or leakage failures."""


class S4CaseRuntimeBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ref: Literal["fin01.s4.case_runtime_binding:v1"] = (
        S4_CASE_RUNTIME_CONTRACT_REF
    )
    case_ticker: Literal["DELL", "MU"]
    legal_name: str = Field(min_length=1)
    issuer_identifier_kind: Literal["SEC_CIK"] = "SEC_CIK"
    issuer_identifier: str = Field(pattern=r"^CIK[0-9]{10}$")
    issuer_identifier_source_ref: str = Field(
        min_length=1, pattern=r"^https://www\.sec\.gov/"
    )
    issuer_resolution_status: Literal[
        "official_SEC_identifier_and_local_routes_resolved_for_deterministic_fixture"
    ] = "official_SEC_identifier_and_local_routes_resolved_for_deterministic_fixture"
    case_profile_ref: str = Field(min_length=1)
    research_profile_ref: str = Field(min_length=1)
    case_pack_ref: str = Field(min_length=1)
    case_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_contract_ref: Literal[
        "fin01.s4.financial_method_to_runtime.dell_mu:v1"
    ] = S4_METHOD_CONTRACT_REF
    method_contract_path: str = Field(min_length=1)
    method_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_id: str = Field(min_length=1)
    runtime_family: Literal["Fin01ResearchRuntime"] = "Fin01ResearchRuntime"
    input_contract_ref: str = Field(min_length=1)
    output_contract_ref: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    program_cell_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    case_identity_namespace: str = Field(min_length=1)
    local_source_routes_by_cell: dict[str, tuple[str, ...]]
    consumer_ids: tuple[str, ...] = Field(min_length=7, max_length=7)
    consumer_requirements: dict[str, tuple[str, ...]]
    program_cell_contracts: tuple[dict[str, Any], ...] = Field(
        min_length=3, max_length=3
    )
    source_authority_policy: dict[str, Any]
    numeric_policy: dict[str, Any]
    graph_policy: dict[str, Any]
    judgment_atom_contract: dict[str, Any]
    method_contract: dict[str, Any]
    factual_content_counts: dict[str, Literal[0]]
    runtime_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class S4CaseRuntimeResearchProfileOverlay(BaseModel):
    """Versioned lineage from one frozen Case binding to its effective profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ref: Literal[
        "fin01.s4.case_runtime_research_profile_overlay:v1"
    ] = S4_CASE_RUNTIME_RESEARCH_PROFILE_OVERLAY_REF
    case_ticker: Literal["DELL", "MU"]
    program_cell_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    base_case_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_runtime_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_profile_ref: str = Field(min_length=1)
    research_profile_contract_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_runtime_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    overlay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class S4CaseRuntimeConsumerInjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_contract_ref: Literal["fin01.s4.case_runtime_binding:v1"] = (
        S4_CASE_RUNTIME_CONTRACT_REF
    )
    runtime_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumer_id: str = Field(min_length=1)
    case_ticker: Literal["DELL", "MU"]
    issuer_identifier: str = Field(pattern=r"^CIK[0-9]{10}$")
    case_profile_ref: str = Field(min_length=1)
    research_profile_ref: str = Field(min_length=1)
    case_identity_namespace: str = Field(min_length=1)
    method_contract_ref: Literal[
        "fin01.s4.financial_method_to_runtime.dell_mu:v1"
    ] = S4_METHOD_CONTRACT_REF
    method_contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_id: str = Field(min_length=1)
    program_cell_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    consumer_requirements: tuple[str, ...] = Field(min_length=1)
    injected_contract: dict[str, Any]
    injection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_proven: Literal[True] = True
    runtime_injected: Literal[True] = True
    paid_artifact_proven: Literal[False] = False


class S4CaseEvidenceRoleGroup(BaseModel):
    """One case-local evidence-role group on the shared three-Cell axis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program_cell_id: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    source_evidence_roles: tuple[str, ...] = Field(min_length=1)
    role_group_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class S4CaseEvidenceRoleGroupMapping(BaseModel):
    """Derived projection of one Case Pack; never a ticker-authored lookup table."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ref: Literal[
        "fin01.s4.case_evidence_role_group_mapping:v1"
    ] = S4_CASE_EVIDENCE_ROLE_GROUP_MAPPING_REF
    case_ticker: Literal["DELL", "MU"]
    case_identity_namespace: str = Field(min_length=1)
    runtime_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    role_groups: tuple[S4CaseEvidenceRoleGroup, ...] = Field(
        min_length=3, max_length=3
    )
    exact_role_count: int = Field(ge=1)
    role_group_mapping_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class S4CaseEvidenceSlotBinding(BaseModel):
    """Exact `(program_cell_id, evidence_role)` to Canonical slot binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program_cell_id: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    evidence_role: str = Field(min_length=1)
    cell_version_ref: str = Field(min_length=1)
    slot_version_ref: str = Field(min_length=1)
    acceptance_role: str = Field(min_length=1)
    slot_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class S4CaseEvidenceSlotAlignmentReceipt(BaseModel):
    """Zero-call proof that every case role resolves once in its owning Cell."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ref: Literal[
        "fin01.s4.case_evidence_slot_alignment:v1"
    ] = S4_CASE_EVIDENCE_SLOT_ALIGNMENT_REF
    case_id: str = Field(min_length=1)
    decision_surface_contract_ref: str = Field(min_length=1)
    case_ticker: Literal["DELL", "MU"]
    case_identity_namespace: str = Field(min_length=1)
    runtime_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    role_group_mapping_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    slot_bindings: tuple[S4CaseEvidenceSlotBinding, ...] = Field(min_length=1)
    resolved_role_count: int = Field(ge=1)
    alignment_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    network_calls: Literal[0] = 0
    source_network_calls: Literal[0] = 0
    external_tool_calls: Literal[0] = 0
    canonical_writes: Literal[0] = 0


_CASE_CONFIG = {
    "DELL": {
        "case_pack_ref": (
            "configs/releases/"
            "fin_ia_0_1_s4_t02_dell_oem_exact_case_pack_v1_0.json"
        ),
        "case_pack_sha256": (
            "71e7fb3ba56275760f0d2b84006d30fd"
            "192a15ad9be234740dc336cd4a15217e"
        ),
        "method_id": (
            "s4_dell_oem_order_to_revenue_and_working_capital_playbook"
        ),
        "issuer_identifier": "CIK0001571996",
        "issuer_identifier_source_ref": (
            "https://www.sec.gov/Archives/edgar/data/1571996/"
            "000157199626000024/0001571996-26-000024-index.htm"
        ),
    },
    "MU": {
        "case_pack_ref": (
            "configs/releases/"
            "fin_ia_0_1_s4_t02_mu_hbm_exact_case_pack_v1_0.json"
        ),
        "case_pack_sha256": (
            "0de20e119e3ab78b273b96895f7fb707"
            "0da24b6c35122daa53d94d522edb2612"
        ),
        "method_id": "s4_mu_hbm_supply_pricing_and_cycle_playbook",
        "issuer_identifier": "CIK0000723125",
        "issuer_identifier_source_ref": (
            "https://www.sec.gov/Archives/edgar/data/723125/"
            "000196922326000605/0001969223-26-000605-index.htm"
        ),
    },
}
_METHOD_CONTRACT_PATH = (
    "configs/releases/"
    "fin_ia_0_1_s4_t02_financial_method_to_runtime_contract_v1_0.json"
)
_METHOD_CONTRACT_SHA256 = (
    "740d3da108e4bf0082eeea47cb9fdbf8"
    "4d0e992fe20b3db86967dc3336cc5c53"
)
_FACTUAL_KEYS = (
    "evidence_rows",
    "numeric_rows",
    "graph_edges",
    "claims",
    "judgments",
    "preaccepted_conclusions",
)

_SOURCE_GROUNDED_PACK_PATHS = {
    "DELL": (
        "configs/releases/"
        "fin_ia_0_1_s4_t04_dell_source_grounded_input_pack_v1_0.json"
    ),
    "MU": (
        "configs/releases/"
        "fin_ia_0_1_s4_t06_mu_source_grounded_input_pack_v1_0.json"
    ),
}
_CASE_PACK_RESOURCE_IDS = {
    "DELL": "s4.case_pack.dell",
    "MU": "s4.case_pack.mu",
}
_SOURCE_GROUNDED_PACK_RESOURCE_IDS = {
    "DELL": "s4.source_grounded_input.dell",
    "MU": "s4.source_grounded_input.mu",
}
_METHOD_CONTRACT_RESOURCE_ID = "s4.financial_method_runtime_contract"
_SOURCE_GROUNDED_ROUTE_COUNTS = {"DELL": 11, "MU": 8}


class S4SourceGroundedInputPack(BaseModel):
    """Frozen issuer-bound S4 facts plus context-only graph rows.

    This object is intentionally separate from the T02 question/policy Case
    Pack. It can add sourced rows without mutating the frozen T02 contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "fin_ia_0_1_s4_t04_source_grounded_input_pack_v1_0"
    ]
    contract_ref: Literal[
        "fin01.s4.source_grounded_case_input:v1"
    ] = S4_SOURCE_GROUNDED_INPUT_CONTRACT_REF
    pack_id: str = Field(min_length=1)
    frozen_at: str = Field(min_length=1)
    status: Literal[
        "source_routes_executed_issuer_bound_input_head_ready"
    ]
    case_ticker: Literal["DELL", "MU"]
    legal_name: str = Field(min_length=1)
    issuer_identifier: str = Field(pattern=r"^CIK[0-9]{10}$")
    as_of: str = Field(min_length=1)
    source_snapshots: tuple[dict[str, Any], ...] = Field(min_length=1)
    route_execution_receipts: tuple[dict[str, Any], ...] = Field(min_length=1)
    evidence_rows: tuple[dict[str, Any], ...] = Field(min_length=1)
    numeric_rows: tuple[dict[str, Any], ...] = Field(min_length=1)
    derived_metrics: tuple[dict[str, Any], ...]
    graph_edges: tuple[dict[str, Any], ...] = Field(min_length=1)
    typed_gaps: tuple[dict[str, Any], ...] = Field(min_length=1)
    cannot_infer_boundaries: tuple[str, ...] = Field(min_length=1)
    authority_boundary: dict[str, Any]
    observed_counts: dict[str, int]
    source_pack_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_source_grounded_boundary(self) -> "S4SourceGroundedInputPack":
        route_ids = [
            str(row.get("route_id") or "")
            for row in self.route_execution_receipts
        ]
        expected_route_count = _SOURCE_GROUNDED_ROUTE_COUNTS[
            self.case_ticker
        ]
        expected_route_prefix = (
            f"p34_route::{self.case_ticker.lower()}_"
        )
        if (
            self.issuer_identifier
            != _CASE_CONFIG[self.case_ticker]["issuer_identifier"]
            or len(route_ids) != expected_route_count
            or len(set(route_ids)) != expected_route_count
            or any(
                not value.startswith(expected_route_prefix)
                for value in route_ids
            )
        ):
            raise ValueError("s4_source_grounded_route_coverage_invalid")
        if any(
            row.get("route_execution_status") == "planned_not_executed"
            for row in self.route_execution_receipts
        ):
            raise ValueError("s4_source_grounded_route_still_unexecuted")
        for row in self.evidence_rows:
            if (
                row.get("entity_ref") != self.case_ticker
                or not row.get("evidence_ref")
                or not row.get("source_url")
                or not row.get("citation")
                or not row.get("parser_lineage")
            ):
                raise ValueError("s4_source_grounded_evidence_row_invalid")
        for row in self.numeric_rows:
            if (
                row.get("entity_ref") != self.case_ticker
                or not row.get("numeric_ref")
                or not row.get("metric_family")
                or row.get("value") in (None, "")
                or not row.get("unit")
                or not row.get("period")
                or not row.get("source_ref")
                or not row.get("source_coordinate")
                or row.get("exact_value_authority") is not True
            ):
                raise ValueError("s4_source_grounded_numeric_row_invalid")
        for row in self.graph_edges:
            if (
                row.get("graph_edge_is_direct_evidence") is not False
                or not row.get("source_ref")
                or not row.get("boundary")
            ):
                raise ValueError("s4_source_grounded_graph_boundary_invalid")
        expected_counts = {
            "source_snapshots": len(self.source_snapshots),
            "route_execution_receipts": len(self.route_execution_receipts),
            "evidence_rows": len(self.evidence_rows),
            "numeric_rows": len(self.numeric_rows),
            "derived_metrics": len(self.derived_metrics),
            "graph_edges": len(self.graph_edges),
            "typed_gaps": len(self.typed_gaps),
        }
        if any(self.observed_counts.get(key) != value for key, value in expected_counts.items()):
            raise ValueError("s4_source_grounded_observed_counts_mismatch")
        digest_payload = self.model_dump(mode="json")
        digest_payload.pop("source_pack_digest", None)
        if canonical_digest(digest_payload) != self.source_pack_digest:
            raise ValueError("s4_source_grounded_pack_digest_mismatch")
        return self

def load_s4_source_grounded_input_pack(
    repo_root: str | Path,
    case_ticker: str,
) -> S4SourceGroundedInputPack:
    """Load one frozen source-grounded input without executing a source route."""

    try:
        relative_path = _SOURCE_GROUNDED_PACK_PATHS[case_ticker]
    except KeyError as exc:
        raise S4CaseRuntimeError(
            "s4_source_grounded_input_case_unsupported"
        ) from exc
    raw = read_registered_runtime_json(
        repo_root,
        _SOURCE_GROUNDED_PACK_RESOURCE_IDS[case_ticker],
    )
    try:
        pack = S4SourceGroundedInputPack.model_validate(raw)
    except ValueError as exc:
        raise S4CaseRuntimeError(
            "s4_source_grounded_input_pack_invalid"
        ) from exc
    if (
        pack.case_ticker != case_ticker
        or pack.issuer_identifier != _CASE_CONFIG[case_ticker]["issuer_identifier"]
    ):
        raise S4CaseRuntimeError(
            "s4_source_grounded_input_identity_mismatch"
        )
    return pack


def _binding_digest_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    payload.pop("runtime_binding_digest", None)
    return payload


def _assert_binding_digest(binding: S4CaseRuntimeBinding) -> None:
    expected = canonical_digest(
        _binding_digest_payload(binding.model_dump(mode="json"))
    )
    if expected != binding.runtime_binding_digest:
        raise S4CaseRuntimeError("s4_case_runtime_binding_digest_mismatch")


def _overlay_digest_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    payload.pop("overlay_digest", None)
    return payload


def apply_s4_case_runtime_research_profile_overlay(
    base_binding: S4CaseRuntimeBinding,
    *,
    research_profile_ref: str,
    research_profile_contract_payload: Mapping[str, Any],
) -> tuple[S4CaseRuntimeBinding, S4CaseRuntimeResearchProfileOverlay]:
    """Create an immutable effective binding without changing the frozen Case Pack."""

    _assert_binding_digest(base_binding)
    profile_payload = dict(research_profile_contract_payload)
    if (
        not research_profile_ref.strip()
        or profile_payload.get("profile_ref") != research_profile_ref
        or profile_payload.get("company") != base_binding.case_ticker
        or tuple(profile_payload.get("program_cell_ids") or ())
        != base_binding.program_cell_ids
        or profile_payload.get("maximum_cell_count")
        != len(base_binding.program_cell_ids)
    ):
        raise S4CaseRuntimeError(
            "s4_case_runtime_research_profile_overlay_scope_mismatch"
        )

    draft = base_binding.model_copy(
        update={
            "research_profile_ref": research_profile_ref,
            "runtime_binding_digest": "0" * 64,
        }
    )
    effective_binding = draft.model_copy(
        update={
            "runtime_binding_digest": canonical_digest(
                _binding_digest_payload(draft.model_dump(mode="json"))
            )
        }
    )
    _assert_binding_digest(effective_binding)
    overlay_payload = {
        "contract_ref": S4_CASE_RUNTIME_RESEARCH_PROFILE_OVERLAY_REF,
        "case_ticker": base_binding.case_ticker,
        "program_cell_ids": list(base_binding.program_cell_ids),
        "base_case_pack_sha256": base_binding.case_pack_sha256,
        "base_runtime_binding_digest": base_binding.runtime_binding_digest,
        "research_profile_ref": research_profile_ref,
        "research_profile_contract_digest": canonical_digest(profile_payload),
        "effective_runtime_binding_digest": (
            effective_binding.runtime_binding_digest
        ),
    }
    overlay = S4CaseRuntimeResearchProfileOverlay(
        **overlay_payload,
        overlay_digest=canonical_digest(overlay_payload),
    )
    return effective_binding, overlay


def assert_s4_case_runtime_research_profile_overlay(
    effective_binding: S4CaseRuntimeBinding,
    value: Mapping[str, Any],
) -> S4CaseRuntimeResearchProfileOverlay:
    """Validate embedded overlay lineage against an effective runtime binding."""

    _assert_binding_digest(effective_binding)
    try:
        overlay = S4CaseRuntimeResearchProfileOverlay.model_validate(dict(value))
    except ValueError as exc:
        raise S4CaseRuntimeError(
            "s4_case_runtime_research_profile_overlay_shape_invalid"
        ) from exc
    if (
        canonical_digest(
            _overlay_digest_payload(overlay.model_dump(mode="json"))
        )
        != overlay.overlay_digest
        or overlay.case_ticker != effective_binding.case_ticker
        or overlay.program_cell_ids != effective_binding.program_cell_ids
        or overlay.base_case_pack_sha256 != effective_binding.case_pack_sha256
        or overlay.research_profile_ref
        != effective_binding.research_profile_ref
        or overlay.effective_runtime_binding_digest
        != effective_binding.runtime_binding_digest
    ):
        raise S4CaseRuntimeError(
            "s4_case_runtime_research_profile_overlay_mismatch"
        )
    return overlay


def compile_s4_case_evidence_role_group_mapping(
    binding: S4CaseRuntimeBinding,
) -> S4CaseEvidenceRoleGroupMapping:
    """Derive exact evidence-role groups from the frozen Case runtime binding."""

    _assert_binding_digest(binding)
    if tuple(binding.program_cell_ids) != S4_PROGRAM_CELL_IDS:
        raise S4CaseRuntimeError("s4_role_group_program_cell_axis_mismatch")
    if len(binding.program_cell_contracts) != len(S4_PROGRAM_CELL_IDS):
        raise S4CaseRuntimeError("s4_role_group_cell_cardinality_mismatch")

    groups: list[S4CaseEvidenceRoleGroup] = []
    observed_roles: set[str] = set()
    for expected_cell_id, raw in zip(
        S4_PROGRAM_CELL_IDS, binding.program_cell_contracts, strict=True
    ):
        program_cell_id = str(raw.get("program_cell_id") or "")
        owner_role = str(raw.get("owner_role") or "")
        source_roles = tuple(
            str(role) for role in (raw.get("required_evidence_roles") or ())
        )
        if (
            program_cell_id != expected_cell_id
            or not owner_role
            or not source_roles
            or any(not role for role in source_roles)
            or len(set(source_roles)) != len(source_roles)
            or observed_roles.intersection(source_roles)
        ):
            raise S4CaseRuntimeError("s4_case_evidence_role_group_invalid")
        observed_roles.update(source_roles)
        group_payload = {
            "program_cell_id": program_cell_id,
            "owner_role": owner_role,
            "source_evidence_roles": list(source_roles),
        }
        groups.append(
            S4CaseEvidenceRoleGroup(
                **group_payload,
                role_group_digest=canonical_digest(group_payload),
            )
        )

    payload = {
        "contract_ref": S4_CASE_EVIDENCE_ROLE_GROUP_MAPPING_REF,
        "case_ticker": binding.case_ticker,
        "case_identity_namespace": binding.case_identity_namespace,
        "runtime_binding_digest": binding.runtime_binding_digest,
        "role_groups": [row.model_dump(mode="json") for row in groups],
        "exact_role_count": len(observed_roles),
    }
    return S4CaseEvidenceRoleGroupMapping(
        **payload,
        role_group_mapping_digest=canonical_digest(payload),
    )


def compile_s4_case_evidence_slot_alignment(
    binding: S4CaseRuntimeBinding,
    *,
    case_id: str,
    decision_surface_contract_ref: str,
    cells: Sequence[Mapping[str, Any]],
    slots: Sequence[Mapping[str, Any]],
) -> S4CaseEvidenceSlotAlignmentReceipt:
    """Resolve all case-local roles without renaming, fallback, or route execution."""

    if not case_id.strip() or not decision_surface_contract_ref.strip():
        raise S4CaseRuntimeError("s4_evidence_alignment_identity_required")
    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    cells_by_owner: dict[str, Mapping[str, Any]] = {}
    cells_by_version: dict[str, Mapping[str, Any]] = {}
    for cell in cells:
        if str(cell.get("contract_version_id") or "") != (
            decision_surface_contract_ref
        ):
            raise S4CaseRuntimeError("s4_evidence_alignment_surface_mismatch")
        owner_role = str(cell.get("owner_role") or "")
        cell_version_ref = str(cell.get("cell_version_id") or "")
        if (
            not owner_role
            or not cell_version_ref
            or owner_role in cells_by_owner
            or cell_version_ref in cells_by_version
        ):
            raise S4CaseRuntimeError("s4_evidence_alignment_cell_cardinality")
        cells_by_owner[owner_role] = cell
        cells_by_version[cell_version_ref] = cell

    expected_owners = {row.owner_role for row in mapping.role_groups}
    if set(cells_by_owner) != expected_owners:
        raise S4CaseRuntimeError("s4_evidence_alignment_cell_owner_mismatch")

    slots_by_cell: dict[str, list[Mapping[str, Any]]] = {
        cell_version_ref: [] for cell_version_ref in cells_by_version
    }
    for slot in slots:
        cell_version_ref = str(slot.get("cell_version_id") or "")
        if cell_version_ref not in slots_by_cell:
            raise S4CaseRuntimeError("s4_evidence_alignment_unknown_cell")
        slots_by_cell[cell_version_ref].append(slot)

    slot_bindings: list[S4CaseEvidenceSlotBinding] = []
    observed_slot_refs: set[str] = set()
    for group in mapping.role_groups:
        cell = cells_by_owner[group.owner_role]
        cell_version_ref = str(cell["cell_version_id"])
        cell_slots = slots_by_cell[cell_version_ref]
        roles = [str(row.get("evidence_role") or "") for row in cell_slots]
        if (
            len(roles) != len(set(roles))
            or set(roles) != set(group.source_evidence_roles)
        ):
            raise S4CaseRuntimeError(
                "s4_evidence_alignment_missing_extra_or_duplicate_role"
            )
        slots_by_role = {
            str(row["evidence_role"]): row for row in cell_slots
        }
        for evidence_role in group.source_evidence_roles:
            slot = slots_by_role[evidence_role]
            slot_version_ref = str(slot.get("slot_version_id") or "")
            acceptance_role = str(slot.get("acceptance_role") or "")
            entity_scope = tuple(str(row) for row in slot.get("entity_scope") or ())
            if (
                not slot_version_ref
                or slot_version_ref in observed_slot_refs
                or acceptance_role != group.owner_role
                or slot.get("required") is not True
                or entity_scope != (binding.case_ticker,)
            ):
                raise S4CaseRuntimeError(
                    "s4_evidence_alignment_slot_owner_or_scope_mismatch"
                )
            observed_slot_refs.add(slot_version_ref)
            binding_payload = {
                "program_cell_id": group.program_cell_id,
                "owner_role": group.owner_role,
                "evidence_role": evidence_role,
                "cell_version_ref": cell_version_ref,
                "slot_version_ref": slot_version_ref,
                "acceptance_role": acceptance_role,
            }
            slot_bindings.append(
                S4CaseEvidenceSlotBinding(
                    **binding_payload,
                    slot_binding_digest=canonical_digest(binding_payload),
                )
            )

    if len(slot_bindings) != mapping.exact_role_count:
        raise S4CaseRuntimeError("s4_evidence_alignment_role_count_mismatch")
    payload = {
        "contract_ref": S4_CASE_EVIDENCE_SLOT_ALIGNMENT_REF,
        "case_id": case_id,
        "decision_surface_contract_ref": decision_surface_contract_ref,
        "case_ticker": binding.case_ticker,
        "case_identity_namespace": binding.case_identity_namespace,
        "runtime_binding_digest": binding.runtime_binding_digest,
        "role_group_mapping_digest": mapping.role_group_mapping_digest,
        "slot_bindings": [
            row.model_dump(mode="json") for row in slot_bindings
        ],
        "resolved_role_count": len(slot_bindings),
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "canonical_writes": 0,
    }
    return S4CaseEvidenceSlotAlignmentReceipt(
        **payload,
        alignment_digest=canonical_digest(payload),
    )


def load_s4_case_runtime_binding(
    repo_root: str | Path,
    case_ticker: str,
) -> S4CaseRuntimeBinding:
    """Load and freeze one DELL/MU Case Pack into the shared runtime contract."""

    root = Path(repo_root).resolve()
    try:
        case_config = _CASE_CONFIG[case_ticker]
    except KeyError as exc:
        raise S4CaseRuntimeError("s4_case_runtime_case_unsupported") from exc

    case_bytes = read_registered_runtime_bytes(
        root,
        _CASE_PACK_RESOURCE_IDS[case_ticker],
    )
    method_bytes = read_registered_runtime_bytes(
        root,
        _METHOD_CONTRACT_RESOURCE_ID,
    )
    case_pack = read_registered_runtime_json(
        root,
        _CASE_PACK_RESOURCE_IDS[case_ticker],
    )
    method_contract = read_registered_runtime_json(
        root,
        _METHOD_CONTRACT_RESOURCE_ID,
    )
    case_sha = hashlib.sha256(case_bytes).hexdigest()
    method_sha = hashlib.sha256(method_bytes).hexdigest()
    if (
        case_sha != case_config["case_pack_sha256"]
        or method_sha != _METHOD_CONTRACT_SHA256
    ):
        raise S4CaseRuntimeError("s4_case_runtime_frozen_digest_mismatch")
    if (
        case_pack.get("schema_version")
        != "fin_ia_0_1_s4_t02_exact_case_pack_v1_0"
        or method_contract.get("contract_ref") != S4_METHOD_CONTRACT_REF
        or case_pack.get("status")
        != (
            "contract_translated_exact_case_pack_frozen_"
            "T03_fixture_and_runtime_injection_pending"
        )
    ):
        raise S4CaseRuntimeError("s4_case_runtime_schema_or_status_invalid")

    identity = case_pack.get("case_identity")
    shared = case_pack.get("shared_runtime_contract")
    cells = case_pack.get("program_cells")
    source_policy = case_pack.get("source_authority_policy")
    numeric_policy = case_pack.get("numeric_policy")
    graph_policy = case_pack.get("graph_policy")
    atom_contract = case_pack.get("judgment_atom_contract")
    factual = case_pack.get("factual_content_boundary")
    if not all(
        isinstance(value, dict)
        for value in (
            identity,
            shared,
            source_policy,
            numeric_policy,
            graph_policy,
            atom_contract,
            factual,
        )
    ) or not isinstance(cells, list):
        raise S4CaseRuntimeError("s4_case_runtime_case_pack_shape_invalid")
    if (
        identity.get("ticker") != case_ticker
        or identity.get("canonical_entity_ref") != case_ticker
        or identity.get("canonical_CaseVersion_id") is not None
        or shared.get("runtime_family") != "Fin01ResearchRuntime"
        or tuple(shared.get("program_cell_ids") or ()) != S4_PROGRAM_CELL_IDS
        or tuple(row.get("program_cell_id") for row in cells)
        != S4_PROGRAM_CELL_IDS
        or numeric_policy.get("entity_ref_must_equal") != case_ticker
        or graph_policy.get("graph_edge_is_direct_Evidence") is not False
        or atom_contract.get(
            "model_should_return_judgment_atoms_not_case_pack_structure"
        )
        is not True
        or any(factual.get(key) != [] for key in _FACTUAL_KEYS)
    ):
        raise S4CaseRuntimeError("s4_case_runtime_identity_or_boundary_invalid")

    consumer_rows = method_contract.get("runtime_consumer_registry")
    methods = method_contract.get("methods")
    if not isinstance(consumer_rows, list) or not isinstance(methods, list):
        raise S4CaseRuntimeError("s4_case_runtime_method_contract_shape_invalid")
    consumer_ids = tuple(str(row.get("consumer_id") or "") for row in consumer_rows)
    if consumer_ids != S4_RUNTIME_CONSUMER_IDS:
        raise S4CaseRuntimeError("s4_case_runtime_consumer_registry_mismatch")
    method_rows = [
        row
        for row in methods
        if row.get("method_id") == case_config["method_id"]
    ]
    if (
        len(method_rows) != 1
        or method_rows[0].get("case_scope") != [case_ticker]
        or method_rows[0].get("S4_T02_state") != "contract_translated"
    ):
        raise S4CaseRuntimeError("s4_case_runtime_method_scope_invalid")
    method = dict(method_rows[0])
    route_map = source_policy.get("route_order_by_cell")
    if (
        not isinstance(route_map, dict)
        or tuple(route_map) != S4_PROGRAM_CELL_IDS
        or any(
            not isinstance(routes, list) or not routes
            for routes in route_map.values()
        )
    ):
        raise S4CaseRuntimeError("s4_case_runtime_local_source_routes_invalid")

    namespace_payload = {
        "case_ticker": case_ticker,
        "legal_name": identity["legal_name"],
        "issuer_identifier": case_config["issuer_identifier"],
        "case_profile_ref": case_pack["case_profile_ref"],
        "as_of": identity["as_of"],
        "program_cell_ids": list(S4_PROGRAM_CELL_IDS),
    }
    namespace = (
        f"s4:{case_ticker}:{case_config['issuer_identifier']}:"
        f"{canonical_digest(namespace_payload)[:20]}"
    )
    consumer_requirements = {
        str(row["consumer_id"]): tuple(map(str, row.get("consumes") or ()))
        for row in consumer_rows
    }
    payload: dict[str, Any] = {
        "case_ticker": case_ticker,
        "legal_name": str(identity["legal_name"]),
        "issuer_identifier": str(case_config["issuer_identifier"]),
        "issuer_identifier_source_ref": str(
            case_config["issuer_identifier_source_ref"]
        ),
        "case_profile_ref": str(case_pack["case_profile_ref"]),
        "research_profile_ref": str(shared["research_profile_target_ref"]),
        "case_pack_ref": str(case_config["case_pack_ref"]),
        "case_pack_sha256": case_sha,
        "method_contract_path": _METHOD_CONTRACT_PATH,
        "method_contract_sha256": method_sha,
        "method_id": str(case_config["method_id"]),
        "input_contract_ref": str(shared["input_contract_ref"]),
        "output_contract_ref": str(shared["output_contract_ref"]),
        "as_of": str(identity["as_of"]),
        "program_cell_ids": S4_PROGRAM_CELL_IDS,
        "case_identity_namespace": namespace,
        "local_source_routes_by_cell": {
            str(cell_id): tuple(map(str, routes))
            for cell_id, routes in route_map.items()
        },
        "consumer_ids": S4_RUNTIME_CONSUMER_IDS,
        "consumer_requirements": consumer_requirements,
        "program_cell_contracts": tuple(dict(row) for row in cells),
        "source_authority_policy": dict(source_policy),
        "numeric_policy": dict(numeric_policy),
        "graph_policy": dict(graph_policy),
        "judgment_atom_contract": dict(atom_contract),
        "method_contract": method,
        "factual_content_counts": {key: 0 for key in _FACTUAL_KEYS},
    }
    draft = S4CaseRuntimeBinding(
        **payload,
        runtime_binding_digest="0" * 64,
    )
    binding = draft.model_copy(
        update={
            "runtime_binding_digest": canonical_digest(
                _binding_digest_payload(draft.model_dump(mode="json"))
            )
        }
    )
    _assert_binding_digest(binding)
    return binding


def _cell_contract_rows(
    binding: S4CaseRuntimeBinding,
    fields: Sequence[str],
) -> list[dict[str, Any]]:
    return [
        {
            "program_cell_id": row["program_cell_id"],
            **{field: row[field] for field in fields if field in row},
        }
        for row in binding.program_cell_contracts
    ]


def consume_s4_case_runtime_binding(
    binding: S4CaseRuntimeBinding,
    consumer_id: str,
) -> S4CaseRuntimeConsumerInjection:
    """Return the exact case-local method view owned by one existing consumer."""

    _assert_binding_digest(binding)
    if (
        consumer_id not in binding.consumer_ids
        or consumer_id not in binding.consumer_requirements
    ):
        raise S4CaseRuntimeError("s4_case_runtime_consumer_not_registered")

    if consumer_id == "evidence_route_plan":
        injected = {
            "source_authority_policy": binding.source_authority_policy,
            "local_source_routes_by_cell": binding.local_source_routes_by_cell,
            "cell_contracts": _cell_contract_rows(
                binding,
                (
                    "required_evidence_roles",
                    "typed_cannot_infer_codes",
                    "stop_rule",
                    "what_would_change_targets",
                ),
            ),
        }
    elif consumer_id == "financial_numeric_pack":
        injected = {
            "numeric_policy": binding.numeric_policy,
            "cell_contracts": _cell_contract_rows(
                binding,
                ("numeric_questions", "typed_cannot_infer_codes", "stop_rule"),
            ),
        }
    elif consumer_id == "bounded_graph_pack":
        injected = {
            "graph_policy": binding.graph_policy,
            "cell_contracts": _cell_contract_rows(
                binding,
                (
                    "graph_context_questions",
                    "required_evidence_roles",
                    "what_would_change_targets",
                ),
            ),
        }
    elif consumer_id == "specialist_and_research_lead":
        injected = {
            "method_contract": binding.method_contract,
            "judgment_atom_contract": binding.judgment_atom_contract,
            "cell_contracts": _cell_contract_rows(
                binding,
                (
                    "owner_role",
                    "decision_question",
                    "mandatory_judgment_chain",
                    "typed_cannot_infer_codes",
                    "stop_rule",
                    "what_would_change_targets",
                ),
            ),
        }
    elif consumer_id == "bounded_agent_input_and_execution":
        injected = {
            "input_contract_ref": binding.input_contract_ref,
            "output_contract_ref": binding.output_contract_ref,
            "method_contract": binding.method_contract,
            "judgment_atom_contract": binding.judgment_atom_contract,
            "source_authority_policy": binding.source_authority_policy,
            "numeric_policy": binding.numeric_policy,
            "graph_policy": binding.graph_policy,
        }
    elif consumer_id == "writer_verifier_and_review_surface":
        injected = {
            "method_id": binding.method_id,
            "judgment_atom_contract": binding.judgment_atom_contract,
            "cell_contracts": _cell_contract_rows(
                binding,
                (
                    "decision_question",
                    "typed_cannot_infer_codes",
                    "stop_rule",
                    "what_would_change_targets",
                ),
            ),
            "new_source_or_numeric_authority": False,
            "human_review_completed": False,
        }
    else:
        injected = {
            "method_id": binding.method_id,
            "cell_contracts": _cell_contract_rows(
                binding,
                (
                    "decision_question",
                    "typed_cannot_infer_codes",
                    "what_would_change_targets",
                ),
            ),
            "boundary_labels": {
                "candidate_is_evidence": False,
                "graph_edge_is_evidence": False,
                "numeric_requires_exact_scope": True,
                "human_review_completed": False,
            },
        }

    payload = {
        "runtime_binding_digest": binding.runtime_binding_digest,
        "consumer_id": consumer_id,
        "case_ticker": binding.case_ticker,
        "issuer_identifier": binding.issuer_identifier,
        "case_profile_ref": binding.case_profile_ref,
        "research_profile_ref": binding.research_profile_ref,
        "case_identity_namespace": binding.case_identity_namespace,
        "method_contract_sha256": binding.method_contract_sha256,
        "method_id": binding.method_id,
        "program_cell_ids": binding.program_cell_ids,
        "consumer_requirements": binding.consumer_requirements[consumer_id],
        "injected_contract": injected,
    }
    return S4CaseRuntimeConsumerInjection(
        **payload,
        injection_digest=canonical_digest(payload),
    )


def assert_s4_consumer_injection(
    binding: S4CaseRuntimeBinding,
    value: Mapping[str, Any],
    consumer_id: str,
) -> None:
    expected = consume_s4_case_runtime_binding(binding, consumer_id)
    try:
        observed = S4CaseRuntimeConsumerInjection.model_validate(dict(value))
    except ValueError as exc:
        raise S4CaseRuntimeError("s4_case_runtime_injection_shape_invalid") from exc
    if observed.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise S4CaseRuntimeError("s4_case_runtime_injection_mismatch")


def s4_scoped_local_ref(
    binding: S4CaseRuntimeBinding,
    *,
    program_cell_id: str,
    identity_kind: Literal["claim", "fact", "context", "WWC"],
    local_id: str,
) -> dict[str, str]:
    if program_cell_id not in binding.program_cell_ids or not local_id.strip():
        raise S4CaseRuntimeError("s4_case_runtime_scoped_ref_invalid")
    return {
        "case_identity_namespace": binding.case_identity_namespace,
        "identity_kind": identity_kind,
        "program_cell_id": program_cell_id,
        "local_id": local_id,
    }


def assert_s4_case_local_fact_rows(
    binding: S4CaseRuntimeBinding,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    for row in rows:
        if (
            row.get("case_identity_namespace")
            != binding.case_identity_namespace
            or row.get("entity_ref") != binding.case_ticker
            or row.get("issuer_identifier") != binding.issuer_identifier
            or row.get("program_cell_id") not in binding.program_cell_ids
        ):
            raise S4CaseRuntimeError("s4_case_runtime_cross_case_fact_leakage")


def assert_s4_structural_fixture_has_no_case_facts(
    structural_profile: Literal["SaaS", "Bank"],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    del structural_profile
    if rows:
        raise S4CaseRuntimeError(
            "s4_case_runtime_structural_fixture_fact_leakage"
        )


def assemble_s4_case_local_judgment_atom(
    binding: S4CaseRuntimeBinding,
    *,
    program_cell_id: str,
    provider_atom: Mapping[str, Any],
    fact_aliases: Mapping[str, str],
    context_aliases: Mapping[str, str],
    what_would_change_aliases: Mapping[str, str],
) -> dict[str, Any]:
    """Locally assemble IDs, scope, ClaimFactLink, lineage, and WWC refs."""

    required = {
        "epistemic_status",
        "direct_answer_atom",
        "counterevidence_atom",
        "boundary_atom",
        "selected_fact_aliases",
        "selected_context_aliases",
        "selected_WWC_aliases",
    }
    if set(provider_atom) != required:
        raise S4CaseRuntimeError("s4_case_runtime_judgment_atom_shape_invalid")
    if (
        program_cell_id not in binding.program_cell_ids
        or provider_atom["epistemic_status"]
        not in binding.judgment_atom_contract["epistemic_states"]
        or any(
            not isinstance(provider_atom[field], str)
            or not provider_atom[field].strip()
            for field in (
                "direct_answer_atom",
                "counterevidence_atom",
                "boundary_atom",
            )
        )
    ):
        raise S4CaseRuntimeError("s4_case_runtime_judgment_atom_value_invalid")

    alias_sets = (
        ("selected_fact_aliases", fact_aliases),
        ("selected_context_aliases", context_aliases),
        ("selected_WWC_aliases", what_would_change_aliases),
    )
    selected: dict[str, tuple[str, ...]] = {}
    for field, authority in alias_sets:
        aliases = provider_atom[field]
        if (
            not isinstance(aliases, list)
            or len(set(map(str, aliases))) != len(aliases)
            or any(alias not in authority for alias in aliases)
        ):
            raise S4CaseRuntimeError(
                "s4_case_runtime_judgment_atom_alias_invalid"
            )
        selected[field] = tuple(str(alias) for alias in aliases)
    if (
        provider_atom["epistemic_status"] == "cannot_infer"
        and selected["selected_fact_aliases"]
    ):
        raise S4CaseRuntimeError(
            "s4_case_runtime_cannot_infer_fact_support_forbidden"
        )

    local_seed = canonical_digest(
        {
            "binding": binding.runtime_binding_digest,
            "program_cell_id": program_cell_id,
            "provider_atom": dict(provider_atom),
        }
    )[:20]
    claim_ref = s4_scoped_local_ref(
        binding,
        program_cell_id=program_cell_id,
        identity_kind="claim",
        local_id=f"claim_{local_seed}",
    )
    support_fact_refs = [
        s4_scoped_local_ref(
            binding,
            program_cell_id=program_cell_id,
            identity_kind="fact",
            local_id=fact_aliases[alias],
        )
        for alias in selected["selected_fact_aliases"]
    ]
    context_refs = [
        s4_scoped_local_ref(
            binding,
            program_cell_id=program_cell_id,
            identity_kind="context",
            local_id=context_aliases[alias],
        )
        for alias in selected["selected_context_aliases"]
    ]
    wwc_refs = [
        s4_scoped_local_ref(
            binding,
            program_cell_id=program_cell_id,
            identity_kind="WWC",
            local_id=what_would_change_aliases[alias],
        )
        for alias in selected["selected_WWC_aliases"]
    ]
    return {
        "schema_ref": S4_CASE_LOCAL_JUDGMENT_ATOM_REF,
        "case_ticker": binding.case_ticker,
        "issuer_identifier": binding.issuer_identifier,
        "case_profile_ref": binding.case_profile_ref,
        "method_id": binding.method_id,
        "program_cell_id": program_cell_id,
        "claim_ref": claim_ref,
        "epistemic_status": provider_atom["epistemic_status"],
        "direct_answer_atom": provider_atom["direct_answer_atom"],
        "counterevidence_atom": provider_atom["counterevidence_atom"],
        "boundary_atom": provider_atom["boundary_atom"],
        "support_fact_refs": support_fact_refs,
        "context_refs": context_refs,
        "what_would_change_refs": wwc_refs,
        "claim_fact_links": [
            {
                "claim_ref": claim_ref,
                "fact_ref": fact_ref,
                "link_type": "direct_support",
            }
            for fact_ref in support_fact_refs
        ],
        "canonical_scope": {
            "entity_ref": binding.case_ticker,
            "issuer_identifier": binding.issuer_identifier,
            "business_scope_kind": "company_or_exact_issuer_disclosed_scope",
            "segment_ref": "__unallocated_until_exact_row__",
        },
        "lineage": {
            "runtime_binding_digest": binding.runtime_binding_digest,
            "method_contract_sha256": binding.method_contract_sha256,
            "local_assembly": True,
            "provider_owned_ID_or_scope": False,
        },
    }
