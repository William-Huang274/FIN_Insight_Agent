from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.financial_evidence_shortlist import (  # noqa: E402
    rank_financial_evidence_shortlist,
)
from retrieval.query_atom_shadow import compile_atom_lane, load_query_atoms  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402


POLICY_SCHEMA_VERSION = "fin_ia_s1_vs3_financial_shortlist_policy_v1_0"
POLICY_OVERLAY_SCHEMA_VERSION = "fin_ia_s1_vs3_financial_shortlist_policy_v1_1"
RESULT_SCHEMA_VERSION = "fin_ia_s1_vs3_financial_shortlist_result_v1_0"
SUMMARY_SCHEMA_VERSION = "fin_ia_s1_vs3_financial_shortlist_summary_v1_0"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _load_policy(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if raw.get("schema_version") != POLICY_OVERLAY_SCHEMA_VERSION:
        return raw
    parent_path = _resolve(str(raw.get("parent_policy_ref") or ""))
    if _sha256_lf(parent_path) != str(raw.get("parent_policy_sha256_lf") or ""):
        raise ValueError("financial_shortlist_parent_policy_drift")
    parent = _read_json(parent_path)
    if parent.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("financial_shortlist_parent_policy_schema_invalid")
    merged = dict(parent)
    merged.update(
        {
            "schema_version": POLICY_SCHEMA_VERSION,
            "status": raw["status"],
            "recorded_at": raw["recorded_at"],
            "experiment_id": raw["experiment_id"],
            "policy_lineage": {
                "parent_policy_ref": _relative(parent_path),
                "parent_policy_sha256_lf": raw["parent_policy_sha256_lf"],
            },
        }
    )
    bindings = dict(parent.get("bound_inputs") or {})
    bindings.update(raw.get("bound_input_overrides") or {})
    merged["bound_inputs"] = bindings
    for key in (
        "shortlist_contract",
        "decision_gates",
        "successor_basis",
        "token_budget_basis",
        "authority",
    ):
        if key in raw:
            merged[key] = raw[key]
    return merged


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _load_bound_paths(policy: Mapping[str, Any]) -> dict[str, Path]:
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ValueError("financial_shortlist_policy_schema_invalid")
    paths: dict[str, Path] = {}
    bindings = policy["bound_inputs"]
    for key, value in bindings.items():
        if not key.endswith("_ref"):
            continue
        prefix = key[:-4]
        path = _resolve(str(value))
        expected = str(bindings.get(f"{prefix}_sha256_lf") or "")
        if not path.is_file() or _sha256_lf(path) != expected:
            raise ValueError(f"financial_shortlist_input_drift:{prefix}")
        paths[prefix] = path
    return paths


def _rank_maps(atom_row: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for route_id, values in (atom_row.get("reranker_ranked_ids") or {}).items():
        for rank, object_id in enumerate(values, start=1):
            output.setdefault(str(object_id), {})[str(route_id)] = rank
    return output


def _evaluate(
    rows: Sequence[Mapping[str, Any]], *, atom: Any, top_k: int
) -> dict[str, Any]:
    rank_by_id = {
        str(row["compiled_object_id"]): rank for rank, row in enumerate(rows, start=1)
    }
    positive_ranks = [
        rank_by_id[value] for value in atom.positive_object_ids if value in rank_by_id
    ]
    negative_ranks = [
        rank_by_id[value]
        for value in atom.hard_negative_object_ids
        if value in rank_by_id
    ]
    best = min(positive_ranks, default=None)
    return {
        "positive_target_available": bool(atom.positive_object_ids),
        "positive_target_in_ranking": bool(positive_ranks),
        "positive_target_rank": best,
        "positive_target_in_top_k": best is not None and best <= top_k,
        "hard_negative_in_top_k_count": sum(rank <= top_k for rank in negative_ranks),
        "reciprocal_rank": round(1.0 / best, 6) if best else 0.0,
    }


def run(policy_path: Path) -> dict[str, Any]:
    policy = _load_policy(policy_path)
    paths = _load_bound_paths(policy)
    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    atoms = load_query_atoms(_read_json(paths["query_atom_eval"]))
    objects = _read_jsonl(paths["compiled_objects"])
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    ranking_summary = _read_json(paths["ranking_summary"])
    full_path = _resolve(str(ranking_summary["storage"]["full_result_ref"]))
    if _sha256_lf(full_path) != str(ranking_summary["storage"]["full_result_sha256"]):
        raise ValueError("financial_shortlist_full_ranking_drift")
    ranking = _read_json(full_path)
    ranking_atoms = {str(row["atom_id"]): row for row in ranking["atoms"]}
    role_replay = _read_json(paths["role_replay_result"])
    replay_decision = role_replay["decision"]
    replay_qualified = (
        replay_decision.get("composite_financial_evidence_quality_gate_passed")
        if "composite_financial_evidence_quality_gate_passed" in replay_decision
        else replay_decision.get("evidence_role_quality_gate_passed")
    )
    if replay_qualified is not True:
        raise ValueError("financial_shortlist_role_replay_not_qualified")
    intent_ontology = (
        _read_json(paths["financial_intent_ontology"])
        if "financial_intent_ontology" in paths
        else None
    )

    top_k = int(policy["shortlist_contract"]["evaluation_top_k"])
    review_limit = int(policy["shortlist_contract"]["review_queue_per_atom"])
    atom_rows: list[dict[str, Any]] = []
    for atom in atoms:
        _, lane = compile_atom_lane(atom, kernel)
        source = ranking_atoms[atom.atom_id]
        union_ids = tuple(str(value) for value in source["candidate_union_ids"])
        ranked = rank_financial_evidence_shortlist(
            union_object_ids=union_ids,
            objects_by_id=objects_by_id,
            lane=lane,
            route_membership=source["route_membership"],
            cross_encoder_ranks_by_id=_rank_maps(source),
            request=atom.request_payload if intent_ontology is not None else None,
            intent_ontology=intent_ontology,
            retrieval_needs=(
                source.get("retrieval_need_set") or {}
            ).get("needs") or (),
        )
        evaluation = _evaluate(ranked, atom=atom, top_k=top_k)
        positive = set(atom.positive_object_ids)
        negative = set(atom.hard_negative_object_ids)
        unjudged = set(atom.unjudged_object_ids)
        review_queue = []
        for rank, features in enumerate(ranked[:review_limit], start=1):
            object_id = str(features["compiled_object_id"])
            obj = objects_by_id[object_id]
            review_queue.append(
                {
                    "rank": rank,
                    "compiled_object_id": object_id,
                    "development_judgement": (
                        "positive"
                        if object_id in positive
                        else "hard_negative"
                        if object_id in negative
                        else "unjudged"
                        if object_id in unjudged
                        else "unlabelled"
                    ),
                    "text_excerpt": str(obj.get("model_text") or "")[:360],
                    "features": features,
                }
            )
        atom_rows.append(
            {
                "atom_id": atom.atom_id,
                "case_key": str(atom.request_payload["case_key"]),
                "facet_id": lane.facet_id,
                "candidate_union_count": len(union_ids),
                "evaluation": evaluation,
                "review_queue": review_queue,
                "full_ranked_ids": [
                    str(value["compiled_object_id"]) for value in ranked
                ],
            }
        )

    positive_atoms = [
        row for row in atom_rows if row["evaluation"]["positive_target_available"]
    ]
    top_count = sum(
        row["evaluation"]["positive_target_in_top_k"] for row in positive_atoms
    )
    negative_top_count = sum(
        row["evaluation"]["hard_negative_in_top_k_count"] for row in atom_rows
    )
    mean_rr = (
        sum(row["evaluation"]["reciprocal_rank"] for row in positive_atoms)
        / len(positive_atoms)
        if positive_atoms
        else 0.0
    )
    gates = policy["decision_gates"]
    head_passed = (
        top_count / len(positive_atoms)
        >= float(gates["positive_target_in_head_minimum_rate"])
        and negative_top_count
        <= int(gates["hard_negative_in_head_maximum_count"])
    )
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "zero_call_financial_shortlist_materialized",
        "recorded_at": "2026-08-17",
        "experiment_id": policy["experiment_id"],
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256_lf": _sha256_lf(policy_path),
            **{
                f"{key}_ref": _relative(path)
                for key, path in paths.items()
            },
            "ranking_full_result_ref": _relative(full_path),
            "ranking_full_result_sha256_lf": _sha256_lf(full_path),
        },
        "execution": {
            "network_calls": 0,
            "generation_model_calls": 0,
            "training_steps": 0,
            "labels_joined_after_shortlist_ranking": True,
        },
        "summary": {
            "atom_count": len(atom_rows),
            "positive_atom_count": len(positive_atoms),
            "positive_target_in_top10_count": top_count,
            "positive_target_in_top10_rate": round(
                top_count / len(positive_atoms), 6
            ),
            "mean_reciprocal_rank": round(mean_rr, 6),
            "hard_negative_in_top10_count": negative_top_count,
            "review_queue_total": sum(len(row["review_queue"]) for row in atom_rows),
            "candidate_decision_universe_preserved": sum(
                row["candidate_union_count"] for row in atom_rows
            ),
        },
        "atoms": atom_rows,
        "decision": {
            "development_head_quality_gate_passed": head_passed,
            "runtime_route_promotion_authorized": False,
            "runtime_evidence_promotion_authorized": False,
            "review_queue_is_priority_projection_not_candidate_drop": True,
            "owner_acceptance": False,
            "fine_tuning_authorized": False,
            "s1_complete_claimed": False,
        },
        "authority": policy["authority"],
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _compact(result: Mapping[str, Any], *, full_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "experiment_id": result["experiment_id"],
        "storage": {
            "full_result_ref": _relative(full_path),
            "full_result_sha256_lf": _sha256_lf(full_path),
            "full_result_digest": result["result_digest"],
        },
        "bound_inputs": result["bound_inputs"],
        "execution": result["execution"],
        "summary": result["summary"],
        "decision": result["decision"],
        "authority": result["authority"],
        "result_digest": result["result_digest"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the VS3 financial shortlist.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--full-output-root", required=True)
    parser.add_argument("--summary-output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(_resolve(args.policy))
    full_root = _resolve(args.full_output_root)
    full_path = full_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path=full_path)
    _write_json(_resolve(args.summary_output), summary)
    print(json.dumps(summary["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["decision"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
