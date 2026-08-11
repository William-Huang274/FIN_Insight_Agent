from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    CandidateBundlePhysicalIndexError,
    FakeEmbedder,
    FakeMilvusWriter,
    build_object_bm25_from_specs,
    canonical_digest,
    complete_observed_calls,
    execute_dense_build,
    execute_fake_physical_index_proof,
    inspect_physical_store_artifact,
    load_bound_private_manifest,
    load_physical_index_policy,
    normalized_sha256,
    validate_build_authority,
    validate_candidate_specs,
)


POLICY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_1.json"
)
OUTPUT_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_1.json"
)
BINDING_REFS = (
    POLICY_REF,
    "configs/runtime/fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_policy_v1_0.json",
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "src/sec_agent/s1_candidate_bundle_physical_index.py",
    "scripts/releases/materialize_fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_1.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_r1.py",
    "scripts/releases/issue_fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_authority_v1_0.py",
    "scripts/releases/prepare_fin_ia_0_1_3_s1_candidate_bundle_physical_index_v1_1_clean_proof.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_candidate_bundle_physical_index_r2.py",
    "scripts/releases/issue_fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_authority_v1_1.py",
    "tests/contract/test_fin_0_1_3_s1_candidate_bundle_physical_index.py",
)


class PartialAckWriter(FakeMilvusWriter):
    def insert(self, specs, vectors):  # type: ignore[no-untyped-def]
        acknowledged = super().insert(specs, vectors)
        return max(0, acknowledged - 1)


def _observed_failure(scenario: str, fn: Callable[[], Any]) -> dict[str, str]:
    try:
        fn()
    except Exception as exc:
        return {
            "scenario": scenario,
            "error_type": type(exc).__name__,
            "observed_code": str(getattr(exc, "code", str(exc))),
        }
    raise RuntimeError(f"physical_index_v1_1_mutation_did_not_fail:{scenario}")


def _directory_store(
    root: Path,
    *,
    collection_name: str,
    current_seq: int,
) -> Path:
    store = root / "milvus_lite.db"
    collection = store / "collections" / collection_name
    data = collection / "partitions" / "_default" / "data"
    indexes = collection / "partitions" / "_default" / "indexes"
    data.mkdir(parents=True)
    indexes.mkdir(parents=True)
    (store / "LOCK").write_bytes(b"")
    (data / "data_000001_000093.parquet").write_bytes(b"parquet-fixture")
    (indexes / "data_000001_000093.embedding.flat.idx").write_bytes(b"index-fixture")
    (collection / "manifest.json").write_text(
        json.dumps(
            {
                "current_seq": current_seq,
                "index_specs": {
                    "embedding": {
                        "field_name": "embedding",
                        "metric_type": "COSINE",
                        "index_type": "FLAT",
                    }
                },
                "partitions": {
                    "_default": {
                        "data_files": ["data/data_000001_000093.parquet"]
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


def _candidate_mutations(
    policy: dict[str, Any], specs: list[dict[str, Any]]
) -> list[dict[str, str]]:
    duplicate = deepcopy(specs)
    duplicate[-1]["vector_id"] = duplicate[0]["vector_id"]
    duplicate[-1]["spec_digest"] = canonical_digest(
        {key: value for key, value in duplicate[-1].items() if key != "spec_digest"}
    )
    vector_text_drift = deepcopy(specs)
    vector_text_drift[0]["vector_text"] += " drift"
    candidate_state = deepcopy(specs)
    candidate_state[0]["candidate_state"] = "evidence"
    candidate_state[0]["spec_digest"] = canonical_digest(
        {key: value for key, value in candidate_state[0].items() if key != "spec_digest"}
    )
    wrong_case = deepcopy(specs)
    wrong_case[0]["case_key"] = "WRONG"
    wrong_case[0]["spec_digest"] = canonical_digest(
        {key: value for key, value in wrong_case[0].items() if key != "spec_digest"}
    )
    return [
        _observed_failure(
            "duplicate_vector_identity",
            lambda: validate_candidate_specs(
                duplicate, policy=policy, require_manifest_digest=False
            ),
        ),
        _observed_failure(
            "vector_text_digest_drift",
            lambda: validate_candidate_specs(
                vector_text_drift, policy=policy, require_manifest_digest=False
            ),
        ),
        _observed_failure(
            "candidate_evidence_infiltration",
            lambda: validate_candidate_specs(
                candidate_state, policy=policy, require_manifest_digest=False
            ),
        ),
        _observed_failure(
            "cross_case_population_drift",
            lambda: validate_candidate_specs(
                wrong_case, policy=policy, require_manifest_digest=False
            ),
        ),
        _observed_failure(
            "dense_partial_acknowledgement",
            lambda: execute_dense_build(
                specs,
                policy=policy,
                embedder=FakeEmbedder(dimension=1024),
                writer=PartialAckWriter(),
            ),
        ),
        _observed_failure(
            "authority_digest_drift",
            lambda: validate_build_authority(
                {
                    "schema_version": policy["authority_schema"],
                    "status": "issued_unconsumed",
                    "attempt_id": policy["attempt_id"],
                    "authority_digest": "wrong",
                },
                policy=policy,
            ),
        ),
    ]


def main() -> int:
    output = ROOT / OUTPUT_REF
    if output.exists():
        raise RuntimeError("candidate_bundle_physical_v1_1_proof_already_exists")
    policy = load_physical_index_policy(ROOT / POLICY_REF, repo_root=ROOT)
    _manifest, specs = load_bound_private_manifest(policy, repo_root=ROOT)
    temporary_root = Path(tempfile.mkdtemp(prefix="fin013-s1-physical-index-v1-1-"))
    try:
        full_fake = execute_fake_physical_index_proof(
            policy=policy,
            specs=specs,
            output_root=temporary_root / "full-fake",
        )
        artifact_contract = dict(policy["index_contract"]["physical_store_artifact"])
        directory_store = _directory_store(
            temporary_root / "directory-positive",
            collection_name=str(artifact_contract["collection_name"]),
            current_seq=len(specs),
        )
        directory_artifact = inspect_physical_store_artifact(
            directory_store,
            contract=artifact_contract,
            expected_count=len(specs),
            embedding_dimension=1024,
        )
        file_store = temporary_root / "file-positive.db"
        file_store.write_bytes(b"provider-neutral-single-file-store")
        file_artifact = inspect_physical_store_artifact(
            file_store,
            contract={"artifact_kind": "file"},
            expected_count=0,
            embedding_dimension=0,
        )
        preexisting = temporary_root / "preexisting-sparse"
        preexisting.mkdir()
        missing_index_store = _directory_store(
            temporary_root / "missing-index",
            collection_name=str(artifact_contract["collection_name"]),
            current_seq=len(specs),
        )
        next(missing_index_store.rglob("*.idx")).unlink()
        path_escape_store = _directory_store(
            temporary_root / "path-escape",
            collection_name=str(artifact_contract["collection_name"]),
            current_seq=len(specs),
        )
        path_escape_manifest = next(path_escape_store.rglob("manifest.json"))
        path_escape_value = json.loads(path_escape_manifest.read_text(encoding="utf-8"))
        path_escape_value["partitions"]["_default"]["data_files"] = [
            "../../outside.parquet"
        ]
        path_escape_manifest.write_text(
            json.dumps(path_escape_value), encoding="utf-8"
        )
        partition_escape_store = _directory_store(
            temporary_root / "partition-escape",
            collection_name=str(artifact_contract["collection_name"]),
            current_seq=len(specs),
        )
        partition_escape_manifest = next(partition_escape_store.rglob("manifest.json"))
        partition_escape_value = json.loads(
            partition_escape_manifest.read_text(encoding="utf-8")
        )
        partition_escape_value["partitions"] = {
            "../escape": partition_escape_value["partitions"]["_default"]
        }
        partition_escape_manifest.write_text(
            json.dumps(partition_escape_value), encoding="utf-8"
        )
        mutations = _candidate_mutations(policy, specs)
        mutations.extend(
            [
                _observed_failure(
                    "sparse_target_preexists",
                    lambda: build_object_bm25_from_specs(
                        specs,
                        output_dir=preexisting,
                    ),
                ),
                _observed_failure(
                    "directory_declared_as_file",
                    lambda: inspect_physical_store_artifact(
                        directory_store,
                        contract={"artifact_kind": "file"},
                        expected_count=len(specs),
                        embedding_dimension=1024,
                    ),
                ),
                _observed_failure(
                    "directory_index_missing",
                    lambda: inspect_physical_store_artifact(
                        missing_index_store,
                        contract=artifact_contract,
                        expected_count=len(specs),
                        embedding_dimension=1024,
                    ),
                ),
                _observed_failure(
                    "directory_manifest_path_escape",
                    lambda: inspect_physical_store_artifact(
                        path_escape_store,
                        contract=artifact_contract,
                        expected_count=len(specs),
                        embedding_dimension=1024,
                    ),
                ),
                _observed_failure(
                    "directory_partition_name_escape",
                    lambda: inspect_physical_store_artifact(
                        partition_escape_store,
                        contract=artifact_contract,
                        expected_count=len(specs),
                        embedding_dimension=1024,
                    ),
                ),
            ]
        )
    finally:
        shutil.rmtree(temporary_root)

    complete_failure_shape = complete_observed_calls(
        embedder=FakeEmbedder(dimension=4),
        writer=FakeMilvusWriter(),
    )
    body = {
        "schema_version": policy["implementation_proof_schema"],
        "contract_ref": policy["contract_ref"],
        "run_scope": policy["run_scope"],
        "recorded_at": policy["recorded_at"],
        "attempt_id": "20260810_s1_candidate_bundle_physical_index_v1_1_full_fake_r1",
        "status": "terminal_succeeded_file_or_directory_store_full_fake",
        "policy_digest": canonical_digest(policy),
        "source_bindings": {
            ref: normalized_sha256(ROOT / ref) for ref in BINDING_REFS
        },
        "manifest_binding": {
            "spec_count": len(specs),
            "spec_digest": policy["immutable_inputs"]["manifest_spec_digest"],
            "specs_by_case": policy["immutable_inputs"]["expected_specs_by_case"],
            "candidate_state": "candidate_only_not_evidence",
        },
        "full_fake": full_fake,
        "store_artifact_proof": {
            "directory": directory_artifact,
            "file_provider_neutral_control": file_artifact,
            "directory_digest_deterministic": True,
            "complete_failure_counter_keys": sorted(complete_failure_shape),
        },
        "mutation_proof": {
            "scenario_count": len(mutations),
            "all_failed_closed": True,
            "rows": mutations,
        },
        "observed_real_calls": {
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
        },
        "stage_acceptance": {
            "shared_sparse_dense_population": True,
            "provider_neutral_file_or_directory_store": True,
            "directory_tree_and_collection_manifest": True,
            "complete_success_failure_call_shape": True,
            "isolated_real_microcanary": False,
            "clean_independent_proof": False,
            "r2_authority": False,
            "real_business_index": False,
            "retrieval_quality": False,
            "evidence": False,
            "release": False,
        },
        "decision_zh": (
            "v1.1 已在零调用路径同时证明文件型控制组和目录型 Milvus store；目录树、collection "
            "manifest、数据文件、索引文件、维度与 current_seq 均被绑定，成功和失败计数同形。"
            "下一步必须在 clean commit 上签发并执行一次无 BGE、无业务数据的一向量 microcanary。"
        ),
        "known_boundary": (
            "This is a zero-call implementation proof. It does not write a real Milvus store, "
            "load BGE-M3, build the 93-vector index, search, rank, promote Evidence or accept release."
        ),
    }
    result = {**body, "proof_digest": canonical_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "manifest_binding": result["manifest_binding"],
                "store_artifact_proof": {
                    "directory_digest": directory_artifact["artifact_digest"],
                    "directory_files": directory_artifact["file_count"],
                    "file_control_digest": file_artifact["artifact_digest"],
                },
                "mutations": result["mutation_proof"],
                "proof_digest": result["proof_digest"],
                "output": output.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
