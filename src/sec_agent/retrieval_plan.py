from __future__ import annotations

import re
from datetime import datetime
from typing import Any


SCHEMA_VERSION = "sec_agent_retrieval_plan_v0.1"
EVIDENCE_REQUIREMENT_SCHEMA_VERSION = "sec_agent_evidence_requirement_plan_v0.1"

ALLOWED_RETRIEVAL_ROUTES = {
    "ledger_first",
    "filing_text",
    "8k_commentary",
    "milvus_semantic",
    "market_snapshot",
    "industry_snapshot",
    "risk_text",
    "run_artifact",
}

ROUTE_COST_TIERS = {
    "ledger_first": "low",
    "run_artifact": "low",
    "filing_text": "medium",
    "8k_commentary": "medium",
    "risk_text": "medium",
    "market_snapshot": "medium",
    "industry_snapshot": "medium",
    "milvus_semantic": "high",
    "relationship_graph": "high",
}
ROUTE_COST_TIER_RANK = {"low": 1, "medium": 2, "high": 3}

MARKET_SOURCE_TIER = "market_snapshot"
INDUSTRY_SOURCE_TIER = "industry_snapshot"
RUN_ARTIFACT_SOURCE_TIER = "run_artifact"
PRIMARY_SEC_SOURCE_TIER = "primary_sec_filing"
COMPANY_AUTHORED_SOURCE_TIER = "company_authored_unaudited_sec_filing"

MARKET_TERMS = (
    "market",
    "valuation",
    "multiple",
    "return",
    "stock",
    "price",
    "drawdown",
    "reaction",
    "relative",
    "估值",
    "市场",
    "收益",
    "股价",
    "回撤",
    "反应",
)

COMMENTARY_TERMS = (
    "management",
    "commentary",
    "explain",
    "guidance",
    "demand",
    "order",
    "backlog",
    "margin",
    "capex",
    "investment",
    "momentum",
    "why",
    "driver",
    "管理层",
    "解释",
    "指引",
    "需求",
    "订单",
    "资本开支",
    "投资",
    "业绩",
    "驱动",
)

RISK_TERMS = (
    "risk",
    "counterargument",
    "uncertainty",
    "litigation",
    "regulatory",
    "customer concentration",
    "cyclical",
    "风险",
    "反证",
    "不确定",
    "监管",
    "客户集中",
    "周期",
)

SEMANTIC_RECALL_TERMS = (
    "typed semantic recall",
    "semantic recall",
    "semantic search",
    "milvus",
    "vector recall",
    "rag",
    "typed vector",
    "语义召回",
    "语义检索",
    "向量召回",
    "向量检索",
    "已入库",
)

INDUSTRY_CONTEXT_TERMS = (
    "industry",
    "sector",
    "macro",
    "rates",
    "credit cycle",
    "commodity",
    "consumer demand",
    "housing",
    "regulatory",
    "行业",
    "板块",
    "宏观",
    "利率",
    "信用周期",
    "大宗商品",
    "需求环境",
    "监管",
)

PERIOD_ROLES = {"QTD", "YTD", "TTM", "ANNUAL"}


def build_retrieval_plan(
    query_contract: dict[str, Any],
    *,
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile an executable retrieval plan from planner evidence requirements."""
    case = case or {}
    contract = dict(query_contract or {})
    evidence_requirement_plan = build_evidence_requirement_plan(contract, case=case)
    focus_tickers = _unique_upper(
        contract.get("focus_tickers")
        or (contract.get("scope") or {}).get("focus_tickers")
        or case.get("companies")
        or []
    )
    search_scope_tickers = _unique_upper(
        contract.get("search_scope_tickers")
        or (contract.get("scope") or {}).get("universe_tickers")
        or focus_tickers
    )
    years = _unique_ints(contract.get("years") or (contract.get("scope") or {}).get("years") or case.get("years") or [])
    filing_types = _unique_form_types(contract.get("filing_types") or (contract.get("scope") or {}).get("filing_types") or [])
    source_tiers = _unique_strings(contract.get("source_tiers") or (contract.get("scope") or {}).get("source_tiers") or [])
    requirements = [
        requirement
        for requirement in evidence_requirement_plan.get("requirements") or []
        if isinstance(requirement, dict)
    ]
    if not requirements:
        requirements = _derive_evidence_requirements(contract, case, focus_tickers, search_scope_tickers, years, filing_types, source_tiers)

    plan_tasks: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    plan_semantic_recall_requested = _contract_requests_semantic_recall(contract, case)
    plan_semantic_recall_added = False
    for index, requirement in enumerate(requirements, start=1):
        task = _requirement_as_task(requirement)
        task_id = _task_id(task, index)
        task_text = _task_text(task)
        task_tickers = _task_tickers(task, focus_tickers, search_scope_tickers)
        peer_tickers = _task_peer_tickers(task, task_tickers, focus_tickers, search_scope_tickers)
        route_tickers = _unique_upper([*task_tickers, *peer_tickers])
        task_years = _unique_ints(task.get("years") or years)
        task_source_tiers = _unique_strings(task.get("source_tiers") or source_tiers)
        task_filing_types = _unique_form_types(task.get("filing_types") or filing_types)
        metric_families = _unique_strings(task.get("required_metric_families") or contract.get("metric_families") or [])
        period_roles = _period_roles(task, contract)
        fallback_route_names = _routes_for_task(
            task=task,
            task_text=task_text,
            metric_families=metric_families,
            filing_types=task_filing_types,
            source_tiers=task_source_tiers,
        )
        route_names = _routes_for_requirement(requirement, fallback_route_names)
        if _semantic_recall_forbidden_for_requirement(requirement, task_text=task_text, case=case):
            route_names = [route_name for route_name in route_names if route_name != "milvus_semantic"]
        if "milvus_semantic" in route_names:
            plan_semantic_recall_added = True
        elif (
            plan_semantic_recall_requested
            and not plan_semantic_recall_added
            and _semantic_recall_scope_allowed(task_source_tiers, task_filing_types)
            and not _semantic_recall_forbidden_for_requirement(requirement, task_text=task_text, case=case)
        ):
            route_names = _dedupe_keep_order([*route_names, "milvus_semantic"])
            plan_semantic_recall_added = True
        coverage_requirements = {
            "tickers": route_tickers or search_scope_tickers,
            "years": task_years,
            "filing_types": task_filing_types,
            "source_tiers": task_source_tiers,
            "metric_families": metric_families,
            "period_roles": period_roles,
            "market_fields": _market_fields_for_task(task, contract),
        }
        if isinstance(requirement.get("coverage_requirements"), dict):
            coverage_requirements.update(
                {
                    key: requirement["coverage_requirements"][key]
                    for key in requirement["coverage_requirements"]
                    if key in coverage_requirements
                }
            )
        plan_tasks.append(
            {
                "task_id": task_id,
                "question_zh": str(task.get("question_zh") or task.get("question") or "").strip()[:120],
                "priority": str(task.get("priority") or "supporting"),
                "analysis_intent": _analysis_intent(task, contract, route_names),
                "tickers": route_tickers or search_scope_tickers,
                "sector": str(task.get("sector") or ""),
                "years": task_years,
                "filing_types": task_filing_types,
                "source_tiers": task_source_tiers,
                "metric_families": metric_families,
                "period_roles": period_roles,
                "retrieval_routes": route_names,
                "coverage_requirements": coverage_requirements,
                "route_selection_reason": requirement.get("route_selection_reason") or "",
                "route_cost_tier": requirement.get("route_cost_tier") or _normalize_route_cost_tier("", route_names),
                "route_selection_policy": requirement.get("route_selection_policy") or "",
                "second_pass_policy": _second_pass_policy(),
                "evidence_requirement_id": requirement.get("requirement_id") or requirement.get("evidence_requirement_id") or "",
                "evidence_requirement_source": evidence_requirement_plan.get("source") or "",
            }
        )
        for route_name in route_names:
            budgets = _route_budgets(route_name, ticker_count=len(route_tickers or search_scope_tickers), family_count=len(metric_families))
            raw_candidate_budget = _clamp_int(requirement.get("candidate_budget"), 0, 1000, 0)
            candidate_budget = raw_candidate_budget if raw_candidate_budget > 0 else budgets["candidate_budget"]
            raw_rerank_budget = _clamp_int(requirement.get("rerank_budget"), 0, candidate_budget, 0)
            rerank_budget = raw_rerank_budget if raw_rerank_budget > 0 else min(budgets["rerank_budget"], candidate_budget)
            if route_name in {"ledger_first", "market_snapshot", "industry_snapshot"}:
                rerank_budget = 0
            routes.append(
                {
                    "route_id": f"{task_id}::{route_name}",
                    "task_id": task_id,
                    "retrieval_route": route_name,
                    "tickers": route_tickers or search_scope_tickers,
                    "sector": str(task.get("sector") or ""),
                    "years": task_years,
                    "filing_types": _route_filing_types(route_name, task_filing_types),
                    "source_tiers": _route_source_tiers(route_name, task_source_tiers),
                    "metric_families": metric_families,
                    "period_roles": period_roles,
                    "section_hints": _section_hints(route_name),
                    "candidate_budget": candidate_budget,
                    "rerank_budget": rerank_budget,
                    "coverage_requirements": coverage_requirements,
                    "route_selection_reason": requirement.get("route_selection_reason") or "",
                    "route_cost_tier": ROUTE_COST_TIERS.get(route_name, requirement.get("route_cost_tier") or "medium"),
                    "route_selection_policy": requirement.get("route_selection_policy") or "",
                    "second_pass_policy": _second_pass_policy(),
                    "evidence_requirement_id": requirement.get("requirement_id") or requirement.get("evidence_requirement_id") or "",
                }
            )

    plan = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "query_contract_derived_retrieval_plan",
        "case_id": case.get("case_id") or contract.get("case_id") or "",
        "query_contract_digest": contract.get("project_inventory_digest") or "",
        "source_policy": contract.get("source_policy") or case.get("source_policy") or "",
        "scope": {
            "focus_tickers": focus_tickers,
            "search_scope_tickers": search_scope_tickers,
            "years": years,
            "filing_types": filing_types,
            "source_tiers": source_tiers,
        },
        "evidence_requirement_plan": evidence_requirement_plan,
        "tasks": plan_tasks,
        "routes": routes,
    }
    plan["summary"] = _summary(plan)
    result = validate_retrieval_plan(plan, query_contract=contract, case=case)
    return result["plan"]


def build_evidence_requirement_plan(
    query_contract: dict[str, Any],
    *,
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize model-specified evidence needs before physical route compilation."""
    case = case or {}
    contract = dict(query_contract or {})
    focus_tickers = _unique_upper(
        contract.get("focus_tickers")
        or (contract.get("scope") or {}).get("focus_tickers")
        or case.get("companies")
        or []
    )
    search_scope_tickers = _unique_upper(
        contract.get("search_scope_tickers")
        or (contract.get("scope") or {}).get("universe_tickers")
        or focus_tickers
    )
    years = _unique_ints(contract.get("years") or (contract.get("scope") or {}).get("years") or case.get("years") or [])
    filing_types = _unique_form_types(contract.get("filing_types") or (contract.get("scope") or {}).get("filing_types") or [])
    source_tiers = _unique_strings(contract.get("source_tiers") or (contract.get("scope") or {}).get("source_tiers") or [])
    explicit_plan = contract.get("evidence_requirement_plan") if isinstance(contract.get("evidence_requirement_plan"), dict) else {}
    raw_requirements = (
        explicit_plan.get("requirements")
        if isinstance(explicit_plan.get("requirements"), list)
        else contract.get("evidence_requirements")
    )
    source = "planner_output_evidence_requirements" if isinstance(raw_requirements, list) and raw_requirements else "query_contract_derived_evidence_requirements"
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raw_requirements = _derive_evidence_requirements(
            contract,
            case,
            focus_tickers,
            search_scope_tickers,
            years,
            filing_types,
            source_tiers,
        )

    requirements, report = _normalize_evidence_requirements(
        raw_requirements,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
        years=years,
        filing_types=filing_types,
        source_tiers=source_tiers,
        contract=contract,
    )
    plan = {
        "schema_version": EVIDENCE_REQUIREMENT_SCHEMA_VERSION,
        "source": source,
        "case_id": case.get("case_id") or contract.get("case_id") or "",
        "scope": {
            "focus_tickers": focus_tickers,
            "search_scope_tickers": search_scope_tickers,
            "years": years,
            "filing_types": filing_types,
            "source_tiers": source_tiers,
        },
        "requirements": requirements,
        "summary": _evidence_requirement_summary(requirements),
        "evidence_requirement_validation": report,
    }
    return plan


def validate_retrieval_plan(
    plan: dict[str, Any],
    *,
    query_contract: dict[str, Any] | None = None,
    case: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_contract = query_contract or {}
    case = case or {}
    clean = dict(plan or {})
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []

    clean["schema_version"] = SCHEMA_VERSION
    allowed_tickers = set(
        _unique_upper(
            query_contract.get("search_scope_tickers")
            or (query_contract.get("scope") or {}).get("universe_tickers")
            or query_contract.get("focus_tickers")
            or case.get("companies")
            or []
        )
    )
    allowed_years = set(_unique_ints(query_contract.get("years") or case.get("years") or []))
    allowed_forms = set(_unique_form_types(query_contract.get("filing_types") or case.get("filing_types") or []))
    allowed_source_tiers = set(_unique_strings(query_contract.get("source_tiers") or case.get("source_tiers") or []))

    routes = [dict(route) for route in clean.get("routes") or [] if isinstance(route, dict)]
    tasks = [dict(task) for task in clean.get("tasks") or [] if isinstance(task, dict)]
    if not tasks:
        errors.append({"type": "missing_retrieval_plan_tasks"})
    if not routes:
        errors.append({"type": "missing_retrieval_plan_routes"})
    erp = clean.get("evidence_requirement_plan") if isinstance(clean.get("evidence_requirement_plan"), dict) else {}
    erp_report = erp.get("evidence_requirement_validation") if isinstance(erp.get("evidence_requirement_validation"), dict) else {}
    if erp_report.get("status") == "fail":
        errors.append({"type": "evidence_requirement_plan_validation_failed", "report": erp_report})

    normalized_routes = []
    seen_route_ids = set()
    for index, route in enumerate(routes, start=1):
        route_name = str(route.get("retrieval_route") or "").strip()
        if route_name not in ALLOWED_RETRIEVAL_ROUTES:
            errors.append({"type": "invalid_retrieval_route", "route": route_name, "index": index})
            continue
        route_id = str(route.get("route_id") or f"{route.get('task_id') or 'task'}::{route_name}").strip()
        if route_id in seen_route_ids:
            route_id = f"{route_id}::{index}"
            normalizations.append({"field": "route_id", "action": "deduped", "index": index})
        seen_route_ids.add(route_id)
        route["route_id"] = route_id
        route["retrieval_route"] = route_name
        route["tickers"] = _clamp_upper(route.get("tickers"), allowed_tickers)
        route["years"] = _clamp_ints(route.get("years"), allowed_years)
        route["filing_types"] = _clamp_forms(route.get("filing_types"), allowed_forms)
        route["source_tiers"] = _clamp_strings(route.get("source_tiers"), allowed_source_tiers)
        route["metric_families"] = _unique_strings(route.get("metric_families") or [])
        route["period_roles"] = _period_role_list(route.get("period_roles") or [])
        route["candidate_budget"] = _clamp_int(route.get("candidate_budget"), 0, 1000, 120)
        route["rerank_budget"] = _clamp_int(route.get("rerank_budget"), 0, route["candidate_budget"], min(80, route["candidate_budget"]))
        if route_name in {"ledger_first", "market_snapshot", "industry_snapshot"} and route["rerank_budget"] != 0:
            route["rerank_budget"] = 0
            normalizations.append({"field": "rerank_budget", "action": "zeroed_for_structured_route", "route_id": route_id})
        route["second_pass_policy"] = _normalize_second_pass_policy(route.get("second_pass_policy"))
        if not route["tickers"] and allowed_tickers:
            warnings.append({"type": "empty_route_tickers_after_scope_clamp", "route_id": route_id})
        if not route["years"] and allowed_years and route_name not in {"market_snapshot", "industry_snapshot"}:
            warnings.append({"type": "empty_route_years_after_scope_clamp", "route_id": route_id})
        if not route["source_tiers"] and allowed_source_tiers:
            warnings.append({"type": "empty_route_source_tiers_after_scope_clamp", "route_id": route_id})
        normalized_routes.append(route)

    clean["tasks"] = tasks
    clean["routes"] = normalized_routes
    clean["summary"] = _summary(clean)
    report = {
        "schema_version": "sec_agent_retrieval_plan_validation_report_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "normalizations": normalizations,
    }
    clean["retrieval_plan_validation"] = report
    return {"plan": clean, "report": report}


def _derive_evidence_requirements(
    contract: dict[str, Any],
    case: dict[str, Any],
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
) -> list[dict[str, Any]]:
    tasks = [task for task in contract.get("decomposed_tasks") or [] if isinstance(task, dict)] or [_fallback_task(contract)]
    requirements: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        task_text = _task_text(task)
        task_tickers = _task_tickers(task, focus_tickers, search_scope_tickers)
        peer_tickers = _task_peer_tickers(task, task_tickers, focus_tickers, search_scope_tickers)
        tickers = _unique_upper([*task_tickers, *peer_tickers]) or search_scope_tickers
        task_years = _unique_ints(task.get("years") or years)
        task_source_tiers = _unique_strings(task.get("source_tiers") or source_tiers)
        task_filing_types = _unique_form_types(task.get("filing_types") or filing_types)
        metric_families = _unique_strings(task.get("required_metric_families") or contract.get("metric_families") or [])
        routes = _routes_for_task(
            task=task,
            task_text=task_text,
            metric_families=metric_families,
            filing_types=task_filing_types,
            source_tiers=task_source_tiers,
        )
        requirements.append(
            {
                "requirement_id": f"req_{_task_id(task, index)}",
                "task_id": _task_id(task, index),
                "question_zh": str(task.get("question_zh") or task.get("question") or case.get("prompt") or "").strip(),
                "priority": str(task.get("priority") or "supporting"),
                "analysis_intent": _analysis_intent(task, contract, routes),
                "tickers": tickers,
                "peer_tickers": peer_tickers,
                "sector": str(task.get("sector") or ""),
                "years": task_years,
                "filing_types": task_filing_types,
                "source_tiers": task_source_tiers,
                "metric_families": metric_families,
                "period_roles": _period_roles(task, contract),
                "evidence_routes": routes,
                "section_hints": _unique_strings(task.get("section_hints") or []),
                "market_fields": _market_fields_for_task(task, contract),
                "coverage_requirements": {},
                "candidate_budget": 0,
                "rerank_budget": 0,
                "second_pass_policy": _second_pass_policy(),
            }
        )
    return requirements


def _normalize_evidence_requirements(
    raw_requirements: list[Any],
    *,
    focus_tickers: list[str],
    search_scope_tickers: list[str],
    years: list[int],
    filing_types: list[str],
    source_tiers: list[str],
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed_tickers = set(search_scope_tickers or focus_tickers)
    allowed_years = set(years)
    allowed_forms = set(filing_types)
    allowed_source_tiers = set(source_tiers)
    requirements: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalizations: list[dict[str, Any]] = []

    for index, item in enumerate(raw_requirements, start=1):
        if not isinstance(item, dict):
            warnings.append({"type": "dropped_non_object_evidence_requirement", "index": index})
            continue
        req = dict(item)
        requirement_id = _slug_text(req.get("requirement_id") or req.get("evidence_requirement_id") or f"req_{index}")[:80] or f"req_{index}"
        task_id = _slug_text(req.get("task_id") or requirement_id.replace("req_", "task_"))[:80] or f"task_{index}"
        routes = _unique_strings(req.get("evidence_routes") or req.get("retrieval_routes") or req.get("retrieval_route") or [])
        routes = [route for route in routes if route in ALLOWED_RETRIEVAL_ROUTES]
        is_run_artifact = "run_artifact" in routes
        if not routes:
            fallback_task = _requirement_as_task({**req, "task_id": task_id, "requirement_id": requirement_id})
            routes = _routes_for_task(
                task=fallback_task,
                task_text=_task_text(fallback_task),
                metric_families=_unique_strings(req.get("metric_families") or req.get("required_metric_families") or []),
                filing_types=_clamp_forms(req.get("filing_types"), allowed_forms) or filing_types,
                source_tiers=_clamp_strings(req.get("source_tiers"), allowed_source_tiers) or source_tiers,
            )
            normalizations.append({"field": "evidence_routes", "action": "derived_from_requirement_text", "requirement_id": requirement_id})
            is_run_artifact = "run_artifact" in routes
        tickers = _clamp_upper(req.get("tickers") or req.get("required_tickers"), allowed_tickers) or focus_tickers or search_scope_tickers
        years_scoped = _clamp_ints(req.get("years"), allowed_years) or years
        forms_scoped = _clamp_forms(req.get("filing_types"), allowed_forms) or filing_types
        tiers_scoped = [RUN_ARTIFACT_SOURCE_TIER] if is_run_artifact else _clamp_strings(req.get("source_tiers"), allowed_source_tiers) or source_tiers
        metric_families = _unique_strings(req.get("metric_families") or req.get("required_metric_families") or [])
        if not metric_families:
            metric_families = _unique_strings(contract.get("metric_families") or [])[:8]
        requirement = {
            "requirement_id": requirement_id,
            "task_id": task_id,
            "question_zh": _short_text(req.get("question_zh") or req.get("question") or "", 120),
            "priority": str(req.get("priority") or "supporting"),
            "analysis_intent": _short_text(req.get("analysis_intent") or "", 80),
            "tickers": tickers,
            "peer_tickers": _clamp_upper(req.get("peer_tickers"), allowed_tickers),
            "sector": _short_text(req.get("sector"), 80),
            "years": years_scoped,
            "filing_types": forms_scoped,
            "source_tiers": tiers_scoped,
            "metric_families": metric_families,
            "period_roles": _period_role_list(req.get("period_roles") or req.get("period_role") or []) or ["ANNUAL", "YTD", "QTD", "TTM"],
            "evidence_routes": routes,
            "section_hints": _unique_strings(req.get("section_hints") or [])[:8],
            "market_fields": _unique_strings(req.get("market_fields") or req.get("required_market_fields") or [])[:16],
            "coverage_requirements": dict(req.get("coverage_requirements")) if isinstance(req.get("coverage_requirements"), dict) else {},
            "candidate_budget": _clamp_int(req.get("candidate_budget"), 0, 1000, 0),
            "rerank_budget": _clamp_int(req.get("rerank_budget"), 0, 1000, 0),
            "route_selection_reason": _short_text(req.get("route_selection_reason") or req.get("route_reason") or "", 240),
            "route_cost_tier": _normalize_route_cost_tier(req.get("route_cost_tier") or req.get("cost_tier"), routes),
            "route_selection_policy": _short_text(req.get("route_selection_policy") or "cost_and_query_type_aware_v0_1", 80),
            "second_pass_policy": _normalize_second_pass_policy(req.get("second_pass_policy")),
        }
        if not requirement["tickers"] and not is_run_artifact:
            errors.append({"type": "empty_requirement_tickers", "requirement_id": requirement_id})
        if not requirement["years"] and not is_run_artifact:
            errors.append({"type": "empty_requirement_years", "requirement_id": requirement_id})
        requirements.append(requirement)
    if not requirements:
        errors.append({"type": "missing_evidence_requirements"})
    report = {
        "schema_version": "sec_agent_evidence_requirement_validation_report_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "normalizations": normalizations,
    }
    return requirements, report


def _requirement_as_task(requirement: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": requirement.get("task_id") or requirement.get("requirement_id") or "",
        "question_zh": requirement.get("question_zh") or requirement.get("question") or "",
        "priority": requirement.get("priority") or "supporting",
        "analysis_intent": requirement.get("analysis_intent") or "",
        "required_tickers": requirement.get("tickers") or requirement.get("required_tickers") or [],
        "peer_tickers": requirement.get("peer_tickers") or [],
        "years": requirement.get("years") or [],
        "filing_types": requirement.get("filing_types") or [],
        "source_tiers": requirement.get("source_tiers") or [],
        "required_metric_families": requirement.get("metric_families") or requirement.get("required_metric_families") or [],
        "period_roles": requirement.get("period_roles") or [],
        "section_hints": requirement.get("section_hints") or [],
        "required_market_fields": requirement.get("market_fields") or requirement.get("required_market_fields") or [],
        "sector": requirement.get("sector") or "",
    }


def _routes_for_requirement(requirement: dict[str, Any], fallback_routes: list[str]) -> list[str]:
    routes = _unique_strings(requirement.get("evidence_routes") or requirement.get("retrieval_routes") or requirement.get("retrieval_route") or [])
    routes = [route for route in routes if route in ALLOWED_RETRIEVAL_ROUTES]
    return routes or fallback_routes


def _normalize_route_cost_tier(value: Any, routes: list[str]) -> str:
    text = str(value or "").strip().lower()
    if text in ROUTE_COST_TIER_RANK:
        return text
    tiers = [ROUTE_COST_TIERS.get(route, "medium") for route in routes]
    if not tiers:
        return "medium"
    return max(tiers, key=lambda tier: ROUTE_COST_TIER_RANK.get(tier, 2))


def _evidence_requirement_summary(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    route_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for req in requirements:
        for route in req.get("evidence_routes") or []:
            route_counts[str(route)] = route_counts.get(str(route), 0) + 1
        for tier in req.get("source_tiers") or []:
            source_counts[str(tier)] = source_counts.get(str(tier), 0) + 1
    return {
        "requirement_count": len(requirements),
        "route_counts": dict(sorted(route_counts.items())),
        "source_tier_counts": dict(sorted(source_counts.items())),
        "second_pass_enabled": any(((req.get("second_pass_policy") or {}).get("enabled")) for req in requirements),
    }


def _routes_for_task(
    *,
    task: dict[str, Any],
    task_text: str,
    metric_families: list[str],
    filing_types: list[str],
    source_tiers: list[str],
) -> list[str]:
    routes: list[str] = []
    form_set = set(filing_types)
    tier_set = set(source_tiers)
    sec_scope = bool(
        tier_set & {PRIMARY_SEC_SOURCE_TIER, COMPANY_AUTHORED_SOURCE_TIER}
        or {"10-K", "10-Q"} & form_set
    )
    if RUN_ARTIFACT_SOURCE_TIER in tier_set:
        return ["run_artifact"]
    if metric_families and (PRIMARY_SEC_SOURCE_TIER in tier_set or "10-K" in form_set or "10-Q" in form_set):
        routes.append("ledger_first")
    if MARKET_SOURCE_TIER in tier_set or _task_requests_market(task, task_text):
        routes.append("market_snapshot")
    if INDUSTRY_SOURCE_TIER in tier_set or _task_requests_industry(task, task_text):
        routes.append("industry_snapshot")
    if COMPANY_AUTHORED_SOURCE_TIER in tier_set or "8-K" in form_set:
        if _contains_any(task_text, COMMENTARY_TERMS) or metric_families:
            routes.append("8k_commentary")
    if _contains_any(task_text, RISK_TERMS):
        routes.append("risk_text")
    if PRIMARY_SEC_SOURCE_TIER in tier_set or {"10-K", "10-Q"} & form_set:
        if _contains_any(task_text, (*COMMENTARY_TERMS, *RISK_TERMS)) or not metric_families:
            routes.append("filing_text")
        elif not routes or set(routes) == {"ledger_first"}:
            routes.append("filing_text")
    if sec_scope and _task_requests_semantic_recall(task, task_text):
        routes.append("milvus_semantic")
    return _dedupe_keep_order(routes or ["filing_text"])


def _task_requests_semantic_recall(task: dict[str, Any], task_text: str) -> bool:
    text = " ".join(
        [
            task_text,
            str(task.get("analysis_intent") or ""),
            " ".join(str(item) for item in task.get("source_families") or []),
            " ".join(str(item) for item in task.get("evidence_source_needed") or []),
        ]
    )
    return _contains_any(text, SEMANTIC_RECALL_TERMS)


def _contract_requests_semantic_recall(contract: dict[str, Any], case: dict[str, Any]) -> bool:
    text_parts: list[str] = [
        str(contract.get("user_query") or ""),
        str(contract.get("prompt") or ""),
        str(contract.get("source_policy") or ""),
        str(case.get("prompt") or ""),
        str(case.get("case_id") or ""),
    ]
    for task in contract.get("decomposed_tasks") or []:
        if not isinstance(task, dict):
            continue
        text_parts.extend(
            [
                str(task.get("question_zh") or ""),
                str(task.get("question") or ""),
                str(task.get("analysis_intent") or ""),
                " ".join(str(item) for item in task.get("source_families") or []),
                " ".join(str(item) for item in task.get("evidence_source_needed") or []),
            ]
        )
    return _contains_any(" ".join(text_parts), SEMANTIC_RECALL_TERMS)


def _semantic_recall_forbidden_for_requirement(requirement: dict[str, Any], *, task_text: str, case: dict[str, Any]) -> bool:
    contract = case.get("query_contract") if isinstance(case.get("query_contract"), dict) else {}
    mode = str(case.get("expected_execution_mode") or contract.get("expected_execution_mode") or contract.get("execution_mode") or "").strip()
    category = str(case.get("category") or contract.get("category") or "").strip()
    if mode == "deterministic_lookup" or category == "exact_lookup":
        return True
    text = " ".join(
        [
            task_text,
            str(requirement.get("route_selection_reason") or ""),
            str(requirement.get("question") or ""),
            str(requirement.get("question_zh") or ""),
            str(contract.get("task_type") or ""),
            str(contract.get("case_id") or ""),
        ]
    ).lower()
    routes = set(_unique_strings(requirement.get("evidence_routes") or requirement.get("retrieval_routes") or []))
    metric_families = _unique_strings(
        requirement.get("metric_families")
        or requirement.get("required_metric_families")
        or contract.get("metric_families")
        or []
    )
    exact_markers = (
        "deterministic",
        "single metric",
        "single exact",
        "单一指标",
        "单一精确",
        "只回答",
    )
    if "ledger_first" in routes and metric_families and any(marker in text for marker in exact_markers):
        return True
    return any(
        marker in text
        for marker in (
            "no semantic",
            "no milvus",
            "semantic route not needed",
            "不需要语义",
            "无需语义",
            "不要语义",
            "不走语义",
            "不走 milvus",
            "无需 milvus",
        )
    )


def _semantic_recall_scope_allowed(source_tiers: list[str], filing_types: list[str]) -> bool:
    return bool(
        set(source_tiers) & {PRIMARY_SEC_SOURCE_TIER, COMPANY_AUTHORED_SOURCE_TIER}
        or {"10-K", "10-Q"} & set(filing_types)
    )


def _route_budgets(route_name: str, *, ticker_count: int, family_count: int) -> dict[str, int]:
    scale = max(1, min(4, (ticker_count + 19) // 20))
    if route_name == "ledger_first":
        return {"candidate_budget": min(500, max(24, ticker_count * max(1, family_count) * 2)), "rerank_budget": 0}
    if route_name == "market_snapshot":
        return {"candidate_budget": min(200, max(16, ticker_count * 2)), "rerank_budget": 0}
    if route_name == "industry_snapshot":
        return {"candidate_budget": 80, "rerank_budget": 0}
    if route_name == "milvus_semantic":
        return {"candidate_budget": 120 * scale, "rerank_budget": 0}
    if route_name == "8k_commentary":
        return {"candidate_budget": 80 * scale, "rerank_budget": 40 * scale}
    if route_name == "risk_text":
        return {"candidate_budget": 80 * scale, "rerank_budget": 40 * scale}
    return {"candidate_budget": 120 * scale, "rerank_budget": 64 * scale}


def _route_filing_types(route_name: str, filing_types: list[str]) -> list[str]:
    if route_name == "run_artifact":
        return []
    if route_name == "8k_commentary":
        return ["8-K"] if "8-K" in set(filing_types) else filing_types
    if route_name == "industry_snapshot":
        return []
    if route_name in {"ledger_first", "filing_text", "risk_text", "milvus_semantic"}:
        scoped = [form for form in filing_types if form in {"10-K", "10-Q"}]
        return scoped or filing_types
    return []


def _route_source_tiers(route_name: str, source_tiers: list[str]) -> list[str]:
    if route_name == "run_artifact":
        return [RUN_ARTIFACT_SOURCE_TIER]
    if route_name == "market_snapshot":
        return [MARKET_SOURCE_TIER] if MARKET_SOURCE_TIER in set(source_tiers) else []
    if route_name == "industry_snapshot":
        return [INDUSTRY_SOURCE_TIER] if INDUSTRY_SOURCE_TIER in set(source_tiers) else []
    if route_name == "8k_commentary":
        return [COMPANY_AUTHORED_SOURCE_TIER] if COMPANY_AUTHORED_SOURCE_TIER in set(source_tiers) else []
    if route_name in {"ledger_first", "filing_text", "risk_text", "milvus_semantic"}:
        scoped = [tier for tier in source_tiers if tier in {PRIMARY_SEC_SOURCE_TIER, COMPANY_AUTHORED_SOURCE_TIER}]
        return scoped
    return source_tiers


def _section_hints(route_name: str) -> list[str]:
    if route_name == "run_artifact":
        return ["artifact_index", "graph_state", "coverage_summary"]
    if route_name == "ledger_first":
        return ["financial_statements", "segment_tables", "cash_flow_tables"]
    if route_name == "8k_commentary":
        return ["item_2_02", "exhibit_99_1", "earnings_release"]
    if route_name == "market_snapshot":
        return ["market_analytics", "event_window", "valuation_snapshot"]
    if route_name == "industry_snapshot":
        return ["industry_observations", "sector_context", "macro_context"]
    if route_name == "milvus_semantic":
        return ["typed_semantic_vector", "semantic_scope", "vector_kind_filter"]
    if route_name == "risk_text":
        return ["risk_factors", "md&a_risk", "business_risk"]
    return ["md&a", "business", "segment_discussion"]


def _summary(plan: dict[str, Any]) -> dict[str, Any]:
    routes = [route for route in plan.get("routes") or [] if isinstance(route, dict)]
    counts: dict[str, int] = {}
    bge_budget = 0
    candidate_budget = 0
    for route in routes:
        route_name = str(route.get("retrieval_route") or "")
        counts[route_name] = counts.get(route_name, 0) + 1
        bge_budget += int(route.get("rerank_budget") or 0)
        candidate_budget += int(route.get("candidate_budget") or 0)
    return {
        "task_count": len([task for task in plan.get("tasks") or [] if isinstance(task, dict)]),
        "route_count": len(routes),
        "route_counts": dict(sorted(counts.items())),
        "candidate_budget_total": candidate_budget,
        "rerank_budget_total": bge_budget,
        "second_pass_enabled": any(((route.get("second_pass_policy") or {}).get("enabled")) for route in routes),
    }


def _fallback_task(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": "task_1",
        "question_zh": "Answer the user question under the validated source policy.",
        "priority": "primary",
        "required_tickers": contract.get("focus_tickers") or [],
        "required_metric_families": contract.get("metric_families") or [],
    }


def _analysis_intent(task: dict[str, Any], contract: dict[str, Any], routes: list[str]) -> str:
    if "market_snapshot" in routes and "ledger_first" in routes:
        return "fundamental_vs_market_reaction"
    if "8k_commentary" in routes and "ledger_first" in routes:
        return "fundamental_with_management_explanation"
    if "risk_text" in routes:
        return "risk_and_counterargument"
    return str(task.get("analysis_intent") or contract.get("task_type") or "sec_evidence_analysis")


def _second_pass_policy() -> dict[str, Any]:
    return {
        "enabled": True,
        "max_passes": 1,
        "trigger": "coverage_matrix_searchable_in_current_inventory",
        "external_gap_behavior": "report_boundary_without_autosearch",
    }


def _normalize_second_pass_policy(value: Any) -> dict[str, Any]:
    policy = dict(value) if isinstance(value, dict) else {}
    normalized = _second_pass_policy()
    normalized.update({key: policy[key] for key in policy if key in normalized})
    normalized["enabled"] = bool(normalized.get("enabled"))
    normalized["max_passes"] = _clamp_int(normalized.get("max_passes"), 0, 2, 1)
    return normalized


def _task_id(task: dict[str, Any], index: int) -> str:
    raw = str(task.get("task_id") or f"task_{index}").strip().lower()
    slug = re.sub(r"[^a-z0-9_:-]+", "_", raw).strip("_")
    return slug[:80] or f"task_{index}"


def _slug_text(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9_:-]+", "_", raw).strip("_")


def _short_text(value: Any, max_chars: int) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:max_chars]


def _task_text(task: dict[str, Any]) -> str:
    parts = [
        task.get("question_zh"),
        task.get("question"),
        task.get("analysis_intent"),
        " ".join(str(item) for item in task.get("required_metric_families") or []),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _task_tickers(task: dict[str, Any], focus_tickers: list[str], search_scope_tickers: list[str]) -> list[str]:
    explicit = _unique_upper(task.get("required_tickers") or task.get("tickers") or [])
    allowed = set(search_scope_tickers)
    scoped = [ticker for ticker in explicit if ticker in allowed]
    return scoped or focus_tickers or search_scope_tickers


def _task_peer_tickers(
    task: dict[str, Any],
    task_tickers: list[str],
    focus_tickers: list[str],
    search_scope_tickers: list[str],
) -> list[str]:
    explicit = _unique_upper(task.get("peer_tickers") or [])
    allowed = set(search_scope_tickers)
    return [ticker for ticker in explicit if ticker in allowed and ticker not in set(task_tickers)]


def _period_roles(task: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    roles = _period_role_list(task.get("period_roles") or task.get("period_role") or contract.get("period_roles") or [])
    return roles or ["ANNUAL", "YTD", "QTD", "TTM"]


def _period_role_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    roles = []
    for item in raw_items:
        role = str(item or "").strip().upper()
        if role in PERIOD_ROLES and role not in roles:
            roles.append(role)
    return roles


def _market_fields_for_task(task: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    if isinstance(task.get("required_market_fields"), list):
        return _unique_strings(task.get("required_market_fields") or [])
    market = contract.get("market_snapshot") if isinstance(contract.get("market_snapshot"), dict) else {}
    return _unique_strings(market.get("fields") or market.get("required_fields") or [])


def _task_requests_market(task: dict[str, Any], task_text: str) -> bool:
    return bool(task.get("required_market_fields") or task.get("required_market_tools") or _contains_any(task_text, MARKET_TERMS))


def _task_requests_industry(task: dict[str, Any], task_text: str) -> bool:
    source_families = task.get("source_families") or task.get("industry_source_families") or []
    return bool(source_families or _contains_any(task_text, INDUSTRY_CONTEXT_TERMS))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(term.lower() in lowered for term in terms)


def _unique_upper(value: Any) -> list[str]:
    return _dedupe_keep_order(str(item).upper().strip() for item in _iterable(value) if str(item or "").strip())


def _unique_strings(value: Any) -> list[str]:
    return _dedupe_keep_order(str(item).strip() for item in _iterable(value) if str(item or "").strip())


def _unique_ints(value: Any) -> list[int]:
    out = []
    seen = set()
    for item in _iterable(value):
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        if number not in seen:
            seen.add(number)
            out.append(number)
    return out


def _unique_form_types(value: Any) -> list[str]:
    forms = []
    for item in _iterable(value):
        form = str(item or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")
        if form and form not in forms:
            forms.append(form)
    return forms


def _iterable(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _dedupe_keep_order(items: Any) -> list[Any]:
    out = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _clamp_upper(value: Any, allowed: set[str]) -> list[str]:
    items = _unique_upper(value)
    return [item for item in items if not allowed or item in allowed]


def _clamp_strings(value: Any, allowed: set[str]) -> list[str]:
    items = _unique_strings(value)
    return [item for item in items if not allowed or item in allowed]


def _clamp_forms(value: Any, allowed: set[str]) -> list[str]:
    items = _unique_form_types(value)
    return [item for item in items if not allowed or item in allowed]


def _clamp_ints(value: Any, allowed: set[int]) -> list[int]:
    items = _unique_ints(value)
    return [item for item in items if not allowed or item in allowed]


def _clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))
