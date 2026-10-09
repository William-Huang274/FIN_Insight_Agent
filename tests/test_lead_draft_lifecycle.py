import asyncio
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from test_case_review_agent import artifacts, call
from test_report_synthesis_agent import NativeFixtureModel
from test_request_summary import policy
from sec_agent.agent_runtime.lead_draft_context import project_lead_draft
from sec_agent.agent_runtime.report_authoring import research_handoff
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
from sec_agent.agent_runtime.source_reading_windows import reading_windows


def exchange(name, args, result, key, status='success'):
    return [AIMessage(content='', id='ai-' + key, tool_calls=[call(name, args, key)],
                additional_kwargs={'reasoning_content': 'private-' + key}),
            ToolMessage(content=json.dumps(result), id='tool-' + key, tool_call_id=key, name=name, status=status)]


def saved(body, version):
    return exchange('WriteWorkingNote', {'title': '研究草稿', 'body': body, 'mode': 'replace', 'base_version': version-1},
        {'saved': True, 'note_id': 'note-one', 'version': version}, 'save' + str(version))


def test_repeated_replacement_retires_old_text_retains_task_navigation_and_fresh_reads():
    rows = [HumanMessage(content='Original research question', id='user')]
    rows += exchange('read_current_source', {'source_id': 'S1'}, {'text': 'OLD SOURCE BODY'}, 'r1')
    rows += saved('Initial explanation [S1]', 1)
    rows += [HumanMessage(content='User correction: include customer payments', id='correction')]
    rows += exchange('read_current_source', {'source_id': 'S2'}, {'text': 'SECOND SOURCE BODY'}, 'r2')
    rows += saved('Updated explanation and countercase [S1] [S2]', 2)
    rows += exchange('read_current_source', {'source_id': 'S3'}, {'text': 'UNCONSUMED SOURCE BODY'}, 'r3')
    original = deepcopy(rows)
    projected, key = project_lead_draft(rows)
    text = json.dumps([m.model_dump() for m in projected])
    assert 'OLD SOURCE BODY' not in text and 'SECOND SOURCE BODY' not in text
    assert 'Initial explanation' not in text and 'Updated explanation' in text
    assert 'Original research question' in text and 'User correction' in text
    assert 'S1' in text and 'S2' in text and 'UNCONSUMED SOURCE BODY' in text
    assert 'private-save1' not in text and 'private-r3' in text
    assert rows == original and projected[-2:] == rows[-2:]
    assert project_lead_draft(rows)[1] == key


def test_failed_save_cannot_release_reads_and_parallel_new_result_survives():
    rows = [HumanMessage(content='Question', id='u')]
    rows += exchange('read_current_source', {'source_id': 'S1'}, {'text': 'Original'}, 'r1')
    rows += exchange('WriteWorkingNote', {'title': 'Draft', 'body': 'Unsaved'}, {'saved': False}, 'bad')
    assert project_lead_draft(rows) == (rows, None)
    write = call('WriteWorkingNote', {'title': 'Draft', 'body': 'Saved', 'mode': 'replace'}, 'ok')
    read = call('read_current_source', {'source_id': 'S2'}, 'parallel')
    rows += [AIMessage(content='', tool_calls=[write, read], id='parallel-ai'),
        ToolMessage(content='{"text":"NEW PARALLEL EVIDENCE"}', tool_call_id='parallel', name='read_current_source'),
        ToolMessage(content='{"saved":true,"note_id":"n","version":1}', tool_call_id='ok', name='WriteWorkingNote')]
    view, _ = project_lead_draft(rows)
    assert 'NEW PARALLEL EVIDENCE' in json.dumps([m.model_dump() for m in view])
    assert not any(isinstance(m, ToolMessage) for m in view)


def test_archiving_keeps_exact_read_citation_ids_without_old_author_text():
    rows = [HumanMessage(content='Question', id='u')]
    rows += exchange('read_current_workpaper', {'paper_id': 'P01', 'section': 'analysis'},
        {'paper_id': 'P01', 'version': 'old', 'claims': [{'citation_id': 'P01:OLD'}]}, 'old')
    rows += exchange('read_current_workpaper', {'paper_id': 'P01', 'section': 'handoff'},
        {'paper_id': 'P01', 'version': 'current', 'source_catalog': [
            {'source_id': 'S1', 'citation_ids': ['P01:C14_FULL_EXACT_ID']}],
         'source_materials': [{'text': 'OLD SOURCE TEXT'}]}, 'source')
    rows += exchange('read_current_workpaper', {'paper_id': 'P01', 'section': 'citations'},
        {'paper_id': 'P01', 'version': 'current', 'citations': [
            {'citation_id': 'P01:C14_FULL_EXACT_ID', 'statement_preview': 'OLD AUTHOR TEXT'},
            {'claim_id': 'C15_FULL_EXACT_ID'}]}, 'ids')
    rows += saved('My current understanding with a shorthand [P01:C14]', 1)
    projected, _ = project_lead_draft(rows)
    history = json.loads(projected[1].content)
    assert history['available_citations']['P01'] == {'version': 'current',
        'citation_ids': ['P01:C14_FULL_EXACT_ID', 'P01:C15_FULL_EXACT_ID']}
    text = json.dumps([m.model_dump() for m in projected])
    assert 'OLD SOURCE TEXT' not in text and 'OLD AUTHOR TEXT' not in text and 'P01:OLD' not in text


def test_native_summary_uses_projected_history_and_new_draft_supersedes_old_summary():
    async def run():
        calls = []
        middleware = policy(calls, trigger=1500, keep=200)
        middleware.history_projection = project_lead_draft
        rows = [HumanMessage(content='Question', id='u')]
        rows += exchange('read_current_source', {'source_id': 'S1'}, {'text': 'BIG OLD SOURCE ' * 10000}, 'r1')
        rows += saved('Current judgment [S1]', 1)
        assert await middleware.abefore_model({'messages': rows}, None) is None
        assert not calls  # No paid summary of already archived originals.
        for i in range(6):
            rows += exchange('read_current_source', {'source_id': 'S2'}, {'text': 'NEW FACT ' * 500}, f'new{i}')
        update = await middleware.abefore_model({'messages': rows}, None)
        assert update and len(calls) == 1
        state = {'messages': rows, **update}
        first = middleware.projected_messages(middleware._working_state(state))
        assert first[0].content == 'Question'
        rows += saved('Revised current judgment [S1] [S2]', 2)
        assert 'request_summary' not in middleware._working_state(state)
        assert await middleware.abefore_model(state, None) is None
        assert len(calls) == 1
        # Replacing a draft invalidates summary content, not the paid-call cap.
        middleware.max_summaries = 1
        for i in range(6):
            rows += exchange('read_current_source', {'source_id': 'S3'}, {'text': 'LATER FACT ' * 500}, f'later{i}')
        assert await middleware.abefore_model(state, None) is None
        assert len(calls) == 1
    asyncio.run(run())


def test_summary_pins_actual_correction_and_current_draft_separately():
    from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware
    rows = [HumanMessage(content='Question', id='u'), HumanMessage(content='Actual correction', id='c')]
    rows += saved('CURRENT DRAFT', 1)
    rows += exchange('read_current_source', {'source_id': 'S2'}, {'text': 'Fresh read'}, 'r2')
    projected, key = project_lead_draft(rows)
    end = len(projected) - 2
    state = {'messages': projected, 'request_summary': {'prefix_end': end,
        'first_original_id': projected[0].id, 'last_original_id': projected[end-1].id,
        'projection_key': key, 'message': HumanMessage(content='Lossy summary').model_dump()}}
    output = RequestSummaryMiddleware.projected_messages(state)
    assert [m.content for m in output[:3]] == ['Question', 'Lossy summary', 'Actual correction']
    assert 'CURRENT DRAFT' in output[3].content and output[-2:] == rows[-2:]


def test_source_context_keeps_causal_sentence_and_preserves_literal_offsets():
    class Sources:
        def source_item(self, _):
            return {'result_state': 'source_bound_passage'}
        def _source_text(self, _):
            return ('Earlier background.\n\n' * 250 +
                'Cost increased from USD 4.3 million in 2023 to USD 26.8 million in 2024.\n'
                'Cloud costs rose because customer API use increased. This is one issuer only.\n\n' +
                'Other background.\n\n' * 250)
    source = Sources()
    result = reading_windows(source, 'S1', ['Cost increased from USD 4.3 million in 2023 to USD 26.8 million'])
    text = source._source_text({})
    assert 'in 2024' in result['windows'][0]['text']
    assert 'because customer API use increased' in result['windows'][0]['text']
    for window in result['windows']:
        assert text[window['offset']:window['end_offset']] == window['text']
    assert result['windows'][0]['read_more']


def test_pagination_keeps_every_source_discoverable_and_selected_read_matches(artifacts):
    full = research_handoff(artifacts, 'P01')
    refs = [r['source_id'] for r in full['source_materials']]
    first = research_handoff(artifacts, 'P01', limit=1)
    assert [r['source_id'] for r in first['source_catalog']] == refs
    pages = [research_handoff(artifacts, 'P01', offset=i, limit=1) for i in range(len(refs))]
    assert [p['source_materials'][0] for p in pages] == full['source_materials']
    assert pages[-1]['next_read'] is None
    selected = research_handoff(artifacts, 'P01', source_ids=[refs[-1]], limit=1)
    assert selected['source_materials'][0] == full['source_materials'][-1]


def test_native_lead_reads_updates_twice_then_writes_from_latest_draft(artifacts, monkeypatch, tmp_path):
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(tmp_path / 'notes.sqlite'))
    monkeypatch.setenv('FINSIGHT_AUTH_MODE', 'local')
    citation = 'P01:' + artifacts.read_paper('P01')['claims'][0]['claim_id']
    class Sequential(NativeFixtureModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.contexts.append(deepcopy(messages))
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='',
                tool_calls=self.replies[len(self.contexts)-1], additional_kwargs={'reasoning_content': self.marker}))])
    model = Sequential(marker='native-draft', replies=[
        [call('read_current_workpaper', {'paper_id':'P01'}, 'read1')],
        [call('WriteWorkingNote', {'title':'研究草稿','body':'Initial understanding ['+citation+']','mode':'replace'}, 'save1')],
        [call('read_current_workpaper', {'paper_id':'P01','section':'analysis'}, 'read2')],
        [call('WriteWorkingNote', {'title':'研究草稿','body':'Changed interpretation with conditions ['+citation+']','mode':'replace','base_version':1}, 'save2')],
        [call('submit_case_report', {'report':{'title':'Synthetic report',
            'narrative_markdown':'Synthetic interpretation from current research, not financial certification. '*5+'['+citation+']'}}, 'report')]])
    async def run():
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls':6,'tool_calls':8})
        return await agent.ainvoke({'messages':[HumanMessage(content='Original question')]},
            {'configurable':{'thread_id':'test-lead'}})
    result = asyncio.run(run())
    assert result['output']['title'] == 'Synthetic report'
    last = json.dumps([m.model_dump() for m in model.contexts[-1]])
    assert 'Changed interpretation' in last and 'Initial understanding' not in last
    assert 'source_materials.v4' not in last
    mem = WorkingMemory(tmp_path/'notes.sqlite',owner='local-pilot',workspace='test-lead',actor='synthesis:report')
    note = mem.search()['items'][0]
    assert mem.read(note['id'],version=1)['body'].startswith('Initial')
    assert mem.read(note['id'])['body'].startswith('Changed')
