from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.financial_research_held_out_profile_registry import (
    load_held_out_profile_selection_policy,
)
from sec_agent.financial_research_source_object_vertical import normalized_sha256


HELD_OUT_REVIEW_POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_three_held_out_business_review_policy_v1_0"
)
HELD_OUT_REVIEW_RESULT_SCHEMA = (
    "fin_ia_0_1_3_s1_three_held_out_business_review_result_v1_0"
)
HELD_OUT_REVIEW_RUN_SCOPE = "S1_THREE_HELD_OUT_BUSINESS_RELEVANCE_REVIEW"

LANE_VERDICTS = {
    "strong",
    "usable_with_parent_context",
    "partial",
    "parser_unsafe",
    "off_target",
    "zero_result",
}
MUTATION_OUTCOMES = {"pass", "fail", "not_proven"}


class HeldOutBusinessReviewError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LockedReviewArtifact(StrictModel):
    artifact_id: str
    path: str
    normalized_sha256: str
    role: str


class LaneBusinessReview(StrictModel):
    lane_id: str
    verdict: str
    useful_candidate_refs: tuple[str, ...]
    business_answer_zh: str
    limitation_zh: str


class HeldOutMutationReview(StrictModel):
    mutation_id: str
    outcome: str
    evidence_zh: str


class HeldOutBusinessBlocker(StrictModel):
    code: str
    owning_layer: str
    affected_lane_ids: tuple[str, ...]
    business_impact_zh: str
    required_next_action_zh: str
    blocks_sparse_dense_rebuild: bool


class HeldOutCaseBusinessReview(StrictModel):
    case_key: str
    lane_reviews: tuple[LaneBusinessReview, ...]
    mutation_reviews: tuple[HeldOutMutationReview, ...]
    blockers: tuple[HeldOutBusinessBlocker, ...]
    current_period_answer_zh: str
    product_readiness_zh: str


class HeldOutBusinessReviewPolicy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    review_attempt_id: str
    selection_policy_ref: str
    candidate_result_ref: str
    candidate_result_digest: str
    expected_core_fingerprint: str
    locked_artifacts: tuple[LockedReviewArtifact, ...]
    case_reviews: tuple[HeldOutCaseBusinessReview, ...]
    cross_case_findings: tuple[HeldOutBusinessBlocker, ...]
    hard_boundaries: dict[str, Any]


def load_held_out_business_review_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> tuple[HeldOutBusinessReviewPolicy, dict[str, Any]]:
    root = Path(repo_root).resolve()
    try:
        policy = HeldOutBusinessReviewPolicy.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise HeldOutBusinessReviewError(
            "held_out_business_review_policy_shape_invalid"
        ) from exc
    if (
        policy.schema_version != HELD_OUT_REVIEW_POLICY_SCHEMA
        or policy.run_scope != HELD_OUT_REVIEW_RUN_SCOPE
    ):
        raise HeldOutBusinessReviewError(
            "held_out_business_review_policy_identity_invalid"
        )
    _validate_hard_boundaries(policy.hard_boundaries)
    _validate_locked_artifacts(policy, repo_root=root)
    candidate_result = _load_result(
        _resolve(root, policy.candidate_result_ref),
        expected_digest=policy.candidate_result_digest,
    )
    selection, base_contract, _extended = load_held_out_profile_selection_policy(
        _resolve(root, policy.selection_policy_ref),
        repo_root=root,
    )
    _validate_reviews(
        policy,
        candidate_result=candidate_result,
        selection=selection,
        base_contract=base_contract,
    )
    return policy, candidate_result


def execute_held_out_business_review(
    *,
    policy: HeldOutBusinessReviewPolicy,
    candidate_result: Mapping[str, Any],
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    before = _locked_digest_map(policy, repo_root=root)
    candidates_by_case = {
        str(row["case_key"]): row for row in candidate_result["case_results"]
    }
    case_summaries: list[dict[str, Any]] = []
    for review in policy.case_reviews:
        candidate_case = candidates_by_case[review.case_key]
        verdict_counts = Counter(row.verdict for row in review.lane_reviews)
        useful_refs = {
            ref
            for lane in review.lane_reviews
            for ref in lane.useful_candidate_refs
        }
        mutation_counts = Counter(row.outcome for row in review.mutation_reviews)
        blocking = [row for row in review.blockers if row.blocks_sparse_dense_rebuild]
        body = {
            "case_key": review.case_key,
            "candidate_case_result_digest": candidate_case["case_result_digest"],
            "source_currentness_status": candidate_case[
                "source_currentness_status"
            ],
            "lane_verdict_counts": dict(sorted(verdict_counts.items())),
            "reviewed_useful_candidate_ref_count": len(useful_refs),
            "lane_reviews": [
                row.model_dump(mode="json") for row in review.lane_reviews
            ],
            "mutation_reviews": [
                row.model_dump(mode="json") for row in review.mutation_reviews
            ],
            "mutation_outcome_counts": dict(sorted(mutation_counts.items())),
            "blockers": [row.model_dump(mode="json") for row in review.blockers],
            "current_period_answer_zh": review.current_period_answer_zh,
            "product_readiness_zh": review.product_readiness_zh,
            "interface_terminalization_pass": True,
            "business_content_acceptance": "fail" if review.blockers else "pass",
            "sparse_dense_rebuild_admitted": not blocking
            and not any(row.outcome != "pass" for row in review.mutation_reviews),
        }
        case_summaries.append(
            {**body, "case_review_digest": canonical_digest(body)}
        )
    after = _locked_digest_map(policy, repo_root=root)
    locked_unchanged = before == after
    all_mutations_pass = all(
        row.outcome == "pass"
        for review in policy.case_reviews
        for row in review.mutation_reviews
    )
    rebuild_blockers = [
        row
        for row in (
            *policy.cross_case_findings,
            *(item for review in policy.case_reviews for item in review.blockers),
        )
        if row.blocks_sparse_dense_rebuild
    ]
    body = {
        "schema_version": HELD_OUT_REVIEW_RESULT_SCHEMA,
        "contract_ref": policy.contract_ref,
        "run_scope": policy.run_scope,
        "recorded_at": policy.recorded_at,
        "review_attempt_id": policy.review_attempt_id,
        "status": "held_out_generalization_blocked_before_index_rebuild",
        "candidate_result_ref": policy.candidate_result_ref,
        "candidate_result_digest": policy.candidate_result_digest,
        "expected_core_fingerprint": policy.expected_core_fingerprint,
        "locked_artifacts_before": before,
        "locked_artifacts_after": after,
        "case_summaries": case_summaries,
        "cross_case_findings": [
            row.model_dump(mode="json") for row in policy.cross_case_findings
        ],
        "rebuild_blocker_codes": sorted({row.code for row in rebuild_blockers}),
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
            "additional_retrieval": 0,
        },
        "stage_acceptance": {
            "locked_candidate_set_reviewed": locked_unchanged,
            "business_semantics_reviewed": True,
            "required_mutations_all_proven": all_mutations_pass,
            "held_out_interface_terminalization_pass": True,
            "held_out_product_generalization_pass": False,
            "sparse_dense_rebuild_admitted": False,
            "external_supplement_admitted": False,
            "model_synthesis_admitted": False,
        },
        "decision_zh": (
            "三案证明了同一接口可以完成候选终结，但没有证明本地对象和候选池足以形成当前期、"
            "可归因、单位可靠的研究证据包。先修通用父子对象展开、单位语义、当前期来源与"
            "缺口分类，再重跑同一冻结案例；在此之前不启动 sparse/dense 重建。"
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _validate_reviews(
    policy: HeldOutBusinessReviewPolicy,
    *,
    candidate_result: Mapping[str, Any],
    selection: Any,
    base_contract: Any,
) -> None:
    candidate_cases = {
        str(row["case_key"]): row for row in candidate_result["case_results"]
    }
    selected_cases = tuple(row.profile.case_key for row in selection.selections)
    if tuple(row.case_key for row in policy.case_reviews) != selected_cases:
        raise HeldOutBusinessReviewError(
            "held_out_business_review_case_order_or_identity_invalid"
        )
    required_mutations = {
        row.profile.case_key: next(
            archetype.required_mutations
            for archetype in base_contract.held_out_archetypes
            if archetype.archetype_id == row.archetype_id
        )
        for row in selection.selections
    }
    for review in policy.case_reviews:
        candidate_case = candidate_cases.get(review.case_key)
        if candidate_case is None:
            raise HeldOutBusinessReviewError(
                "held_out_business_review_candidate_case_missing"
            )
        candidate_lanes = {
            str(row["lane_id"]): row
            for row in candidate_case["query_lane_results"]
        }
        reviewed_lane_ids = tuple(row.lane_id for row in review.lane_reviews)
        if (
            len(reviewed_lane_ids) != len(set(reviewed_lane_ids))
            or set(reviewed_lane_ids) != set(candidate_lanes)
        ):
            raise HeldOutBusinessReviewError(
                "held_out_business_review_lane_coverage_invalid"
            )
        for lane_review in review.lane_reviews:
            if lane_review.verdict not in LANE_VERDICTS:
                raise HeldOutBusinessReviewError(
                    "held_out_business_review_lane_verdict_invalid"
                )
            candidate_refs = {
                str(row["target_id"])
                for row in candidate_lanes[lane_review.lane_id]["candidates"]
            }
            if (
                set(lane_review.useful_candidate_refs) - candidate_refs
                or (
                    lane_review.verdict in {"strong", "usable_with_parent_context"}
                    and not lane_review.useful_candidate_refs
                )
                or (
                    lane_review.verdict in {"off_target", "zero_result", "parser_unsafe"}
                    and lane_review.useful_candidate_refs
                )
                or not lane_review.business_answer_zh.strip()
                or not lane_review.limitation_zh.strip()
            ):
                raise HeldOutBusinessReviewError(
                    "held_out_business_review_candidate_binding_invalid"
                )
        mutation_ids = tuple(row.mutation_id for row in review.mutation_reviews)
        if mutation_ids != tuple(required_mutations[review.case_key]):
            raise HeldOutBusinessReviewError(
                "held_out_business_review_mutation_coverage_invalid"
            )
        if any(row.outcome not in MUTATION_OUTCOMES for row in review.mutation_reviews):
            raise HeldOutBusinessReviewError(
                "held_out_business_review_mutation_outcome_invalid"
            )
        known_lanes = set(candidate_lanes)
        for blocker in review.blockers:
            if set(blocker.affected_lane_ids) - known_lanes:
                raise HeldOutBusinessReviewError(
                    "held_out_business_review_blocker_lane_unknown"
                )
def _validate_hard_boundaries(boundary: Mapping[str, Any]) -> None:
    required_zero = {
        "network",
        "provider",
        "model",
        "embedding",
        "rerank",
        "evidence_promotion",
        "additional_retrieval",
    }
    if any(int(boundary.get(key, -1)) != 0 for key in required_zero):
        raise HeldOutBusinessReviewError(
            "held_out_business_review_zero_call_boundary_invalid"
        )
    if (
        boundary.get("candidate_set_must_remain_frozen") is not True
        or boundary.get("core_modification_allowed") is not False
        or boundary.get("index_rebuild_allowed") is not False
    ):
        raise HeldOutBusinessReviewError(
            "held_out_business_review_authority_boundary_invalid"
        )


def _load_result(path: Path, *, expected_digest: str) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HeldOutBusinessReviewError(
            "held_out_business_review_candidate_result_missing"
        ) from exc
    digest = str(result.get("result_digest") or "")
    body = {key: value for key, value in result.items() if key != "result_digest"}
    if digest != expected_digest or canonical_digest(body) != digest:
        raise HeldOutBusinessReviewError(
            "held_out_business_review_candidate_result_integrity_invalid"
        )
    return result


def _validate_locked_artifacts(
    policy: HeldOutBusinessReviewPolicy,
    *,
    repo_root: Path,
) -> None:
    identities = tuple(row.artifact_id for row in policy.locked_artifacts)
    if len(identities) < 3 or len(identities) != len(set(identities)):
        raise HeldOutBusinessReviewError(
            "held_out_business_review_locked_artifact_identity_invalid"
        )
    expected = {
        row.artifact_id: row.normalized_sha256 for row in policy.locked_artifacts
    }
    if _locked_digest_map(policy, repo_root=repo_root) != expected:
        raise HeldOutBusinessReviewError(
            "held_out_business_review_locked_artifact_digest_mismatch"
        )


def _locked_digest_map(
    policy: HeldOutBusinessReviewPolicy,
    *,
    repo_root: Path,
) -> dict[str, str]:
    return {
        row.artifact_id: normalized_sha256(_resolve(repo_root, row.path))
        for row in policy.locked_artifacts
    }


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


__all__ = [
    "HELD_OUT_REVIEW_POLICY_SCHEMA",
    "HELD_OUT_REVIEW_RESULT_SCHEMA",
    "HELD_OUT_REVIEW_RUN_SCOPE",
    "HeldOutBusinessReviewError",
    "HeldOutBusinessReviewPolicy",
    "execute_held_out_business_review",
    "load_held_out_business_review_policy",
]
