"""Actual phase factory with static models and organization originals; no provider."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from langgraph.graph import StateGraph, START, END
from pydantic import SecretStr, TypeAdapter
import pytest

from sec_agent.agent_runtime import research_session_runtime as runtime
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.specialist_graph import SpecialistAction, SpecialistNativeToolBatch
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_data_composition import organization, specialist
from test_organization_case_artifacts import submitted, submitted_paper
from test_specialist_graph import _model_turn_receipt
from test_specialist_tool_batch import _handoff
from test_case_review_agent import ScriptedNativeChat, call, review_fixture

ROOT = Path(__file__).resolve().parents[1]


def phases_for(factory, tmp_path, **overrides):
    profile, case = runtime.load_research_runtime_profile(ROOT)
    # Keep optional summarization from creating additional scripted actors.
    profile = deepcopy(profile)
    profile['context_summarization'] = None
    args = dict(root=ROOT, settings={'audit_root':str(tmp_path),
        'research_library':str(tmp_path/'forbidden-library'),
        'conversation_fact_mart':str(tmp_path/'forbidden-facts')}, profile=profile, case=case,
        run_id='static-organization-phase', thread_id=factory.grant['execution_id'],
        api_key=SecretStr('offline-not-a-key'), environment={
            'FINSIGHT_TASK_ATTACHMENTS_ROOT':str(tmp_path/'forbidden-personal-uploads'),
            'FINSIGHT_RESEARCH_LIBRARY_PATH':str(tmp_path/'forbidden-library')},
        public_sink=lambda _:None, private_sink=lambda _:None, organization_data_factory=factory,
        execution=ExecutionOptions(mode='single', branch_ids=('Q1_ISSUER_TRUTH',)))
    args.update(overrides)
    return runtime.create_research_phase_runnables(**args)


def invoke(phases, name, state):
    graph = StateGraph(dict).add_node('phase', phases[name]).add_edge(START, 'phase').add_edge('phase', END).compile()
    return asyncio.run(graph.ainvoke(state, {'recursion_limit':100}))


def replay(action, request):
    schema = SpecialistNativeToolBatch if action['action'] == 'native_tool_batch' else SpecialistAction
    parsed = TypeAdapter(schema).validate_json(json.dumps(action)).model_dump(mode='json')
    return {'action':parsed, 'runtime_receipt':_model_turn_receipt(request, parsed,
        receipt_id='organization-phase-static', kind='model', actor=request['agent_id'])}


@pytest.fixture(autouse=True)
def forbid_host_data(monkeypatch):
    import sec_agent.agent_runtime.specialist_composition as composition
    import sec_agent.research_foundation.research_library as library
    def forbidden(*args, **kwargs):
        pytest.fail('organization phase opened host public or personal data')
    monkeypatch.setattr(runtime, 'open_approved_data_composition', forbidden)
    monkeypatch.setattr(composition, 'open_approved_data_composition', forbidden)
    monkeypatch.setattr(library, 'open_library', forbidden)
    monkeypatch.setattr(runtime, 'case_chat_model', forbidden)
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', forbidden)


@pytest.mark.parametrize('fault', ['thread', 'legacy', 'branch'])
def test_factory_scope_rejected_before_host_paths_or_models(organization, tmp_path, fault):
    factory, _ = organization
    options = {'thread_id':'foreign'} if fault == 'thread' else {'contract_version':'legacy'}
    if fault == 'branch':
        _, case = runtime.load_research_runtime_profile(ROOT)
        case = deepcopy(case)
        case['branch_topics'][0]['objective'] = 'Foreign branch objective'
        options = {'case':case}
    with pytest.raises(ValueError, match='organization_phase_scope_mismatch'):
        phases_for(factory, tmp_path, **options)


@pytest.mark.parametrize('stage', ['research','review','triage_review','converge','revise_research','writer','verifier','quick_writer'])
def test_every_phase_denies_revocation_before_reading_state(organization, tmp_path, stage):
    factory, authority = organization
    phases = phases_for(factory, tmp_path)
    authority['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        invoke(phases, stage, {})


@pytest.mark.parametrize('revoke', [False, True])
def test_single_expert_phase_reads_originals_and_checks_response(organization, tmp_path, monkeypatch, revoke):
    factory, authority = organization
    with specialist(factory) as opened:
        from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
        catalog = opened.source_reader(SourceDocumentRequest(source_space='organization', operation='catalog'))
    document = next(r['document_id'] for r in catalog['items'] if 'document_id' in r)
    requests = []
    def model(request):
        requests.append(deepcopy(request))
        if len(requests) == 1:
            action = {'action':'request_source','context_digest':request['context_digest'],
                'reason_summary':'Read the fixed original, using the real phase factory.',
                'selection':{'source_space':'organization','operation':'read','document_id':document}}
        else:
            assert 'Pinned original evidence.' in json.dumps(request)
            action = _handoff(request)
        result = replay(action, request)
        if revoke: authority['status'] = 404
        return result
    def adapter(**kwargs):
        kwargs['source_access_check']()
        return SimpleNamespace(specialist_model_turn=model)
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', adapter)
    phases = phases_for(factory, tmp_path)
    if revoke:
        with pytest.raises(Exception) as denied:
            invoke(phases, 'research', {'question':'Read the selected original.'})
        import traceback
        assert 'specialist_model_turn_failed' in ''.join(traceback.format_exception(denied.value))
        assert len(requests) == 1
    else:
        result = invoke(phases, 'research', {'question':'Read the selected original.'})
        assert result['phase'] == 'research_needs_attention'
        assert len(requests) == 2
        assert 'source_bound_passage' in json.dumps(result)


def test_actual_review_phase_consumes_validated_case(submitted, tmp_path, monkeypatch):
    factory, _, artifacts, paper = submitted
    seen = []
    def model(*args, **kwargs):
        seen.append(True)
        review = {**review_fixture(artifacts), 'completion':'incomplete',
            'unresolved_data_requests':['Static access qualification; financial review not performed.']}
        return ScriptedNativeChat(marker='phase-review', replies=[
            [call('read_research_artifact', {'paper_id':'P01'}, 'paper')],
            [call('read_research_source', {'source_id':'P01:S001'}, 'source')],
            [call('submit_case_review', {'review':review}, 'submit')]])
    monkeypatch.setattr(runtime, 'case_chat_model', model)
    result = invoke(phases_for(factory, tmp_path), 'review', {'question':'Static access qualification', 'case_papers':[paper]})
    assert len(seen) == 2
    assert result['phase'] == 'case_review_incomplete'


@pytest.mark.parametrize('stage', ['writer','quick_writer'])
def test_interactive_phase_reads_organization_source(submitted, tmp_path, monkeypatch, stage):
    from test_report_synthesis_agent import NativeFixtureModel
    factory, _, _, paper = submitted
    model = NativeFixtureModel(marker='organization-answer', replies=[
        [call('read_research_source', {'source_id':'P01:S001'}, 'read')],
        [call('submit_case_answer', {'answer_markdown':'The fixed original states: Pinned original evidence. [P01:S001]'}, 'answer')]])
    monkeypatch.setattr(runtime, 'case_chat_model', lambda *a, **k:model)
    result = invoke(phases_for(factory, tmp_path), stage, {'question':'Static question', 'case_papers':[paper],
        'messages':[], 'request_action':'ask', 'report':{}, 'revisions':{}, 'conversation':[]})
    assert result['output']['kind'] == 'answer'
    assert result['output']['citations']


@pytest.mark.parametrize('saved_kind', ['completed','failed'])
def test_recovered_scope_is_revalidated_before_lead_model(submitted, tmp_path, saved_kind):
    factory, _, _, paper = submitted
    saved = deepcopy(paper)
    saved['task']['snapshot_id'] = 'foreign-snapshot'
    state = {'question':'Static continuation'}
    state.update(completed_workpapers=[saved]) if saved_kind == 'completed' else state.update(
        failed_workpapers=[{'task_id':saved['task']['task_id'],'agent_state':saved}])
    with pytest.raises(Exception) as denied:
        invoke(phases_for(factory, tmp_path), 'research', state)
    import traceback
    assert 'scope_mismatch' in ''.join(traceback.format_exception(denied.value))


def test_lead_phase_reads_fixed_catalog_without_public_library(organization, tmp_path, monkeypatch):
    from test_lead_research_graph import _call, _stop
    factory, _ = organization
    requests = []
    def lead(request):
        requests.append(request)
        if len(requests) == 1:
            result = _call(request, 'RequestSourceAction', action='request_source', selection={'source_space':'organization','operation':'catalog'})
        else:
            assert 'organization' in json.dumps(request['tool_results'])
            result = _stop(request)
            result['action']['tool_calls'][0]['args']['execution_plan'] = {
                'depth':'integrated', 'rationale':'Static source availability test.',
                'omitted_steps_reason':'No financial research was attempted.',
                'escalation_conditions':'A real research question needs independent verification.'}
            result['action']['tool_calls'][0]['args']['question_coverage'] = [{
                'question_quote':request['research_question'], 'status':'unresolved',
                'supporting_task_ids':[], 'rationale':'This fixture only checks authorized navigation, not financial research.'}]
        return replay(result['action'], request)
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', lambda **k:
        SimpleNamespace(lead_research_turn=lead, specialist_model_turn=lambda _:pytest.fail('unexpected delegation')))
    result = invoke(phases_for(factory, tmp_path, execution=ExecutionOptions(mode='auto')), 'research',
        {'question':'Read the organization catalog; leave the financial question unresolved.'})
    assert result['phase'] == 'research_needs_attention'
    assert len(requests) == 2


@pytest.mark.parametrize('revoke', [False, True])
def test_dependency_read_is_currently_authorized(submitted, tmp_path, monkeypatch, revoke):
    from test_lead_research_graph import _task
    from sec_agent.agent_runtime.specialist_handoff import DependencyReader
    factory, authority, _, paper = submitted
    task_id = paper['task']['task_id']
    task = _task('organization-dependent', branch='Q1_ISSUER_TRUTH', dependencies=(task_id,))
    task['requested_capability_refs'] = ['capability:research:source-document-read']
    reads, requests = [], []
    original_read = DependencyReader.__call__
    def read(reader, request):
        reads.append(request)
        result = original_read(reader, request)
        if revoke: authority['status'] = 404
        return result
    monkeypatch.setattr(DependencyReader, '__call__', read)
    def model(request):
        requests.append(request)
        if len(requests) == 1:
            return {'action':'read_dependency_work','context_digest':request['context_digest'],
                'reason_summary':'Read the selected upstream original.', 'task_id':task_id,
                'section':'handoff', 'source_ids':['P01:S001']}
        assert 'Pinned original evidence.' in json.dumps(request)
        return _handoff(request)
    def execute():
        with specialist(factory, model, research_task=task, dependency_workpapers={task_id:paper}) as opened:
            return opened.graph.invoke(opened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
    if revoke:
        with pytest.raises(Exception) as denied:
            execute()
        import traceback
        assert 'OrganizationExecutionUnavailable' in ''.join(traceback.format_exception(denied.value))
        assert len(requests) == 1
    else:
        result = execute()
        assert result['notebook']['observations']
        assert len(requests) == 2
    assert len(reads) == 1


@pytest.mark.parametrize('revoke', [False, True])
def test_convergence_opens_same_revision_for_local_and_mcp_readers(submitted, tmp_path, monkeypatch, revoke):
    from langchain_core.runnables import RunnableLambda
    factory, authority, artifacts, paper = submitted
    workpaper = artifacts.read_paper('P01')
    workpaper['narrative_markdown'] += ' Current revision must be visible to the writer.'
    revision = {'status':'revision_submitted','paper_id':'P01','workpaper':workpaper,
        'finding_responses':[], 'sources':{}}
    revised = artifacts.with_revisions({'P01':revision})
    checked = []
    # The orchestration driver selects a writer candidate. The production
    # phase callback must open fresh real MCP data before constructing it.
    def convergence(**kwargs):
        async def exercise(state, config):
            return await kwargs['make_agent']('writer', revised).ainvoke({}, config)
        return SimpleNamespace(compile=lambda:RunnableLambda(exercise))
    def output_agent(**kwargs):
        assert kwargs['artifacts'].read_paper('P01') == workpaper
        kwargs['audit'].source_access_check()
        async def exercise(state):
            tool = next(t for t in kwargs['tools'] if t.name == 'read_research_artifact')
            observed = await tool.ainvoke({'paper_id':'P01'})
            assert 'Current revision must be visible' in str(observed)
            checked.append(True)
            if revoke: authority['status'] = 404
            return {'phase':'synthetic_candidate', 'candidate':workpaper}
        return RunnableLambda(exercise)
    monkeypatch.setattr(runtime, 'build_research_convergence_graph', convergence)
    monkeypatch.setattr(runtime, 'build_case_output_agent', output_agent)
    monkeypatch.setattr(runtime, 'case_chat_model', lambda *a, **k:object())
    state = {'question':'Static revision', 'case_papers':[paper], 'feedback':{}, 'review_repair_decision':{}}
    if revoke:
        with pytest.raises(Exception) as denied:
            invoke(phases_for(factory, tmp_path), 'converge', state)
        import traceback
        assert 'OrganizationExecutionUnavailable' in ''.join(traceback.format_exception(denied.value))
    else:
        assert invoke(phases_for(factory, tmp_path), 'converge', state)['candidate'] == workpaper
    assert checked == [True]


def test_revision_phase_resumes_original_author_with_bound_private_history(submitted, tmp_path, monkeypatch):
    from langchain_core.messages import HumanMessage, AIMessage
    from langchain_core.runnables import RunnableLambda
    from sec_agent.agent_runtime.specialist_composition import open_specialist_receipted_composition
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    from test_lead_research_graph import _task
    factory, _, _, template = submitted
    assignment = _task('phase-original-author', branch='Q1_ISSUER_TRUTH')
    assignment['requested_capability_refs'] = ['capability:research:source-document-read']
    passage = next(x for o in template['notebook']['observations'] for x in o['content']
                   if x.get('result_state') == 'source_bound_passage')
    calls = []
    def initial(request):
        calls.append(request)
        if len(calls) == 1:
            action = {'action':'request_source','context_digest':request['context_digest'],
                'reason_summary':'Read the original for an assigned static paper.',
                'selection':passage['readback']}
        else:
            action = {**deepcopy(template['final_submission']), 'context_digest':request['context_digest']}
        return replay(action, request)
    with open_specialist_receipted_composition(run_id='static-assigned', run_invocation_id='static-assigned-attempt',
            branch_id='Q1_ISSUER_TRUTH', turn_source='provider_model', model_turn=initial,
            research_task=assignment, research_question='Static revision question', source_read_enabled=True,
            data_composition_factory=factory) as opened:
        paper = opened.graph.invoke(opened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
    assert paper['phase'] == 'specialist_submission_accepted'
    # A synthetic prior response is stored through the same receipt-bound audit
    # shape. No arbitrary history loader or model transport is substituted.
    record = paper['notebook']['model_turn_records'][-1]
    history_path = tmp_path/'static-author-history.jsonl'
    history_path.write_text(json.dumps({'actor':paper['agent_id'],
        'request_digest':record['runtime_receipt']['request_digest'],
        'messages':[HumanMessage(content='Static prior question').model_dump(mode='json')],
        'raw_response':AIMessage(content='Static prior receipt').model_dump(mode='json')})+'\n', encoding='utf-8')
    feedback = [{'finding_id':'verifier:scope', 'diagnosis':'State the access-only fixture boundary explicitly.'}]
    adapter = SimpleNamespace(_agentic_history={})
    def repair(request):
        assert paper['agent_id'] in adapter._agentic_history
        assert request['task_context']['revision_feedback'] == feedback
        action = {**deepcopy(paper['final_submission']), 'context_digest':request['context_digest']}
        action['narrative_markdown'] += ' This changed text proves revision wiring, not financial quality.'
        action['task_note'] = {'summary':'Clarified static boundary.', 'changes':'Added scope statement.',
            'finding_responses':[{'finding_id':'verifier:scope','disposition':'corrected',
                'explanation':'Added explicit qualification scope; financial judgment remains untested.'}]}
        return replay(action, request)
    adapter.specialist_model_turn = repair
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', lambda **k:adapter)
    def convergence(**kwargs):
        async def exercise(state, config):
            revision = await kwargs['run_author']('P01', {'pending_feedback':{'P01':feedback}, 'revisions':{}}, config)
            return {'revision':revision}
        return SimpleNamespace(compile=lambda:RunnableLambda(exercise))
    monkeypatch.setattr(runtime, 'build_research_convergence_graph', convergence)
    profile, _ = runtime.load_research_runtime_profile(ROOT)
    profile = deepcopy(profile)
    profile['authoring']['enabled'] = False  # Saved paper predates staged authoring; retain its mode.
    result = invoke(phases_for(factory, tmp_path, profile=profile, author_audit_paths=(history_path,),
        plan_invocation_id='static-assigned-attempt'), 'revise_research',
        {'question':'Static revision question','case_papers':[paper], 'revisions':{}, 'message':'Clarify qualification scope.'})
    revised = result['revision']
    assert revised['status'] == 'revision_submitted'
    assert revised['author_identity']['agent_id'] == paper['agent_id']
    assert 'This changed text proves' in revised['workpaper']['narrative_markdown']
    assert revised['author_state']['notebook']['observations'] == paper['notebook']['observations']


def test_lead_delegates_through_same_organization_factory(submitted, tmp_path, monkeypatch):
    from test_lead_research_graph import _task, _call, _stop
    factory, _, _, template = submitted
    assigned = _task('organization-phase-child', branch='Q1_ISSUER_TRUTH')
    assigned['requested_capability_refs'] = ['capability:research:source-document-read']
    plan = {'depth':'integrated','rationale':'Exercise actual delegated phase wiring.',
        'omitted_steps_reason':'This is static engineering qualification only.',
        'escalation_conditions':'Financial review remains necessary.'}
    passage = next(x for o in template['notebook']['observations'] for x in o['content']
                   if x.get('result_state') == 'source_bound_passage')
    lead_calls, child_calls = [], []
    def lead(request):
        lead_calls.append(request)
        if len(lead_calls) == 1:
            action = _call(request, 'RequestSourceAction', action='request_source', selection=passage['readback'])['action']
        elif len(lead_calls) == 2:
            action = _call(request, 'DelegateResearchTasksAction', tasks=[assigned], execution_plan=plan)['action']
        else:
            action = _stop(request)['action']
            action['tool_calls'][0]['args'].update(execution_plan=plan, question_coverage=[{
                'question_quote':request['research_question'], 'status':'unresolved', 'supporting_task_ids':[],
                'rationale':'Submitted fixture demonstrates source wiring; real research remains unverified.'}])
        return replay(action, request)
    def child(request):
        child_calls.append(request)
        if len(child_calls) == 1:
            action = {'action':'request_source','context_digest':request['context_digest'],
                'reason_summary':'Read authorized fixed original for delegated task.', 'selection':passage['readback']}
        else:
            action = {**deepcopy(template['final_submission']), 'context_digest':request['context_digest']}
        return replay(action, request)
    monkeypatch.setattr(runtime.DeepSeekStructuredAgentAdapter, 'from_config', lambda **k:
        SimpleNamespace(lead_research_turn=lead, specialist_model_turn=child))
    profile, _ = runtime.load_research_runtime_profile(ROOT)
    profile = deepcopy(profile)
    profile['authoring']['enabled'] = False
    result = invoke(phases_for(factory, tmp_path, profile=profile, execution=ExecutionOptions(mode='auto')),
        'research', {'question':'Static delegated source qualification'})
    assert len(child_calls) == 2 and len(lead_calls) == 3, [r.get('tool_results') for r in lead_calls]
    assert result['task_results'][0]['agent_state']['phase'] == 'specialist_submission_accepted'
    assert result['task_results'][0]['task_id'] == assigned['task_id']
