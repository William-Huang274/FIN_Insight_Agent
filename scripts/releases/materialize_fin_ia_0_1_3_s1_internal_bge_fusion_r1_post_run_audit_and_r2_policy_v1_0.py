from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_internal_bge_fusion_evaluation import (  # noqa: E402
    POLICY_SCHEMA_V1_1,
    RESULT_SCHEMA_V1_1,
    VECTOR_KIND_SUFFIXES,
    validate_internal_bge_fusion_evaluation_result,
)


R1_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_policy_v1_0.json"
)
R1_RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_attempt_r1.json"
)
AUDIT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_bge_fusion_"
    "evaluation_attempt_r1_post_run_identity_audit_v1_0.json"
)
R2_POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "bge_fusion_evaluation_policy_v1_1.json"
)
R1_ATTEMPT_ID = (
    "20260809_three_case_s1_internal_ranking_bge_m3_sparse_dense_"
    "facet_fusion_owner_qrels_v1_r1"
)
R2_ATTEMPT_ID = (
    "20260809_three_case_s1_internal_ranking_bge_m3_sparse_dense_"
    "facet_fusion_owner_qrels_v2_r2"
)
R1_EXECUTION_COMMIT = "7135159999216c9b82c3fc62582365bd6fb91b5a"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _strip_vector_kind(alias: str) -> str:
    if "::" not in alias:
        return alias
    prefix, suffix = alias.rsplit("::", 1)
    return prefix if suffix in VECTOR_KIND_SUFFIXES else alias


def _identity_collision_records(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rankings = (result.get("candidate_generation") or {}).get("rankings") or {}
    records: list[dict[str, Any]] = []
    for approach in ("dense_rankings", "fusion_rankings"):
        for bundle_id, candidates in sorted((rankings.get(approach) or {}).items()):
            for candidate in candidates:
                key = str(candidate.get("candidate_key") or "")
                if not key or "::" in key:
                    continue
                bases = sorted(
                    {
                        _strip_vector_kind(str(alias))
                        for alias in candidate.get("aliases") or []
                        if "::" in str(alias)
                    }
                )
                same_namespace = [
                    alias for alias in bases if alias.startswith(f"{key}::")
                ]
                if len(same_namespace) < 2:
                    continue
                records.append(
                    {
                        "approach": approach,
                        "bundle_id": str(bundle_id),
                        "collapsed_candidate_key": key,
                        "distinct_namespaced_evidence_identities": len(
                            same_namespace
                        ),
                        "sample_evidence_identities": same_namespace[:5],
                    }
                )
    return records


def main() -> int:
    if AUDIT_PATH.exists() or R2_POLICY_PATH.exists():
        raise RuntimeError("internal_bge_fusion_r1_audit_or_r2_policy_already_exists")
    r1_result = validate_internal_bge_fusion_evaluation_result(
        _read(R1_RESULT_PATH)
    )
    if r1_result.get("attempt_id") != R1_ATTEMPT_ID:
        raise RuntimeError("internal_bge_fusion_r1_attempt_identity_invalid")
    collisions = _identity_collision_records(r1_result)
    if not collisions or not any(
        row["collapsed_candidate_key"] == "8K_EARNINGS" for row in collisions
    ):
        raise RuntimeError("internal_bge_fusion_r1_identity_collision_not_proven")
    audit_body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_internal_bge_fusion_evaluation_"
            "post_run_identity_audit_v1_0"
        ),
        "contract_ref": (
            "fin_0_1_3.S1.internal_bge_fusion_evaluation."
            "post_run_identity_audit:v1"
        ),
        "recorded_at": "2026-08-09",
        "status": (
            "attempt_invalidated_for_adoption_identity_canonicalization_defect"
        ),
        "source_attempt": {
            "attempt_id": R1_ATTEMPT_ID,
            "execution_commit": R1_EXECUTION_COMMIT,
            "result_ref": R1_RESULT_PATH.relative_to(ROOT).as_posix(),
            "result_sha256": _normalized_sha256(R1_RESULT_PATH),
            "result_digest": str(r1_result["result_digest"]),
            "terminal_execution_status": str(r1_result["status"]),
        },
        "defect": {
            "code_location": (
                "src/sec_agent/s1_internal_bge_fusion_evaluation.py:"
                "_candidate_aliases"
            ),
            "old_rule": "split_vector_id_at_first_double_colon",
            "required_rule": "strip_only_final_known_vector_kind_suffix",
            "impact": (
                "Distinct namespaced evidence blocks were coalesced before RRF. "
                "R1 dense and fusion metrics are invalid for adoption and must not "
                "be interpreted as BGE-M3 model quality."
            ),
            "collision_record_count": len(collisions),
            "collapsed_namespace_prefixes": sorted(
                {row["collapsed_candidate_key"] for row in collisions}
            ),
            "collision_records": collisions,
        },
        "disposition": {
            "r1_artifact_immutable": True,
            "r1_metrics_valid_for_adoption": False,
            "automatic_retry_occurred": False,
            "replacement_eligible": True,
            "maximum_replacement_executions": 1,
            "replacement_preconditions": [
                "final_known_vector_kind_suffix_only_implementation",
                "namespaced_multi_block_non_merge_mutation_pass",
                "same_evidence_vector_kind_coalescing_pass",
                "clean_synced_commit",
                "project_os_preflight_pass",
            ],
        },
        "preserved_boundaries": {
            "current_quarter_exact_sql": "0_of_6_open",
            "external_official_required_slot_coverage": (
                "4_of_12_open_release_blocker"
            ),
            "reranker": "optional_resource_absent_not_executed",
            "evidence_promotion": False,
            "downstream_utilization": False,
            "release": "not_qualified",
        },
    }
    audit = {**audit_body, "audit_digest": canonical_digest(audit_body)}
    _write_atomic(AUDIT_PATH, audit)

    policy = deepcopy(_read(R1_POLICY_PATH))
    policy.update(
        {
            "schema_version": POLICY_SCHEMA_V1_1,
            "result_schema": RESULT_SCHEMA_V1_1,
            "contract_ref": "fin_0_1_3.S1.internal_bge_fusion_evaluation:v1.1",
            "attempt_id": R2_ATTEMPT_ID,
            "replacement_authority": {
                "invalidated_attempt_id": R1_ATTEMPT_ID,
                "post_run_identity_audit_digest": audit["audit_digest"],
                "maximum_replacement_executions": 1,
                "automatic_retry": False,
                "reason": "candidate_identity_namespace_prefix_collapse",
            },
        }
    )
    policy["immutable_inputs"].update(
        {
            "invalidated_attempt_r1_ref": R1_RESULT_PATH.relative_to(
                ROOT
            ).as_posix(),
            "invalidated_attempt_r1_sha256": _normalized_sha256(R1_RESULT_PATH),
            "post_run_identity_audit_ref": AUDIT_PATH.relative_to(ROOT).as_posix(),
            "post_run_identity_audit_sha256": _normalized_sha256(AUDIT_PATH),
        }
    )
    policy["candidate_contract"]["identity_canonicalization"] = {
        "vector_base_rule": "strip_only_final_known_vector_kind_suffix",
        "known_vector_kind_suffixes": sorted(VECTOR_KIND_SUFFIXES),
        "namespace_prefix_is_never_evidence_identity": True,
        "cross_document_merge_forbidden": True,
    }
    policy["experiment_governance"].update(
        {
            "invalidated_attempt": R1_ATTEMPT_ID,
            "replacement_hypothesis": (
                "After correcting evidence identity canonicalization, measure the "
                "same frozen sparse, dense and facet-fusion strategies without "
                "changing queries, weights, qrels, filters or budgets."
            ),
            "decision_label_before_run": (
                "proceed_once_after_structural_identity_fix"
            ),
        }
    )
    _write_atomic(R2_POLICY_PATH, policy)
    print(
        json.dumps(
            {
                "status": "r1_invalidated_r2_policy_materialized",
                "collision_records": len(collisions),
                "audit_digest": audit["audit_digest"],
                "audit": AUDIT_PATH.relative_to(ROOT).as_posix(),
                "policy": R2_POLICY_PATH.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
