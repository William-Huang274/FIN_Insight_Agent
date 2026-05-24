from __future__ import annotations

import importlib.util
from pathlib import Path

from sec_agent.coverage_matrix import build_coverage_matrix
from sec_agent.query_contract import validate_query_contract
from evidence.schema import EvidenceObject
from evidence.structured_extractor import extract_structured_objects
from retrieval.bm25_retriever import _record_matches as evidence_record_matches
from retrieval.object_bm25_retriever import _record_matches as object_record_matches


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_synthesis_module():
    path = REPO_ROOT / "scripts" / "run_sec_eval_synthesis_qwen9b_backend.py"
    spec = importlib.util.spec_from_file_location("sec_agent_synthesis_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_ledger_missing_gate_module():
    path = REPO_ROOT / "scripts" / "validate_sec_benchmark_ledger_missing_consistency.py"
    spec = importlib.util.spec_from_file_location("ledger_missing_gate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_query_contract_records_10q_inventory_gap_for_selected_ticker() -> None:
    inventory = {
        "inventory_digest": "inv-test",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "tech",
                "filings": [
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                        "period_type": "quarterly",
                    }
                ],
            },
            {
                "ticker": "NVDA",
                "company": "NVIDIA",
                "category": "tech",
                "filings": [],
            },
        ],
        "categories": [{"category": "tech", "tickers": ["MSFT", "NVDA"]}],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT", "NVDA"],
        "focus_tickers": ["MSFT", "NVDA"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "required_caveats": [
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含具体数字。",
            "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含具体数字。",
        ],
        "decomposed_tasks": [
            {
                "task_id": "cloud_latest_quarter",
                "question_zh": "Use latest quarterly cloud evidence.",
                "priority": "primary",
                "required_tickers": ["MSFT", "NVDA"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    result = validate_query_contract(
        contract,
        selected_tickers=["MSFT", "NVDA"],
        selected_years=[2026],
        project_inventory=inventory,
    )

    clean = result["contract"]
    assert clean["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"
    assert clean["scope"]["source_tiers"] == ["primary_sec_filing"]
    assert any(
        gap["ticker"] == "NVDA"
        and gap["form_type"] == "10-Q"
        and gap["reason"] == "10q_not_in_inventory"
        for gap in clean["source_coverage_gaps"]
    )
    assert not any("不包含具体数字" in caveat for caveat in clean["required_caveats"])
    assert any("不得使用模型记忆或未授权来源补数" in caveat for caveat in clean["required_caveats"])
    assert any("10-Q evidence is unaudited quarterly" in caveat for caveat in clean["required_caveats"])


def test_coverage_matrix_does_not_count_10k_rows_for_10q_scope() -> None:
    query_contract = {
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_latest_quarter",
                "question_zh": "Compare latest quarterly cloud revenue.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }
    wrong_form_context = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-K",
            "source_tier": "primary_sec_filing",
            "text": "Microsoft cloud revenue.",
            "source_evidence_id": "MSFT_2026_10K_ITEM7_BLOCK_1",
        }
    ]
    wrong_form_ledger = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-K",
            "source_tier": "primary_sec_filing",
            "metric_family": "cloud_revenue",
            "metric_id": "m1",
            "source_evidence_id": "MSFT_2026_10K_ITEM7_BLOCK_1",
        }
    ]

    matrix = build_coverage_matrix(
        case={"case_id": "case_10q_scope"},
        query_contract=query_contract,
        context_rows=wrong_form_context,
        ledger_rows=wrong_form_ledger,
    )

    task = matrix["tasks"][0]
    assert task["support_level"] == "insufficient"
    assert task["ledger_row_count"] == 0
    assert task["context_row_count"] == 0
    assert task["missing_filing_types"] == ["10-Q"]
    assert "10-Q" in " ".join(task["must_caveat"])


def test_coverage_matrix_counts_matching_10q_source_scope() -> None:
    query_contract = {
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_latest_quarter",
                "question_zh": "Compare latest quarterly cloud revenue.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }
    context_rows = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "text": "Microsoft cloud revenue.",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        }
    ]
    ledger_rows = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metric_family": "cloud_revenue",
            "metric_id": "m1",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        }
    ]

    matrix = build_coverage_matrix(
        case={"case_id": "case_10q_scope"},
        query_contract=query_contract,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
    )

    task = matrix["tasks"][0]
    assert task["support_level"] == "medium"
    assert task["covered_filing_types"] == ["10-Q"]
    assert task["covered_source_tiers"] == ["primary_sec_filing"]
    assert task["missing_filing_types"] == []


def test_runtime_ledger_preserves_10q_source_metadata_and_rejects_false_rows() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "obj_amzn_aws_operating_income",
        "source_evidence_id": "AMZN_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "AMZN",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "metric_name": "AWS operating income",
        "raw_value": "$11,531",
        "value": 11531,
        "unit": "usd_millions",
        "period": "2026",
        "context": "Operating income by segment. AWS operating income was $11,531 million.",
    }

    row = interactive._ledger_row_from_metric("case", record)

    assert row is not None
    assert row["form_type"] == "10-Q"
    assert row["source_tier"] == "primary_sec_filing"
    assert row["period_type"] == "quarterly"
    assert interactive._ledger_row_allowed(row, {"focus_tickers": ["AMZN"]}, None)

    false_operating_income = dict(row)
    false_operating_income.update(
        {
            "metric_name": "Revenue",
            "row_label": "Revenue",
            "metric_family": "operating_income",
            "record_title": "Operating income by segment",
        }
    )
    assert not interactive._ledger_row_allowed(false_operating_income, {"focus_tickers": ["AMZN"]}, None)

    operating_income_change = interactive._ledger_row_from_metric(
        "case",
        {
            "object_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_METRIC_SENT_D017C4E9",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metric_name": "operating income",
            "raw_value": "$6.4 billion",
            "value": 6.4,
            "unit": "usd_billions",
            "period": "2026",
            "context": "Operating income increased $6.4 billion or 20% driven by growth in Productivity and Business Processes and Intelligent Cloud.",
        },
    )
    assert operating_income_change is not None
    assert operating_income_change["metric_role"] == "period_change_amount"
    assert not interactive._ledger_row_allowed(operating_income_change, {"focus_tickers": ["MSFT"]}, None)

    gross_margin_change = {
        "ticker": "MSFT",
        "metric_family": "gross_margin",
        "metric_role": "percentage_rate",
        "metric_name": "Gross margin growth rate",
        "raw_value_text": "17%",
        "value": 17,
        "unit": "percent",
        "source_text": "Gross margin increased 17% driven by cloud services.",
    }
    assert not interactive._ledger_row_allowed(gross_margin_change, {"focus_tickers": ["MSFT"]}, None)

    gross_margin_change_cell = interactive._ledger_row_from_metric(
        "case",
        {
            "object_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_METRIC_TABLE_9D476233",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metric_name": "Gross margin",
            "row_label": "Gross margin",
            "raw_value": "17%",
            "value": 17,
            "unit": "percent",
            "period": "2026",
            "context": "SUMMARY RESULTS OF OPERATIONS",
            "metadata": {"cell_kind": "change_value", "table_object_id": "table_msft_summary"},
        },
    )
    assert gross_margin_change_cell is not None
    assert gross_margin_change_cell["cell_kind"] == "change_value"
    assert not interactive._ledger_row_allowed(gross_margin_change_cell, {"focus_tickers": ["MSFT"]}, None)

    stale_gross_margin_change_cell = dict(gross_margin_change_cell)
    stale_gross_margin_change_cell["cell_kind"] = "period_value"
    stale_gross_margin_change_cell["column_label"] = None
    assert not interactive._ledger_row_allowed(stale_gross_margin_change_cell, {"focus_tickers": ["MSFT"]}, None)


def test_runtime_ledger_extracts_growth_rate_without_losing_source_metadata() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "obj_msft_cloud_revenue",
        "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "metric_name": "Microsoft Cloud revenue",
        "raw_value": "$42.4 billion",
        "value": 42.4,
        "unit": "usd_billions",
        "period": "2026",
        "context": "Microsoft Cloud revenue increased $9.8 billion or 31% driven by Azure.",
    }
    base_row = interactive._ledger_row_from_metric("case", record)
    assert base_row is not None

    growth_rows = interactive._ledger_growth_rate_rows_from_metric("case", record, base_row)

    assert len(growth_rows) == 1
    assert growth_rows[0]["metric_role"] == "percentage_rate"
    assert growth_rows[0]["raw_value_text"] == "31%"
    assert growth_rows[0]["form_type"] == "10-Q"
    assert interactive._ledger_row_allowed(growth_rows[0], {"focus_tickers": ["MSFT"]}, None)


def test_heuristic_banking_contract_sets_source_tiers_without_planner_state() -> None:
    interactive = _load_interactive_module()
    inventory = {
        "inventory_digest": "inv-bank",
        "companies": [
            {
                "ticker": "JPM",
                "company": "JPMorgan Chase",
                "category": "banking",
                "filings": [
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                    }
                ],
            }
        ],
        "categories": [{"category": "banking", "tickers": ["JPM"]}],
    }

    contract = interactive._build_heuristic_query_contract("JPM银行净息差和存贷款表现如何", ["JPM"], [2026], inventory)

    assert contract["source_tiers"] == ["primary_sec_filing"]


def test_retriever_source_filters_infer_form_type_from_legacy_ids() -> None:
    evidence_record = {
        "evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "metadata": {},
    }
    object_record = {
        "object_id": "MSFT_2026_10Q_ITEM2_BLOCK_1_TABLE_1",
        "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "metadata": {},
    }

    source_filters = {"form_type": ["10-Q"], "source_tier": ["primary_sec_filing"]}
    wrong_form_filters = {"form_type": ["10-K"], "source_tier": ["primary_sec_filing"]}

    assert evidence_record_matches(evidence_record, source_filters)
    assert object_record_matches(object_record, source_filters)
    assert not evidence_record_matches(evidence_record, wrong_form_filters)
    assert not object_record_matches(object_record, wrong_form_filters)


def test_synthesis_removes_protocol_has_no_numbers_limitation_when_ledger_exists() -> None:
    synthesis = _load_synthesis_module()
    answer = {
        "not_found": ["NVDA 2026 10-Q still missing"],
        "source_limitations": [
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。",
            "10-Q evidence is unaudited quarterly evidence.",
        ],
        "limitations": [
            "精确数值必须来自运行时Exact-Value Ledger，本协议不包含具体数字。",
            "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含任何具体数字。",
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。",
            "Evidence Coverage Matrix records source inventory gaps.",
        ],
    }
    ledger_rows = [
        {
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "metric_family": "data_center_revenue",
            "metric_id": "m_nvda_2026_q1_dc",
        }
    ]

    cleaned = synthesis._remove_false_missing_ledger_claims(answer, ledger_rows)

    assert cleaned["not_found"] == ["NVDA 2026 10-Q still missing"]
    assert cleaned["source_limitations"] == ["10-Q evidence is unaudited quarterly evidence."]
    assert cleaned["limitations"] == ["Evidence Coverage Matrix records source inventory gaps."]


def test_ledger_missing_gate_flags_protocol_no_final_numbers_with_ledger() -> None:
    gate = _load_ledger_missing_gate_module()
    answer = {
        "source_limitations": [
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。"
        ],
        "limitations": [],
        "not_found": [],
    }
    locations = gate._missing_statement_locations(answer)
    available = {("AMZN", 2026, "cloud_revenue")}

    assert locations == [
        {
            "location": "source_limitations[1]",
            "text": "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。",
        }
    ]
    assert gate._false_missing_matches(locations[0]["text"], available) == [("AMZN", 2026, "cloud_revenue")]


def test_structured_extractor_aligns_multirow_percentage_change_columns() -> None:
    evidence = EvidenceObject(
        evidence_id="MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
        source_type="10-Q",
        source_tier="primary_sec_filing",
        ticker="MSFT",
        fiscal_year=2026,
        period_end="2026-03-31",
        period_type="quarterly",
        duration_months=3,
        fiscal_period="Q1",
        section="Item 2. Management's Discussion and Analysis",
        subsection="Productivity and Business Processes and Intelligent Cloud",
        evidence_type="section_text",
        text=(
            "SUMMARY RESULTS OF OPERATIONS\n"
            "[TABLE_START id=47 rows=4]\n"
            "(In millions, except percentages and per share amounts)|Three Months Ended March 31,|Percentage Change|Nine Months Ended March 31,|Percentage Change\n"
            "2026|2025|2026|2025\n"
            "Revenue|$|82,886|$|70,066|18%|$|241,832|$|205,283|18%\n"
            "Gross margin|56,058|48,147|16%|164,983|141,466|17%\n"
            "[TABLE_END]"
        ),
        metadata={"form_type": "10-Q", "block_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004"},
    )

    result = extract_structured_objects(evidence)
    table = result.tables[0]
    gross_cells = [cell for cell in table.cells if cell["row_label"] == "Gross margin"]
    amount_cell = next(cell for cell in gross_cells if cell["raw_value"] == "56,058")
    change_cell = next(cell for cell in gross_cells if cell["raw_value"] == "17%")

    assert amount_cell["unit"] == "usd_millions"
    assert amount_cell["cell_kind"] == "period_value"
    assert change_cell["column_label"] == "Percentage Change"
    assert change_cell["cell_kind"] == "change_value"
