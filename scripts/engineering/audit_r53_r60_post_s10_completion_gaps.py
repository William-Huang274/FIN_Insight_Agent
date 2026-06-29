from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


S0_S10_SUMMARY_FILES = [
    ("S0", "r53_r60_unified_backlog_summary_v0_1.json"),
    ("S1", "r53_r60_s1_runtime_task_spine_summary_v0_1.json"),
    ("S2", "r53_r60_s2_tool_sandbox_trace_summary_v0_1.json"),
    ("S3", "r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json"),
    ("S4", "r53_r60_s4_context_graph_skill_registry_summary_v0_1.json"),
    ("S5", "r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json"),
    ("S6", "r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json"),
    ("S7", "r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json"),
    ("S8", "r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json"),
    ("S9", "r53_r60_s9_research_to_quant_lab_summary_v0_1.json"),
    ("S10", "r53_r60_s10_enterprise_release_candidate_summary_v0_1.json"),
]


COMPLETED_SCOPE_ITEMS = [
    {
        "area": "program_governance",
        "covered_by": ["S0", "S10"],
        "status": "scope_pass",
        "evidence": "Machine-readable backlog, gate matrix, release board, S10 release-readiness report.",
    },
    {
        "area": "runtime_spine",
        "covered_by": ["S1", "S5", "S10"],
        "status": "scope_pass",
        "evidence": "SQL-final ResearchTask/TaskRun/TaskEvent/WorkpaperEvent/artifact/checkpoint/trace ledger.",
    },
    {
        "area": "tool_sandbox_contract",
        "covered_by": ["S2", "S10"],
        "status": "scope_pass",
        "evidence": "SandboxPolicy, ApprovalPolicy, ToolInvocationLedger, blocked/approved tool-call rows.",
    },
    {
        "area": "retrieval_evidence_spine",
        "covered_by": ["S3"],
        "status": "scope_pass",
        "evidence": "RetrievalIntent, RoutePolicyMatrix, RouteExecution, candidates, selected evidence, qrels, typed gaps.",
    },
    {
        "area": "graph_skill_context_registry_minimal",
        "covered_by": ["S4"],
        "status": "scope_pass",
        "evidence": "GraphPack, SkillPack, MemoryPack, ContextInjectionPlan and context selection gates.",
    },
    {
        "area": "workpaper_lead_review",
        "covered_by": ["S5", "S6"],
        "status": "scope_pass",
        "evidence": "ResearchObjectiveContract, Workpaper sections, ClaimCards, LeadReviewCheckpoint, JudgmentState, review actions.",
    },
    {
        "area": "deliverable_dashboard_projection",
        "covered_by": ["S7"],
        "status": "scope_pass",
        "evidence": "DeliverablePlan, RenderJob, dashboard projection, composer permission and quality gates.",
    },
    {
        "area": "secondary_market_capital_feedback",
        "covered_by": ["S8"],
        "status": "scope_pass",
        "evidence": "603 issuer packs, bounded signals, typed gaps, graph edges, source registry.",
    },
    {
        "area": "research_to_quant_lab",
        "covered_by": ["S9"],
        "status": "scope_pass",
        "evidence": "FactorHypothesis, PIT dataset, leakage guard, deterministic backtest smoke, FactorCard, experience records.",
    },
    {
        "area": "release_candidate_quality_ops_subset",
        "covered_by": ["S10"],
        "status": "scope_pass",
        "evidence": "Tenant/RBAC, load/chaos/SLA, incident dashboard, release readiness, online eval feedback lifecycle.",
    },
]


PRODUCTION_GAPS = [
    {
        "gap_id": "P-S10-001",
        "area": "production_sla_and_cloud_pilot",
        "source_docs": ["35_R60", "36_S10"],
        "current_state": "local deterministic release-candidate gate only",
        "why_not_done": "S10 intentionally records controlled internal pilot readiness, not cloud/production SLO proof.",
        "required_next_work": "Run cloud-backed multi-user pilot with queue/worker/provider failures, p95/p99 latency, cost budgets, recovery rate, alert routing, rollback rehearsal, and on-call runbook evidence.",
        "blocked_by": "needs pilot environment and longer dogfood window",
        "severity": "release_blocker_for_L4_production",
    },
    {
        "gap_id": "P-R56-001",
        "area": "durable_agent_runtime",
        "source_docs": ["31_R56"],
        "current_state": "S1/S2/S4/S10 provide SQL ledger, tool policy, context registry and trace rows",
        "why_not_done": "LangGraph checkpoint bridge, HIL interrupt/resume, resource/model router ledger, trace export adapter and runtime replay gate are not fully wired to real graph execution.",
        "required_next_work": "Wire actual graph nodes through RuntimeFacade, model/resource router, checkpoint/resume, HIL approval and replay; export SQL trace to optional OTel/Langfuse/Phoenix-compatible spans.",
        "blocked_by": "requires agent graph integration pass",
        "severity": "high",
    },
    {
        "gap_id": "P-R57-001",
        "area": "graph_skill_memory_lifecycle",
        "source_docs": ["32_R57"],
        "current_state": "S4 has minimal GraphPack/SkillPack/MemoryPack registry and ContextInjectionPlan",
        "why_not_done": "Tenant overlays, SkillPatch/GraphPatch/MemoryPatch staging, compression quality gates, staleness/supersession/permission invalidation and behavior eval suite are still planned.",
        "required_next_work": "Implement plug-in graph/skill/memory lifecycle with staging, eval, human approval, canary promotion, invalidation and compression artifacts connected to ContextEngine.",
        "blocked_by": "needs enterprise customization and context lifecycle design pass",
        "severity": "high",
    },
    {
        "gap_id": "P-R58-001",
        "area": "data_ingestion_retrieval_control_plane",
        "source_docs": ["33_R58"],
        "current_state": "S3 covers retrieval evidence spine; prior R-series covers many public-source rows",
        "why_not_done": "IngestionJob, RawSourceDocument, FetchAttempt, ParserRun, storage lineage convention, parser tool contract, DB performance profile and ContextEngine retrieval bridge are not fully productized.",
        "required_next_work": "Build SQL/ObjectStore ingestion control plane with source snapshots, parser metrics, lineage, refresh policy, performance profiles, qrels and retrieval-context bridge.",
        "blocked_by": "requires data engineering release slice",
        "severity": "high",
    },
    {
        "gap_id": "P-R59-001",
        "area": "enterprise_backend_frontend_product_surface",
        "source_docs": ["34_R59"],
        "current_state": "S6/S7 expose workbench drilldown and deliverable/dashboard deterministic surfaces; S10 has release candidate RBAC/load/incident objects",
        "why_not_done": "Java gateway is not yet production framework; frontend still lacks full Research Task Center, Evidence Workbench, Workpaper Builder, Review Queue, Artifact Browser, Admin/Ops Console and upload/data room product surfaces.",
        "required_next_work": "Create enterprise API boundary, idempotency, lease/heartbeat/recovery, artifact/review/deliverable APIs, and product-grade frontend workflows with E2E checks.",
        "blocked_by": "requires backend/frontend implementation program",
        "severity": "high",
    },
    {
        "gap_id": "P-R60-001",
        "area": "full_eval_observability_quality_engineering",
        "source_docs": ["35_R60"],
        "current_state": "S10 has release-candidate subset: demand acceptance, incident, load/chaos/SLA, feedback lifecycle and release report",
        "why_not_done": "Full EvalCase/EvalDataset/EvalRun, TokenCostLedger, parser/chunk/retrieval/context/tool/deliverable node gates, CI/CD integration, sandbox regression, BudgetExceededGate and eval dashboard API are not complete.",
        "required_next_work": "Implement runtime eval store, token/cost ledger, node/full-chain eval suites, QAExecutionPlan/DefectRecord, sandbox regression, BudgetExceededGate and dashboard APIs.",
        "blocked_by": "requires quality engineering release slice",
        "severity": "high",
    },
    {
        "gap_id": "P-PRD-001",
        "area": "product_dogfood_and_user_acceptance",
        "source_docs": ["PRD_20260628", "36_S10"],
        "current_state": "Release candidate artifacts exist but not validated by repeated real analyst/reviewer workflows",
        "why_not_done": "S10 deterministic gates cannot prove workflow value, user trust, reviewer acceptance, or token/cost ROI across real tasks.",
        "required_next_work": "Run internal dogfood over representative research tasks, capture reviewer feedback, defect lifecycle, token/cost quality metrics and accepted/rejected deliverables.",
        "blocked_by": "requires agreed pilot case catalog and reviewer protocol",
        "severity": "release_blocker_for_external_pilot",
    },
]


NEXT_RELEASE_SLICES = [
    {
        "slice_id": "P11",
        "name": "Production Pilot Readiness Gate",
        "primary_gaps": ["P-S10-001", "P-PRD-001"],
        "target": "Cloud/internal pilot evidence for L4_production_candidate, without external client access.",
    },
    {
        "slice_id": "P12",
        "name": "Durable Runtime + HIL + Resource Router",
        "primary_gaps": ["P-R56-001"],
        "target": "Actual agent graph execution uses RuntimeFacade, checkpoint/resume, HIL and model/resource budget ledger.",
    },
    {
        "slice_id": "P13",
        "name": "Graph/Skill/Memory Lifecycle",
        "primary_gaps": ["P-R57-001"],
        "target": "Plug-in graph/skill/memory packs with staging, eval, approval, compression and invalidation gates.",
    },
    {
        "slice_id": "P14",
        "name": "Data Ingestion + Retrieval Control Plane",
        "primary_gaps": ["P-R58-001"],
        "target": "Source snapshots, parser runs, lineage, qrels, route budget and DB/index performance profiles become first-class runtime rows.",
    },
    {
        "slice_id": "P15",
        "name": "Enterprise Workbench Product Surface",
        "primary_gaps": ["P-R59-001"],
        "target": "Task Center, Evidence Workbench, Workpaper Builder, Review Queue, Artifact Browser, Admin/Ops Console and Data Room surfaces.",
    },
    {
        "slice_id": "P16",
        "name": "Quality Engineering + Online Eval Platform",
        "primary_gaps": ["P-R60-001"],
        "target": "Eval registry, token/cost ledger, node/full-chain gates, CI hooks, sandbox regression, defect/gold/failure lifecycle.",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_register(root: Path) -> dict[str, Any]:
    manifest_dir = root / "data" / "manifests"
    dependencies: list[dict[str, Any]] = []
    for slice_id, file_name in S0_S10_SUMMARY_FILES:
        payload = load_json(manifest_dir / file_name)
        dependencies.append(
            {
                "slice_id": slice_id,
                "summary_file": f"data/manifests/{file_name}",
                "exists": bool(payload),
                "status": str(payload.get("status") or "missing"),
                "release_decision": str(payload.get("release_decision") or ""),
                "closeout_level": str(payload.get("closeout_level") or ""),
            }
        )
    dependency_pass_count = len([row for row in dependencies if row["status"] == "pass"])
    return {
        "schema_version": "r53_r60_post_s10_completion_gap_register_v0_1",
        "status": "pass" if dependency_pass_count == len(S0_S10_SUMMARY_FILES) else "blocked",
        "scope": "post_s10_completion_gap_audit",
        "dependency_pass_count": dependency_pass_count,
        "dependency_count": len(S0_S10_SUMMARY_FILES),
        "dependencies": dependencies,
        "completed_scope_items": COMPLETED_SCOPE_ITEMS,
        "production_gaps": PRODUCTION_GAPS,
        "next_release_slices": NEXT_RELEASE_SLICES,
        "decision": "R53-R60 reached controlled internal release-candidate scope pass; next work should target production pilot and productized runtime/data/frontend/eval gaps, not claim full production.",
    }


def render_markdown(register: dict[str, Any]) -> str:
    lines = [
        "# R53-R60 Post-S10 Completion Gap Register",
        "",
        f"- Status: `{register['status']}`",
        f"- Dependency pass: `{register['dependency_pass_count']}/{register['dependency_count']}`",
        "- Decision: R53-R60 has reached controlled internal release-candidate scope pass, but not full production.",
        "",
        "## S0-S10 Dependency Status",
        "",
        "| Slice | Status | Release Decision | Closeout | Summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in register["dependencies"]:
        lines.append(
            f"| `{row['slice_id']}` | `{row['status']}` | `{row['release_decision']}` | `{row['closeout_level']}` | `{row['summary_file']}` |"
        )
    lines.extend(["", "## Covered Scope", ""])
    for item in register["completed_scope_items"]:
        lines.append(f"- `{item['area']}`: `{item['status']}` via {', '.join(item['covered_by'])}. {item['evidence']}")
    lines.extend(["", "## Remaining Production Gaps", ""])
    for gap in register["production_gaps"]:
        lines.extend(
            [
                f"### {gap['gap_id']} `{gap['area']}`",
                "",
                f"- Source docs: `{', '.join(gap['source_docs'])}`",
                f"- Current state: {gap['current_state']}",
                f"- Why not done: {gap['why_not_done']}",
                f"- Required next work: {gap['required_next_work']}",
                f"- Blocked by: {gap['blocked_by']}",
                f"- Severity: `{gap['severity']}`",
                "",
            ]
        )
    lines.extend(["## Suggested Next Release Slices", ""])
    for item in register["next_release_slices"]:
        lines.append(f"- `{item['slice_id']}` {item['name']}: {item['target']} Primary gaps: {', '.join(item['primary_gaps'])}.")
    return "\n".join(lines) + "\n"


def write_outputs(root: Path, register: dict[str, Any]) -> dict[str, str]:
    summary_path = root / "data" / "manifests" / "r53_r60_post_s10_completion_gap_register_v0_1.json"
    report_path = root / "docs" / "internal" / "vnext_20260610" / "r53_r60_post_s10_completion_gap_register.zh-CN.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(register, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown(register), encoding="utf-8")
    return {
        "summary": summary_path.relative_to(root).as_posix(),
        "report": report_path.relative_to(root).as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit R53-R60 post-S10 completion gaps.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    register = build_register(root)
    outputs = write_outputs(root, register)
    print(json.dumps({**register, "outputs": outputs}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if register["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
