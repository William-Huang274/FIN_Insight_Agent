from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from sec_agent.agent_runtime.research_context_view import public_operation, history_operation_page, working_view
from test_revision_execution_window import revision

ROOT = 'runtime:context:/submission_to_repair/candidate'


def begin():
    c = revision()
    c['submission_to_repair']['candidate']['narrative_markdown'] = 'Unneeded whole manuscript. ' * 3000
    return c, [SystemMessage(content='fixture'), HumanMessage(content=json.dumps(c))]


def read(rows, c, path, cid='field-read', max_characters=24000):
    args = {'section': 'operation', 'tool_call_id': ROOT + path, 'max_characters': max_characters}
    page = history_operation_page(public_operation(rows, ROOT + path), max_characters=max_characters)
    action(rows, c, 'ReadResearchHistoryAction', args, {'historical_record': page}, cid)


def action(rows, c, name, args, result, cid, status='success'):
    rows.extend([AIMessage(content='', tool_calls=[{'name': name, 'id': cid, 'args': args}]),
        ToolMessage(name=name, tool_call_id=cid, status=status,
                    content=json.dumps({'result': result, 'current_context': deepcopy(c)}))])


def visible(rows):
    return next(json.loads(m.content) for m in working_view(rows) if m.additional_kwargs.get('fin_research_working_view'))


def test_outline_keeps_current_statements_and_exact_reads_without_pin_of_whole_old_paper():
    c, rows = begin(); original = deepcopy(rows)
    v = visible(rows); repair = v['current_context']['submission_to_repair']
    outline = repair['manuscript']['claim_outline']
    assert outline[1]['statement'] == 'Unchanged other claim'
    assert 'statement' not in outline[0]  # Complete target already lives in current_fragment.
    assert 'Unneeded whole manuscript.' not in json.dumps(v)
    for row, claim in zip(outline, c['submission_to_repair']['candidate']['claims']):
        assert public_operation(rows, row['read']['arguments']['tool_call_id'])['receipt']['result'] == claim
    assert rows == original


def test_focused_read_survives_calculation_then_failed_save_and_retires_after_success():
    c, rows = begin()
    read(rows, c, '/claims/1')
    assert visible(rows)['current_context']['submission_to_repair']['manuscript']['open_fields'] == []
    action(rows, c, 'RequestCalculationAction', {}, {'calculation': 'fixture'}, 'calc')
    kept = visible(rows)['current_context']['submission_to_repair']['manuscript']['open_fields']
    assert kept[0]['value'] == c['submission_to_repair']['candidate']['claims'][1]
    action(rows, c, 'SaveWorkpaperEditsAction', {}, {'saved': False, 'error': 'bad path'}, 'bad', 'error')
    assert visible(rows)['current_context']['submission_to_repair']['manuscript']['open_fields'] == kept
    c['submission_to_repair']['candidate']['claims'][1]['statement'] = 'Updated statement'
    action(rows, c, 'SaveWorkpaperEditsAction', {}, {'saved': True, 'changed_paths': ['/claims/1/statement']}, 'save')
    v = visible(rows)['current_context']['submission_to_repair']['manuscript']
    assert v['open_fields'] == [] and v['claim_outline'][1]['statement'] == 'Updated statement'
    assert public_operation(rows, ROOT+'/claims/1')['receipt']['result']['statement'] == 'Updated statement'


def test_whole_record_and_old_checklist_reads_do_not_expand_persistent_editing_surface():
    c, rows = begin()
    read(rows, c, '')
    read(rows, c, '/task_note/coverage', 'old-checklist')
    action(rows, c, 'RequestCalculationAction', {}, {'calculation': 'fixture'}, 'calc')
    surface = visible(rows)['current_context']['submission_to_repair']['manuscript']
    assert not surface['open_fields']
    assert 'OLD CRITERION' not in json.dumps(surface)
    assert 'Unneeded whole manuscript.' not in json.dumps(surface)


def test_changed_or_reordered_claim_never_resurrects_old_text():
    c, rows = begin(); read(rows, c, '/claims/1')
    c['submission_to_repair']['candidate']['claims'].reverse()
    action(rows, c, 'RequestCalculationAction', {}, {'calculation': 'fixture'}, 'calc')
    surface = visible(rows)['current_context']['submission_to_repair']['manuscript']
    assert surface['open_fields'] == []
    assert surface['claim_outline'][0]['statement'] == 'Unchanged other claim'
    assert surface['claim_outline'][0]['read']['arguments']['tool_call_id'].endswith('/claims/0')


def test_new_revision_boundary_releases_prior_open_fields():
    c, rows = begin(); read(rows, c, '/claims/1')
    rows.append(HumanMessage(content=json.dumps(c), additional_kwargs={'fin_research_stage_boundary': 'accepted_submission_to_revision'}))
    action(rows, c, 'RequestCalculationAction', {}, {'calculation': 'fixture'}, 'calc')
    assert visible(rows)['current_context']['submission_to_repair']['manuscript']['open_fields'] == []


def test_partial_field_read_keeps_only_read_window_and_next_page_locator():
    c, rows = begin(); read(rows, c, '/narrative_markdown', max_characters=1000)
    action(rows, c, 'RequestCalculationAction', {}, {'calculation': 'fixture'}, 'calc')
    fields = visible(rows)['current_context']['submission_to_repair']['manuscript']['open_fields']
    assert len(fields)==1 and 'value' not in fields[0]
    page = fields[0]['read_windows'][0]['page']
    assert len(page['serialized_record_window'])==1000
    assert page['next_read']['arguments']['offset']==1000
    assert page['next_read']['arguments']['tool_call_id']==ROOT+'/narrative_markdown'


def test_source_material_handoff_does_not_end_active_manuscript_edit():
    c, rows = begin(); read(rows, c, '/claims/1')
    rows.append(HumanMessage(content=json.dumps(c), additional_kwargs={'fin_research_stage_boundary': 'revision_material_handoff', 'fin_revision_material_ids': []}))
    action(rows, c, 'RequestCalculationAction', {}, {'calculation': 'fixture'}, 'calc')
    surface = visible(rows)['current_context']['submission_to_repair']['manuscript']
    assert surface['open_fields'][0]['value']['statement']=='Unchanged other claim'
    assert 'statement' not in surface['claim_outline'][1]
