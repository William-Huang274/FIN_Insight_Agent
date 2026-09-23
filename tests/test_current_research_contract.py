"""Identity migration and real in-process MCP checks; no model/provider calls."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sec_agent.agent_runtime.current_research_contract import current_foundation, canonical_capability
from sec_agent.agent_runtime.research_session import ResearchRequest
from sec_agent.agent_runtime.research_mcp_tools import compose_mcp_graph_run, MCPToolLaneAdapter
from sec_agent.agent_runtime.research_graph_contracts import BoundBranchTask, canonical_sha256
from sec_agent.agent_runtime.specialist_composition import _build_graph_input
from sec_agent.research_foundation.contracts import load_research_graph_foundation, bind_research_method
from sec_agent.research_foundation.mcp_server import FoundationMethodReader

ROOT = Path(__file__).resolve().parents[1]
THREAD = 'c527b9a2-6c9d-402a-94e5-0079257d63e3'
ASOF = '2026-09-23T00:00:00Z'
BRANCH = 'Q1_ISSUER_TRUTH'


def foundation():
    return current_foundation(load_research_graph_foundation(), thread_id=THREAD,
        profile=json.loads((ROOT / 'configs/research/cases/growth_quality.json').read_text(encoding='utf-8')),
        research_as_of=ASOF)


def assert_no_legacy_config(value):
    text = json.dumps(value, ensure_ascii=False).lower()
    for marker in ('dell_ai_infra_reference_vertical', 'dell_growth_quality', 'capability:dell:',
                   'fin_ia_dell_', 'dell-owner-data', 'get_dell_research_method', 'f2_dell_', 'f3_dell_'):
        assert marker not in text, marker


def test_current_binding_is_task_scoped_and_does_not_mutate_archive():
    archived = load_research_graph_foundation()
    original = archived.model_dump(mode='json')
    current = foundation()
    assert current.case_identity.case_id == 'research:' + THREAD
    assert current.scope_ceiling.one_subject_company_only is False
    bound = bind_research_method(current, [BRANCH], research_as_of=datetime(2026, 9, 23, tzinfo=timezone.utc),
        data_snapshot_id='research-data:test', execution_attempt_id='contract-test')
    assert_no_legacy_config(bound.model_dump(mode='json'))
    assert archived.model_dump(mode='json') == original
    assert current.case_identity.subject_ticker == 'task-defined'
    old = bind_research_method(archived, [BRANCH], research_as_of=datetime(2026, 9, 2, tzinfo=timezone.utc),
        data_snapshot_id='historical-snapshot', execution_attempt_id='historical-test')
    assert old.run_scope.case_id == 'DELL_AI_INFRA_REFERENCE_VERTICAL'
    assert old.run_scope.schema_version == 'fin_ia_dell_research_run_scope_v1_0'


def test_new_profile_accepts_retired_input_but_emits_only_general_profile():
    for value in ({}, {'case_profile': 'dell_growth_quality'}, {'case_profile': 'general_research'}):
        result = ResearchRequest(question='Compare current demand evidence across multiple companies.', **value)
        assert result.case_profile == 'general_research'
    assert 'dell' not in json.dumps(ResearchRequest.model_json_schema()).lower()
    assert canonical_capability('capability:dell:source-document-read') == 'capability:research:source-document-read'
    assert canonical_capability('capability:unknown:write') == 'capability:unknown:write'


def test_new_specialist_input_has_no_reference_routes_or_issuer_scope():
    graph = compose_mcp_graph_run(foundation(), branch_ids=[BRANCH], research_as_of=ASOF,
        snapshot_id='research-data:test', execution_attempt_id='contract-test')
    value = _build_graph_input(run_id='research-test', run_invocation_id='contract-test', branch_id=BRANCH,
        foundation_binding=graph.foundation_binding, source_route_catalog={'catalog_digest': 'a'*64},
        planner_tool_capabilities={'finance': {'metrics': [{'metric_id': 'revenue', 'observed_tickers': ['MSFT', 'DELL']}]}},
        reviewed_topic_refs_by_branch={}, owner_data_gate_decision_digest='b'*64,
        inventory_snapshot_digest='c'*64, max_model_turns=2, max_tool_actions=4,
        source_read_enabled=True, research_question='Compare current demand evidence across multiple companies.')
    assert_no_legacy_config(value.model_dump(mode='json'))
    assert not value.required_route_obligation_ids and not value.task.evidence_requests
    assert all(c.get('capability_ref') != 'capability:research:reviewed-evidence-query'
               for c in value.l0_context.capability_summaries)
    # Dell can still be a real data subject; never censor evidence/company names.
    assert 'DELL' in json.dumps(value.model_dump(mode='json'))
    from sec_agent.agent_runtime.specialist_graph import _build_notebook, _model_request
    notebook = _build_notebook(run_id=value.run_id, run_invocation_id=value.run_invocation_id,
        agent_id=value.agent_id, task_id=value.task.task_id, branch_id=BRANCH, task_revision=0,
        owner_data_gate_decision_digest='b'*64, source_route_catalog_digest='a'*64,
        inventory_snapshot_digest='c'*64, model_turn_count=0, tool_action_count=0,
        required_route_obligation_ids=(), satisfied_route_obligation_ids=(),
        model_turn_records=(), observations=(), feedback=(), dispatched_action_digests=(),
        status='researching', source_read_enabled=True)
    request = _model_request(state=value.model_dump(mode='json'), notebook=notebook)
    assert_no_legacy_config(request)
    assert 'request_evidence' not in request['allowed_actions']
    from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph
    captured = []
    def capture_only(request):
        captured.append(request)
        raise RuntimeError('stop_before_provider_call')
    lead = build_lead_research_graph(expected_input=value,
        research_question='Compare current demand evidence across multiple companies.',
        branch_catalog=[{'branch_id': BRANCH, 'objective': 'Inspect issuer evidence.'}],
        allowed_branch_ids=(BRANCH,), seed_workpapers={}, model_turn=capture_only,
        run_child=lambda *_: None).compile()
    with pytest.raises(RuntimeError, match='stop_before_provider_call'):
        lead.invoke(value.model_dump(mode='json'))
    assert len(captured) == 1
    assert_no_legacy_config(captured[0])


def test_new_binding_executes_mcp_and_missing_ticker_cannot_select_reference_issuer(monkeypatch):
    from test_research_mcp import _build_server
    current = foundation()
    monkeypatch.setattr(FoundationMethodReader, 'from_default_contract', classmethod(lambda cls: cls(current)))
    graph = compose_mcp_graph_run(current, branch_ids=[BRANCH], research_as_of=ASOF,
        snapshot_id='research-data:test', execution_attempt_id='contract-test')
    task = BoundBranchTask(task_id='task:test', case_id=graph.foundation_binding.case_id,
        branch_id=BRANCH, revision=0, priority='high', objective='Read explicit company revenue.',
        evidence_requests=(), fact_requests=({'metric_ids': ['revenue'], 'selection_mode': 'latest_on_or_before'},),
        research_as_of=ASOF, snapshot_id='research-data:test',
        foundation_digest=graph.foundation_binding.foundation_digest,
        method_digest=graph.mcp_run_binding.branch_method_digests[BRANCH], plan_digest='d'*64)
    with MCPToolLaneAdapter(_build_server(), run_binding=graph.mcp_run_binding) as adapter:
        result = adapter.finance_tool({'lane': 'finance', 'task': task.model_dump(mode='json')})
        assert result['status'] == 'tool_failure'
        assert 'explicit_ticker_required' in json.dumps(result)
        body = task.model_dump(mode='json')
        body['fact_requests'][0]['ticker'] = 'MSFT'
        result = adapter.finance_tool({'lane': 'finance', 'task': body})
        assert result['status'] == 'success'
        assert_no_legacy_config(result)
        assert 'MSFT' in json.dumps(result)
        bad = {**body, 'case_id': 'research:another-task'}
        failed = adapter.finance_tool({'lane': 'finance', 'task': bad})
        assert failed['status'] == 'tool_failure'
        assert 'case_binding_mismatch' in json.dumps(failed)
