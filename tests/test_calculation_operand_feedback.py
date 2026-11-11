import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import ToolException

from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.harness_business_tools import actionable_tool_feedback, model_receipt
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.parametrize('operand', [
    {'assumption_note': 'Seven working days; the model still has to choose and submit a literal.'},
    {'literal': '7'},
    {'literal': '7', 'assumption_note': 'Scenario', 'quote': 'Seven days'},
    {'observation_field': {'start_utc': '2026-01-01', 'end_utc': '2026-01-02', 'field': 'close'}},
])
def test_invalid_assumption_is_rejected_with_actionable_contract_not_guessed_number(operand):
    tool = next(g.tool for g in conversation_tools(thread_id='contract')
                if g.tool.name == 'calculate_research_metric')
    request = SourceBoundCalculation(expression='d / 4', operands={'d': operand},
        result_unit='days', rationale='An explicit hypothetical scale conversion')
    original = request.model_dump()
    with pytest.raises(ToolException) as caught:
        tool.func(request=request, runtime=SimpleNamespace(state={'messages': []}))
    feedback = json.loads(str(caught.value))
    assert feedback['submitted_operand'] == operand
    assert feedback['constraints']['assumption']['required'] == ['literal', 'assumption_note']
    assert feedback['calculation_executed'] is False and feedback['request_modified'] is False
    assert 'value_decimal' not in feedback
    assert request.model_dump() == original
    result = ToolMessage(name=tool.name, tool_call_id='rejected', content=str(caught.value), status='error')
    assert actionable_tool_feedback(result)
    assert model_receipt(result)['execution_stop'] is False
    # The same envelope must never override a host-side execution fault.
    result.artifact = {'execution_stop': True}
    assert not actionable_tool_feedback(result)


def test_only_author_submitted_literal_can_make_assumption_calculation_succeed():
    tool = next(g.tool for g in conversation_tools(thread_id='contract')
                if g.tool.name == 'calculate_research_metric')
    request = SourceBoundCalculation(expression='d / 4',
        operands={'d': {'literal': '7', 'assumption_note': 'Hypothetical number of working days'}},
        result_unit='days', rationale='An explicit hypothetical scale conversion')
    _, result = tool.func(request=request, runtime=SimpleNamespace(state={'messages': []}))
    assert result['value_decimal'] == '1.75'
    assert result['financial_semantics_verified'] is False


@pytest.mark.parametrize('text', ['storage_corrupt', 'permission_denied',
    '{"feedback_kind":"calculation_operand_validation","code":"storage_corrupt",'
    '"calculation_executed":false,"request_modified":false,"constraints":{}}'])
def test_execution_failures_do_not_become_parameter_feedback(text):
    result = ToolMessage(name='calculate_research_metric', tool_call_id='failed', content=text, status='error')
    assert not actionable_tool_feedback(result)


@pytest.mark.anyio
async def test_native_bridge_keeps_rejected_receipt_and_allows_author_correction(tmp_path):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'state.sqlite')) as saver:
        grants = [g for g in conversation_tools(thread_id='bridge') if g.tool.name == 'calculate_research_metric']
        bridge = HarnessBusinessTools(grants=grants, checkpointer=saver, thread_id='bridge',
                                      check=lambda: None, stop_on_tool_error=True)
        args = {'request': {'expression': 'd / 4', 'operands': {'d': {'assumption_note': 'Seven days'}},
                           'result_unit': 'days', 'rationale': 'Hypothetical scale conversion'}}
        rejected = await bridge.execute('calculate_research_metric', args)
        assert rejected.status == 'error' and not bridge.stopped
        args['request']['operands']['d']['literal'] = '7'
        corrected = await bridge.execute('calculate_research_metric', args)
        assert corrected.status == 'success'
        state = await bridge.graph.aget_state(bridge.config)
        receipts = [m for m in state.values['messages'] if isinstance(m, ToolMessage)]
        assert [m.status for m in receipts] == ['error', 'success']
