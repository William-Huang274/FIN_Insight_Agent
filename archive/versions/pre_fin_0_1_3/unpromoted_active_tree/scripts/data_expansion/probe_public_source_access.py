from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from env_loader import load_env_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_access_probe_v0.1"
DEFAULT_USER_AGENT = "FinSight-Agent/0.1 public-source-probe contact@example.com"


ProbeParser = Callable[[bytes], dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded no-key public source access probes.")
    parser.add_argument("--access-plan", default="data/manifests/public_source_access_plan_v0_1.jsonl")
    parser.add_argument("--output", default="data/manifests/public_source_access_probe_v0_1.jsonl")
    parser.add_argument("--summary-output", default="data/manifests/public_source_access_probe_summary_v0_1.json")
    parser.add_argument("--source-id-filter", default="", help="Comma-separated source_id filter.")
    parser.add_argument("--phase-filter", default="P1", help="Comma-separated phase filter; default P1.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--allow-failures", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loaded_env_keys = load_env_file(_resolve(args.env_file))
    plan_path = _resolve(args.access_plan)
    rows = _read_jsonl(plan_path)
    source_filter = set(_split_csv(args.source_id_filter))
    phase_filter = set(_split_csv(args.phase_filter))
    candidates = [
        row
        for row in rows
        if row.get("live_probe_supported")
        and (not source_filter or row.get("source_id") in source_filter)
        and (not phase_filter or row.get("phase") in phase_filter)
    ]
    if args.limit > 0:
        candidates = candidates[: args.limit]
    probe_rows = [
        probe_source(row, timeout_s=args.timeout_s, skip_live=args.skip_live)
        for row in candidates
    ]
    output_path = _resolve(args.output)
    summary_path = _resolve(args.summary_output)
    _write_jsonl(output_path, probe_rows)
    summary = summarize_probe(
        plan_path=plan_path,
        output_path=output_path,
        summary_path=summary_path,
        candidates=candidates,
        probe_rows=probe_rows,
        skip_live=args.skip_live,
        loaded_env_keys=loaded_env_keys,
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary["failed_count"] and not args.allow_failures:
        return 2
    return 0


def probe_source(row: dict[str, Any], *, timeout_s: float, skip_live: bool = False) -> dict[str, Any]:
    source_id = str(row.get("source_id") or "")
    profile = PROBE_PROFILES.get(source_id)
    base = {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "provider": row.get("provider"),
        "phase": row.get("phase"),
        "auth_status": row.get("auth_status"),
        "claim_scope": row.get("claim_scope"),
        "boundary_notes": row.get("boundary_notes"),
        "probed_at": datetime.now(timezone.utc).isoformat(),
    }
    if not profile:
        return {**base, "probe_status": "skipped_no_probe_profile"}
    url = str(profile["url"])
    params = {str(key): str(value) for key, value in (profile.get("params") or {}).items()}
    redact_params = {str(param) for param in profile.get("redact_params") or []}
    env_var = str(profile.get("env_var") or "")
    env_param = str(profile.get("env_param") or "")
    env_location = str(profile.get("env_location") or "query")
    env_required = bool(profile.get("env_required", True))
    headers = {str(key): str(value) for key, value in (profile.get("headers") or {}).items()}
    json_body = profile.get("json_body")
    if isinstance(json_body, dict):
        json_body = dict(json_body)
    elif isinstance(json_body, list):
        json_body = [dict(item) if isinstance(item, dict) else item for item in json_body]
    env_metadata: dict[str, Any] = {}
    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        env_metadata = {"env_var": env_var, "env_present": bool(env_value)}
        if not env_value:
            if not env_required:
                env_value = ""
            else:
                return {
                    **base,
                    **env_metadata,
                    "probe_status": "missing_env",
                    "env_var": env_var,
                    "error": f"Missing required environment variable {env_var}",
                }
        if env_value:
            if not env_param:
                return {
                    **base,
                    **env_metadata,
                    "probe_status": "error",
                    "env_var": env_var,
                    "error": f"Probe profile for {source_id} is missing env_param",
                }
            if env_location == "header":
                headers[env_param] = env_value
            elif env_location == "json":
                if not isinstance(json_body, dict):
                    return {
                        **base,
                        **env_metadata,
                        "probe_status": "error",
                        "env_var": env_var,
                        "error": f"Probe profile for {source_id} is missing JSON body",
                    }
                json_body[env_param] = env_value
            else:
                params[env_param] = env_value
                redact_params.add(env_param)
    full_url = _full_url(url, params)
    logged_url = _full_url(url, _redacted_params(params, redact_params))
    if skip_live:
        return {**base, **env_metadata, "probe_status": "skipped_live", "probe_url": logged_url}
    try:
        payload, content_type, status_code = fetch_url(full_url, timeout_s=timeout_s, headers=headers, json_body=json_body)
        parsed = profile["parser"](payload)
        return {
            **base,
            **env_metadata,
            "probe_status": "pass",
            "probe_url": logged_url,
            "http_status": status_code,
            "content_type": content_type,
            **parsed,
        }
    except HTTPError as exc:
        return {
            **base,
            **env_metadata,
            "probe_status": "http_error",
            "probe_url": logged_url,
            "http_status": exc.code,
            "error": str(exc),
        }
    except (URLError, TimeoutError, ValueError, RuntimeError) as exc:
        return {
            **base,
            **env_metadata,
            "probe_status": "error",
            "probe_url": logged_url,
            "error": str(exc),
        }

def fetch_url(
    url: str,
    *,
    timeout_s: float,
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
) -> tuple[bytes, str, int]:
    request_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json,text/csv,*/*",
        **(headers or {}),
    }
    body_bytes = None
    if json_body is not None:
        body_bytes = json.dumps(json_body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body_bytes, headers=request_headers)
    with urlopen(request, timeout=timeout_s) as response:
        return response.read(), response.headers.get("content-type", ""), int(response.status)


def parse_fred_csv(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", "replace")
    rows = list(csv.DictReader(text.splitlines()))
    usable = [row for row in rows if any(value not in {"", "."} for key, value in row.items() if key != "observation_date")]
    latest = usable[-1] if usable else {}
    return {
        "normalized_row_count": len(usable),
        "sample_fields": list(rows[0].keys()) if rows else [],
        "latest_observation_date": latest.get("observation_date"),
        "latest_value": next((value for key, value in latest.items() if key != "observation_date"), None),
    }


def parse_json_list_payload(payload: bytes, *, list_key: str) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    rows = data.get(list_key) if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"JSON payload missing list key {list_key!r}")
    sample = rows[0] if rows and isinstance(rows[0], dict) else {}
    return {
        "normalized_row_count": len(rows),
        "sample_fields": sorted(sample.keys())[:20],
    }


def parse_fred_api_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    rows = data.get("observations") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("FRED API payload missing observations list")
    latest = rows[0] if rows and isinstance(rows[0], dict) else {}
    sample = latest if isinstance(latest, dict) else {}
    return {
        "normalized_row_count": len(rows),
        "sample_fields": sorted(sample.keys())[:20],
        "latest_observation_date": sample.get("date"),
        "latest_value": sample.get("value"),
    }


def parse_bea_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    results = ((data.get("BEAAPI") or {}).get("Results") or {}) if isinstance(data, dict) else {}
    rows = results.get("Data") if isinstance(results, dict) else None
    if not isinstance(rows, list):
        raise ValueError("BEA payload missing BEAAPI.Results.Data list")
    sample = rows[0] if rows and isinstance(rows[0], dict) else {}
    return {
        "normalized_row_count": len(rows),
        "sample_fields": sorted(sample.keys())[:20],
        "sample_table": sample.get("TableName") or sample.get("TableName".lower()),
        "sample_time_period": sample.get("TimePeriod"),
    }


def parse_census_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        raise ValueError("Census payload is not a tabular JSON array")
    return {
        "normalized_row_count": max(len(data) - 1, 0),
        "sample_fields": [str(item) for item in data[0]][:20],
    }


def parse_eia_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    response = data.get("response") if isinstance(data, dict) else None
    rows = response.get("data") if isinstance(response, dict) else None
    if not isinstance(rows, list):
        raise ValueError("EIA payload missing response.data list")
    sample = rows[0] if rows and isinstance(rows[0], dict) else {}
    return {
        "normalized_row_count": len(rows),
        "sample_fields": sorted(sample.keys())[:20],
        "sample_period": sample.get("period"),
    }


def parse_bls_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    if not isinstance(data, dict):
        raise ValueError("BLS payload is not an object")
    status = str(data.get("status") or "")
    if status and status.upper() != "REQUEST_SUCCEEDED":
        messages = data.get("message") if isinstance(data.get("message"), list) else []
        raise ValueError(f"BLS provider status {status}: {'; '.join(str(item) for item in messages)}")
    series = ((data.get("Results") or {}).get("series") or []) if isinstance(data.get("Results"), dict) else []
    if not isinstance(series, list):
        raise ValueError("BLS payload missing Results.series list")
    first = series[0] if series and isinstance(series[0], dict) else {}
    observations = first.get("data") if isinstance(first, dict) else []
    sample = observations[0] if observations and isinstance(observations[0], dict) else {}
    return {
        "normalized_row_count": len(observations) if isinstance(observations, list) else 0,
        "sample_fields": sorted(sample.keys())[:20],
        "provider_status": status,
        "sample_series_id": first.get("seriesID") if isinstance(first, dict) else None,
    }


def parse_dart_company_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    if not isinstance(data, dict):
        raise ValueError("DART payload is not an object")
    status = str(data.get("status") or "")
    message = str(data.get("message") or "")
    if status != "000":
        raise ValueError(f"DART provider status {status}: {message}")
    return {
        "normalized_row_count": 1,
        "sample_fields": sorted(data.keys())[:20],
        "provider_status": status,
        "provider_message": message,
        "sample_company_name": data.get("corp_name"),
        "sample_corp_code": data.get("corp_code"),
    }


def parse_openfigi_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    if not isinstance(data, list):
        raise ValueError("OpenFIGI payload is not a list")
    first = data[0] if data and isinstance(data[0], dict) else {}
    rows = first.get("data") if isinstance(first, dict) else []
    sample = rows[0] if rows and isinstance(rows[0], dict) else {}
    if first.get("warning") and not rows:
        raise ValueError(f"OpenFIGI warning: {first.get('warning')}")
    if first.get("error"):
        raise ValueError(f"OpenFIGI error: {first.get('error')}")
    return {
        "normalized_row_count": len(rows) if isinstance(rows, list) else 0,
        "sample_fields": sorted(sample.keys())[:20],
        "sample_ticker": sample.get("ticker"),
        "sample_name": sample.get("name"),
    }


def parse_fdic_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("FDIC payload missing data list")
    sample = rows[0].get("data", {}) if rows and isinstance(rows[0], dict) else {}
    return {
        "normalized_row_count": len(rows),
        "sample_fields": sorted(sample.keys())[:20],
    }


def parse_sec_submissions_payload(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload.decode("utf-8", "replace"))
    if not isinstance(data, dict):
        raise ValueError("SEC submissions payload is not an object")
    recent = ((data.get("filings") or {}).get("recent") or {}) if isinstance(data.get("filings"), dict) else {}
    forms = recent.get("form") if isinstance(recent, dict) else []
    return {
        "normalized_row_count": len(forms) if isinstance(forms, list) else 0,
        "sample_fields": sorted(data.keys())[:20],
        "sample_company_name": data.get("name"),
        "sample_cik": data.get("cik"),
    }


def summarize_probe(
    *,
    plan_path: Path,
    output_path: Path,
    summary_path: Path,
    candidates: list[dict[str, Any]],
    probe_rows: list[dict[str, Any]],
    skip_live: bool,
    loaded_env_keys: list[str],
) -> dict[str, Any]:
    passed = [row for row in probe_rows if row.get("probe_status") == "pass"]
    failed = [row for row in probe_rows if row.get("probe_status") not in {"pass", "skipped_live"}]
    return {
        "schema_version": "fin_agent_public_source_access_probe_summary_v0.1",
        "status": "skipped" if skip_live else ("pass" if not failed and passed else "partial" if passed else "fail"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {"access_plan": _repo_path(plan_path)},
        "loaded_env_key_names": sorted(loaded_env_keys),
        "outputs": {"probe_rows": _repo_path(output_path), "summary": _repo_path(summary_path)},
        "candidate_count": len(candidates),
        "probed_count": len(probe_rows),
        "passed_count": len(passed),
        "failed_count": len(failed),
        "passed_sources": [row["source_id"] for row in passed],
        "failed_sources": [{"source_id": row.get("source_id"), "status": row.get("probe_status"), "error": row.get("error")} for row in failed],
    }


def _json_parser(list_key: str) -> ProbeParser:
    return lambda payload: parse_json_list_payload(payload, list_key=list_key)


PROBE_PROFILES: dict[str, dict[str, Any]] = {
    "bea_data_api": {
        "url": "https://apps.bea.gov/api/data",
        "params": {
            "method": "GetData",
            "datasetname": "NIPA",
            "TableName": "T10101",
            "Frequency": "Q",
            "Year": "2025",
            "ResultFormat": "JSON",
        },
        "env_var": "BEA_API_KEY",
        "env_param": "UserID",
        "redact_params": ["UserID"],
        "parser": parse_bea_payload,
    },
    "bls_public_api": {
        "url": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "params": {},
        "json_body": {"seriesid": ["CUUR0000SA0"], "startyear": "2025", "endyear": "2026"},
        "env_var": "BLS_API_KEY",
        "env_param": "registrationkey",
        "env_location": "json",
        "parser": parse_bls_payload,
    },
    "census_data_api": {
        "url": "https://api.census.gov/data/2023/acs/acs5",
        "params": {"get": "NAME,B01001_001E", "for": "us:*"},
        "env_var": "CENSUS_API_KEY",
        "env_param": "key",
        "redact_params": ["key"],
        "parser": parse_census_payload,
    },
    "sec_edgar_apis": {
        "url": "https://data.sec.gov/submissions/CIK0000320193.json",
        "params": {},
        "parser": parse_sec_submissions_payload,
    },
    "eia_open_data": {
        "url": "https://api.eia.gov/v2/total-energy/data/",
        "params": {
            "frequency": "monthly",
            "data[0]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": "0",
            "length": "1",
        },
        "env_var": "EIA_API_KEY",
        "env_param": "api_key",
        "redact_params": ["api_key"],
        "parser": parse_eia_payload,
    },
    "fred_api": {
        "url": "https://api.stlouisfed.org/fred/series/observations",
        "params": {"series_id": "FEDFUNDS", "file_type": "json", "limit": "1", "sort_order": "desc"},
        "env_var": "FRED_API_KEY",
        "env_param": "api_key",
        "redact_params": ["api_key"],
        "parser": parse_fred_api_payload,
    },
    "fred_graph_csv": {
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv",
        "params": {"id": "FEDFUNDS"},
        "parser": parse_fred_csv,
    },
    "fdic_bankfind_api": {
        "url": "https://banks.data.fdic.gov/api/institutions",
        "params": {"filters": "ACTIVE:1", "fields": "NAME,CERT,ACTIVE", "limit": "1", "format": "json"},
        "parser": parse_fdic_payload,
    },
    "clinicaltrials_api": {
        "url": "https://clinicaltrials.gov/api/v2/studies",
        "params": {"query.term": "cancer", "pageSize": "1"},
        "parser": _json_parser("studies"),
    },
    "openfda_api": {
        "url": "https://api.fda.gov/drug/drugsfda.json",
        "params": {"limit": "1"},
        "parser": _json_parser("results"),
    },
    "openfigi_api": {
        "url": "https://api.openfigi.com/v3/mapping",
        "params": {},
        "json_body": [{"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}],
        "env_var": "OPENFIGI_API_KEY",
        "env_param": "X-OPENFIGI-APIKEY",
        "env_location": "header",
        "parser": parse_openfigi_payload,
    },
    "kr_dart_openapi": {
        "url": "https://opendart.fss.or.kr/api/company.json",
        "params": {"corp_code": "00126380"},
        "env_var": "DART_API_KEY",
        "env_param": "crtfc_key",
        "redact_params": ["crtfc_key"],
        "parser": parse_dart_company_payload,
    },
    "nhtsa_vpic_api": {
        "url": "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/Tesla",
        "params": {"format": "json"},
        "parser": _json_parser("Results"),
    },
    "gleif_api": {
        "url": "https://api.gleif.org/api/v1/lei-records",
        "params": {"page[size]": "1"},
        "parser": _json_parser("data"),
    },
    "openalex_api": {
        "url": "https://api.openalex.org/works",
        "params": {"search": "semiconductor", "per-page": "1"},
        "parser": _json_parser("results"),
    },
}


def _full_url(url: str, params: dict[str, str]) -> str:
    if not params:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


def _redacted_params(params: dict[str, str], redact_params: set[str]) -> dict[str, str]:
    return {key: ("REDACTED" if key in redact_params else value) for key, value in params.items()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
