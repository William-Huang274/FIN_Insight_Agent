"""Compact, one-run authority boundary for the Dell Q1 paid shadow."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .dell_reference_vertical_contracts import canonical_sha256


DELL_Q1_PAID_SHADOW_SERVING_MODE = "q1_specialist_paid_shadow_v1"
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
    serving_mode: Literal["q1_specialist_paid_shadow_v1"]
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
    max_model_turns: int = Field(ge=2, le=8)
    max_tool_actions: int = Field(ge=1, le=12)
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
    other_model_nodes_authorized: Literal[False]
    artifact_root_container: str = Field(min_length=20, max_length=1_000)
    model_audit_filename: Literal["model-call-events.jsonl"]
    decision_digest: str = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_authority(self) -> "DellQ1SpecialistPaidShadowAuthority":
        if len(self.required_outputs) != len(set(self.required_outputs)):
            raise ValueError("paid_shadow_required_output_duplicate")
        if not self.artifact_root_container.startswith(
            "/run/fin-insight/paid-shadow/"
        ):
            raise ValueError("paid_shadow_artifact_root_invalid")
        if Path(self.artifact_root_container).name != self.paid_full_chain_execution_id:
            raise ValueError("paid_shadow_artifact_execution_binding_invalid")
        unsigned = self.model_dump(mode="json", exclude={"decision_digest"})
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
