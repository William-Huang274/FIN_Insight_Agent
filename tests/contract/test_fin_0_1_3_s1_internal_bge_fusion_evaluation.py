from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_bge_fusion_evaluation import (  # noqa: E402
    RESULT_SCHEMA_V1_1,
    S1InternalBGEFusionEvaluationError,
    execute_internal_bge_fusion_evaluation,
    load_internal_bge_fusion_evaluation_policy,
    merge_ranked_lanes,
    validate_internal_bge_fusion_evaluation_result,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_policy_v1_0.json"
)
SUCCESSOR_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_policy_v1_1.json"
)
R1_AUDIT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_bge_fusion_"
    "evaluation_attempt_r1_post_run_identity_audit_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_policy_binds_owner_qrels_and_local_resources_without_reranker() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    assert policy["run_scope"] == (
        "S1_INTERNAL_BGE_FUSION_AND_RERANK_EVALUATION"
    )
    assert policy["candidate_contract"]["bundle_count"] == 18
    assert policy["candidate_contract"][
        "milvus_fiscal_year_field_authority"
    ] == "reporting_fiscal_years"
    assert policy["resource_bindings"]["reranker"] == (
        "optional_resource_absent_not_executed"
    )
    assert policy["hard_boundaries"]["may_download_model_or_reranker"] is False


def test_r1_audit_invalidates_metrics_and_successor_policy_binds_fix() -> None:
    audit = _load(R1_AUDIT_PATH)
    body = dict(audit)
    supplied = body.pop("audit_digest")
    assert supplied == canonical_digest(body)
    assert audit["status"] == (
        "attempt_invalidated_for_adoption_identity_canonicalization_defect"
    )
    assert audit["defect"]["collision_record_count"] == 18
    assert "8K_EARNINGS" in audit["defect"]["collapsed_namespace_prefixes"]
    assert audit["disposition"]["r1_metrics_valid_for_adoption"] is False
    policy = load_internal_bge_fusion_evaluation_policy(
        SUCCESSOR_POLICY_PATH, repo_root=ROOT
    )
    identity = policy["candidate_contract"]["identity_canonicalization"]
    assert identity["vector_base_rule"] == (
        "strip_only_final_known_vector_kind_suffix"
    )
    assert identity["namespace_prefix_is_never_evidence_identity"] is True
    assert policy["replacement_authority"]["maximum_replacement_executions"] == 1


def test_historical_r1_policy_cannot_execute_real_embedding_again() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    with pytest.raises(
        S1InternalBGEFusionEvaluationError,
        match="internal_bge_fusion_r1_policy_invalidated_for_real_execution",
    ):
        execute_internal_bge_fusion_evaluation(policy=policy, repo_root=ROOT)


def test_lane_merge_is_order_stable_and_coalesces_same_evidence() -> None:
    bm25 = [
        {
            "route_rank": 2,
            "source_key": "EVIDENCE_A",
            "ticker": "NVDA",
            "fiscal_year": 2027,
        },
        {"route_rank": 1, "source_key": "EVIDENCE_B", "ticker": "NVDA"},
    ]
    dense = [
        {"rank": 1, "evidence_id": "EVIDENCE_A", "ticker": "NVDA"},
        {"rank": 2, "evidence_id": "EVIDENCE_C", "ticker": "NVDA"},
    ]
    weights = {"internal_bm25": 1.0, "dense_en": 1.0}
    first = merge_ranked_lanes(
        lanes={"internal_bm25": bm25, "dense_en": dense},
        weights=weights,
        rrf_k=60,
        top_k=4,
    )
    second = merge_ranked_lanes(
        lanes={
            "dense_en": list(reversed(dense)),
            "internal_bm25": list(reversed(bm25)),
        },
        weights=weights,
        rrf_k=60,
        top_k=4,
    )
    assert [item["candidate_key"] for item in first] == [
        item["candidate_key"] for item in second
    ]
    assert first[0]["candidate_key"] == "EVIDENCE_A"
    assert first[0]["route_ranks"] == {"dense_en": 1, "internal_bm25": 2}


def test_namespaced_vector_identity_strips_only_final_vector_kind_suffix() -> None:
    first_evidence = (
        "8K_EARNINGS::DELL::0001::EXHIBIT991::BLOCK_0001::CHUNK_0001"
    )
    second_evidence = (
        "8K_EARNINGS::DELL::0001::EXHIBIT991::BLOCK_0002::CHUNK_0001"
    )
    ranked = merge_ranked_lanes(
        lanes={
            "dense_en": [
                {
                    "rank": 1,
                    "evidence_id": first_evidence,
                    "vector_id": first_evidence,
                    "vector_kind": "narrative_chunk",
                },
                {
                    "rank": 2,
                    "evidence_id": second_evidence,
                    "vector_id": f"{second_evidence}::paraphrase_context",
                    "vector_kind": "paraphrase_context",
                },
            ],
            "dense_zh": [
                {
                    "rank": 1,
                    "evidence_id": first_evidence,
                    "vector_id": f"{first_evidence}::table_chunk",
                    "vector_kind": "table_chunk",
                }
            ],
        },
        weights={"dense_en": 1.0, "dense_zh": 0.85},
        rrf_k=60,
        top_k=4,
    )
    assert len(ranked) == 2
    assert ranked[0]["candidate_key"] == first_evidence
    assert ranked[0]["route_ranks"] == {"dense_en": 1, "dense_zh": 1}
    assert ranked[1]["candidate_key"] == second_evidence
    assert "8K_EARNINGS" not in {
        alias for item in ranked for alias in item["aliases"]
    }


class _FakeModel:
    def encode(self, texts, **_):
        assert len(texts) == 36
        return [[0.0] * 1024 for _ in texts]


class _FakeClient:
    def __init__(self) -> None:
        self.searches = 0
        self.loaded = False

    def load_collection(self, *, collection_name: str) -> None:
        assert collection_name
        self.loaded = True

    def search(self, **kwargs):
        assert self.loaded
        assert kwargs["limit"] == 24
        assert "fiscal_year in" in kwargs["filter"]
        self.searches += 1
        return [
            [
                {
                    "distance": 0.1,
                    "entity": {
                        "vector_id": f"FAKE_{self.searches}",
                        "evidence_id": f"FAKE_{self.searches}",
                        "ticker": "",
                        "fiscal_year": None,
                        "form_type": "",
                        "source_tier": "primary_sec_filing",
                        "vector_kind": "narrative_chunk",
                        "preview": "fake deterministic candidate",
                    },
                }
            ]
        ]

    def release_collection(self, *, collection_name: str) -> None:
        assert collection_name
        self.loaded = False


def test_full_fake_executes_36_embeddings_and_searches_then_loads_qrels() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    client = _FakeClient()
    result = execute_internal_bge_fusion_evaluation(
        policy=policy,
        repo_root=ROOT,
        model_factory=lambda _path, _device: _FakeModel(),
        client_factory=lambda **_: client,
        execution_kind="full_fake_zero_external_call",
    )
    assert client.searches == 36
    assert result["candidate_generation"]["status"] == (
        "terminal_before_qrels_load"
    )
    assert result["candidate_generation"][
        "qrels_loaded_after_candidate_generation"
    ] is True
    assert len(
        result["candidate_generation"]["preserved_sparse_typed_gaps"]
    ) == 1
    assert result["observed_calls"]["embedding_vectors"] == 36
    assert result["observed_calls"]["milvus_searches"] == 36
    assert result["adoption_decision"]["reranker"] == (
        "not_executed_optional_resource_absent"
    )
    assert result["preserved_boundaries"]["current_quarter_exact_sql"] == (
        "0_of_6_open"
    )


def test_successor_full_fake_binds_r1_invalidation_and_identity_fix() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        SUCCESSOR_POLICY_PATH, repo_root=ROOT
    )
    result = execute_internal_bge_fusion_evaluation(
        policy=policy,
        repo_root=ROOT,
        model_factory=lambda _path, _device: _FakeModel(),
        client_factory=lambda **_: _FakeClient(),
        execution_kind="full_fake_zero_external_call",
    )
    assert result["schema_version"] == RESULT_SCHEMA_V1_1
    assert result["supersession"]["invalidated_attempt_id"].endswith("v1_r1")
    assert result["candidate_generation"]["identity_canonicalization"][
        "namespace_prefix_is_never_evidence_identity"
    ] is True


def test_result_boundary_mutation_fails_closed() -> None:
    policy = load_internal_bge_fusion_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )
    result = execute_internal_bge_fusion_evaluation(
        policy=policy,
        repo_root=ROOT,
        model_factory=lambda _path, _device: _FakeModel(),
        client_factory=lambda **_: _FakeClient(),
        execution_kind="full_fake_zero_external_call",
    )
    mutated = deepcopy(result)
    mutated["preserved_boundaries"]["release"] = "qualified"
    with pytest.raises(
        S1InternalBGEFusionEvaluationError,
        match="internal_bge_fusion_result_digest_invalid",
    ):
        validate_internal_bge_fusion_evaluation_result(mutated)
