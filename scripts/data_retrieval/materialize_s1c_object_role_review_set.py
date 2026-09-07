from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.evidence_role_contract import (  # noqa: E402
    assert_object_view_is_label_free,
    build_evidence_object_view,
    build_object_annotation,
    build_query_relation,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


ADJUDICATION_SCHEMA_VERSION = "fin_ia_s1c_object_role_adjudication_v1_0"
REVIEW_SET_SCHEMA_VERSION = "fin_ia_s1c_object_role_review_set_v1_0"
HOLDOUT_CASES = frozenset({"ANET", "ASML", "ORCL"})
DEVELOPMENT_CASES = frozenset({"DELL", "MU", "NVDA"})


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


def _jsonl_by_id(path: Path, key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            identity = str(value.get(key) or "")
            if not identity or identity in rows:
                raise ValueError(f"object_role_source_identity_invalid:{key}")
            rows[identity] = value
    return rows


def _verify_bound_input(
    adjudication: Mapping[str, Any], *, name: str, path: Path
) -> None:
    binding = adjudication.get("bound_inputs", {}).get(name)
    if not isinstance(binding, Mapping):
        raise ValueError(f"object_role_adjudication_binding_missing:{name}")
    if (
        str(binding.get("ref") or "") != path.relative_to(ROOT).as_posix()
        or str(binding.get("sha256") or "") != _sha256(path)
    ):
        raise ValueError(f"object_role_adjudication_binding_drift:{name}")


def _primary_pack_surface_gaps(
    *, pack_result: Mapping[str, Any], pack_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gaps: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for case_key in sorted(DEVELOPMENT_CASES):
        artifact = pack_result.get("pack_artifacts", {}).get(case_key)
        if not isinstance(artifact, Mapping):
            raise ValueError(f"object_role_primary_pack_missing:{case_key}")
        path = pack_root / str(artifact.get("object_key") or "")
        digest = _sha256(path)
        if digest != str(artifact.get("digest") or ""):
            raise ValueError(f"object_role_primary_pack_drift:{case_key}")
        payload = _read_json(path)
        bindings.append(
            {
                "case_key": case_key,
                "object_key": str(artifact["object_key"]),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )
        for item in payload.get("evidence_items") or ():
            if item.get("claim_text") or isinstance(item.get("structured_metric"), Mapping):
                continue
            gaps.append(
                {
                    "case_key": case_key,
                    "target_id": str(item.get("target_id") or ""),
                    "source_record_id": str(item.get("source_record_id") or ""),
                    "object_type": str(item.get("object_type") or ""),
                    "gap_code": "claim_or_metric_surface_unbound_for_role_training",
                    "impact": (
                        "Reviewer business meaning remains usable as a qualification note, "
                        "but cannot be substituted for model-visible source text or used as "
                        "a claim-level training label."
                    ),
                    "evidence_pack_invalidated": False,
                }
            )
    return gaps, bindings


def materialize(
    *,
    adjudication_path: Path,
    qrels_path: Path,
    records_path: Path,
    documents_path: Path,
    pack_result_path: Path,
    pack_root: Path,
) -> dict[str, Any]:
    adjudication = _read_json(adjudication_path)
    if adjudication.get("schema_version") != ADJUDICATION_SCHEMA_VERSION:
        raise ValueError("object_role_adjudication_schema_invalid")
    if adjudication.get("status") != "codex_reviewed_development_labels_frozen":
        raise ValueError("object_role_adjudication_status_invalid")
    for name, path in (
        ("qrels", qrels_path),
        ("records", records_path),
        ("documents", documents_path),
        ("pack_result", pack_result_path),
    ):
        _verify_bound_input(adjudication, name=name, path=path)

    qrels_payload = _read_json(qrels_path)
    qrels = {str(row["qrel_id"]): row for row in qrels_payload["qrels"]}
    records = _jsonl_by_id(records_path, "evidence_id")
    parents = _jsonl_by_id(documents_path, "document_id")
    review_authority = str(adjudication.get("review_authority") or "").strip()
    if not review_authority:
        raise ValueError("object_role_review_authority_missing")

    object_views: list[dict[str, Any]] = []
    object_annotations: list[dict[str, Any]] = []
    view_by_key: dict[str, dict[str, Any]] = {}
    for spec in adjudication.get("objects") or ():
        object_key = str(spec.get("object_key") or "")
        source_record_id = str(spec.get("source_record_id") or "")
        if not object_key or object_key in view_by_key or source_record_id not in records:
            raise ValueError(f"object_role_object_spec_invalid:{object_key}")
        record = records[source_record_id]
        if str(record.get("ticker") or "") in HOLDOUT_CASES:
            raise ValueError(f"object_role_holdout_leakage:{source_record_id}")
        parent_id = str((record.get("metadata") or {}).get("parent_document_id") or "")
        if parent_id not in parents:
            raise ValueError(f"object_role_parent_missing:{source_record_id}")
        view = build_evidence_object_view(
            object_key=object_key,
            object_form=str(spec.get("object_form") or ""),
            locator=spec.get("locator") or {},
            record=record,
            parent=parents[parent_id],
        ).as_dict()
        assert_object_view_is_label_free(view)
        annotation = build_object_annotation(
            object_view=view,
            role_labels=spec.get("role_labels"),
            fact_state_labels=spec.get("fact_state_labels"),
            reason_codes=spec.get("reason_codes"),
            label_authority=str(spec.get("label_authority") or review_authority),
        )
        object_views.append(view)
        object_annotations.append(annotation)
        view_by_key[object_key] = view

    relations: list[dict[str, Any]] = []
    review_ids: set[str] = set()
    relation_keys: set[tuple[str, str]] = set()
    for spec in adjudication.get("relations") or ():
        review_id = str(spec.get("review_id") or "")
        qrel_id = str(spec.get("qrel_id") or "")
        object_key = str(spec.get("object_key") or "")
        if (
            not review_id
            or review_id in review_ids
            or qrel_id not in qrels
            or object_key not in view_by_key
        ):
            raise ValueError(f"object_role_relation_spec_invalid:{review_id}")
        qrel = qrels[qrel_id]
        if str(qrel.get("case_key") or "") not in DEVELOPMENT_CASES:
            raise ValueError(f"object_role_relation_holdout_leakage:{review_id}")
        view = view_by_key[object_key]
        if str(view["ticker"]) != str(qrel.get("evidence_owner_ticker") or ""):
            raise ValueError(f"object_role_relation_owner_mismatch:{review_id}")
        relation_key = (qrel_id, str(view["object_view_id"]))
        if relation_key in relation_keys:
            raise ValueError(f"object_role_relation_duplicate:{review_id}")
        relations.append(
            build_query_relation(
                review_id=review_id,
                qrel=qrel,
                object_view=view,
                relevance_judgement=str(spec.get("relevance_judgement") or ""),
                directness=str(spec.get("directness") or ""),
                background_state=str(spec.get("background_state") or ""),
                reason_codes=spec.get("reason_codes"),
                business_rationale_zh=str(spec.get("business_rationale_zh") or ""),
                label_authority=str(spec.get("label_authority") or review_authority),
            )
        )
        review_ids.add(review_id)
        relation_keys.add(relation_key)

    used_object_ids = {str(row["object_view_id"]) for row in relations}
    if used_object_ids != {str(row["object_view_id"]) for row in object_views}:
        raise ValueError("object_role_unreferenced_object_view")
    pack_result = _read_json(pack_result_path)
    typed_gaps, pack_bindings = _primary_pack_surface_gaps(
        pack_result=pack_result,
        pack_root=pack_root,
    )

    object_form_counts = Counter(row["object_form"] for row in object_views)
    role_counts = Counter(
        role for row in object_annotations for role in row["role_labels"]
    )
    fact_counts = Counter(
        state for row in object_annotations for state in row["fact_state_labels"]
    )
    judgement_counts = Counter(row["relevance_judgement"] for row in relations)
    case_counts = Counter(row["case_key"] for row in relations)
    unsigned = {
        "schema_version": REVIEW_SET_SCHEMA_VERSION,
        "status": "object_level_financial_role_review_complete_development_only",
        "recorded_at": "2026-08-12",
        "scope": "FIN_0_1_3_S1C_OBJECT_LEVEL_EVIDENCE_ROLE_CONTRACT",
        "bound_inputs": {
            "adjudication_ref": adjudication_path.relative_to(ROOT).as_posix(),
            "adjudication_sha256": _sha256(adjudication_path),
            "qrels_ref": qrels_path.relative_to(ROOT).as_posix(),
            "qrels_sha256": _sha256(qrels_path),
            "qrel_manifest_digest": str(qrels_payload["qrel_manifest_digest"]),
            "records_ref": records_path.relative_to(ROOT).as_posix(),
            "records_sha256": _sha256(records_path),
            "documents_ref": documents_path.relative_to(ROOT).as_posix(),
            "documents_sha256": _sha256(documents_path),
            "pack_result_ref": pack_result_path.relative_to(ROOT).as_posix(),
            "pack_result_sha256": _sha256(pack_result_path),
            "primary_pack_bindings": pack_bindings,
        },
        "separation_policy": {
            "model_visible_objects_contain_no_human_labels": True,
            "annotations_contain_no_source_surface_text": True,
            "labels_joined_only_after_candidate_generation_or_scoring": True,
            "ranking_relevance_is_not_evidence_promotion": True,
            "parent_context_cannot_be_positive_evidence": True,
            "reviewer_business_meaning_cannot_substitute_for_source_text": True,
            "holdout_cases_forbidden_from_design_tuning_and_training": sorted(HOLDOUT_CASES),
            "development_cases": sorted(DEVELOPMENT_CASES),
        },
        "summary": {
            "object_view_count": len(object_views),
            "object_form_counts": dict(sorted(object_form_counts.items())),
            "object_role_counts": dict(sorted(role_counts.items())),
            "fact_state_counts": dict(sorted(fact_counts.items())),
            "query_relation_count": len(relations),
            "judgement_counts": dict(sorted(judgement_counts.items())),
            "case_relation_counts": dict(sorted(case_counts.items())),
            "primary_pack_unbound_claim_or_metric_surface_count": len(typed_gaps),
        },
        "object_views": object_views,
        "object_annotations": object_annotations,
        "query_relations": relations,
        "typed_gaps": typed_gaps,
        "authority": {
            "candidate_is_not_evidence": True,
            "evidence_promoted": False,
            "owner_acceptance_claimed": False,
            "fine_tuning_authorized": False,
            "runtime_route_promotion_authorized": False,
            "s1d_authorized": False,
        },
        "known_boundary": (
            "This is a Codex-supervised development review of DELL, MU and NVDA. "
            "It establishes a source-bound object/label contract and diagnoses current "
            "role errors. ORCL, ASML and ANET remain untouched holdouts. The packet is "
            "not Evidence promotion, model training, runtime promotion or S1 completion."
        ),
    }
    return {**unsigned, "review_set_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize source-bound S1-C object-level Evidence Role reviews."
    )
    parser.add_argument(
        "--adjudication",
        default="configs/retrieval/fin_ia_0_1_3_s1c_object_role_adjudication_v1_0.json",
    )
    parser.add_argument(
        "--qrels",
        default="configs/retrieval/fin_ia_0_1_3_s1c_requalified_qrels_v1_1.json",
    )
    parser.add_argument(
        "--records",
        default="data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v1/records.jsonl",
    )
    parser.add_argument(
        "--documents",
        default="data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v1/documents.jsonl",
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
        "--output",
        default="configs/retrieval/fin_ia_0_1_3_s1c_object_role_review_set_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize(
        adjudication_path=_resolve(args.adjudication),
        qrels_path=_resolve(args.qrels),
        records_path=_resolve(args.records),
        documents_path=_resolve(args.documents),
        pack_result_path=_resolve(args.pack_result),
        pack_root=_resolve(args.pack_root),
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
                "summary": result["summary"],
                "review_set_digest": result["review_set_digest"],
                "output": output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
