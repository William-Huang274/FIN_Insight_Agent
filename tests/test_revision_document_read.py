"""Old author checklists are archived data, not reissued revision instructions."""
from copy import deepcopy
import json

from langchain_core.messages import HumanMessage
from sec_agent.agent_runtime.research_context_view import public_operation, history_operation_page
from test_revision_execution_window import revision


ROOT = 'runtime:context:/submission_to_repair/candidate'


def fixture():
    c = revision()
    p = c['submission_to_repair']['candidate']
    p['task_note'] = {'summary': 'Prior analytical summary, not an instruction.',
        'coverage': [{'criterion': 'OLD CHECK EVERY COMPANY', 'status': 'partial'}],
        'issues': [{'next_action': 'OLD EXPAND ALL RESEARCH'}],
        'changes': 'OLD rewrite plan', 'finding_responses': [
            {'finding_id': 'OLD', 'explanation': 'Previous response'},
            {'finding_id': 'F1', 'explanation': 'Current response'}]}
    return c


def test_default_read_separates_checklist_but_preserves_manuscript_and_exact_raw_read():
    c = fixture(); before = deepcopy(c)
    rows = [HumanMessage(content=json.dumps(c))]
    original = public_operation(rows, ROOT)
    assert original['receipt']['result'] == c['submission_to_repair']['candidate']
    page = history_operation_page(original, max_characters=24000)
    document = page['receipt']['result']
    for field, value in c['submission_to_repair']['candidate'].items():
        if field != 'task_note': assert document[field] == value
    assert document['task_note'] == {'summary': 'Prior analytical summary, not an instruction.',
        'finding_responses': [{'finding_id': 'F1', 'explanation': 'Current response'}]}
    assert 'OLD CHECK' not in json.dumps(page) and 'OLD EXPAND' not in json.dumps(page)
    raw = history_operation_page(original, view='record', max_characters=24000)
    assert raw['receipt']['result'] == c['submission_to_repair']['candidate']
    read = page['receipt']['task_record_read']['arguments']
    note = history_operation_page(public_operation(rows, read['tool_call_id']), view=read['view'], max_characters=24000)
    assert note['receipt']['result'] == c['submission_to_repair']['candidate']['task_note']
    assert c == before


def test_paging_projects_before_serialization_and_explicit_historical_field_is_readable():
    c = fixture(); c['submission_to_repair']['candidate']['narrative_markdown'] *= 200
    rows = [HumanMessage(content=json.dumps(c))]
    original = public_operation(rows, ROOT)
    page = history_operation_page(original, max_characters=1000)
    pieces = [page['serialized_record_window']]
    while page['next_read']:
        args = page['next_read']['arguments']
        assert args['view'] == 'receipt'
        page = history_operation_page(original, view=args['view'], offset=args['offset'], max_characters=1000)
        pieces.append(page['serialized_record_window'])
    receipt = json.loads(''.join(pieces))
    assert receipt['result']['narrative_markdown'] == c['submission_to_repair']['candidate']['narrative_markdown']
    assert 'OLD CHECK' not in ''.join(pieces)
    explicit = public_operation(rows, ROOT+'/task_note/coverage')
    assert explicit['receipt']['result'] == c['submission_to_repair']['candidate']['task_note']['coverage']
    assert explicit['field_role'] == 'saved_workpaper_field_not_an_execution_requirement'


def test_current_saved_change_record_is_not_hidden_and_initial_authoring_unchanged():
    c = fixture(); c['submission_to_repair']['draft_state'] = {'changed_paths': ['/task_note/changes']}
    p = history_operation_page(public_operation([HumanMessage(content=json.dumps(c))], ROOT), max_characters=24000)
    assert p['receipt']['result']['task_note']['changes'] == 'OLD rewrite plan'
    del c['task_context']['accepted_revision_baseline']
    record = public_operation([HumanMessage(content=json.dumps(c))], ROOT)
    assert 'revision_document' not in record
    assert history_operation_page(record, max_characters=24000)['receipt']['result'] == c['submission_to_repair']['candidate']
