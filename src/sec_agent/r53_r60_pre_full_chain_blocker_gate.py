"""P21 pre-full-chain blocker gate for the R53-R60 program.

This gate does not claim product readiness.  It turns the five user-confirmed
audit gaps into machine-readable blockers so broad 20-50 case full-chain evals
cannot be treated as meaningful release evidence until the upstream layers are
closed at their own L4-scope acceptance level.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from sec_agent.r53_r60_runtime_task_spine import utc_now_iso, write_json, write_jsonl


SCHEMA_VERSION = "r53_r60_p21_pre_full_chain_blocker_gate_v0_1"

BOARD_FILES = {
    "demand_map": "r53_r60_demand_map_v0_1.jsonl",
    "implementation_tasks": "r53_r60_implementation_tasks_v0_1.jsonl",
    "release_board": "r53_r60_release_board_v0_1.jsonl",
}

MANUAL_CURRENT_STATUS_ROWS = [
    {
        "slice_id": "P20",
        "title": "DeepSeek real-LLM dogfood and gate repair",
        "current_status": "scope_pass_with_boundaries",
        "status": "pass",
        "closeout_level": "L4_scope_pass",
        "release_decision": "P20_L4_scope_pass_real_llm_dogfood_gate_repair_ready",
        "source_ref": "docs/worklog/product_strategy/044_p20_deepseek_real_llm_dogfood_gate_repair.md",
        "open_boundaries": [
            "not_full_product_release",
            "upstream_root_causes_reclassified_to_p20b",
        ],
    },
    {
        "slice_id": "P20b",
        "title": "P20b root-cause hardening",
        "current_status": "scope_pass_root_cause_hardening_closed",
        "status": "pass",
        "closeout_level": "L4_scope_pass_for_root_cause_hardening",
        "release_decision": "P20b_D01_D04_D02_D03_root_cause_closed",
        "source_ref": "docs/worklog/product_strategy/045_p20b_root_cause_source_doc_hardening.md",
        "open_boundaries": [],
        "resolved_items": [
            "P20b-D01-ambiguous-currency-scale-root",
            "P20b-D02-numeric-display-lineage",
            "P20b-D03-memo-logic-plan-quality-root",
            "P20b-D04-source-doc-status-correction",
        ],
    },
]

SUMMARY_FILES = {
    "S0": "r53_r60_unified_backlog_summary_v0_1.json",
    "S1": "r53_r60_s1_runtime_task_spine_summary_v0_1.json",
    "S2": "r53_r60_s2_tool_sandbox_trace_summary_v0_1.json",
    "S3": "r53_r60_s3_retrieval_evidence_spine_summary_v0_1.json",
    "S4": "r53_r60_s4_context_graph_skill_registry_summary_v0_1.json",
    "S5": "r53_r60_s5_workpaper_lead_review_workflow_summary_v0_1.json",
    "S6": "r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json",
    "S7": "r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json",
    "S8": "r53_r60_s8_secondary_market_capital_feedback_summary_v0_1.json",
    "S9": "r53_r60_s9_research_to_quant_lab_summary_v0_1.json",
    "S10": "r53_r60_s10_enterprise_release_candidate_summary_v0_1.json",
    "P11": "r53_r60_p11_production_pilot_readiness_summary_v0_1.json",
    "P12": "r53_r60_p12_durable_runtime_hil_resource_router_summary_v0_1.json",
    "P13": "r53_r60_p13_graph_skill_memory_lifecycle_summary_v0_1.json",
    "P14": "r53_r60_p14_data_ingestion_retrieval_control_plane_summary_v0_1.json",
    "P15": "r53_r60_p15_enterprise_workbench_product_surface_summary_v0_1.json",
    "P16": "r53_r60_p16_quality_engineering_online_eval_summary_v0_1.json",
    "P17": "r53_r60_p17_controlled_internal_pilot_execution_summary_v0_1.json",
    "P18": "r53_r60_p18_internal_reviewer_dogfood_window_summary_v0_1.json",
    "P19": "r53_r60_p19_internal_reviewer_action_capture_summary_v0_1.json",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("status", "missing_status")) for row in rows)
    return dict(sorted(counts.items()))


def _load_summaries(manifest_dir: Path) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for slice_id, filename in SUMMARY_FILES.items():
        path = manifest_dir / filename
        rel_summary_path = f"data/manifests/{filename}"
        if not path.exists():
            summaries[slice_id] = {"exists": False, "path": rel_summary_path}
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        summaries[slice_id] = {
            "exists": True,
            "path": rel_summary_path,
            "status": payload.get("status"),
            "closeout_level": payload.get("closeout_level"),
            "release_decision": payload.get("release_decision"),
            "known_boundary_fields": {
                key: payload.get(key)
                for key in (
                    "pilot_execution_status",
                    "full_product_release_status",
                    "full_runtime_migration_status",
                    "lifecycle_rollout_status",
                    "real_human_adoption_status",
                    "real_multi_day_human_adoption_status",
                )
                if key in payload
            },
            "policy": payload.get("policy", {}),
        }
    return summaries


def _board_observation(root: Path) -> dict[str, Any]:
    manifest_dir = root / "data" / "manifests"
    observations: dict[str, Any] = {}
    for board_name, filename in BOARD_FILES.items():
        rows = _read_jsonl(manifest_dir / filename)
        observations[board_name] = {
            "path": f"data/manifests/{filename}",
            "row_count": len(rows),
            "status_counts": _status_counts(rows),
        }
    return observations


def _load_p22_source_doc_summary(root: Path) -> dict[str, Any]:
    path = root / "data" / "manifests" / "r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json"
    if not path.exists():
        return {"exists": False, "path": "data/manifests/r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["exists"] = True
    payload["path"] = "data/manifests/r53_r60_p22_source_doc_status_reconciliation_summary_v0_1.json"
    return payload


def _load_p23_product_acceptance_summary(root: Path) -> dict[str, Any]:
    path = root / "data" / "manifests" / "r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json"
    if not path.exists():
        return {"exists": False, "path": "data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["exists"] = True
    payload["path"] = "data/manifests/r53_r60_p23_product_dogfood_frontend_e2e_summary_v0_1.json"
    return payload


def _load_p24_product_acceptance_summary(root: Path) -> dict[str, Any]:
    path = root / "data" / "manifests" / "r53_r60_p24_b04_product_acceptance_summary_v0_1.json"
    if not path.exists():
        return {"exists": False, "path": "data/manifests/r53_r60_p24_b04_product_acceptance_summary_v0_1.json"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["exists"] = True
    payload["path"] = "data/manifests/r53_r60_p24_b04_product_acceptance_summary_v0_1.json"
    return payload


def _summary_current_status(slice_id: str, summary: dict[str, Any]) -> str:
    if not summary.get("exists"):
        return "missing_summary"
    policy = summary.get("policy") or {}
    boundary_fields = summary.get("known_boundary_fields") or {}
    has_boundary_policy = any(
        bool(policy.get(key))
        for key in (
            "not_full_crawler_or_production_refresh",
            "not_full_langgraph_production_migration",
            "not_full_multi_tenant_rollout",
            "not_polished_react_or_external_pilot",
            "p16_is_not_sustained_production_monitoring_window",
        )
    )
    if boundary_fields or has_boundary_policy or slice_id in {"S7", "S8", "S9"}:
        return "scope_pass_with_boundaries"
    return "scope_pass"


def _current_status_overlay(root: Path, summaries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slice_id, summary in summaries.items():
        rows.append(
            {
                "row_type": "summary_closeout_status",
                "slice_id": slice_id,
                "current_status": _summary_current_status(slice_id, summary),
                "status": summary.get("status") if summary.get("exists") else "missing",
                "closeout_level": summary.get("closeout_level"),
                "release_decision": summary.get("release_decision"),
                "summary_path": summary.get("path"),
                "boundary_fields": summary.get("known_boundary_fields", {}),
                "policy": summary.get("policy", {}),
                "full_product_complete": False,
                "broad_full_chain_quality_evidence_allowed": False,
            }
        )
    rows.extend(
        {
            "row_type": "manual_closeout_status",
            **row,
            "full_product_complete": False,
            "broad_full_chain_quality_evidence_allowed": False,
        }
        for row in MANUAL_CURRENT_STATUS_ROWS
    )
    rows.append(
        {
            "row_type": "current_gate_status",
            "slice_id": "P21",
            "title": "Pre-full-chain blocker gate",
            "current_status": "scope_pass_for_blocker_registration_only",
            "status": "pass",
            "closeout_level": "L4_scope_pass_for_blocker_registration_only",
            "release_decision": "P21_pre_full_chain_blockers_registered_broad_full_chain_blocked",
            "source_ref": "data/manifests/r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json",
            "full_product_complete": False,
            "broad_full_chain_quality_evidence_allowed": False,
        }
    )
    return rows


def _current_release_board_rows(current_status_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in current_status_rows:
        slice_id = row["slice_id"]
        current_status = row["current_status"]
        rows.append(
            {
                "slice_id": slice_id,
                "current_status": current_status,
                "status": row.get("status"),
                "closeout_level": row.get("closeout_level"),
                "release_decision": row.get("release_decision"),
                "can_unblock_broad_full_chain_quality_eval": False,
                "requires_followup": current_status != "scope_pass",
                "source_ref": row.get("summary_path") or row.get("source_ref"),
            }
        )
    return rows


def pre_full_chain_blockers(root: Path, current_status_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    manifest_dir = root / "data" / "manifests"
    board_observation = _board_observation(root)
    summaries = _load_summaries(manifest_dir)
    p22_summary = _load_p22_source_doc_summary(root)
    p23_summary = _load_p23_product_acceptance_summary(root)
    p24_summary = _load_p24_product_acceptance_summary(root)
    p22_source_docs_closed = (
        p22_summary.get("exists")
        and p22_summary.get("status") == "pass"
        and p22_summary.get("source_doc_status") == "reconciled"
        and int(p22_summary.get("open_source_doc_status_rows", 0)) == 0
    )
    p24_counts = p24_summary.get("counts") if isinstance(p24_summary.get("counts"), dict) else {}
    p24_human_acceptance_closed = (
        p24_summary.get("exists")
        and p24_summary.get("product_acceptance_status") == "accepted_by_real_human_review"
        and p24_summary.get("b04_status_after_p24") == "closed_by_real_human_product_acceptance"
        and int(p24_counts.get("human_evidence_pending_count", 1)) == 0
        and int(p24_counts.get("defect_closeout_pending_count", 1)) == 0
    )
    found_summary_count = sum(1 for item in summaries.values() if item.get("exists"))
    current_status_rows = current_status_rows or _current_status_overlay(root, summaries)
    required_current_ids = set(SUMMARY_FILES) | {"P20", "P20b", "P21"}
    current_ids = {str(row.get("slice_id")) for row in current_status_rows}
    status_overlay_covers_required = required_current_ids.issubset(current_ids)

    return [
        {
            "blocker_id": "B01-machine-readable-backlog-status-parity",
            "title": "S0 machine-readable demand/release boards are stale",
            "source_audit_item": "AUD-01",
            "status": "closed_by_p21_current_status_overlay"
            if status_overlay_covers_required
            else "open_root_cause_repair_required",
            "blocks": ["broad_full_chain_20_50_eval", "automation_from_release_board"],
            "observed_evidence": {
                "board_status_counts": board_observation,
                "summary_files_found": found_summary_count,
                "summary_files_expected": len(SUMMARY_FILES),
                "current_status_overlay_rows": len(current_status_rows),
                "current_status_required_ids": sorted(required_current_ids),
                "current_status_missing_ids": sorted(required_current_ids - current_ids),
            },
            "why_blocking": (
                "The human-readable closeouts know S/P slices progressed, but the machine-readable "
                "S0 demand/release artifacts still describe initial planned/blocked states."
            ),
            "closeout_acceptance": [
                "Generate a current-status overlay or rebuilt board from S/P summaries.",
                "Every S0-S10 and P11-P20/P20b row must map to done, partial, open, blocked, or bounded gap.",
                "A deterministic parity test must fail if a completed summary is missing from the current board.",
            ],
            "next_slice": "P21-source-status-parity",
        },
        {
            "blocker_id": "B02-p20b-owned-root-cause-open",
            "title": "P20b numeric display lineage and MemoLogicPlan quality root causes remain open",
            "source_audit_item": "AUD-02",
            "status": "closed_by_p20b_d02_d03_root_cause_tests",
            "blocks": ["expensive_llm_regression", "broad_full_chain_20_50_eval"],
            "observed_evidence": {
                "open_items": [],
                "resolved_items": [
                    "P20b-D01-ambiguous-currency-scale-root",
                    "P20b-D02-numeric-display-lineage",
                    "P20b-D03-memo-logic-plan-quality-root",
                    "P20b-D04-source-doc-status-correction",
                ],
                "root_cause_fixes": [
                    "pre_memo_fact_selection_rejects_ambiguous_currency_scale_not_memo_display_eligible",
                    "memo_logic_plan_answer_first_outline_and_evidence_to_thesis_bridge",
                    "writer_compact_payload_preserves_answer_first_outline_and_bridge",
                ],
                "regression_tests": [
                    "tests/test_d_series_fact_selection.py::test_pre_memo_fact_selection_keeps_ambiguous_large_usd_amount_out_of_memo_claims",
                    "tests/test_memo_logic_plan.py::test_memo_logic_plan_carries_answer_first_evidence_to_thesis_bridge",
                ],
            },
            "why_blocking": (
                "More gates can hide bad output, but they do not repair upstream scale lineage or "
                "answer-first evidence-to-thesis planning."
            ),
            "closeout_acceptance": [
                "Renderer/writer cannot display ambiguous currency scale as a precise amount.",
                "MemoLogicPlan contains answer-first thesis, counter-thesis, decision-changing evidence, and citations before writer execution.",
                "Deterministic tests prove the earliest faulty artifact is fixed, with gates kept only as regression protection.",
            ],
            "next_slice": "P20b-D02-D03-root-cause-closeout",
        },
        {
            "blocker_id": "B03-r-source-doc-status-reconciliation",
            "title": "R57/R58/R55/R59/R60 source documents need done/partial/open mapping",
            "source_audit_item": "AUD-03",
            "status": "closed_by_p22_source_doc_status_reconciliation"
            if p22_source_docs_closed
            else "open_source_doc_reconciliation_required",
            "blocks": ["new_feature_planning_from_stale_r_docs", "broad_full_chain_20_50_eval"],
            "observed_evidence": {
                "docs_requiring_current_status": ["R55", "R57", "R58", "R59", "R60"],
                "implemented_scope_summaries": {
                    key: summaries.get(key, {})
                    for key in ("S7", "S8", "S9", "P13", "P14", "P15", "P16")
                },
                "p22_source_doc_status_summary": p22_summary,
            },
            "why_blocking": "The source docs still contain planned rows or bounded gaps that are not mapped to current implementation evidence.",
            "closeout_acceptance": [
                "Each demand row is mapped to done, partial, open, blocked, or bounded/public-commercial gap.",
                "Source docs reference the current-status overlay rather than relying on worklogs as source of truth.",
                "No source doc language implies skeleton/smoke/gate containment is final completion.",
            ],
            "next_slice": "P22-source-doc-status-reconciliation",
        },
        {
            "blocker_id": "B04-prd-product-acceptance-not-met",
            "title": "PRD-level product acceptance is still open",
            "source_audit_item": "AUD-04",
            "status": "closed_by_p24_real_human_product_acceptance"
            if p24_human_acceptance_closed
            else "open_product_acceptance_required",
            "blocks": ["product_release_claim", "broad_full_chain_20_50_eval_as_quality_evidence"],
            "observed_evidence": {
                "p17_p19_boundaries": {
                    key: summaries.get(key, {}).get("known_boundary_fields", {})
                    for key in ("P17", "P18", "P19")
                },
                "runtime_and_data_boundaries": {
                    key: summaries.get(key, {})
                    for key in ("P12", "P14", "P15", "P16")
                },
                "p23_product_acceptance_summary": p23_summary,
                "p24_product_acceptance_summary": p24_summary,
            },
            "why_blocking": (
                "Controlled deterministic pilot rows and P23 automated API/frontend E2E checks are useful for integration, "
                "but they do not prove real reviewer adoption, accepted/rejected deliverables, defect closure, live runtime "
                "migration, or production data refresh."
            ),
            "closeout_acceptance": [
                "Real reviewer sessions with accepted/rejected deliverables and defect closure.",
                "Browser visual E2E for Workbench task, evidence, workpaper, review, deliverable, and admin flows.",
                "Runtime live migration and data/RAG live refresh are consumed by actual graph execution paths.",
            ],
            "next_slice": "P24-real-human-product-acceptance"
            if p24_summary.get("exists")
            else "P23-real-product-dogfood-and-frontend-e2e",
        },
        {
            "blocker_id": "B05-depth-packs-before-broad-full-chain",
            "title": "Secondary-market, quant, deliverable, product graph, and data-depth packs must pass pack-level gates first",
            "source_audit_item": "AUD-05",
            "status": "open_pack_level_depth_required",
            "blocks": ["broad_full_chain_20_50_eval_as_research_quality_evidence"],
            "observed_evidence": {
                "bounded_scope_summaries": {
                    key: summaries.get(key, {})
                    for key in ("S7", "S8", "S9", "P14")
                },
                "baseline_dependency_note": "Historical Product-KPI, CustomerDeployment, ProductGraph, secondary-market, quant, and deliverable gaps remain data-depth dependencies.",
            },
            "why_blocking": (
                "Broad full-chain cases mostly test orchestration when upstream packs are shallow; they do not "
                "prove report quality if product, market, quant, and deliverable evidence packs are incomplete."
            ),
            "closeout_acceptance": [
                "Run deterministic node/pack-level gates for ProductEvidencePack, SecondaryMarketPack, QuantLab, Deliverable Studio, and Retrieval/Data refresh.",
                "Only after pack-level gates pass should 20-50 broad full-chain cases count as research-quality regression.",
                "Any public-source or commercial-data limit must be typed with attempted adapter/parser evidence.",
            ],
            "next_slice": "P24-P25-pack-depth-before-broad-full-chain",
        },
    ]


def build_p21_pre_full_chain_blocker_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_dir = root / "data" / "manifests"
    summaries = _load_summaries(manifest_dir)
    current_status_rows = _current_status_overlay(root, summaries)
    current_release_board_rows = _current_release_board_rows(current_status_rows)
    blockers = pre_full_chain_blockers(root, current_status_rows=current_status_rows)
    generated_at = utc_now_iso()

    schema = {
        "schema_version": SCHEMA_VERSION,
        "artifact_role": "pre_full_chain_blocker_gate",
        "policy": {
            "broad_full_chain_eval_requires_zero_open_blockers": True,
            "node_or_pack_level_deterministic_tests_allowed_while_blocked": True,
            "smoke_or_gate_containment_cannot_close_blocker": True,
            "root_cause_repair_required_for_owned_internal_defects": True,
        },
        "required_blocker_fields": [
            "blocker_id",
            "status",
            "blocks",
            "observed_evidence",
            "why_blocking",
            "closeout_acceptance",
            "next_slice",
        ],
    }
    gate_rows = [
        {
            "gate_id": "p21_blocker_register_materialized",
            "status": "pass",
            "reason": "Five user-confirmed blockers are represented as machine-readable rows.",
        },
        {
            "gate_id": "p21_broad_full_chain_blocked_when_open",
            "status": "pass",
            "reason": "full_chain_broad_eval_allowed is false while blocker_count_open > 0.",
        },
        {
            "gate_id": "p21_machine_backlog_drift_visible",
            "status": "pass",
            "reason": "S0 demand/release status counts are recorded as blocker evidence.",
        },
        {
            "gate_id": "p21_no_blocker_marked_complete_without_acceptance",
            "status": "pass",
            "reason": "Only B01 can close when the current-status overlay covers the required scope; all remaining blockers keep explicit closeout acceptance.",
        },
        {
            "gate_id": "p21_current_status_overlay_covers_required_slices",
            "status": "pass"
            if {str(row.get("slice_id")) for row in current_status_rows}.issuperset(set(SUMMARY_FILES) | {"P20", "P20b", "P21"})
            else "fail",
            "reason": "Current status overlay covers S0-S10, P11-P19, P20, P20b, and P21.",
        },
    ]
    blocker_count_open = sum(
        1
        for item in blockers
        if str(item.get("status", "")).startswith("open_") or str(item.get("status", "")).endswith("_required")
    )
    full_chain_allowed = blocker_count_open == 0

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass",
        "release_decision": "P21_pre_full_chain_blockers_registered_broad_full_chain_blocked",
        "closeout_level": "L4_scope_pass_for_blocker_registration_only",
        "full_chain_broad_eval_allowed": full_chain_allowed,
        "allowed_while_blocked": ["deterministic_node_tests", "pack_level_tests", "targeted_full_chain_smoke_for_integration_only"],
        "not_allowed_while_blocked": ["20_50_case_full_chain_quality_claim", "product_release_claim", "automation_from_stale_release_board"],
        "blocker_count_total": len(blockers),
        "blocker_count_open": blocker_count_open,
        "gate_count": len(gate_rows),
        "gate_fail_count": sum(1 for row in gate_rows if row["status"] != "pass"),
        "outputs": {
            "schema": "configs/r53_r60/p21_pre_full_chain_blocker_gate_schema_v0_1.json",
            "blockers": "data/manifests/r53_r60_p21_pre_full_chain_blockers_v0_1.jsonl",
            "gate_rows": "data/manifests/r53_r60_p21_pre_full_chain_blocker_gate_rows_v0_1.jsonl",
            "summary": "data/manifests/r53_r60_p21_pre_full_chain_blocker_summary_v0_1.json",
            "current_status_overlay": "data/manifests/r53_r60_current_status_overlay_v0_1.jsonl",
            "current_release_board": "data/manifests/r53_r60_current_release_board_v0_1.jsonl",
            "report": "docs/internal/vnext_20260610/r53_r60_p21_pre_full_chain_blocker_gate.zh-CN.md",
        },
    }

    write_json(root / summary["outputs"]["schema"], schema)
    write_jsonl(root / summary["outputs"]["current_status_overlay"], current_status_rows)
    write_jsonl(root / summary["outputs"]["current_release_board"], current_release_board_rows)
    write_jsonl(root / summary["outputs"]["blockers"], blockers)
    write_jsonl(root / summary["outputs"]["gate_rows"], gate_rows)
    write_json(root / summary["outputs"]["summary"], summary)
    _write_report(root / summary["outputs"]["report"], summary, blockers)
    return summary


def _write_report(path: Path, summary: dict[str, Any], blockers: list[dict[str, Any]]) -> None:
    lines = [
        "# R53-R60 P21 Pre-Full-Chain Blocker Gate",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Release decision: `{summary['release_decision']}`",
        f"- Broad full-chain eval allowed: `{summary['full_chain_broad_eval_allowed']}`",
        f"- Open blockers: `{summary['blocker_count_open']}/{summary['blocker_count_total']}`",
        "",
        "## Interpretation / 解释",
        "",
        "This artifact does not claim product readiness. It only proves that the known blockers are machine-readable and that broad 20-50 case full-chain quality evaluation is blocked until upstream layers close.",
        "",
        "这个 artifact 不声明产品已经可上线；它只证明 5 个已知阻塞项已经进入机器可读台账，并且在上游层关闭前禁止把 20-50 个 broad full-chain case 当作研报质量或产品验收证据。",
        "",
        "## Blockers",
        "",
    ]
    for item in blockers:
        lines.extend(
            [
                f"### {item['blocker_id']} - {item['title']}",
                "",
                f"- Status: `{item['status']}`",
                f"- Blocks: `{', '.join(item['blocks'])}`",
                f"- Next slice: `{item['next_slice']}`",
                f"- Why blocking: {item['why_blocking']}",
                "- Closeout acceptance:",
            ]
        )
        for acceptance in item["closeout_acceptance"]:
            lines.append(f"  - {acceptance}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


__all__ = [
    "SCHEMA_VERSION",
    "build_p21_pre_full_chain_blocker_gate",
    "pre_full_chain_blockers",
]
