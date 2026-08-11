from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_dense_resource_qualification import (  # noqa: E402
    S1InternalDenseResourceQualificationError,
    load_dense_resource_qualification_policy,
    materialize_dense_resource_qualification,
    validate_dense_resource_qualification,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_internal_dense_resource_qualification_policy_v1_0.json"
)


def _observation() -> dict:
    policy = load_dense_resource_qualification_policy(POLICY_PATH, repo_root=ROOT)
    result = materialize_dense_resource_qualification(policy, repo_root=ROOT)
    validate_dense_resource_qualification(result)
    return result


def test_local_bge_and_milvus_are_qualified_without_executing_ranking() -> None:
    result = _observation()
    assert result["status"] == "resources_qualified_execution_not_admitted_owner_review_pending"
    assert result["resource_qualification"]["bge_m3"]["status"] == (
        "qualified_successor_locator_not_yet_bound"
    )
    assert result["resource_qualification"]["bge_m3"]["hidden_size"] == 1024
    assert result["resource_qualification"]["milvus_runtime_dependency"]["status"] == (
        "qualified_via_explicit_runtime_dependency_path"
    )
    assert result["execution_gate"]["owner_review_complete"] is False
    assert result["execution_gate"]["BGE_dense_execution_admitted"] is False
    assert all(value == 0 for value in result["observed_calls"].values())


def test_missing_reranker_is_optional_and_not_silently_downloaded() -> None:
    result = _observation()
    assert result["resource_qualification"]["reranker"]["status"] == (
        "optional_resource_absent"
    )
    assert result["resource_qualification"]["reranker"]["present_paths"] == []
    assert result["execution_gate"]["rerank_execution_admitted"] is False


def test_resource_qualification_digest_fails_closed_on_admission_mutation() -> None:
    result = _observation()
    mutated = deepcopy(result)
    mutated["execution_gate"]["BGE_dense_execution_admitted"] = True
    with pytest.raises(
        S1InternalDenseResourceQualificationError,
        match="dense_resource_observation_digest_invalid",
    ):
        validate_dense_resource_qualification(mutated)
