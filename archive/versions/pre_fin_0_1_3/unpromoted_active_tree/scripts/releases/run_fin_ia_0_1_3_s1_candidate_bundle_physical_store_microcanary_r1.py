from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_candidate_bundle_physical_index import (  # noqa: E402
    CandidateBundlePhysicalIndexError,
    MilvusCandidateBundleWriter,
    canonical_digest,
    canonical_tree_manifest,
    complete_observed_calls,
    inspect_physical_store_artifact,
    normalized_sha256,
)


POLICY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_policy_v1_0.json"
)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateBundlePhysicalIndexError(code)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "physical_store_microcanary_json_object_required")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def load_policy(path: Path) -> dict[str, Any]:
    policy = _read_json(path)
    runtime = dict(policy.get("runtime") or {})
    store = dict(policy.get("store_contract") or {})
    target = dict(policy.get("private_target") or {})
    prefix = str(target.get("target_prefix") or "")
    _require(
        policy.get("schema_version")
        == "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_policy_v1_0"
        and policy.get("contract_ref")
        == "fin_0_1_3.S1.physical_store_artifact_microcanary:v1"
        and policy.get("run_scope")
        == "S1_IMMUTABLE_SUPPLEMENTAL_DENSE_INDEX_REPLACEMENT_BUILD"
        and runtime.get("distribution") == "Ubuntu-22.04"
        and runtime.get("required_packages")
        == {"pymilvus": "3.0.0", "milvus-lite": "3.0"}
        and store.get("profile_id")
        == "pymilvus-3.0_milvus-lite-3.0_directory-store"
        and store.get("artifact_kind") == "directory"
        and int(store.get("expected_count") or 0) == 1
        and int(store.get("embedding_dimension") or 0) == 4
        and prefix.startswith("/home/william/.cache/fin_insight/")
        and str(target.get("working_root") or "").startswith(prefix + "/")
        and str(target.get("final_root") or "").startswith(prefix + "/")
        and target.get("publish_by_same_filesystem_rename") is True,
        "physical_store_microcanary_policy_invalid",
    )
    return policy


def inspect_environment(policy: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        platform.system().lower() == "linux",
        "physical_store_microcanary_linux_required",
    )
    runtime = dict(policy["runtime"])
    packages = {
        name: importlib.metadata.version(name)
        for name in runtime["required_packages"]
    }
    _require(
        packages == runtime["required_packages"],
        "physical_store_microcanary_package_drift",
    )
    target = dict(policy["private_target"])
    working = Path(str(target["working_root"]))
    final = Path(str(target["final_root"]))
    prefix = Path(str(target["target_prefix"]))
    anchor = prefix
    while not anchor.exists() and anchor != anchor.parent:
        anchor = anchor.parent
    disk = shutil.disk_usage(anchor)
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "packages": packages,
        "profile_id": policy["store_contract"]["profile_id"],
        "target": {
            "working_root": working.as_posix(),
            "working_root_absent": not working.exists(),
            "final_root": final.as_posix(),
            "final_root_absent": not final.exists(),
            "disk_free_bytes": disk.free,
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding_model_loads": 0,
            "milvus_write": 0,
        },
    }
    _require(
        result["target"]["working_root_absent"]
        and result["target"]["final_root_absent"]
        and int(result["target"]["disk_free_bytes"]) >= 1024**3,
        "physical_store_microcanary_target_unqualified",
    )
    return result


def _environment_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    target = dict(value.get("target") or {})
    return {
        "platform": value.get("platform"),
        "python": value.get("python"),
        "python_executable": value.get("python_executable"),
        "packages": value.get("packages"),
        "profile_id": value.get("profile_id"),
        "target": {
            "working_root": target.get("working_root"),
            "working_root_absent": target.get("working_root_absent"),
            "final_root": target.get("final_root"),
            "final_root_absent": target.get("final_root_absent"),
        },
    }


def validate_authority(
    authority: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    repo_root: Path,
    requalify_environment: bool = True,
) -> None:
    body = {key: value for key, value in authority.items() if key != "authority_digest"}
    implementation = dict(authority.get("implementation") or {})
    environment = dict(authority.get("environment") or {})
    target = dict(environment.get("target") or {})
    expected_target = dict(policy["private_target"])
    observed_calls = dict(environment.get("observed_calls") or {})
    environment_is_bound = (
        str(environment.get("platform") or "").lower().startswith("linux")
        and environment.get("python_executable")
        == policy["runtime"]["python_executable"]
        and environment.get("packages") == policy["runtime"]["required_packages"]
        and environment.get("profile_id") == policy["store_contract"]["profile_id"]
        and target.get("working_root") == expected_target["working_root"]
        and target.get("final_root") == expected_target["final_root"]
        and target.get("working_root_absent") is True
        and target.get("final_root_absent") is True
        and all(
            int(observed_calls.get(key, -1)) == 0
            for key in (
                "network",
                "provider",
                "llm_model",
                "embedding_model_loads",
                "milvus_write",
            )
        )
    )
    environment_requalified = (
        not requalify_environment
        or _environment_identity(environment)
        == _environment_identity(inspect_environment(policy))
    )
    _require(
        authority.get("schema_version")
        == "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_authority_v1_0"
        and authority.get("status") == "issued_unconsumed"
        and authority.get("attempt_id") == policy.get("attempt_id")
        and authority.get("policy_digest") == canonical_digest(policy)
        and authority.get("run_scope") == policy.get("run_scope")
        and authority.get("execution_ceiling") == policy.get("execution_ceiling")
        and authority.get("maximum_executions") == 1
        and authority.get("automatic_retry") is False
        and implementation.get("clean") is True
        and implementation.get("synced") is True
        and canonical_digest(body) == authority.get("authority_digest")
        and environment_is_bound
        and environment_requalified,
        "physical_store_microcanary_authority_invalid",
    )
    for binding in implementation.get("bindings") or []:
        ref = str(binding.get("ref") or "")
        _require(
            bool(ref)
            and (repo_root / ref).is_file()
            and normalized_sha256(repo_root / ref) == binding.get("sha256"),
            "physical_store_microcanary_authority_binding_drift",
        )


def _synthetic_spec() -> dict[str, Any]:
    body = {
        "vector_id": "FIN013_S1_PHYSICAL_STORE_MICROCANARY::synthetic",
        "case_key": "CANARY",
        "target_id": "physical_store_artifact_publication",
        "object_type": "synthetic_canary",
        "quality_tier": "canary_not_evidence",
        "candidate_state": "bundle_candidate_only_not_evidence",
        "slot_ids": ["synthetic_dependency_qualification"],
        "facet_ids": ["directory_store"],
        "source_reporting_period_end": "2026-08-10",
        "source_locator": "local://synthetic/physical-store-microcanary",
        "vector_text": "Synthetic storage qualification row; never eligible for Evidence.",
    }
    return {
        **body,
        "spec_digest": canonical_digest(body),
        "vector_text_sha256": hashlib.sha256(
            body["vector_text"].encode("utf-8")
        ).hexdigest(),
    }


def _prove_symlink_rejection() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="fin013-store-symlink-mutation-") as parent:
        root = Path(parent) / "store"
        root.mkdir()
        outside = Path(parent) / "outside.bin"
        outside.write_bytes(b"outside")
        (root / "linked.bin").symlink_to(outside)
        try:
            canonical_tree_manifest(root)
        except CandidateBundlePhysicalIndexError as exc:
            _require(
                exc.code
                == "candidate_bundle_physical_directory_artifact_symlink_forbidden",
                "physical_store_microcanary_symlink_wrong_failure",
            )
            return {
                "scenario": "directory_tree_symlink",
                "failed_closed": True,
                "observed_code": exc.code,
            }
    raise CandidateBundlePhysicalIndexError(
        "physical_store_microcanary_symlink_did_not_fail"
    )


def execute(
    *,
    policy: Mapping[str, Any],
    authority: Mapping[str, Any],
    repo_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    _require(not output_path.exists(), "physical_store_microcanary_result_preexists")
    validate_authority(authority, policy=policy, repo_root=repo_root)
    target = dict(policy["private_target"])
    store_contract = dict(policy["store_contract"])
    working = Path(str(target["working_root"]))
    final = Path(str(target["final_root"]))
    phase = "validate_fresh_targets"
    phases: list[dict[str, Any]] = []
    writer: MilvusCandidateBundleWriter | None = None
    started = time.perf_counter()

    def verified(name: str, snapshot: Mapping[str, Any]) -> None:
        phases.append(
            {
                "phase": name,
                "snapshot": dict(snapshot),
                "snapshot_digest": canonical_digest(snapshot),
            }
        )

    try:
        phase = "requalify_environment"
        environment = inspect_environment(policy)
        verified(
            phase,
            {"environment_digest": canonical_digest(_environment_identity(environment))},
        )
        phase = "prove_symlink_rejection"
        symlink_mutation = _prove_symlink_rejection()
        verified(phase, symlink_mutation)
        phase = "validate_fresh_targets"
        _require(
            not working.exists() and not final.exists(),
            "physical_store_microcanary_target_preexists",
        )
        working.parent.mkdir(parents=True, exist_ok=True)
        working.mkdir()
        verified(phase, {"working_root_created": True, "final_root_absent": True})
        phase = "write_close_reopen_synthetic_vector"
        store_path = working / str(target["store_relative_path"])
        writer = MilvusCandidateBundleWriter(uri=str(store_path))
        writer.begin(
            collection_name=str(store_contract["collection_name"]),
            embedding_dimension=int(store_contract["embedding_dimension"]),
        )
        spec = _synthetic_spec()
        acknowledged = writer.insert([spec], [[1.0, 0.0, 0.0, 0.0]])
        count_before_close = writer.finalize()
        rows = writer.reopen_and_read_identities(limit=2)
        writer.close()
        _require(
            acknowledged == 1
            and count_before_close == 1
            and len(rows) == 1
            and rows[0].get("vector_id") == spec["vector_id"]
            and rows[0].get("spec_digest") == spec["spec_digest"],
            "physical_store_microcanary_identity_mismatch",
        )
        verified(
            phase,
            {
                "acknowledged": acknowledged,
                "count_before_close": count_before_close,
                "identity_digest": canonical_digest(rows),
                "writer_calls": dict(writer.calls),
            },
        )
        phase = "validate_directory_artifact"
        artifact = inspect_physical_store_artifact(
            store_path,
            contract=store_contract,
            expected_count=1,
            embedding_dimension=4,
        )
        verified(
            phase,
            {
                "artifact_kind": artifact["artifact_kind"],
                "artifact_digest": artifact["artifact_digest"],
                "total_bytes": artifact["total_bytes"],
            },
        )
        phase = "write_receipt"
        receipt_body = {
            "schema_version": "fin_ia_physical_store_microcanary_private_receipt_v1_0",
            "attempt_id": policy["attempt_id"],
            "synthetic_not_evidence": True,
            "physical_store_artifact": artifact,
            "writer_calls": dict(writer.calls),
        }
        receipt = {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        _write_json_atomic(working / "receipt.json", receipt)
        verified(phase, {"receipt_digest": receipt["receipt_digest"]})
        phase = "publish_whole_root"
        working.rename(final)
        published = inspect_physical_store_artifact(
            final / str(target["store_relative_path"]),
            contract=store_contract,
            expected_count=1,
            embedding_dimension=4,
        )
        _require(
            published["artifact_digest"] == artifact["artifact_digest"],
            "physical_store_microcanary_published_digest_mismatch",
        )
        verified(
            phase,
            {
                "final_root": final.as_posix(),
                "artifact_digest": published["artifact_digest"],
            },
        )
        body = {
            "schema_version": "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_result_v1_0",
            "contract_ref": policy["contract_ref"],
            "run_scope": policy["run_scope"],
            "recorded_at": policy["recorded_at"],
            "attempt_id": policy["attempt_id"],
            "status": "terminal_succeeded_directory_store_publication_microcanary",
            "automatic_retry": False,
            "authority_digest": authority["authority_digest"],
            "implementation_commit": authority["implementation"]["commit"],
            "wall_time_ms": round((time.perf_counter() - started) * 1000, 3),
            "physical_store_artifact": published,
            "mutation_proof": {"symlink_rejection": symlink_mutation},
            "private_final_root": final.as_posix(),
            "private_receipt_digest": receipt["receipt_digest"],
            "phase_receipt": {
                "last_verified_phase": phases[-1]["phase"],
                "verified_phases": phases,
            },
            "observed_calls": {
                **complete_observed_calls(embedder=None, writer=writer),
                "synthetic_vectors": 1,
            },
            "stage_acceptance": {
                "directory_artifact_contract": True,
                "directory_symlink_rejection": True,
                "close_reopen_identity": True,
                "complete_call_receipt": True,
                "whole_root_atomic_publication": True,
                "business_index": False,
                "retrieval_quality": False,
                "evidence": False,
                "release": False,
            },
            "known_boundary": policy["known_boundary"],
        }
    except Exception as exc:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
        body = {
            "schema_version": "fin_ia_0_1_3_s1_candidate_bundle_physical_store_microcanary_result_v1_0",
            "contract_ref": policy["contract_ref"],
            "run_scope": policy["run_scope"],
            "recorded_at": policy["recorded_at"],
            "attempt_id": policy["attempt_id"],
            "status": "terminal_failed_directory_store_publication_microcanary_no_retry",
            "automatic_retry": False,
            "authority_digest": authority["authority_digest"],
            "implementation_commit": authority["implementation"]["commit"],
            "failure": {
                "phase": phase,
                "error_type": type(exc).__name__,
                "error_code": str(getattr(exc, "code", str(exc))),
                "last_verified_phase": phases[-1]["phase"] if phases else None,
            },
            "private_state": {
                "working_root": working.as_posix(),
                "working_root_exists": working.exists(),
                "final_root": final.as_posix(),
                "final_root_exists": final.exists(),
            },
            "phase_receipt": {
                "last_verified_phase": phases[-1]["phase"] if phases else None,
                "verified_phases": phases,
            },
            "observed_calls": {
                **complete_observed_calls(embedder=None, writer=writer),
                "synthetic_vectors": int(
                    dict(getattr(writer, "calls", {}) or {}).get(
                        "inserted_vectors", 0
                    )
                ),
            },
            "stage_acceptance": {
                "directory_artifact_contract": False,
                "business_index": False,
                "retrieval_quality": False,
                "evidence": False,
                "release": False,
            },
            "known_boundary": (
                "This exact-once synthetic failure is preserved with no retry. It does not "
                "authorize the 93-vector R2 build."
            ),
        }
    result = {**body, "result_digest": canonical_digest(body)}
    _write_json_atomic(output_path, result)
    return result


def verify_published(
    *,
    policy: Mapping[str, Any],
    result_path: Path,
) -> dict[str, Any]:
    result = _read_json(result_path)
    body = {key: value for key, value in result.items() if key != "result_digest"}
    _require(
        result.get("status")
        == "terminal_succeeded_directory_store_publication_microcanary"
        and result.get("result_digest") == canonical_digest(body),
        "physical_store_microcanary_public_result_invalid",
    )
    target = dict(policy["private_target"])
    final = Path(str(target["final_root"]))
    working = Path(str(target["working_root"]))
    artifact = inspect_physical_store_artifact(
        final / str(target["store_relative_path"]),
        contract=dict(policy["store_contract"]),
        expected_count=1,
        embedding_dimension=4,
    )
    receipt = _read_json(final / "receipt.json")
    receipt_body = {
        key: value for key, value in receipt.items() if key != "receipt_digest"
    }
    _require(
        not working.exists()
        and final.is_dir()
        and artifact["artifact_digest"]
        == result.get("physical_store_artifact", {}).get("artifact_digest")
        and receipt.get("receipt_digest") == canonical_digest(receipt_body)
        and receipt.get("receipt_digest") == result.get("private_receipt_digest"),
        "physical_store_microcanary_published_state_invalid",
    )
    return {
        "status": "published_microcanary_reverified_read_only",
        "result_digest": result["result_digest"],
        "artifact_digest": artifact["artifact_digest"],
        "receipt_digest": receipt["receipt_digest"],
        "working_root_absent": True,
        "final_root_present": True,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "llm_model": 0,
            "embedding_model_loads": 0,
            "milvus_write": 0,
            "vector_search": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--verify-published", action="store_true")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    policy_path = args.policy or repo_root / POLICY_REF
    policy = load_policy(policy_path)
    if args.inspect_only:
        print(json.dumps(inspect_environment(policy), ensure_ascii=False, sort_keys=True))
        return 0
    if args.verify_published:
        if args.result is None:
            raise SystemExit("--result is required with --verify-published")
        print(
            json.dumps(
                verify_published(policy=policy, result_path=args.result),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.authority is None or args.output is None:
        raise SystemExit("--authority and --output are required")
    result = execute(
        policy=policy,
        authority=_read_json(args.authority),
        repo_root=repo_root,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempt_id": result["attempt_id"],
                "result_digest": result["result_digest"],
                "failure": result.get("failure"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"].startswith("terminal_succeeded") else 1


if __name__ == "__main__":
    raise SystemExit(main())
