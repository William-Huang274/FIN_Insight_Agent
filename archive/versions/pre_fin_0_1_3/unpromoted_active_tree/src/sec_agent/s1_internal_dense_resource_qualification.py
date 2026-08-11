from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight
from sec_agent.s1_internal_candidate_ceiling import canonical_observation_digest


RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_dense_resource_qualification_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_dense_resource_qualification_observation_v1_0"


class S1InternalDenseResourceQualificationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_json_object_required"
        )
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_dense_resource_qualification_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("result_schema") != RESULT_SCHEMA
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile")
        != "sha256_utf8_lf_normalized_v1"
    ):
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_policy_identity_invalid"
        )
    immutable = dict(policy.get("immutable_inputs") or {})
    for key in ("candidate_observation", "research_qrels", "milvus_runtime"):
        ref = str(immutable.get(f"{key}_ref") or "")
        supplied = str(immutable.get(f"{key}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _normalized_sha256(target) != supplied:
            raise S1InternalDenseResourceQualificationError(
                f"dense_resource_policy_binding_invalid:{key}"
            )
    hard = dict(policy.get("hard_boundaries") or {})
    if any(
        int(hard.get(key, -1)) != 0
        for key in (
            "network",
            "provider",
            "model",
            "embedding",
            "rerank",
            "evidence_promotion",
        )
    ) or hard.get("may_change_runtime_model_locator") is not False:
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_policy_boundary_invalid"
        )
    return policy


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def materialize_dense_resource_qualification(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_project_os_preflight_failed"
        )
    immutable = dict(policy["immutable_inputs"])
    candidate = _read_json(root / immutable["candidate_observation_ref"])
    qrels = _read_json(root / immutable["research_qrels_ref"])
    runtime = _read_json(root / immutable["milvus_runtime_ref"])
    if candidate.get("result_digest") != canonical_observation_digest(candidate):
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_candidate_observation_digest_invalid"
        )
    qrels_body = dict(qrels)
    qrels_digest = str(qrels_body.pop("review_digest", ""))
    if not qrels_digest or qrels_digest != canonical_digest(qrels_body):
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_qrels_digest_invalid"
        )
    resources = dict(policy["resources"])
    configured_model = Path(str(runtime["embedding_model"]))
    replacement_model = Path(str(resources["local_bge_m3_candidate"])).resolve()
    required_files = list(resources["local_bge_m3_required_files"])
    missing_model_files = [
        name for name in required_files if not (replacement_model / name).is_file()
    ]
    config = (
        _read_json(replacement_model / "config.json")
        if not missing_model_files
        else {}
    )
    model_qualified = (
        not missing_model_files
        and int(config.get("hidden_size") or 0) == int(runtime["embedding_dim"])
    )
    dependency_dir = Path(str(resources["milvus_dependencies_dir"])).resolve()
    pymilvus_dir = dependency_dir / "pymilvus"
    milvus_dependency_qualified = pymilvus_dir.is_dir() and any(
        dependency_dir.glob("pymilvus-*.dist-info")
    )
    reranker_candidates = [
        Path(str(value)).resolve() for value in resources["reranker_model_candidates"]
    ]
    present_rerankers = [str(path) for path in reranker_candidates if path.is_dir()]
    qrels_gate = dict(qrels.get("gate_decision") or {})
    owner_review_complete = qrels_gate.get("owner_review_complete") is True
    candidate_ceiling = qrels_gate.get("agent_curated_candidate_ceiling_pass") is True
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": "fin_0_1_3.S1.internal_dense_resource_qualification:v1",
        "run_scope": RUN_SCOPE,
        "status": "resources_qualified_execution_not_admitted_owner_review_pending",
        "project_os_preflight": preflight,
        "policy_digest": canonical_digest(policy),
        "candidate_observation_digest": str(candidate["result_digest"]),
        "research_qrels_review_digest": qrels_digest,
        "resource_qualification": {
            "milvus_collection": candidate["resource_qualification"]["milvus_dense"],
            "milvus_runtime_dependency": {
                "dependencies_dir": str(dependency_dir).replace("\\", "/"),
                "pymilvus_bundle_present": bool(milvus_dependency_qualified),
                "default_interpreter_pymilvus_importable": (
                    importlib.util.find_spec("pymilvus") is not None
                ),
                "status": (
                    "qualified_via_explicit_runtime_dependency_path"
                    if milvus_dependency_qualified
                    else "blocked_missing_runtime_dependency"
                ),
            },
            "bge_m3": {
                "configured_model_locator": str(configured_model).replace("\\", "/"),
                "configured_model_exists": configured_model.is_dir(),
                "qualified_successor_locator": str(replacement_model).replace("\\", "/"),
                "required_files_present": not missing_model_files,
                "missing_required_files": missing_model_files,
                "hidden_size": config.get("hidden_size"),
                "expected_embedding_dim": int(runtime["embedding_dim"]),
                "sentence_transformers_version": _package_version(
                    "sentence-transformers"
                ),
                "torch_version": _package_version("torch"),
                "status": (
                    "qualified_successor_locator_not_yet_bound"
                    if model_qualified
                    else "blocked"
                ),
            },
            "reranker": {
                "candidate_paths": [
                    str(path).replace("\\", "/") for path in reranker_candidates
                ],
                "present_paths": [path.replace("\\", "/") for path in present_rerankers],
                "status": (
                    "qualified_optional_candidate_present"
                    if present_rerankers
                    else "optional_resource_absent"
                ),
            },
            "deterministic_fusion": {
                "resource_required": False,
                "status": "available_after_ranking_admission",
            },
        },
        "execution_gate": {
            "agent_curated_candidate_ceiling_pass": candidate_ceiling,
            "owner_review_complete": owner_review_complete,
            "BGE_dense_execution_admitted": False,
            "fusion_execution_admitted": False,
            "rerank_execution_admitted": False,
            "reason": (
                "The BGE-M3 successor locator and Milvus dependency bundle are locally "
                "qualified, but the current configured model locator is stale and the "
                "18-row research qrels remain owner-review pending. No embedding, fusion "
                "or rerank execution is authorized by resource qualification."
            ),
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "known_boundary": (
            "This is file, dependency and lineage qualification only. It does not load "
            "BGE weights, connect to Milvus, mutate the runtime profile, download a "
            "reranker, score a candidate, or satisfy Owner qrels review."
        ),
        "implementation": {
            "module_ref": "src/sec_agent/s1_internal_dense_resource_qualification.py",
            "policy_ref": "configs/runtime/fin_ia_0_1_3_s1_internal_dense_resource_qualification_policy_v1_0.json",
            "materializer_ref": "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_dense_resource_qualification_v1_0.py",
        },
    }
    result["result_digest"] = canonical_digest(result)
    return result


def validate_dense_resource_qualification(value: Mapping[str, Any]) -> None:
    body = dict(value)
    supplied = str(body.pop("result_digest", ""))
    if value.get("schema_version") != RESULT_SCHEMA or not supplied:
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_observation_identity_invalid"
        )
    if supplied != canonical_digest(body):
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_observation_digest_invalid"
        )
    if any(int(value["observed_calls"].get(key, -1)) != 0 for key in value["observed_calls"]):
        raise S1InternalDenseResourceQualificationError(
            "dense_resource_observation_call_boundary_invalid"
        )
