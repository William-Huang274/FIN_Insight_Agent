from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .artifact_spine import sha256_file


EVALUATION_INPUT_SCHEMA_VERSION = "fin_ia_s1_evaluation_input_v1_0"
EVALUATION_REFERENCE_SCHEMA_VERSION = "fin_ia_s1_evaluation_reference_v1_0"
EVALUATION_PROGRAM_SCHEMA_VERSION = "fin_ia_s1_evaluation_program_v1_0"

SplitName = Literal[
    "train_internal",
    "valid_temporal",
    "test_frozen",
    "holdout_heterogeneous",
]

_FORBIDDEN_RUNTIME_KEYS = frozenset(
    {
        "answer_key",
        "expected",
        "expected_artifact_ids",
        "expected_outcome",
        "gold",
        "gold_label",
        "hard_negative",
        "label",
        "qrel_id",
        "reason_code",
        "reference_answer",
        "relevance_grade",
        "target_source_record_ids",
    }
)


class EvaluationAssetError(ValueError):
    """Raised when eval labels can leak or a split cannot be reproduced."""


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationAssetRef(_FrozenModel):
    ref: str
    sha256: str
    role: Literal[
        "runtime_input",
        "evaluator_reference",
        "legacy_development_asset",
        "source_fixture",
        "schema",
    ]
    visibility: Literal["runtime_visible", "evaluator_only", "governance_only"]

    @field_validator("ref")
    @classmethod
    def validate_ref(cls, value: str) -> str:
        normalized = value.strip().replace("\\", "/")
        if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
            raise ValueError("evaluation_asset_ref_invalid")
        return normalized

    @field_validator("sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("evaluation_asset_digest_invalid")
        return value


class EvaluationInput(_FrozenModel):
    schema_version: Literal["fin_ia_s1_evaluation_input_v1_0"]
    example_id: str
    split: SplitName
    responsibility_axes: tuple[
        Literal[
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
        ],
        ...,
    ]
    vertical_slices: tuple[Literal["VS1", "VS2", "VS3", "VS4", "VS5"], ...]
    evaluation_unit: Literal[
        "artifact_contract",
        "seam",
        "candidate_quality",
        "evidence_admission",
        "coverage_or_gap",
        "consumer_projection",
        "mutation",
    ]
    case_role: Literal[
        "development",
        "regression",
        "temporal_validation",
        "frozen_test",
        "heterogeneous_holdout",
    ]
    source_fixture_refs: tuple[str, ...]
    runtime_input: Mapping[str, Any]

    @model_validator(mode="after")
    def prevent_label_leakage(self) -> "EvaluationInput":
        leaks = sorted(_find_forbidden_keys(self.runtime_input))
        if leaks:
            raise ValueError(f"evaluation_runtime_label_leak:{','.join(leaks)}")
        if self.split in {"test_frozen", "holdout_heterogeneous"} and self.case_role in {
            "development",
            "regression",
        }:
            raise ValueError("evaluation_hidden_split_case_role_invalid")
        return self


class EvaluationReference(_FrozenModel):
    schema_version: Literal["fin_ia_s1_evaluation_reference_v1_0"]
    example_id: str
    split: SplitName
    label_type: Literal[
        "accept",
        "reject",
        "abstain",
        "typed_gap",
        "typed_failure",
        "exact_binding",
        "ordered_candidates",
    ]
    expected_outcome: Mapping[str, Any]
    hard_gate: bool
    rationale_zh: str = Field(min_length=1)
    adjudication_authority: str = Field(min_length=1)
    review_state: Literal[
        "development_reviewed",
        "owner_reviewed",
        "qualification_blinded",
    ]


class EvaluationCatalog(_FrozenModel):
    catalog_id: str
    split: SplitName
    status: Literal["active", "reserved_unpopulated", "retired"]
    input_asset: EvaluationAssetRef | None = None
    reference_asset: EvaluationAssetRef | None = None
    example_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_catalog_state(self) -> "EvaluationCatalog":
        if self.status == "active":
            if not self.input_asset or not self.reference_asset or self.example_count < 1:
                raise ValueError("evaluation_active_catalog_incomplete")
            if self.input_asset.ref == self.reference_asset.ref:
                raise ValueError("evaluation_inputs_and_references_not_separated")
            if self.input_asset.visibility != "runtime_visible":
                raise ValueError("evaluation_input_visibility_invalid")
            if self.reference_asset.visibility != "evaluator_only":
                raise ValueError("evaluation_reference_visibility_invalid")
        elif self.input_asset or self.reference_asset or self.example_count:
            raise ValueError("evaluation_reserved_catalog_must_be_empty")
        return self


class SplitPolicy(_FrozenModel):
    split: SplitName
    status: Literal["active", "reserved_unpopulated"]
    allowed_uses: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    observed_case_keys: tuple[str, ...]
    configuration_frozen_before_execution: bool


class EvaluationProgramManifest(_FrozenModel):
    schema_version: Literal["fin_ia_s1_evaluation_program_v1_0"]
    status: Literal["split_safe_foundation_ready_not_qualified"]
    program_id: str
    program_version: str
    recorded_at: str
    policies: Mapping[str, bool]
    schemas: tuple[EvaluationAssetRef, ...]
    split_policies: tuple[SplitPolicy, ...]
    catalogs: tuple[EvaluationCatalog, ...]
    legacy_development_assets: tuple[EvaluationAssetRef, ...]
    final_threshold_state: Literal[
        "schema_and_non_compensable_gates_frozen_performance_thresholds_open"
    ]

    @model_validator(mode="after")
    def validate_program(self) -> "EvaluationProgramManifest":
        splits = [row.split for row in self.split_policies]
        if set(splits) != set(SplitName.__args__) or len(splits) != 4:
            raise ValueError("evaluation_split_policy_coverage_invalid")
        catalog_splits = [row.split for row in self.catalogs]
        if set(catalog_splits) != set(SplitName.__args__) or len(catalog_splits) != 4:
            raise ValueError("evaluation_catalog_split_coverage_invalid")
        required = {
            "runtime_inputs_physically_separate_from_references",
            "labels_joined_only_inside_evaluator",
            "observed_cases_not_hidden_qualification",
            "test_snapshot_immutable_after_first_execution",
            "model_generated_examples_not_final_gold",
            "average_score_cannot_compensate_hard_gate",
        }
        if not required.issubset(self.policies) or not all(
            self.policies[key] for key in required
        ):
            raise ValueError("evaluation_program_policy_invalid")
        return self


def load_evaluation_program_manifest(path: Path) -> EvaluationProgramManifest:
    return EvaluationProgramManifest.model_validate_json(path.read_text(encoding="utf-8"))


def validate_evaluation_program(
    *, repo_root: Path, manifest: EvaluationProgramManifest
) -> dict[str, Any]:
    split_policies = {row.split: row for row in manifest.split_policies}
    total_examples = 0
    for asset in (*manifest.schemas, *manifest.legacy_development_assets):
        _validate_bound_asset(repo_root, asset)

    for catalog in manifest.catalogs:
        policy = split_policies[catalog.split]
        if catalog.status == "reserved_unpopulated":
            if policy.status != "reserved_unpopulated":
                raise EvaluationAssetError("evaluation_reserved_split_policy_drift")
            continue
        if policy.status != "active":
            raise EvaluationAssetError("evaluation_active_split_policy_drift")
        assert catalog.input_asset is not None
        assert catalog.reference_asset is not None
        input_path = _validate_bound_asset(repo_root, catalog.input_asset)
        reference_path = _validate_bound_asset(repo_root, catalog.reference_asset)
        inputs = _read_jsonl(input_path, EvaluationInput)
        references = _read_jsonl(reference_path, EvaluationReference)
        if len(inputs) != catalog.example_count or len(references) != catalog.example_count:
            raise EvaluationAssetError("evaluation_catalog_example_count_drift")
        input_ids = {row.example_id for row in inputs}
        reference_ids = {row.example_id for row in references}
        if len(input_ids) != len(inputs) or len(reference_ids) != len(references):
            raise EvaluationAssetError("evaluation_example_id_duplicate")
        if input_ids != reference_ids:
            raise EvaluationAssetError("evaluation_input_reference_join_invalid")
        if any(row.split != catalog.split for row in (*inputs, *references)):
            raise EvaluationAssetError("evaluation_catalog_split_drift")
        total_examples += catalog.example_count
    return {
        "active_catalog_count": sum(
            row.status == "active" for row in manifest.catalogs
        ),
        "reserved_catalog_count": sum(
            row.status == "reserved_unpopulated" for row in manifest.catalogs
        ),
        "example_count": total_examples,
        "qualification_ready": False,
    }


def _validate_bound_asset(repo_root: Path, asset: EvaluationAssetRef) -> Path:
    path = repo_root / asset.ref
    if not path.is_file():
        raise EvaluationAssetError(f"evaluation_asset_missing:{asset.ref}")
    if sha256_file(path) != asset.sha256:
        raise EvaluationAssetError(f"evaluation_asset_digest_drift:{asset.ref}")
    return path


def _read_jsonl(path: Path, model: type[_FrozenModel]) -> list[Any]:
    rows: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(model.model_validate_json(line))
        except ValueError as exc:
            raise EvaluationAssetError(
                f"evaluation_jsonl_invalid:{path.as_posix()}:{line_number}"
            ) from exc
    return rows


def _find_forbidden_keys(value: Any, prefix: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if key.casefold() in _FORBIDDEN_RUNTIME_KEYS:
                found.add(path)
            found.update(_find_forbidden_keys(child, path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.update(_find_forbidden_keys(child, f"{prefix}[{index}]"))
    return found


__all__ = [
    "EVALUATION_INPUT_SCHEMA_VERSION",
    "EVALUATION_PROGRAM_SCHEMA_VERSION",
    "EVALUATION_REFERENCE_SCHEMA_VERSION",
    "EvaluationAssetError",
    "EvaluationInput",
    "EvaluationProgramManifest",
    "EvaluationReference",
    "load_evaluation_program_manifest",
    "validate_evaluation_program",
]
