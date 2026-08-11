from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROFITABILITY_FAMILIES = {"operating_income", "gross_margin", "operating_margin"}
PROXY_FAMILY_MARKERS = ("proxy",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic SEC benchmark Judgment Plan seeds from reviewed ledger rows."
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--cases-path", default="eval/sec_cases/test_cases_v1.jsonl")
    parser.add_argument(
        "--ledger-path",
        default="reports/exact_value_ledgers/sec_benchmark_v1_reviewed_exact_value_ledger.json",
    )
    parser.add_argument(
        "--rubric-path",
        default="eval/sec_cases/abstract_judgment_rubric_v0_1.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/evidence_packs/sec_benchmark_v1_reviewed_judgment_plans_seed.json",
    )
    parser.add_argument("--report-path", default="")
    parser.add_argument(
        "--trace-run-dir",
        action="append",
        default=[],
        help="Optional context trace run directory; when provided, qualitative trace evidence may support plan drivers.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = {str(row.get("case_id") or ""): row for row in _read_jsonl(_resolve(args.cases_path))}
    ledger = _read_json(_resolve(args.ledger_path))
    rubric = _read_json(_resolve(args.rubric_path)) if _resolve(args.rubric_path).exists() else {}
    trace_rows_by_case = _load_trace_context_rows(args.trace_run_dir)
    ledger_rows_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger.get("rows") or []:
        ledger_rows_by_case[str(row.get("case_id") or "")].append(row)

    case_ids = args.case_id or list(ledger_rows_by_case)
    plans = []
    skipped = []
    for case_id in case_ids:
        case = cases.get(case_id)
        rows = ledger_rows_by_case.get(case_id, [])
        if not case:
            skipped.append({"case_id": case_id, "reason": "case_not_found"})
            continue
        if not rows:
            skipped.append({"case_id": case_id, "reason": "no_ledger_rows"})
            continue
        plans.append(
            _build_plan(
                case,
                rows,
                (rubric.get("cases") or {}).get(case_id) or {},
                trace_rows_by_case.get(case_id, []),
            )
        )

    payload = {
        "schema_version": "sec_benchmark_judgment_plan_seed_v0.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generation_mode": (
            "deterministic_seed_from_reviewed_ledger_and_trace"
            if trace_rows_by_case
            else "deterministic_seed_from_reviewed_ledger"
        ),
        "source_paths": {
            "cases_path": str(_resolve(args.cases_path).resolve()),
            "ledger_path": str(_resolve(args.ledger_path).resolve()),
            "rubric_path": str(_resolve(args.rubric_path).resolve()),
            "trace_run_dirs": [str(_resolve(path).resolve()) for path in args.trace_run_dir],
        },
        "intended_use": (
            "Validated intermediate plan for final synthesis. This seed is deterministic and can be "
            "replaced by a model-generated plan only if the same validator passes."
        ),
        "plans": plans,
        "skipped": skipped,
    }
    output_path = _resolve(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = _build_report(payload)
    if args.report_path:
        report_path = _resolve(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "report_path": args.report_path,
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _build_plan(
    case: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    case_rubric: dict[str, Any],
    trace_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    years = sorted({int(year) for year in case.get("years") or [] if _is_int_like(year)})
    required_groups_by_company = _required_metric_groups_by_company(case)
    rows_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger_rows:
        rows_by_ticker[str(row.get("ticker") or "")].append(row)

    trace_rows = trace_rows or []
    custom_drivers = _task_aware_trace_drivers(case, ledger_rows, trace_rows)
    drivers = []
    downgrade_reasons = []
    if custom_drivers:
        drivers.extend(custom_drivers)
        for driver in custom_drivers:
            downgrade_reasons.extend(driver["downgrade_reasons"])
    else:
        for ticker in sorted(rows_by_ticker):
            driver = _build_driver(
                ticker=ticker,
                rows=rows_by_ticker[ticker],
                case=case,
                case_years=years,
                required_groups=required_groups_by_company.get(ticker, []),
            )
            if trace_rows:
                _enrich_driver_with_trace(driver, trace_rows, tickers=[ticker])
            drivers.append(driver)
            downgrade_reasons.extend(driver["downgrade_reasons"])

    drivers.sort(key=lambda item: (-item["support_score"], item["covered_companies"][0]))
    for rank, driver in enumerate(drivers, start=1):
        driver["rank"] = rank
        driver.pop("support_score", None)
        driver.pop("downgrade_reasons", None)

    forbidden_summaries = [
        str(item.get("description") or item.get("id") or "")
        for item in case_rubric.get("forbidden_claims") or []
        if isinstance(item, dict)
    ]
    do_not_overstate = [str(item) for item in case.get("hallucination_traps") or []]
    do_not_overstate.extend(item for item in forbidden_summaries if item)
    do_not_overstate.extend(_case_disallowed_claim_summaries(case))
    do_not_overstate.extend(_generic_overstatement_guards(case, drivers))

    unique_downgrades = _unique_strings(downgrade_reasons)
    main_strength = "weak" if any(driver.get("conclusion_strength") == "weak" for driver in drivers) else "medium"
    if not unique_downgrades and all(driver.get("conclusion_strength") == "strong" for driver in drivers):
        main_strength = "strong"
    if str(case.get("task_type") or "").startswith("peer_comparison"):
        main_strength = "medium" if main_strength == "strong" else main_strength

    return {
        "case_id": case_id,
        "mode": "pipeline_context",
        "case_task_type": case.get("task_type"),
        "companies": case.get("companies") or [],
        "years": years,
        "main_judgment": {
            "claim": _main_claim(case, drivers, bool(unique_downgrades)),
            "strength": main_strength,
            "claim_type": _claim_type(case, bool(unique_downgrades)),
        },
        "drivers": drivers,
        "must_downgrade_because": unique_downgrades,
        "do_not_overstate": _unique_strings(do_not_overstate),
        "plan_validator_expectations": {
            "support_ids_must_exist": True,
            "proxy_metrics_require_caveat": True,
            "missing_profitability_or_visibility_evidence_requires_downgrade": True,
            "forbidden_claims_are_hard_failures": True,
        },
    }


def _build_driver(
    *,
    ticker: str,
    rows: list[dict[str, Any]],
    case: dict[str, Any],
    case_years: list[int],
    required_groups: list[set[str]],
) -> dict[str, Any]:
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            int(row.get("fiscal_year") or 0),
            str(row.get("metric_family") or ""),
            str(row.get("metric_role") or ""),
        ),
    )
    metric_ids = [str(row.get("metric_id") or "") for row in sorted_rows if row.get("metric_id")]
    evidence_ids = _ledger_support_ids(sorted_rows)
    families = sorted({str(row.get("metric_family") or "") for row in sorted_rows if row.get("metric_family")})
    years = sorted({int(row.get("fiscal_year")) for row in sorted_rows if _is_int_like(row.get("fiscal_year"))})
    missing_required_groups = [
        sorted(group)
        for group in required_groups
        if group and not (set(families) & group)
    ]
    has_proxy = any(_is_proxy_family(family) for family in families)
    has_profitability = bool(set(families) & PROFITABILITY_FAMILIES)
    prompt_text = " ".join(
        str(part)
        for part in [
            case.get("prompt"),
            case.get("task_type"),
            " ".join(str(item) for item in case.get("gold_points") or []),
        ]
    ).lower()
    needs_profitability = any(token in prompt_text for token in ["operating income", "margin", "profitability", "毛利", "利润"])

    caveats: list[str] = []
    downgrades: list[str] = []
    if has_proxy:
        caveats.append(f"{ticker} includes proxy metrics; treat them as disclosure proxies, not directly comparable segment metrics.")
        downgrades.append(f"{ticker}: proxy metric family requires caveat and prevents a strong conclusion.")
    if missing_required_groups:
        caveats.append(f"{ticker} is missing at least one required metric-family group: {missing_required_groups}.")
        downgrades.append(f"{ticker}: missing required metric-family coverage.")
    if needs_profitability and not has_profitability:
        caveats.append(f"{ticker} lacks operating-income or margin evidence in this ledger; profitability visibility must be downgraded.")
        downgrades.append(f"{ticker}: missing profitability metric for a profitability or margin prompt.")
    if "subscription" in prompt_text and "services_revenue" in families and "subscription_revenue" not in families:
        caveats.append(f"{ticker} services revenue is not the same as pure subscription revenue.")
        downgrades.append(f"{ticker}: services revenue cannot be overstated as subscription revenue.")
    needs_contract_visibility = any(
        token in prompt_text
        for token in ["recurring", "subscription", "contract", "visibility quality", "visibility and"]
    )
    if needs_contract_visibility and not any("subscription" in family or "rpo" in family or "arr" in family for family in families):
        caveats.append(f"{ticker} has limited contract-visibility evidence in the current ledger.")
        downgrades.append(f"{ticker}: visibility evidence is limited.")

    role = _driver_role(families, needs_profitability)
    strength = _driver_strength(
        has_proxy=has_proxy,
        missing_required_groups=missing_required_groups,
        has_profitability=has_profitability,
        needs_profitability=needs_profitability,
        case_years=case_years,
        years=years,
        families=families,
    )
    if downgrades and strength == "strong":
        strength = "medium"
    claim = _driver_claim(ticker, families, years, strength)
    why = _driver_why(ticker, families, years, strength)
    support_score = _support_score(
        years=years,
        families=families,
        has_proxy=has_proxy,
        missing_required_groups=missing_required_groups,
        has_profitability=has_profitability,
        needs_profitability=needs_profitability,
    )
    return {
        "rank": 0,
        "claim": claim,
        "claim_role": role,
        "why_ranked_here": why,
        "supporting_metric_ids": metric_ids,
        "supporting_evidence_ids": evidence_ids,
        "covered_companies": [ticker],
        "covered_years": years,
        "metric_families": families,
        "conclusion_strength": strength,
        "caveats": _unique_strings(caveats),
        "support_score": support_score,
        "downgrade_reasons": _unique_strings(downgrades),
    }


def _task_aware_trace_drivers(
    case: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    task_type = str(case.get("task_type") or "")
    if task_type == "peer_comparison_ads_ai_infra_growth_quality":
        return _ads_ai_infra_trace_drivers(case, ledger_rows, trace_rows)
    if task_type == "peer_comparison_semiconductor_durability":
        return _semiconductor_trace_drivers(case, ledger_rows, trace_rows)
    return []


def _ads_ai_infra_trace_drivers(
    case: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    core_rows = _rows_matching_families(ledger_rows, {"advertising_revenue", "operating_income"})
    capex_rows = _rows_matching_families(ledger_rows, {"capex", "operating_income"})
    meta_rows = [
        row
        for row in ledger_rows
        if str(row.get("ticker") or "") == "META" and str(row.get("metric_family") or "") == "operating_income"
    ]
    drivers = [
        _driver_from_rows(
            claim="Alphabet and Meta advertising recovery and operating leverage are supported by planned SEC revenue and operating-income evidence.",
            role="growth_quality",
            rows=core_rows,
            extra_evidence_ids=_trace_evidence_ids(
                trace_rows,
                terms=(
                    "advertising",
                    "ads",
                    "revenues by type",
                    "google services",
                    "operating income",
                    "segment",
                ),
                limit=16,
            ),
            strength="strong",
            caveats=[
                "Advertising recovery and operating leverage should not be treated as proof that AI directly caused ad growth."
            ],
            support_score=20.0,
        ),
        _driver_from_rows(
            claim="Technical infrastructure and AI investment pressure are supported by capex and operating-income evidence, but attribution to ads is limited.",
            role="investment_pressure",
            rows=capex_rows,
            extra_evidence_ids=_trace_evidence_ids(
                trace_rows,
                terms=(
                    "capital expenditures",
                    "technical infrastructure",
                    "servers",
                    "network equipment",
                    "data centers",
                    "ai",
                    "infrastructure",
                ),
                limit=16,
            ),
            strength="strong",
            caveats=[
                "SEC evidence does not allocate all technical infrastructure capex directly to advertising products."
            ],
            support_score=18.0,
        ),
        _driver_from_rows(
            claim="Meta Reality Labs losses are a planned caveat on interpreting consolidated operating leverage.",
            role="profitability_caveat",
            rows=meta_rows,
            extra_evidence_ids=_trace_evidence_ids(
                trace_rows,
                terms=("reality labs", "operating loss", "loss from operations", "family of apps"),
                tickers=["META"],
                limit=12,
            ),
            strength="strong",
            caveats=[
                "Reality Labs evidence is a caveat on Meta consolidated profitability, not direct evidence about advertising demand."
            ],
            support_score=16.0,
        ),
    ]
    return [driver for driver in drivers if driver.get("supporting_metric_ids") or driver.get("supporting_evidence_ids")]


def _semiconductor_trace_drivers(
    case: dict[str, Any],
    ledger_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    revenue_rows = _rows_matching_families(ledger_rows, {"compute_revenue", "data_center_revenue"})
    growth_evidence = _trace_evidence_ids(
        trace_rows,
        terms=(
            "reportable segments",
            "data center segment",
            "compute & networking",
            "data center revenue",
            "compute revenue",
            "accelerated computing",
            "epyc",
            "instinct",
            "gpu",
            "segment",
        ),
        limit=18,
    )
    risk_evidence = _trace_evidence_ids(
        trace_rows,
        terms=(
            "customer concentration",
            "single customer",
            "customer accounted",
            "supply",
            "supply constraints",
            "supply-demand mismatches",
            "foundries",
            "export control",
            "geopolitical",
            "capacity",
            "hopper",
            "blackwell",
            "product transition",
            "manufacturing lead times",
        ),
        limit=18,
    )
    return [
        _driver_from_rows(
            claim="NVIDIA and AMD data-center or compute-related revenue growth is supported, but segment labels are not directly identical.",
            role="growth_comparability",
            rows=revenue_rows,
            extra_evidence_ids=growth_evidence,
            strength="medium",
            caveats=[
                "NVIDIA Compute & Networking and AMD Data Center are different disclosure labels, so direct numerical comparison requires a scope caveat."
            ],
            support_score=20.0,
        ),
        _driver_from_rows(
            claim="Durability must be caveated by supply-chain, customer concentration, product-transition, or export-control risk evidence.",
            role="risk_caveat",
            rows=[],
            extra_evidence_ids=risk_evidence,
            strength="medium",
            caveats=[
                "Risk-factor evidence supports uncertainty and caveats; it does not prove the risk occurred or quantify future durability."
            ],
            support_score=12.0,
            covered_companies=[str(item) for item in case.get("companies") or []],
            covered_years=[int(year) for year in case.get("years") or [] if _is_int_like(year)],
            metric_families=[],
        ),
    ]


def _driver_from_rows(
    *,
    claim: str,
    role: str,
    rows: list[dict[str, Any]],
    extra_evidence_ids: list[str],
    strength: str,
    caveats: list[str],
    support_score: float,
    covered_companies: list[str] | None = None,
    covered_years: list[int] | None = None,
    metric_families: list[str] | None = None,
) -> dict[str, Any]:
    metric_ids = [str(row.get("metric_id") or "") for row in rows if row.get("metric_id")]
    row_evidence = _ledger_support_ids(rows)
    companies = covered_companies or sorted({str(row.get("ticker") or "") for row in rows if row.get("ticker")})
    years = covered_years or sorted({int(row.get("fiscal_year")) for row in rows if _is_int_like(row.get("fiscal_year"))})
    families = metric_families or sorted(
        {str(row.get("metric_family") or "") for row in rows if row.get("metric_family")}
    )
    return {
        "rank": 0,
        "claim": claim,
        "claim_role": role,
        "why_ranked_here": "Task-aware trace plan groups ledger metrics with qualitative evidence required by the prompt.",
        "supporting_metric_ids": metric_ids,
        "supporting_evidence_ids": _unique_strings([*row_evidence, *extra_evidence_ids]),
        "covered_companies": companies,
        "covered_years": years,
        "metric_families": families,
        "conclusion_strength": strength,
        "caveats": _unique_strings(caveats),
        "support_score": support_score,
        "downgrade_reasons": [],
    }


def _rows_matching_families(ledger_rows: list[dict[str, Any]], families: set[str]) -> list[dict[str, Any]]:
    return [row for row in ledger_rows if str(row.get("metric_family") or "") in families]


def _ledger_support_ids(rows: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        for key in ("source_evidence_id", "evidence_id", "object_id"):
            value = str(row.get(key) or "").strip()
            if value:
                ids.append(value)
    return _unique_strings(ids)


def _enrich_driver_with_trace(driver: dict[str, Any], trace_rows: list[dict[str, Any]], tickers: list[str]) -> None:
    families = set(str(family) for family in driver.get("metric_families") or [])
    terms = set(families)
    terms.update(str(term).replace("_", " ") for term in families)
    terms.update(
        {
            "subscription",
            "remaining performance obligation",
            "rpo",
            "product revenue",
            "consumption",
            "revenue recognition",
            "billings",
            "deferred revenue",
            "net revenue retention",
            "customer",
            "remaining performance obligations",
            "performance obligations",
        }
    )
    driver["supporting_evidence_ids"] = _unique_strings(
        [
            *[str(item) for item in driver.get("supporting_evidence_ids") or []],
            *_trace_evidence_ids(trace_rows, terms=tuple(sorted(terms)), tickers=tickers, limit=18),
        ]
    )


def _trace_evidence_ids(
    trace_rows: list[dict[str, Any]],
    *,
    terms: tuple[str, ...],
    tickers: list[str] | None = None,
    limit: int,
) -> list[str]:
    ticker_set = set(tickers or [])
    scored: list[tuple[int, int, str]] = []
    for index, row in enumerate(trace_rows):
        if ticker_set and str(row.get("ticker") or "") not in ticker_set:
            continue
        evidence_id = str(row.get("evidence_id") or row.get("object_id") or "")
        if not evidence_id:
            continue
        haystack = " ".join(
            str(row.get(key) or "")
            for key in ("selection_query", "section", "preview", "text", "raw_text", "content")
        ).lower()
        score = sum(1 for term in terms if term and term.lower() in haystack)
        if score <= 0:
            continue
        scored.append((-score, index, evidence_id))
    scored.sort()
    return _unique_strings(item[2] for item in scored[:limit])


def _load_trace_context_rows(trace_run_dirs: list[str]) -> dict[str, list[dict[str, Any]]]:
    rows_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run_dir in trace_run_dirs:
        trace_path = _resolve(run_dir) / "trace_logs.jsonl"
        if not trace_path.exists():
            continue
        for row in _read_jsonl(trace_path):
            case_id = str(row.get("case_id") or "")
            for context in row.get("context_rows") or []:
                if isinstance(context, dict):
                    rows_by_case[case_id].append(context)
    return rows_by_case


def _required_metric_groups_by_company(case: dict[str, Any]) -> dict[str, list[set[str]]]:
    groups_by_company: dict[str, list[set[str]]] = defaultdict(list)
    for check in case.get("numeric_checks") or []:
        if not isinstance(check, dict):
            continue
        families = {str(item) for item in check.get("metric_families") or [] if item}
        companies = [str(item) for item in check.get("companies") or [] if item]
        if not families:
            continue
        for company in companies:
            groups_by_company[company].append(families)
    return groups_by_company


def _driver_role(families: list[str], needs_profitability: bool) -> str:
    if set(families) & PROFITABILITY_FAMILIES:
        return "profitability"
    if any("risk" in family for family in families):
        return "risk"
    if any("subscription" in family or "rpo" in family or "arr" in family for family in families):
        return "visibility"
    if needs_profitability:
        return "comparability"
    return "growth"


def _driver_strength(
    *,
    has_proxy: bool,
    missing_required_groups: list[list[str]],
    has_profitability: bool,
    needs_profitability: bool,
    case_years: list[int],
    years: list[int],
    families: list[str],
) -> str:
    has_visibility_family = any("subscription" in family or "rpo" in family or "arr" in family for family in families)
    if has_proxy:
        return "weak"
    if missing_required_groups:
        return "medium"
    if needs_profitability and not has_profitability:
        if has_visibility_family:
            return "medium"
        return "weak"
    if case_years and set(case_years).issubset(set(years)) and len(families) >= 2:
        return "strong"
    return "medium"


def _driver_claim(ticker: str, families: list[str], years: list[int], strength: str) -> str:
    year_text = f"{years[0]}-{years[-1]}" if len(years) > 1 else (str(years[0]) if years else "available years")
    family_text = ", ".join(families)
    return f"{ticker} has {year_text} ledger support for {family_text}; conclusion strength is {strength} under the current evidence boundary."


def _driver_why(ticker: str, families: list[str], years: list[int], strength: str) -> str:
    return (
        f"{ticker} is ranked by audited ledger coverage, metric-family directness, and caveat severity: "
        f"{len(years)} years, {len(families)} metric families, strength={strength}."
    )


def _support_score(
    *,
    years: list[int],
    families: list[str],
    has_proxy: bool,
    missing_required_groups: list[list[str]],
    has_profitability: bool,
    needs_profitability: bool,
) -> float:
    score = float(len(years) * 2 + len(families))
    if has_profitability:
        score += 1.5
    if has_proxy:
        score -= 4.0
    if missing_required_groups:
        score -= float(len(missing_required_groups) * 2)
    if needs_profitability and not has_profitability:
        score -= 2.0
    return score


def _main_claim(case: dict[str, Any], drivers: list[dict[str, Any]], has_downgrades: bool) -> str:
    companies = ", ".join(str(item) for item in case.get("companies") or [])
    if str(case.get("task_type") or "").startswith("peer_comparison"):
        if has_downgrades:
            return f"The plan supports a caveated comparison across {companies}; evidence asymmetry and proxy metrics limit direct ranking."
        return f"The plan supports a direct comparison across {companies} within the reviewed SEC ledger boundary."
    return "The plan supports a ledger-backed answer within the reviewed SEC evidence boundary."


def _claim_type(case: dict[str, Any], has_downgrades: bool) -> str:
    if has_downgrades:
        return "caveated_comparison"
    if str(case.get("task_type") or "").startswith("peer_comparison"):
        return "comparison"
    return "comparison"


def _generic_overstatement_guards(case: dict[str, Any], drivers: list[dict[str, Any]]) -> list[str]:
    guards = []
    if any(any(_is_proxy_family(family) for family in driver.get("metric_families") or []) for driver in drivers):
        guards.append("Do not treat proxy metric families as directly comparable segment revenue, ARR, or profitability.")
    if str(case.get("task_type") or "").startswith("peer_comparison"):
        guards.append("Do not declare a simple winner when segment definitions or profitability metrics are asymmetric.")
    if any("services_revenue" in (driver.get("metric_families") or []) for driver in drivers):
        guards.append("Do not describe services revenue as entirely subscription revenue unless subscription evidence is present.")
    return guards


def _case_disallowed_claim_summaries(case: dict[str, Any]) -> list[str]:
    summaries = []
    for item in case.get("disallowed_claims") or []:
        if isinstance(item, dict):
            text = str(item.get("description") or item.get("id") or "")
        else:
            text = str(item or "")
        if text:
            summaries.append(text)
    return summaries


def _is_proxy_family(family: str) -> bool:
    lowered = family.lower()
    return any(marker in lowered for marker in PROXY_FAMILY_MARKERS)


def _unique_strings(values: Any) -> list[str]:
    seen = set()
    out = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _build_report(payload: dict[str, Any]) -> dict[str, Any]:
    plans = payload.get("plans") or []
    drivers = [
        driver
        for plan in plans
        for driver in plan.get("drivers") or []
        if isinstance(driver, dict)
    ]
    proxy_driver_count = sum(
        any(_is_proxy_family(str(family)) for family in driver.get("metric_families") or [])
        for driver in drivers
    )
    return {
        "schema_version": "sec_benchmark_judgment_plan_seed_report_v0.1",
        "summary": {
            "plan_count": len(plans),
            "driver_count": len(drivers),
            "proxy_driver_count": proxy_driver_count,
            "plans_with_downgrades": sum(bool(plan.get("must_downgrade_because")) for plan in plans),
            "skipped_count": len(payload.get("skipped") or []),
        },
        "cases": [
            {
                "case_id": plan.get("case_id"),
                "driver_count": len(plan.get("drivers") or []),
                "main_strength": (plan.get("main_judgment") or {}).get("strength"),
                "claim_type": (plan.get("main_judgment") or {}).get("claim_type"),
                "downgrade_count": len(plan.get("must_downgrade_because") or []),
            }
            for plan in plans
        ],
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _resolve(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
