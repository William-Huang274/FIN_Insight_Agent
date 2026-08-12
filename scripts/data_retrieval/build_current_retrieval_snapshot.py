from __future__ import annotations

import argparse
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

from retrieval import (  # noqa: E402
    compile_query_facet_plan,
    load_candidate_corpus,
    load_financial_research_kernel,
    retrieve_query_plan,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


SNAPSHOT_SCHEMA_VERSION = "fin_ia_current_retrieval_snapshot_v1_0"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _reviewed_targets(
    *,
    kernel: Any,
    pack_result: Mapping[str, Any],
    pack_object_root: Path,
    case_key: str,
) -> dict[str, set[str]]:
    artifact = dict(pack_result["pack_artifacts"][case_key])
    pack_path = (pack_object_root / str(artifact["object_key"])).resolve()
    pack_path.relative_to(pack_object_root.resolve())
    pack = _read_json(pack_path)
    reviewed_to_current: dict[str, set[str]] = {}
    for slot in kernel.slots:
        for reviewed_id in slot.reviewed_pack_slot_ids:
            reviewed_to_current.setdefault(reviewed_id, set()).add(slot.slot_id)
    targets: dict[str, set[str]] = {slot.slot_id: set() for slot in kernel.slots}
    for item in pack.get("evidence_items") or ():
        if not isinstance(item, Mapping):
            continue
        source_record_id = str(item.get("source_record_id") or "").strip()
        if not source_record_id:
            continue
        for binding in item.get("slot_bindings") or ():
            if not isinstance(binding, Mapping):
                continue
            reviewed_slot = str(binding.get("slot_id") or "")
            for current_slot in reviewed_to_current.get(reviewed_slot, ()):
                targets[current_slot].add(source_record_id)
    return targets


def build_snapshot(
    *,
    kernel_path: Path,
    records_path: Path,
    pack_result_path: Path,
    pack_object_root: Path,
    source_object_result_path: Path | None = None,
) -> dict[str, Any]:
    kernel_payload = _read_json(kernel_path)
    kernel = load_financial_research_kernel(kernel_payload)
    allowed_tickers = {
        ticker
        for profile in kernel.cases.values()
        for ticker in (
            profile.subject_ticker,
            *(entity.ticker for entity in profile.related_entities),
        )
    }
    corpus = load_candidate_corpus(
        records_path,
        allowed_tickers=allowed_tickers,
    )
    pack_result = _read_json(pack_result_path)
    source_object_result = (
        _read_json(source_object_result_path)
        if source_object_result_path is not None
        else None
    )
    cases: list[dict[str, Any]] = []
    for case_key in kernel.cases:
        plan = compile_query_facet_plan(kernel, case_key)
        targets = _reviewed_targets(
            kernel=kernel,
            pack_result=pack_result,
            pack_object_root=pack_object_root,
            case_key=case_key,
        )
        retrieval = retrieve_query_plan(
            kernel,
            plan,
            corpus,
            reviewed_targets_by_slot=targets,
        )
        missing = retrieval["summary"]["slots_missing_required_source_roles"]
        source_gap_summary = _source_gap_summary(
            retrieval,
            current_object_store=source_object_result is not None,
        )
        cases.append(
            {
                "case_key": case_key,
                "status": retrieval["status"],
                "query_plan": plan.as_dict(),
                "retrieval": retrieval,
                "source_gap_summary": source_gap_summary,
                "business_findings_zh": _business_findings(case_key, missing),
            }
        )

    dell = next(row for row in cases if row["case_key"] == "DELL")
    transfer_cases = [row for row in cases if row["case_key"] in {"MU", "NVDA"}]
    acceptance = {
        "dell_vertical_slice_hard_constraints_pass": (
            dell["status"] == "typed_local_candidate_retrieval_ready"
        ),
        "dell_required_candidate_facets_materialized": (
            dell["retrieval"]["summary"]["nonempty_lane_count"]
            >= dell["retrieval"]["summary"]["lane_count"] - 1
        ),
        "mu_nvda_same_core_transfer_pass": all(
            row["status"] == "typed_local_candidate_retrieval_ready"
            for row in transfer_cases
        ),
        "candidate_labels_joined_after_generation": all(
            lane["evaluation"]["labels_joined_after_candidate_generation"]
            for row in cases
            for lane in row["retrieval"]["lane_results"]
        ),
        "model_calls": 0,
        "network_calls": 0,
        "dense_calls": 0,
        "rerank_calls": 0,
        "complete_s1_claimed": False,
        "evidence_pack_promoted": False,
        "historical_corpus_sufficient_for_current_product": False,
    }
    status = (
        (
            "s1b_current_source_object_retrieval_snapshot_ready_with_typed_gaps"
            if source_object_result is not None
            else "s1a_typed_local_retrieval_vertical_slice_ready"
        )
        if all(
            acceptance[key]
            for key in (
                "dell_vertical_slice_hard_constraints_pass",
                "dell_required_candidate_facets_materialized",
                "mu_nvda_same_core_transfer_pass",
                "candidate_labels_joined_after_generation",
            )
        )
        else (
            "s1b_current_source_object_retrieval_snapshot_failed"
            if source_object_result is not None
            else "s1a_typed_local_retrieval_vertical_slice_failed"
        )
    )
    unsigned = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "status": status,
        "recorded_at": "2026-08-12",
        "scope": (
            "FIN_0_1_3_S1B_CURRENT_SOURCE_OBJECT_RETRIEVAL"
            if source_object_result is not None
            else "FIN_0_1_3_S1A_PROVIDER_NEUTRAL_LOCAL_RETRIEVAL_VERTICAL_SLICE"
        ),
        "kernel_contract_ref": kernel_path.relative_to(ROOT).as_posix(),
        "kernel_contract_digest": canonical_digest(kernel_payload),
        "source_snapshot": {
            "logical_id": records_path.parent.name,
            "records": corpus.records_scanned,
            "case_scope_records": len(corpus.records),
            "invalid_records_excluded": corpus.invalid_records_excluded,
            "records_sha256": _sha256(records_path),
            "source_boundary": (
                "current_parent_child_financial_object_store_with_legacy_lineage"
                if source_object_result is not None
                else "workstation_local_historical_sec_candidate_store"
            ),
        },
        "source_object_store": (
            {
                "result_ref": source_object_result_path.relative_to(ROOT).as_posix(),
                "result_digest": source_object_result.get("result_digest"),
                "status": source_object_result.get("status"),
                "object_store": source_object_result.get("object_store"),
                "case_readiness": source_object_result.get("case_readiness"),
                "typed_gaps": source_object_result.get("typed_gaps"),
            }
            if source_object_result is not None
            else None
        ),
        "reviewed_label_source_digest": str(pack_result.get("result_digest") or ""),
        "cases": cases,
        "acceptance": acceptance,
        "known_boundary": (
            "S1-B connects a bounded parent-child financial object store, current official "
            "captures, inherited semantic children and point-in-time market roles to the same "
            "provider-neutral candidate runtime. Candidates are not Evidence; Dell and Micron "
            "call-material transport, TSM advanced-packaging evidence, fresh 2026-08-06 market "
            "data and valuation fields remain typed gaps; "
            "dense retrieval, reranking, Evidence Pack promotion and model research remain open."
            if source_object_result is not None
            else "S1-A proves a provider-neutral typed query plan, pre-score identity/date/source "
            "constraints, local lexical candidate generation and a Workbench-consumable "
            "diagnostic snapshot. The historical local SEC corpus is not a complete current "
            "research source universe; candidates are not Evidence; external supplementation, "
            "chunk rebuild, dense retrieval, reranking and dynamic model research remain open."
        ),
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def _business_findings(
    case_key: str,
    missing_roles_by_slot: Mapping[str, Any],
) -> list[str]:
    findings = [
        f"{case_key} 的候选先按披露主体、关系角色和截至日收窄，再进入词法排名。",
        "关联公司材料只作为关系背景候选，不自动证明对研究主体的采购、供应或分配。",
    ]
    if "capital_allocation_and_valuation" in missing_roles_by_slot:
        findings.append("当前本地 SEC 语料没有截至日行情角色，因此估值仍是明确缺口。")
    if missing_roles_by_slot:
        findings.append(
            "仍缺来源角色："
            + "；".join(
                f"{slot}={','.join(roles)}"
                for slot, roles in sorted(missing_roles_by_slot.items())
            )
        )
    return findings


def _source_gap_summary(
    retrieval: Mapping[str, Any],
    *,
    current_object_store: bool,
) -> dict[str, Any]:
    missing_from_corpus = 0
    eligible_before_scoring = 0
    matched_after_scoring = 0
    for lane in retrieval.get("lane_results") or ():
        evaluation = lane.get("evaluation") or {}
        missing_from_corpus += len(evaluation.get("missing_from_source_corpus") or ())
        eligible_before_scoring += int(
            evaluation.get("reviewed_targets_eligible_before_scoring") or 0
        )
        matched_after_scoring += int(
            evaluation.get("reviewed_targets_in_candidate_pool") or 0
        )
    return {
        "reviewed_label_occurrences_missing_from_current_corpus": missing_from_corpus,
        "reviewed_label_occurrences_eligible_before_scoring": eligible_before_scoring,
        "reviewed_label_occurrences_matched_after_scoring": matched_after_scoring,
        "interpretation_zh": (
            "旧 reviewed chunk 已通过 lineage crosswalk 重定基到当前对象；仍缺失才属于对象覆盖问题，"
            "eligible 但未入池的项属于查询、对象形状或排序问题。"
            if current_object_store
            else "缺失项属于当前本地候选语料覆盖问题；eligible 但未入池的项属于查询、对象形状或排序问题。"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the current typed local retrieval snapshot."
    )
    parser.add_argument(
        "--kernel",
        default="configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json",
    )
    parser.add_argument(
        "--source-object-result",
        default=None,
        help="Optional S1-B object-store result bound into the snapshot.",
    )
    parser.add_argument(
        "--records",
        default=(
            "data/indexes/bm25/"
            "sector_depth_full238_us_v0_3_mixed_with_8k_fy2023_2027/records.jsonl"
        ),
    )
    parser.add_argument(
        "--pack-result",
        default="configs/runtime/fin_ia_current_research_evidence_pack_result_v1_0.json",
    )
    parser.add_argument(
        "--pack-object-root",
        default=(
            "data/workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/"
            "zero-call-r1/objects"
        ),
    )
    parser.add_argument(
        "--output",
        default="configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = _resolve(args.output)
    snapshot = build_snapshot(
        kernel_path=_resolve(args.kernel),
        records_path=_resolve(args.records),
        pack_result_path=_resolve(args.pack_result),
        pack_object_root=_resolve(args.pack_object_root),
        source_object_result_path=(
            _resolve(args.source_object_result)
            if args.source_object_result
            else None
        ),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "result_digest": snapshot["result_digest"],
                "output": output.relative_to(ROOT).as_posix(),
                "cases": [
                    {
                        "case_key": row["case_key"],
                        **row["retrieval"]["summary"],
                    }
                    for row in snapshot["cases"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if "_ready" in str(snapshot["status"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
