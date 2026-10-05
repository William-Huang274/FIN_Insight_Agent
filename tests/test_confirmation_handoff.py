from copy import deepcopy
import json

from sec_agent.agent_runtime.review_recovery import public_confirmation


def test_incomplete_confirmation_handoff_excludes_private_recovery_journal():
    record = {'context': {'author_responses': {'P02': ['not independently closed']},
                          'paper_version_digests': {'P02': 'current'}},
              'correction_round': 1, 'review': {'phase': 'case_review_incomplete',
              'scope_digest': 'scope', 'counter': {
                  'status': 'review_submitted', 'model_calls': 21, 'tool_calls': 30,
                  'review': {'completion': 'incomplete', 'findings': [{'finding_id': 'unit'}],
                             'unresolved_data_requests': ['read current claim'],
                             'inspection_checks': [{'status': 'incomplete'}]},
                  'recorded_findings': {'unit': {'diagnosis': 'unit mismatch'}},
                  'tool_feedback': ['invalid field path'],
                  'recovery_state': {'messages': [{'reasoning_content': 'PRIVATE_SENTINEL'}]},
                  'incomplete_output': ['PRIVATE_SENTINEL'],
                  'runtime_notices': ['PRIVATE_SENTINEL']}}}
    original = deepcopy(record)
    view = public_confirmation(record)
    assert 'PRIVATE_SENTINEL' not in json.dumps(view)
    assert view['context'] == record['context']
    assert view['review']['phase'] == 'case_review_incomplete'
    row = view['review']['counter']
    assert row['review'] == record['review']['counter']['review']
    assert row['recorded_findings'] == record['review']['counter']['recorded_findings']
    assert row['tool_feedback'] == ['invalid field path'] and row['resumable']
    assert record == original
    row['review']['findings'].clear()
    assert record == original
