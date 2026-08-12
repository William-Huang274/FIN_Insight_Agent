from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.ranking_comparison import build_document_text  # noqa: E402


SCHEMA_VERSION = "fin_ia_s1c_financial_role_eval_set_v1_1"


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


def _records(path: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row.get("evidence_id") or "")
            if not key or key in output:
                raise ValueError("financial_role_eval_record_identity_invalid")
            output[key] = row
    return output


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _document_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "document_id": str(record["evidence_id"]),
        "ticker": str(record.get("ticker") or ""),
        "source_type": str(record.get("source_type") or ""),
        "publication_date": str(record.get("publication_date") or ""),
        "fiscal_year": record.get("fiscal_year"),
        "period_end": str(record.get("period_end") or ""),
        "section": str(record.get("section") or ""),
        "subsection": str(record.get("subsection") or ""),
        "document_text": build_document_text(record),
    }


def _heldout_document_text(item: Mapping[str, Any]) -> str:
    claim_text = str(item.get("claim_text") or "").strip()
    if claim_text:
        return claim_text
    metric = item.get("structured_metric")
    if not isinstance(metric, Mapping):
        raise ValueError("financial_role_eval_holdout_document_text_missing")
    table_path = metric.get("table_path")
    if not isinstance(table_path, Mapping):
        raise ValueError("financial_role_eval_holdout_metric_path_missing")
    meanings = [
        str(binding.get("business_meaning_zh") or "")
        for binding in item.get("slot_bindings") or ()
        if isinstance(binding, Mapping)
    ]
    return " | ".join(
        value
        for value in (
            str(table_path.get("table_header") or ""),
            str(metric.get("metric_name") or ""),
            str(table_path.get("column_label") or ""),
            str(metric.get("raw_value") or ""),
            str(metric.get("unit") or ""),
            *meanings,
        )
        if value
    )


def _primary_rows(
    qrels: Mapping[str, Any],
    ranking: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ranked = {
        str(row["qrel_id"]): row
        for row in ranking["comparison"]["queries"]
    }
    output: list[dict[str, Any]] = []
    for qrel in qrels["qrels"]:
        qrel_id = str(qrel["qrel_id"])
        query_text = " ".join(
            _ordered_unique(
                [
                    *qrel.get("sparse_query_texts", ()),
                    *qrel.get("semantic_query_texts", ()),
                ]
            )
        )
        targets = [
            str(value)
            for value in qrel.get("target_current_source_record_ids") or ()
        ]
        if not query_text or not targets:
            raise ValueError(f"financial_role_eval_primary_label_invalid:{qrel_id}")
        positives = [
            {
                **_document_projection(records[target]),
                "label": "owner_accepted_ranking_relevant",
                "relevance_grade": int(qrel["relevance_grade"]),
            }
            for target in targets
        ]
        hard_negative_by_id: dict[str, dict[str, Any]] = {}
        for route in ranked[qrel_id]["routes"].values():
            for candidate in route["candidates"]:
                candidate_id = str(candidate["source_record_id"])
                diagnostic = str(candidate.get("business_diagnostic_code") or "")
                if (
                    candidate_id in targets
                    or not diagnostic
                    or diagnostic == "no_automatic_business_error_detected"
                ):
                    continue
                hard_negative_by_id[candidate_id] = {
                    **_document_projection(records[candidate_id]),
                    "label": "existing_business_diagnostic_hard_negative",
                    "reason_code": diagnostic,
                }
        output.append(
            {
                "query_id": qrel_id,
                "split": "primary_three_case",
                "case_key": str(qrel["case_key"]),
                "slot_id": str(qrel["evidence_slot_id"]),
                "facet_id": None,
                "query_text": query_text,
                "publication_date_lte": str(qrel["publication_date_lte"]),
                "positives": positives,
                "hard_negatives": sorted(
                    hard_negative_by_id.values(), key=lambda row: row["document_id"]
                ),
            }
        )
    return output


def _heldout_rows(
    *,
    kernel_payload: Mapping[str, Any],
    pack_result: Mapping[str, Any],
    pack_root: Path,
    adjudication: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kernel = load_financial_research_kernel(kernel_payload)
    slot_question = {
        slot.slot_id: slot.business_question_zh for slot in kernel.slots
    }
    output: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for case_key in ("ORCL", "ASML", "ANET"):
        artifact = pack_result["pack_artifacts"][case_key]
        path = pack_root / Path(str(artifact["object_key"]))
        if _sha256(path) != str(artifact["digest"]):
            raise ValueError(f"financial_role_eval_holdout_pack_drift:{case_key}")
        pack = _read_json(path)
        positives_by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
        document_by_id: dict[str, dict[str, Any]] = {}
        for item in pack.get("evidence_items") or ():
            document = {
                "document_id": str(item["target_id"]),
                "ticker": case_key,
                "source_type": "reviewed_official_source_claim",
                "publication_date": str(item.get("publication_date") or ""),
                "fiscal_year": None,
                "period_end": str(item.get("source_reporting_period_end") or ""),
                "section": "reviewed_claim",
                "subsection": str(item.get("claim_type") or ""),
                "document_text": _heldout_document_text(item),
                "label": "reviewed_holdout_positive",
                "evidence_role": str(item.get("evidence_role") or ""),
            }
            bound_slots = {
                str(binding["slot_id"])
                for binding in item.get("slot_bindings") or ()
            }
            document_by_id[document["document_id"]] = {
                **document,
                "bound_slots": sorted(bound_slots),
            }
            for slot_id in bound_slots:
                positives_by_slot[slot_id].append(document)
        rejected_pool = []
        for item in pack.get("rejected_items") or ():
            rejected = {
                "document_id": str(item["target_id"]),
                "ticker": case_key,
                "source_type": "reviewed_rejected_claim",
                "publication_date": "",
                "fiscal_year": None,
                "period_end": "",
                "section": "reviewed_rejected_claim",
                "subsection": str(item.get("reason_code") or ""),
                "document_text": str(item["observed_surface"]),
                "label": "reviewed_holdout_rejection",
                "reason_code": str(item.get("reason_code") or ""),
            }
            rejected_pool.append(rejected)
            document_by_id[rejected["document_id"]] = rejected
        for slot_id, positives in sorted(positives_by_slot.items()):
            if slot_id not in slot_question:
                raise ValueError(f"financial_role_eval_holdout_slot_unknown:{slot_id}")
            query_text = f"研究主体 {case_key}：{slot_question[slot_id]}"
            query_id = f"holdout__{case_key.lower()}__{slot_id}"
            decisions = adjudication["queries"].get(query_id)
            if not isinstance(decisions, list) or len(decisions) < 2:
                raise ValueError(
                    f"financial_role_eval_holdout_adjudication_missing:{query_id}"
                )
            positive_ids = {str(item["document_id"]) for item in positives}
            hard_negatives: list[dict[str, Any]] = []
            for decision in decisions:
                if not isinstance(decision, Mapping) or set(decision) != {
                    "document_id",
                    "reason_code",
                }:
                    raise ValueError(
                        f"financial_role_eval_holdout_adjudication_invalid:{query_id}"
                    )
                document_id = str(decision["document_id"])
                if document_id in positive_ids or document_id not in document_by_id:
                    raise ValueError(
                        f"financial_role_eval_holdout_negative_invalid:{query_id}:{document_id}"
                    )
                negative = dict(document_by_id[document_id])
                negative.pop("bound_slots", None)
                negative.update(
                    {
                        "label": "codex_supervised_role_contrast_hard_negative",
                        "reason_code": str(decision["reason_code"]),
                    }
                )
                hard_negatives.append(negative)
            output.append(
                {
                    "query_id": query_id,
                    "split": "holdout_unseen_case",
                    "case_key": case_key,
                    "slot_id": slot_id,
                    "facet_id": None,
                    "query_text": query_text,
                    "publication_date_lte": "2026-08-06",
                    "positives": sorted(positives, key=lambda row: row["document_id"]),
                    "hard_negatives": hard_negatives,
                    "unjudged_same_case_document_count": (
                        len(document_by_id)
                        - len(positive_ids)
                        - len({item["document_id"] for item in hard_negatives})
                    ),
                }
            )
        bindings.append(
            {
                "case_key": case_key,
                "pack_object_key": str(artifact["object_key"]),
                "pack_sha256": _sha256(path),
                "pack_bytes": path.stat().st_size,
            }
        )
    return output, bindings


def materialize(
    *,
    kernel_path: Path,
    qrel_path: Path,
    ranking_path: Path,
    records_path: Path,
    pack_result_path: Path,
    pack_root: Path,
    adjudication_path: Path,
) -> dict[str, Any]:
    kernel = _read_json(kernel_path)
    qrels = _read_json(qrel_path)
    ranking = _read_json(ranking_path)
    pack_result = _read_json(pack_result_path)
    adjudication = _read_json(adjudication_path)
    if (
        adjudication.get("schema_version")
        != "fin_ia_s1c_holdout_role_adjudication_v1_0"
        or adjudication.get("bound_inputs", {}).get("pack_result_sha256")
        != _sha256(pack_result_path)
        or adjudication.get("bound_inputs", {}).get("pack_result_digest")
        != pack_result.get("result_digest")
    ):
        raise ValueError("financial_role_eval_holdout_adjudication_drift")
    if qrels.get("summary", {}).get("mapped_current_target_count") != 18:
        raise ValueError("financial_role_eval_qrels_not_fully_mapped")
    if ranking.get("bound_inputs", {}).get("qrel_manifest_digest") != qrels.get(
        "qrel_manifest_digest"
    ):
        raise ValueError("financial_role_eval_ranking_qrel_drift")
    records = _records(records_path)
    primary = _primary_rows(qrels, ranking, records)
    heldout, heldout_bindings = _heldout_rows(
        kernel_payload=kernel,
        pack_result=pack_result,
        pack_root=pack_root,
        adjudication=adjudication,
    )
    expected_holdout_ids = {
        str(row["query_id"]) for row in heldout
    }
    if set(adjudication["queries"]) != expected_holdout_ids:
        raise ValueError("financial_role_eval_holdout_adjudication_scope_invalid")
    queries = [*primary, *heldout]
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "status": "frozen_financial_role_eval_ready",
        "recorded_at": "2026-08-12",
        "scope": "FIN_0_1_3_S1C_CROSS_ENCODER_AND_EVIDENCE_ROLE_SHADOW",
        "bound_inputs": {
            "kernel_ref": kernel_path.relative_to(ROOT).as_posix(),
            "kernel_sha256": _sha256(kernel_path),
            "qrels_ref": qrel_path.relative_to(ROOT).as_posix(),
            "qrels_sha256": _sha256(qrel_path),
            "qrel_manifest_digest": str(qrels["qrel_manifest_digest"]),
            "ranking_ref": ranking_path.relative_to(ROOT).as_posix(),
            "ranking_sha256": _sha256(ranking_path),
            "ranking_result_digest": str(ranking["result_digest"]),
            "records_ref": records_path.relative_to(ROOT).as_posix(),
            "records_sha256": _sha256(records_path),
            "pack_result_ref": pack_result_path.relative_to(ROOT).as_posix(),
            "pack_result_sha256": _sha256(pack_result_path),
            "holdout_adjudication_ref": adjudication_path.relative_to(ROOT).as_posix(),
            "holdout_adjudication_sha256": _sha256(adjudication_path),
            "heldout_pack_bindings": heldout_bindings,
        },
        "label_policy": {
            "primary_positive_authority": "owner_accepted_ranking_relevance_only",
            "primary_negative_authority": "existing_business_diagnostic_only",
            "heldout_positive_authority": "previous_reviewed_evidence_pack",
            "heldout_negative_authority": (
                "codex_supervised_explicit_business_role_contrast_pending_owner"
            ),
            "cross_slot_absence_is_not_negative": True,
            "labels_joined_after_candidate_generation": True,
            "candidate_is_not_evidence": True,
            "holdout_cases_forbidden_from_tuning": ["ANET", "ASML", "ORCL"],
        },
        "summary": {
            "primary_query_count": len(primary),
            "primary_positive_count": sum(len(row["positives"]) for row in primary),
            "primary_hard_negative_count": sum(
                len(row["hard_negatives"]) for row in primary
            ),
            "holdout_query_count": len(heldout),
            "holdout_positive_count": sum(len(row["positives"]) for row in heldout),
            "holdout_hard_negative_count": sum(
                len(row["hard_negatives"]) for row in heldout
            ),
        },
        "queries": queries,
        "known_boundary": (
            "This frozen set evaluates ranking relevance and evidence-role discrimination. "
            "Primary positives are ranking labels, not Evidence promotion. Holdout claims "
            "come from prior reviewed packs and are forbidden from tuning. The set does "
            "not prove source coverage, numeric authority, Agentic Research or release."
        ),
    }
    return {**unsigned, "eval_set_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze S1-C business hard negatives and unseen-case role labels."
    )
    parser.add_argument(
        "--kernel",
        default="configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json",
    )
    parser.add_argument(
        "--qrels",
        default="configs/retrieval/fin_ia_0_1_3_s1c_requalified_qrels_v1_1.json",
    )
    parser.add_argument(
        "--ranking",
        default="configs/retrieval/fin_ia_0_1_3_s1c_ranking_comparison_result_v1_1.json",
    )
    parser.add_argument(
        "--records",
        default="data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v1/records.jsonl",
    )
    parser.add_argument(
        "--pack-result",
        default="configs/runtime/fin_ia_current_research_evidence_pack_result_v1_0.json",
    )
    parser.add_argument(
        "--pack-root",
        default="data/workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects",
    )
    parser.add_argument(
        "--holdout-adjudication",
        default="configs/retrieval/fin_ia_0_1_3_s1c_holdout_role_adjudication_v1_0.json",
    )
    parser.add_argument(
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_financial_role_eval_set_v1_1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize(
        kernel_path=_resolve(args.kernel),
        qrel_path=_resolve(args.qrels),
        ranking_path=_resolve(args.ranking),
        records_path=_resolve(args.records),
        pack_result_path=_resolve(args.pack_result),
        pack_root=_resolve(args.pack_root),
        adjudication_path=_resolve(args.holdout_adjudication),
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
                **result["summary"],
                "eval_set_digest": result["eval_set_digest"],
                "output": output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
