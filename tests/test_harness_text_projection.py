import json
from types import SimpleNamespace

import pytest

from sec_agent.agent_runtime.harness_acp_session import (
    HarnessSession, HarnessSessionClient, TurnTextProjection,
    completed_text_projection,
    native_tool_recovery,
    compatible_session_binding,
)


def test_model_takeover_cannot_change_authority_or_release_or_other_session():
    prior={'session_id':'native','binding':{'execution_id':'task','manifest_digest':'grant','release':'pinned','model':'old'}}
    binding={**prior['binding'],'model':'new'}
    transition={'session_id':'native','from_model':'old','to_model':'new'}
    assert not compatible_session_binding(prior,binding)
    assert compatible_session_binding(prior,binding,transition)
    for key in ('execution_id','manifest_digest','release'):
        assert not compatible_session_binding(prior,{**binding,key:'changed'},transition)
    assert not compatible_session_binding(prior,binding,{**transition,'session_id':'other'})
    assert not compatible_session_binding(prior,binding,{**transition,'from_model':'other'})
    assert compatible_session_binding({'session_id':'native','binding':binding},binding,transition)


def chunk(text, message_id='answer'):
    return {'sessionUpdate': 'agent_message_chunk', 'messageId': message_id,
            'content': {'type': 'text', 'text': text}}


def call(identity):
    return {'sessionUpdate': 'tool_call', 'toolCallId': identity, 'status': 'in_progress'}


def test_only_tool_starts_end_a_segment_and_all_text_survives():
    p = TurnTextProjection()
    rows = [chunk('Check the sources.', 'progress'), call('a'), call('b'),
            chunk('Conclusion with [REF-123].'),
            {'sessionUpdate': 'tool_call_update', 'toolCallId': 'a', 'status': 'completed'},
            call('b'),  # repeated notification cannot erase the answer
            chunk('\nNecessary condition.'),
            {'sessionUpdate': 'agent_thought_chunk', 'content': {'type': 'text', 'text': 'private'}}]
    for row in rows:
        p.accept(row)
    assert p.fields()['text'] == 'Conclusion with [REF-123].\nNecessary condition.'
    assert p.fields()['progress_text'] == 'Check the sources.'


def test_tool_only_turn_does_not_promote_the_preceding_answer_or_progress():
    p = TurnTextProjection()
    p.accept(chunk('Provisional answer; saving now.'))
    p.accept(call('save'))
    assert p.fields()['text'] == ''
    assert p.fields()['progress_text'] == 'Provisional answer; saving now.'


def test_no_tool_answer_keeps_all_chunks_even_multiple_message_ids():
    p = TurnTextProjection()
    p.accept(chunk('Main answer', 'one'))
    p.accept(chunk('\nAdditional detail', 'two'))
    assert p.fields()['text'] == 'Main answer\nAdditional detail'
    assert p.fields()['progress_text'] == ''


def test_completed_legacy_receipt_uses_bound_events_without_editing_original(tmp_path):
    events = tmp_path / 'events.private.jsonl'
    rows = [chunk('Looking up.'), call('a'), chunk('Answer.')]
    events.write_text(''.join(json.dumps({'session_id': 's', 'update': r})+'\n' for r in rows))
    prior = {'status': 'completed', 'session_id': 's', 'text': 'Looking up.Answer.'}
    before = events.read_bytes()
    result = completed_text_projection(prior, events)
    assert result['text'] == 'Answer.' and result['progress_text'] == 'Looking up.'
    assert prior['text'] == 'Looking up.Answer.' and events.read_bytes() == before
    assert completed_text_projection(result, events) == result
    with pytest.raises(ValueError, match='events_mismatch'):
        completed_text_projection({**prior, 'text': 'incomplete record'}, events)
    with pytest.raises(ValueError, match='session_mismatch'):
        completed_text_projection({**prior, 'session_id': 'other'}, events)
    with pytest.raises(ValueError, match='events_missing'):
        completed_text_projection(prior, tmp_path / 'absent')


@pytest.mark.anyio
@pytest.mark.parametrize('stop_reason', ['end_turn', 'max_tokens'])
async def test_live_projection_and_recovery_share_contract_without_model_calls(tmp_path, stop_reason):
    updates = [chunk('Read source.'), call('source'), chunk('Answer [REF-123].')]
    published = []
    client = HarnessSessionClient(tmp_path / 'events.private.jsonl', published.append)
    class Connection:
        calls = 0
        async def prompt(self, **kwargs):
            self.calls += 1
            for update in updates:
                await client.session_update('s', SimpleNamespace(model_dump=lambda **_: update))
            return SimpleNamespace(stop_reason=stop_reason)
    connection = Connection()
    session = HarnessSession(connection, client, 's', authority=lambda: None, stop=lambda: None,
                             turn_path=tmp_path / 'turn.private.json')
    result = await session.prompt('Original task')
    assert result['text'] == 'Answer [REF-123].' and result['progress_text'] == 'Read source.'
    assert [x['text'] for x in published] == ['Read source.', 'Answer [REF-123].']
    assert len(client.events.read_text().splitlines()) == len(updates)
    if stop_reason == 'end_turn':
        assert await session.prompt('Original task') == result
        assert connection.calls == 1
    else:
        assert result['status'] == 'interrupted'
        with pytest.raises(RuntimeError, match='requires_recovery'):
            await session.prompt('Original task')


@pytest.mark.anyio
async def test_native_failure_stops_live_admission_but_not_loaded_history(tmp_path):
    stopped = []
    client = HarnessSessionClient(tmp_path / 'events.jsonl', stop_on_failure=lambda: stopped.append(True))
    failed = {'sessionUpdate': 'tool_call_update', 'toolCallId': 'bad', 'status': 'failed'}
    update = SimpleNamespace(model_dump=lambda **_: failed)
    await client.session_update('s', update)
    assert not stopped
    client.active_turn = True
    await client.session_update('s', update)
    assert stopped == [True]
    assert len(client.events.read_text().splitlines()) == 2


def test_native_unknown_tool_feedback_uses_only_actual_grants(tmp_path):
    events = tmp_path / 'events.jsonl'
    events.write_text(json.dumps({'update': {'sessionUpdate': 'tool_call_update',
        'toolCallId': 'x', 'status': 'failed', 'content': [{'content': {
            'text': 'Error: unknown tool "mcp__financial__writeworkingnote"'}}]}}))
    before = events.read_bytes()
    result = native_tool_recovery(events, ['WriteWorkingNote'])
    assert result[0]['available_exact_names'] == ['mcp__financial__WriteWorkingNote']
    assert result[0]['status'] == 'not_executed'
    assert native_tool_recovery(events, ['write_report'])[0]['available_exact_names'] == []
    assert events.read_bytes() == before
