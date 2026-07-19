"""P27 B04 real-reviewer acceptance package builder.

This module turns the P24 B04 infrastructure outputs into an executable
reviewer package. It deliberately does not write the real reviewer evidence
ledger; a real reviewer must still submit evidence through Workbench/API/CLI.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from sec_agent.r53_r60_product_acceptance_b04_gate import default_p24_paths, get_product_acceptance_evidence_status
from sec_agent.r53_r60_runtime_task_spine import rel_path, utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p27_b04_reviewer_acceptance_package_v0_1"
P27_TASK_ID = "p27_scope_task_b04_reviewer_acceptance_package"
P27_REPORT_ID = "p27_b04_reviewer_acceptance_package_report_v0_1"


@dataclass(frozen=True)
class P27Paths:
    package_path: Path
    step_rows_path: Path
    evidence_template_rows_path: Path
    reviewer_candidate_rows_path: Path
    report_path: Path


def default_p27_paths(root: Path) -> P27Paths:
    return P27Paths(
        package_path=root / "data" / "manifests" / "r53_r60_p27_b04_reviewer_acceptance_package_v0_1.json",
        step_rows_path=root / "data" / "manifests" / "r53_r60_p27_b04_reviewer_acceptance_steps_v0_1.jsonl",
        evidence_template_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p27_b04_reviewer_acceptance_evidence_templates_v0_1.jsonl",
        reviewer_candidate_rows_path=root
        / "data"
        / "manifests"
        / "r53_r60_p27_b04_reviewer_acceptance_candidate_refs_v0_1.jsonl",
        report_path=root / "docs" / "internal" / "vnext_20260610" / "r53_r60_p27_b04_reviewer_acceptance_package.zh-CN.md",
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _runtime_candidate_refs(db_path: Path, limit: int = 12) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            task_rows = _rows_to_dicts(
                conn.execute(
                    """
                    select task_id, current_run_id as run_id, case_id, status, query_text, updated_at
                    from research_tasks
                    order by updated_at desc, created_at desc
                    limit ?
                    """,
                    (limit,),
                ).fetchall()
            )
            artifact_rows = _rows_to_dicts(
                conn.execute(
                    """
                    select artifact_ref_id, task_id, run_id, artifact_type, uri, byte_size, created_at
                    from artifact_refs
                    where artifact_type like 'deliverable_%'
                       or artifact_type like '%report%'
                       or artifact_type like '%summary%'
                       or artifact_type like '%dashboard%'
                    order by created_at desc
                    limit ?
                    """,
                    (limit,),
                ).fetchall()
            )
            trace_rows = _rows_to_dicts(
                conn.execute(
                    """
                    select span_id, task_id, run_id, actor, span_kind, name, status, latency_ms, created_at
                    from trace_spans
                    order by created_at desc
                    limit ?
                    """,
                    (limit,),
                ).fetchall()
            )
    except sqlite3.Error:
        return []

    candidates: list[dict[str, Any]] = []
    for row in task_rows:
        candidates.append({"candidate_type": "task", **row})
    for row in artifact_rows:
        candidates.append({"candidate_type": "artifact_ref", **row})
    for row in trace_rows:
        candidates.append({"candidate_type": "trace_span", **row})
    return candidates


def _human_step_rows(human_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    step_order = {
        "reviewer_session": 1,
        "deliverable_acceptance": 2,
        "defect_closeout": 3,
        "visual_acceptance": 4,
        "audit_replay": 5,
    }
    rows: list[dict[str, Any]] = []
    for row in sorted(human_rows, key=lambda item: step_order.get(str(item.get("evidence_type")), 99)):
        evidence_type = str(row.get("evidence_type", ""))
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "step_id": f"p27_step_{evidence_type or row.get('requirement_id', 'unknown')}",
                "requirement_id": row.get("requirement_id", ""),
                "evidence_type": evidence_type,
                "review_action": _review_action_for_type(evidence_type),
                "required_fields": row.get("evidence_needed", []),
                "input_surface": "Workbench Product acceptance evidence panel / API / CLI",
                "must_be_real_human": True,
                "automation_allowed": False,
                "current_status": row.get("current_status", ""),
                "acceptance_impact": "required_for_b04_close" if row.get("required_for_b04_close") else "supporting",
            }
        )
    return rows


def _review_action_for_type(evidence_type: str) -> str:
    return {
        "reviewer_session": "Open Workbench, select an R53-R60 task/case, review task context and record a completed reviewer session.",
        "deliverable_acceptance": "Open rendered deliverables, accept or reject with artifact reference and reviewer comment.",
        "defect_closeout": "Close each pending defect source by repair, regression coverage, or typed-gap acceptance.",
        "visual_acceptance": "Inspect desktop/mobile Workbench screenshots or live UI and record readability/usability decision.",
        "audit_replay": "Trace the final deliverable back through task, Workpaper, artifact refs and trace spans.",
    }.get(evidence_type, "Review requirement and record real-human evidence.")


def _template_rows(human_rows: list[dict[str, Any]], defect_rows: list[dict[str, Any]], workbench_url: str) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for row in human_rows:
        evidence_type = str(row.get("evidence_type", ""))
        template: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "template_id": f"p27_template_{evidence_type}",
            "template_only": True,
            "not_reviewer_evidence": True,
            "workbench_url": workbench_url,
            "evidence_type": evidence_type,
            "reviewer_role": "<lead_analyst|portfolio_manager|senior_research_reviewer|product_owner>",
            "session_id": "<real_reviewer_session_id>",
            "status": "complete",
            "notes": "Template only. Do not copy into the P24 reviewer evidence ledger without replacing placeholders from a real review.",
        }
        if evidence_type == "reviewer_session":
            template.update({"task_id": "<reviewed_task_id>", "case_id": "<reviewed_case_id>"})
        elif evidence_type == "deliverable_acceptance":
            template.update(
                {
                    "decision_status": "<accepted|rejected>",
                    "deliverable_ref": "<deliverable_uri_or_name>",
                    "artifact_ref_id": "<artifact_ref_id>",
                    "review_comment": "<reviewer_reason>",
                }
            )
        elif evidence_type == "visual_acceptance":
            template.update({"visual_decision": "<accepted|rejected>", "browser_screenshot_refs": ["<screenshot_path>"]})
        elif evidence_type == "audit_replay":
            template.update({"task_id": "<reviewed_task_id>", "artifact_ref_ids": ["<artifact_ref_id>"], "trace_ref": "<trace_span_or_sql_ref>"})
        elif evidence_type == "defect_closeout":
            template.update({"closeout_status": "<repaired|regression_covered|typed_gap_accepted>", "covered_source_ids": ["<source_id>"]})
        templates.append(template)

    for row in defect_rows:
        templates.append(
            {
                "schema_version": SCHEMA_VERSION,
                "template_id": f"p27_defect_template_{row.get('source_id', row.get('closeout_id', 'unknown'))}",
                "template_only": True,
                "not_reviewer_evidence": True,
                "evidence_type": "defect_closeout",
                "reviewer_role": "<lead_analyst|portfolio_manager|senior_research_reviewer|product_owner>",
                "session_id": "<real_reviewer_session_id>",
                "closeout_status": "<repaired|regression_covered|typed_gap_accepted>",
                "source_id": row.get("source_id", ""),
                "case_id": row.get("case_id", ""),
                "defect_type": row.get("defect_type", ""),
                "required_closeout": row.get("required_closeout", ""),
                "review_comment": "<why this defect is repaired, regression-covered, or accepted as typed gap>",
                "notes": "Template only. One real defect_closeout evidence row is still required per source_id.",
            }
        )
    return templates


def _write_report(
    *,
    root: Path,
    path: Path,
    package: dict[str, Any],
    step_rows: list[dict[str, Any]],
    template_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> None:
    outputs = package["outputs"]
    lines = [
        "# R53-R60 P27 B04 Reviewer Acceptance Package",
        "",
        "## 状态",
        "",
        f"- package_status: `{package['package_status']}`",
        f"- b04_status_after_p27: `{package['b04_status_after_p27']}`",
        f"- real_reviewer_evidence_row_count: `{package['counts']['real_reviewer_evidence_row_count']}`",
        f"- reviewer_session_count: `{package['counts']['reviewer_session_count']}`",
        f"- ready_reviewer_session_count: `{package['counts']['ready_reviewer_session_count']}`",
        f"- pending human requirements: `{package['counts']['human_evidence_pending_count']}`",
        f"- pending defect closeouts: `{package['counts']['defect_closeout_pending_count']}`",
        "",
        "P27 只生成真实人工验收的执行包，不写入真实 reviewer evidence ledger，也不关闭 B04。",
        "",
        "## Reviewer 执行顺序",
        "",
    ]
    for step in step_rows:
        lines.extend(
            [
                f"### {step['step_id']}",
                "",
                f"- evidence_type: `{step['evidence_type']}`",
                f"- action: {step['review_action']}",
                f"- required_fields: `{', '.join(map(str, step.get('required_fields', [])))}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 写入入口",
            "",
            f"- Workbench: `{package['workbench_url']}` -> R53-R60 工作台 -> Product acceptance evidence",
            "- API: `POST /api/r53-r60/product-acceptance/evidence`",
            "- CLI: `python scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py --help`",
            "",
            "## 候选引用",
            "",
            f"- task / artifact / trace candidate refs: `{len(candidate_rows)}`",
            f"- evidence templates: `{len(template_rows)}`",
            "",
            "## 输出",
            "",
        ]
    )
    for key, value in outputs.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## 关闭条件")
    lines.append("")
    lines.append("B04 只有在真实 reviewer 提交完整 evidence 后，重跑 P24/P21 并看到 `accepted_by_real_human_review` / `closed_by_real_human_product_acceptance` 才能关闭。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_b04_reviewer_acceptance_package(root: Path, *, workbench_url: str = "http://127.0.0.1:18080") -> dict[str, Any]:
    root = root.resolve()
    p24_paths = default_p24_paths(root)
    p27_paths = default_p27_paths(root)
    p24_summary = _read_json(p24_paths.summary_path)
    human_rows = _read_jsonl(p24_paths.human_evidence_rows_path)
    defect_rows = _read_jsonl(p24_paths.defect_closeout_rows_path)
    status = get_product_acceptance_evidence_status(root)
    step_rows = _human_step_rows(human_rows)
    template_rows = _template_rows(human_rows, defect_rows, workbench_url)
    candidate_rows = _runtime_candidate_refs(p24_paths.db_path)
    counts = {
        "human_evidence_requirement_count": len(human_rows),
        "human_evidence_pending_count": int(p24_summary.get("counts", {}).get("human_evidence_pending_count", 0) or 0),
        "defect_closeout_requirement_count": len(defect_rows),
        "defect_closeout_pending_count": int(p24_summary.get("counts", {}).get("defect_closeout_pending_count", 0) or 0),
        "real_reviewer_evidence_row_count": int(status.get("counts", {}).get("real_reviewer_evidence_row_count", 0) or 0),
        "reviewer_session_count": int(status.get("counts", {}).get("session_count", 0) or 0),
        "ready_reviewer_session_count": int(status.get("counts", {}).get("ready_session_count", 0) or 0),
        "review_step_count": len(step_rows),
        "evidence_template_count": len(template_rows),
        "reviewer_candidate_ref_count": len(candidate_rows),
    }
    package_status = "ready_for_real_reviewer_execution" if step_rows and template_rows else "blocked_missing_p24_requirements"
    package = {
        "schema_version": SCHEMA_VERSION,
        "task_id": P27_TASK_ID,
        "report_id": P27_REPORT_ID,
        "generated_at": utc_now_iso(),
        "package_status": package_status,
        "b04_status_after_p27": "open_product_acceptance_required",
        "does_not_close_b04": True,
        "full_chain_broad_eval_allowed": False,
        "workbench_url": workbench_url,
        "source_p24_summary": rel_path(p24_paths.summary_path, root),
        "counts": counts,
        "reviewer_execution_contract": {
            "allowed_entrypoints": [
                "Workbench Product acceptance evidence panel",
                "POST /api/r53-r60/product-acceptance/evidence",
                "scripts/engineering/record_r53_r60_p24_b04_reviewer_acceptance_evidence.py",
            ],
            "forbidden_shortcuts": [
                "editing P24 summary fields to close B04",
                "copying template rows into reviewer evidence without real review",
                "using automation_e2e or deterministic drill rows as human acceptance",
            ],
            "after_real_review": ["rerun P24", "rerun P21", "verify B04 closes only from manifest-backed evidence"],
        },
        "outputs": {
            "package": rel_path(p27_paths.package_path, root),
            "step_rows": rel_path(p27_paths.step_rows_path, root),
            "evidence_template_rows": rel_path(p27_paths.evidence_template_rows_path, root),
            "reviewer_candidate_rows": rel_path(p27_paths.reviewer_candidate_rows_path, root),
            "report": rel_path(p27_paths.report_path, root),
        },
    }
    write_json(p27_paths.package_path, package)
    write_jsonl(p27_paths.step_rows_path, step_rows)
    write_jsonl(p27_paths.evidence_template_rows_path, template_rows)
    write_jsonl(p27_paths.reviewer_candidate_rows_path, candidate_rows)
    _write_report(
        root=root,
        path=p27_paths.report_path,
        package=package,
        step_rows=step_rows,
        template_rows=template_rows,
        candidate_rows=candidate_rows,
    )
    return package


def get_b04_reviewer_acceptance_package(root: Path) -> dict[str, Any]:
    root = root.resolve()
    p27_paths = default_p27_paths(root)
    package = _read_json(p27_paths.package_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "package": package,
        "step_rows": _read_jsonl(p27_paths.step_rows_path),
        "evidence_template_rows": _read_jsonl(p27_paths.evidence_template_rows_path),
        "reviewer_candidate_rows": _read_jsonl(p27_paths.reviewer_candidate_rows_path),
        "report_markdown_path": rel_path(p27_paths.report_path, root) if p27_paths.report_path.exists() else "",
        "package_exists": bool(package),
    }


__all__ = [
    "SCHEMA_VERSION",
    "P27Paths",
    "build_b04_reviewer_acceptance_package",
    "default_p27_paths",
    "get_b04_reviewer_acceptance_package",
]
