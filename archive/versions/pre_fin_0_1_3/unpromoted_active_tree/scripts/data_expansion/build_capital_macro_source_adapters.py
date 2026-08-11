from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.capital_macro_pack import build_capital_macro_pack
from sec_agent.capital_macro_source_adapters import (
    CAPITAL_MACRO_SOURCE_ADAPTER_SCHEMA_VERSION,
    build_capital_macro_source_adapter,
    load_jsonl,
    load_universe_csv,
    parse_sec_13f_bulk_zip,
    parse_sec_fsd_capital_structure_zip,
)


DEFAULT_OUTPUT_ROOT = Path("Z:/FIN_Insight_Agent_data/processed_private/capital_macro_source_adapters")
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "capital_macro_source_adapter_summary_v0_1.json"
DEFAULT_UNIVERSE_CSV = REPO_ROOT / "data" / "manifests" / "tier1_tier2_market_universe_v0_1.csv"
DEFAULT_UNIVERSE_MANIFEST = REPO_ROOT / "data" / "manifests" / "tier1_plus_tier2_supply_chain_manifest.jsonl"
DEFAULT_NORMALIZED_RECORDS = Path("Z:/FIN_Insight_Agent_data/processed_private/public_sources/public_source_normalized_materialized_v0_3/normalized_records.jsonl")
DEFAULT_ENDPOINT_RECORDS = REPO_ROOT / "data" / "processed_private" / "public_sources" / "public_source_mapping_endpoint_gate_v0_1" / "endpoint_records.jsonl"
DEFAULT_MAPPING_CANDIDATES = REPO_ROOT / "data" / "processed_private" / "public_sources" / "public_source_mapping_endpoint_gate_v0_1" / "mapping_candidates.jsonl"
DEFAULT_INVENTORY_ROWS = REPO_ROOT / "data" / "processed_private" / "public_sources" / "public_source_inventory_adapter_v0_1" / "public_source_inventory_rows.jsonl"
DEFAULT_13F_ZIP = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/sec_ownership_and_13f/01mar2026-31may2026_form13f.zip")
DEFAULT_FSD_ZIP = Path("Z:/FIN_Insight_Agent_data/raw_private/public_source_extended_materialization/sec_financial_statement_data_sets/2026q1.zip")
DEFAULT_SEC_CAPITAL_TEXT_INPUTS = (
    REPO_ROOT / "data" / "staging" / "sec_tier1_sp500_annual" / "chunks" / "tier1_sp500_us_annual_10k_chunks_fy2023_2025_v0_1.jsonl",
    REPO_ROOT / "data" / "staging" / "sec_tier2_supply_chain_annual" / "chunks" / "tier2_supply_chain_sec_annual_chunks_fy2023_2025_v0_1.jsonl",
)

SEC_CAPITAL_TEXT_KEYWORDS = (
    "senior notes",
    "senior unsecured notes",
    "long-term debt",
    "long term debt",
    "debt securities",
    "debentures",
    "term loan",
    "credit facility",
    "revolving credit",
    "revolver",
    "commercial paper",
    "borrowings",
)
SEC_CAPITAL_SECTION_HINTS = (
    "financial statements",
    "management's discussion",
    "management discussion",
    "liquidity",
    "debt",
    "borrowings",
    "credit",
    "financing",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill K5/K6 source-specific rows into CapitalMacroExposurePack inputs.")
    parser.add_argument("--run-id", default="capital_macro_source_adapter_v0_1")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--universe-csv", type=Path, default=DEFAULT_UNIVERSE_CSV)
    parser.add_argument("--universe-manifest", type=Path, default=DEFAULT_UNIVERSE_MANIFEST)
    parser.add_argument("--normalized-records", type=Path, default=DEFAULT_NORMALIZED_RECORDS)
    parser.add_argument("--endpoint-records", type=Path, default=DEFAULT_ENDPOINT_RECORDS)
    parser.add_argument("--mapping-candidates", type=Path, default=DEFAULT_MAPPING_CANDIDATES)
    parser.add_argument("--inventory-rows", type=Path, default=DEFAULT_INVENTORY_ROWS)
    parser.add_argument(
        "--sec-capital-text-input",
        type=Path,
        action="append",
        default=None,
        help="JSONL SEC filing chunks to scan for debt footnote / credit facility parser inputs. Can be repeated.",
    )
    parser.add_argument("--sec-13f-zip", type=Path, default=DEFAULT_13F_ZIP)
    parser.add_argument("--sec-fsd-zip", type=Path, default=DEFAULT_FSD_ZIP)
    parser.add_argument("--max-normalized-records", type=int, default=10000)
    parser.add_argument("--max-endpoint-records", type=int, default=20000)
    parser.add_argument("--max-mapping-candidates", type=int, default=5000)
    parser.add_argument("--max-sec-capital-text-rows", type=int, default=20000)
    parser.add_argument("--max-13f-positions", type=int, default=5000)
    parser.add_argument("--max-fsd-filings", type=int, default=1000)
    parser.add_argument("--max-adapter-items-per-family", type=int, default=20000)
    parser.add_argument("--max-pack-items-per-family", type=int, default=20000)
    parser.add_argument("--skip-13f", action="store_true")
    parser.add_argument("--skip-fsd", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).isoformat()
    output_dir = _resolve_output(args.output_root) / args.run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    target_companies = load_universe_csv(args.universe_csv, manifest_path=args.universe_manifest)
    normalized_records = _load_jsonl_if_exists(args.normalized_records, limit=args.max_normalized_records)
    endpoint_records = _load_jsonl_if_exists(args.endpoint_records, limit=args.max_endpoint_records)
    mapping_candidates = _load_jsonl_if_exists(args.mapping_candidates, limit=args.max_mapping_candidates)
    inventory_rows = _load_jsonl_if_exists(args.inventory_rows, limit=args.max_mapping_candidates)
    sec_capital_text_inputs = args.sec_capital_text_input or list(DEFAULT_SEC_CAPITAL_TEXT_INPUTS)
    sec_capital_text_rows = _load_sec_capital_text_rows(sec_capital_text_inputs, limit=args.max_sec_capital_text_rows)
    sec_filing_metadata_rows = _sec_filing_metadata_rows_from_public_records(normalized_records, target_companies)

    adapter_inputs: dict[str, Any] = {
        "run_id": args.run_id,
        "target_companies": target_companies,
        "sec_capital_text_rows": sec_capital_text_rows,
        "sec_filing_metadata_rows": sec_filing_metadata_rows,
        "public_source_normalized_records": normalized_records,
        "public_source_endpoint_records": endpoint_records,
        "public_source_mapping_candidates": mapping_candidates,
        "public_source_inventory_rows": inventory_rows,
        "preparsed_capital_ownership_rows": [],
    }
    source_gap_rows: list[dict[str, Any]] = []

    if not args.skip_13f:
        sec_13f = parse_sec_13f_bulk_zip(args.sec_13f_zip, target_companies=target_companies, max_positions=args.max_13f_positions)
        adapter_inputs["preparsed_capital_ownership_rows"].extend(sec_13f["capital_ownership_rows"])
        source_gap_rows.extend(sec_13f["source_gaps"])
    if not args.skip_fsd:
        sec_fsd = parse_sec_fsd_capital_structure_zip(args.sec_fsd_zip, target_companies=target_companies, max_filings=args.max_fsd_filings)
        adapter_inputs["preparsed_capital_ownership_rows"].extend(sec_fsd["capital_ownership_rows"])
        source_gap_rows.extend(sec_fsd["source_gaps"])

    adapter = build_capital_macro_source_adapter(adapter_inputs, max_items_per_family=args.max_adapter_items_per_family)
    adapter["source_gaps"] = [*adapter.get("source_gaps", []), *source_gap_rows]
    adapter["summary"] = _adapter_summary(adapter)
    pack = build_capital_macro_pack(
        {"run_id": args.run_id, "capital_macro_source_adapter": adapter},
        max_items=args.max_pack_items_per_family,
    )

    output_paths = {
        "capital_ownership_rows": output_dir / "capital_ownership_rows.jsonl",
        "macro_driver_rows": output_dir / "macro_driver_rows.jsonl",
        "macro_exposure_rows": output_dir / "macro_exposure_rows.jsonl",
        "vertical_official_object_rows": output_dir / "vertical_official_object_rows.jsonl",
        "source_gaps": output_dir / "source_gaps.jsonl",
        "capital_macro_pack": output_dir / "capital_macro_pack.json",
        "summary": output_dir / "summary.json",
    }
    _write_jsonl(output_paths["capital_ownership_rows"], adapter.get("capital_ownership_rows") or [])
    _write_jsonl(output_paths["macro_driver_rows"], adapter.get("macro_driver_rows") or [])
    _write_jsonl(output_paths["macro_exposure_rows"], adapter.get("macro_exposure_rows") or [])
    _write_jsonl(output_paths["vertical_official_object_rows"], adapter.get("vertical_official_object_rows") or [])
    _write_jsonl(output_paths["source_gaps"], adapter.get("source_gaps") or [])
    _write_json(output_paths["capital_macro_pack"], pack)

    summary = {
        "schema_version": "sec_agent_capital_macro_source_adapter_summary_v0.1",
        "status": "pass" if pack.get("status") == "pass" else "partial_with_gaps",
        "generated_at": generated_at,
        "run_id": args.run_id,
        "adapter_schema_version": CAPITAL_MACRO_SOURCE_ADAPTER_SCHEMA_VERSION,
        "target_company_count": len(target_companies),
        "input_counts": {
            "normalized_record_count": len(normalized_records),
            "endpoint_record_count": len(endpoint_records),
            "mapping_candidate_count": len(mapping_candidates),
            "inventory_row_count": len(inventory_rows),
            "sec_capital_text_candidate_count": len(sec_capital_text_rows),
            "sec_filing_metadata_candidate_count": len(sec_filing_metadata_rows),
        },
        "adapter_summary": adapter["summary"],
        "capital_macro_pack_summary": pack.get("summary") or {},
        "capital_macro_pack_validation": pack.get("validation") or {},
        "outputs": {key: _path_str(path) for key, path in output_paths.items()},
        "inputs": {
            "normalized_records": _path_str(args.normalized_records),
            "endpoint_records": _path_str(args.endpoint_records),
            "mapping_candidates": _path_str(args.mapping_candidates),
            "inventory_rows": _path_str(args.inventory_rows),
            "sec_capital_text_inputs": [_path_str(path) for path in sec_capital_text_inputs],
            "sec_13f_zip": _path_str(args.sec_13f_zip),
            "sec_fsd_zip": _path_str(args.sec_fsd_zip),
        },
        "known_source_family_gaps": _known_source_family_gaps(summary=pack.get("summary") or {}),
        "boundary_policy": "K5/K6 rows are parser-gated pack inputs; unresolved source rows stay in source_gaps and must not be proxied into company claims.",
    }
    _write_json(output_paths["summary"], summary)
    manifest_output = _resolve_output(args.manifest_output)
    _write_json(manifest_output, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if pack.get("validation", {}).get("status") == "pass" else 2


def _adapter_summary(adapter: dict[str, Any]) -> dict[str, int]:
    return {
        "capital_ownership_row_count": len(adapter.get("capital_ownership_rows") or []),
        "macro_driver_row_count": len(adapter.get("macro_driver_rows") or []),
        "macro_exposure_row_count": len(adapter.get("macro_exposure_rows") or []),
        "vertical_official_object_row_count": len(adapter.get("vertical_official_object_rows") or []),
        "source_gap_count": len(adapter.get("source_gaps") or []),
        "pack_input_row_count": sum(
            len(adapter.get(key) or [])
            for key in ("capital_ownership_rows", "macro_driver_rows", "macro_exposure_rows", "vertical_official_object_rows")
        ),
    }


def _load_jsonl_if_exists(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    resolved = _resolve_output(path)
    if not resolved.exists():
        return []
    return load_jsonl(resolved, limit=limit)


def _load_sec_capital_text_rows(paths: Iterable[Path], *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        resolved = _resolve_output(path)
        if not resolved.exists():
            continue
        with resolved.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(rows) >= limit:
                    return rows
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                if not _is_sec_capital_text_candidate(row):
                    continue
                rows.append(_normalize_sec_capital_text_row(row, input_path=resolved))
    return rows


def _is_sec_capital_text_candidate(row: dict[str, Any]) -> bool:
    text = str(row.get("text") or row.get("snippet") or "")
    lowered = text.lower()
    if not lowered:
        return False
    if not any(keyword in lowered for keyword in SEC_CAPITAL_TEXT_KEYWORDS):
        return False
    if not _has_capital_amount_and_timing_signal(text):
        return False
    section_text = " ".join(
        str(row.get(key) or "").lower()
        for key in ("section", "block_heading", "block_type", "item_code")
    )
    if str(row.get("item_code") or "") in {"7", "8"}:
        return True
    return any(hint in section_text for hint in SEC_CAPITAL_SECTION_HINTS)


def _has_capital_amount_and_timing_signal(text: str) -> bool:
    lowered = text.lower()
    has_amount = bool(re.search(r"(?i)(\$|usd\s*)\s*[0-9][0-9,]*(?:\.[0-9]+)?", text)) or bool(
        re.search(r"(?i)\b[0-9][0-9,]*(?:\.[0-9]+)?\s*(billion|million|thousand|bn|mm)\b", text)
    )
    has_timing = "matur" in lowered or bool(re.search(r"(?i)\bdue\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|20\d{2})", text))
    has_rate = "%" in lowered
    return has_amount and (has_timing or has_rate)


def _normalize_sec_capital_text_row(row: dict[str, Any], *, input_path: Path) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    enriched = dict(row)
    enriched["source_id"] = str(row.get("source_id") or "sec_annual_debt_footnote_chunk")
    enriched["input_path"] = _path_str(input_path)
    for key in ("accession_number", "filing_date", "report_date", "period_end", "primary_document"):
        if not enriched.get(key) and metadata.get(key):
            enriched[key] = metadata[key]
    return enriched


def _sec_filing_metadata_rows_from_public_records(records: Iterable[dict[str, Any]], target_companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ticker_by_cik = {
        _normalize_cik(str(row.get("cik") or row.get("identifier") or "")): str(row.get("ticker") or "").upper()
        for row in target_companies
        if row.get("ticker")
    }
    rows: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("record_type") or "") != "filing_metadata_record":
            continue
        attributes = _attributes_dict(record.get("attributes") or record.get("attributes_json"))
        form_type = str(attributes.get("form") or record.get("form_type") or record.get("status") or "").upper()
        if not form_type:
            continue
        ticker = str(record.get("ticker") or "").upper()
        cik = _normalize_cik(str(record.get("identifier") or attributes.get("cik") or ""))
        if not ticker and cik:
            ticker = ticker_by_cik.get(cik, "")
        rows.append(
            {
                "source_id": "sec_edgar_apis",
                "record_type": "filing_metadata_record",
                "ticker": ticker,
                "form_type": form_type,
                "accession_number": attributes.get("accession_number") or record.get("record_id") or "",
                "filing_date": attributes.get("filing_date") or record.get("observation_date") or "",
                "source_url": record.get("api_route") or record.get("source_url") or "",
                "evidence_ref": record.get("record_id") or "",
            }
        )
    return rows


def _attributes_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_cik(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits.lstrip("0")


def _known_source_family_gaps(*, summary: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if int(summary.get("debt_instrument_count") or 0) == 0:
        gaps.append(
            {
                "source_family": "sec_debt_footnote",
                "status": "no_parser_promoted_rows",
                "reason": "Configured SEC capital text chunks did not satisfy strict amount/coupon/maturity gates.",
            }
        )
    if int(summary.get("equity_offering_count") or 0) == 0:
        gaps.append(
            {
                "source_family": "sec_offering_forms_s1_s3_424b_8k_exhibits",
                "status": "raw_material_not_materialized",
                "reason": "Parser gate exists, but no configured local S-1/S-3/424B/8-K exhibit source text or structured offering rows were found.",
            }
        )
    if int(summary.get("insider_transaction_count") or 0) == 0:
        gaps.append(
            {
                "source_family": "sec_form_3_4_5_insider_transactions",
                "status": "raw_material_not_materialized",
                "reason": "Parser gate exists, but no configured local Form 3/4/5 XML or structured insider transaction rows were found.",
            }
        )
    return gaps


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_output(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _path_str(path: Path) -> str:
    try:
        return _resolve_output(path).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return _resolve_output(path).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
