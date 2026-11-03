"""Formula visibility without changing CALC identity or inferring conclusions."""
import json
from copy import deepcopy

import pytest
from langchain_core.messages import ToolMessage

from sec_agent.agent_runtime.harness_business_tools import model_receipt
from sec_agent.agent_runtime.source_result_view import source_result_view
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources


def calculation(expression):
    return calculate_from_sources(SourceBoundCalculation(
        expression=expression, operands={
            'part': {'literal': '60', 'assumption_note': 'Synthetic segment increment'},
            'total': {'literal': '100', 'assumption_note': 'Synthetic total increment'},
            'adjustment': {'literal': '10', 'assumption_note': 'Synthetic segment-specific adjustment'}},
        result_unit='ratio', rationale='Conditional contribution, not reported data.'), lambda _: {})


def test_same_values_different_denominators_remain_different_questions():
    originals = [calculation('(part-adjustment)/total'),
                 calculation('(part-adjustment)/(total-adjustment)')]
    before = deepcopy(originals)
    views = [source_result_view(x) for x in originals]
    assert [v['formula_basis']['ratios'][0]['denominator']['expression'] for v in views] == [
        'total', 'total - adjustment']
    assert views[0]['formula_basis']['ratios'][0]['numerator']['operand_keys'] == ['adjustment', 'part']
    for original, view in zip(originals, views):
        assert view['calculation_id'] == original['calculation_id']
        assert view['value_decimal'] == original['value_decimal']
        assert view['operands'] == original['operands']
        assert not view['formula_basis']['semantics_inferred']
        assert not view['financial_semantics_verified']
        assert source_result_view(view) == view
    assert originals == before and 'formula_basis' not in originals[0]


def test_native_visible_lane_and_restored_object_share_projection_without_mutating_receipt():
    raw = calculation('(part-adjustment)/total*100')
    msg = ToolMessage(content=json.dumps(raw), artifact=deepcopy(raw), name='calculate_research_metric', tool_call_id='original')
    view = model_receipt(msg)
    assert view['result']['formula_basis']['ratios'][0]['denominator']['expression'] == 'total'
    assert view['original_readback']['arguments']['tool_call_id'] == 'original'
    assert json.loads(msg.content) == msg.artifact == raw
    restored = source_result_view({'saved_source': deepcopy(raw)})
    assert restored['saved_source']['formula_basis'] == view['result']['formula_basis']


def test_multiple_ratios_are_not_mislabeled_as_one_ratio():
    raw = calculation('part/total-adjustment/total')
    view = source_result_view(raw)
    assert [r['division_expression'] for r in view['formula_basis']['ratios']] == ['part / total', 'adjustment / total']
    assert 'numerator' not in view['formula_basis']


@pytest.mark.parametrize('expression', ['part+total-adjustment', '__import__("os")/total', 'part /', 'part/unknown'])
def test_no_inferred_ratio_for_unsupported_or_non_ratio_legacy_shapes(expression):
    raw = calculation('(part-adjustment)/total')
    raw['expression'] = expression
    assert 'formula_basis' not in source_result_view(raw)


def test_failed_or_unverified_calculation_is_not_presented_as_verified():
    raw = calculation('(part-adjustment)/total')
    raw['arithmetic_verified'] = False
    assert 'formula_basis' not in source_result_view(raw)
