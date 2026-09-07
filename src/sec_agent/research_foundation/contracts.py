"""Strict, answer-free contracts for the DELL reference vertical.

The foundation document records research methods and source boundaries.  It is
not a case answer.  Runtime consumers receive a whitelist projection containing
only the requested question branches and the source/formula contracts they use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )


class CaseIdentity(_StrictFrozenModel):
    case_id: str = Field(min_length=1)
    subject_ticker: str = Field(min_length=1)
    subject_legal_name: str = Field(min_length=1)
    top_level_question_zh: str = Field(min_length=1)
    current_snapshot_state: str = Field(min_length=1)
    current_complete_financial_period: str = Field(min_length=1)
    public_demo_requires_latest_refresh: bool


class ScopeCeiling(_StrictFrozenModel):
    one_subject_company_only: bool
    context_entities: tuple[str, ...] = Field(min_length=1)
    context_entity_rule: str = Field(min_length=1)
    company_financial_window: str = Field(min_length=1)
    industry_and_model_window: str = Field(min_length=1)
    regulatory_window: str = Field(min_length=1)
    maximum_external_search_rounds_per_high_materiality_branch: int = Field(ge=1)
    maximum_results_per_search: int = Field(ge=1)
    maximum_captured_pages_per_branch: int = Field(ge=1)
    maximum_live_pages_per_run: int = Field(ge=1)
    maximum_sources_visible_per_agent_step: int = Field(ge=1)
    maximum_specialist_model_rounds: int = Field(ge=1)
    maximum_targeted_counter_reroutes: int = Field(ge=0)
    allow_unresolved_bounded_gaps: bool
    perfect_recall_or_accuracy_required: bool
    non_goals: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scope_invariants(self) -> "ScopeCeiling":
        if not self.one_subject_company_only:
            raise ValueError("reference_vertical_must_remain_single_subject")
        if not self.allow_unresolved_bounded_gaps:
            raise ValueError("bounded_gaps_must_remain_allowed")
        if self.perfect_recall_or_accuracy_required:
            raise ValueError("perfect_metric_gate_is_forbidden")
        if len(set(self.context_entities)) != len(self.context_entities):
            raise ValueError("context_entities_must_be_unique")
        if len(set(self.non_goals)) != len(self.non_goals):
            raise ValueError("non_goals_must_be_unique")
        return self


class SourceClasses(_StrictFrozenModel):
    A: str = Field(min_length=1)
    B: str = Field(min_length=1)
    C: str = Field(min_length=1)
    D: str = Field(min_length=1)


class SourceFamily(_StrictFrozenModel):
    source_family_id: str = Field(min_length=1)
    classes: tuple[Literal["A", "B", "C", "D"], ...] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    entrypoints: tuple[str, ...]
    storage_route: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    boundary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_family(self) -> "SourceFamily":
        if len(set(self.classes)) != len(self.classes):
            raise ValueError("source_family_classes_must_be_unique")
        invalid_entrypoints = [
            value
            for value in self.entrypoints
            if not value.startswith(("https://", "http://"))
        ]
        if invalid_entrypoints:
            raise ValueError("source_family_entrypoints_must_be_http_urls")
        return self


class QuestionBranch(_StrictFrozenModel):
    branch_id: str = Field(min_length=1)
    priority: Literal["high", "medium", "low"]
    objective: str = Field(min_length=1)
    required_source_families: tuple[str, ...] = Field(min_length=1)
    formula_ids: tuple[str, ...]
    counter_questions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_branch_members(self) -> "QuestionBranch":
        if len(set(self.required_source_families)) != len(
            self.required_source_families
        ):
            raise ValueError("required_source_families_must_be_unique")
        if len(set(self.formula_ids)) != len(self.formula_ids):
            raise ValueError("formula_ids_must_be_unique")
        return self


class Formula(_StrictFrozenModel):
    formula_id: str = Field(min_length=1)
    expression: str = Field(min_length=1)
    required_inputs: tuple[str, ...] = Field(min_length=1)
    output_authority: str = Field(min_length=1)
    stop_if: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_formula_inputs(self) -> "Formula":
        if len(set(self.required_inputs)) != len(self.required_inputs):
            raise ValueError("formula_required_inputs_must_be_unique")
        return self


class ContextDelivery(_StrictFrozenModel):
    protocol: Literal["MCP"]
    protocol_sdk: str = Field(min_length=1)
    selection_rule: str = Field(min_length=1)
    tool_result_states: tuple[
        Literal[
            "retrieval_candidate",
            "captured_source_candidate",
            "reviewed_evidence",
            "numeric_fact",
            "deterministic_derived_metric",
            "research_scenario",
            "typed_gap",
            "tool_failure",
        ],
        ...,
    ] = Field(min_length=1)
    candidate_is_not_evidence: bool
    search_snippet_is_not_source_text: bool
    numeric_fact_requires_typed_SQL_route: bool
    raw_private_paths_forbidden_in_model_context: bool
    model_context_compaction_rule: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_authority_boundaries(self) -> "ContextDelivery":
        required_true = (
            self.candidate_is_not_evidence,
            self.search_snippet_is_not_source_text,
            self.numeric_fact_requires_typed_SQL_route,
            self.raw_private_paths_forbidden_in_model_context,
        )
        if not all(required_true):
            raise ValueError("context_authority_boundaries_must_fail_closed")
        if len(set(self.tool_result_states)) != len(self.tool_result_states):
            raise ValueError("tool_result_states_must_be_unique")
        return self


class FreshnessContract(_StrictFrozenModel):
    special_event: str = Field(min_length=1)
    call_time_local: datetime
    pre_release_snapshot_must_not_claim_day_end_freshness: bool
    poll_order: tuple[str, ...] = Field(min_length=1)
    E0_earnings_event_seal: tuple[str, ...] = Field(min_length=1)
    E1_filing_seal: tuple[str, ...] = Field(min_length=1)
    public_complete_demo_requires: Literal[
        "E0_earnings_event_seal_with_an_explicit_current_quarter_structured_numeric_gap"
    ]
    E0_may_be_used_as: Literal[
        "event_aware_demo_and_issuer_disclosed_evidence_but_not_current_quarter_SQL_NumericFact"
    ]
    freshness_hold_conditions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_freshness_boundaries(self) -> "FreshnessContract":
        if not self.pre_release_snapshot_must_not_claim_day_end_freshness:
            raise ValueError("pre_release_snapshot_boundary_must_be_preserved")
        return self


class AcceptanceAndStop(_StrictFrozenModel):
    branch_terminal_states: tuple[
        Literal["supported", "countered", "bounded_gap", "not_material"], ...
    ] = Field(min_length=1)
    supported_target: str = Field(min_length=1)
    tolerance_policy: str = Field(min_length=1)
    no_perfect_metric_gate: bool
    must_have: tuple[str, ...] = Field(min_length=1)
    stop_and_leave_null: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_acceptance_boundaries(self) -> "AcceptanceAndStop":
        if not self.no_perfect_metric_gate:
            raise ValueError("perfect_metric_gate_must_remain_disabled")
        if len(set(self.branch_terminal_states)) != len(
            self.branch_terminal_states
        ):
            raise ValueError("branch_terminal_states_must_be_unique")
        return self


class AnswerPolicy(_StrictFrozenModel):
    contains_case_answer: Literal[False]
    contains_target_company_forecast: Literal[False]
    contains_hidden_gold: Literal[False]
    method_and_formula_injection_allowed: Literal[True]
    runtime_must_record_method_digest_and_selected_branch_ids: Literal[True]


class DellReferenceVerticalFoundation(_StrictFrozenModel):
    schema_version: Literal["fin_ia_dell_reference_vertical_foundation_v1_0"]
    status: Literal["active_single_case_foundation"]
    recorded_at: datetime
    purpose: str = Field(min_length=1)
    case_identity: CaseIdentity
    scope_ceiling: ScopeCeiling
    source_classes: SourceClasses
    source_families: tuple[SourceFamily, ...] = Field(min_length=1)
    question_branches: tuple[QuestionBranch, ...] = Field(min_length=1)
    formulas: tuple[Formula, ...] = Field(min_length=1)
    context_delivery: ContextDelivery
    freshness_contract: FreshnessContract
    acceptance_and_stop: AcceptanceAndStop
    answer_policy: AnswerPolicy

    @model_validator(mode="after")
    def validate_cross_references(self) -> "DellReferenceVerticalFoundation":
        source_family_ids = [row.source_family_id for row in self.source_families]
        branch_ids = [row.branch_id for row in self.question_branches]
        formula_ids = [row.formula_id for row in self.formulas]
        for label, values in (
            ("source_family_id", source_family_ids),
            ("branch_id", branch_ids),
            ("formula_id", formula_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate_{label}")

        known_source_families = set(source_family_ids)
        known_formulas = set(formula_ids)
        for branch in self.question_branches:
            unknown_sources = set(branch.required_source_families).difference(
                known_source_families
            )
            if unknown_sources:
                raise ValueError(
                    f"unknown_source_family_for_{branch.branch_id}:"
                    f"{','.join(sorted(unknown_sources))}"
                )
            unknown_formulas = set(branch.formula_ids).difference(known_formulas)
            if unknown_formulas:
                raise ValueError(
                    f"unknown_formula_for_{branch.branch_id}:"
                    f"{','.join(sorted(unknown_formulas))}"
                )
        return self


class DellResearchMethodProjection(_StrictFrozenModel):
    """Whitelist-only runtime projection; it has no answer/result fields."""

    schema_version: Literal["fin_ia_dell_research_method_projection_v1_0"]
    foundation_schema_version: Literal[
        "fin_ia_dell_reference_vertical_foundation_v1_0"
    ]
    case_identity: CaseIdentity
    scope_ceiling: ScopeCeiling
    source_classes: SourceClasses
    selected_branch_ids: tuple[str, ...] = Field(min_length=1)
    question_branches: tuple[QuestionBranch, ...] = Field(min_length=1)
    source_families: tuple[SourceFamily, ...] = Field(min_length=1)
    formulas: tuple[Formula, ...]
    context_delivery: ContextDelivery
    freshness_contract: FreshnessContract
    acceptance_and_stop: AcceptanceAndStop

    @model_validator(mode="after")
    def validate_projection_members(self) -> "DellResearchMethodProjection":
        projected_branch_ids = tuple(row.branch_id for row in self.question_branches)
        if projected_branch_ids != self.selected_branch_ids:
            raise ValueError("selected_branch_ids_must_match_projected_branches")
        referenced_sources = {
            source_id
            for branch in self.question_branches
            for source_id in branch.required_source_families
        }
        if referenced_sources != {
            row.source_family_id for row in self.source_families
        }:
            raise ValueError("projection_source_families_must_match_branch_references")
        referenced_formulas = {
            formula_id
            for branch in self.question_branches
            for formula_id in branch.formula_ids
        }
        if referenced_formulas != {row.formula_id for row in self.formulas}:
            raise ValueError("projection_formulas_must_match_branch_references")
        return self


class DellResearchMethodPackage(_StrictFrozenModel):
    schema_version: Literal["fin_ia_dell_research_method_package_v1_0"]
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method: DellResearchMethodProjection

    @model_validator(mode="after")
    def validate_digest(self) -> "DellResearchMethodPackage":
        if self.method_sha256 != canonical_sha256(self.method):
            raise ValueError("method_sha256_mismatch")
        return self


class DellResearchRunScope(_StrictFrozenModel):
    """One immutable, method-bound scope reused by every non-method tool.

    The scope is deliberately self-contained and deterministic.  A transport can
    validate it by projecting the same branches again; no mutable run registry is
    required.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=False,
        str_strip_whitespace=True,
    )

    schema_version: Literal["fin_ia_dell_research_run_scope_v1_0"]
    case_id: str = Field(min_length=1, max_length=160)
    research_as_of: datetime
    data_snapshot_id: str = Field(min_length=1, max_length=256)
    method_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_branch_ids: tuple[str, ...] = Field(min_length=1)
    execution_attempt_id: str = Field(min_length=1, max_length=160)
    source_policy: Literal[
        "frozen_local_reviewed_plus_public_web_locator_only"
    ]
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator(
        "case_id",
        "data_snapshot_id",
        "execution_attempt_id",
    )
    @classmethod
    def validate_nonempty_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("run_scope_identifier_empty")
        return normalized

    @field_validator("research_as_of")
    @classmethod
    def validate_aware_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("research_as_of_timezone_required")
        return value

    @model_validator(mode="after")
    def validate_scope_digest(self) -> "DellResearchRunScope":
        if len(set(self.selected_branch_ids)) != len(self.selected_branch_ids):
            raise ValueError("run_scope_branch_ids_must_be_unique")
        body = self.model_dump(mode="json", exclude={"run_scope_digest"})
        if self.run_scope_digest != canonical_sha256(body):
            raise ValueError("run_scope_digest_mismatch")
        return self


class DellResearchMethodBinding(_StrictFrozenModel):
    """Answer-free method package plus its exact run-bound scope."""

    schema_version: Literal["fin_ia_dell_research_method_binding_v1_0"]
    method_package: DellResearchMethodPackage
    run_scope: DellResearchRunScope

    @model_validator(mode="after")
    def validate_binding(self) -> "DellResearchMethodBinding":
        if self.run_scope.case_id != self.method_package.method.case_identity.case_id:
            raise ValueError("run_scope_case_id_mismatch")
        if self.run_scope.method_sha256 != self.method_package.method_sha256:
            raise ValueError("run_scope_method_sha256_mismatch")
        if (
            self.run_scope.selected_branch_ids
            != self.method_package.method.selected_branch_ids
        ):
            raise ValueError("run_scope_selected_branches_mismatch")
        return self


def _canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Return the SHA256 of the canonical UTF-8 JSON representation."""

    return sha256(_canonical_json_bytes(value)).hexdigest()


def load_dell_reference_vertical_foundation(
    path: str | Path = DEFAULT_DELL_REFERENCE_VERTICAL_FOUNDATION_PATH,
) -> DellReferenceVerticalFoundation:
    """Load and strictly validate the answer-free foundation contract."""

    return DellReferenceVerticalFoundation.model_validate_json(
        Path(path).read_bytes()
    )


def project_dell_research_method(
    foundation: DellReferenceVerticalFoundation,
    branch_ids: Sequence[str],
) -> DellResearchMethodPackage:
    """Project the selected branches in foundation order and seal the method.

    ``branch_ids`` is treated as a set: caller order and duplicates do not alter
    the package digest.  Unknown or empty selections fail closed.
    """

    requested = frozenset(branch_ids)
    if not requested:
        raise ValueError("at_least_one_branch_id_is_required")

    branches_by_id: Mapping[str, QuestionBranch] = {
        row.branch_id: row for row in foundation.question_branches
    }
    unknown = requested.difference(branches_by_id)
    if unknown:
        raise ValueError(f"unknown_branch_ids:{','.join(sorted(unknown))}")

    selected_branches = tuple(
        branch
        for branch in foundation.question_branches
        if branch.branch_id in requested
    )
    required_source_ids = {
        source_id
        for branch in selected_branches
        for source_id in branch.required_source_families
    }
    required_formula_ids = {
        formula_id
        for branch in selected_branches
        for formula_id in branch.formula_ids
    }
    projection = DellResearchMethodProjection(
        schema_version="fin_ia_dell_research_method_projection_v1_0",
        foundation_schema_version=foundation.schema_version,
        case_identity=foundation.case_identity,
        scope_ceiling=foundation.scope_ceiling,
        source_classes=foundation.source_classes,
        selected_branch_ids=tuple(row.branch_id for row in selected_branches),
        question_branches=selected_branches,
        source_families=tuple(
            row
            for row in foundation.source_families
            if row.source_family_id in required_source_ids
        ),
        formulas=tuple(
            row
            for row in foundation.formulas
            if row.formula_id in required_formula_ids
        ),
        context_delivery=foundation.context_delivery,
        freshness_contract=foundation.freshness_contract,
        acceptance_and_stop=foundation.acceptance_and_stop,
    )
    return DellResearchMethodPackage(
        schema_version="fin_ia_dell_research_method_package_v1_0",
        method_sha256=canonical_sha256(projection),
        method=projection,
    )


def bind_dell_research_method(
    foundation: DellReferenceVerticalFoundation,
    branch_ids: Sequence[str],
    *,
    research_as_of: datetime,
    data_snapshot_id: str,
    execution_attempt_id: str,
    source_policy: Literal[
        "frozen_local_reviewed_plus_public_web_locator_only"
    ] = "frozen_local_reviewed_plus_public_web_locator_only",
) -> DellResearchMethodBinding:
    """Project the answer-free method and seal the only valid tool-call scope."""

    package = project_dell_research_method(foundation, branch_ids)
    scope_body = {
        "schema_version": "fin_ia_dell_research_run_scope_v1_0",
        "case_id": package.method.case_identity.case_id,
        "research_as_of": research_as_of.isoformat().replace("+00:00", "Z"),
        "data_snapshot_id": data_snapshot_id,
        "method_sha256": package.method_sha256,
        "selected_branch_ids": package.method.selected_branch_ids,
        "execution_attempt_id": execution_attempt_id,
        "source_policy": source_policy,
    }
    scope = DellResearchRunScope(
        **{**scope_body, "research_as_of": research_as_of},
        run_scope_digest=canonical_sha256(scope_body),
    )
    return DellResearchMethodBinding(
        schema_version="fin_ia_dell_research_method_binding_v1_0",
        method_package=package,
        run_scope=scope,
    )
