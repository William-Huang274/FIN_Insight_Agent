"""Organization paper/alias/reviewer boundaries with native scripted agents."""
import asyncio
from copy import deepcopy
import json

import pytest
from mcp import Client

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_data_composition import organization, specialist
from test_model_dispatch_guard import boundary, response


@pytest.fixture
def submitted(organization):
    factory, state = organization
    paper = submitted_paper(factory)
    return factory, state, CaseArtifacts([paper]), paper


def submitted_paper(factory):
    """Use the actual expert graph for both fake-authority and real-Java tests."""
    from test_specialist_graph import _submission
    turns = []
    def model(request):
        turns.append(request)
        if len(turns) == 1:
            return {'action':'request_source','context_digest':request['context_digest'],
                'reason_summary':'Read the fixed original for a synthetic paper.',
                'selection':{'source_space':'organization','operation':'read','document_id':document}}
        if len(turns) == 2:
            return {'action':'request_calculation', 'context_digest':request['context_digest'],
                'reason_summary':'Record a synthetic calculation for alias recovery.',
                'request':{'expression':'x * 2','operands':{'x':{'literal':'12.50','assumption_note':'Synthetic scenario'}},
                    'result_unit':'USD','rationale':'Static arithmetic fixture; no financial assertion'}}
        action = _submission(evidence_id=passage['passage_id'])(request)
        action.update(context_digest=request['context_digest'], thesis='The selected original contains a synthetic evidence statement.',
            mechanism='This fixture checks source access, without a financial inference.',
            narrative_markdown='The selected original states: ' + passage['passage'] + ' This is a synthetic access test.',
            claims=[{**action['claims'][0], 'statement':passage['passage'],
                'authority_note':'Synthetic original passage, not verified financial authority.',
                'citation_quotes':{passage['passage_id']:passage['passage']}}],
            counterevidence=['This synthetic source cannot establish a real financial conclusion.'],
            what_would_change=['A different authorized source version requires a new evidence review.'],
            open_gaps=['No real financial conclusion was tested.'])
        return action
    with specialist(factory, model) as opened:
        catalog = opened.source_reader(SourceDocumentRequest(source_space='organization',operation='catalog'))
        document = next(row['document_id'] for row in catalog['items'] if 'document_id' in row)
        read = opened.source_reader(SourceDocumentRequest(source_space='organization',operation='read',document_id=document))
        passage = next(row for row in read['items'] if row.get('result_state') == 'source_bound_passage')
        paper = opened.graph.invoke(opened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
    assert paper['phase'] == 'specialist_submission_accepted', paper.get('last_submission_attempt')
    return paper


def open_case(factory, artifacts):
    return factory(run_invocation_id='review-attempt', source_read_enabled=True, case_artifacts=artifacts)


def test_real_expert_paper_is_validated_and_existing_case_tools_read_aliases(submitted):
    from sec_agent.agent_runtime.case_review_agent import case_mcp_tools
    factory, _, artifacts, _ = submitted
    original = artifacts.source_snapshot()
    alias = next(iter(original))
    with open_case(factory, artifacts) as data:
        assert data.case_artifacts.catalog() == artifacts.catalog()
        assert 'mcp_receipt_chain' not in data.case_artifacts.source_item(alias)
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                tools = {tool.name:tool for tool in await case_mcp_tools(client)}
                assert {'research_artifact_catalog','read_research_artifact','read_research_source',
                    'search_research_sources','calculate_research_metric'}.issubset(tools)
                assert 'query_company_financial_facts' not in tools
                result = await tools['read_research_artifact'].ainvoke({'paper_id':'P01'})
                assert 'Pinned original evidence.' in str(result)
                read = await client.call_tool('read_research_source', {'source_id':alias})
                assert not read.is_error and 'Pinned original evidence.' in str(read)
                assert (await client.call_tool('read_research_source', {'source_id':'P02:S001'})).is_error
        asyncio.run(exercise())
    assert artifacts.source_snapshot() == original


@pytest.mark.parametrize('field', ['case_id','snapshot_id','research_as_of','foundation_digest',
    'owner_data_gate_decision_digest','source_route_catalog_digest','inventory_snapshot_digest'])
def test_paper_scope_mismatch_is_rejected_before_tools_exist(submitted, field):
    factory, _, artifacts, _ = submitted
    setattr(artifacts, field, 'foreign-scope')
    with pytest.raises(ValueError, match='scope_mismatch'):
        with open_case(factory, artifacts): pass


@pytest.mark.parametrize('fault', ['text','execution','numeric_fact','source_only'])
def test_unverified_paper_sources_cannot_be_promoted(submitted, fault):
    factory, _, artifacts, _ = submitted
    sources = artifacts.source_snapshot()
    alias = next(iter(sources))
    if fault == 'text': sources[alias]['passage'] = 'Forged source'
    elif fault == 'execution': sources[alias]['organization_source']['execution_id'] = 'another'
    elif fault == 'numeric_fact': sources[alias]['result_state'] = 'numeric_fact'
    if fault == 'source_only':
        item = sources[alias]
        artifacts = CaseArtifacts.from_observed_sources({item['passage_id']:item},
            case_id=artifacts.case_id, research_as_of=artifacts.research_as_of)
    else: artifacts = artifacts.with_source_snapshot(sources)
    with pytest.raises(ValueError):
        with open_case(factory, artifacts): pass


@pytest.mark.parametrize('tool,args', [
    ('research_artifact_catalog',{}), ('read_research_artifact',{'paper_id':'P01'}),
    ('search_research_sources',{'query':'Pinned'}), ('read_research_source',{'source_id':'P01:S001'}),
    ('calculate_research_metric',{'request':{'expression':'x * 2','operands':{
        'x':{'literal':'2','assumption_note':'Synthetic scenario'}},'result_unit':'USD','rationale':'Static only'}}),
])
def test_revocation_protects_paper_titles_search_read_and_calculation(submitted, tool, args):
    factory, state, artifacts, _ = submitted
    with open_case(factory, artifacts) as data:
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                state['status'] = 404
                result = await client.call_tool(tool, args)
                assert result.is_error and 'Pinned original evidence.' not in str(result)
        asyncio.run(exercise())
    with pytest.raises(OrganizationExecutionUnavailable):
        with open_case(factory, artifacts): pass


def test_alias_calculation_uses_canonical_operands_and_survives_next_review_session(submitted):
    factory, _, artifacts, _ = submitted
    alias, original = next((alias,item) for alias,item in artifacts.source_snapshot().items()
        if item['result_state'] == 'non_authoritative_metric')
    with open_case(factory, artifacts) as data:
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                result = await client.call_tool('calculate_research_metric', {'request':{
                    'expression':'prior / 2', 'operands':{'prior':{'source_id':alias}},
                    'result_unit':'USD','rationale':'Synthetic alias arithmetic'}})
                assert not result.is_error, result
                return result.structured_content
        calculation = asyncio.run(exercise())
    assert calculation['value_decimal'] == '12.50'
    assert calculation['operands']['prior']['source_id'] == original['calculation_id']
    saved = artifacts.with_saved_calculations({'test':{'sources':[{
        'source_id':calculation['calculation_id'], 'calculation':calculation}]}})
    with open_case(factory, saved) as restored:
        assert restored.case_artifacts.source_item(calculation['calculation_id']) == calculation


def test_original_expert_revises_from_validated_history_then_reopens_for_review(submitted, tmp_path):
    from test_specialist_tool_batch import _batch
    factory, _, _, paper = submitted
    original = deepcopy(paper)
    feedback = [{'finding_id':'verifier:scope', 'diagnosis':'Clarify this fixture does not establish financial correctness.'}]
    requests = []
    def model(request):
        requests.append(request)
        (tmp_path/'revision-request.json').write_text(json.dumps(request), encoding='utf8')
        assert request['task_context']['revision_feedback'] == feedback
        repair = request['submission_to_repair']
        if repair['candidate']['narrative_markdown'] != paper['final_submission']['narrative_markdown']:
            return {'action':'finalize_workpaper_revision', 'context_digest':request['context_digest'],
                'reason_summary':'Submit the explicitly saved scope correction.',
                'draft_digest':repair['base_submission_digest']}
        note = {'summary':'Clarified the scope of the static fixture.',
            'changes':'Added an explicit access-only boundary.', 'finding_responses':[{
                'finding_id':'verifier:scope', 'disposition':'corrected',
                'explanation':'Added the requested qualification boundary; independent financial review remains outstanding.'}]}
        return {'action':'save_workpaper_edits', 'context_digest':request['context_digest'],
            'operation_id':'static-scope-edit', 'reason_summary':'Clarify the engineering qualification boundary.',
            'base_submission_digest':repair['base_submission_digest'], 'edits':[
                {'op':'set_field','path':'/narrative_markdown',
                 'value':paper['final_submission']['narrative_markdown'] + ' This revision validates access and source continuity only.'},
                {'op':'set_field', 'path':'/task_note', 'value':{**(repair['candidate'].get('task_note') or {}), **note}}]}
    with specialist(factory, lambda request: _batch(request, [model(request)]),
            recovery_state=paper, revision_feedback=feedback) as opened:
        revised = opened.graph.invoke(opened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
    assert revised['phase'] == 'specialist_submission_accepted', revised.get('last_submission_attempt')
    assert len(requests) == 2
    assert revised['notebook']['observations'] == paper['notebook']['observations']
    assert revised['final_submission']['narrative_markdown'] != paper['final_submission']['narrative_markdown']
    with open_case(factory, CaseArtifacts([revised])) as data:
        assert data.case_artifacts.read_paper('P01')['narrative_markdown'] == revised['final_submission']['narrative_markdown']
    assert paper == original


def audit_for(data, boundary):
    from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
    events, private = [], []
    audit = CaseModelAudit(actor='organization-static-review', profile=boundary.profile,
        basis=boundary.basis.model_copy(update={'max_input_characters':1000000}),
        public_sink=events.append, private_sink=private.append, source_access_check=data.access_check)
    audit.working_note_context = lambda: ''
    return audit, events, private


@pytest.mark.parametrize('revision', [False, True])
def test_existing_reviewer_consumes_validated_paper_and_revision(submitted, boundary, revision):
    from langchain_core.messages import HumanMessage
    from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, case_mcp_tools
    from sec_agent.agent_runtime.case_artifacts import revision_review_target
    from test_case_review_agent import ScriptedNativeChat, call, review_fixture
    factory, _, artifacts, _ = submitted
    target = None
    if revision:
        workpaper = artifacts.read_paper('P01')
        workpaper['narrative_markdown'] += ' Revised synthetic explanation; no financial quality conclusion.'
        change = {'status':'revision_submitted','workpaper':workpaper,'finding_responses':[],'sources':{}}
        target = revision_review_target(artifacts, 'P01', change)
        artifacts = artifacts.with_revisions({'P01':change})
    with open_case(factory, artifacts) as data:
        audit, events, _ = audit_for(data, boundary)
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                pending = 'Static execution only; financial correctness has not been independently assessed.'
                review = {**review_fixture(data.case_artifacts), 'completion':'incomplete',
                    'unresolved_data_requests':[pending]}
                first = call('read_review_target', {}, 'paper') if revision else call('read_research_artifact', {'paper_id':'P01'}, 'paper')
                replies = [[first], [call('read_research_source', {'source_id':'P01:S001'}, 'source')],
                    [call('submit_case_review', {'review':review}, 'submit')]]
                agent = build_case_reviewer(role='verifier', model=ScriptedNativeChat(replies=replies, marker='static'),
                    tools=await case_mcp_tools(client), artifacts=data.case_artifacts, audit=audit, revision_target=target)
                result = await agent.ainvoke({'messages':[HumanMessage(content='Synthetic boundary qualification only.')]})
                assert result['review']['completion'] == 'incomplete'
                assert result['review']['unresolved_data_requests'] == [pending]
                if revision: assert result['review']['review_scope']['kind'] == 'revision_only'
        asyncio.run(exercise())
        assert len([event for event in events if event.get('status') == 'success']) == 3


@pytest.mark.parametrize('when', ['before','during'])
def test_local_tool_boundary_withholds_content_when_access_changes(submitted, boundary, when):
    factory, state, artifacts, _ = submitted
    with open_case(factory, artifacts) as data:
        audit, _, _ = audit_for(data, boundary)
        calls = []
        async def handler(request):
            calls.append('called')
            result = data.case_artifacts.catalog()
            state['status'] = 404
            return result
        if when == 'before': state['status'] = 404
        with pytest.raises(OrganizationExecutionUnavailable):
            asyncio.run(audit.awrap_tool_call(None, handler))
        assert calls == ([] if when == 'before' else ['called'])


@pytest.mark.parametrize('when', ['before','during'])
def test_model_boundary_preserves_audit_but_withholds_revoked_response(submitted, boundary, when):
    factory, state, artifacts, _ = submitted
    with open_case(factory, artifacts) as data:
        audit, events, private = audit_for(data, boundary)
        calls = []
        async def handler(request):
            calls.append('called')
            state['status'] = 404
            return response()
        if when == 'before': state['status'] = 404
        with pytest.raises(OrganizationExecutionUnavailable):
            asyncio.run(audit.awrap_model_call(boundary.request, handler))
        assert calls == ([] if when == 'before' else ['called'])
        assert not any(event.get('status') in {'success','candidate'} for event in events)
        if when == 'during':
            outcome = events[-1]
            assert outcome['status'] == 'blocked_after_response_source_access'
            assert outcome['usage_reported'] is True
            assert any(event['event'] == 'response' for event in private)
