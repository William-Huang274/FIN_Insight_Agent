from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    candidate_spec_to_sparse_record,
    load_bound_private_manifest,
    load_physical_index_policy,
)
from sec_agent.s1_candidate_bundle_retrieval_evaluation import (  # noqa: E402
    CASES,
    OWNER_SUITE,
    SLOT_SUITE,
    CandidateBundleRetrievalEvaluationError,
    attribute_ranking_error,
    compile_query_bundles,
    fuse_rankings,
    load_candidate_bundle_retrieval_evaluation_policy,
    load_labels_after_candidate_generation,
    materialize_candidate_bundle_retrieval_terminal_result,
    rank_dense_bge_m3,
    rank_object_bm25,
    validate_candidate_records,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_candidate_bundle_retrieval_evaluation import normalized_sha256  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_retrieval_evaluation_policy_v1_0.json"
)
BUILD_POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_1.json"
)


def _policy() -> dict:
    return load_candidate_bundle_retrieval_evaluation_policy(
        POLICY_PATH, repo_root=ROOT
    )


def _records() -> list[dict]:
    build_policy = load_physical_index_policy(BUILD_POLICY_PATH, repo_root=ROOT)
    _manifest, specs = load_bound_private_manifest(build_policy, repo_root=ROOT)
    return [candidate_spec_to_sparse_record(spec) for spec in specs]


def _record(
    vector_id: str,
    *,
    case_key: str,
    slot_id: str,
    score_text: str,
    target_id: str | None = None,
) -> dict:
    return {
        "object_id": vector_id,
        "object_type": "financial_source_object",
        "source_evidence_id": target_id or vector_id,
        "ticker": case_key,
        "fiscal_year": 2026,
        "period_end": "2026-06-30",
        "preview": score_text,
        "search_text": score_text,
        "metadata": {
            "candidate_state": "bundle_candidate_only_not_evidence",
            "target_id": target_id or vector_id,
            "source_locator": "fixture://candidate",
            "slot_ids": [slot_id],
            "facet_ids": ["fixture_facet"],
        },
    }


def test_policy_compiles_72_queries_without_gold_or_url_leakage() -> None:
    policy = _policy()
    bundles = compile_query_bundles(policy, repo_root=ROOT)
    assert len(bundles) == 72
    assert len({row["bundle_id"] for row in bundles}) == 72
    assert sum(row["suite_id"] == OWNER_SUITE for row in bundles) == 18
    assert sum(row["suite_id"] == SLOT_SUITE for row in bundles) == 54
    assert {
        case: sum(
            row["suite_id"] == SLOT_SUITE and row["case_key"] == case
            for row in bundles
        )
        for case in CASES
    } == {case: 9 for case in CASES}
    assert all(row["target_identity_in_query"] is False for row in bundles)
    assert all("::" not in row["query_text"] for row in bundles)
    assert all("http://" not in row["query_text"] for row in bundles)
    assert all("https://" not in row["query_text"] for row in bundles)


def test_frozen_population_exposes_business_candidate_ceiling_before_ranking() -> None:
    policy = _policy()
    bundles = compile_query_bundles(policy, repo_root=ROOT)
    records = validate_candidate_records(
        _records(),
        expected_case_counts=policy["physical_index_binding"]["expected_case_counts"],
    )
    labels = load_labels_after_candidate_generation(
        policy=policy,
        repo_root=ROOT,
        records=records,
        bundles=bundles,
    )
    owner_rows = [row for row in bundles if row["suite_id"] == OWNER_SUITE]
    assert sum(bool(labels[row["bundle_id"]]["relevant_vector_ids"]) for row in owner_rows) == 16
    missing_owner = {
        (row["case_key"], row["research_slot_id"])
        for row in owner_rows
        if not labels[row["bundle_id"]]["relevant_vector_ids"]
    }
    assert missing_owner == {
        ("NVDA", "regulatory_risk_and_financial_reconciliation"),
        ("NVDA", "supply_chain_capacity_and_counterevidence"),
    }

    required_rows = [
        row
        for row in bundles
        if row["suite_id"] == SLOT_SUITE and row["required"]
    ]
    assert sum(bool(labels[row["bundle_id"]]["relevant_vector_ids"]) for row in required_rows) == 36
    assert {
        case: sum(
            bool(labels[row["bundle_id"]]["relevant_vector_ids"])
            for row in required_rows
            if row["case_key"] == case
        )
        for case in CASES
    } == {
        "DELL": 8,
        "MU": 8,
        "NVDA": 8,
        "ORCL": 5,
        "ASML": 3,
        "ANET": 4,
    }


class _FakeBM25:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores

    def get_scores(self, _tokens: list[str]) -> list[float]:
        return list(self.scores)


def test_sparse_ranking_filters_case_before_top_k() -> None:
    records = [
        _record("DELL_A", case_key="DELL", slot_id="operating_performance", score_text="Dell revenue"),
        _record("MU_HIGH", case_key="MU", slot_id="operating_performance", score_text="Micron revenue"),
        _record("DELL_B", case_key="DELL", slot_id="demand_volume_quality", score_text="Dell orders"),
    ]
    bundle = {
        "bundle_id": "B1",
        "case_key": "DELL",
        "query_text": "Dell revenue orders",
    }
    ranked = rank_object_bm25(
        records=records,
        bm25=_FakeBM25([0.4, 99.0, 0.8]),
        bundles=[bundle],
        top_k=10,
    )
    assert [row["vector_id"] for row in ranked["B1"]] == ["DELL_B", "DELL_A"]


class _FakeEmbedder:
    calls = 0
    vectors = 0

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.vectors += len(texts)
        return [[0.0, 1.0] for _ in texts]


class _FakeDenseClient:
    def __init__(self) -> None:
        self.search_calls: list[tuple[str, int]] = []

    def search(self, **kwargs):  # type: ignore[no-untyped-def]
        case_key = str(kwargs["filter"]).split('"')[1]
        self.search_calls.append((case_key, len(kwargs["data"])))
        return [
            [
                {
                    "distance": 0.75,
                    "entity": {
                        "vector_id": f"{case_key}_FAKE_{index}",
                        "case_key": case_key,
                        "target_id": f"{case_key}_TARGET_{index}",
                        "object_type": "financial_source_object",
                        "slot_ids_json": '["operating_performance"]',
                        "facet_ids_json": '["reported_revenue"]',
                        "source_reporting_period_end": "2026-06-30",
                        "source_locator": "fixture://dense",
                        "preview": "fixture dense candidate",
                    },
                }
            ]
            for index, _vector in enumerate(kwargs["data"])
        ]


def test_dense_groups_72_vectors_into_exactly_six_case_filtered_searches() -> None:
    bundles = compile_query_bundles(_policy(), repo_root=ROOT)
    client = _FakeDenseClient()
    rankings, calls = rank_dense_bge_m3(
        bundles=bundles,
        embedder=_FakeEmbedder(),
        client=client,
        collection_name="fixture_collection",
        top_k=10,
    )
    assert calls == {"search_invocations": 6, "query_vectors": 72}
    assert client.search_calls == [
        ("DELL", 15),
        ("MU", 15),
        ("NVDA", 15),
        ("ORCL", 9),
        ("ASML", 9),
        ("ANET", 9),
    ]
    assert len(rankings) == 72


def test_dense_rejects_cross_case_result() -> None:
    class CrossCaseClient(_FakeDenseClient):
        def search(self, **kwargs):  # type: ignore[no-untyped-def]
            rows = super().search(**kwargs)
            rows[0][0]["entity"]["case_key"] = "WRONG"
            return rows

    bundles = compile_query_bundles(_policy(), repo_root=ROOT)
    with pytest.raises(CandidateBundleRetrievalEvaluationError) as exc:
        rank_dense_bge_m3(
            bundles=bundles,
            embedder=_FakeEmbedder(),
            client=CrossCaseClient(),
            collection_name="fixture_collection",
            top_k=10,
        )
    assert exc.value.code == "candidate_bundle_retrieval_dense_cross_case_or_identity_invalid"


def test_equal_weight_rrf_is_route_order_stable() -> None:
    a = {"vector_id": "A", "rank": 1, "case_key": "DELL"}
    b = {"vector_id": "B", "rank": 2, "case_key": "DELL"}
    c = {"vector_id": "C", "rank": 1, "case_key": "DELL"}
    first = fuse_rankings(
        sparse={"Q": [a, b]},
        dense={"Q": [c, a]},
        rrf_k=60,
        top_k=10,
    )
    second = fuse_rankings(
        sparse={"Q": [a, b]},
        dense={"Q": [c, a]},
        rrf_k=60,
        top_k=10,
    )
    assert first == second
    assert [row["vector_id"] for row in first["Q"]] == ["A", "C", "B"]


def test_business_error_attribution_separates_upstream_absence_and_wrong_slot() -> None:
    bundle = {
        "suite_id": SLOT_SUITE,
        "case_key": "ASML",
        "research_slot_id": "demand_volume_quality",
        "required": True,
        "reporting_years": [2026],
    }
    absent = attribute_ranking_error(
        bundle=bundle,
        label={"relevant_vector_ids": []},
        ranking=[],
    )
    assert absent is not None
    assert absent["error_class"] == "required_candidate_slot_absent_from_93_population"

    wrong = attribute_ranking_error(
        bundle=bundle,
        label={"relevant_vector_ids": ["ASML_DEMAND"]},
        ranking=[
            {
                "vector_id": "ASML_REVENUE",
                "slot_ids": ["operating_performance"],
                "fiscal_year": 2026,
            },
            {
                "vector_id": "ASML_DEMAND",
                "slot_ids": ["demand_volume_quality"],
                "fiscal_year": 2026,
            },
        ],
    )
    assert wrong is not None
    assert wrong["error_class"] == "same_case_wrong_research_slot"
    assert "different financial question" in wrong["business_explanation"]


def test_unexpected_local_failure_is_materialized_once_as_typed_terminal(
    tmp_path: Path,
) -> None:
    policy = _policy()
    authority_body = {
        "schema_version": policy["authority_schema"],
        "status": "issued_unconsumed",
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "policy_digest": canonical_digest(policy),
        "implementation": {
            "commit": "0" * 40,
            "clean": True,
            "synced": True,
            "ahead": 0,
            "behind": 0,
            "bindings": [
                {
                    "ref": str(POLICY_PATH.relative_to(ROOT)).replace("\\", "/"),
                    "sha256": normalized_sha256(POLICY_PATH),
                }
            ],
            "implementation_proof_digest": "1" * 64,
        },
        "environment_qualification": {
            "qualified": True,
            "physical_artifact_digest": policy["physical_index_binding"][
                "expected_artifact_digest"
            ],
            "sparse_files_present": True,
            "observed_calls": {"network": 0, "llm_model": 0},
        },
        "project_os_preflight": {"status": "pass"},
        "execution_ceiling": policy["execution_ceiling"],
        "maximum_executions": 1,
        "automatic_retry": False,
    }
    authority = {
        **authority_body,
        "authority_digest": canonical_digest(authority_body),
    }
    output = tmp_path / "terminal.json"
    result = materialize_candidate_bundle_retrieval_terminal_result(
        policy=policy,
        authority=authority,
        repo_root=ROOT,
        output_path=output,
    )
    assert result["status"] == (
        "terminal_failed_six_case_retrieval_business_evaluation"
    )
    assert result["failure"]["automatic_retry"] is False
    assert result["stage_acceptance"]["retrieval_measurement_terminal"] is False
    assert output.is_file()
    with pytest.raises(CandidateBundleRetrievalEvaluationError) as exc:
        materialize_candidate_bundle_retrieval_terminal_result(
            policy=policy,
            authority=authority,
            repo_root=ROOT,
            output_path=output,
        )
    assert exc.value.code == "candidate_bundle_retrieval_terminal_result_preexists"
