"""Compact, one-run authority boundary for the Dell Q1 paid shadow."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dell_reference_vertical_contracts import canonical_sha256
from .deepseek_structured_agents import TokenBudgetBasis


DELL_Q1_PAID_SHADOW_SERVING_MODE = "q1_specialist_paid_shadow_v1"
DELL_Q1_REVIEW_SERVING_MODE = "q1_workpaper_review_repair_v1"
DELL_LEAD_RESEARCH_SERVING_MODE = "lead_research_delegation_v1"
DELL_Q1_PAID_SHADOW_AUTHORITY_ENV = "FINSIGHT_DELL_PAID_SHADOW_AUTHORITY_PATH"
DELL_IMPLEMENTATION_COMMIT_ENV = "FINSIGHT_DELL_IMPLEMENTATION_COMMIT"

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_COMMIT_PATTERN = r"^[0-9a-f]{40}$"
_FORBIDDEN_AUDIT_KEYS = frozenset(
    {
        "semantic_input",
        "raw_response",
        "messages",
        "prompt",
        "reasoning",
        "reasoning_content",
        "api_key",
    }
)


class DellSpecialistPaidShadowError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkpaperReviewScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    seed_state_relative_path: str = Field(pattern=r"^[a-z0-9_-]+/specialist-final-state\.private\.json$")
    seed_state_sha256: str = Field(pattern=_DIGEST_PATTERN)
    node_budgets: dict[Literal["verifier", "counter", "repair"], TokenBudgetBasis]
    max_reviewer_model_turns: int = Field(ge=2, le=12)
    max_reviewer_tool_actions: int = Field(ge=1, le=16)
    max_author_revisions: Literal[1]

    @model_validator(mode="after")
    def validate_nodes(self) -> "WorkpaperReviewScope":
        if set(self.node_budgets) != {"verifier", "counter", "repair"}:
            raise ValueError("review_node_budget_set_invalid")
        if any(b.node_role != "specialist" for b in self.node_budgets.values()):
            raise ValueError("review_nodes_require_existing_agentic_transport")
        return self


class LeadResearchScope(BaseModel):
    """First two-topic delegation qualification, not full-case publication."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    seed_state_relative_path: str = Field(pattern=r"^[a-z0-9_-]+/specialist-final-state\.private\.json$")
    seed_state_sha256: str = Field(pattern=_DIGEST_PATTERN)
    allowed_branch_ids: tuple[Literal["Q5_SUPPLY_AND_PRICE", "Q6_MODEL_COMPUTE_DEMAND"], ...]
    node_budgets: dict[Literal["lead", "specialist"], TokenBudgetBasis]
    max_lead_model_turns: int = Field(ge=2, le=12)
    max_tasks: int = Field(ge=2, le=4)
    max_parallel_tasks: Literal[2]

    @model_validator(mode="after")
    def validate_scope(self) -> "LeadResearchScope":
        if (len(self.allowed_branch_ids) != 2 or set(self.allowed_branch_ids)
                != {"Q5_SUPPLY_AND_PRICE", "Q6_MODEL_COMPUTE_DEMAND"}):
            raise ValueError("lead_requires_both_qualified_research_topics")
        if set(self.node_budgets) != {"lead", "specialist"} or any(
            role != basis.node_role or basis.reasoning_profile != "agentic_message_history_thinking_enabled"
            for role, basis in self.node_budgets.items()
        ):
            raise ValueError("lead_node_budget_or_context_profile_invalid")
        return self


class DellQ1SpecialistPaidShadowAuthority(BaseModel):
    """The only checked-in Owner decision consumed by this one shadow."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        str_strip_whitespace=True,
    )

    schema_version: Literal[
        "fin_ia_dell_q1_specialist_paid_shadow_authority_v1_0"
    ]
    decision_id: str = Field(min_length=1, max_length=240)
    decision_status: Literal["authorized_once"]
    qualification_only: Literal[True]
    paid_full_chain_execution_id: str = Field(min_length=1, max_length=240)
    agent_session_id: str = Field(min_length=1, max_length=180)
    fin_thread_id: str = Field(min_length=1, max_length=180)
    research_run_id: str = Field(min_length=1, max_length=180)
    run_invocation_id: str = Field(min_length=1, max_length=180)
    graph_id: Literal["dell_reference_vertical"]
    serving_mode: Literal["q1_specialist_paid_shadow_v1", "q1_workpaper_review_repair_v1", "lead_research_delegation_v1"]
    branch_id: Literal["Q1_ISSUER_TRUTH"]
    node_id: Literal["specialist:Q1_ISSUER_TRUTH"]
    provider: Literal["deepseek"]
    model: Literal["deepseek-v4-pro"]
    research_as_of: Literal["2026-09-02T00:00:00Z"]
    implementation_commit: str = Field(pattern=_COMMIT_PATTERN)
    deepseek_config_sha256: str = Field(pattern=_DIGEST_PATTERN)
    owner_data_gate_decision_digest: str = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: str = Field(pattern=_DIGEST_PATTERN)
    source_route_catalog_digest: str = Field(pattern=_DIGEST_PATTERN)
    max_model_turns: int = Field(ge=2, le=24)
    max_tool_actions: int = Field(ge=1, le=48)
    max_input_characters_per_turn: int = Field(ge=10_000, le=500_000)
    max_output_tokens_per_turn: int = Field(ge=1_000, le=32_000)
    timeout_seconds_per_turn: float = Field(ge=30, le=600)
    max_transport_attempts_per_turn: Literal[1]
    retry_policy: Literal["none"]
    fallback_policy: Literal["none"]
    truncation_behavior: Literal["fail_closed_no_partial_promotion"]
    unknown_outcome_behavior: Literal["stop_and_require_human_review"]
    node_purpose: str = Field(min_length=20, max_length=2_000)
    input_scale_basis: str = Field(min_length=20, max_length=2_000)
    required_outputs: tuple[str, ...] = Field(min_length=1, max_length=8)
    schema_burden: str = Field(min_length=20, max_length=2_000)
    materiality_quality_risk: str = Field(min_length=20, max_length=2_000)
    comparable_run_evidence: str = Field(min_length=20, max_length=2_000)
    reasoning_profile: str = Field(min_length=20, max_length=1_000)
    cost_and_latency_estimate: str = Field(min_length=20, max_length=2_000)
    live_external_calls_authorized: Literal[False]
    evidence_admission_authorized: Literal[False]
    s2_write_authorized: Literal[False]
    other_model_nodes_authorized: bool
    workflow: Literal["single_specialist", "workpaper_review_repair", "lead_research_delegation"] = "single_specialist"
    review_scope: WorkpaperReviewScope | None = None
    lead_scope: LeadResearchScope | None = None
    artifact_root_container: str = Field(min_length=20, max_length=1_000)
    model_audit_filename: Literal["model-call-events.jsonl"]
    source_read_enabled: bool = False
    private_reasoning_audit_authorized: bool = False
    deepseek_config_filename: str = Field(
        default="fin_ia_0_1_3_dell_reference_vertical_deepseek_structured_agents_v1_0.json",
        pattern=r"^[a-z0-9_]+\.json$",
    )
    decision_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_authority(self) -> "DellQ1SpecialistPaidShadowAuthority":
        is_review = self.workflow == "workpaper_review_repair"
        is_lead = self.workflow == "lead_research_delegation"
        if (is_review != (self.serving_mode == DELL_Q1_REVIEW_SERVING_MODE)
                or is_lead != (self.serving_mode == DELL_LEAD_RESEARCH_SERVING_MODE)):
            raise ValueError("paid_shadow_workflow_serving_mode_mismatch")
        if ((is_review or is_lead) != self.other_model_nodes_authorized
                or is_review != (self.review_scope is not None) or is_lead != (self.lead_scope is not None)):
            raise ValueError("paid_shadow_review_scope_authority_mismatch")
        if (is_review or is_lead) and not (self.source_read_enabled and self.private_reasoning_audit_authorized):
            raise ValueError("paid_review_requires_source_context_and_private_audit")
        if is_lead:
            basis = self.lead_scope.node_budgets["specialist"]
            if (basis.max_input_characters != self.max_input_characters_per_turn
                    or basis.max_output_tokens != self.max_output_tokens_per_turn
                    or basis.timeout_seconds != self.timeout_seconds_per_turn):
                raise ValueError("lead_specialist_budget_must_match_execution_envelope")
        if len(self.required_outputs) != len(set(self.required_outputs)):
            raise ValueError("paid_shadow_required_output_duplicate")
        if not self.artifact_root_container.startswith(
            "/run/fin-insight/paid-shadow/"
        ):
            raise ValueError("paid_shadow_artifact_root_invalid")
        if Path(self.artifact_root_container).name != self.paid_full_chain_execution_id:
            raise ValueError("paid_shadow_artifact_execution_binding_invalid")
        unsigned = self.model_dump(mode="json", exclude={"decision_digest"})
        # Old consumed authorities remain readable; their original signed JSON
        # did not have these opt-in fields. Never rewrite those old files.
        for field in ("source_read_enabled", "private_reasoning_audit_authorized", "deepseek_config_filename", "workflow", "review_scope", "lead_scope"):
            if field not in self.model_fields_set:
                unsigned.pop(field, None)
        if canonical_sha256(unsigned) != self.decision_digest:
            raise ValueError("paid_shadow_decision_digest_mismatch")
        return self


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_dell_q1_paid_shadow_authority(
    path: str | Path,
) -> DellQ1SpecialistPaidShadowAuthority:
    try:
        return DellQ1SpecialistPaidShadowAuthority.model_validate_json(
            Path(path).read_text(encoding="utf-8")
        )
    except Exception:
        raise DellSpecialistPaidShadowError(
            "paid_shadow_authority_invalid"
        ) from None


def require_runtime_authority_binding(
    authority: DellQ1SpecialistPaidShadowAuthority,
    *,
    agent_session_id: str,
    research_run_id: str,
    run_invocation_id: str,
    implementation_commit: str,
) -> None:
    if (
        authority.agent_session_id != agent_session_id
        or authority.research_run_id != research_run_id
        or authority.run_invocation_id != run_invocation_id
        or authority.implementation_commit != implementation_commit
    ):
        raise DellSpecialistPaidShadowError(
            "paid_shadow_runtime_authority_binding_invalid"
        )


def require_data_authority_binding(
    authority: DellQ1SpecialistPaidShadowAuthority,
    *,
    owner_data_gate_decision_digest: str,
    inventory_snapshot_digest: str,
    source_route_catalog_digest: str,
) -> None:
    if (
        authority.owner_data_gate_decision_digest
        != owner_data_gate_decision_digest
        or authority.inventory_snapshot_digest != inventory_snapshot_digest
        or authority.source_route_catalog_digest != source_route_catalog_digest
    ):
        raise DellSpecialistPaidShadowError(
            "paid_shadow_data_authority_binding_invalid"
        )


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(
                nested
                for child in value.values()
                for nested in _nested_keys(child)
            ),
        }
    if isinstance(value, list | tuple):
        return {
            nested
            for child in value
            for nested in _nested_keys(child)
        }
    return set()


def build_public_model_audit_sink(
    authority: DellQ1SpecialistPaidShadowAuthority,
) -> Callable[[Mapping[str, Any]], None]:
    root = Path(authority.artifact_root_container)
    path = root / authority.model_audit_filename
    root.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise DellSpecialistPaidShadowError(
            "paid_shadow_model_audit_already_exists"
        )

    def write(event: Mapping[str, Any]) -> None:
        body = json.loads(
            json.dumps(dict(event), ensure_ascii=False, allow_nan=False)
        )
        if _FORBIDDEN_AUDIT_KEYS.intersection(_nested_keys(body)):
            raise DellSpecialistPaidShadowError(
                "paid_shadow_private_model_payload_forbidden"
            )
        record = {
            **body,
            "paid_execution_id": authority.paid_full_chain_execution_id,
            "authority_decision_digest": authority.decision_digest,
        }
        record["audit_event_digest"] = canonical_sha256(record)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    return write


def build_private_model_audit_sink(authority: DellQ1SpecialistPaidShadowAuthority):
    if not authority.private_reasoning_audit_authorized:
        return None
    path = Path(authority.artifact_root_container) / "model-context-reasoning.private.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8"):
        pass

    def write(event: Mapping[str, Any]) -> None:
        # Payloads come from SDK messages, never environment/clients/credentials.
        record = {**dict(event), "paid_execution_id": authority.paid_full_chain_execution_id}
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    return write


__all__ = [
    "DELL_IMPLEMENTATION_COMMIT_ENV",
    "DELL_Q1_PAID_SHADOW_AUTHORITY_ENV",
    "DELL_Q1_PAID_SHADOW_SERVING_MODE",
    "DellQ1SpecialistPaidShadowAuthority",
    "DellSpecialistPaidShadowError",
    "build_public_model_audit_sink",
    "file_sha256",
    "load_dell_q1_paid_shadow_authority",
    "require_data_authority_binding",
    "require_runtime_authority_binding",
]
