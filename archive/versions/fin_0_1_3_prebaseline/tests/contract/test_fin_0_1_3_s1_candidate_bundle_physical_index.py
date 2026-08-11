from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from retrieval.object_bm25_retriever import ObjectBM25Retriever  # noqa: E402
from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    CandidateBundlePhysicalIndexError,
    FakeEmbedder,
    FakeMilvusWriter,
    build_object_bm25_from_specs,
    canonical_digest,
    complete_observed_calls,
    execute_dense_build,
    execute_fake_physical_index_proof,
    load_bound_private_manifest,
    load_physical_index_policy,
    inspect_physical_store_artifact,
    validate_build_authority,
    validate_candidate_specs,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_0.json"
)
POLICY_V1_1_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_1.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_0.json"
)
AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_authority_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_result_v1_0.json"
)


def _policy() -> dict:
    return load_physical_index_policy(POLICY_PATH, repo_root=ROOT)


def _specs() -> list[dict]:
    _manifest, specs = load_bound_private_manifest(_policy(), repo_root=ROOT)
    return specs


def _directory_store(root: Path, *, collection_name: str, count: int = 3) -> Path:
    store = root / "milvus_lite.db"
    collection = store / "collections" / collection_name
    data = collection / "partitions" / "_default" / "data"
    indexes = collection / "partitions" / "_default" / "indexes"
    data.mkdir(parents=True)
    indexes.mkdir(parents=True)
    (store / "LOCK").write_bytes(b"")
    (data / "data_000001_000003.parquet").write_bytes(b"parquet-fixture")
    (indexes / "data_000001_000003.embedding.flat.idx").write_bytes(
        b"index-fixture"
    )
    (collection / "manifest.json").write_text(
        json.dumps(
            {
                "current_seq": count,
                "index_specs": {
                    "embedding": {
                        "field_name": "embedding",
                        "metric_type": "COSINE",
                        "index_type": "FLAT",
                    }
                },
                "partitions": {
                    "_default": {
                        "data_files": ["data/data_000001_000003.parquet"]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (collection / "schema.json").write_text(
        json.dumps(
            {
                "collection_name": collection_name,
                "fields": [{"name": "embedding", "dim": 1024}],
            }
        ),
        encoding="utf-8",
    )
    return store


def test_policy_binds_clean_manifest_and_linux_exact_once_boundary() -> None:
    policy = _policy()
    assert policy["immutable_inputs"]["expected_spec_count"] == 93
    assert policy["immutable_inputs"]["manifest_spec_digest"] == (
        "af1f2439bc78a22dc00f27e55594c01ac73bfd2c11fa7a8c57f6546549b14df9"
    )
    assert policy["runtime_contract"]["distribution"] == "Ubuntu-22.04"
    assert policy["runtime_contract"]["embedding_device"] == "cpu"
    assert policy["execution_ceiling"]["maximum_executions"] == 1
    assert policy["execution_ceiling"]["automatic_retry"] is False
    assert policy["stage_boundaries"]["may_search_vectors"] is False
    assert policy["stage_boundaries"]["may_claim_workbench_integration"] is False


def test_v1_1_policy_declares_fingerprint_bound_directory_store_and_fresh_r2() -> None:
    policy = load_physical_index_policy(POLICY_V1_1_PATH, repo_root=ROOT)
    store = policy["index_contract"]["physical_store_artifact"]
    assert policy["attempt_id"].endswith("_r2")
    assert policy["private_target"]["working_root"].endswith("attempt_r2_building")
    assert policy["private_target"]["final_root"].endswith("/v2")
    assert store["artifact_kind"] == "directory"
    assert store["profile_id"] == "pymilvus-3.0_milvus-lite-3.0_directory-store"
    assert policy["execution_ceiling"]["milvus_reopens"] == 1


def test_private_manifest_has_exact_shared_six_case_population() -> None:
    policy = _policy()
    manifest, specs = load_bound_private_manifest(policy, repo_root=ROOT)
    assert manifest["candidate_state"] == "candidate_only_not_evidence"
    assert len(specs) == 93
    assert canonical_digest(specs) == policy["immutable_inputs"]["manifest_spec_digest"]
    assert {tuple(spec["index_lanes"]) for spec in specs} == {
        ("object_bm25", "bge_m3_milvus")
    }
    assert len({spec["vector_id"] for spec in specs}) == 93


def test_object_bm25_is_readable_by_existing_retriever(tmp_path: Path) -> None:
    specs = _specs()
    index_root = tmp_path / "object-bm25"
    metadata = build_object_bm25_from_specs(specs, output_dir=index_root)
    assert metadata["records"] == 93
    retriever = ObjectBM25Retriever(index_root)
    try:
        rows = retriever.search(
            "DELL regulatory policy exposure NVIDIA",
            top_k=10,
            filters={"ticker": "DELL"},
        )
    finally:
        retriever.close()
    assert rows
    assert all(row["ticker"] == "DELL" for row in rows)
    assert all(row["record"]["metadata"]["candidate_state"] == "bundle_candidate_only_not_evidence" for row in rows)


def test_full_fake_sparse_dense_population_and_call_shape(tmp_path: Path) -> None:
    policy = _policy()
    result = execute_fake_physical_index_proof(
        policy=policy,
        specs=_specs(),
        output_root=tmp_path / "full-fake",
    )
    assert result["sparse"]["records"] == 93
    assert result["dense"]["terminal_count"] == 93
    assert result["dense"]["batch_count"] == 12
    assert result["dense"]["writer_calls"] == {
        "database_create": 1,
        "collection_create": 1,
        "insert_batches": 12,
        "inserted_vectors": 93,
        "flush": 2,
        "count": 2,
        "metadata_query": 1,
        "reopen": 1,
    }


def test_partial_dense_acknowledgement_fails_closed() -> None:
    class PartialWriter(FakeMilvusWriter):
        def insert(self, specs, vectors):  # type: ignore[no-untyped-def]
            return super().insert(specs, vectors) - 1

    policy = _policy()
    with pytest.raises(CandidateBundlePhysicalIndexError) as exc:
        execute_dense_build(
            _specs(),
            policy=policy,
            embedder=FakeEmbedder(dimension=1024),
            writer=PartialWriter(),
        )
    assert exc.value.code == "candidate_bundle_physical_dense_terminal_identity_mismatch"


def test_directory_store_artifact_binds_tree_collection_data_and_index(
    tmp_path: Path,
) -> None:
    collection_name = "fin_test_dense_v1"
    store = _directory_store(tmp_path, collection_name=collection_name)
    contract = {
        "artifact_kind": "directory",
        "collection_name": collection_name,
        "metric_type": "COSINE",
        "index_type": "FLAT",
    }
    first = inspect_physical_store_artifact(
        store,
        contract=contract,
        expected_count=3,
        embedding_dimension=1024,
    )
    second = inspect_physical_store_artifact(
        store,
        contract=contract,
        expected_count=3,
        embedding_dimension=1024,
    )
    assert first == second
    assert first["artifact_kind"] == "directory"
    assert first["collection_validation"]["current_seq"] == 3
    assert len(first["collection_validation"]["data_paths"]) == 1
    assert len(first["collection_validation"]["index_paths"]) == 1


def test_physical_store_artifact_wrong_kind_and_missing_index_fail_closed(
    tmp_path: Path,
) -> None:
    collection_name = "fin_test_dense_v1"
    store = _directory_store(tmp_path, collection_name=collection_name)
    contract = {
        "artifact_kind": "file",
        "collection_name": collection_name,
        "metric_type": "COSINE",
        "index_type": "FLAT",
    }
    with pytest.raises(CandidateBundlePhysicalIndexError) as exc:
        inspect_physical_store_artifact(
            store,
            contract=contract,
            expected_count=3,
            embedding_dimension=1024,
        )
    assert exc.value.code == "candidate_bundle_physical_store_artifact_kind_mismatch"

    contract["artifact_kind"] = "directory"
    next(store.rglob("*.idx")).unlink()
    with pytest.raises(CandidateBundlePhysicalIndexError) as exc:
        inspect_physical_store_artifact(
            store,
            contract=contract,
            expected_count=3,
            embedding_dimension=1024,
        )
    assert exc.value.code == "candidate_bundle_physical_store_collection_invariant_invalid"


def test_directory_store_artifact_rejects_partition_name_escape(
    tmp_path: Path,
) -> None:
    collection_name = "fin_test_dense_v1"
    store = _directory_store(tmp_path, collection_name=collection_name)
    manifest_path = store / "collections" / collection_name / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["partitions"] = {
        "../escape": manifest["partitions"]["_default"],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CandidateBundlePhysicalIndexError) as exc:
        inspect_physical_store_artifact(
            store,
            contract={
                "artifact_kind": "directory",
                "collection_name": collection_name,
                "metric_type": "COSINE",
                "index_type": "FLAT",
            },
            expected_count=3,
            embedding_dimension=1024,
        )
    assert exc.value.code == "candidate_bundle_physical_store_manifest_path_escape"


def test_file_store_artifact_remains_provider_neutral(tmp_path: Path) -> None:
    store = tmp_path / "store.db"
    store.write_bytes(b"single-file-backend")
    artifact = inspect_physical_store_artifact(
        store,
        contract={"artifact_kind": "file"},
        expected_count=0,
        embedding_dimension=0,
    )
    assert artifact["artifact_kind"] == "file"
    assert artifact["file_count"] == 1
    assert artifact["total_bytes"] == len(b"single-file-backend")


def test_directory_store_artifact_rejects_symlink(tmp_path: Path) -> None:
    collection_name = "fin_test_dense_v1"
    store = _directory_store(tmp_path, collection_name=collection_name)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    try:
        (store / "linked.bin").symlink_to(outside)
    except OSError:
        pytest.skip("host does not permit symlink creation")
    with pytest.raises(CandidateBundlePhysicalIndexError) as exc:
        inspect_physical_store_artifact(
            store,
            contract={
                "artifact_kind": "directory",
                "collection_name": collection_name,
                "metric_type": "COSINE",
                "index_type": "FLAT",
            },
            expected_count=3,
            embedding_dimension=1024,
        )
    assert (
        exc.value.code
        == "candidate_bundle_physical_directory_artifact_symlink_forbidden"
    )


def test_complete_call_receipt_has_same_shape_after_partial_progress() -> None:
    embedder = FakeEmbedder(dimension=4)
    writer = FakeMilvusWriter()
    writer.calls.update(
        {
            "database_create": 1,
            "collection_create": 1,
            "insert_batches": 2,
            "inserted_vectors": 5,
            "flush": 2,
            "count": 2,
            "metadata_query": 1,
            "reopen": 1,
        }
    )
    embedder.calls = 2
    embedder.vectors = 5
    calls = complete_observed_calls(embedder=embedder, writer=writer)
    assert calls["milvus_flushes"] == 2
    assert calls["milvus_count_reads"] == 2
    assert calls["milvus_metadata_queries"] == 1
    assert calls["milvus_reopens"] == 1
    assert calls["embedding_vectors"] == 5


def test_candidate_infiltration_and_duplicate_identity_fail_closed() -> None:
    policy = _policy()
    specs = _specs()
    mutated = [dict(item) for item in specs]
    mutated[0]["candidate_state"] = "evidence"
    mutated[0]["spec_digest"] = canonical_digest(
        {key: value for key, value in mutated[0].items() if key != "spec_digest"}
    )
    with pytest.raises(CandidateBundlePhysicalIndexError) as exc:
        validate_candidate_specs(mutated, policy=policy, require_manifest_digest=False)
    assert exc.value.code == "candidate_bundle_physical_spec_integrity_invalid"


def test_materialized_implementation_proof_preserves_product_boundary() -> None:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    body = {key: value for key, value in proof.items() if key != "proof_digest"}
    assert proof["proof_digest"] == canonical_digest(body)
    assert proof["status"] == "terminal_succeeded_full_fake_physical_index_implementation"
    assert proof["full_fake"]["sparse"]["records"] == 93
    assert proof["full_fake"]["dense"]["terminal_count"] == 93
    assert proof["mutation_proof"]["scenario_count"] == 7
    assert proof["mutation_proof"]["all_failed_closed"] is True
    assert proof["observed_real_calls"] == {
        "network": 0,
        "provider": 0,
        "llm_model": 0,
        "document_fetch": 0,
        "embedding_model_loads": 0,
        "embedding_vectors": 0,
        "milvus_read": 0,
        "milvus_write": 0,
        "vector_search": 0,
        "rerank": 0,
        "evidence_promotion": 0,
    }
    assert proof["stage_acceptance"]["clean_commit_authority_issuance"] is True
    assert proof["stage_acceptance"]["real_embedding_or_index_build"] is False
    assert proof["stage_acceptance"]["retrieval_quality"] is False


def test_authority_validation_requires_exact_digest_and_fresh_target() -> None:
    policy = _policy()
    runtime = policy["runtime_contract"]
    target = policy["private_target"]
    body = {
        "schema_version": policy["authority_schema"],
        "status": "issued_unconsumed",
        "run_scope": policy["run_scope"],
        "attempt_id": policy["attempt_id"],
        "policy_digest": canonical_digest(policy),
        "maximum_executions": 1,
        "automatic_retry": False,
        "implementation": {
            "commit": "a" * 40,
            "clean": True,
            "synced": True,
            "ahead": 0,
            "behind": 0,
            "bindings": [{"ref": "placeholder", "sha256": "placeholder"}],
        },
        "manifest_binding": {
            "spec_count": 93,
            "spec_digest": policy["immutable_inputs"]["manifest_spec_digest"],
            "private_manifest_file_sha256": policy["immutable_inputs"][
                "private_manifest_file_sha256"
            ],
            "candidate_state": "candidate_only_not_evidence",
        },
        "environment_qualification": {
            "qualified": True,
            "python_executable": runtime["python_executable"],
            "packages": runtime["required_packages"],
            "model_files": runtime["required_model_files"],
            "embedding_device": runtime["embedding_device"],
            "observed_calls": {"network": 0, "model": 0},
        },
        "private_target": {
            "working_root": target["working_root"],
            "working_root_absent": True,
            "final_root": target["final_root"],
            "final_root_absent": True,
            "disk_free_bytes": 20 * 1024**3,
        },
        "execution_ceiling": policy["execution_ceiling"],
        "preserved_boundaries": policy["stage_boundaries"],
    }
    authority = {**body, "authority_digest": canonical_digest(body)}
    assert validate_build_authority(authority, policy=policy)["status"] == "issued_unconsumed"
    authority["private_target"]["final_root_absent"] = False
    with pytest.raises(CandidateBundlePhysicalIndexError):
        validate_build_authority(authority, policy=policy)


def test_materialized_authority_binds_clean_environment_and_one_r1() -> None:
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    validated = validate_build_authority(
        authority,
        policy=_policy(),
    )
    assert validated["status"] == "issued_unconsumed"
    assert validated["implementation"]["commit"] == (
        "566d5223dca1d6d28dc802cd4bfa4fa6cc1a477e"
    )
    assert validated["maximum_executions"] == 1
    assert validated["automatic_retry"] is False
    assert validated["manifest_binding"]["spec_count"] == 93
    assert validated["environment_qualification"]["packages"]["torch"] == "2.10.0+cpu"
    assert validated["environment_qualification"]["milvus_manifest_source"][
        "commit_primitive"
    ] == "os.rename"
    assert validated["private_target"]["working_root_absent"] is True
    assert validated["private_target"]["final_root_absent"] is True


def test_materialized_r1_failure_is_consumed_and_not_product_index_success() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    body = {key: value for key, value in result.items() if key != "result_digest"}
    assert result["result_digest"] == canonical_digest(body)
    assert result["status"] == "terminal_failed_physical_sparse_dense_build_no_retry"
    assert result["automatic_retry"] is False
    assert result["failure"] == {
        "error_code": "candidate_bundle_physical_dense_database_missing",
        "error_type": "CandidateBundlePhysicalIndexError",
        "phase": "build_bge_m3_milvus",
    }
    assert result["observed_calls"]["embedding_model_loads"] == 1
    assert result["observed_calls"]["embedding_vectors"] == 93
    assert result["observed_calls"]["milvus_inserted_vectors"] == 93
    assert result["private_state"]["working_root_exists"] is True
    assert result["private_state"]["final_root_exists"] is False
    assert result["stage_acceptance"]["physical_sparse_index"] is False
    assert result["stage_acceptance"]["physical_dense_index"] is False
    assert result["stage_acceptance"]["retrieval_quality"] is False
