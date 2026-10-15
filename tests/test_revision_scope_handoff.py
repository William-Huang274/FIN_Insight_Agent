"""Review identity repair must not silently become a new financial assertion."""
from copy import deepcopy

from sec_agent.agent_runtime.author_revision import author_feedback
from sec_agent.agent_runtime.revision_guidance import lead_repair_feedback, AUTHOR_REVISION_GUIDANCE
from test_evidence_resolution import sample
import pytest


def test_lead_remedy_preserves_original_review_and_does_not_mutate_it():
    original = {'finding_id': 'F1', 'requested_change': 'Restore the complete identifier.',
                'source_checks': [], 'finding_type': 'traceability'}
    snapshot = deepcopy(original)
    decision = {'requested_change': 'Preserve 40% and add the cost amount.',
                'rationale': 'Lead proposal, not original source.', 'expected_progress': 'Resolvable citation.'}
    result = lead_repair_feedback(original, decision)
    assert result['requested_change'] == original['requested_change']
    assert result['lead_requested_change'] == decision['requested_change']
    result['source_checks'].append({'source_id': 'other'})
    assert original == snapshot
    next_result = lead_repair_feedback(result, {**decision, 'requested_change': 'Check identifier only.'})
    assert next_result['requested_change'] == original['requested_change']
    assert next_result['lead_requested_change'] == 'Check identifier only.'


def test_legacy_identifier_finding_gets_exact_current_navigation_without_fact_edits():
    artifacts = sample()
    before = artifacts.read_paper('P01')
    finding = {'paper_id': 'P01', 'finding_type': 'other', 'problematic_quote': 'PASSAGE::...2:3',
               'requested_change': 'Restore the identifier; preserve numbers from feedback.'}
    result = author_feedback([finding], artifacts)[0]
    location = result['reference_navigation']['locations'][0]
    assert location['field_path'] == '/narrative_markdown'
    assert location['status'] == 'candidate_requires_confirmation'
    assert location['candidates'][0]['source_id'] == 'P01:S002'
    assert location['candidates'][0]['canonical_ids'] == ['PASSAGE::CHUNK::docA:2:3::hashA']
    assert result['requested_change'] == finding['requested_change']
    assert 'reference_navigation' not in finding
    assert artifacts.read_paper('P01') == before


@pytest.mark.parametrize('kind', ['matched', 'different_quote', 'different_source', 'duplicate', 'absent'])
def test_legacy_overwritten_review_is_recovered_only_from_exact_unique_parent(kind):
    from sec_agent.agent_runtime.revision_guidance import restore_review_request
    original = {'finding_id': 'F1', 'paper_id': 'P01', 'problematic_quote': 'old id',
                'diagnosis': 'Unresolvable identifier.', 'source_checks': [],
                'requested_change': 'Restore complete identifier.'}
    legacy = {**original, 'requested_change': 'Preserve extra numbers.', 'lead_rationale': 'Lead proposal.'}
    parent = deepcopy(original)
    if kind == 'different_quote': parent['problematic_quote'] = 'different id'
    if kind == 'different_source': parent['source_checks'] = [{'source_id': 'other'}]
    parents = [] if kind == 'absent' else [parent, parent] if kind == 'duplicate' else [parent]
    result = restore_review_request(legacy, parents)
    if kind == 'matched':
        assert result['requested_change'] == original['requested_change']
        assert result['lead_requested_change'] == legacy['requested_change']
    else:
        assert result == legacy
    assert legacy['requested_change'] == 'Preserve extra numbers.'


def test_ambiguous_and_stale_reference_navigation_never_selects_or_fabricates_source():
    artifacts = sample()
    artifacts._sources['P01:S003'] = dict(artifacts._sources['P01:S002'],
        passage_id='PASSAGE::CHUNK::docB:2:3::hashB', document_id='docB', node_id='CHUNK::docB:2:3')
    artifacts._papers['P01']['sources']['P01:S003'] = {}
    finding = {'paper_id': 'P01', 'problematic_quote': 'PASSAGE::...2:3'}
    result = author_feedback([finding], artifacts)[0]
    location = result['reference_navigation']['locations'][0]
    assert location['status'] == 'ambiguous' and len(location['candidates']) == 2
    artifacts._papers['P01']['workpaper']['narrative_markdown'] = 'No reference here.'
    assert 'reference_navigation' not in author_feedback([finding], artifacts)[0]


def test_native_revision_request_replaces_unconditional_reread_instruction():
    from test_connected_revision_loop import submitted_original
    from test_specialist_graph import _input, _ToolPorts
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    original = submitted_original()
    original['task_context'] = {'revision_instruction': 'Read relevant original sources to evaluate every assigned finding'}
    ports = _ToolPorts()
    graph = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=lambda _: None, evidence_tool=ports.evidence, finance_tool=ports.finance),
        recovery_state=original, revision_feedback=[{'finding_id': 'F1'}]).compile()
    events = graph.stream(_input(), stream_mode='values')
    next(events)
    state = next(events)
    events.close()
    assert state['task_context']['revision_instruction'] == AUTHOR_REVISION_GUIDANCE
    assert state['last_submission_attempt']['arguments']['claims'] == original['final_submission']['claims']
    assert state['notebook']['observations'] == original['notebook']['observations']
