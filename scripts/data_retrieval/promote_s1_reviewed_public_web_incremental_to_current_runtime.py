from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
SCRIPT_ROOT = ROOT / "scripts" / "data_retrieval"
for import_root in (SRC_ROOT, SCRIPT_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from build_current_retrieval_snapshot import build_snapshot  # noqa: E402
from promote_s1_reviewed_public_pdf_to_current_runtime import (  # noqa: E402
    REGISTRY_REF,
    _read_json,
    _read_jsonl,
    _refresh_registry_aggregate,
    _sha256_file,
    _validated_digest,
    _with_resource,
    _write_json,
)
from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
    canonical_digest,
    load_current_s1_runtime_binding_policy,
    validate_current_s1_runtime_binding_receipt,
)
from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    load_dynamic_single_unit_policy,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


RECORDED_AT = "2026-08-25"
PREDECESSOR_REGISTRY_ID = (
    "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R37"
)
REGISTRY_ID = "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R38"
SOURCE_RECORDS_REF = (
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v5/records.jsonl"
)
SOURCE_PREDECESSOR_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1b_current_financial_object_store_result_v1_3.json"
)
SOURCE_RESULT_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1b_current_financial_object_store_result_v1_4.json"
)
PUBLIC_WEB_RESULT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_reviewed_public_web_incremental_successor_result_v1_0.json"
)
EMBEDDING_RESULT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_qwen_embedding_cache_successor_result_v1_2.json"
)
OBJECTS_REF = (
    "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/"
    "v8/objects.jsonl"
)
EMBEDDING_MANIFEST_REF = (
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v8/qwen3_embedding_0_6b_v1/manifest.json"
)
EMBEDDING_DENSE_REF = (
    "data/workbench_private/fin_0_1_3_s1c_hybrid_candidate_runtime/"
    "model_cache_v8/qwen3_embedding_0_6b_v1/dense.float16.npy"
)
SNAPSHOT_REF = (
    "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_4.json"
)
HYBRID_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_7.json"
)
HYBRID_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_8.json"
)
BINDING_PREDECESSOR_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_12.json"
)
BINDING_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_13.json"
)
RECEIPT_REF = (
    "configs/runtime/fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_14.json"
)
DYNAMIC_PREDECESSOR_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_6.json"
)
DYNAMIC_REF = (
    "configs/research/"
    "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_7.json"
)
KERNEL_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_5.json"
)
PACK_RESULT_REF = (
    "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_6.json"
)
PACK_OBJECT_ROOT = (
    "data/workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/"
    "zero-call-r1/objects"
)
MISSING_PAGE_ID = "PUBLIC::DELL-EXT::2184F13EB685F627C757"


def _path(ref: str) -> Path:
    return ROOT / ref


def _count_by(
    rows: Iterable[Mapping[str, Any]], key: str
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _build_source_result(
    predecessor: Mapping[str, Any],
    public_web_result: Mapping[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    _validated_digest(
        predecessor, "public_web_source_result_predecessor_digest_drift"
    )
    public_web_result_digest = _validated_digest(
        public_web_result, "public_web_incremental_result_digest_drift"
    )
    summary = dict(public_web_result.get("summary") or {})
    if (
        len(records) != 1888
        or summary.get("base_source_record_count") != 1886
        or summary.get("appended_canonical_source_record_count") != 2
        or summary.get("successor_source_record_count") != 1888
        or summary.get("appended_page_ids") != [MISSING_PAGE_ID]
    ):
        raise ValueError("public_web_source_successor_population_drift")
    appended_rows = records[-2:]
    if (
        {str(row.get("source_type") or "") for row in appended_rows}
        != {"PUBLIC_WEB"}
        or MISSING_PAGE_ID
        not in {str(row.get("evidence_id") or "") for row in appended_rows}
    ):
        raise ValueError("public_web_source_successor_tail_invalid")

    source_results = deepcopy(list(predecessor.get("source_results") or []))
    source_results.append(
        {
            "source_id": "reviewed_public_web_incremental_capture_bound_source_v1",
            "input_kind": "reviewed_public_web_page_and_exact_slice_records",
            "status": "source_compiled",
            "source_ref": SOURCE_RECORDS_REF,
            "source_sha256": _sha256_file(SOURCE_RECORDS_REF),
            "authority_result_ref": PUBLIC_WEB_RESULT_REF,
            "authority_result_digest": public_web_result_digest,
            "document_parents_added": 1,
            "retrieval_children_added": 2,
            "invalid_records_excluded": 0,
        }
    )

    parent_ids = {
        str((row.get("metadata") or {}).get("parent_document_id") or "")
        for row in records
        if str((row.get("metadata") or {}).get("parent_document_id") or "")
    }
    previous_store = dict(predecessor.get("object_store") or {})
    object_store = {
        **previous_store,
        "document_parents": len(parent_ids),
        "retrieval_children": len(records),
        "children_from_immutable_current_capture": int(
            previous_store.get("children_from_immutable_current_capture") or 0
        )
        + len(appended_rows),
        "children_by_ticker": _count_by(records, "ticker"),
        "children_by_source_type": _count_by(records, "source_type"),
        "max_retrieval_child_characters": max(
            len(str(row.get("text") or "")) for row in records
        ),
        "reviewed_public_page_records": int(
            previous_store.get("reviewed_public_page_records") or 0
        )
        + 1,
        "reviewed_public_exact_slice_records": int(
            previous_store.get("reviewed_public_exact_slice_records") or 0
        )
        + 1,
        "reviewed_public_web_incremental_page_records": 1,
        "reviewed_public_web_incremental_exact_slice_records": 1,
    }

    case_readiness: dict[str, dict[str, Any]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        case_rows = [row for row in records if row.get("ticker") == ticker]
        issuer_rows = [
            row
            for row in case_rows
            if row.get("source_type") != "MARKET_SNAPSHOT"
        ]
        market_rows = [
            row
            for row in case_rows
            if row.get("source_type") == "MARKET_SNAPSHOT"
        ]
        publication_dates = sorted(
            {
                str(row.get("publication_date") or "")
                for row in issuer_rows
                if str(row.get("publication_date") or "")
            }
        )
        case_readiness[ticker] = {
            "issuer_retrieval_children": len(issuer_rows),
            "latest_issuer_publication_date": (
                publication_dates[-1] if publication_dates else ""
            ),
            "point_in_time_market_children": len(market_rows),
            "market_as_of_dates": sorted(
                {
                    str(row.get("period_end") or "")
                    for row in market_rows
                    if str(row.get("period_end") or "")
                }
            ),
        }

    predecessor_body = deepcopy(dict(predecessor))
    predecessor_body.pop("result_digest", None)
    acceptance = deepcopy(dict(predecessor.get("acceptance") or {}))
    acceptance.update(
        {
            "current_pack_reviewed_public_web_page_and_slice_lineage_complete": True,
            "reviewed_public_web_candidates_remain_non_authoritative": True,
            "public_relationship_does_not_prove_private_allocation": True,
        }
    )
    body = {
        **predecessor_body,
        "recorded_at": RECORDED_AT,
        "source_results": source_results,
        "object_store": object_store,
        "case_readiness": case_readiness,
        "acceptance": acceptance,
        "successor_authority": {
            "result_ref": PUBLIC_WEB_RESULT_REF,
            "result_digest": public_web_result_digest,
            "source_records_ref": SOURCE_RECORDS_REF,
            "source_records_sha256": _sha256_file(SOURCE_RECORDS_REF),
        },
        "known_boundary": (
            "This R38 successor retains every R37 source record and appends "
            "only the one current-Pack reviewed NVIDIA public-web page plus its "
            "exact slice. It restores source/object synchronization without "
            "changing Evidence, NumericFact, causal, S1 qualification, private "
            "allocation, publication or release authority."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _build_hybrid_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    public_web_result = _read_json(PUBLIC_WEB_RESULT_REF)
    embedding_result = _read_json(EMBEDDING_RESULT_REF)
    value["object_store"] = {
        "objects_ref": OBJECTS_REF,
        "objects_sha256": public_web_result["outputs"]["objects_sha256"],
    }
    value["qwen_embedding"]["dense_cache_ref"] = EMBEDDING_DENSE_REF
    value["qwen_embedding"]["cache_manifest_ref"] = EMBEDDING_MANIFEST_REF
    if (
        set(value) != set(predecessor)
        or embedding_result["runtime"]["device"] != "cuda:0"
        or embedding_result["runtime"]["parameter_dtype"] != "torch.float16"
        or embedding_result["runtime"]["cpu_fallback_count"] != 0
        or embedding_result["runtime"]["new_object_count_embedded"] != 9
    ):
        raise ValueError("public_web_hybrid_successor_contract_invalid")
    return value


def _build_binding_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["policy_id"] = (
        "FIN-0.1.3-S1-CURRENT-PRODUCT-RUNTIME-BINDING-V1.13"
    )
    assets = value["assets"]
    assets["retrieval_snapshot"]["ref"] = SNAPSHOT_REF
    assets["object_compiler_result"]["ref"] = PUBLIC_WEB_RESULT_REF
    assets["hybrid_runtime_policy"]["ref"] = HYBRID_REF
    value["successor_change"] = {
        "runtime_registry_id": REGISTRY_ID,
        "failed_full_repository_gate_ref": (
            "configs/audits/"
            "fin_ia_0_1_3_r37_full_repository_gate_R1_failure_assessment_v1_0.json"
        ),
        "reviewed_public_web_source_object_sync_completed": True,
        "historical_R37_immutable": True,
        "S1_qualification_claimed": False,
    }
    return load_current_s1_runtime_binding_policy(value)


def _build_dynamic_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["objective"]["objective_id"] = (
        "OBJ::DELL::DYNAMIC-VALUE-CAPTURE-R38-REVIEWED-PUBLIC-WEB-SYNC"
    )
    value["authority"][
        "reviewed_public_web_requires_current_source_object_index_sync"
    ] = True
    request_basis = value["token_budget_bases"]["request_planning"]
    request_basis["comparable_run_evidence"] = (
        "The immutable R37 full-repository R1 gate found the current DELL R4 "
        "Pack's reviewed NVIDIA public-web source absent from the source/object "
        "corpus. R38 appends only that page, its exact slice and nine candidate "
        "objects; Evidence and NumericFact authority remain unchanged."
    )
    request_basis["node_purpose"] = (
        "Select proposition-bound S1/S2 requests from the current R38 source-"
        "synchronized tool catalog without seeing answers."
    )
    return load_dynamic_single_unit_policy(value)


def _require_new_outputs() -> None:
    for ref in (
        SOURCE_RESULT_REF,
        SNAPSHOT_REF,
        HYBRID_REF,
        BINDING_REF,
        RECEIPT_REF,
        DYNAMIC_REF,
    ):
        if _path(ref).exists():
            raise FileExistsError(f"public_web_runtime_successor_exists:{ref}")


def main() -> int:
    _require_new_outputs()
    registry = deepcopy(_read_json(REGISTRY_REF))
    if registry.get("registry_id") != PREDECESSOR_REGISTRY_ID:
        raise ValueError("public_web_runtime_R37_predecessor_required")

    records = _read_jsonl(SOURCE_RECORDS_REF)
    source_result = _build_source_result(
        _read_json(SOURCE_PREDECESSOR_REF),
        _read_json(PUBLIC_WEB_RESULT_REF),
        records,
    )
    _write_json(SOURCE_RESULT_REF, source_result)
    snapshot = build_snapshot(
        kernel_path=_path(KERNEL_REF),
        records_path=_path(SOURCE_RECORDS_REF),
        pack_result_path=_path(PACK_RESULT_REF),
        pack_object_root=_path(PACK_OBJECT_ROOT),
        pack_private_root_base=ROOT / "data" / "workbench_private",
        source_object_result_path=_path(SOURCE_RESULT_REF),
    )
    dell = next(
        row for row in snapshot["cases"] if row.get("case_key") == "DELL"
    )
    if (
        dell["source_gap_summary"][
            "reviewed_label_occurrences_missing_from_current_corpus"
        ]
        != 0
    ):
        raise ValueError("public_web_runtime_source_gap_not_closed")
    _write_json(SNAPSHOT_REF, snapshot)

    hybrid = _build_hybrid_policy(_read_json(HYBRID_PREDECESSOR_REF))
    binding = _build_binding_policy(_read_json(BINDING_PREDECESSOR_REF))
    dynamic = _build_dynamic_policy(_read_json(DYNAMIC_PREDECESSOR_REF))
    _write_json(HYBRID_REF, hybrid)
    _write_json(BINDING_REF, binding)
    _write_json(DYNAMIC_REF, dynamic)

    registry["registry_id"] = REGISTRY_ID
    for resource_id, ref, payload in (
        (
            "application.config.current_hybrid_candidate_runtime_policy",
            HYBRID_REF,
            hybrid,
        ),
        (
            "application.config.current_s1_runtime_binding_policy",
            BINDING_REF,
            binding,
        ),
        (
            "application.result.current_research_retrieval_snapshot",
            SNAPSHOT_REF,
            snapshot,
        ),
    ):
        _with_resource(
            registry,
            resource_id=resource_id,
            ref=ref,
            payload=payload,
        )
    _refresh_registry_aggregate(registry)

    receipt = build_current_s1_runtime_binding_receipt(
        ROOT,
        binding,
        payload_overrides={"runtime_registry": registry},
    )
    _write_json(RECEIPT_REF, receipt)
    _with_resource(
        registry,
        resource_id="application.result.current_s1_runtime_binding_receipt",
        ref=RECEIPT_REF,
        payload=receipt,
    )
    _refresh_registry_aggregate(registry)
    _write_json(REGISTRY_REF, registry)

    load_runtime_resource_registry(ROOT)
    validate_current_s1_runtime_binding_receipt(
        receipt,
        binding,
        repository_root=ROOT,
    )
    print(
        json.dumps(
            {
                "status": "current_reviewed_public_web_sync_promoted",
                "registry_id": REGISTRY_ID,
                "source_record_count": receipt[
                    "source_object_index_lineage"
                ]["source_record_count"],
                "compiled_object_count": receipt[
                    "source_object_index_lineage"
                ]["compiled_object_count"],
                "embedding_object_count": receipt["embedding_index"][
                    "object_count"
                ],
                "dell_missing_reviewed_label_occurrences": 0,
                "snapshot_digest": snapshot["result_digest"],
                "binding_digest": receipt["result_digest"],
                "dynamic_policy_ref": DYNAMIC_REF,
                "model_calls": 0,
                "network_calls": 0,
                "paid_tool_calls": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
