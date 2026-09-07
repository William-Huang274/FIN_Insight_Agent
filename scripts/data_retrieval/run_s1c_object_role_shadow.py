from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.cross_encoder import (  # noqa: E402
    cross_encoder_model_identity,
    load_local_cross_encoder,
    score_cross_encoder_pairs,
)
from retrieval.evidence_role import (  # noqa: E402
    LEGACY_EVIDENCE_SLOT_MAP,
    evaluate_evidence_role,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.ranking_comparison import load_ranking_queries  # noqa: E402


POLICY_SCHEMA_VERSION = "fin_ia_s1c_object_role_shadow_policy_v1_0"
RESULT_SCHEMA_VERSION = "fin_ia_s1c_object_role_shadow_result_v1_0"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _role_evaluation(
    *, relation: Mapping[str, Any], object_view: Mapping[str, Any]
) -> dict[str, Any]:
    slot_id = LEGACY_EVIDENCE_SLOT_MAP[str(relation["evidence_slot_id"])]
    document = {
        "ticker": object_view["ticker"],
        "section": object_view["section"],
        "subsection": object_view["subsection"],
        "source_type": object_view["source_type"],
        "document_text": object_view["surface_text"],
    }
    return evaluate_evidence_role(
        document,
        slot_id=slot_id,
        subject_ticker=str(relation["subject_ticker"]),
        evidence_owner_ticker=str(relation["evidence_owner_ticker"]),
        relationship_direction=str(relation["relationship_direction"]),
    ).as_dict()


def _ranking_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["relevance_judgement"] != "unjudged":
            by_query[row["qrel_id"]].append(row)

    pairwise_total = 0
    pairwise_wins = 0
    eligible_queries = 0
    top1_wins = 0
    top3_wins = 0
    details: list[dict[str, Any]] = []
    for qrel_id, candidates in sorted(by_query.items()):
        positives = [row for row in candidates if row["relevance_judgement"] == "positive"]
        negatives = [row for row in candidates if row["relevance_judgement"] == "hard_negative"]
        if not positives or not negatives:
            continue
        ordered = sorted(candidates, key=lambda row: (-row["cross_encoder_score"], row["review_id"]))
        comparisons = [(positive, negative) for positive in positives for negative in negatives]
        wins = sum(
            positive["cross_encoder_score"] > negative["cross_encoder_score"]
            for positive, negative in comparisons
        )
        pairwise_total += len(comparisons)
        pairwise_wins += wins
        eligible_queries += 1
        top1_wins += ordered[0]["relevance_judgement"] == "positive"
        top3_wins += any(
            row["relevance_judgement"] == "positive" for row in ordered[:3]
        )
        details.append(
            {
                "qrel_id": qrel_id,
                "judged_candidate_count": len(ordered),
                "positive_count": len(positives),
                "hard_negative_count": len(negatives),
                "pairwise_wins": wins,
                "pairwise_comparisons": len(comparisons),
                "top_ranked_review_id": ordered[0]["review_id"],
                "top_ranked_judgement": ordered[0]["relevance_judgement"],
                "ordered_reviews": [
                    {
                        "review_id": row["review_id"],
                        "object_form": row["object_form"],
                        "judgement": row["relevance_judgement"],
                        "score": row["cross_encoder_score"],
                    }
                    for row in ordered
                ],
            }
        )
    return {
        "eligible_query_count": eligible_queries,
        "pairwise_comparisons": pairwise_total,
        "positive_over_hard_negative_pairwise_accuracy": _ratio(
            pairwise_wins, pairwise_total
        ),
        "judged_query_top1_positive_rate": _ratio(top1_wins, eligible_queries),
        "judged_query_top3_positive_rate": _ratio(top3_wins, eligible_queries),
        "queries": details,
    }


def _role_metrics(
    *,
    rows: list[dict[str, Any]],
    annotations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    positives = [row for row in rows if row["relevance_judgement"] == "positive"]
    negatives = [row for row in rows if row["relevance_judgement"] == "hard_negative"]
    positive_compatible = sum(
        row["legacy_rule_role"]["compatibility"] == "compatible" for row in positives
    )
    negative_suppressed = sum(
        row["legacy_rule_role"]["compatibility"] == "incompatible" for row in negatives
    )
    positive_abstain = sum(
        row["legacy_rule_role"]["compatibility"] == "abstain" for row in positives
    )
    negative_abstain = sum(
        row["legacy_rule_role"]["compatibility"] == "abstain" for row in negatives
    )

    tp = fp = fn = 0
    object_rows: dict[str, dict[str, Any]] = {}
    for row in rows:
        object_id = str(row["object_view_id"])
        if object_id in object_rows:
            continue
        expected = set(annotations[object_id]["role_labels"])
        predicted = set(row["legacy_rule_role"]["labels"])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        object_rows[object_id] = {
            "object_view_id": object_id,
            "object_form": row["object_form"],
            "expected_roles": sorted(expected),
            "predicted_roles": sorted(predicted),
            "missing_roles": sorted(expected - predicted),
            "spurious_roles": sorted(predicted - expected),
        }
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 6) if precision + recall else 0.0

    errors_by_form: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        compatibility = row["legacy_rule_role"]["compatibility"]
        judgement = row["relevance_judgement"]
        form = row["object_form"]
        if judgement == "positive" and compatibility != "compatible":
            errors_by_form[form][f"positive_{compatibility}"] += 1
        if judgement == "hard_negative" and compatibility == "compatible":
            errors_by_form[form]["hard_negative_false_compatible"] += 1
    return {
        "positive_count": len(positives),
        "hard_negative_count": len(negatives),
        "positive_role_compatibility_rate": _ratio(
            positive_compatible, len(positives)
        ),
        "positive_role_abstain_rate": _ratio(positive_abstain, len(positives)),
        "hard_negative_role_suppression_rate": _ratio(
            negative_suppressed, len(negatives)
        ),
        "hard_negative_role_abstain_rate": _ratio(negative_abstain, len(negatives)),
        "multi_label_role_micro_precision": precision,
        "multi_label_role_micro_recall": recall,
        "multi_label_role_micro_f1": f1,
        "multi_label_counts": {"true_positive": tp, "false_positive": fp, "false_negative": fn},
        "errors_by_object_form": {
            form: dict(sorted(counts.items()))
            for form, counts in sorted(errors_by_form.items())
        },
        "object_role_details": sorted(
            object_rows.values(), key=lambda row: row["object_view_id"]
        ),
    }


def run(
    *,
    policy_path: Path,
    review_set_path: Path,
    qrels_path: Path,
    cross_encoder_model_dir: Path,
) -> dict[str, Any]:
    policy = _read_json(policy_path)
    review_set = _read_json(review_set_path)
    qrels_payload = _read_json(qrels_path)
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("object_role_shadow_policy_invalid")
    bindings = policy["bound_inputs"]
    if (
        str(bindings["review_set_sha256"]) != _sha256(review_set_path)
        or str(bindings["review_set_digest"]) != str(review_set["review_set_digest"])
        or str(bindings["qrels_sha256"]) != _sha256(qrels_path)
    ):
        raise ValueError("object_role_shadow_bound_input_drift")
    model_identity = cross_encoder_model_identity(cross_encoder_model_dir)
    if model_identity["model_digest"] != str(bindings["fixed_model_digest"]):
        raise ValueError("object_role_shadow_model_drift")

    views = {str(row["object_view_id"]): row for row in review_set["object_views"]}
    annotations = {
        str(row["object_view_id"]): row for row in review_set["object_annotations"]
    }
    queries = {query.qrel_id: query for query in load_ranking_queries(qrels_payload)}
    relations = review_set["query_relations"]
    scoring_manifest = [
        {
            "review_id": str(row["review_id"]),
            "qrel_id": str(row["qrel_id"]),
            "object_view_id": str(row["object_view_id"]),
        }
        for row in relations
    ]
    if len(scoring_manifest) != len({row["review_id"] for row in scoring_manifest}):
        raise ValueError("object_role_shadow_scoring_identity_invalid")
    pairs = [
        (
            queries[row["qrel_id"]].query_text("dense_bge_m3"),
            str(views[row["object_view_id"]]["surface_text"]),
        )
        for row in scoring_manifest
    ]

    import torch

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    runtime = load_local_cross_encoder(
        cross_encoder_model_dir,
        maximum_sequence_length=int(policy["model"]["maximum_sequence_length"]),
    )
    started = time.perf_counter()
    scores = score_cross_encoder_pairs(
        runtime,
        pairs,
        batch_size=int(policy["model"]["batch_size"]),
        progress_every=None,
    )
    elapsed = time.perf_counter() - started
    score_by_review = {
        row["review_id"]: float(score) for row, score in zip(scoring_manifest, scores)
    }

    evaluated: list[dict[str, Any]] = []
    for relation in relations:
        object_view = views[str(relation["object_view_id"])]
        legacy_role = _role_evaluation(relation=relation, object_view=object_view)
        evaluated.append(
            {
                "review_id": str(relation["review_id"]),
                "qrel_id": str(relation["qrel_id"]),
                "case_key": str(relation["case_key"]),
                "object_view_id": str(relation["object_view_id"]),
                "object_key": str(object_view["object_key"]),
                "object_form": str(object_view["object_form"]),
                "relevance_judgement": str(relation["relevance_judgement"]),
                "directness": str(relation["directness"]),
                "background_state": str(relation["background_state"]),
                "cross_encoder_score": round(score_by_review[str(relation["review_id"])], 8),
                "legacy_rule_role": legacy_role,
            }
        )

    ranking = _ranking_metrics(evaluated)
    role = _role_metrics(rows=evaluated, annotations=annotations)
    gates = policy["decision_gates"]
    cross_encoder_credible = (
        ranking["positive_over_hard_negative_pairwise_accuracy"]
        >= float(gates["cross_encoder_object_projection_credible_pairwise_minimum"])
        and ranking["judged_query_top1_positive_rate"]
        >= float(gates["cross_encoder_object_projection_credible_top1_minimum"])
    )
    rule_role_credible = (
        role["positive_role_compatibility_rate"]
        >= float(gates["existing_rule_role_credible_positive_compatibility_minimum"])
        and role["hard_negative_role_suppression_rate"]
        >= float(gates["existing_rule_role_credible_negative_suppression_minimum"])
        and role["multi_label_role_micro_f1"]
        >= float(gates["existing_rule_role_credible_multilabel_micro_f1_minimum"])
    )
    development_cases = {row["case_key"] for row in evaluated}
    fine_tuning_eligible = (
        len(evaluated)
        >= int(gates["minimum_reviewed_relations_before_any_fine_tuning"])
        and len(development_cases)
        >= int(gates["minimum_development_cases_before_any_fine_tuning"])
    )
    if cross_encoder_credible and not rule_role_credible:
        disposition = (
            "expand_source_bound_role_labels_then_run_separate_role_classifier_shadow;"
            "do_not_fine_tune_cross_encoder"
        )
    elif not cross_encoder_credible:
        disposition = (
            "repair_query_decomposition_or_object_projection_before_any_model_training"
        )
    else:
        disposition = "retain_fixed_cross_encoder_shadow_and_prepare_targeted_s1d_gap_review"

    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "object_bound_cross_encoder_and_role_shadow_complete",
        "recorded_at": "2026-08-12",
        "experiment_id": str(policy["experiment_id"]),
        "bound_inputs": {
            "policy_ref": policy_path.relative_to(ROOT).as_posix(),
            "policy_sha256": _sha256(policy_path),
            "review_set_ref": review_set_path.relative_to(ROOT).as_posix(),
            "review_set_sha256": _sha256(review_set_path),
            "review_set_digest": str(review_set["review_set_digest"]),
            "qrels_ref": qrels_path.relative_to(ROOT).as_posix(),
            "qrels_sha256": _sha256(qrels_path),
            "qrel_manifest_digest": str(qrels_payload["qrel_manifest_digest"]),
        },
        "execution": {
            "model_identity": model_identity,
            "scored_pair_count": len(pairs),
            "maximum_sequence_length": int(policy["model"]["maximum_sequence_length"]),
            "batch_size": int(policy["model"]["batch_size"]),
            "device": str(runtime[2]),
            "elapsed_seconds": round(elapsed, 3),
            "pairs_per_second": round(len(pairs) / elapsed, 3),
            "peak_gpu_memory_bytes": (
                int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
            ),
            "network_calls": 0,
            "training_steps": 0,
            "generation_model_calls": 0,
            "labels_joined_after_scoring": True,
        },
        "cross_encoder_development_review": ranking,
        "legacy_rule_role_development_review": role,
        "evaluated_relations": evaluated,
        "decision": {
            "cross_encoder_object_projection_credible": cross_encoder_credible,
            "legacy_rule_role_credible": rule_role_credible,
            "fine_tuning_eligible": fine_tuning_eligible,
            "next_disposition": disposition,
            "real_source_semantic_gap": {
                "code": "tsm_advanced_packaging_capacity_not_present_in_reviewed_target",
                "affected_qrels": ["s1c_qrel_06", "s1c_qrel_12", "s1c_qrel_18"],
                "owning_stage": "S1-D targeted source supplementation",
                "currently_authorized": False,
            },
            "representation_gap": {
                "code": "primary_pack_claim_or_metric_surface_unbound_for_role_training",
                "affected_evidence_item_count": int(
                    review_set["summary"][
                        "primary_pack_unbound_claim_or_metric_surface_count"
                    ]
                ),
                "owning_stage": "S1-C object compiler and reviewed role labels",
            },
        },
        "authority": {
            "candidate_is_not_evidence": True,
            "evidence_promoted": False,
            "cross_encoder_runtime_promoted": False,
            "legacy_rule_role_runtime_promoted": False,
            "fine_tuning_authorized": False,
            "s1d_authorized": False,
            "s1_complete_claimed": False,
        },
        "known_boundary": (
            "This fixed-model result is a post-contract development audit on 24 source-bound "
            "objects and 35 reviewed relations. It does not reuse ORCL, ASML or ANET, does "
            "not train a model, and cannot establish independent generalization or Evidence authority."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fixed Cross-Encoder and legacy role rules on object-bound reviews."
    )
    parser.add_argument(
        "--policy",
        default="configs/retrieval/fin_ia_0_1_3_s1c_object_role_shadow_policy_v1_0.json",
    )
    parser.add_argument(
        "--review-set",
        default="configs/retrieval/fin_ia_0_1_3_s1c_object_role_review_set_v1_0.json",
    )
    parser.add_argument(
        "--qrels",
        default="configs/retrieval/fin_ia_0_1_3_s1c_requalified_qrels_v1_1.json",
    )
    parser.add_argument("--cross-encoder-model", required=True)
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_object_role_shadow_result_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        policy_path=_resolve(args.policy),
        review_set_path=_resolve(args.review_set),
        qrels_path=_resolve(args.qrels),
        cross_encoder_model_dir=_resolve(args.cross_encoder_model),
    )
    output = _resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "execution": result["execution"],
                "cross_encoder": {
                    key: value
                    for key, value in result["cross_encoder_development_review"].items()
                    if key != "queries"
                },
                "legacy_rule_role": {
                    key: value
                    for key, value in result[
                        "legacy_rule_role_development_review"
                    ].items()
                    if key not in {"object_role_details"}
                },
                "decision": result["decision"],
                "result_digest": result["result_digest"],
                "output": output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
