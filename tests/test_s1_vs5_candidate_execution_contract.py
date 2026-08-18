from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_candidate_execution_policy_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_vs5_candidate_execution_policy_binds_every_runtime_input() -> None:
    value = json.loads(POLICY.read_text(encoding="utf-8"))
    assert value["status"] == "frozen_before_any_qualification_ranking"
    for binding in value["bound_inputs"].values():
        path = ROOT / binding["ref"]
        assert path.is_file()
        assert _sha256(path) == binding["sha256"]


def test_vs5_candidate_execution_is_label_blind_and_cuda_fp16_only() -> None:
    value = json.loads(POLICY.read_text(encoding="utf-8"))
    serialized_bindings = json.dumps(value["bound_inputs"], ensure_ascii=False)
    assert "reference" not in serialized_bindings.casefold()
    contract = value["candidate_contract"]
    assert contract["learned_vector_device"] == "cuda:0"
    assert contract["learned_vector_precision"] == "fp16"
    assert contract["cpu_vector_fallback_allowed"] is False
    assert contract["rerank_each_candidate_against_all_needs"] is False
    assert contract["rerank_only_against_needs_that_recalled_candidate"] is True
    assert contract["maximum_relevant_needs_per_candidate"] == 3
    assert contract["candidate_is_not_evidence"] is True
    assert contract["numeric_fact_authority"] is False


def test_vs5_reranker_pair_budget_matches_bounded_algorithm() -> None:
    value = json.loads(POLICY.read_text(encoding="utf-8"))
    contract = value["candidate_contract"]
    basis = value["token_budget_basis"]["reranker_per_model"]
    assert basis["maximum_pair_count"] == (
        30
        * contract["reranker_pool_limit"]
        * contract["maximum_relevant_needs_per_candidate"]
    )
    assert basis["valid_temporal_maximum_pair_count"] == (
        5
        * contract["reranker_pool_limit"]
        * contract["maximum_relevant_needs_per_candidate"]
    )
