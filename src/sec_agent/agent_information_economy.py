"""Agent information-economy ledger derived from saved runtime artifacts.

The ledger is intentionally deterministic: it does not call models or
retrieval tools. It turns scattered token, specialist, claim, and quality
signals into a single audit object that can explain why a run spent tokens
and whether those tokens produced memo-ready judgment.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


AGENT_INFORMATION_ECONOMY_SCHEMA_VERSION = "finsight_agent_information_economy_ledger_v0_1"


BLOCKING_ISSUES = {
    "high_token_low_supported_claim_yield",
    "high_token_low_rendered_claim_yield",
    "overbroad_specialist_fanout",
    "specialist_without_required_item_match",
    "invalid_information_transfer_proxy",
    "duplicate_evidence_ref_transfer_proxy",
    "prompt_pack_overlap_proxy",
    "repair_loop_agent_failure_proxy",
    "memo_writer_raw_gate_or_salvage_failure",
    "memo_payload_not_dense_enough",
}


def build_agent_information_economy_summary(
    summary: Mapping[str, Any],
    *,
    output_quality_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a run-level information-economy ledger from an eval summary."""

    quality_by_case = {
        str(case.get("case_id") or ""): case
        for case in (output_quality_audit or {}).get("cases") or []
        if isinstance(case, Mapping)
    }
    cases = [
        build_agent_information_economy_case(case, output_quality_case=quality_by_case.get(str(case.get("case_id") or "")))
        for case in summary.get("cases") or []
        if isinstance(case, Mapping)
    ]
    issue_counts: Counter[str] = Counter()
    for case in cases:
        issue_counts.update(case.get("issues") or [])
    failed_cases = [case.get("case_id") for case in cases if case.get("gate_status") == "fail"]
    return {
        "schema_version": AGENT_INFORMATION_ECONOMY_SCHEMA_VERSION,
        "run_id": str(summary.get("run_id") or ""),
        "diagnostic_only": True,
        "status": "pass" if not failed_cases else "fail",
        "case_count": len(cases),
        "failed_case_ids": failed_cases,
        "issue_counts": dict(sorted(issue_counts.items())),
        "aggregate_metrics": _aggregate_metrics(cases),
        "cases": cases,
        "policy": "token_spend_must_map_to_role_specific_memo_ready_judgment_v0_1",
    }


def build_preflight_information_economy(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Build a no-paid preflight information-economy plan from token estimates."""

    cases: list[dict[str, Any]] = []
    for case in plan.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        nodes = [row for row in case.get("nodes") or [] if isinstance(row, Mapping)]
        specialist_nodes = [
            row
            for row in nodes
            if str(row.get("node") or "").endswith("_analyst")
            or str(row.get("node") or "")
            in {
                "fundamental_analyst",
                "product_technology_analyst",
                "industry_supply_chain_analyst",
                "market_valuation_analyst",
                "risk_counterevidence_analyst",
            }
        ]
        total_tokens = int(case.get("estimated_total_tokens") or 0)
        paid_calls = int(case.get("estimated_paid_call_count") or len(nodes))
        issues: list[str] = []
        if total_tokens >= 120000:
            issues.append("preflight_case_token_budget_high")
        if paid_calls > 8:
            issues.append("preflight_paid_call_fanout_high")
        if len(specialist_nodes) > 4:
            issues.append("preflight_specialist_fanout_broad")
        pruned_from_quality = _string_list(case.get("pruned_from_quality_expected_specialist_agents"))
        prunable_agents = _string_list(case.get("prunable_specialist_agents")) or pruned_from_quality
        if _string_list(case.get("prunable_specialist_agents")):
            issues.append("preflight_specialist_pruning_available")
        cases.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "status": "fail" if issues else "pass",
                "estimated_total_tokens": total_tokens,
                "estimated_paid_call_count": paid_calls,
                "estimated_specialist_count": int(case.get("estimated_specialist_count") or len(specialist_nodes)),
                "quality_expected_specialist_agents": _string_list(case.get("quality_expected_specialist_agents")),
                "expected_specialist_agents": _string_list(case.get("expected_specialist_agents")),
                "expected_paid_specialist_priorities": dict(case.get("expected_paid_specialist_priorities") or {})
                if isinstance(case.get("expected_paid_specialist_priorities"), Mapping)
                else {},
                "cost_aware_specialist_agents": _string_list(case.get("cost_aware_specialist_agents")),
                "pruned_from_quality_expected_specialist_agents": pruned_from_quality,
                "prunable_specialist_agents": prunable_agents,
                "estimated_total_tokens_after_specialist_pruning": int(
                    case.get("estimated_total_tokens_after_specialist_pruning") or 0
                ),
                "estimated_paid_call_count_after_specialist_pruning": int(
                    case.get("estimated_paid_call_count_after_specialist_pruning") or 0
                ),
                "issues": issues,
                "nodes": nodes,
            }
        )
    issue_counts: Counter[str] = Counter()
    for case in cases:
        issue_counts.update(case.get("issues") or [])
    return {
        "schema_version": AGENT_INFORMATION_ECONOMY_SCHEMA_VERSION,
        "run_id": str(plan.get("run_id") or ""),
        "diagnostic_only": True,
        "preflight_only": True,
        "status": "pass" if not issue_counts and bool(plan.get("allowed", True)) else "fail",
        "plan_status": str(plan.get("status") or ""),
        "estimated_total_tokens": int(plan.get("estimated_total_tokens") or 0),
        "estimated_paid_call_count": int(plan.get("estimated_paid_call_count") or 0),
        "issue_counts": dict(sorted(issue_counts.items())),
        "scheduler_advice": dict(plan.get("scheduler_advice") or {})
        if isinstance(plan.get("scheduler_advice"), Mapping)
        else {},
        "cases": cases,
        "policy": "preflight_information_economy_blocks_expensive_unreviewed_runs_v0_1",
    }


def build_agent_information_economy_case(
    case: Mapping[str, Any],
    *,
    output_quality_case: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a case-level ledger row from one real-chain case score."""

    quality = output_quality_case if isinstance(output_quality_case, Mapping) else {}
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    tokens = _token_stats(agent_audit, quality)
    specialists = _specialist_stats(case, quality)
    claim_metrics = _claim_metrics(case, quality)
    transfer = _information_transfer_metrics(case, quality, specialists=specialists)
    repair = _repair_metrics(agent_audit, quality)
    issues = _case_issues(
        case,
        quality,
        tokens=tokens,
        specialists=specialists,
        claim_metrics=claim_metrics,
        transfer=transfer,
        repair=repair,
    )
    return {
        "schema_version": AGENT_INFORMATION_ECONOMY_SCHEMA_VERSION,
        "case_id": str(case.get("case_id") or ""),
        "category": str(case.get("category") or ""),
        "execution_mode": str(case.get("execution_mode") or ""),
        "gate_status": "fail" if any(issue in BLOCKING_ISSUES for issue in issues) else "pass",
        "tokens": tokens,
        "specialists": specialists,
        "claim_metrics": claim_metrics,
        "information_transfer": transfer,
        "repair_loop": repair,
        "quality_flags": _string_list(quality.get("quality_flags")),
        "issues": issues,
        "root_cause_candidates": _root_cause_candidates(issues, quality),
        "policy": "case_token_spend_must_have_role_specific_claim_yield_v0_1",
    }


def _token_stats(agent_audit: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    quality_tokens = quality.get("token_stats") if isinstance(quality.get("token_stats"), Mapping) else {}
    if quality_tokens:
        return {
            "total_tokens": int(quality_tokens.get("total_tokens") or 0),
            "research_lead_tokens": int(quality_tokens.get("research_lead_tokens") or 0),
            "specialist_tokens": int(quality_tokens.get("specialist_tokens") or 0),
            "memo_writer_tokens": int(quality_tokens.get("memo_writer_tokens") or 0),
            "verifier_tokens": int(quality_tokens.get("verifier_tokens") or 0),
        }

    def route_tokens(key: str) -> int:
        node = agent_audit.get(key) if isinstance(agent_audit.get(key), Mapping) else {}
        diagnostics = node.get("diagnostics") if isinstance(node.get("diagnostics"), Mapping) else {}
        return int(diagnostics.get("total_tokens") or 0)

    specialists = agent_audit.get("specialists") if isinstance(agent_audit.get("specialists"), Mapping) else {}
    specialist_tokens = sum(
        int(row.get("total_tokens") or 0)
        for row in specialists.get("route_results") or []
        if isinstance(row, Mapping)
    )
    return {
        "total_tokens": route_tokens("research_lead")
        + route_tokens("universe_relationship")
        + route_tokens("memo_writer")
        + route_tokens("verifier")
        + specialist_tokens,
        "research_lead_tokens": route_tokens("research_lead"),
        "specialist_tokens": specialist_tokens,
        "memo_writer_tokens": route_tokens("memo_writer"),
        "verifier_tokens": route_tokens("verifier"),
    }


def _specialist_stats(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    quality_specialists = quality.get("specialist_stats") if isinstance(quality.get("specialist_stats"), Mapping) else {}
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    audit_specialists = agent_audit.get("specialists") if isinstance(agent_audit.get("specialists"), Mapping) else {}
    quality_routes = (
        quality_specialists.get("route_results")
        if isinstance(quality_specialists.get("route_results"), (list, tuple))
        else None
    )
    audit_routes = [row for row in audit_specialists.get("route_results") or [] if isinstance(row, Mapping)]
    # Prefer the runtime route summary when it carries prompt-row counts. The
    # quality audit may retain data-view row counts, which are useful
    # diagnostics but are not the actual specialist model input.
    if any(row.get("prompt_bounded_evidence_row_count") is not None for row in audit_routes):
        routes = audit_routes
    elif quality_routes is not None:
        routes = [row for row in quality_routes if isinstance(row, Mapping)]
    else:
        routes = audit_routes
    active_routes = [row for row in routes if _active_specialist_route(row)]
    active_agents = [str(row.get("agent_id") or "") for row in active_routes if str(row.get("agent_id") or "")]
    activation_decisions = [
        dict(row)
        for row in audit_specialists.get("activation_decisions") or []
        if isinstance(row, Mapping)
    ]
    quality_input_rows_by_agent = (
        quality_specialists.get("input_rows_by_agent")
        if isinstance(quality_specialists.get("input_rows_by_agent"), Mapping)
        else {}
    )
    prompt_rows_by_agent = {
        str(row.get("agent_id") or ""): int(row.get("prompt_bounded_evidence_row_count") or 0)
        for row in active_routes
        if isinstance(row, Mapping)
        and str(row.get("agent_id") or "")
        and row.get("prompt_bounded_evidence_row_count") is not None
    }
    input_rows_by_agent = prompt_rows_by_agent or {
        str(key): int(value or 0) for key, value in dict(quality_input_rows_by_agent).items()
    }
    data_view_rows_by_agent = {
        str(key): int(value or 0) for key, value in dict(quality_input_rows_by_agent).items()
    }
    real_quality = audit_specialists.get("real_evidence_quality") if isinstance(audit_specialists.get("real_evidence_quality"), Mapping) else {}
    details = real_quality.get("details") if isinstance(real_quality.get("details"), Mapping) else {}
    zero_claim_agents = []
    no_required_item_agents = []
    for agent_id in active_agents:
        detail = details.get(agent_id) if isinstance(details.get(agent_id), Mapping) else {}
        checks = detail.get("checks") if isinstance(detail.get("checks"), Mapping) else {}
        if str(detail.get("status") or "") == "fail" and not any(bool(value) for value in checks.values()):
            zero_claim_agents.append(agent_id)
    if activation_decisions:
        for row in activation_decisions:
            if not _activation_decision_requires_required_item(row):
                continue
            no_required_item_agents.append(str(row.get("agent_id") or ""))
    for row in active_routes:
        if not isinstance(row, Mapping):
            continue
        matched = int(row.get("matched_requirement_count") or 0)
        reason = str(row.get("activation_reason") or row.get("reason") or row.get("failure_reason") or "")
        priority = str(row.get("priority") or "")
        explicit_intent = bool(row.get("explicit_intent"))
        if (
            str(row.get("agent_id") or "")
            and matched == 0
            and not explicit_intent
            and (priority in {"supporting", "conditional", "low"} or "required_item" in reason)
        ):
            no_required_item_agents.append(str(row.get("agent_id") or ""))
    return {
        "active_count": len(active_agents),
        "active_agents": active_agents,
        "route_count": int(quality_specialists.get("route_count") or len(active_agents)),
        "route_result_count": len(routes),
        "skipped_route_count": max(0, len(routes) - len(active_routes)),
        "activation_decisions": activation_decisions,
        "input_rows_by_agent": input_rows_by_agent,
        "input_row_measurement_boundary": (
            "prompt_bounded_evidence_row_count_from_route_summary"
            if prompt_rows_by_agent
            else "quality_specialist_stats_input_rows_by_agent"
        ),
        "data_view_rows_by_agent": data_view_rows_by_agent,
        "unsupported_claim_count": int(quality_specialists.get("unsupported_claim_count") or 0),
        "zero_claim_or_failed_agents": sorted(set(zero_claim_agents)),
        "agents_without_required_item_match": sorted(set(no_required_item_agents)),
    }


def _active_specialist_route(row: Mapping[str, Any]) -> bool:
    agent_id = str(row.get("agent_id") or "")
    if not agent_id:
        return False
    status = str(row.get("status") or "").strip().lower()
    decision = str(row.get("activation_decision") or "").strip().lower()
    return status != "skipped" and decision != "skipped"


def _activation_decision_requires_required_item(row: Mapping[str, Any]) -> bool:
    agent_id = str(row.get("agent_id") or "")
    if not agent_id or str(row.get("decision") or "").strip().lower() != "run":
        return False
    if int(row.get("matched_requirement_count") or 0) > 0 or bool(row.get("explicit_intent")):
        return False
    priority = str(row.get("priority") or "").strip().lower()
    reason = str(row.get("reason") or "").strip().lower()
    if reason in {
        "fundamental_core_financial_rows_visible",
        "relationship_rows_visible_for_industry_lens",
        "primary_specialist_allowed_by_core_role",
    }:
        return False
    return priority in {"supporting", "conditional", "low"} or agent_id in {
        "product_technology_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
    }


def _claim_metrics(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    cost = quality.get("cost_quality_stats") if isinstance(quality.get("cost_quality_stats"), Mapping) else {}
    specialists = quality.get("specialist_stats") if isinstance(quality.get("specialist_stats"), Mapping) else {}
    claim_card_stats = specialists.get("claim_card_stats") if isinstance(specialists.get("claim_card_stats"), Mapping) else {}
    supported_claims = int(claim_card_stats.get("supported_claim_count") or 0)
    memo_claims = int(case.get("memo_claim_count") or quality.get("memo_claim_count") or 0)
    rendered_chars = int(case.get("rendered_answer_chars") or quality.get("rendered_answer_chars") or 0)
    return {
        "supported_claim_card_count": supported_claims,
        "memo_claim_count": memo_claims,
        "rendered_answer_chars": rendered_chars,
        "tokens_per_supported_claim_card": _coalesce_float(cost.get("tokens_per_supported_claim_card")),
        "tokens_per_rendered_memo_claim": _coalesce_float(cost.get("tokens_per_rendered_memo_claim")),
        "memo_chars_per_total_token": _coalesce_float(cost.get("memo_chars_per_total_token")),
    }


def _information_transfer_metrics(
    case: Mapping[str, Any],
    quality: Mapping[str, Any],
    *,
    specialists: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_refs = _nested_evidence_refs(case)
    duplicate_refs = sorted(ref for ref, count in Counter(evidence_refs).items() if count >= 3)
    prompt_pack_overlap = _prompt_pack_overlap_metrics(case, quality)
    research_lead_input_pack = _research_lead_input_pack_metrics(case, quality)
    universe_relationship_input_pack = _universe_relationship_input_pack_metrics(case, quality)
    memo_writer_input_pack = _memo_writer_input_pack_metrics(case, quality)
    verifier_input_pack = _verifier_input_pack_metrics(case, quality)
    input_rows = [int(value or 0) for value in (specialists.get("input_rows_by_agent") or {}).values()]
    quality_flags = set(_string_list(quality.get("quality_flags")))
    invalid_proxy = bool(
        "specialist_claim_yield_low" in quality_flags
        or "many_unsupported_specialist_claims" in quality_flags
        or specialists.get("unsupported_claim_count", 0) >= 8
    )
    return {
        "duplicate_evidence_ref_count": len(duplicate_refs),
        "duplicate_evidence_refs_sample": duplicate_refs[:12],
        "prompt_pack_overlap": prompt_pack_overlap,
        "research_lead_input_pack": research_lead_input_pack,
        "universe_relationship_input_pack": universe_relationship_input_pack,
        "memo_writer_input_pack": memo_writer_input_pack,
        "verifier_input_pack": verifier_input_pack,
        "max_specialist_input_rows": max(input_rows or [0]),
        "min_specialist_input_rows": min(input_rows or [0]) if input_rows else 0,
        "invalid_information_transfer_proxy": invalid_proxy,
        "duplicate_context_proxy": bool(duplicate_refs),
        "prompt_pack_overlap_proxy": bool(prompt_pack_overlap.get("overlap_detected")),
        "measurement_boundary": prompt_pack_overlap.get("measurement_boundary")
        or "Proxy from saved artifacts; exact cross-agent prompt-token overlap requires prompt-pack capture.",
    }


def _repair_metrics(agent_audit: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    memo = agent_audit.get("memo_writer") if isinstance(agent_audit.get("memo_writer"), Mapping) else {}
    route = memo.get("route_result") if isinstance(memo.get("route_result"), Mapping) else {}
    diagnostics = memo.get("diagnostics") if isinstance(memo.get("diagnostics"), Mapping) else {}
    cost = quality.get("cost_quality_stats") if isinstance(quality.get("cost_quality_stats"), Mapping) else {}
    attempt_count = int(route.get("attempt_count") or cost.get("memo_writer_attempt_count") or diagnostics.get("call_count") or 0)
    repair_attempts = int(route.get("repair_attempts") or cost.get("memo_writer_repair_attempts") or max(0, attempt_count - 1))
    raw_output_audit = route.get("raw_output_audit") if isinstance(route.get("raw_output_audit"), Mapping) else {}
    raw_gate_failed = str(raw_output_audit.get("deterministic_gate_status") or "").lower() == "fail"
    deterministic_salvage_used = bool(route.get("deterministic_salvage_used") or raw_output_audit.get("salvage_triggered"))
    return {
        "memo_writer_attempt_count": attempt_count,
        "memo_writer_repair_attempts": repair_attempts,
        "memo_writer_repair_attempt_ratio": _coalesce_float(cost.get("memo_writer_repair_attempt_ratio")),
        "memo_writer_repair_token_ratio": _coalesce_float(cost.get("memo_writer_repair_token_ratio")),
        "memo_writer_raw_gate_failed": raw_gate_failed,
        "memo_writer_deterministic_salvage_used": deterministic_salvage_used,
        "memo_writer_raw_gate_error_types": _string_list(raw_output_audit.get("deterministic_gate_error_types"))[:12],
    }


def _case_issues(
    case: Mapping[str, Any],
    quality: Mapping[str, Any],
    *,
    tokens: Mapping[str, Any],
    specialists: Mapping[str, Any],
    claim_metrics: Mapping[str, Any],
    transfer: Mapping[str, Any],
    repair: Mapping[str, Any],
) -> list[str]:
    issues = set(_string_list(quality.get("quality_flags")))
    total_tokens = int(tokens.get("total_tokens") or 0)
    supported_claims = int(claim_metrics.get("supported_claim_card_count") or 0)
    memo_claims = int(claim_metrics.get("memo_claim_count") or 0)
    active_count = int(specialists.get("active_count") or 0)
    if total_tokens >= 60000 and supported_claims < 8:
        issues.add("high_token_low_supported_claim_yield")
    if total_tokens >= 60000 and memo_claims < 4:
        issues.add("high_token_low_rendered_claim_yield")
    if str(case.get("execution_mode") or "") == "deep_research" and active_count > 4:
        issues.add("overbroad_specialist_fanout")
    if specialists.get("agents_without_required_item_match"):
        issues.add("specialist_without_required_item_match")
    if transfer.get("invalid_information_transfer_proxy"):
        issues.add("invalid_information_transfer_proxy")
    if transfer.get("duplicate_context_proxy"):
        issues.add("duplicate_evidence_ref_transfer_proxy")
    if transfer.get("prompt_pack_overlap_proxy"):
        issues.add("prompt_pack_overlap_proxy")
    if int(repair.get("memo_writer_repair_attempts") or 0) > 0 and (
        "memo_payload_not_dense_enough" in issues
        or "memo_surface_boundary_heavy_or_noncommittal" in issues
        or "specialist_claim_yield_low" in issues
    ):
        issues.add("repair_loop_agent_failure_proxy")
    if repair.get("memo_writer_raw_gate_failed") or repair.get("memo_writer_deterministic_salvage_used"):
        issues.add("memo_writer_raw_gate_or_salvage_failure")
    return sorted(issues)


def _root_cause_candidates(issues: Sequence[str], quality: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    diagnosis = quality.get("claim_yield_diagnosis") if isinstance(quality.get("claim_yield_diagnosis"), Mapping) else {}
    candidates.extend(_string_list(diagnosis.get("suspected_root_layers")))
    mapping = {
        "overbroad_specialist_fanout": "research_lead_activation_breadth",
        "specialist_without_required_item_match": "research_lead_required_item_to_specialist_routing",
        "invalid_information_transfer_proxy": "specialist_role_specific_selector_or_claim_conversion",
        "duplicate_evidence_ref_transfer_proxy": "context_pack_deduplication",
        "prompt_pack_overlap_proxy": "specialist_input_pack_deduplication_or_coalescing",
        "repair_loop_agent_failure_proxy": "repair_loop_due_to_agent_quality_not_external_gap",
        "memo_writer_raw_gate_or_salvage_failure": "memo_raw_output_to_normalized_writer_contract",
        "memo_payload_not_dense_enough": "memo_logic_plan_to_writer_payload",
        "high_token_low_supported_claim_yield": "agent_information_transfer_quality",
        "high_token_low_rendered_claim_yield": "memo_projection_or_writer_thesis_selection",
    }
    for issue in issues:
        if issue in mapping:
            candidates.append(mapping[issue])
    return _dedupe(candidates)


def _aggregate_metrics(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total_tokens = sum(int((case.get("tokens") or {}).get("total_tokens") or 0) for case in cases)
    supported_claims = sum(int((case.get("claim_metrics") or {}).get("supported_claim_card_count") or 0) for case in cases)
    memo_claims = sum(int((case.get("claim_metrics") or {}).get("memo_claim_count") or 0) for case in cases)
    return {
        "total_tokens": total_tokens,
        "supported_claim_card_count": supported_claims,
        "memo_claim_count": memo_claims,
        "tokens_per_supported_claim_card": _safe_ratio(total_tokens, supported_claims),
        "tokens_per_rendered_memo_claim": _safe_ratio(total_tokens, memo_claims),
    }


def _nested_evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key in ("evidence_refs", "refs", "supporting_evidence_ids", "evidence_ref", "evidence_id", "source_fact_id", "raw_record_ref"):
            refs.extend(_string_list(value.get(key)))
        for item in value.values():
            if isinstance(item, (Mapping, list)):
                refs.extend(_nested_evidence_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_nested_evidence_refs(item))
    return [ref for ref in refs if ref]


def _prompt_pack_overlap_metrics(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    routes = _specialist_route_rows(case, quality)
    fingerprints = [
        row.get("input_pack_fingerprint")
        for row in routes
        if isinstance(row.get("input_pack_fingerprint"), Mapping)
    ]
    fingerprints = [dict(item) for item in fingerprints if isinstance(item, Mapping)]
    if not fingerprints:
        return {
            "available": False,
            "overlap_detected": False,
            "measurement_boundary": "no_prompt_pack_fingerprint_in_saved_artifacts",
        }

    ref_agents: dict[str, set[str]] = {}
    same_component_digest_rows: list[dict[str, Any]] = []
    component_digest_agents: dict[tuple[str, str], set[str]] = {}
    for fingerprint in fingerprints:
        agent_id = str(fingerprint.get("agent_id") or "")
        for ref in _string_list(fingerprint.get("known_evidence_refs")):
            ref_agents.setdefault(ref, set()).add(agent_id)
        components = fingerprint.get("component_summaries") if isinstance(fingerprint.get("component_summaries"), Mapping) else {}
        for component, summary in components.items():
            if not isinstance(summary, Mapping):
                continue
            digest = str(summary.get("digest") or "")
            item_count = int(summary.get("item_count") or 0)
            if not digest or item_count <= 0:
                continue
            component_digest_agents.setdefault((str(component), digest), set()).add(agent_id)

    duplicate_refs = {
        ref: sorted(agents)
        for ref, agents in ref_agents.items()
        if len(agents) >= 2
    }
    for (component, digest), agents in sorted(component_digest_agents.items()):
        if len(agents) < 2:
            continue
        same_component_digest_rows.append(
            {
                "component": component,
                "digest": digest,
                "agents": sorted(agents),
            }
        )

    overlap_detected = bool(same_component_digest_rows) or len(duplicate_refs) >= 8
    return {
        "available": True,
        "overlap_detected": overlap_detected,
        "specialist_fingerprint_count": len(fingerprints),
        "duplicate_prompt_evidence_ref_count": len(duplicate_refs),
        "duplicate_prompt_evidence_refs_sample": [
            {"evidence_ref": ref, "agents": agents}
            for ref, agents in sorted(duplicate_refs.items())[:12]
        ],
        "same_component_digest_count": len(same_component_digest_rows),
        "same_component_digest_sample": same_component_digest_rows[:12],
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
        "measurement_boundary": (
            "Uses saved specialist input-pack fingerprints with evidence refs and component digests; "
            "does not persist full prompt text."
        ),
    }


def _memo_writer_input_pack_metrics(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    memo = agent_audit.get("memo_writer") if isinstance(agent_audit.get("memo_writer"), Mapping) else {}
    route = memo.get("route_result") if isinstance(memo.get("route_result"), Mapping) else {}
    fingerprint = route.get("input_pack_fingerprint") if isinstance(route.get("input_pack_fingerprint"), Mapping) else {}
    if not fingerprint:
        quality_agent_audit = quality.get("agent_audit") if isinstance(quality.get("agent_audit"), Mapping) else {}
        quality_memo = quality_agent_audit.get("memo_writer") if isinstance(quality_agent_audit.get("memo_writer"), Mapping) else {}
        quality_route = quality_memo.get("route_result") if isinstance(quality_memo.get("route_result"), Mapping) else {}
        fingerprint = (
            quality_route.get("input_pack_fingerprint")
            if isinstance(quality_route.get("input_pack_fingerprint"), Mapping)
            else {}
        )
    if not fingerprint:
        return {
            "available": False,
            "measurement_boundary": "no_memo_writer_input_pack_fingerprint_in_saved_artifacts",
        }
    return _input_pack_fingerprint_metrics(fingerprint, boundary="memo_writer_fingerprint_only_no_prompt_text_persisted")


def _research_lead_input_pack_metrics(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    fingerprint = _agent_audit_input_fingerprint(case, quality, agent_id="research_lead")
    if not fingerprint:
        return {
            "available": False,
            "measurement_boundary": "no_research_lead_input_pack_fingerprint_in_saved_artifacts",
        }
    return _input_pack_fingerprint_metrics(fingerprint, boundary="research_lead_fingerprint_only_no_prompt_text_persisted")


def _universe_relationship_input_pack_metrics(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    fingerprint = _agent_audit_input_fingerprint(case, quality, agent_id="universe_relationship")
    if not fingerprint:
        return {
            "available": False,
            "measurement_boundary": "no_universe_relationship_input_pack_fingerprint_in_saved_artifacts",
        }
    return _input_pack_fingerprint_metrics(fingerprint, boundary="universe_relationship_fingerprint_only_no_prompt_text_persisted")


def _agent_audit_input_fingerprint(
    case: Mapping[str, Any],
    quality: Mapping[str, Any],
    *,
    agent_id: str,
) -> Mapping[str, Any]:
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    route = agent_audit.get(agent_id) if isinstance(agent_audit.get(agent_id), Mapping) else {}
    fingerprint = route.get("input_pack_fingerprint") if isinstance(route.get("input_pack_fingerprint"), Mapping) else {}
    if fingerprint:
        return fingerprint
    quality_agent_audit = quality.get("agent_audit") if isinstance(quality.get("agent_audit"), Mapping) else {}
    quality_route = (
        quality_agent_audit.get(agent_id)
        if isinstance(quality_agent_audit.get(agent_id), Mapping)
        else {}
    )
    return (
        quality_route.get("input_pack_fingerprint")
        if isinstance(quality_route.get("input_pack_fingerprint"), Mapping)
        else {}
    )


def _verifier_input_pack_metrics(case: Mapping[str, Any], quality: Mapping[str, Any]) -> dict[str, Any]:
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    verifier = agent_audit.get("verifier") if isinstance(agent_audit.get("verifier"), Mapping) else {}
    projection = verifier.get("input_projection") if isinstance(verifier.get("input_projection"), Mapping) else {}
    fingerprint = projection.get("input_pack_fingerprint") if isinstance(projection.get("input_pack_fingerprint"), Mapping) else {}
    if not fingerprint:
        fingerprint = (
            verifier.get("input_pack_fingerprint")
            if isinstance(verifier.get("input_pack_fingerprint"), Mapping)
            else {}
        )
    if not fingerprint:
        quality_agent_audit = quality.get("agent_audit") if isinstance(quality.get("agent_audit"), Mapping) else {}
        quality_verifier = quality_agent_audit.get("verifier") if isinstance(quality_agent_audit.get("verifier"), Mapping) else {}
        quality_projection = (
            quality_verifier.get("input_projection")
            if isinstance(quality_verifier.get("input_projection"), Mapping)
            else {}
        )
        fingerprint = (
            quality_projection.get("input_pack_fingerprint")
            if isinstance(quality_projection.get("input_pack_fingerprint"), Mapping)
            else {}
        )
    if not fingerprint:
        return {
            "available": False,
            "measurement_boundary": "no_verifier_input_pack_fingerprint_in_saved_artifacts",
        }
    return _input_pack_fingerprint_metrics(fingerprint, boundary="verifier_fingerprint_only_no_prompt_text_persisted")


def _input_pack_fingerprint_metrics(fingerprint: Mapping[str, Any], *, boundary: str) -> dict[str, Any]:
    components = fingerprint.get("component_summaries") if isinstance(fingerprint.get("component_summaries"), Mapping) else {}
    component_rows = []
    for name, summary in components.items():
        if not isinstance(summary, Mapping):
            continue
        component_rows.append(
            {
                "component": str(name),
                "digest": str(summary.get("digest") or ""),
                "item_count": int(summary.get("item_count") or 0),
                "evidence_ref_count": int(summary.get("evidence_ref_count") or 0),
                "approx_chars": int(summary.get("approx_chars") or 0),
            }
        )
    component_rows.sort(key=lambda row: (-int(row.get("approx_chars") or 0), str(row.get("component") or "")))
    return {
        "available": True,
        "schema_version": str(fingerprint.get("schema_version") or ""),
        "digest": str(fingerprint.get("digest") or ""),
        "memo_profile": str(fingerprint.get("memo_profile") or ""),
        "known_evidence_ref_count": int(fingerprint.get("known_evidence_ref_count") or len(_string_list(fingerprint.get("known_evidence_refs")))),
        "known_evidence_refs_sample": _string_list(fingerprint.get("known_evidence_refs"))[:12],
        "component_count": len(component_rows),
        "largest_components": component_rows[:8],
        "approx_prompt_payload_chars": int(fingerprint.get("approx_prompt_payload_chars") or 0),
        "fingerprint_policy": str(fingerprint.get("fingerprint_policy") or fingerprint.get("policy") or ""),
        "capture_source": str(fingerprint.get("capture_source") or ""),
        "measurement_boundary": boundary,
    }


def _specialist_route_rows(case: Mapping[str, Any], quality: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    quality_specialists = quality.get("specialist_stats") if isinstance(quality.get("specialist_stats"), Mapping) else {}
    rows.extend(row for row in quality_specialists.get("route_results") or [] if isinstance(row, Mapping))
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    audit_specialists = agent_audit.get("specialists") if isinstance(agent_audit.get("specialists"), Mapping) else {}
    rows.extend(row for row in audit_specialists.get("route_results") or [] if isinstance(row, Mapping))
    return rows


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)] if str(value or "").strip() else []


def _safe_ratio(numerator: int, denominator: int, *, precision: int = 2) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), precision)


def _coalesce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
