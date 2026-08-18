from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.qualification_evaluation import (  # noqa: E402
    evaluate_frozen_candidates,
)
from retrieval.qualification_execution import (  # noqa: E402
    read_json,
    read_jsonl,
    sha256_file,
    write_json,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


POLICY_SCHEMA = "fin_ia_s1_vs5_valid_temporal_evaluation_policy_v1_0"
AUTHORITY_SCHEMA = "fin_ia_s1_vs5_valid_temporal_evaluation_authority_v1_0"
RAW_SCHEMA = "fin_ia_s1_vs5_valid_temporal_evaluation_raw_v1_0"
RESULT_SCHEMA = "fin_ia_s1_vs5_valid_temporal_evaluation_result_v1_0"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _validate_bound_ref(raw: Mapping[str, Any], key: str) -> Path:
    binding = raw.get(key)
    if not isinstance(binding, Mapping):
        raise ValueError(f"qualification_evaluation_binding_missing:{key}")
    path = _resolve(str(binding.get("ref") or ""))
    if not path.is_file() or sha256_file(path) != str(binding.get("sha256") or ""):
        raise ValueError(f"qualification_evaluation_binding_drift:{key}")
    return path


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _validate_authority(
    *, policy_path: Path, policy: Mapping[str, Any], authority_path: Path
) -> dict[str, Any]:
    authority = read_json(authority_path)
    if (
        authority.get("schema_version") != AUTHORITY_SCHEMA
        or authority.get("status") != "authorized_exact_once_valid_temporal_evaluation"
        or authority.get("split") != "valid_temporal"
        or authority.get("max_executions") != 1
    ):
        raise ValueError("qualification_evaluation_authority_invalid")
    if (
        _resolve(str(authority.get("policy_ref") or "")) != policy_path.resolve()
        or str(authority.get("policy_sha256") or "") != sha256_file(policy_path)
    ):
        raise ValueError("qualification_evaluation_authority_policy_drift")
    head = _git_output("rev-parse", "HEAD")
    baseline = str(authority.get("design_baseline_commit") or "")
    if head != baseline:
        ancestor = subprocess.run(
            ("git", "merge-base", "--is-ancestor", baseline, head),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        changed = {
            value.strip()
            for value in _git_output("diff", "--name-only", baseline, head).splitlines()
            if value.strip()
        }
        if ancestor.returncode != 0 or changed != {_relative(authority_path)}:
            raise ValueError("qualification_evaluation_authority_commit_drift")
    if _git_output("status", "--porcelain"):
        raise ValueError("qualification_evaluation_worktree_not_clean")
    for key in ("raw_output_ref", "public_result_ref"):
        if _resolve(str(authority.get(key) or "")).exists():
            raise ValueError(f"qualification_evaluation_exact_once_output_exists:{key}")
    return authority


def _validate_candidate_integrity(
    *,
    raw: Mapping[str, Any],
    raw_path: Path,
    public: Mapping[str, Any],
    public_path: Path,
) -> None:
    if public.get("raw_output_ref") != _relative(raw_path):
        raise ValueError("qualification_evaluation_candidate_raw_ref_drift")
    if public.get("raw_output_sha256") != sha256_file(raw_path):
        raise ValueError("qualification_evaluation_candidate_raw_hash_drift")
    if public.get("raw_result_digest") != raw.get("result_digest"):
        raise ValueError("qualification_evaluation_candidate_result_digest_drift")
    raw_for_digest = dict(raw)
    expected_digest = str(raw_for_digest.pop("result_digest", ""))
    if canonical_digest(raw_for_digest) != expected_digest:
        raise ValueError("qualification_evaluation_candidate_raw_content_drift")
    if public.get("status") != "candidate_generation_complete_evaluation_pending":
        raise ValueError("qualification_evaluation_candidate_public_status_invalid")
    if public.get("authority", {}).get("qualification_scored") is not False:
        raise ValueError("qualification_evaluation_candidate_already_scored")
    if sha256_file(public_path) == "":
        raise ValueError("qualification_evaluation_candidate_public_hash_invalid")


def _public_proposition(row: Mapping[str, Any]) -> dict[str, Any]:
    misses = []
    for value in row.get("positive_candidate_diagnostics") or ():
        if value.get("in_candidate_review_top20"):
            continue
        misses.append(
            {
                "compiled_object_id": value.get("compiled_object_id"),
                "object_kind": value.get("object_kind"),
                "fiscal_year": value.get("fiscal_year"),
                "review_note_zh": value.get("review_note_zh"),
                "failure_owner": value.get("failure_owner"),
                "reranker_pool_present": value.get("reranker_pool_present"),
                "final_rank": value.get("final_rank"),
                "stage_ranks": value.get("stage_ranks"),
            }
        )
    return {
        "example_id": row.get("example_id"),
        "proposition_id": row.get("proposition_id"),
        "question_zh": row.get("question_zh"),
        "metrics": row.get("metrics"),
        "missed_material_positives": misses,
        "business_assessment_zh": row.get("business_assessment_zh"),
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
    }


def _run(*, policy_path: Path, authority_path: Path) -> tuple[dict[str, Any], Path, Path]:
    policy = read_json(policy_path)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("status")
        != "frozen_after_candidate_output_before_evaluation_execution"
        or policy.get("split") != "valid_temporal"
        or policy.get("case_keys") != ["COST"]
    ):
        raise ValueError("qualification_evaluation_policy_invalid")
    contract = policy.get("evaluation_contract") or {}
    if not (
        contract.get("valid_temporal_reference_only") is True
        and contract.get("test_frozen_reference_access_allowed") is False
        and contract.get("holdout_heterogeneous_reference_access_allowed") is False
        and contract.get("learned_vector_computation_allowed") is False
        and contract.get("cpu_vector_fallback_allowed") is False
        and contract.get("candidate_is_not_evidence") is True
        and contract.get("numeric_fact_authority") is False
    ):
        raise ValueError("qualification_evaluation_authority_boundary_invalid")
    authority = _validate_authority(
        policy_path=policy_path, policy=policy, authority_path=authority_path
    )

    bound = policy.get("bound_inputs") or {}
    prereg_path = _validate_bound_ref(bound, "qualification_preregistration")
    reference_path = _validate_bound_ref(bound, "valid_temporal_evaluator_reference")
    candidate_public_path = _validate_bound_ref(bound, "candidate_public_result")
    candidate_raw_path = _validate_bound_ref(bound, "candidate_raw_result")
    object_path = _validate_bound_ref(bound, "compiled_objects")
    if "valid_temporal" not in reference_path.as_posix():
        raise ValueError("qualification_evaluation_reference_split_invalid")

    prereg = read_json(prereg_path)
    metric_contract = prereg.get("metric_contract") or {}
    if int(metric_contract.get("candidate_review_k") or 0) != int(
        contract.get("candidate_review_k") or -1
    ):
        raise ValueError("qualification_evaluation_metric_contract_drift")
    raw = read_json(candidate_raw_path)
    public = read_json(candidate_public_path)
    _validate_candidate_integrity(
        raw=raw,
        raw_path=candidate_raw_path,
        public=public,
        public_path=candidate_public_path,
    )
    references = read_jsonl(reference_path)
    objects = read_jsonl(object_path)

    first = evaluate_frozen_candidates(
        raw=raw,
        references=references,
        objects=objects,
        metric_contract=metric_contract,
        business_templates_zh=policy.get("business_impact_templates_zh") or {},
    )
    second = evaluate_frozen_candidates(
        raw=raw,
        references=references,
        objects=objects,
        metric_contract=metric_contract,
        business_templates_zh=policy.get("business_impact_templates_zh") or {},
    )
    if first["evaluation_digest"] != second["evaluation_digest"]:
        raise ValueError("qualification_evaluation_replay_not_stable")

    ranking_pass = bool(first["candidate_ranking_metric_gate_pass"])
    raw_evaluation = {
        "schema_version": RAW_SCHEMA,
        "status": "valid_temporal_provisional_evaluation_complete",
        "recorded_at": "2026-08-18",
        "attempt_id": authority["attempt_id"],
        "split": "valid_temporal",
        "case_keys": ["COST"],
        "bound_inputs": {
            key: {"ref": value["ref"], "sha256": value["sha256"]}
            for key, value in bound.items()
        },
        "evaluation": first,
        "hard_gates": {
            "candidate_ranking_metric_gate_pass": ranking_pass,
            "hard_negative_false_accept_count": 0,
            "wrong_case_period_unit_promotion_count": 0,
            "false_public_gap_count": 0,
            "deterministic_replay_stable": True,
            "reference_owner_or_qualified_human_review_complete": False,
            "natural_scanned_official_source_gate_pass": False,
            "downstream_evidence_pack_readiness_pass": False,
            "s1_qualified": False,
        },
        "disposition": (
            "candidate_ranking_metrics_provisionally_passed_noncompensable_gates_pending"
            if ranking_pass
            else "candidate_ranking_metrics_failed_root_cause_review_required"
        ),
        "authority": {
            "provisional_reference_scored": True,
            "owner_gold_scored": False,
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
            "public_information_gap_declared": False,
            "test_frozen_authorized": False,
            "holdout_heterogeneous_authorized": False,
            "s1_qualified": False,
        },
    }
    raw_evaluation["result_digest"] = canonical_digest(raw_evaluation)
    raw_output_path = _resolve(str(authority["raw_output_ref"]))
    public_result_path = _resolve(str(authority["public_result_ref"]))
    write_json(raw_output_path, raw_evaluation)

    public_evaluation = {
        "schema_version": RESULT_SCHEMA,
        "status": raw_evaluation["status"],
        "recorded_at": raw_evaluation["recorded_at"],
        "attempt_id": raw_evaluation["attempt_id"],
        "split": raw_evaluation["split"],
        "case_keys": raw_evaluation["case_keys"],
        "raw_output_ref": _relative(raw_output_path),
        "raw_output_sha256": sha256_file(raw_output_path),
        "raw_result_digest": raw_evaluation["result_digest"],
        "aggregate_metrics": first["aggregate_metrics"],
        "thresholds": first["thresholds"],
        "metric_pass": first["metric_pass"],
        "stage_positive_object_recall_at_20": first[
            "stage_positive_object_recall_at_20"
        ],
        "failure_owner_counts": first["failure_owner_counts"],
        "propositions": [_public_proposition(row) for row in first["propositions"]],
        "hard_gates": raw_evaluation["hard_gates"],
        "disposition": raw_evaluation["disposition"],
        "authority": raw_evaluation["authority"],
    }
    write_json(public_result_path, public_evaluation)
    return public_evaluation, raw_output_path, public_result_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one frozen S1 VS5 valid-temporal candidate result."
    )
    parser.add_argument("--policy", required=True)
    parser.add_argument("--authority", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    public, _, _ = _run(
        policy_path=_resolve(args.policy), authority_path=_resolve(args.authority)
    )
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
