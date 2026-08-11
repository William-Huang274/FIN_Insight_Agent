from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sec_agent.p33_ai_semis_gold_workpaper_preflight import (
    CASE_ID,
    RELEASE_DECISION_BLOCKED,
    RELEASE_DECISION_READY,
    REQUIRED_DIMENSION_IDS,
    build_p33_ai_semis_gold_workpaper_preflight,
    default_p33_gold_workpaper_preflight_paths,
)


def seed_p33_2_manifest(tmp_path: Path) -> None:
    path = tmp_path / "data" / "manifests" / "p33_runtime_assimilation_fixture_v0_1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    evidence_refs = [
        "ev_product_nvda_blackwell_architecture",
        "ev_customer_cloud_gpu_deployment",
        "ev_fundamental_dell_ai_server_margin",
        "ev_industry_semis_value_chain_cycle",
        "ev_relationship_graph_gpu_to_foundry_semicap",
        "ev_capital_cloud_capex_market_feedback",
    ]
    judgment_cards = [
        "jc_product_architecture",
        "jc_customer_deployment",
        "jc_fundamental_margin",
        "jc_supply_chain_cycle",
        "jc_capital_feedback",
        "jc_exact_kpi_gap",
    ]
    manifest = {
        "schema_version": "fin_insight_p33_runtime_assimilation_fixture_v0_1",
        "status": "pass",
        "closeout_level": "L4_scope_pass",
        "gate_fail_count": 0,
        "evidence_packs": {
            "pack_ids_used_by_judgment_spine": [
                "ProductIntelligenceGraph",
                "FundamentalStatementPack",
                "CapitalMarketFeedbackPack",
                "CustomerDeploymentPack",
                "IndustryPlaybook",
            ],
            "evidence_rows": [
                {
                    "evidence_id": evidence_id,
                    "pack_id": "ProductIntelligenceGraph",
                    "source_role": "fixture_source_role",
                    "citation": f"fixture:{evidence_id}",
                    "authority_boundary": "bounded_thesis_driver",
                    "can_enter_judgment_spine": True,
                }
                for evidence_id in evidence_refs
            ],
            "typed_gap_refs": [
                {
                    "gap_id": "gap_sku_revenue_exact_tracker",
                    "gap_type": "commercial_or_company_undisclosed_exact_product_kpi",
                    "statement": "SKU-level exact KPI remains unavailable.",
                    "next_action": "Use product spec/deployment as bounded thesis evidence only.",
                    "public_source_absent": False,
                    "source_absent": False,
                },
                {
                    "gap_id": "gap_customer_order_amount_exact",
                    "gap_type": "public_source_or_commercial_order_exact_gap",
                    "statement": "Customer deployment exists but exact order value is unavailable.",
                    "next_action": "Use adoption signal only; do not render as revenue or backlog exact.",
                    "public_source_absent": False,
                    "source_absent": False,
                },
            ],
        },
        "judgment_state": {
            "judgment_cards": [
                {
                    "judgment_card_id": card_id,
                    "authority_boundary": "bounded_thesis_driver_not_exact_fact",
                    "business_mechanism": "Connect evidence to thesis path.",
                    "evidence_bridge": "Use evidence refs as bounded support.",
                    "financial_bridge": "Bridge through issuer facts or bounded read-through.",
                    "counter_read": "Contradictory exact evidence would weaken the card.",
                    "evidence_refs": [evidence_refs[index % len(evidence_refs)]],
                    "what_would_change_view": ["Exact KPI disclosure", "Contrary customer evidence"],
                }
                for index, card_id in enumerate(judgment_cards)
            ],
        },
        "research_lead_runtime_plan": {
            "thesis_path": {"primary_thesis": "bounded AI/Semis thesis"},
            "required_item_plan": [
                {"question_item_id": "nvda_amd_google_accelerator_competitive_position"},
                {"question_item_id": "cloud_capex_to_ai_server_readthrough"},
                {"question_item_id": "dell_ai_server_margin_quality"},
                {"question_item_id": "semicap_orders_backlog_export_risk"},
            ],
            "evidence_role_plan": [{"role": role} for role in ["product", "fundamental", "customer", "supply", "capital"]],
        },
        "memo_logic_plan": {
            "plan_id": "memo_logic:test",
            "writer_execution_policy": "writer_expression_only",
            "validation": {"status": "pass", "errors": []},
        },
        "workbench_trace_projection": {"task_id": "p33_2_runtime_assimilation_ai_semis"},
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def seed_root_cause_ledger(tmp_path: Path, *, open_blockers: bool) -> None:
    seed_project_os_required_files(tmp_path)
    path = tmp_path / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
    rows = []
    if open_blockers:
        rows.append(
            {
                "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
                "issue_id": "RC-P30-001-real-single-case-artifact-proof-pending",
                "status": "open",
                "severity": "high",
                "full_chain_blocker": True,
                "owned_by_project": True,
                "layer": "full_chain_quality",
                "symptom": "single case artifact proof pending",
                "required_fix": "run gated single case only after preflight",
            }
        )
    else:
        rows.append(
            {
                "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
                "issue_id": "RC-P30-001-real-single-case-artifact-proof-pending",
                "status": "closed",
                "severity": "high",
                "full_chain_blocker": True,
                "owned_by_project": True,
            }
        )
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def seed_scoped_p33_root_cause_ledger(tmp_path: Path) -> None:
    seed_project_os_required_files(tmp_path)
    path = tmp_path / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
    rows = [
        {
            "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
            "issue_id": "RC-P30-001-real-single-case-artifact-proof-pending",
            "status": "open",
            "severity": "high",
            "full_chain_blocker": True,
            "owned_by_project": True,
            "layer": "full_chain_quality",
            "symptom": "single case artifact proof pending",
            "required_fix": "run gated single case only after preflight",
            "blocking_run_scopes": ["broad_full_chain", "case_expansion", "release_eval"],
            "allowed_run_scopes": ["p33_single_gold_case"],
        },
        {
            "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
            "issue_id": "RC-P30-003-paid-full-chain-overuse-risk",
            "status": "closed",
            "severity": "medium",
            "full_chain_blocker": False,
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def seed_project_os_required_files(tmp_path: Path) -> None:
    project_os = tmp_path / "docs" / "project_os"
    project_os.mkdir(parents=True, exist_ok=True)
    for name in [
        "README.md",
        "current_context_pack.zh-CN.md",
        "full_chain_run_policy.zh-CN.md",
        "token_budget_policy.zh-CN.md",
        "done_definition_l4_scope_pass.zh-CN.md",
    ]:
        (project_os / name).write_text("# test\n", encoding="utf-8")
    (project_os / "full_chain_preflight_checklist.json").write_text(
        json.dumps({"schema_version": "test", "checks": [{"check_id": "x"}]}),
        encoding="utf-8",
    )
    (project_os / "external_pattern_registry.jsonl").write_text(
        json.dumps({"pattern_id": "p", "status": "active_reference"}) + "\n",
        encoding="utf-8",
    )
    (project_os / "financial_research_method_registry.jsonl").write_text(
        json.dumps({"method_id": "m", "status": "active"}) + "\n",
        encoding="utf-8",
    )
    (project_os / "capability_status_ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"capability_id": "p31_project_os_core", "status": "L4_scope_pass"}),
                json.dumps({"capability_id": "p31_full_chain_preflight_guard", "status": "L4_scope_pass"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_p33_gold_preflight_blocks_paid_run_when_project_os_has_open_blocker(tmp_path: Path) -> None:
    seed_p33_2_manifest(tmp_path)
    seed_root_cause_ledger(tmp_path, open_blockers=True)

    manifest = build_p33_ai_semis_gold_workpaper_preflight(tmp_path)
    paths = default_p33_gold_workpaper_preflight_paths(tmp_path)

    assert manifest["case_id"] == CASE_ID
    assert manifest["deterministic_preflight_status"] == "pass"
    assert manifest["status"] == "blocked"
    assert manifest["paid_run_allowed"] is False
    assert manifest["release_decision"] == RELEASE_DECISION_BLOCKED
    assert manifest["project_os_preflight"]["open_full_chain_blocker_count"] == 1
    assert manifest["gate_fail_count"] == 0
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()


def test_p33_gold_case_contract_has_required_dimensions_and_fail_conditions(tmp_path: Path) -> None:
    seed_p33_2_manifest(tmp_path)
    seed_root_cause_ledger(tmp_path, open_blockers=True)

    manifest = build_p33_ai_semis_gold_workpaper_preflight(tmp_path)
    contract = manifest["case_contract"]

    assert set(REQUIRED_DIMENSION_IDS).issubset(set(contract["required_dimensions"]))
    assert contract["case_scope"] == "single_ai_semis_gold_case"
    assert "NVDA" in contract["focus_tickers"]
    assert "DELL" in contract["focus_tickers"]
    assert "memo_says_product_layer_unanswerable_only_because_no_sku_revenue" in contract["fail_conditions"]
    assert "required_dimension_missing_from_memo" in contract["targeted_repair_triggers"]


def test_p33_gold_preflight_uses_p33_2_upstream_material(tmp_path: Path) -> None:
    seed_p33_2_manifest(tmp_path)
    seed_root_cause_ledger(tmp_path, open_blockers=True)

    manifest = build_p33_ai_semis_gold_workpaper_preflight(tmp_path)
    material = manifest["upstream_material_projection"]

    assert "ProductIntelligenceGraph" in material["pack_ids"]
    assert "FundamentalStatementPack" in material["pack_ids"]
    assert "ev_product_nvda_blackwell_architecture" in material["evidence_refs"]
    assert "ev_fundamental_dell_ai_server_margin" in material["evidence_refs"]
    assert "jc_product_architecture" in material["judgment_card_ids"]
    assert "gap_sku_revenue_exact_tracker" in material["typed_gap_refs"]
    assert material["memo_logic_plan_refs"] == ["memo_logic:test"]
    assert material["data_script_lineage_preflight"]["status"] == "pass"


def test_p33_gold_preflight_fails_when_pre_paid_lineage_is_not_auditable(tmp_path: Path) -> None:
    seed_p33_2_manifest(tmp_path)
    seed_root_cause_ledger(tmp_path, open_blockers=True)
    path = tmp_path / "data" / "manifests" / "p33_runtime_assimilation_fixture_v0_1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["evidence_packs"]["evidence_rows"][0].pop("citation")
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    result = build_p33_ai_semis_gold_workpaper_preflight(tmp_path, write_outputs=False)
    material = result["upstream_material_projection"]

    assert result["deterministic_preflight_status"] == "fail"
    assert material["data_script_lineage_preflight"]["status"] == "fail"
    assert result["gate_fail_count"] >= 1
    assert any(
        row["gate_id"] == "p33_3_data_script_lineage_preflight_pass" and row["status"] == "fail"
        for row in result["acceptance_gates"]
    )


def test_p33_gold_preflight_can_become_ready_after_project_os_blockers_close(tmp_path: Path) -> None:
    seed_p33_2_manifest(tmp_path)
    seed_root_cause_ledger(tmp_path, open_blockers=False)

    manifest = build_p33_ai_semis_gold_workpaper_preflight(tmp_path, write_outputs=False)

    assert manifest["deterministic_preflight_status"] == "pass"
    assert manifest["status"] == "ready_for_paid_run_preflights"
    assert manifest["paid_run_allowed"] is True
    assert manifest["release_decision"] == RELEASE_DECISION_READY
    assert manifest["paid_run_policy"]["remaining_pre_paid_preflights"]


def test_p33_gold_preflight_can_proceed_for_scoped_single_case_blockers(tmp_path: Path) -> None:
    seed_p33_2_manifest(tmp_path)
    seed_scoped_p33_root_cause_ledger(tmp_path)

    manifest = build_p33_ai_semis_gold_workpaper_preflight(tmp_path, write_outputs=False)

    assert manifest["deterministic_preflight_status"] == "pass"
    assert manifest["status"] == "ready_for_paid_run_preflights"
    assert manifest["paid_run_allowed"] is True
    assert manifest["release_decision"] == RELEASE_DECISION_READY
    assert manifest["project_os_preflight"]["run_scope"] == "p33_single_gold_case"
