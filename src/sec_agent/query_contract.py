from __future__ import annotations

import re
from typing import Any

from sec_agent.project_inventory import DEFAULT_SECTIONS, inventory_brief


QUERY_TASK_TYPES = {
    "ai_industry_financial_trend",
    "company_comparison",
    "metric_table",
    "risk_summary",
    "open_analysis",
    "general_sec_financial_question",
}

METRIC_FAMILY_ONTOLOGY = sorted(
    {
        "advertising_revenue",
        "arr_or_recurring_proxy",
        "asset_quality",
        "capex",
        "capital_expenditure_proxy",
        "allowance_for_credit_losses",
        "capital_ratio",
        "cloud_revenue",
        "credit_quality",
        "credit_risk",
        "customer_concentration",
        "data_center_revenue",
        "deferred_revenue",
        "deposits",
        "free_cash_flow_proxy",
        "gross_margin",
        "infrastructure_software",
        "net_interest_income",
        "net_interest_margin",
        "net_charge_offs",
        "nonperforming_assets",
        "nonperforming_loans",
        "operating_cash_flow",
        "operating_income",
        "pipeline",
        "product_revenue",
        "provision_for_credit_losses",
        "research_and_development",
        "revenue",
        "loans",
        "rpo",
        "segment_growth",
        "semiconductor_solutions",
        "semiconductor_systems",
        "services_revenue",
        "subscription_revenue",
        "total_assets",
        "total_revenue",
    }
)

DEFAULT_REQUIRED_CAVEATS = (
    "SEC-only evidence boundary.",
    "Precise values must come from runtime Exact-Value Ledger only.",
)

DEFAULT_FORBIDDEN_CLAIMS = (
    "Do not use market prices, news, earnings calls, or macro data outside the project inventory.",
    "Do not make a risk or industry claim without retrieved SEC evidence.",
)

BANKING_METRIC_FAMILIES = {
    "allowance_for_credit_losses",
    "asset_quality",
    "capital_ratio",
    "credit_quality",
    "credit_risk",
    "deposits",
    "loans",
    "net_charge_offs",
    "net_interest_income",
    "net_interest_margin",
    "nonperforming_assets",
    "nonperforming_loans",
    "provision_for_credit_losses",
    "total_assets",
}

BANKING_TASK_TERMS = (
    "bank",
    "banking",
    "deposit",
    "deposits",
    "loan",
    "loans",
    "net interest",
    "credit risk",
    "银行",
    "存款",
    "贷款",
    "净利息",
    "信用风险",
)


def validate_query_contract(
    contract: dict[str, Any],
    *,
    selected_tickers: list[str],
    selected_years: list[int],
    project_inventory: dict[str, Any],
    sections: tuple[str, ...] = DEFAULT_SECTIONS,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []

    selected_tickers_clean = _unique_upper(selected_tickers)
    selected_years_clean = _unique_ints(selected_years)
    allowed_forms = _selected_form_types(project_inventory, selected_tickers_clean, selected_years_clean)
    allowed_source_tiers = _selected_source_tiers(
        project_inventory,
        selected_tickers_clean,
        selected_years_clean,
        allowed_forms,
    )

    clean = dict(contract)
    clean["schema_version"] = "interactive_query_contract_v0.2"

    task_type = str(clean.get("task_type") or "").strip()
    if task_type not in QUERY_TASK_TYPES:
        warnings.append({"type": "invalid_task_type_normalized", "value": task_type})
        task_type = "general_sec_financial_question"
    clean["task_type"] = task_type

    scope_tickers = _clamp_tickers(clean.get("search_scope_tickers"), selected_tickers_clean)
    if not scope_tickers:
        scope_tickers = selected_tickers_clean
        normalizations.append({"field": "search_scope_tickers", "action": "filled_from_selected_scope"})
    clean["search_scope_tickers"] = scope_tickers

    focus_tickers = _clamp_tickers(clean.get("focus_tickers"), scope_tickers)
    if not focus_tickers:
        focus_tickers = scope_tickers
        normalizations.append({"field": "focus_tickers", "action": "filled_from_search_scope"})
    clean["focus_tickers"] = focus_tickers

    years = _clamp_years(clean.get("years"), selected_years_clean)
    if not years:
        years = selected_years_clean
        normalizations.append({"field": "years", "action": "filled_from_selected_scope"})
    clean["years"] = years

    filing_types = _clamp_form_types(clean.get("filing_types"), allowed_forms)
    if not filing_types:
        filing_types = allowed_forms
        normalizations.append({"field": "filing_types", "action": "filled_from_project_inventory"})
    clean["filing_types"] = filing_types

    source_tiers = _clamp_source_tiers(
        clean.get("source_tiers") or (clean.get("scope") or {}).get("source_tiers"),
        allowed_source_tiers,
    )
    if not source_tiers:
        source_tiers = allowed_source_tiers
        normalizations.append({"field": "source_tiers", "action": "filled_from_project_inventory"})
    clean["source_tiers"] = source_tiers
    clean["source_policy"] = _source_policy_for_scope(filing_types, source_tiers)

    clean["scope"] = {
        "universe_tickers": scope_tickers,
        "focus_tickers": focus_tickers,
        "years": years,
        "filing_types": filing_types,
        "source_tiers": source_tiers,
        "sec_sections": list(sections),
    }

    clean["analysis_axes"] = _string_list(clean.get("analysis_axes"), max_items=12, max_chars=80)
    clean["facets"] = _string_list(clean.get("facets"), max_items=12, max_chars=96)
    clean["metric_families"] = _metric_family_list(clean.get("metric_families"), warnings, field="metric_families")
    clean["metric_queries"] = _string_list(clean.get("metric_queries"), max_items=10, max_chars=220)
    clean["qualitative_queries"] = _string_list(clean.get("qualitative_queries"), max_items=10, max_chars=220)
    clean["decomposed_tasks"] = _normalize_decomposed_tasks(clean.get("decomposed_tasks"), clean, warnings)
    if not _scope_has_banking_company(clean["focus_tickers"], project_inventory):
        clean = _drop_nonbank_banking_scope(clean, warnings, normalizations)
    clean["required_caveats"] = _ensure_required_items(
        _normalize_required_caveats(_string_list(clean.get("required_caveats"), max_items=12, max_chars=260), normalizations),
        (*DEFAULT_REQUIRED_CAVEATS, *_source_policy_caveats(filing_types)),
        "required_caveats",
        normalizations,
    )
    clean["forbidden_claims"] = _ensure_required_items(
        _string_list(clean.get("forbidden_claims"), max_items=12, max_chars=260),
        DEFAULT_FORBIDDEN_CLAIMS,
        "forbidden_claims",
        normalizations,
    )
    clean["evidence_gaps"] = _normalize_evidence_gaps(clean.get("evidence_gaps"))
    source_coverage_gaps = _source_coverage_gaps(
        project_inventory,
        scope_tickers,
        years,
        filing_types,
        source_tiers,
    )
    clean["source_coverage_gaps"] = source_coverage_gaps
    if source_coverage_gaps:
        warnings.append(
            {
                "type": "source_coverage_gaps",
                "gap_count": len(source_coverage_gaps),
                "sample": source_coverage_gaps[:5],
            }
        )
    clean["planner_confidence"] = _planner_confidence(clean.get("planner_confidence"))
    clean["project_inventory"] = inventory_brief(project_inventory)
    clean["project_inventory_digest"] = project_inventory.get("inventory_digest")

    if not clean["search_scope_tickers"]:
        errors.append({"type": "empty_search_scope"})
    if not clean["years"]:
        errors.append({"type": "empty_year_scope"})
    if not clean["filing_types"]:
        errors.append({"type": "empty_filing_type_scope"})
    if not clean["decomposed_tasks"]:
        errors.append({"type": "missing_decomposed_tasks"})
    if str(clean.get("task_type") or "") in {"ai_industry_financial_trend", "open_analysis"} and len(clean["decomposed_tasks"]) < 2:
        errors.append({"type": "broad_task_requires_multiple_decomposed_tasks", "task_count": len(clean["decomposed_tasks"])})
    elif _is_broad_task(clean) and len(clean["decomposed_tasks"]) < 2:
        warnings.append({"type": "broad_task_has_single_decomposed_task", "task_count": len(clean["decomposed_tasks"])})
    if not clean["metric_families"]:
        warnings.append({"type": "missing_metric_families"})

    report = {
        "schema_version": "query_contract_validation_report_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "normalizations": normalizations,
        "selected_scope": {
            "tickers": selected_tickers_clean,
            "years": selected_years_clean,
            "filing_types": allowed_forms,
            "source_tiers": allowed_source_tiers,
            "source_policy": clean["source_policy"],
        },
        "source_coverage_gaps": source_coverage_gaps,
        "inventory_digest": project_inventory.get("inventory_digest"),
    }
    clean["query_contract_validation"] = report
    return {"contract": clean, "report": report}


def _selected_form_types(project_inventory: dict[str, Any], tickers: list[str], years: list[int]) -> list[str]:
    selected = {ticker.upper() for ticker in tickers}
    selected_years = {int(year) for year in years}
    forms = set()
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            if selected_years and year not in selected_years:
                continue
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if form_type:
                forms.add(form_type)
    return sorted(forms) or ["10-K"]


def _selected_source_tiers(
    project_inventory: dict[str, Any],
    tickers: list[str],
    years: list[int],
    form_types: list[str],
) -> list[str]:
    selected = {ticker.upper() for ticker in tickers}
    selected_years = {int(year) for year in years}
    selected_forms = {str(form).upper() for form in form_types}
    tiers = set()
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if selected and ticker not in selected:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            if selected_years and year not in selected_years:
                continue
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if selected_forms and form_type not in selected_forms:
                continue
            source_tier = str(filing.get("source_tier") or "primary_sec_filing").strip()
            if source_tier:
                tiers.add(source_tier)
    return sorted(tiers) or ["primary_sec_filing"]


def _source_policy_for_scope(filing_types: list[str], source_tiers: list[str]) -> str:
    forms = {str(form).upper() for form in filing_types if str(form)}
    tiers = {str(tier) for tier in source_tiers if str(tier)}
    primary_sec_only = not tiers or tiers <= {"primary_sec_filing"}
    if primary_sec_only and forms == {"10-K"}:
        return "SEC_ONLY_10K"
    if primary_sec_only and forms and forms <= {"10-K", "10-Q"} and "10-Q" in forms:
        return "SEC_PRIMARY_MIXED_RECENT"
    if primary_sec_only:
        return "SEC_ONLY"
    return "MIXED_SOURCE"


def _source_policy_caveats(filing_types: list[str]) -> tuple[str, ...]:
    forms = {str(form).upper() for form in filing_types if str(form)}
    caveats = []
    if "10-Q" in forms:
        caveats.append(
            "10-Q evidence is unaudited quarterly SEC evidence; do not mix quarterly, YTD, and annual values without period caveats."
        )
    if {"10-K", "10-Q"} <= forms:
        caveats.append("When 10-K and 10-Q evidence both appear, label audited annual versus unaudited quarterly boundaries.")
    return tuple(caveats)


def _source_coverage_gaps(
    project_inventory: dict[str, Any],
    tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
) -> list[dict[str, Any]]:
    lookup: dict[tuple[str, int, str], set[str]] = {}
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if not ticker:
            continue
        for filing in company.get("filings") or []:
            year = _int_or_none(filing.get("year"))
            form_type = str(filing.get("form_type") or filing.get("source_type") or "").upper().strip()
            if year is None or not form_type:
                continue
            key = (ticker, int(year), form_type)
            lookup.setdefault(key, set()).add(str(filing.get("source_tier") or "primary_sec_filing"))

    gaps: list[dict[str, Any]] = []
    required_tiers = [str(tier) for tier in source_tiers if str(tier)] or ["primary_sec_filing"]
    for ticker in tickers:
        ticker_text = str(ticker or "").upper()
        if not ticker_text:
            continue
        for year in years:
            year_value = _int_or_none(year)
            if year_value is None:
                continue
            for form_type in filing_types:
                form = str(form_type or "").upper().strip()
                if not form:
                    continue
                key = (ticker_text, int(year_value), form)
                available_tiers = lookup.get(key, set())
                if not available_tiers:
                    gaps.append(
                        {
                            "ticker": ticker_text,
                            "year": int(year_value),
                            "form_type": form,
                            "period_type": _period_type_for_form(form),
                            "reason": _missing_form_reason(form),
                        }
                    )
                    continue
                missing_tiers = sorted(set(required_tiers) - available_tiers)
                if missing_tiers:
                    gaps.append(
                        {
                            "ticker": ticker_text,
                            "year": int(year_value),
                            "form_type": form,
                            "missing_source_tiers": missing_tiers,
                            "available_source_tiers": sorted(available_tiers),
                            "period_type": _period_type_for_form(form),
                            "reason": "source_tier_not_in_inventory",
                        }
                    )
                if len(gaps) >= 40:
                    return gaps
    return gaps


def _period_type_for_form(form_type: str) -> str:
    form = str(form_type or "").upper()
    if form == "10-K":
        return "annual"
    if form == "10-Q":
        return "quarterly"
    return "unknown"


def _missing_form_reason(form_type: str) -> str:
    form = str(form_type or "").upper().replace("-", "").lower()
    if form:
        return f"{form}_not_in_inventory"
    return "filing_type_not_in_inventory"


def _normalize_decomposed_tasks(value: Any, contract: dict[str, Any], warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    allowed_tickers = _unique_upper(contract.get("search_scope_tickers") or contract.get("focus_tickers") or [])
    for idx, item in enumerate(value or [], start=1):
        if not isinstance(item, dict):
            warnings.append({"type": "dropped_non_object_decomposed_task", "index": idx})
            continue
        task_id = _slug(str(item.get("task_id") or f"task_{idx}"))[:64] or f"task_{idx}"
        priority = str(item.get("priority") or "supporting").strip().lower()
        if priority not in {"primary", "supporting", "caveat"}:
            warnings.append({"type": "invalid_task_priority_normalized", "task_id": task_id, "value": priority})
            priority = "supporting"
        families = _metric_family_list(item.get("required_metric_families"), warnings, field=f"decomposed_tasks.{task_id}.required_metric_families")
        if not families:
            families = [str(family) for family in (contract.get("metric_families") or [])[:4]]
        question = _short_text(item.get("question_zh") or item.get("question") or "", 260)
        if not question:
            question = f"Evaluate task {task_id} within the SEC evidence boundary."
            warnings.append({"type": "missing_task_question_filled", "task_id": task_id})
        required_tickers = _clamp_tickers(item.get("required_tickers"), allowed_tickers)
        peer_tickers = [ticker for ticker in _clamp_tickers(item.get("peer_tickers"), allowed_tickers) if ticker not in set(required_tickers)]
        tasks.append(
            {
                "task_id": task_id,
                "question_zh": question,
                "priority": priority,
                "required_metric_families": families,
                "required_tickers": required_tickers,
                "peer_tickers": peer_tickers,
            }
        )
        if len(tasks) >= 10:
            break
    return tasks


def _scope_has_banking_company(focus_tickers: list[str], project_inventory: dict[str, Any]) -> bool:
    focus = {str(ticker or "").upper() for ticker in focus_tickers}
    for category in (project_inventory.get("categories") or []):
        category_name = str(category.get("category") or "").lower()
        if "bank" not in category_name and "financial" not in category_name:
            continue
        for ticker in category.get("tickers") or []:
            if str(ticker or "").upper() in focus:
                return True
    for company in project_inventory.get("companies") or []:
        ticker = str(company.get("ticker") or "").upper()
        if ticker not in focus:
            continue
        category_name = str(company.get("category") or "").lower()
        if "bank" in category_name or "financial" in category_name:
            return True
    return False


def _drop_nonbank_banking_scope(
    contract: dict[str, Any],
    warnings: list[dict[str, Any]],
    normalizations: list[dict[str, Any]],
) -> dict[str, Any]:
    clean = dict(contract)
    metric_families = [family for family in clean.get("metric_families") or [] if family not in BANKING_METRIC_FAMILIES]
    if len(metric_families) != len(clean.get("metric_families") or []):
        normalizations.append({"field": "metric_families", "action": "dropped_banking_families_for_nonbank_scope"})
    clean["metric_families"] = metric_families

    filtered_tasks = []
    for task in clean.get("decomposed_tasks") or []:
        task_text = " ".join(str(task.get(key) or "") for key in ("task_id", "question_zh", "question")).lower()
        families = list(task.get("required_metric_families") or [])
        has_banking_terms = _contains_any(task_text, BANKING_TASK_TERMS)
        has_banking_families = any(family in BANKING_METRIC_FAMILIES for family in families)
        if has_banking_terms and has_banking_families:
            warnings.append({"type": "dropped_banking_task_for_nonbank_scope", "task_id": task.get("task_id")})
            continue
        filtered_families = [family for family in families if family not in BANKING_METRIC_FAMILIES]
        if len(filtered_families) != len(families):
            warnings.append({"type": "dropped_banking_metric_family_for_nonbank_task", "task_id": task.get("task_id")})
        task = dict(task)
        task["required_metric_families"] = filtered_families or metric_families[:4]
        filtered_tasks.append(task)
    clean["decomposed_tasks"] = filtered_tasks
    return clean


def _normalize_evidence_gaps(value: Any) -> list[dict[str, str]]:
    gaps = []
    for item in value or []:
        if isinstance(item, dict):
            task_id = _slug(str(item.get("task_id") or "gap"))[:64] or "gap"
            gap = _short_text(item.get("gap") or item.get("description") or "", 260)
        else:
            task_id = "gap"
            gap = _short_text(item, 260)
        if gap:
            gaps.append({"task_id": task_id, "gap": gap})
        if len(gaps) >= 10:
            break
    return gaps


def _metric_family_list(value: Any, warnings: list[dict[str, Any]], *, field: str) -> list[str]:
    allowed = set(METRIC_FAMILY_ONTOLOGY)
    out = []
    for item in value or []:
        family = str(item or "").strip()
        if not family:
            continue
        if family not in allowed:
            warnings.append({"type": "unknown_metric_family_dropped", "field": field, "value": family})
            continue
        if family not in out:
            out.append(family)
    return out[:20]


def _ensure_required_items(
    values: list[str],
    required: tuple[str, ...],
    field: str,
    normalizations: list[dict[str, Any]],
) -> list[str]:
    out = list(values)
    lower = " || ".join(item.lower() for item in out)
    for item in required:
        probe = item.lower().rstrip(".")
        if probe not in lower:
            out.append(item)
            normalizations.append({"field": field, "action": "added_required_item", "value": item})
    return out[:16]


def _normalize_required_caveats(values: list[str], normalizations: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for value in values:
        normalized = _normalize_required_caveat_text(value)
        if normalized != value:
            normalizations.append({"field": "required_caveats", "action": "normalized_false_no_number_caveat"})
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _normalize_required_caveat_text(value: str) -> str:
    text = str(value or "").strip()
    replacements = {
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含具体数字。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含具体数值。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含任何具体数字。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含任何具体数值。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含具体数字。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含具体数值。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含任何具体数字。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
        "精确数值必须从运行时Exact-Value Ledger提取，当前协议不包含任何具体数值。": "精确数值必须从运行时 Exact-Value Ledger 提取；不得使用模型记忆或未授权来源补数。",
    }
    return replacements.get(text, text)


def _is_broad_task(contract: dict[str, Any]) -> bool:
    task_type = str(contract.get("task_type") or "")
    focus_count = len(contract.get("focus_tickers") or [])
    years_count = len(contract.get("years") or [])
    return task_type in {"ai_industry_financial_trend", "open_analysis"} or focus_count >= 5 or years_count >= 3


def _clamp_tickers(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {ticker.upper() for ticker in allowed}
    out = []
    for item in value or []:
        ticker = str(item or "").upper().strip()
        if ticker in allowed_set and ticker not in out:
            out.append(ticker)
    return out


def _clamp_years(value: Any, allowed: list[int]) -> list[int]:
    allowed_set = {int(year) for year in allowed}
    out = []
    for item in value or []:
        year = _int_or_none(item)
        if year in allowed_set and year not in out:
            out.append(int(year))
    return out


def _clamp_form_types(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {str(item).upper() for item in allowed}
    out = []
    for item in value or []:
        form_type = str(item or "").upper().strip()
        if form_type in allowed_set and form_type not in out:
            out.append(form_type)
    return out


def _clamp_source_tiers(value: Any, allowed: list[str]) -> list[str]:
    allowed_set = {str(item) for item in allowed}
    out = []
    for item in value or []:
        source_tier = str(item or "").strip()
        if source_tier in allowed_set and source_tier not in out:
            out.append(source_tier)
    return out


def _string_list(value: Any, *, max_items: int, max_chars: int = 80) -> list[str]:
    out = []
    for item in value or []:
        text = _short_text(item, max_chars)
        if text and text not in out:
            out.append(text)
        if len(out) >= max_items:
            break
    return out


def _unique_upper(value: list[str]) -> list[str]:
    out = []
    for item in value:
        text = str(item or "").upper().strip()
        if text and text not in out:
            out.append(text)
    return out


def _unique_ints(value: list[int]) -> list[int]:
    out = []
    for item in value:
        number = _int_or_none(item)
        if number is not None and number not in out:
            out.append(number)
    return sorted(out)


def _planner_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low"} else "medium"


def _short_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_chars]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _contains_any(text: str, probes: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(str(probe).lower() in lowered for probe in probes)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None
