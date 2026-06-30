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

    expected = Path("data") / "workbench_private" / "run_audit" / "unit_audit_default.sqlite"
    assert state["run_audit_db_path"] == str(expected)
    assert state["multi_agent_context"]["run_audit_db_path"] == str(expected)


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
