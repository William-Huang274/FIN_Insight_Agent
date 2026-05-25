from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from connectors import SecEdgarConnector, SecEdgarConnectorError, SecFilingManifestRecord  # noqa: E402
from evidence import build_evidence_from_chunks  # noqa: E402
from evidence.schema import EvidenceObject  # noqa: E402
from ingestion import build_8k_earnings_chunks  # noqa: E402
from sec_agent.query_contract import validate_query_contract  # noqa: E402
from sec_agent.project_inventory import build_project_inventory  # noqa: E402
from sec_agent.tool_harness import SecAgentToolHarness  # noqa: E402
from sec_agent.context_api import _default_source_policy  # noqa: E402


def _load_8k_manifest_module():
    path = REPO_ROOT / "scripts" / "build_sec_8k_earnings_manifest.py"
    spec = importlib.util.spec_from_file_location("build_sec_8k_earnings_manifest_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_8k_downloader_module():
    path = REPO_ROOT / "scripts" / "download_sec_8k_earnings.py"
    spec = importlib.util.spec_from_file_location("download_sec_8k_earnings_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_source_gap_merge_module():
    path = REPO_ROOT / "scripts" / "merge_sec_source_gaps.py"
    spec = importlib.util.spec_from_file_location("merge_sec_source_gaps_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_benchmark_eval_module():
    path = REPO_ROOT / "scripts" / "run_sec_benchmark_eval.py"
    spec = importlib.util.spec_from_file_location("run_sec_benchmark_eval_8k_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_context_session_cli_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_context_session_cli.py"
    spec = importlib.util.spec_from_file_location("sec_agent_context_session_cli_8k_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_8k_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_synthesis_module():
    path = REPO_ROOT / "scripts" / "run_sec_eval_synthesis_qwen9b_backend.py"
    scripts_root = str(REPO_ROOT / "scripts")
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    spec = importlib.util.spec_from_file_location("sec_agent_synthesis_8k_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_answer_ledger_validator_module():
    path = REPO_ROOT / "scripts" / "validate_sec_benchmark_answer_ledger.py"
    spec = importlib.util.spec_from_file_location("answer_ledger_validator_8k_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_object_accepts_8k_earnings_source_tier() -> None:
    evidence = EvidenceObject(
        evidence_id="8K_EARNINGS::MSFT::000000::EX99_1::0001",
        source_type="8-K",
        source_tier="company_authored_unaudited_sec_filing",
        ticker="MSFT",
        fiscal_year=2026,
        evidence_type="management_commentary",
        text="Microsoft reported quarterly results in an earnings release.",
    )

    assert evidence.source_tier == "company_authored_unaudited_sec_filing"
    assert evidence.source_type == "8-K"


def test_query_contract_recognizes_mixed_with_8k_earnings_policy() -> None:
    inventory = {
        "inventory_digest": "inv-8k",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "mega-cap software/cloud",
                "filings": [
                    {"year": 2025, "form_type": "10-K", "source_tier": "primary_sec_filing"},
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {
                        "year": 2026,
                        "form_type": "8-K",
                        "source_tier": "company_authored_unaudited_sec_filing",
                    },
                ],
            }
        ],
        "categories": [{"category": "mega-cap software/cloud", "tickers": ["MSFT"]}],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_management_commentary",
                "question_zh": "Use 10-Q values and 8-K earnings release commentary.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    result = validate_query_contract(
        contract,
        selected_tickers=["MSFT"],
        selected_years=[2025, 2026],
        project_inventory=inventory,
    )
    clean = result["contract"]

    assert clean["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert clean["source_tiers"] == ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    assert any("8-K earnings-release evidence" in caveat for caveat in clean["required_caveats"])
    assert clean["source_coverage_gaps"] == []
    assert result["report"]["status"] == "pass"


def test_context_and_harness_accept_mixed_with_8k_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS")

    assert _default_source_policy() == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"

    harness = SecAgentToolHarness(session_root=tmp_path)
    result = harness.start_memo_analysis(
        query="结合MSFT最新10-Q和8-K业绩新闻稿解释云业务表现",
        user_id="u1",
        tenant_id="t1",
        session_id="s1",
        source_policy="SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        execute=False,
    )

    assert result.status == "planned"
    session_path = tmp_path / "s1" / "session_state.json"
    assert session_path.exists()
    assert "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS" in session_path.read_text(encoding="utf-8")


def test_runtime_case_adds_8k_source_boundary_gate() -> None:
    interactive = _load_interactive_module()
    case = interactive._build_case(
        "结合10-Q和8-K业绩新闻稿解释MSFT云业务表现",
        ["MSFT"],
        [2026],
        "run_8k",
        {
            "task_type": "general_sec_financial_question",
            "focus_tickers": ["MSFT"],
            "filing_types": ["10-K", "10-Q", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "required_caveats": [
                "8-K earnings-release evidence is company-authored unaudited management material."
            ],
        },
    )

    assert "Label 8-K earnings-release evidence as company-authored unaudited material." in case["gold_points"]
    assert any("Use retrieved 8-K earnings-release evidence as qualitative support" in point for point in case["gold_points"])
    assert any("Do not treat company-authored 8-K" in trap for trap in case["hallucination_traps"])
    assert case["required_caveats"][0]["required"] is True


def test_planner_prompt_uses_compact_json_contract() -> None:
    interactive = _load_interactive_module()
    prompt = interactive._query_planner_system_prompt(
        {
            "inventory_digest": "inv",
            "companies": [],
            "categories": [],
            "form_types": {"10-Q": 1, "8-K": 1},
        },
        ["GE", "PG", "TXN"],
        [2026],
    )

    assert '  "evidence_gaps"' not in prompt
    assert "不要输出 evidence_gaps" in prompt
    assert "最多 5 个任务" in prompt
    assert "不超过 80 字" in prompt


def test_planner_normalization_limits_tasks_and_field_lengths() -> None:
    interactive = _load_interactive_module()
    inventory = {
        "inventory_digest": "inv-compact",
        "companies": [
            {
                "ticker": "GE",
                "company": "GE",
                "filings": [
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {"year": 2026, "form_type": "8-K", "source_tier": "company_authored_unaudited_sec_filing"},
                ],
            }
        ],
        "categories": [],
    }
    fallback = {
        "task_type": "company_comparison",
        "search_scope_tickers": ["GE"],
        "focus_tickers": ["GE"],
        "years": [2026],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["revenue"],
        "decomposed_tasks": [],
        "required_caveats": [],
        "forbidden_claims": [],
    }
    planned = {
        **fallback,
        "decomposed_tasks": [
            {
                "task_id": f"task_{idx}",
                "question_zh": "这是一条很长的 planner 任务问题，用来验证输出契约会被截断到固定长度并避免接近 token 上限。" * 3,
                "priority": "primary",
                "required_tickers": ["GE"],
                "required_metric_families": ["revenue"],
            }
            for idx in range(8)
        ],
        "required_caveats": ["长 caveat " * 80 for _ in range(8)],
        "forbidden_claims": ["长 forbidden " * 80 for _ in range(8)],
        "evidence_gaps": [{"task_id": "gap", "gap": "gap text " * 80} for _ in range(8)],
    }

    clean = interactive._normalize_llm_query_contract(planned, fallback, ["GE"], [2026], inventory)
    clean = interactive._apply_planner_output_limits(clean)

    assert len(clean["decomposed_tasks"]) == 5
    assert all(len(task["question_zh"]) <= 80 for task in clean["decomposed_tasks"])
    assert len(clean["required_caveats"]) <= 6
    assert all(len(item) <= 120 for item in clean["required_caveats"])
    assert len(clean["forbidden_claims"]) <= 6
    assert all(len(item) <= 120 for item in clean["forbidden_claims"])
    assert len(clean["evidence_gaps"]) <= 4


def test_planner_retries_length_truncated_json_before_fallback(monkeypatch) -> None:
    interactive = _load_interactive_module()
    monkeypatch.setenv("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS")
    monkeypatch.setattr(interactive, "_ensure_llm_ready", lambda args: None)
    calls: list[int | None] = []

    def fake_planner(args, prompt, tickers, years, project_inventory, fallback, *, max_tokens=None, retry_reason=""):
        calls.append(max_tokens)
        if len(calls) == 1:
            return (
                '{"schema_version":"interactive_query_contract_planner_v0.1","task_type":"company_comparison",'
                '"focus_tickers":["GE"],"years":[2026],"decomposed_tasks":[',
                {
                    "status": "ok",
                    "finish_reason": "length",
                    "output_tokens": 100,
                    "trace_tags": {"requested_max_tokens": 100},
                },
            )
        return (
            json.dumps(
                {
                    "schema_version": "interactive_query_contract_planner_v0.1",
                    "rewritten_question_zh": "比较GE最新10-Q和8-K业绩驱动。",
                    "task_type": "company_comparison",
                    "focus_tickers": ["GE"],
                    "years": [2026],
                    "filing_types": ["10-Q", "8-K"],
                    "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                    "facets": ["revenue", "management_discussion"],
                    "metric_families": ["revenue"],
                    "decomposed_tasks": [
                        {
                            "task_id": "ge_latest_drivers",
                            "question_zh": "比较GE最新季度业绩驱动和8-K管理层解释。",
                            "priority": "primary",
                            "required_tickers": ["GE"],
                            "peer_tickers": [],
                            "required_metric_families": ["revenue"],
                        }
                    ],
                    "required_caveats": ["8-K为公司未审计管理层口径。"],
                    "forbidden_claims": ["不要使用市场价格或分析师预期。"],
                    "planner_confidence": "high",
                },
                ensure_ascii=False,
            ),
            {
                "status": "ok",
                "finish_reason": "stop",
                "output_tokens": 120,
                "trace_tags": {"requested_max_tokens": 300},
            },
        )

    monkeypatch.setattr(interactive, "_ask_query_contract_planner", fake_planner)
    args = SimpleNamespace(
        query_planner="llm",
        llm_backend="deepseek",
        model="deepseek-v4-pro",
        planner_max_tokens=100,
        planner_retry_max_tokens=300,
        planner_timeout_s=180,
        planner_fail_closed=True,
        quiet=True,
    )
    inventory = {
        "inventory_digest": "inv-retry",
        "companies": [
            {
                "ticker": "GE",
                "company": "GE",
                "filings": [
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {"year": 2026, "form_type": "8-K", "source_tier": "company_authored_unaudited_sec_filing"},
                ],
            }
        ],
        "categories": [],
    }

    contract = interactive._build_query_contract(args, "比较GE最新10-Q和8-K业绩驱动", ["GE"], [2026], inventory)
    trace = contract["_planner_trace"]

    assert calls == [None, 300]
    assert contract["planner_status"] == "ok"
    assert trace["status"] == "parsed_after_length_retry"
    assert trace["retry"]["parse_status"] == "parsed"


def test_full30_8k_earnings_config_covers_entire_company_universe() -> None:
    downloader = _load_8k_downloader_module()
    config = downloader.load_config(REPO_ROOT / "configs" / "sec_tech_8k_earnings_full30_2026_2027.yaml")
    tickers = [str(company.get("ticker") or "").upper() for company in config.get("companies") or []]

    assert config["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert config["source_tier"] == "company_authored_unaudited_sec_filing"
    assert config["years"] == [2026, 2027]
    assert len(tickers) == 30
    assert len(set(tickers)) == 30
    assert {"MSFT", "AMZN", "NVDA", "JPM", "CVX"}.issubset(set(tickers))


def test_synthesis_preserves_cited_8k_earnings_release_numbers() -> None:
    synthesis = _load_synthesis_module()
    eight_k_id = "8K_EARNINGS::MSFT::000119312526191457::MSFTEX991HTM::BLOCK_0001::CHUNK_0001"
    answer = {
        "direct_answer": "微软云表现强，但 8-K 数字只能作为未审计管理层材料。",
        "investment_thesis": "10-Q ledger 和 8-K 管理层材料共同指向云业务仍在增长。",
        "what_changed": [
            {
                "claim": "8-K earnings release 显示 Microsoft Cloud revenue was $46.7 billion and Azure grew 39%，该数字来自公司未审计管理层材料。",
                "metric_ids": [],
                "evidence_ids": [eight_k_id],
                "confidence": "medium",
            }
        ],
        "source_limitations": ["8-K earnings release is company-authored unaudited management material."],
    }
    context_rows = [
        {
            "evidence_id": eight_k_id,
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "text": "Microsoft Cloud revenue was $46.7 billion and Azure and other cloud services revenue grew 39%.",
        }
    ]

    normalized = synthesis._normalize_answer(
        answer,
        ledger_rows=[
            {
                "metric_id": "MSFT_2026_10Q_CLOUD_REVENUE",
                "value": 46700.0,
                "unit": "usd_millions",
                "display_value_zh": "46,700（百万美元）",
            }
        ],
        context_rows=context_rows,
        case={
            "query_contract": {
                "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            }
        },
    )

    payload = json.dumps(normalized, ensure_ascii=False)
    assert "$46.7 billion" in payload
    assert "39%" in payload
    assert "相应披露金额" not in payload
    assert "相应披露比例" not in payload
    assert normalized["_qwen_output_status"] == "valid_json"
    assert normalized["_ledger_text_contract_sanitized_count"] == 0


def test_synthesis_rejects_uncited_8k_numbers_from_primary_evidence() -> None:
    synthesis = _load_synthesis_module()
    primary_id = "MSFT_2026_10Q_ITEM2_BLOCK_0001_PART_01_OF_01"
    answer = {
        "direct_answer": "微软云表现强。",
        "investment_thesis": "10-Q evidence supports a conservative read.",
        "what_changed": [
            {
                "claim": "Azure grew 39%，但该数字没有被当前引用的 10-Q evidence 支撑。",
                "metric_ids": [],
                "evidence_ids": [primary_id],
                "confidence": "medium",
            }
        ],
    }
    context_rows = [
        {
            "evidence_id": primary_id,
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "text": "Microsoft discusses cloud demand without disclosing Azure growth percentage in this excerpt.",
        }
    ]

    normalized = synthesis._normalize_answer(
        answer,
        ledger_rows=[
            {
                "metric_id": "MSFT_2026_10Q_CLOUD_REVENUE",
                "value": 46700.0,
                "unit": "usd_millions",
                "display_value_zh": "46,700（百万美元）",
            }
        ],
        context_rows=context_rows,
        case={},
    )

    payload = json.dumps(normalized, ensure_ascii=False)
    assert "39%" not in payload
    assert normalized["_ledger_text_contract_sanitized_count"] >= 1


def test_synthesis_caps_weak_plan_memo_language_and_restores_plan_drivers() -> None:
    synthesis = _load_synthesis_module()
    metric_id = "INTERACTIVE_TEST::JPM::2026::revenue::total_value::qtd"
    evidence_id = "JPM_2026_10Q_ITEM2_BLOCK_0001_CHUNK_0001"
    answer = {
        "direct_answer": "JPM是当前样本里的最强明确赢家。",
        "investment_thesis": "JPM明显优于其他公司，但该判断应受SEC证据边界约束。",
        "why_it_matters": [
            {
                "insight": "JPM收入和管理层解释在当前证据中相对更完整。",
                "business_implication": "该结论仍需要后续10-Q继续验证。",
                "metric_ids": [metric_id],
                "evidence_ids": [evidence_id],
            }
        ],
    }
    judgment_plan = {
        "main_judgment": {"strength": "weak"},
        "drivers": [
            {
                "rank": 1,
                "claim": "JPM has weak SEC support under the current evidence boundary.",
                "supporting_metric_ids": [metric_id],
                "supporting_evidence_ids": [evidence_id],
                "conclusion_strength": "weak",
                "caveats": ["10-Q和8-K证据边界限制主结论强度。"],
            }
        ],
    }

    normalized = synthesis._normalize_answer(
        answer,
        ledger_rows=[
            {
                "metric_id": metric_id,
                "ticker": "JPM",
                "fiscal_year": 2026,
                "metric_family": "revenue",
                "metric_role": "total_value",
                "source_evidence_id": evidence_id,
            }
        ],
        context_rows=[
            {
                "evidence_id": evidence_id,
                "ticker": "JPM",
                "fiscal_year": 2026,
                "form_type": "10-Q",
                "source_tier": "primary_sec_filing",
                "text": "JPM revenue discussion and management explanation.",
            }
        ],
        judgment_plan=judgment_plan,
        case={},
    )

    payload = json.dumps(normalized, ensure_ascii=False)
    assert "最强" not in payload
    assert "明确赢家" not in payload
    assert "明显优于" not in payload
    assert normalized["decision_drivers"]
    assert normalized["decision_drivers"][0]["conclusion_strength"] == "weak"
    assert "Judgment Plan main strength is weak" in payload


def test_synthesis_cleanup_uses_explicit_missing_value_language() -> None:
    synthesis = _load_synthesis_module()

    cleaned = synthesis._cleanup_unsupported_value_text(
        "收入增幅当前引用未保留的精确比例，并且AI run-rate突破当前引用未保留的精确金额。"
    )

    assert "相应披露" not in cleaned
    assert "增幅未进入当前 ledger" in cleaned
    assert "run-rate精确金额未进入当前引用" in cleaned


def test_synthesis_cleanup_removes_missing_value_phrase_from_growth_modifier() -> None:
    synthesis = _load_synthesis_module()

    cleaned = synthesis._cleanup_unsupported_value_text(
        "Azure在10-Q中精确比例未获当前引用保留的季度增速是经审阅的硬证据。"
    )

    assert "精确比例未获当前引用保留的季度增速" not in cleaned
    assert "季度增速" in cleaned


def test_answer_ledger_gate_accepts_cited_8k_earnings_release_number() -> None:
    validator = _load_answer_ledger_validator_module()
    eight_k_id = "8K_EARNINGS::MSFT::000119312526191457::MSFTEX991HTM::BLOCK_0002::PART_02_OF_03"
    result = validator._validate_agent_row(
        {
            "case_id": "case",
            "mode": "pipeline_context",
            "status": "answered",
            "answer": {
                "what_changed": [
                    {
                        "claim": "8-K earnings release 显示 Azure 和其他云服务收入增长40%。",
                        "metric_ids": [],
                        "evidence_ids": [eight_k_id],
                    }
                ]
            },
        },
        ledger_rows=[],
        context_rows=[
            {
                "evidence_id": eight_k_id,
                "form_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "text": "Azure and other cloud services revenue grew 40%.",
            }
        ],
        require_metric_id_support=True,
        metric_id_window=240,
    )

    assert result["status"] == "pass"
    assert result["hits"][0]["supported_source"] == "company_authored_unaudited_8k_evidence"


def test_synthesis_prompt_exposes_8k_source_boundary_and_numeric_contract() -> None:
    synthesis = _load_synthesis_module()
    prompt = synthesis._build_prompt(
        {
            "case_id": "case_8k_prompt",
            "prompt": "结合MSFT 10-Q和8-K解释云业务",
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "query_contract": {
                "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            },
        },
        [
            {
                "evidence_id": "8K_EARNINGS::MSFT::000119312526191457::MSFTEX991HTM::BLOCK_0001::CHUNK_0001",
                "ticker": "MSFT",
                "fiscal_year": 2026,
                "fiscal_period": "Q1",
                "form_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "text": "Microsoft Cloud revenue was $46.7 billion.",
            }
        ],
        [
            {
                "metric_id": "MSFT_2026_10Q_CLOUD_REVENUE",
                "value": 46700.0,
                "unit": "usd_millions",
                "display_value_zh": "46,700（百万美元）",
                "metric_family": "cloud_revenue",
            }
        ],
    )

    assert '"form_type": "8-K"' in prompt
    assert '"source_tier": "company_authored_unaudited_sec_filing"' in prompt
    assert "8-K earnings release 的金额、百分比或业务 KPI" in prompt
    assert "不能把 8-K earnings release 数字写成 audited Exact-Value Ledger fact" in prompt
    assert "不能只在 source_limitations 泛泛提及" in prompt
    assert "业绩表现、guidance、demand、capex/投资节奏" in prompt
    assert "公司8-K业绩新闻稿，未审计/管理层口径" in prompt


def test_prompt_context_selection_reserves_requested_8k_source_rows() -> None:
    synthesis = _load_synthesis_module()
    context_rows = [
        {
            "source_kind": "structured_object",
            "object_id": f"OBJ_{idx:03d}",
            "source_evidence_id": f"TENQ_{idx:03d}",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
        }
        for idx in range(70)
    ]
    eight_k_rows = [
        {
            "source_kind": "evidence_object",
            "evidence_id": "8K_EARNINGS::NVDA::000104581026000051::Q1FY27PRHTM::BLOCK_0001::CHUNK_0001",
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "text": "NVIDIA management commentary from Exhibit 99.1.",
        },
        {
            "source_kind": "evidence_object",
            "evidence_id": "8K_EARNINGS::AMD::000000248826000072::Q12026991HTM::BLOCK_0003::CHUNK_0001",
            "ticker": "AMD",
            "fiscal_year": 2026,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "text": "AMD management commentary from Exhibit 99.1.",
        },
        {
            "source_kind": "evidence_object",
            "evidence_id": "8K_EARNINGS::MSFT::000119312526191457::MSFTEX991HTM::BLOCK_0001::CHUNK_0001",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "text": "Microsoft Cloud and AI strength from Exhibit 99.1.",
        },
    ]
    context_rows.extend(eight_k_rows)
    ledger_rows = [
        {
            "metric_id": f"metric_{idx:03d}",
            "object_id": f"OBJ_{idx:03d}",
            "source_evidence_id": f"TENQ_{idx:03d}",
        }
        for idx in range(70)
    ]
    coverage_matrix = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "tasks": [
            {
                "task_id": "ledger_fills_prompt_budget",
                "priority": "primary",
                "sample_metric_ids": [f"metric_{idx:03d}" for idx in range(70)],
            }
        ],
    }

    selected = synthesis._select_prompt_context_rows(
        context_rows,
        ledger_rows,
        coverage_matrix=coverage_matrix,
        max_rows=48,
    )

    selected_8k_ids = {
        row.get("evidence_id")
        for row in selected
        if row.get("source_tier") == "company_authored_unaudited_sec_filing"
    }
    assert len(selected) == 48
    assert selected_8k_ids == {row["evidence_id"] for row in eight_k_rows}


def test_llm_contract_normalization_preserves_8k_source_tier() -> None:
    interactive = _load_interactive_module()
    inventory = {
        "inventory_digest": "inv-8k",
        "companies": [
            {
                "ticker": "MSFT",
                "filings": [
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {
                        "year": 2026,
                        "form_type": "8-K",
                        "source_tier": "company_authored_unaudited_sec_filing",
                    },
                ],
            },
            {
                "ticker": "AMZN",
                "filings": [
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {
                        "year": 2026,
                        "form_type": "8-K",
                        "source_tier": "company_authored_unaudited_sec_filing",
                    },
                ],
            },
        ],
    }
    fallback = {
        "schema_version": "interactive_query_contract_v0.2",
        "task_type": "company_comparison",
        "focus_tickers": ["MSFT", "AMZN"],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing"],
        "decomposed_tasks": [
            {
                "task_id": "compare_cloud",
                "question_zh": "Compare cloud performance.",
                "required_tickers": ["MSFT", "AMZN"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }
    planned = {
        "task_type": "company_comparison",
        "focus_tickers": ["MSFT", "AMZN"],
        "filing_types": ["10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": fallback["decomposed_tasks"],
    }

    contract = interactive._normalize_llm_query_contract(
        planned,
        fallback,
        ["MSFT", "AMZN"],
        [2026],
        inventory,
    )
    contract = interactive._repair_query_contract_from_prompt(
        contract,
        "结合MSFT和AMZN的2026 10-Q以及8-K earnings release",
        ["MSFT", "AMZN"],
        [2026],
        inventory,
    )
    validated = interactive._validate_query_contract(contract, ["MSFT", "AMZN"], [2026], inventory)

    assert validated["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert validated["source_tiers"] == ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    assert validated["source_coverage_gaps"] == []


def test_connector_selects_earnings_release_exhibit_99_1(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "MICROSOFT CORP",
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "accessionNumber": ["0000789019-26-000111", "0000789019-26-000222"],
                "primaryDocument": ["msft-20260424.htm", "msft-20260201.htm"],
                "filingDate": ["2026-04-24", "2026-02-01"],
                "reportDate": ["", ""],
                "acceptanceDateTime": ["2026-04-24T20:00:00.000Z", "2026-02-01T20:00:00.000Z"],
                "primaryDocDescription": ["8-K", "8-K"],
                "items": ["2.02,9.01", "8.01,9.01"],
            }
        },
    }
    detail_index = {
        "directory": {
            "item": [
                {"name": "msft-20260424.htm", "type": "text/html"},
                {"name": "ex991.htm", "type": "text/html"},
                {"name": "ex992.htm", "type": "text/html"},
            ]
        }
    }
    primary_html = """
    <html><body><table>
      <tr><td>EX-99.1</td><td><a href="ex991.htm">ex991.htm</a></td><td>Press Release dated April 24, 2026 announcing quarterly financial results</td></tr>
      <tr><td>EX-99.2</td><td><a href="ex992.htm">ex992.htm</a></td><td>Investor presentation</td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    filing = connector.find_earnings_release_8k("789019", 2026)

    assert filing["form_type"] == "8-K"
    assert filing["source_tier"] == "company_authored_unaudited_sec_filing"
    assert filing["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert filing["accession_number"] == "0000789019-26-000111"
    assert filing["exhibit_document"] == "ex991.htm"
    assert filing["exhibit_type"] == "EX-99.1"
    assert "Press Release" in filing["exhibit_description"]
    assert filing["earnings_release_candidate_reason"]
    assert filing["exhibit_url"].endswith("/000078901926000111/ex991.htm")


def test_connector_selects_plain_99_1_press_release_exhibit(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "NVIDIA CORP",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0001045810-26-000051"],
                "primaryDocument": ["nvda-20260527.htm"],
                "filingDate": ["2026-05-27"],
                "reportDate": ["2026-05-27"],
                "acceptanceDateTime": ["2026-05-27T20:00:00.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["2.02,9.01"],
            }
        },
    }
    detail_index = {
        "directory": {
            "item": [
                {"name": "nvda-20260527.htm", "type": "text/html"},
                {"name": "q1fy27pr.htm", "type": "text/html"},
                {"name": "q1fy27cfocommentary.htm", "type": "text/html"},
            ]
        }
    }
    primary_html = """
    <html><body><table>
      <tr><td>99.1</td><td><a href="q1fy27pr.htm">Press Release</a></td></tr>
      <tr><td>99.2</td><td><a href="q1fy27cfocommentary.htm">CFO Commentary</a></td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    filing = connector.find_earnings_release_8k("1045810", 2026)

    assert filing["accession_number"] == "0001045810-26-000051"
    assert filing["exhibit_document"] == "q1fy27pr.htm"
    assert filing["exhibit_type"] == "EX-99.1"
    assert "Press Release" in filing["exhibit_description"]


def test_connector_selects_exhibit991_filename_without_primary_href(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "PROCTER & GAMBLE Co",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0000080424-26-000056"],
                "primaryDocument": ["pg-20260424.htm"],
                "filingDate": ["2026-04-24"],
                "reportDate": ["2026-04-24"],
                "acceptanceDateTime": ["2026-04-24T20:00:00.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["2.02,9.01"],
            }
        },
    }
    detail_index = {
        "directory": {
            "item": [
                {"name": "pg-20260424.htm", "type": "text/html"},
                {"name": "fy2526q3jfm8-kexhibit991.htm", "type": "text/html"},
            ]
        }
    }
    primary_html = """
    <html><body>
      <p>ITEM 9.01 FINANCIAL STATEMENTS AND EXHIBITS</p>
      <p>99.1 News Release by The Procter & Gamble Company dated April 24, 2026.</p>
    </body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    filing = connector.find_earnings_release_8k("80424", 2026)

    assert filing["exhibit_document"] == "fy2526q3jfm8-kexhibit991.htm"
    assert filing["exhibit_type"] == "EX-99.1"


def test_connector_selects_earningsrelease_filename_without_ex99(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "GE AEROSPACE",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0000040545-26-000026"],
                "primaryDocument": ["ge-20260421.htm"],
                "filingDate": ["2026-04-21"],
                "reportDate": ["2026-04-21"],
                "acceptanceDateTime": ["2026-04-21T20:00:00.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["2.02,9.01"],
            }
        },
    }
    detail_index = {
        "directory": {
            "item": [
                {"name": "ge-20260421.htm", "type": "text/html"},
                {"name": "ge1q2026earningsrelease.htm", "type": "text/html"},
            ]
        }
    }

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: "<html>Item 2.02 earnings release</html>")

    filing = connector.find_earnings_release_8k("40545", 2026)

    assert filing["exhibit_document"] == "ge1q2026earningsrelease.htm"
    assert filing["exhibit_type"] == "EX-99"


def test_connector_scores_news_release_ex99_as_earnings_release(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "TEXAS INSTRUMENTS INC",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0000097476-26-000097"],
                "primaryDocument": ["txn-20260422.htm"],
                "filingDate": ["2026-04-22"],
                "reportDate": ["2026-04-22"],
                "acceptanceDateTime": ["2026-04-22T20:00:00.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["2.02,9.01"],
            }
        },
    }
    detail_index = {
        "directory": {
            "item": [
                {"name": "txn-20260422.htm", "type": "text/html"},
                {"name": "q12026txnex99-eredgar.htm", "type": "text/html"},
            ]
        }
    }
    primary_html = """
    <html><body><table>
      <tr><td>99</td><td><a href="q12026txnex99-eredgar.htm">Registrant's News Release</a></td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    filing = connector.find_earnings_release_8k("97476", 2026)

    assert filing["exhibit_document"] == "q12026txnex99-eredgar.htm"
    assert filing["exhibit_type"] == "EX-99"
    assert "News Release" in filing["exhibit_description"]


def test_connector_downloads_8k_earnings_release_exhibit(tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    filing_meta = {
        "company": "MICROSOFT CORP",
        "cik": "0000789019",
        "form_type": "8-K",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "filing_year": 2026,
        "fiscal_year": 2026,
        "fiscal_year_source": "filing_year",
        "filing_date": "2026-04-24",
        "report_date": "",
        "period_end": "2026-04-24",
        "period_type": "current_report",
        "accession_number": "0000789019-26-000111",
        "primary_document": "msft-20260424.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/msft-20260424.htm",
        "exhibit_document": "ex991.htm",
        "exhibit_type": "EX-99.1",
        "exhibit_description": "Press Release dated April 24, 2026 announcing quarterly financial results",
        "exhibit_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/ex991.htm",
        "_prefetched_primary_html": "<html>primary</html>",
        "_prefetched_exhibit_html": "<html>earnings release</html>",
    }

    result = connector.download_earnings_release_8k(
        filing_meta,
        ticker="MSFT",
        category="mega-cap software/cloud",
        category_slug="mega-cap_software_cloud",
    )

    exhibit_path = Path(result["local_exhibit_path"])
    metadata_path = Path(result["local_metadata_path"])
    assert exhibit_path.exists()
    assert metadata_path.exists()
    assert exhibit_path.read_text(encoding="utf-8") == "<html>earnings release</html>"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["ticker"] == "MSFT"
    assert metadata["source_tier"] == "company_authored_unaudited_sec_filing"
    assert "_prefetched_exhibit_html" not in metadata


def test_connector_does_not_select_generic_9_01_press_release(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "MICROSOFT CORP",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0001193125-26-224155"],
                "primaryDocument": ["d125909d8k.htm"],
                "filingDate": ["2026-05-14"],
                "reportDate": ["2026-05-13"],
                "acceptanceDateTime": ["2026-05-14T20:28:48.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["5.02,9.01"],
            }
        },
    }
    primary_html = """
    <html><body><table>
      <tr><td>EX-99.1</td><td><a href="d125909dex991.htm">d125909dex991.htm</a></td><td>Press Release of Microsoft Corporation dated May 14, 2026</td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: {"directory": {"item": []}})
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    try:
        connector.find_earnings_release_8k("789019", 2026)
    except SecEdgarConnectorError as exc:
        assert "No earnings-release 8-K exhibit found" in str(exc)
        assert exc.reason_code == "no_item_2_02_8k_for_filing_year"
        assert exc.diagnostics["eight_k_rows_in_year"] == 1
        assert exc.diagnostics["item_2_02_8k_rows"] == 0
    else:
        raise AssertionError("expected SecEdgarConnectorError")


def test_connector_rejects_8k_without_earnings_release_exhibit(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "MICROSOFT CORP",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0000789019-26-000111"],
                "primaryDocument": ["msft-20260424.htm"],
                "filingDate": ["2026-04-24"],
                "reportDate": [""],
                "acceptanceDateTime": ["2026-04-24T20:00:00.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["2.02,9.01"],
            }
        },
    }
    detail_index = {"directory": {"item": [{"name": "ex991.htm", "type": "text/html"}]}}
    primary_html = """
    <html><body><table>
      <tr><td>EX-99.1</td><td><a href="ex991.htm">ex991.htm</a></td><td>Investor presentation</td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    try:
        connector.find_earnings_release_8k("789019", 2026)
    except SecEdgarConnectorError as exc:
        assert "No earnings-release 8-K exhibit found" in str(exc)
        assert exc.reason_code == "no_earnings_release_exhibit_for_item_2_02_8k"
        assert exc.diagnostics["item_2_02_8k_rows"] == 1
        assert exc.diagnostics["non_earnings_exhibit_count"] == 1
    else:
        raise AssertionError("expected SecEdgarConnectorError")


def test_8k_downloader_builds_structured_missing_record() -> None:
    downloader = _load_8k_downloader_module()
    planned = {
        "ticker": "NVDA",
        "year": 2027,
        "form_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "category": "AI/GPU semiconductor",
        "category_slug": "ai_gpu_semiconductor",
    }
    exc = SecEdgarConnectorError(
        "No earnings-release 8-K exhibit found for CIK 0001045810 and filing year 2027 "
        "(reason_code=no_item_2_02_8k_for_filing_year).",
        reason_code="no_item_2_02_8k_for_filing_year",
        diagnostics={"eight_k_rows_in_year": 2, "item_2_02_8k_rows": 0},
    )

    record = downloader.build_missing_record(planned, exc, after_date="2026-01-01")

    assert record["schema_version"] == "sec_8k_earnings_source_gap_v0.1"
    assert record["ticker"] == "NVDA"
    assert record["filing_year"] == 2027
    assert record["reason_code"] == "no_item_2_02_8k_for_filing_year"
    assert record["diagnostics"]["eight_k_rows_in_year"] == 2


def test_8k_earnings_manifest_builder_collects_exhibit_paths(tmp_path: Path) -> None:
    manifest = _load_8k_manifest_module()
    cache_root = tmp_path / "sec_8k_earnings"
    filing_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000078901926000111"
    filing_dir.mkdir(parents=True)
    exhibit_path = filing_dir / "ex991.htm"
    exhibit_path.write_text("<html>Microsoft quarterly financial results</html>", encoding="utf-8")
    metadata_path = filing_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "ticker": "MSFT",
                "company": "MICROSOFT CORP",
                "cik": "0000789019",
                "fiscal_year": 2026,
                "fiscal_year_source": "filing_year",
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "form_type": "8-K",
                "source_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "filing_date": "2026-04-24",
                "report_date": "",
                "period_end": "2026-04-24",
                "period_type": "current_report",
                "fiscal_period_source": "not_applicable",
                "filing_items": "2.02,9.01",
                "accession_number": "0000789019-26-000111",
                "primary_document": "msft-20260424.htm",
                "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/msft-20260424.htm",
                "exhibit_document": "ex991.htm",
                "local_html_path": "ex991.htm",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records = manifest.collect_8k_earnings_manifest(
        cache_root,
        years=[2026],
        tickers=["MSFT"],
        categories=["mega-cap_software_cloud"],
    )

    assert len(records) == 1
    record = records[0]
    assert record.form_type == "8-K"
    assert record.source_tier == "company_authored_unaudited_sec_filing"
    assert record.period_type == "current_report"
    assert record.html_path == str(exhibit_path.resolve())
    assert record.metadata_path == str(metadata_path)


def test_8k_manifest_builder_rejects_cached_non_202_item_press_release(tmp_path: Path) -> None:
    manifest = _load_8k_manifest_module()
    cache_root = tmp_path / "sec_8k_earnings"
    filing_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000119312526224155"
    filing_dir.mkdir(parents=True)
    (filing_dir / "ex991.htm").write_text("<html>Generic press release</html>", encoding="utf-8")
    (filing_dir / "metadata.json").write_text(
        json.dumps(
            {
                "ticker": "MSFT",
                "company": "MICROSOFT CORP",
                "fiscal_year": 2026,
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "form_type": "8-K",
                "source_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "filing_items": "5.02,9.01",
                "period_type": "current_report",
                "accession_number": "0001193125-26-224155",
                "exhibit_document": "ex991.htm",
                "local_html_path": "ex991.htm",
            }
        ),
        encoding="utf-8",
    )

    records = manifest.collect_8k_earnings_manifest(cache_root, years=[2026], tickers=["MSFT"])

    assert records == []


def test_8k_manifest_builder_reports_cached_source_gaps(tmp_path: Path) -> None:
    manifest = _load_8k_manifest_module()
    cache_root = tmp_path / "sec_8k_earnings"
    filing_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000119312526224155"
    filing_dir.mkdir(parents=True)
    (filing_dir / "ex991.htm").write_text("<html>Generic press release</html>", encoding="utf-8")
    (filing_dir / "metadata.json").write_text(
        json.dumps(
            {
                "ticker": "MSFT",
                "company": "MICROSOFT CORP",
                "fiscal_year": 2026,
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "form_type": "8-K",
                "source_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "filing_items": "5.02,9.01",
                "period_type": "current_report",
                "accession_number": "0001193125-26-224155",
                "exhibit_document": "ex991.htm",
                "local_html_path": "ex991.htm",
            }
        ),
        encoding="utf-8",
    )

    records, gaps = manifest.collect_8k_earnings_manifest_with_gaps(
        cache_root,
        years=[2026],
        tickers=["MSFT"],
        expected_scope=[
            {
                "ticker": "MSFT",
                "year": 2026,
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "source_tier": "company_authored_unaudited_sec_filing",
            },
            {
                "ticker": "NVDA",
                "year": 2026,
                "category": "AI/GPU semiconductor",
                "category_slug": "ai_gpu_semiconductor",
                "source_tier": "company_authored_unaudited_sec_filing",
            },
        ],
    )

    assert records == []
    assert {gap["ticker"]: gap["reason_code"] for gap in gaps} == {
        "MSFT": "cached_8k_missing_item_2_02",
        "NVDA": "no_cached_8k_earnings_metadata",
    }


def test_8k_manifest_builder_drops_candidate_gap_when_scope_has_valid_release(tmp_path: Path) -> None:
    manifest = _load_8k_manifest_module()
    cache_root = tmp_path / "sec_8k_earnings"
    stale_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000119312526111111"
    valid_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000119312526222222"
    stale_dir.mkdir(parents=True)
    valid_dir.mkdir(parents=True)
    (stale_dir / "ex991.htm").write_text("<html>Generic press release</html>", encoding="utf-8")
    (valid_dir / "ex991.htm").write_text("<html>Microsoft earnings release</html>", encoding="utf-8")
    base_metadata = {
        "ticker": "MSFT",
        "company": "MICROSOFT CORP",
        "fiscal_year": 2026,
        "category": "mega-cap software/cloud",
        "category_slug": "mega-cap_software_cloud",
        "form_type": "8-K",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "period_type": "current_report",
        "exhibit_document": "ex991.htm",
        "local_html_path": "ex991.htm",
    }
    (stale_dir / "metadata.json").write_text(
        json.dumps({**base_metadata, "accession_number": "0001193125-26-111111", "filing_items": "5.02,9.01"}),
        encoding="utf-8",
    )
    (valid_dir / "metadata.json").write_text(
        json.dumps({**base_metadata, "accession_number": "0001193125-26-222222", "filing_items": "2.02,9.01"}),
        encoding="utf-8",
    )

    records, gaps = manifest.collect_8k_earnings_manifest_with_gaps(
        cache_root,
        years=[2026],
        tickers=["MSFT"],
        expected_scope=[
            {
                "ticker": "MSFT",
                "year": 2026,
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "source_tier": "company_authored_unaudited_sec_filing",
            }
        ],
    )

    assert len(records) == 1
    assert records[0].accession_number == "0001193125-26-222222"
    assert gaps == []


def test_query_contract_uses_inventory_8k_source_gap_reasons() -> None:
    manifest_rows = [
        {
            "ticker": "MSFT",
            "company": "MICROSOFT CORP",
            "fiscal_year": 2026,
            "category": "mega-cap software/cloud",
            "category_slug": "mega-cap_software_cloud",
            "form_type": "10-Q",
            "source_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "html_path": "msft-10q.html",
            "metadata_path": "msft-10q.metadata.json",
        }
    ]
    inventory = build_project_inventory(
        manifest_rows,
        manifest_path="manifest.jsonl",
        bm25_index_dir="bm25",
        object_bm25_index_dir="objects",
        bge_model="bge",
        source_gap_rows=[
            {
                "ticker": "MSFT",
                "year": 2026,
                "form_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "reason_code": "no_item_2_02_8k_for_filing_year",
                "source": "download_sec_8k_earnings",
            }
        ],
    )
    result = validate_query_contract(
        {
            "task_type": "general_sec_financial_question",
            "search_scope_tickers": ["MSFT"],
            "focus_tickers": ["MSFT"],
            "years": [2026],
            "filing_types": ["10-Q", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            "metric_families": ["cloud_revenue"],
            "decomposed_tasks": [
                {
                    "task_id": "cloud_8k_boundary",
                    "question_zh": "Use 10-Q values and explain whether 8-K earnings release exists.",
                    "priority": "primary",
                    "required_tickers": ["MSFT"],
                    "required_metric_families": ["cloud_revenue"],
                }
            ],
        },
        selected_tickers=["MSFT"],
        selected_years=[2026],
        project_inventory=inventory,
    )

    gaps = result["contract"]["source_coverage_gaps"]
    assert any(
        gap["ticker"] == "MSFT"
        and gap["form_type"] == "8-K"
        and gap["reason"] == "no_item_2_02_8k_for_filing_year"
        for gap in gaps
    )


def test_source_gap_merge_prefers_discovery_reason_over_manifest_cache_gap() -> None:
    merger = _load_source_gap_merge_module()
    rows = [
        {
            "source": "build_sec_8k_earnings_manifest",
            "ticker": "NVDA",
            "year": 2027,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "category_slug": "ai_gpu_semiconductor",
            "reason_code": "no_cached_8k_earnings_metadata",
        },
        {
            "source": "download_sec_8k_earnings",
            "ticker": "NVDA",
            "filing_year": 2027,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "category_slug": "ai_gpu_semiconductor",
            "reason_code": "no_item_2_02_8k_for_filing_year",
            "diagnostics": {"eight_k_rows_in_year": 3, "item_2_02_8k_rows": 0},
        },
        {
            "source": "build_sec_8k_earnings_manifest",
            "ticker": "MSFT",
            "year": 2026,
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "category_slug": "mega-cap_software_cloud",
            "reason_code": "selected_8k_exhibit_html_missing",
            "html_path": "missing/ex991.htm",
        },
    ]

    merged = merger.merge_source_gaps(rows)

    assert len(merged) == 2
    nvda = next(row for row in merged if row["ticker"] == "NVDA")
    assert nvda["reason_code"] == "no_item_2_02_8k_for_filing_year"
    assert nvda["discarded_gap_reasons"] == ["no_cached_8k_earnings_metadata"]
    assert nvda["diagnostics"]["item_2_02_8k_rows"] == 0
    msft = next(row for row in merged if row["ticker"] == "MSFT")
    assert msft["reason_code"] == "selected_8k_exhibit_html_missing"


def test_context_session_forwards_source_gap_path_to_graph_args() -> None:
    session_cli = _load_context_session_cli_module()
    args = session_cli.parse_args(
        [
            "--source-policy",
            "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "--source-gap-path",
            "data/processed_private/source_gaps/merged.jsonl",
            "--manifest-path",
            "data/processed_private/manifests/mixed_with_8k.jsonl",
        ]
    )

    graph_args = session_cli._graph_args(args)

    assert "--source-gap-path" in graph_args
    assert graph_args[graph_args.index("--source-gap-path") + 1] == "data/processed_private/source_gaps/merged.jsonl"
    assert "--manifest-path" in graph_args
    assert graph_args[graph_args.index("--manifest-path") + 1] == "data/processed_private/manifests/mixed_with_8k.jsonl"


def test_mixed_8k_pipeline_context_adds_source_aware_requirement_queries() -> None:
    evaluator = _load_benchmark_eval_module()
    queries = evaluator._requirement_queries(
        {
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "query_contract": {
                "filing_types": ["10-Q", "8-K"],
                "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            },
        }
    )

    assert any("Exhibit 99.1 earnings release" in query for query in queries)
    assert any("company-authored unaudited" in query for query in queries)


def test_mixed_8k_pipeline_context_reserves_requested_8k_rows_after_rerank() -> None:
    evaluator = _load_benchmark_eval_module()
    case = {
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "companies": ["MSFT"],
        "query_contract": {
            "focus_tickers": ["MSFT"],
            "filing_types": ["10-Q", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        },
    }
    scored = [
        {
            "ticker": "MSFT",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "source_kind": "evidence_object",
            "evidence_id": "msft-10q-cloud",
            "rerank_score": 1.0,
        },
        {
            "ticker": "MSFT",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "source_kind": "evidence_object",
            "evidence_id": "msft-10q-capex",
            "rerank_score": 0.9,
        },
        {
            "ticker": "MSFT",
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "source_kind": "evidence_object",
            "evidence_id": "msft-8k-ex991",
            "rerank_score": 0.1,
        },
    ]

    rows = evaluator._apply_context_reservations(case, scored, top_k=2)

    assert len(rows) == 2
    reserved = [row for row in rows if row["form_type"] == "8-K"]
    assert len(reserved) == 1
    assert reserved[0]["reservation_policy"] == "requested_8k_earnings_source_coverage"


def test_8k_earnings_parser_builds_source_bounded_chunks_and_evidence(tmp_path: Path) -> None:
    html_path = tmp_path / "ex991.htm"
    html_path.write_text(
        """
        <html><body>
        <h1>Microsoft Reports Fiscal 2026 First Quarter Results</h1>
        <p>Microsoft Corp. today announced results for the quarter ended March 31, 2026.</p>
        <h2>Business Highlights</h2>
        <p>Cloud revenue increased as Azure and AI services remained in demand.</p>
        <table>
          <tr><th>Metric</th><th>Amount</th></tr>
          <tr><td>Revenue</td><td>$70.0 billion</td></tr>
        </table>
        <h2>Forward-Looking Statements</h2>
        <p>This release contains forward-looking statements about future business conditions.</p>
        <h2>Non-GAAP Reconciliation</h2>
        <p>Non-GAAP operating income excludes certain items and should not be viewed as audited.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    record = SecFilingManifestRecord(
        ticker="MSFT",
        company="MICROSOFT CORP",
        cik="0000789019",
        fiscal_year=2026,
        fiscal_year_source="filing_year",
        category="mega-cap software/cloud",
        category_slug="mega-cap_software_cloud",
        form_type="8-K",
        source_type="8-K",
        source_tier="company_authored_unaudited_sec_filing",
        filing_date="2026-04-24",
        period_end="2026-04-24",
        period_type="current_report",
        fiscal_period_source="not_applicable",
        accession_number="0000789019-26-000111",
        primary_document="msft-20260424.htm",
        filing_url="https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/msft-20260424.htm",
        html_path=str(html_path),
        metadata_path=str(tmp_path / "metadata.json"),
        metadata={
            "exhibit_document": "ex991.htm",
            "exhibit_type": "EX-99.1",
            "exhibit_description": "Press Release dated April 24, 2026 announcing quarterly financial results",
            "exhibit_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/ex991.htm",
        },
    )

    chunks = build_8k_earnings_chunks(record, target_words=35, overlap_words=5, min_words=5)
    evidence = build_evidence_from_chunks(chunks)

    assert chunks
    assert all(chunk.form_type == "8-K" for chunk in chunks)
    assert all(chunk.source_tier == "company_authored_unaudited_sec_filing" for chunk in chunks)
    assert all(chunk.metadata["exclude_from_exact_value_ledger"] is True for chunk in chunks)
    assert any(chunk.contains_table for chunk in chunks)
    assert chunks[0].chunk_id.startswith("8K_EARNINGS::MSFT::000078901926000111::EX991HTM::")
    assert chunks[0].metadata["reported_period_end"] == "2026-03-31"
    assert chunks[0].metadata["reported_fiscal_period"] == "Q1"
    assert chunks[0].metadata["reported_fiscal_year"] == 2026
    assert evidence[0].evidence_type == "management_commentary"
    assert evidence[0].source_url.endswith("/ex991.htm")
    assert evidence[0].metadata["source_boundary"] == "company_authored_unaudited_sec_filing"


def test_renderer_labels_8k_and_primary_sec_source_boundaries() -> None:
    interactive = _load_interactive_module()
    eight_k_id = "8K_EARNINGS::MSFT::000119312526191457::MSFTEX991HTM::BLOCK_0001::CHUNK_0001"
    ten_q_id = "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04"
    context_rows = [
        {
            "evidence_id": eight_k_id,
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
        },
        {
            "evidence_id": ten_q_id,
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
        },
    ]
    answer = {
        "what_changed": [
            {
                "claim": "Management commentary and 10-Q filing evidence are shown separately.",
                "evidence_ids": [eight_k_id, ten_q_id],
            }
        ]
    }

    rendered = interactive._rendered_answer_markdown(
        "test",
        answer,
        metric_rows={},
        evidence_rows=interactive._evidence_rows_by_id(context_rows),
    )

    assert "MSFT 2026 Q1 8-K earnings release Exhibit 99.1 (company-authored unaudited)" in rendered
    assert "MSFT 2026 10-Q Item 2 (SEC primary filing)" in rendered
