"""P33-3 AI/Semis gold workpaper no-paid preflight.

This fixture freezes one AI/Semis gold-case objective and verifies that the
post-P33-2 runtime-assimilation artifact contains enough writer-ready material
before any paid/full-chain run is allowed. It uses a scoped Project OS preflight:
broad case expansion can remain blocked while this one controlled gold-case run
is allowed to proceed to the remaining pre-paid gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_runtime_task_spine import digest_payload, rel_path, stable_id, utc_now_iso, write_json
from sec_agent.project_os_preflight import compact_preflight_stdout, run_project_os_preflight


SCHEMA_VERSION = "fin_insight_p33_ai_semis_gold_workpaper_preflight_v0_1"
CONTRACT_ID = "p33_ai_semis_gold_workpaper_case_contract_v0_1"
CASE_ID = "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
P33_PROJECT_OS_RUN_SCOPE = "p33_single_gold_case"
RELEASE_DECISION_BLOCKED = "P33_3_paid_run_blocked_by_project_os_preflight"
RELEASE_DECISION_READY = "P33_3_ready_for_remaining_pre_paid_preflights"

REQUIRED_DIMENSION_IDS = [
    "opening_thesis",
    "fundamentals",
    "product_architecture",
    "customer_deployment",
    "industry_supply_chain",
    "capital_market_feedback",
    "counter_thesis_and_what_would_change",
]

REQUIRED_P33_2_PACK_IDS = [
    "ProductIntelligenceGraph",
    "FundamentalStatementPack",
    "CapitalMarketFeedbackPack",
    "CustomerDeploymentPack",
    "IndustryPlaybook",
]

REQUIRED_P33_2_EVIDENCE_REFS = [
    "ev_product_nvda_blackwell_architecture",
    "ev_customer_cloud_gpu_deployment",
    "ev_fundamental_dell_ai_server_margin",
    "ev_industry_semis_value_chain_cycle",
    "ev_relationship_graph_gpu_to_foundry_semicap",
    "ev_capital_cloud_capex_market_feedback",
]

REQUIRED_P33_2_JUDGMENT_CARDS = [
    "jc_product_architecture",
    "jc_customer_deployment",
    "jc_fundamental_margin",
    "jc_supply_chain_cycle",
    "jc_capital_feedback",
    "jc_exact_kpi_gap",
]


@dataclass(frozen=True)
class P33GoldWorkpaperPreflightPaths:
    manifest_path: Path
    report_path: Path


def default_p33_gold_workpaper_preflight_paths(root: Path) -> P33GoldWorkpaperPreflightPaths:
    return P33GoldWorkpaperPreflightPaths(
        manifest_path=root / "data" / "manifests" / "p33_ai_semis_gold_workpaper_preflight_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_ai_semis_gold_workpaper_preflight_report.zh-CN.md",
    )


def build_p33_ai_semis_gold_workpaper_preflight(root: Path, *, write_outputs: bool = True) -> dict[str, Any]:
    root = root.resolve()
    p33_2_manifest_path = root / "data" / "manifests" / "p33_runtime_assimilation_fixture_v0_1.json"
    p33_2_manifest = _read_json_required(p33_2_manifest_path)
    project_os_preflight = _build_project_os_preflight_snapshot(root)
    case_contract = _build_case_contract()
    upstream_material = _build_upstream_material_projection(root, p33_2_manifest)
    paid_run_policy = _build_paid_run_policy(project_os_preflight)
    acceptance_gates = evaluate_p33_gold_workpaper_preflight_gates(
        p33_2_manifest=p33_2_manifest,
        project_os_preflight=project_os_preflight,
        case_contract=case_contract,
        upstream_material=upstream_material,
        paid_run_policy=paid_run_policy,
    )
    fail_count = sum(1 for row in acceptance_gates if row["status"] != "pass")
    deterministic_status = "pass" if fail_count == 0 else "fail"
    paid_run_allowed = bool(paid_run_policy["paid_run_allowed"])
    status = "ready_for_paid_run_preflights" if deterministic_status == "pass" and paid_run_allowed else "blocked"
    release_decision = RELEASE_DECISION_READY if paid_run_allowed else RELEASE_DECISION_BLOCKED
    paths = default_p33_gold_workpaper_preflight_paths(root)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "contract_id": CONTRACT_ID,
        "case_id": CASE_ID,
        "status": status,
        "deterministic_preflight_status": deterministic_status,
        "paid_run_allowed": paid_run_allowed,
        "release_decision": release_decision,
        "closeout_level": "preflight_contract_pass_paid_run_blocked" if not paid_run_allowed else "ready_for_next_preflights",
        "gate_fail_count": fail_count,
        "case_contract": case_contract,
        "project_os_preflight": project_os_preflight,
        "upstream_material_projection": upstream_material,
        "paid_run_policy": paid_run_policy,
        "acceptance_gates": acceptance_gates,
        "source_fixture_refs": {
            "p33_2_manifest": rel_path(p33_2_manifest_path, root),
            "p33_2_report": "docs/internal/vnext_20260610/p33_runtime_assimilation_fixture_report.zh-CN.md",
            "project_os_root_cause_ledger": "docs/project_os/root_cause_issue_ledger.jsonl",
            "p33_preflight_manifest": rel_path(paths.manifest_path, root),
            "p33_preflight_report": rel_path(paths.report_path, root),
        },
        "next_action": (
            "Do not run paid full-chain until Project OS full-chain blockers are explicitly "
            "closed or the user grants a diagnostic override after seeing blockers."
            if not paid_run_allowed
            else "Run token/provider/real-evidence/AIE preflights before one paid real-evidence case."
        ),
        "do_not_promote": [
            "boundary_heavy_memo_as_gold",
            "search_summary_as_gold_workpaper",
            "product_layer_failed_only_because_no_sku_revenue",
            "cloud_capex_as_supplier_exact_revenue",
            "wide_specialist_fanout_without_required_item",
            "raw_evidence_dump_to_writer",
            "memo_claims_missing_when_upstream_judgment_cards_exist",
        ],
    }
    if write_outputs:
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_p33_gold_workpaper_preflight_report(manifest), encoding="utf-8")
    return manifest


def evaluate_p33_gold_workpaper_preflight_gates(
    *,
    p33_2_manifest: Mapping[str, Any],
    project_os_preflight: Mapping[str, Any],
    case_contract: Mapping[str, Any],
    upstream_material: Mapping[str, Any],
    paid_run_policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks = [
        (
            "p33_3_p33_2_runtime_assimilation_input_valid",
            p33_2_manifest.get("status") == "pass"
            and p33_2_manifest.get("closeout_level") == "L4_scope_pass"
            and int(p33_2_manifest.get("gate_fail_count") or 0) == 0,
            "P33-2 runtime-assimilation artifact is available and passed deterministic L4 scope gates.",
            {
                "status": p33_2_manifest.get("status"),
                "closeout_level": p33_2_manifest.get("closeout_level"),
                "gate_fail_count": p33_2_manifest.get("gate_fail_count"),
            },
        ),
        (
            "p33_3_single_case_contract_frozen",
            case_contract.get("case_id") == CASE_ID
            and case_contract.get("case_scope") == "single_ai_semis_gold_case"
            and len(case_contract.get("focus_tickers") or []) >= 4,
            "Exactly one AI/Semis gold-case objective contract is frozen before paid execution.",
            {"case_id": case_contract.get("case_id"), "focus_tickers": case_contract.get("focus_tickers")},
        ),
        (
            "p33_3_gold_dimensions_required",
            set(REQUIRED_DIMENSION_IDS).issubset(set(case_contract.get("required_dimensions") or [])),
            "Gold workpaper dimensions cover thesis, fundamentals, product, deployment, supply chain, capital and counter-thesis.",
            {"required_dimensions": case_contract.get("required_dimensions")},
        ),
        (
            "p33_3_upstream_material_traceable",
            set(REQUIRED_P33_2_PACK_IDS).issubset(set(upstream_material.get("pack_ids") or []))
            and set(REQUIRED_P33_2_EVIDENCE_REFS).issubset(set(upstream_material.get("evidence_refs") or []))
            and set(REQUIRED_P33_2_JUDGMENT_CARDS).issubset(set(upstream_material.get("judgment_card_ids") or [])),
            "Required Product/Fundamental/Capital/Customer/Industry packs, evidence refs and JudgmentCards are present.",
            {
                "pack_ids": upstream_material.get("pack_ids"),
                "evidence_ref_count": len(upstream_material.get("evidence_refs") or []),
                "judgment_card_count": len(upstream_material.get("judgment_card_ids") or []),
            },
        ),
        (
            "p33_3_required_item_to_writer_mapping_present",
            len(upstream_material.get("required_item_plan") or []) >= 4
            and len(upstream_material.get("memo_logic_plan_refs") or []) >= 1
            and len(upstream_material.get("typed_gap_refs") or []) >= 2,
            "Research Lead required items, MemoLogicPlan and typed gaps are visible before paid execution.",
            {
                "required_item_count": len(upstream_material.get("required_item_plan") or []),
                "memo_logic_plan_refs": upstream_material.get("memo_logic_plan_refs"),
                "typed_gap_refs": upstream_material.get("typed_gap_refs"),
            },
        ),
        (
            "p33_3_data_script_lineage_preflight_pass",
            upstream_material.get("data_script_lineage_preflight", {}).get("status") == "pass",
            "Pre-paid data/script lineage check proves evidence rows, JudgmentCards, typed gaps and MemoLogicPlan are auditable before paid execution.",
            upstream_material.get("data_script_lineage_preflight", {}),
        ),
        (
            "p33_3_fail_conditions_and_repair_triggers_explicit",
            len(case_contract.get("fail_conditions") or []) >= 8
            and len(case_contract.get("targeted_repair_triggers") or []) >= 5,
            "Known failure modes and targeted-repair triggers are explicit before paid execution.",
            {
                "fail_condition_count": len(case_contract.get("fail_conditions") or []),
                "targeted_repair_trigger_count": len(case_contract.get("targeted_repair_triggers") or []),
            },
        ),
        (
            "p33_3_project_os_preflight_enforced",
            (
                project_os_preflight.get("status") == "blocked"
                and paid_run_policy.get("paid_run_allowed") is False
                and project_os_preflight.get("open_full_chain_blocker_count", 0) > 0
            )
            or (project_os_preflight.get("status") == "pass" and paid_run_policy.get("paid_run_allowed") is True),
            "Project OS full-chain preflight is enforced with run-scope-aware blockers.",
            {
                "run_scope": project_os_preflight.get("run_scope"),
                "project_os_status": project_os_preflight.get("status"),
                "open_full_chain_blocker_count": project_os_preflight.get("open_full_chain_blocker_count"),
                "paid_run_allowed": paid_run_policy.get("paid_run_allowed"),
            },
        ),
        (
            "p33_3_no_paid_or_full_chain_used",
            paid_run_policy.get("paid_llm_call_count") == 0 and paid_run_policy.get("full_chain_run_count") == 0,
            "P33-3 preflight used no paid LLM and no full-chain run.",
            {
                "paid_llm_call_count": paid_run_policy.get("paid_llm_call_count"),
                "full_chain_run_count": paid_run_policy.get("full_chain_run_count"),
            },
        ),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "fixture_id": "P33-3",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "preflight_contract_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def render_p33_gold_workpaper_preflight_report(manifest: Mapping[str, Any]) -> str:
    case = manifest.get("case_contract") if isinstance(manifest.get("case_contract"), Mapping) else {}
    project_os = manifest.get("project_os_preflight") if isinstance(manifest.get("project_os_preflight"), Mapping) else {}
    material = (
        manifest.get("upstream_material_projection")
        if isinstance(manifest.get("upstream_material_projection"), Mapping)
        else {}
    )
    lines = [
        "# P33-3 AI/Semis Gold Workpaper Preflight",
        "",
        f"Generated: `{manifest['generated_at']}`",
        f"Case: `{manifest['case_id']}`",
        f"Status: `{manifest['status']}`",
        f"Deterministic preflight: `{manifest['deterministic_preflight_status']}`",
        f"Paid run allowed: `{manifest['paid_run_allowed']}`",
        f"Release decision: `{manifest['release_decision']}`",
        "",
        "## Case Objective",
        "",
        str(case.get("research_question") or ""),
        "",
        "## Required Dimensions",
        "",
    ]
    for dimension in case.get("required_dimensions") or []:
        lines.append(f"- `{dimension}`")
    lines.extend(["", "## Upstream Material", ""])
    lines.append(f"- Packs: `{len(material.get('pack_ids') or [])}`")
    lines.append(f"- Evidence refs: `{len(material.get('evidence_refs') or [])}`")
    lines.append(f"- JudgmentCards: `{len(material.get('judgment_card_ids') or [])}`")
    lines.append(f"- Typed gaps: `{len(material.get('typed_gap_refs') or [])}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in manifest.get("acceptance_gates") or []:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Project OS Preflight", ""])
    lines.append(f"- Status: `{project_os.get('status')}`")
    lines.append(f"- Run scope: `{project_os.get('run_scope')}`")
    lines.append(f"- Open full-chain blockers: `{project_os.get('open_full_chain_blocker_count')}`")
    for blocker in project_os.get("open_full_chain_blockers") or []:
        lines.append(f"- `{blocker.get('issue_id')}`: {blocker.get('symptom')}")
    lines.extend(["", "## Next Action", "", str(manifest.get("next_action")), ""])
    return "\n".join(lines)


def _build_case_contract() -> dict[str, Any]:
    return {
        "schema_version": "fin_insight_p33_case_objective_contract_v0_1",
        "case_id": CASE_ID,
        "case_scope": "single_ai_semis_gold_case",
        "case_family": "AI/Semis",
        "research_question": (
            "Assess whether AI infrastructure demand read-through from hyperscaler capex, "
            "accelerator architecture, customer deployment and DELL AI server margin quality "
            "supports a bounded thesis on NVDA/AMD/GOOGL TPU competition and DELL supply-chain exposure."
        ),
        "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
        "supporting_tickers": ["ASML", "LRCX", "AMAT", "KLAC", "TSM"],
        "required_dimensions": REQUIRED_DIMENSION_IDS,
        "required_answer_moves": [
            "Start with a clear bounded thesis, not background.",
            "Explain product/architecture advantage and competitive/substitution edges.",
            "Bridge deployment and cloud capex to demand pool without treating it as supplier exact revenue.",
            "Assess DELL AI server revenue quality through margin, cash flow and working-capital implications.",
            "Map supply-chain dependencies and bottlenecks from GPU to foundry/packaging/HBM/semicap.",
            "Separate exact facts, bounded thesis drivers, proxies and typed gaps.",
            "State counter-thesis and what evidence would change the view.",
        ],
        "minimum_upstream_inputs": {
            "runtime_assimilation_manifest": "data/manifests/p33_runtime_assimilation_fixture_v0_1.json",
            "required_pack_ids": REQUIRED_P33_2_PACK_IDS,
            "required_evidence_refs": REQUIRED_P33_2_EVIDENCE_REFS,
            "required_judgment_cards": REQUIRED_P33_2_JUDGMENT_CARDS,
        },
        "fail_conditions": [
            "opening_is_background_summary_not_thesis",
            "memo_is_claim_inventory_or_search_summary",
            "memo_says_product_layer_unanswerable_only_because_no_sku_revenue",
            "cloud_capex_rendered_as_supplier_exact_revenue_or_backlog",
            "customer_deployment_rendered_as_order_amount_without_exact_source",
            "capital_market_feedback_rendered_as_investment_advice_or_realtime_flow",
            "memo_claims_missing_evidence_when_upstream_judgment_card_exists",
            "writer_receives_raw_evidence_dump_instead_of_memo_logic_plan",
            "section_dominated_by_scope_hypothesis_without_low_confidence_context_label",
            "wide_specialist_fanout_without_required_item",
        ],
        "targeted_repair_triggers": [
            "required_dimension_missing_from_memo",
            "existing_upstream_evidence_not_used_by_writer",
            "typed_gap_not_traceable_to_source_or_adapter_attempt",
            "numeric_or_display_value_lineage_missing",
            "product_graph_edge_used_without_authority_boundary",
            "token_to_judgment_yield_below_threshold",
        ],
        "manual_review_standard": {
            "target_style": "buyside-style analyst workpaper",
            "not_target_style": ["sell-side marketing report", "search result summary", "gap-only caution memo"],
            "review_required_before_gold_candidate": True,
        },
    }


def _build_upstream_material_projection(root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    evidence_packs = manifest.get("evidence_packs") if isinstance(manifest.get("evidence_packs"), Mapping) else {}
    judgment_state = manifest.get("judgment_state") if isinstance(manifest.get("judgment_state"), Mapping) else {}
    lead_plan = manifest.get("research_lead_runtime_plan") if isinstance(manifest.get("research_lead_runtime_plan"), Mapping) else {}
    trace = manifest.get("workbench_trace_projection") if isinstance(manifest.get("workbench_trace_projection"), Mapping) else {}
    memo_logic = manifest.get("memo_logic_plan") if isinstance(manifest.get("memo_logic_plan"), Mapping) else {}
    pack_ids = list(evidence_packs.get("pack_ids_used_by_judgment_spine") or [])
    evidence_refs = [str(row.get("evidence_id")) for row in evidence_packs.get("evidence_rows") or [] if row.get("evidence_id")]
    if not evidence_refs:
        evidence_refs = list(trace.get("evidence_refs") or [])
    judgment_cards = [str(row.get("judgment_card_id")) for row in judgment_state.get("judgment_cards") or [] if row.get("judgment_card_id")]
    if not judgment_cards:
        judgment_cards = list(trace.get("judgment_card_ids") or [])
    typed_gap_refs = [str(row.get("gap_id")) for row in evidence_packs.get("typed_gap_refs") or [] if row.get("gap_id")]
    if not typed_gap_refs:
        typed_gap_refs = list(trace.get("typed_gap_refs") or [])
    return {
        "schema_version": "fin_insight_p33_upstream_material_projection_v0_1",
        "source_manifest_digest": digest_payload(manifest),
        "source_manifest_ref": "data/manifests/p33_runtime_assimilation_fixture_v0_1.json",
        "root": root.as_posix(),
        "pack_ids": pack_ids,
        "evidence_refs": sorted(set(evidence_refs)),
        "judgment_card_ids": sorted(set(judgment_cards)),
        "typed_gap_refs": sorted(set(typed_gap_refs)),
        "required_item_plan": list(lead_plan.get("required_item_plan") or []),
        "evidence_role_plan": list(lead_plan.get("evidence_role_plan") or []),
        "thesis_path_digest": digest_payload(lead_plan.get("thesis_path") or {}),
        "memo_logic_plan_refs": [str(memo_logic.get("plan_id") or "")] if memo_logic.get("plan_id") else [],
        "writer_payload_policy": memo_logic.get("writer_execution_policy", "writer_expression_only_no_fact_tools"),
        "data_script_lineage_preflight": _build_pre_paid_data_script_lineage_preflight(manifest),
        "workbench_trace_task_id": trace.get("task_id"),
    }


def _build_pre_paid_data_script_lineage_preflight(manifest: Mapping[str, Any]) -> dict[str, Any]:
    evidence_packs = manifest.get("evidence_packs") if isinstance(manifest.get("evidence_packs"), Mapping) else {}
    judgment_state = manifest.get("judgment_state") if isinstance(manifest.get("judgment_state"), Mapping) else {}
    memo_logic = manifest.get("memo_logic_plan") if isinstance(manifest.get("memo_logic_plan"), Mapping) else {}
    evidence_rows = [row for row in evidence_packs.get("evidence_rows") or [] if isinstance(row, Mapping)]
    typed_gaps = [row for row in evidence_packs.get("typed_gap_refs") or [] if isinstance(row, Mapping)]
    judgment_cards = [row for row in judgment_state.get("judgment_cards") or [] if isinstance(row, Mapping)]
    issues: list[dict[str, Any]] = []
    for row in evidence_rows:
        evidence_id = str(row.get("evidence_id") or "")
        for field in ("pack_id", "source_role", "citation", "authority_boundary"):
            if not str(row.get(field) or "").strip():
                issues.append({"type": "evidence_row_missing_lineage_field", "evidence_id": evidence_id, "field": field})
        if row.get("can_enter_judgment_spine") is not True:
            issues.append({"type": "evidence_row_not_marked_judgment_spine_ready", "evidence_id": evidence_id})
    for row in judgment_cards:
        card_id = str(row.get("judgment_card_id") or "")
        for field in ("authority_boundary", "business_mechanism", "evidence_bridge", "financial_bridge", "counter_read"):
            if not str(row.get(field) or "").strip():
                issues.append({"type": "judgment_card_missing_writer_lineage_field", "judgment_card_id": card_id, "field": field})
        if not row.get("evidence_refs"):
            issues.append({"type": "judgment_card_missing_evidence_refs", "judgment_card_id": card_id})
        if not row.get("what_would_change_view"):
            issues.append({"type": "judgment_card_missing_what_would_change_view", "judgment_card_id": card_id})
    for row in typed_gaps:
        gap_id = str(row.get("gap_id") or "")
        for field in ("gap_type", "next_action", "statement"):
            if not str(row.get(field) or "").strip():
                issues.append({"type": "typed_gap_missing_boundary_field", "gap_id": gap_id, "field": field})
        if "public_source_absent" not in row or "source_absent" not in row:
            issues.append({"type": "typed_gap_missing_source_absence_flags", "gap_id": gap_id})
    validation = memo_logic.get("validation") if isinstance(memo_logic.get("validation"), Mapping) else {}
    if not str(memo_logic.get("plan_id") or "").strip():
        issues.append({"type": "memo_logic_plan_missing_plan_id"})
    if validation.get("status") != "pass":
        issues.append({"type": "memo_logic_plan_validation_not_pass", "status": validation.get("status")})
    return {
        "schema_version": "fin_insight_p33_pre_paid_data_script_lineage_preflight_v0_1",
        "status": "pass" if not issues else "fail",
        "evidence_row_count": len(evidence_rows),
        "judgment_card_count": len(judgment_cards),
        "typed_gap_count": len(typed_gaps),
        "memo_logic_plan_ref": str(memo_logic.get("plan_id") or ""),
        "issue_count": len(issues),
        "issues": issues[:20],
        "policy": (
            "This is a pre-paid lineage check over P33-2 writer-ready material. "
            "Post-run DataScriptQualityAudit must still inspect generated full-chain artifacts."
        ),
    }


def _build_project_os_preflight_snapshot(root: Path) -> dict[str, Any]:
    return compact_preflight_stdout(run_project_os_preflight(root, run_scope=P33_PROJECT_OS_RUN_SCOPE))


def _build_paid_run_policy(project_os_preflight: Mapping[str, Any]) -> dict[str, Any]:
    paid_allowed = project_os_preflight.get("status") == "pass"
    return {
        "schema_version": "fin_insight_p33_paid_run_policy_v0_1",
        "paid_run_allowed": paid_allowed,
        "requires_explicit_diagnostic_override": not paid_allowed,
        "remaining_pre_paid_preflights": [
            "token_budget_preflight",
            "provider_health_preflight",
            "real_evidence_mode_preflight",
            "agent_information_economy_preflight",
            "data_script_lineage_preflight",
        ],
        "paid_llm_call_count": 0,
        "full_chain_run_count": 0,
        "policy_note": (
            "This preflight does not close RC-P30 blockers. It freezes the case contract "
            "and records whether paid execution is allowed."
        ),
    }


def _read_json_required(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required_json_missing:{path}")
    return json.loads(path.read_text(encoding="utf-8"))
