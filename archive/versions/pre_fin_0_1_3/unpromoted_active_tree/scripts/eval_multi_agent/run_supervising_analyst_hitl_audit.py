from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
for path in (SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sec_agent.supervising_analyst import build_supervising_analyst_pack  # noqa: E402


ARTIFACT_KEYS = {
    "verified_judgment_plan": "verified_judgment_plan.json",
    "fundamental_statement_pack": "fundamental_statement_pack.json",
    "pre_memo_fact_selection": "pre_memo_fact_selection.json",
    "lead_review_checkpoint": "lead_review_checkpoint.json",
    "memo_logic_plan": "memo_logic_plan.json",
    "multi_agent_summary": "multi_agent_summary.json",
    "memo_answer": "memo_answer.json",
    "claim_cards": "claim_cards.json",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a human-in-the-loop Research Lead audit on completed case artifacts.")
    parser.add_argument("--case-dir", action="append", required=True, help="Completed case output directory. Repeat for multiple cases.")
    parser.add_argument("--output-dir", default="", help="Optional directory for aggregate audit artifacts.")
    parser.add_argument("--write-pack-to-case-dir", action="store_true", help="Also write supervising_analyst_pack.json into each case directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    case_dirs = [Path(raw).resolve() for raw in args.case_dir]
    output_dir = Path(args.output_dir).resolve() if args.output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for case_dir in case_dirs:
        report = audit_case(case_dir, write_pack_to_case_dir=bool(args.write_pack_to_case_dir))
        reports.append(report)
    aggregate = {
        "schema_version": "sec_agent_supervising_analyst_hitl_audit_summary_v0.1",
        "case_count": len(reports),
        "case_ids": [str(report.get("case_id") or "") for report in reports],
        "issue_counts": _aggregate_issue_counts(reports),
        "reports": reports,
    }
    target_dir = output_dir or (case_dirs[0].parent if case_dirs else Path.cwd())
    (target_dir / "supervising_analyst_hitl_audit_summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target_dir / "supervising_analyst_hitl_audit_summary.md").write_text(
        render_markdown(aggregate),
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "case_count": len(reports), "output_dir": str(target_dir)}, ensure_ascii=False, indent=2))
    return 0


def audit_case(case_dir: Path, *, write_pack_to_case_dir: bool) -> dict[str, Any]:
    state = load_case_state(case_dir)
    pack = build_supervising_analyst_pack(state)
    rendered = _read_text(case_dir / "qwen" / "rendered_answer.md")
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), Mapping) else {}
    surface_issues = audit_rendered_surface(rendered, memo=memo, pack=pack)
    downstream_issues = audit_downstream_agent_outputs(state, pack=pack)
    case_id = _case_id(case_dir, state)
    report = {
        "schema_version": "sec_agent_supervising_analyst_hitl_case_audit_v0.1",
        "case_id": case_id,
        "case_dir": str(case_dir),
        "supervising_analyst_pack": {
            "validation": pack.get("validation") or {},
            "summary": pack.get("summary") or {},
            "stance": ((pack.get("research_lead_synthesis_plan") or {}).get("stance") if isinstance(pack.get("research_lead_synthesis_plan"), Mapping) else ""),
            "core_judgment": ((pack.get("research_lead_synthesis_plan") or {}).get("core_judgment") if isinstance(pack.get("research_lead_synthesis_plan"), Mapping) else ""),
        },
        "surface_issues": surface_issues,
        "downstream_agent_issues": downstream_issues,
        "recommended_fixes": recommended_fixes(surface_issues, downstream_issues),
        "artifact_outputs": {},
    }
    if write_pack_to_case_dir:
        pack_path = case_dir / "supervising_analyst_pack.json"
        pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["artifact_outputs"]["supervising_analyst_pack"] = str(pack_path)
    report_path = case_dir / "codex_supervising_analyst_hil_report.md"
    report_path.write_text(render_case_markdown(report, pack=pack), encoding="utf-8")
    report["artifact_outputs"]["case_report_md"] = str(report_path)
    return report


def load_case_state(case_dir: Path) -> dict[str, Any]:
    state: dict[str, Any] = {"run_id": case_dir.name, "output_dir": str(case_dir)}
    for key, filename in ARTIFACT_KEYS.items():
        value = _load_json(case_dir / filename)
        if value is not None:
            state[key] = value
    claim_cards = state.get("claim_cards") if isinstance(state.get("claim_cards"), Mapping) else {}
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {}
    if claim_cards and not judgment:
        state["verified_judgment_plan"] = {
            "supported_claims": claim_cards.get("supported_claims") or [],
            "unsupported_claims": claim_cards.get("unsupported_claims") or [],
            "conflicts": claim_cards.get("conflicts") or [],
        }
    summary = state.get("multi_agent_summary") if isinstance(state.get("multi_agent_summary"), Mapping) else {}
    state["user_query"] = str(summary.get("user_query") or summary.get("case_id") or case_dir.name)
    return state


def audit_rendered_surface(rendered: str, *, memo: Mapping[str, Any], pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues = []
    text = str(rendered or "")
    if not text.strip():
        issues.append(_issue("memo_surface_empty", "Rendered answer is empty.", "memo_writer"))
        return issues
    if _gap_term_count(text) > max(8, len(_sentences(text)) // 2):
        issues.append(_issue("gap_language_dominates", "The answer still spends too much surface area on missing-data language.", "memo_writer"))
    if "投资含义" in text and _section_is_generic_how_to_judge(text, "投资含义"):
        issues.append(_issue("investment_implication_not_judgment", "Investment implication reads like a checklist instead of a present judgment.", "memo_writer"))
    if _capital_edge_count(pack) >= 2 and not _has_rendered_transmission_path(text):
        issues.append(_issue("capital_graph_not_rendered", "Capital or supply-chain transmission edges exist but are not rendered as a concrete relationship path/table.", "memo_writer"))
    if _financial_line_count(pack) >= 3 and not any(term in text for term in ["资产负债", "利润", "现金流", "capex", "收入", "毛利"]):
        issues.append(_issue("financial_backbone_not_visible", "Financial model exists but the rendered memo does not visibly use it.", "memo_writer"))
    if _derived_ratio_count(pack) >= 1 and not _has_ratio_or_mix_surface(text):
        issues.append(_issue("derived_financial_bridge_not_used", "Derived ratios or product mix are available but the memo does not use them to deepen the financial/product bridge.", "memo_writer"))
    if _product_kpi_count(pack) >= 2 and not _has_product_comparison_surface(text):
        issues.append(_issue("product_bridge_too_shallow", "Product KPI rows exist but the memo does not compare product lines, mix, parameters, or order/backlog context.", "memo_writer"))
    dimension_analyses = [row for row in memo.get("dimension_analyses") or [] if isinstance(row, Mapping)]
    if dimension_analyses and len(dimension_analyses) < 2:
        issues.append(_issue("dimension_analysis_too_thin", "Memo has fewer than two dimension analyses despite a deep research run.", "memo_writer"))
    return issues


def audit_downstream_agent_outputs(state: Mapping[str, Any], *, pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues = []
    financial = pack.get("financial_analysis_model") if isinstance(pack.get("financial_analysis_model"), Mapping) else {}
    product = pack.get("product_bridge_pack") if isinstance(pack.get("product_bridge_pack"), Mapping) else {}
    graph = pack.get("capital_transmission_graph") if isinstance(pack.get("capital_transmission_graph"), Mapping) else {}
    numeric = financial.get("numeric_reconciler") if isinstance(financial.get("numeric_reconciler"), Mapping) else {}
    statement_coverage = financial.get("statement_coverage") if isinstance(financial.get("statement_coverage"), Mapping) else {}
    if not statement_coverage.get("has_balance_sheet"):
        issues.append(_issue("balance_sheet_missing", "Fundamental specialist did not promote balance-sheet rows into the financial backbone.", "fundamental_specialist"))
    if not product.get("company_disclosed_product_kpis"):
        issues.append(_issue("product_kpi_missing", "Product specialist did not deliver company-disclosed product KPI rows.", "product_technology_specialist"))
    if numeric.get("attention_required_count"):
        issues.append(_issue("numeric_display_choice_missing", "Numeric reconciler needs selected display values for mixed period/unit rows.", "fundamental_specialist"))
    edge_counts = graph.get("edge_counts_by_type") if isinstance(graph.get("edge_counts_by_type"), Mapping) else {}
    if edge_counts.get("relationship_hypothesis_only") and not edge_counts.get("supplier_product_revenue_readthrough"):
        issues.append(_issue("relationship_only_no_revenue_readthrough", "Supply-chain specialist only provided relationship hypotheses, not supplier revenue readthrough.", "industry_supply_chain_specialist"))
    if _tool_repair_was_not_used_for_retrievable_gap(state):
        issues.append(_issue("lead_targeted_repair_underused", "Research Lead did not use targeted repair despite retrievable official/source gaps.", "research_lead"))
    return issues


def recommended_fixes(surface_issues: list[dict[str, Any]], downstream_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fixes = []
    issue_types = {str(item.get("type") or "") for item in [*surface_issues, *downstream_issues]}
    if "investment_implication_not_judgment" in issue_types or "gap_language_dominates" in issue_types:
        fixes.append(
            {
                "target": "memo_writer",
                "fix": "Make ResearchLeadSynthesisPlan the primary input; require a present judgment in direct_answer and investment_implications before gaps.",
            }
        )
    if "capital_graph_not_rendered" in issue_types or "relationship_only_no_revenue_readthrough" in issue_types:
        fixes.append(
            {
                "target": "industry_supply_chain_specialist",
                "fix": "Emit directed transmission edges with edge_type, strength, proves, and boundary; writer renders a relationship path/table.",
            }
        )
    if (
        "financial_backbone_not_visible" in issue_types
        or "derived_financial_bridge_not_used" in issue_types
        or "balance_sheet_missing" in issue_types
        or "numeric_display_choice_missing" in issue_types
    ):
        fixes.append(
            {
                "target": "fundamental_specialist",
                "fix": "Promote three-statement peer/period line items into FinancialAnalysisModel and run numeric display reconciliation before memo.",
            }
        )
    if "product_kpi_missing" in issue_types or "product_bridge_too_shallow" in issue_types:
        fixes.append(
            {
                "target": "product_technology_specialist",
                "fix": "Run product KPI/spec/order repair through official product pages or permitted public sources before exposing product gap.",
            }
        )
    if "lead_targeted_repair_underused" in issue_types:
        fixes.append(
            {
                "target": "research_lead",
                "fix": "After first barrier, classify gaps as retrievable/bounded/commercial and trigger targeted repair for retrievable gaps.",
            }
        )
    return fixes


def render_markdown(aggregate: Mapping[str, Any]) -> str:
    lines = [
        "# Supervising Analyst HIL Audit",
        "",
        f"- case_count: {aggregate.get('case_count')}",
        f"- issue_counts: `{json.dumps(aggregate.get('issue_counts') or {}, ensure_ascii=False)}`",
        "",
    ]
    for report in aggregate.get("reports") or []:
        if not isinstance(report, Mapping):
            continue
        lines.append(f"## {report.get('case_id')}")
        pack = report.get("supervising_analyst_pack") if isinstance(report.get("supervising_analyst_pack"), Mapping) else {}
        lines.append(f"- stance: `{pack.get('stance') or ''}`")
        lines.append(f"- core_judgment: {pack.get('core_judgment') or ''}")
        lines.append(f"- surface_issues: {len(report.get('surface_issues') or [])}")
        lines.append(f"- downstream_agent_issues: {len(report.get('downstream_agent_issues') or [])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_case_markdown(report: Mapping[str, Any], *, pack: Mapping[str, Any]) -> str:
    lines = [
        f"# HIL Supervising Analyst Audit: {report.get('case_id')}",
        "",
        "## Research Lead View",
    ]
    synth = pack.get("research_lead_synthesis_plan") if isinstance(pack.get("research_lead_synthesis_plan"), Mapping) else {}
    lines.append(f"- stance: `{synth.get('stance') or ''}`")
    lines.append(f"- core judgment: {synth.get('core_judgment') or ''}")
    lines.append("")
    lines.append("## Proven / Not Proven")
    for label in ("proven", "supported_inference", "not_proven"):
        values = synth.get(label) if isinstance(synth.get(label), list) else []
        lines.append(f"- {label}: " + ("; ".join(str(item) for item in values) if values else ""))
    lines.append("")
    lines.append("## Surface Issues")
    for issue in report.get("surface_issues") or []:
        if isinstance(issue, Mapping):
            lines.append(f"- `{issue.get('type')}` ({issue.get('owner_agent')}): {issue.get('message')}")
    if not report.get("surface_issues"):
        lines.append("- none")
    lines.append("")
    lines.append("## Downstream Agent Issues")
    for issue in report.get("downstream_agent_issues") or []:
        if isinstance(issue, Mapping):
            lines.append(f"- `{issue.get('type')}` ({issue.get('owner_agent')}): {issue.get('message')}")
    if not report.get("downstream_agent_issues"):
        lines.append("- none")
    lines.append("")
    lines.append("## Recommended Fixes")
    for fix in report.get("recommended_fixes") or []:
        if isinstance(fix, Mapping):
            lines.append(f"- `{fix.get('target')}`: {fix.get('fix')}")
    if not report.get("recommended_fixes"):
        lines.append("- none")
    lines.append("")
    lines.append("## Supervising Pack Summary")
    lines.append("```json")
    lines.append(json.dumps(pack.get("summary") or {}, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def _aggregate_issue_counts(reports: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for report in reports:
        for issue in [*(report.get("surface_issues") or []), *(report.get("downstream_agent_issues") or [])]:
            if not isinstance(issue, Mapping):
                continue
            issue_type = str(issue.get("type") or "")
            counts[issue_type] = counts.get(issue_type, 0) + 1
    return dict(sorted(counts.items()))


def _issue(issue_type: str, message: str, owner_agent: str) -> dict[str, Any]:
    return {"type": issue_type, "message": message, "owner_agent": owner_agent}


def _case_id(case_dir: Path, state: Mapping[str, Any]) -> str:
    score = _load_json(case_dir / "real_chain_case_score.json")
    if isinstance(score, Mapping) and score.get("case_id"):
        return str(score.get("case_id"))
    summary = state.get("multi_agent_summary") if isinstance(state.get("multi_agent_summary"), Mapping) else {}
    return str(summary.get("case_id") or state.get("run_id") or case_dir.name)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _sentences(text: str) -> list[str]:
    import re

    return [part.strip() for part in re.split(r"[。！？.!?]\s*|\n+", str(text or "")) if len(part.strip()) >= 8]


def _gap_term_count(text: str) -> int:
    terms = ["缺口", "缺乏", "不足", "不能", "无法", "未披露", "找不到", "gap", "missing", "not prove", "unproven"]
    value = str(text or "").lower()
    return sum(value.count(term.lower()) for term in terms)


def _section_is_generic_how_to_judge(text: str, title: str) -> bool:
    start = text.find(title)
    if start < 0:
        return False
    section = text[start : start + 480]
    generic_terms = ["应关注", "需要跟踪", "如果", "若", "when", "monitor", "would change", "要先确认", "只有", "优先检查", "作用是告诉"]
    present_judgment_terms = ["当前更支持", "当前偏", "结论是", "我会判断", "意味着"]
    return sum(term in section for term in generic_terms) >= 2 and not any(term in section for term in present_judgment_terms)


def _capital_edge_count(pack: Mapping[str, Any]) -> int:
    graph = pack.get("capital_transmission_graph") if isinstance(pack.get("capital_transmission_graph"), Mapping) else {}
    return len([row for row in graph.get("edges") or [] if isinstance(row, Mapping)])


def _derived_ratio_count(pack: Mapping[str, Any]) -> int:
    financial = pack.get("financial_analysis_model") if isinstance(pack.get("financial_analysis_model"), Mapping) else {}
    return len([row for row in financial.get("derived_ratios") or [] if isinstance(row, Mapping)])


def _product_kpi_count(pack: Mapping[str, Any]) -> int:
    product = pack.get("product_bridge_pack") if isinstance(pack.get("product_bridge_pack"), Mapping) else {}
    return len([row for row in product.get("company_disclosed_product_kpis") or [] if isinstance(row, Mapping)])


def _financial_line_count(pack: Mapping[str, Any]) -> int:
    financial = pack.get("financial_analysis_model") if isinstance(pack.get("financial_analysis_model"), Mapping) else {}
    return len([row for row in financial.get("key_line_items") or [] if isinstance(row, Mapping)])


def _has_rendered_transmission_path(text: str) -> bool:
    value = str(text or "")
    path_markers = ["->", "→", "=>", "路径:", "路径：", "链条:", "链条：", "边：", "edge", "传导图", "关系表"]
    return any(marker in value for marker in path_markers)


def _has_ratio_or_mix_surface(text: str) -> bool:
    value = str(text or "").lower()
    return any(term in value for term in ["占比", "mix", "ratio", "capex/revenue", "资本开支率", "收入占", "%"])


def _has_product_comparison_surface(text: str) -> bool:
    value = str(text or "")
    comparison_terms = ["对比", "占比", "高于", "低于", "产品组合", "产品线", "参数", "规格", "积压", "backlog", "orders"]
    return sum(term in value for term in comparison_terms) >= 2


def _tool_repair_was_not_used_for_retrievable_gap(state: Mapping[str, Any]) -> bool:
    checkpoint = state.get("lead_review_checkpoint") if isinstance(state.get("lead_review_checkpoint"), Mapping) else {}
    repair = state.get("lead_targeted_repair_execution") if isinstance(state.get("lead_targeted_repair_execution"), Mapping) else {}
    if not repair:
        repair = checkpoint.get("lead_targeted_repair_execution") if isinstance(checkpoint.get("lead_targeted_repair_execution"), Mapping) else {}
    reviews = [row for row in checkpoint.get("dimension_reviews") or [] if isinstance(row, Mapping)]
    retrievable = any(str(row.get("status") or "") == "retrievable_gap" for row in reviews)
    attempted = int(repair.get("attempted_count") or 0) if repair else 0
    return retrievable and attempted <= 0


if __name__ == "__main__":
    raise SystemExit(main())
