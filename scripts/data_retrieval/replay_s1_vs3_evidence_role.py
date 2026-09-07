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
from retrieval.evidence_role import evaluate_evidence_role  # noqa: E402
from retrieval.financial_intent import (  # noqa: E402
    combine_financial_evidence_compatibility,
    evaluate_financial_intent,
)
from retrieval.query_atom_shadow import compile_atom_lane, load_query_atoms  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402


POLICY_SCHEMA_VERSION = "fin_ia_s1_vs3_evidence_role_replay_policy_v1_0"
POLICY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1_vs3_evidence_role_replay_policy_v1_1"
)
POLICY_OVERLAY_SCHEMA_VERSION = (
    "fin_ia_s1_vs3_evidence_role_replay_policy_v1_2"
)
RESULT_SCHEMA_VERSION = "fin_ia_s1_vs3_evidence_role_replay_result_v1_0"
RESULT_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_s1_vs3_evidence_role_replay_result_v1_1"
)


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
        raise ValueError("evidence_role_replay_parent_policy_drift")
    parent = _read_json(parent_path)
    if parent.get("schema_version") != POLICY_SUCCESSOR_SCHEMA_VERSION:
        raise ValueError("evidence_role_replay_parent_policy_schema_invalid")
    merged = dict(parent)
    merged.update(
        {
            "schema_version": POLICY_SUCCESSOR_SCHEMA_VERSION,
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
    for key in ("decision_gates", "change_scope", "token_budget_basis", "authority"):
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


def _metrics(
    rows: Sequence[Mapping[str, Any]], *, evaluation_key: str = "evaluation"
) -> dict[str, Any]:
    positives = [row for row in rows if row["judgement"] == "positive"]
    negatives = [row for row in rows if row["judgement"] == "hard_negative"]
    compatible = sum(
        row[evaluation_key]["compatibility"] == "compatible" for row in positives
    )
    suppressed = sum(
        row[evaluation_key]["compatibility"] != "compatible" for row in negatives
    )
    return {
        "positive_count": len(positives),
        "hard_negative_count": len(negatives),
        "positive_compatible_count": compatible,
        "positive_compatible_rate": (
            round(compatible / len(positives), 6) if positives else None
        ),
        "hard_negative_suppressed_or_abstained_count": suppressed,
        "hard_negative_suppressed_or_abstained_rate": (
            round(suppressed / len(negatives), 6) if negatives else None
        ),
    }


def _composite_evaluation(
    *, role: Mapping[str, Any], intent: Mapping[str, Any], has_typed_intent: bool
) -> dict[str, Any]:
    role_state = str(role["compatibility"])
    intent_state = str(intent["compatibility"])
    compatibility = combine_financial_evidence_compatibility(
        role_compatibility=role_state,
        intent_compatibility=intent_state,
        has_typed_intent=has_typed_intent,
    )
    return {
        "compatibility": compatibility,
        "evidence_role_compatibility": role_state,
        "financial_intent_compatibility": intent_state,
        "has_typed_intent": has_typed_intent,
        "candidate_not_evidence": True,
    }


def run(policy_path: Path) -> dict[str, Any]:
    policy = _load_policy(policy_path)
    policy_schema = policy.get("schema_version")
    if policy_schema not in {
        POLICY_SCHEMA_VERSION,
        POLICY_SUCCESSOR_SCHEMA_VERSION,
    }:
        raise ValueError("evidence_role_replay_policy_schema_invalid")
    bindings = policy["bound_inputs"]
    paths: dict[str, Path] = {}
    for key, value in bindings.items():
        if not key.endswith("_ref"):
            continue
        prefix = key[:-4]
        path = _resolve(str(value))
        expected = str(bindings.get(f"{prefix}_sha256_lf") or "")
        if not path.is_file() or _sha256_lf(path) != expected:
            raise ValueError(f"evidence_role_replay_input_drift:{prefix}")
        paths[prefix] = path

    kernel = load_financial_research_kernel(_read_json(paths["kernel"]))
    atoms = load_query_atoms(_read_json(paths["query_atom_eval"]))
    objects = _read_jsonl(paths["compiled_objects"])
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    ranking_summary = _read_json(paths["ranking_summary"])
    full_path = _resolve(str(ranking_summary["storage"]["full_result_ref"]))
    if _sha256_lf(full_path) != str(ranking_summary["storage"]["full_result_sha256"]):
        raise ValueError("evidence_role_replay_full_ranking_drift")
    ranking = _read_json(full_path)
    intent_ontology = (
        _read_json(paths["financial_intent_ontology"])
        if "financial_intent_ontology" in paths
        else None
    )
    if policy_schema == POLICY_SUCCESSOR_SCHEMA_VERSION and intent_ontology is None:
        raise ValueError("evidence_role_replay_financial_intent_ontology_missing")
    candidate_ids_by_atom = {
        str(row["atom_id"]): tuple(str(value) for value in row["candidate_union_ids"])
        for row in ranking["atoms"]
    }

    all_label_rows: list[dict[str, Any]] = []
    candidate_label_rows: list[dict[str, Any]] = []
    atom_rows: list[dict[str, Any]] = []
    for atom in atoms:
        request, lane = compile_atom_lane(atom, kernel)
        positive = set(atom.positive_object_ids)
        negative = set(atom.hard_negative_object_ids)
        labelled_ids = tuple(dict.fromkeys((*positive, *negative)))
        candidate_ids = set(candidate_ids_by_atom.get(atom.atom_id, ()))
        rows: list[dict[str, Any]] = []
        for object_id in labelled_ids:
            if object_id not in objects_by_id:
                raise ValueError(f"evidence_role_replay_object_missing:{object_id}")
            obj = objects_by_id[object_id]
            base = obj["base_object_view"]
            evaluation = evaluate_evidence_role(
                {
                    "ticker": base.get("ticker"),
                    "section": base.get("section"),
                    "subsection": base.get("subsection"),
                    "source_type": base.get("source_type"),
                    "object_kind": obj.get("object_kind"),
                    "document_text": obj.get("model_text"),
                    "structured_projection": obj.get("structured_projection"),
                },
                slot_id=lane.slot_id,
                facet_id=lane.facet_id,
                subject_ticker=lane.subject_ticker,
                evidence_owner_ticker=lane.evidence_owner_tickers[0],
                relationship_direction=lane.relationship_constraints[0],
            ).as_dict()
            intent = (
                evaluate_financial_intent(
                    obj,
                    metric_intents=tuple(atom.request_payload.get("metric_intents") or ()),
                    product_intents=tuple(atom.request_payload.get("product_intents") or ()),
                    acceptable_proxy=bool(atom.request_payload.get("acceptable_proxy")),
                    ontology=intent_ontology,
                ).as_dict()
                if intent_ontology is not None
                else {
                    "compatibility": "abstain",
                    "candidate_not_evidence": True,
                }
            )
            composite = _composite_evaluation(
                role=evaluation,
                intent=intent,
                has_typed_intent=bool(
                    atom.request_payload.get("metric_intents")
                    or atom.request_payload.get("product_intents")
                ),
            )
            row = {
                "compiled_object_id": object_id,
                "judgement": "positive" if object_id in positive else "hard_negative",
                "expected_roles": list(
                    atom.expected_roles_by_object_id.get(object_id, ())
                ),
                "in_candidate_union": object_id in candidate_ids,
                "evaluation": evaluation,
                "financial_intent_evaluation": intent,
                "composite_evaluation": composite,
            }
            rows.append(row)
            all_label_rows.append(row)
            if object_id in candidate_ids:
                candidate_label_rows.append(row)
        atom_rows.append(
            {
                "atom_id": atom.atom_id,
                "case_key": request.case_key,
                "facet_id": lane.facet_id,
                "label_metrics": _metrics(rows),
                "financial_intent_metrics": _metrics(
                    rows, evaluation_key="financial_intent_evaluation"
                ),
                "composite_metrics": _metrics(
                    rows, evaluation_key="composite_evaluation"
                ),
                "rows": rows,
            }
        )

    metrics = _metrics(all_label_rows)
    candidate_metrics = _metrics(candidate_label_rows)
    intent_metrics = _metrics(
        all_label_rows, evaluation_key="financial_intent_evaluation"
    )
    composite_metrics = _metrics(
        all_label_rows, evaluation_key="composite_evaluation"
    )
    candidate_composite_metrics = _metrics(
        candidate_label_rows, evaluation_key="composite_evaluation"
    )
    gates = policy["decision_gates"]
    gate_metrics = (
        composite_metrics
        if policy_schema == POLICY_SUCCESSOR_SCHEMA_VERSION
        else metrics
    )
    passed = (
        float(gate_metrics["positive_compatible_rate"] or 0.0)
        >= float(gates["judged_positive_role_compatible_minimum_rate"])
        and float(gate_metrics["hard_negative_suppressed_or_abstained_rate"] or 0.0)
        >= float(gates["judged_hard_negative_suppression_minimum_rate"])
    )
    unsigned = {
        "schema_version": (
            RESULT_SUCCESSOR_SCHEMA_VERSION
            if policy_schema == POLICY_SUCCESSOR_SCHEMA_VERSION
            else RESULT_SCHEMA_VERSION
        ),
        "status": "zero_call_evidence_role_replay_complete",
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
            "label_rows_evaluated": len(all_label_rows),
            "candidate_label_rows_evaluated": len(candidate_label_rows),
        },
        "summary": {
            "judged_label_metrics": metrics,
            "candidate_pool_judged_label_metrics": candidate_metrics,
            "judged_financial_intent_metrics": intent_metrics,
            "judged_composite_metrics": composite_metrics,
            "candidate_pool_judged_composite_metrics": (
                candidate_composite_metrics
            ),
            "atom_count": len(atom_rows),
        },
        "atoms": atom_rows,
        "decision": {
            "evidence_role_quality_gate_passed": passed,
            "composite_financial_evidence_quality_gate_passed": (
                passed if policy_schema == POLICY_SUCCESSOR_SCHEMA_VERSION else False
            ),
            "runtime_authority": "shadow_only",
            "runtime_promotion_authorized": False,
            "fine_tuning_authorized": False,
            "s1_complete_claimed": False,
        },
        "authority": policy["authority"],
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay VS3 Evidence Role without model calls.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(_resolve(args.policy))
    _write_json(_resolve(args.output), result)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
