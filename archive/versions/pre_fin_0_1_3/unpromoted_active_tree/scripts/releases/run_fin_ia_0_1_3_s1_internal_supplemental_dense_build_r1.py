from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_supplemental_dense_execution import (  # noqa: E402
    TERMINAL_RESULT_SCHEMA,
    LocalBGEEmbedder,
    MilvusIndexWriter,
    load_supplemental_dense_execution_policy,
    validate_clean_execution_authority,
    validate_terminal_result,
)
from sec_agent.s1_internal_supplemental_dense_index import (  # noqa: E402
    compile_supplemental_vector_specs,
    execute_index_build_plan,
    validate_target_isolation,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_internal_supplemental_dense_execution_policy_v1_0.json"


def _write_result(path: Path, result: dict) -> None:
    result["result_digest"] = canonical_digest(result)
    validate_terminal_result(result)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    policy, build_policy, zero_proof = load_supplemental_dense_execution_policy(
        POLICY_PATH, repo_root=ROOT
    )
    public = dict(policy["public_outputs"])
    result_path = ROOT / str(public["terminal_result_ref"])
    if result_path.exists():
        raise RuntimeError("supplemental_dense_terminal_result_already_exists")
    authority = json.loads((ROOT / str(public["authority_ref"])).read_text(encoding="utf-8"))
    validate_clean_execution_authority(
        authority, policy=policy, repo_root=ROOT, require_clean_synced=True
    )
    preflight = run_project_os_preflight(ROOT, run_scope=str(policy["run_scope"]))
    if preflight.get("status") != "pass":
        raise RuntimeError("supplemental_dense_execution_project_os_preflight_failed")
    private = dict(policy["private_execution"])
    working_root = (ROOT / str(private["working_root"])).resolve()
    final_root = (ROOT / str(private["final_root"])).resolve()
    working_db = working_root / str(private["milvus_db_filename"])
    final_db = final_root / str(private["milvus_db_filename"])
    runtime = json.loads(
        (ROOT / str(build_policy["immutable_inputs"]["historical_milvus_runtime_ref"])).read_text(encoding="utf-8")
    )
    validate_target_isolation(
        build_policy, repo_root=ROOT, historical_runtime=runtime
    )
    if working_root.exists() or final_root.exists():
        raise RuntimeError("supplemental_dense_execution_private_target_preexists")
    started = time.perf_counter()
    phase = "prepare_private_working_root"
    writer: MilvusIndexWriter | None = None
    embedder: LocalBGEEmbedder | None = None
    try:
        working_root.parent.mkdir(parents=True, exist_ok=True)
        working_root.mkdir()
        phase = "compile_source_specs"
        specs, _ = compile_supplemental_vector_specs(build_policy, repo_root=ROOT)
        spec_digest = canonical_digest(specs)
        if spec_digest != zero_proof["source_inventory"]["vector_spec_terminal_digest"]:
            raise RuntimeError("supplemental_dense_execution_vector_spec_drift")
        resources = dict(policy["resource_bindings"])
        phase = "load_local_bge_m3"
        embedder = LocalBGEEmbedder(
            model_path=str(resources["embedding_model"]),
            expected_dim=int(resources["expected_embedding_dim"]),
            batch_size=int(resources["model_micro_batch_size"]),
            normalize=bool(resources["normalize_embeddings"]),
        )
        phase = "create_and_populate_working_milvus"
        writer = MilvusIndexWriter(
            uri=str(working_db),
            dependency_dir=str(resources["milvus_dependencies_dir"]),
        )
        build = execute_index_build_plan(
            specs, policy=build_policy, embed_batch=embedder, writer=writer
        )
        writer.close()
        phase = "atomic_publish_private_root"
        working_root.rename(final_root)
        if not final_db.is_file():
            raise RuntimeError("supplemental_dense_execution_published_db_missing")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        result = {
            "schema_version": TERMINAL_RESULT_SCHEMA,
            "contract_ref": "fin_0_1_3.S1.internal_supplemental_dense_execution:v1",
            "run_scope": str(policy["run_scope"]),
            "recorded_at": "2026-08-09",
            "attempt_id": str(policy["attempt_id"]),
            "status": "terminal_succeeded_real_incremental_dense_build",
            "automatic_retry": False,
            "authority_digest": str(authority["authority_digest"]),
            "implementation_commit": str(authority["implementation"]["commit"]),
            "vector_spec_terminal_digest": spec_digest,
            "resource": {
                "embedding_model": str(resources["embedding_model"]),
                "device": embedder.device,
                "embedding_dim": int(resources["expected_embedding_dim"]),
                "model_load_ms": embedder.model_load_ms,
                "embedding_ms": round(embedder.embedding_ms, 3),
                "wall_time_ms": elapsed_ms,
            },
            "build": {
                **build,
                "private_db_ref": final_db.relative_to(ROOT).as_posix(),
                "private_db_bytes": final_db.stat().st_size,
                "private_db_sha256": hashlib.sha256(final_db.read_bytes()).hexdigest(),
                "collection_name": str(private["collection_name"]),
                "terminal_entity_count": int(build["terminal_count"]),
                "historical_collection_write_count": 0,
                "writer_calls": dict(writer.calls),
            },
            "observed_calls": {
                "network": 0,
                "provider": 0,
                "llm_model": 0,
                "document_fetch": 0,
                "embedding_model_loads": 1,
                "embedding_batches": embedder.embedding_calls,
                "embedding_model_micro_batches": embedder.embedding_micro_batches,
                "embedding_vectors": embedder.embedding_vectors,
                "milvus_database_creates": writer.calls["database_create"],
                "milvus_collection_creates": writer.calls["collection_create"],
                "milvus_insert_batches": writer.calls["insert_batches"],
                "milvus_inserted_vectors": writer.calls["inserted_vectors"],
                "vector_search": 0,
                "rerank": 0,
                "evidence_promotion": 0,
            },
            "execution_gate": {
                "real_incremental_build_passed": True,
                "presence_reproof_required": True,
                "ranking_successor_authorized": False,
            },
            "known_boundary": "The supplemental collection exists and has 410 entities. Selected-target physical presence still requires a separate read-only proof; semantic ranking and downstream product quality are not established.",
        }
        _write_result(result_path, result)
        print(json.dumps({"status": result["status"], "attempt_id": result["attempt_id"], "device": result["resource"]["device"], "build": result["build"], "result_digest": result["result_digest"]}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        result = {
            "schema_version": TERMINAL_RESULT_SCHEMA,
            "contract_ref": "fin_0_1_3.S1.internal_supplemental_dense_execution:v1",
            "run_scope": str(policy["run_scope"]),
            "recorded_at": "2026-08-09",
            "attempt_id": str(policy["attempt_id"]),
            "status": "terminal_failed_real_incremental_dense_build_no_retry",
            "automatic_retry": False,
            "authority_digest": str(authority["authority_digest"]),
            "implementation_commit": str(authority["implementation"]["commit"]),
            "failure": {"phase": phase, "error_type": type(exc).__name__, "error_code": str(exc)},
            "private_state": {
                "working_root_ref": working_root.relative_to(ROOT).as_posix(),
                "working_root_exists": working_root.exists(),
                "final_root_ref": final_root.relative_to(ROOT).as_posix(),
                "final_root_exists": final_root.exists(),
            },
            "observed_calls": {
                "network": 0,
                "provider": 0,
                "llm_model": 0,
                "document_fetch": 0,
                "embedding_model_loads": int(embedder is not None),
                "embedding_batches": int(embedder.embedding_calls if embedder else 0),
                "embedding_model_micro_batches": int(
                    embedder.embedding_micro_batches if embedder else 0
                ),
                "embedding_vectors": int(embedder.embedding_vectors if embedder else 0),
                "milvus_database_creates": int((writer.calls if writer else {}).get("database_create", 0)),
                "milvus_collection_creates": int((writer.calls if writer else {}).get("collection_create", 0)),
                "milvus_insert_batches": int((writer.calls if writer else {}).get("insert_batches", 0)),
                "milvus_inserted_vectors": int((writer.calls if writer else {}).get("inserted_vectors", 0)),
                "vector_search": 0,
                "rerank": 0,
                "evidence_promotion": 0,
            },
            "execution_gate": {"real_incremental_build_passed": False, "presence_reproof_required": False, "ranking_successor_authorized": False},
            "known_boundary": "Failure is immutable and no automatic retry or replacement attempt is authorized.",
        }
        _write_result(result_path, result)
        print(json.dumps({"status": result["status"], "failure": result["failure"], "result_digest": result["result_digest"]}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
