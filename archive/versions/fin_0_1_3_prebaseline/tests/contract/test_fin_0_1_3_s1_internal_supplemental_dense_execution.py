from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_internal_supplemental_dense_execution import (  # noqa: E402
    S1InternalSupplementalDenseExecutionError,
    build_real_presence_proof,
    load_supplemental_dense_execution_policy,
    materialize_execution_implementation_proof,
    validate_execution_implementation_proof,
    validate_real_presence_proof,
    validate_terminal_result,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_implementation_proof_v1_0.json"


class _PresenceClient:
    def __init__(self, *, present: set[str]) -> None:
        self.present = present

    def load_collection(self, **_: object) -> None:
        return None

    def query(self, *, filter: str, **_: object) -> list[dict]:
        return [{"evidence_id": item} for item in self.present if json.dumps(item) in filter]

    def get_collection_stats(self, **_: object) -> dict[str, int]:
        return {"row_count": 410}

    def release_collection(self, **_: object) -> None:
        return None

    def close(self) -> None:
        return None


def _loaded() -> tuple[dict, dict, dict]:
    return load_supplemental_dense_execution_policy(POLICY_PATH, repo_root=ROOT)


def test_execution_adapter_full_fake_is_exact_and_does_not_create_target() -> None:
    policy, build_policy, _ = _loaded()
    result = materialize_execution_implementation_proof(
        policy, build_policy, repo_root=ROOT
    )
    validate_execution_implementation_proof(result)
    assert result == json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    assert result["fake_execution"] == {
        "embedding_batch_count": 13,
        "embedding_vector_count": 410,
        "insert_batch_count": 13,
        "inserted_vector_count": 410,
        "terminal_count": 410,
    }
    assert result["milvus_adapter"]["stored_vector_text"] is False
    assert result["milvus_adapter"]["writer_calls"] == {
        "database_create": 1,
        "collection_create": 1,
        "insert_batches": 13,
        "inserted_vectors": 410,
        "flush": 2,
        "count": 1,
    }
    assert result["execution_gate"]["real_build_authorized"] is False
    assert all(value == 0 for value in result["observed_real_calls"].values())


def test_materialized_implementation_proof_is_digest_bound() -> None:
    result = validate_execution_implementation_proof(
        json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    )
    mutated = deepcopy(result)
    mutated["execution_gate"]["real_build_authorized"] = True
    with pytest.raises(
        S1InternalSupplementalDenseExecutionError,
        match="supplemental_dense_execution_implementation_proof_invalid",
    ):
        validate_execution_implementation_proof(mutated)


def test_terminal_failure_requires_truthful_private_state() -> None:
    terminal = {
        "schema_version": "fin_ia_0_1_3_s1_internal_supplemental_dense_execution_result_v1_0",
        "status": "terminal_failed_real_incremental_dense_build_no_retry",
        "automatic_retry": False,
        "failure": {
            "phase": "create_and_populate_working_milvus",
            "error_type": "RuntimeError",
            "error_code": "synthetic_failure",
        },
        "private_state": {
            "working_root_ref": "data/workbench_private/example/building",
            "working_root_exists": True,
            "final_root_ref": "data/workbench_private/example/v1",
            "final_root_exists": False,
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "document_fetch": 0,
            "vector_search": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "execution_gate": {
            "real_incremental_build_passed": False,
            "ranking_successor_authorized": False,
        },
    }
    terminal["result_digest"] = canonical_digest(terminal)
    validate_terminal_result(terminal)
    mutated = deepcopy(terminal)
    mutated["private_state"].pop("working_root_exists")
    mutated.pop("result_digest")
    mutated["result_digest"] = canonical_digest(mutated)
    with pytest.raises(S1InternalSupplementalDenseExecutionError):
        validate_terminal_result(mutated)


def test_presence_proof_queries_both_collections_and_requires_all_ten(tmp_path: Path) -> None:
    policy, build_policy, _ = _loaded()
    diagnostic = json.loads(
        (ROOT / build_policy["immutable_inputs"]["dense_index_diagnostic_ref"]).read_text(encoding="utf-8")
    )
    historical = {
        alias
        for row in diagnostic["rows"]
        if row["present_in_milvus"]
        for alias in row["selected_aliases"]
    }
    supplemental = {
        alias
        for row in diagnostic["rows"]
        if not row["present_in_milvus"]
        for alias in row["selected_aliases"]
    }
    fake_db = tmp_path / "fake.db"
    fake_db.write_bytes(b"fake-milvus")
    terminal = {
        "schema_version": policy["terminal_result_schema"],
        "attempt_id": policy["attempt_id"],
        "status": "terminal_succeeded_real_incremental_dense_build",
        "automatic_retry": False,
        "build": {"terminal_entity_count": 410, "historical_collection_write_count": 0, "private_db_ref": fake_db.as_posix(), "private_db_bytes": fake_db.stat().st_size, "private_db_sha256": __import__("hashlib").sha256(fake_db.read_bytes()).hexdigest(), "collection_name": policy["private_execution"]["collection_name"]},
        "observed_calls": {"network": 0, "provider": 0, "llm_model": 0, "document_fetch": 0, "embedding_model_loads": 1, "embedding_batches": 13, "embedding_model_micro_batches": 52, "embedding_vectors": 410, "milvus_database_creates": 1, "milvus_collection_creates": 1, "milvus_insert_batches": 13, "milvus_inserted_vectors": 410, "vector_search": 0, "rerank": 0, "evidence_promotion": 0},
        "execution_gate": {"presence_reproof_required": True, "ranking_successor_authorized": False},
    }
    terminal["result_digest"] = canonical_digest(terminal)
    clients = iter([_PresenceClient(present=historical), _PresenceClient(present=supplemental)])
    result = build_real_presence_proof(
        repo_root=ROOT,
        policy=policy,
        build_policy=build_policy,
        terminal_result=terminal,
        client_factory=lambda **_: next(clients),
    )
    validate_real_presence_proof(result)
    assert result["unique_selected_targets_present"] == 10
    assert result["row_weighted_satisfied_count"] == 18
    assert result["observed_calls"]["milvus_metadata_queries"] == 20


def test_presence_proof_fails_when_one_target_is_missing(tmp_path: Path) -> None:
    policy, build_policy, _ = _loaded()
    diagnostic = json.loads(
        (ROOT / build_policy["immutable_inputs"]["dense_index_diagnostic_ref"]).read_text(encoding="utf-8")
    )
    all_aliases = sorted({alias for row in diagnostic["rows"] for alias in row["selected_aliases"]})
    fake_db = tmp_path / "fake.db"
    fake_db.write_bytes(b"fake-milvus")
    terminal = {
        "schema_version": policy["terminal_result_schema"],
        "attempt_id": policy["attempt_id"],
        "status": "terminal_succeeded_real_incremental_dense_build",
        "automatic_retry": False,
        "build": {"terminal_entity_count": 410, "historical_collection_write_count": 0, "private_db_ref": fake_db.as_posix(), "private_db_bytes": fake_db.stat().st_size, "private_db_sha256": __import__("hashlib").sha256(fake_db.read_bytes()).hexdigest(), "collection_name": policy["private_execution"]["collection_name"]},
        "observed_calls": {"network": 0, "provider": 0, "llm_model": 0, "document_fetch": 0, "embedding_model_loads": 1, "embedding_batches": 13, "embedding_model_micro_batches": 52, "embedding_vectors": 410, "milvus_database_creates": 1, "milvus_collection_creates": 1, "milvus_insert_batches": 13, "milvus_inserted_vectors": 410, "vector_search": 0, "rerank": 0, "evidence_promotion": 0},
        "execution_gate": {"presence_reproof_required": True, "ranking_successor_authorized": False},
    }
    terminal["result_digest"] = canonical_digest(terminal)
    clients = iter([_PresenceClient(present=set(all_aliases[:-1])), _PresenceClient(present=set())])
    with pytest.raises(
        S1InternalSupplementalDenseExecutionError,
        match="supplemental_dense_real_presence_gate_failed",
    ):
        build_real_presence_proof(
            repo_root=ROOT,
            policy=policy,
            build_policy=build_policy,
            terminal_result=terminal,
            client_factory=lambda **_: next(clients),
        )
