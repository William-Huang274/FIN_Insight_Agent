from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .query_plan import canonical_digest


class QualificationEvaluationError(ValueError):
    """A frozen qualification result cannot be evaluated safely."""


_FACET_NAMES_ZH = {
    "direct_support": "直接证据",
    "counterevidence": "反方证据",
    "alternative_explanation": "替代解释",
    "numeric_bridge": "数值桥",
    "independent_readthrough": "独立旁证",
}

_ROLE_NAMES_ZH = {
    "direct": "直接支持",
    "counter": "反方",
    "bridge": "数值桥接",
    "context": "背景/替代解释",
}


def _rank_map(values: Sequence[str]) -> dict[str, int]:
    return {str(value): index for index, value in enumerate(values, 1)}


def _short_text(value: object, *, maximum: int = 360) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


def _safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0


def _require_unique_by(
    rows: Sequence[Mapping[str, Any]], key: str, *, label: str
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if not value or value in output:
            raise QualificationEvaluationError(f"{label}_key_invalid:{value}")
        output[value] = row
    return output


def _object_summary(
    object_id: str, objects_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    row = objects_by_id.get(object_id)
    if row is None:
        return {
            "compiled_object_id": object_id,
            "catalog_present": False,
            "object_kind": None,
            "company": None,
            "fiscal_year": None,
            "publication_date": None,
            "source_type": None,
            "source_record_id": None,
            "snippet": None,
        }
    base = row.get("base_object_view") or {}
    return {
        "compiled_object_id": object_id,
        "catalog_present": True,
        "object_kind": row.get("object_kind"),
        "company": base.get("company"),
        "fiscal_year": base.get("fiscal_year"),
        "publication_date": base.get("publication_date"),
        "source_type": base.get("source_type"),
        "source_record_id": base.get("source_record_id"),
        "snippet": _short_text(row.get("model_text")),
    }


def _miss_owner(
    *, catalog_present: bool, reranker_pool_present: bool, final_rank: int | None
) -> str:
    if not catalog_present:
        return "source_parser_or_object_compilation"
    if not reranker_pool_present:
        return "typed_recall_or_reranker_pool_cutoff"
    if final_rank is None:
        return "candidate_manifest_drift"
    if final_rank > 20:
        return "financial_shortlist_or_fusion_ranking"
    return "retrieved_in_review_window"


def _business_assessment(
    *,
    proposition_id: str,
    question_zh: str,
    missing_facets: Sequence[str],
    missing_roles: Sequence[str],
    missing_positive_notes: Sequence[str],
    business_template: str,
) -> str:
    if not missing_facets and not missing_roles and not missing_positive_notes:
        return (
            f"“{question_zh}”所需的已审材料均进入前 20 候选；这只证明候选可供复核，"
            "不等于已经成为 Evidence 或最终研究结论。"
        )
    details: list[str] = []
    if missing_facets:
        details.append(
            "缺少" + "、".join(_FACET_NAMES_ZH.get(row, row) for row in missing_facets)
        )
    if missing_roles:
        details.append(
            "缺少" + "、".join(_ROLE_NAMES_ZH.get(row, row) for row in missing_roles)
            + "角色"
        )
    if missing_positive_notes:
        details.append("未进入前 20 的材料包括：" + "；".join(missing_positive_notes))
    prefix = f"{proposition_id}（{question_zh}）：" + "；".join(details) + "。"
    return prefix + (business_template or "该缺口会削弱下游研究判断的完整性。")


def evaluate_frozen_candidates(
    *,
    raw: Mapping[str, Any],
    references: Sequence[Mapping[str, Any]],
    objects: Sequence[Mapping[str, Any]],
    metric_contract: Mapping[str, Any],
    business_templates_zh: Mapping[str, str],
) -> dict[str, Any]:
    """Evaluate an immutable label-blind candidate result.

    The function never promotes a candidate to Evidence or NumericFact.  It is
    intentionally CPU-only deterministic bookkeeping over already-frozen ranks;
    learned vector work must have happened in the preceding CUDA-only run.
    """

    if raw.get("status") != "candidate_generation_complete_labels_not_loaded":
        raise QualificationEvaluationError("candidate_raw_status_invalid")
    execution = raw.get("execution") or {}
    authority = raw.get("authority") or {}
    if execution.get("labels_loaded") is not False:
        raise QualificationEvaluationError("candidate_runtime_was_not_label_blind")
    if authority.get("qualification_scored") is not False:
        raise QualificationEvaluationError("candidate_was_already_scored")
    if authority.get("evidence_promotion_authorized") is not False:
        raise QualificationEvaluationError("candidate_evidence_authority_invalid")
    if authority.get("numeric_fact_authority") is not False:
        raise QualificationEvaluationError("candidate_numeric_authority_invalid")

    propositions = _require_unique_by(
        list(raw.get("propositions") or ()), "example_id", label="candidate_proposition"
    )
    reference_map = _require_unique_by(references, "example_id", label="reference")
    if set(propositions) != set(reference_map):
        raise QualificationEvaluationError("candidate_reference_example_set_mismatch")
    objects_by_id = _require_unique_by(objects, "compiled_object_id", label="object")

    review_k = int(metric_contract["candidate_review_k"])
    if review_k != 20:
        raise QualificationEvaluationError("unsupported_candidate_review_k")

    proposition_results: list[dict[str, Any]] = []
    owner_counts: Counter[str] = Counter()
    total_positives = 0
    total_positive_hits = 0
    total_required_facets = 0
    total_covered_facets = 0
    total_required_roles = 0
    total_covered_roles = 0

    stage_names = (
        "candidate_union_top20",
        "bge_reranker_top20",
        "qwen_reranker_top20",
        "role_guarded_top20",
        "candidate_review_top20",
    )
    stage_positive_hits: dict[str, int] = {name: 0 for name in stage_names}

    for example_id in sorted(propositions):
        candidate = propositions[example_id]
        reference = reference_map[example_id]
        expected = reference.get("expected_outcome") or {}
        if expected.get("case_key") != candidate.get("case_key"):
            raise QualificationEvaluationError(f"case_key_mismatch:{example_id}")
        if reference.get("review_state") != "qualification_blinded":
            raise QualificationEvaluationError(f"reference_review_state_invalid:{example_id}")
        boundary = expected.get("authority_boundary") or {}
        if boundary.get("runtime_may_read_reference") is not False:
            raise QualificationEvaluationError(
                f"reference_runtime_boundary_invalid:{example_id}"
            )
        if boundary.get("owner_or_qualified_human_review_pending") is not True:
            raise QualificationEvaluationError(
                f"reference_adjudication_boundary_invalid:{example_id}"
            )

        positive_rows = list(expected.get("positive_candidates") or ())
        positive_ids = [str(row.get("compiled_object_id") or "") for row in positive_rows]
        if not positive_ids or len(positive_ids) != len(set(positive_ids)):
            raise QualificationEvaluationError(f"positive_candidate_ids_invalid:{example_id}")

        final_rows = list(candidate.get("final_shortlist") or ())
        final_rank = {
            str(row.get("compiled_object_id") or ""): int(row.get("rank"))
            for row in final_rows
        }
        stage_ranks = {
            name: _rank_map(list(candidate.get(name) or ())) for name in stage_names
        }
        reranker_pool_ids = set((candidate.get("bge_best_need_by_candidate") or {}).keys())
        reranker_pool_ids.update(
            (candidate.get("qwen_best_need_by_candidate") or {}).keys()
        )
        review_ids = set(stage_ranks["candidate_review_top20"])
        hit_rows = [row for row in positive_rows if row["compiled_object_id"] in review_ids]
        hit_ids = {str(row["compiled_object_id"]) for row in hit_rows}

        required_facets = sorted(set(expected.get("required_facets") or ()))
        required_roles = sorted(set(expected.get("required_roles") or ()))
        covered_facets = sorted(
            set().union(*(set(row.get("facets") or ()) for row in hit_rows))
            if hit_rows
            else set()
        )
        covered_roles = sorted(
            set().union(*(set(row.get("roles") or ()) for row in hit_rows))
            if hit_rows
            else set()
        )
        missing_facets = sorted(set(required_facets) - set(covered_facets))
        missing_roles = sorted(set(required_roles) - set(covered_roles))

        positive_diagnostics: list[dict[str, Any]] = []
        missing_notes: list[str] = []
        for positive in positive_rows:
            object_id = str(positive["compiled_object_id"])
            summary = _object_summary(object_id, objects_by_id)
            rank = final_rank.get(object_id)
            owner = _miss_owner(
                catalog_present=bool(summary["catalog_present"]),
                reranker_pool_present=object_id in reranker_pool_ids,
                final_rank=rank,
            )
            owner_counts[owner] += 1
            if object_id not in hit_ids:
                missing_notes.append(str(positive.get("review_note_zh") or object_id))
            positive_diagnostics.append(
                {
                    **summary,
                    "review_note_zh": positive.get("review_note_zh"),
                    "expected_facets": sorted(positive.get("facets") or ()),
                    "expected_roles": sorted(positive.get("roles") or ()),
                    "reranker_pool_present": object_id in reranker_pool_ids,
                    "final_rank": rank,
                    "in_candidate_review_top20": object_id in hit_ids,
                    "stage_ranks": {
                        name: stage_ranks[name].get(object_id) for name in stage_names
                    },
                    "failure_owner": owner,
                }
            )

        top_candidates: list[dict[str, Any]] = []
        positive_id_set = set(positive_ids)
        for object_id in list(candidate.get("candidate_review_top20") or ())[:5]:
            top_candidates.append(
                {
                    **_object_summary(str(object_id), objects_by_id),
                    "reference_status": (
                        "material_positive" if object_id in positive_id_set else "unjudged"
                    ),
                }
            )

        for stage_name, ranks in stage_ranks.items():
            stage_positive_hits[stage_name] += len(positive_id_set & set(ranks))

        total_positives += len(positive_ids)
        total_positive_hits += len(hit_ids)
        total_required_facets += len(required_facets)
        total_covered_facets += len(set(required_facets) & set(covered_facets))
        total_required_roles += len(required_roles)
        total_covered_roles += len(set(required_roles) & set(covered_roles))

        proposition_results.append(
            {
                "example_id": example_id,
                "case_key": expected.get("case_key"),
                "proposition_id": expected.get("proposition_id"),
                "question_zh": candidate.get("question_zh"),
                "reference_review_state": reference.get("review_state"),
                "reference_authority": reference.get("adjudication_authority"),
                "metrics": {
                    "any_hit_at_20": bool(hit_ids),
                    "positive_objects_expected": len(positive_ids),
                    "positive_objects_at_20": len(hit_ids),
                    "positive_object_recall_at_20": _safe_ratio(
                        len(hit_ids), len(positive_ids)
                    ),
                    "required_facets": required_facets,
                    "covered_required_facets_at_20": sorted(
                        set(required_facets) & set(covered_facets)
                    ),
                    "missing_required_facets_at_20": missing_facets,
                    "material_facet_coverage_at_20": _safe_ratio(
                        len(set(required_facets) & set(covered_facets)),
                        len(required_facets),
                    ),
                    "required_roles": required_roles,
                    "covered_required_roles_at_20": sorted(
                        set(required_roles) & set(covered_roles)
                    ),
                    "missing_required_roles_at_20": missing_roles,
                    "required_role_coverage_at_20": _safe_ratio(
                        len(set(required_roles) & set(covered_roles)),
                        len(required_roles),
                    ),
                },
                "positive_candidate_diagnostics": positive_diagnostics,
                "top5_candidate_review": top_candidates,
                "business_assessment_zh": _business_assessment(
                    proposition_id=str(expected.get("proposition_id") or example_id),
                    question_zh=str(candidate.get("question_zh") or ""),
                    missing_facets=missing_facets,
                    missing_roles=missing_roles,
                    missing_positive_notes=missing_notes,
                    business_template=str(
                        business_templates_zh.get(
                            str(expected.get("proposition_id") or ""), ""
                        )
                    ),
                ),
                "candidate_is_not_evidence": True,
                "numeric_fact_authority": False,
                "public_information_gap_declared": False,
            }
        )

    example_count = len(proposition_results)
    propositions_with_hit = sum(
        1 for row in proposition_results if row["metrics"]["any_hit_at_20"]
    )
    aggregate = {
        "example_count": example_count,
        "proposition_any_hit_at_20": _safe_ratio(propositions_with_hit, example_count),
        "all_positive_object_recall_at_20": _safe_ratio(
            total_positive_hits, total_positives
        ),
        "material_facet_coverage_at_20": _safe_ratio(
            total_covered_facets, total_required_facets
        ),
        "required_role_coverage_at_20": _safe_ratio(
            total_covered_roles, total_required_roles
        ),
        "positive_objects_expected": total_positives,
        "positive_objects_at_20": total_positive_hits,
    }
    thresholds = {
        "proposition_any_hit_at_20": float(
            metric_contract["proposition_any_hit_minimum"]
        ),
        "all_positive_object_recall_at_20": float(
            metric_contract["all_positive_object_recall_minimum"]
        ),
        "material_facet_coverage_at_20": float(
            metric_contract["material_facet_coverage_minimum"]
        ),
        "required_role_coverage_at_20": float(
            metric_contract["required_role_coverage_minimum"]
        ),
    }
    metric_pass = {
        key: aggregate[key] >= minimum for key, minimum in thresholds.items()
    }
    stage_recall = {
        stage: _safe_ratio(count, total_positives)
        for stage, count in stage_positive_hits.items()
    }
    result = {
        "aggregate_metrics": aggregate,
        "thresholds": thresholds,
        "metric_pass": metric_pass,
        "candidate_ranking_metric_gate_pass": all(metric_pass.values()),
        "stage_positive_object_recall_at_20": stage_recall,
        "failure_owner_counts": dict(sorted(owner_counts.items())),
        "propositions": proposition_results,
        "authority_boundary": {
            "reference_is_owner_gold": False,
            "owner_or_qualified_human_review_pending": True,
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
            "public_information_gap_declared": False,
            "s1_qualified": False,
        },
    }
    result["evaluation_digest"] = canonical_digest(result)
    return result


__all__ = [
    "QualificationEvaluationError",
    "evaluate_frozen_candidates",
]
