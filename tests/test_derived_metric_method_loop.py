"""Development regressions, including sign changes; not blind financial gold."""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import hashlib

import pytest

from financial_facts import FactLookup, execute_fact_lookup, write_company_fact_mart
from financial_facts.derived_metrics import derived_metric_catalog
from sec_agent.agent_runtime.planner_tool_capabilities import derive_planner_tool_capabilities
from sec_agent.research_foundation.report_charts import ReportChart, bind_report_charts
from test_s2_company_financial_fact_mart import _metric, _observation, _policy


def build_mart(tmp_path, *, ticker="ALPHA", start="2025-01-01", end="2025-12-31", year=2025,
               now_income="-20", old_income="100", now_revenue="200", old_revenue="100",
               old_unit="USD", role="fiscal_year", fp="FY", prior_start="2024-01-01", prior_end="2024-12-31", prior_year=2024, prior_fp="FY"):
    rows = []
    for current, values in [(True, {"revenue": now_revenue, "net_income": now_income, "operating_income": now_income, "operating_cash_flow": "60", "capital_expenditures": "20"}),
                            (False, {"revenue": old_revenue, "net_income": old_income, "operating_income": old_income, "operating_cash_flow": "50", "capital_expenditures": "10"})]:
        period_start, period_end = (start, end) if current else (prior_start, prior_end)
        accepted = (date.fromisoformat(period_end) + timedelta(days=30)).isoformat() + "T00:00:00+00:00"
        for key, value in values.items():
            row = _observation(f"{ticker}-{current}-{key}", key, value, period_start=period_start,
                period_end=period_end, fiscal_year=year if current else prior_year,
                fiscal_period=fp if current else prior_fp, accepted_at=accepted,
                accession=f"filing-{current}", period_role=role)
            rows.append(replace(row, ticker=ticker, legal_name=ticker, unit="USD" if current else old_unit,
                                duration_days=(date.fromisoformat(period_end)-date.fromisoformat(period_start)).days+1))
    metrics = tuple(_metric(key) for key in values)
    path = tmp_path / "facts.sqlite"
    write_company_fact_mart(path, observations=rows, metrics=metrics, policy=_policy(metrics=metrics))
    return path, FactLookup("development-query", ticker, "revenue", "2026-09-10",
        {"selection_mode": "exact_period_end", "end_date": end}, role, "reported_source_unit")


@pytest.mark.parametrize("ticker,start,end,year,prior_start,prior_end,prior_year", [
    ("ALPHA", "2025-01-01", "2025-12-31", 2025, "2024-01-01", "2024-12-31", 2024),
    ("BETA", "2025-07-01", "2026-06-30", 2026, "2024-07-01", "2025-06-30", 2025),
    ("GAMMA", "2025-01-27", "2026-01-25", 2026, "2024-01-29", "2025-01-26", 2025),
])
def test_cross_fiscal_calendar_growth_and_loss(tmp_path, ticker, start, end, year, prior_start, prior_end, prior_year):
    path, lookup = build_mart(tmp_path, ticker=ticker, start=start, end=end, year=year,
        prior_start=prior_start, prior_end=prior_end, prior_year=prior_year)
    before = path.read_bytes()
    growth = execute_fact_lookup(path, replace(lookup, metric_id="revenue_yoy_growth"))
    assert growth.status == "resolved"
    assert Decimal(growth.facts[0].value_decimal) == 100
    assert growth.facts[0].formula_trace["inputs"][1]["period_end"] == prior_end
    change = execute_fact_lookup(path, replace(lookup, metric_id="operating_income_yoy_change"))
    assert change.status == "resolved" and Decimal(change.facts[0].value_decimal) == -120
    rejected = execute_fact_lookup(path, replace(lookup, metric_id="operating_income_yoy_growth"))
    assert rejected.typed_gap["gap_code"] == "growth_rate_not_meaningful_for_nonpositive_values"
    assert path.read_bytes() == before


@pytest.mark.parametrize("metric,expected,unit", [
    ("net_margin", -10, "percent"), ("free_cash_flow", 40, "USD"),
    ("free_cash_flow_margin", 20, "percent"), ("capex_to_revenue", 10, "percent"),
    ("net_margin_yoy_pp", -110, "percentage_point"), ("free_cash_flow_yoy_change", 0, "USD"),
    ("capital_expenditures_yoy_growth", 100, "percent"),
])
def test_nested_metrics_have_exact_values_and_recursive_source_trace(tmp_path, metric, expected, unit):
    path, lookup = build_mart(tmp_path)
    result = execute_fact_lookup(path, replace(lookup, metric_id=metric))
    assert result.status == "resolved", result.as_dict()
    fact = result.facts[0]
    assert Decimal(fact.value_decimal) == expected and fact.unit == unit
    assert fact.source_observation_ids and fact.formula_trace["inputs"]


def test_qoq_rejects_ytd_and_accepts_contiguous_discrete_quarters(tmp_path):
    path, lookup = build_mart(tmp_path, start="2025-04-01", end="2025-06-30", role="quarter_discrete", fp="Q2",
        prior_start="2025-01-01", prior_end="2025-03-31", prior_year=2025, prior_fp="Q1")
    result = execute_fact_lookup(path, replace(lookup, metric_id="revenue_qoq_growth"))
    assert result.status == "resolved" and Decimal(result.facts[0].value_decimal) == 100
    annual, look2 = build_mart(tmp_path / "annual" )
    bad = execute_fact_lookup(annual, replace(look2, metric_id="revenue_qoq_growth"))
    assert bad.status == "typed_conflict"


@pytest.mark.parametrize("old_income,now_income", [("0", "20"), ("-10", "20"), ("-10", "-5"), ("20", "0")])
def test_growth_does_not_disguise_zero_or_loss_transitions(tmp_path, old_income, now_income):
    path, lookup = build_mart(tmp_path, old_income=old_income, now_income=now_income)
    result = execute_fact_lookup(path, replace(lookup, metric_id="net_income_yoy_growth"))
    assert result.status == "typed_gap"
    assert len(result.typed_gap["current_fact"]["source_observation_ids"]) == 1


def test_comparison_rejects_unit_mismatch(tmp_path):
    path, lookup = build_mart(tmp_path, old_unit="EUR")
    assert execute_fact_lookup(path, replace(lookup, metric_id="revenue_yoy_change")).status == "typed_conflict"


def test_catalog_and_existing_chart_use_same_numeric_fact_without_retyping(tmp_path):
    path, lookup = build_mart(tmp_path)
    projection = derive_planner_tool_capabilities(sqlite_path=path, expected_mart_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), snapshot_id="development")
    assert "net_margin_yoy_pp" in {m.metric_id for m in projection.finance.metrics}
    assert "gross_margin" not in {m["metric_id"] for m in derived_metric_catalog(["revenue", "net_income"])}
    facts = [execute_fact_lookup(path, replace(lookup, metric_id=m)).facts[0] for m in ("revenue_yoy_change", "net_income_yoy_change")]
    sources = {f.numeric_fact_id: {**f.as_dict(), "result_state": "numeric_fact"} for f in facts}
    chart = ReportChart(title="变化额对比", unit="USD", interpretation="收入和净利润的同比变化额，不能单独证明变化原因。",
        points=[{"label": f.metric_id, "source": {"source_id": f.numeric_fact_id}} for f in facts])
    bound = bind_report_charts([chart], sources.__getitem__)[0]
    assert [p["value"] for p in bound["points"]] == [100, -120]
    assert [p["source_id"] for p in bound["points"]] == [f.numeric_fact_id for f in facts]
    assert bound["points"][0]["provenance"]["formula_trace"]["formula"] == "current - prior"
    with pytest.raises(ValueError, match="chart_unit_differs"):
        bind_report_charts([chart.model_copy(update={"unit": "EUR"})], sources.__getitem__)


def test_native_conversation_consumes_method_query_and_chart(tmp_path):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
    from sec_agent.agent_runtime.conversation_tools import conversation_tools
    from sec_agent.agent_runtime.conversation_handoff import answer_charts
    from test_conversation_agent import ScriptedTools
    path, lookup = build_mart(tmp_path)
    def call(name, args, identifier):
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": identifier, "type": "tool_call"}])
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "metric-loop"}}
    grants = conversation_tools(thread_id="metric-loop", fact_mart=path)
    agent = build_conversation_agent(model=ScriptedTools(responses=[
        call("get_research_method", {"method_id": "finance"}, "method"),
        call("query_financial_data", {"ticker": "ALPHA", "metric_id": "net_income_yoy_change", "fiscal_years": [2025],
             "research_as_of": "2026-09-10", "granularity": "fiscal_year"}, "query"), AIMessage(content="Development query received.")]),
        grants=grants, permission_mode="request_standard", checkpointer=saver)
    result = agent.invoke({"messages": [HumanMessage(content="Synthetic development protocol, not real company research.")]}, config)
    methods = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "get_research_method")
    assert "执行顺序与交付" in methods.content
    query = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "query_financial_data")
    fact = query.artifact["results"][0]["facts"][0]
    assert Decimal(fact["value_decimal"]) == -120
    chart = {"title": "精确结果复用", "unit": "USD", "interpretation": "同一计算对象重复展示仅用于工具协议测试，不是真实比较图。",
             "points": [{"label": label, "source": {"source_id": fact["numeric_fact_id"]}} for label in ("观察一", "观察二")]}
    second = build_conversation_agent(model=ScriptedTools(responses=[call("create_report_chart", {"chart": chart}, "chart"), AIMessage(content="Bound chart saved.")]),
        grants=grants, permission_mode="request_standard", checkpointer=saver)
    result = second.invoke({"messages": [HumanMessage(content="Reuse the previously queried fact in a development chart.")]}, config)
    messages = [m.model_dump(mode="json") for m in result["messages"]]
    assert answer_charts(messages)[0]["points"][0]["value"] == -120
    assert not answer_charts([*messages, {"type": "human", "content": "new question"}])


def test_batch_query_retains_successful_facts_with_individual_gaps(tmp_path):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
    from sec_agent.agent_runtime.conversation_tools import conversation_tools
    from test_conversation_agent import ScriptedTools
    path, _ = build_mart(tmp_path)
    args = {"ticker": "ALPHA", "metric_ids": ["revenue", "net_income_yoy_change", "net_income_yoy_growth", "unavailable_metric"],
            "fiscal_years": [2025], "research_as_of": "2026-09-10", "granularity": "fiscal_year"}
    agent = build_conversation_agent(model=ScriptedTools(responses=[AIMessage(content="", tool_calls=[{
        "name": "query_financial_data", "args": args, "id": "batch", "type": "tool_call"}]), AIMessage(content="Observed both facts and gaps.")]),
        grants=conversation_tools(thread_id="batch", fact_mart=path), permission_mode="request_standard", checkpointer=InMemorySaver())
    result = agent.invoke({"messages": [HumanMessage(content="Synthetic batch protocol.")]}, {"configurable": {"thread_id": "batch"}})
    rows = next(m.artifact["results"] for m in result["messages"] if isinstance(m, ToolMessage))
    assert [r["status"] for r in rows] == ["resolved", "resolved", "typed_gap", "typed_gap"]
    assert [Decimal(r["facts"][0]["value_decimal"]) for r in rows[:2]] == [200, -120]
    assert len({r["fact_request_id"] for r in rows}) == 4


def test_prior_year_comparison_uses_disclosed_period_not_latest_filing_cohort(tmp_path):
    # The latest filing at the comparison-period cutoff contains FY2023,
    # whereas the FY2024 result is disclosed only after that cutoff. It must
    # still be available at the later research_as_of, including a restatement.
    rows = []
    for year, value in [(2023, "90"), (2024, "100"), (2025, "220")]:
        rows.append(replace(_observation(str(year), "revenue", value,
            period_start=f"{year}-01-01", period_end=f"{year}-12-31", fiscal_year=year, fiscal_period="FY",
            period_role="fiscal_year", accepted_at=f"{year+1}-02-01T00:00:00+00:00", accession=str(year)), duration_days=366 if year == 2024 else 365))
    rows.append(replace(rows[1], observation_id="restated", value_decimal="110", accepted_at="2026-02-01T00:00:00+00:00", accession_number="2025"))
    path = tmp_path / "vintages.sqlite"
    metrics = (_metric("revenue"),)
    write_company_fact_mart(path, observations=rows, metrics=metrics, policy=_policy(metrics=metrics))
    lookup = FactLookup("restated-comparison", "DELL", "revenue_yoy_growth", "2026-09-10",
                        {"selection_mode": "exact_period_end", "end_date": "2025-12-31"}, "fiscal_year", "reported_source_unit")
    result = execute_fact_lookup(path, lookup)
    assert result.status == "resolved", result.as_dict()
    assert Decimal(result.facts[0].value_decimal) == 100
    prior = result.facts[0].formula_trace["inputs"][1]
    assert prior["period_end"] == "2024-12-31" and "restated" in prior["source_observation_ids"]
