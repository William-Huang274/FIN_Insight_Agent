"""Build observable A/B audits for WorkBuddy expert and skill configuration variants."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from bs4 import BeautifulSoup

from sec_agent.workbuddy_semantic_trajectory_reaudit import _object, _report_metrics, _trace_metrics


SCHEMA_VERSION = "finsight_workbuddy_expert_variant_audit_v0_1"
CONFIG_SCHEMA = "finsight_workbuddy_expert_variant_review_config_v0_1"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_config(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != CONFIG_SCHEMA:
        errors.append("expert_variant_config_schema_invalid")
    dimensions = set(payload.get("score_dimensions") or [])
    variants = payload.get("variants") or []
    variant_ids = [str(row.get("variant_id") or "") for row in variants]
    if not variants or len(variant_ids) != len(set(variant_ids)) or any(not value for value in variant_ids):
        errors.append("expert_variant_ids_invalid")
    for row in variants:
        if dimensions - set((row.get("scores") or {}).keys()):
            errors.append(f"expert_variant_scores_missing:{row.get('variant_id')}")
        if row.get("disposition") not in {"improve", "redesign", "reject_as_reference"}:
            errors.append(f"expert_variant_disposition_invalid:{row.get('variant_id')}")
        for side in ("base", "variant"):
            required = {"task_dir", "html_file", "trace_file"}
            if required - set((row.get(side) or {}).keys()):
                errors.append(f"expert_variant_{side}_source_missing:{row.get('variant_id')}")
    return errors


def _invoked_skills(trace_path: Path) -> list[str]:
    payload = load_json(trace_path)
    values: list[str] = []
    for span in payload.get("spans") or []:
        if span.get("type") != "function" or span.get("name") != "Skill":
            continue
        skill = str(_object(span.get("toolInput")).get("skill") or "").strip()
        if skill:
            values.append(skill)
    return values


def _observable_metrics(report_path: Path, trace_path: Path) -> dict[str, Any]:
    payload = load_json(trace_path)
    spans = payload.get("spans") or []
    agents = [row for row in spans if row.get("type") == "agent"]
    functions = [row for row in spans if row.get("type") == "function"]
    function_counts = Counter(str(row.get("name") or "unknown") for row in functions)
    report = _report_metrics(report_path)
    soup = BeautifulSoup(report_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    visible_text = soup.get_text(" ", strip=True)
    trace_text = trace_path.read_text(encoding="utf-8", errors="ignore")
    trace = _trace_metrics(trace_path)
    trace_header = payload.get("trace") or {}
    return {
        "report_path": str(report_path),
        "trace_path": str(trace_path),
        "report_bytes": report_path.stat().st_size,
        "duration_ms": int(trace_header.get("duration") or 0),
        **report,
        "missing_marker_count": visible_text.count("[MISSING]"),
        "stale_marker_count": visible_text.count("[STALE]"),
        "svg_count": len(soup.find_all("svg")),
        "script_count": len(soup.find_all("script")),
        "agent_span_count": len(agents),
        "agent_names": [str(row.get("name") or row.get("agentName") or "unknown") for row in agents],
        "function_counts": dict(sorted(function_counts.items())),
        "invoked_skills": _invoked_skills(trace_path),
        "credential_material_observed": any(
            marker in trace_text
            for marker in ('--save-token', '\"token\":', 'connect_cloud_service_result')
        ),
        **trace,
    }


def _delta(base: Mapping[str, Any], variant: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "report_bytes", "visible_numeric_token_count", "numeric_table_cell_count",
        "external_link_count", "heading_count", "table_count", "estimate_marker_count",
        "model_calls", "input_tokens_cumulative", "output_tokens", "tool_call_count",
        "web_search_count", "structured_financial_query_count", "source_open_or_fetch_count",
        "artifact_syntax_validation_call_count", "post_write_research_call_count",
    ]
    return {key: int(variant.get(key) or 0) - int(base.get(key) or 0) for key in keys}


def build_audit(
    workbuddy_root: str | Path,
    state_root: str | Path,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    errors = validate_config(config)
    workbuddy = Path(workbuddy_root)
    state = Path(state_root)
    rows: list[dict[str, Any]] = []
    for review in config.get("variants") or []:
        sides: dict[str, dict[str, Any]] = {}
        for side in ("base", "variant"):
            source = review[side]
            report_path = workbuddy / str(source["task_dir"]) / str(source["html_file"])
            trace_path = state / "traces" / str(source["trace_file"])
            if not report_path.exists():
                errors.append(f"expert_variant_report_missing:{review['variant_id']}:{side}")
                continue
            if not trace_path.exists():
                errors.append(f"expert_variant_trace_missing:{review['variant_id']}:{side}")
                continue
            sides[side] = _observable_metrics(report_path, trace_path)
        if len(sides) != 2:
            continue
        selected = [str(value) for value in (review.get("ui_configuration") or {}).get("selected_skill_labels") or []]
        aliases = {
            str(key): str(value)
            for key, value in ((review.get("ui_configuration") or {}).get("skill_label_aliases") or {}).items()
        }
        invoked = sides["variant"]["invoked_skills"]
        normalized_invoked = {item.lower().replace(" ", "-") for item in invoked}
        rows.append({
            "variant_id": review["variant_id"],
            "base_case_id": review["base_case_id"],
            "sector": review.get("sector"),
            "report_type": review.get("report_type"),
            "ui_configuration": review.get("ui_configuration") or {},
            "selected_skill_labels_without_observable_invocation": [
                value for value in selected
                if aliases.get(value, value).lower().replace(" ", "-") not in normalized_invoked
            ],
            "base": sides["base"],
            "variant": sides["variant"],
            "delta": _delta(sides["base"], sides["variant"]),
            "scores": review.get("scores") or {},
            "disposition": review.get("disposition"),
            "material_defect_severity": review.get("material_defect_severity"),
            "capability_findings": review.get("capability_findings") or [],
            "quality_findings": review.get("quality_findings") or [],
            "retain_candidates": review.get("retain_candidates") or [],
            "redesign_requirements": review.get("redesign_requirements") or [],
            "official_checks": review.get("official_checks") or [],
            "direct_pack_promotion_allowed": False,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_id": config.get("audit_id"),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "model_boundary": config.get("model_boundary") or {},
        "review_boundary": config.get("review_boundary") or {},
        "variant_count": len(rows),
        "variants": rows,
        "competitive_position": config.get("competitive_position") or {},
        "promotion_summary": {
            "direct_pack_promotion_count": 0,
            "variant_overwrite_count": 0,
            "redesign_variant_count": sum(row["disposition"] == "redesign" for row in rows),
        },
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# WorkBuddy 专家 / Skill 配置变体 A/B 校准审计",
        "",
        f"- audit id：`{audit.get('audit_id')}`",
        f"- status：`{audit.get('status')}`",
        f"- variant count：`{audit.get('variant_count')}`",
        "- 边界：只审可观察工具轨迹，不读取或保存 raw CoT；变体不覆盖基准 case；WorkBuddy 事实不得直接晋升 FIN pack。",
        "",
        "## 总结",
        "",
        "专家配置和渐进式 Skill 可以显著提升行业框架、报告结构与前端完成度，但当前两个变体仍只有一个可观察 Agent，且没有 claim-local lineage、来源打开核验、数值程序或写后语义修复。",
        "",
    ]
    for row in audit.get("variants") or []:
        base = row["base"]
        variant = row["variant"]
        lines.extend([
            f"## {row['variant_id']}（基准 {row['base_case_id']}）",
            "",
            f"- disposition：`{row['disposition']}`；severity：`{row['material_defect_severity']}`。",
            f"- 可观察 Agent：`{base['agent_span_count']} -> {variant['agent_span_count']}`；subagent/handoff：`{base['subagent_or_handoff_count']} -> {variant['subagent_or_handoff_count']}`。",
            f"- 模型调用：`{base['model_calls']} -> {variant['model_calls']}`；工具调用：`{base['tool_call_count']} -> {variant['tool_call_count']}`。",
            f"- WebSearch：`{base['web_search_count']} -> {variant['web_search_count']}`；结构化金融查询：`{base['structured_financial_query_count']} -> {variant['structured_financial_query_count']}`；source-open：`{base['source_open_or_fetch_count']} -> {variant['source_open_or_fetch_count']}`。",
            f"- HTML：`{base['report_bytes']} -> {variant['report_bytes']}` bytes；表格：`{base['table_count']} -> {variant['table_count']}`；外链：`{base['external_link_count']} -> {variant['external_link_count']}`。",
            f"- numeric cell claim-local linkage：`{base['direct_numeric_linkage_ratio']} -> {variant['direct_numeric_linkage_ratio']}`。",
            f"- 实际调用 Skill：{', '.join(variant['invoked_skills']) or 'none'}。",
            "",
            "### 能力发现",
            "",
        ])
        lines.extend(f"- {value}" for value in row.get("capability_findings") or [])
        lines.extend(["", "### 质量发现", ""])
        lines.extend(f"- {value}" for value in row.get("quality_findings") or [])
        lines.extend(["", "### 允许吸收", ""])
        lines.extend(f"- {value}" for value in row.get("retain_candidates") or [])
        lines.extend(["", "### 必须重设计", ""])
        lines.extend(f"- {value}" for value in row.get("redesign_requirements") or [])
        lines.append("")
    position = audit.get("competitive_position") or {}
    lines.extend(["## 生态位与替代压力", "", "### 当前高压区", ""])
    lines.extend(f"- {value}" for value in position.get("current_high_pressure_segments") or [])
    lines.extend(["", "### 尚未被替代", ""])
    lines.extend(f"- {value}" for value in position.get("not_yet_replaced_capabilities") or [])
    lines.extend(["", "### FIN 必须响应", ""])
    lines.extend(f"- {value}" for value in position.get("required_finsight_response") or [])
    return "\n".join(lines).rstrip() + "\n"
