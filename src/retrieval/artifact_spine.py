from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ARTIFACT_ENVELOPE_SCHEMA_VERSION = "fin_ia_s1_artifact_envelope_v1_0"
ARTIFACT_SPINE_POLICY_SCHEMA_VERSION = "fin_ia_s1_artifact_spine_policy_v1_0"
COVERAGE_MATRIX_SCHEMA_VERSION = "fin_ia_s1_implementation_coverage_matrix_v1_0"

ArtifactType = Literal[
    "source_route_decision",
    "raw_source_capture",
    "parsed_document",
    "financial_evidence_object",
    "object_manifest",
    "index_snapshot",
    "s2_sibling_binding",
    "evidence_request",
    "query_facet_plan",
    "candidate_set",
    "candidate_ranking",
    "candidate_decision",
    "evidence_coverage_state",
    "evidence_pack_readiness",
    "workbench_projection",
    "frozen_consumer_probe",
]

ResponsibilityAxis = Literal[
    "S1-A",
    "S1-B",
    "S1-C",
    "S1-D",
    "S1-E",
    "S1-F",
    "S1-G",
    "S1-H",
    "S1-I",
    "S1-J",
]

DeliveryState = Literal[
    "unproven",
    "component_engineering_pass",
    "vertical_slice_integrated",
    "S1_qualified_stable",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,255}$")
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,15}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ArtifactSpineError(ValueError):
    """Raised when the canonical S1 control-plane lineage is ambiguous."""


def canonical_json_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportingPeriodBinding(_FrozenModel):
    start_date: str | None = None
    end_date: str | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    fiscal_period: str | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_iso_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _ISO_DATE.fullmatch(value):
            raise ValueError("artifact_reporting_period_date_invalid")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("artifact_reporting_period_date_invalid") from exc
        return value

    @model_validator(mode="after")
    def require_one_period_field(self) -> "ReportingPeriodBinding":
        if not any(
            (
                self.start_date,
                self.end_date,
                self.fiscal_year,
                self.fiscal_period,
            )
        ):
            raise ValueError("artifact_reporting_period_empty")
        if (
            self.start_date
            and self.end_date
            and self.start_date > self.end_date
        ):
            raise ValueError("artifact_reporting_period_range_invalid")
        return self


class SourceLocatorBinding(_FrozenModel):
    locator_type: Literal[
        "url",
        "page",
        "page_bbox",
        "section",
        "xpath",
        "char_span",
        "table_cell",
        "sql_row",
        "object_id",
    ]
    locator_value: str = Field(min_length=1, max_length=2048)


class ArtifactScope(_FrozenModel):
    binding_state: Literal[
        "source_only",
        "case_bound",
        "case_and_source_bound",
        "aggregate",
    ]
    case_key: str | None = None
    subject_ticker: str | None = None
    source_owner_ticker: str | None = None
    discussed_entity_tickers: tuple[str, ...] = ()
    research_as_of: str | None = None
    reporting_period: ReportingPeriodBinding | None = None
    locator: SourceLocatorBinding | None = None

    @field_validator(
        "case_key",
        "subject_ticker",
        "source_owner_ticker",
        mode="before",
    )
    @classmethod
    def normalize_identifier(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip().upper()
        if not _TICKER.fullmatch(normalized):
            raise ValueError("artifact_scope_identifier_invalid")
        return normalized

    @field_validator("discussed_entity_tickers", mode="before")
    @classmethod
    def normalize_discussed_entities(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        normalized = tuple(str(item).strip().upper() for item in value)
        if len(normalized) != len(set(normalized)) or not all(
            _TICKER.fullmatch(item) for item in normalized
        ):
            raise ValueError("artifact_scope_discussed_entities_invalid")
        return normalized

    @field_validator("research_as_of")
    @classmethod
    def validate_research_as_of(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _ISO_DATE.fullmatch(value):
            raise ValueError("artifact_scope_as_of_invalid")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("artifact_scope_as_of_invalid") from exc
        return value

    @model_validator(mode="after")
    def validate_binding_state(self) -> "ArtifactScope":
        if self.binding_state == "source_only" and not self.source_owner_ticker:
            raise ValueError("artifact_scope_source_owner_required")
        if self.binding_state in {"case_bound", "case_and_source_bound"}:
            if not self.case_key or not self.subject_ticker:
                raise ValueError("artifact_scope_case_identity_required")
        if (
            self.binding_state == "case_and_source_bound"
            and not self.source_owner_ticker
        ):
            raise ValueError("artifact_scope_source_owner_required")
        return self


class ArtifactRef(_FrozenModel):
    artifact_type: ArtifactType
    artifact_id: str
    artifact_version: str
    payload_sha256: str
    relation: Literal["derived_from", "bound_to", "consumes", "projects"]

    @field_validator("artifact_id", "artifact_version")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("artifact_ref_identifier_invalid")
        return value

    @field_validator("payload_sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("artifact_ref_digest_invalid")
        return value


class ArtifactEnvelope(_FrozenModel):
    schema_version: Literal["fin_ia_s1_artifact_envelope_v1_0"]
    artifact_type: ArtifactType
    artifact_id: str
    artifact_version: str
    producer_id: str
    payload_schema_version: str
    payload_ref: str
    payload_sha256: str
    lifecycle_state: Literal["materialized", "rejected", "typed_gap"]
    scope: ArtifactScope
    parent_refs: tuple[ArtifactRef, ...] = ()
    lineage_digest: str

    @field_validator(
        "artifact_id",
        "artifact_version",
        "producer_id",
        "payload_schema_version",
    )
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("artifact_envelope_identifier_invalid")
        return value

    @field_validator("payload_sha256", "lineage_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("artifact_envelope_digest_invalid")
        return value

    @field_validator("payload_ref")
    @classmethod
    def validate_payload_ref(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        if not normalized or "\x00" in normalized:
            raise ValueError("artifact_payload_ref_invalid")
        return normalized

    @model_validator(mode="after")
    def validate_lineage_digest(self) -> "ArtifactEnvelope":
        expected = canonical_json_digest(
            [row.model_dump(mode="json") for row in self.parent_refs]
        )
        if self.lineage_digest != expected:
            raise ValueError("artifact_lineage_digest_mismatch")
        return self

    def as_ref(self, relation: str = "derived_from") -> ArtifactRef:
        return ArtifactRef(
            artifact_type=self.artifact_type,
            artifact_id=self.artifact_id,
            artifact_version=self.artifact_version,
            payload_sha256=self.payload_sha256,
            relation=relation,
        )


class ArtifactTypeRule(_FrozenModel):
    artifact_type: ArtifactType
    responsibility_axis: ResponsibilityAxis
    data_plane: Literal[
        "control",
        "source",
        "document",
        "object",
        "index",
        "query",
        "candidate",
        "evidence",
        "product",
    ]
    root_allowed: bool = False
    required_parent_types_all: tuple[ArtifactType, ...] = ()
    required_parent_type_groups_any: tuple[tuple[ArtifactType, ...], ...] = ()


class ArtifactSpinePolicy(_FrozenModel):
    schema_version: Literal["fin_ia_s1_artifact_spine_policy_v1_0"]
    status: Literal["canonical_control_plane_contract"]
    policy_id: str
    policy_version: str
    principles: Mapping[str, bool]
    artifact_types: tuple[ArtifactTypeRule, ...]

    @model_validator(mode="after")
    def validate_rules(self) -> "ArtifactSpinePolicy":
        names = [row.artifact_type for row in self.artifact_types]
        if len(names) != len(set(names)):
            raise ValueError("artifact_spine_rule_duplicate")
        expected = set(ArtifactType.__args__)
        if set(names) != expected:
            raise ValueError("artifact_spine_rule_coverage_invalid")
        required_principles = {
            "control_plane_not_single_physical_pipeline",
            "parallel_data_planes_preserved",
            "payloads_content_addressed",
            "identity_period_locator_and_lineage_fail_closed",
            "candidate_is_not_evidence",
            "numeric_fact_authority_remains_s2",
            "workbench_is_permanent_consumer",
        }
        if not required_principles.issubset(self.principles) or not all(
            self.principles[key] for key in required_principles
        ):
            raise ValueError("artifact_spine_principles_invalid")
        return self

    def rules_by_type(self) -> dict[str, ArtifactTypeRule]:
        return {row.artifact_type: row for row in self.artifact_types}


class CoverageGap(_FrozenModel):
    gap_id: str
    business_effect_zh: str = Field(min_length=1)
    earliest_responsibility_axis: ResponsibilityAxis
    next_vertical_slice: Literal["VS1", "VS2", "VS3", "VS4", "VS5"]


class CoverageRow(_FrozenModel):
    responsibility_axis: ResponsibilityAxis
    name_zh: str
    canonical_artifact_types: tuple[ArtifactType, ...]
    producer_refs: tuple[str, ...]
    consumer_refs: tuple[str, ...]
    current_artifact_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    highest_proven_state: DeliveryState
    proven_scope_zh: tuple[str, ...]
    qualification_state: Literal["open", "qualified"]
    known_gaps: tuple[CoverageGap, ...]
    migration_or_rollback_entry_refs: tuple[str, ...]


class ImplementationCoverageMatrix(_FrozenModel):
    schema_version: Literal["fin_ia_s1_implementation_coverage_matrix_v1_0"]
    status: Literal["current_implementation_evidence_backed_snapshot"]
    matrix_id: str
    audited_git_commit: str
    recorded_at: str
    policy: Mapping[str, bool]
    rows: tuple[CoverageRow, ...]

    @model_validator(mode="after")
    def validate_matrix_shape(self) -> "ImplementationCoverageMatrix":
        axes = [row.responsibility_axis for row in self.rows]
        if set(axes) != set(ResponsibilityAxis.__args__) or len(axes) != 10:
            raise ValueError("coverage_matrix_axes_invalid")
        if any(
            row.highest_proven_state == "S1_qualified_stable"
            and row.qualification_state != "qualified"
            for row in self.rows
        ):
            raise ValueError("coverage_matrix_qualification_state_invalid")
        if not self.policy.get("evidence_refs_required", False):
            raise ValueError("coverage_matrix_evidence_policy_missing")
        return self


def load_artifact_spine_policy(path: Path) -> ArtifactSpinePolicy:
    return ArtifactSpinePolicy.model_validate_json(path.read_text(encoding="utf-8"))


def load_implementation_coverage_matrix(path: Path) -> ImplementationCoverageMatrix:
    return ImplementationCoverageMatrix.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def build_artifact_envelope(
    *,
    artifact_type: ArtifactType,
    artifact_version: str,
    producer_id: str,
    payload_schema_version: str,
    payload_ref: str,
    payload_sha256: str,
    lifecycle_state: Literal["materialized", "rejected", "typed_gap"],
    scope: ArtifactScope,
    parent_refs: Sequence[ArtifactRef] = (),
) -> ArtifactEnvelope:
    parents = tuple(parent_refs)
    identity = {
        "artifact_type": artifact_type,
        "artifact_version": artifact_version,
        "payload_sha256": payload_sha256,
        "scope": scope.model_dump(mode="json"),
        "parent_refs": [row.model_dump(mode="json") for row in parents],
    }
    artifact_id = f"FIN-S1::{artifact_type.upper()}::{canonical_json_digest(identity)[:24]}"
    return ArtifactEnvelope(
        schema_version=ARTIFACT_ENVELOPE_SCHEMA_VERSION,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        artifact_version=artifact_version,
        producer_id=producer_id,
        payload_schema_version=payload_schema_version,
        payload_ref=payload_ref,
        payload_sha256=payload_sha256,
        lifecycle_state=lifecycle_state,
        scope=scope,
        parent_refs=parents,
        lineage_digest=canonical_json_digest(
            [row.model_dump(mode="json") for row in parents]
        ),
    )


def validate_artifact_chain(
    envelopes: Sequence[ArtifactEnvelope],
    policy: ArtifactSpinePolicy,
) -> None:
    by_id: dict[str, ArtifactEnvelope] = {}
    for envelope in envelopes:
        if envelope.artifact_id in by_id:
            raise ArtifactSpineError("artifact_chain_duplicate_id")
        by_id[envelope.artifact_id] = envelope

    rules = policy.rules_by_type()
    graph: dict[str, set[str]] = defaultdict(set)
    for envelope in envelopes:
        rule = rules[envelope.artifact_type]
        direct_parent_types: set[str] = set()
        for parent_ref in envelope.parent_refs:
            parent = by_id.get(parent_ref.artifact_id)
            if parent is None:
                raise ArtifactSpineError("artifact_chain_parent_missing")
            if (
                parent.artifact_type != parent_ref.artifact_type
                or parent.artifact_version != parent_ref.artifact_version
                or parent.payload_sha256 != parent_ref.payload_sha256
            ):
                raise ArtifactSpineError("artifact_chain_parent_ref_drift")
            direct_parent_types.add(parent.artifact_type)
            graph[envelope.artifact_id].add(parent.artifact_id)
            _validate_scope_seam(parent, envelope)

        if not envelope.parent_refs and not rule.root_allowed:
            raise ArtifactSpineError("artifact_chain_root_forbidden")
        if not set(rule.required_parent_types_all).issubset(direct_parent_types):
            raise ArtifactSpineError("artifact_chain_required_parent_missing")
        for group in rule.required_parent_type_groups_any:
            if not direct_parent_types.intersection(group):
                raise ArtifactSpineError("artifact_chain_parent_group_missing")

    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(artifact_id: str) -> None:
        if artifact_id in visiting:
            raise ArtifactSpineError("artifact_chain_cycle")
        if artifact_id in visited:
            return
        visiting.add(artifact_id)
        for parent_id in graph.get(artifact_id, set()):
            walk(parent_id)
        visiting.remove(artifact_id)
        visited.add(artifact_id)

    for artifact_id in by_id:
        walk(artifact_id)


def validate_inline_payload_refs(
    result: Mapping[str, Any],
    envelopes: Sequence[ArtifactEnvelope],
    *,
    resource_id: str,
) -> None:
    """Require every result-local envelope ref to resolve and match its digest.

    A lineage graph can be structurally valid while an inline ``payload_ref``
    points at a JSON path that was never materialized. That produces an
    apparently complete Workbench projection but leaves no auditable payload
    for replay or a successor. External file references remain the owning
    adapter's responsibility; this check is intentionally scoped to one result.
    """

    prefix = f"{resource_id}#"
    for envelope in envelopes:
        if not envelope.payload_ref.startswith(prefix):
            continue
        pointer = envelope.payload_ref[len(prefix) :]
        if not pointer.startswith("/"):
            raise ArtifactSpineError("artifact_inline_payload_pointer_invalid")
        current: Any = result
        for raw_part in pointer[1:].split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, Mapping) and part in current:
                current = current[part]
                continue
            if isinstance(current, Sequence) and not isinstance(
                current, (str, bytes, bytearray)
            ):
                try:
                    current = current[int(part)]
                    continue
                except (ValueError, IndexError):
                    pass
            raise ArtifactSpineError(
                f"artifact_inline_payload_missing:{envelope.artifact_type}"
            )
        if canonical_json_digest(current) != envelope.payload_sha256:
            raise ArtifactSpineError(
                f"artifact_inline_payload_digest_mismatch:{envelope.artifact_type}"
            )


def validate_coverage_matrix(
    *,
    repo_root: Path,
    matrix: ImplementationCoverageMatrix,
    policy: ArtifactSpinePolicy,
) -> None:
    rules = policy.rules_by_type()
    for row in matrix.rows:
        for artifact_type in row.canonical_artifact_types:
            if rules[artifact_type].responsibility_axis != row.responsibility_axis:
                raise ArtifactSpineError("coverage_matrix_artifact_owner_drift")
        refs = (
            *row.producer_refs,
            *row.consumer_refs,
            *row.current_artifact_refs,
            *row.test_refs,
            *row.migration_or_rollback_entry_refs,
        )
        if not row.producer_refs or not row.test_refs:
            raise ArtifactSpineError("coverage_matrix_evidence_refs_missing")
        for ref in refs:
            normalized = ref.replace("\\", "/")
            if normalized.startswith("archive/") or not (repo_root / normalized).is_file():
                raise ArtifactSpineError(
                    f"coverage_matrix_repo_ref_invalid:{normalized}"
                )


def _validate_scope_seam(parent: ArtifactEnvelope, child: ArtifactEnvelope) -> None:
    if (
        parent.scope.case_key
        and child.scope.case_key
        and parent.scope.case_key != child.scope.case_key
    ):
        raise ArtifactSpineError("artifact_chain_case_scope_drift")
    if (
        parent.scope.research_as_of
        and child.scope.research_as_of
        and parent.scope.research_as_of != child.scope.research_as_of
    ):
        raise ArtifactSpineError("artifact_chain_as_of_scope_drift")


__all__ = [
    "ARTIFACT_ENVELOPE_SCHEMA_VERSION",
    "ARTIFACT_SPINE_POLICY_SCHEMA_VERSION",
    "COVERAGE_MATRIX_SCHEMA_VERSION",
    "ArtifactEnvelope",
    "ArtifactRef",
    "ArtifactScope",
    "ArtifactSpineError",
    "ArtifactSpinePolicy",
    "ImplementationCoverageMatrix",
    "ReportingPeriodBinding",
    "SourceLocatorBinding",
    "build_artifact_envelope",
    "canonical_json_digest",
    "load_artifact_spine_policy",
    "load_implementation_coverage_matrix",
    "sha256_file",
    "validate_artifact_chain",
    "validate_inline_payload_refs",
    "validate_coverage_matrix",
]
