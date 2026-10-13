"""Real specialist composition/MCP, fixed originals and scripted turns only."""
from pathlib import Path
import json

import pytest

from sec_agent.agent_runtime.current_research_contract import current_foundation
from sec_agent.agent_runtime.organization_data_composition import OrganizationDataFactory
from sec_agent.agent_runtime.specialist_composition import open_specialist_receipted_composition
from sec_agent.research_foundation.contracts import load_research_graph_foundation
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_grant, runtime_at
from test_specialist_tool_batch import _handoff
from test_specialist_graph import _model_turn_receipt
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticGraphError, SpecialistAction
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'Q1_ISSUER_TRUTH'


@pytest.fixture
def organization(tmp_path):
    shared, preparation = fixture(tmp_path)
    grant = runtime_grant(preparation)
    reader, state = runtime_at(shared, grant)
    cutoff = preparation['manifest']['research_as_of'] + 'T12:00:00+08:00'
    foundation = current_foundation(load_research_graph_foundation(), thread_id=grant['execution_id'],
        profile=json.loads((ROOT / 'configs/research/cases/growth_quality.json').read_text(encoding='utf-8')),
        research_as_of=cutoff)
    factory = OrganizationDataFactory(reader, foundation=foundation, research_as_of=cutoff,
                                      workbench_url='https://workbench.example.test')
    return factory, state


def specialist(factory, model=_handoff, **extra):
    def replay(request):
        action = TypeAdapter(SpecialistAction).validate_python(model(request)).model_dump(mode='json')
        return {'action':action, 'runtime_receipt':_model_turn_receipt(request, action,
            receipt_id='host:organization-static-replay',
            kind='host', actor='dell_specialist_saved_response_replay', input_tokens=0, output_tokens=0,
            total_tokens=0, usage_reported=None)}
    return open_specialist_receipted_composition(run_id='organization-test', run_invocation_id='organization-invocation',
        branch_id=BRANCH, turn_source='saved_response_replay', model_turn=replay, source_read_enabled=True,
        research_question='Read only the selected organizational originals.', data_composition_factory=factory,
        environment={'FINSIGHT_RESEARCH_LIBRARY_PATH':'Z:/must-not-open/library',
                     'FINSIGHT_TASK_ATTACHMENTS_ROOT':'Z:/must-not-open/private-uploads'}, **extra)


def test_specialist_real_entry_discloses_only_organization_sources_and_reads_via_existing_receipts(organization, monkeypatch):
    import sec_agent.agent_runtime.specialist_composition as module
    factory, _ = organization
    monkeypatch.setattr(module, 'open_approved_data_composition', lambda **kwargs: pytest.fail('host data opened'))
    with specialist(factory) as opened:
        summaries = opened.graph_input.l0_context.capability_summaries
        assert not any(row.get('capability_ref') == 'capability:research:financial-fact-query' for row in summaries)
        source = next(row for row in summaries if row.get('capability_ref') == 'capability:research:source-document-read')
        assert source['source_spaces'] == ['organization']
        catalog = opened.source_reader(SourceDocumentRequest(source_space='organization', operation='catalog'))
        assert catalog['status'] == 'success', catalog
        document = next(row['document_id'] for row in catalog['items'] if 'document_id' in row)
        read = opened.source_reader(SourceDocumentRequest(source_space='organization', operation='read', document_id=document))
        assert read['status'] == 'success', read
        passage = next(row for row in read['items'] if row['result_state'] == 'source_bound_passage')
        assert passage['passage'] == 'Pinned original evidence.'
        assert len(passage['mcp_receipt_chain']) == 2
        assert read['snapshot_id'] == factory.reader.authority.manifest_digest
        assert not opened.graph_input.required_route_obligation_ids


@pytest.mark.parametrize('space', ['local','library','uploads','web'])
def test_specialist_cannot_call_host_spaces_even_with_host_environment(organization, space):
    factory, _ = organization
    with specialist(factory) as opened:
        selection = {'operation':'search','query':'private'} if space == 'web' else {'operation':'catalog'}
        result = opened.source_reader(SourceDocumentRequest(source_space=space, **selection))
        assert result['status'] == 'tool_failure'
        assert 'organization_tool_capability_not_authorized' in json.dumps(result)


def test_real_specialist_graph_consumes_source_tool_and_records_native_observation(organization):
    factory, _ = organization
    turns = []
    def model(request):
        turns.append(request)
        if len(turns) > 1: return _handoff(request)
        return {'action':'request_source','context_digest':request['context_digest'],
                'reason_summary':'Read the fixed original located by the planning entry.',
                'selection':{'source_space':'organization','operation':'read','document_id':document}}
    with specialist(factory, model) as opened:
        catalog = opened.source_reader(SourceDocumentRequest(source_space='organization',operation='catalog'))
        document = next(row['document_id'] for row in catalog['items'] if 'document_id' in row)
        result = opened.graph.invoke(opened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
        observations = result['notebook']['observations']
        assert len(observations) == 1
        assert observations[0]['provenance_kind'] == 'mcp_bridge'
        assert any(row.get('document_id','').startswith('ORGDOC::') for row in observations[0]['content'])
        assert any(row.get('passage') == 'Pinned original evidence.' for row in observations[0]['content'])
        assert observations[0]['references']
        assert len(turns) == 2


def test_permission_loss_blocks_next_tool_and_model_at_actual_specialist_entry(organization):
    factory, state = organization
    calls = []
    with specialist(factory, lambda request: calls.append(request)) as opened:
        state['status'] = 404
        with pytest.raises(OrganizationExecutionUnavailable):
            opened.source_reader(SourceDocumentRequest(source_space='organization', operation='catalog'))
        with pytest.raises(SpecialistAgenticGraphError, match='specialist_model_turn_failed'):
            opened.graph.invoke(opened.graph_input.model_dump(mode='json'))
    assert calls == []


@pytest.mark.parametrize('option', ['web','artifacts'])
def test_unfinished_lanes_fail_explicitly_before_old_data_is_opened(organization, option):
    factory, _ = organization
    extra = {'live_web_read_enabled':True} if option == 'web' else {'case_artifacts':object()}
    with pytest.raises(ValueError):
        with factory(run_invocation_id='attempt', source_read_enabled=True, **extra): pass


def test_financial_query_is_not_available_but_explicit_scenario_calculation_is(organization):
    factory, _ = organization
    with specialist(factory) as opened:
        task = opened.graph_input.task.model_dump(mode='json')
    with factory(run_invocation_id='organization-invocation', source_read_enabled=True) as data:
        task.update(evidence_requests=[], fact_requests=[{'ticker':'MSFT', 'metric_id':'revenue'}])
        denied = data.dependencies.finance_tool({'lane':'finance','task':task})
        assert denied['status'] == 'tool_failure'
        assert 'organization_tool_capability_not_authorized' in json.dumps(denied)
        task['fact_requests'] = [{'calculation':{'expression':'x * 2', 'operands':{
            'x':{'literal':'12.50','assumption_note':'Synthetic scenario, not a reported figure'}},
            'result_unit':'USD', 'rationale':'Static calculator integration only'}}]
        computed = data.dependencies.finance_tool({'lane':'finance','task':task})
        assert computed['status'] == 'success', computed
        item = computed['items'][0]
        assert item['value_decimal'] == '25.00' and not item['numeric_fact_authority']
        assert item['operands']['x']['authority'] == 'assumption'


@pytest.mark.parametrize('change', ['thread', 'cutoff', 'naive_cutoff'])
def test_factory_requires_execution_identity_and_explicit_manifest_calendar(organization, change):
    factory, _ = organization
    foundation = factory.foundation
    cutoff = factory.research_as_of
    if change == 'thread':
        foundation = foundation.model_copy(update={'case_identity':foundation.case_identity.model_copy(
            update={'case_id':'research:other-thread'})})
    elif change == 'cutoff': cutoff = '2026-10-11T12:00:00+08:00'
    else: cutoff = '2026-10-12T12:00:00'
    with pytest.raises(ValueError, match='identity_or_cutoff'):
        OrganizationDataFactory(factory.reader, foundation=foundation, research_as_of=cutoff,
                                workbench_url=factory.workbench_url)


def test_method_scope_tampering_is_rejected_by_real_mcp(organization):
    import asyncio
    from mcp import Client
    factory, _ = organization
    with factory(run_invocation_id='attempt', source_read_enabled=True) as data:
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                bound = data.foundation_binding
                args = {'branch_ids':list(bound.required_branch_ids), 'research_as_of':bound.research_as_of,
                    'data_snapshot_id':bound.snapshot_id, 'execution_attempt_id':'attempt',
                    'source_policy':'organization_fixed_inputs_only'}
                first = await client.call_tool('get_research_source_binding', args)
                assert not first.is_error, first
                for key, value in [('execution_attempt_id','other-attempt'), ('data_snapshot_id','other-snapshot'),
                                   ('source_policy','frozen_local_reviewed_plus_public_web_locator_only')]:
                    assert (await client.call_tool('get_research_source_binding', {**args,key:value})).is_error
                scope = first.structured_content['run_scope']
                request = {'source_space':'organization','operation':'catalog'}
                assert (await client.call_tool('read_source_document', {'request':request})).is_error
                assert (await client.call_tool('read_source_document', {'request':request, 'branch_id':BRANCH,
                    'run_scope':{**scope,'run_scope_digest':'0'*64}})).is_error
        asyncio.run(exercise())
