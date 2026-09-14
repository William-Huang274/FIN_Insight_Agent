"""A task mart's catalog must not depend on the historical reference issuer."""
import pytest
import json

from sec_agent.agent_runtime.specialist_composition import _build_graph_input, SpecialistAgenticCompositionError
from sec_agent.agent_runtime.research_graph_contracts import CaseFoundationBinding
from test_research_graph import FakeRuntime, _start_input, _source_route_catalog, _planner_tool_capabilities


def graph_input(rows):
    capabilities = _planner_tool_capabilities()
    capabilities['finance']['metrics'] = rows
    return _build_graph_input(
        run_id='catalog-test', run_invocation_id='catalog-attempt', branch_id='Q1_ISSUER_TRUTH',
        foundation_binding=CaseFoundationBinding.model_validate_json(json.dumps(FakeRuntime().foundation_binder(_start_input()))),
        source_route_catalog=_source_route_catalog(), planner_tool_capabilities=capabilities,
        reviewed_topic_refs_by_branch={'Q1_ISSUER_TRUTH': ('fixture-topic',)},
        owner_data_gate_decision_digest='a'*64, inventory_snapshot_digest='b'*64,
        max_model_turns=2, max_tool_actions=4, research_question='Compare the task issuer with its peer.')


@pytest.mark.parametrize('issuer', ['GOOGL', 'MSFT', 'DELL'])
def test_specialist_sees_issuer_and_peer_metrics_with_per_metric_coverage(issuer):
    rows = [dict(metric_id='revenue', availability='direct_observation', observed_tickers=[issuer]),
            dict(metric_id='operating_income', availability='direct_observation', observed_tickers=['AMZN']),
            dict(metric_id='operating_margin', availability='derived_at_query_time', observed_tickers=[])]
    result = graph_input(rows)
    catalog = next(c for c in result.l0_context.capability_summaries if 'metrics' in c)
    assert [m['metric_id'] for m in catalog['metrics']] == [r['metric_id'] for r in rows]
    assert [m['observed_tickers'] for m in catalog['metrics']] == [[issuer], ['AMZN'], []]
    assert catalog['grants_authority'] is False
    assert result.task.case_id == 'DELL'  # Historical data identity is not rewritten.


def test_empty_catalog_does_not_invent_financial_coverage():
    with pytest.raises(SpecialistAgenticCompositionError, match='specialist_finance_metrics_missing'):
        graph_input([])
