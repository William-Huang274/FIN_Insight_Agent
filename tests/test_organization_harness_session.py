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
async def test_host_composition_guard_tools_and_completed_recovery(setup, tmp_path, monkeypatch):
    _, args, auth, _, _ = setup
    tid, rid = auth['execution_id'], auth['authorized_run_id']
    binary = tmp_path / 'pinned-fixture'
    binary.write_bytes(b'not-executed-fixture')
    release = sha256(binary.read_bytes()).hexdigest()
    binding = dict(execution_id=tid, manifest_digest=auth['manifest_digest'], release=release, model='fixture-model')
    options = dict(manifest_digest=auth['manifest_digest'], model='fixture-model', reasoning='high',
        binary=str(binary), binary_sha256=release, provider='fixture-provider', protocol='qwen_chat',
        provider_endpoint='https://provider.invalid', provider_key_env='FIXTURE_SECRET',
        token_budget_basis=args['basis'], context_window=262144, output_tokens=32000, summary_tokens=16000)
    grant = dict(auth, question='Original research question', organization_id=str(uuid4()))
    execution = SimpleNamespace(apply_profile=lambda _: {'nodes': {'lead': {'profile': {
        'model': 'fixture-model', 'reasoning_effort': 'high'}}}}, delivery_intent='answer', require_report_review=False)
    budget = SimpleNamespace(**{k: args[k] for k in ('store', 'owner', 'budget')},
        prices={'fixture-model': args['prices']}, roles={'lead': {
            'reservation_micros': args['reservation_micros'], 'reservation_basis': args['reservation_basis']}})
    phases = dict(thread_id=tid, run_id=rid, settings={'harness_execution_bindings': {tid: options}},
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
    initial = {'question': grant['question'], 'messages': [HumanMessage(content=grant['question'])]}
    async with module.organization_harness_session(**common) as graph:
        result = await graph.ainvoke(initial)
    assert result['task_outcome']['execution_status'] == 'submitted'
    assert result['messages'][-1].content == 'Original answer'
    assert starts == ['local']
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
