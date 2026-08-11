"""Build a bounded semantic and structured-trajectory re-audit for WorkBuddy cases."""

from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Mapping

from bs4 import BeautifulSoup


SCHEMA_VERSION = "finsight_workbuddy_semantic_trajectory_reaudit_v0_1"
CONFIG_SCHEMA = "finsight_workbuddy_semantic_trajectory_review_config_v0_1"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def validate_review_config(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != CONFIG_SCHEMA:
        errors.append("semantic_review_config_schema_invalid")
    cases = payload.get("cases") or []
    case_ids = [str(row.get("case_id") or "") for row in cases]
    if len(case_ids) != 12 or len(case_ids) != len(set(case_ids)) or any(not value for value in case_ids):
        errors.append("semantic_review_case_ids_invalid")
    required_scores = set(payload.get("required_score_dimensions") or [])
    for row in cases:
        scores = set((row.get("scores") or {}).keys())
        if required_scores - scores:
            errors.append(f"semantic_review_scores_missing:{row.get('case_id')}")
        if row.get("disposition") not in {"improve", "redesign", "reject_as_reference"}:
            errors.append(f"semantic_review_disposition_invalid:{row.get('case_id')}")
    return errors


def _report_metrics(path: Path) -> dict[str, Any]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    visible_text = soup.get_text(" ", strip=True)
    numeric_tokens = re.findall(
        r"(?<!\w)(?:[$¥€£]?\s?\d[\d,.]*\s?(?:%|bp|bps|[KMBT]|亿|万亿|百万|十亿|倍|x|×)?)",
        visible_text,
        flags=re.IGNORECASE,
    )
    numeric_cells = [
        cell for cell in soup.find_all(["td", "th"])
        if re.search(r"\d", cell.get_text(" ", strip=True))
    ]
    linked_numeric_cells = [cell for cell in numeric_cells if cell.find("a", href=True)]
    links = [str(anchor.get("href")) for anchor in soup.find_all("a", href=True)]
    return {
        "visible_numeric_token_count": len(numeric_tokens),
        "numeric_table_cell_count": len(numeric_cells),
        "directly_linked_numeric_table_cell_count": len(linked_numeric_cells),
        "direct_numeric_linkage_ratio": round(len(linked_numeric_cells) / len(numeric_cells), 4) if numeric_cells else 0.0,
        "external_link_count": sum(link.startswith(("http://", "https://")) for link in links),
        "heading_count": len(soup.find_all(["h1", "h2", "h3"])),
        "table_count": len(soup.find_all("table")),
        "estimate_marker_count": len(re.findall(r"估算|估计|estimate|estimated|~|约", visible_text, flags=re.IGNORECASE)),
        "source_list_is_detached_from_numeric_cells": bool(numeric_cells) and not linked_numeric_cells,
    }


def _trace_path(state_root: Path, session: Mapping[str, Any]) -> Path | None:
    trace_dir = state_root / "traces" / str(session.get("pid"))
    candidates = [path for path in trace_dir.glob("*.json") if path.stat().st_size >= 100_000]
    return max(candidates, key=lambda item: item.stat().st_size) if candidates else None


def _trace_metrics(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    trace = payload.get("trace") or {}
    functions = [row for row in payload.get("spans") or [] if row.get("type") == "function"]
    counts = Counter(str(row.get("name") or "unknown") for row in functions)
    web_queries = [
        str(_object(row.get("toolInput")).get("query") or "").strip().lower()
        for row in functions
        if row.get("name") == "WebSearch"
    ]
    similarities = [
        SequenceMatcher(None, web_queries[left], web_queries[right]).ratio()
        for left in range(len(web_queries))
        for right in range(left + 1, len(web_queries))
    ]
    source_open_names = {"WebFetch", "Fetch", "OpenURL", "BrowserOpen", "ReadUrl"}
    source_open_count = sum(str(row.get("name")) in source_open_names for row in functions)
    structured_financial_queries = sum(
        row.get("name") == "Bash"
        and any(token in str(row.get("toolInput") or "").lower() for token in ("neodata", "westock", "query.py"))
        for row in functions
    )
    report_write_index = next(
        (
            index for index, row in enumerate(functions)
            if row.get("name") == "Write" and ".html" in str(row.get("toolInput") or "").lower()
        ),
        len(functions),
    )
    research_names = {"WebSearch", "WebFetch", "Fetch", "OpenURL", "ReadUrl", "DeferExecuteTool"}
    post_write_research = sum(
        row.get("name") in research_names
        or (
            row.get("name") == "Bash"
            and any(token in str(row.get("toolInput") or "").lower() for token in ("neodata", "westock", "query.py"))
        )
        for row in functions[report_write_index + 1 :]
    )
    validation_count = sum(
        row.get("name") == "Bash"
        and any(token in str(row.get("toolInput") or "").lower() for token in ("node --check", "syntax", "validate", "grep -n"))
        for row in functions
    )
    explicit_errors = sum(row.get("status") == "error" or bool(row.get("error")) for row in functions)
    output_errors = sum(
        str(row.get("toolOutput") or "").lstrip().startswith(("Error", '{"content":"Error'))
        for row in functions
        if row.get("status") != "error"
    )
    model = trace.get("modelInfo") or {}
    input_tokens = int(model.get("totalInputTokens") or 0)
    cached_tokens = int(model.get("totalCachedTokens") or 0)
    return {
        "trace_status": trace.get("status"),
        "model_calls": int(model.get("callCount") or 0),
        "input_tokens_cumulative": input_tokens,
        "cached_tokens_cumulative": cached_tokens,
        "uncached_input_tokens_cumulative": input_tokens - cached_tokens,
        "output_tokens": int(model.get("totalOutputTokens") or 0),
        "tool_call_count": sum(counts.values()),
        "tool_counts": dict(sorted(counts.items())),
        "web_search_count": counts.get("WebSearch", 0),
        "source_open_or_fetch_count": source_open_count,
        "structured_financial_query_count": structured_financial_queries,
        "subagent_or_handoff_count": sum(counts.get(name, 0) for name in ("Agent", "Subagent", "Handoff")),
        "explicit_function_error_count": explicit_errors,
        "status_ok_but_output_error_count": output_errors,
        "post_write_research_call_count": post_write_research,
        "artifact_syntax_validation_call_count": validation_count,
        "max_web_query_similarity": round(max(similarities, default=0.0), 4),
        "claim_to_observation_lineage_count": 0,
        "raw_generation_or_reasoning_reviewed": False,
    }


def build_reaudit(
    workbuddy_root: str | Path,
    state_root: str | Path,
    source_config: Mapping[str, Any],
    review_config: Mapping[str, Any],
) -> dict[str, Any]:
    errors = validate_review_config(review_config)
    workbuddy = Path(workbuddy_root)
    state = Path(state_root)
    sessions = {
        Path(row.get("cwd", "")).name.lower(): row
        for path in (state / "sessions").glob("*.json")
        for row in [load_json(path)]
        if row.get("cwd")
    }
    source_by_id = {str(row["case_id"]): row for row in source_config.get("cases") or []}
    review_by_id = {str(row["case_id"]): row for row in review_config.get("cases") or []}
    rows: list[dict[str, Any]] = []
    for case_id in sorted(review_by_id):
        source = source_by_id.get(case_id)
        review = review_by_id[case_id]
        if not source:
            errors.append(f"semantic_review_source_case_missing:{case_id}")
            continue
        report_path = workbuddy / str(source["task_dir"]) / str(source["html_file"])
        session = sessions.get(str(source["task_dir"]).lower())
        trace_path = _trace_path(state, session or {}) if session else None
        if not report_path.exists() or not trace_path:
            errors.append(f"semantic_review_artifact_or_trace_missing:{case_id}")
            continue
        scores = {key: int(value) for key, value in (review.get("scores") or {}).items()}
        rows.append(
            {
                "case_id": case_id,
                "sector": source.get("sector"),
                "report_type": source.get("report_type"),
                "disposition": review.get("disposition"),
                "material_defect_severity": review.get("material_defect_severity"),
                "scores": scores,
                "score_mean": round(sum(scores.values()) / len(scores), 2) if scores else 0.0,
                "semantic_findings": review.get("semantic_findings") or [],
                "trajectory_findings": review.get("trajectory_findings") or [],
                "retain_candidates": review.get("retain_candidates") or [],
                "improve_or_redesign_candidates": review.get("improve_or_redesign_candidates") or [],
                "reject_patterns": review.get("reject_patterns") or [],
                "report_metrics": _report_metrics(report_path),
                "trajectory_metrics": _trace_metrics(trace_path),
                "runtime_evidence_status": "not_runtime_evidence",
                "direct_pack_promotion_allowed": False,
            }
        )
    dimensions = list(review_config.get("required_score_dimensions") or [])
    dimension_means = {
        dimension: round(sum(row["scores"][dimension] for row in rows) / len(rows), 2)
        for dimension in dimensions
    } if rows else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_id": review_config.get("audit_id"),
        "status": "pass" if not errors and len(rows) == 12 else "fail",
        "status_meaning": "semantic_and_structured_trajectory_review_completed_not_pack_promotion",
        "model_boundary": review_config.get("model_boundary") or {},
        "case_count": len(rows),
        "score_scale": review_config.get("score_scale") or {},
        "dimension_means": dimension_means,
        "critical_systemic_findings": review_config.get("critical_systemic_findings") or [],
        "official_verification_samples": review_config.get("official_verification_samples") or [],
        "cases": rows,
        "pack_candidate_matrix": review_config.get("pack_candidate_matrix") or [],
        "global_reject_patterns": review_config.get("global_reject_patterns") or [],
        "promotion_summary": {
            "direct_workbuddy_pack_promotion_count": 0,
            "candidate_count": len(review_config.get("pack_candidate_matrix") or []),
            "retain_with_independent_evidence_count": sum(
                row.get("decision") == "retain_with_independent_evidence"
                for row in review_config.get("pack_candidate_matrix") or []
            ),
            "redesign_then_pack_count": sum(
                row.get("decision") == "redesign_then_pack"
                for row in review_config.get("pack_candidate_matrix") or []
            ),
            "reject_count": len(review_config.get("global_reject_patterns") or []),
        },
        "review_boundaries": {
            "raw_reasoning_or_generation_span_reviewed": False,
            "all_report_claims_exhaustively_verified": False,
            "structured_tool_inputs_outputs_and_final_reports_reviewed": True,
            "workbuddy_output_is_mature_reference": False,
            "pack_compilation_allowed_without_fin_fixtures": False,
            "paid_model_or_fin_full_chain_run": False,
        },
        "errors": errors,
    }


def render_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        "# WorkBuddy 12-case 语义与结构化轨迹复审",
        "",
        "日期：2026-07-11",
        "",
        f"状态：`{audit['status']}`。含义：{audit['status_meaning']}。",
        "",
        "## 总结",
        "",
        f"- Case：{audit['case_count']}。直接晋升 WorkBuddy pack：`{audit['promotion_summary']['direct_workbuddy_pack_promotion_count']}`。",
        f"- Pack candidates：{audit['promotion_summary']['candidate_count']}；retain with independent evidence：{audit['promotion_summary']['retain_with_independent_evidence_count']}；redesign then pack：{audit['promotion_summary']['redesign_then_pack_count']}。",
        "- 全部 12 个 case 的数值表格单元格均未提供 claim-local citation；source list 与数值 claim 分离。",
        "- 复审读取最终 HTML 与结构化 tool input/output、error、sequence 和 token metadata；未读取或复制 raw reasoning/generation spans。",
        "",
        "## 系统性发现",
        "",
    ]
    lines.extend(f"- {value}" for value in audit.get("critical_systemic_findings") or [])
    lines.extend(
        [
            "",
            "## Case 裁决",
            "",
            "| Case | Sector | Type | Decision | Severity | Semantic | Evidence | Numeric | Tool grounding | Repair |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in audit.get("cases") or []:
        scores = row["scores"]
        lines.append(
            f"| {row['case_id']} | {row['sector']} | {row['report_type']} | {row['disposition']} | "
            f"{row['material_defect_severity']} | {scores['decision_cell_semantics']} | {scores['evidence_binding']} | "
            f"{scores['numeric_integrity']} | {scores['tool_grounding']} | {scores['repair_reflection']} |"
        )
    lines.extend(["", "## 逐案发现", ""])
    for row in audit.get("cases") or []:
        lines.extend(
            [
                f"### {row['case_id']} - {row['disposition']}",
                "",
                "语义：" + "；".join(row.get("semantic_findings") or []),
                "",
                "轨迹：" + "；".join(row.get("trajectory_findings") or []),
                "",
                "可保留候选：" + "；".join(row.get("retain_candidates") or ["无"]),
                "",
                "必须改进：" + "；".join(row.get("improve_or_redesign_candidates") or ["无"]),
                "",
                "拒绝继承：" + "；".join(row.get("reject_patterns") or ["无"]),
                "",
            ]
        )
    lines.extend(["## Pack 候选", ""])
    for candidate in audit.get("pack_candidate_matrix") or []:
        lines.extend(
            [
                f"### {candidate['candidate_id']} - {candidate['decision']}",
                "",
                f"层级：`{candidate['layer']}`；Owner：`{candidate['owner']}`；来源 cases：{', '.join(candidate.get('source_case_ids') or [])}。",
                "",
                "计划内容：" + "；".join(candidate.get("content") or []),
                "",
                "进入 pack 前：" + "；".join(candidate.get("required_improvements") or []),
                "",
                "禁止继承：" + "；".join(candidate.get("forbidden_carryover") or []),
                "",
            ]
        )
    lines.extend(["## 全局拒绝模式", ""])
    lines.extend(f"- {value}" for value in audit.get("global_reject_patterns") or [])
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "本复审不是 FIN runtime pass、pack promotion、paid model run 或 full-chain。Pack candidates 只表示拟实现内容；必须经过 FIN schema、deterministic fixture、独立 rubric、Evidence/Numeric Gate 和 M3 shadow comparison。",
            "",
        ]
    )
    return "\n".join(lines)
