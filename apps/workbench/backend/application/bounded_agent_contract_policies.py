from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, ClassVar, Mapping, Sequence

from sec_agent.canonical_runtime.failure_observation_policy import (
    S4_STRICT_TRUTH_KERNEL_POLICY_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest


S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF = (
    "fin01.s3.research_profile.nvda_three_cell:v1"
)
S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF = (
    "fin01.s3.research_profile.nvda_three_cell:v2"
)
S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF = (
    "fin01.s3.research_profile.nvda_three_cell:v3"
)
S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF = (
    "fin01.s3.research_profile.nvda_three_cell:v4"
)
S3_CLAIM_FACT_LINK_POLICY_REF = "fin01.s3.claim_fact_link_policy:v1"
S3_TASK_CLAIM_LINK_POLICY_REF = "fin01.s3.task_claim_link_policy:v1"
S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF = (
    "fin01.s3.what_would_change_authority_policy:v1"
)
S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF = (
    "fin01.s3.specialist_WWC_judgment_atom_deterministic_assembly:v1"
)
S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF = (
    "fin01.s4.specialist_WWC_judgment_atom_deterministic_"
    "temporal_authority:v2"
)
SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REFS = (
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
)
S4_CASE_NUMERIC_AUTHORITY_POLICY_REF = (
    "fin01.s4.case_numeric_authority_projection_and_deterministic_rendering:v1"
)
S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF = (
    "fin01.s4.case_numeric_authority_projection_and_deterministic_rendering:v2"
)
S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS = (
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
)
S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF = (
    "fin01.s4.deterministic_judgment_atom_planner_and_"
    "compiled_contract_invariants:v1"
)
S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF = (
    "fin01.s4.deterministic_judgment_atom_planner_and_"
    "compiled_contract_invariants:v2"
)
S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REFS = (
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF,
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
)
S4_CASE_DELIVERY_IDENTITY_POLICY_REF = (
    "fin01.s4.case_delivery_identity_projection:v1"
)
S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF = (
    "fin01.s4.case_delivery_identity_current_case_aware_provider_boundary:v2"
)
S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF = (
    "fin01.s4.case_delivery_identity_registry:v1"
)
S4_CASE_DELIVERY_IDENTITY_POLICY_REFS = (
    S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
)
S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF = (
    "fin01.s4.case_runtime_mandatory_material_truth_and_"
    "identity_safety_closure:v1"
)
S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF = (
    "fin01.provider.capability.strict_json_schema:v1"
)
S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF = (
    "fin01.provider.openai_structured_outputs_supported_subset:v1"
)
S4_STRICT_TRUTH_KERNEL_LOCAL_VALIDATOR_REF = (
    "fin01.s4.strict_truth_kernel.local_semantic_validator:v1"
)
S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF = (
    "fin01.s4.non_authoritative_narrative_shell:v1"
)


def estimate_provider_input_tokens(value: str) -> int:
    """Return a conservative, explicitly token-unit prompt estimate.

    This is intentionally an estimator rather than a tokenizer claim.  The
    larger of a UTF-8/4 and Unicode/2 projection is used so multibyte text is
    not priced as one token per byte while short or empty requests still
    reserve at least one input token.
    """

    if not isinstance(value, str):
        raise TypeError("provider_input_token_estimator_requires_string")
    utf8_bytes = len(value.encode("utf-8"))
    unicode_characters = len(value)
    return max(
        1,
        (utf8_bytes + 3) // 4,
        (unicode_characters + 1) // 2,
    )
S4_DELL_THREE_CELL_RESEARCH_PROFILE_REF = (
    "fin01.s4.research_profile.dell_oem_three_cell:v1"
)
S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF = (
    "fin01.s4.research_profile.dell_oem_three_cell:v2"
)
S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF = (
    "fin01.s4.research_profile.dell_oem_three_cell:v3"
)
S4_MU_THREE_CELL_RESEARCH_PROFILE_REF = (
    "fin01.s4.research_profile.mu_hbm_three_cell:v1"
)
S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF = (
    "fin01.s3.specialist_local_assembly_capacity."
    "validated_segment_union_upper_bound:v1"
)
S3_SPECIALIST_LOCAL_ASSEMBLY_LEGACY_CAPACITY_CONTRACT_REF = (
    "fin01.s3.specialist_local_assembly_capacity.legacy_fixed_whole:v1"
)
PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF = (
    "fin01.bounded_agent.profile_aware_artifact_lineage_validation:v1"
)
LEGACY_S3_ARTIFACT_LINEAGE_KEYS = (
    "T02_runtime_plan",
    "T03_evidence_route_plan",
    "T04_financial_pack",
    "T05_graph_pack",
    "T06_judgment_contract",
    "T07_presentation_contract",
)
S4_BASE_ARTIFACT_LINEAGE_KEYS = (
    "S4_T02_case_pack",
    "S4_T02_method_contract",
    "S4_T03_runtime_binding",
    "S4_T04_source_grounded_input",
)
S4_RESEARCH_PROFILE_OVERLAY_LINEAGE_KEY = (
    "S4_research_profile_overlay"
)
PROFILE_AWARE_ARTIFACT_LINEAGE_FAMILIES = frozenset(
    {
        "legacy_s3",
        "s4_base",
        "s4_research_profile_overlay",
        "unresolved",
    }
)
PROFILE_AWARE_ARTIFACT_LINEAGE_FAILURE_SUBTYPES = frozenset(
    {
        "bounded_agent_profile_lineage_contract_mismatch",
        "bounded_agent_profile_lineage_digest_mismatch",
        "bounded_agent_profile_lineage_overlay_mismatch",
    }
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ProfileAwareArtifactLineageError(ValueError):
    """Content-free L1 lineage failure safe for post-Provider persistence."""

    def __init__(
        self,
        validation_subtype: str,
        *,
        artifact_type: str,
        lineage_family: str,
    ) -> None:
        if (
            validation_subtype
            not in PROFILE_AWARE_ARTIFACT_LINEAGE_FAILURE_SUBTYPES
            or artifact_type
            not in {
                "bounded_agent_manifest",
                "bounded_agent_trace",
                "s4_case_runtime",
            }
            or lineage_family
            not in PROFILE_AWARE_ARTIFACT_LINEAGE_FAMILIES
        ):
            raise ValueError(
                "profile_aware_artifact_lineage_error_contract_invalid"
            )
        super().__init__(validation_subtype)
        self.telemetry = {
            "validation_contract_ref": (
                PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
            ),
            "validation_subtype": validation_subtype,
            "artifact_type": artifact_type,
            "lineage_family": lineage_family,
            "raw_output_persisted": False,
            "private_reasoning_persisted": False,
            "credential_persisted": False,
            "stack_persisted": False,
        }


@dataclass(frozen=True)
class ProfileAwareArtifactLineageContract:
    contract_ref: str
    lineage_family: str
    lineage_digest: str


def _raise_lineage(
    subtype: str,
    *,
    artifact_type: str,
    lineage_family: str,
) -> None:
    raise ProfileAwareArtifactLineageError(
        subtype,
        artifact_type=artifact_type,
        lineage_family=lineage_family,
    )


def _validate_lineage_rows(
    lineage: Mapping[str, Any],
    *,
    lineage_family: str,
    artifact_type: str,
) -> None:
    for row in lineage.values():
        if (
            not isinstance(row, Mapping)
            or set(row) != {"version_ref", "digest"}
            or not str(row.get("version_ref") or "").strip()
        ):
            _raise_lineage(
                "bounded_agent_profile_lineage_contract_mismatch",
                artifact_type=artifact_type,
                lineage_family=lineage_family,
            )
        if not _SHA256_PATTERN.fullmatch(
            str(row.get("digest") or "")
        ):
            _raise_lineage(
                "bounded_agent_profile_lineage_digest_mismatch",
                artifact_type=artifact_type,
                lineage_family=lineage_family,
            )


def _expected_lineage_family(
    *,
    s4_context: Mapping[str, Any] | None,
) -> tuple[str, tuple[str, ...]]:
    if s4_context is None:
        return "legacy_s3", LEGACY_S3_ARTIFACT_LINEAGE_KEYS
    raw_overlay = (
        s4_context.get("research_profile_overlay")
        if "binding" in s4_context
        else s4_context.get("research_profile_overlay")
    )
    if raw_overlay is None:
        return "s4_base", S4_BASE_ARTIFACT_LINEAGE_KEYS
    if not isinstance(raw_overlay, Mapping):
        _raise_lineage(
            "bounded_agent_profile_lineage_overlay_mismatch",
            artifact_type="s4_case_runtime",
            lineage_family="unresolved",
        )
    return (
        "s4_research_profile_overlay",
        (
            *S4_BASE_ARTIFACT_LINEAGE_KEYS,
            S4_RESEARCH_PROFILE_OVERLAY_LINEAGE_KEY,
        ),
    )


def _assert_lineage_row(
    lineage: Mapping[str, Any],
    key: str,
    *,
    version_ref: Any,
    digest: Any,
    lineage_family: str,
    overlay: bool = False,
) -> None:
    row = lineage[key]
    if row.get("version_ref") != version_ref:
        _raise_lineage(
            (
                "bounded_agent_profile_lineage_overlay_mismatch"
                if overlay
                else "bounded_agent_profile_lineage_contract_mismatch"
            ),
            artifact_type="bounded_agent_trace",
            lineage_family=lineage_family,
        )
    if row.get("digest") != digest:
        _raise_lineage(
            (
                "bounded_agent_profile_lineage_overlay_mismatch"
                if overlay
                else "bounded_agent_profile_lineage_digest_mismatch"
            ),
            artifact_type="bounded_agent_trace",
            lineage_family=lineage_family,
        )


def compile_profile_aware_artifact_lineage_contract(
    lineage: Mapping[str, Any],
    *,
    s4_case_runtime: Mapping[str, Any] | None,
) -> ProfileAwareArtifactLineageContract:
    """Validate locally compiled lineage and produce its manifest stamp."""

    family, expected_keys = _expected_lineage_family(
        s4_context=s4_case_runtime
    )
    if tuple(lineage) != expected_keys:
        key_delta = set(lineage).symmetric_difference(expected_keys)
        _raise_lineage(
            (
                "bounded_agent_profile_lineage_overlay_mismatch"
                if key_delta
                == {S4_RESEARCH_PROFILE_OVERLAY_LINEAGE_KEY}
                else "bounded_agent_profile_lineage_contract_mismatch"
            ),
            artifact_type="bounded_agent_trace",
            lineage_family=family,
        )
    _validate_lineage_rows(
        lineage,
        lineage_family=family,
        artifact_type="bounded_agent_trace",
    )
    if s4_case_runtime is not None:
        binding = s4_case_runtime.get("binding")
        source = s4_case_runtime.get("source_grounded_input")
        overlay = s4_case_runtime.get("research_profile_overlay")
        if not isinstance(binding, Mapping) or not isinstance(
            source, Mapping
        ):
            _raise_lineage(
                "bounded_agent_profile_lineage_contract_mismatch",
                artifact_type="s4_case_runtime",
                lineage_family=family,
            )
        _assert_lineage_row(
            lineage,
            "S4_T02_case_pack",
            version_ref=binding.get("case_profile_ref"),
            digest=binding.get("case_pack_sha256"),
            lineage_family=family,
        )
        _assert_lineage_row(
            lineage,
            "S4_T02_method_contract",
            version_ref=binding.get("method_contract_ref"),
            digest=binding.get("method_contract_sha256"),
            lineage_family=family,
        )
        _assert_lineage_row(
            lineage,
            "S4_T03_runtime_binding",
            version_ref=binding.get("contract_ref"),
            digest=binding.get("runtime_binding_digest"),
            lineage_family=family,
        )
        _assert_lineage_row(
            lineage,
            "S4_T04_source_grounded_input",
            version_ref=source.get("contract_ref"),
            digest=source.get("source_pack_digest"),
            lineage_family=family,
        )
        if overlay is not None:
            if (
                not isinstance(overlay, Mapping)
                or overlay.get("research_profile_ref")
                != binding.get("research_profile_ref")
                or overlay.get("effective_runtime_binding_digest")
                != binding.get("runtime_binding_digest")
            ):
                _raise_lineage(
                    "bounded_agent_profile_lineage_overlay_mismatch",
                    artifact_type="s4_case_runtime",
                    lineage_family=family,
                )
            _assert_lineage_row(
                lineage,
                S4_RESEARCH_PROFILE_OVERLAY_LINEAGE_KEY,
                version_ref=overlay.get("contract_ref"),
                digest=overlay.get("overlay_digest"),
                lineage_family=family,
                overlay=True,
            )
    return ProfileAwareArtifactLineageContract(
        contract_ref=(
            PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
        ),
        lineage_family=family,
        lineage_digest=canonical_digest(dict(lineage)),
    )


def validate_profile_aware_artifact_lineage_projection(
    *,
    lineage: Mapping[str, Any],
    manifest_contract_ref: Any,
    manifest_lineage_family: Any,
    manifest_lineage_digest: Any,
    s4_case_runtime: Mapping[str, Any] | None,
) -> ProfileAwareArtifactLineageContract:
    """Validate one persisted trace against its independent artifact projection."""

    family, expected_keys = _expected_lineage_family(
        s4_context=s4_case_runtime
    )
    if tuple(lineage) != expected_keys:
        key_delta = set(lineage).symmetric_difference(expected_keys)
        _raise_lineage(
            (
                "bounded_agent_profile_lineage_overlay_mismatch"
                if key_delta
                == {S4_RESEARCH_PROFILE_OVERLAY_LINEAGE_KEY}
                else "bounded_agent_profile_lineage_contract_mismatch"
            ),
            artifact_type="bounded_agent_trace",
            lineage_family=family,
        )
    if (
        manifest_contract_ref
        != PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
        or manifest_lineage_family != family
    ):
        _raise_lineage(
            "bounded_agent_profile_lineage_contract_mismatch",
            artifact_type="bounded_agent_manifest",
            lineage_family=family,
        )
    _validate_lineage_rows(
        lineage,
        lineage_family=family,
        artifact_type="bounded_agent_trace",
    )
    observed_digest = canonical_digest(dict(lineage))
    if (
        not _SHA256_PATTERN.fullmatch(
            str(manifest_lineage_digest or "")
        )
        or manifest_lineage_digest != observed_digest
    ):
        _raise_lineage(
            "bounded_agent_profile_lineage_digest_mismatch",
            artifact_type="bounded_agent_manifest",
            lineage_family=family,
        )
    if s4_case_runtime is not None:
        _assert_lineage_row(
            lineage,
            "S4_T02_case_pack",
            version_ref=s4_case_runtime.get("case_profile_ref"),
            digest=s4_case_runtime.get("case_pack_sha256"),
            lineage_family=family,
        )
        _assert_lineage_row(
            lineage,
            "S4_T02_method_contract",
            version_ref=s4_case_runtime.get("method_contract_ref"),
            digest=s4_case_runtime.get("method_contract_sha256"),
            lineage_family=family,
        )
        _assert_lineage_row(
            lineage,
            "S4_T03_runtime_binding",
            version_ref=s4_case_runtime.get(
                "runtime_binding_contract_ref"
            ),
            digest=s4_case_runtime.get("runtime_binding_digest"),
            lineage_family=family,
        )
        _assert_lineage_row(
            lineage,
            "S4_T04_source_grounded_input",
            version_ref=s4_case_runtime.get(
                "source_grounded_input_contract_ref"
            ),
            digest=s4_case_runtime.get(
                "source_grounded_input_digest"
            ),
            lineage_family=family,
        )
        overlay = s4_case_runtime.get("research_profile_overlay")
        if overlay is not None:
            workbench = s4_case_runtime.get("workbench_projection")
            if (
                not isinstance(overlay, Mapping)
                or not isinstance(workbench, Mapping)
                or overlay.get("research_profile_ref")
                != s4_case_runtime.get("research_profile_ref")
                or overlay.get("research_profile_ref")
                != workbench.get("research_profile_ref")
                or overlay.get("effective_runtime_binding_digest")
                != s4_case_runtime.get("runtime_binding_digest")
            ):
                _raise_lineage(
                    "bounded_agent_profile_lineage_overlay_mismatch",
                    artifact_type="s4_case_runtime",
                    lineage_family=family,
                )
            _assert_lineage_row(
                lineage,
                S4_RESEARCH_PROFILE_OVERLAY_LINEAGE_KEY,
                version_ref=overlay.get("contract_ref"),
                digest=overlay.get("overlay_digest"),
                lineage_family=family,
                overlay=True,
            )
    return ProfileAwareArtifactLineageContract(
        contract_ref=(
            PROFILE_AWARE_ARTIFACT_LINEAGE_VALIDATION_CONTRACT_REF
        ),
        lineage_family=family,
        lineage_digest=observed_digest,
    )


@dataclass(frozen=True)
class BoundedResearchProfile:
    """Versioned research-shape and capacity configuration.

    Domain policies consume this object rather than embedding a company, Cell
    inventory, or capacity number in Provider adapters.
    """

    profile_ref: str
    company: str
    program_cell_ids: tuple[str, ...]
    maximum_cell_count: int
    maximum_narrative_characters: int
    specialist_segment_max_utf8_bytes: int
    specialist_assembly_max_utf8_bytes: int
    specialist_segment_token_budgets: tuple[tuple[str, int], ...]
    owner_grade_stage_token_budgets: tuple[tuple[str, int], ...]
    owner_grade_lead_v2_stage_token_budgets: tuple[tuple[str, int], ...]
    owner_grade_aggregate_output_tokens: int
    owner_grade_lead_v2_aggregate_output_tokens: int
    research_lead_provider_raw_max_utf8_bytes: int = 6000
    research_lead_canonical_alias_max_utf8_bytes: int = 6000
    research_lead_local_expanded_hard_max_utf8_bytes: int = 8192
    research_lead_aggregate_narrative_max_characters: int = 3200
    research_lead_narrative_target_characters: int = 320
    research_lead_narrative_hard_max_characters: int = 320
    research_lead_narrative_character_limits_terminal: bool = True
    research_lead_local_capacity_formula_ref: str = (
        "fin01.s3.research_lead_local_capacity.legacy_fixed:v1"
    )

    def __post_init__(self) -> None:
        if (
            not self.profile_ref
            or not self.company
            or not self.program_cell_ids
            or self.maximum_cell_count != len(self.program_cell_ids)
            or len(set(self.program_cell_ids)) != len(self.program_cell_ids)
            or min(
                self.maximum_narrative_characters,
                self.specialist_segment_max_utf8_bytes,
                self.specialist_assembly_max_utf8_bytes,
                self.owner_grade_aggregate_output_tokens,
                self.owner_grade_lead_v2_aggregate_output_tokens,
                self.research_lead_provider_raw_max_utf8_bytes,
                self.research_lead_canonical_alias_max_utf8_bytes,
                self.research_lead_local_expanded_hard_max_utf8_bytes,
                self.research_lead_aggregate_narrative_max_characters,
                self.research_lead_narrative_target_characters,
                self.research_lead_narrative_hard_max_characters,
            )
            <= 0
            or self.specialist_assembly_max_utf8_bytes
            < self.specialist_segment_max_utf8_bytes
            or self.research_lead_provider_raw_max_utf8_bytes
            < self.research_lead_canonical_alias_max_utf8_bytes
            or self.research_lead_narrative_target_characters
            > self.research_lead_narrative_hard_max_characters
            or not self.research_lead_local_capacity_formula_ref
        ):
            raise ValueError("bounded_research_profile_invalid")
        for rows in (
            self.specialist_segment_token_budgets,
            self.owner_grade_stage_token_budgets,
            self.owner_grade_lead_v2_stage_token_budgets,
        ):
            if (
                not rows
                or len({key for key, _ in rows}) != len(rows)
                or any(not key or value <= 0 for key, value in rows)
            ):
                raise ValueError("bounded_research_profile_token_budget_invalid")

    @property
    def segment_token_budgets(self) -> dict[str, int]:
        return dict(self.specialist_segment_token_budgets)

    def stage_token_budgets(self, *, expanded_lead: bool) -> dict[str, int]:
        return dict(
            self.owner_grade_lead_v2_stage_token_budgets
            if expanded_lead
            else self.owner_grade_stage_token_budgets
        )

    def aggregate_output_tokens(self, *, expanded_lead: bool) -> int:
        return (
            self.owner_grade_lead_v2_aggregate_output_tokens
            if expanded_lead
            else self.owner_grade_aggregate_output_tokens
        )

    def assert_scope(
        self,
        *,
        company: str,
        program_cell_ids: Sequence[str],
        maximum_cell_count: int,
    ) -> None:
        if (
            company != self.company
            or tuple(program_cell_ids) != self.program_cell_ids
            or maximum_cell_count != self.maximum_cell_count
        ):
            raise ValueError("s3_bounded_admission_research_profile_scope_mismatch")


S3_NVDA_THREE_CELL_RESEARCH_PROFILE = BoundedResearchProfile(
    profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
    company="NVDA",
    program_cell_ids=(
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    ),
    maximum_cell_count=3,
    maximum_narrative_characters=320,
    specialist_segment_max_utf8_bytes=6000,
    specialist_assembly_max_utf8_bytes=8192,
    specialist_segment_token_budgets=(
        ("facts_explanation_and_terminal", 1600),
        ("owner_grade_claim_cards", 1200),
        ("actionable_what_would_change_tasks", 1400),
    ),
    owner_grade_stage_token_budgets=(
        ("specialist", 4200),
        ("lead", 1200),
        ("writer", 1400),
        ("verifier", 1000),
    ),
    owner_grade_lead_v2_stage_token_budgets=(
        ("specialist", 4200),
        ("lead", 1800),
        ("writer", 1400),
        ("verifier", 1000),
    ),
    owner_grade_aggregate_output_tokens=16200,
    owner_grade_lead_v2_aggregate_output_tokens=16800,
)

S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2 = replace(
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE,
    profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    research_lead_provider_raw_max_utf8_bytes=8192,
    research_lead_canonical_alias_max_utf8_bytes=6000,
    research_lead_local_expanded_hard_max_utf8_bytes=32768,
    research_lead_aggregate_narrative_max_characters=3200,
    research_lead_local_capacity_formula_ref=(
        "fin01.s3.research_lead_local_capacity."
        "exact_surface_maximum_valid_shape:v1"
    ),
)

S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3 = replace(
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
    profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
    research_lead_narrative_target_characters=320,
    research_lead_narrative_hard_max_characters=512,
)

S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4 = replace(
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3,
    profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
    research_lead_narrative_character_limits_terminal=False,
)

S4_DELL_THREE_CELL_RESEARCH_PROFILE = replace(
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4,
    profile_ref=S4_DELL_THREE_CELL_RESEARCH_PROFILE_REF,
    company="DELL",
)

S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2 = replace(
    S4_DELL_THREE_CELL_RESEARCH_PROFILE,
    profile_ref=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    specialist_segment_token_budgets=(
        ("facts_explanation_and_terminal", 1600),
        ("owner_grade_claim_cards", 1200),
        ("actionable_what_would_change_tasks", 1800),
    ),
    owner_grade_stage_token_budgets=(
        ("specialist", 4600),
        ("lead", 1200),
        ("writer", 1400),
        ("verifier", 1000),
    ),
    owner_grade_lead_v2_stage_token_budgets=(
        ("specialist", 4600),
        ("lead", 1800),
        ("writer", 1400),
        ("verifier", 1000),
    ),
    owner_grade_aggregate_output_tokens=17400,
    owner_grade_lead_v2_aggregate_output_tokens=18000,
)

S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3 = replace(
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2,
    profile_ref=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)

S4_MU_THREE_CELL_RESEARCH_PROFILE = replace(
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4,
    profile_ref=S4_MU_THREE_CELL_RESEARCH_PROFILE_REF,
    company="MU",
)

_RESEARCH_PROFILES = {
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE.profile_ref: (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE
    ),
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2.profile_ref: (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2
    ),
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3.profile_ref: (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3
    ),
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4.profile_ref: (
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4
    ),
    S4_DELL_THREE_CELL_RESEARCH_PROFILE.profile_ref: (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE
    ),
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2.profile_ref: (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2
    ),
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3.profile_ref: (
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3
    ),
    S4_MU_THREE_CELL_RESEARCH_PROFILE.profile_ref: (
        S4_MU_THREE_CELL_RESEARCH_PROFILE
    ),
}


def research_profile_for_ref(
    profile_ref: str | None,
) -> BoundedResearchProfile:
    """Resolve an explicit profile; legacy absence maps to the frozen S3 profile."""

    resolved = profile_ref or S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF
    try:
        return _RESEARCH_PROFILES[resolved]
    except KeyError as exc:
        raise ValueError("s3_bounded_admission_research_profile_unsupported") from exc


def bounded_research_profile_contract_payload(
    profile: BoundedResearchProfile,
) -> dict[str, Any]:
    """Return the complete deterministic payload bound by S4 profile overlays."""

    return {
        "contract_ref": "fin01.bounded_research_profile:v1",
        **asdict(profile),
    }


class NarrativeQualityPolicy:
    """Provider-neutral hard safety and non-terminal quality grading.

    The policy intentionally reports only closed field identifiers and length
    metadata. It never persists model text, row indexes, references, or private
    reasoning.
    """

    contract_ref = "fin01.s3.narrative_quality_policy:v1"
    layered_contract_ref = "fin01.s3.narrative_quality_policy:v2"
    contract_refs = frozenset({contract_ref, layered_contract_ref})
    quality_codes = frozenset(
        {
            "narrative_target_exceeded",
            "narrative_quality_ceiling_exceeded",
            "narrative_aggregate_quality_ceiling_exceeded",
        }
    )

    @classmethod
    def assess(
        cls,
        narrative_fields: Sequence[tuple[str, Any]],
        *,
        target_characters: int,
        hard_max_characters: int,
        length_exceedance_is_terminal: bool = True,
        aggregate_target_characters: int | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
        if (
            target_characters <= 0
            or hard_max_characters <= 0
            or target_characters > hard_max_characters
            or (
                aggregate_target_characters is not None
                and aggregate_target_characters <= 0
            )
        ):
            raise ValueError("narrative_quality_policy_limits_invalid")

        soft_by_code_and_field: dict[tuple[str, str], list[int]] = {}
        hard_by_subtype: dict[str, dict[str, int]] = {}
        aggregate_characters = 0
        for field_id, value in narrative_fields:
            subtype: str | None = None
            if not isinstance(value, str):
                subtype = "item_not_string"
            elif not value.strip():
                subtype = "item_blank"
            elif len(value) > hard_max_characters:
                aggregate_characters += len(value)
                if length_exceedance_is_terminal:
                    subtype = "item_over_max_unicode_characters"
                else:
                    soft_by_code_and_field.setdefault(
                        ("narrative_quality_ceiling_exceeded", field_id),
                        [],
                    ).append(len(value))
            elif len(value) > target_characters:
                aggregate_characters += len(value)
                soft_by_code_and_field.setdefault(
                    ("narrative_target_exceeded", field_id),
                    [],
                ).append(len(value))
            else:
                aggregate_characters += len(value)
            if subtype is not None:
                field_counts = hard_by_subtype.setdefault(subtype, {})
                field_counts[field_id] = field_counts.get(field_id, 0) + 1

        quality_contract_ref = (
            cls.contract_ref
            if length_exceedance_is_terminal
            and aggregate_target_characters is None
            else cls.layered_contract_ref
        )
        observations = [
            {
                "quality_contract_ref": quality_contract_ref,
                "quality_code": quality_code,
                "field_id": field_id,
                "failing_item_count": len(lengths),
                "maximum_observed_unicode_characters": max(lengths),
                "target_unicode_characters": target_characters,
                "quality_ceiling_unicode_characters": hard_max_characters,
                "acceptance_layer": "L4_user_fit_and_delivery",
                "disposition": "persist_quality_finding_and_continue",
                "terminal": False,
                "raw_text_persisted": False,
                "item_index_persisted": False,
            }
            for (quality_code, field_id), lengths in sorted(
                soft_by_code_and_field.items()
            )
        ]
        if (
            aggregate_target_characters is not None
            and aggregate_characters > aggregate_target_characters
        ):
            observations.append(
                {
                    "quality_contract_ref": quality_contract_ref,
                    "quality_code": (
                        "narrative_aggregate_quality_ceiling_exceeded"
                    ),
                    "field_id": "assembled_output",
                    "failing_item_count": 1,
                    "maximum_observed_unicode_characters": (
                        aggregate_characters
                    ),
                    "target_unicode_characters": target_characters,
                    "quality_ceiling_unicode_characters": (
                        aggregate_target_characters
                    ),
                    "acceptance_layer": "L4_user_fit_and_delivery",
                    "disposition": "persist_quality_finding_and_continue",
                    "terminal": False,
                    "raw_text_persisted": False,
                    "item_index_persisted": False,
                }
            )
        return observations, hard_by_subtype


@dataclass(frozen=True)
class SpecialistTransportContract:
    """Capabilities owned by a Provider transport version.

    Validators and prompt builders consume these flags. They do not infer
    behavior from version-number sets.
    """

    transport_ref: str
    field_local_text: bool = False
    closed_context_authority: bool = False
    epistemic_status_state: bool = False
    bounded_assembly: bool = False
    local_scope_assembly: bool = False
    field_local_fact_support_authority: bool = False
    field_local_what_would_change_authority: bool = False
    what_would_change_judgment_atom_assembly: bool = False
    explicit_output_capture_binding: bool = False
    local_deterministic_fact_interaction: bool = False


_TRANSPORT_PREFIX = (
    "fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist"
)

_SPECIALIST_TRANSPORT_CONTRACTS = {
    f"{_TRANSPORT_PREFIX}:v1": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v1",
    ),
    f"{_TRANSPORT_PREFIX}:v2": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v2",
        field_local_text=True,
    ),
    f"{_TRANSPORT_PREFIX}:v3": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v3",
        field_local_text=True,
        closed_context_authority=True,
    ),
    f"{_TRANSPORT_PREFIX}:v4": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v4",
        field_local_text=True,
        closed_context_authority=True,
        epistemic_status_state=True,
        explicit_output_capture_binding=True,
    ),
    f"{_TRANSPORT_PREFIX}:v5": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v5",
        field_local_text=True,
        closed_context_authority=True,
        epistemic_status_state=True,
        bounded_assembly=True,
        explicit_output_capture_binding=True,
    ),
    f"{_TRANSPORT_PREFIX}:v6": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v6",
        field_local_text=True,
        closed_context_authority=True,
        epistemic_status_state=True,
        bounded_assembly=True,
        local_scope_assembly=True,
        explicit_output_capture_binding=True,
    ),
    f"{_TRANSPORT_PREFIX}:v7": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v7",
        field_local_text=True,
        closed_context_authority=True,
        epistemic_status_state=True,
        bounded_assembly=True,
        local_scope_assembly=True,
        field_local_fact_support_authority=True,
        field_local_what_would_change_authority=True,
        explicit_output_capture_binding=True,
    ),
    f"{_TRANSPORT_PREFIX}:v8": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v8",
        field_local_text=True,
        closed_context_authority=True,
        epistemic_status_state=True,
        bounded_assembly=True,
        local_scope_assembly=True,
        field_local_fact_support_authority=True,
        field_local_what_would_change_authority=True,
        what_would_change_judgment_atom_assembly=True,
        explicit_output_capture_binding=True,
    ),
    f"{_TRANSPORT_PREFIX}:v9": SpecialistTransportContract(
        transport_ref=f"{_TRANSPORT_PREFIX}:v9",
        field_local_text=True,
        closed_context_authority=True,
        epistemic_status_state=True,
        bounded_assembly=True,
        local_scope_assembly=True,
        field_local_fact_support_authority=True,
        field_local_what_would_change_authority=True,
        what_would_change_judgment_atom_assembly=True,
        explicit_output_capture_binding=True,
        local_deterministic_fact_interaction=True,
    ),
}


def specialist_transport_contract(
    transport_ref: str,
) -> SpecialistTransportContract:
    try:
        return _SPECIALIST_TRANSPORT_CONTRACTS[transport_ref]
    except KeyError as exc:
        raise ValueError("s3_segmented_specialist_transport_unknown") from exc


def specialist_transport_refs() -> tuple[str, ...]:
    return tuple(_SPECIALIST_TRANSPORT_CONTRACTS)


def specialist_assembled_output_max_utf8_bytes(
    *,
    transport_ref: str,
    research_profile: BoundedResearchProfile,
) -> int:
    """Resolve the whole-output limit from capabilities plus profile capacity."""

    contract = specialist_transport_contract(transport_ref)
    return (
        research_profile.specialist_assembly_max_utf8_bytes
        if contract.bounded_assembly
        else research_profile.specialist_segment_max_utf8_bytes
    )


@dataclass(frozen=True)
class SpecialistLocalAssemblyCapacity:
    """Closed provider/local-segment/validated-union capacity envelope."""

    contract_ref: str
    provider_raw_segment_limit_utf8_bytes: int
    post_local_expansion_segment_limit_utf8_bytes: int
    validated_segment_count: int
    whole_union_limit_utf8_bytes: int

    def __post_init__(self) -> None:
        if (
            not self.contract_ref
            or min(
                self.provider_raw_segment_limit_utf8_bytes,
                self.post_local_expansion_segment_limit_utf8_bytes,
                self.validated_segment_count,
                self.whole_union_limit_utf8_bytes,
            )
            <= 0
            or self.post_local_expansion_segment_limit_utf8_bytes
            < self.provider_raw_segment_limit_utf8_bytes
            or self.whole_union_limit_utf8_bytes
            < self.post_local_expansion_segment_limit_utf8_bytes
        ):
            raise ValueError("specialist_local_assembly_capacity_invalid")

    def failure_telemetry(
        self,
        *,
        observed_validated_segment_utf8_bytes: Sequence[int],
        observed_whole_union_utf8_bytes: int,
        failure_phase: str,
    ) -> dict[str, Any]:
        observed = tuple(observed_validated_segment_utf8_bytes)
        if (
            len(observed) != self.validated_segment_count
            or any(type(value) is not int or value < 0 for value in observed)
            or type(observed_whole_union_utf8_bytes) is not int
            or observed_whole_union_utf8_bytes < 0
            or not failure_phase
        ):
            raise ValueError(
                "specialist_local_assembly_capacity_telemetry_invalid"
            )
        return {
            "contract_ref": self.contract_ref,
            "segment_count": self.validated_segment_count,
            "provider_raw_segment_limit_utf8_bytes": (
                self.provider_raw_segment_limit_utf8_bytes
            ),
            "post_local_expansion_segment_limit_utf8_bytes": (
                self.post_local_expansion_segment_limit_utf8_bytes
            ),
            "whole_union_limit_utf8_bytes": (
                self.whole_union_limit_utf8_bytes
            ),
            "observed_validated_segment_utf8_bytes": list(observed),
            "observed_whole_union_utf8_bytes": (
                observed_whole_union_utf8_bytes
            ),
            "failure_phase": failure_phase,
            "raw_text_persisted": False,
            "private_reasoning_persisted": False,
            "credentials_persisted": False,
            "stack_persisted": False,
            "exception_message_persisted": False,
        }


def specialist_local_assembly_capacity(
    *,
    transport_ref: str,
    research_profile: BoundedResearchProfile,
) -> SpecialistLocalAssemblyCapacity:
    """Resolve both local-segment and whole-union limits from one owner."""

    contract = specialist_transport_contract(transport_ref)
    local_limit = (
        research_profile.specialist_assembly_max_utf8_bytes
        if contract.local_scope_assembly
        else research_profile.specialist_segment_max_utf8_bytes
    )
    if (
        research_profile.profile_ref
        == S4_DELL_THREE_CELL_RESEARCH_PROFILE_V3_REF
    ):
        if not contract.local_scope_assembly:
            raise ValueError(
                "specialist_local_assembly_capacity_transport_required"
            )
        validated_segment_count = 3
        whole_limit = validated_segment_count * local_limit
        contract_ref = S3_SPECIALIST_LOCAL_ASSEMBLY_CAPACITY_CONTRACT_REF
    else:
        validated_segment_count = 3 if contract.local_scope_assembly else 1
        whole_limit = specialist_assembled_output_max_utf8_bytes(
            transport_ref=transport_ref,
            research_profile=research_profile,
        )
        contract_ref = (
            S3_SPECIALIST_LOCAL_ASSEMBLY_LEGACY_CAPACITY_CONTRACT_REF
        )
    return SpecialistLocalAssemblyCapacity(
        contract_ref=contract_ref,
        provider_raw_segment_limit_utf8_bytes=(
            research_profile.specialist_segment_max_utf8_bytes
        ),
        post_local_expansion_segment_limit_utf8_bytes=local_limit,
        validated_segment_count=validated_segment_count,
        whole_union_limit_utf8_bytes=whole_limit,
    )


@dataclass(frozen=True)
class ResearchLeadTransportContract:
    """Provider-neutral Lead capabilities, independent of version branching."""

    transport_ref: str
    closed_semantic_output: bool = False
    conflict_local_fact_presence: bool = False
    typed_scoped_identity: bool = False
    compact_scoped_alias_wire: bool = False
    local_row_ids: bool = False
    dual_capacity: bool = False
    gap_atom_deterministic_projection: bool = False
    case_material_truth_identity_safety_composable: bool = False
    conflict_fact_presence_materialization_policy_ref: str | None = None
    claim_evidence_state_local_narrative_policy_ref: str | None = None


@dataclass(frozen=True)
class ResearchLeadConflictFactPresenceMaterializationPolicy:
    """Single owner for deterministic conflict fact-presence summaries."""

    policy_ref: str
    provider_field_id: str
    canonical_field_id: str
    truth_table: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if (
            not self.policy_ref
            or self.provider_field_id != "fact_presence_summary"
            or self.canonical_field_id != "fact_presence_summary"
            or dict(self.truth_table)
            != {
                "all_involved_claims_supported": "facts_present",
                "no_involved_claims_supported": "no_facts_present",
                "some_involved_claims_supported": "mixed_fact_presence",
            }
        ):
            raise ValueError(
                "s3_research_lead_conflict_fact_presence_"
                "materialization_policy_invalid"
            )

    def expected_summary(
        self,
        support_presence: Sequence[bool],
    ) -> str:
        if not support_presence:
            raise ValueError(
                "s3_research_lead_conflict_fact_presence_input_empty"
            )
        truth_table = dict(self.truth_table)
        if all(support_presence):
            return truth_table["all_involved_claims_supported"]
        if any(support_presence):
            return truth_table["some_involved_claims_supported"]
        return truth_table["no_involved_claims_supported"]


S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY = (
    ResearchLeadConflictFactPresenceMaterializationPolicy(
        policy_ref=(
            "fin01.s3.research_lead.conflict_fact_presence_"
            "local_materialization:v1"
        ),
        provider_field_id="fact_presence_summary",
        canonical_field_id="fact_presence_summary",
        truth_table=(
            ("all_involved_claims_supported", "facts_present"),
            ("no_involved_claims_supported", "no_facts_present"),
            ("some_involved_claims_supported", "mixed_fact_presence"),
        ),
    )
)


S3_RESEARCH_LEAD_CLAIM_EVIDENCE_STATE_LOCAL_NARRATIVE_POLICY_REF = (
    "fin01.s3.research_lead.claim_evidence_state_local_narrative_"
    "materialization:v1"
)


@dataclass(frozen=True)
class ResearchLeadGapAtomProjectionPolicy:
    """Single source for Provider atoms, local ranking, and L2 telemetry."""

    policy_ref: str
    provider_field_id: str
    canonical_field_id: str
    canonical_maximum: int
    atom_fields: tuple[str, ...]
    claim_uncertainty_ranks: tuple[tuple[str, int], ...]
    ranking_fields: tuple[str, ...]
    finding_code: str
    acceptance_layer: str

    def __post_init__(self) -> None:
        if (
            not self.policy_ref
            or self.provider_field_id == self.canonical_field_id
            or self.canonical_maximum <= 0
            or self.atom_fields
            != (
                "statement",
                "claim_ids",
                "what_would_change_task_ids",
            )
            or len(dict(self.claim_uncertainty_ranks))
            != len(self.claim_uncertainty_ranks)
            or not self.ranking_fields
            or not self.finding_code
            or self.acceptance_layer != "L2_recoverable_protocol"
        ):
            raise ValueError("s3_research_lead_gap_atom_projection_policy_invalid")

    @property
    def uncertainty_rank_by_status(self) -> dict[str, int]:
        return dict(self.claim_uncertainty_ranks)


S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY = (
    ResearchLeadGapAtomProjectionPolicy(
        policy_ref=(
            "fin01.s3.research_lead_gap_atom_deterministic_projection:v1"
        ),
        provider_field_id="remaining_gap_atoms",
        canonical_field_id="remaining_gaps",
        canonical_maximum=4,
        atom_fields=(
            "statement",
            "claim_ids",
            "what_would_change_task_ids",
        ),
        claim_uncertainty_ranks=(
            ("cannot_infer", 4),
            ("hypothesis", 3),
            ("bounded_inference", 2),
            ("fact_supported", 1),
        ),
        ranking_fields=(
            "has_nonempty_what_would_change_task_ids_desc",
            "maximum_linked_claim_uncertainty_rank_desc",
            "distinct_linked_program_cell_count_desc",
            "distinct_linked_claim_count_desc",
            "canonical_atom_digest_ascending",
            "provider_ordinal_ascending",
        ),
        finding_code=(
            "research_lead_gap_atom_overflow_deterministically_projected"
        ),
        acceptance_layer="L2_recoverable_protocol",
    )
)


_RESEARCH_LEAD_TRANSPORT_PREFIX = (
    "fin01.s3.bounded_agent.research_lead_owner_grade"
)
_RESEARCH_LEAD_TRANSPORT_CONTRACTS = {
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v1": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v1",
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v2": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v2",
        closed_semantic_output=True,
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v3": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v3",
        closed_semantic_output=True,
        conflict_local_fact_presence=True,
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v4": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v4",
        closed_semantic_output=True,
        conflict_local_fact_presence=True,
        typed_scoped_identity=True,
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v5": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v5",
        closed_semantic_output=True,
        conflict_local_fact_presence=True,
        typed_scoped_identity=True,
        compact_scoped_alias_wire=True,
        local_row_ids=True,
        dual_capacity=True,
        case_material_truth_identity_safety_composable=True,
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v6": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v6",
        closed_semantic_output=True,
        conflict_local_fact_presence=True,
        typed_scoped_identity=True,
        compact_scoped_alias_wire=True,
        local_row_ids=True,
        dual_capacity=True,
        gap_atom_deterministic_projection=True,
        case_material_truth_identity_safety_composable=True,
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v7": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v7",
        closed_semantic_output=True,
        conflict_local_fact_presence=True,
        typed_scoped_identity=True,
        compact_scoped_alias_wire=True,
        local_row_ids=True,
        dual_capacity=True,
        case_material_truth_identity_safety_composable=True,
        conflict_fact_presence_materialization_policy_ref=(
            S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
            .policy_ref
        ),
    ),
    f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v8": ResearchLeadTransportContract(
        transport_ref=f"{_RESEARCH_LEAD_TRANSPORT_PREFIX}:v8",
        closed_semantic_output=True,
        conflict_local_fact_presence=True,
        typed_scoped_identity=True,
        compact_scoped_alias_wire=True,
        local_row_ids=True,
        dual_capacity=True,
        gap_atom_deterministic_projection=True,
        case_material_truth_identity_safety_composable=True,
        conflict_fact_presence_materialization_policy_ref=(
            S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
            .policy_ref
        ),
        claim_evidence_state_local_narrative_policy_ref=(
            S3_RESEARCH_LEAD_CLAIM_EVIDENCE_STATE_LOCAL_NARRATIVE_POLICY_REF
        ),
    ),
}


def research_lead_transport_contract(
    transport_ref: str,
) -> ResearchLeadTransportContract:
    try:
        return _RESEARCH_LEAD_TRANSPORT_CONTRACTS[transport_ref]
    except KeyError as exc:
        raise ValueError("s3_research_lead_transport_unknown") from exc


def research_lead_transport_refs() -> tuple[str, ...]:
    return tuple(_RESEARCH_LEAD_TRANSPORT_CONTRACTS)


@dataclass(frozen=True)
class AuthorityViolation:
    subtype: str
    failing_item_count: int

    def __post_init__(self) -> None:
        if not self.subtype or self.failing_item_count <= 0:
            raise ValueError("bounded_authority_violation_invalid")


def _exact_nonblank_strings(
    values: Any,
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return ()
    return tuple(
        sorted(
            {
                value
                for value in values
                if isinstance(value, str) and value.strip()
            }
        )
    )


@dataclass(frozen=True)
class CellAuthoritySurface:
    """Canonical projection of one Cell's four declared authority classes."""

    evidence_refs: tuple[str, ...]
    numeric_refs: tuple[str, ...]
    candidate_refs: tuple[str, ...]
    graph_context_refs: tuple[str, ...]

    @classmethod
    def from_cell_input(
        cls, cell_input: Mapping[str, Any]
    ) -> CellAuthoritySurface:
        authority = cell_input.get("authority_refs")
        authority = authority if isinstance(authority, Mapping) else {}
        return cls(
            evidence_refs=_exact_nonblank_strings(
                authority.get("accepted_evidence_refs")
            ),
            numeric_refs=_exact_nonblank_strings(authority.get("numeric_refs")),
            candidate_refs=_exact_nonblank_strings(
                authority.get("candidate_refs_not_evidence")
            ),
            graph_context_refs=_exact_nonblank_strings(
                authority.get("graph_context_refs_not_evidence")
            ),
        )


@dataclass(frozen=True)
class FactSupportAuthorityPolicy:
    """Closed, field-local Evidence/Numeric authority for Fact support."""

    evidence_refs: tuple[str, ...]
    numeric_refs: tuple[str, ...]
    candidate_refs: tuple[str, ...]
    graph_context_refs: tuple[str, ...]

    @classmethod
    def from_cell_input(
        cls, cell_input: Mapping[str, Any]
    ) -> FactSupportAuthorityPolicy:
        surface = CellAuthoritySurface.from_cell_input(cell_input)
        return cls(
            evidence_refs=surface.evidence_refs,
            numeric_refs=surface.numeric_refs,
            candidate_refs=surface.candidate_refs,
            graph_context_refs=surface.graph_context_refs,
        )

    def prompt_contract(self) -> dict[str, Any]:
        return {
            "contract_ref": "closed_fact_support_authority:v1",
            "field_id": "fact_layer.support_refs",
            "allowed_refs_by_support_type": {
                "Evidence": list(self.evidence_refs),
                "Numeric": list(self.numeric_refs),
            },
            "selection_rule": (
                "Each Fact must select a non-empty exact subset from the list "
                "matching its support_type."
            ),
            "cross_type_selection_allowed": False,
            "forbidden_authority_classes": [
                "Candidate",
                "Graph",
                "fact_id",
                "routing_ref",
                "free_text_or_derived_ref",
            ],
            "normalization_trim_remap_or_drop_allowed": False,
        }

    def first_violation(
        self, facts: Any
    ) -> AuthorityViolation | None:
        if not isinstance(facts, list):
            return AuthorityViolation("fact_layer_not_array", 1)

        invalid_support_type_count = 0
        refs_not_array_count = 0
        empty_count = 0
        invalid_item_count = 0
        forbidden_count = 0
        cross_type_count = 0
        outside_count = 0
        duplicate_count = 0
        evidence = set(self.evidence_refs)
        numeric = set(self.numeric_refs)
        forbidden = set(self.candidate_refs) | set(self.graph_context_refs)
        all_fact_authority = evidence | numeric
        for fact in facts:
            if not isinstance(fact, Mapping):
                continue
            support_type = fact.get("support_type")
            refs = fact.get("support_refs")
            if support_type not in {"Evidence", "Numeric"}:
                invalid_support_type_count += 1
                continue
            if not isinstance(refs, list):
                refs_not_array_count += 1
                continue
            if not refs:
                empty_count += 1
                continue
            valid_strings = [
                ref for ref in refs if isinstance(ref, str) and ref.strip()
            ]
            invalid_item_count += len(refs) - len(valid_strings)
            forbidden_count += sum(ref in forbidden for ref in valid_strings)
            opposite = numeric if support_type == "Evidence" else evidence
            cross_type_count += sum(ref in opposite for ref in valid_strings)
            allowed = evidence if support_type == "Evidence" else numeric
            outside_count += sum(
                ref not in all_fact_authority and ref not in forbidden
                for ref in valid_strings
            )
            duplicate_count += len(valid_strings) - len(set(valid_strings))
            # An authority value from the matching set is valid. Cross-type,
            # forbidden, and unknown values were classified above.
            _ = allowed

        precedence = (
            ("support_type_invalid", invalid_support_type_count),
            ("support_refs_not_array", refs_not_array_count),
            ("support_refs_empty", empty_count),
            ("item_not_nonblank_string", invalid_item_count),
            ("candidate_or_graph_ref_misclassified_as_fact", forbidden_count),
            ("evidence_or_numeric_cross_type", cross_type_count),
            ("outside_current_cell_fact_authority", outside_count),
            ("support_ref_duplicate", duplicate_count),
        )
        return next(
            (
                AuthorityViolation(subtype, count)
                for subtype, count in precedence
                if count
            ),
            None,
        )


@dataclass(frozen=True)
class CaseNumericAuthorityViolation:
    """Content-free L1 numeric-integrity failure."""

    subtype: str
    field_id: str
    failing_item_count: int
    contract_ref: str = S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
    match_paths: tuple[str, ...] = ()
    semantic_classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.subtype
            or not self.field_id
            or self.failing_item_count <= 0
            or self.contract_ref not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
            or any(
                not re.fullmatch(r"\$(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+", path)
                for path in self.match_paths
            )
            or any(
                not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", semantic_class)
                for semantic_class in self.semantic_classes
            )
        ):
            raise ValueError("s4_case_numeric_authority_violation_invalid")

    def telemetry(
        self,
        *,
        capture_sequence: int | None = None,
        provider_phase: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract_ref": self.contract_ref,
            "acceptance_layer": "L1_hard_integrity",
            "failure_subtype": self.subtype,
            "field_id": self.field_id,
            "failing_item_count": self.failing_item_count,
            "raw_text_persisted": False,
            "private_reasoning_persisted": False,
            "credentials_persisted": False,
            "stack_persisted": False,
        }
        if self.contract_ref == S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF:
            payload.update(
                {
                    "validator_rule_code": (
                        "material_numeric_provider_narrative_boundary_v2"
                    ),
                    "match_paths": list(self.match_paths),
                    "semantic_classes": list(self.semantic_classes),
                    "capture_sequence": capture_sequence,
                    "provider_phase": str(provider_phase or ""),
                }
            )
        return payload


@dataclass(frozen=True)
class CaseNumericNarrativeMatch:
    """Safe index entry for one classified provider-narrative surface."""

    field_id: str
    field_path: str
    semantic_class: str
    terminal: bool

    def safe_index(self) -> dict[str, Any]:
        return {
            "validator_rule_code": (
                "material_numeric_provider_narrative_boundary_v2"
            ),
            "field_path": self.field_path,
            "semantic_class": self.semantic_class,
            "terminal": self.terminal,
            "raw_match_persisted": False,
        }


@dataclass(frozen=True)
class S4FinalArtifactSafetyViolation:
    """Content-free final Artifact L1 safety-envelope failure."""

    subtype: str
    artifact_type: str
    field_id: str
    failing_item_count: int

    def __post_init__(self) -> None:
        if (
            not self.subtype
            or not self.artifact_type
            or not self.field_id
            or self.failing_item_count <= 0
        ):
            raise ValueError(
                "s4_final_artifact_safety_violation_invalid"
            )

    def telemetry(self) -> dict[str, Any]:
        return {
            "contract_ref": (
                S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF
            ),
            "acceptance_layer": "L1_hard_integrity",
            "failure_subtype": self.subtype,
            "artifact_type": self.artifact_type,
            "field_id": self.field_id,
            "failing_item_count": self.failing_item_count,
            "raw_text_persisted": False,
            "private_reasoning_persisted": False,
            "credentials_persisted": False,
            "stack_persisted": False,
        }


@dataclass(frozen=True)
class CaseNumericProjectionRow:
    alias: str
    numeric_ref: str
    authority_kind: str
    entity_ref: str
    business_scope_ref: str
    period: str
    metric_family: str
    comparison_operator: str
    exact_value: str
    currency: str
    unit: str
    scale_multiplier: str
    source_or_formula_lineage: str
    cannot_support: tuple[str, ...]
    formula: str
    input_numeric_refs: tuple[str, ...]
    rounding_rule: str
    projection_digest: str

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "numeric_ref": self.numeric_ref,
            "authority_kind": self.authority_kind,
            "entity_ref": self.entity_ref,
            "business_scope_ref": self.business_scope_ref,
            "period": self.period,
            "metric_family": self.metric_family,
            "comparison_operator": self.comparison_operator,
            "exact_value": self.exact_value,
            "currency": self.currency,
            "unit": self.unit,
            "scale_multiplier": self.scale_multiplier,
            "source_or_formula_lineage": self.source_or_formula_lineage,
            "cannot_support": list(self.cannot_support),
            "formula": self.formula,
            "input_numeric_refs": list(self.input_numeric_refs),
            "rounding_rule": self.rounding_rule,
            "projection_digest": self.projection_digest,
        }

    def provider_payload(self) -> dict[str, Any]:
        return {
            "numeric_alias": self.alias,
            "authority_kind": self.authority_kind,
            "entity_ref": self.entity_ref,
            "business_scope_ref": self.business_scope_ref,
            "period": self.period,
            "metric_family": self.metric_family,
            "comparison_operator": self.comparison_operator,
            "exact_value": self.exact_value,
            "currency": self.currency,
            "unit": self.unit,
            "scale_multiplier": self.scale_multiplier,
            "formula": self.formula,
            "input_numeric_aliases": [],
            "rounding_rule": self.rounding_rule,
            "cannot_support": list(self.cannot_support),
        }

    def rendered_clause(self) -> str:
        operator = {
            "exact": "=",
            "equals": "=",
            "greater_than": ">",
            "greater_than_or_equal": ">=",
            "less_than": "<",
            "less_than_or_equal": "<=",
        }.get(self.comparison_operator, self.comparison_operator)
        value = self.exact_value
        if self.unit == "percent":
            rendered_value = f"{value}%"
        else:
            prefix = f"{self.currency} " if self.currency else ""
            rendered_value = f"{prefix}{value} {self.unit}".strip()
        return (
            f"{self.entity_ref} {self.business_scope_ref} {self.period} "
            f"{self.metric_family} {operator} {rendered_value}"
        )


@dataclass(frozen=True)
class CaseNumericAuthorityPolicy:
    """One canonical owner for S4 flat and legacy numeric authority."""

    program_cell_id: str
    rows: tuple[CaseNumericProjectionRow, ...]
    contract_ref: str = S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
    allowed_reporting_period_labels: tuple[str, ...] = ()

    _NARRATIVE_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "statement",
            "boundary",
            "explanation_layer",
            "remaining_gaps",
            "terminal_state_summary",
            "fact_presence_summary",
            "resolution_status",
            "variant_view",
            "analysis_text_zh_cn",
            "issues",
            "issue_codes",
            "metric_or_observation",
            "source_type",
            "entity_or_owner",
            "document_event_or_dataset",
            "rule_type",
            "comparator_or_condition",
            "threshold_or_observation",
            "start_or_trigger",
            "deadline_or_review_date",
            "expected_claim_transition",
            "fallback_stop_condition",
            "qualification",
            "cannot_support",
        }
    )
    _PROVIDER_NUMERIC_TOKEN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<![A-Za-z_])[+\-]?(?:\d+(?:[.,]\d+)?|\.\d+)(?![A-Za-z_])"
        r"|[%％$¥￥]"
    )
    _V2_NUMERIC_VALUE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?<![A-Za-z_])[+\-]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?"
        r"|\d+(?:\.\d+)?|\.\d+)(?![A-Za-z_])"
    )
    _V2_REPORTING_PERIOD: ClassVar[re.Pattern[str]] = re.compile(
        r"(?i)(?:\b(?:FQ|Q)\s*[1-4]"
        r"(?:\s*[-_:/]?\s*(?:FY)?\s*\d{2,4})?\b"
        r"|\b(?:FY|CY)\s*[-_:]?\s*\d{2,4}\b"
        r"|\bH[12](?:\s*[-_:/]?\s*\d{2,4})?\b"
        r"|\b\d{4}\s*(?:FY|FQ|Q|CY|H)\s*\d{0,2}\b"
        r"|\b\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?\b)"
    )
    _V2_REQUEST_LOCAL_IDENTIFIER: ClassVar[re.Pattern[str]] = re.compile(
        r"(?i)(?:\b(?:N|C|F|J|T|E|G|D)\d{3,}\b"
        r"|\b(?:claim|fact|task|gap|cell)\s*[:#_-]?\s*\d+\b"
        r"|第\s*\d+\s*(?:项|条|步|阶段|组|个))"
    )
    _V2_PERCENT_SUFFIX: ClassVar[re.Pattern[str]] = re.compile(r"^\s*[%％]")
    _V2_CURRENCY_PREFIX: ClassVar[re.Pattern[str]] = re.compile(
        r"(?i)(?:[$¥￥]\s*|(?:USD|CNY|RMB|EUR|JPY|GBP)\s*)$"
    )
    _V2_CURRENCY_SUFFIX: ClassVar[re.Pattern[str]] = re.compile(
        r"(?i)^\s*(?:USD|CNY|RMB|EUR|JPY|GBP)\b"
    )
    _V2_MEASUREMENT_SUFFIX: ClassVar[re.Pattern[str]] = re.compile(
        r"(?i)^\s*(?:k|m|mm|mn|b|bn|million|billion|trillion|"
        r"days?|months?|years?|bps?|x|倍|天|日|月|年|亿元?|万元?|百万|十亿)"
    )

    @staticmethod
    def _text(value: Any, default: str = "") -> str:
        return str(value if value not in (None, "") else default)

    @staticmethod
    def _decimal_text(value: Any) -> str:
        text = str(value if value is not None else "").strip()
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                "s4_case_numeric_projection_exact_value_invalid"
            ) from exc
        if not parsed.is_finite():
            raise ValueError(
                "s4_case_numeric_projection_exact_value_invalid"
            )
        return text

    @classmethod
    def _normalize_financial_row(
        cls,
        row: Mapping[str, Any],
        *,
        program_cell_id: str,
    ) -> dict[str, Any]:
        selector = row.get("selector")
        selector = selector if isinstance(selector, Mapping) else {}
        numeric_ref = cls._text(
            row.get("numeric_ref") or row.get("financial_row_id")
        )
        entity_ref = cls._text(
            row.get("entity_ref") or selector.get("entity_ref"),
            "unknown",
        )
        business_scope_ref = cls._text(
            row.get("segment_ref") or selector.get("segment_ref"),
            "__company_total__",
        )
        period = cls._text(
            row.get("period") or selector.get("period"),
            "unknown",
        )
        metric_family = cls._text(
            row.get("metric_family") or selector.get("metric_family"),
            "unknown",
        )
        exact_value = cls._decimal_text(
            row.get("value")
            if row.get("value") not in (None, "")
            else row.get("normalized_value")
        )
        currency = cls._text(
            row.get("currency") or selector.get("currency")
        )
        unit = cls._text(
            row.get("unit") or selector.get("unit"),
            "unitless",
        )
        scale_multiplier = cls._decimal_text(
            row.get("scale_multiplier", 1)
        )
        cannot_support = _exact_nonblank_strings(
            row.get("cannot_support")
        )
        lineage = row.get("parser_lineage")
        if isinstance(lineage, Mapping):
            lineage_text = canonical_digest(dict(lineage))
        else:
            lineage_text = cls._text(
                row.get("source_ref")
                or row.get("evidence_ref")
                or row.get("source_coordinate"),
                "legacy_numeric_lineage",
            )
        allowed_cells = row.get("program_cell_ids")
        if isinstance(allowed_cells, (list, tuple)) and (
            program_cell_id not in set(map(str, allowed_cells))
        ):
            raise ValueError(
                "s4_case_numeric_projection_cross_cell_row"
            )
        if not numeric_ref:
            raise ValueError("s4_case_numeric_projection_ref_missing")
        return {
            "numeric_ref": numeric_ref,
            "authority_kind": "financial_row",
            "entity_ref": entity_ref,
            "business_scope_ref": business_scope_ref,
            "period": period,
            "metric_family": metric_family,
            "comparison_operator": cls._text(
                row.get("comparison_operator"), "exact"
            ),
            "exact_value": exact_value,
            "currency": currency,
            "unit": unit,
            "scale_multiplier": scale_multiplier,
            "source_or_formula_lineage": lineage_text,
            "cannot_support": cannot_support,
            "formula": "",
            "input_numeric_refs": (),
            "rounding_rule": "",
        }

    @classmethod
    def _normalize_derived_row(
        cls,
        row: Mapping[str, Any],
        *,
        program_cell_id: str,
        financial_by_ref: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        numeric_ref = cls._text(
            row.get("derived_metric_ref")
            or row.get("derived_metric_id")
        )
        input_refs = _exact_nonblank_strings(
            row.get("input_numeric_refs")
        )
        if not input_refs:
            input_refs = _exact_nonblank_strings(
                [
                    item.get("financial_row_ref")
                    for item in row.get("inputs", ())
                    if isinstance(item, Mapping)
                ]
            )
        input_rows = [
            financial_by_ref[ref]
            for ref in input_refs
            if ref in financial_by_ref
        ]
        entities = {str(item["entity_ref"]) for item in input_rows}
        periods = {str(item["period"]) for item in input_rows}
        scopes = {str(item["business_scope_ref"]) for item in input_rows}
        unit = cls._text(
            row.get("unit") or row.get("result_unit"),
            "unitless",
        )
        exact_value = cls._decimal_text(
            row.get("value")
            if row.get("value") not in (None, "")
            else row.get("result_value")
            if row.get("result_value") not in (None, "")
            else row.get("normalized_value")
        )
        allowed_cells = row.get("program_cell_ids")
        if isinstance(allowed_cells, (list, tuple)) and (
            program_cell_id not in set(map(str, allowed_cells))
        ):
            raise ValueError(
                "s4_case_numeric_projection_cross_cell_row"
            )
        if not numeric_ref or not input_refs:
            raise ValueError(
                "s4_case_numeric_projection_derived_lineage_invalid"
            )
        return {
            "numeric_ref": numeric_ref,
            "authority_kind": "derived_metric",
            "entity_ref": (
                next(iter(entities))
                if len(entities) == 1
                else cls._text(row.get("scope"), "mixed")
            ),
            "business_scope_ref": (
                next(iter(scopes))
                if len(scopes) == 1
                else cls._text(row.get("scope"), "mixed")
            ),
            "period": (
                next(iter(periods))
                if len(periods) == 1
                else cls._text(row.get("scope"), "mixed")
            ),
            "metric_family": cls._text(
                row.get("metric")
                or row.get("metric_family"),
                "unknown",
            ),
            "comparison_operator": "exact",
            "exact_value": exact_value,
            "currency": (
                "USD" if unit.startswith("USD") else ""
            ),
            "unit": unit,
            "scale_multiplier": "1",
            "source_or_formula_lineage": canonical_digest(
                {
                    "formula": cls._text(row.get("formula")),
                    "input_numeric_refs": list(input_refs),
                    "rounding_rule": cls._text(
                        row.get("rounding_rule")
                    ),
                }
            ),
            "cannot_support": _exact_nonblank_strings(
                row.get("cannot_support")
            ),
            "formula": cls._text(row.get("formula")),
            "input_numeric_refs": input_refs,
            "rounding_rule": cls._text(row.get("rounding_rule")),
        }

    @classmethod
    def from_cell_input(
        cls,
        cell_input: Mapping[str, Any],
    ) -> CaseNumericAuthorityPolicy:
        contract_ref = cls._text(
            cell_input.get("_case_numeric_authority_policy_ref"),
            S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
        )
        if contract_ref not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS:
            raise ValueError("s4_case_numeric_authority_policy_unsupported")
        program_cell_id = cls._text(
            cell_input.get("program_cell_id")
        )
        numeric_input = cell_input.get("numeric_input")
        numeric_input = (
            numeric_input if isinstance(numeric_input, Mapping) else {}
        )
        authority = cell_input.get("authority_refs")
        authority = authority if isinstance(authority, Mapping) else {}
        declared_refs = set(
            _exact_nonblank_strings(authority.get("numeric_refs"))
        )
        normalized: list[dict[str, Any]] = []
        for row in numeric_input.get("selected_financial_rows", ()):
            if isinstance(row, Mapping):
                normalized.append(
                    cls._normalize_financial_row(
                        row,
                        program_cell_id=program_cell_id,
                    )
                )
        financial_by_ref = {
            str(row["numeric_ref"]): row for row in normalized
        }
        for row in numeric_input.get("derived_metrics", ()):
            if isinstance(row, Mapping):
                normalized.append(
                    cls._normalize_derived_row(
                        row,
                        program_cell_id=program_cell_id,
                        financial_by_ref=financial_by_ref,
                    )
                )
        refs = [str(row["numeric_ref"]) for row in normalized]
        if len(refs) != len(set(refs)):
            raise ValueError(
                "s4_case_numeric_projection_duplicate_ref"
            )
        if set(refs) != declared_refs:
            raise ValueError(
                "s4_case_numeric_projection_authority_mismatch"
            )
        rows: list[CaseNumericProjectionRow] = []
        for ordinal, row in enumerate(
            sorted(normalized, key=lambda item: str(item["numeric_ref"])),
            1,
        ):
            payload = {
                **row,
                "program_cell_id": program_cell_id,
            }
            rows.append(
                CaseNumericProjectionRow(
                    alias=f"N{ordinal:03d}",
                    **row,
                    projection_digest=canonical_digest(payload),
                )
            )
        reporting_period_labels: tuple[str, ...] = ()
        if contract_ref == S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF:
            labels: set[str] = set()

            def collect_period_labels(value: Any) -> None:
                if isinstance(value, Mapping):
                    for item in value.values():
                        collect_period_labels(item)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        collect_period_labels(item)
                elif isinstance(value, str):
                    labels.update(
                        match.group(0).strip()
                        for match in cls._V2_REPORTING_PERIOD.finditer(
                            value
                        )
                    )

            collect_period_labels(cell_input)
            labels.update(
                row.period.strip()
                for row in rows
                if row.period.strip()
            )
            reporting_period_labels = tuple(
                sorted(labels, key=lambda item: (item.casefold(), item))
            )
        return cls(
            program_cell_id=program_cell_id,
            rows=tuple(rows),
            contract_ref=contract_ref,
            allowed_reporting_period_labels=reporting_period_labels,
        )

    @classmethod
    def from_prompt_contract(
        cls,
        value: Mapping[str, Any],
    ) -> CaseNumericAuthorityPolicy:
        if (
            value.get("contract_ref")
            not in S4_CASE_NUMERIC_AUTHORITY_POLICY_REFS
            or not isinstance(value.get("rows"), list)
        ):
            raise ValueError(
                "s4_case_numeric_prompt_contract_invalid"
            )
        program_cell_id = cls._text(value.get("program_cell_id"))
        rows = tuple(
            CaseNumericProjectionRow(
                alias=cls._text(row.get("numeric_alias")),
                numeric_ref=cls._text(row.get("numeric_ref")),
                authority_kind=cls._text(row.get("authority_kind")),
                entity_ref=cls._text(row.get("entity_ref")),
                business_scope_ref=cls._text(
                    row.get("business_scope_ref")
                ),
                period=cls._text(row.get("period")),
                metric_family=cls._text(row.get("metric_family")),
                comparison_operator=cls._text(
                    row.get("comparison_operator")
                ),
                exact_value=cls._decimal_text(row.get("exact_value")),
                currency=cls._text(row.get("currency")),
                unit=cls._text(row.get("unit")),
                scale_multiplier=cls._decimal_text(
                    row.get("scale_multiplier")
                ),
                source_or_formula_lineage=cls._text(
                    row.get("source_or_formula_lineage")
                ),
                cannot_support=_exact_nonblank_strings(
                    row.get("cannot_support")
                ),
                formula=cls._text(row.get("formula")),
                input_numeric_refs=_exact_nonblank_strings(
                    row.get("input_numeric_refs")
                ),
                rounding_rule=cls._text(row.get("rounding_rule")),
                projection_digest=cls._text(
                    row.get("projection_digest")
                ),
            )
            for row in value["rows"]
            if isinstance(row, Mapping)
        )
        policy = cls(
            program_cell_id=program_cell_id,
            rows=rows,
            contract_ref=str(value["contract_ref"]),
            allowed_reporting_period_labels=(
                _exact_nonblank_strings(
                    value.get("allowed_reporting_period_labels")
                )
                if value.get("contract_ref")
                == S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
                else ()
            ),
        )
        if value.get("projection_digest") != policy.projection_digest:
            raise ValueError(
                "s4_case_numeric_prompt_contract_digest_mismatch"
            )
        return policy

    @property
    def projection_digest(self) -> str:
        payload = {
            "contract_ref": self.contract_ref,
            "program_cell_id": self.program_cell_id,
            "rows": [
                row.canonical_payload() for row in self.rows
            ],
        }
        if self.contract_ref == S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF:
            payload["allowed_reporting_period_labels"] = list(
                self.allowed_reporting_period_labels
            )
        return canonical_digest(payload)

    def prompt_contract(self) -> dict[str, Any]:
        alias_by_ref = {
            row.numeric_ref: row.alias for row in self.rows
        }
        rows: list[dict[str, Any]] = []
        for row in self.rows:
            payload = row.canonical_payload()
            payload["numeric_alias"] = payload.pop("alias")
            payload["input_numeric_aliases"] = [
                alias_by_ref[ref]
                for ref in row.input_numeric_refs
                if ref in alias_by_ref
            ]
            rows.append(payload)
        contract = {
            "contract_ref": self.contract_ref,
            "program_cell_id": self.program_cell_id,
            "rows": rows,
            "provider_selection_field": (
                "fact_layer.support_refs when support_type is Numeric"
            ),
            "provider_selection_values": [
                row.alias for row in self.rows
            ],
            "local_rendering_owner": True,
            "projection_digest": self.projection_digest,
        }
        if self.contract_ref == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF:
            contract["provider_authored_numeric_tokens_allowed"] = False
        else:
            contract.update(
                {
                    "allowed_reporting_period_labels": list(
                        self.allowed_reporting_period_labels
                    ),
                    "provider_authored_exact_reporting_period_labels_allowed": True,
                    "provider_authored_request_local_identifiers_allowed": True,
                    "provider_authored_material_numeric_tokens_allowed": False,
                    "unknown_reporting_period_labels_allowed": False,
                }
            )
        return contract

    def provider_narrative_instruction(self) -> str:
        if self.contract_ref == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF:
            return (
                "Do not write any digit, amount, percentage, period value, "
                "sign, currency symbol, unit conversion, or numeric precision "
                "in provider-authored narrative. Exact numeric clauses are "
                "owned and rendered locally from the bound contract."
            )
        return (
            "Provider-authored narrative may repeat only exact reporting-period "
            "labels and request-local identifiers already present in the bound "
            "contract. Do not author or restate any material numeric value, "
            "amount, percentage, measurement, sign, currency symbol, unit "
            "conversion, or numeric precision. Exact numeric clauses remain "
            "locally owned and rendered."
        )

    @classmethod
    def combined_narrative_classifier(
        cls,
        policies: Sequence[CaseNumericAuthorityPolicy],
    ) -> CaseNumericAuthorityPolicy:
        if not policies:
            raise ValueError("s4_case_numeric_classifier_policy_missing")
        first = policies[0]
        if any(
            policy.contract_ref != first.contract_ref
            for policy in policies
        ):
            raise ValueError("s4_case_numeric_classifier_policy_mixed")
        if first.contract_ref == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF:
            return first
        return cls(
            program_cell_id="__cross_cell_narrative__",
            rows=first.rows,
            contract_ref=first.contract_ref,
            allowed_reporting_period_labels=tuple(
                sorted(
                    {
                        label
                        for policy in policies
                        for label in policy.allowed_reporting_period_labels
                    },
                    key=lambda item: (item.casefold(), item),
                )
            ),
        )

    @classmethod
    def _narrative_values(
        cls,
        value: Any,
        *,
        field_id: str = "",
    ) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        if isinstance(value, Mapping):
            for key, item in value.items():
                found.extend(
                    cls._narrative_values(
                        item,
                        field_id=str(key),
                    )
                )
        elif isinstance(value, (list, tuple)):
            for item in value:
                found.extend(
                    cls._narrative_values(
                        item,
                        field_id=field_id,
                    )
                )
        elif (
            isinstance(value, str)
            and field_id in cls._NARRATIVE_FIELDS
        ):
            found.append((field_id, value))
        return found

    @classmethod
    def _narrative_values_with_paths(
        cls,
        value: Any,
        *,
        field_id: str = "",
        field_path: str = "$",
    ) -> list[tuple[str, str, str]]:
        found: list[tuple[str, str, str]] = []
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                found.extend(
                    cls._narrative_values_with_paths(
                        item,
                        field_id=key_text,
                        field_path=f"{field_path}.{key_text}",
                    )
                )
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                found.extend(
                    cls._narrative_values_with_paths(
                        item,
                        field_id=field_id,
                        field_path=f"{field_path}[{index}]",
                    )
                )
        elif (
            isinstance(value, str)
            and field_id in cls._NARRATIVE_FIELDS
        ):
            found.append((field_id, field_path, value))
        return found

    @staticmethod
    def _span_within(
        span: tuple[int, int],
        containers: Sequence[tuple[int, int]],
    ) -> bool:
        return any(
            start <= span[0] and span[1] <= end
            for start, end in containers
        )

    def _v2_matches_for_text(
        self,
        *,
        field_id: str,
        field_path: str,
        text: str,
    ) -> list[CaseNumericNarrativeMatch]:
        allowed_period_spans: list[tuple[int, int]] = []
        lower_text = text.casefold()
        allowed_period_keys = {
            re.sub(r"[^a-z0-9]", "", period.casefold())
            for period in self.allowed_reporting_period_labels
        }
        for period in self.allowed_reporting_period_labels:
            needle = period.casefold()
            start = 0
            while needle and (index := lower_text.find(needle, start)) >= 0:
                if any(character.isdigit() for character in needle):
                    allowed_period_spans.append(
                        (index, index + len(needle))
                    )
                start = index + max(1, len(needle))
        identifier_spans = [
            match.span()
            for match in self._V2_REQUEST_LOCAL_IDENTIFIER.finditer(text)
        ]
        generic_period_spans: list[tuple[int, int]] = []
        for match in self._V2_REPORTING_PERIOD.finditer(text):
            span = match.span()
            period_key = re.sub(
                r"[^a-z0-9]", "", match.group(0).casefold()
            )
            if period_key in allowed_period_keys:
                allowed_period_spans.append(span)
            else:
                generic_period_spans.append(span)
        classes: dict[str, bool] = {}
        if allowed_period_spans:
            classes["reporting_period_label"] = False
        if identifier_spans:
            classes["request_local_identifier"] = False
        for match in self._V2_NUMERIC_VALUE.finditer(text):
            span = match.span()
            if self._span_within(span, allowed_period_spans):
                continue
            if self._span_within(span, identifier_spans):
                continue
            if self._span_within(span, generic_period_spans):
                semantic_class = "unknown_reporting_period_label"
            else:
                before = text[max(0, span[0] - 12):span[0]]
                after = text[span[1]:span[1] + 18]
                if self._V2_PERCENT_SUFFIX.search(after):
                    semantic_class = "percentage"
                elif (
                    self._V2_CURRENCY_PREFIX.search(before)
                    or self._V2_CURRENCY_SUFFIX.search(after)
                ):
                    semantic_class = "financial_amount"
                elif self._V2_MEASUREMENT_SUFFIX.search(after):
                    semantic_class = "measurement"
                else:
                    semantic_class = "material_numeric_value"
            classes[semantic_class] = True
        if re.search(r"[$¥￥]", text):
            classes["financial_amount"] = True
        if re.search(r"[%％]", text):
            classes["percentage"] = True
        return [
            CaseNumericNarrativeMatch(
                field_id=field_id,
                field_path=field_path,
                semantic_class=semantic_class,
                terminal=terminal,
            )
            for semantic_class, terminal in sorted(classes.items())
        ]

    def provider_narrative_matches(
        self,
        value: Any,
    ) -> tuple[CaseNumericNarrativeMatch, ...]:
        if self.contract_ref == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF:
            return tuple(
                CaseNumericNarrativeMatch(
                    field_id=field_id,
                    field_path=field_path,
                    semantic_class="blanket_numeric_token",
                    terminal=True,
                )
                for field_id, field_path, text
                in self._narrative_values_with_paths(value)
                if self._PROVIDER_NUMERIC_TOKEN.search(text)
            )
        matches: list[CaseNumericNarrativeMatch] = []
        for field_id, field_path, text in self._narrative_values_with_paths(
            value
        ):
            matches.extend(
                self._v2_matches_for_text(
                    field_id=field_id,
                    field_path=field_path,
                    text=text,
                )
            )
        return tuple(matches)

    def first_provider_narrative_violation(
        self,
        value: Any,
    ) -> CaseNumericAuthorityViolation | None:
        matches = [
            match
            for match in self.provider_narrative_matches(value)
            if match.terminal
        ]
        if matches:
            return CaseNumericAuthorityViolation(
                subtype=(
                    "provider_authored_numeric_token"
                    if self.contract_ref
                    == S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
                    else "provider_authored_material_numeric_token"
                ),
                field_id=sorted(
                    match.field_id for match in matches
                )[0],
                failing_item_count=len(
                    {match.field_path for match in matches}
                ),
                contract_ref=self.contract_ref,
                match_paths=tuple(
                    sorted({match.field_path for match in matches})
                ),
                semantic_classes=tuple(
                    sorted({match.semantic_class for match in matches})
                ),
            )
        return None

    def expand_provider_fact_output(
        self,
        output: Mapping[str, Any],
    ) -> tuple[dict[str, Any] | None, CaseNumericAuthorityViolation | None]:
        violation = self.first_provider_narrative_violation(output)
        if violation is not None:
            return None, violation
        facts = output.get("fact_layer")
        if not isinstance(facts, list):
            return None, CaseNumericAuthorityViolation(
                subtype="fact_layer_not_array",
                field_id="fact_layer",
                failing_item_count=1,
            )
        alias_rows = {row.alias: row for row in self.rows}
        expanded = dict(output)
        expanded_facts: list[dict[str, Any]] = []
        for fact in facts:
            if not isinstance(fact, Mapping):
                return None, CaseNumericAuthorityViolation(
                    subtype="fact_shape_invalid",
                    field_id="fact_layer",
                    failing_item_count=1,
                )
            local = dict(fact)
            if local.get("support_type") == "Numeric":
                refs = local.get("support_refs")
                if (
                    not isinstance(refs, list)
                    or not refs
                    or any(ref not in alias_rows for ref in refs)
                    or len(refs) != len(set(refs))
                ):
                    return None, CaseNumericAuthorityViolation(
                        subtype="numeric_alias_unknown_or_duplicate",
                        field_id="fact_layer.support_refs",
                        failing_item_count=1,
                    )
                rows = [alias_rows[str(ref)] for ref in refs]
                interpretation = str(local.get("statement") or "").strip()
                local["support_refs"] = [
                    row.numeric_ref for row in rows
                ]
                local["statement"] = (
                    "；".join(row.rendered_clause() for row in rows)
                    + "；"
                    + interpretation
                )
            expanded_facts.append(local)
        expanded["fact_layer"] = expanded_facts
        return expanded, None

    def first_canonical_fact_violation(
        self,
        facts: Any,
    ) -> CaseNumericAuthorityViolation | None:
        if not isinstance(facts, list):
            return CaseNumericAuthorityViolation(
                subtype="fact_layer_not_array",
                field_id="fact_layer",
                failing_item_count=1,
            )
        by_ref = {row.numeric_ref: row for row in self.rows}
        failure_count = 0
        for fact in facts:
            if (
                not isinstance(fact, Mapping)
                or fact.get("support_type") != "Numeric"
            ):
                continue
            refs = fact.get("support_refs")
            statement = str(fact.get("statement") or "")
            if (
                not isinstance(refs, list)
                or not refs
                or any(ref not in by_ref for ref in refs)
            ):
                failure_count += 1
                continue
            expected = "；".join(
                by_ref[str(ref)].rendered_clause() for ref in refs
            )
            if not statement.startswith(f"{expected}；"):
                failure_count += 1
        if failure_count:
            return CaseNumericAuthorityViolation(
                subtype="canonical_rendering_mismatch",
                field_id="fact_layer.statement",
                failing_item_count=failure_count,
            )
        return None

    def rendered_clauses_for_refs(
        self,
        refs: Sequence[str],
    ) -> tuple[str, ...]:
        by_ref = {row.numeric_ref: row for row in self.rows}
        if any(ref not in by_ref for ref in refs):
            raise ValueError(
                "s4_case_numeric_rendering_unknown_ref"
            )
        return tuple(by_ref[ref].rendered_clause() for ref in refs)


@dataclass(frozen=True)
class StrictTruthKernelViolation:
    """Content-free strict-kernel failure safe for canonical telemetry."""

    subtype: str
    field_id: str
    failing_item_count: int

    def __post_init__(self) -> None:
        if (
            not self.subtype
            or not self.field_id
            or self.failing_item_count <= 0
        ):
            raise ValueError("s4_strict_truth_kernel_violation_invalid")

    def telemetry(self) -> dict[str, Any]:
        return {
            "contract_ref": S4_STRICT_TRUTH_KERNEL_POLICY_REF,
            "acceptance_layer": "L1_hard_integrity",
            "failure_subtype": self.subtype,
            "field_id": self.field_id,
            "failing_item_count": self.failing_item_count,
            "raw_text_persisted": False,
            "private_reasoning_persisted": False,
            "credentials_persisted": False,
            "stack_persisted": False,
        }


class OpenAIStructuredOutputsSubsetCompiler:
    """Compile semantic JSON Schema into the documented server subset."""

    contract_ref = S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF
    allowed_keywords = frozenset(
        {
            "type",
            "properties",
            "required",
            "additionalProperties",
            "items",
            "minItems",
            "maxItems",
            "enum",
        }
    )
    local_only_keywords = frozenset({"uniqueItems"})

    @classmethod
    def compile(
        cls,
        semantic_schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        compiled = cls._compile_node(semantic_schema, path="$")
        cls._validate_node(compiled, path="$")
        return compiled

    @classmethod
    def _compile_node(
        cls,
        schema: Mapping[str, Any],
        *,
        path: str,
    ) -> dict[str, Any]:
        if not isinstance(schema, Mapping):
            raise ValueError(
                f"strict_server_schema_node_invalid:{path}"
            )
        unknown = set(schema).difference(
            cls.allowed_keywords,
            cls.local_only_keywords,
        )
        if unknown:
            keyword = sorted(str(item) for item in unknown)[0]
            raise ValueError(
                "strict_server_schema_keyword_not_allowlisted:"
                f"{path}:{keyword}"
            )
        compiled: dict[str, Any] = {}
        for keyword, value in schema.items():
            if keyword == "uniqueItems":
                if value is not True:
                    raise ValueError(
                        "strict_local_uniqueItems_contract_invalid:"
                        f"{path}"
                    )
                continue
            if keyword == "properties":
                if not isinstance(value, Mapping):
                    raise ValueError(
                        "strict_server_schema_properties_invalid:"
                        f"{path}"
                    )
                compiled[keyword] = {
                    str(field): cls._compile_node(
                        field_schema,
                        path=f"{path}.properties.{field}",
                    )
                    for field, field_schema in value.items()
                }
                continue
            if keyword == "items":
                compiled[keyword] = cls._compile_node(
                    value,
                    path=f"{path}.items",
                )
                continue
            compiled[keyword] = deepcopy(value)
        return compiled

    @classmethod
    def _validate_node(
        cls,
        schema: Mapping[str, Any],
        *,
        path: str,
    ) -> None:
        if set(schema).difference(cls.allowed_keywords):
            raise ValueError(
                f"strict_server_schema_compiler_escape:{path}"
            )
        schema_type = schema.get("type")
        if schema_type == "object":
            properties = schema.get("properties")
            required = schema.get("required")
            if (
                not isinstance(properties, Mapping)
                or not isinstance(required, list)
                or set(required) != set(properties)
                or len(required) != len(set(required))
                or schema.get("additionalProperties") is not False
            ):
                raise ValueError(
                    "strict_server_schema_object_contract_invalid:"
                    f"{path}"
                )
            for field, field_schema in properties.items():
                cls._validate_node(
                    field_schema,
                    path=f"{path}.properties.{field}",
                )
        elif schema_type == "array":
            items = schema.get("items")
            if not isinstance(items, Mapping):
                raise ValueError(
                    "strict_server_schema_array_items_invalid:"
                    f"{path}"
                )
            minimum = schema.get("minItems")
            maximum = schema.get("maxItems")
            if minimum is not None and (
                not isinstance(minimum, int) or minimum < 0
            ):
                raise ValueError(
                    "strict_server_schema_minItems_invalid:"
                    f"{path}"
                )
            if maximum is not None and (
                not isinstance(maximum, int) or maximum < 0
            ):
                raise ValueError(
                    "strict_server_schema_maxItems_invalid:"
                    f"{path}"
                )
            if (
                isinstance(minimum, int)
                and isinstance(maximum, int)
                and minimum > maximum
            ):
                raise ValueError(
                    "strict_server_schema_array_bounds_invalid:"
                    f"{path}"
                )
            cls._validate_node(items, path=f"{path}.items")


@dataclass(frozen=True)
class StrictTruthKernelPolicy:
    """Alias/enum-only Provider surface with deterministic fact rendering."""

    program_cell_id: str
    numeric_policy: CaseNumericAuthorityPolicy
    evidence_aliases: tuple[str, ...]
    contract_ref: str = S4_STRICT_TRUTH_KERNEL_POLICY_REF
    provider_capability_ref: str = (
        S4_STRICT_JSON_SCHEMA_PROVIDER_CAPABILITY_REF
    )
    narrative_shell_ref: str = (
        S4_NON_AUTHORITATIVE_NARRATIVE_SHELL_REF
    )

    _DIRECTIONS: ClassVar[tuple[str, ...]] = (
        "supports",
        "challenges",
        "mixed",
        "unknown",
    )
    _MATERIALITY: ClassVar[tuple[str, ...]] = (
        "high",
        "medium",
        "low",
    )
    _CONFIDENCE: ClassVar[tuple[str, ...]] = (
        "high",
        "medium",
        "low",
    )
    _INTERPRETATION_CODES: ClassVar[tuple[str, ...]] = (
        "directional_support",
        "margin_pressure",
        "cash_conversion",
        "demand_durability",
        "supply_constraint",
        "counterevidence_present",
    )
    _TERMINAL_CLASSES: ClassVar[tuple[str, ...]] = (
        "supported",
        "mixed",
        "insufficient",
    )
    _INTERPRETATION_TEXT: ClassVar[dict[str, str]] = {
        "directional_support": "该权威口径支持方向性判断",
        "margin_pressure": "该权威口径指向利润承压机制",
        "cash_conversion": "该权威口径指向现金转换机制",
        "demand_durability": "该权威口径指向需求持续性机制",
        "supply_constraint": "该权威口径指向供给约束机制",
        "counterevidence_present": "该权威口径需要结合反证共同判断",
    }

    @classmethod
    def from_cell_input(
        cls,
        cell_input: Mapping[str, Any],
    ) -> StrictTruthKernelPolicy:
        numeric_policy = CaseNumericAuthorityPolicy.from_cell_input(
            cell_input
        )
        authority = cell_input.get("authority_refs")
        authority = authority if isinstance(authority, Mapping) else {}
        evidence_refs = tuple(
            sorted(
                set(
                    _exact_nonblank_strings(
                        authority.get("accepted_evidence_refs")
                    )
                )
            )
        )
        return cls(
            program_cell_id=numeric_policy.program_cell_id,
            numeric_policy=numeric_policy,
            evidence_aliases=tuple(
                (
                    f"E{numeric_policy.projection_digest[:10].upper()}"
                    f"{ordinal:03d}"
                )
                for ordinal, _ in enumerate(evidence_refs, 1)
            ),
        )

    @property
    def strict_numeric_aliases(self) -> tuple[str, ...]:
        prefix = self.numeric_policy.projection_digest[:10].upper()
        return tuple(
            f"N{prefix}{ordinal:03d}"
            for ordinal, _ in enumerate(self.numeric_policy.rows, 1)
        )

    @property
    def schema_name(self) -> str:
        suffix = re.sub(
            r"[^a-z0-9_]",
            "_",
            self.program_cell_id.lower(),
        ).strip("_")
        return f"fin01_s4_truth_kernel_{suffix}"

    def semantic_json_schema(self) -> dict[str, Any]:
        numeric_aliases = list(self.strict_numeric_aliases)
        evidence_items: dict[str, Any] = {
            "type": "string",
            "enum": list(self.evidence_aliases),
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "program_cell_id",
                "fact_judgments",
                "terminal_class",
            ],
            "properties": {
                "program_cell_id": {
                    "type": "string",
                    "enum": [self.program_cell_id],
                },
                "fact_judgments": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": min(3, len(numeric_aliases)),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "numeric_alias",
                            "direction",
                            "materiality",
                            "confidence",
                            "interpretation_code",
                            "counterevidence_aliases",
                        ],
                        "properties": {
                            "numeric_alias": {
                                "type": "string",
                                "enum": numeric_aliases,
                            },
                            "direction": {
                                "type": "string",
                                "enum": list(self._DIRECTIONS),
                            },
                            "materiality": {
                                "type": "string",
                                "enum": list(self._MATERIALITY),
                            },
                            "confidence": {
                                "type": "string",
                                "enum": list(self._CONFIDENCE),
                            },
                            "interpretation_code": {
                                "type": "string",
                                "enum": list(
                                    self._INTERPRETATION_CODES
                                ),
                            },
                            "counterevidence_aliases": {
                                "type": "array",
                                "uniqueItems": True,
                                "items": evidence_items,
                            },
                        },
                    },
                },
                "terminal_class": {
                    "type": "string",
                    "enum": list(self._TERMINAL_CLASSES),
                },
            },
        }

    def server_json_schema(self) -> dict[str, Any]:
        return OpenAIStructuredOutputsSubsetCompiler.compile(
            self.semantic_json_schema()
        )

    def json_schema(self) -> dict[str, Any]:
        """Backward-compatible name for the exact provider-wire schema."""

        return self.server_json_schema()

    def prompt_contract(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "provider_capability_ref": self.provider_capability_ref,
            "server_schema_compiler_ref": (
                S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF
            ),
            "local_validator_ref": (
                S4_STRICT_TRUTH_KERNEL_LOCAL_VALIDATOR_REF
            ),
            "narrative_shell_ref": self.narrative_shell_ref,
            "program_cell_id": self.program_cell_id,
            "numeric_aliases": [
                *self.strict_numeric_aliases
            ],
            "evidence_aliases": list(self.evidence_aliases),
            "provider_wire_forbidden": [
                "arbitrary_free_text",
                "material_numeric_value",
                "currency",
                "percentage",
                "period",
                "entity_or_ticker",
                "canonical_id",
                "lineage",
            ],
            "strict_json_schema": self.server_json_schema(),
            "local_semantic_rules": {
                "numeric_alias_uniqueness_required": True,
                "counterevidence_alias_uniqueness_required": True,
                "cross_case_alias_rejected": True,
                "closed_enum_membership_required": True,
            },
            "local_rendering_owner": True,
            "independent_L1_recomputation_required": True,
            "projection_digest": self.numeric_policy.projection_digest,
        }

    def render_provider_output(
        self,
        value: Any,
    ) -> tuple[dict[str, Any] | None, StrictTruthKernelViolation | None]:
        if not isinstance(value, Mapping) or set(value) != {
            "program_cell_id",
            "fact_judgments",
            "terminal_class",
        }:
            return None, StrictTruthKernelViolation(
                "top_level_shape_invalid",
                "top_level",
                1,
            )
        if value.get("program_cell_id") != self.program_cell_id:
            return None, StrictTruthKernelViolation(
                "program_cell_mismatch",
                "program_cell_id",
                1,
            )
        judgments = value.get("fact_judgments")
        if (
            not isinstance(judgments, list)
            or not 1 <= len(judgments) <= min(
                3, len(self.numeric_policy.rows)
            )
        ):
            return None, StrictTruthKernelViolation(
                "fact_judgment_cardinality_invalid",
                "fact_judgments",
                1,
            )
        if value.get("terminal_class") not in self._TERMINAL_CLASSES:
            return None, StrictTruthKernelViolation(
                "enum_value_invalid",
                "terminal_class",
                1,
            )

        rows_by_alias = dict(
            zip(
                self.strict_numeric_aliases,
                self.numeric_policy.rows,
                strict=True,
            )
        )
        observed_aliases: list[str] = []
        rendered_facts: list[dict[str, Any]] = []
        explanations: list[str] = []
        expected_item_keys = {
            "numeric_alias",
            "direction",
            "materiality",
            "confidence",
            "interpretation_code",
            "counterevidence_aliases",
        }
        for ordinal, judgment in enumerate(judgments, 1):
            if not isinstance(judgment, Mapping) or set(
                judgment
            ) != expected_item_keys:
                return None, StrictTruthKernelViolation(
                    "fact_judgment_shape_invalid",
                    "fact_judgments",
                    1,
                )
            alias = str(judgment.get("numeric_alias") or "")
            if alias not in rows_by_alias:
                return None, StrictTruthKernelViolation(
                    "numeric_alias_unknown_or_cross_case",
                    "fact_judgments.numeric_alias",
                    1,
                )
            observed_aliases.append(alias)
            if len(observed_aliases) != len(set(observed_aliases)):
                return None, StrictTruthKernelViolation(
                    "numeric_alias_duplicate",
                    "fact_judgments.numeric_alias",
                    1,
                )
            if (
                judgment.get("direction") not in self._DIRECTIONS
                or judgment.get("materiality") not in self._MATERIALITY
                or judgment.get("confidence") not in self._CONFIDENCE
                or judgment.get("interpretation_code")
                not in self._INTERPRETATION_CODES
            ):
                return None, StrictTruthKernelViolation(
                    "enum_value_invalid",
                    "fact_judgments",
                    1,
                )
            counterevidence = judgment.get(
                "counterevidence_aliases"
            )
            if not isinstance(counterevidence, list) or any(
                alias_value not in self.evidence_aliases
                for alias_value in counterevidence
            ):
                return None, StrictTruthKernelViolation(
                    "counterevidence_alias_unknown_or_cross_case",
                    "fact_judgments.counterevidence_aliases",
                    1,
                )
            if len(counterevidence) != len(set(counterevidence)):
                return None, StrictTruthKernelViolation(
                    "counterevidence_alias_duplicate",
                    "fact_judgments.counterevidence_aliases",
                    1,
                )
            row = rows_by_alias[alias]
            interpretation_code = str(
                judgment["interpretation_code"]
            )
            interpretation = self._INTERPRETATION_TEXT[
                interpretation_code
            ]
            rendered_facts.append(
                {
                    "fact_id": (
                        f"local_truth_kernel_fact_{ordinal:03d}"
                    ),
                    "statement": (
                        f"{row.rendered_clause()}；{interpretation}"
                    ),
                    "support_type": "Numeric",
                    "support_refs": [row.numeric_ref],
                    "boundary": (
                        "仅限本地绑定的实体、期间、口径、单位与公式"
                    ),
                }
            )
            if interpretation not in explanations:
                explanations.append(interpretation)
        terminal = str(value["terminal_class"])
        remaining_gap = {
            "supported": "仍需持续核对新增反证与口径变化",
            "mixed": "方向混合，需补充独立权威证据",
            "insufficient": "当前权威集合不足以形成更强结论",
        }[terminal]
        return (
            {
                "program_cell_id": self.program_cell_id,
                "fact_layer": rendered_facts,
                "explanation_layer": explanations,
                "remaining_gaps": [remaining_gap],
                "terminal_class": terminal,
            },
            None,
        )


@dataclass(frozen=True)
class CaseDeliveryIdentityPolicy:
    """Case-local owner for every entity-bearing delivery label."""

    company: str
    case_ticker: str
    case_identity_namespace: str
    case_profile_ref: str
    delivery_language: str = "zh-CN"
    contract_ref: str = S4_CASE_DELIVERY_IDENTITY_POLICY_REF
    case_identity_registry_ref: str | None = None
    registered_case_tickers: tuple[str, ...] = ()

    _CASE_IDENTITY_REGISTRY: ClassVar[dict[str, str]] = {
        "NVDA": "fin01.case_identity.NVDA:v1",
        "DELL": "fin01.case_identity.DELL:v1",
        "MU": "fin01.case_identity.MU:v1",
    }

    @classmethod
    def registered_identity_tickers(cls) -> tuple[str, ...]:
        """Return the versioned release-case registry in stable order."""

        return tuple(cls._CASE_IDENTITY_REGISTRY)

    @property
    def current_case_aware(self) -> bool:
        return (
            self.contract_ref
            == S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        )

    @property
    def registered_nonlocal_case_tickers(self) -> tuple[str, ...]:
        return tuple(
            ticker
            for ticker in self.registered_case_tickers
            if ticker != self.case_ticker
        )

    def provider_identity_boundary_instruction(self) -> str:
        if not self.current_case_aware:
            return (
                " Do not write any registered case ticker, company name, or "
                "delivery title in provider-authored narrative. Delivery "
                "identity remains locally owned."
            )
        nonlocal_tickers = ", ".join(
            self.registered_nonlocal_case_tickers
        )
        return (
            f" The current case ticker {self.case_ticker} may appear only as "
            "non-authoritative analytical context. Never write any registered "
            f"nonlocal case ticker ({nonlocal_tickers}) or any delivery title; "
            "title, workpaper, review, manifest, and runtime identity remain "
            "locally owned."
        )

    @staticmethod
    def _token_occurrences(text: str, ticker: str) -> int:
        return len(
            re.findall(
                rf"(?<![A-Za-z0-9]){re.escape(ticker)}"
                rf"(?![A-Za-z0-9])",
                text,
            )
        )

    @classmethod
    def compile(
        cls,
        *,
        company: str,
        s4_case_runtime: Mapping[str, Any] | None,
        contract_ref: str = S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    ) -> CaseDeliveryIdentityPolicy:
        ticker = str(company or "").strip()
        namespace = f"legacy:{ticker}"
        profile_ref = "legacy_s3_input_company"
        if isinstance(s4_case_runtime, Mapping):
            binding = s4_case_runtime.get("binding")
            if isinstance(binding, Mapping):
                bound_ticker = str(
                    binding.get("case_ticker") or ""
                ).strip()
                if bound_ticker != ticker:
                    raise ValueError(
                        "s4_case_delivery_identity_binding_mismatch"
                    )
                namespace = str(
                    binding.get("case_identity_namespace") or ""
                ).strip()
                profile_ref = str(
                    binding.get("case_profile_ref") or ""
                ).strip()
        if (
            not ticker
            or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", ticker)
            or not namespace
            or not profile_ref
            or contract_ref not in S4_CASE_DELIVERY_IDENTITY_POLICY_REFS
        ):
            raise ValueError(
                "s4_case_delivery_identity_input_invalid"
            )
        registry_tickers: tuple[str, ...] = ()
        registry_ref: str | None = None
        if (
            contract_ref
            == S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        ):
            registry_tickers = cls.registered_identity_tickers()
            registry_ref = S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF
            if ticker not in registry_tickers:
                raise ValueError(
                    "s4_case_delivery_identity_registry_scope_invalid"
                )
        return cls(
            company=ticker,
            case_ticker=ticker,
            case_identity_namespace=namespace,
            case_profile_ref=profile_ref,
            contract_ref=contract_ref,
            case_identity_registry_ref=registry_ref,
            registered_case_tickers=registry_tickers,
        )

    @property
    def title_zh_cn(self) -> str:
        return f"{self.case_ticker} 三单元内部研究备忘录"

    @property
    def projection_digest(self) -> str:
        payload = {
            "contract_ref": self.contract_ref,
            "company": self.company,
            "case_ticker": self.case_ticker,
            "case_identity_namespace": (
                self.case_identity_namespace
            ),
            "case_profile_ref": self.case_profile_ref,
            "delivery_language": self.delivery_language,
            "title_zh_cn": self.title_zh_cn,
        }
        if self.current_case_aware:
            payload.update(
                {
                    "case_identity_registry_ref": (
                        self.case_identity_registry_ref
                    ),
                    "registered_case_tickers": list(
                        self.registered_case_tickers
                    ),
                }
            )
        return canonical_digest(payload)

    def projection(self) -> dict[str, Any]:
        projection = {
            "contract_ref": self.contract_ref,
            "company": self.company,
            "case_ticker": self.case_ticker,
            "case_identity_namespace": self.case_identity_namespace,
            "case_profile_ref": self.case_profile_ref,
            "delivery_language": self.delivery_language,
            "title_zh_cn": self.title_zh_cn,
            "workpaper_entity_label": self.case_ticker,
            "review_surface_entity_label": self.case_ticker,
            "manifest_case_ticker": self.case_ticker,
            "projection_digest": self.projection_digest,
        }
        if self.current_case_aware:
            projection.update(
                {
                    "case_identity_registry_ref": (
                        self.case_identity_registry_ref
                    ),
                    "registered_case_tickers": list(
                        self.registered_case_tickers
                    ),
                }
            )
        return projection

    def first_provider_narrative_identity_violation(
        self,
        value: Any,
    ) -> dict[str, Any] | None:
        tickers = (
            self.registered_nonlocal_case_tickers
            if self.current_case_aware
            else self.registered_case_tickers
            or self.registered_identity_tickers()
        )
        for field_id, text in CaseNumericAuthorityPolicy._narrative_values(
            value
        ):
            count = sum(
                self._token_occurrences(text, ticker)
                for ticker in tickers
            )
            if count:
                return {
                    "contract_ref": self.contract_ref,
                    "acceptance_layer": "L1_hard_integrity",
                    "failure_subtype": (
                        "provider_narrative_nonlocal_registered_case_"
                        "identity_token"
                        if self.current_case_aware
                        else "provider_authored_case_entity_token"
                    ),
                    "field_id": field_id or "provider_narrative",
                    "failing_item_count": count,
                    "current_case_identity_digest": canonical_digest(
                        {
                            "case_ticker": self.case_ticker,
                            "case_identity_namespace": (
                                self.case_identity_namespace
                            ),
                            "case_profile_ref": self.case_profile_ref,
                        }
                    ),
                    "registered_nonlocal_match_count": count,
                    "raw_text_persisted": False,
                    "private_reasoning_persisted": False,
                }
        return None

    def provider_narrative_has_entity_token(
        self,
        value: Any,
    ) -> bool:
        """Backward-compatible predicate; v2 rejects nonlocal identities only."""

        return (
            self.first_provider_narrative_identity_violation(value)
            is not None
        )

    @classmethod
    def from_projection(
        cls,
        value: Mapping[str, Any],
    ) -> CaseDeliveryIdentityPolicy:
        contract_ref = str(value.get("contract_ref") or "")
        if contract_ref not in S4_CASE_DELIVERY_IDENTITY_POLICY_REFS:
            raise ValueError(
                "s4_case_delivery_identity_projection_invalid"
            )
        policy = cls(
            company=str(value.get("company") or ""),
            case_ticker=str(value.get("case_ticker") or ""),
            case_identity_namespace=str(
                value.get("case_identity_namespace") or ""
            ),
            case_profile_ref=str(
                value.get("case_profile_ref") or ""
            ),
            delivery_language=str(
                value.get("delivery_language") or ""
            ),
            contract_ref=contract_ref,
            case_identity_registry_ref=(
                str(value.get("case_identity_registry_ref") or "")
                or None
            ),
            registered_case_tickers=tuple(
                str(ticker)
                for ticker in (
                    value.get("registered_case_tickers") or ()
                )
            ),
        )
        if (
            value.get("title_zh_cn") != policy.title_zh_cn
            or value.get("workpaper_entity_label")
            != policy.case_ticker
            or value.get("review_surface_entity_label")
            != policy.case_ticker
            or value.get("manifest_case_ticker")
            != policy.case_ticker
            or value.get("projection_digest")
            != policy.projection_digest
            or (
                policy.current_case_aware
                and (
                    policy.case_identity_registry_ref
                    != S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF
                    or policy.registered_case_tickers
                    != policy.registered_identity_tickers()
                    or policy.case_ticker
                    not in policy.registered_case_tickers
                )
            )
            or (
                not policy.current_case_aware
                and (
                    policy.case_identity_registry_ref is not None
                    or policy.registered_case_tickers
                )
            )
        ):
            raise ValueError(
                "s4_case_delivery_identity_projection_mismatch"
            )
        return policy


@dataclass(frozen=True)
class WhatWouldChangeAuthorityPolicy:
    """Closed current-Cell authority membership for WWC task references."""

    evidence_refs: tuple[str, ...]
    numeric_refs: tuple[str, ...]
    candidate_refs: tuple[str, ...]
    graph_context_refs: tuple[str, ...]
    contract_ref: str = S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF

    @classmethod
    def from_cell_input(
        cls, cell_input: Mapping[str, Any]
    ) -> WhatWouldChangeAuthorityPolicy:
        surface = CellAuthoritySurface.from_cell_input(cell_input)
        return cls(
            evidence_refs=surface.evidence_refs,
            numeric_refs=surface.numeric_refs,
            candidate_refs=surface.candidate_refs,
            graph_context_refs=surface.graph_context_refs,
        )

    @property
    def allowed_refs(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(self.evidence_refs)
                | set(self.numeric_refs)
                | set(self.candidate_refs)
                | set(self.graph_context_refs)
            )
        )

    def prompt_contract(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "field_id": "what_would_change.authority_refs",
            "allowed_refs_by_authority_class": {
                "Evidence": list(self.evidence_refs),
                "Numeric": list(self.numeric_refs),
                "Candidate": list(self.candidate_refs),
                "Graph": list(self.graph_context_refs),
            },
            "selection_rule": (
                "Each task must select a non-empty exact subset of the union "
                "of the four current-Cell authority-class lists."
            ),
            "cross_class_selection_allowed": True,
            "cross_cell_selection_allowed": False,
            (
                "normalization_trim_casefold_fuzzy_match_remap_drop_or_"
                "relink_allowed"
            ): False,
        }

    def first_violation(
        self, tasks: Any
    ) -> AuthorityViolation | None:
        # Task collection shape/cardinality belongs to the existing WWC
        # validator. This policy owns only authority_refs membership.
        if not isinstance(tasks, list):
            return None
        invalid_array_count = 0
        outside_count = 0
        allowed = set(self.allowed_refs)
        for task in tasks:
            if not isinstance(task, Mapping):
                continue
            refs = task.get("authority_refs")
            if not isinstance(refs, list) or not refs:
                invalid_array_count += 1
                continue
            valid_strings = [
                ref for ref in refs if isinstance(ref, str) and ref.strip()
            ]
            invalid_array_count += len(refs) - len(valid_strings)
            outside_count += sum(ref not in allowed for ref in valid_strings)
        if invalid_array_count:
            return AuthorityViolation(
                "authority_refs_not_nonempty_string_array",
                invalid_array_count,
            )
        if outside_count:
            return AuthorityViolation(
                "authority_ref_outside_current_cell_closed_surface",
                outside_count,
            )
        return None


@dataclass(frozen=True)
class ClaimFactAlias:
    alias: str
    fact_id: str
    statement: str
    support_type: str
    boundary: str
    locally_assembled_scope_summary: tuple[tuple[str, str], ...]

    def provider_payload(self) -> dict[str, Any]:
        return {
            "fact_alias": self.alias,
            "fact_statement": self.statement,
            "support_type": self.support_type,
            "boundary": self.boundary,
            "locally_assembled_scope_summary": dict(
                self.locally_assembled_scope_summary
            ),
        }


@dataclass(frozen=True)
class ClaimFactLinkPolicy:
    """Closed Provider aliases with exact local canonical Fact expansion."""

    program_cell_id: str
    alias_rows: tuple[ClaimFactAlias, ...]
    forbidden_raw_refs: tuple[str, ...]
    contract_ref: str = S3_CLAIM_FACT_LINK_POLICY_REF

    _SCOPE_FIELDS = (
        "entity_ref",
        "business_scope_kind",
        "business_scope_ref",
        "period",
        "attribution_level",
    )

    @classmethod
    def from_validated_facts(
        cls,
        *,
        program_cell_id: str,
        facts: Any,
        numeric_scopes: Mapping[str, Mapping[str, Any]],
        additional_forbidden_refs: Sequence[str] = (),
    ) -> ClaimFactLinkPolicy:
        if not program_cell_id or not isinstance(facts, list):
            raise ValueError("claim_fact_link_policy_validated_facts_invalid")
        fact_rows: list[Mapping[str, Any]] = []
        fact_ids: set[str] = set()
        raw_refs = {
            value
            for value in additional_forbidden_refs
            if isinstance(value, str) and value
        }
        for fact in facts:
            if not isinstance(fact, Mapping):
                raise ValueError("claim_fact_link_policy_validated_facts_invalid")
            fact_id = fact.get("fact_id")
            statement = fact.get("statement")
            support_type = fact.get("support_type")
            boundary = fact.get("boundary")
            support_refs = fact.get("support_refs")
            if (
                not isinstance(fact_id, str)
                or not fact_id
                or fact_id in fact_ids
                or not isinstance(statement, str)
                or not statement.strip()
                or support_type not in {"Evidence", "Numeric"}
                or not isinstance(boundary, str)
                or not boundary.strip()
                or not isinstance(support_refs, list)
                or any(
                    not isinstance(ref, str) or not ref
                    for ref in support_refs
                )
            ):
                raise ValueError(
                    "claim_fact_link_policy_validated_facts_invalid"
                )
            fact_ids.add(fact_id)
            raw_refs.add(fact_id)
            raw_refs.update(support_refs)
            fact_rows.append(fact)

        aliases: list[ClaimFactAlias] = []
        for ordinal, fact in enumerate(
            sorted(fact_rows, key=lambda row: str(row["fact_id"])),
            1,
        ):
            supported_scopes = [
                numeric_scopes[ref]
                for ref in fact["support_refs"]
                if ref in numeric_scopes
            ]
            scope_summary: list[tuple[str, str]] = []
            for field_id in cls._SCOPE_FIELDS:
                values = {
                    str(row.get(field_id) or "unknown")
                    for row in supported_scopes
                }
                scope_summary.append(
                    (
                        field_id.removesuffix("_ref"),
                        (
                            next(iter(values))
                            if len(values) == 1
                            else "mixed"
                            if values
                            else "unknown"
                        ),
                    )
                )
            aliases.append(
                ClaimFactAlias(
                    alias=f"F{ordinal:03d}",
                    fact_id=str(fact["fact_id"]),
                    statement=str(fact["statement"]),
                    support_type=str(fact["support_type"]),
                    boundary=str(fact["boundary"]),
                    locally_assembled_scope_summary=tuple(scope_summary),
                )
            )
        return cls(
            program_cell_id=program_cell_id,
            alias_rows=tuple(aliases),
            forbidden_raw_refs=tuple(sorted(raw_refs)),
        )

    @property
    def alias_to_fact_id(self) -> dict[str, str]:
        return {row.alias: row.fact_id for row in self.alias_rows}

    def prompt_contract(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "field_id": "judgment_layer.support_fact_aliases",
            "allowed_facts": [
                row.provider_payload() for row in self.alias_rows
            ],
            "selection_rule": (
                "Select only exact fact_alias values from allowed_facts. "
                "Use [] only when the epistemic status permits no support."
            ),
            "provider_response_field": "support_fact_aliases",
            "local_canonical_output_field": "support_fact_ids",
            "local_expansion": "exact_request_local_alias_membership_only",
            "provider_hidden_authority_classes": [
                "Evidence_ref",
                "Numeric_ref",
                "Candidate_ref",
                "Graph_ref",
                "canonical_object_ref",
                "routing_ref",
            ],
            "normalization_trim_prefix_guess_fuzzy_match_or_rewrite_allowed": (
                False
            ),
        }

    def provider_prior_segment(
        self, segment: Mapping[str, Any]
    ) -> dict[str, Any]:
        projected = {
            key: value
            for key, value in segment.items()
            if key != "fact_layer"
        }
        projected["fact_layer"] = [
            row.provider_payload() for row in self.alias_rows
        ]
        return projected

    @classmethod
    def redact_claim_selection_model_view(cls, value: Any) -> Any:
        """Remove object/source identities from the Claim-link semantic view."""

        if isinstance(value, Mapping):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if key_text == "authority_refs":
                    continue
                if (
                    key_text != "program_cell_id"
                    and (
                        key_text.endswith("_id")
                        or key_text.endswith("_ids")
                        or key_text.endswith("_ref")
                        or key_text.endswith("_refs")
                    )
                ):
                    continue
                redacted[key_text] = cls.redact_claim_selection_model_view(
                    item
                )
            return redacted
        if isinstance(value, (list, tuple)):
            return [
                cls.redact_claim_selection_model_view(item)
                for item in value
            ]
        return value

    def expand_claim_output(
        self, output: Mapping[str, Any]
    ) -> tuple[dict[str, Any] | None, AuthorityViolation | None]:
        if output.get("program_cell_id") != self.program_cell_id:
            return None, AuthorityViolation("support_alias_wrong_cell", 1)
        claims = output.get("judgment_layer")
        if not isinstance(claims, list):
            return None, AuthorityViolation("support_alias_not_array", 1)

        aliases = self.alias_to_fact_id
        forbidden = set(self.forbidden_raw_refs)
        expanded_claims: list[dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                return None, AuthorityViolation(
                    "support_alias_item_invalid", 1
                )
            if "support_fact_ids" in claim:
                return None, AuthorityViolation(
                    "raw_fact_or_source_ref_used_in_alias_field", 1
                )
            support_aliases = claim.get("support_fact_aliases")
            if not isinstance(support_aliases, list):
                return None, AuthorityViolation(
                    "support_alias_not_array", 1
                )
            invalid_count = sum(
                not isinstance(alias, str) or not alias.strip()
                for alias in support_aliases
            )
            if invalid_count:
                return None, AuthorityViolation(
                    "support_alias_item_invalid", invalid_count
                )
            raw_ref_count = sum(
                str(alias) in forbidden for alias in support_aliases
            )
            if raw_ref_count:
                return None, AuthorityViolation(
                    "raw_fact_or_source_ref_used_in_alias_field",
                    raw_ref_count,
                )
            unknown_count = sum(
                str(alias) not in aliases for alias in support_aliases
            )
            if unknown_count:
                return None, AuthorityViolation(
                    "support_alias_unknown", unknown_count
                )
            duplicate_count = len(support_aliases) - len(
                set(map(str, support_aliases))
            )
            if duplicate_count:
                return None, AuthorityViolation(
                    "support_alias_duplicate", duplicate_count
                )
            if (
                claim.get("epistemic_status")
                in {"fact_supported", "bounded_inference"}
                and not support_aliases
            ):
                return None, AuthorityViolation(
                    "support_alias_empty_when_required", 1
                )
            expanded = dict(claim)
            expanded.pop("support_fact_aliases")
            expanded["support_fact_ids"] = [
                aliases[str(alias)] for alias in support_aliases
            ]
            if len(expanded["support_fact_ids"]) != len(support_aliases):
                return None, AuthorityViolation(
                    "local_expansion_mismatch", 1
                )
            expanded_claims.append(expanded)

        expanded_output = dict(output)
        expanded_output["judgment_layer"] = expanded_claims
        return expanded_output, None


@dataclass(frozen=True)
class TaskClaimAlias:
    alias: str
    claim_id: str
    statement: str
    epistemic_status: str
    locally_assembled_scope_summary: tuple[tuple[str, str], ...]

    def provider_payload(self) -> dict[str, Any]:
        return {
            "claim_alias": self.alias,
            "statement": self.statement,
            "epistemic_status": self.epistemic_status,
            "locally_assembled_scope_summary": dict(
                self.locally_assembled_scope_summary
            ),
        }


@dataclass(frozen=True)
class TaskClaimLinkPolicy:
    """Closed Claim aliases with exact local WWC task-link expansion."""

    program_cell_id: str
    alias_rows: tuple[TaskClaimAlias, ...]
    contract_ref: str = S3_TASK_CLAIM_LINK_POLICY_REF

    _SCOPE_FIELDS = (
        ("entity", "entity_ref"),
        ("business_scope_kind", "business_scope_kind"),
        ("business_scope", "business_scope_ref"),
        ("period", "period"),
        ("metric_or_mechanism", "metric_or_mechanism"),
        ("attribution_level", "attribution_level"),
    )
    _EPISTEMIC_STATUSES = frozenset(
        {
            "fact_supported",
            "bounded_inference",
            "hypothesis",
            "cannot_infer",
        }
    )

    @classmethod
    def from_validated_claims(
        cls,
        *,
        program_cell_id: str,
        claims: Any,
    ) -> TaskClaimLinkPolicy:
        if not program_cell_id or not isinstance(claims, list):
            raise ValueError("task_claim_link_policy_validated_claims_invalid")
        claim_rows: list[Mapping[str, Any]] = []
        claim_ids: set[str] = set()
        for claim in claims:
            if not isinstance(claim, Mapping):
                raise ValueError(
                    "task_claim_link_policy_validated_claims_invalid"
                )
            claim_id = claim.get("claim_id")
            statement = claim.get("statement")
            epistemic_status = claim.get("epistemic_status")
            scope = claim.get("scope")
            if (
                not isinstance(claim_id, str)
                or not claim_id
                or claim_id in claim_ids
                or not isinstance(statement, str)
                or not statement.strip()
                or epistemic_status not in cls._EPISTEMIC_STATUSES
                or not isinstance(scope, Mapping)
            ):
                raise ValueError(
                    "task_claim_link_policy_validated_claims_invalid"
                )
            claim_ids.add(claim_id)
            claim_rows.append(claim)

        aliases: list[TaskClaimAlias] = []
        for ordinal, claim in enumerate(
            sorted(claim_rows, key=lambda row: str(row["claim_id"])),
            1,
        ):
            scope = claim["scope"]
            aliases.append(
                TaskClaimAlias(
                    alias=f"Q{ordinal:03d}",
                    claim_id=str(claim["claim_id"]),
                    statement=str(claim["statement"]),
                    epistemic_status=str(claim["epistemic_status"]),
                    locally_assembled_scope_summary=tuple(
                        (
                            provider_field,
                            str(scope.get(canonical_field) or "unknown"),
                        )
                        for provider_field, canonical_field in cls._SCOPE_FIELDS
                    ),
                )
            )
        return cls(
            program_cell_id=program_cell_id,
            alias_rows=tuple(aliases),
        )

    @property
    def alias_to_claim_id(self) -> dict[str, str]:
        return {row.alias: row.claim_id for row in self.alias_rows}

    def prompt_contract(self) -> dict[str, Any]:
        return {
            "contract_ref": self.contract_ref,
            "field_id": "what_would_change.claim_alias",
            "allowed_claims": [
                row.provider_payload() for row in self.alias_rows
            ],
            "selection_rule": (
                "For each task, copy exactly one claim_alias from "
                "allowed_claims. Never emit a raw claim_id."
            ),
            "provider_response_field": "claim_alias",
            "local_canonical_output_field": "claim_id",
            "local_expansion": "exact_request_local_alias_membership_only",
            "provider_hidden_identity_classes": [
                "raw_local_claim_id",
                "CellScopedResearchRef",
                "canonical_object_ref",
                "cross_Cell_claim_ref",
            ],
            "normalization_trim_casefold_prefix_guess_fuzzy_match_nearest_"
            "claim_relink_task_drop_or_rewrite_allowed": False,
        }

    def provider_prior_claim_segment(
        self,
        segment: Mapping[str, Any],
    ) -> dict[str, Any]:
        projected = {
            key: value
            for key, value in segment.items()
            if key != "judgment_layer"
        }
        projected["judgment_layer"] = [
            row.provider_payload() for row in self.alias_rows
        ]
        return projected

    def expand_task_output(
        self,
        output: Mapping[str, Any],
    ) -> tuple[dict[str, Any] | None, AuthorityViolation | None]:
        tasks = output.get("what_would_change")
        if not isinstance(tasks, list):
            return dict(output), None

        aliases = self.alias_to_claim_id
        invalid_selection_count = 0
        expanded_tasks: list[Any] = []
        for task in tasks:
            if not isinstance(task, Mapping):
                expanded_tasks.append(task)
                continue
            alias = task.get("claim_alias")
            if (
                "claim_id" in task
                or not isinstance(alias, str)
                or not alias
                or alias not in aliases
            ):
                invalid_selection_count += 1
                expanded_tasks.append(dict(task))
                continue
            expanded = dict(task)
            expanded.pop("claim_alias")
            expanded["claim_id"] = aliases[alias]
            expanded_tasks.append(expanded)

        if invalid_selection_count:
            return None, AuthorityViolation(
                "task_claim_alias_unknown",
                invalid_selection_count,
            )
        expanded_output = dict(output)
        expanded_output["what_would_change"] = expanded_tasks
        return expanded_output, None


@dataclass(frozen=True)
class EpistemicStatePolicy:
    """One source of truth for Claim status prompt and local validation."""

    contract_ref: str = "closed_claim_card_epistemic_status_state:v1"

    def prompt_contract(
        self,
        *,
        support_field_id: str = "support_fact_ids",
    ) -> dict[str, Any]:
        if support_field_id not in {
            "support_fact_ids",
            "support_fact_aliases",
        }:
            raise ValueError("epistemic_state_support_field_invalid")
        return {
            "field_id": (
                "judgment_layer.epistemic_status_"
                f"{support_field_id}_qualification_cannot_support"
            ),
            "status_rules": {
                "fact_supported": {
                    support_field_id: "one_or_more_exact_validated_fact_refs",
                    "qualification": "string_may_be_empty",
                    "cannot_support": "zero_or_more_nonblank_boundaries",
                },
                "bounded_inference": {
                    support_field_id: "one_or_more_exact_validated_fact_refs",
                    "qualification": "string_may_be_empty",
                    "cannot_support": "zero_or_more_nonblank_boundaries",
                },
                "hypothesis": {
                    support_field_id: "zero_or_more_exact_validated_fact_refs",
                    "qualification": "nonblank_string_required",
                    "cannot_support": "zero_or_more_nonblank_boundaries",
                },
                "cannot_infer": {
                    support_field_id: "exactly_empty_array",
                    "qualification": "string_may_be_empty",
                    "cannot_support": "one_or_more_nonblank_boundaries",
                },
            },
            "pre_response_cross_field_check": (
                "For every claim, select exactly one epistemic_status row and "
                f"verify {support_field_id}, qualification, and cannot_support "
                "against that row before returning the JSON object."
            ),
            "forbidden_repairs": [
                "silently_change_epistemic_status",
                "silently_drop_support_fact_ids",
                "silently_add_cannot_support_boundary",
                "coerce_or_rewrite_field_values",
            ],
        }

    def cannot_infer_violation(
        self, claims: Any
    ) -> AuthorityViolation | None:
        if not isinstance(claims, list):
            return None
        count = 0
        has_support_conflict = False
        missing_boundary_conflict = False
        for claim in claims:
            if (
                not isinstance(claim, Mapping)
                or claim.get("epistemic_status") != "cannot_infer"
            ):
                continue
            support_fact_ids = claim.get("support_fact_ids")
            cannot_support = claim.get("cannot_support")
            if not isinstance(support_fact_ids, list) or not isinstance(
                cannot_support, list
            ):
                continue
            has_support = bool(support_fact_ids)
            missing_boundary = not cannot_support
            if has_support or missing_boundary:
                count += 1
                has_support_conflict = has_support_conflict or has_support
                missing_boundary_conflict = (
                    missing_boundary_conflict or missing_boundary
                )
        if not count:
            return None
        if has_support_conflict and missing_boundary_conflict:
            subtype = "cannot_infer_has_support_and_missing_boundary"
        elif has_support_conflict:
            subtype = "cannot_infer_has_support_fact_ids"
        else:
            subtype = "cannot_infer_missing_cannot_support"
        return AuthorityViolation(subtype, count)


@dataclass(frozen=True)
class ClaimScopeResolver:
    """Deterministically bind Claim scope to already validated Numeric facts."""

    deterministic_fields: tuple[str, ...] = (
        "entity_ref",
        "business_scope_kind",
        "business_scope_ref",
        "period",
        "attribution_level",
    )

    def prompt_contract(
        self,
        *,
        support_field_id: str = "support_fact_ids",
    ) -> dict[str, Any]:
        if support_field_id not in {
            "support_fact_ids",
            "support_fact_aliases",
        }:
            raise ValueError("claim_scope_support_field_invalid")
        return {
            "provider_emitted_scope_fields": ["metric_or_mechanism"],
            "locally_assembled_scope_fields": list(self.deterministic_fields),
            "numeric_support_rule": (
                "Runtime derives exact canonical tokens from the Numeric refs "
                f"behind locally expanded {support_field_id}; all supported "
                "Numeric rows must agree."
            ),
            "non_numeric_support_rule": (
                "Runtime binds unknown/unknown/unknown/unknown/none."
            ),
            "provider_must_not_emit_locally_assembled_fields": True,
            "normalization_or_token_copy_by_provider_allowed": False,
        }

    def assemble(
        self,
        *,
        claims: Any,
        facts: Mapping[str, Mapping[str, Any]],
        numeric_scopes: Mapping[str, Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(claims, list):
            raise ValueError(
                "s3_bounded_specialist_scope_assembly_provider_shape_invalid"
            )
        assembled_claims: list[dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                raise ValueError(
                    "s3_bounded_specialist_scope_assembly_provider_shape_invalid"
                )
            provider_scope = claim.get("scope")
            if (
                not isinstance(provider_scope, Mapping)
                or set(provider_scope) != {"metric_or_mechanism"}
                or not isinstance(
                    provider_scope.get("metric_or_mechanism"), str
                )
                or not str(provider_scope["metric_or_mechanism"]).strip()
            ):
                raise ValueError(
                    "s3_bounded_specialist_scope_assembly_provider_shape_invalid"
                )
            support_fact_ids = claim.get("support_fact_ids")
            if (
                not isinstance(support_fact_ids, list)
                or any(
                    not isinstance(fact_id, str) or not fact_id
                    for fact_id in support_fact_ids
                )
            ):
                raise ValueError(
                    "s3_bounded_specialist_scope_assembly_provider_shape_invalid"
                )
            supported_numeric_scopes = [
                numeric_scopes[ref]
                for fact_id in support_fact_ids
                if fact_id in facts
                for ref in facts[fact_id].get("support_refs", ())
                if ref in numeric_scopes
            ]
            if supported_numeric_scopes:
                resolved: dict[str, str] = {}
                for field_id in self.deterministic_fields:
                    values = {
                        str(row[field_id]) for row in supported_numeric_scopes
                    }
                    if len(values) != 1:
                        raise ValueError(
                            "s3_bounded_specialist_scope_assembly_authority_ambiguous"
                        )
                    resolved[field_id] = next(iter(values))
            else:
                resolved = {
                    "entity_ref": "unknown",
                    "business_scope_kind": "unknown",
                    "business_scope_ref": "unknown",
                    "period": "unknown",
                    "attribution_level": "none",
                }
            assembled = dict(claim)
            assembled["scope"] = {
                "entity_ref": resolved["entity_ref"],
                "business_scope_kind": resolved["business_scope_kind"],
                "business_scope_ref": resolved["business_scope_ref"],
                "period": resolved["period"],
                "metric_or_mechanism": str(
                    provider_scope["metric_or_mechanism"]
                ),
                "attribution_level": resolved["attribution_level"],
            }
            assembled_claims.append(assembled)
        return assembled_claims


@dataclass(frozen=True)
class WWCJudgmentAtomViolation:
    """Content-free failure emitted by the v8 WWC atom contract."""

    subtype: str
    field_id: str
    failing_item_count: int

    def __post_init__(self) -> None:
        if (
            not self.subtype
            or not self.field_id
            or type(self.failing_item_count) is not int
            or self.failing_item_count <= 0
        ):
            raise ValueError("WWC_judgment_atom_violation_invalid")


@dataclass(frozen=True)
class WWCAuthorityAlias:
    alias: str
    authority_ref: str
    authority_kind: str
    source_type: str
    entity_or_owner: str
    document_event_or_dataset: str

    def provider_payload(self) -> dict[str, str]:
        return {
            "authority_alias": self.alias,
            "authority_kind": self.authority_kind,
            "entity_or_owner": self.entity_or_owner,
            "document_event_or_dataset": self.document_event_or_dataset,
        }

    def source_target(self) -> dict[str, str]:
        return {
            "source_type": self.source_type,
            "entity_or_owner": self.entity_or_owner,
            "document_event_or_dataset": self.document_event_or_dataset,
        }


@dataclass(frozen=True)
class WWCTemporalDateAlias:
    alias: str
    iso_date: str

    def __post_init__(self) -> None:
        try:
            parsed = date.fromisoformat(self.iso_date)
        except ValueError as exc:
            raise ValueError("WWC_temporal_date_alias_invalid") from exc
        if self.alias == "NONE" or parsed.isoformat() != self.iso_date:
            raise ValueError("WWC_temporal_date_alias_invalid")

    def provider_payload(self) -> dict[str, str]:
        return {
            "date_alias": self.alias,
            "iso_date": self.iso_date,
        }


@dataclass(frozen=True)
class SpecialistWWCJudgmentAtomPolicy:
    """Small Provider judgments deterministically assembled into canonical tasks.

    This object is the single source for the v8 prompt schema, closed alias
    surface, validation, canonical assembly, and fake-Provider fixtures.
    """

    program_cell_id: str
    as_of: str
    claim_policy: TaskClaimLinkPolicy
    authority_aliases: tuple[WWCAuthorityAlias, ...]
    temporal_date_aliases: tuple[WWCTemporalDateAlias, ...] = ()
    contract_ref: str = S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
    omitted_incomplete_authority_ref_count: int = 0

    provider_atom_max_unicode_characters = 160
    provider_output_max_utf8_bytes = 4800
    provider_atom_minimum = 1
    provider_atom_maximum = 3
    rule_types = (
        "threshold_cross",
        "event_occurs",
        "trend_persists",
        "evidence_confirmation",
    )
    expected_claim_transitions = (
        "strengthen",
        "weaken",
        "resolve_cannot_infer",
        "invalidate",
        "no_change",
    )
    start_trigger_codes = (
        "immediate",
        "when_rule_condition_met",
        "next_authority_event",
        "bound_date",
    )
    review_timing_codes = (
        "next_authority_event",
        "next_reporting_event",
        "next_month_end",
        "next_quarter_end",
        "bound_date",
        "unscheduled",
    )
    _transition_text = {
        "strengthen": "strengthen the linked claim",
        "weaken": "weaken the linked claim",
        "resolve_cannot_infer": (
            "resolve the linked claim from cannot_infer"
        ),
        "invalidate": "invalidate the linked claim",
        "no_change": "retain the linked claim state",
    }
    _atom_fields = frozenset(
        {
            "claim_alias",
            "primary_authority_alias",
            "authority_aliases",
            "metric_or_observation",
            "rule_type",
            "comparator_or_condition",
            "threshold_or_observation",
            "start_or_trigger",
            "deadline_or_review_date",
            "expected_claim_transition",
            "fallback_stop_condition",
        }
    )
    _narrative_fields = (
        "metric_or_observation",
        "comparator_or_condition",
        "threshold_or_observation",
        "start_or_trigger",
        "deadline_or_review_date",
        "fallback_stop_condition",
    )
    _temporal_atom_fields = frozenset(
        {
            "claim_alias",
            "primary_authority_alias",
            "authority_aliases",
            "metric_or_observation",
            "rule_type",
            "comparator_or_condition",
            "threshold_or_observation",
            "start_trigger_code",
            "start_date_alias",
            "review_timing_code",
            "review_date_alias",
            "expected_claim_transition",
            "fallback_stop_condition",
        }
    )
    _temporal_narrative_fields = (
        "metric_or_observation",
        "comparator_or_condition",
        "threshold_or_observation",
        "fallback_stop_condition",
    )
    _authority_kinds = (
        ("Evidence", "accepted_evidence_refs"),
        ("Numeric", "numeric_refs"),
        ("Candidate", "candidate_refs_not_evidence"),
        ("Graph", "graph_context_refs_not_evidence"),
    )

    @staticmethod
    def _walk_mapping_rows(value: Any) -> list[Mapping[str, Any]]:
        rows: list[Mapping[str, Any]] = []
        if isinstance(value, Mapping):
            rows.append(value)
            for child in value.values():
                rows.extend(
                    SpecialistWWCJudgmentAtomPolicy._walk_mapping_rows(child)
                )
        elif isinstance(value, (list, tuple)):
            for child in value:
                rows.extend(
                    SpecialistWWCJudgmentAtomPolicy._walk_mapping_rows(child)
                )
        return rows

    @staticmethod
    def _row_for_ref(
        rows: Sequence[Mapping[str, Any]],
        *,
        authority_kind: str,
        authority_ref: str,
    ) -> Mapping[str, Any] | None:
        keys = {
            "Evidence": ("evidence_ref",),
            "Numeric": (
                "numeric_ref",
                "derived_metric_id",
                "derived_metric_ref",
            ),
            "Candidate": ("candidate_id", "document_id"),
            "Graph": (
                "graph_edge_ref",
                "graph_edge_projection_ref",
                "market_context_id",
                "risk_context_id",
            ),
        }[authority_kind]
        return next(
            (
                row
                for row in rows
                if any(row.get(key) == authority_ref for key in keys)
            ),
            None,
        )

    @staticmethod
    def _metadata_for_row(
        authority_kind: str,
        row: Mapping[str, Any],
    ) -> tuple[str, str, str]:
        entity = str(
            row.get("entity_ref")
            or row.get("entity_or_owner")
            or row.get("from_ref")
            or row.get("scope")
            or ""
        )
        if authority_kind == "Evidence":
            label = str(
                row.get("evidence_role")
                or row.get("citation")
                or ""
            )
            period = str(
                row.get("period_or_version")
                or row.get("period")
                or ""
            )
        elif authority_kind == "Numeric":
            label = str(
                row.get("metric_family")
                or row.get("metric")
                or row.get("formula")
                or ""
            )
            period = str(row.get("period") or "")
        elif authority_kind == "Candidate":
            label = str(
                row.get("source_role")
                or row.get("evidence_role")
                or row.get("section_or_table_ref")
                or ""
            )
            period = str(
                row.get("period_ref")
                or row.get("period_or_version")
                or ""
            )
        else:
            label = str(
                row.get("edge_semantics")
                or row.get("risk_type")
                or row.get("status")
                or ""
            )
            endpoints = "->".join(
                value
                for value in (
                    str(row.get("from_ref") or ""),
                    str(row.get("to_ref") or ""),
                )
                if value
            )
            if endpoints:
                label = f"{label}:{endpoints}" if label else endpoints
            period = str(row.get("as_of") or row.get("period") or "")
        dataset = "@".join(value for value in (label, period) if value)
        return authority_kind, entity, dataset

    @classmethod
    def from_cell_input(
        cls,
        *,
        cell_input: Mapping[str, Any],
        claims: Any,
        as_of: str,
        contract_ref: str = S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
        omit_incomplete_authority_refs: bool = False,
    ) -> SpecialistWWCJudgmentAtomPolicy:
        program_cell_id = str(cell_input.get("program_cell_id") or "")
        if (
            not program_cell_id
            or not isinstance(as_of, str)
            or not as_of.strip()
            or contract_ref not in SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REFS
        ):
            raise ValueError("WWC_judgment_atom_local_identity_or_as_of_missing")
        try:
            as_of_date = date.fromisoformat(as_of[:10]).isoformat()
        except ValueError as exc:
            raise ValueError(
                "WWC_judgment_atom_local_identity_or_as_of_missing"
            ) from exc
        claim_policy = TaskClaimLinkPolicy.from_validated_claims(
            program_cell_id=program_cell_id,
            claims=claims,
        )
        authority = cell_input.get("authority_refs")
        if not isinstance(authority, Mapping):
            raise ValueError("WWC_judgment_atom_local_authority_missing")
        searchable_rows = cls._walk_mapping_rows(
            {
                "evidence_input": cell_input.get("evidence_input"),
                "numeric_input": cell_input.get("numeric_input"),
                "graph_context_input": cell_input.get("graph_context_input"),
            }
        )
        raw_rows: list[tuple[str, str, str, str, str]] = []
        omitted_incomplete_authority_ref_count = 0
        for authority_kind, surface_key in cls._authority_kinds:
            refs = _exact_nonblank_strings(authority.get(surface_key))
            for authority_ref in refs:
                row = cls._row_for_ref(
                    searchable_rows,
                    authority_kind=authority_kind,
                    authority_ref=authority_ref,
                )
                if row is None:
                    if omit_incomplete_authority_refs:
                        omitted_incomplete_authority_ref_count += 1
                        continue
                    raise ValueError(
                        "WWC_judgment_atom_local_authority_metadata_missing"
                    )
                source_type, entity, dataset = cls._metadata_for_row(
                    authority_kind, row
                )
                if not entity.strip() or not dataset.strip():
                    if omit_incomplete_authority_refs:
                        omitted_incomplete_authority_ref_count += 1
                        continue
                    raise ValueError(
                        "WWC_judgment_atom_local_authority_metadata_missing"
                    )
                raw_rows.append(
                    (
                        authority_kind,
                        authority_ref,
                        source_type,
                        entity,
                        dataset,
                    )
                )
        if not raw_rows:
            raise ValueError("WWC_judgment_atom_local_authority_missing")
        authority_aliases = tuple(
            WWCAuthorityAlias(
                alias=f"A{ordinal:03d}",
                authority_kind=authority_kind,
                authority_ref=authority_ref,
                source_type=source_type,
                entity_or_owner=entity,
                document_event_or_dataset=dataset,
            )
            for ordinal, (
                authority_kind,
                authority_ref,
                source_type,
                entity,
                dataset,
            ) in enumerate(raw_rows, 1)
        )
        temporal_date_aliases: tuple[WWCTemporalDateAlias, ...] = ()
        if contract_ref == S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF:
            iso_dates = {as_of_date}
            iso_pattern = re.compile(
                r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)"
            )
            for row in cls._walk_mapping_rows(cell_input):
                for value in row.values():
                    if not isinstance(value, str):
                        continue
                    for match in iso_pattern.finditer(value):
                        try:
                            iso_dates.add(
                                date.fromisoformat(match.group(1)).isoformat()
                            )
                        except ValueError:
                            continue
            temporal_date_aliases = tuple(
                WWCTemporalDateAlias(
                    alias=f"D{ordinal:03d}",
                    iso_date=iso_date,
                )
                for ordinal, iso_date in enumerate(sorted(iso_dates), 1)
            )
        return cls(
            program_cell_id=program_cell_id,
            as_of=as_of,
            claim_policy=claim_policy,
            authority_aliases=authority_aliases,
            temporal_date_aliases=temporal_date_aliases,
            contract_ref=contract_ref,
            omitted_incomplete_authority_ref_count=(
                omitted_incomplete_authority_ref_count
            ),
        )

    @property
    def alias_to_authority(self) -> dict[str, WWCAuthorityAlias]:
        return {row.alias: row for row in self.authority_aliases}

    @property
    def alias_to_iso_date(self) -> dict[str, str]:
        return {
            row.alias: row.iso_date for row in self.temporal_date_aliases
        }

    @property
    def temporal_authority_enabled(self) -> bool:
        return (
            self.contract_ref
            == S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
        )

    def required_output_schema(self) -> dict[str, Any]:
        bounded = (
            "non-empty string, maximum "
            f"{self.provider_atom_max_unicode_characters} Unicode characters"
        )
        atom_schema = {
            "claim_alias": (
                "exact claim_alias from "
                "WWC_judgment_atom_contract.allowed_claims"
            ),
            "primary_authority_alias": (
                "exact authority_alias from "
                "WWC_judgment_atom_contract.allowed_authorities"
            ),
            "authority_aliases": [
                (
                    "one or more exact authority_alias values; include "
                    "primary_authority_alias"
                )
            ],
            "metric_or_observation": bounded,
            "rule_type": "|".join(self.rule_types),
            "comparator_or_condition": bounded,
            "threshold_or_observation": bounded,
            "expected_claim_transition": "|".join(
                self.expected_claim_transitions
            ),
            "fallback_stop_condition": bounded,
        }
        if self.temporal_authority_enabled:
            atom_schema.update(
                {
                    "start_trigger_code": "|".join(
                        self.start_trigger_codes
                    ),
                    "start_date_alias": (
                        "exact date_alias from allowed_date_aliases when "
                        "start_trigger_code=bound_date; otherwise NONE"
                    ),
                    "review_timing_code": "|".join(
                        self.review_timing_codes
                    ),
                    "review_date_alias": (
                        "exact date_alias from allowed_date_aliases when "
                        "review_timing_code=bound_date; otherwise NONE"
                    ),
                }
            )
        else:
            atom_schema.update(
                {
                    "start_or_trigger": bounded,
                    "deadline_or_review_date": bounded,
                }
            )
        return {
            "program_cell_id": "exact input program_cell_id",
            "what_would_change_judgment_atoms": [atom_schema],
        }

    def prompt_contract(self) -> dict[str, Any]:
        contract = {
            "contract_ref": self.contract_ref,
            "allowed_claims": [
                row.provider_payload()
                for row in self.claim_policy.alias_rows
            ],
            "allowed_authorities": [
                row.provider_payload() for row in self.authority_aliases
            ],
            "provider_owned_fields": sorted(
                self._temporal_atom_fields
                if self.temporal_authority_enabled
                else self._atom_fields
            ),
            "locally_assembled_fields": [
                "task_id",
                "claim_id",
                "source_target",
                "decision_rule",
                (
                    "time_window"
                    if self.temporal_authority_enabled
                    else "time_window.as_of"
                ),
                "authority_refs",
                "canonical ordering and lineage",
            ],
            "provider_must_not_emit": [
                "task_id",
                "claim_id",
                "source_target",
                "decision_rule",
                "time_window",
                "authority_refs",
                "raw authority refs",
            ],
            "rule_types": list(self.rule_types),
            "expected_claim_transitions": list(
                self.expected_claim_transitions
            ),
            "atom_cardinality": "1..3",
            "maximum_atom_narrative_unicode_characters": (
                self.provider_atom_max_unicode_characters
            ),
            "maximum_provider_output_utf8_bytes": (
                self.provider_output_max_utf8_bytes
            ),
            "normalization_guess_fuzzy_match_remap_or_silent_drop_allowed": (
                False
            ),
        }
        if self.temporal_authority_enabled:
            contract.update(
                {
                    "allowed_date_aliases": [
                        row.provider_payload()
                        for row in self.temporal_date_aliases
                    ],
                    "no_date_alias": "NONE",
                    "start_trigger_codes": list(
                        self.start_trigger_codes
                    ),
                    "review_timing_codes": list(
                        self.review_timing_codes
                    ),
                    "provider_authored_calendar_text_allowed": False,
                    "local_exact_date_and_relative_time_rendering_owner": True,
                }
            )
        return contract

    def provider_prior_claim_segment(
        self, claim_segment: Mapping[str, Any]
    ) -> dict[str, Any]:
        return self.claim_policy.provider_prior_claim_segment(claim_segment)

    @staticmethod
    def _exact_bounded_text(value: Any, maximum: int) -> bool:
        return (
            isinstance(value, str)
            and bool(value)
            and value == value.strip()
            and len(value) <= maximum
        )

    @staticmethod
    def _month_end(value: date) -> date:
        following_month = (
            date(value.year + 1, 1, 1)
            if value.month == 12
            else date(value.year, value.month + 1, 1)
        )
        return following_month - timedelta(days=1)

    @classmethod
    def _next_month_end(cls, value: date) -> date:
        current = cls._month_end(value)
        if value < current:
            return current
        following = current + timedelta(days=1)
        return cls._month_end(following)

    @staticmethod
    def _next_quarter_end(value: date) -> date:
        quarter_end_month = ((value.month - 1) // 3 + 1) * 3
        following_month = (
            date(value.year + 1, 1, 1)
            if quarter_end_month == 12
            else date(value.year, quarter_end_month + 1, 1)
        )
        current = following_month - timedelta(days=1)
        if value < current:
            return current
        next_quarter_month = quarter_end_month + 3
        next_year = value.year
        if next_quarter_month > 12:
            next_quarter_month -= 12
            next_year += 1
        next_following = (
            date(next_year + 1, 1, 1)
            if next_quarter_month == 12
            else date(next_year, next_quarter_month + 1, 1)
        )
        return next_following - timedelta(days=1)

    def _render_temporal_fields(
        self,
        atom: Mapping[str, Any],
    ) -> tuple[dict[str, str] | None, WWCJudgmentAtomViolation | None]:
        start_code = atom.get("start_trigger_code")
        review_code = atom.get("review_timing_code")
        if start_code not in self.start_trigger_codes:
            return None, WWCJudgmentAtomViolation(
                "start_trigger_code_unknown",
                "start_trigger_code",
                1,
            )
        if review_code not in self.review_timing_codes:
            return None, WWCJudgmentAtomViolation(
                "review_timing_code_unknown",
                "review_timing_code",
                1,
            )
        date_by_alias = self.alias_to_iso_date
        start_alias = atom.get("start_date_alias")
        review_alias = atom.get("review_date_alias")
        if (
            (start_code == "bound_date" and start_alias not in date_by_alias)
            or (start_code != "bound_date" and start_alias != "NONE")
        ):
            return None, WWCJudgmentAtomViolation(
                "start_date_alias_binding_invalid",
                "start_date_alias",
                1,
            )
        if (
            (review_code == "bound_date" and review_alias not in date_by_alias)
            or (review_code != "bound_date" and review_alias != "NONE")
        ):
            return None, WWCJudgmentAtomViolation(
                "review_date_alias_binding_invalid",
                "review_date_alias",
                1,
            )
        as_of_date = date.fromisoformat(self.as_of[:10])
        start_rendering = {
            "immediate": f"immediate_from:{self.as_of}",
            "when_rule_condition_met": "when_decision_rule_condition_is_met",
            "next_authority_event": (
                f"next_bound_authority_event_after:{self.as_of}"
            ),
            "bound_date": date_by_alias.get(str(start_alias), ""),
        }[str(start_code)]
        review_rendering = {
            "next_authority_event": (
                f"next_bound_authority_event_after:{self.as_of}"
            ),
            "next_reporting_event": (
                f"next_reporting_event_after:{self.as_of}"
            ),
            "next_month_end": self._next_month_end(
                as_of_date
            ).isoformat(),
            "next_quarter_end": self._next_quarter_end(
                as_of_date
            ).isoformat(),
            "bound_date": date_by_alias.get(str(review_alias), ""),
            "unscheduled": "unscheduled",
        }[str(review_code)]
        return {
            "as_of": self.as_of,
            "start_or_trigger": start_rendering,
            "deadline_or_review_date": review_rendering,
        }, None

    def assemble(
        self,
        output: Mapping[str, Any],
        *,
        provider_output_utf8_bytes: int,
    ) -> tuple[dict[str, Any] | None, WWCJudgmentAtomViolation | None]:
        if (
            type(provider_output_utf8_bytes) is not int
            or provider_output_utf8_bytes <= 0
        ):
            return None, WWCJudgmentAtomViolation(
                "provider_output_byte_count_invalid",
                "assembled_output",
                1,
            )
        if provider_output_utf8_bytes > self.provider_output_max_utf8_bytes:
            return None, WWCJudgmentAtomViolation(
                "provider_output_over_max_utf8_bytes",
                "assembled_output",
                1,
            )
        if set(output) != {
            "program_cell_id",
            "what_would_change_judgment_atoms",
        } or output.get("program_cell_id") != self.program_cell_id:
            return None, WWCJudgmentAtomViolation(
                "provider_top_level_shape_invalid",
                "top_level",
                1,
            )
        atoms = output.get("what_would_change_judgment_atoms")
        if (
            not isinstance(atoms, list)
            or not self.provider_atom_minimum
            <= len(atoms)
            <= self.provider_atom_maximum
        ):
            return None, WWCJudgmentAtomViolation(
                "atom_cardinality_invalid",
                "what_would_change_judgment_atoms",
                1,
            )
        claim_by_alias = self.claim_policy.alias_to_claim_id
        authority_by_alias = self.alias_to_authority
        atom_fields = (
            self._temporal_atom_fields
            if self.temporal_authority_enabled
            else self._atom_fields
        )
        narrative_fields = (
            self._temporal_narrative_fields
            if self.temporal_authority_enabled
            else self._narrative_fields
        )
        canonical_tasks: list[dict[str, Any]] = []
        for ordinal, atom in enumerate(atoms, 1):
            if not isinstance(atom, Mapping) or set(atom) != atom_fields:
                return None, WWCJudgmentAtomViolation(
                    "atom_shape_invalid",
                    "what_would_change_judgment_atoms",
                    1,
                )
            claim_alias = atom.get("claim_alias")
            if claim_alias not in claim_by_alias:
                subtype = (
                    "claim_alias_wrong_kind"
                    if claim_alias in authority_by_alias
                    else "claim_alias_unknown_or_cross_cell"
                )
                return None, WWCJudgmentAtomViolation(
                    subtype,
                    "claim_alias",
                    1,
                )
            primary_alias = atom.get("primary_authority_alias")
            if primary_alias not in authority_by_alias:
                subtype = (
                    "authority_alias_wrong_kind"
                    if primary_alias in claim_by_alias
                    else "authority_alias_unknown_or_cross_cell"
                )
                return None, WWCJudgmentAtomViolation(
                    subtype,
                    "primary_authority_alias",
                    1,
                )
            authority_aliases = atom.get("authority_aliases")
            if (
                not isinstance(authority_aliases, list)
                or not authority_aliases
                or primary_alias not in authority_aliases
                or any(
                    not isinstance(alias, str) or not alias
                    for alias in authority_aliases
                )
                or len(authority_aliases) != len(set(authority_aliases))
            ):
                return None, WWCJudgmentAtomViolation(
                    "authority_alias_array_invalid",
                    "authority_aliases",
                    1,
                )
            unknown_authorities = [
                alias
                for alias in authority_aliases
                if alias not in authority_by_alias
            ]
            if unknown_authorities:
                wrong_kind = sum(
                    alias in claim_by_alias for alias in unknown_authorities
                )
                return None, WWCJudgmentAtomViolation(
                    (
                        "authority_alias_wrong_kind"
                        if wrong_kind
                        else "authority_alias_unknown_or_cross_cell"
                    ),
                    "authority_aliases",
                    len(unknown_authorities),
                )
            invalid_narrative = [
                field_id
                for field_id in narrative_fields
                if not self._exact_bounded_text(
                    atom.get(field_id),
                    self.provider_atom_max_unicode_characters,
                )
            ]
            if invalid_narrative:
                return None, WWCJudgmentAtomViolation(
                    "atom_narrative_invalid",
                    invalid_narrative[0],
                    len(invalid_narrative),
                )
            rule_type = atom.get("rule_type")
            if rule_type not in self.rule_types:
                return None, WWCJudgmentAtomViolation(
                    "rule_type_unknown",
                    "rule_type",
                    1,
                )
            transition = atom.get("expected_claim_transition")
            if transition not in self.expected_claim_transitions:
                return None, WWCJudgmentAtomViolation(
                    "expected_claim_transition_unknown",
                    "expected_claim_transition",
                    1,
                )
            if self.temporal_authority_enabled:
                time_window, temporal_violation = (
                    self._render_temporal_fields(atom)
                )
                if temporal_violation is not None:
                    return None, temporal_violation
                if time_window is None:
                    return None, WWCJudgmentAtomViolation(
                        "temporal_local_rendering_failed",
                        "time_window",
                        1,
                    )
            else:
                time_window = {
                    "as_of": self.as_of,
                    "start_or_trigger": atom["start_or_trigger"],
                    "deadline_or_review_date": atom[
                        "deadline_or_review_date"
                    ],
                }
            primary = authority_by_alias[str(primary_alias)]
            canonical_tasks.append(
                {
                    "task_id": (
                        f"{self.program_cell_id}:what_would_change:"
                        f"{ordinal:03d}"
                    ),
                    "claim_id": claim_by_alias[str(claim_alias)],
                    "source_target": primary.source_target(),
                    "metric_or_observation": atom["metric_or_observation"],
                    "decision_rule": {
                        "rule_type": rule_type,
                        "comparator_or_condition": atom[
                            "comparator_or_condition"
                        ],
                        "threshold_or_observation": atom[
                            "threshold_or_observation"
                        ],
                    },
                    "time_window": time_window,
                    "expected_claim_transition": self._transition_text[
                        str(transition)
                    ],
                    "fallback_stop_condition": atom[
                        "fallback_stop_condition"
                    ],
                    "authority_refs": [
                        authority_by_alias[alias].authority_ref
                        for alias in sorted(authority_aliases)
                    ],
                }
            )
        return {
            "program_cell_id": self.program_cell_id,
            "what_would_change": canonical_tasks,
        }, None

    def fake_provider_output(
        self,
        *,
        atom_count: int = 3,
        narrative_characters: int = 24,
    ) -> dict[str, Any]:
        """Generate a contract-owned valid fake response without a model call."""

        if (
            not self.provider_atom_minimum
            <= atom_count
            <= self.provider_atom_maximum
            or not 1
            <= narrative_characters
            <= self.provider_atom_max_unicode_characters
        ):
            raise ValueError("WWC_judgment_atom_fake_shape_invalid")
        claim_aliases = [row.alias for row in self.claim_policy.alias_rows]
        authority_aliases = [row.alias for row in self.authority_aliases]
        filler = "x" * narrative_characters
        atoms = []
        for ordinal in range(1, atom_count + 1):
            atom = {
                "claim_alias": claim_aliases[
                    (ordinal - 1) % len(claim_aliases)
                ],
                "primary_authority_alias": authority_aliases[
                    (ordinal - 1) % len(authority_aliases)
                ],
                "authority_aliases": [
                    authority_aliases[
                        (ordinal - 1) % len(authority_aliases)
                    ]
                ],
                "metric_or_observation": filler,
                "rule_type": self.rule_types[
                    (ordinal - 1) % len(self.rule_types)
                ],
                "comparator_or_condition": filler,
                "threshold_or_observation": filler,
                "expected_claim_transition": (
                    self.expected_claim_transitions[
                        (ordinal - 1)
                        % len(self.expected_claim_transitions)
                    ]
                ),
                "fallback_stop_condition": filler,
            }
            if self.temporal_authority_enabled:
                atom.update(
                    {
                        "start_trigger_code": (
                            self.start_trigger_codes[
                                (ordinal - 1)
                                % (len(self.start_trigger_codes) - 1)
                            ]
                        ),
                        "start_date_alias": "NONE",
                        "review_timing_code": (
                            self.review_timing_codes[
                                (ordinal - 1)
                                % (len(self.review_timing_codes) - 1)
                            ]
                        ),
                        "review_date_alias": "NONE",
                    }
                )
            else:
                atom.update(
                    {
                        "start_or_trigger": filler,
                        "deadline_or_review_date": filler,
                    }
                )
            atoms.append(atom)
        output = {
            "program_cell_id": self.program_cell_id,
            "what_would_change_judgment_atoms": atoms,
        }
        serialized = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(serialized) > self.provider_output_max_utf8_bytes:
            raise ValueError("WWC_judgment_atom_fake_output_over_byte_cap")
        return output
