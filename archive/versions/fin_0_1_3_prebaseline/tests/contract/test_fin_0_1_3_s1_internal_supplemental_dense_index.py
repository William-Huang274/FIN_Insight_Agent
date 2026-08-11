from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_dense_index import (  # noqa: E402
    S1InternalSupplementalDenseIndexError,
    compile_supplemental_vector_specs,
    load_supplemental_dense_index_policy,
    materialize_supplemental_dense_index_zero_call_proof,
    validate_supplemental_dense_index_zero_call_proof,
    validate_vector_specs,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_internal_supplemental_dense_index_policy_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_internal_supplemental_dense_index_"
    "zero_call_proof_v1_0.json"
)


def _policy() -> dict:
    return load_supplemental_dense_index_policy(POLICY_PATH, repo_root=ROOT)


def test_compiler_uses_all_capture_backed_rows_without_qrels_shaping() -> None:
    policy = _policy()
    specs, manifests = compile_supplemental_vector_specs(policy, repo_root=ROOT)
    assert len(specs) == len({row["evidence_id"] for row in specs}) == 410
    assert [row["vector_spec_count"] for row in manifests] == [292, 118]
    assert {ticker: sum(row["ticker"] == ticker for row in specs) for ticker in {"DELL", "MU", "TSM"}} == {
        "DELL": 279,
        "MU": 128,
        "TSM": 3,
    }
    assert all(row["vector_id"] == row["evidence_id"] for row in specs)
    assert all(row["candidate_state"] == "candidate_only_not_evidence" for row in specs)
    assert all(row["capture_digest"] and row["source_url"] for row in specs)


def test_zero_call_proof_closes_presence_only_and_fails_mutations_closed() -> None:
    result = materialize_supplemental_dense_index_zero_call_proof(
        _policy(), repo_root=ROOT
    )
    validate_supplemental_dense_index_zero_call_proof(result)
    assert result["federated_presence_gate"] == {
        "owner_selected_unique_target_count": 10,
        "historical_present_unique_target_count": 5,
        "supplemental_present_unique_target_count": 5,
        "missing_unique_target_count": 0,
        "row_weighted_target_count": 18,
        "row_weighted_satisfied_count": 18,
        "status": "pass_10_of_10_unique_and_18_of_18_rows_present_after_successor_build",
    }
    assert result["fake_execution"]["fake_embedding_batch_count"] == 13
    assert result["fake_execution"]["fake_inserted_vector_count"] == 410
    assert result["mutation_proof"]["scenario_count"] == 8
    assert result["mutation_proof"]["all_failed_closed"] is True
    assert result["execution_gate"]["real_embedding_build_admitted"] is False
    assert all(value == 0 for value in result["observed_real_calls"].values())


def test_duplicate_and_lineage_mutations_cannot_enter_build_plan() -> None:
    policy = _policy()
    specs, _ = compile_supplemental_vector_specs(policy, repo_root=ROOT)
    with pytest.raises(
        S1InternalSupplementalDenseIndexError,
        match="supplemental_dense_duplicate_or_missing_evidence_identity",
    ):
        validate_vector_specs(specs + [deepcopy(specs[0])], policy=policy)
    mutated = deepcopy(specs)
    mutated[0]["capture_digest"] = ""
    with pytest.raises(
        S1InternalSupplementalDenseIndexError,
        match="supplemental_dense_vector_identity_or_lineage_invalid",
    ):
        validate_vector_specs(mutated, policy=policy)


def test_materialized_result_is_digest_bound_and_does_not_claim_ranking_gain() -> None:
    result = validate_supplemental_dense_index_zero_call_proof(
        json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    )
    assert result["source_inventory"]["vector_spec_count"] == 410
    assert result["preserved_boundaries"]["semantic_ranking_quality_improved"] is False
    mutated = deepcopy(result)
    mutated["execution_gate"]["real_embedding_build_admitted"] = True
    with pytest.raises(
        S1InternalSupplementalDenseIndexError,
        match="supplemental_dense_zero_call_proof_invalid",
    ):
        validate_supplemental_dense_index_zero_call_proof(mutated)
