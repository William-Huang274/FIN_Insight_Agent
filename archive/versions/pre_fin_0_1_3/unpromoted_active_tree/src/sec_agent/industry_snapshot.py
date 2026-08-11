from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "sec_agent_industry_snapshot_query_v0.1"
SOURCE_TIER = "industry_snapshot"


def query_industry_snapshot(
    *,
    source_families: list[str] | None = None,
    providers: list[str] | None = None,
    datasets: list[str] | None = None,
    series_ids: list[str] | None = None,
    facets: dict[str, Any] | None = None,
    start_date: str = "",
    end_date: str = "",
    latest_only: bool = False,
    industry_evidence_path: str | Path = "",
    industry_snapshot_db_path: str | Path = "",
    limit: int = 500,
) -> dict[str, Any]:
    """Query normalized industry evidence rows and optional DuckDB observations."""
    families = _string_list(source_families)
    providers_clean = _string_list(providers)
    datasets_clean = _string_list(datasets)
    series_clean = _string_list(series_ids)
    limit_value = max(1, min(int(limit or 500), 10_000))
    db_path = Path(industry_snapshot_db_path).resolve() if str(industry_snapshot_db_path or "").strip() else None
    evidence_path = Path(industry_evidence_path).resolve() if str(industry_evidence_path or "").strip() else None

    evidence_rows: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    errors: list[str] = []

    if db_path and db_path.exists():
        try:
            evidence_rows = _query_evidence_rows_from_duckdb(
                db_path,
                source_families=families,
                providers=providers_clean,
                datasets=datasets_clean,
                series_ids=series_clean,
                limit=limit_value,
            )
            observations = _query_observations_from_duckdb(
                db_path,
                source_families=families,
                providers=providers_clean,
                datasets=datasets_clean,
                series_ids=series_clean,
                facets=facets or {},
                start_date=start_date,
                end_date=end_date,
                latest_only=latest_only,
                limit=limit_value,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"duckdb_query_failed:{type(exc).__name__}:{exc}")
    elif db_path:
        errors.append(f"industry_snapshot_db_not_found:{db_path}")

    if not evidence_rows and evidence_path and evidence_path.exists():
        try:
            evidence_rows = _query_evidence_rows_from_jsonl(
                evidence_path,
                source_families=families,
                providers=providers_clean,
                datasets=datasets_clean,
                series_ids=series_clean,
                limit=limit_value,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"evidence_jsonl_query_failed:{type(exc).__name__}:{exc}")
    elif not evidence_rows and evidence_path:
        errors.append(f"industry_evidence_path_not_found:{evidence_path}")

    present_families = {str(row.get("source_family") or "") for row in [*evidence_rows, *observations] if row.get("source_family")}
    source_family_gaps = [
        {"source_family": family, "reason": "not_found_in_requested_snapshot"}
        for family in families
        if family not in present_families
    ]
    status = "error" if errors and not evidence_rows and not observations else "partial" if errors or source_family_gaps else "ok"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_tier": SOURCE_TIER,
        "industry_rows": evidence_rows,
        "observations": observations,
        "source_family_gaps": source_family_gaps,
        "errors": errors,
        "artifact_refs": _artifact_refs(db_path, evidence_path),
        "summary": {
            "evidence_row_count": len(evidence_rows),
            "observation_count": len(observations),
            "source_families": sorted(present_families),
            "latest_only": bool(latest_only),
        },
    }


def _query_evidence_rows_from_duckdb(
    db_path: Path,
    *,
    source_families: list[str],
    providers: list[str],
    datasets: list[str],
    series_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    import duckdb

    where: list[str] = []
    params: list[Any] = []
    _add_in_filter(where, params, "source_family", source_families)
    _add_in_filter(where, params, "provider", providers)
    _add_in_filter(where, params, "dataset_id", datasets)
    _add_in_filter(where, params, "series_id", series_ids)
    sql = "SELECT * FROM industry_evidence_rows"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY source_family, provider, dataset_id, series_id LIMIT ?"
    params.append(limit)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        result = con.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        con.close()
    return [_normalize_evidence_row(row) for row in rows]


def _query_observations_from_duckdb(
    db_path: Path,
    *,
    source_families: list[str],
    providers: list[str],
    datasets: list[str],
    series_ids: list[str],
    facets: dict[str, Any],
    start_date: str,
    end_date: str,
    latest_only: bool,
    limit: int,
) -> list[dict[str, Any]]:
    import duckdb

    where: list[str] = []
    params: list[Any] = []
    _add_in_filter(where, params, "source_family", source_families)
    _add_in_filter(where, params, "provider", providers)
    _add_in_filter(where, params, "dataset_id", datasets)
    _add_in_filter(where, params, "series_id", series_ids)
    if start_date:
        where.append("observation_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("observation_date <= ?")
        params.append(end_date)
    sql = "SELECT * FROM industry_observations"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY source_family, series_id, observation_date DESC LIMIT ?"
    fetch_limit = limit * 10 if facets else limit
    params.append(max(limit, fetch_limit))
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        result = con.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        raw_rows = [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        con.close()
    rows = [_normalize_observation_row(row) for row in raw_rows]
    if facets:
        rows = [row for row in rows if _facet_matches(row.get("facet") or {}, facets)]
    if latest_only:
        rows = _latest_observation_per_series(rows)
    return rows[:limit]


def _query_evidence_rows_from_jsonl(
    path: Path,
    *,
    source_families: list[str],
    providers: list[str],
    datasets: list[str],
    series_ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_set = set(source_families)
    provider_set = set(providers)
    dataset_set = set(datasets)
    series_set = set(series_ids)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if family_set and str(row.get("source_family") or "") not in family_set:
                continue
            if provider_set and str(row.get("provider") or "") not in provider_set:
                continue
            if dataset_set and str(row.get("dataset_id") or "") not in dataset_set:
                continue
            if series_set and str(row.get("series_id") or "") not in series_set:
                continue
            rows.append(_normalize_jsonl_evidence_row(row))
            if len(rows) >= limit:
                break
    return rows


def _normalize_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_tier": SOURCE_TIER,
        "evidence_id": str(row.get("evidence_id") or ""),
        "source_family": str(row.get("source_family") or ""),
        "provider": str(row.get("provider") or ""),
        "dataset_id": str(row.get("dataset_id") or ""),
        "series_id": str(row.get("series_id") or ""),
        "as_of_date": _date_text(row.get("as_of_date")),
        "allowed_claim_types": _json_list(row.get("allowed_claim_types_json")),
        "summary": str(row.get("summary") or ""),
        "caveats": _json_list(row.get("caveats_json")),
        "latest_observation_date": _date_text(row.get("latest_observation_date")),
        "latest_value": row.get("latest_value"),
        "unit": str(row.get("unit") or ""),
        "frequency": str(row.get("frequency") or ""),
        "fetched_at": _date_text(row.get("fetched_at")),
        "route_type": str(row.get("route_type") or ""),
        "api_route": str(row.get("api_route") or ""),
        "facet": _json_dict(row.get("facet_json")),
    }


def _normalize_jsonl_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    clean = dict(row)
    clean["source_tier"] = SOURCE_TIER
    clean["allowed_claim_types"] = list(row.get("allowed_claim_types") or [])
    clean["caveats"] = list(row.get("caveats") or [])
    return clean


def _normalize_observation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_tier": SOURCE_TIER,
        "source_family": str(row.get("source_family") or ""),
        "provider": str(row.get("provider") or ""),
        "dataset_id": str(row.get("dataset_id") or ""),
        "series_id": str(row.get("series_id") or ""),
        "observation_date": _date_text(row.get("observation_date")),
        "as_of_date": _date_text(row.get("as_of_date")),
        "frequency": str(row.get("frequency") or ""),
        "value": row.get("value"),
        "unit": str(row.get("unit") or ""),
        "revision_status": str(row.get("revision_status") or ""),
        "fetched_at": _date_text(row.get("fetched_at")),
        "route_type": str(row.get("route_type") or ""),
        "api_route": str(row.get("api_route") or ""),
        "facet": _json_dict(row.get("facet_json")),
        "allowed_claim_types": _json_list(row.get("allowed_claim_types_json")),
    }


def _latest_observation_per_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("source_family") or ""),
            str(row.get("dataset_id") or ""),
            str(row.get("series_id") or ""),
        )
        current = latest.get(key)
        if current is None or str(row.get("observation_date") or "") > str(current.get("observation_date") or ""):
            latest[key] = row
    return sorted(latest.values(), key=lambda item: (item.get("source_family") or "", item.get("series_id") or ""))


def _facet_matches(row_facet: dict[str, Any], requested: dict[str, Any]) -> bool:
    for key, value in requested.items():
        row_value = row_facet.get(str(key))
        if isinstance(value, list):
            allowed = {str(item) for item in value}
            if str(row_value) not in allowed:
                return False
        elif str(row_value) != str(value):
            return False
    return True


def _add_in_filter(where: list[str], params: list[Any], column: str, values: list[str]) -> None:
    clean = [str(value) for value in values if str(value)]
    if not clean:
        return
    placeholders = ", ".join("?" for _ in clean)
    where.append(f"{column} IN ({placeholders})")
    params.extend(clean)


def _artifact_refs(db_path: Path | None, evidence_path: Path | None) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if db_path:
        refs.append({"artifact_id": "industry_snapshot_db", "path": str(db_path), "digest": "", "row_count": 0})
    if evidence_path:
        refs.append({"artifact_id": "industry_evidence_rows", "path": str(evidence_path), "digest": "", "row_count": 0})
    return refs


def _string_list(value: list[str] | None) -> list[str]:
    out: list[str] = []
    for item in value or []:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _json_list(value: Any) -> list[Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
