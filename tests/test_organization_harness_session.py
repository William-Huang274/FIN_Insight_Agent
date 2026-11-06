"""Composition tests; Java/ACP peers are fixtures, not service qualification."""
from contextlib import asynccontextmanager
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from test_harness_dispatch_host import setup
from sec_agent.agent_runtime import organization_harness_session as module
from sec_agent.agent_runtime.harness_acp_session import _persist


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
@pytest.mark.parametrize('report_review', [False, True])
async def test_host_composition_guard_tools_and_completed_recovery(setup, tmp_path, monkeypatch, report_review):
    _, args, auth, _, _ = setup
    tid, rid = auth['execution_id'], auth['authorized_run_id']
    binary = tmp_path / 'pinned-fixture'
    binary.write_bytes(b'not-executed-fixture')
    release = sha256(binary.read_bytes()).hexdigest()
    binding = dict(execution_id=tid, manifest_digest=auth['manifest_digest'], release=release, model='fixture-model')
    options = dict(manifest_digest=auth['manifest_digest'], model='fixture-model', reasoning='high',
        binary=str(binary), binary_sha256=release, provider='fixture-provider', protocol='qwen_chat',
        provider_endpoint='https://provider.invalid', provider_key_env='FIXTURE_SECRET',
        token_budget_basis=args['basis'], context_window=262144, output_tokens=32000, summary_tokens=16000,
        preloaded_research_methods=['research_loop', 'counter', 'finance'])
    grant = dict(auth, question='Original research question', organization_id=str(uuid4()))
    execution = SimpleNamespace(apply_profile=lambda _: {'nodes': {'lead': {'profile': {
        'model': 'fixture-model', 'reasoning_effort': 'high'}}}}, delivery_intent='answer', require_report_review=False)
    budget = SimpleNamespace(**{k: args[k] for k in ('store', 'owner', 'budget')},
        prices={'fixture-model': args['prices']}, roles={'lead': {
            'reservation_micros': args['reservation_micros'], 'reservation_basis': args['reservation_basis']}})
    phases = dict(thread_id=tid, run_id=rid, settings={'harness_execution_bindings': {tid: options}, 'audit_root':str(tmp_path/'audit')},
        execution=execution, profile={}, budget_scope=budget, public_sink=lambda _: None,
        root=Path(__file__).resolve().parents[1])
    environment = dict(FINSIGHT_HARNESS_STATE_ROOT=str(tmp_path / 'sessions'),
        FINSIGHT_WORKING_MEMORY_PATH=str(tmp_path / 'notes.sqlite'), FIXTURE_SECRET='fixture-only')
    prepared = []
    organization = SimpleNamespace(retrieval=SimpleNamespace(navigation=lambda: SimpleNamespace()),
        research_as_of='2026-09-23', prepare_retrieval=lambda: prepared.append(True))
    saved = {'values': {}}
    async def state(*_, **__): return saved
    native = SimpleNamespace(threads=SimpleNamespace(get_state=state))
    starts = []
    @asynccontextmanager
    async def local(**kw):
        assert prepared  # Cold preparation cannot consume a model tool deadline.
        tools = {t.name for t in (await kw['business'].list_tools(None, None)).tools}
        assert {'browse_context', 'read_research_source', 'calculate_research_metric', 'save_research_report'} <= tools
        starts.append('local')
        yield 'http://127.0.0.1:9'
    @asynccontextmanager
    async def acp(**kw):
        from sec_agent.research_foundation.research_methods import get_research_method
        profile_text = Path(kw['arguments'][-1]).read_text(encoding='utf8')
        profile_text = json.dumps(json.loads(profile_text), ensure_ascii=False)
        for key in options['preloaded_research_methods']:
            assert get_research_method(key)['resource_digest'] in profile_text
        assert 'FIXTURE_SECRET' not in kw['environment']
        async def prompt(text):
            data = json.loads(text)
            assert data['original_question'] == grant['question']
            assert data['handoff']['kind'] == 'imported_fin_tool_records_not_native_acp_history'
            return {'status': 'completed', 'session_id': 'native-fixture', 'text': 'Original answer'}
        yield SimpleNamespace(prompt=prompt)
    monkeypatch.setattr(module, 'harness_local_services', local)
    monkeypatch.setattr(module, 'admitted_acp_session', acp)
    common = dict(native=native, resources=None, authority=lambda: auth, check=lambda: None,
        organization=organization, phase_arguments=phases, config={}, grant=grant,
        expected_input={'question': grant['question']}, environment=environment)
    report = {'title': 'Complete report', 'narrative_markdown': 'Full original report. '*20, 'citations': {}}
    initial = {'question': grant['question'], 'messages': [HumanMessage(content=grant['question'])],
               **({'report': report, 'report_version': 4} if report_review else {})}
    if report_review:
        saved['values'] = initial
    async with module.organization_harness_session(**common) as graph:
        result = await graph.ainvoke(initial)
    assert result['task_outcome']['execution_status'] == 'submitted'
    assert result['messages'][-1].content == 'Original answer'
    assert starts == ['local']
    delivered_message = result['messages'][-1]
    # Success was durable before the root graph result could be committed.
    directory = tmp_path / 'sessions' / tid
    _persist(directory / 'session-binding.json', {'binding': binding, 'session_id': 'native-fixture'})
    _persist(directory / rid / 'turn.private.json', {'status': 'completed', 'session_id': 'native-fixture',
        'text': 'Original answer', 'stop_reason': 'end_turn'})
    (directory / rid / 'events.private.jsonl').write_text(json.dumps({
        'session_id': 'native-fixture', 'update': {'sessionUpdate': 'agent_message_chunk',
            'content': {'type': 'text', 'text': 'Original answer'}}}) + '\n', encoding='utf8')
    new_run = str(uuid4())
    recovery = dict(grant, report_command_id=str(uuid4()), report_action_request={
        'action': 'recover', 'previous_run_id': rid, 'message': 'Continue', 'checkpoint_id': str(uuid4())})
    saved['values'] = initial
    async with module.organization_harness_session(**{**common, 'grant': recovery, 'expected_input': None,
            'phase_arguments': {**phases, 'run_id': new_run}}) as graph:
        result = await graph.ainvoke({**initial, 'messages': [*initial['messages'], HumanMessage(content='Continue')]})
    assert result['messages'][-1].content == 'Original answer'
    assert result['task_outcome']['run_id'] == new_run
    assert starts == ['local']  # no private service, ACP process or provider replay
    assert json.loads((directory / new_run / 'turn.private.json').read_text())['reused_from_run'] == rid

    if report_review:
        from sec_agent.agent_runtime.answer_review import PREFIX
        from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
        from sec_agent.agent_runtime import answer_review_provider
        options['answer_review_model'] = 'gpt-6.1-sol'
        review_run = str(uuid4())
        command = PREFIX + json.dumps(dict(artifact='report', version=canonical_sha256(report),
            quote='', offset=0, question='Check the material explanations.'))
        review_grant = dict(grant, report_command_id=str(uuid4()), report_action_request={
            'action':'continue', 'delivery_intent':'report', 'require_report_review':False,
            'message':command, 'previous_run_id':new_run, 'checkpoint_id':str(uuid4())})
        saved['values'] = {**initial, 'messages': [*initial['messages'],delivered_message]}
        bridge_holder = {}
        @asynccontextmanager
        async def report_local(**kw):
            bridge_holder['bridge'] = kw['business']
            yield 'http://127.0.0.1:9'
        async def reviewer(**kw):
            assert kw['message'].content == report['narrative_markdown']
            assert kw['selected'].artifact == 'report'
            return 'Independent report opinion.'
        @asynccontextmanager
        async def report_acp(**kw):
            async def prompt(text):
                data = json.loads(text)
                assert data['original_answer'] == report['narrative_markdown']
                assert data['independent_review'] == 'Independent report opinion.'
                assert data['report_version'] == 4
                receipt = await bridge_holder['bridge'].execute('deliver_current_report', {'version':4})
                assert receipt.status == 'success'
                return {'status':'completed','session_id':'native-fixture','text':'Retained the supported conclusions.'}
            yield SimpleNamespace(prompt=prompt)
        monkeypatch.setattr(module,'harness_local_services',report_local)
        monkeypatch.setattr(module,'admitted_acp_session',report_acp)
        monkeypatch.setattr(answer_review_provider,'independent_review',reviewer)
        async with module.organization_harness_session(**{**common,'grant':review_grant,'expected_input':None,
                'phase_arguments':{**phases,'run_id':review_run}}) as graph:
            result = await graph.ainvoke({**saved['values'],'messages':[*saved['values']['messages'],HumanMessage(content=command)]})
        assert result['report'] == report and result['report_version'] == 4
        assert result['task_outcome']['artifact_kind'] == 'report'
        annotation = result['messages'][-1].additional_kwargs['answer_review']
        assert annotation['reviewed_report_version'] == annotation['revised_report_version'] == 4
        assert json.loads((directory/review_run/'review-target.json').read_text())['report'] == report
        return

    # Operator-selected pre-generation checkpoint must not inherit the later
    # outer answer, old business ledger, or the old note workspace.
    from sec_agent.agent_runtime import harness_legacy_import
    import_digest = 'b' * 64
    imported = ToolMessage(content='exact original', name='read_source_document', tool_call_id='retained', id='retained')
    monkeypatch.setattr(harness_legacy_import, 'legacy_receipts', lambda *a, **k: {
        'messages': [imported], 'harness_import_digest': import_digest})
    options.update(isolated_receipt_replay=True, legacy_receipt_import={'sha256': import_digest})
    saved['values'] = {'messages': [HumanMessage(content='later incorrect answer')], 'question': grant['question']}
    @asynccontextmanager
    async def clean_local(**kw):
        current = await kw['business'].state()
        assert [m.content for m in current['messages']] == ['exact original']
        yield 'http://127.0.0.1:9'
    monkeypatch.setattr(module, 'harness_local_services', clean_local)
    async with module.organization_harness_session(**common) as graph:
        result = await graph.ainvoke(initial)
    assert (directory / ('import-' + import_digest) / 'business-checkpoint.sqlite').exists()
    assert (directory / 'business-checkpoint.sqlite').exists()
    options.pop('legacy_receipt_import')
    with pytest.raises(ValueError, match='requires_pinned_checkpoint'):
        async with module.organization_harness_session(**common):
            pass
