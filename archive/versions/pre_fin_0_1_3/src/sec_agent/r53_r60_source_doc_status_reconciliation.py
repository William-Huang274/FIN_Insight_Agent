"""P22 source-document status reconciliation for R55/R57/R58/R59/R60.

This module makes the R55/R57/R58/R59/R60 technical plans reflect current
implementation evidence from S/P closeout artifacts.  It does not claim the
whole product is release-ready; partial rows remain partial with explicit
boundaries and next actions.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from sec_agent.r53_r60_runtime_task_spine import utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p22_source_doc_status_reconciliation_v0_1"
CURRENT_STATUS_MARKER = "## P22 Current Status Reconciliation"

SOURCE_DOCS = {
    "R55": "docs/architecture/agent_graph_vnext/30_r55_deliverable_studio_dashboard_projection_technical_plan.zh-CN.md",
    "R57": "docs/architecture/agent_graph_vnext/32_r57_graph_skill_memory_pack_operating_model.zh-CN.md",
    "R58": "docs/architecture/agent_graph_vnext/33_r58_db_rag_retrieval_data_pipeline_control_plane.zh-CN.md",
    "R59": "docs/architecture/agent_graph_vnext/34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md",
    "R60": "docs/architecture/agent_graph_vnext/35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md",
}

EVIDENCE_REFS = {
    "S1": "data/manifests/r53_r60_s1_runtime_task_spine_summary_v0_1.json",
    "S2": "data/manifests/r53_r60_s2_tool_sandbox_trace_summary_v0_1.json",
    "S3": "data/manifests/r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json",
    "S4": "data/manifests/r53_r60_s4_context_graph_skill_registry_summary_v0_1.json",
    "S7": "data/manifests/r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json",
    "S8": "data/manifests/r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json",
    "S9": "data/manifests/r53_r60_s9_research_to_quant_lab_summary_v0_1.json",
    "S10": "data/manifests/r53_r60_s10_enterprise_release_candidate_summary_v0_1.json",
    "P12": "data/manifests/r53_r60_p12_durable_runtime_hil_resource_router_summary_v0_1.json",
    "P13": "data/manifests/r53_r60_p13_graph_skill_memory_lifecycle_summary_v0_1.json",
    "P14": "data/manifests/r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json",
    "P15": "data/manifests/r53_r60_p15_enterprise_workbench_product_surface_summary_v0_1.json",
    "P16": "data/manifests/r53_r60_p16_quality_engineering_online_eval_summary_v0_1.json",
    "P17": "data/manifests/r53_r60_p17_controlled_internal_pilot_execution_summary_v0_1.json",
    "P18": "data/manifests/r53_r60_p18_internal_reviewer_dogfood_window_summary_v0_1.json",
    "P19": "data/manifests/r53_r60_p19_internal_reviewer_action_capture_summary_v0_1.json",
    "P21": "data/manifests/r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json",
}


def _row(
    doc_id: str,
    item_id: str,
    title: str,
    current_status: str,
    evidence_keys: Iterable[str],
    boundary: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "source_doc_status_row",
        "doc_id": doc_id,
        "source_doc": SOURCE_DOCS[doc_id],
        "item_id": item_id,
        "title": title,
        "current_status": current_status,
        "evidence_refs": [EVIDENCE_REFS[key] for key in evidence_keys],
        "boundary": boundary,
        "next_action": next_action,
        "broad_full_chain_quality_evidence_allowed": False,
    }


SOURCE_STATUS_ROWS: list[dict[str, Any]] = [
    _row("R55", "R55-S01-deliverable-plan-contract", "DeliverablePlan / section / artifact contract", "done", ["S7", "P15"], "Scope contract exists; not a full template library.", "Keep renderer/template variants as separate product-surface work."),
    _row("R55", "R55-S02-render-job-artifact-contract", "RenderJob and ArtifactRef traceability", "done", ["S7", "P15"], "Artifact contract is traceable; polished multi-format rendering remains product work.", "Bind real DOCX/PPTX/XLSX/PDF renderers in later Deliverable Studio slice."),
    _row("R55", "R55-S03-dashboard-projection-parity", "Dashboard projection parity", "partial", ["S7", "P15", "P18", "P19"], "Projection rows exist, but frontend visual E2E and real reviewer workflow are not product-pass.", "Close under P23 with browser E2E and reviewer acceptance."),
    _row("R55", "R55-S04-composer-permission-boundary", "Composer tool permission boundary", "partial", ["S2", "S7", "P16"], "Contracts and sandbox regression exist; runtime UI approval surface still needs product validation.", "Verify composer cannot fetch new facts in real Workbench sessions."),
    _row("R55", "R55-S05-multi-format-output-surface", "Markdown/Word/PPT/Excel/PDF deliverable surface", "partial", ["S7", "P15"], "Planning and artifact contracts exist; production renderer depth is still bounded.", "Implement and visually verify format-specific renderers before product release."),
    _row("R55", "R55-S06-template-governance", "Template governance and client-safe policy", "partial", ["S7", "P15", "P16"], "Governance objects exist, but tenant template lifecycle is not rolled out.", "Connect template approval to R57/R59 tenant overlay and R60 eval gates."),
    _row("R55", "R55-S07-graph-visual-deliverables", "Graph, timeline, and mind-map deliverables", "partial", ["S4", "S7", "P15"], "Graph/artifact projection exists; final visual renderer quality is not proven.", "Add deterministic renderer tests and human visual review."),
    _row("R55", "R55-S08-deliverable-product-acceptance", "Deliverable Studio product acceptance", "partial", ["P15", "P19", "P21"], "P21 still blocks broad full-chain and product-release claims.", "Do not count broad full-chain as quality evidence until P23/P24 close."),
    _row("R57", "R57-D01-graph-capability-registry", "GraphPack registry schema and inventory", "done", ["S4", "P13"], "Controlled lifecycle drill only; not full tenant rollout.", "Keep canary/promotion gates active for new graph packs."),
    _row("R57", "R57-D02-skillpack-registry", "Structured SkillPack contract", "done", ["S4", "P13"], "Registry exists; behavior quality still depends on specialist eval depth.", "Extend specialist behavior eval with real workpaper cases."),
    _row("R57", "R57-D03-memorypack-registry", "MemoryPack tiers and metadata contract", "done", ["S4", "P13"], "Memory has no standalone fact authority.", "Preserve ref-only exact facts in future memory injections."),
    _row("R57", "R57-D04-lead-graph-skill-selector", "Lead graph/skill selector", "partial", ["S4", "P13"], "Policy and active versions exist; full live graph nodes are not all migrated to dynamic selection.", "Bind Research Lead planner to active GraphPack/SkillPack versions in runtime cases."),
    _row("R57", "R57-D05-specialist-required-pack-gate", "Specialist required-pack gate", "partial", ["S4", "P13", "P16"], "Registry gates exist; not every specialist route has live consumption evidence.", "Add specialist-pack consumption checks to P23/P24 task cases."),
    _row("R57", "R57-D06-learning-patch-lifecycle", "Graph/Skill/Memory patch staging and approval", "done", ["P13"], "Agents cannot self-promote active assets.", "Keep human approval and canary required."),
    _row("R57", "R57-D07-behavior-eval-suite", "Behavior eval suite", "partial", ["P13", "P16"], "Deterministic and patch evals exist; real reviewer behavioral evidence remains limited.", "Promote real failures into R60 regression cases."),
    _row("R57", "R57-D08-tenant-overlay-contract", "Tenant overlay contract", "partial", ["P13"], "Tenant overlay rows exist; no full multi-tenant rollout.", "Run pilot tenant overlay acceptance before product pass."),
    _row("R57", "R57-D09-contextengine-lifecycle-contract", "ContextEngine lifecycle contract", "partial", ["S4", "P13", "P14"], "Context policy and bridge exist; not every live node reads active strategy dynamically.", "Migrate graph nodes to ContextEngine plan injection."),
    _row("R57", "R57-D10-memory-promotion-invalidation-gates", "Memory promotion and invalidation gates", "done", ["P13"], "Controlled lifecycle drill, not production traffic.", "Keep invalidation rows tied to eval outcomes."),
    _row("R57", "R57-D11-context-compression-policy", "Context compression policy", "partial", ["S4", "P13"], "Policy exists; compression quality across all agent contexts is not fully proven.", "Extend R60 compression regression cases."),
    _row("R57", "R57-D12-context-compression-artifact", "ContextCompressionArtifact and injection linkage", "partial", ["S4", "P13", "P14"], "Artifact linkage exists in control plane; full runtime migration remains bounded.", "Require compression refs in every Research Lead/Specialist run."),
    _row("R57", "R57-D13-compression-quality-gates", "Compression quality gates", "partial", ["P13", "P16"], "Quality gates exist for scope; broader case coverage remains pending.", "Add exact/citation/numeric preservation to P23/P24 eval sets."),
    _row("R58", "R58-D01-retrieval-intent-taxonomy", "Retrieval intent schema and classifier contract", "done", ["S3", "P14"], "Representative intent set exists.", "Expand intents only via versioned route policy."),
    _row("R58", "R58-D02-route-policy-matrix", "Route policy matrix", "done", ["S3", "P14"], "Policies are control-plane ready, not broad production tuning.", "Keep source-family quota and forbidden boundary tests active."),
    _row("R58", "R58-D03-query-rewrite-facet-plan", "Query rewrite and facet plan", "partial", ["S3", "P14"], "Facet/retrieval plan exists; query drift and full intent coverage need more cases.", "Add qrels-backed query rewrite eval before broad full-chain."),
    _row("R58", "R58-D04-hybrid-recall-rerank-policy", "Hybrid recall/rerank policy", "partial", ["S3", "P14"], "Candidate/drop ledger exists; rerank quality is not fully tuned.", "Run recall/rerank eval cohorts before research-quality claims."),
    _row("R58", "R58-D05-retrieval-execution-ledger", "Retrieval execution ledger", "done", ["S3", "P14"], "Ledger rows exist with selected/dropped evidence.", "Use as required input for full-chain cases."),
    _row("R58", "R58-D06-retrieval-eval-qrels", "Retrieval qrels and gold refs", "partial", ["S3", "P16"], "Initial qrels/eval rows exist but coverage is small.", "Grow qrels by failure/gold lifecycle."),
    _row("R58", "R58-D07-data-ingestion-contract", "IngestionJob / RawSourceDocument / FetchAttempt / ParserRun", "done", ["P14"], "Representative modalities only; not full crawler coverage.", "Onboard real adapters source-family by source-family."),
    _row("R58", "R58-D08-storage-lineage-convention", "Storage and lineage convention", "done", ["P14"], "Lineage is ready for scope.", "Apply to new ingestion outputs."),
    _row("R58", "R58-D09-parser-tool-contract", "Crawler/fetcher/parser/verifier/authority mapper contract", "done", ["P14", "P16"], "Parser contracts exist; source-specific coverage remains data-depth work.", "Do not promote raw snippets without parser run."),
    _row("R58", "R58-D10-database-performance-profile", "Database/index performance profile", "partial", ["P14", "P16"], "Local profile recorded; production p95/p99 SLA is not proven.", "Run load/SLA gates after runtime/data live integration."),
    _row("R58", "R58-D11-contextengine-retrieval-bridge", "Retrieval ledger to ContextEngine bridge", "done", ["P14"], "Bridge exists; full node migration remains bounded.", "Require ContextInjectionPlan refs in live graph runs."),
    _row("R58", "R58-D12-release-gate", "Retrieval/data-pipeline release gate", "partial", ["P14", "P16", "P21"], "Scope gates pass; broad full-chain remains blocked by product/depth gates.", "Close P23/P24 before release-quality full-chain."),
    _row("R58", "R58-D13-reference-source-ledger", "ReferenceSourceLedger and ChangeLedger", "done", ["P16"], "Reference governance rows exist.", "Maintain update/delete/rollback reasons."),
    _row("R58", "R58-D14-reference-adoption-performance-gate", "Reference adoption performance gate", "done", ["P16"], "Performance profile exists for absorbed designs.", "Review profile after each reference adoption."),
    _row("R59", "R59-D01-current-surface-inventory", "Current backend/frontend surface inventory", "done", ["P15"], "Inventory exists for scope.", "Keep updated when UI/backend files change."),
    _row("R59", "R59-D02-api-boundary-contract", "Java/Python API boundary", "partial", ["P12", "P15"], "Contracts exist; full production migration is not complete.", "Run live migration and replay tests before product pass."),
    _row("R59", "R59-D03-task-run-state-machine", "Task run state machine", "done", ["S1", "P12"], "SQL-final state machine exists for scope.", "Keep legal transition tests active."),
    _row("R59", "R59-D04-sql-final-task-audit", "SQL-final task audit", "done", ["S1", "P16"], "SQL ledger is final audit source.", "Do not use Redis as final audit source."),
    _row("R59", "R59-D05-queue-worker-recovery", "Queue/worker recovery", "partial", ["P12", "S10"], "Recovery drill exists; real load/chaos SLA remains open.", "Run 10-20 task load and worker-crash tests."),
    _row("R59", "R59-D06-sse-event-replay", "SSE + event replay", "partial", ["P15", "P18"], "Projection exists; browser visual E2E is still pending.", "Verify reconnect/replay in real frontend flow."),
    _row("R59", "R59-D07-auth-tenant-rbac", "Auth / tenant / RBAC", "partial", ["P15", "S10"], "Positive/negative RBAC contracts exist; full org rollout is pending.", "Run cross-tenant browser/API regression."),
    _row("R59", "R59-D08-artifact-browser", "Artifact Browser", "done", ["P15"], "Artifact browser links trace/gate/source refs for scope.", "Add product visual QA later."),
    _row("R59", "R59-D09-evidence-workbench-ui", "Evidence Workbench UI", "partial", ["P15", "P16"], "Data/API projection exists; polished React visual E2E not complete.", "Run browser drilldown acceptance."),
    _row("R59", "R59-D10-workpaper-builder-ui", "Workpaper Builder UI", "partial", ["P15", "P19"], "Review action capture exists; multi-day human workflow pending.", "Run real reviewer sessions."),
    _row("R59", "R59-D11-review-queue-ui", "Review Queue UI", "partial", ["P15", "P18", "P19"], "Append-only review actions exist; real adoption pending.", "Close through P23."),
    _row("R59", "R59-D12-deliverable-studio-ui", "Deliverable Studio UI", "partial", ["S7", "P15"], "Contracts exist; full renderer/UI quality pending.", "Implement visual E2E and renderer QA."),
    _row("R59", "R59-D13-dashboard-watchlist-projection", "Dashboard projection", "partial", ["S7", "P15", "P18"], "Projection rows exist; frontend visual/product acceptance pending.", "Add browser dashboard acceptance."),
    _row("R59", "R59-D14-admin-ops-console", "Admin/Ops console", "partial", ["P15", "P16"], "Ops rows and projections exist; sustained incident monitoring not proven.", "Run live incident dashboard drill."),
    _row("R59", "R59-D15-upload-data-room-input", "Upload/Data Room surface", "partial", ["P14", "P15"], "Upload/data-room contracts exist; real file ingestion UI is not product-pass.", "Run upload-to-parser-to-evidence E2E."),
    _row("R59", "R59-D16-load-and-chaos-gate", "Load/chaos gate", "partial", ["S10", "P16"], "Controlled chaos rows exist; cloud/prod SLA not proven.", "Run load/SLA after runtime live integration."),
    _row("R59", "R59-D17-reference-source-ledger", "Reference source ledger", "done", ["P16"], "Reference ledger exists.", "Maintain provenance for every reference update."),
    _row("R59", "R59-D18-reference-change-performance-ledger", "Reference change/performance ledger", "done", ["P16"], "Reference performance profile exists.", "Review profile during adoption/removal."),
    _row("R59", "R59-D19-sandbox-policy-contract", "Sandbox / approval policy contract", "done", ["S2", "P16"], "Policy contract and regression exist.", "Keep fail-closed path tests active."),
    _row("R59", "R59-D20-sandbox-ui-and-regression-gate", "Sandbox UI / eval gate", "partial", ["P15", "P16"], "Regression exists; UI permission visibility still needs browser acceptance.", "Expose tool allow/block reasons in Workbench E2E."),
    _row("R60", "R60-D01", "Eval registry schema", "done", ["P16"], "Eval registry exists for scope.", "Keep dataset versions mandatory."),
    _row("R60", "R60-D02", "Trace / usage schema", "done", ["P16"], "Trace and model/tool/retrieval/parser metrics exist.", "Propagate to every runtime node."),
    _row("R60", "R60-D03", "TokenCostLedger", "done", ["P16"], "Token/cost ledgers exist.", "Use cost-quality tradeoff in release gates."),
    _row("R60", "R60-D04", "Node eval gates", "done", ["P16"], "Node gates and failure taxonomy exist.", "Expand failure cases over time."),
    _row("R60", "R60-D05", "Full-chain eval harness", "partial", ["P16", "P21"], "Harness exists, but broad full-chain quality claims are blocked.", "Run only targeted integration smoke until P23/P24 close."),
    _row("R60", "R60-D06", "Online eval feedback loop", "partial", ["P16", "P19"], "Failure/regression rows exist; sustained production feedback loop is not live.", "Connect real reviewer/product feedback into regression lifecycle."),
    _row("R60", "R60-D07", "DemandAcceptanceRecord", "done", ["P16"], "Demand acceptance records exist.", "Keep Product/Engineering/Quality/Ops acceptance separate."),
    _row("R60", "R60-D08", "QAExecutionPlan / DefectRecord", "done", ["P16"], "QA plans and defect records exist.", "Use in every slice closeout."),
    _row("R60", "R60-D09", "Failure / gold lifecycle", "done", ["P16"], "Failure/gold/regression lifecycle exists.", "Require second review before final gold promotion."),
    _row("R60", "R60-D10", "Incident dashboard", "partial", ["P16"], "Incident rows/projections exist; sustained monitoring window is not proven.", "Run live incident drill."),
    _row("R60", "R60-D11", "Release readiness report", "partial", ["S10", "P16", "P21"], "Readiness report exists, but product/depth blockers remain.", "Do not mark whole-product release until P23/P24 close."),
    _row("R60", "R60-D12", "CI/CD gate integration", "partial", ["P16"], "Equivalent scripts/gates exist; hosted CI integration is not established.", "Wire into CI or document equivalent release command."),
    _row("R60", "R60-D13", "Sandbox regression", "done", ["P16"], "Sandbox regression records exist.", "Keep negative cases active."),
    _row("R60", "R60-D14", "Load / chaos / SLA tests", "partial", ["S10", "P16"], "Controlled chaos rows exist; p95/p99 SLA not proven.", "Run load/SLA under target resource profile."),
    _row("R60", "R60-D15", "Eval dashboard API", "partial", ["P15", "P16"], "Dashboard projections exist; product visual flow is pending.", "Verify in Workbench browser E2E."),
    _row("R60", "R60-D16", "BudgetExceededGate", "done", ["P16"], "BudgetExceededGate exists.", "Enforce fail-closed behavior in model runs."),
    _row("R60", "R60-D17", "ReferenceSourceLedger / ChangeLedger", "done", ["P16"], "Reference governance ledgers exist.", "Keep update/delete reasons mandatory."),
    _row("R60", "R60-D18", "ReferenceAdoptionPerformanceProfile", "done", ["P16"], "Adoption performance profiles exist.", "Review profile after every reference design change."),
]


def _status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("current_status", "missing")) for row in rows)
    return dict(sorted(counts.items()))


def _doc_counts(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, Counter[str]] = {}
    for row in rows:
        doc_id = str(row["doc_id"])
        result.setdefault(doc_id, Counter())[str(row["current_status"])] += 1
    return {doc_id: dict(sorted(counter.items())) for doc_id, counter in sorted(result.items())}


def _source_doc_markers(root: Path) -> dict[str, bool]:
    markers: dict[str, bool] = {}
    for doc_id, rel_path in SOURCE_DOCS.items():
        path = root / rel_path
        markers[doc_id] = path.exists() and CURRENT_STATUS_MARKER in path.read_text(encoding="utf-8")
    return markers


def _missing_evidence_refs(root: Path, rows: Iterable[dict[str, Any]]) -> list[str]:
    missing: set[str] = set()
    for row in rows:
        for rel_path in row.get("evidence_refs", []):
            if not (root / rel_path).exists():
                missing.add(rel_path)
    return sorted(missing)


def p22_gate_rows(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markers = _source_doc_markers(root)
    missing_evidence = _missing_evidence_refs(root, rows)
    required_docs = set(SOURCE_DOCS)
    observed_docs = {str(row["doc_id"]) for row in rows}
    unknown_status_rows = [
        row["item_id"]
        for row in rows
        if str(row["current_status"]) not in {"done", "partial", "bounded_gap", "blocked", "open"}
    ]
    unfinished_untyped_rows = [
        row["item_id"]
        for row in rows
        if row["current_status"] in {"partial", "bounded_gap", "blocked", "open"}
        and (not row.get("boundary") or not row.get("next_action"))
    ]
    planned_like_rows = [
        row["item_id"]
        for row in rows
        if str(row["current_status"]) in {"planned", "draft", "unknown", "todo"}
    ]
    open_rows = [
        row["item_id"]
        for row in rows
        if str(row["current_status"]) in {"open", "blocked", "planned", "draft", "unknown", "todo"}
    ]
    p21_summary_path = root / EVIDENCE_REFS["P21"]
    p21_summary = json.loads(p21_summary_path.read_text(encoding="utf-8")) if p21_summary_path.exists() else {}
    broad_allowed = bool(p21_summary.get("full_chain_broad_eval_allowed"))
    return [
        {
            "gate_id": "p22_required_source_docs_mapped",
            "status": "pass" if required_docs.issubset(observed_docs) else "fail",
            "reason": "R55/R57/R58/R59/R60 all have status rows.",
            "missing_docs": sorted(required_docs - observed_docs),
        },
        {
            "gate_id": "p22_source_docs_have_current_status_sections",
            "status": "pass" if all(markers.values()) else "fail",
            "reason": "Each source doc contains a P22 Current Status Reconciliation section.",
            "missing_markers": [doc_id for doc_id, ok in sorted(markers.items()) if not ok],
        },
        {
            "gate_id": "p22_no_planned_or_unknown_current_rows",
            "status": "pass" if not unknown_status_rows and not planned_like_rows else "fail",
            "reason": "Current rows must use explicit done/partial/bounded_gap/blocked/open status, never planned/draft/unknown.",
            "unknown_status_rows": unknown_status_rows,
            "planned_like_rows": planned_like_rows,
        },
        {
            "gate_id": "p22_partial_rows_have_boundary_and_next_action",
            "status": "pass" if not unfinished_untyped_rows else "fail",
            "reason": "Partial/bounded/blocked/open rows need boundary and next_action.",
            "unfinished_untyped_rows": unfinished_untyped_rows,
        },
        {
            "gate_id": "p22_evidence_refs_exist",
            "status": "pass" if not missing_evidence else "fail",
            "reason": "Every row points to existing S/P evidence artifacts.",
            "missing_evidence_refs": missing_evidence,
        },
        {
            "gate_id": "p22_broad_full_chain_remains_blocked",
            "status": "pass" if broad_allowed is False else "fail",
            "reason": "P22 only reconciles source docs; it must not unlock broad full-chain quality claims.",
            "p21_full_chain_broad_eval_allowed": broad_allowed,
        },
        {
            "gate_id": "p22_no_open_source_doc_status_rows",
            "status": "pass" if not open_rows else "fail",
            "reason": "P22 closes the source-doc drift blocker only when every row has a concrete status and no source-doc row remains open/blocked.",
            "open_rows": open_rows,
        },
    ]


def _report(summary: dict[str, Any], rows: list[dict[str, Any]], gates: list[dict[str, Any]]) -> str:
    counts = summary["status_counts"]
    doc_counts = summary["doc_status_counts"]
    lines = [
        "# R53-R60 P22 Source-Doc Status Reconciliation",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Status: `{summary['status']}`",
        f"- Closeout level: `{summary['closeout_level']}`",
        f"- Source-doc status: `{summary['source_doc_status']}`",
        f"- Rows: `{summary['row_count']}`",
        f"- Status counts: `{counts}`",
        f"- Doc counts: `{doc_counts}`",
        f"- Broad full-chain quality evidence allowed: `{summary['full_chain_broad_eval_allowed']}`",
        "",
        "## Meaning",
        "",
        "P22 does not mark the whole product as production-ready. It only closes the source-document drift blocker by mapping R55/R57/R58/R59/R60 rows to current done/partial/bounded statuses with S/P evidence refs.",
        "",
        "## Gate Rows",
        "",
    ]
    for gate in gates:
        lines.append(f"- `{gate['gate_id']}`: `{gate['status']}` - {gate['reason']}")
    lines.extend(["", "## Source Document Status Rows", ""])
    for row in rows:
        lines.append(
            f"- `{row['doc_id']}` `{row['item_id']}`: `{row['current_status']}`; boundary: {row['boundary']}; next: {row['next_action']}"
        )
    return "\n".join(lines) + "\n"


def build_p22_source_doc_status_reconciliation(root: Path) -> dict[str, Any]:
    root = root.resolve()
    rows = [dict(row, generated_at=utc_now_iso()) for row in SOURCE_STATUS_ROWS]
    gates = p22_gate_rows(root, rows)
    gate_fail_count = sum(1 for gate in gates if gate["status"] != "pass")
    open_source_rows = [
        row
        for row in rows
        if row["current_status"] in {"open", "blocked", "planned", "draft", "unknown", "todo"}
    ]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if gate_fail_count == 0 else "fail",
        "closeout_level": "L4_scope_pass_for_source_doc_reconciliation_only",
        "source_doc_status": "reconciled" if gate_fail_count == 0 else "needs_repair",
        "row_count": len(rows),
        "status_counts": _status_counts(rows),
        "doc_status_counts": _doc_counts(rows),
        "open_source_doc_status_rows": len(open_source_rows),
        "gate_count": len(gates),
        "gate_fail_count": gate_fail_count,
        "full_chain_broad_eval_allowed": False,
        "release_decision": "P22_source_docs_reconciled_broad_full_chain_still_blocked"
        if gate_fail_count == 0
        else "P22_source_docs_need_repair",
        "outputs": {
            "schema": "configs/r53_r60/p22_source_doc_status_reconciliation_schema_v0_1.json",
            "status_rows": "data/manifests/r53_r60_p22_source_doc_status_rows_v0_1.jsonl",
            "gate_rows": "data/manifests/r53_r60_p22_source_doc_status_gate_rows_v0_1.jsonl",
            "summary": "data/manifests/r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json",
            "report": "docs/internal/vnext_20260610/r53_r60_p22_source_doc_status_reconciliation_l4_scope_pass.zh-CN.md",
        },
    }
    schema = {
        "schema_version": SCHEMA_VERSION,
        "required_row_fields": [
            "doc_id",
            "source_doc",
            "item_id",
            "title",
            "current_status",
            "evidence_refs",
            "boundary",
            "next_action",
            "broad_full_chain_quality_evidence_allowed",
        ],
        "allowed_current_status": ["done", "partial", "bounded_gap", "blocked", "open"],
        "current_status_marker": CURRENT_STATUS_MARKER,
    }
    write_json(root / summary["outputs"]["schema"], schema)
    write_jsonl(root / summary["outputs"]["status_rows"], rows)
    write_jsonl(root / summary["outputs"]["gate_rows"], gates)
    write_json(root / summary["outputs"]["summary"], summary)
    (root / summary["outputs"]["report"]).parent.mkdir(parents=True, exist_ok=True)
    (root / summary["outputs"]["report"]).write_text(_report(summary, rows, gates), encoding="utf-8")
    return summary

