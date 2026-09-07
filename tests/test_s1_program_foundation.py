from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from retrieval.artifact_spine import (
    ArtifactScope,
    ArtifactSpineError,
    ReportingPeriodBinding,
    build_artifact_envelope,
    load_artifact_spine_policy,
    load_implementation_coverage_matrix,
    validate_artifact_chain,
    validate_coverage_matrix,
)
from retrieval.evaluation_assets import (
    EvaluationInput,
    EvaluationProgramManifest,
    EvaluationReference,
    QualificationExecutionBinding,
    QualificationPreRegistration,
    load_evaluation_program_manifest,
    validate_evaluation_program,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_canonical_artifact_spine_policy_v1_0.json"
)
MATRIX = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_implementation_coverage_matrix_v1_0.json"
)
PROGRAM = ROOT / "eval_sets/fin_0_1_3_s1/program_manifest_v1_0.json"
PREREGISTRATION = (
    ROOT / "eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json"
)


def test_canonical_spine_policy_and_coverage_matrix_are_complete() -> None:
    policy = load_artifact_spine_policy(POLICY)
    matrix = load_implementation_coverage_matrix(MATRIX)

    validate_coverage_matrix(repo_root=ROOT, matrix=matrix, policy=policy)

    assert len(policy.artifact_types) == 16
    assert [row.responsibility_axis for row in matrix.rows] == [
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
    assert sum(len(row.known_gaps) for row in matrix.rows) == 20
    assert all(row.qualification_state == "open" for row in matrix.rows)
    assert all(row.highest_proven_state != "S1_qualified_stable" for row in matrix.rows)


def test_representative_two_root_spine_reaches_product_consumer() -> None:
    policy = load_artifact_spine_policy(POLICY)
    source_scope = ArtifactScope(
        binding_state="source_only",
        source_owner_ticker="DELL",
        discussed_entity_tickers=("DELL",),
    )
    case_scope = ArtifactScope(
        binding_state="case_bound",
        case_key="DELL",
        subject_ticker="DELL",
        discussed_entity_tickers=("DELL",),
        research_as_of="2026-08-06",
    )
    rows = []

    def add(
        artifact_type: str,
        scope: ArtifactScope,
        parents: tuple = (),
    ):
        row = build_artifact_envelope(
            artifact_type=artifact_type,
            artifact_version="v1.0",
            producer_id=f"test.{artifact_type}",
            payload_schema_version=f"fixture_{artifact_type}_v1_0",
            payload_ref=f"fixture://{artifact_type}",
            payload_sha256=(f"{len(rows) + 1:064x}"[-64:]),
            lifecycle_state="materialized",
            scope=scope,
            parent_refs=parents,
        )
        rows.append(row)
        return row

    route = add("source_route_decision", source_scope)
    capture = add("raw_source_capture", source_scope, (route.as_ref(),))
    parsed = add("parsed_document", source_scope, (capture.as_ref(),))
    obj = add("financial_evidence_object", source_scope, (parsed.as_ref(),))
    manifest = add("object_manifest", source_scope, (obj.as_ref(),))
    index = add("index_snapshot", source_scope, (manifest.as_ref(),))
    request = add("evidence_request", case_scope)
    query = add("query_facet_plan", case_scope, (request.as_ref(),))
    candidates = add(
        "candidate_set",
        case_scope,
        (query.as_ref(relation="consumes"), index.as_ref(relation="consumes")),
    )
    ranking = add("candidate_ranking", case_scope, (candidates.as_ref(),))
    decision = add("candidate_decision", case_scope, (ranking.as_ref(),))
    coverage = add(
        "evidence_coverage_state",
        case_scope,
        (request.as_ref(relation="bound_to"), decision.as_ref()),
    )
    pack = add("evidence_pack_readiness", case_scope, (coverage.as_ref(),))
    add("workbench_projection", case_scope, (pack.as_ref(relation="projects"),))
    add("frozen_consumer_probe", case_scope, (pack.as_ref(relation="consumes"),))

    validate_artifact_chain(rows, policy)


def test_candidate_decision_cannot_skip_ranking_seam() -> None:
    policy = load_artifact_spine_policy(POLICY)
    scope = ArtifactScope(
        binding_state="case_bound",
        case_key="DELL",
        subject_ticker="DELL",
        research_as_of="2026-08-06",
    )
    request = build_artifact_envelope(
        artifact_type="evidence_request",
        artifact_version="v1.0",
        producer_id="test.request",
        payload_schema_version="fixture_request_v1_0",
        payload_ref="fixture://request",
        payload_sha256="1" * 64,
        lifecycle_state="materialized",
        scope=scope,
    )
    decision = build_artifact_envelope(
        artifact_type="candidate_decision",
        artifact_version="v1.0",
        producer_id="test.decision",
        payload_schema_version="fixture_decision_v1_0",
        payload_ref="fixture://decision",
        payload_sha256="2" * 64,
        lifecycle_state="materialized",
        scope=scope,
        parent_refs=(request.as_ref(),),
    )

    with pytest.raises(
        ArtifactSpineError, match="artifact_chain_required_parent_missing"
    ):
        validate_artifact_chain((request, decision), policy)


@pytest.mark.parametrize(
    "invalid_as_of",
    ("2026/08/06", "2026-02-30", "20260806"),
)
def test_artifact_scope_rejects_non_iso_or_impossible_dates(
    invalid_as_of: str,
) -> None:
    with pytest.raises(ValidationError, match="artifact_scope_as_of_invalid"):
        ArtifactScope(
            binding_state="case_bound",
            case_key="DELL",
            subject_ticker="DELL",
            research_as_of=invalid_as_of,
        )


def test_reporting_period_rejects_reversed_range() -> None:
    with pytest.raises(
        ValidationError, match="artifact_reporting_period_range_invalid"
    ):
        ReportingPeriodBinding(
            start_date="2026-08-01",
            end_date="2026-07-31",
        )


def test_eval_program_keeps_inputs_and_labels_physically_separate() -> None:
    manifest = load_evaluation_program_manifest(PROGRAM)
    result = validate_evaluation_program(repo_root=ROOT, manifest=manifest)

    assert result == {
        "active_catalog_count": 5,
        "reserved_catalog_count": 0,
        "example_count": 39,
        "qualification_preregistered_case_count": 6,
        "qualification_execution_binding_count": 1,
        "qualification_ready": False,
    }
    train = next(row for row in manifest.catalogs if row.split == "train_internal")
    assert train.input_asset is not None
    assert train.reference_asset is not None
    assert train.input_asset.ref != train.reference_asset.ref
    assert train.input_asset.visibility == "runtime_visible"
    assert train.reference_asset.visibility == "evaluator_only"


def test_runtime_visible_eval_input_rejects_embedded_gold() -> None:
    valid = {
        "schema_version": "fin_ia_s1_evaluation_input_v1_0",
        "example_id": "leak-test",
        "split": "train_internal",
        "responsibility_axes": ["S1-H"],
        "vertical_slices": ["VS1"],
        "evaluation_unit": "evidence_admission",
        "case_role": "development",
        "source_fixture_refs": ["fixture://candidate"],
        "runtime_input": {"candidate": {"text": "generic text"}},
    }
    EvaluationInput.model_validate(valid)
    valid["runtime_input"]["candidate"]["relevance_grade"] = 3

    with pytest.raises(ValidationError, match="evaluation_runtime_label_leak"):
        EvaluationInput.model_validate(valid)


def test_vs5_preregistration_is_unseen_split_complete_and_cuda_only() -> None:
    value = QualificationPreRegistration.model_validate_json(
        PREREGISTRATION.read_text(encoding="utf-8")
    )

    assert {row.split for row in value.cases} == {
        "valid_temporal",
        "test_frozen",
        "holdout_heterogeneous",
    }
    assert not (set(value.observed_case_keys) & {row.case_key for row in value.cases})
    assert value.execution_policy.learned_vector_device_required == "cuda"
    assert value.execution_policy.learned_vector_precision == "fp16"
    assert value.execution_policy.cpu_vector_fallback_allowed is False
    assert value.execution_policy.test_frozen_max_executions == 1
    assert value.execution_policy.holdout_heterogeneous_max_executions == 1
    assert value.metric_contract.natural_scanned_official_source_required is True
    assert value.metric_contract.averages_cannot_compensate_hard_gates is True


def test_checked_in_json_schemas_match_current_models() -> None:
    expected = {
        "artifact_envelope.schema.json": __import__(
            "retrieval.artifact_spine", fromlist=["ArtifactEnvelope"]
        ).ArtifactEnvelope.model_json_schema(),
        "evaluation_input.schema.json": EvaluationInput.model_json_schema(),
        "evaluation_reference.schema.json": EvaluationReference.model_json_schema(),
        "evaluation_program_manifest.schema.json": (
            EvaluationProgramManifest.model_json_schema()
        ),
        "qualification_preregistration.schema.json": (
            QualificationPreRegistration.model_json_schema()
        ),
        "qualification_execution_binding.schema.json": (
            QualificationExecutionBinding.model_json_schema()
        ),
    }
    schema_root = ROOT / "eval_sets/fin_0_1_3_s1/schemas"
    for filename, schema in expected.items():
        assert json.loads((schema_root / filename).read_text(encoding="utf-8")) == schema
