"""Audit multi-agent full-chain output quality from saved Step17 artifacts.

This is a diagnostic-only artifact reader. It does not call any model or
retrieval tool, and it should not require API credentials.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


QUALITY_AUDIT_SCHEMA_VERSION = "sec_agent_multi_agent_output_quality_audit_v0.1"


def audit_summary(summary: Mapping[str, Any], *, artifact_root: Path | None = None) -> dict[str, Any]:
    root = _artifact_root(summary, artifact_root)
    cases = []
    issue_counts: dict[str, int] = {}
    for case in [row for row in summary.get("cases") or [] if isinstance(row, Mapping)]:
        case_audit = audit_case(case, artifact_root=root)
        cases.append(case_audit)
        for issue in case_audit["quality_flags"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    return {
        "schema_version": QUALITY_AUDIT_SCHEMA_VERSION,
        "run_id": str(summary.get("run_id") or ""),
        "diagnostic_only": True,
        "source_summary": str(summary.get("output_dir") or ""),
        "case_count": len(cases),
        "issue_counts": dict(sorted(issue_counts.items())),
        "cases": cases,
        "run_hypotheses": _run_hypotheses(cases),
    }


def audit_case(case: Mapping[str, Any], *, artifact_root: Path | None = None) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "")
    sidecar = _load_case_sidecar(case_id, artifact_root)
    agent_audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
    tools = _tool_stats(agent_audit)
    tokens = _token_stats(agent_audit)
    specialists = _specialist_stats(agent_audit, sidecar)
    cost_quality = _cost_quality_stats(case, agent_audit=agent_audit, tokens=tokens, specialists=specialists)
    preview = str(case.get("rendered_answer_preview") or "")
    second_pass_attempts = _nested_int(sidecar, ("second_pass", "attempts"), default=0)
    second_pass_quality_gap_count = _nested_int(sidecar, ("second_pass", "quality_gap_count"), default=-1)
    quality_flags = _quality_flags(
        case=case,
        preview=preview,
        tools=tools,
        tokens=tokens,
        specialists=specialists,
        cost_quality=cost_quality,
        second_pass_attempts=second_pass_attempts,
        second_pass_quality_gap_count=second_pass_quality_gap_count,
    )
    return {
        "case_id": case_id,
        "category": str(case.get("category") or ""),
        "gate_status": str(case.get("gate_status") or ""),
        "execution_mode": str(case.get("execution_mode") or ""),
        "memo_status": str(case.get("memo_status") or ""),
        "claim_verification": str(case.get("claim_verification") or ""),
        "specialist_verification": str(case.get("specialist_verification") or ""),
        "elapsed_ms": int(case.get("elapsed_ms") or 0),
        "token_stats": tokens,
        "cost_quality_stats": cost_quality,
        "tool_stats": tools,
        "specialist_stats": specialists,
        "second_pass_attempts": second_pass_attempts,
        "rendered_preview_chars": len(preview),
        "rendered_answer_chars": int(case.get("rendered_answer_chars") or len(preview)),
        "memo_claim_count": int(case.get("memo_claim_count") or 0),
        "rendered_answer_has_claim_section": bool(case.get("rendered_answer_has_claim_section")),
        "rendered_answer_has_evidence_refs": bool(case.get("rendered_answer_has_evidence_refs")),
        "rendered_preview_gap_language": _has_gap_language(preview),
        "quality_flags": quality_flags,
        "quality_risk_level": _risk_level(quality_flags),
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        f"# Multi-agent Output Quality Audit: {audit.get('run_id') or ''}",
        "",
        "Diagnostic-only audit generated from saved full-chain artifacts. It does not call LLMs or retrieval tools.",
        "",
        "## Case Summary",
        "",
        "| Case | Risk | Gate | Tokens | Cost/claim | Chars/token | Tool rows | Source gaps | Second pass | Specialist rows | Claim cards | Flags |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for case in audit.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        tools = case.get("tool_stats") if isinstance(case.get("tool_stats"), Mapping) else {}
        tokens = case.get("token_stats") if isinstance(case.get("token_stats"), Mapping) else {}
        specs = case.get("specialist_stats") if isinstance(case.get("specialist_stats"), Mapping) else {}
        cost = case.get("cost_quality_stats") if isinstance(case.get("cost_quality_stats"), Mapping) else {}
        rows = specs.get("input_rows_by_agent") if isinstance(specs.get("input_rows_by_agent"), Mapping) else {}
        rows_text = ", ".join(f"{_short_agent(agent)}={count}" for agent, count in rows.items()) or "n/a"
        claim_card_stats = specs.get("claim_card_stats") if isinstance(specs.get("claim_card_stats"), Mapping) else {}
        flags = ", ".join(case.get("quality_flags") or []) or "none"
        lines.append(
            "| {case_id} | {risk} | {gate} | {tokens} | {cost_claim} | {chars_token} | {rows_total} | {gaps} | {second} | {spec_rows} | {claim_cards} | {flags} |".format(
                case_id=case.get("case_id") or "",
                risk=case.get("quality_risk_level") or "",
                gate=case.get("gate_status") or "",
                tokens=tokens.get("total_tokens") or 0,
                cost_claim=_fmt_metric(cost.get("tokens_per_rendered_memo_claim")),
                chars_token=_fmt_metric(cost.get("memo_chars_per_total_token")),
                rows_total=tools.get("row_count_total") or 0,
                gaps=tools.get("source_gap_count_total") or 0,
                second=case.get("second_pass_attempts") or 0,
                spec_rows=rows_text,
                claim_cards=claim_card_stats.get("supported_claim_count") or 0,
                flags=flags,
            )
        )
    lines.extend(["", "## Run Hypotheses", ""])
    for item in audit.get("run_hypotheses") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Issue Counts", ""])
    for issue, count in (audit.get("issue_counts") or {}).items():
        lines.append(f"- `{issue}`: {count}")
    return "\n".join(lines).rstrip() + "\n"


def _tool_stats(agent_audit: Mapping[str, Any]) -> dict[str, Any]:
    evidence = agent_audit.get("evidence_operators") if isinstance(agent_audit.get("evidence_operators"), Mapping) else {}
    calls = [row for row in evidence.get("tool_calls") or [] if isinstance(row, Mapping)]
    rows_by_tool: dict[str, int] = {}
    rows_by_agent: dict[str, int] = {}
    sec_bge_candidates = 0
    sec_pre_rerank_candidates = 0
    source_gap_count_total = 0
    for call in calls:
        tool = str(call.get("tool_name") or "")
        agent = str(call.get("agent_id") or "")
        row_count = int(call.get("row_count") or 0)
        rows_by_tool[tool] = rows_by_tool.get(tool, 0) + row_count
        rows_by_agent[agent] = rows_by_agent.get(agent, 0) + row_count
        source_gap_count_total += int(call.get("source_gap_count") or 0)
        runtime = call.get("runtime_summary") if isinstance(call.get("runtime_summary"), Mapping) else {}
        counts = runtime.get("candidate_counts") if isinstance(runtime.get("candidate_counts"), Mapping) else {}
        sec_bge_candidates += int(counts.get("candidate_sent_to_bge") or 0)
        sec_pre_rerank_candidates += int(counts.get("candidate_row_count_pre_rerank") or 0)
    return {
        "tool_call_count": len(calls),
        "row_count_total": sum(rows_by_tool.values()),
        "rows_by_tool": dict(sorted(rows_by_tool.items())),
        "rows_by_agent": dict(sorted(rows_by_agent.items())),
        "source_gap_count_total": source_gap_count_total,
        "sec_pre_rerank_candidates": sec_pre_rerank_candidates,
        "sec_bge_candidates": sec_bge_candidates,
    }


def _token_stats(agent_audit: Mapping[str, Any]) -> dict[str, Any]:
    tokens_by_agent: dict[str, int] = {}
    for agent in ("research_lead", "universe_relationship", "memo_writer", "verifier"):
        payload = agent_audit.get(agent) if isinstance(agent_audit.get(agent), Mapping) else {}
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), Mapping) else {}
        value = int(diagnostics.get("total_tokens") or 0)
        if value:
            tokens_by_agent[agent] = value
    specialists = agent_audit.get("specialists") if isinstance(agent_audit.get("specialists"), Mapping) else {}
    specialist_tokens = 0
    for row in specialists.get("route_results") or []:
        if not isinstance(row, Mapping):
            continue
        agent_id = str(row.get("agent_id") or "")
        value = int(row.get("total_tokens") or 0)
        if agent_id and value:
            tokens_by_agent[agent_id] = value
            specialist_tokens += value
    return {
        "total_tokens": sum(tokens_by_agent.values()),
        "tokens_by_agent": dict(sorted(tokens_by_agent.items())),
        "research_lead_tokens": tokens_by_agent.get("research_lead", 0),
        "universe_relationship_tokens": tokens_by_agent.get("universe_relationship", 0),
        "specialist_tokens": specialist_tokens,
        "memo_writer_tokens": tokens_by_agent.get("memo_writer", 0),
        "verifier_tokens": tokens_by_agent.get("verifier", 0),
    }


def _cost_quality_stats(
    case: Mapping[str, Any],
    *,
    agent_audit: Mapping[str, Any],
    tokens: Mapping[str, Any],
    specialists: Mapping[str, Any],
) -> dict[str, Any]:
    total_tokens = int(tokens.get("total_tokens") or 0)
    memo_tokens = int(tokens.get("memo_writer_tokens") or 0)
    verifier_tokens = int(tokens.get("verifier_tokens") or 0)
    specialist_tokens = int(tokens.get("specialist_tokens") or 0)
    claim_card_stats = specialists.get("claim_card_stats") if isinstance(specialists.get("claim_card_stats"), Mapping) else {}
    supported_claims = int(claim_card_stats.get("supported_claim_count") or 0)
    memo_claims = int(case.get("memo_claim_count") or 0)
    rendered_chars = int(case.get("rendered_answer_chars") or len(str(case.get("rendered_answer_preview") or "")))
    memo_writer = agent_audit.get("memo_writer") if isinstance(agent_audit.get("memo_writer"), Mapping) else {}
    route_result = memo_writer.get("route_result") if isinstance(memo_writer.get("route_result"), Mapping) else {}
    diagnostics = memo_writer.get("diagnostics") if isinstance(memo_writer.get("diagnostics"), Mapping) else {}
    attempt_count = int(route_result.get("attempt_count") or diagnostics.get("call_count") or 0)
    repair_attempts = int(route_result.get("repair_attempts") or max(0, attempt_count - 1))
    repair_tokens = _repair_tokens_from_diagnostics(diagnostics)
    return {
        "tokens_per_supported_claim_card": _safe_ratio(total_tokens, supported_claims),
        "specialist_tokens_per_supported_claim_card": _safe_ratio(specialist_tokens, supported_claims),
        "tokens_per_rendered_memo_claim": _safe_ratio(total_tokens, memo_claims),
        "memo_chars_per_total_token": _safe_ratio(rendered_chars, total_tokens, precision=5),
        "memo_writer_token_share": _safe_ratio(memo_tokens, total_tokens, precision=5),
        "verifier_token_share": _safe_ratio(verifier_tokens, total_tokens, precision=5),
        "memo_writer_attempt_count": attempt_count,
        "memo_writer_repair_attempts": repair_attempts,
        "memo_writer_repair_attempt_ratio": _safe_ratio(repair_attempts, attempt_count, precision=5),
        "memo_writer_repair_token_ratio": _safe_ratio(repair_tokens, memo_tokens, precision=5) if repair_tokens is not None else None,
    }


def _specialist_stats(agent_audit: Mapping[str, Any], sidecar: Mapping[str, Any]) -> dict[str, Any]:
    specialists = agent_audit.get("specialists") if isinstance(agent_audit.get("specialists"), Mapping) else {}
    quality = specialists.get("real_evidence_quality") if isinstance(specialists.get("real_evidence_quality"), Mapping) else {}
    details = quality.get("details") if isinstance(quality.get("details"), Mapping) else {}
    input_rows_by_agent: dict[str, int] = {}
    sources_by_agent: dict[str, list[str]] = {}
    for agent_id, detail in details.items():
        if not isinstance(detail, Mapping):
            continue
        input_rows_by_agent[str(agent_id)] = int(detail.get("input_row_count") or 0)
        sources_by_agent[str(agent_id)] = [str(item) for item in detail.get("input_source_families") or []]
    sidecar_specialists = sidecar.get("specialists") if isinstance(sidecar.get("specialists"), Mapping) else {}
    route_results = [row for row in specialists.get("route_results") or [] if isinstance(row, Mapping)]
    return {
        "route_count": len(route_results),
        "route_results": [
            {
                "agent_id": str(row.get("agent_id") or ""),
                "status": str(row.get("status") or ""),
                "attempt_count": int(row.get("attempt_count") or 0),
                "repair_attempts": int(row.get("repair_attempts") or 0),
                "total_tokens": int(row.get("total_tokens") or 0),
            }
            for row in route_results
        ],
        "input_rows_by_agent": dict(sorted(input_rows_by_agent.items())),
        "input_sources_by_agent": dict(sorted(sources_by_agent.items())),
        "real_evidence_quality_pass": bool(quality.get("quality_pass")),
        "unsupported_claim_count": int(sidecar_specialists.get("unsupported_claim_count") or 0),
        "claim_card_stats": _claim_card_stats_from_sidecar(sidecar),
        "agent_priorities": dict(sidecar.get("agent_priorities") or {}) if isinstance(sidecar.get("agent_priorities"), Mapping) else {},
    }


def _quality_flags(
    *,
    case: Mapping[str, Any],
    preview: str,
    tools: Mapping[str, Any],
    tokens: Mapping[str, Any],
    specialists: Mapping[str, Any],
    cost_quality: Mapping[str, Any],
    second_pass_attempts: int,
    second_pass_quality_gap_count: int = -1,
) -> list[str]:
    flags: list[str] = []
    if int(tokens.get("total_tokens") or 0) >= 60000:
        flags.append("high_total_token_cost")
    if int(tokens.get("memo_writer_tokens") or 0) >= 20000:
        flags.append("memo_writer_high_token_cost")
    if int(tokens.get("verifier_tokens") or 0) >= 12000:
        flags.append("verifier_high_token_cost")
    if _numeric(cost_quality.get("tokens_per_rendered_memo_claim")) >= 18000:
        flags.append("low_rendered_claim_token_efficiency")
    if _numeric(cost_quality.get("tokens_per_supported_claim_card")) >= 6000:
        flags.append("low_claim_card_token_efficiency")
    mode = str(case.get("execution_mode") or "")
    if (
        mode != "deterministic_lookup"
        and _numeric(cost_quality.get("memo_chars_per_total_token")) > 0
        and _numeric(cost_quality.get("memo_chars_per_total_token")) < 0.05
    ):
        flags.append("low_memo_chars_per_token")
    repair_token_ratio = _numeric(cost_quality.get("memo_writer_repair_token_ratio"))
    repair_attempt_ratio = _numeric(cost_quality.get("memo_writer_repair_attempt_ratio"))
    if repair_token_ratio >= 0.25 or repair_attempt_ratio >= 0.5:
        flags.append("memo_writer_retry_cost_present")
    if (
        int(tools.get("source_gap_count_total") or 0) > 0
        and second_pass_attempts == 0
        and second_pass_quality_gap_count != 0
    ):
        flags.append("source_gaps_without_second_pass")
    input_rows = [
        int(value)
        for value in (specialists.get("input_rows_by_agent") or {}).values()
        if isinstance(value, int) or str(value).isdigit()
    ]
    if input_rows and max(input_rows) <= 16:
        flags.append("specialist_inputs_tightly_capped")
    if int(specialists.get("unsupported_claim_count") or 0) >= 8:
        flags.append("many_unsupported_specialist_claims")
    claim_card_stats = specialists.get("claim_card_stats") if isinstance(specialists.get("claim_card_stats"), Mapping) else {}
    supported_claim_count = int(claim_card_stats.get("supported_claim_count") or 0)
    claim_card_stats_present = bool(claim_card_stats.get("present"))
    if claim_card_stats_present and supported_claim_count == 0 and mode in {"deep_research", "standard_memo"}:
        flags.append("claim_card_density_zero")
    if claim_card_stats_present and mode == "deep_research" and supported_claim_count < 8:
        flags.append("claim_card_density_low")
    if claim_card_stats_present and mode == "standard_memo" and supported_claim_count < 4:
        flags.append("claim_card_density_low")
    memo_slot_count = int(claim_card_stats.get("memo_slot_count") or 0)
    supported_slot_count = int(claim_card_stats.get("supported_memo_slot_count") or 0)
    if memo_slot_count and supported_slot_count < min(3, memo_slot_count):
        flags.append("memo_outline_under_supported")
    if _has_gap_language(preview):
        flags.append("memo_surface_says_evidence_thin")
    rendered_chars = int(case.get("rendered_answer_chars") or len(preview))
    if mode == "deep_research" and str(case.get("memo_status") or "") == "draft" and rendered_chars < 900:
        flags.append("rendered_memo_too_short")
    if mode == "deep_research" and int(case.get("memo_claim_count") or 0) > 0 and not bool(case.get("rendered_answer_has_evidence_refs")):
        flags.append("rendered_memo_missing_evidence_refs")
    if (
        str(case.get("execution_mode") or "") == "deep_research"
        and int(specialists.get("route_count") or 0) >= 4
        and not _has_nonuniform_specialist_priorities(specialists)
    ):
        flags.append("deep_research_all_specialists_active")
    return flags


def _has_nonuniform_specialist_priorities(specialists: Mapping[str, Any]) -> bool:
    priorities = specialists.get("agent_priorities") if isinstance(specialists.get("agent_priorities"), Mapping) else {}
    specialist_priorities = {
        agent_id: str(priorities.get(agent_id) or "")
        for agent_id in (
            "fundamental_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        )
        if priorities.get(agent_id)
    }
    if len(specialist_priorities) < 4:
        return False
    return len(set(specialist_priorities.values())) > 1


def _run_hypotheses(cases: list[Mapping[str, Any]]) -> list[str]:
    hypotheses: list[str] = []
    if any("specialist_inputs_tightly_capped" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Specialist data views are safe but too narrow for sector-depth multi-company synthesis; increase budget by execution mode and source quota, not globally.")
    if any("high_total_token_cost" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Total token cost remains high; inspect specialist activation breadth and repeated downstream verification before adding more evidence.")
    if any("many_unsupported_specialist_claims" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Specialist outputs are still gap-heavy observations instead of memo-ready claim cards; the downstream memo receives too few supported investment claims.")
    if any("claim_card_density_low" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Claim-card density is low for the execution mode; tokens are not yet converting into enough memo-ready supported claims.")
    if any("claim_card_density_zero" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("No supported claim cards were recorded in the summary artifact; inspect Specialist normalization and Judgment Aggregator transfer before tuning Memo Writer.")
    if any("memo_outline_under_supported" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Judgment aggregation produced memo sections with too few supported claim cards; Memo Writer will likely stay conservative or caveat-heavy.")
    if any("source_gaps_without_second_pass" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Coverage / Reflection is not converting source gaps into useful second-pass retrieval before memo generation.")
    if any("memo_writer_high_token_cost" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Memo Writer spends many tokens on a large compressed judgment payload, but the contract does not force a dense structured memo.")
    if any("low_rendered_claim_token_efficiency" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("The chain spends many tokens per rendered memo claim; inspect Memo Writer retries, Specialist breadth, and claim projection before adding more evidence.")
    if any("low_claim_card_token_efficiency" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Token spend is not converting efficiently into supported ClaimCards; inspect Specialist role prompts and row selectors before increasing caps.")
    if any("low_memo_chars_per_token" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Final memo surface area is low relative to token spend; improve thesis-led rendering or reduce upstream payloads.")
    if any("memo_writer_retry_cost_present" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Memo Writer retries are a material cost driver; inspect max-token truncation, output schema compactness, and repair prompts.")
    if any("rendered_memo_too_short" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Renderer is not converting verified memo claims into a sufficiently useful final memo surface.")
    if any("rendered_memo_missing_evidence_refs" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Final memo rendering is hiding evidence refs, making a supported memo look like an unsupported summary.")
    if any("verifier_high_token_cost" in case.get("quality_flags", []) for case in cases):
        hypotheses.append("Verifier is acting as an expensive safety door; it does not add memo depth and should be paired with separate quality gates.")
    if not hypotheses:
        hypotheses.append("No major artifact-level quality risk was detected by the static audit; run a deeper raw-output review before changing prompts.")
    return hypotheses


def _artifact_root(summary: Mapping[str, Any], override: Path | None) -> Path | None:
    if override is not None:
        return override
    text = str(summary.get("output_dir") or "").strip()
    return Path(text) if text else None


def _load_case_sidecar(case_id: str, root: Path | None) -> dict[str, Any]:
    if not root or not case_id:
        return {}
    path = root / case_id / "multi_agent_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _nested_int(payload: Mapping[str, Any], path: tuple[str, ...], *, default: int) -> int:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping):
            return default
        value = value.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _repair_tokens_from_diagnostics(diagnostics: Mapping[str, Any]) -> int | None:
    calls = [row for row in diagnostics.get("calls") or [] if isinstance(row, Mapping)]
    if not calls:
        return None
    values = [int(row.get("total_tokens") or 0) for row in calls[1:]]
    return sum(values) if values else 0


def _safe_ratio(numerator: int, denominator: int, *, precision: int = 2) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), precision)


def _numeric(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.5f}".rstrip("0").rstrip(".")
    return str(value)


def _claim_card_stats_from_sidecar(sidecar: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [
        sidecar.get("verified_judgment_plan") if isinstance(sidecar.get("verified_judgment_plan"), Mapping) else {},
        sidecar.get("judgment_plan") if isinstance(sidecar.get("judgment_plan"), Mapping) else {},
    ]
    for candidate in candidates:
        stats = candidate.get("claim_card_stats") if isinstance(candidate.get("claim_card_stats"), Mapping) else {}
        if stats:
            return {
                "present": True,
                "supported_claim_count": int(stats.get("supported_claim_count") or 0),
                "high_materiality_claim_count": int(stats.get("high_materiality_claim_count") or 0),
                "memo_slot_count": int(stats.get("memo_slot_count") or 0),
                "supported_memo_slot_count": int(stats.get("supported_memo_slot_count") or 0),
                "synthesized_thesis_claim_count": int(stats.get("synthesized_thesis_claim_count") or 0),
            }
    return {}


def _has_gap_language(text: str) -> bool:
    lowered = str(text or "").lower()
    markers = (
        "missing",
        "insufficient",
        "incomplete",
        "lack",
        "limited",
        "有限",
        "缺失",
        "不足",
        "不完整",
    )
    return any(marker in lowered for marker in markers)


def _risk_level(flags: list[str]) -> str:
    if len(flags) >= 5 or "source_gaps_without_second_pass" in flags:
        return "high"
    if len(flags) >= 2:
        return "medium"
    if flags:
        return "low"
    return "none"


def _short_agent(agent_id: Any) -> str:
    aliases = {
        "fundamental_analyst": "fund",
        "industry_supply_chain_analyst": "ind",
        "market_valuation_analyst": "mkt",
        "risk_counterevidence_analyst": "risk",
    }
    return aliases.get(str(agent_id), str(agent_id))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, help="Path to real_chain_eval_summary.json")
    parser.add_argument("--artifact-root", type=Path, default=None, help="Optional eval output directory containing per-case sidecars.")
    parser.add_argument("--json-out", type=Path, default=None, help="Audit JSON output path.")
    parser.add_argument("--md-out", type=Path, default=None, help="Audit Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    audit = audit_summary(summary, artifact_root=args.artifact_root)
    json_out = args.json_out or args.summary.with_name("multi_agent_output_quality_audit.json")
    md_out = args.md_out or args.summary.with_name("multi_agent_output_quality_audit.md")
    json_out.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({"status": "ok", "json_out": str(json_out), "md_out": str(md_out), "case_count": audit["case_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
