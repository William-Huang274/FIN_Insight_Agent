from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and normalize concrete industry source-family snapshots."
    )
    parser.add_argument("--contract", default="configs/industry_data_api_contracts_v0_2.yaml")
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--output-root", default="data/processed_private/industry_data")
    parser.add_argument("--timeout-s", type=int, default=25)
    parser.add_argument("--sleep-s", type=float, default=0.1)
    parser.add_argument("--max-rows-per-series", type=int, default=5000)
    parser.add_argument("--skip-live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = load_yaml(REPO_ROOT / args.contract)
    snapshot_id = args.snapshot_id or contract.get("snapshot_policy", {}).get("batch_id") or "industry_snapshot"
    as_of_date = args.as_of_date or contract.get("snapshot_policy", {}).get("default_as_of_date") or datetime.now(timezone.utc).date().isoformat()
    output_dir = REPO_ROOT / args.output_root / snapshot_id
    output_dir.mkdir(parents=True, exist_ok=True)

    fetched_at = datetime.now(timezone.utc).isoformat()
    observations: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for source in contract.get("source_families", []) or []:
        provider = str(source.get("provider") or "")
        route_type = str(source.get("route_type") or "")
        if args.skip_live:
            failures.append(
                {
                    "source_family": source.get("source_family"),
                    "provider": provider,
                    "status": "skipped_live",
                }
            )
            continue
        if route_type == "fred_csv":
            for series in source.get("series", []) or []:
                try:
                    rows = download_fred_series(source, series, as_of_date=as_of_date, fetched_at=fetched_at, timeout=args.timeout_s)
                    if args.max_rows_per_series > 0:
                        rows = rows[-args.max_rows_per_series :]
                    observations.extend(rows)
                    evidence_rows.append(build_series_evidence_row(source, series, rows, as_of_date=as_of_date, fetched_at=fetched_at))
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        {
                            "source_family": source.get("source_family"),
                            "provider": provider,
                            "series_id": series.get("series_id"),
                            "status": "download_failed",
                            "error": str(exc),
                        }
                    )
                if args.sleep_s > 0:
                    time.sleep(args.sleep_s)
        elif route_type == "public_json":
            try:
                row = download_public_json_source(source, as_of_date=as_of_date, fetched_at=fetched_at, timeout=args.timeout_s)
                evidence_rows.append(row)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "source_family": source.get("source_family"),
                        "provider": provider,
                        "dataset_id": (source.get("dataset") or {}).get("dataset_id"),
                        "status": "download_failed",
                        "error": str(exc),
                    }
                )
            if args.sleep_s > 0:
                time.sleep(args.sleep_s)
        elif route_type == "eia_v2_json":
            try:
                rows, row = download_eia_v2_source(source, as_of_date=as_of_date, fetched_at=fetched_at, timeout=args.timeout_s)
                observations.extend(rows)
                evidence_rows.append(row)
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "source_family": source.get("source_family"),
                        "provider": provider,
                        "dataset_id": (source.get("dataset") or {}).get("dataset_id"),
                        "status": "download_failed",
                        "error": str(exc),
                    }
                )
            if args.sleep_s > 0:
                time.sleep(args.sleep_s)
        else:
            failures.append(
                {
                    "source_family": source.get("source_family"),
                    "provider": provider,
                    "route_type": route_type,
                    "status": "unsupported_route_type",
                }
            )

    observations_path = output_dir / "industry_observations.jsonl"
    evidence_path = output_dir / "industry_evidence_rows.jsonl"
    metadata_path = output_dir / "industry_snapshot_metadata.json"
    duckdb_path = output_dir / "industry_snapshot.duckdb"
    write_jsonl(observations_path, observations)
    write_jsonl(evidence_path, evidence_rows)
    duckdb_summary = write_duckdb(duckdb_path, observations, evidence_rows)

    metadata = {
        "schema_version": "industry_source_snapshot_v0.2",
        "snapshot_id": snapshot_id,
        "as_of_date": as_of_date,
        "contract_path": args.contract,
        "generated_at": fetched_at,
        "observation_count": len(observations),
        "evidence_row_count": len(evidence_rows),
        "failure_count": len(failures),
        "failures": failures,
        "outputs": {
            "observations": str(observations_path),
            "evidence_rows": str(evidence_path),
            "duckdb": str(duckdb_path),
            "metadata": str(metadata_path),
        },
        "duckdb": duckdb_summary,
        "deferred_provider_contracts": contract.get("deferred_provider_contracts", []),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0 if (not failures or args.skip_live) else 2


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def download_fred_series(
    source: dict[str, Any],
    series: dict[str, Any],
    *,
    as_of_date: str,
    fetched_at: str,
    timeout: int,
) -> list[dict[str, Any]]:
    series_id = str(series.get("series_id") or "")
    if not series_id:
        raise ValueError("Missing FRED series_id")
    base_url = str(source.get("base_url") or "https://fred.stlouisfed.org/graph/fredgraph.csv")
    response = requests.get(base_url, params={"id": series_id}, timeout=timeout)
    response.raise_for_status()
    rows: list[dict[str, Any]] = []
    for raw in csv.DictReader(response.text.splitlines()):
        observation_date = raw.get("observation_date")
        raw_value = raw.get(series_id)
        if not observation_date or raw_value in {None, "", "."}:
            continue
        try:
            value: float | None = float(raw_value)
        except ValueError:
            value = None
        if value is None:
            continue
        rows.append(
            {
                "source_family": source.get("source_family"),
                "provider": source.get("provider"),
                "dataset_id": series.get("dataset_id"),
                "series_id": series_id,
                "observation_date": observation_date,
                "as_of_date": as_of_date,
                "frequency": series.get("frequency") or source.get("default_frequency"),
                "value": value,
                "unit": series.get("unit"),
                "revision_status": "latest_provider_csv",
                "fetched_at": fetched_at,
                "route_type": source.get("route_type"),
                "api_route": f"{base_url}?id={series_id}",
                "facet_json": json.dumps(series.get("facet") or {}, ensure_ascii=False, sort_keys=True),
                "allowed_claim_types_json": json.dumps(source.get("allowed_claim_types") or [], ensure_ascii=False),
            }
        )
    if not rows:
        raise RuntimeError(f"FRED returned no usable observations for {series_id}")
    return rows


def build_series_evidence_row(
    source: dict[str, Any],
    series: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    as_of_date: str,
    fetched_at: str,
) -> dict[str, Any]:
    first = rows[0] if rows else {}
    latest = rows[-1] if rows else {}
    series_id = str(series.get("series_id") or "")
    return {
        "evidence_id": f"INDUSTRY::{source.get('source_family')}::{series_id}::{as_of_date}",
        "source_family": source.get("source_family"),
        "provider": source.get("provider"),
        "dataset_id": series.get("dataset_id"),
        "series_id": series_id,
        "as_of_date": as_of_date,
        "allowed_claim_types": source.get("allowed_claim_types") or [],
        "summary": (
            f"{series_id} has {len(rows)} normalized observations from {first.get('observation_date')} "
            f"to {latest.get('observation_date')}; latest value={latest.get('value')} {series.get('unit')}."
        ),
        "caveats": [
            "Industry data provides macro or sector context only.",
            "It must not overwrite company-filed financial facts.",
        ],
        "latest_observation_date": latest.get("observation_date"),
        "latest_value": latest.get("value"),
        "unit": series.get("unit"),
        "frequency": series.get("frequency") or source.get("default_frequency"),
        "fetched_at": fetched_at,
        "route_type": source.get("route_type"),
        "facet": series.get("facet") or {},
    }


def download_public_json_source(
    source: dict[str, Any],
    *,
    as_of_date: str,
    fetched_at: str,
    timeout: int,
) -> dict[str, Any]:
    endpoint = str(source.get("endpoint") or "")
    params = source.get("params") or {}
    dataset = source.get("dataset") or {}
    response = requests.get(endpoint, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    count = _json_payload_count(payload)
    return {
        "evidence_id": f"INDUSTRY::{source.get('source_family')}::{dataset.get('dataset_id')}::{as_of_date}",
        "source_family": source.get("source_family"),
        "provider": source.get("provider"),
        "dataset_id": dataset.get("dataset_id"),
        "series_id": None,
        "as_of_date": as_of_date,
        "allowed_claim_types": source.get("allowed_claim_types") or [],
        "summary": f"{source.get('provider')} public JSON route returned a usable payload with {count} top-level/event rows.",
        "caveats": [
            "Public JSON canary is normalized as evidence metadata, not company financial facts.",
            "Field-level normalization must be reviewed before using event-level claims.",
        ],
        "latest_observation_date": None,
        "latest_value": None,
        "unit": dataset.get("unit"),
        "frequency": source.get("default_frequency"),
        "fetched_at": fetched_at,
        "route_type": source.get("route_type"),
        "api_route": response.url,
        "facet": dataset.get("facet") or {},
        "payload_top_level_type": type(payload).__name__,
    }


def download_eia_v2_source(
    source: dict[str, Any],
    *,
    as_of_date: str,
    fetched_at: str,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint = str(source.get("endpoint") or "")
    if not endpoint:
        raise ValueError("Missing EIA endpoint")
    dataset = source.get("dataset") or {}
    params = dict(source.get("params") or {})
    env_var = str(source.get("api_key_env_var") or "EIA_API_KEY")
    api_key = os.environ.get(env_var, "").strip()
    if not api_key:
        raise RuntimeError(f"Missing {env_var}; EIA v2 routes require api_key")
    params["api_key"] = api_key

    response = requests.get(endpoint, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    response_block = payload.get("response") if isinstance(payload, dict) else {}
    data_rows = response_block.get("data") if isinstance(response_block, dict) else None
    if not isinstance(data_rows, list):
        raise RuntimeError("EIA response did not include response.data rows")

    observations: list[dict[str, Any]] = []
    skipped_non_numeric = 0
    for raw in data_rows:
        if not isinstance(raw, dict):
            continue
        period = str(raw.get("period") or "").strip()
        observation_date = _normalize_eia_period(period)
        if not period or not observation_date:
            skipped_non_numeric += 1
            continue
        extracted = _extract_eia_observations_from_row(
            source,
            dataset,
            params,
            raw,
            observation_date=observation_date,
            as_of_date=as_of_date,
            fetched_at=fetched_at,
            api_route=_redact_api_key_url(response.url),
        )
        if not extracted:
            skipped_non_numeric += 1
        observations.extend(extracted)
    if not observations:
        raise RuntimeError("EIA returned no usable numeric observations")

    observations.sort(key=lambda row: (str(row.get("observation_date") or ""), str(row.get("series_id") or "")))
    first = observations[0]
    latest_date = max(str(row.get("observation_date") or "") for row in observations)
    latest_rows = [row for row in observations if str(row.get("observation_date") or "") == latest_date]
    sample_series = sorted({str(row.get("series_id") or "") for row in latest_rows if row.get("series_id")})[:8]
    total = response_block.get("total") if isinstance(response_block, dict) else None
    evidence_row = {
        "evidence_id": f"INDUSTRY::{source.get('source_family')}::{dataset.get('dataset_id')}::{as_of_date}",
        "source_family": source.get("source_family"),
        "provider": source.get("provider"),
        "dataset_id": dataset.get("dataset_id"),
        "series_id": None,
        "as_of_date": as_of_date,
        "allowed_claim_types": source.get("allowed_claim_types") or [],
        "summary": (
            f"EIA {dataset.get('dataset_id')} returned {len(observations)} numeric observations "
            f"across {len({row.get('series_id') for row in observations})} series from "
            f"{first.get('observation_date')} to {latest_date}; sample latest series={sample_series}."
        ),
        "caveats": [
            "EIA data provides energy or power-market context only.",
            "It must not overwrite company-filed financial facts.",
            f"{skipped_non_numeric} non-numeric or unavailable EIA rows were skipped during normalization.",
        ],
        "latest_observation_date": latest_date,
        "latest_value": None,
        "unit": dataset.get("unit") or "mixed",
        "frequency": params.get("frequency") or source.get("default_frequency"),
        "fetched_at": fetched_at,
        "route_type": source.get("route_type"),
        "api_route": _redact_api_key_url(response.url),
        "facet": {
            **(dataset.get("facet") or {}),
            "response_total": total,
            "normalized_observation_count": len(observations),
            "skipped_non_numeric_count": skipped_non_numeric,
        },
        "payload_top_level_type": type(payload).__name__,
    }
    return observations, evidence_row


def _extract_eia_observations_from_row(
    source: dict[str, Any],
    dataset: dict[str, Any],
    params: dict[str, Any],
    raw: dict[str, Any],
    *,
    observation_date: str,
    as_of_date: str,
    fetched_at: str,
    api_route: str,
) -> list[dict[str, Any]]:
    source_family = source.get("source_family")
    provider = source.get("provider")
    dataset_id = dataset.get("dataset_id")
    frequency = params.get("frequency") or source.get("default_frequency")
    allowed_claim_types = json.dumps(source.get("allowed_claim_types") or [], ensure_ascii=False)
    if raw.get("msn") or raw.get("series") or raw.get("series_id"):
        series_id = str(raw.get("msn") or raw.get("series") or raw.get("series_id") or "").strip()
        value = _parse_provider_float(raw.get("value"))
        if not series_id or value is None:
            return []
        description = str(raw.get("seriesDescription") or raw.get("series-description") or "").strip()
        unit = str(raw.get("unit") or dataset.get("unit") or "").strip() or None
        facet = {
            **(dataset.get("facet") or {}),
            "msn": series_id,
            "series_description": description,
        }
        return [
            {
                "source_family": source_family,
                "provider": provider,
                "dataset_id": dataset_id,
                "series_id": series_id,
                "observation_date": observation_date,
                "as_of_date": as_of_date,
                "frequency": frequency,
                "value": value,
                "unit": unit,
                "revision_status": "latest_provider_json",
                "fetched_at": fetched_at,
                "route_type": source.get("route_type"),
                "api_route": api_route,
                "facet_json": json.dumps(facet, ensure_ascii=False, sort_keys=True),
                "allowed_claim_types_json": allowed_claim_types,
            }
        ]

    rows: list[dict[str, Any]] = []
    data_fields = _eia_data_fields(params, dataset)
    field_units = dataset.get("field_units") if isinstance(dataset.get("field_units"), dict) else {}
    field_descriptions = dataset.get("field_descriptions") if isinstance(dataset.get("field_descriptions"), dict) else {}
    for field in data_fields:
        value = _parse_provider_float(raw.get(field))
        if value is None:
            continue
        unit = str(raw.get(f"{field}-units") or field_units.get(field) or dataset.get("unit") or "").strip() or None
        series_id = _format_eia_series_id(dataset, raw, field)
        facet = {
            **(dataset.get("facet") or {}),
            "metric": field,
            "metric_description": field_descriptions.get(field) or field,
            "stateid": raw.get("stateid"),
            "state_description": raw.get("stateDescription"),
            "sectorid": raw.get("sectorid"),
            "sector_name": raw.get("sectorName"),
        }
        rows.append(
            {
                "source_family": source_family,
                "provider": provider,
                "dataset_id": dataset_id,
                "series_id": series_id,
                "observation_date": observation_date,
                "as_of_date": as_of_date,
                "frequency": frequency,
                "value": value,
                "unit": unit,
                "revision_status": "latest_provider_json",
                "fetched_at": fetched_at,
                "route_type": source.get("route_type"),
                "api_route": api_route,
                "facet_json": json.dumps(facet, ensure_ascii=False, sort_keys=True),
                "allowed_claim_types_json": allowed_claim_types,
            }
        )
    return rows


def _json_payload_count(payload: Any) -> int:
    if isinstance(payload, dict):
        for key in ("results", "dataset", "distribution"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return len(payload)
    if isinstance(payload, list):
        return len(payload)
    return 1


def _parse_provider_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"not available", "na", "n/a", "null", "none", "--", "."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _eia_data_fields(params: dict[str, Any], dataset: dict[str, Any]) -> list[str]:
    explicit = dataset.get("data_fields")
    if isinstance(explicit, list):
        return [str(item).strip() for item in explicit if str(item).strip()]
    fields: list[tuple[int, str]] = []
    for key, value in params.items():
        match = re.fullmatch(r"data\[(\d+)\]", str(key))
        if not match:
            continue
        fields.append((int(match.group(1)), str(value).strip()))
    return [field for _, field in sorted(fields) if field]


def _format_eia_series_id(dataset: dict[str, Any], raw: dict[str, Any], field: str) -> str:
    template = str(dataset.get("series_id_template") or "").strip()
    values = {
        "dataset_id": dataset.get("dataset_id") or "eia",
        "metric": field,
        "stateid": raw.get("stateid") or "NA",
        "sectorid": raw.get("sectorid") or "NA",
    }
    if template:
        try:
            return template.format(**values)
        except KeyError:
            pass
    return f"{values['dataset_id']}::{values['stateid']}::{values['sectorid']}::{field}"


def _normalize_eia_period(period: str) -> str | None:
    text = period.strip()
    if len(text) == 7 and text[4] == "-":
        return f"{text}-01"
    if len(text) == 4 and text.isdigit():
        return f"{text}-01-01"
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text
    return None


def _redact_api_key_url(url: str) -> str:
    return re.sub(r"([?&]api_key=)[^&]+", r"\1<redacted>", url)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_duckdb(path: Path, observations: list[dict[str, Any]], evidence_rows: list[dict[str, Any]]) -> dict[str, Any]:
    import duckdb

    if path.exists():
        path.unlink()
    wal_path = Path(str(path) + ".wal")
    if wal_path.exists():
        wal_path.unlink()
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            CREATE TABLE industry_observations (
                source_family VARCHAR,
                provider VARCHAR,
                dataset_id VARCHAR,
                series_id VARCHAR,
                observation_date DATE,
                as_of_date DATE,
                frequency VARCHAR,
                value DOUBLE,
                unit VARCHAR,
                revision_status VARCHAR,
                fetched_at TIMESTAMP,
                route_type VARCHAR,
                api_route VARCHAR,
                facet_json VARCHAR,
                allowed_claim_types_json VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE industry_evidence_rows (
                evidence_id VARCHAR,
                source_family VARCHAR,
                provider VARCHAR,
                dataset_id VARCHAR,
                series_id VARCHAR,
                as_of_date DATE,
                allowed_claim_types_json VARCHAR,
                summary VARCHAR,
                caveats_json VARCHAR,
                latest_observation_date DATE,
                latest_value DOUBLE,
                unit VARCHAR,
                frequency VARCHAR,
                fetched_at TIMESTAMP,
                route_type VARCHAR,
                api_route VARCHAR,
                facet_json VARCHAR,
                payload_top_level_type VARCHAR
            )
            """
        )
        if observations:
            con.executemany(
                """
                INSERT INTO industry_observations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [industry_observation_row(row) for row in observations],
            )
        if evidence_rows:
            con.executemany(
                """
                INSERT INTO industry_evidence_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [industry_evidence_db_row(row) for row in evidence_rows],
            )
        con.execute("CREATE INDEX idx_industry_observations_family_series ON industry_observations(source_family, series_id)")
        con.execute("CREATE INDEX idx_industry_observations_date ON industry_observations(observation_date)")
        con.execute("CREATE INDEX idx_industry_evidence_family ON industry_evidence_rows(source_family, provider)")
    finally:
        con.close()
    return {
        "path": str(path),
        "industry_observations": len(observations),
        "industry_evidence_rows": len(evidence_rows),
    }


def industry_observation_row(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("source_family"),
        row.get("provider"),
        row.get("dataset_id"),
        row.get("series_id"),
        row.get("observation_date"),
        row.get("as_of_date"),
        row.get("frequency"),
        row.get("value"),
        row.get("unit"),
        row.get("revision_status"),
        row.get("fetched_at"),
        row.get("route_type"),
        row.get("api_route"),
        row.get("facet_json"),
        row.get("allowed_claim_types_json"),
    )


def industry_evidence_db_row(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("evidence_id"),
        row.get("source_family"),
        row.get("provider"),
        row.get("dataset_id"),
        row.get("series_id"),
        row.get("as_of_date"),
        json.dumps(row.get("allowed_claim_types") or [], ensure_ascii=False),
        row.get("summary"),
        json.dumps(row.get("caveats") or [], ensure_ascii=False),
        row.get("latest_observation_date"),
        row.get("latest_value"),
        row.get("unit"),
        row.get("frequency"),
        row.get("fetched_at"),
        row.get("route_type"),
        row.get("api_route"),
        json.dumps(row.get("facet") or {}, ensure_ascii=False, sort_keys=True),
        row.get("payload_top_level_type"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
