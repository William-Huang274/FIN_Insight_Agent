"""Keep typed calculation lineage without writing the author's analysis."""
from copy import deepcopy
import json

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from sec_agent.agent_runtime.calculation_bindings import calculation_binding_issues
from sec_agent.agent_runtime.submission_reference_feedback import reference_issue
from sec_agent.agent_runtime.specialist_graph import SaveWorkpaperEditsAction
from sec_agent.agent_runtime.workpaper_drafts import save_draft
from test_workpaper_draft_lifecycle import state, save_action


CALC = 'CALC::fixture'


def notebook(verified=True):
    return {'observations': [{'status': 'success', 'failure': None,
        'references': [{'ref_id': CALC, 'authority_state': 'non_authoritative_metric',
                        'writer_citable': False, 'numeric_fact_authority': False}],
        'content': [{'calculation_id': CALC, 'result_state': 'non_authoritative_metric',
                     'arithmetic_verified': verified, 'numeric_fact_authority': False}]}]}


def paper(bound=True):
    return {'narrative_markdown': 'Assumption-bound computed result (' + CALC + ').',
        'claims': [{'claim_id': 'C1', 'kind': 'inference', 'numeric_authority': 'not_applicable',
            'statement': 'Interpretation with source evidence and assumptions.',
            'evidence_ids': ['PASSAGE::source'], 'fact_ids': [CALC] if bound else []}]}


def blocking(p, n=None, prior=None):
    return [r for r in calculation_binding_issues(p, n or notebook(), prior) if r['blocking']]


def test_removal_while_prose_remains_locates_claim_and_preserves_all_inputs():
    old, new, nb = paper(), paper(False), notebook()
    before = deepcopy((old, new, nb))
    issues = blocking(new, nb, old)
    assert len(issues) == 1
    issue = issues[0]
    assert issue['code'] == 'calculation_binding_missing'
    assert issue['location'] == ['claims', 0, 'fact_ids']
    assert issue['removed_claim_ids'] == ['C1'] and issue['source_id'] == CALC
    assert issue['classification_options'][0] == {
        'kind': 'inference', 'numeric_authority': 'not_applicable',
        'when': 'The assertion interprets disclosure or an observed calculation; preserve supporting PASSAGE and CALC bindings.'}
    assert (old, new, nb) == before


def test_binding_and_verified_receipt_make_analysis_valid_without_authority_promotion():
    p, nb = paper(), notebook()
    original = deepcopy((p, nb))
    assert blocking(p, nb) == []
    assert (p, nb) == original
    assert not nb['observations'][0]['references'][0]['writer_citable']
    assert p['claims'][0]['numeric_authority'] == 'not_applicable'


def test_another_claim_binding_does_not_cover_an_explicit_unbound_claim_reference():
    p = paper()
    p['claims'].append({'claim_id': 'C2', 'kind': 'inference', 'fact_ids': [],
                        'statement': 'Uses ' + CALC})
    issues = blocking(p)
    assert issues[0]['claim_ids'] == ['C2']
    assert issues[0]['location'] == ['claims', 1, 'statement']


@pytest.mark.parametrize('kind', ['inference', 'calculation', 'hypothesis', 'boundary'])
def test_reclassification_never_bypasses_canonical_receipt_verification(kind):
    p = paper(); p['claims'][0]['kind'] = kind
    assert blocking(p, notebook(False))[0]['code'] == 'calculation_receipt_unverified'


def test_unknown_explicit_prose_calculation_is_detected():
    p = paper(False)
    p['narrative_markdown'] = 'Result CALC::unknown.'
    assert {r['code'] for r in blocking(p)} == {'calculation_reference_unobserved', 'calculation_binding_missing'}


def test_administrative_records_and_source_quotes_are_not_reissued_as_dependencies():
    p = paper()
    p.update(task_note={'issues': ['Old failure CALC::unknown']}, reason_summary='Old repair CALC::unknown')
    p['claims'][0]['citation_quotes'] = {'PASSAGE::source': 'Quoted source text says CALC::unknown.'}
    assert blocking(p) == []


def test_retirement_and_reassignment_are_advisory_and_no_keyword_semantic_gate():
    old, new = paper(), paper(False)
    new['narrative_markdown'] = 'Illustrative 1/15 versus 1/25; no explicit ID.'
    issues = calculation_binding_issues(new, notebook(), old)
    assert len(issues) == 1 and issues[0]['code'] == 'calculation_binding_removed' and not issues[0]['blocking']
    new['claims'].append({'claim_id': 'C2', 'kind': 'calculation', 'statement': 'Computed result.', 'fact_ids': [CALC]})
    new['narrative_markdown'] = old['narrative_markdown']
    assert not blocking(new, notebook(), old)


def test_classification_feedback_locates_id_and_keeps_choice_with_author():
    p, nb = paper(), notebook()
    p['claims'][0]['kind'] = 'reported_fact'
    before = deepcopy((p, nb))
    issue = reference_issue('fact_reference_authority_invalid:reported_fact:' + CALC, p, nb)
    assert issue['location'] == ['claims', 0, 'fact_ids', 0]
    assert issue['claim_ids'] == ['C1']
    assert issue['observed_authority'] == 'non_authoritative_metric'
    assert [r['kind'] for r in issue['classification_options']] == ['inference', 'calculation']
    assert 'will not choose a kind' in issue['instruction']
    assert (p, nb) == before


def test_save_keeps_incomplete_batch_and_surfaces_warning_without_auto_rebinding():
    s = state(); s['notebook'] = notebook()
    cid = s['last_submission_attempt']['arguments']['claims'][0]['claim_id']
    s['last_submission_attempt']['arguments']['claims'][0].update(
        kind='inference', numeric_authority='not_applicable', fact_ids=[CALC], authority_note='Explicit assumptions.')
    s['last_submission_attempt']['arguments']['narrative_markdown'] += '\nResult (' + CALC + ').'
    before = deepcopy(s)
    action = save_action(s, [{'op': 'update_claim', 'claim_id': cid, 'changes': {'fact_ids': []}}])
    draft, receipt = save_draft(s, action)
    assert receipt['saved'] and not receipt['accepted'] and not receipt['submitted']
    issue = receipt['calculation_binding_issues'][0]
    assert issue['blocks_final_submission'] and not issue['blocking']
    assert issue['removed_claim_ids'] == [cid]
    assert draft['arguments']['claims'][0]['fact_ids'] == []
    assert draft['arguments']['claims'][0]['kind'] == 'inference'
    assert draft['arguments']['narrative_markdown'] == before['last_submission_attempt']['arguments']['narrative_markdown']
    assert s == before
    restored = {**s, 'workpaper_draft': json.loads(json.dumps(draft))}
    repeated, again = save_draft(restored, action)
    assert repeated == draft and again['replayed']
    corrected, good = save_draft(restored, save_action(restored,
        [{'op': 'update_claim', 'claim_id': cid, 'changes': {'fact_ids': [CALC]}}], operation='rebind'))
    assert 'calculation_binding_issues' not in good
    assert corrected['arguments']['claims'][0]['fact_ids'] == [CALC]


def test_revision_schema_teaches_the_same_kind_contract_as_first_submission():
    from sec_agent.agent_runtime.specialist_graph import SpecialistClaim, WorkpaperClaimChanges
    first = SpecialistClaim.model_json_schema()['properties']['kind']['description']
    revised = WorkpaperClaimChanges.model_json_schema()['properties']['kind']['description']
    assert first == revised and 'inference' in revised and 'not_applicable' in revised
    assert 'separate the assertions' not in revised  # Local update_claim cannot insert new claims.
    tool = json.dumps(convert_to_openai_tool(SaveWorkpaperEditsAction), ensure_ascii=False)
    assert 'Preserve its binding while dependent text remains' in tool


def test_reading_old_accepted_history_is_not_new_submission_approval():
    from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
    from sec_agent.agent_runtime.specialist_graph import SubmitWorkpaperAction, SpecialistNotebook, _submission_errors
    from test_research_session import _new_worker_fixture
    old = _new_worker_fixture()
    old['final_submission']['narrative_markdown'] += '\nHistorical text CALC::legacy.'
    before = deepcopy(old)
    view = CaseArtifacts([old])
    assert 'CALC::legacy' in view.read_paper('P01')['narrative_markdown']
    with pytest.raises(ValueError, match='unknown_source_id'):
        view.source_item('CALC::legacy')
    errors = _submission_errors(SubmitWorkpaperAction.model_validate_json(json.dumps(old['final_submission'])),
        SpecialistNotebook.model_validate_json(json.dumps(old['notebook'])), enforce_case_route_requirements=False)
    assert 'calculation_binding:calculation_reference_unobserved:CALC::legacy' in errors
    assert old == before


@pytest.mark.parametrize('claims', [None, 'invalid', {}, [None], [{'fact_ids': None}], [{'fact_ids': 'invalid'}]])
def test_partial_rejected_schema_remains_available_for_original_shape_feedback(claims):
    value = {'claims': claims}
    old = deepcopy(value)
    assert isinstance(calculation_binding_issues(value, notebook()), list)
    assert value == old  # Do not repair or invent fields in malformed proposals.


def test_native_submission_returns_local_calculation_diagnostics_without_model_retry():
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    from test_specialist_graph import _input, _ToolPorts, _evidence_action, _finance_action
    from test_specialist_tool_batch import _batch, _handoff
    from test_workpaper_partial_edits import paper as workpaper
    requests = []; ports = _ToolPorts()
    def turn(request):
        requests.append(request)
        if len(requests) == 1: return _batch(request, [_evidence_action()({}), _finance_action()({})])
        if len(requests) == 2:
            p = workpaper(); p['narrative_markdown'] += '\nResult ' + CALC
            return _batch(request, [p])
        issue = next(r for r in request['submission_to_repair']['validation_feedback']['issues']
                     if r.get('code') == 'calculation_binding_missing')
        assert issue['location'] == ['narrative_markdown'] and issue['source_id'] == CALC
        return _handoff(request)
    result = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance,
        allow_workpaper_field_edits=True)).compile().invoke(_input(), {'recursion_limit': 30})
    assert len(requests) == 3 and result.get('final_submission') is None
