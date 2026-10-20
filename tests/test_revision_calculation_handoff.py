from copy import deepcopy
import json

import pytest

from sec_agent.agent_runtime.revision_calculation_handoff import restore_revision_calculations
from sec_agent.agent_runtime.research_context_view import compact_current_context, public_operation
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources, ObservedSourceRegistry
from test_research_convergence import artifact_fixture


def inputs():
    artifacts = artifact_fixture()
    state = deepcopy(artifacts._author_states['P01'])
    calc = calculate_from_sources(SourceBoundCalculation(expression='a*2', operands={
        'a': {'literal': '3', 'assumption_note': 'Synthetic assumption only'}}, result_unit='units',
        rationale='No financial interpretation'), artifacts.source_item)
    ref = calc['calculation_id']
    decision = {'dispositions': [{'paper_id': 'P01', 'disposition': 'repair', 'citation_ids': [ref]}],
        'citations': {ref: {'sources': [{'source_id': ref, 'calculation': calc}]}}}
    return state, decision, artifacts, ref


def test_saved_receipt_retains_identity_is_idempotent_and_can_be_read_and_calculated():
    from langchain_core.messages import HumanMessage
    state, decision, artifacts, ref = inputs()
    original = deepcopy(state)
    restored = restore_revision_calculations(state, decision, artifacts, 'P01')
    assert state == original
    assert restored['final_submission'] == state['final_submission']
    assert restored['notebook']['model_turn_count'] == state['notebook']['model_turn_count']
    assert restored['notebook']['observations'][:-1] == state['notebook']['observations']
    assert restore_revision_calculations(restored, decision, artifacts, 'P01') == restored
    registry = ObservedSourceRegistry(restored['notebook']['observations'])
    assert registry.get(ref) == decision['citations'][ref]['sources'][0]['calculation']
    value = calculate_from_sources(SourceBoundCalculation(expression='x/2', operands={'x': {'source_id': ref}},
        result_unit='units', rationale='Use exact transferred receipt'), registry.get)
    assert value['value_decimal'] == '3'
    context = {'task_context': restored['task_context']}
    row = compact_current_context(context)['task_context']['revision_calculation_handoff']['calculations'][0]
    result = public_operation([HumanMessage(content=json.dumps(context))], row['read']['arguments']['tool_call_id'])
    assert result['receipt']['result']['calculation'] == registry.get(ref)
    assert row['financial_semantics_verified'] is False


def test_receipts_do_not_cross_papers_or_accept_tampering():
    state, decision, artifacts, ref = inputs()
    assert restore_revision_calculations(state, decision, artifacts, 'P02') == state
    decision['citations'][ref]['sources'][0]['calculation']['value_decimal'] = '7'
    with pytest.raises(ValueError, match='original_mismatch'):
        restore_revision_calculations(state, decision, artifacts, 'P01')


def test_missing_receipt_and_case_scope_fail_before_model_dispatch():
    state, decision, artifacts, ref = inputs()
    decision['citations'] = {}
    with pytest.raises(ValueError, match='receipt_missing'):
        restore_revision_calculations(state, decision, artifacts, 'P01')
    state['task']['case_id'] = 'other-case'
    with pytest.raises(ValueError, match='case_scope_mismatch'):
        restore_revision_calculations(state, decision, artifacts, 'P01')


def test_enriched_receipt_retains_transport_history_and_exact_readback():
    state, decision, artifacts, ref = inputs()
    calc = decision['citations'][ref]['sources'][0]['calculation']
    calc.update(fact_id=ref, cell_binding_used=False, source_tool_lane_receipt_id='fixture-lane',
                mcp_receipt_chain=[{'call_id': 'fixture-calculator', 'is_error': False}])
    before = deepcopy((state, decision))
    restored = restore_revision_calculations(state, decision, artifacts, 'P01')
    assert (state, decision) == before
    registry = ObservedSourceRegistry(restored['notebook']['observations'])
    assert registry.get(ref) == calc
    receipt = restored['task_context']['revision_calculation_handoff']['receipts'][ref]
    assert receipt['calculation'] == calc
    assert receipt['financial_semantics_verified'] is False
    assert restore_revision_calculations(restored, decision, artifacts, 'P01') == restored


@pytest.mark.parametrize('field,value', [
    ('fact_id', 'CALC::wrong-identity'), ('value_decimal', '7'),
    ('result_unit', 'different-unit'), ('financial_semantics_verified', True),
    ('unknown_financial_condition', 'Do not ignore an unknown field'),
])
def test_enriched_receipt_does_not_hide_identity_or_semantic_conflicts(field, value):
    state, decision, artifacts, ref = inputs()
    calc = decision['citations'][ref]['sources'][0]['calculation']
    calc.update(fact_id=ref, mcp_receipt_chain=[{'call_id': 'fixture'}])
    calc[field] = value
    with pytest.raises(ValueError, match='original_mismatch'):
        restore_revision_calculations(state, decision, artifacts, 'P01')
