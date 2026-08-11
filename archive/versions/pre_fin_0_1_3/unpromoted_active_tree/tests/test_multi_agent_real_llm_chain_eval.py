from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_real_llm_chain_cases_v0_1.jsonl"
FULL_CHAIN_MULTITURN_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_full_chain_multiturn_cases_v0_1.jsonl"
VNEXT_G11_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_g11_cases_v0_1.jsonl"
VNEXT_RUN_AUDIT_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_run_audit_full_chain_cases_v0_1.jsonl"
)
VNEXT_DIAGNOSTIC_FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_diagnostic_probe_cases_v0_1.jsonl"
)
VNEXT_50_CASE_CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "eval_multi_agent_real_llm_chain.py"


def test_multi_agent_real_llm_chain_fixture_schema() -> None:
    rows = _read_jsonl(FIXTURE_PATH)

    assert len(rows) == 10
    assert {row["category"] for row in rows} == {"detailed_probe", "single_turn", "multi_turn", "sector_depth"}
    assert any(row.get("detailed_probe") for row in rows)
    assert any(row.get("conversation_id") for row in rows)
    assert all(row["case_id"].startswith("ma_real_") for row in rows)
    assert any(row["expected_execution_mode"] == "deep_research" for row in rows)
    assert sum(1 for row in rows if row.get("require_real_retrieval_pass")) == 4
    sector_cases = [row for row in rows if row["category"] == "sector_depth"]
    assert all(row.get("expected_relationship_pack_ids") for row in sector_cases)
    assert all(row.get("require_rendered_memo_claims") for row in sector_cases)
    assert all(row.get("require_rendered_evidence_refs") for row in sector_cases)


def test_dimension_number_sequence_stops_before_required_question_section() -> None:
    module = _load_script_module()
    rendered = "\n\n".join(
        [
            "核心判断:\n当前判断集中在财务、产品和供应链传导。",
            "分维度分析:\n1. 基本面与财务质量：AMAT 毛利率支撑盈利质量判断。\n2. 产品与产线：KLAC 产品收入支撑过程控制业务规模判断。\n3. 投融资与资本开支：发行人自身 capex 不能等同客户订单。",
            "关键问题回应:\n1. 出口限制与中国暴露风险：只能形成风险折价方向判断。\n2. 订单/积压：需要 parsed bookings/backlog 才能提权。",
            "证据索引:\n- [C1] AMAT / gross margin",
        ]
    )

    assert module._dimension_number_sequence_ok(rendered, "zh-CN") is True


def test_fin_agent_full_chain_multiturn_fixture_schema() -> None:
    rows = _read_jsonl(FULL_CHAIN_MULTITURN_FIXTURE_PATH)

    assert 10 <= len(rows) <= 20
    assert {row["category"] for row in rows} >= {"exact_lookup", "focused_answer", "standard_memo", "sector_depth", "multi_turn"}
    assert any(row.get("response_language") == "en-US" for row in rows)
    assert sum(1 for row in rows if row.get("conversation_id")) >= 4
    assert sum(1 for row in rows if row.get("require_real_retrieval_pass")) >= 5
    assert all(row["case_id"].startswith("fin_full_") for row in rows)
    assert all(row.get("response_language") for row in rows)
    sector_cases = [row for row in rows if row["category"] == "sector_depth"]
    assert all(row.get("expected_relationship_pack_ids") for row in sector_cases)
    assert all(row.get("require_rendered_memo_claims") for row in sector_cases)
    assert all(row.get("require_rendered_evidence_refs") for row in sector_cases)


def test_fin_agent_vnext_g11_fixture_schema() -> None:
    rows = _read_jsonl(VNEXT_G11_FIXTURE_PATH)

    assert 10 <= len(rows) <= 20
    assert {row["category"] for row in rows} >= {"exact_lookup", "focused_answer", "standard_memo", "sector_depth", "multi_turn"}
    assert all(row.get("require_vnext_contract") for row in rows)
    assert all(row.get("require_milvus_runtime_contract") for row in rows)
    assert all(row["case_id"].startswith("fin_g11_") for row in rows)
    assert all(row.get("response_language") for row in rows)
    assert sum(1 for row in rows if row.get("conversation_id")) >= 2
    assert {"semiconductor", "consumer_electronics", "saas_cloud", "banking", "energy", "healthcare_pharma", "automotive", "retail_cpg"} <= {
        row.get("industry_schema") for row in rows
    }
    assert any("product_technology_analyst" in row.get("expected_specialist_agents", []) for row in rows)
    assert any("milvus_semantic" in row.get("source_tiers", []) for row in rows)


def test_fin_agent_vnext_run_audit_full_chain_fixture_schema() -> None:
    rows = _read_jsonl(VNEXT_RUN_AUDIT_FIXTURE_PATH)

    assert len(rows) == 2
    assert all(row["case_id"].startswith("fin_run_audit_") for row in rows)
    assert {row["category"] for row in rows} == {"sector_depth", "standard_memo"}
    assert all(row.get("require_run_audit_store") for row in rows)
    assert all(row.get("require_dimension_memo_surface") for row in rows)
    assert all(row.get("require_analyst_depth_gate") for row in rows)
    assert all(row.get("require_real_retrieval_pass") for row in rows)
    assert all(row.get("require_real_evidence_quality_pass") for row in rows)
    assert all(row.get("required_dimension_ids") for row in rows)
    assert all(
        {
            "run",
            "node_execution",
            "artifact_ref",
            "evidence_row",
            "claim_card",
            "gap",
            "gate_result",
            "model_call",
        }
        <= set(row.get("required_run_audit_tables", []))
        for row in rows
    )


def test_fin_agent_vnext_diagnostic_probe_fixture_schema() -> None:
    rows = _read_jsonl(VNEXT_DIAGNOSTIC_FIXTURE_PATH)

    assert len(rows) == 2
    assert all(row["case_id"].startswith("fin_diag_") for row in rows)
    assert {row["category"] for row in rows} == {"diagnostic_probe"}
    assert all(row.get("require_no_internal_synthesis_dimension") for row in rows)
    assert all(row.get("require_numeric_fact_sanity") for row in rows)
    assert all(row.get("require_product_or_gap_evidence") for row in rows)
    assert any(row.get("require_capital_financing_signal") for row in rows)
    assert any("product_kpi:product_revenue" in row.get("required_approved_metric_ids", []) for row in rows)


def test_multi_agent_real_llm_chain_dry_run_resolves_catalog_subset(tmp_path: Path) -> None:
    module = _load_script_module()
    summary_path = tmp_path / "summary.json"
    expanded_path = tmp_path / "expanded_cases.jsonl"

    exit_code = module.main(
        [
            "--case-catalog-path",
            str(VNEXT_50_CASE_CATALOG_PATH),
            "--case-subset",
            "r12_successor_12",
            "--dry-run-cases",
            "--dump-expanded-cases-path",
            str(expanded_path),
            "--summary-output-path",
            str(summary_path),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "catalog_dry_run_fixture",
        ]
    )

    assert exit_code == 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expanded = _read_jsonl(expanded_path)
    assert summary["schema_version"] == "sec_agent_multi_agent_real_llm_chain_case_resolution_v0.1"
    assert summary["case_count"] == 12
    assert summary["case_catalog"]["case_subset"] == "r12_successor_12"
    assert summary["case_families"] == {"L3_deep_research": 12}
    assert len(expanded) == 12
    assert all(row["require_vnext_contract"] for row in expanded)
    assert all(row["expected_execution_mode"] == "deep_research" for row in expanded)
    assert all(row["require_investment_memo_quality"] for row in expanded)
    ai_case = next(row for row in expanded if row["case_id"] == "fin_deep_ai_infra_nvda_dell_capex_023")
    semicap_case = next(row for row in expanded if row["case_id"] == "fin_deep_semicap_asml_amat_lrcx_klac_cycle_025")
    for row in (ai_case, semicap_case):
        assert "market_valuation_analyst" in row["expected_specialist_agents"]
        assert "market_valuation_analyst" not in row["expected_paid_specialist_agents"]
        assert set(row["expected_paid_specialist_agents"]) < set(row["expected_specialist_agents"])
        assert row["expected_paid_specialist_priorities"]["risk_counterevidence_analyst"] == "supporting"
        assert row["expected_paid_specialist_priorities"]["fundamental_analyst"] == "primary"


def test_real_llm_chain_token_budget_preflight_blocks_expensive_paid_run(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args(
        [
            "--token-budget-total",
            "50000",
            "--token-budget-per-case",
            "50000",
            "--max-paid-calls",
            "3",
        ]
    )
    cases = [
        {
            "case_id": "deep_cost_case_a",
            "expected_execution_mode": "deep_research",
            "required_agents": [
                "research_lead",
                "universe_relationship",
                "fundamental_analyst",
                "product_technology_analyst",
                "industry_supply_chain_analyst",
                "memo_writer",
                "verifier",
            ],
        },
        {
            "case_id": "deep_cost_case_b",
            "expected_execution_mode": "deep_research",
            "required_agents": [
                "research_lead",
                "universe_relationship",
                "fundamental_analyst",
                "industry_supply_chain_analyst",
                "memo_writer",
                "verifier",
            ],
        },
    ]

    plan = module._token_budget_plan(args=args, cases=cases, run_id="unit_budget", output_dir=tmp_path)

    assert plan["paid_backend"] is True
    assert plan["allowed"] is False
    assert plan["status"] == "blocked_preflight_token_budget"
    assert {row["type"] for row in plan["violations"]} >= {
        "run_token_budget_exceeded",
        "paid_call_budget_exceeded",
        "case_token_budget_exceeded",
    }
    assert plan["scheduler_advice"]["status"] == "case_budget_repair_required"
    assert plan["scheduler_advice"]["blocked_case_ids"] == ["deep_cost_case_a", "deep_cost_case_b"]


def test_real_llm_chain_preflight_blocks_paid_real_retrieval_case_without_real_evidence_operators(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args([])
    case = {
        "case_id": "requires_real_retrieval",
        "expected_execution_mode": "deep_research",
        "required_agents": ["research_lead", "memo_writer", "verifier"],
        "require_real_retrieval_pass": True,
        "require_real_evidence_quality_pass": True,
    }

    plan = module._token_budget_plan(args=args, cases=[case], run_id="unit_real_evidence_mode", output_dir=tmp_path)

    assert plan["allowed"] is False
    assert plan["status"] == "blocked_preflight_evidence_operator_mode"
    assert plan["real_evidence_operators"] is False
    assert plan["evidence_operator_mode_policy"] == "paid_real_retrieval_cases_require_real_evidence_operators_v0_1"
    assert [row["type"] for row in plan["violations"]] == ["real_evidence_operators_required"]
    assert plan["violations"][0]["case_id"] == "requires_real_retrieval"
    assert "Pass --real-evidence-operators" in plan["required_action"]


def test_real_llm_chain_preflight_allows_paid_real_retrieval_case_with_real_evidence_operators(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args(["--real-evidence-operators"])
    case = {
        "case_id": "requires_real_retrieval",
        "expected_execution_mode": "focused_answer",
        "required_agents": ["research_lead", "memo_writer", "verifier"],
        "require_real_retrieval_pass": True,
        "require_real_evidence_quality_pass": True,
    }

    plan = module._token_budget_plan(args=args, cases=[case], run_id="unit_real_evidence_mode", output_dir=tmp_path)

    assert plan["allowed"] is True
    assert plan["status"] == "allowed"
    assert plan["real_evidence_operators"] is True
    assert not [row for row in plan["violations"] if row["type"] == "real_evidence_operators_required"]


def test_real_llm_chain_token_budget_uses_expected_paid_specialists(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args([])
    case = {
        "case_id": "paid_specialist_case",
        "expected_execution_mode": "deep_research",
        "required_agents": [
            "research_lead",
            "universe_relationship",
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
            "memo_writer",
            "verifier",
        ],
        "expected_specialist_agents": [
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        ],
        "expected_paid_specialist_agents": [
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "risk_counterevidence_analyst",
        ],
        "expected_paid_specialist_priorities": {
            "fundamental_analyst": "primary",
            "product_technology_analyst": "primary",
            "industry_supply_chain_analyst": "primary",
            "risk_counterevidence_analyst": "supporting",
        },
    }

    plan = module._token_budget_plan(args=args, cases=[case], run_id="paid_specialist_unit", output_dir=tmp_path)
    case_plan = plan["cases"][0]

    assert case_plan["quality_expected_specialist_agents"] == case["expected_specialist_agents"]
    assert case_plan["expected_specialist_agents"] == case["expected_paid_specialist_agents"]
    assert case_plan["pruned_from_quality_expected_specialist_agents"] == ["market_valuation_analyst"]
    assert "market_valuation_analyst" not in {row["node"] for row in case_plan["nodes"]}
    node_by_id = {row["node"]: row for row in case_plan["nodes"]}
    assert node_by_id["risk_counterevidence_analyst"]["priority"] == "supporting"
    assert node_by_id["risk_counterevidence_analyst"]["estimated_input_tokens"] < 11000
    assert case_plan["estimate_policy"] == "role_projected_compact_prompt_budget_v0_3"
    assert case_plan["estimate_adjustments"]["memo_writer_input"] == "writer_thesis_skeleton_first_compact_verified_inputs"
    assert node_by_id["memo_writer"]["estimated_input_tokens"] == 10500
    assert int(case_plan["estimated_total_tokens"]) < 70000


def test_real_llm_chain_runtime_required_agents_use_expected_paid_specialists() -> None:
    module = _load_script_module()
    case = {
        "required_agents": [
            "research_lead",
            "universe_relationship",
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
            "memo_writer",
            "verifier",
            "renderer",
        ],
        "expected_specialist_agents": [
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        ],
        "expected_paid_specialist_agents": [
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "risk_counterevidence_analyst",
        ],
    }

    required = module._runtime_required_agents(case)

    assert "market_valuation_analyst" not in required
    assert {"fundamental_analyst", "product_technology_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"} <= required
    assert {"research_lead", "universe_relationship", "memo_writer", "verifier", "renderer"} <= required


def test_real_llm_chain_initial_state_exports_cost_aware_paid_specialist_whitelist(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args([])
    case = {
        "case_id": "ai_infra_cost_whitelist",
        "prompt": "分析 NVDA/DELL AI server demand read-through，不要求估值或股价反应。",
        "expected_execution_mode": "deep_research",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT"],
        "source_tiers": ["primary_sec_filing", "relationship_graph"],
        "metric_families": ["revenue", "gross_margin", "capex"],
        "required_dimension_ids": ["fundamentals", "industry_supply_chain", "risk_and_counterevidence"],
        "expected_specialist_agents": [
            "fundamental_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        ],
    }

    state = module._initial_state(
        case,
        tmp_path,
        run_id="unit_paid_specialist_whitelist",
        previous_turn_summary=None,
        args=args,
    )

    context = state["multi_agent_context"]
    assert context["expected_specialist_agents"] == case["expected_specialist_agents"]
    assert "market_valuation_analyst" not in context["expected_paid_specialist_agents"]
    assert {
        "fundamental_analyst",
        "industry_supply_chain_analyst",
        "risk_counterevidence_analyst",
    } <= set(context["expected_paid_specialist_agents"])


def test_real_llm_chain_cost_aware_specialists_keep_capital_market_feedback_role(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args([])
    case = {
        "case_id": "p33_capital_market_feedback_role",
        "prompt": "分析 NVDA/DELL AI server 与资本市场预期、price-in 和资金面反馈。",
        "expected_execution_mode": "deep_research",
        "source_tiers": ["primary_sec_filing", "market_snapshot", "relationship_graph"],
        "metric_families": ["revenue", "gross_margin", "capital_market_feedback"],
        "required_dimensions": ["fundamentals", "capital_market_feedback"],
        "expected_specialist_agents": [
            "fundamental_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        ],
    }

    plan = module._token_budget_plan(args=args, cases=[case], run_id="unit_capital_feedback", output_dir=tmp_path)
    case_plan = plan["cases"][0]

    assert "market_valuation_analyst" in case_plan["cost_aware_specialist_agents"]
    assert "market_valuation_analyst" not in case_plan["prunable_specialist_agents"]
    assert "market_valuation_analyst" in {row["node"] for row in case_plan["nodes"]}


def test_real_llm_chain_counter_thesis_requirement_does_not_force_paid_risk_specialist(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args([])
    case = {
        "case_id": "p33_counter_thesis_without_risk_specialist",
        "prompt": "输出反证和 what-would-change，作为常规报告结构要求。",
        "expected_execution_mode": "deep_research",
        "source_tiers": ["primary_sec_filing", "relationship_graph"],
        "metric_families": ["revenue", "gross_margin"],
        "required_dimensions": ["fundamentals", "counter_thesis_and_what_would_change"],
        "expected_specialist_agents": [
            "fundamental_analyst",
            "risk_counterevidence_analyst",
        ],
    }

    plan = module._token_budget_plan(args=args, cases=[case], run_id="unit_counter_thesis", output_dir=tmp_path)
    case_plan = plan["cases"][0]

    assert "risk_counterevidence_analyst" not in case_plan["cost_aware_specialist_agents"]
    assert "risk_counterevidence_analyst" in case_plan["prunable_specialist_agents"]
    assert "risk_counterevidence_analyst" not in {row["node"] for row in case_plan["nodes"]}


def test_real_llm_chain_case_normalization_aligns_score_with_paid_specialist_whitelist() -> None:
    module = _load_script_module()
    case = {
        "case_id": "ai_infra_cost_whitelist",
        "prompt": "分析 NVDA/DELL AI server demand read-through，不要求估值或股价反应。",
        "expected_execution_mode": "deep_research",
        "source_tiers": ["primary_sec_filing", "relationship_graph"],
        "metric_families": ["revenue", "gross_margin", "capex"],
        "required_dimension_ids": ["fundamentals", "industry_supply_chain", "risk_and_counterevidence"],
        "expected_specialist_agents": [
            "fundamental_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        ],
    }

    normalized = module._case_with_runtime_paid_specialists(case)

    assert normalized["expected_specialist_agents"] == case["expected_specialist_agents"]
    assert "market_valuation_analyst" not in normalized["expected_paid_specialist_agents"]
    required = module._runtime_required_agents(
        {
            **normalized,
            "required_agents": [
                "research_lead",
                "fundamental_analyst",
                "industry_supply_chain_analyst",
                "market_valuation_analyst",
                "risk_counterevidence_analyst",
                "memo_writer",
                "verifier",
            ],
        }
    )
    assert "market_valuation_analyst" not in required


def test_real_llm_chain_token_budget_scheduler_splits_batch_before_paid_run(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args([])
    base_case = {
        "expected_execution_mode": "deep_research",
        "required_agents": [
            "research_lead",
            "universe_relationship",
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "risk_counterevidence_analyst",
            "memo_writer",
            "verifier",
        ],
        "expected_paid_specialist_agents": [
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "risk_counterevidence_analyst",
        ],
        "expected_paid_specialist_priorities": {
            "fundamental_analyst": "primary",
            "product_technology_analyst": "primary",
            "industry_supply_chain_analyst": "primary",
            "risk_counterevidence_analyst": "supporting",
        },
    }
    cases = [
        {**base_case, "case_id": "ai_infra_case"},
        {**base_case, "case_id": "semicap_case"},
    ]

    plan = module._token_budget_plan(args=args, cases=cases, run_id="batch_scheduler_unit", output_dir=tmp_path)

    assert plan["allowed"] is False
    assert plan["scheduler_advice"]["status"] == "split_required"
    assert plan["scheduler_advice"]["blocked_case_ids"] == []
    assert plan["scheduler_advice"]["recommended_batch_count"] == 2
    assert [batch["case_ids"] for batch in plan["scheduler_advice"]["batches"]] == [["ai_infra_case"], ["semicap_case"]]
    assert plan["required_action"].startswith("Run the recommended paid batches separately")


def test_real_llm_chain_token_budget_preflight_only_writes_plan_without_graph(tmp_path: Path) -> None:
    module = _load_script_module()
    plan_path = tmp_path / "budget.json"

    exit_code = module.main(
        [
            "--case-catalog-path",
            str(VNEXT_50_CASE_CATALOG_PATH),
            "--case-id",
            "fin_deep_ai_infra_nvda_dell_capex_023",
            "--token-budget-preflight-only",
            "--token-budget-plan-path",
            str(plan_path),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--run-id",
            "preflight_only_unit",
        ]
    )

    assert exit_code == 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    economy_plan = json.loads((tmp_path / "outputs" / "preflight_only_unit" / "agent_information_economy_preflight.json").read_text(encoding="utf-8"))
    assert plan["schema_version"] == "sec_agent_paid_llm_token_budget_plan_v0.1"
    assert plan["cases"][0]["case_id"] == "fin_deep_ai_infra_nvda_dell_capex_023"
    assert "estimated_total_tokens" in plan
    assert plan["cases"][0]["estimate_policy"] == "role_projected_compact_prompt_budget_v0_3"
    assert int(plan["cases"][0]["estimated_total_tokens"]) < 119600
    assert economy_plan["schema_version"] == "finsight_agent_information_economy_ledger_v0_1"
    assert economy_plan["preflight_only"] is True


def test_real_llm_chain_provider_preflight_writes_fail_fast_artifact(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args(
        [
            "--llm-backend",
            "openai_compat",
            "--base-url",
            "http://43.135.174.27:8080",
            "--chat-completions-path",
            "/v1/chat/completions",
            "--model",
            "gpt-5.5",
            "--api-key-env",
            "GPT_COMPAT_API_KEY",
        ]
    )

    def fake_chat_completion(**kwargs: object) -> dict[str, object]:
        return {
            "status": "provider_error",
            "call_id": "unit_call",
            "provider": kwargs.get("llm_backend"),
            "model": kwargs.get("model"),
            "url": "http://43.135.174.27:8080/v1/chat/completions",
            "proxy_mode": "direct",
            "latency_ms": 12,
            "failure_reason": "ConnectionResetError: simulated",
            "transport_attempt_count": 1,
            "transport_failures": [],
        }

    monkeypatch.setenv("GPT_COMPAT_API_KEY", "unit-key")
    monkeypatch.setattr(module, "chat_completion", fake_chat_completion)

    preflight = module._write_provider_preflight(args=args, run_id="unit_provider", output_dir=tmp_path)
    saved = json.loads((tmp_path / "provider_preflight.json").read_text(encoding="utf-8"))

    assert preflight["status"] == "fail"
    assert saved["status"] == "fail"
    assert saved["api_key_present"] is True
    assert saved["api_key_saved"] is False
    assert saved["proxy_mode"] == "direct"
    assert "simulated" in saved["failure_reason"]


def test_real_llm_chain_auto_proxy_mode_uses_direct_for_http_ip_endpoint() -> None:
    module = _load_script_module()
    args = module.parse_args(
        [
            "--llm-backend",
            "openai_compat",
            "--base-url",
            "http://43.135.174.27:8080",
            "--llm-gateway-proxy-mode",
            "auto",
        ]
    )

    assert module._resolved_llm_gateway_proxy_mode(args) == "direct"


def test_real_llm_chain_graph_env_uses_deterministic_routes_for_unpaid_backend() -> None:
    module = _load_script_module()
    args = module.parse_args(["--llm-backend", "mock"])

    env = module._graph_env(args)

    assert env["SEC_AGENT_MULTI_AGENT_LEAD_ROUTER"] == "deterministic"
    assert env["SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER"] == "mock"
    assert env["SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER"] == "deterministic"
    assert env["SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"] == "deterministic"


def test_real_llm_chain_graph_env_uses_llm_routes_for_paid_backend_with_program_owned_relationships() -> None:
    module = _load_script_module()
    args = module.parse_args(["--llm-backend", "deepseek"])

    env = module._graph_env(args)

    assert env["SEC_AGENT_MULTI_AGENT_LEAD_ROUTER"] == "llm"
    assert env["SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER"] == "llm"
    assert env["SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER"] == "deterministic"
    assert env["SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"] == "llm"


def test_real_llm_chain_graph_env_allows_explicit_universe_llm_overlay_for_paid_backend() -> None:
    module = _load_script_module()
    args = module.parse_args(["--llm-backend", "deepseek", "--universe-llm-overlay"])

    env = module._graph_env(args)

    assert env["SEC_AGENT_MULTI_AGENT_LEAD_ROUTER"] == "llm"
    assert env["SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER"] == "llm"
    assert env["SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER"] == "llm"
    assert env["SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"] == "llm"


def test_real_llm_chain_token_budget_does_not_charge_universe_relationship_without_llm_requirement() -> None:
    module = _load_script_module()
    args = module.parse_args(["--llm-backend", "deepseek"])
    case = {
        "case_id": "program_owned_relationships",
        "expected_execution_mode": "deep_research",
        "required_agents": ["research_lead", "universe_relationship", "memo_writer", "verifier"],
    }

    estimate = module._estimate_case_token_budget(case, args=args)

    assert "universe_relationship" not in {row["node"] for row in estimate["nodes"]}


def test_real_llm_chain_token_budget_ignores_legacy_universe_llm_requirement_without_overlay() -> None:
    module = _load_script_module()
    args = module.parse_args(["--llm-backend", "deepseek"])
    case = {
        "case_id": "legacy_relationship_requirement",
        "expected_execution_mode": "deep_research",
        "required_agents": ["research_lead", "universe_relationship", "memo_writer", "verifier"],
        "require_universe_llm_pass": True,
    }

    estimate = module._estimate_case_token_budget(case, args=args)

    assert "universe_relationship" not in {row["node"] for row in estimate["nodes"]}


def test_real_llm_chain_token_budget_charges_universe_relationship_when_overlay_required() -> None:
    module = _load_script_module()
    args = module.parse_args(["--llm-backend", "deepseek", "--universe-llm-overlay"])
    case = {
        "case_id": "model_explained_relationships",
        "expected_execution_mode": "deep_research",
        "required_agents": ["research_lead", "universe_relationship", "memo_writer", "verifier"],
        "require_universe_llm_pass": True,
    }

    estimate = module._estimate_case_token_budget(case, args=args)

    assert "universe_relationship" in {row["node"] for row in estimate["nodes"]}


def test_real_llm_chain_universe_checks_accept_program_owned_relationship_completion_without_llm_call() -> None:
    module = _load_script_module()
    checks = module._universe_checks(
        {
            "case_id": "program_owned_relationships",
            "required_agents": ["universe_relationship"],
        },
        result={"agent_activation_plan": {"activate_agents": ["universe_relationship"]}},
        route={},
        lookup={
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "DELL",
                    "claim_scope": "scope_or_hypothesis_only",
                }
            ]
        },
        validation={"status": "pass"},
        tool_calls=[{"tool_name": "relationship_graph_lookup", "status": "ok"}],
    )

    assert checks["llm_invoked_when_expected"] is True
    assert checks["llm_calls_ok"] is True
    assert checks["validation_pass_when_expected"] is True
    assert checks["relationship_lookup_called"] is True


def test_real_llm_chain_universe_checks_require_llm_only_for_explicit_overlay() -> None:
    module = _load_script_module()
    checks = module._universe_checks(
        {
            "case_id": "model_explained_relationships",
            "required_agents": ["universe_relationship"],
            "require_universe_llm_pass": True,
            "_universe_llm_overlay_required": True,
        },
        result={"agent_activation_plan": {"activate_agents": ["universe_relationship"]}},
        route={},
        lookup={
            "relationships": [
                {
                    "ticker": "NVDA",
                    "related_ticker": "DELL",
                    "claim_scope": "scope_or_hypothesis_only",
                }
            ]
        },
        validation={"status": "pass"},
        tool_calls=[{"tool_name": "relationship_graph_lookup", "status": "ok"}],
    )

    assert checks["llm_invoked_when_expected"] is False
    assert checks["llm_calls_ok"] is False
    assert checks["validation_pass_when_expected"] is True


def test_agent_audit_projects_input_fingerprints_for_deterministic_routes() -> None:
    module = _load_script_module()
    result = {
        "query_contract": {"focus_tickers": ["NVDA"], "search_scope_tickers": ["NVDA", "DELL"]},
        "agent_activation_plan": {"execution_mode": "deep_research", "focus_tickers": ["NVDA"]},
        "evidence_requirement_plan": {"requirements": [{"requirement_id": "req_gpu", "evidence_refs": ["req_ref"]}]},
        "relationship_graph_observation": {
            "status": "ok",
            "relationships": [{"ticker": "NVDA", "related_ticker": "DELL", "evidence_refs": ["rel_ref"]}],
        },
        "universe_relationship_plan": {"relationships": [{"evidence_refs": ["rel_ref"]}]},
        "memo_logic_plan": {"required_item_answer_plan": [{"item_id": "gpu_supply", "evidence_refs": ["memo_ref"]}]},
        "verified_judgment_plan": {"supported_claims": [{"claim_id": "c1", "evidence_refs": ["claim_ref"]}]},
        "pre_memo_fact_selection": {"approved_facts": [{"evidence_ref": "fact_ref"}]},
        "memo_answer": {"memo_claims": [{"claim_id": "m1", "evidence_refs": ["claim_ref"]}]},
        "claim_evidence_ledger": {"claims": [{"claim_id": "c1", "evidence_refs": ["claim_ref"]}]},
        "specialist_outputs": [
            {"agent_id": "product_technology_analyst", "observations": [{"evidence_refs": ["product_ref"]}]}
        ],
    }

    audit = module._agent_audit(
        result,
        {},
        tool_calls=[],
        specialist_routes=[{"agent_id": "product_technology_analyst", "status": "run"}],
        specialist_quality={},
    )

    assert audit["research_lead"]["input_pack_fingerprint"]["capture_source"] == (
        "deterministic_fallback_from_saved_research_lead_state"
    )
    assert audit["universe_relationship"]["input_pack_fingerprint"]["known_evidence_ref_count"] >= 1
    memo_fp = audit["memo_writer"]["route_result"]["input_pack_fingerprint"]
    verifier_fp = audit["verifier"]["input_projection"]["input_pack_fingerprint"]
    specialist_fp = audit["specialists"]["route_results"][0]["input_pack_fingerprint"]
    assert memo_fp["agent_id"] == "memo_writer"
    assert verifier_fp["agent_id"] == "verifier"
    assert specialist_fp["capture_source"] == "deterministic_fallback_from_saved_specialist_output_proxy"
    assert "raw_prompt" not in memo_fp
    assert "messages" not in memo_fp
    assert "component_summaries" in memo_fp


def test_real_llm_chain_initial_state_forces_catalog_execution_mode(tmp_path: Path) -> None:
    module = _load_script_module()
    from sec_agent.multi_agent_router import route_multi_agent_activation

    args = module.parse_args(
        [
            "--case-catalog-path",
            str(VNEXT_50_CASE_CATALOG_PATH),
            "--case-id",
            "fin_deep_ai_infra_nvda_dell_capex_023",
            "--llm-backend",
            "mock",
        ]
    )
    case = module._load_cases(args)[0]
    state = module._initial_state(
        case,
        tmp_path,
        run_id="unit_catalog_mode",
        previous_turn_summary=None,
        args=args,
    )

    assert state["multi_agent_context"]["execution_mode"] == "deep_research"
    route = route_multi_agent_activation(
        {
            "user_query": state["user_query"],
            "focus_tickers": state["selected_tickers"],
            "search_scope_tickers": state["multi_agent_context"]["search_scope_tickers"],
            "source_inventory": state["project_inventory"],
            "context": {**state["multi_agent_context"], "query_contract": state["query_contract"]},
        }
    )
    assert route["activation_plan"]["execution_mode"] == "deep_research"


def test_query_contract_infers_cloud_buyer_demand_proxy_roles_for_ai_capex_case() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_diag_ai_infra_dell_product_capex_zh",
        "industry_schema": "technology_ai_infrastructure",
        "prompt": (
            "用 AI infrastructure sector-depth pack 诊断 NVDA 与 DELL 的基本面、产品证据、"
            "MSFT/AMZN/GOOGL capex 背景、需求传导和反证风险。"
        ),
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT", "MSFT", "AMZN", "GOOGL"],
        "metric_families": ["revenue", "capex", "product_revenue"],
    }

    contract = module._query_contract(case)

    assert contract["demand_proxy_tickers"] == ["MSFT", "AMZN", "GOOGL"]
    assert contract["ticker_roles"] == {
        "MSFT": "cloud_buyer_demand_proxy",
        "AMZN": "cloud_buyer_demand_proxy",
        "GOOGL": "cloud_buyer_demand_proxy",
    }


def test_query_contract_does_not_infer_infra_suppliers_as_demand_proxy_roles() -> None:
    module = _load_script_module()
    case = {
        "case_id": "ma_real_sector_ai_infra_full_chain_real_retrieval",
        "industry_schema": "technology_ai_infrastructure",
        "prompt": "从 AI infrastructure sector-depth pack 出发，分析 NVDA、DELL、ANET、VRT 的需求传导。",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "ANET", "VRT"],
        "metric_families": ["revenue", "capex"],
    }

    contract = module._query_contract(case)

    assert contract["demand_proxy_tickers"] == []
    assert contract["ticker_roles"] == {}


def test_multi_agent_real_llm_chain_reads_milvus_runtime_config_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    config_path = tmp_path / "milvus_runtime.json"
    config_path.write_text(
        json.dumps(
            {
                "status": "available",
                "location": "local_windows_milvus_lite",
                "db_path": "Z:/demo/milvus_lite.db",
                "collection_name": "demo_collection",
                "vector_count": 10,
                "vector_kinds": ["narrative_chunk"],
                "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FINSIGHT_MILVUS_RUNTIME_CONFIG", str(config_path))
    monkeypatch.delenv("MILVUS_DB_PATH", raising=False)
    monkeypatch.delenv("MILVUS_COLLECTION_NAME", raising=False)
    monkeypatch.delenv("MILVUS_COLLECTION", raising=False)

    context = module._milvus_runtime_context_from_env({})

    assert context["milvus_db_path"] == "Z:/demo/milvus_lite.db"
    assert context["milvus_collection_name"] == "demo_collection"
    assert context["milvus_runtime"]["status"] == "available"
    assert context["milvus_runtime"]["location"] == "local"
    assert context["milvus_runtime"]["fallback_routes"] == ["bm25", "object_bm25", "exact_value_ledger"]


def test_real_llm_chain_initial_state_marks_unavailable_milvus_as_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_script_module()
    monkeypatch.delenv("FINSIGHT_MILVUS_RUNTIME_CONFIG", raising=False)
    monkeypatch.delenv("MILVUS_DB_PATH", raising=False)
    monkeypatch.delenv("MILVUS_COLLECTION_NAME", raising=False)
    monkeypatch.delenv("MILVUS_COLLECTION", raising=False)
    args = module.parse_args([])
    case = {
        "case_id": "milvus_unavailable_inventory_contract",
        "prompt": "Analyze NVDA DELL AI infrastructure evidence.",
        "expected_execution_mode": "deep_research",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "relationship_graph",
            "company_product_evidence_graph",
        ],
        "metric_families": ["revenue", "capex", "customer_deployment"],
        "require_milvus_runtime_contract": True,
    }

    state = module._initial_state(
        case,
        tmp_path,
        run_id="unit_milvus_unavailable_inventory",
        previous_turn_summary=None,
        args=args,
    )

    inventory = state["project_inventory"]
    milvus = inventory["milvus_runtime"]
    availability = inventory["source_family_availability"]["milvus_semantic"]
    assert milvus["available"] is False
    assert milvus["status"] == "unavailable"
    assert availability["available"] is False
    assert availability["status"] == "unavailable"
    assert "milvus_semantic" not in inventory["available_source_families"]
    assert "milvus_semantic" not in inventory["source_families"]


def test_real_llm_chain_resource_policy_serializes_local_cuda_fanout() -> None:
    module = _load_script_module()
    args = module.parse_args(["--bge-device", "cuda", "--context-runner", "in_process"])

    policy = module._evidence_operator_resource_policy(args)

    assert module._resolved_evidence_operator_fanout_workers(args) == 1
    assert policy["policy_name"] == "local_cuda_serial_bge_queue"
    assert policy["evidence_operator_fanout_workers"] == 1


def test_real_llm_chain_resource_policy_queues_auto_subprocess_bge_fanout() -> None:
    module = _load_script_module()
    args = module.parse_args(["--bge-device", "auto", "--context-runner", "subprocess"])

    policy = module._evidence_operator_resource_policy(args)

    assert module._resolved_evidence_operator_fanout_workers(args) == 2
    assert policy["policy_name"] == "local_bge_subprocess_queue"
    assert policy["evidence_operator_fanout_workers"] == 2


def test_real_llm_chain_resource_policy_honors_explicit_fanout_workers() -> None:
    module = _load_script_module()
    args = module.parse_args(
        [
            "--bge-device",
            "cuda",
            "--context-runner",
            "in_process",
            "--evidence-operator-fanout-workers",
            "3",
        ]
    )

    policy = module._evidence_operator_resource_policy(args)

    assert module._resolved_evidence_operator_fanout_workers(args) == 3
    assert policy["policy_name"] == "explicit"
    assert policy["requested_evidence_operator_fanout_workers"] == 3


def test_supervising_analyst_pack_gate_required_for_deep_investment_cases() -> None:
    module = _load_script_module()
    case = {
        "expected_execution_mode": "deep_research",
        "require_investment_memo_quality": True,
    }
    result = {
        "supervising_analyst_pack": {
            "validation": {"status": "pass"},
            "financial_analysis_model": {"key_line_items": [{"ticker": "DELL"}]},
            "product_bridge_pack": {"company_disclosed_product_kpis": [{"ticker": "DELL"}]},
            "capital_transmission_graph": {"edges": [{"source": "GOOGL", "target": "AI infrastructure demand pool"}]},
            "research_lead_synthesis_plan": {
                "core_judgment": "Qualified positive readthrough.",
                "writer_directives": ["Open with judgment."],
            },
        },
        "multi_agent_summary": {"supervising_analyst_pack": {"status": "pass"}},
    }

    audit = module._supervising_analyst_pack_checks(case, result=result)

    assert audit["required"] is True
    assert audit["status"] == "pass"
    assert all(audit["checks"].values())


def test_source_layer_capability_gate_accepts_visible_l2_l3_l4_audit() -> None:
    module = _load_script_module()
    case = {"require_source_layer_capability_audit": True}
    result = {
        "source_layer_capability_audit": {
            "schema_version": "finsight_source_layer_capability_audit_v0_1",
            "status": "loaded",
            "rows": [
                {
                    "source_id": "company_product_pages",
                    "layer_id": "L2",
                    "evidence_graph_status": "structured_not_promoted",
                    "context_or_proxy_allowed": True,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
                {
                    "source_id": "ecommerce_major_platforms",
                    "layer_id": "L3",
                    "evidence_graph_status": "not_registered",
                    "context_or_proxy_allowed": False,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
                {
                    "source_id": "unverified_self_media_forums",
                    "layer_id": "L4",
                    "evidence_graph_status": "blocked_by_auth_or_policy",
                    "context_or_proxy_allowed": False,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
            ],
            "summary": {
                "source_count": 3,
                "context_or_proxy_allowed_count": 1,
                "expected_missing_count": 1,
                "exact_authority_ready_count": 0,
                "by_layer": {"L2": {"count": 1}, "L3": {"count": 1}, "L4": {"count": 1}},
                "by_evidence_graph_status": {
                    "structured_not_promoted": 1,
                    "not_registered": 1,
                    "blocked_by_auth_or_policy": 1,
                },
            },
            "validation": {"status": "pass"},
        }
    }

    audit = module._source_layer_capability_checks(case, result=result, summary={})

    assert audit["status"] == "pass"
    assert audit["checks"]["required_layers_visible"] is True
    assert audit["metrics"]["layer_counts"] == {"L2": 1, "L3": 1, "L4": 1}


def test_source_layer_capability_gate_rejects_l3_exact_authority_promotion() -> None:
    module = _load_script_module()
    case = {"require_l2_l3_l4_source_audit": True}
    result = {
        "source_layer_capability_audit": {
            "rows": [
                {
                    "source_id": "company_product_pages",
                    "layer_id": "L2",
                    "evidence_graph_status": "structured_not_promoted",
                    "context_or_proxy_allowed": True,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
                {
                    "source_id": "ecommerce_major_platforms",
                    "layer_id": "L3",
                    "evidence_graph_status": "runtime_ready_context",
                    "context_or_proxy_allowed": True,
                    "exact_value_authority_ready": True,
                    "can_support_company_exact_fact": True,
                },
                {
                    "source_id": "unverified_self_media_forums",
                    "layer_id": "L4",
                    "evidence_graph_status": "not_registered",
                    "context_or_proxy_allowed": False,
                    "exact_value_authority_ready": False,
                    "can_support_company_exact_fact": False,
                },
            ],
            "summary": {
                "source_count": 3,
                "context_or_proxy_allowed_count": 2,
                "expected_missing_count": 1,
                "by_layer": {"L2": {"count": 1}, "L3": {"count": 1}, "L4": {"count": 1}},
                "by_evidence_graph_status": {"structured_not_promoted": 1, "runtime_ready_context": 1, "not_registered": 1},
            },
            "validation": {"status": "fail"},
        }
    }

    audit = module._source_layer_capability_checks(case, result=result, summary={})

    assert audit["status"] == "fail"
    assert audit["checks"]["non_l1_exact_authority_absent"] is False
    assert audit["metrics"]["non_l1_exact_violation_sources"] == ["ecommerce_major_platforms"]


def test_role_source_layer_distribution_gate_accepts_explicit_selector_gap() -> None:
    module = _load_script_module()
    case = {
        "require_role_source_layer_distribution": True,
        "expected_specialist_agents": ["product_technology_analyst"],
    }
    result = {
        "specialist_fanout_barrier": {
            "source_layer_distribution": {
                "schema_version": "finsight_role_source_layer_distribution_v0_1",
                "status": "gap",
                "role_count": 1,
                "failed_roles": [],
                "gap_roles": ["product_technology_analyst"],
                "roles": {
                    "product_technology_analyst": {
                        "coverage_status": "gap",
                        "candidate_count": 3,
                        "selected_count": 2,
                        "repairable_candidate_count": 2,
                        "not_registered_count": 1,
                        "selected_by_layer": {"L1": 1, "L2": 1},
                        "selected_missing_required_layers": ["L3"],
                        "exact_authority_violation_sources": [],
                    }
                },
            }
        },
        "specialist_route_results": [
            {
                "agent_id": "product_technology_analyst",
                "status": "pass",
                "source_layer_distribution": {"coverage_status": "gap"},
            }
        ],
    }

    audit = module._role_source_layer_distribution_checks(case, result=result, summary={})

    assert audit["status"] == "pass"
    assert audit["selector_gap_roles"] == ["product_technology_analyst"]
    assert audit["checks"]["gap_status_allowed"] is True


def test_role_source_layer_distribution_gate_rejects_proxy_exact_promotion() -> None:
    module = _load_script_module()
    case = {
        "require_role_source_layer_distribution": True,
        "expected_specialist_agents": ["market_valuation_analyst"],
    }
    result = {
        "specialist_fanout_barrier": {
            "source_layer_distribution": {
                "schema_version": "finsight_role_source_layer_distribution_v0_1",
                "status": "fail",
                "role_count": 1,
                "failed_roles": ["market_valuation_analyst"],
                "gap_roles": [],
                "roles": {
                    "market_valuation_analyst": {
                        "coverage_status": "fail",
                        "candidate_count": 1,
                        "selected_count": 1,
                        "repairable_candidate_count": 1,
                        "not_registered_count": 0,
                        "selected_by_layer": {"L3": 1},
                        "selected_missing_required_layers": [],
                        "exact_authority_violation_sources": ["channel_pricing_quotations"],
                    }
                },
            }
        }
    }

    audit = module._role_source_layer_distribution_checks(case, result=result, summary={})

    assert audit["status"] == "fail"
    assert audit["checks"]["exact_authority_violation_absent"] is False
    assert audit["exact_authority_violation_roles"] == ["market_valuation_analyst"]


def test_multi_agent_real_llm_chain_scoring_accepts_layered_success() -> None:
    module = _load_script_module()
    case = _read_jsonl(FIXTURE_PATH)[0]
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
            ]
        },
        "memo_answer": {"answer_status": "draft", "bounded_answer_allowed": False},
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {
            "status": "pass",
            "verifier_input_projection": {
                "projection_policy": "final_memo_claims_and_referenced_evidence_only",
                "projected_claim_count": 2,
            },
        },
        "rendered_answer": "bounded rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "pass"
    assert all(score["checks"].values())
    assert score["agent_audit"]["research_lead"]["validation_status"] == "pass"
    assert score["agent_audit"]["verifier"]["input_projection"]["projected_claim_count"] == 2


def test_multi_agent_real_llm_chain_scoring_accepts_stepwise_research_lead_validation() -> None:
    module = _load_script_module()
    case = _read_jsonl(FIXTURE_PATH)[0]
    result = {
        "status": "stopped_after_node",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "research_lead_validation": {"status": "pass"},
        "memo_answer": {"answer_status": "draft", "bounded_answer_allowed": False},
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {
            "status": "pass",
            "verifier_input_projection": {
                "projection_policy": "final_memo_claims_and_referenced_evidence_only",
                "projected_claim_count": 2,
            },
        },
        "rendered_answer": "bounded rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["checks"]["research_lead.validation_pass"] is True
    assert score["agent_audit"]["research_lead"]["validation_status"] == "pass"


def test_real_llm_chain_diagnostic_quality_accepts_product_and_capex_facts() -> None:
    module = _load_script_module()
    case = {
        "case_id": "diagnostic_quality_unit",
        "category": "diagnostic_probe",
        "required_approved_metric_ids": ["financial_metric:capex", "product_kpi:product_revenue"],
        "required_deterministic_claim_dimensions": ["capital_and_financing", "product_and_production"],
        "required_product_fact_terms": ["AI-optimized servers"],
        "require_no_internal_synthesis_dimension": True,
        "require_numeric_fact_sanity": True,
        "require_product_or_gap_evidence": True,
        "require_capital_financing_signal": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "selection_id": "fact_capex",
                    "fact_id": "capex_ref",
                    "ticker": "MSFT",
                    "canonical_metric_id": "financial_metric:capex",
                    "value": "9.1",
                    "unit": "usd_billions",
                    "evidence_ref": "capex_ref",
                },
                {
                    "selection_id": "fact_dell_ai_servers",
                    "fact_id": "dell_product_ref",
                    "ticker": "DELL",
                    "canonical_metric_id": "product_kpi:product_revenue",
                    "product_or_segment": "AI-optimized servers",
                    "value": "16132",
                    "unit": "usd_millions",
                    "evidence_ref": "dell_product_ref",
                },
            ]
        },
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "claim_capex",
                    "agent_id": "pre_memo_fact_selector",
                    "analysis_dimension": "capital_and_financing",
                    "metric_scope": ["financial_metric:capex"],
                    "evidence_refs": ["capex_ref"],
                },
                {
                    "claim_id": "claim_product",
                    "agent_id": "pre_memo_fact_selector",
                    "analysis_dimension": "product_and_production",
                    "metric_scope": ["product_kpi:product_revenue"],
                    "product_or_segment": "AI-optimized servers",
                    "evidence_refs": ["dell_product_ref"],
                },
            ]
        },
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {"dimension_id": "capital_and_financing", "summary": "Capex fact.", "evidence_refs": ["capex_ref"]},
                {"dimension_id": "product_and_production", "summary": "AI-optimized servers fact.", "evidence_refs": ["dell_product_ref"]},
            ],
        },
        "claim_verification": {"status": "pass"},
        "rendered_answer": "分维度分析:\n- 产品产线：DELL AI-optimized servers 有公司披露收入。\n关键论据:\n1. capex fact 证据=capex_ref",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "pass"
    assert all(score["layer_checks"]["diagnostic_quality"].values())
    assert score["diagnostic_quality_audit"]["product_evidence_present"] is True


def test_real_llm_chain_investment_quality_rejects_gap_ledger_surface() -> None:
    module = _load_script_module()
    case = {
        "case_id": "investment_quality_gap_ledger",
        "category": "sector_depth",
        "response_language": "zh-CN",
        "require_investment_memo_quality": True,
        "require_dimension_memo_surface": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {"dimension_id": "fundamentals", "summary": "云收入和 RPO 支撑需求判断。", "evidence_refs": ["capex_cloud_rpo"]},
                {"dimension_id": "product_and_production", "summary": "DELL AI server 收入支撑产品传导。", "evidence_refs": ["dell_ai_servers"]},
            ],
        },
        "claim_verification": {"status": "pass"},
        "verified_judgment_plan": {
            "thesis_driver_pack": {
                "dimension_sections": [
                    {"dimension_id": "fundamentals"},
                    {"dimension_id": "product_and_production"},
                ]
            }
        },
        "rendered_answer": (
            "核心判断:\n当前数据不足，无法判断。缺口在 ASML、产品、订单、capex 和竞争位置。无法给出投资含义。\n\n"
            "分维度分析:\n1. 产品产线：当前缺口较多，不能判断。[C1]\n2. 投融资：公开数据不足，不能判断。[C2]\n\n"
            "关键论据:\n1. 该声明为已核对财务事实，不得推断未验证。[C1]\n\n"
            "投资含义:\n- 数据缺口较多，无法判断。\n\n"
            "什么会改变判断:\n- 如果补到数据。\n\n"
            "后续跟踪:\n- 跟踪更多数据。\n\n"
            "可行动的证据缺口:\n- 缺口很多，当前不能判断，公开数据不足，商业 tracker 缺口。"
        ),
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["layer_checks"]["memo_verifier"]["investment_memo_quality_pass"] is False
    quality_checks = score["investment_quality"]["checks"]
    assert quality_checks["gap_budget_ok"] is False
    assert quality_checks["internal_gate_prose_absent"] is False


def test_real_llm_chain_investment_quality_allows_role_boundary_opening() -> None:
    module = _load_script_module()
    text = (
        "核心判断:\n"
        "已披露事实给出的主线是：DELL 的产品收入（$16.1B、2026）提供公司披露的产品或分部收入锚点，"
        "可用于收入承接和业务组合判断，但不能外推 SKU 份额、ASP 或客户订单；"
        "AMZN 的资本开支（$151B、2026）只能说明客户/需求侧资本开支或终端需求池扩张，"
        "不能当作供应商收入、backlog 或直接订单。投资判断应先区分客户/需求侧 capex、供应商自身 capex、产品收入/订单与毛利锚点。"
        "\n\n分维度分析:\n"
        "1. 基本面与财务质量：DELL AI server 收入和 NVDA 毛利率共同支撑收入质量判断。[C1]\n"
        "2. 产品与产线证据：DELL AI server 与 NVDA GPU 构成供应链桥接，需要看客户部署和利润率。[C2]\n\n"
        "关键论据:\n1. DELL AI server 收入构成产品-财务桥接。[C1]\n\n"
        "投资含义:\n- 当前证据支持 AI 基础设施需求池扩张，但需要用 DELL 利润率和 NVDA 数据中心收入验证传导质量。\n\n"
        "什么会改变判断:\n- 如果客户部署或订单证据无法对应 DELL/NVDA 收入，供应链传导判断需要下修。\n\n"
        "后续跟踪:\n- 跟踪云厂商 capex、DELL AI server 毛利、NVDA GPU 供给和客户部署。"
    )

    quality = module._rendered_investment_quality_checks(text, "zh-CN")

    assert quality["checks"]["thesis_not_gap_first"] is True


def test_real_llm_chain_investment_quality_rejects_fake_product_financial_lines_and_metadata() -> None:
    module = _load_script_module()
    case = {
        "case_id": "investment_quality_fake_product_line",
        "category": "sector_depth",
        "response_language": "zh-CN",
        "require_investment_memo_quality": True,
        "require_dimension_memo_surface": True,
        "require_rendered_evidence_refs": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {"dimension_id": "fundamentals", "summary": "收入证据可用。", "evidence_refs": ["rev_ref"]},
                {"dimension_id": "product_and_production", "summary": "产品证据可用。", "evidence_refs": ["bad_product_ref"]},
                {"dimension_id": "capital_and_financing", "summary": "资本开支证据可用。", "evidence_refs": ["capex_ref"]},
            ],
        },
        "claim_verification": {"status": "pass"},
        "verified_judgment_plan": {
            "thesis_driver_pack": {
                "dimension_sections": [
                    {"dimension_id": "fundamentals"},
                    {"dimension_id": "product_and_production"},
                    {"dimension_id": "capital_and_financing"},
                ]
            }
        },
        "rendered_answer": (
            "核心判断:\n半导体设备周期需要同时看订单、收入和资本开支传导。[C1]\n\n"
            "分维度分析:\n"
            "1. 基本面：ASML 收入和订单是判断周期的锚点。[C1]\n"
            "2. 产品产线：AMAT 的 Proceeds from sales and maturities of investments 被写成产品收入证据，KLAC 的 Receivables sold under factoring agreements 和 Costs of revenues 被写成产品表现证据。[C2]\n"
            "3. 投融资/资本开支：资本开支影响供应链收入和现金流回报。[C3]\n"
            "5. 风险反证：若订单不跟随收入改善，周期判断要下修。[C4]\n\n"
            "关键论据:\n1. 产品段落混入投资收益和成本行。[C2]\n\n"
            "投资含义:\n- 投资判断应先落在 fundamentals / financial_metric:revenue 这条已验证证据链上，再判断周期。\n\n"
            "什么会改变判断:\n- 如果订单和收入背离，意味着需求传导失败。\n\n"
            "后续跟踪:\n- 跟踪订单、积压、客户和产能证据。\n\n"
            "证据索引:\n- [C1] revenue\n- [C2] bad product financial line\n- [C3] capex\n- [C4] order risk"
        ),
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["layer_checks"]["memo_verifier"]["surface.no_internal_field_labels"] is False
    quality_checks = score["investment_quality"]["checks"]
    assert quality_checks["product_section_not_fake_financial_line"] is False
    assert quality_checks["dimension_number_sequence_ok"] is False
    assert quality_checks["decision_sections_actionable"] is False
    assert quality_checks["internal_gate_prose_absent"] is False


def test_real_llm_chain_investment_quality_rejects_capex_as_product_line() -> None:
    module = _load_script_module()
    case = {
        "case_id": "investment_quality_capex_product_line",
        "category": "sector_depth",
        "response_language": "zh-CN",
        "require_investment_memo_quality": True,
        "require_dimension_memo_surface": True,
        "require_rendered_evidence_refs": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {"dimension_id": "fundamentals", "summary": "收入证据可用。", "evidence_refs": ["rev_ref"]},
                {"dimension_id": "product_and_production", "summary": "产品证据可用。", "evidence_refs": ["capex_ref"]},
            ],
        },
        "claim_verification": {"status": "pass"},
        "verified_judgment_plan": {
            "thesis_driver_pack": {
                "dimension_sections": [
                    {"dimension_id": "fundamentals"},
                    {"dimension_id": "product_and_production"},
                ]
            }
        },
        "rendered_answer": (
            "核心判断:\nAI infra 需求要看客户投入是否传导到供应商产品收入。[C1]\n\n"
            "分维度分析:\n"
            "1. 基本面：收入与现金流是判断基线。[C1]\n"
            "2. 产品与产线证据：DELL资本支出-9.63亿美元，远高于ANET和VRT，反映其在AI基础设施产能上的重投。[C2]\n"
            "3. 投融资/资本开支：资本开支影响自由现金流和回报周期。[C2]\n\n"
            "关键论据:\n1. capex 是资本配置证据，不应冒充产品证据。[C2]\n\n"
            "投资含义:\n- 如果产品收入跟随客户投入，供应链收入传导才成立。\n\n"
            "什么会改变判断:\n- 若产品收入不跟随资本开支，意味着投入回报弱化。\n\n"
            "后续跟踪:\n- 跟踪产品收入、订单、客户部署和资本开支。\n\n"
            "证据索引:\n- [C1] revenue\n- [C2] capex"
        ),
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["investment_quality"]["checks"]["product_section_not_fake_financial_line"] is False
    assert score["investment_quality"]["metrics"]["product_section_fake_financial_line_count"] >= 1


def test_p30_required_item_gate_requires_summary_projection_for_answer_plan() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_nvda_dell_capex_023",
        "prompt": "诊断 NVDA 与 DELL AI infrastructure demand read-through。",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "AMZN", "MSFT", "GOOGL"],
    }
    required_plan = [
        {"question_item_id": "dell_ai_server_quality_margin_bridge"},
        {"question_item_id": "nvda_gpu_supply_generation"},
        {"question_item_id": "cloud_capex_read_through"},
        {"question_item_id": "customer_deployment_or_order_signal"},
    ]
    result = {
        "memo_logic_plan": {
            "validation": {"status": "pass"},
            "required_item_answer_plan": required_plan,
            "product_reasoning_frame": {"coverage_roles": ["product_kpi", "customer_deployment"]},
        },
        "multi_agent_summary": {
            "memo_logic_plan": {
                "status": "pass",
                "required_item_answer_plan_count": 0,
                "required_item_answer_plan": [],
            }
        },
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "ticker": "DELL",
                    "canonical_metric_id": "product_kpi:product_revenue",
                    "display_value": "$16.1B",
                    "display_value_lineage": {"schema_version": "sec_agent_display_value_lineage_v0.1"},
                    "source_statement": "DELL AI server revenue and gross margin bridge.",
                }
            ]
        },
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "dell_ai_server_quality",
                    "claim": "DELL AI server gross margin bridge supports product quality analysis.",
                    "analysis_dimension": "product_and_production",
                    "ticker_scope": ["DELL"],
                    "evidence_refs": ["dell_ai_server_quality"],
                },
                {
                    "claim_id": "nvda_gpu_supply",
                    "claim": "NVDA GPU H100 Blackwell generation supports supply analysis.",
                    "analysis_dimension": "product_and_production",
                    "ticker_scope": ["NVDA"],
                    "evidence_refs": ["nvda_gpu_supply"],
                },
                {
                    "claim_id": "cloud_capex",
                    "claim": "AMZN MSFT GOOGL cloud capex supports data center read-through.",
                    "analysis_dimension": "capital_and_financing",
                    "ticker_scope": ["AMZN", "MSFT", "GOOGL"],
                    "evidence_refs": ["cloud_capex"],
                },
                {
                    "claim_id": "customer_deployment",
                    "claim": "Customer deployment and order adoption signal supports demand quality.",
                    "analysis_dimension": "product_and_production",
                    "ticker_scope": ["DELL", "NVDA"],
                    "evidence_refs": ["deployment"],
                },
            ]
        },
    }
    rendered = (
        "DELL AI server gross margin supports a bounded product-quality judgment. "
        "NVDA GPU H100 Blackwell generation supports supply and architecture judgment. "
        "AMZN MSFT GOOGL cloud capex supports data center read-through. "
        "Customer deployment and order adoption signal supports demand quality."
    )

    audit = module._p30_root_cause_quality_audit(case, result=result, rendered_answer=rendered, memo_dimension_analyses=[])

    assert audit["status"] == "fail"
    assert audit["checks"]["required_item_answer_plan_present"] is True
    assert audit["checks"]["required_item_answer_plan_projected_to_summary"] is False
    assert any(row["symptom"] == "required_item_answer_plan_not_projected_to_summary" for row in audit["root_cause_rows"])


def test_real_llm_chain_investment_quality_is_required_for_deep_dimension_surface() -> None:
    module = _load_script_module()
    case = {
        "case_id": "investment_quality_implicit_required",
        "category": "sector_depth",
        "response_language": "zh-CN",
        "expected_execution_mode": "deep_research",
        "require_dimension_memo_surface": True,
        "require_analyst_depth_gate": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research"},
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {"answer_status": "draft", "dimension_analyses": []},
        "claim_verification": {"status": "pass"},
        "rendered_answer": (
            "核心判断:\n当前公开数据缺口较多，无法判断。缺少产品、订单、capex 和竞争证据。\n\n"
            "分维度分析:\n1. 产品产线：缺口较多，不能判断。[C1]\n2. 投融资：公开数据不足，不能判断。[C2]\n\n"
            "投资含义:\n- 数据不足，无法判断。\n\n"
            "什么会改变判断:\n- 如果补到数据。\n\n"
            "后续跟踪:\n- 跟踪更多数据。\n\n"
            "可行动的证据缺口:\n- 缺口很多，当前不能判断，公开数据不足，商业 tracker 缺口。"
        ),
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["investment_quality_required"] is True
    assert score["gate_status"] == "fail"
    assert score["layer_checks"]["memo_verifier"]["investment_memo_quality_pass"] is False


def test_real_llm_chain_product_fake_financial_gate_only_scans_product_dimension() -> None:
    module = _load_script_module()
    rendered_answer = (
        "核心判断:\nAI infrastructure 需求要看产品收入、订单和资本开支传导。[C1]\n\n"
        "分维度分析:\n"
        "1. 基本面与财务质量：收入和现金流决定盈利能力。[C1]\n"
        "2. 产品与产线证据：DELL AI server 产品收入把客户需求传到供应商产品线。[C2]\n"
        "3. 投融资/资本开支：资本开支影响供应商产品线的回报周期和现金流压力。[C3]\n\n"
        "投资含义:\n- 如果产品收入跟随客户投入，需求传导才成立。\n\n"
        "什么会改变判断:\n- 若产品收入不跟随资本开支，说明投入回报弱化。\n\n"
        "后续跟踪:\n- 跟踪订单、积压、客户部署和资本开支。\n\n"
        "证据索引:\n- [C1] revenue\n- [C2] product revenue\n- [C3] capex"
    )

    assert module._product_section_fake_financial_line_count(rendered_answer, "zh-CN") == 0


def test_real_llm_chain_investment_quality_accepts_decision_useful_surface() -> None:
    module = _load_script_module()
    case = {
        "case_id": "investment_quality_pass",
        "category": "sector_depth",
        "response_language": "zh-CN",
        "require_investment_memo_quality": True,
        "require_dimension_memo_surface": True,
        "require_rendered_evidence_refs": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {"dimension_id": "fundamentals", "summary": "云收入和 RPO 支撑需求判断。", "evidence_refs": ["capex_cloud_rpo"]},
                {"dimension_id": "product_and_production", "summary": "DELL AI server 收入支撑产品传导。", "evidence_refs": ["dell_ai_servers"]},
            ],
        },
        "claim_verification": {"status": "pass"},
        "verified_judgment_plan": {
            "thesis_driver_pack": {
                "dimension_sections": [
                    {"dimension_id": "fundamentals"},
                    {"dimension_id": "product_and_production"},
                ]
            }
        },
        "rendered_answer": (
            "核心判断:\nAI infra 需求仍然更像资本开支传导到供应链收入的中期主线，而不是单一季度订单交易。"
            "MSFT/AMZN/GOOGL 的 capex 与云收入/RPO 同时扩张，意味着需求端还在释放算力预算；DELL AI-optimized servers 收入对应到供应端，支撑服务器环节已经把预算转化为产品收入。[C1][C2]\n\n"
            "分维度分析:\n1. 基本面：云收入和 RPO 的增长说明需求不只停留在叙事层，现金流和资本开支共同决定回报压力。[C1]\n"
            "2. 产品产线：DELL AI-optimized servers 收入把 hyperscaler capex 传导到供应商产品线，支撑产品维度的可验证性。[C2]\n"
            "3. 投融资/资本开支：capex 扩张会压制短期 FCF，但如果云收入和 RPO 延续，回报周期可以被收入增长吸收。[C1]\n\n"
            "关键论据:\n1. hyperscaler capex 与云/RPO 同向改善。[C1]\n2. DELL AI server 产品收入已披露。[C2]\n\n"
            "投资含义:\n- 组合判断应把 capex 压力和供应链收入放在一起看：如果供应商产品收入继续跟随 hyperscaler capex，AI 需求对基本面的支撑强于单纯费用化叙事。\n\n"
            "什么会改变判断:\n- 如果 capex 继续上行但云收入/RPO 放缓，意味着投入回报被拉长，供应链订单质量也要下调。\n\n"
            "后续跟踪:\n- 跟踪 MSFT/AMZN/GOOGL 下一季 capex、云收入/RPO 和 DELL AI server 收入口径，验证预算到产品收入的传导是否延续。\n\n"
            "可行动的证据缺口:\n- 真实客户订单拆分仍需要公司披露或商业 tracker，不能用公开 proxy 替代。\n\n"
            "证据索引:\n- [C1] capex cloud rpo\n- [C2] dell ai servers"
        ),
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "pass"
    assert score["layer_checks"]["memo_verifier"]["investment_memo_quality_pass"] is True
    assert score["investment_quality"]["metrics"]["insight_sentence_count"] >= 3


def test_real_llm_chain_diagnostic_quality_rejects_product_fact_not_promoted_to_claim() -> None:
    module = _load_script_module()
    case = {
        "case_id": "diagnostic_quality_product_not_promoted",
        "category": "diagnostic_probe",
        "required_approved_metric_ids": ["product_kpi:product_revenue"],
        "required_deterministic_claim_dimensions": ["product_and_production"],
        "required_product_fact_terms": ["AI-optimized servers"],
        "require_product_or_gap_evidence": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "selection_id": "fact_dell_ai_servers",
                    "fact_id": "dell_product_ref",
                    "ticker": "DELL",
                    "canonical_metric_id": "product_kpi:product_revenue",
                    "product_or_segment": "AI-optimized servers",
                    "value": "16132",
                    "unit": "usd_millions",
                    "evidence_ref": "dell_product_ref",
                }
            ]
        },
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "claim_capex",
                    "agent_id": "pre_memo_fact_selector",
                    "analysis_dimension": "capital_and_financing",
                    "metric_scope": ["financial_metric:capex"],
                    "evidence_refs": ["capex_ref"],
                }
            ]
        },
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {
                    "dimension_id": "product_and_production",
                    "status": "gap_or_counterevidence",
                    "summary": "当前产品/产线维度只有公开证据缺口。",
                    "gap_ids": ["gap_product"],
                }
            ],
        },
        "claim_verification": {"status": "pass"},
        "rendered_answer": "分维度分析:\n- 产品产线：当前产品/产线维度只有公开证据缺口。\n关键论据:\n1. capex fact 证据=capex_ref",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["layer_checks"]["diagnostic_quality"]["required_deterministic_claim_dimensions_present"] is False
    assert score["layer_checks"]["diagnostic_quality"]["required_product_fact_terms_present"] is False
    assert score["diagnostic_quality_audit"]["product_evidence_present"] is True


def test_real_llm_chain_diagnostic_quality_rejects_bad_numeric_and_internal_synthesis() -> None:
    module = _load_script_module()
    case = {
        "case_id": "diagnostic_quality_bad_unit",
        "category": "diagnostic_probe",
        "require_no_internal_synthesis_dimension": True,
        "require_numeric_fact_sanity": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "selection_id": "bad_revenue",
                    "fact_id": "bad_revenue_ref",
                    "ticker": "GOOGL",
                    "canonical_metric_id": "financial_metric:revenue",
                    "value": "19",
                    "unit": "%",
                    "evidence_ref": "bad_revenue_ref",
                },
                {
                    "selection_id": "bad_gross_margin",
                    "fact_id": "bad_gross_margin_ref",
                    "ticker": "DELL",
                    "canonical_metric_id": "financial_metric:gross_margin",
                    "product_or_segment": "Cash flow from operations",
                    "value": "65.0",
                    "unit": "percent",
                    "evidence_ref": "bad_gross_margin_ref",
                },
                {
                    "selection_id": "bad_deferred_revenue",
                    "fact_id": "bad_deferred_revenue_ref",
                    "ticker": "LRCX",
                    "canonical_metric_id": "financial_metric:revenue",
                    "value": "300.0",
                    "unit": "usd_millions",
                    "evidence_ref": "INTERACTIVE::LRCX::2026::deferred_revenue::total_value::qtd",
                }
            ]
        },
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {"dimension_id": "thesis_synthesis", "summary": "Internal synthesis should not render.", "evidence_refs": ["bad_revenue_ref"]}
            ],
        },
        "claim_verification": {"status": "pass"},
        "rendered_answer": "Synthesis: primary_sec_filing should not be rendered.",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["layer_checks"]["diagnostic_quality"]["numeric_fact_sanity"] is False
    assert score["layer_checks"]["diagnostic_quality"]["no_internal_synthesis_dimension"] is False
    reasons = {row.get("reason") for row in score["diagnostic_quality_audit"]["numeric_violations"]}
    assert "profitability_metric_semantic_noise" in reasons
    assert "revenue_metric_semantic_noise" in reasons


def test_real_llm_chain_scoring_accepts_run_audit_and_dimension_depth() -> None:
    module = _load_script_module()
    case = {
        "case_id": "run_audit_depth_unit",
        "category": "standard_memo",
        "response_language": "zh-CN",
        "require_run_audit_store": True,
        "require_dimension_memo_surface": True,
        "require_analyst_depth_gate": True,
        "required_dimension_ids": ["fundamentals", "product_and_production", "risk_and_counterevidence"],
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {},
        "agent_activation_validation": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "dimension_analyses": [
                {
                    "dimension_id": "fundamentals",
                    "summary": "Fundamental evidence is traceable.",
                    "evidence_refs": ["ref_1"],
                },
                {
                    "dimension_id": "product_and_production",
                    "section_thesis": "Product evidence is traceable.",
                    "claim_ids": ["claim_2"],
                },
                {
                    "dimension_id": "risk_and_counterevidence",
                    "section_thesis": "Risk evidence is currently a bounded public-source gap.",
                    "gap_ids": ["gap_3"],
                },
            ],
        },
        "claim_verification": {
            "status": "pass",
            "analyst_depth_gate": {"status": "pass"},
        },
        "verified_judgment_plan": {
            "thesis_driver_pack": {
                "dimension_sections": [
                    {"dimension_id": "fundamentals"},
                    {"dimension_id": "product_and_production"},
                    {"dimension_id": "risk_and_counterevidence"},
                ]
            }
        },
        "run_audit_materialization_report": {
            "status": "pass",
            "run_audit_policy": "sqlite_is_final_audit_source_redis_coordination_only_v0_1",
            "table_counts": {
                "run": 1,
                "node_execution": 4,
                "artifact_ref": 2,
                "evidence_row": 1,
                "claim_card": 1,
                "gap": 0,
                "gate_result": 2,
                "model_call": 1,
            },
        },
        "rendered_answer": (
            "核心判断:\n公司基本面、产品线和风险证据形成可审计但仍需跟踪的判断：收入证据支撑基本面稳定，产品线证据说明需求能落到业务活动，风险证据决定结论权重。[C1][C2]\n\n"
            "分维度分析:\n"
            "1. 基本面：收入和现金流证据说明当前业务质量有事实锚点，后续要用利润率和经营现金流验证增长质量。[C1]\n"
            "2. 产品产线：产品线证据把需求方向连接到具体业务活动，只有订单、积压或产品收入继续跟上，才能提高产品判断权重。[C2]\n"
            "3. 风险反证：如果产品需求没有进入收入或订单，说明需求传导失败，估值应回到更保守情景。[C3]\n\n"
            "关键论据:\n1. 收入和产品线证据共同支撑当前判断。[C1][C2]\n2. 风险证据决定是否下调结论权重。[C3]\n\n"
            "投资含义:\n- 若产品线和收入继续同向改善，说明需求不是叙事而是正在进入业务；若只看到产品叙事而没有收入或订单承接，应降低结论强度。\n\n"
            "什么会改变判断:\n- 如果后续收入放缓但资本开支或库存上升，意味着投入回报弱化，判断需要下修。\n\n"
            "后续跟踪:\n- 跟踪收入、产品线订单、积压、现金流和风险反证，验证需求到财务的传导是否延续。\n\n"
            "证据索引:\n- [C1] ref 1\n- [C2] product ref\n- [C3] risk gap"
        ),
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "pass"
    assert all(score["layer_checks"]["run_audit"].values())
    assert all(score["layer_checks"]["analyst_depth"].values())
    assert score["memo_dimension_analysis_count"] == 3
    assert score["analyst_depth_gate_status"] == "pass"
    assert score["run_audit"]["table_counts"]["model_call"] == 1


def test_initial_state_adds_default_case_run_audit_path_when_required(tmp_path: Path) -> None:
    module = _load_script_module()
    args = module.parse_args(["--run-id", "unit_audit_default"])
    case = {
        "case_id": "case_audit_default",
        "prompt": "Run audit required case",
        "focus_tickers": ["LLY"],
        "search_scope_tickers": ["LLY"],
        "require_run_audit_store": True,
    }

    state = module._initial_state(
        case,
        tmp_path / "case_audit_default",
        run_id="unit_audit_default",
        previous_turn_summary=None,
        args=args,
    )

    expected = (REPO_ROOT / "data" / "workbench_private" / "run_audit" / "unit_audit_default.sqlite").resolve()
    assert state["run_audit_db_path"] == str(expected)
    assert state["multi_agent_context"]["run_audit_db_path"] == str(expected)


def test_p30_root_cause_quality_flags_raw_numeric_and_false_missing_evidence() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_semicap_p30_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "focus_tickers": ["LRCX"],
        "search_scope_tickers": ["LRCX"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "selection_id": "sel_lrcx_revenue",
                    "fact_id": "fact_lrcx_revenue",
                    "ticker": "LRCX",
                    "canonical_metric_id": "financial_metric:revenue",
                    "value": "14922.0",
                    "numeric_value": "14922.0",
                    "unit": "usd_millions",
                    "display_value": "$14.9B",
                    "display_value_lineage": {"schema_version": "sec_agent_display_value_lineage_v0.1"},
                    "evidence_ref": "lrcx_revenue_ref",
                }
            ]
        },
        "verified_judgment_plan": {"supported_claims": []},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "LRCX 财务数据缺失，后续仍需补表。另有内部数值 1743504.0 被写出。",
    }
    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)
    audit = score["p30_root_cause_quality_audit"]

    assert score["layer_checks"]["p30_root_cause_quality"]["rendered_no_raw_unitless_numeric"] is False
    assert score["layer_checks"]["p30_root_cause_quality"]["focus_ticker_no_evidence_contradiction"] is False
    assert {row["symptom"] for row in audit["root_cause_rows"]} >= {
        "raw_unitless_numeric_rendered",
        "memo_claims_missing_data_despite_available_evidence",
    }


def test_p30_root_cause_quality_flags_false_missing_product_evidence() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_product_p30_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA 和 DELL 的 AI server 产品、客户部署和供应链 read-through",
        "focus_tickers": ["DELL"],
        "search_scope_tickers": ["NVDA", "DELL"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "pre_memo_fact_selection": {
            "approved_facts": [
                {
                    "selection_id": "sel_dell_ai_server_revenue",
                    "fact_id": "fact_dell_ai_server_revenue",
                    "ticker": "DELL",
                    "canonical_metric_id": "product_kpi:product_revenue",
                    "product_or_segment": "AI-optimized server / ISG",
                    "display_value": "$16.1B AI-optimized server annual revenue",
                    "display_value_lineage": {"schema_version": "sec_agent_display_value_lineage_v0.1"},
                    "evidence_ref": "dell_ai_server_revenue_ref",
                }
            ]
        },
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "dell_isg_product_revenue_claim",
                    "claim_type": "company_reported_product_operating_fact",
                    "ticker_scope": ["DELL"],
                    "metric_scope": ["product_kpi:product_revenue", "AI-optimized server"],
                    "claim": "DELL reported AI-optimized server revenue and ISG revenue, giving a product-level bridge for AI server exposure.",
                    "evidence_refs": ["dell_ai_server_revenue_ref"],
                }
            ]
        },
        "memo_logic_plan": {"product_reasoning_frame": {"coverage_roles": ["exact_product_kpi"]}},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "DELL 的产品 taxonomy 可见，但 no runtime facts confirm AI-optimized server revenue or ISG performance。",
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    checks = score["layer_checks"]["p30_root_cause_quality"]
    assert checks["focus_ticker_no_product_evidence_contradiction"] is False
    assert any(
        row["symptom"] == "memo_claims_missing_product_data_despite_available_evidence"
        and row["root_cause_layer"] == "memo_writer_or_memo_logic_plan_product_evidence_selection"
        for row in score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_p30_root_cause_quality_flags_memo_logic_plan_validation_failure() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_p30_plan_validation_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "memo_logic_plan": {
            "validation": {"status": "fail", "errors": ["required item not projected into writer skeleton"]},
            "product_reasoning_frame": {"coverage_roles": ["official_product_surface"]},
        },
        "verified_judgment_plan": {"supported_claims": []},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "NVDA 产品线和需求背景被简要覆盖。",
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["memo_logic_plan_validation_pass"] is False
    assert any(
        row["symptom"] == "memo_logic_plan_validation_failed"
        for row in score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_p30_raw_numeric_gate_ignores_evidence_index_artifact_ids() -> None:
    module = _load_script_module()

    assert module._p30_raw_numeric_surface_violations(
        "核心判断:\n资本支出约为1510亿美元。\n\n证据索引:\n- [C1] 20260702_p30_root BLOCK_0013"
    ) == []
    assert module._p30_raw_numeric_surface_violations("核心判断:\n内部数值 1743504.0 被写出。")


def test_p30_required_item_gate_accepts_chinese_product_terms() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_semicap_p30_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA、DELL、ASML、AMAT、LRCX、KLAC 的 AI server 和 semicap 周期",
        "focus_tickers": ["NVDA", "DELL", "ASML", "AMAT", "LRCX", "KLAC"],
        "search_scope_tickers": ["NVDA", "DELL", "ASML", "AMAT", "LRCX", "KLAC"],
        "require_p30_root_cause_quality": True,
    }
    rendered = (
        "NVDA GPU 与 Blackwell 代际支撑算力判断；DELL AI服务器毛利和客户订单需要联动。"
        "MSFT、AMZN、GOOGL 云服务资本支出和数据中心投入提供需求 read-through。"
        "ASML 订单积压、半导体设备出货周期、台积电/三星/英特尔客户部署，以及中国出口限制和许可证约束均被覆盖。"
    )
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {"supported_claims": []},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "memo_logic_plan": {"product_reasoning_frame": {"coverage_roles": ["official_relationship"]}},
        "rendered_answer": rendered,
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["required_items_covered"] is True


def test_p30_root_cause_quality_flags_economic_role_misuse() -> None:
    module = _load_script_module()
    ai_case = {
        "case_id": "fin_deep_ai_infra_economic_role_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA、DELL 与 MSFT、AMZN、GOOGL cloud capex 的 AI server 需求传导",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
        "require_p30_root_cause_quality": True,
    }
    ai_result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {"supported_claims": []},
        "memo_logic_plan": {"product_reasoning_frame": {"coverage_roles": ["product_kpi"]}},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "AMZN 的产品线/产品面/aws revenue/operating income说明供应商端已有产品收入或产品线证据承接需求。NVDA GPU 和 DELL AI server 毛利判断可回答。",
    }

    ai_score = module.score_case(ai_case, ai_result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert ai_score["layer_checks"]["p30_root_cause_quality"]["economic_role_no_misuse"] is False
    assert any(
        row["symptom"] == "peer_or_customer_capex_context_rendered_as_supplier_revenue"
        for row in ai_score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )

    ai_issuer_capex_result = {
        **ai_result,
        "rendered_answer": "DELL 的资本支出（$0.67B、2026）说明需求端投入或再投资强度，是供应链收入传导的上游约束。",
    }

    ai_issuer_capex_score = module.score_case(
        ai_case,
        ai_issuer_capex_result,
        {"payload_policy": {"raw_evidence": "not_included"}},
        {},
        elapsed_ms=1,
    )

    assert ai_issuer_capex_score["layer_checks"]["p30_root_cause_quality"]["economic_role_no_misuse"] is False
    assert any(
        row["symptom"] == "issuer_own_capex_rendered_as_customer_demand"
        and row["affected_tickers"] == ["DELL"]
        for row in ai_issuer_capex_score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )

    semicap_case = {
        "case_id": "fin_deep_semicap_economic_role_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 ASML、AMAT、LRCX、KLAC 的订单、积压、出货周期和客户需求",
        "focus_tickers": ["ASML", "AMAT", "LRCX", "KLAC"],
        "search_scope_tickers": ["ASML", "AMAT", "LRCX", "KLAC", "INTC"],
        "require_p30_root_cause_quality": True,
    }
    semicap_result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {"supported_claims": []},
        "memo_logic_plan": {"product_reasoning_frame": {"coverage_roles": ["product_kpi"]}},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "KLAC 的资本支出（$287M、2026）说明需求端投入或再投资强度，是供应链收入传导的上游约束；ASML 订单、backlog 和客户部署均被覆盖。",
    }

    semicap_score = module.score_case(
        semicap_case,
        semicap_result,
        {"payload_policy": {"raw_evidence": "not_included"}},
        {},
        elapsed_ms=1,
    )

    assert semicap_score["layer_checks"]["p30_root_cause_quality"]["economic_role_no_misuse"] is False
    assert any(
        row["symptom"] == "issuer_own_capex_rendered_as_customer_demand"
        for row in semicap_score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_p30_root_cause_quality_allows_capex_customer_demand_boundary_language() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_economic_role_boundary_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA、DELL 与 MSFT、AMZN、GOOGL cloud capex 的 AI server 需求传导",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {"supported_claims": []},
        "memo_logic_plan": {
            "product_reasoning_frame": {"coverage_roles": ["product_kpi"]},
            "required_item_answer_plan": [
                {"item_id": "cloud_capex_signal", "terms_any": ["capex", "资本支出"], "answer_strategy": "judgment"}
            ],
        },
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": (
            "NVDA 的营收和毛利率反映 AI demand 与 pricing power。"
            "DELL 的资本支出约6.7亿美元，反映其自身产能投资，不是客户需求信号。"
            "MSFT、AMZN、GOOGL 的资本支出只能说明需求池扩张，不能直接等同于供应商营收。"
        ),
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["economic_role_no_misuse"] is True
    assert not score["p30_root_cause_quality_audit"]["economic_role_misuse_rows"]


def test_p30_root_cause_quality_does_not_treat_supplier_revenue_to_customer_capex_as_own_capex() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_supplier_revenue_customer_capex_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA 与 DELL 的 AI server、cloud capex 和客户部署",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {"supported_claims": []},
        "memo_logic_plan": {"validation": {"status": "pass"}},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": (
            "NVDA 的营收规模可以作为数据中心客户资本支出强度的供应商侧结果线索，"
            "但不能直接等同于客户订单或未来份额。"
            "DELL 的资本开支是自身再投资，不是客户需求信号。"
        ),
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["economic_role_no_misuse"] is True
    assert not score["p30_root_cause_quality_audit"]["economic_role_misuse_rows"]


def test_p30_required_item_gate_rejects_keyword_only_boundary_language() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_p30_keyword_only_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA 与 DELL 的 AI server、cloud capex 和客户部署",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "claim_dell_ai_server_margin",
                    "claim": "DELL AI server gross margin and ISG revenue are available for judging AI server quality.",
                    "ticker_scope": ["DELL"],
                    "metric_scope": ["gross margin", "AI server"],
                    "evidence_refs": ["ev_dell_margin"],
                }
            ]
        },
        "memo_logic_plan": {
            "product_reasoning_frame": {"coverage_roles": ["exact_product_kpi"]},
            "required_item_answer_plan": [
                {
                    "question_item_id": "dell_ai_server_quality_margin_bridge",
                    "dimension": "product_and_production",
                    "answer_first_judgment_prompt": "Judge DELL AI server quality.",
                }
            ],
        },
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "DELL AI server gross margin 需要继续验证；NVDA GPU、cloud capex 和客户部署也需要后续跟踪。",
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    audit = score["p30_root_cause_quality_audit"]
    assert score["layer_checks"]["p30_root_cause_quality"]["required_items_covered"] is False
    dell_row = next(row for row in audit["required_item_matrix"] if row["item_id"] == "dell_ai_server_quality_margin_bridge")
    assert dell_row["status"] == "term_only_or_boundary_only"
    assert dell_row["rendered_judgment_hit"] is False
    assert any(
        row["symptom"] == "required_item_keyword_covered_without_analyst_judgment"
        and row["root_cause_layer"] == "memo_writer_required_item_answer_execution"
        for row in audit["root_cause_rows"]
    )


def test_p30_required_item_gate_requires_answer_plan_for_required_items() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_semicap_answer_plan_missing_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 ASML、AMAT、LRCX、KLAC 的订单、积压和出口限制",
        "focus_tickers": ["ASML", "AMAT", "LRCX", "KLAC"],
        "search_scope_tickers": ["ASML", "AMAT", "LRCX", "KLAC"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "claim_asml_backlog",
                    "claim": "ASML backlog and order cycle evidence supports semicap cycle visibility.",
                    "ticker_scope": ["ASML"],
                    "metric_scope": ["orders", "backlog"],
                    "evidence_refs": ["ev_asml_backlog"],
                }
            ]
        },
        "memo_logic_plan": {
            "product_reasoning_frame": {"coverage_roles": ["official_product_surface"]},
            "required_item_answer_plan": [],
        },
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "ASML 订单积压支撑半导体设备周期判断，出口限制构成中国收入风险。",
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["required_item_answer_plan_present"] is False
    assert any(
        row["symptom"] == "required_item_missing_answer_plan"
        and row["earliest_faulty_artifact"] == "memo_logic_plan.required_item_answer_plan"
        for row in score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_p30_non_us_official_source_gap_requires_parser_diagnosis() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_semicap_asml_p30_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 ASML、AMAT、LRCX、KLAC 的订单、积压和半导体设备周期",
        "focus_tickers": ["ASML", "AMAT", "LRCX", "KLAC"],
        "search_scope_tickers": ["ASML", "AMAT", "LRCX", "KLAC"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "pre_memo_fact_selection": {"approved_facts": []},
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "lead_targeted_repair_claim:issuer_official:asml",
                    "ticker_scope": ["ASML"],
                    "claim": "ASML targeted web repair reached official issuer sources via government_dataset_endpoint. Official parser targets include net bookings, backlog and systems revenue.",
                    "evidence_refs": ["official_asml_submissions"],
                    "parser_diagnosis_complete": True,
                    "parser_diagnosis": {
                        "parser_diagnosis_complete": True,
                        "source_specific_parser_statuses": [
                            "filing_presence_parser_pass_exact_filing_document_parser_not_run"
                        ],
                        "exact_fact_parser_failure_reasons": [
                            "SEC submissions JSON proves issuer filing presence, but this route does not fetch and parse the linked 6-K/20-F filing body tables into period/unit/citation exact facts."
                        ],
                        "next_parser_actions": [
                            "resolve filing accession links, fetch 6-K/20-F/annual report documents, then parse tables for net bookings, backlog and systems revenue with period/unit/citation gates"
                        ],
                    },
                }
            ]
        },
        "memo_logic_plan": {"product_reasoning_frame": {"coverage_roles": ["official_product_surface"]}},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": (
            "核心判断:\nASML 订单积压和半导体设备周期需要以 6-K/20-F、IR 表格和客户部署交叉验证。"
            "当前官方源已定位，但 exact 表格解析还未把订单/积压提成可引用数值。\n"
        ),
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["non_us_official_source_gaps_have_parser_diagnosis"] is True
    assert not any(
        row["required_item_id"] == "ASML_non_us_disclosure_parser"
        for row in score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_p30_non_us_official_source_gap_fails_without_parser_diagnosis() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_semicap_asml_p30_missing_diagnosis_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 ASML 的 6-K、20-F、订单和积压",
        "focus_tickers": ["ASML"],
        "search_scope_tickers": ["ASML"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "pre_memo_fact_selection": {"approved_facts": []},
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "lead_targeted_repair_claim:issuer_official:asml",
                    "ticker_scope": ["ASML"],
                    "claim": "ASML targeted web repair reached official issuer sources via government_dataset_endpoint and found 6-K / 20-F presence.",
                    "evidence_refs": ["official_asml_submissions"],
                }
            ]
        },
        "memo_logic_plan": {"product_reasoning_frame": {"coverage_roles": ["official_product_surface"]}},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "ASML 6-K/20-F 官方源已定位，但没有订单和积压 exact fact。",
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["non_us_official_source_gaps_have_parser_diagnosis"] is False
    assert any(
        row["required_item_id"] == "ASML_non_us_disclosure_parser"
        for row in score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_p30_root_cause_quality_flags_scope_hypothesis_as_product_primary_proof() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_deep_ai_infra_p30_unit",
        "category": "sector_depth",
        "expected_execution_mode": "deep_research",
        "prompt": "分析 NVDA 和 DELL 的 AI server 产品、客户部署和供应链 read-through",
        "focus_tickers": ["NVDA", "DELL"],
        "search_scope_tickers": ["NVDA", "DELL"],
        "required_dimension_ids": ["product_and_production"],
        "require_p30_root_cause_quality": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {"execution_mode": "deep_research", "activate_agents": []},
        "memo_logic_plan": {
            "product_reasoning_frame": {
                "schema_version": "finsight_product_reasoning_frame_v0_1",
                "coverage_roles": ["scope_hypothesis"],
                "scope_hypothesis_refs": ["same_family_ai_infra_peer_group"],
            }
        },
        "verified_judgment_plan": {"supported_claims": []},
        "memo_answer": {"answer_status": "draft", "memo_claims": []},
        "rendered_answer": "产品产线主要基于 NVDA、DELL 同属 AI infrastructure peer group 判断，未展开客户部署。",
    }
    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["layer_checks"]["p30_root_cause_quality"]["scope_hypothesis_not_primary_product_proof"] is False
    assert any(
        row["symptom"] == "product_section_scope_hypothesis_only"
        for row in score["p30_root_cause_quality_audit"]["root_cause_rows"]
    )


def test_real_llm_chain_scoring_accepts_vnext_contract_summary() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_g11_contract_unit",
        "category": "standard_memo",
        "expected_execution_mode": "standard_memo",
        "required_agents": ["research_lead", "sec_operator", "memo_writer", "verifier", "renderer"],
        "expected_operator_agents": ["sec_operator"],
        "expected_tool_names": ["sec_search_filings"],
        "memo_status_allowed": ["draft"],
        "require_vnext_contract": True,
        "require_milvus_runtime_contract": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "memo_writer", "verifier", "renderer"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {"records": [{"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "ok", "row_count": 2}]},
        "bounded_gap_register": {
            "schema_version": "sec_agent_bounded_gap_register_v0.1",
            "gap_count": 1,
            "gaps": [
                {
                    "gap_id": "gap_market_share_tracker",
                    "source_family": "public_source_context",
                    "gap_type": "commercial_tracker_gap",
                    "bounded_reason": "true market share needs commercial tracker",
                    "claim_boundary": "do_not_fill_with_generic_fallback_or_proxy_fact",
                }
            ],
        },
        "memo_answer": {"answer_status": "draft"},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "bounded rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "plan_reflection": {"status": "pass"},
        "evidence_fusion": {
            "schema_version": "sec_agent_evidence_fusion_bundle_v0.1",
            "public_exact_authority_violation_count": 0,
            "semantic_exact_authority_violation_count": 0,
        },
        "bounded_gap_register": {
            "schema_version": "sec_agent_bounded_gap_register_v0.1",
            "gap_count": 1,
            "commercial_tracker_gap_count": 1,
        },
        "milvus_runtime": {
            "status": "unavailable",
            "available": False,
            "location": "none",
            "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
            "fallback_routes": ["bm25", "object_bm25", "exact_value_ledger"],
        },
        "graph_barriers": {
            "claim_card_store": {"schema_version": "sec_agent_claim_card_store_barrier_v0.1"},
            "adjudicator": {"schema_version": "sec_agent_adjudicator_barrier_v0.1"},
            "specialist_fanout": {"schema_version": ""},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "pass"
    assert all(score["layer_checks"]["vnext_contract"].values())
    assert score["vnext_contract_audit"]["details"]["milvus_runtime_status"] == "unavailable"


def test_real_llm_chain_scoring_reports_plan_reflection_early_stop_without_hiding_lead_call() -> None:
    module = _load_script_module()
    case = {
        "case_id": "p33_plan_reflection_early_stop_unit",
        "category": "p33_gold_workpaper",
        "expected_execution_mode": "deep_research",
        "required_agents": ["research_lead", "universe_relationship", "memo_writer", "verifier", "renderer"],
        "memo_status_allowed": ["draft"],
        "require_lead_llm_pass": True,
        "require_plan_reflection_gate": True,
    }
    result = {
        "status": "failed",
        "loop_break_reason": "plan_reflection_gate_failed",
        "agent_activation_plan": {
            "execution_mode": "deep_research",
            "activate_agents": ["research_lead", "universe_relationship", "coverage_reflection", "memo_writer", "verifier", "renderer"],
            "allowed_source_families": ["relationship_graph"],
        },
        "agent_activation_validation": {"status": "pass"},
        "plan_reflection_report": {
            "schema_version": "sec_agent_plan_reflection_gate_v0.1",
            "status": "fail",
            "errors": [{"type": "milvus_semantic_requested_but_unavailable", "status": "unavailable"}],
            "warnings": [],
            "checked": {"allowed_source_families": ["milvus_semantic", "relationship_graph"]},
        },
        "research_lead_model_diagnostics": _ok_diag(),
        "memo_answer": {"answer_status": ""},
        "claim_verification": {"status": ""},
        "rendered_answer": "",
    }

    score = module.score_case(case, result, {"payload_policy": {"raw_evidence": "not_included"}}, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["layer_checks"]["research_lead"]["llm_invoked"] is True
    assert score["layer_checks"]["research_lead"]["llm_calls_ok"] is True
    assert score["layer_checks"]["vnext_contract"]["plan_reflection_pass"] is False
    assert score["vnext_contract_audit"]["required"] is True
    assert score["vnext_contract_audit"]["details"]["plan_reflection_status"] == "fail"
    assert score["plan_reflection_report"]["errors"][0]["type"] == "milvus_semantic_requested_but_unavailable"


def test_real_llm_chain_scoring_rejects_milvus_exact_authority_misuse() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_g11_milvus_exact_misuse",
        "category": "standard_memo",
        "expected_execution_mode": "standard_memo",
        "required_agents": ["research_lead", "sec_operator", "memo_writer", "verifier", "renderer"],
        "expected_operator_agents": ["sec_operator"],
        "expected_tool_names": ["sec_search_filings"],
        "memo_status_allowed": ["draft"],
        "require_vnext_contract": True,
        "require_milvus_runtime_contract": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "memo_writer", "verifier", "renderer"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {"records": [{"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "ok", "row_count": 2}]},
        "context_rows": [{"source_family": "milvus_semantic", "evidence_ref": "milvus_1", "exact_value_authority": True}],
        "bounded_gap_register": {"schema_version": "sec_agent_bounded_gap_register_v0.1", "gap_count": 0, "gaps": []},
        "memo_answer": {"answer_status": "draft"},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "bounded rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "plan_reflection": {"status": "pass"},
        "evidence_fusion": {
            "schema_version": "sec_agent_evidence_fusion_bundle_v0.1",
            "public_exact_authority_violation_count": 0,
            "semantic_exact_authority_violation_count": 1,
        },
        "bounded_gap_register": {"schema_version": "sec_agent_bounded_gap_register_v0.1", "gap_count": 0},
        "milvus_runtime": {
            "status": "cloud_available",
            "available": True,
            "location": "cloud",
            "claim_boundary": "semantic_recall_supplement_not_exact_value_authority",
            "fallback_routes": ["bm25", "object_bm25", "exact_value_ledger"],
        },
        "graph_barriers": {
            "claim_card_store": {"schema_version": "sec_agent_claim_card_store_barrier_v0.1"},
            "adjudicator": {"schema_version": "sec_agent_adjudicator_barrier_v0.1"},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "fail"
    assert score["checks"]["vnext_contract.source_boundary_violation_absent"] is False
    assert score["checks"]["vnext_contract.milvus_not_exact_value_authority"] is False


def test_exact_lookup_real_retrieval_accepts_structured_ledger_first_without_bge_rerank() -> None:
    module = _load_script_module()
    case = {
        "case_id": "fin_full_exact_unit",
        "category": "exact_lookup",
        "expected_execution_mode": "deterministic_lookup",
        "required_agents": ["sec_operator", "renderer"],
        "expected_operator_agents": ["sec_operator"],
        "expected_tool_names": ["sec_search_filings", "sec_query_exact_value_ledger"],
        "require_real_retrieval_pass": True,
        "require_runtime_ledger_rows": True,
        "max_tool_calls_total_lte": 2,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "deterministic_lookup",
            "activate_agents": ["sec_operator", "renderer"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
        },
        "agent_activation_validation": {"status": "pass"},
        "context_rows": [{"evidence_ref": "ctx_1"}],
        "runtime_ledger_rows": [{"metric_id": "m1", "source_family": "primary_sec_filing"}],
        "tool_call_ledger": {
            "records": [
                {
                    "agent_id": "sec_operator",
                    "tool_name": "sec_search_filings",
                    "status": "ok",
                    "row_count": 4,
                    "metadata": {
                        "runtime_summary": {
                            "candidate_counts": {
                                "candidate_row_count_pre_rerank": 4,
                                "candidate_sent_to_bge": 0,
                                "route_candidate_stats": [
                                    {"retrieval_route": "ledger_first", "candidate_count": 4, "rerank_eligible_count": 0}
                                ],
                            }
                        }
                    },
                }
            ]
        },
        "rendered_answer": "单指标结果：MSFT capex。证据=ctx_1",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["gate_status"] == "pass"
    assert score["checks"]["evidence_operators.sec_search_bge_rerank_present"] is True
    assert score["checks"]["evidence_operators.sec_search_runtime_ledger_rows_present"] is True


def test_real_llm_chain_tool_budget_excludes_cached_calls() -> None:
    module = _load_script_module()
    case = {
        "case_id": "cached_budget_unit",
        "category": "standard_memo",
        "expected_execution_mode": "standard_memo",
        "required_agents": ["research_lead", "sec_operator", "memo_writer", "renderer"],
        "expected_operator_agents": ["sec_operator"],
        "expected_tool_names": ["sec_search_filings"],
        "max_tool_calls_total_lte": 1,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["research_lead", "sec_operator", "memo_writer", "renderer"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "ok", "row_count": 2},
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "cached", "row_count": 2},
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "cached", "row_count": 2},
            ]
        },
        "memo_answer": {"answer_status": "draft"},
        "rendered_answer": "bounded answer",
    }
    summary = {"payload_policy": {"raw_evidence": "not_included"}}

    score = module.score_case(case, result, summary, {}, elapsed_ms=1)

    assert score["tool_call_count"] == 3
    assert score["budgeted_tool_call_count"] == 1
    assert score["cached_tool_call_count"] == 2
    assert score["checks"]["evidence_operators.tool_budget_lte"] is True


def test_multi_agent_real_llm_chain_scoring_rejects_memo_fallback_from_summary() -> None:
    module = _load_script_module()
    case = _read_jsonl(FIXTURE_PATH)[0]
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
            ]
        },
        "memo_answer": {"answer_status": "draft", "bounded_answer_allowed": False},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "fallback rendered answer",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"route_result": {"status": "fallback"}, "diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "fail"
    assert score["checks"]["memo_verifier.memo_llm_pass"] is False


def test_multi_agent_real_llm_chain_scoring_requires_rendered_claim_refs_when_configured() -> None:
    module = _load_script_module()
    case = {
        **_read_jsonl(FIXTURE_PATH)[0],
        "require_rendered_memo_claims": True,
        "require_rendered_evidence_refs": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "focused_answer",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "coverage_reflection",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["AMZN"],
            "search_scope_tickers": ["AMZN"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "dry_run", "row_count": 1},
            ]
        },
        "memo_answer": {
            "answer_status": "draft",
            "bounded_answer_allowed": False,
            "memo_claims": [{"claim": "Supported claim.", "evidence_refs": ["ref_1"]}],
        },
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "Supported claim without rendered refs.",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "fail"
    assert score["checks"]["memo_verifier.rendered_answer_has_memo_claims"] is False
    assert score["checks"]["memo_verifier.rendered_answer_has_evidence_refs"] is False


def test_real_llm_chain_scoring_accepts_chinese_rendered_claim_refs_and_language() -> None:
    module = _load_script_module()
    case = {
        **_read_jsonl(FULL_CHAIN_MULTITURN_FIXTURE_PATH)[4],
        "require_rendered_memo_claims": True,
        "require_rendered_evidence_refs": True,
        "require_response_language_match": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": [
                "research_lead",
                "sec_operator",
                "eight_k_operator",
                "market_operator",
                "coverage_reflection",
                "fundamental_analyst",
                "market_valuation_analyst",
                "risk_counterevidence_analyst",
                "memo_writer",
                "verifier",
                "renderer",
            ],
            "focus_tickers": ["NVDA", "AMD"],
            "search_scope_tickers": ["NVDA", "AMD"],
        },
        "agent_activation_validation": {"status": "pass"},
        "tool_call_ledger": {
            "records": [
                {"agent_id": "sec_operator", "tool_name": "sec_search_filings", "status": "completed", "row_count": 2},
                {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "completed", "row_count": 1},
                {"agent_id": "market_operator", "tool_name": "market_get_snapshot", "status": "completed", "row_count": 1},
            ]
        },
        "specialist_route_results": [
            {"agent_id": "fundamental_analyst", "status": "pass"},
            {"agent_id": "market_valuation_analyst", "status": "pass"},
            {"agent_id": "risk_counterevidence_analyst", "status": "pass"},
        ],
        "specialist_verification": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "response_language": {"language": "zh-CN"},
            "memo_claims": [{"claim": "中文支持性论据。", "evidence_refs": ["ref_1"]}],
        },
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {"status": "pass"},
        "rendered_answer": "这是中文投研结论，包含足够中文正文用于语言门控，并说明基本面、市场反应、估值风险和证据边界都已经被综合。关键论据:\n1. 中文支持性论据。 [C1]\n\n证据索引:\n- [C1] ref 1",
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "specialist": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "pass"
    assert score["checks"]["memo_verifier.rendered_answer_has_memo_claims"] is True
    assert score["checks"]["memo_verifier.rendered_answer_has_evidence_refs"] is True
    assert score["checks"]["memo_verifier.response_language_matches_query"] is True
    assert score["checks"]["memo_verifier.rendered_user_language_ok"] is True


def test_real_llm_chain_surface_gate_rejects_internal_renderer_dump() -> None:
    module = _load_script_module()
    case = {
        **_read_jsonl(FULL_CHAIN_MULTITURN_FIXTURE_PATH)[4],
        "require_rendered_memo_claims": True,
        "require_rendered_evidence_refs": True,
        "require_response_language_match": True,
        "require_dimension_memo_surface": True,
    }
    result = {
        "status": "completed",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": [
                "research_lead",
                "fundamental_analyst",
                "memo_writer",
                "verifier",
                "renderer",
            ],
        },
        "agent_activation_validation": {"status": "pass"},
        "specialist_route_results": [{"agent_id": "fundamental_analyst", "status": "pass"}],
        "specialist_verification": {"status": "pass"},
        "memo_answer": {
            "answer_status": "draft",
            "response_language": {"language": "zh-CN"},
            "memo_claims": [{"claim": "中文支持性论据。", "evidence_refs": ["ref_1"]}],
            "dimension_analyses": [{"dimension_id": "fundamentals", "summary": "中文分析", "evidence_refs": ["ref_1"]}],
        },
        "memo_route_result": {"status": "pass", "attempt_count": 1},
        "claim_verification": {"status": "pass"},
        "rendered_answer": (
            "核心判断:\n这是中文投研结论，中文长度足够用于语言门控。\n\n"
            "分维度分析:\n1. 基本面：中文分析 | 机制：Bridge the claim through revenue | 财务桥：margin "
            "证据=INTERACTIVE_MSFT_2026_10K::MSFT::2026\n\n"
            "关键论据:\n1. 中文支持性论据。 证据=ref_1"
        ),
    }
    summary = {
        "payload_policy": {"raw_evidence": "not_included"},
        "llm_routes": {
            "research_lead": {"diagnostics": _ok_diag()},
            "specialist": {"diagnostics": _ok_diag()},
            "memo_writer": {"diagnostics": _ok_diag()},
            "verifier": {"diagnostics": _ok_diag()},
        },
    }

    score = module.score_case(case, result, summary, {}, elapsed_ms=12)

    assert score["gate_status"] == "fail"
    assert score["checks"]["memo_verifier.surface_readability_pass"] is False
    assert score["checks"]["memo_verifier.surface.no_internal_field_labels"] is False
    assert score["checks"]["memo_verifier.surface.no_raw_interactive_refs"] is False


def test_real_llm_chain_specialist_quality_requires_industry_relationship_ref_for_sector_depth() -> None:
    module = _load_script_module()
    case = {
        "case_id": "sector_relationship_gate",
        "category": "sector_depth",
        "source_tiers": ["industry_snapshot", "relationship_graph"],
        "expected_tool_names": ["relationship_graph_lookup"],
    }
    result = {
        "specialist_route_results": [{"agent_id": "industry_supply_chain_analyst", "status": "pass"}],
        "specialist_outputs": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Industry-only output.",
                "observations": [
                    {
                        "claim": "Power demand is relevant context.",
                        "claim_type": "industry_context_only",
                        "evidence_refs": ["industry_ref"],
                        "source_families": ["industry_snapshot"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "industry_snapshot_rows": [
            {"evidence_ref": "industry_ref", "source_family": "industry_snapshot", "summary": "Power demand context."}
        ],
        "universe_relationship_plan": {
            "relationships": [
                {
                    "ticker": "SRE",
                    "related_ticker": "XEL",
                    "relationship_type": "peer",
                    "evidence_refs": ["rel_ref"],
                    "inclusion_rationale": "Utilities relationship hypothesis.",
                }
            ]
        },
    }

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is False
    assert detail["relationship_gate_required"] is True
    assert detail["checks"]["relationship_input_present_when_required"] is True
    assert detail["checks"]["relationship_evidence_ref_cited_when_required"] is False


def test_real_llm_chain_industry_supply_chain_accepts_public_product_context_sources() -> None:
    module = _load_script_module()
    case = {
        "case_id": "industry_public_product_context",
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"DELL": 2},
                    "by_source_family": {"public_source_context": 1, "company_product_evidence_graph": 1},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Official customer and product context support bounded supply-chain readthrough.",
                "observations": [
                    {
                        "claim": "DELL has official customer deployment context tied to AI infrastructure demand.",
                        "claim_type": "industry_context_only",
                        "evidence_refs": ["public_deploy_ref", "product_graph_ref"],
                        "source_families": ["public_source_context", "company_product_evidence_graph"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "public_source_context_rows": [
            {
                "ticker": "DELL",
                "evidence_ref": "public_deploy_ref",
                "source_family": "public_source_context",
                "structured_context_type": "official_customer_deployment_context",
                "claim_boundary": "context_only_no_revenue_or_backlog_inference",
            }
        ],
        "product_evidence_rows": [
            {
                "ticker": "DELL",
                "evidence_ref": "product_graph_ref",
                "source_family": "company_product_evidence_graph",
                "relationship_type": "deployed_by",
                "promotion_status": "runtime_context_taxonomy_only",
                "claim_boundary": "product_relationship_context_only",
            }
        ],
    }

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is True
    assert detail["checks"]["bounded_row_source_family_owned"] is True
    assert detail["checks"]["observation_source_family_owned"] is True
    assert detail["input_source_families"] == ["company_product_evidence_graph", "public_source_context"]


def test_real_llm_chain_fundamental_accepts_owned_derived_metric_layer() -> None:
    module = _load_script_module()
    case = {"case_id": "fundamental_derived_metric_layer", "category": "sector_depth"}
    result = {
        "specialist_route_results": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"DELL": 1},
                    "by_source_family": {"derived_metric_layer": 1},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Derived filing metric supports a bounded margin-change observation.",
                "observations": [
                    {
                        "claim": "DELL product gross margin declined by 8 percentage points.",
                        "claim_type": "financial_metric_observation",
                        "evidence_refs": ["derived_margin_pp"],
                        "source_families": ["derived_metric_layer"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "derived_metric_layer": {
            "derived_metrics": [
                {
                    "derived_metric_id": "derived_margin_pp",
                    "ticker": "DELL",
                    "evidence_ref": "derived_margin_pp",
                    "source_family": "derived_metric_layer",
                    "derived_metric_family": "yoy_change_pp",
                    "input_evidence_refs": ["sec_current", "sec_prior"],
                    "value": "-8",
                    "unit": "percentage_points",
                }
            ]
        },
    }

    quality = module._specialist_real_evidence_quality(case, result, {"fundamental_analyst"}, required=True)
    detail = quality["details"]["fundamental_analyst"]

    assert quality["quality_pass"] is True
    assert detail["checks"]["observation_source_family_owned"] is True


def test_real_llm_chain_relationship_pack_gate_rejects_off_sector_citation_without_cross_sector_prompt() -> None:
    module = _load_script_module()
    case = {
        "case_id": "sector_pack_gate",
        "category": "sector_depth",
        "prompt": "用 energy infrastructure 和 real estate utilities sector-depth packs 分析电力负荷和利率背景。",
        "source_tiers": ["industry_snapshot", "relationship_graph"],
        "expected_tool_names": ["relationship_graph_lookup"],
        "expected_relationship_pack_ids": ["energy_infrastructure_depth", "real_estate_utilities_depth"],
        "allowed_cross_sector_relationship_pack_ids": ["technology_ai_infrastructure_depth"],
    }
    result = _industry_relationship_result(
        "sector_depth_pack:technology_ai_infrastructure_depth:VRT",
        "AI infrastructure power readthrough.",
        extra_relationship_refs=["sector_depth_pack:real_estate_utilities_depth:XEL"],
    )

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is False
    assert detail["relationship_pack_gate_required"] is True
    assert detail["cross_sector_relationship_query_allowed"] is False
    assert detail["relationship_pack_ids_cited"] == ["technology_ai_infrastructure_depth"]
    assert detail["checks"]["relationship_available_pack_relevance_when_required"] is False
    assert detail["checks"]["relationship_cited_pack_relevance_when_required"] is False


def test_real_llm_chain_relationship_pack_gate_allows_explicit_ai_power_transmission() -> None:
    module = _load_script_module()
    case = {
        "case_id": "sector_pack_cross_sector_allowed",
        "category": "sector_depth",
        "prompt": "分析 utilities 的 data center power load 和 AI infrastructure demand transmission。",
        "source_tiers": ["industry_snapshot", "relationship_graph"],
        "expected_tool_names": ["relationship_graph_lookup"],
        "expected_relationship_pack_ids": ["real_estate_utilities_depth"],
        "allowed_cross_sector_relationship_pack_ids": ["technology_ai_infrastructure_depth"],
    }
    result = _industry_relationship_result(
        "sector_depth_pack:technology_ai_infrastructure_depth:VRT",
        "AI infrastructure power readthrough.",
        extra_relationship_refs=["sector_depth_pack:real_estate_utilities_depth:XEL"],
    )

    quality = module._specialist_real_evidence_quality(
        case,
        result,
        {"industry_supply_chain_analyst"},
        required=True,
    )
    detail = quality["details"]["industry_supply_chain_analyst"]

    assert quality["quality_pass"] is True
    assert detail["cross_sector_relationship_query_allowed"] is True
    assert detail["effective_allowed_relationship_pack_ids"] == [
        "real_estate_utilities_depth",
        "technology_ai_infrastructure_depth",
    ]
    assert detail["checks"]["relationship_cited_pack_relevance_when_required"] is True


def test_real_llm_chain_specialist_quality_requires_comparative_primary_rows_or_gap() -> None:
    module = _load_script_module()
    case = {
        "case_id": "comparative_primary_gate",
        "focus_tickers": ["NVDA", "AMD"],
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "prompt_row_distribution": {"by_ticker": {"AMD": 1}, "by_source_family": {"primary_sec_filing": 1}},
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "AMD-only output.",
                "observations": [
                    {
                        "claim": "AMD has bounded revenue evidence.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["AMD"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "fundamentals",
                        "evidence_refs": ["amd_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {"metric_id": "amd_ref", "source_family": "primary_sec_filing", "ticker": "AMD", "metric": "revenue"}
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"fundamental_analyst"}, required=True)
    detail = quality["details"]["fundamental_analyst"]

    assert quality["quality_pass"] is False
    assert detail["comparative_primary_gate_required"] is True
    assert detail["focus_ticker_primary_missing"] == ["NVDA"]
    assert detail["checks"]["comparative_focus_ticker_primary_visible_or_gap"] is False


def test_real_llm_chain_specialist_quality_accepts_route_coverage_source_gap() -> None:
    module = _load_script_module()
    case = {
        "case_id": "comparative_primary_route_gap_gate",
        "focus_tickers": ["ASML", "AMAT"],
        "category": "sector_depth",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"AMAT": 1},
                    "by_source_family": {"primary_sec_filing": 1},
                },
                "input_coverage_summary": {
                    "focus_ticker_primary_row_counts": {"ASML": 0, "AMAT": 1},
                    "focus_ticker_source_gap_reasons": {
                        "ASML": ["not_in_manifest_for_mcp_route_scope"],
                    },
                    "coverage_policy": "comparative_focus_tickers_must_have_visible_primary_rows_or_ticker_source_gap",
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "AMAT primary evidence and ASML bounded source gap.",
                "observations": [
                    {
                        "claim": "AMAT has bounded revenue evidence, while ASML is a source-gap ticker for primary SEC rows.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["AMAT", "ASML"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "fundamentals",
                        "evidence_refs": ["amat_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {"metric_id": "amat_ref", "source_family": "primary_sec_filing", "ticker": "AMAT", "metric": "revenue"}
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"fundamental_analyst"}, required=True)
    detail = quality["details"]["fundamental_analyst"]

    assert quality["quality_pass"] is True
    assert detail["checks"]["comparative_focus_ticker_primary_visible_or_gap"] is True
    assert detail["focus_ticker_primary_source_gaps"] == ["ASML"]
    assert detail["focus_ticker_primary_source_gap_reasons"] == {"ASML": ["not_in_manifest_for_mcp_route_scope"]}
    assert detail["focus_ticker_primary_missing"] == []


def test_real_llm_chain_specialist_quality_rejects_single_ref_temporal_inference() -> None:
    module = _load_script_module()
    case = {
        "case_id": "temporal_ref_depth_gate",
        "focus_tickers": ["NVDA", "AMD"],
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"NVDA": 1, "AMD": 1},
                    "by_source_family": {"primary_sec_filing": 2},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Risk output.",
                "observations": [
                    {
                        "claim": "NVDA revenue implies a sequential decline from prior quarters.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "risk_counterevidence",
                        "evidence_refs": ["nvda_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {"metric_id": "nvda_ref", "source_family": "primary_sec_filing", "ticker": "NVDA", "metric": "revenue"},
            {"metric_id": "amd_ref", "source_family": "primary_sec_filing", "ticker": "AMD", "metric": "revenue"},
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"risk_counterevidence_analyst"}, required=True)
    detail = quality["details"]["risk_counterevidence_analyst"]

    assert quality["quality_pass"] is False
    assert detail["checks"]["temporal_claim_ref_depth_valid"] is False
    assert detail["temporal_claim_ref_depth_failures"]


def test_real_llm_chain_exact_lookup_accepts_runtime_ledger_as_real_retrieval() -> None:
    module = _load_script_module()
    case = {
        "case_id": "exact_lookup_ledger_gate",
        "category": "exact_lookup",
        "expected_execution_mode": "deterministic_lookup",
        "expected_tool_names": ["sec_search_filings", "sec_query_exact_value_ledger"],
        "require_real_retrieval_pass": True,
        "require_runtime_ledger_rows": True,
    }
    result = {
        "runtime_ledger_rows": [
            {
                "metric_id": "MSFT_CAPEX",
                "source_family": "primary_sec_filing",
                "ticker": "MSFT",
                "metric_family": "capital_expenditure_proxy",
            }
        ],
    }
    tool_calls = [
        {
            "agent_id": "sec_operator",
            "tool_name": "sec_query_exact_value_ledger",
            "status": "completed",
            "row_count": 1,
        }
    ]

    checks = module._real_operator_checks(case, result, tool_calls, required=True)

    assert checks["sec_search_not_dry_run"] is True
    assert checks["sec_search_context_rows_present"] is True
    assert checks["sec_search_bm25_candidates_present"] is True
    assert checks["sec_search_bge_rerank_present"] is True
    assert checks["sec_search_runtime_ledger_rows_present"] is True


def test_real_operator_checks_treat_source_gap_as_coverage_gap_not_runtime_error() -> None:
    module = _load_script_module()
    case = {
        "case_id": "source_gap_sec_scope",
        "expected_tool_names": ["sec_search_filings"],
        "require_real_retrieval_pass": True,
    }
    result = {
        "context_rows": [{"evidence_ref": "AMAT_2026_8K"}],
        "runtime_ledger_rows": [],
    }
    tool_calls = [
        {"agent_id": "eight_k_operator", "tool_name": "sec_search_filings", "status": "ok", "row_count": 4},
        {
            "agent_id": "eight_k_operator",
            "tool_name": "sec_search_filings",
            "status": "source_gap",
            "row_count": 0,
            "source_gap_count": 1,
            "error": "not_in_manifest_for_mcp_route_scope",
        },
    ]

    checks = module._real_operator_checks(case, result, tool_calls, required=True)

    assert checks["sec_search_not_dry_run"] is True
    assert checks["sec_search_errors_absent"] is True
    assert checks["sec_search_context_rows_present"] is True


def test_real_llm_chain_specialist_quality_allows_single_ref_yoy_row_with_raw_value() -> None:
    module = _load_script_module()
    case = {
        "case_id": "temporal_single_row_yoy_gate",
        "focus_tickers": ["JPM", "C"],
        "category": "sector_depth",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"JPM": 1, "C": 1},
                    "by_source_family": {"company_authored_unaudited_sec_filing": 2},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Fundamental output.",
                "observations": [
                    {
                        "claim": "JPM reported 1Q26 net revenue of $23.4 billion, up 19% YoY.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["JPM"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "fundamentals",
                        "evidence_refs": ["jpm_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "context_rows": [
                {
                    "evidence_ref": "jpm_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "JPM",
                    "metric": "net revenue",
                    "raw_value_text": "$23.4 billion, up 19% YoY",
                },
                {
                    "evidence_ref": "c_ref",
                    "source_family": "primary_sec_filing",
                    "ticker": "C",
                    "metric": "revenue",
                },
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"fundamental_analyst"}, required=True)
    detail = quality["details"]["fundamental_analyst"]

    assert detail["checks"]["temporal_claim_ref_depth_valid"] is True


def test_real_llm_chain_specialist_quality_does_not_treat_growth_from_sector_as_temporal() -> None:
    module = _load_script_module()

    assert (
        module._looks_like_temporal_inference(
            "NEE storm cost recovery may mask underlying demand-driven growth from AI data centers."
        )
        is False
    )


def test_real_llm_chain_specialist_quality_allows_self_comparative_single_row() -> None:
    module = _load_script_module()
    case = {
        "case_id": "temporal_self_comparative_gate",
        "focus_tickers": ["CVX", "XOM"],
        "category": "standard_memo",
    }
    result = {
        "specialist_route_results": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"CVX": 1, "XOM": 1},
                    "by_source_family": {"primary_sec_filing": 2},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Risk output.",
                "observations": [
                    {
                        "claim": "CVX capex rose 4% YoY to $16.4B.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["CVX"],
                        "metric_scope": ["capex"],
                        "memo_slot": "risk_counterevidence",
                        "evidence_refs": ["cvx_ref"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "runtime_ledger_rows": [
            {
                "metric_id": "cvx_ref",
                "source_family": "primary_sec_filing",
                "ticker": "CVX",
                "metric": "capex",
                "summary": "Capex for 2024 was $16.4 billion, 4 percent higher than 2023.",
            },
            {"metric_id": "xom_ref", "source_family": "primary_sec_filing", "ticker": "XOM", "metric": "capex"},
        ],
    }

    quality = module._specialist_real_evidence_quality(case, result, {"risk_counterevidence_analyst"}, required=True)
    detail = quality["details"]["risk_counterevidence_analyst"]

    assert detail["checks"]["temporal_claim_ref_depth_valid"] is True


def _industry_relationship_result(
    evidence_ref: str,
    rationale: str,
    *,
    extra_relationship_refs: list[str] | None = None,
) -> dict:
    relationships = [
        {
            "ticker": "SRE",
            "related_ticker": "VRT",
            "relationship_type": "sector",
            "evidence_refs": [evidence_ref],
            "inclusion_rationale": rationale,
            "claim_scope": "scope_or_hypothesis_only",
        }
    ]
    for index, ref in enumerate(extra_relationship_refs or [], start=1):
        relationships.append(
            {
                "ticker": "SRE",
                "related_ticker": f"REL{index}",
                "relationship_type": "sector",
                "evidence_refs": [ref],
                "inclusion_rationale": "Expected sector relationship context.",
                "claim_scope": "scope_or_hypothesis_only",
            }
        )
    return {
        "specialist_route_results": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "prompt_row_distribution": {
                    "by_ticker": {"SRE": 1},
                    "by_source_family": {"relationship_graph": 1},
                },
            }
        ],
        "specialist_outputs": [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "pass",
                "evidence_boundary": "bounded_rows_only",
                "summary": "Relationship-cited output.",
                "observations": [
                    {
                        "claim": "The cited relationship evidence is relevant.",
                        "claim_type": "relationship_hypothesis",
                        "evidence_refs": [evidence_ref],
                        "source_families": ["relationship_graph"],
                        "confidence": "medium",
                        "unsupported": False,
                    }
                ],
                "unsupported_claims": [],
                "conflicts": [],
            }
        ],
        "universe_relationship_plan": {"relationships": relationships},
    }


def _ok_diag() -> dict:
    return {
        "call_count": 1,
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "latency_ms": 100,
        "total_tokens": 1000,
        "finish_reasons": ["stop"],
        "all_calls_ok": True,
        "direct_tool_call_count": 0,
        "raw_response_saved": False,
    }


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_script_module():
    spec = importlib.util.spec_from_file_location("eval_multi_agent_real_llm_chain_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
