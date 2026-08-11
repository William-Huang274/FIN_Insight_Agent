from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CURRENT_CONFIG = REPO_ROOT / "configs" / "sector_depth_full238_us_v0_2_10k_fy2023_2025.yaml"
DEFAULT_SEC_TICKERS = REPO_ROOT / "data" / "raw_private" / "sec" / "_reference" / "company_tickers.json"
DEFAULT_COMPANY_OVERRIDES = REPO_ROOT / "configs" / "data_sources" / "universe_company_overrides_v0_1.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "manifests"
SCHEMA_VERSION = "fin_agent_universe_manifest_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Tier 0/Tier 1 universe manifests for staged data expansion.")
    parser.add_argument("--current-config", type=Path, default=DEFAULT_CURRENT_CONFIG)
    parser.add_argument("--sec-company-tickers", type=Path, default=DEFAULT_SEC_TICKERS)
    parser.add_argument("--company-overrides", type=Path, default=DEFAULT_COMPANY_OVERRIDES)
    parser.add_argument("--sp500-csv", type=Path, default=None, help="Optional CSV with ticker/symbol, company/name, sector, cik columns.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tier0-output", default="tier0_full238_manifest.jsonl")
    parser.add_argument("--tier1-output", default="tier1_sp500_plus_current_manifest.jsonl")
    parser.add_argument("--target-tier1-count", type=int, default=500, help="Diagnostic target; does not cap output unless --cap-tier1-count is set.")
    parser.add_argument("--cap-tier1-count", type=int, default=0, help="Optional hard cap. Default 0 preserves S&P 500 plus current coverage.")
    parser.add_argument("--summary-output", default="universe_tiers_build_summary_v0_1.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    current_config = _load_yaml(_resolve(args.current_config))
    sec_reference = _load_sec_company_reference(_resolve(args.sec_company_tickers))
    company_overrides = _load_company_overrides(_resolve(args.company_overrides))
    current_rows = _current_config_rows(current_config, sec_reference=sec_reference, company_overrides=company_overrides)
    sp500_rows = _sp500_rows(args.sp500_csv, sec_reference=sec_reference, company_overrides=company_overrides) if args.sp500_csv else []

    tier0 = _dedupe_rows(current_rows, tier="tier0_current_full238", dedupe_by_cik=True)
    tier1_source_rows = [*sp500_rows, *current_rows]
    tier1 = _dedupe_rows(tier1_source_rows, tier="tier1_sp500_plus_current", dedupe_by_cik=True)
    if args.cap_tier1_count > 0 and len(tier1) > args.cap_tier1_count:
        tier1 = _cap_tier1(tier1, target=args.cap_tier1_count)

    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tier0_path = output_dir / args.tier0_output
    tier1_path = output_dir / args.tier1_output
    summary_path = output_dir / args.summary_output
    _write_jsonl(tier0_path, tier0)
    _write_jsonl(tier1_path, tier1)

    summary = {
        "schema_version": "fin_agent_universe_tiers_build_summary_v0.1",
        "status": "completed",
        "current_config": str(_resolve(args.current_config)),
        "sec_company_reference": str(_resolve(args.sec_company_tickers)),
        "company_overrides": str(_resolve(args.company_overrides)) if _resolve(args.company_overrides).exists() else "",
        "sp500_csv": str(_resolve(args.sp500_csv)) if args.sp500_csv else "",
        "sp500_source_status": "provided" if sp500_rows else "not_provided_current_only_tier1",
        "tier0_company_count": len(tier0),
        "tier1_company_count": len(tier1),
        "tier1_sp500_source_row_count": len(sp500_rows),
        "tier1_added_current_only_company_count": sum(1 for row in tier1 if "current_full238" in set(row.get("source_sets") or []) and "sp500_constituent" not in set(row.get("source_sets") or [])),
        "target_tier1_count": args.target_tier1_count,
        "cap_tier1_count": args.cap_tier1_count,
        "tier0_missing_cik": sum(1 for row in tier0 if not row.get("cik")),
        "tier1_missing_cik": sum(1 for row in tier1 if not row.get("cik")),
        "outputs": {
            "tier0_manifest": str(tier0_path),
            "tier1_manifest": str(tier1_path),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _current_config_rows(
    config: Mapping[str, Any],
    *,
    sec_reference: Mapping[str, Mapping[str, Any]],
    company_overrides: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for company in config.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        override = company_overrides.get(ticker, {})
        ref = sec_reference.get(ticker, {})
        cik = _normalize_cik(company.get("cik") or override.get("cik") or ref.get("cik"))
        name = str(company.get("company_name") or company.get("name") or override.get("company_name") or ref.get("company_name") or "").strip()
        category = str(company.get("category") or "").strip()
        industry_groups = _string_list(company.get("industry_groups"))
        sector = industry_groups[0] if industry_groups else category
        rows.append(
            _manifest_row(
                ticker=ticker,
                cik=cik,
                company_name=name,
                sector=sector,
                category=category,
                source_sets=["current_full238", *(_string_list(company.get("source_sets")))],
                source_config_ref=str(config.get("batch_id") or ""),
                source_gap="" if cik else "missing_cik_mapping",
            )
        )
    return rows


def _sp500_rows(
    path: Path | None,
    *,
    sec_reference: Mapping[str, Mapping[str, Any]],
    company_overrides: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if path is None:
        return []
    resolved = _resolve(path)
    if not resolved.exists():
        raise FileNotFoundError(f"S&P 500 CSV not found: {resolved}")
    rows: list[dict[str, Any]] = []
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            ticker = str(raw.get("ticker") or raw.get("symbol") or raw.get("Symbol") or raw.get("Ticker") or "").upper().strip()
            if not ticker:
                continue
            ticker = ticker.replace(".", "-")
            override = company_overrides.get(ticker, {})
            ref = sec_reference.get(ticker, {})
            cik = _normalize_cik(raw.get("cik") or raw.get("CIK") or override.get("cik") or ref.get("cik"))
            name = str(
                raw.get("company_name")
                or raw.get("company")
                or raw.get("Security")
                or raw.get("name")
                or raw.get("Name")
                or override.get("company_name")
                or ref.get("company_name")
                or ""
            ).strip()
            sector = str(raw.get("sector") or raw.get("GICS Sector") or raw.get("Sector") or "").strip()
            rows.append(
                _manifest_row(
                    ticker=ticker,
                    cik=cik,
                    company_name=name,
                    sector=sector,
                    category=sector,
                    source_sets=["sp500_constituent"],
                    source_config_ref=str(resolved),
                    source_gap="" if cik else "missing_cik_mapping",
                )
            )
    return rows


def _manifest_row(
    *,
    ticker: str,
    cik: str,
    company_name: str,
    sector: str,
    category: str,
    source_sets: list[str],
    source_config_ref: str,
    source_gap: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "cik": cik,
        "company_name": company_name,
        "sector": sector,
        "category": category,
        "source_sets": _unique_strings(source_sets),
        "source_config_ref": source_config_ref,
        "sec_download_eligible": bool(cik),
        "source_gap": source_gap,
        "alternate_tickers": [],
    }


def _dedupe_rows(rows: Iterable[Mapping[str, Any]], *, tier: str, dedupe_by_cik: bool) -> list[dict[str, Any]]:
    by_ticker: dict[str, dict[str, Any]] = {}
    by_cik: dict[str, dict[str, Any]] = {}
    for raw in rows:
        ticker = str(raw.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        cik = str(raw.get("cik") or "").strip()
        current = by_cik.get(cik) if dedupe_by_cik and cik else None
        if current is None:
            current = by_ticker.get(ticker)
        if current is None:
            current = dict(raw)
            current["alternate_tickers"] = _unique_strings(current.get("alternate_tickers") or [])
            by_ticker[ticker] = current
            if dedupe_by_cik and cik:
                by_cik[cik] = current
        else:
            if current.get("ticker") != ticker:
                current["alternate_tickers"] = _unique_strings([*(current.get("alternate_tickers") or []), ticker])
                if _prefer_replacement_ticker(current, raw):
                    previous = str(current.get("ticker") or "").upper().strip()
                    current["ticker"] = ticker
                    current["alternate_tickers"] = _unique_strings([*(current.get("alternate_tickers") or []), previous])
            current["source_sets"] = _unique_strings([*(current.get("source_sets") or []), *(raw.get("source_sets") or [])])
            current["company_name"] = current.get("company_name") or raw.get("company_name") or ""
            current["cik"] = current.get("cik") or raw.get("cik") or ""
            current["sector"] = current.get("sector") or raw.get("sector") or ""
            current["category"] = current.get("category") or raw.get("category") or ""
            current["sec_download_eligible"] = bool(current.get("cik"))
            current["source_gap"] = "" if current.get("cik") else "missing_cik_mapping"
        current["universe_tier"] = tier
    result = list({id(row): row for row in by_ticker.values()}.values())
    for row in result:
        row["alternate_tickers"] = [ticker for ticker in _unique_strings(row.get("alternate_tickers") or []) if ticker != row.get("ticker")]
    return sorted(result, key=lambda item: str(item.get("ticker") or ""))


def _cap_tier1(rows: list[dict[str, Any]], *, target: int) -> list[dict[str, Any]]:
    current = [row for row in rows if "current_full238" in set(row.get("source_sets") or [])]
    rest = [row for row in rows if row not in current]
    selected = [*current, *rest]
    return selected[:target]


def _prefer_replacement_ticker(current: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    current_sources = set(current.get("source_sets") or [])
    candidate_sources = set(candidate.get("source_sets") or [])
    if "current_full238" in candidate_sources and "current_full238" not in current_sources:
        return True
    return False


def _load_sec_company_reference(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.values() if isinstance(payload, Mapping) else payload
    result: dict[str, dict[str, str]] = {}
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        result[ticker] = {
            "ticker": ticker,
            "cik": _normalize_cik(item.get("cik_str") or item.get("cik")),
            "company_name": str(item.get("title") or item.get("name") or "").strip(),
        }
    return result


def _load_company_overrides(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("companies") if isinstance(payload, Mapping) else []
    result: dict[str, dict[str, str]] = {}
    for item in rows or []:
        if not isinstance(item, Mapping):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        result[ticker] = {
            "ticker": ticker,
            "cik": _normalize_cik(item.get("cik")),
            "company_name": str(item.get("company_name") or "").strip(),
        }
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _resolve(path: Path | str | None) -> Path:
    if path is None:
        return Path("")
    resolved = Path(path)
    return resolved if resolved.is_absolute() else REPO_ROOT / resolved


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = "".join(char for char in text if char.isdigit())
    return digits.zfill(10) if digits else ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
