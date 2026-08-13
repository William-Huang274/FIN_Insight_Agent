from __future__ import annotations

import argparse
from collections import Counter
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

from retrieval.financial_objects import (  # noqa: E402
    FinancialObjectError,
    attach_legacy_aliases,
    compile_parsed_sec_capture,
    compile_raw_sec_html_capture,
    content_digest,
    normalize_legacy_candidate,
    project_market_snapshot,
    sha256_file,
    summarize_object_store,
    validate_source_object_manifest,
)
from retrieval.official_pdf_objects import compile_official_pdf_document  # noqa: E402


RESULT_SCHEMA_VERSION = "fin_ia_s1b_current_financial_object_store_result_v1_0"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FinancialObjectError(f"json_object_required:{path.name}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def build_object_store(
    *,
    manifest_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = validate_source_object_manifest(_read_json(manifest_path))
    allowed_tickers = {
        str(value).strip().upper() for value in manifest["allowed_tickers"]
    }
    case_tickers = {
        str(value).strip().upper() for value in manifest["case_tickers"]
    }
    parents: dict[str, dict[str, Any]] = {}
    parent_priorities: dict[str, int] = {}
    children: dict[str, dict[str, Any]] = {}
    source_results: list[dict[str, Any]] = []
    duplicate_children_identical = 0
    invalid_records_excluded = 0
    alias_records: list[dict[str, Any]] = []

    def add_parent(parent: dict[str, Any]) -> None:
        parent_id = str(parent["document_id"])
        priority = {
            "immutable_capture_bound": 3,
            "immutable_local_snapshot_bound": 3,
            "local_candidate_store_lineage_only": 1,
        }.get(str(parent.get("lineage_state") or ""), 0)
        if parent_id not in parents or priority > parent_priorities[parent_id]:
            parents[parent_id] = parent
            parent_priorities[parent_id] = priority

    def add_child(child: dict[str, Any]) -> None:
        nonlocal duplicate_children_identical
        child_id = str(child["evidence_id"])
        existing = children.get(child_id)
        if existing is None:
            children[child_id] = child
            return
        if content_digest(existing) != content_digest(child):
            raise FinancialObjectError(f"financial_object_id_collision:{child_id}")
        duplicate_children_identical += 1

    for source in manifest["sources"]:
        source_id = str(source["source_id"])
        input_kind = str(source["input_kind"])
        path = _resolve(str(source["path"]))
        if not path.is_file():
            if source.get("required") is True:
                raise FinancialObjectError(f"required_source_missing:{source_id}")
            source_results.append(
                {"source_id": source_id, "status": "optional_source_missing"}
            )
            continue
        actual_sha256 = sha256_file(path)
        expected_sha256 = str(source.get("expected_sha256") or "")
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise FinancialObjectError(f"source_digest_mismatch:{source_id}")
        source_ref = _relative(path)
        before_parents = len(parents)
        before_children = len(children)
        source_invalid = 0

        if input_kind in {"legacy_candidate_jsonl", "legacy_qrel_alias_jsonl"}:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        source_invalid += 1
                        continue
                    if not isinstance(raw, Mapping):
                        source_invalid += 1
                        continue
                    ticker = str(raw.get("ticker") or "").strip().upper()
                    if ticker not in allowed_tickers:
                        continue
                    if input_kind == "legacy_qrel_alias_jsonl":
                        if not (
                            str(raw.get("evidence_id") or "").strip()
                            and str(raw.get("text") or "").strip()
                            and str(raw.get("source_url") or "").strip()
                        ):
                            source_invalid += 1
                            continue
                        alias_records.append(dict(raw))
                        continue
                    try:
                        parent, child = normalize_legacy_candidate(
                            raw,
                            source_ref=source_ref,
                            source_sha256=actual_sha256,
                        )
                    except FinancialObjectError:
                        source_invalid += 1
                        continue
                    add_parent(parent)
                    add_child(child)
        elif input_kind in {"parsed_sec_capture", "raw_sec_html_capture"}:
            compiler = (
                compile_raw_sec_html_capture
                if input_kind == "raw_sec_html_capture"
                else compile_parsed_sec_capture
            )
            parent, parsed_children = compiler(
                _read_json(path),
                source_spec=source,
                capture_ref=source_ref,
                capture_sha256=actual_sha256,
            )
            if str(parent["ticker"]) not in allowed_tickers:
                raise FinancialObjectError(f"parsed_source_owner_not_allowed:{source_id}")
            add_parent(parent)
            for child in parsed_children:
                add_child(child)
        elif input_kind == "parsed_official_pdf_document":
            parent, parsed_children = compile_official_pdf_document(
                _read_json(path),
                source_spec=source,
                parsed_ref=source_ref,
                parsed_sha256=actual_sha256,
            )
            if str(parent["ticker"]) not in allowed_tickers:
                raise FinancialObjectError(
                    f"parsed_source_owner_not_allowed:{source_id}"
                )
            add_parent(parent)
            for child in parsed_children:
                add_child(child)
        elif input_kind == "market_evidence_jsonl":
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        source_invalid += 1
                        continue
                    if not isinstance(raw, Mapping):
                        source_invalid += 1
                        continue
                    ticker = str(raw.get("ticker") or "").strip().upper()
                    if ticker not in case_tickers:
                        continue
                    try:
                        parent, child = project_market_snapshot(
                            raw,
                            source_ref=source_ref,
                            source_sha256=actual_sha256,
                        )
                    except FinancialObjectError:
                        source_invalid += 1
                        continue
                    add_parent(parent)
                    add_child(child)
        else:  # pragma: no cover - guarded by manifest validation
            raise FinancialObjectError(f"source_kind_unreachable:{input_kind}")

        invalid_records_excluded += source_invalid
        source_results.append(
            {
                "source_id": source_id,
                "input_kind": input_kind,
                "status": "source_compiled",
                "source_ref": source_ref,
                "source_sha256": actual_sha256,
                "document_parents_added": len(parents) - before_parents,
                "retrieval_children_added": len(children) - before_children,
                "invalid_records_excluded": source_invalid,
            }
        )

    alias_crosswalk = attach_legacy_aliases(alias_records, children.values())
    required_alias_ids = {
        str(value) for value in manifest.get("required_qrel_alias_ids") or ()
    }
    alias_result_by_id = {
        str(row["legacy_source_record_id"]): row for row in alias_crosswalk
    }
    missing_required_aliases = sorted(
        alias_id
        for alias_id in required_alias_ids
        if alias_result_by_id.get(alias_id, {}).get("status") != "alias_mapped"
    )

    parent_child_counts = Counter(
        str((child.get("metadata") or {}).get("parent_document_id") or "")
        for child in children.values()
    )
    for parent_id, parent in parents.items():
        parent["child_count"] = parent_child_counts[parent_id]
    missing_parent_ids = sorted(set(parent_child_counts) - set(parents))
    if missing_parent_ids:
        raise FinancialObjectError(
            f"financial_object_parent_missing:{missing_parent_ids[0]}"
        )

    parent_rows = sorted(
        parents.values(),
        key=lambda row: (
            str(row.get("ticker") or ""),
            str(row.get("publication_date") or ""),
            str(row.get("source_type") or ""),
            str(row.get("document_id") or ""),
        ),
    )
    child_rows = sorted(
        children.values(),
        key=lambda row: (
            str(row.get("ticker") or ""),
            str(row.get("publication_date") or ""),
            str(row.get("source_type") or ""),
            str(row.get("evidence_id") or ""),
        ),
    )
    store_summary = summarize_object_store(parents=parent_rows, children=child_rows)
    case_readiness: dict[str, Any] = {}
    for ticker in sorted(case_tickers):
        issuer_children = [
            row
            for row in child_rows
            if row.get("ticker") == ticker
            and row.get("source_type")
            in {"10-K", "10-Q", "8-K", "20-F", "40-F", "6-K"}
        ]
        market_children = [
            row
            for row in child_rows
            if row.get("ticker") == ticker
            and row.get("source_type") == "MARKET_SNAPSHOT"
        ]
        case_readiness[ticker] = {
            "issuer_retrieval_children": len(issuer_children),
            "latest_issuer_publication_date": max(
                (str(row.get("publication_date") or "") for row in issuer_children),
                default=None,
            ),
            "point_in_time_market_children": len(market_children),
            "market_as_of_dates": sorted(
                {str(row.get("publication_date") or "") for row in market_children}
            ),
        }

    acceptance = {
        "source_digests_verified": all(
            row.get("status") == "source_compiled" for row in source_results
        ),
        "parent_child_lineage_complete": not missing_parent_ids,
        "parsed_current_sources_capture_bound": (
            store_summary["children_from_immutable_current_capture"] > 0
        ),
        "table_boundaries_balanced": (
            store_summary["unbalanced_table_children"] == 0
        ),
        "retrieval_children_bounded": (
            not store_summary["oversized_non_table_children"]
            and not store_summary["oversized_table_children"]
        ),
        "three_case_issuer_children_present": all(
            row["issuer_retrieval_children"] > 0
            for row in case_readiness.values()
        ),
        "three_case_market_role_present": all(
            row["point_in_time_market_children"] == 1
            for row in case_readiness.values()
        ),
        "required_qrel_aliases_mapped": not missing_required_aliases,
        "candidate_state": "candidate_not_evidence",
        "model_calls": 0,
        "network_calls": 0,
        "dense_calls": 0,
        "rerank_calls": 0,
        "complete_s1_claimed": False,
        "valuation_ready": False,
    }
    ready_keys = (
        "source_digests_verified",
        "parent_child_lineage_complete",
        "parsed_current_sources_capture_bound",
        "table_boundaries_balanced",
        "retrieval_children_bounded",
        "three_case_issuer_children_present",
        "three_case_market_role_present",
        "required_qrel_aliases_mapped",
    )
    status = (
        "s1b_current_financial_object_store_ready_with_typed_gaps"
        if all(acceptance[key] for key in ready_keys)
        else "s1b_current_financial_object_store_failed"
    )
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": status,
        "recorded_at": "2026-08-12",
        "manifest_ref": _relative(manifest_path),
        "manifest_digest": content_digest(manifest),
        "source_results": source_results,
        "object_store": store_summary,
        "case_readiness": case_readiness,
        "duplicate_children_identical": duplicate_children_identical,
        "invalid_records_excluded": invalid_records_excluded,
        "legacy_alias_crosswalk": {
            "aliases_seen": len(alias_crosswalk),
            "aliases_mapped": sum(
                row["status"] == "alias_mapped" for row in alias_crosswalk
            ),
            "required_aliases": len(required_alias_ids),
            "missing_required_aliases": missing_required_aliases,
            "mappings": [
                row
                for row in alias_crosswalk
                if row["legacy_source_record_id"] in required_alias_ids
            ],
        },
        "typed_gaps": manifest.get("typed_gaps") or [],
        "acceptance": acceptance,
        "known_boundary": (
            "This S1-B result compiles current official disclosures, inherited semantic "
            "children and point-in-time market snapshots into one parent-child object store. "
            "It does not promote candidates to Evidence, does not supply missing Dell prepared "
            "remarks, and does not claim valuation readiness from a price-only stale snapshot."
        ),
    }
    result = {**unsigned, "result_digest": content_digest(unsigned)}
    return result, parent_rows, child_rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the FIN 0.1.3 S1-B current financial object store."
    )
    parser.add_argument(
        "--manifest",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1b_current_source_object_manifest_v1_0.json"
        ),
    )
    parser.add_argument(
        "--output-root",
        default=(
            "data/workbench_private/"
            "fin_0_1_3_s1b_current_financial_object_store/v1"
        ),
    )
    parser.add_argument(
        "--summary-output",
        default=(
            "configs/runtime/"
            "fin_ia_0_1_3_s1b_current_financial_object_store_result_v1_0.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result, parents, children = build_object_store(
        manifest_path=_resolve(args.manifest)
    )
    output_root = _resolve(args.output_root)
    _write_jsonl(output_root / "documents.jsonl", parents)
    _write_jsonl(output_root / "records.jsonl", children)
    _write_json(output_root / "result.json", result)
    _write_json(_resolve(args.summary_output), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "object_store": result["object_store"],
                "case_readiness": result["case_readiness"],
                "output_root": _relative(output_root),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"].endswith("_with_typed_gaps") else 1


if __name__ == "__main__":
    raise SystemExit(main())
