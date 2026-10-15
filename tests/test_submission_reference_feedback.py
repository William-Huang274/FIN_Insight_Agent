from copy import deepcopy
import json

from sec_agent.agent_runtime.submission_reference_feedback import (
    reference_issue, refresh_reference_feedback, refresh_terminal_receipts,
)


NODE = 'CHUNK::' + 'a' * 40
PASSAGE = 'PASSAGE::' + NODE


def fixture():
    selection = {'operation': 'read', 'source_space': 'library',
                 'document_id': 'DOC::fixture', 'node_id': NODE}
    notebook = {'observations': [{'references': [{'ref_id': NODE,
        'authority_state': 'retrieval_candidate', 'writer_citable': False}],
        'content': [{'node_id': NODE, 'result_state': 'retrieval_candidate',
                     'readback': selection}]}]}
    paper = {'action': 'submit_workpaper', 'claims': [
        {'evidence_ids': [PASSAGE]}, {'evidence_ids': [PASSAGE]}]}
    return notebook, paper, selection


def test_candidate_diagnosis_returns_exact_readback_without_promoting_or_mutating():
    notebook, paper, selection = fixture()
    before = deepcopy((notebook, paper))
    issue = reference_issue('unknown_evidence_id:' + PASSAGE, paper, notebook)
    assert issue['diagnosis'] == 'candidate_not_source_bound'
    assert issue['readback_options'] == [selection]
    assert issue['affected_locations'] == [['claims', 0, 'evidence_ids', 0], ['claims', 1, 'evidence_ids', 0]]
    assert 'Adding PASSAGE::' in issue['instruction']
    assert (notebook, paper) == before


def test_unknown_spelling_is_not_confused_with_candidate_or_inferred_from_prose():
    notebook, paper, _ = fixture()
    notebook['observations'][0]['references'].append({'ref_id': PASSAGE,
        'writer_citable': True, 'authority_state': 'source_bound_passage'})
    typo = PASSAGE[:-1]
    issue = reference_issue('unknown_evidence_id:' + typo, paper, notebook)
    assert issue['diagnosis'] == 'unique_observed_spelling_match'
    assert issue['suggested_id'] == PASSAGE
    notebook['observations'][0]['references'].append({'ref_id': PASSAGE[:-1] + 'b'})
    assert reference_issue('unknown_evidence_id:' + typo, paper, notebook)['diagnosis'] == 'ambiguous_reference_spelling'
    assert reference_issue('unknown_evidence_id:P01:S001', paper, notebook)['diagnosis'] == 'unobserved_reference'


def test_saved_helper_requires_original_observation_then_explicit_binding():
    notebook, paper, _ = fixture()
    helper = {'H1': {'result': {'phase': 'specialist_submission_accepted', 'notebook': {
        'observations': [{'observation_digest': 'obs123', 'references': [
            {'ref_id': 'E:helper', 'writer_citable': True}]}]}}}}
    issue = reference_issue('unknown_evidence_id:E:helper', paper, notebook, helper)
    assert issue['diagnosis'] == 'helper_source_not_bound'
    assert issue['readback']['source_observation_ref'] == 'obs123'
    assert issue['readback']['subtask_id'] == 'H1'
    helper['H1']['result']['phase'] = 'unfinished'
    assert reference_issue('unknown_evidence_id:E:helper', paper, notebook, helper)['diagnosis'] == 'unobserved_reference'


def test_recovery_projects_feedback_only_on_matching_rejected_receipt():
    notebook, paper, _ = fixture()
    old = {'location': ['references'], 'message': 'unknown_evidence_id:' + PASSAGE}
    last = {'accepted': False, 'arguments': paper, 'validation_issues': [old]}
    receipt = {'name': 'SubmitWorkpaperAction', 'status': 'error', 'tool_call_id': 'call1',
               'content': json.dumps({'accepted': False, 'validation_issues': [old]})}
    before = deepcopy((last, receipt))
    refreshed = refresh_reference_feedback(last, notebook)
    projected = refresh_terminal_receipts([receipt], refreshed)[0]
    assert json.loads(projected['content'])['validation_issues'][0]['diagnosis'] == 'candidate_not_source_bound'
    assert projected['tool_call_id'] == 'call1'
    assert (last, receipt) == before
    other = {**receipt, 'content': json.dumps({'accepted': False, 'validation_issues': [{'message': 'other'}]})}
    assert refresh_terminal_receipts([other], refreshed) == [other]
    assert refresh_reference_feedback({**last, 'accepted': True}, notebook)['validation_issues'] == [old]
