from __future__ import annotations

from copy import deepcopy
import hashlib
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
from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
    canonical_digest,
    validate_current_s1_runtime_binding_receipt,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    load_runtime_resource_registry,
)


RECORDED_AT = "2026-08-23"
SOURCE_RECORDS_REF = (
    "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
    "v3/records.jsonl"
)
SOURCE_RESULT_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_s1b_current_financial_object_store_result_v1_2.json"
)
SNAPSHOT_REF = (
    "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_2.json"
)
POLICY_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_7.json"
)
RECEIPT_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_8.json"
)
REGISTRY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
)
PUBLIC_RESULT_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_dynamic_public_reachability_successor_result_v1_0.json"
)
KERNEL_REF = (
    "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_4.json"
)
HYBRID_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_5.json"
)
ROUTE_REF = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_4.json"
)
PACK_RESULT_REF = (
    "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_5.json"
)
PACK_OBJECT_ROOT = (
    "data/workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/"
    "zero-call-r1/objects"
)


def _path(ref: str) -> Path:
    return ROOT / ref


def _read_json(ref: str) -> dict[str, Any]:
    value = json.loads(_path(ref).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{ref}")
    return value


def _read_jsonl(ref: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with _path(ref).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{ref}:{line_number}")
            rows.append(value)
    return rows


def _render_json(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(ref: str, value: Mapping[str, Any]) -> None:
    path = _path(ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_render_json(value))
    temporary.replace(path)


def _sha256_file(ref: str) -> str:
    digest = hashlib.sha256()
    with _path(ref).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _count_by(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _build_source_result(
    predecessor: Mapping[str, Any],
    public_result: Mapping[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    predecessor_body = deepcopy(dict(predecessor))
    predecessor_digest = str(predecessor_body.pop("result_digest", ""))
    if predecessor_digest != canonical_digest(predecessor_body):
        raise ValueError("current_source_result_predecessor_digest_drift")
    public_body = deepcopy(dict(public_result))
    public_digest = str(public_body.pop("result_digest", ""))
    if public_digest != canonical_digest(public_body):
        raise ValueError("public_reachability_result_digest_drift")

    public_rows = [row for row in records if row.get("source_type") == "PUBLIC_WEB"]
    page_rows = [
        row
        for row in public_rows
        if (row.get("metadata") or {}).get("object_level")
        == "source_page_lineage_parent"
    ]
    slice_rows = [row for row in public_rows if row not in page_rows]
    if (
        len(records) != 1877
        or len(public_rows) != 36
        or len(page_rows) != 17
        or len(slice_rows) != 19
    ):
        raise ValueError("current_source_successor_population_drift")

    source_results = deepcopy(list(predecessor.get("source_results") or []))
    source_results.append(
        {
            "source_id": "reviewed_public_capture_bound_sources_v1",
            "input_kind": "reviewed_public_capture_bound_page_and_slice_records",
            "status": "source_compiled",
            "source_ref": SOURCE_RECORDS_REF,
            "source_sha256": _sha256_file(SOURCE_RECORDS_REF),
            "authority_result_ref": PUBLIC_RESULT_REF,
            "authority_result_digest": public_digest,
            "document_parents_added": len(page_rows),
            "retrieval_children_added": len(public_rows),
            "invalid_records_excluded": 0,
        }
    )

    parent_ids = {
        str((row.get("metadata") or {}).get("parent_document_id") or "")
        for row in records
        if str((row.get("metadata") or {}).get("parent_document_id") or "")
    }
    source_types = _count_by(records, "source_type")
    tickers = _count_by(records, "ticker")
    previous_store = dict(predecessor.get("object_store") or {})
    object_store = {
        **previous_store,
        "document_parents": len(parent_ids),
        "retrieval_children": len(records),
        "children_from_immutable_current_capture": int(
            previous_store.get("children_from_immutable_current_capture") or 0
        )
        + len(public_rows),
        "children_by_ticker": tickers,
        "children_by_source_type": source_types,
        "max_retrieval_child_characters": max(
            len(str(row.get("text") or "")) for row in records
        ),
        "reviewed_public_page_records": len(page_rows),
        "reviewed_public_exact_slice_records": len(slice_rows),
    }

    case_readiness: dict[str, dict[str, Any]] = {}
    for ticker in ("DELL", "MU", "NVDA"):
        case_rows = [row for row in records if row.get("ticker") == ticker]
        issuer_rows = [
            row for row in case_rows if row.get("source_type") != "MARKET_SNAPSHOT"
        ]
        market_rows = [
            row for row in case_rows if row.get("source_type") == "MARKET_SNAPSHOT"
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

    acceptance = deepcopy(dict(predecessor.get("acceptance") or {}))
    acceptance.update(
        {
            "reviewed_public_page_and_slice_lineage_complete": True,
            "reviewed_public_candidates_remain_non_authoritative": True,
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
            "result_ref": PUBLIC_RESULT_REF,
            "result_digest": public_digest,
            "source_records_ref": SOURCE_RECORDS_REF,
            "source_records_sha256": _sha256_file(SOURCE_RECORDS_REF),
        },
        "known_boundary": (
            "This successor keeps the current official disclosure, transcript and "
            "PIT objects and adds 17 capture-bound reviewed public pages plus 19 "
            "exact source slices to the canonical source store. The public records "
            "are retrievable candidates only; Evidence authority still requires an "
            "exact page-lineage and content-digest join to the immutable reviewed "
            "Pack. It grants no new numeric, causal, S1 qualification or publication "
            "authority."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _with_resource(
    registry: dict[str, Any],
    *,
    resource_id: str,
    ref: str,
    payload: Mapping[str, Any],
) -> None:
    # Registry identity is byte-for-byte file identity, not merely canonical JSON
    # identity. Existing versioned assets are not guaranteed to use this script's
    # serializer, so hash the materialized file after confirming the payload is the
    # one we intended to register.
    if canonical_digest(_read_json(ref)) != canonical_digest(dict(payload)):
        raise ValueError(f"runtime_registry_payload_file_drift:{resource_id}")
    rendered = _path(ref).read_bytes()
    rows = registry.get("resources") or []
    matching = [row for row in rows if row.get("resource_id") == resource_id]
    if len(matching) != 1:
        raise ValueError(f"runtime_registry_resource_missing:{resource_id}")
    matching[0]["repo_relative_path"] = ref
    matching[0]["sha256"] = hashlib.sha256(rendered).hexdigest()
    matching[0]["bytes"] = len(rendered)


def _refresh_registry_aggregate(registry: dict[str, Any]) -> None:
    rows = registry.get("resources") or []
    if [str(row.get("resource_id") or "") for row in rows] != sorted(
        str(row.get("resource_id") or "") for row in rows
    ):
        raise ValueError("runtime_registry_resource_order_invalid")
    registry["resource_count"] = len(rows)
    registry["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    registry["resource_canonical_digest"] = canonical_digest(rows)


def _build_policy(predecessor: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(predecessor))
    value["policy_id"] = "FIN-0.1.3-S1-CURRENT-PRODUCT-RUNTIME-BINDING-V1.7"
    assets = value["assets"]
    assets["retrieval_snapshot"]["ref"] = SNAPSHOT_REF
    assets["object_compiler_result"]["ref"] = PUBLIC_RESULT_REF
    assets["hybrid_runtime_policy"]["ref"] = HYBRID_REF
    assets["route_policy"]["ref"] = ROUTE_REF
    return value


def main() -> int:
    predecessor_source = _read_json(
        "configs/runtime/"
        "fin_ia_0_1_3_s1b_current_financial_object_store_result_v1_1.json"
    )
    public_result = _read_json(PUBLIC_RESULT_REF)
    records = _read_jsonl(SOURCE_RECORDS_REF)
    source_result = _build_source_result(
        predecessor_source,
        public_result,
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
    _write_json(SNAPSHOT_REF, snapshot)

    policy = _build_policy(
        _read_json(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_6.json"
        )
    )
    _write_json(POLICY_REF, policy)

    registry = deepcopy(_read_json(REGISTRY_REF))
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R32"
    )
    replacements: dict[str, tuple[str, Mapping[str, Any]]] = {
        "application.config.current_financial_research_kernel": (
            KERNEL_REF,
            _read_json(KERNEL_REF),
        ),
        "application.config.current_hybrid_candidate_runtime_policy": (
            HYBRID_REF,
            _read_json(HYBRID_REF),
        ),
        "application.config.current_query_object_fact_route_policy": (
            ROUTE_REF,
            _read_json(ROUTE_REF),
        ),
        "application.config.current_s1_runtime_binding_policy": (
            POLICY_REF,
            policy,
        ),
        "application.result.current_research_retrieval_snapshot": (
            SNAPSHOT_REF,
            snapshot,
        ),
    }
    for resource_id, (ref, payload) in replacements.items():
        _with_resource(
            registry,
            resource_id=resource_id,
            ref=ref,
            payload=payload,
        )
    _refresh_registry_aggregate(registry)

    receipt = build_current_s1_runtime_binding_receipt(
        ROOT,
        policy,
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
        policy,
        repository_root=ROOT,
    )
    print(
        json.dumps(
            {
                "status": "current_public_reachability_runtime_promoted",
                "registry_id": registry["registry_id"],
                "source_record_count": receipt["source_object_index_lineage"][
                    "source_record_count"
                ],
                "compiled_object_count": receipt["source_object_index_lineage"][
                    "compiled_object_count"
                ],
                "public_page_records": source_result["object_store"][
                    "reviewed_public_page_records"
                ],
                "public_exact_slice_records": source_result["object_store"][
                    "reviewed_public_exact_slice_records"
                ],
                "snapshot_digest": snapshot["result_digest"],
                "binding_digest": receipt["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
