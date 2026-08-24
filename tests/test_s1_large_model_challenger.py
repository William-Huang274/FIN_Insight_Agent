from __future__ import annotations

import hashlib
import json
from pathlib import Path

from retrieval.large_model_challenger import evaluate_large_model_resource_gate
from retrieval.model_identity import (
    ACQUISITION_MANIFEST_NAME,
    ACQUISITION_MANIFEST_SCHEMA_VERSION,
)
from retrieval.query_plan import canonical_digest


ROOT = Path(__file__).resolve().parents[1]


def _program(version: str = "v1_2") -> dict[str, object]:
    return json.loads(
        (
            ROOT
            / "configs/retrieval/"
            f"fin_ia_0_1_3_s1_large_model_challenger_program_{version}.json"
        ).read_text(encoding="utf-8")
    )


PROGRAM = _program()
SUITABLE_HARDWARE = {
    "cuda_available": True,
    "total_memory_bytes": 24 * 1024**3,
    "free_memory_bytes": 22 * 1024**3,
}
SUITABLE_STORAGE = {"free_bytes": 30 * 1024**3}


def test_ancestor_locator_preflight_successor_receipt_is_canonical() -> None:
    path = (
        ROOT
        / "configs/retrieval/"
        "fin_ia_0_1_3_s1_large_model_challenger_preflight_result_v1_3.json"
    )
    result = json.loads(path.read_text(encoding="utf-8"))
    unsigned = {
        key: value for key, value in result.items() if key != "result_digest"
    }

    assert result["result_digest"] == canonical_digest(unsigned)
    assert result["status"] == "resource_blocked_before_download"
    assert all(result["audit_successor_checks"].values())
    assert result["identity_contract"][
        "every_locator_ancestor_link_or_reparse_component_forbidden"
    ] is True
    assert result["artifact_blockers"] == [
        "model_artifact_absent:qwen3_embedding_4b",
        "model_artifact_absent:qwen3_reranker_4b",
    ]
    assert result["calls"] == {"network": 0, "provider": 0, "model": 0}
    assert result["decision"][
        "development_execution_authorized_by_this_preflight"
    ] is False


def _locators(embedding_dir: Path, reranker_dir: Path) -> dict[str, dict[str, str]]:
    return {
        "qwen3_embedding_4b": {
            "status": "caller_claim_only",
            "local_dir": str(embedding_dir),
        },
        "qwen3_reranker_4b": {
            "status": "caller_claim_only",
            "local_dir": str(reranker_dir),
        },
    }


def _write_model(model_dir: Path, *, model_id: str) -> None:
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"weights")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
    files = []
    for path in sorted(model_dir.iterdir(), key=lambda value: value.name):
        files.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (model_dir / ACQUISITION_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema_version": ACQUISITION_MANIFEST_SCHEMA_VERSION,
                "model_id": model_id,
                "resolved_revision": "a" * 40,
                "acquisition_tool": "huggingface_hub.snapshot_download",
                "files": files,
            }
        ),
        encoding="utf-8",
    )


def test_local_8gb_profile_fails_closed_before_download(tmp_path: Path) -> None:
    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware={
            "cuda_available": True,
            "total_memory_bytes": 8 * 1024**3,
            "free_memory_bytes": 7 * 1024**3,
        },
        storage=SUITABLE_STORAGE,
        model_artifacts=_locators(
            tmp_path / "missing-embedding", tmp_path / "missing-reranker"
        ),
    )

    assert result["status"] == "resource_blocked_before_download"
    assert result["resource_blockers"] == [
        "gpu_total_memory_below_preregistered_profile",
        "gpu_free_memory_below_preregistered_profile",
    ]
    assert result["decision"]["development_execution_authorized_by_this_preflight"] is False
    assert result["calls"] == {"network": 0, "provider": 0, "model": 0}


def test_suitable_profile_still_requires_owner_approved_acquisition_revision(
    tmp_path: Path,
) -> None:
    embedding_dir = tmp_path / "embedding"
    reranker_dir = tmp_path / "reranker"
    _write_model(embedding_dir, model_id="Qwen/Qwen3-Embedding-4B")
    _write_model(reranker_dir, model_id="Qwen/Qwen3-Reranker-4B")

    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware=SUITABLE_HARDWARE,
        storage=SUITABLE_STORAGE,
        model_artifacts=_locators(embedding_dir, reranker_dir),
    )

    assert result["status"] == (
        "model_artifacts_missing_download_not_authorized_by_preflight"
    )
    assert result["resource_blockers"] == []
    assert result["artifact_blockers"] == [
        "model_artifact_upstream_revision_not_owner_approved:qwen3_embedding_4b",
        "model_artifact_upstream_revision_not_owner_approved:qwen3_reranker_4b",
    ]
    assert all(
        artifact["gate_revalidated_from_local_files"] is True
        and artifact["status"] == "identity_bound_v3_revision_approval_pending"
        and artifact["upstream_origin_attested_by_local_manifest"] is False
        for artifact in result["model_artifacts"].values()
    )
    assert result["decision"]["runtime_promotion_authorized"] is False
    assert result["decision"]["evidence_or_numeric_authority_granted"] is False


def test_status_only_claim_cannot_cross_attempt_eligibility_seam() -> None:
    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware=SUITABLE_HARDWARE,
        storage=SUITABLE_STORAGE,
        model_artifacts={
            "qwen3_embedding_4b": {"status": "identity_bound_v3"},
            "qwen3_reranker_4b": {"status": "identity_bound_v3"},
        },
    )

    assert result["status"] == (
        "model_artifacts_missing_download_not_authorized_by_preflight"
    )
    assert result["artifact_blockers"] == [
        "model_artifact_locator_missing:qwen3_embedding_4b",
        "model_artifact_locator_missing:qwen3_reranker_4b",
    ]


def test_caller_digest_and_status_are_ignored_in_favor_of_filesystem(
    tmp_path: Path,
) -> None:
    embedding_dir = tmp_path / "embedding"
    reranker_dir = tmp_path / "reranker"
    _write_model(embedding_dir, model_id="Qwen/Qwen3-Embedding-4B")
    _write_model(reranker_dir, model_id="Qwen/Qwen3-Reranker-4B")
    locators = _locators(embedding_dir, reranker_dir)
    for value in locators.values():
        value["status"] = "identity_bound_v3"
        value["model_digest"] = "f" * 64

    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware=SUITABLE_HARDWARE,
        storage=SUITABLE_STORAGE,
        model_artifacts=locators,
    )

    assert result["status"] == (
        "model_artifacts_missing_download_not_authorized_by_preflight"
    )
    assert all(
        artifact["model_digest"] != "f" * 64
        and artifact["caller_claimed_status"] == "identity_bound_v3"
        for artifact in result["model_artifacts"].values()
    )


def test_partial_local_artifact_returns_revalidation_blocker(
    tmp_path: Path,
) -> None:
    embedding_dir = tmp_path / "embedding"
    reranker_dir = tmp_path / "reranker"
    embedding_dir.mkdir()
    (embedding_dir / "config.json").write_text("{}", encoding="utf-8")
    _write_model(reranker_dir, model_id="Qwen/Qwen3-Reranker-4B")

    result = evaluate_large_model_resource_gate(
        PROGRAM,
        hardware=SUITABLE_HARDWARE,
        storage=SUITABLE_STORAGE,
        model_artifacts=_locators(embedding_dir, reranker_dir),
    )

    artifact = result["model_artifacts"]["qwen3_embedding_4b"]
    assert artifact["status"] == "identity_invalid"
    assert artifact["identity_error"] == "local_model_acquisition_manifest_missing"
    assert result["status"] == (
        "model_artifacts_missing_download_not_authorized_by_preflight"
    )
    assert result["artifact_blockers"] == [
        "model_artifact_identity_revalidation_failed:"
        "qwen3_embedding_4b:local_model_acquisition_manifest_missing",
        "model_artifact_upstream_revision_not_owner_approved:"
        "qwen3_reranker_4b",
    ]


def test_historical_programs_replay_but_cannot_authorize_new_attempt() -> None:
    for version, status in (
        ("v1_0", "identity_bound"),
        ("v1_1", "identity_bound_v3"),
    ):
        result = evaluate_large_model_resource_gate(
            _program(version),
            hardware=SUITABLE_HARDWARE,
            storage=SUITABLE_STORAGE,
            model_artifacts={
                "qwen3_embedding_4b": {"status": status},
                "qwen3_reranker_4b": {"status": status},
            },
        )

        assert result["status"] == (
            "historical_identity_contract_not_authorized_for_new_attempt"
        )
        assert result["historical_replay_only"] is True
        assert result["artifact_blockers"] == [
            "historical_program_cannot_authorize_new_attempt:"
            f"fin_ia_s1_large_model_challenger_program_{version}"
        ]


def test_program_forbids_hidden_cost_and_runtime_promotion() -> None:
    split = PROGRAM["split_and_leakage_policy"]
    assert split["forbidden_case_keys"] == ["COST"]
    assert split["hidden_frozen_holdout_reference_loading_forbidden"] is True
    assert split["historical_forbidden_case_diagnostics_as_execution_input_allowed"] is False
    assert PROGRAM["authority"]["runtime_promotion_authorized"] is False
    identity = PROGRAM["artifact_identity_contract"]
    assert identity["identity_contract_version"] == "local_model_identity_v3"
    assert identity["gate_revalidates_local_files"] is True
    assert identity["caller_supplied_status_is_authority"] is False
    assert identity["local_manifest_proves_upstream_origin"] is False
    assert identity["separate_acquisition_receipt_required"] is True
    assert identity["owner_approved_resolved_revision_required"] is True


def test_program_without_gate_revalidation_contract_fails_closed() -> None:
    invalid = dict(PROGRAM)
    invalid["artifact_identity_contract"] = {
        **PROGRAM["artifact_identity_contract"],
        "gate_revalidates_local_files": False,
    }

    try:
        evaluate_large_model_resource_gate(
            invalid,
            hardware=SUITABLE_HARDWARE,
            storage=SUITABLE_STORAGE,
            model_artifacts={},
        )
    except ValueError as exc:
        assert str(exc) == "large_model_challenger_identity_contract_invalid"
    else:
        raise AssertionError("invalid identity contract must fail closed")


def test_split_policy_mutation_cannot_cross_gate() -> None:
    invalid = dict(PROGRAM)
    invalid["split_and_leakage_policy"] = {
        **PROGRAM["split_and_leakage_policy"],
        "forbidden_case_keys": [],
        "historical_forbidden_case_diagnostics_as_execution_input_allowed": True,
    }

    try:
        evaluate_large_model_resource_gate(
            invalid,
            hardware=SUITABLE_HARDWARE,
            storage=SUITABLE_STORAGE,
            model_artifacts={},
        )
    except ValueError as exc:
        assert str(exc) == "large_model_challenger_split_contract_invalid"
    else:
        raise AssertionError("mutated split contract must fail closed")


def test_development_input_digest_mutation_cannot_cross_gate() -> None:
    invalid = dict(PROGRAM)
    invalid["bound_development_inputs"] = [
        *PROGRAM["bound_development_inputs"][:-1],
        {
            **PROGRAM["bound_development_inputs"][-1],
            "sha256": "f" * 64,
        },
    ]

    try:
        evaluate_large_model_resource_gate(
            invalid,
            hardware=SUITABLE_HARDWARE,
            storage=SUITABLE_STORAGE,
            model_artifacts={},
        )
    except ValueError as exc:
        assert str(exc).startswith(
            "large_model_challenger_development_input_digest_mismatch:"
        )
    else:
        raise AssertionError("mutated development input digest must fail closed")


def test_unrelated_program_field_mutation_breaks_approved_digest() -> None:
    invalid = {**PROGRAM, "decision_target": "load COST and hidden answers"}

    try:
        evaluate_large_model_resource_gate(
            invalid,
            hardware=SUITABLE_HARDWARE,
            storage=SUITABLE_STORAGE,
            model_artifacts={},
        )
    except ValueError as exc:
        assert str(exc) == (
            "large_model_challenger_approved_program_digest_mismatch"
        )
    else:
        raise AssertionError("unapproved program content must fail closed")
