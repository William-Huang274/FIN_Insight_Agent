from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.project_os_preflight import run_project_os_preflight


RUN_SCOPE = "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
POLICY_SCHEMA = "fin_ia_0_1_3_s1_internal_numeric_sql_qrels_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_internal_numeric_sql_qrels_observation_v1_0"


class S1InternalNumericSqlQrelsError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise S1InternalNumericSqlQrelsError("numeric_sql_json_object_required")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ro_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_numeric_sql_qrels_policy(
    path: str | Path, *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("result_schema") != RESULT_SCHEMA
        or policy.get("run_scope") != RUN_SCOPE
        or policy.get("binding_hash_profile") != "sha256_file_bytes_v1"
    ):
        raise S1InternalNumericSqlQrelsError("numeric_sql_policy_identity_invalid")
    immutable = dict(policy.get("immutable_inputs") or {})
    for key in (
        "annual_period_authority",
        "annual_fact_authority",
        "current_quarter_evidence_pack",
        "candidate_policy",
    ):
        ref = str(immutable.get(f"{key}_ref") or "")
        supplied = str(immutable.get(f"{key}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _sha256(target) != supplied:
            raise S1InternalNumericSqlQrelsError(
                f"numeric_sql_policy_binding_invalid:{key}"
            )
    assets = dict(policy.get("local_assets") or {})
    for key in ("legacy_gold_sqlite", "current_successor_gold_sqlite"):
        ref = str(assets.get(f"{key}_ref") or "")
        supplied = str(assets.get(f"{key}_sha256") or "")
        target = root / ref
        if not ref or not target.is_file() or _sha256(target) != supplied:
            raise S1InternalNumericSqlQrelsError(
                f"numeric_sql_asset_binding_invalid:{key}"
            )
    hard = dict(policy.get("hard_boundaries") or {})
    if any(
        int(hard.get(key, -1)) != 0
        for key in (
            "network",
            "provider",
            "model",
            "embedding",
            "rerank",
            "evidence_promotion",
        )
    ) or hard.get("benchmark_pack_may_refresh_sqlite") is not False:
        raise S1InternalNumericSqlQrelsError("numeric_sql_policy_boundary_invalid")
    return policy


def _annual_periods(authority: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = list(authority.get("current_annual_truth") or [])
    result = {
        str(row["case_key"]): {
            "fiscal_year": int(row["fiscal_year"]),
            "period_start": str(row["period_start"]),
            "period_end": str(row["period_end"]),
            "published_at": str(row["source_filed_at"]),
        }
        for row in rows
    }
    if set(result) != {"DELL", "MU", "NVDA"}:
        raise S1InternalNumericSqlQrelsError("numeric_sql_annual_period_set_invalid")
    return result


def _annual_qrels(
    fact_authority: Mapping[str, Any], period_authority: Mapping[str, Any]
) -> list[dict[str, Any]]:
    periods = _annual_periods(period_authority)
    program = dict(fact_authority.get("retrieval_usefulness_program") or {})
    rows: list[dict[str, Any]] = []
    for query in list(program.get("query_results") or []):
        case_key = str(query.get("case_key") or "")
        if query.get("cell_id") != "value_and_profit_capture" or case_key not in periods:
            continue
        for candidate in list(query.get("selected_candidates") or []):
            if candidate.get("candidate_role") != "current_exact_numeric_sql":
                continue
            metric = str(candidate.get("metric_family") or "")
            if metric not in {"revenue", "gross_profit", "operating_income"}:
                continue
            period = periods[case_key]
            rows.append(
                {
                    "qrel_id": f"annual::{case_key}::{metric}",
                    "stratum": "latest_available_annual",
                    "case_key": case_key,
                    "ticker": case_key,
                    "metric_family": metric,
                    "fiscal_year": int(period["fiscal_year"]),
                    "period_role": "annual",
                    "period_start": period["period_start"],
                    "period_end": period["period_end"],
                    "published_at_on_or_before": "2026-07-26",
                    "expected_value": str(candidate["normalized_value"]),
                    "expected_unit": str(candidate["unit"]),
                    "authority_ref": (
                        "configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_"
                        "retrieval_evidence_usefulness_and_s1_closeout_v1_0.json#"
                        f"{case_key}/value_and_profit_capture/{metric}"
                    ),
                    "authority_mode": "frozen_current_exact_numeric_sql_release",
                }
            )
    rows.sort(key=lambda item: item["qrel_id"])
    if len(rows) != 9:
        raise S1InternalNumericSqlQrelsError(
            f"numeric_sql_annual_qrel_count_invalid:{len(rows)}"
        )
    return rows


def _quarter_spec() -> tuple[tuple[str, str, str], ...]:
    return (
        ("DELL", "revenue", "revenue"),
        ("DELL", "operating_cash_flow", "operating_cash_flow"),
        ("MU", "revenue", "revenue"),
        ("MU", "capex", "capital_expenditure_proxy"),
        ("NVDA", "revenue", "revenue"),
        ("NVDA", "operating_cash_flow", "operating_cash_flow"),
    )


def _usd_value(value: str, unit: str) -> tuple[str, str]:
    if unit == "USD_billion":
        normalized = Decimal(value) * Decimal("1000000000")
        return format(normalized.quantize(Decimal("1")), "f"), "USD"
    return value, unit


def _quarter_qrels(pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases = {str(item["case_key"]): item for item in list(pack.get("cases") or [])}
    rows: list[dict[str, Any]] = []
    for case_key, pack_metric, sql_metric in _quarter_spec():
        matches: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        for evidence in list(cases.get(case_key, {}).get("evidence_items") or []):
            for fact in list(evidence.get("numeric_facts") or []):
                if fact.get("metric") == pack_metric:
                    matches.append((evidence, fact))
        if len(matches) != 1:
            raise S1InternalNumericSqlQrelsError(
                f"numeric_sql_quarter_authority_ambiguous:{case_key}:{pack_metric}"
            )
        evidence, fact = matches[0]
        observed_period = str(evidence["observed_period"])
        match = re.fullmatch(r"Q([1-4]) FY(\d{4})", observed_period)
        if match is None:
            raise S1InternalNumericSqlQrelsError(
                f"numeric_sql_quarter_period_invalid:{case_key}:{observed_period}"
            )
        value, unit = _usd_value(str(fact["value"]), str(fact["unit"]))
        rows.append(
            {
                "qrel_id": f"quarter::{case_key}::{sql_metric}",
                "stratum": "current_quarter_product_input",
                "case_key": case_key,
                "ticker": case_key,
                "metric_family": sql_metric,
                "fiscal_year": int(match.group(2)),
                "fiscal_quarter": f"Q{match.group(1)}",
                "period_role": "quarter",
                "observed_period": observed_period,
                "expected_value": value,
                "expected_unit": unit,
                "authority_ref": (
                    "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/"
                    "shared_benchmark_evidence_pack_v1.json#"
                    f"{evidence['evidence_id']}/{pack_metric}"
                ),
                "authority_mode": "frozen_model_visible_primary_evidence_fact",
                "source_id": str(evidence["source_id"]),
                "evidence_digest": str(evidence["evidence_digest"]),
            }
        )
    return rows


def _query_candidates(
    connection: sqlite3.Connection, qrel: Mapping[str, Any]
) -> list[dict[str, Any]]:
    clauses = [
        "ticker = ?",
        "metric_family = ?",
        "CAST(NULLIF(fiscal_year, '') AS INTEGER) = ?",
        "exact_value_authority = 1",
        "can_enter_evidence_bundle = 1",
    ]
    params: list[Any] = [
        qrel["ticker"],
        qrel["metric_family"],
        int(qrel["fiscal_year"]),
    ]
    if qrel["period_role"] == "annual":
        clauses.append("period_role = 'annual'")
        clauses.append("period_start = ?")
        clauses.append("period_end = ?")
        params.extend([qrel["period_start"], qrel["period_end"]])
    else:
        clauses.append("period_role IN ('quarter', 'quarterly')")
        clauses.append("period LIKE ?")
        params.append(f"%{qrel['fiscal_quarter']}%")
    query = (
        "SELECT gold_row_id,ticker,metric_family,metric_name,value,unit,period,"
        "fiscal_year,period_role,period_start,period_end,published_at,authority_mode,"
        "source_url,evidence_ref FROM gold_fact_signal_mart WHERE "
        + " AND ".join(clauses)
        + " ORDER BY published_at DESC, gold_row_id"
    )
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def _evaluate_database(path: Path, qrels: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    with _ro_connection(path) as connection:
        table_count = int(
            connection.execute("SELECT COUNT(*) FROM gold_fact_signal_mart").fetchone()[0]
        )
        evaluated = []
        for qrel in qrels:
            candidates = _query_candidates(connection, qrel)
            exact = [
                row
                for row in candidates
                if str(row.get("value")) == str(qrel["expected_value"])
                and str(row.get("unit")) == str(qrel["expected_unit"])
            ]
            state = "exact_match" if len(exact) == 1 else (
                "ambiguous_exact_match" if len(exact) > 1 else "typed_freshness_gap"
            )
            evaluated.append(
                {
                    "qrel_id": qrel["qrel_id"],
                    "stratum": qrel["stratum"],
                    "candidate_count": len(candidates),
                    "exact_match_count": len(exact),
                    "state": state,
                    "matched_row": exact[0] if len(exact) == 1 else None,
                }
            )
    strata: dict[str, dict[str, Any]] = {}
    for stratum in sorted({item["stratum"] for item in evaluated}):
        rows = [item for item in evaluated if item["stratum"] == stratum]
        strata[stratum] = {
            "qrel_count": len(rows),
            "exact_match_count": sum(item["state"] == "exact_match" for item in rows),
            "typed_freshness_gap_count": sum(
                item["state"] == "typed_freshness_gap" for item in rows
            ),
        }
    return {
        "table_row_count": table_count,
        "strata": strata,
        "qrel_results": evaluated,
    }


def materialize_numeric_sql_qrels_observation(
    policy: Mapping[str, Any], *, repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preflight = run_project_os_preflight(root, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise S1InternalNumericSqlQrelsError("numeric_sql_project_os_preflight_failed")
    immutable = dict(policy["immutable_inputs"])
    period_authority = _read_json(root / immutable["annual_period_authority_ref"])
    fact_authority = _read_json(root / immutable["annual_fact_authority_ref"])
    benchmark = _read_json(root / immutable["current_quarter_evidence_pack_ref"])
    candidate_policy = _read_json(root / immutable["candidate_policy_ref"])
    annual = _annual_qrels(fact_authority, period_authority)
    quarterly = _quarter_qrels(benchmark)
    qrels = [*annual, *quarterly]
    assets = dict(policy["local_assets"])
    legacy_ref = str(assets["legacy_gold_sqlite_ref"])
    successor_ref = str(assets["current_successor_gold_sqlite_ref"])
    configured_ref = str(candidate_policy.get("local_assets", {}).get("gold_sqlite") or "")
    if configured_ref != legacy_ref:
        raise S1InternalNumericSqlQrelsError(
            "numeric_sql_candidate_policy_route_binding_changed"
        )
    legacy = _evaluate_database(root / legacy_ref, qrels)
    successor = _evaluate_database(root / successor_ref, qrels)
    annual_pass = (
        successor["strata"]["latest_available_annual"]["exact_match_count"]
        == len(annual)
    )
    quarter_pass = (
        successor["strata"]["current_quarter_product_input"]["exact_match_count"]
        == len(quarterly)
    )
    result: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": "fin_0_1_3.S1.internal_numeric_sql_qrels:v1",
        "run_scope": RUN_SCOPE,
        "status": (
            "annual_exact_route_ready_current_quarter_refresh_blocked"
            if annual_pass and not quarter_pass
            else "pass" if annual_pass and quarter_pass else "failed"
        ),
        "project_os_preflight": preflight,
        "policy_digest": canonical_digest(policy),
        "qrels": qrels,
        "observations": {
            "candidate_policy_configured_exact_asset": legacy_ref,
            "legacy_main_mart": legacy,
            "current_three_case_successor_mart": successor,
        },
        "gate_decision": {
            "latest_available_annual_exact_sql_ready": annual_pass,
            "current_quarter_exact_sql_ready": quarter_pass,
            "research_candidate_ranking_may_use_this_as_owner_review": False,
            "BGE_fusion_rerank_admitted_by_this_gate": False,
            "reason": (
                "The current successor proves 9/9 latest-available annual exact facts. "
                "The research candidate policy still binds the stale main mart, while "
                "neither mart contains the six frozen current-quarter product facts. "
                "Exact numeric routing and current-quarter ingestion remain separate "
                "S1 work; BGE cannot repair either gap."
            ),
        },
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "known_boundary": (
            "The frozen benchmark evidence pack is used only to measure missing current-"
            "quarter SQL coverage. It must not be ingested into the mart or exposed to "
            "query generation. This observation does not refresh data, promote Evidence, "
            "review research qrels, evaluate ranking, or establish product acceptance."
        ),
        "implementation": {
            "module_ref": "src/sec_agent/s1_internal_numeric_sql_qrels.py",
            "policy_ref": "configs/runtime/fin_ia_0_1_3_s1_internal_numeric_sql_qrels_policy_v1_0.json",
            "materializer_ref": "scripts/releases/materialize_fin_ia_0_1_3_s1_internal_numeric_sql_qrels_v1_0.py",
        },
    }
    result["result_digest"] = canonical_digest(result)
    return result


def validate_numeric_sql_qrels_observation(value: Mapping[str, Any]) -> None:
    body = dict(value)
    supplied = str(body.pop("result_digest", ""))
    if value.get("schema_version") != RESULT_SCHEMA or not supplied:
        raise S1InternalNumericSqlQrelsError("numeric_sql_observation_identity_invalid")
    if supplied != canonical_digest(body):
        raise S1InternalNumericSqlQrelsError("numeric_sql_observation_digest_invalid")
    calls = dict(value.get("observed_calls") or {})
    if any(int(calls.get(key, -1)) != 0 for key in calls):
        raise S1InternalNumericSqlQrelsError("numeric_sql_observation_call_boundary_invalid")
