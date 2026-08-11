from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "engineering"))

import run_point01_m6_3r_2_local_retrieval_fixture_gate as runner
from sec_agent.canonical_runtime.local_retrieval_fixture import (
    FixtureNeighborReference,
    LocalRetrievalFixtureEvaluation,
    LocalRetrievalFixtureHarness,
)
from sec_agent.canonical_runtime.local_retrieval_fixture_oracle import FixtureOracleRecord, LocalRetrievalFixtureOracle
from sec_agent.canonical_runtime.local_retrieval_skeleton import ExactValueSqlBindingCompiler, ExactValueSqlBindingPolicy, ExactValueSqlMetricBinding, ExactValueSqlUnitScaleBinding
from sec_agent.canonical_runtime.models import canonical_digest


MODULE = ROOT / "src/sec_agent/canonical_runtime/local_retrieval_fixture.py"
ORACLE_MODULE = ROOT / "src/sec_agent/canonical_runtime/local_retrieval_fixture_oracle.py"
GATE = ROOT / "scripts/engineering/run_point01_m6_3r_2_local_retrieval_fixture_gate.py"
SQL_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_1_exact_value_sql_binding_policy_v1_0.json"
FIXTURE_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_2_fixture_admission_policy_v1_0.json"
FIXTURE_MANIFEST_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_2_fixture_test_manifest_v1_0.json"
OWNER_MAPPING_PATH = ROOT / "configs/engineering_handoff/point01_m6_3r_2_fixture_api_owner_mapping_v1_0.json"


def _harness() -> LocalRetrievalFixtureHarness:
    return LocalRetrievalFixtureHarness(
        admission_policy=runner._fixture_policy(),
        pinned_sql_policy=runner._sql_policy(),
        pinned_sql_policy_raw_sha256=hashlib.sha256(SQL_POLICY_PATH.read_bytes()).hexdigest(),
    )


def _entry(corpus: object, fixture_id: str):
    return next(item for item in corpus.entries if item.fixture_id == fixture_id)  # type: ignore[attr-defined]


def test_sanitized_fixture_corpus_oracle_and_matrix_cover_all_authorized_metadata_shapes() -> None:
    result, corpus = runner.build_result()
    oracle = runner.build_oracle(corpus)
    assert result["status"] == "pass"
    assert result["corpus_digest"] == oracle.corpus_digest
    assert result["oracle_digest"] == oracle.oracle_digest
    assert {entry.query.adapter_snapshot.adapter_kind for entry in corpus.entries} == {"bm25", "object_bm25", "relationship_graph", "exact_value_sql"}
    assert result["matrix_coverage"]["evaluations_by_status"] == {"accepted_fixture_projection": 5, "not_fixture_admitted": 1, "typed_exhaustion": 3}
    assert result["matrix_coverage"]["positive_fixture_count"] == 5
    assert result["matrix_coverage"]["negative_fixture_count"] == 4
    assert result["matrix_coverage"]["typed_exhaustion_fixture_count"] == 3
    assert result["matrix_coverage"]["topk_terminal_cases"] == {"commercial_1_1": "typed_commercial_gap"}
    assert {"next_section", "next_page", "next_row", "table"} <= set(result["matrix_coverage"]["neighbor_relations"])
    assert result["matrix_coverage"]["diversity_applicable_fixture_count"] >= 1
    assert result["matrix_coverage"]["rerank_to_gate_set_preserved_fixture_count"] == 5
    assert all(entry.fixture_provenance == "sanitized_immutable_fixture_only" for entry in corpus.entries)


def test_exact_sql_fixture_is_pinned_to_reviewed_policy_and_alternate_self_signed_policy_is_not_admitted() -> None:
    result, corpus = runner.build_result()
    fixture_policy = json.loads(FIXTURE_POLICY_PATH.read_text(encoding="utf-8"))
    assert result["pinned_sql_policy"] == fixture_policy["sql_fixture_policy_pin"]
    assert result["pinned_sql_policy"]["policy_canonical_digest"] == "75fff84e1d4684aa47eb7b6dc9d2cef2ff50333f27bbce8e3cda17d5a6ef820f"
    assert result["checks"]["alternate_self_signed_policy_is_not_fixture_admitted"] is True

    exact_entry = _entry(corpus, "fixture-exact-value-sql-row-positive")
    scope = exact_entry.query.exact_value_execution_scope
    assert scope is not None
    self_signed = ExactValueSqlBindingPolicy.create(
        policy_ref="self-signed-fixture-policy",
        policy_version="v1",
        compiler_policy_ref="point01-m6-1-evidence-request-policy-v1",
        accepted_evidence_role="numeric_fact",
        source_policy="official_first",
        selected_route_id="issuer_disclosure_metadata_route",
        row_selector_ref="row:self-signed",
        form_type="10-K",
        source_tier="primary_sec",
        metric_bindings=(ExactValueSqlMetricBinding(metric_intent="revenue", metric_ref="self-signed:Revenue"),),
        unit_scale_bindings=(ExactValueSqlUnitScaleBinding(request_unit="USD_millions", unit_ref="USD", scale_ref="millions"),),
    )
    assert ExactValueSqlBindingCompiler().compile(
        evidence_request=scope.evidence_request,
        tool_selection_plan=scope.tool_selection_plan,
        adapter_snapshot=scope.adapter_snapshot,
        binding_policy=self_signed,
    ).status == "resolved"
    assert LocalRetrievalFixtureHarness(
        admission_policy=runner._fixture_policy(),
        pinned_sql_policy=self_signed,
        pinned_sql_policy_raw_sha256=canonical_digest({"self_signed": "raw"}),
    ).evaluate(entry=exact_entry).status == "not_fixture_admitted"


def test_fixture_manifest_and_owner_mapping_preserve_r2_only_boundary() -> None:
    manifest = json.loads(FIXTURE_MANIFEST_PATH.read_text(encoding="utf-8"))
    owner_mapping = json.loads(OWNER_MAPPING_PATH.read_text(encoding="utf-8"))
    assert manifest["execution_stage"] == "fixture_repaired_pending_total_reviewer_audit"
    assert manifest["pinned_sql_policy"]["canonical_digest"] == "75fff84e1d4684aa47eb7b6dc9d2cef2ff50333f27bbce8e3cda17d5a6ef820f"
    assert "independent oracle artifact" in manifest["required_matrix"]
    assert "rerank-to-Gate set preservation" in manifest["required_matrix"]
    assert owner_mapping["residual_risk"].startswith("A self-signed")
    assert "M6.3R.3 execution" in owner_mapping["prohibitions"]


def test_oracle_mutation_cannot_change_actual_evaluation() -> None:
    _, corpus = runner.build_result()
    entry = _entry(corpus, "fixture-typed-empty-exhaustion")
    actual_before = _harness().evaluate(entry=entry)
    oracle = runner.build_oracle(corpus)
    altered_records = tuple(
        record.model_copy(update={"required_reason_codes": ("attacker_supplied_reason",)}) if record.fixture_id == entry.fixture_id else record
        for record in oracle.records
    )
    altered_oracle = LocalRetrievalFixtureOracle.create(corpus=corpus, records=altered_records)
    actual_after = _harness().evaluate(entry=entry)
    assert actual_before.evaluation_digest == actual_after.evaluation_digest
    assert actual_after.reasons == ("retrieval_exhausted_no_metadata_match",)
    checks = altered_oracle.verify(corpus=corpus, evaluations=(actual_after, *tuple(_harness().evaluate(entry=item) for item in corpus.entries if item.fixture_id != entry.fixture_id)))
    assert checks["oracle_required_reason_codes_match_actual"] is False


def test_metadata_filter_duplicate_caps_and_family_diversity_use_eligible_pool_first_pass() -> None:
    _, corpus = runner.build_result()
    entry = _entry(corpus, "fixture-bm25-narrative-positive")
    evaluation = _harness().evaluate(entry=entry)
    assert evaluation.status == "accepted_fixture_projection"
    reasons = {(outcome.candidate_id, outcome.reason) for outcome in evaluation.candidate_outcomes}
    assert ("bm25-narrative-wrong-entity", "metadata_scope_or_lineage_mismatch") in reasons
    assert ("bm25-narrative-duplicate-content", "identical_content_duplicate_cap") in reasons
    assert ("bm25-narrative-source-artifact-cap", "source_artifact_duplicate_cap") in reasons
    assert evaluation.diversity_decision is not None
    assert evaluation.diversity_decision.diversity_applicable is True
    assert evaluation.diversity_decision.selection_policy == "first_pass_per_source_family_then_ranked_fill"
    assert {candidate.source_family for candidate in evaluation.candidate_bundle_projection.candidates} == {"sec", "issuer_ir"}  # type: ignore[union-attr]

    seed = entry.candidates[0]
    sec_candidates = tuple(
        seed.model_copy(
            update={
                "candidate_id": f"sec-high-{index:02d}",
                "metadata_rank": index,
                "source_artifact_ref": f"sanitized-source:sec-high-{index}",
                "source_artifact_digest": canonical_digest({"source": f"sec-high-{index}"}),
                "content_ref": f"sanitized-content:sec-high-{index}",
                "content_digest": canonical_digest({"content": f"sec-high-{index}"}),
                "source_family": "sec",
                "recall_score": float(100 - index),
            }
        )
        for index in range(12)
    )
    issuer_candidate = seed.model_copy(
        update={
            "candidate_id": "issuer-ir-lower-score",
            "metadata_rank": 99,
            "source_artifact_ref": "sanitized-source:issuer-ir",
            "source_artifact_digest": canonical_digest({"source": "issuer-ir"}),
            "content_ref": "sanitized-content:issuer-ir",
            "content_digest": canonical_digest({"content": "issuer-ir"}),
            "source_family": "issuer_ir",
            "recall_score": -1.0,
        }
    )
    starvation_probe = entry.model_copy(update={"candidates": (*sec_candidates, issuer_candidate), "required_candidate_kinds": ("top_k_seed",), "neighbor_references": ()})
    starvation_evaluation = _harness().evaluate(entry=starvation_probe)
    assert starvation_evaluation.diversity_decision is not None
    assert starvation_evaluation.diversity_decision.diversity_applicable is True
    assert "issuer-ir-lower-score" in starvation_evaluation.diversity_decision.first_pass_candidate_ids
    assert {candidate.source_family for candidate in starvation_evaluation.candidate_bundle_projection.candidates} == {"sec", "issuer_ir"}  # type: ignore[union-attr]
    assert any(outcome.status == "capacity_rejected" for outcome in starvation_evaluation.candidate_outcomes)

    _, single_family_decision = _harness()._select_with_diversity(eligible_pool_after_duplicate_filter=sec_candidates[:2], candidate_capacity=12, outcomes=[])
    _, capacity_one_decision = _harness()._select_with_diversity(eligible_pool_after_duplicate_filter=(*sec_candidates[:1], issuer_candidate), candidate_capacity=1, outcomes=[])
    assert single_family_decision.diversity_applicable is False
    assert capacity_one_decision.diversity_applicable is False


def test_neighbor_relation_specific_coordinate_and_requiredness_are_fail_closed() -> None:
    _, corpus = runner.build_result()
    harness = _harness()
    expected_fields = {"next_section": "next_ref", "table": "section_or_table_ref", "next_page": "next_page_ref", "next_row": "next_row_ref"}
    for fixture_id in ("fixture-bm25-narrative-positive", "fixture-object-bm25-table-positive", "fixture-object-bm25-page-row-positive", "fixture-exact-value-sql-row-positive"):
        evaluation = harness.evaluate(entry=_entry(corpus, fixture_id))
        assert all(outcome.status == "validated" for outcome in evaluation.neighbor_outcomes)
        for outcome in evaluation.neighbor_outcomes:
            assert outcome.seed_coordinate_field == expected_fields[outcome.reference.relation]
            assert outcome.seed_coordinate_ref == outcome.reference.expected_coordinate_ref == outcome.neighbor_coordinate_ref
            assert outcome.lineage_match is True

    page_entry = _entry(corpus, "fixture-object-bm25-page-row-positive")
    spoofed_reference = page_entry.neighbor_references[0].model_copy(update={"relation": "previous_row"})
    spoofed_entry = page_entry.model_copy(update={"neighbor_references": (spoofed_reference, *page_entry.neighbor_references[1:])})
    spoofed_evaluation = harness.evaluate(entry=spoofed_entry)
    assert spoofed_evaluation.status == "typed_exhaustion"
    assert spoofed_evaluation.reasons[0] == "boundary_context_missing"
    assert spoofed_evaluation.candidate_bundle_projection is None

    lineage_tampered_neighbor = page_entry.candidates[1].model_copy(update={"source_artifact_digest": canonical_digest({"wrong": "neighbor-lineage"})})
    lineage_tampered_entry = page_entry.model_copy(update={"candidates": (page_entry.candidates[0], lineage_tampered_neighbor, *page_entry.candidates[2:])})
    lineage_evaluation = harness.evaluate(entry=lineage_tampered_entry)
    assert lineage_evaluation.status == "typed_exhaustion"
    assert any(outcome.reason == "fixture_neighbor_lineage_mismatch" for outcome in lineage_evaluation.neighbor_outcomes)

    optional_missing = FixtureNeighborReference(seed_candidate_id=page_entry.candidates[0].candidate_id, neighbor_candidate_id="missing", relation="next_page", expected_coordinate_ref="page:12", required=False)
    optional_entry = page_entry.model_copy(update={"neighbor_references": (optional_missing,)})
    optional_evaluation = harness.evaluate(entry=optional_entry)
    assert optional_evaluation.status == "accepted_fixture_projection"
    assert "optional_neighbor_context_missing" in optional_evaluation.reasons


def test_gate_candidate_set_is_derived_from_rerank_top_n_not_metadata_order() -> None:
    _, corpus = runner.build_result()
    entry = _entry(corpus, "fixture-bm25-narrative-positive")
    seed = entry.candidates[0]
    candidates = tuple(
        seed.model_copy(
            update={
                "candidate_id": f"rerank-rank-{index}",
                "metadata_rank": index,
                "source_artifact_ref": f"sanitized-source:rerank-{index}",
                "source_artifact_digest": canonical_digest({"source": f"rerank-{index}"}),
                "content_ref": f"sanitized-content:rerank-{index}",
                "content_digest": canonical_digest({"content": f"rerank-{index}"}),
                "recall_score": float(index),
            }
        )
        for index in range(4)
    )
    probe = entry.model_copy(update={"candidates": candidates, "required_candidate_kinds": ("top_k_seed",), "neighbor_references": ()})
    evaluation = _harness().evaluate(entry=probe)
    assert evaluation.rerank_top_candidate_ids[:3] == ("rerank-rank-3", "rerank-rank-2", "rerank-rank-1")
    assert evaluation.evidence_gate_candidate_projection is not None
    assert evaluation.evidence_gate_candidate_projection.candidate_ids == ("rerank-rank-1", "rerank-rank-2", "rerank-rank-3")
    assert set(evaluation.evidence_gate_candidate_projection.candidate_ids) == set(evaluation.rerank_top_candidate_ids[:3])
    assert evaluation.rerank_to_gate_set_preserved is True


def test_typed_exhaustion_classifier_does_not_produce_projection() -> None:
    _, corpus = runner.build_result()
    harness = _harness()
    expected = {
        "fixture-typed-empty-exhaustion": "retrieval_exhausted_no_metadata_match",
        "fixture-table-context-missing": "table_context_missing",
        "fixture-boundary-context-missing": "boundary_context_missing",
    }
    for fixture_id, reason in expected.items():
        evaluation = harness.evaluate(entry=_entry(corpus, fixture_id))
        assert evaluation.status == "typed_exhaustion"
        assert evaluation.reasons[0] == reason
        assert evaluation.candidate_bundle_projection is None
        assert evaluation.evidence_gate_candidate_projection is None


def test_over_cap_and_replay_tamper_fail_closed() -> None:
    _, corpus = runner.build_result()
    entry = _entry(corpus, "fixture-bm25-narrative-positive")
    seed = entry.candidates[0]
    candidates = tuple(
        seed.model_copy(
            update={
                "candidate_id": f"over-cap-{index:02d}",
                "metadata_rank": index,
                "source_artifact_ref": f"sanitized-source:cap-{index}",
                "source_artifact_digest": canonical_digest({"source": index}),
                "content_ref": f"sanitized-content:cap-{index}",
                "content_digest": canonical_digest({"content": index}),
            }
        )
        for index in range(13)
    )
    over_cap = entry.model_copy(update={"candidates": candidates, "neighbor_references": (), "required_candidate_kinds": ("top_k_seed",)})
    evaluation = _harness().evaluate(entry=over_cap)
    assert evaluation.status == "accepted_fixture_projection"
    assert any(outcome.reason == "candidate_bundle_capacity_rejected" for outcome in evaluation.candidate_outcomes)
    replay = evaluation.model_dump(mode="json")
    replay["reasons"] = ["forged"]
    with pytest.raises(ValidationError, match="owned_fixture_contract_digest_mismatch"):
        LocalRetrievalFixtureEvaluation.model_validate(replay)


def test_fixture_modules_and_runner_have_no_runtime_adapter_or_transport_imports() -> None:
    for path in (MODULE, ORACLE_MODULE, GATE):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        forbidden = {"duckdb", "requests", "sqlite3", "sec_agent.ledger_store", "sec_agent.mcp_tool_registry", "retrieval.bm25_retriever"}
        assert not forbidden & imports


def test_fixture_gate_writes_only_explicit_sanitized_manifest_outputs(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    oracle = tmp_path / "oracle.json"
    package = tmp_path / "package.json"
    result = tmp_path / "result.json"
    completed = subprocess.run([sys.executable, str(GATE), "--corpus-output", str(corpus), "--oracle-output", str(oracle), "--package-output", str(package), "--output", str(result)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    corpus_payload = json.loads(corpus.read_text(encoding="utf-8"))
    oracle_payload = json.loads(oracle.read_text(encoding="utf-8"))
    package_payload = json.loads(package.read_text(encoding="utf-8"))
    result_payload = json.loads(result.read_text(encoding="utf-8"))
    assert result_payload["status"] == "pass"
    assert result_payload["corpus_digest"] == corpus_payload["corpus_digest"] == oracle_payload["corpus_digest"]
    assert result_payload["oracle_digest"] == oracle_payload["oracle_digest"]
    assert result_payload["fixture_package_digest"] == package_payload["package_digest"]
    assert all(value == 0 for value in result_payload["zero_execution_counts"].values())
