"""Audit WorkBuddy report artifacts and trajectories without copying raw reasoning."""

from __future__ import annotations

import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


SOURCE_SCHEMA = "finsight_workbuddy_multisector_calibration_cases_v0_1"
AUDIT_SCHEMA = "finsight_workbuddy_multisector_calibration_audit_v0_1"


class _ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self.heading_parts: list[str] = []
        self._heading_tag: str | None = None
        self._heading_buffer: list[str] = []
        self.table_count = 0
        self.script_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"h1", "h2", "h3"}:
            self._heading_tag = tag
            self._heading_buffer = []
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))
        if tag == "table":
            self.table_count += 1
        if tag == "script":
            self.script_count += 1

    def handle_endtag(self, tag: str) -> None:
        if self._heading_tag == tag:
            heading = " ".join("".join(self._heading_buffer).split())
            if heading:
                self.heading_parts.append(heading)
            self._heading_tag = None
            self._heading_buffer = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._heading_tag:
            self._heading_buffer.append(data)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_config(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SOURCE_SCHEMA:
        errors.append("workbuddy_source_schema_invalid")
    cases = payload.get("cases") or []
    ids = [str(row.get("case_id") or "") for row in cases]
    if len(ids) != 12 or len(ids) != len(set(ids)) or any(not value for value in ids):
        errors.append("workbuddy_case_ids_invalid")
    for row in cases:
        for field in ("task_dir", "html_file", "sector", "mechanism", "report_type"):
            if not row.get(field):
                errors.append(f"workbuddy_case_field_missing:{row.get('case_id')}:{field}")
    return errors


def _domain_role(domain: str) -> str:
    domain = domain.lower().removeprefix("www.")
    issuer_roots = {
        "salesforce.com", "servicenow.com", "datadoghq.com", "snowflake.com",
        "lilly.com", "novonordisk.com", "walmart.com", "target.com", "costco.com",
        "exxonmobil.com", "chevron.com", "conocophillips.com", "vistracorp.com",
        "nexteraenergy.com", "southerncompany.com", "duke-energy.com", "caterpillar.com",
        "deere.com", "honeywell.com", "geaerospace.com", "crowdstrike.com",
        "paloaltonetworks.com", "zscaler.com",
    }
    if domain.endswith(".gov") or domain == "sec.gov":
        return "government_or_regulator_primary"
    if domain.startswith(("investor.", "investors.", "ir.", "corporate.")):
        return "issuer_primary"
    if any(domain == root or domain.endswith(f".{root}") for root in issuer_roots):
        return "issuer_primary"
    if domain in {"reuters.com", "spglobal.com", "ft.com", "wsj.com", "bloomberg.com", "flightglobal.com", "prnewswire.com"}:
        return "established_secondary_or_wire"
    if domain in {"finance.yahoo.com", "gu.qq.com", "macrotrends.net", "quartr.com", "nasdaq.com"}:
        return "market_aggregator_or_transcript"
    return "other_secondary_or_unknown"


def _parse_report(path: Path, patterns: Mapping[str, list[str]], required: list[str]) -> dict[str, Any]:
    parser = _ReportParser()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    text = " ".join(" ".join(parser.text_parts).split()).lower()
    links = [value for value in parser.links if value.startswith(("http://", "https://"))]
    domains = [urlparse(value).netloc.lower().removeprefix("www.") for value in links]
    domain_roles = Counter(_domain_role(domain) for domain in domains)
    surface_status = {
        surface: any(pattern.lower() in text for pattern in patterns.get(surface, []))
        for surface in required
    }
    return {
        "html_bytes": path.stat().st_size,
        "text_character_count": len(text),
        "heading_count": len(parser.heading_parts),
        "headings": parser.heading_parts,
        "table_count": parser.table_count,
        "script_count": parser.script_count,
        "external_link_count": len(links),
        "unique_domain_count": len(set(domains)),
        "source_domains": sorted(set(domains)),
        "source_domain_role_counts": dict(sorted(domain_roles.items())),
        "primary_source_link_count": sum(
            count for role, count in domain_roles.items()
            if role in {"government_or_regulator_primary", "issuer_primary"}
        ),
        "surface_status": surface_status,
        "surface_pass_count": sum(surface_status.values()),
        "surface_required_count": len(surface_status),
        "claim_level_lineage_status": "not_machine_readable",
        "source_authority_status": (
            "no_clickthrough"
            if not links
            else "primary_present" if sum(count for role, count in domain_roles.items() if role in {"government_or_regulator_primary", "issuer_primary"})
            else "secondary_or_aggregator_only"
        ),
    }


def _session_index(state_root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in (state_root / "sessions").glob("*.json"):
        try:
            row = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        cwd = str(row.get("cwd") or "")
        if cwd:
            rows[Path(cwd).name.lower()] = row
    return rows


def _trace_summary(state_root: Path, session: Mapping[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {"trace_status": "missing_session", "trace_available": False}
    trace_dir = state_root / "traces" / str(session.get("pid"))
    candidates = [path for path in trace_dir.glob("*.json") if path.stat().st_size >= 100_000]
    if not candidates:
        return {"trace_status": "missing_full_trace", "trace_available": False}
    path = max(candidates, key=lambda item: item.stat().st_size)
    payload = load_json(path)
    trace = payload.get("trace") or {}
    spans = payload.get("spans") or []
    tools = Counter(
        str(span.get("name") or "unknown")
        for span in spans
        if span.get("type") == "function"
    )
    statuses = Counter(str(span.get("status") or "unknown") for span in spans)
    error_spans = [
        {"name": span.get("name"), "type": span.get("type"), "error": str(span.get("error") or "")[:300]}
        for span in spans
        if span.get("status") == "error" or span.get("error")
    ]
    model = trace.get("modelInfo") or {}
    return {
        "trace_available": True,
        "trace_status": trace.get("status"),
        "duration_ms": trace.get("duration"),
        "span_count": len(spans),
        "span_error_count": statuses.get("error", 0),
        "error_spans": error_spans,
        "model_calls": model.get("callCount", 0),
        "input_tokens_cumulative": model.get("totalInputTokens", 0),
        "output_tokens": model.get("totalOutputTokens", 0),
        "cached_tokens_cumulative": model.get("totalCachedTokens", 0),
        "tool_call_count": sum(tools.values()),
        "tool_counts": dict(sorted(tools.items())),
        "web_search_count": tools.get("WebSearch", 0),
        "agentic_loop_observed": model.get("callCount", 0) > 3 and sum(tools.values()) > 3,
        "raw_reasoning_ingested": False,
        "trajectory_health": (
            "artifact_complete_trajectory_terminal_error"
            if any(row.get("type") == "agent" for row in error_spans)
            else "artifact_complete_nonfatal_tool_error" if error_spans else "ok"
        ),
    }


def build_audit(
    workbuddy_root: str | Path,
    state_root: str | Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(workbuddy_root)
    state = Path(state_root)
    errors = validate_config(payload)
    sessions = _session_index(state)
    patterns = payload.get("surface_patterns") or {}
    universal = list(payload.get("universal_required_surfaces") or [])
    rows = []
    for case in payload.get("cases") or []:
        report_path = root / str(case["task_dir"]) / str(case["html_file"])
        memory_path = root / str(case["task_dir"]) / ".workbuddy" / "memory" / "2026-07-11.md"
        if not report_path.exists():
            errors.append(f"workbuddy_html_missing:{case['case_id']}")
            continue
        required = [*universal, *(case.get("required_surfaces") or [])]
        report = _parse_report(report_path, patterns, required)
        trace = _trace_summary(state, sessions.get(str(case["task_dir"]).lower()))
        rows.append(
            {
                **dict(case),
                "memory_present": memory_path.exists(),
                "report": report,
                "trajectory": trace,
                "sample_role": "external_product_and_research_process_calibration_only",
                "runtime_evidence_status": "not_runtime_evidence",
            }
        )
    preferred_by_id = {row["case_id"]: row for row in rows}
    duplicate_rows = []
    for item in payload.get("duplicate_or_incomplete_runs") or []:
        html = item.get("html_file")
        path = root / str(item["task_dir"]) / str(html) if html else None
        duplicate = {**dict(item), "html_present": bool(path and path.exists())}
        preferred = preferred_by_id.get(str(item.get("preferred_case_id") or ""))
        if path and path.exists() and preferred:
            required = [*universal, *(preferred.get("required_surfaces") or [])]
            report = _parse_report(path, patterns, required)
            left = set(report["source_domains"])
            right = set(preferred["report"]["source_domains"])
            duplicate["report"] = report
            duplicate["preferred_comparison"] = {
                "source_domain_jaccard": round(len(left & right) / len(left | right), 4) if left | right else 1.0,
                "external_link_count_delta": report["external_link_count"] - preferred["report"]["external_link_count"],
                "table_count_delta": report["table_count"] - preferred["report"]["table_count"],
                "both_surface_complete": (
                    report["surface_pass_count"] == report["surface_required_count"]
                    and preferred["report"]["surface_pass_count"] == preferred["report"]["surface_required_count"]
                ),
            }
        duplicate_rows.append(duplicate)

    trajectories = [row["trajectory"] for row in rows]
    reports = [row["report"] for row in rows]
    total_links = sum(row["external_link_count"] for row in reports)
    total_primary = sum(row["primary_source_link_count"] for row in reports)
    total_duration_ms = sum(row.get("duration_ms") or 0 for row in trajectories)
    total_input = sum(row.get("input_tokens_cumulative") or 0 for row in trajectories)
    total_cached = sum(row.get("cached_tokens_cumulative") or 0 for row in trajectories)
    return {
        "schema_version": AUDIT_SCHEMA,
        "audit_id": payload.get("audit_id"),
        "status": "pass" if not errors else "fail",
        "audit_completion_status": "artifact_and_trajectory_inventory_complete" if not errors else "incomplete",
        "research_quality_status": "not_assessed_comprehensively",
        "model_boundary": {
            "model": payload.get("model"),
            "classification": payload.get("model_strength_classification") or "unclassified_calibration_model",
            "maturity_inference_allowed": bool(payload.get("maturity_inference_allowed", False)),
            "note": "Observed outputs and trajectories are defect baselines, not mature reference implementations.",
        },
        "case_count": len(rows),
        "html_present_count": len(rows),
        "trace_available_count": sum(bool(row.get("trace_available")) for row in trajectories),
        "agentic_loop_observed_count": sum(bool(row.get("agentic_loop_observed")) for row in trajectories),
        "trace_error_case_count": sum((row.get("span_error_count") or 0) > 0 for row in trajectories),
        "total_model_calls": sum(row.get("model_calls") or 0 for row in trajectories),
        "total_tool_calls": sum(row.get("tool_call_count") or 0 for row in trajectories),
        "total_web_searches": sum(row.get("web_search_count") or 0 for row in trajectories),
        "total_duration_ms": total_duration_ms,
        "average_duration_ms": round(total_duration_ms / len(trajectories), 2) if trajectories else 0,
        "total_input_tokens_cumulative": total_input,
        "total_cached_tokens_cumulative": total_cached,
        "cumulative_cache_ratio": round(total_cached / total_input, 4) if total_input else 0.0,
        "cumulative_uncached_input_tokens": total_input - total_cached,
        "total_output_tokens": sum(row.get("output_tokens") or 0 for row in trajectories),
        "report_external_link_count": total_links,
        "report_primary_source_link_count": total_primary,
        "report_primary_source_link_ratio": round(total_primary / total_links, 4) if total_links else 0.0,
        "all_required_surface_pass_case_count": sum(
            row["surface_pass_count"] == row["surface_required_count"] for row in reports
        ),
        "claim_level_lineage_machine_readable_count": 0,
        "cases": rows,
        "duplicate_or_incomplete_runs": duplicate_rows,
        "spot_checks": payload.get("spot_checks") or [],
        "visual_qa_observation": payload.get("visual_qa_observation") or {},
        "audit_coverage": {
            "assessed": [
                "artifact_presence_and_basic_html_structure",
                "trajectory_presence_call_counts_tool_counts_and_terminal_errors",
                "prompt_conditioned_surface_keyword_presence",
                "final_html_link_domain_role_heuristic",
                "six_isolated_primary_source_fact_spot_checks",
                "four_case_desktop_render_smoke",
                "one_same_prompt_source_domain_repeatability_pair",
            ],
            "not_assessed": [
                "decision_cell_semantic_quality_granularity_and_material_coverage",
                "complete_claim_correctness_and_claim_to_source_entailment",
                "complete_numeric_unit_period_currency_and_formula_audit",
                "source_freshness_as_of_consistency_and_conflict_resolution",
                "search_query_quality_tool_necessity_and_observation_usefulness",
                "repair_causality_effectiveness_and_stop_rule_quality",
                "context_duplication_compaction_drift_and_information_yield",
                "subagent_handoff_quality_and_pack_version_consistency",
                "chart_semantic_correctness_and_data_binding",
                "sector_judgment_depth_valuation_quality_and_client_readiness",
            ],
        },
        "pattern_default_disposition": payload.get("default_pattern_disposition") or "requires_improvement_or_rejection_review",
        "findings": [
            "WorkBuddy exhibits multi-step model/tool activity rather than one-shot completion; this does not establish reasoning or research quality.",
            "Required-surface keyword presence is high but prompt-conditioned, so it is not independent evidence that the structure is mature.",
            "Final HTML does not expose machine-readable claim-to-tool-observation lineage.",
            "The same sector produces materially different surfaces for company comparison, event update, valuation and counter-thesis tasks.",
            "High cumulative context and model-call counts establish cost exposure; useful information yield was not measured.",
            "A completed HTML can coexist with a trace-level error, so artifact success and trajectory health must be separate states.",
            "Repeated runs of the same counter-thesis prompt preserve the broad structure but materially vary source selection and quantitative framing.",
            "The prior audit is an artifact/trajectory inventory with limited spot checks, not a comprehensive research-quality audit.",
        ],
        "design_implications": [
            "Use the observed loops as failure and improvement fixtures; do not copy their orchestration as a mature reference.",
            "Test report_type and sector as orthogonal DecisionSurface inputs against independent rubrics before pack promotion.",
            "Redesign candidate matrices, scenario panels and What-Would-Change surfaces around FIN provenance and review contracts before reuse.",
            "Add FIN-only promotion gates for source authority, entity/period/unit binding, numeric trace and claim lineage.",
            "Track useful claim yield per model/tool/context cost, not only report completion.",
            "Add repeatability evals over cell coverage, source authority, material claims and numeric outputs for identical prompts.",
            "Run a pre-matrix semantic re-audit for cell quality, claim support, numeric correctness, tool usefulness and repair causality.",
        ],
        "boundaries": {
            "workbuddy_report_claims_promoted_to_fin_runtime": False,
            "raw_reasoning_copied_to_repo": False,
            "spot_checks_are_exhaustive_fact_verification": False,
            "surface_keyword_pass_is_research_quality_pass": False,
            "agentic_loop_observed_is_mature_agentic_research": False,
            "workbuddy_pattern_default_action_is_absorb": False,
            "paid_model_or_fin_full_chain_executed": False,
        },
        "errors": errors,
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# WorkBuddy 多行业 Calibration 审计",
        "",
        "日期：2026-07-11",
        "",
        f"状态：`{audit['status']}`。审计 {audit['case_count']} 个正式 HTML 与 {audit['trace_available_count']} 条完整 trajectory；未运行 FIN paid/full-chain。",
        f"模型边界：`{audit['model_boundary']['model']}`，按 non-strong calibration model 处理；`status=pass` 只表示审计输入完整，不表示研究质量通过。",
        "",
        "## 总体结果",
        "",
        f"- Agentic loops observed：{audit['agentic_loop_observed_count']}/{audit['case_count']}。",
        f"- Model calls：{audit['total_model_calls']}；tool calls：{audit['total_tool_calls']}；WebSearch：{audit['total_web_searches']}。",
        f"- 总 trajectory wall time：{audit['total_duration_ms'] / 60000:.2f} 分钟；平均每 case：{audit['average_duration_ms'] / 60000:.2f} 分钟。",
        f"- Cumulative input tokens：{audit['total_input_tokens_cumulative']}；cached：{audit['total_cached_tokens_cumulative']}（{audit['cumulative_cache_ratio']:.1%}）；uncached：{audit['cumulative_uncached_input_tokens']}；output：{audit['total_output_tokens']}。",
        f"- External links：{audit['report_external_link_count']}；primary/government/issuer links：{audit['report_primary_source_link_count']}；ratio：{audit['report_primary_source_link_ratio']:.1%}。",
        f"- All required surfaces pass：{audit['all_required_surface_pass_case_count']}/{audit['case_count']}。",
        f"- Machine-readable claim lineage：{audit['claim_level_lineage_machine_readable_count']}/{audit['case_count']}。",
        "",
        "## Case Matrix",
        "",
        "| Case | Sector | Type | Calls | Tools | Search | Links | Primary | Surfaces | Trace |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in audit.get("cases") or []:
        report = row["report"]
        trace = row["trajectory"]
        lines.append(
            f"| {row['case_id']} | {row['sector']} | {row['report_type']} | {trace.get('model_calls', 0)} | "
            f"{trace.get('tool_call_count', 0)} | {trace.get('web_search_count', 0)} | "
            f"{report['external_link_count']} | {report['primary_source_link_count']} | "
            f"{report['surface_pass_count']}/{report['surface_required_count']} | {trace.get('trace_status')} |"
        )
    duplicate = next(
        (row for row in audit.get("duplicate_or_incomplete_runs") or [] if row.get("preferred_comparison")),
        None,
    )
    if duplicate:
        comparison = duplicate["preferred_comparison"]
        lines.extend(
            [
                "",
                "## 同 Prompt 重复运行",
                "",
                f"WB-T04 有两个完成版本，source-domain Jaccard 仅 `{comparison['source_domain_jaccard']:.1%}`。两个版本均覆盖所需结构，但主版本比重复版本多 `{abs(comparison['external_link_count_delta'])}` 个外链、表格数差异 `{abs(comparison['table_count_delta'])}`。这说明结构服从度较稳定，source selection 与 quantitative framing 的可复现性较弱。",
            ]
        )
    visual = audit.get("visual_qa_observation") or {}
    if visual:
        lines.extend(
            [
                "",
                "## Visual QA",
                "",
                f"在 `{visual.get('viewport')}` 使用 {visual.get('browser')} 抽查 {', '.join(visual.get('sample_case_ids') or [])}：横向溢出 `{visual.get('horizontal_overflow_case_count')}`，console errors `{visual.get('console_error_count')}`。银行、GLP-1 和反证报告的 canvas 实际渲染；政策报告以静态表格为主。",
            ]
        )
    lines.extend(
        [
            "",
            "## 审计覆盖与盲区",
            "",
            "本轮实际覆盖 artifact/trace 存在性、调用计数、prompt-conditioned surface 关键词、最终 HTML 链接域启发式、6 个孤立数字 spot checks、4 个桌面渲染 smoke 和 1 组同 prompt 来源域比较。",
            "",
            "本轮没有系统审计 cell 语义质量、完整 claim correctness/entailment、数字单位期间与公式、source freshness/conflict、query/tool/observation usefulness、repair 因果与 stop rule、上下文重复与信息产出、handoff/version consistency、图表数据绑定、行业判断深度或 client readiness。后续 DefectAndPatternCandidateMatrix 前必须补这层复审。",
            "",
            "## 结论",
            "",
            "WorkBuddy 12-case 只证明 DeepSeek V4 在这些 prompts、工具和独立上下文条件下产生了多轮调用及可渲染报告；它没有证明推理、取证、判断、repair 或上下文管理已经成熟。",
            "",
            "因此 FIN 应把这些案例当作跨行业 defect and improvement baseline：逐项判断 retain-with-independent-evidence、redesign、repair 或 reject。不能默认吸收其研究循环、报告结构或轨迹；任何进入 pack 的模式都必须先通过独立 rubric、语义复审、FIN provenance/numeric contracts 和 shadow comparison。",
            "",
            "## 轨迹边界",
            "",
            "- WorkBuddy raw reasoning 存在于本地 project logs，本审计不复制或展示。",
            "- `trace_status=error` 但 HTML 完成的 case 必须记录为 artifact complete / trajectory degraded，而不是简单 pass。",
            "- Spot checks 只验证少数高影响数字，不构成整份报告事实验收。",
            "- WorkBuddy HTML 和 trace 是 calibration input，不是 FIN runtime evidence。",
        ]
    )
    return "\n".join(lines) + "\n"
