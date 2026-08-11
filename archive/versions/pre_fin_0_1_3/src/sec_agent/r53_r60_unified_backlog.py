"""S0 unified backlog and gate matrix builder for the R53-R60 program.

The S0 artifact is intentionally contract-first: downstream slices should
depend on these JSON/JSONL/SQLite outputs, not on prose in architecture docs.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "r53_r60_s0_unified_backlog_v0_1"

ACTIVE_SOURCE_DOCS = [
    "docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md",
    "docs/architecture/agent_graph_vnext/26_b2b_collaborative_agent_graph_and_workflow_runtime.zh-CN.md",
    "docs/architecture/agent_graph_vnext/27_r53_r60_engineering_execution_program.zh-CN.md",
    "docs/architecture/agent_graph_vnext/28_r53_research_to_quant_lab_technical_plan.zh-CN.md",
    "docs/architecture/agent_graph_vnext/29_r54_secondary_market_capital_feedback_technical_plan.zh-CN.md",
    "docs/architecture/agent_graph_vnext/30_r55_deliverable_studio_dashboard_projection_technical_plan.zh-CN.md",
    "docs/architecture/agent_graph_vnext/31_r56_agent_runtime_stack_hardening_technical_plan.zh-CN.md",
    "docs/architecture/agent_graph_vnext/32_r57_graph_skill_memory_pack_operating_model.zh-CN.md",
    "docs/architecture/agent_graph_vnext/33_r58_db_rag_retrieval_data_pipeline_control_plane.zh-CN.md",
    "docs/architecture/agent_graph_vnext/34_r59_backend_frontend_workbench_hardening_technical_plan.zh-CN.md",
    "docs/architecture/agent_graph_vnext/35_r60_eval_observability_incident_fallback_technical_plan.zh-CN.md",
    "docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md",
]

LEGACY_BASELINE_GLOBS = [
    "docs/worklog/integrated_execution_p_series/*.md",
    "docs/worklog/product_strategy/*.md",
]


PASS_LEVELS = [
    {
        "pass_level": "L0_smoke_pass",
        "definition": "Minimal local smoke or diagnostic route can run.",
        "allowed_use": "Diagnostic only.",
        "is_intermediate_gate": True,
        "is_slice_closeout_allowed": False,
        "is_full_product_release_gate": False,
    },
    {
        "pass_level": "L1_contract_pass",
        "definition": "Contracts, fields, failure boundaries, and downstream dependency surfaces are stable.",
        "allowed_use": "Schema/API/data-contract dependency for downstream development.",
        "is_intermediate_gate": True,
        "is_slice_closeout_allowed": False,
        "is_full_product_release_gate": False,
    },
    {
        "pass_level": "L2_internal_dogfood_pass",
        "definition": "Internal real tasks work with human review and traceable accountability.",
        "allowed_use": "Internal dogfood and small reviewed research workflows.",
        "is_intermediate_gate": True,
        "is_slice_closeout_allowed": False,
        "is_full_product_release_gate": False,
    },
    {
        "pass_level": "L3_release_candidate_pass",
        "definition": "Controlled pilot candidate with monitoring, rollback, known risks, and readiness report.",
        "allowed_use": "Pilot release candidate.",
        "is_intermediate_gate": True,
        "is_slice_closeout_allowed": False,
        "is_full_product_release_gate": False,
    },
    {
        "pass_level": "L4_scope_pass",
        "definition": "The slice reaches enterprise-grade standards inside its own responsibility scope.",
        "allowed_use": "Required closeout level for every S0-S10 release slice.",
        "is_intermediate_gate": False,
        "is_slice_closeout_allowed": True,
        "is_full_product_release_gate": False,
    },
    {
        "pass_level": "L4_production_pass",
        "definition": "Full-system enterprise production readiness across users, tenants, operations, and quality.",
        "allowed_use": "Whole-product production release gate, normally after S10.",
        "is_intermediate_gate": False,
        "is_slice_closeout_allowed": False,
        "is_full_product_release_gate": True,
    },
]


SLICE_SPECS: list[dict[str, Any]] = [
    {
        "slice_id": "S0",
        "title": "Unified Backlog / Gate Matrix",
        "capability_domain": "program_governance",
        "dependencies": [],
        "intermediate_gates": ["L1_contract_pass"],
        "scope_l4_acceptance": [
            "RDocumentInventory, RDocumentDemandMap, DemandTicket, ImplementationTask, GateArtifact, release board, and pass-level matrix are machine-readable.",
            "R0-R49 baseline dependencies and known gaps are inventoried as baseline context.",
            "Every demand has Product, Engineering, Quality, and Ops acceptance plus L4_scope_pass closeout.",
        ],
        "demands": [
            ("U0-D01-backlog-schema", "Backlog schema", "Define stable schemas for demand tickets, implementation tasks, gate artifacts, pass decisions, and release board rows."),
            ("U0-D02-r-demand-map", "R-document demand map", "Map active R53-R60 program requirements and R0-R49 baseline dependencies into one backlog."),
            ("U0-D03-pass-level-gate-matrix", "Pass-level gate matrix", "Freeze L0-L4 semantics so intermediate gates cannot be mistaken for slice closeout."),
            ("U0-D04-release-slice-board", "Release slice board", "Create dependency-aware S0-S10 board with blockers, owner placeholders, closeout gates, and rollback notes."),
        ],
        "source_docs": [
            ACTIVE_SOURCE_DOCS[0],
            ACTIVE_SOURCE_DOCS[2],
            ACTIVE_SOURCE_DOCS[-1],
        ],
    },
    {
        "slice_id": "S1",
        "title": "Runtime Task Spine",
        "capability_domain": "runtime_spine",
        "dependencies": ["S0"],
        "intermediate_gates": ["L1_contract_pass", "L2_internal_dogfood_pass"],
        "scope_l4_acceptance": [
            "ResearchTask, TaskRun, TaskEvent, ArtifactRef, trace refs, resume/replay, failure boundaries, and rollback are SQL-final and replayable.",
            "At least one representative internal task demonstrates state consistency across API/CLI/worker surfaces.",
        ],
        "demands": [
            ("U1-D01-runtime-facade-entrypoint", "Runtime facade entrypoint", "Unify CLI, Python runtime, and Java shell create/resume/get-state contracts."),
            ("U1-D02-task-run-state-machine", "Task run state machine", "Persist pending/running/paused/repairing/failed/succeeded/cancelled states with legal transitions."),
            ("U1-D03-sql-final-task-audit", "SQL-final task audit", "Make task/run/node/artifact/event chain queryable without Redis as source of truth."),
            ("U1-D04-workpaper-event-ledger", "Workpaper event ledger", "Create append-only WorkpaperEvent ledger for agent and human changes."),
            ("U1-D05-checkpoint-resume-replay", "Checkpoint resume replay", "Persist checkpoint refs and replay enough state after interruption."),
            ("U1-D06-run-trace-baseline", "Run trace baseline", "Record node spans, model/tool usage, latency, token/cost placeholders, and artifact refs."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[1], ACTIVE_SOURCE_DOCS[6], ACTIVE_SOURCE_DOCS[9], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S2",
        "title": "Tool / Sandbox / Trace Spine",
        "capability_domain": "tool_security_runtime",
        "dependencies": ["S1"],
        "intermediate_gates": ["L1_contract_pass"],
        "scope_l4_acceptance": [
            "Every tool invocation has actor, policy decision, input digest, output artifact, error boundary, and audit row.",
            "Forbidden tool calls fail closed with deterministic tests for writer, composer, verifier, and crawler surfaces.",
        ],
        "demands": [
            ("U2-D01-actor-permission-policy", "Actor permission policy", "Define actor-to-tool permissions and fail-closed rules."),
            ("U2-D02-tool-gateway-contract", "Tool gateway contract", "Unify DB, RAG, web, parser, render, and backtest tool schemas."),
            ("U2-D03-sandbox-local-lightweight", "Local lightweight sandbox", "Enforce workspace paths, domain allowlists, timeouts, output limits, and isolated browser profiles."),
            ("U2-D04-tool-invocation-ledger", "Tool invocation ledger", "Persist tool_call_id, actor, policy, artifact, error, and trace refs."),
            ("U2-D05-sandbox-regression", "Sandbox regression", "Test allowed and forbidden tool calls, including path/network/credential escape attempts."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[6], ACTIVE_SOURCE_DOCS[9], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S3",
        "title": "Data / Retrieval / Evidence Spine",
        "capability_domain": "data_retrieval_evidence",
        "dependencies": ["S1", "S2"],
        "intermediate_gates": ["L1_contract_pass", "L2_internal_dogfood_pass"],
        "scope_l4_acceptance": [
            "DB exact, graph, BM25/ObjectBM25, Milvus/vector, web repair, parser rows, and selected/dropped evidence are all ledgered.",
            "Retrieval eval records target-in-candidates, rerank accuracy, role quotas, source-family quotas, and dropped-row reasons.",
        ],
        "demands": [
            ("U3-D01-retrieval-intent-taxonomy", "Retrieval intent taxonomy", "Classify fundamental/product/capital/market/filing/web-repair intents."),
            ("U3-D02-route-policy-matrix", "Route policy matrix", "Define DB/graph/BM25/Milvus/web route order, budget, and forbidden source boundary by intent."),
            ("U3-D03-query-rewrite-facet-plan", "Query rewrite facet plan", "Generate exact, lexical, semantic, graph, and facet queries with drift audit."),
            ("U3-D04-hybrid-recall-rerank-policy", "Hybrid recall rerank policy", "Apply role/source quotas and fusion/rerank without prematurely capping strong evidence."),
            ("U3-D05-retrieval-execution-ledger", "Retrieval execution ledger", "Persist candidate, rerank, selected, and dropped evidence rows with reasons."),
            ("U3-D06-retrieval-eval-qrels", "Retrieval eval qrels", "Create qrels/gold/negative cases and target-in-candidates gates."),
            ("U3-D07-data-lineage-contract", "Data lineage contract", "Connect source, parser, row, retrieval, context, and Workpaper refs."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[8], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S4",
        "title": "Context / Graph / Skill Registry",
        "capability_domain": "context_graph_skill_memory",
        "dependencies": ["S1", "S3"],
        "intermediate_gates": ["L1_contract_pass"],
        "scope_l4_acceptance": [
            "GraphPack, SkillPack, and MemoryPack registries are versioned, permission-aware, and injectable by ContextEngine.",
            "Every context injection has selected refs, compression artifact, dropped reasons, staleness/authority checks, and replay plan.",
        ],
        "demands": [
            ("U4-D01-graph-capability-registry", "Graph capability registry", "Register GraphPacks with version, scope, authority, and tenant status."),
            ("U4-D02-skillpack-registry", "SkillPack registry", "Structure specialist skills with input/output contracts and eval hooks."),
            ("U4-D03-memorypack-registry", "MemoryPack registry", "Define memory tiers, provenance, TTL, staleness, supersession, and promotion status."),
            ("U4-D04-contextengine-lifecycle", "ContextEngine lifecycle", "Implement resolve/select/compress/inject/write/consolidate/invalidate contracts."),
            ("U4-D05-context-compression-artifact", "Context compression artifact", "Keep exact facts as refs, not summaries, and audit dropped refs."),
            ("U4-D06-lead-graph-skill-selector", "Lead graph-skill selector", "Require Lead and specialists to declare consumed Graph/Skill/Memory packs."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[7], ACTIVE_SOURCE_DOCS[8], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S5",
        "title": "Workpaper / Lead Review Workflow",
        "capability_domain": "research_workflow",
        "dependencies": ["S1", "S2", "S3", "S4"],
        "intermediate_gates": ["L2_internal_dogfood_pass"],
        "scope_l4_acceptance": [
            "Research Lead remains an active supervising analyst across objective, dispatch, review, repair, gap exposure, and writing plan.",
            "Representative real tasks produce reviewable Workpaper with evidence, claims, gaps, counter-thesis, and human review trace.",
        ],
        "demands": [
            ("U5-D01-research-objective-contract", "Research objective contract", "Persist core question, required dimensions, minimum evidence, boundaries, and expected gaps."),
            ("U5-D02-dimension-evidence-portfolio", "Dimension evidence portfolio", "Build dimensional evidence/claim/gap portfolios for fundamental/product/capital/market/risk."),
            ("U5-D03-lead-review-checkpoint", "Lead review checkpoint", "Audit objective coverage and trigger targeted repair, specialist rework, human question, or typed gap."),
            ("U5-D04-specialist-workstreams", "Specialist workstreams", "Make specialists write WorkpaperEvents rather than directly writing final memo."),
            ("U5-D05-judgment-state", "Judgment state", "Maintain thesis, counter-thesis, boundary, confidence, and unsupported-claim gates."),
            ("U5-D06-workpaper-readability-gate", "Workpaper readability gate", "Require issue-first, decision-useful, evidence-backed Workpaper structure."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[0], ACTIVE_SOURCE_DOCS[1], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S6",
        "title": "Workbench Frontdoor And Drilldown",
        "capability_domain": "backend_frontend_workbench",
        "dependencies": ["S1", "S2", "S5"],
        "intermediate_gates": ["L2_internal_dogfood_pass"],
        "scope_l4_acceptance": [
            "Users can create, resume, cancel, and inspect tasks from Workbench with replayed state and artifact drilldown.",
            "Evidence, claims, gaps, gates, context, eval, trace, and final outputs are navigable from the same task surface.",
        ],
        "demands": [
            ("U6-D01-api-boundary-contract", "API boundary contract", "Stabilize Java gateway and Python runtime create/get-state/resume/cancel/artifact APIs."),
            ("U6-D02-task-center-ui", "Task Center UI", "Expose task status, progress, SSE/event replay, and reconnect behavior."),
            ("U6-D03-evidence-workbench-ui", "Evidence Workbench UI", "Drill from conclusion to evidence, claim, gap, gate, context, and eval delta."),
            ("U6-D04-workpaper-builder-ui", "Workpaper Builder UI", "Support dimension sections, comments, versions, and return-to-lead."),
            ("U6-D05-review-queue-ui", "Review Queue UI", "Represent human questions, approval, downgrade, and resume events."),
            ("U6-D06-admin-ops-minimal", "Admin ops minimal", "Show run, queue, cost, latency, and incident summaries."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[9], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S7",
        "title": "Deliverable Studio And Dashboard Projection",
        "capability_domain": "deliverable_dashboard",
        "dependencies": ["S5", "S6"],
        "intermediate_gates": ["L2_internal_dogfood_pass", "L3_release_candidate_pass"],
        "scope_l4_acceptance": [
            "Approved Workpaper can generate Markdown/Word/Excel/dashboard projections without losing citations, gaps, appendices, or artifact refs.",
            "Composer permissions prove render-only behavior and dashboard state can be replayed from SQL/artifact refs.",
        ],
        "demands": [
            ("U7-D01-deliverable-plan", "Deliverable plan", "Define output format, audience, evidence boundary, internal/client variants, and render jobs."),
            ("U7-D02-markdown-docx-renderer", "Markdown and Word renderer", "Render readable docs with citations, gap appendix, and source refs."),
            ("U7-D03-excel-appendix-renderer", "Excel appendix renderer", "Export tables and evidence appendices with traceable refs."),
            ("U7-D04-dashboard-projection-updater", "Dashboard projection updater", "Project task/gap/review/artifact state without ghost UI state."),
            ("U7-D05-composer-permission-gate", "Composer permission gate", "Prove Composer cannot retrieve, browse, or mutate research evidence."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[5], ACTIVE_SOURCE_DOCS[9], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S8",
        "title": "Secondary Market / Capital Feedback Pack",
        "capability_domain": "secondary_market_capital_feedback",
        "dependencies": ["S3", "S5"],
        "intermediate_gates": ["L1_contract_pass", "L2_internal_dogfood_pass"],
        "scope_l4_acceptance": [
            "Ownership, credit/funding, corporate action, liquidity/positioning, valuation/price-in, cross-asset, and derivatives packs have authority boundaries.",
            "Secondary-market signals support price-in/capital-feedback reasoning without becoming fundamental facts.",
        ],
        "demands": [
            ("U8-D01-capital-feedback-source-registry", "Capital feedback source registry", "Maintain source authority, refresh cadence, parser status, and commercial boundaries."),
            ("U8-D02-ownership-holder-pack", "Ownership and holder pack", "Parse delayed holder and insider actions without treating them as realtime flow."),
            ("U8-D03-credit-funding-pack", "Credit funding pack", "Represent debt, credit facility, convertible, rating, and spread proxies."),
            ("U8-D04-liquidity-positioning-pack", "Liquidity positioning pack", "Represent turnover, short interest, borrow proxy, ETF/factor flow, and positioning boundaries."),
            ("U8-D05-valuation-price-in-pack", "Valuation price-in pack", "Connect valuation, implied growth, peer multiples, and sensitivity to thesis state."),
            ("U8-D06-derivatives-market-signal-pack", "Derivatives market signal pack", "Represent futures/options delayed/proxy signals and commercial gaps."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[4], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S9",
        "title": "Research-to-Quant Lab",
        "capability_domain": "research_to_quant",
        "dependencies": ["S3", "S5", "S8"],
        "intermediate_gates": ["L1_contract_pass", "L2_internal_dogfood_pass"],
        "scope_l4_acceptance": [
            "Research thesis drivers can become FactorHypothesis objects only through human approval and PIT/leakage gates.",
            "Backtest/paper-trading outputs produce FactorCards with risk attribution, rejected reasons, and research feedback refs.",
        ],
        "demands": [
            ("U9-D01-factor-hypothesis-schema", "Factor hypothesis schema", "Map Workpaper thesis drivers to FactorHypothesis, FeatureSpec, LabelSpec, and UniverseSpec."),
            ("U9-D02-human-approval-flow", "Human approval flow", "Require explicit approval before dataset build, backtest, or paper-trading monitor."),
            ("U9-D03-pit-dataset-builder-gate", "PIT dataset builder gate", "Enforce publish time, available time, tradable-after time, and leakage guards."),
            ("U9-D04-backtest-adapter", "Backtest adapter", "Run deterministic smoke from at least two thesis drivers to FactorHypothesis and backtest result."),
            ("U9-D05-risk-attribution-factorcard", "Risk attribution FactorCard", "Write risk exposure, failure mode, decay, rejected reason, and promotion state."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[3], ACTIVE_SOURCE_DOCS[4], ACTIVE_SOURCE_DOCS[8], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
    {
        "slice_id": "S10",
        "title": "Enterprise Hardening / Release Candidate",
        "capability_domain": "enterprise_release",
        "dependencies": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"],
        "intermediate_gates": ["L3_release_candidate_pass"],
        "scope_l4_acceptance": [
            "Auth, tenant isolation, load/chaos, incident dashboard, release readiness, online eval, rollback, and failure lifecycle are complete for controlled pilot.",
            "Whole-product L4 production gate remains separate from slice-level L4_scope_pass.",
        ],
        "demands": [
            ("U10-D01-auth-tenant-rbac", "Auth tenant RBAC", "Implement organization/project/role/permission boundaries and tenant tests."),
            ("U10-D02-load-chaos-sla", "Load chaos SLA", "Test multi-task load, worker crash, provider timeout, SSE reconnect, queue wait, and recovery."),
            ("U10-D03-incident-dashboard", "Incident dashboard", "Expose parser, retrieval, tool, model, frontend, cost, and authority incidents."),
            ("U10-D04-release-readiness-report", "Release readiness report", "Publish gates, known gaps, rollback, owner, and feedback entrypoints."),
            ("U10-D05-online-eval-feedback-loop", "Online eval feedback loop", "Route reviewer feedback and production failures into regression/gold lifecycle."),
        ],
        "source_docs": [ACTIVE_SOURCE_DOCS[9], ACTIVE_SOURCE_DOCS[10], ACTIVE_SOURCE_DOCS[-1]],
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def demand_schema() -> dict[str, Any]:
    required = [
        "schema_version",
        "demand_id",
        "slice_id",
        "capability_domain",
        "source_docs",
        "objective",
        "scope",
        "non_goals",
        "dependencies",
        "blocked_by",
        "intermediate_gates",
        "closeout_level",
        "scope_l4_acceptance",
        "product_acceptance",
        "engineering_acceptance",
        "quality_acceptance",
        "ops_acceptance",
        "tests",
        "gate_artifacts",
        "rollback",
        "status",
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "R53-R60 S0 Unified Backlog DemandTicket",
        "schema_version": SCHEMA_VERSION,
        "type": "object",
        "required": required,
        "properties": {
            field: {"description": f"Required S0 DemandTicket field: {field}"}
            for field in required
        },
        "additionalProperties": True,
        "closeout_rule": {
            "field": "closeout_level",
            "required_value": "L4_scope_pass",
            "intermediate_gates_are_not_closeout": True,
        },
    }


def discover_r_documents(root: Path) -> list[dict[str, Any]]:
    generated_at = utc_now_iso()
    rows: list[dict[str, Any]] = []

    for doc in ACTIVE_SOURCE_DOCS:
        path = root / doc
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "doc_id": doc_to_id(doc),
                "source_doc": doc,
                "source_group": classify_doc(doc),
                "exists": path.exists(),
                "is_active_r53_r60_source": True,
                "r_number": extract_r_number(doc),
                "baseline_dependency": False,
                "known_gap_source": False,
            }
        )

    seen = {row["source_doc"] for row in rows}
    for pattern in LEGACY_BASELINE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            relative = rel_path(path, root)
            if relative in seen:
                continue
            r_number = extract_r_number(path.name)
            if r_number is None or r_number > 49:
                continue
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "doc_id": doc_to_id(relative),
                    "source_doc": relative,
                    "source_group": "legacy_r0_r49_baseline",
                    "exists": True,
                    "is_active_r53_r60_source": False,
                    "r_number": r_number,
                    "baseline_dependency": True,
                    "known_gap_source": is_known_gap_doc(path.name),
                }
            )
            seen.add(relative)

    return rows


def doc_to_id(doc: str) -> str:
    stem = Path(doc).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    return stem or "document"


def classify_doc(doc: str) -> str:
    if doc.startswith("docs/product/"):
        return "product_prd"
    if "/26_" in doc or "/27_" in doc or "/36_" in doc:
        return "program_runtime_planning"
    if "/28_" in doc or "/29_" in doc or "/30_" in doc:
        return "capability_plan"
    if "/31_" in doc or "/32_" in doc or "/33_" in doc or "/34_" in doc or "/35_" in doc:
        return "platform_quality_plan"
    return "reference"


def extract_r_number(text: str) -> int | None:
    patterns = [r"(?:^|_)r(\d+)(?:_|-|$)", r"r(\d+)_"]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return int(match.group(1))
    return None


def is_known_gap_doc(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ["gap", "audit", "closeout", "gate", "repair", "depth"])


def build_release_board(generated_at: str) -> list[dict[str, Any]]:
    rows = []
    for spec in SLICE_SPECS:
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "slice_id": spec["slice_id"],
                "title": spec["title"],
                "capability_domain": spec["capability_domain"],
                "dependencies": spec["dependencies"],
                "intermediate_gates": spec["intermediate_gates"],
                "closeout_level": "L4_scope_pass",
                "scope_l4_acceptance": spec["scope_l4_acceptance"],
                "demand_count": len(spec["demands"]),
                "status": "ready_to_start" if spec["slice_id"] == "S0" else "blocked_by_dependencies",
                "owner_placeholder": "single_agent_current_thread",
                "rollback": "Revert this slice commit and restore the previous release board row set.",
            }
        )
    return rows


def build_demands(generated_at: str) -> list[dict[str, Any]]:
    demands: list[dict[str, Any]] = []
    all_by_slice: dict[str, list[str]] = {
        spec["slice_id"]: [demand_id for demand_id, _title, _objective in spec["demands"]]
        for spec in SLICE_SPECS
    }

    for spec in SLICE_SPECS:
        upstream_demand_ids = [
            demand_id
            for upstream_slice in spec["dependencies"]
            for demand_id in all_by_slice.get(upstream_slice, [])
        ]
        for index, (demand_id, title, objective) in enumerate(spec["demands"], start=1):
            demands.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "demand_id": demand_id,
                    "demand_title": title,
                    "slice_id": spec["slice_id"],
                    "capability_domain": spec["capability_domain"],
                    "source_docs": spec["source_docs"],
                    "source_sections": infer_source_sections(spec["slice_id"], demand_id),
                    "objective": objective,
                    "scope": [
                        f"Implement the {title} contract for {spec['title']}.",
                        "Produce machine-readable artifacts, deterministic tests, audit rows, and rollback notes where applicable.",
                    ],
                    "non_goals": [
                        "Do not treat L0/L1/L2/L3 intermediate gates as final slice closeout.",
                        "Do not hide missing requirements with silent fallback or undocumented defaults.",
                    ],
                    "dependencies": upstream_demand_ids if index == 1 else [spec["demands"][index - 2][0]],
                    "blocked_by": spec["dependencies"] if spec["slice_id"] != "S0" else [],
                    "intermediate_gates": spec["intermediate_gates"],
                    "closeout_level": "L4_scope_pass",
                    "scope_l4_acceptance": spec["scope_l4_acceptance"],
                    "product_acceptance": product_acceptance(spec["slice_id"], title),
                    "engineering_acceptance": engineering_acceptance(spec["slice_id"], title),
                    "quality_acceptance": quality_acceptance(spec["slice_id"], title),
                    "ops_acceptance": ops_acceptance(spec["slice_id"], title),
                    "tests": tests_for_demand(spec["slice_id"], demand_id),
                    "gate_artifacts": gate_artifacts_for_demand(spec["slice_id"], demand_id),
                    "rollback": f"Revert artifacts and code owned by {demand_id}; invalidate dependent board rows before retry.",
                    "status": "planned" if spec["slice_id"] != "S0" else "ready_for_implementation",
                }
            )
    return demands


def infer_source_sections(slice_id: str, demand_id: str) -> list[str]:
    return [f"36:{slice_id}", f"36:{demand_id}", "36:0.3-L4_scope_pass"]


def product_acceptance(slice_id: str, title: str) -> list[str]:
    base = f"{title} improves the B-side research workflow by making scope, review, trace, or deliverable state auditable."
    if slice_id in {"S5", "S6", "S7", "S9"}:
        return [base, "A representative internal user path can be reviewed by a senior analyst without reading raw logs."]
    if slice_id == "S0":
        return ["Product and technical requirements can be traced from PRD/R-docs to slice demand tickets before implementation starts."]
    return [base, "The requirement exposes decision boundaries instead of only producing a model answer."]


def engineering_acceptance(slice_id: str, title: str) -> list[str]:
    return [
        f"{title} has stable machine-readable schema or API contract where applicable.",
        "Generated artifacts have deterministic builders or documented regeneration commands.",
        "Downstream dependencies can validate the artifact without parsing prose docs.",
    ]


def quality_acceptance(slice_id: str, title: str) -> list[str]:
    return [
        f"{title} has deterministic tests or eval gates covering positive and negative behavior.",
        "Unsupported claims, silent fallbacks, missing refs, and boundary violations are represented as typed gaps or failing gates.",
    ]


def ops_acceptance(slice_id: str, title: str) -> list[str]:
    return [
        f"{title} records audit artifacts needed for replay, rollback, or incident triage.",
        "Token/cost/latency/resource impact must be recorded when the demand invokes models, retrieval, web, or long-running workers.",
    ]


def tests_for_demand(slice_id: str, demand_id: str) -> list[str]:
    if slice_id == "S0":
        return [
            "tests/test_r53_r60_unified_backlog.py::test_s0_backlog_builds_l4_scope_contract",
            "tests/test_r53_r60_unified_backlog.py::test_s0_gate_blocks_missing_required_sources",
            "tests/test_r53_r60_unified_backlog.py::test_s0_sqlite_counts_match_outputs",
        ]
    return [
        f"future::{slice_id.lower()}::{demand_id}::contract_test",
        f"future::{slice_id.lower()}::{demand_id}::negative_gate_test",
    ]


def gate_artifacts_for_demand(slice_id: str, demand_id: str) -> list[str]:
    if slice_id == "S0":
        return [
            "configs/r53_r60/s0_unified_backlog_schema_v0_1.json",
            "data/manifests/r53_r60_r_document_inventory_v0_1.jsonl",
            "data/manifests/r53_r60_demand_map_v0_1.jsonl",
            "data/manifests/r53_r60_implementation_tasks_v0_1.jsonl",
            "data/manifests/r53_r60_pass_level_gate_matrix_v0_1.jsonl",
            "data/manifests/r53_r60_release_board_v0_1.jsonl",
            "data/manifests/r53_r60_gate_rows_v0_1.jsonl",
            "data/manifests/r53_r60_unified_backlog_summary_v0_1.json",
        ]
    return [
        f"future::data/manifests/{slice_id.lower()}_{demand_id}_pass_level_decision.json",
        f"future::docs/internal/vnext_20260610/{slice_id.lower()}_{demand_id}_closeout.md",
    ]


def build_implementation_tasks(demands: list[dict[str, Any]], generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    task_templates = [
        ("contract", "Freeze schema/API/artifact contracts and rollback notes."),
        ("runtime_or_artifact", "Implement runtime code or materialized artifacts required by the demand."),
        ("gate", "Add deterministic tests, eval gates, and PassLevelDecision evidence."),
    ]
    for demand in demands:
        for ordinal, (kind, objective) in enumerate(task_templates, start=1):
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": generated_at,
                    "implementation_task_id": f"{demand['demand_id']}-T{ordinal:02d}-{kind}",
                    "demand_id": demand["demand_id"],
                    "slice_id": demand["slice_id"],
                    "task_type": kind,
                    "objective": objective,
                    "dependencies": [] if ordinal == 1 else [f"{demand['demand_id']}-T{ordinal - 1:02d}-{task_templates[ordinal - 2][0]}"],
                    "closeout_level": "L4_scope_pass",
                    "status": "planned" if demand["slice_id"] != "S0" else "ready_for_implementation",
                    "acceptance_refs": {
                        "product": demand["product_acceptance"],
                        "engineering": demand["engineering_acceptance"],
                        "quality": demand["quality_acceptance"],
                        "ops": demand["ops_acceptance"],
                    },
                }
            )
    return rows


def build_pass_level_matrix(generated_at: str) -> list[dict[str, Any]]:
    rows = []
    for item in PASS_LEVELS:
        row = dict(item)
        row.update({"schema_version": SCHEMA_VERSION, "generated_at": generated_at})
        rows.append(row)
    return rows


def build_gate_rows(
    root: Path,
    inventory: list[dict[str, Any]],
    demands: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    release_board: list[dict[str, Any]],
    pass_levels: list[dict[str, Any]],
    generated_at: str,
) -> list[dict[str, Any]]:
    active_docs = {row["source_doc"]: row for row in inventory if row["is_active_r53_r60_source"]}
    legacy_rows = [row for row in inventory if row["baseline_dependency"]]
    demand_ids = [row["demand_id"] for row in demands]
    task_ids = [row["implementation_task_id"] for row in tasks]
    slice_ids = {row["slice_id"] for row in release_board}
    required_slices = {spec["slice_id"] for spec in SLICE_SPECS}
    source_docs_in_demands = {doc for row in demands for doc in row["source_docs"]}
    pass_by_level = {row["pass_level"]: row for row in pass_levels}

    checks = [
        (
            "required_active_source_docs_exist",
            all(row["exists"] for row in active_docs.values()),
            "All PRD/R26-R36 active source docs exist.",
            missing_active_docs(active_docs),
        ),
        (
            "active_source_docs_mapped_to_demands",
            set(ACTIVE_SOURCE_DOCS).issubset(source_docs_in_demands),
            "Every active R53-R60/PRD source doc is mapped to at least one demand.",
            sorted(set(ACTIVE_SOURCE_DOCS) - source_docs_in_demands),
        ),
        (
            "legacy_r0_r49_baseline_inventory_present",
            len(legacy_rows) >= 10,
            "R0-R49 baseline dependency inventory is present and non-trivial.",
            {"legacy_baseline_count": len(legacy_rows), "minimum": 10},
        ),
        (
            "all_release_slices_present",
            required_slices == slice_ids,
            "S0-S10 release board rows are complete.",
            sorted(required_slices - slice_ids),
        ),
        (
            "demand_ids_unique",
            len(demand_ids) == len(set(demand_ids)),
            "Demand IDs are unique.",
            duplicate_values(demand_ids),
        ),
        (
            "implementation_task_ids_unique",
            len(task_ids) == len(set(task_ids)),
            "Implementation task IDs are unique.",
            duplicate_values(task_ids),
        ),
        (
            "expected_demand_count",
            len(demands) == sum(len(spec["demands"]) for spec in SLICE_SPECS),
            "Demand count matches S0-S10 specification.",
            {"actual": len(demands), "expected": sum(len(spec["demands"]) for spec in SLICE_SPECS)},
        ),
        (
            "all_demands_closeout_l4_scope",
            all(row["closeout_level"] == "L4_scope_pass" for row in demands),
            "Every demand closes at L4_scope_pass, not L0/L1/L2/L3.",
            [row["demand_id"] for row in demands if row["closeout_level"] != "L4_scope_pass"],
        ),
        (
            "acceptance_fields_complete",
            all(demand_acceptance_complete(row) for row in demands),
            "Every demand has Product/Engineering/Quality/Ops and scope acceptance evidence placeholders.",
            [row["demand_id"] for row in demands if not demand_acceptance_complete(row)],
        ),
        (
            "release_board_dependencies_valid",
            all(set(row["dependencies"]).issubset(slice_ids) for row in release_board),
            "Release board dependencies point only to existing slices.",
            invalid_release_dependencies(release_board, slice_ids),
        ),
        (
            "pass_level_matrix_enforces_l4_scope",
            pass_by_level.get("L4_scope_pass", {}).get("is_slice_closeout_allowed") is True
            and not any(
                pass_by_level[level]["is_slice_closeout_allowed"]
                for level in ["L0_smoke_pass", "L1_contract_pass", "L2_internal_dogfood_pass", "L3_release_candidate_pass"]
            ),
            "Only L4_scope_pass is allowed as slice closeout; L4_production remains whole-product release gate.",
            pass_by_level,
        ),
        (
            "schema_avoids_target_pass_level_legacy_field",
            not any("target_pass_level" in json.dumps(row, ensure_ascii=False) for row in demands),
            "Legacy target_pass_level wording is not used by demand contracts.",
            [],
        ),
    ]

    rows = []
    for gate_id, passed, description, detail in checks:
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": generated_at,
                "gate_id": gate_id,
                "scope": "S0",
                "status": "pass" if passed else "fail",
                "description": description,
                "detail": detail,
                "closeout_level": "L4_scope_pass",
            }
        )
    return rows


def missing_active_docs(active_docs: dict[str, dict[str, Any]]) -> list[str]:
    return sorted(doc for doc, row in active_docs.items() if not row["exists"])


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def demand_acceptance_complete(row: dict[str, Any]) -> bool:
    return all(
        bool(row.get(field))
        for field in [
            "scope_l4_acceptance",
            "product_acceptance",
            "engineering_acceptance",
            "quality_acceptance",
            "ops_acceptance",
            "tests",
            "gate_artifacts",
        ]
    )


def invalid_release_dependencies(release_board: list[dict[str, Any]], slice_ids: set[str]) -> list[dict[str, Any]]:
    invalid = []
    for row in release_board:
        missing = sorted(set(row["dependencies"]) - slice_ids)
        if missing:
            invalid.append({"slice_id": row["slice_id"], "missing_dependencies": missing})
    return invalid


def write_sqlite(path: Path, tables: dict[str, list[dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        for table, rows in tables.items():
            conn.execute(f"CREATE TABLE {table} (payload TEXT NOT NULL)")
            conn.executemany(
                f"INSERT INTO {table} (payload) VALUES (?)",
                [(json.dumps(row, ensure_ascii=False, sort_keys=True),) for row in rows],
            )
        conn.execute("CREATE TABLE table_counts (table_name TEXT PRIMARY KEY, row_count INTEGER NOT NULL)")
        conn.executemany(
            "INSERT INTO table_counts (table_name, row_count) VALUES (?, ?)",
            [(table, len(rows)) for table, rows in tables.items()],
        )


def build_summary(
    root: Path,
    outputs: dict[str, Path],
    inventory: list[dict[str, Any]],
    demands: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    release_board: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    active_docs = [row for row in inventory if row["is_active_r53_r60_source"]]
    legacy_rows = [row for row in inventory if row["baseline_dependency"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if not failed else "fail",
        "release_decision": "S0_L4_scope_pass" if not failed else "S0_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "counts": {
            "active_source_docs": len(active_docs),
            "active_source_docs_missing": sum(1 for row in active_docs if not row["exists"]),
            "legacy_r0_r49_baseline_docs": len(legacy_rows),
            "demand_count": len(demands),
            "implementation_task_count": len(tasks),
            "release_slice_count": len(release_board),
            "gate_count": len(gate_rows),
            "gate_fail_count": len(failed),
        },
        "outputs": {name: rel_path(path, root) for name, path in outputs.items()},
        "failed_gates": failed,
        "next_slice_unlocked": "S1" if not failed else None,
        "notes": [
            "S0 pass means the backlog/gate matrix scope is enterprise-grade; it does not claim full-product production readiness.",
            "L0/L1/L2/L3 remain intermediate gates only and cannot close a slice.",
        ],
    }


def render_report(summary: dict[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    counts = summary["counts"]
    lines = [
        "# R53-R60 S0 Unified Backlog L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for name, path in summary["outputs"].items():
        lines.append(f"- `{name}`: `{path}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "S0 closes only the unified backlog / gate matrix scope. It authorizes S1 to start because the demand schema, R-document map, release board, implementation task board, pass-level matrix, and gate artifact are machine-readable and testable. It does not claim full-product `L4_production_pass`.",
            "",
        ]
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class S0BuildResult:
    summary: dict[str, Any]
    outputs: dict[str, Path]
    gate_rows: list[dict[str, Any]]


def build_s0_unified_backlog(root: Path) -> S0BuildResult:
    root = root.resolve()
    generated_at = utc_now_iso()
    config_dir = root / "configs" / "r53_r60"
    manifests_dir = root / "data" / "manifests"
    sqlite_path = root / "data" / "workbench_private" / "research_data" / "r53_r60_unified_backlog_v0_1.sqlite"
    report_path = root / "docs" / "internal" / "vnext_20260610" / "r53_r60_s0_unified_backlog_l4_scope_pass.zh-CN.md"

    schema_path = config_dir / "s0_unified_backlog_schema_v0_1.json"
    inventory_path = manifests_dir / "r53_r60_r_document_inventory_v0_1.jsonl"
    demand_path = manifests_dir / "r53_r60_demand_map_v0_1.jsonl"
    task_path = manifests_dir / "r53_r60_implementation_tasks_v0_1.jsonl"
    pass_matrix_path = manifests_dir / "r53_r60_pass_level_gate_matrix_v0_1.jsonl"
    release_board_path = manifests_dir / "r53_r60_release_board_v0_1.jsonl"
    gate_rows_path = manifests_dir / "r53_r60_gate_rows_v0_1.jsonl"
    summary_path = manifests_dir / "r53_r60_unified_backlog_summary_v0_1.json"

    inventory = discover_r_documents(root)
    demands = build_demands(generated_at)
    tasks = build_implementation_tasks(demands, generated_at)
    release_board = build_release_board(generated_at)
    pass_levels = build_pass_level_matrix(generated_at)
    gate_rows = build_gate_rows(root, inventory, demands, tasks, release_board, pass_levels, generated_at)

    outputs = {
        "schema": schema_path,
        "r_document_inventory": inventory_path,
        "r_document_demand_map": demand_path,
        "implementation_tasks": task_path,
        "pass_level_gate_matrix": pass_matrix_path,
        "release_board": release_board_path,
        "gate_rows": gate_rows_path,
        "summary": summary_path,
        "sqlite_mirror": sqlite_path,
        "closeout_report": report_path,
    }
    summary = build_summary(root, outputs, inventory, demands, tasks, release_board, gate_rows, generated_at)

    write_json(schema_path, demand_schema())
    write_jsonl(inventory_path, inventory)
    write_jsonl(demand_path, demands)
    write_jsonl(task_path, tasks)
    write_jsonl(pass_matrix_path, pass_levels)
    write_jsonl(release_board_path, release_board)
    write_jsonl(gate_rows_path, gate_rows)
    write_json(summary_path, summary)
    write_sqlite(
        sqlite_path,
        {
            "r_document_inventory": inventory,
            "demand_map": demands,
            "implementation_tasks": tasks,
            "pass_level_gate_matrix": pass_levels,
            "release_board": release_board,
            "gate_rows": gate_rows,
        },
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary, gate_rows), encoding="utf-8")

    return S0BuildResult(summary=summary, outputs=outputs, gate_rows=gate_rows)


def load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
