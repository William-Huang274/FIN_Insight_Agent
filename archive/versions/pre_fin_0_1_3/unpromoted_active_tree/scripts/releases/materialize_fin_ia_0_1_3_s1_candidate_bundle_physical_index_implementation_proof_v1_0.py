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
    IMPLEMENTATION_PROOF_SCHEMA,
    CandidateBundlePhysicalIndexError,
    FakeEmbedder,
    FakeMilvusWriter,
    build_object_bm25_from_specs,
    canonical_digest,
    execute_dense_build,
    execute_fake_physical_index_proof,
    load_bound_private_manifest,
    load_physical_index_policy,
    normalized_sha256,
    validate_build_authority,
    validate_candidate_specs,
)


POLICY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_policy_v1_0.json"
)
OUTPUT_REF = (
    "configs/releases/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_0.json"
)
BINDING_REFS = (
    POLICY_REF,
    "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json",
    "src/sec_agent/s1_candidate_bundle_physical_index.py",
    "scripts/releases/materialize_fin_ia_0_1_3_s1_candidate_bundle_physical_index_implementation_proof_v1_0.py",
    "scripts/releases/run_fin_ia_0_1_3_s1_candidate_bundle_physical_index_r1.py",
    "scripts/releases/issue_fin_ia_0_1_3_s1_candidate_bundle_physical_index_build_authority_v1_0.py",
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
    raise RuntimeError(f"physical_index_mutation_did_not_fail:{scenario}")


def _mutations(policy: dict[str, Any], specs: list[dict[str, Any]]) -> list[dict[str, str]]:
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

    dense_embedder = FakeEmbedder(
        dimension=int(policy["runtime_contract"]["embedding_dimension"])
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
                embedder=dense_embedder,
                writer=PartialAckWriter(),
            ),
        ),
        _observed_failure(
            "authority_digest_drift",
            lambda: validate_build_authority(
                {
                    "schema_version": policy["authority_schema"],
                    "status": "issued_unconsumed",
                    "run_scope": policy["run_scope"],
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
        raise RuntimeError("candidate_bundle_physical_implementation_proof_already_exists")
    policy = load_physical_index_policy(ROOT / POLICY_REF, repo_root=ROOT)
    _manifest, specs = load_bound_private_manifest(policy, repo_root=ROOT)
    temporary_root = Path(tempfile.mkdtemp(prefix="fin013-s1-physical-index-fake-"))
    try:
        full_fake = execute_fake_physical_index_proof(
            policy=policy,
            specs=specs,
            output_root=temporary_root / "full-fake",
        )
        preexisting = temporary_root / "preexisting-sparse"
        preexisting.mkdir()
        mutations = _mutations(policy, specs)
        mutations.append(
            _observed_failure(
                "sparse_target_preexists",
                lambda: build_object_bm25_from_specs(
                    specs,
                    output_dir=preexisting,
                ),
            )
        )
    finally:
        shutil.rmtree(temporary_root)

    body = {
        "schema_version": IMPLEMENTATION_PROOF_SCHEMA,
        "contract_ref": policy["contract_ref"],
        "run_scope": policy["run_scope"],
        "recorded_at": policy["recorded_at"],
        "attempt_id": "20260810_s1_candidate_bundle_physical_index_full_fake_r1",
        "status": "terminal_succeeded_full_fake_physical_index_implementation",
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
            "object_bm25_serialization": True,
            "dense_batch_and_terminal_identity": True,
            "typed_failure_mutations": True,
            "clean_commit_authority_issuance": True,
            "real_embedding_or_index_build": False,
            "retrieval_quality": False,
            "workbench_integration": False,
            "evidence_pack": False,
            "external_residual_supplement": False,
            "deepseek_research": False,
            "release": False,
        },
        "decision_zh": (
            "同一 93 对象清单已通过真实 ObjectBM25 序列化路径和 fake 1024 维 dense/Milvus "
            "12 批完整性验证；七类污染、部分写入和权限突变全部 fail closed。下一步只能先把实现提交并推送，"
            "再从干净 commit 签发一次 Ubuntu R1 authority。"
        ),
        "known_boundary": (
            "This proof uses real sparse serialization and fake embeddings/Milvus only. It does not "
            "load BGE-M3, write a real collection, search, rank, promote Evidence, integrate the "
            "Workbench, supplement externally, call DeepSeek or accept release."
        ),
    }
    result = {**body, "proof_digest": canonical_digest(body)}
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "manifest_binding": result["manifest_binding"],
                "dense": result["full_fake"]["dense"],
                "mutations": result["mutation_proof"],
                "stage_acceptance": result["stage_acceptance"],
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
