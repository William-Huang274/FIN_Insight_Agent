from __future__ import annotations

import json
from pathlib import Path

from sec_agent.data_script_quality_audit import (
    build_data_script_quality_summary,
    render_data_script_quality_markdown,
)
from sec_agent.langgraph_orchestrator import (
    _node_multi_agent_memo_writer,
    _with_multi_agent_artifact_refs,
    _write_memo_surface_artifacts,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_data_script_quality_audit_flags_owned_projection_and_trace_defects(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_ai"
    _write_json(
        case_dir / "pre_memo_fact_selection.json",
        {
            "summary": {"approved_fact_count": 2},
            "approved_facts": [
                {
                    "fact_id": "f_display_ok",
                    "ticker": "DELL",
                    "value": 16.1,
                    "display_value": "$16.1B",
                    "display_lineage_status": "pass",
                },
                {
                    "fact_id": "f_display_bad",
                    "ticker": "NVDA",
                    "numeric_value": 42,
                    "display_value": "",
                    "display_lineage_status": "missing",
                },
            ],
        },
    )
    _write_json(
        case_dir / "claim_cards.json",
        {
            "supported_claims": [
                {"claim_id": "c1", "claim": "DELL AI server revenue supports product analysis."},
                {"claim_id": "c2", "claim": "NVDA Blackwell supply supports product analysis."},
            ]
        },
    )
    _write_json(case_dir / "verified_judgment_plan.json", {"supported_claims": []})
    _write_json(
        case_dir / "memo_answer.json",
        {
            "memo_writer_diagnostics": {
                "deterministic_salvage_used": True,
                "salvage_reason": "deterministic_memo_gate_failed",
            }
        },
    )
    (case_dir / "qwen").mkdir(parents=True)
    (case_dir / "qwen" / "rendered_answer.md").write_text(
        "Bounded answer only: memo verification failed under current evidence constraints.\n",
        encoding="utf-8",
    )
    _write_json(
        case_dir / "p30_root_cause_quality_audit.json",
        {
            "required_item_matrix": {
                "items": [
                    {
                        "question_item_id": "customer_deployment_or_order_signal",
                        "status": "available_not_rendered",
                    }
                ]
            },
            "product_reasoning_frame": {"coverage_roles": ["deployment", "product_spec"]},
            "root_cause_rows": [
                {
                    "symptom": "available evidence not rendered",
                    "earliest_faulty_artifact": "memo_answer.rendered_answer",
                }
            ],
        },
    )
    _write_json(
        case_dir / "typed_gap_ledger.json",
        {
            "gaps": [
                {
                    "gap_type": "parser_gap",
                    "reason": "company IR PDF table parser did not extract numeric rows",
                },
                {
                    "gap_type": "issuer_gap",
                    "reason": "not_in_manifest_for_mcp_route_scope",
                },
            ]
        },
    )
    for filename in ("source_layer_capability_audit.json", "supervising_analyst_pack.json"):
        _write_json(case_dir / filename, {})

    audit = build_data_script_quality_summary({"run_id": "unit", "cases": [{"case_id": "case_ai"}]}, artifact_root=tmp_path)
    case = audit["cases"][0]

    assert audit["status"] == "fail"
    assert case["status"] == "fail"
    assert "memo_logic_plan_artifact_missing" in case["issues"]
    assert "required_item_available_not_rendered" in case["issues"]
    assert "memo_writer_deterministic_salvage_used" in case["issues"]
    assert "product_evidence_available_not_rendered" in case["issues"]
    assert "display_value_lineage_missing" in case["issues"]
    assert "owned_parser_locator_gap_present" in case["issues"]
    assert "source_route_scope_false_gap_present" in case["issues"]
    assert "memo_logic_plan_to_writer_projection" in case["root_cause_candidates"]
    assert "parser_locator_adapter_root_cause" in case["root_cause_candidates"]
    assert "source_route_scope_or_manifest_adapter" in case["root_cause_candidates"]
    assert "data / script" in render_data_script_quality_markdown(audit).lower()


def test_data_script_quality_audit_does_not_misclassify_required_item_repair_text_as_parser_gap(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case_required_item"
    _write_json(case_dir / "pre_memo_fact_selection.json", {"summary": {"approved_fact_count": 0}, "approved_facts": []})
    _write_json(case_dir / "claim_cards.json", {"supported_claims": []})
    _write_json(case_dir / "verified_judgment_plan.json", {"supported_claims": []})
    _write_json(case_dir / "memo_logic_plan.json", {"validation": {"status": "pass"}})
    _write_json(
        case_dir / "memo_answer.json",
        {"memo_writer_diagnostics": {"deterministic_salvage_used": False}, "memo_logic_plan": {"validation": {"status": "pass"}}},
    )
    (case_dir / "qwen").mkdir(parents=True)
    (case_dir / "qwen" / "rendered_answer.md").write_text("ASML 订单和积压没有被充分回答。\n", encoding="utf-8")
    _write_json(
        case_dir / "p30_root_cause_quality_audit.json",
        {
            "required_item_matrix": {
                "items": [{"question_item_id": "asml_orders_or_backlog", "status": "available_not_rendered"}]
            },
            "root_cause_rows": [
                {
                    "symptom": "required_item_not_covered",
                    "required_item_id": "asml_orders_or_backlog",
                    "earliest_faulty_artifact": "memo_answer.rendered_answer",
                    "root_cause_layer": "memo_logic_plan_evidence_selection",
                    "repair_action": (
                        "ensure required item is traced from retrieval to ClaimCard/MemoLogicPlan and final memo, "
                        "or diagnose parser/source boundary"
                    ),
                    "status": "open",
                }
            ],
        },
    )
    _write_json(case_dir / "typed_gap_ledger.json", {"gaps": []})
    for filename in ("source_layer_capability_audit.json", "supervising_analyst_pack.json"):
        _write_json(case_dir / filename, {})

    audit = build_data_script_quality_summary(
        {"run_id": "unit_required_item", "cases": [{"case_id": "case_required_item"}]},
        artifact_root=tmp_path,
    )
    case = audit["cases"][0]

    assert audit["status"] == "fail"
    assert "p30_root_cause_rows_open" in case["issues"]
    assert "required_item_available_not_rendered" in case["issues"]
    assert "owned_parser_locator_gap_present" not in case["issues"]
    assert case["metrics"]["owned_parser_locator_gap_count"] == 0
    assert case["metrics"]["p30_open_root_cause_row_count"] == 1


def test_data_script_quality_audit_passes_complete_trace(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_ok"
    _write_json(
        case_dir / "pre_memo_fact_selection.json",
        {
            "summary": {"approved_fact_count": 1},
            "approved_facts": [
                {
                    "fact_id": "f1",
                    "ticker": "NVDA",
                    "value": 100,
                    "display_value": "$100B",
                    "display_lineage_status": "pass",
                }
            ],
        },
    )
    _write_json(case_dir / "claim_cards.json", {"supported_claims": [{"claim_id": "c1"}]})
    _write_json(case_dir / "verified_judgment_plan.json", {"supported_claims": [{"claim_id": "c1"}]})
    _write_json(case_dir / "memo_logic_plan.json", {"validation": {"status": "pass"}})
    _write_json(case_dir / "memo_answer.json", {"memo_writer_diagnostics": {"deterministic_salvage_used": False}})
    (case_dir / "qwen").mkdir(parents=True)
    (case_dir / "qwen" / "rendered_answer.md").write_text(
        "NVDA 的产品、客户部署和财务证据共同支持一个有边界的判断。\n",
        encoding="utf-8",
    )
    _write_json(
        case_dir / "p30_root_cause_quality_audit.json",
        {
            "required_item_matrix": {"items": [{"question_item_id": "nvda_gpu_supply_generation", "status": "covered"}]},
            "product_reasoning_frame": {"coverage_roles": ["product_spec"]},
        },
    )
    for filename in ("typed_gap_ledger.json", "source_layer_capability_audit.json", "supervising_analyst_pack.json"):
        _write_json(case_dir / filename, {})

    audit = build_data_script_quality_summary({"run_id": "unit_ok", "cases": [{"case_id": "case_ok"}]}, artifact_root=tmp_path)

    assert audit["status"] == "pass"
    assert audit["cases"][0]["issues"] == []


def test_data_script_quality_audit_passes_new_repaired_full_chain_artifact_shape(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_repaired_artifact"
    plan = {
        "schema_version": "finsight_memo_logic_plan_v0_1",
        "validation": {"status": "pass"},
        "section_order": ["core_judgment", "product_and_production"],
        "required_item_answer_plan": [
            {
                "question_item_id": "asml_orders_or_backlog",
                "answer_strategy": "Use official issuer filing presence plus parser-boundary diagnosis.",
                "claim_ids": ["lead_targeted_repair_claim:issuer_official:asml"],
            },
            {
                "question_item_id": "nvda_gpu_customer_deployment",
                "answer_strategy": "Use product architecture and customer-deployment evidence as bounded product adoption signal.",
                "claim_ids": ["claim_nvda_deployment"],
            },
        ],
        "product_reasoning_frame": {
            "roles": ["technical_fact", "deployment_signal", "supply_chain_signal"],
        },
    }
    _write_memo_surface_artifacts(
        case_dir,
        {
            "rendered_answer": (
                "ASML 官方源已定位，订单和积压 exact 表格仍需要 source-specific parser 才能提权。\n\n"
                "NVDA 的产品架构、客户部署和供应链信号能支持有边界的产品采用判断，"
                "但不冒充 SKU revenue。"
            ),
            "memo_logic_plan": plan,
            "memo_answer": {
                "direct_answer": "产品层有可用判断，但 exact KPI 与 bounded product thesis 分开。",
                "memo_logic_plan": plan,
                "memo_writer_diagnostics": {"deterministic_salvage_used": False},
            },
            "verified_judgment_plan": {
                "supported_claims": [
                    {
                        "claim_id": "lead_targeted_repair_claim:issuer_official:asml",
                        "ticker_scope": ["ASML"],
                        "claim": "ASML official issuer source was reached; exact values need filing table parsing.",
                        "parser_diagnosis_complete": True,
                        "parser_diagnosis": {
                            "parser_diagnosis_complete": True,
                            "source_specific_parser_statuses": [
                                "filing_presence_parser_pass_exact_filing_document_parser_not_run"
                            ],
                            "exact_fact_parser_failure_reasons": [
                                "SEC submissions JSON proves issuer filing presence, but linked 6-K/20-F tables were not parsed."
                            ],
                            "next_parser_actions": [
                                "resolve accession links and parse 6-K/20-F filing body tables with period/unit/citation gates"
                            ],
                        },
                    },
                    {
                        "claim_id": "claim_nvda_deployment",
                        "ticker_scope": ["NVDA"],
                        "claim": "NVDA Blackwell customer deployment signals support product adoption context.",
                    },
                ],
                "claim_card_stats": {"supported_claim_count": 2},
            },
            "supervising_analyst_pack": {"status": "pass"},
        },
    )
    _write_json(
        case_dir / "pre_memo_fact_selection.json",
        {
            "summary": {"approved_fact_count": 1},
            "approved_facts": [
                {
                    "fact_id": "nvda_data_center_revenue",
                    "ticker": "NVDA",
                    "value": 115.2,
                    "display_value": "$115.2B",
                    "display_lineage_status": "pass",
                }
            ],
        },
    )
    _write_json(
        case_dir / "multi_agent_summary.json",
        {
            "memo_logic_plan": {
                "status": "pass",
                "required_item_answer_plan_count": 2,
                "required_item_answer_plan_item_ids": [
                    "asml_orders_or_backlog",
                    "nvda_gpu_customer_deployment",
                ],
            }
        },
    )
    _write_json(
        case_dir / "p30_root_cause_quality_audit.json",
        {
            "required_item_matrix": {
                "items": [
                    {"question_item_id": "asml_orders_or_backlog", "status": "covered"},
                    {"question_item_id": "nvda_gpu_customer_deployment", "status": "covered"},
                ]
            },
            "product_reasoning_frame": {"coverage_roles": ["product_spec", "deployment", "supply_chain"]},
        },
    )
    _write_json(
        case_dir / "typed_gap_ledger.json",
        {
            "gaps": [
                {
                    "gap_id": "gap_asml_route_scope",
                    "ticker": "ASML",
                    "reason": "not_in_manifest_for_mcp_route_scope",
                    "repairability": "retrieval_or_refresh",
                }
            ]
        },
    )
    _write_json(case_dir / "source_layer_capability_audit.json", {})

    audit = build_data_script_quality_summary(
        {"run_id": "unit_repaired_artifact", "cases": [{"case_id": "case_repaired_artifact"}]},
        artifact_root=tmp_path,
    )
    case = audit["cases"][0]
    persisted_plan = json.loads((case_dir / "memo_logic_plan.json").read_text(encoding="utf-8"))

    assert persisted_plan["artifact_persistence"]["source"] == "state.memo_logic_plan"
    assert audit["status"] == "pass"
    assert case["issues"] == []
    assert case["metrics"]["memo_answer_embedded_memo_logic_plan_present"] is True
    assert case["metrics"]["summary_memo_logic_plan_present"] is True
    assert case["metrics"]["source_route_scope_false_gap_count"] == 0


def test_data_script_quality_audit_ignores_route_scope_notes_for_covered_focus_and_nonfocus_peer(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case_ai_route_notes"
    _write_json(
        case_dir / "pre_memo_fact_selection.json",
        {
            "summary": {"approved_fact_count": 2},
            "approved_facts": [
                {"ticker": "DELL", "source_family": "company_authored_unaudited_sec_filing", "evidence_ref": "dell_8k_ref"},
                {"ticker": "NVDA", "source_family": "primary_sec_filing", "evidence_ref": "nvda_10k_ref"},
            ],
        },
    )
    _write_json(
        case_dir / "claim_cards.json",
        {
            "supported_claims": [
                {
                    "claim_id": "c_dell",
                    "ticker_scope": ["DELL"],
                    "source_families": ["company_authored_unaudited_sec_filing"],
                    "evidence_refs": ["dell_8k_ref"],
                },
                {
                    "claim_id": "c_nvda",
                    "ticker_scope": ["NVDA"],
                    "source_families": ["primary_sec_filing"],
                    "evidence_refs": ["nvda_10k_ref"],
                },
            ]
        },
    )
    _write_json(case_dir / "verified_judgment_plan.json", {"supported_claims": []})
    _write_json(case_dir / "memo_logic_plan.json", {"validation": {"status": "pass"}})
    _write_json(
        case_dir / "memo_answer.json",
        {
            "memo_writer_diagnostics": {"deterministic_salvage_used": False},
            "memo_logic_plan": {"validation": {"status": "pass"}},
        },
    )
    (case_dir / "qwen").mkdir(parents=True)
    (case_dir / "qwen" / "rendered_answer.md").write_text(
        "DELL / NVDA 证据已覆盖，ANET 只是 peer scope。\n",
        encoding="utf-8",
    )
    _write_json(
        case_dir / "p30_root_cause_quality_audit.json",
        {
            "required_item_matrix": {"items": []},
            "product_reasoning_frame": {"coverage_roles": ["product_spec"]},
            "focus_ticker_coverage_matrix": [
                {"ticker": "DELL", "approved_fact_count": 1, "supported_claim_count": 1},
                {"ticker": "NVDA", "approved_fact_count": 1, "supported_claim_count": 1},
            ],
        },
    )
    _write_json(
        case_dir / "typed_gap_ledger.json",
        {
            "gaps": [
                {"ticker": "DELL", "reason": "not_in_manifest_for_mcp_route_scope"},
                {"ticker": "NVDA", "reason": "not_in_manifest_for_mcp_route_scope"},
                {"ticker": "ANET", "reason": "not_in_manifest_for_mcp_route_scope"},
            ]
        },
    )
    for filename in ("source_layer_capability_audit.json", "supervising_analyst_pack.json"):
        _write_json(case_dir / filename, {})

    audit = build_data_script_quality_summary(
        {"run_id": "unit_route_notes", "cases": [{"case_id": "case_ai_route_notes"}]},
        artifact_root=tmp_path,
    )
    case = audit["cases"][0]

    assert audit["status"] == "pass"
    assert "source_route_scope_false_gap_present" not in case["issues"]
    assert case["metrics"]["source_route_scope_false_gap_count"] == 0


def test_multi_agent_artifact_refs_include_memo_logic_plan(tmp_path: Path) -> None:
    state = _with_multi_agent_artifact_refs({"output_dir": str(tmp_path), "artifact_refs": {}})

    assert state["artifact_refs"]["memo_logic_plan"] == str((tmp_path / "memo_logic_plan.json").resolve())


def test_memo_writer_embeds_memo_logic_plan_for_downstream_trace() -> None:
    plan = {
        "schema_version": "finsight_memo_logic_plan_v0_1",
        "validation": {"status": "pass"},
        "section_order": ["product_and_production"],
    }

    state = _node_multi_agent_memo_writer(
        {
            "memo_logic_plan": plan,
            "verified_judgment_plan": {"supported_claims": []},
            "specialist_verification": {"status": "pass"},
        },
        memo_writer=lambda _state: {"memo_answer": {"direct_answer": "产品证据应进入写作。"}},
    )

    assert state["memo_answer"]["memo_logic_plan"]["validation"]["status"] == "pass"


def test_write_memo_surface_artifacts_recovers_memo_logic_plan_from_memo_answer(tmp_path: Path) -> None:
    plan = {
        "schema_version": "finsight_memo_logic_plan_v0_1",
        "validation": {"status": "pass"},
        "section_order": ["fundamentals", "product_and_production"],
    }

    _write_memo_surface_artifacts(
        tmp_path,
        {
            "memo_answer": {
                "direct_answer": "产品证据应进入写作。",
                "memo_logic_plan": plan,
            }
        },
    )

    persisted = json.loads((tmp_path / "memo_logic_plan.json").read_text(encoding="utf-8"))
    assert persisted["validation"]["status"] == "pass"
    assert persisted["artifact_persistence"]["source"] == "memo_answer.memo_logic_plan"


def test_data_script_quality_audit_distinguishes_missing_plan_persistence_from_generation_loss(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_plan_in_summary_only"
    _write_json(case_dir / "memo_answer.json", {"memo_writer_diagnostics": {"deterministic_salvage_used": False}})
    _write_json(
        case_dir / "multi_agent_summary.json",
        {"memo_logic_plan": {"status": "pass", "required_item_answer_plan_count": 1}},
    )
    (case_dir / "qwen").mkdir(parents=True)
    (case_dir / "qwen" / "rendered_answer.md").write_text("已有答案。\n", encoding="utf-8")
    for filename in (
        "pre_memo_fact_selection.json",
        "claim_cards.json",
        "verified_judgment_plan.json",
        "p30_root_cause_quality_audit.json",
        "typed_gap_ledger.json",
        "source_layer_capability_audit.json",
        "supervising_analyst_pack.json",
    ):
        _write_json(case_dir / filename, {})

    audit = build_data_script_quality_summary(
        {"run_id": "unit_summary_plan", "cases": [{"case_id": "case_plan_in_summary_only"}]},
        artifact_root=tmp_path,
    )
    case = audit["cases"][0]

    assert "memo_logic_plan_artifact_missing" in case["issues"]
    assert "memo_logic_plan_standalone_artifact_persistence" in case["root_cause_candidates"]
    assert case["metrics"]["summary_memo_logic_plan_present"] is True


def test_data_script_quality_audit_does_not_block_resolved_source_route_gap_with_parser_diagnosis(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case_asml_route_diagnosed"
    _write_json(case_dir / "pre_memo_fact_selection.json", {"summary": {"approved_fact_count": 0}, "approved_facts": []})
    _write_json(
        case_dir / "claim_cards.json",
        {
            "supported_claims": [
                {
                    "claim_id": "lead_targeted_repair_claim:issuer_official:asml",
                    "ticker_scope": ["ASML"],
                    "claim": "ASML official issuer source was reached; exact values need filing table parsing.",
                    "parser_diagnosis_complete": True,
                    "parser_diagnosis": {
                        "parser_diagnosis_complete": True,
                        "source_specific_parser_statuses": [
                            "filing_presence_parser_pass_exact_filing_document_parser_not_run"
                        ],
                        "exact_fact_parser_failure_reasons": [
                            "SEC submissions JSON proves issuer filing presence, but linked 6-K/20-F tables were not parsed."
                        ],
                        "next_parser_actions": [
                            "resolve accession links and parse 6-K/20-F filing body tables with period/unit/citation gates"
                        ],
                    },
                }
            ]
        },
    )
    _write_json(case_dir / "verified_judgment_plan.json", {"supported_claims": []})
    _write_json(case_dir / "memo_logic_plan.json", {"validation": {"status": "pass"}})
    _write_json(
        case_dir / "memo_answer.json",
        {
            "memo_writer_diagnostics": {"deterministic_salvage_used": False},
            "memo_logic_plan": {"validation": {"status": "pass"}},
        },
    )
    (case_dir / "qwen").mkdir(parents=True)
    (case_dir / "qwen" / "rendered_answer.md").write_text(
        "ASML 官方源已定位，订单和积压 exact 表格仍需要 source-specific parser 才能提权。\n",
        encoding="utf-8",
    )
    _write_json(
        case_dir / "p30_root_cause_quality_audit.json",
        {
            "required_item_matrix": {"items": [{"question_item_id": "asml_orders_or_backlog", "status": "covered"}]},
            "product_reasoning_frame": {"coverage_roles": ["official_product_surface"]},
        },
    )
    _write_json(
        case_dir / "typed_gap_ledger.json",
        {
            "gaps": [
                {
                    "gap_id": "gap_asml_route_scope",
                    "ticker": "ASML",
                    "reason": "not_in_manifest_for_mcp_route_scope",
                    "repairability": "retrieval_or_refresh",
                }
            ]
        },
    )
    for filename in ("source_layer_capability_audit.json", "supervising_analyst_pack.json"):
        _write_json(case_dir / filename, {})

    audit = build_data_script_quality_summary(
        {"run_id": "unit_asml_diagnosed", "cases": [{"case_id": "case_asml_route_diagnosed"}]},
        artifact_root=tmp_path,
    )
    case = audit["cases"][0]

    assert audit["status"] == "pass"
    assert "source_route_scope_false_gap_present" not in case["issues"]
    assert case["metrics"]["source_route_scope_false_gap_count"] == 0
