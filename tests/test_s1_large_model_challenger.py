from __future__ import annotations

import json
from pathlib import Path

from retrieval.large_model_challenger import evaluate_large_model_resource_gate
from scripts.data_retrieval.materialize_s1_large_model_challenger_preflight import (
    _artifact_state,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = json.loads(
    (
        ROOT
        / "configs/retrieval/fin_ia_0_1_3_s1_large_model_challenger_program_v1_0.json"
    ).read_text(encoding="utf-8")
)


def _artifacts(status: str) -> dict[str, dict[str, str]]:
    return {
        "qwen3_embedding_4b": {"status": status},
        "qwen3_reranker_4b": {"status": status},
    }


def test_local_8gb_profile_fails_closed_before_download() -> None:
    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware={
            "cuda_available": True,
            "total_memory_bytes": 8 * 1024**3,
            "free_memory_bytes": 7 * 1024**3,
        },
        storage={"free_bytes": 30 * 1024**3},
        model_artifacts=_artifacts("absent"),
    )

    assert result["status"] == "resource_blocked_before_download"
    assert result["resource_blockers"] == [
        "gpu_total_memory_below_preregistered_profile",
        "gpu_free_memory_below_preregistered_profile",
    ]
    assert result["decision"]["development_execution_authorized_by_this_preflight"] is False
    assert result["calls"] == {"network": 0, "provider": 0, "model": 0}


def test_suitable_profile_with_bound_models_is_attempt_eligible_not_authority() -> None:
    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware={
            "cuda_available": True,
            "total_memory_bytes": 24 * 1024**3,
            "free_memory_bytes": 22 * 1024**3,
        },
        storage={"free_bytes": 30 * 1024**3},
        model_artifacts=_artifacts("identity_bound"),
    )

    assert result["status"] == "eligible_for_preregistered_development_attempt"
    assert result["resource_blockers"] == []
    assert result["artifact_blockers"] == []
    assert result["decision"]["runtime_promotion_authorized"] is False
    assert result["decision"]["evidence_or_numeric_authority_granted"] is False


def test_program_forbids_hidden_cost_and_runtime_promotion() -> None:
    split = PROGRAM["split_and_leakage_policy"]
    assert split["forbidden_case_keys"] == ["COST"]
    assert split["hidden_frozen_holdout_reference_loading_forbidden"] is True
    assert PROGRAM["authority"]["runtime_promotion_authorized"] is False
    assert PROGRAM["execution_order"][2] == (
        "candidate_ceiling_on_shared_development_corpus"
    )


def test_partial_local_artifact_returns_typed_blocker_instead_of_crashing(
    tmp_path: Path,
) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")

    artifact = _artifact_state(
        tmp_path,
        model_id="Qwen/Qwen3-Embedding-4B",
        kind="embedding",
    )
    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware={
            "cuda_available": True,
            "total_memory_bytes": 24 * 1024**3,
            "free_memory_bytes": 22 * 1024**3,
        },
        storage={"free_bytes": 30 * 1024**3},
        model_artifacts={
            "qwen3_embedding_4b": artifact,
            "qwen3_reranker_4b": {"status": "identity_bound"},
        },
    )

    assert artifact["status"] == "identity_invalid"
    assert artifact["identity_error"].startswith(
        "local_embedding_model_v2_incomplete:"
    )
    assert result["status"] == (
        "model_artifacts_missing_download_not_authorized_by_preflight"
    )
    assert result["artifact_blockers"] == [
        "model_artifact_not_identity_bound:qwen3_embedding_4b:identity_invalid"
    ]
