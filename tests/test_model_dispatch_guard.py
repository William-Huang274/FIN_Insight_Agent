"""Paid-call boundaries with no provider or database I/O; PG/restart has a separate opt-in suite."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, messages_to_dict
from pydantic import SecretStr

from sec_agent.adapters.model_dispatch_store import DispatchBlocked
from sec_agent.agent_runtime import model_dispatch_guard as module
from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekModelProfile, ReasoningPreservingChatDeepSeek, TokenBudgetBasis,
)
from sec_agent.agent_runtime.model_dispatch_guard import ModelDispatchGuard, TokenPrices


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setattr(module, 'get_config', lambda: {'configurable': {
        'thread_id': 'fixture-thread', 'checkpoint_ns': 'child:fixture', '__pregel_task_id': 'native-step'}})
    basis = TokenBudgetBasis(node_role='specialist', node_purpose='Synthetic boundary regression',
        input_scale='One synthetic message', required_outputs=('one synthetic response',),
        schema_burden='AIMessage', materiality_quality_risk='No financial claim; prevent duplicate dispatch',
        comparable_run_evidence='E1 native restart qualification',
        reasoning_profile='agentic_message_history_thinking_disabled', max_input_characters=10000,
        max_output_tokens=1000, timeout_seconds=30, max_transport_attempts=1, retry_policy='none',
        truncation_stop_behavior='fail_closed_no_partial_promotion', input_ceiling_behavior='fail_before_transport')
    profile = DeepSeekModelProfile(model='deepseek-v4-pro', thinking='disabled')
    prices = TokenPrices('synthetic-not-a-real-tariff', profile.model, 'CNY', 1_000_000, 0, 2_000_000)
    store, public = MagicMock(), []
    store.reserve.return_value = {'status': 'dispatched', 'call_id': 'durable-call'}
    guard = ModelDispatchGuard(store, owner='alice', budget='root', prices=prices,
        reservation_micros=600, reservation_basis='Synthetic fixed reservation')
    model = ReasoningPreservingChatDeepSeek(model=profile.model, api_key=SecretStr('fixture-not-a-secret'),
                                          max_retries=0, use_responses_api=False)
    request = ModelRequest(model=model, messages=[HumanMessage(content='Synthetic input')], tools=[], state={})
    audit = CaseModelAudit(actor='child', profile=profile, basis=basis, public_sink=public.append,
                          private_sink=lambda _: None, dispatch_guard=guard)
    return SimpleNamespace(**locals())


def response(**changes):
    fields = dict(content='synthetic result', additional_kwargs={'reasoning_content': 'private reasoning'},
        tool_calls=[{'name': 'synthetic_tool', 'args': {'number': 7}, 'id': 'tool-1', 'type': 'tool_call'}],
        usage_metadata={'input_tokens':100, 'output_tokens':50, 'total_tokens':150,
                        'input_token_details': {'cache_read':0}}, response_metadata={'finish_reason':'tool_calls'})
    fields.update(changes)
    return ModelResponse(result=[AIMessage(**fields)])


def test_durable_identity_settlement_and_complete_message_replay(boundary):
    b, calls = boundary, []
    async def handler(request):
        calls.append(request.model.metadata['fin_call_id'])
        return response()
    first = asyncio.run(b.audit.awrap_model_call(b.request, handler))
    assert calls == ['durable-call']
    assert b.store.received.call_args.args[-1] == 200
    b.store.reserve.return_value = {'status':'received', 'call_id':'durable-call',
                                   'response': {'messages': messages_to_dict(first.result)}}
    replay = asyncio.run(b.audit.awrap_model_call(b.request, handler))
    assert replay.result == first.result  # Reasoning, tools, metadata and usage survive.
    assert calls == ['durable-call'] and b.store.received.call_count == 1
    assert b.public[-1]['provider_call_attempted'] is False
    assert 'private reasoning' not in str(b.public)


@pytest.mark.parametrize('failure', [RuntimeError('provider outcome unknown'), asyncio.CancelledError()])
def test_error_and_cancellation_keep_unknown_reservation(boundary, failure):
    b = boundary
    async def handler(request):
        raise failure
    with pytest.raises(type(failure)):
        asyncio.run(b.audit.awrap_model_call(b.request, handler))
    b.store.unknown.assert_called_once()
    b.store.received.assert_not_called()


@pytest.mark.parametrize('reason', ['native', 'retry', 'model', 'structured', 'input'])
def test_invalid_boundary_blocks_before_reservation_or_transport(boundary, monkeypatch, reason):
    b, calls = boundary, []
    if reason == 'native':
        monkeypatch.setattr(module, 'get_config', lambda: {'configurable': {'thread_id': 't'}})
    elif reason == 'retry':
        b.request = b.request.override(model=b.model.model_copy(update={'max_retries': 2}))
    elif reason == 'model':
        b.request = b.request.override(model_settings={'model':'unpriced-model'})
    elif reason == 'structured':
        b.request = b.request.override(response_format={'type':'json_object'})
    else:
        b.request = b.request.override(messages=[HumanMessage(content='x' * 11000)])
    async def handler(request):
        calls.append(request)
        return response()
    with pytest.raises((DispatchBlocked, ValueError)):
        asyncio.run(b.audit.awrap_model_call(b.request, handler))
    assert not calls
    b.store.reserve.assert_not_called()


def test_missing_or_invalid_usage_keeps_cost_unknown(boundary):
    cost = boundary.prices.cost
    assert cost(response(usage_metadata=None, response_metadata={})) is None
    assert cost(response(usage_metadata={'input_tokens':100,'output_tokens':50,'total_tokens':150})) is None
    assert cost(response(usage_metadata=None, response_metadata={'token_usage': {
        'prompt_tokens':100, 'completion_tokens':50, 'prompt_cache_hit_tokens':120}})) is None
    assert cost(response(usage_metadata=None, response_metadata={'token_usage': {
        'prompt_tokens':100, 'completion_tokens':True, 'prompt_cache_hit_tokens':0}})) is None
    # Partial selected SDK usage must not borrow field presence from provider usage.
    partial = AIMessage.model_construct(content='synthetic', usage_metadata={
        'input_tokens':100,'input_token_details':{'cache_read':0}}, response_metadata={
        'token_usage': {'prompt_tokens':100,'completion_tokens':50}})
    assert cost(ModelResponse(result=[partial])) is None
    assert cost(ModelResponse(result=response().result * 2)) is None


def test_currency_micros_round_up_without_float_loss():
    prices = TokenPrices('synthetic', 'fixture', 'CNY', 1, 0, 1)
    assert prices.cost(response()) == 1


@pytest.mark.parametrize('mode', ['truncated', 'audit_failure'])
def test_known_response_settled_before_acceptance_and_never_repromoted(boundary, mode):
    b, calls = boundary, []
    raw = response(response_metadata={'finish_reason': 'length' if mode == 'truncated' else 'tool_calls'})
    original_private = b.audit.private_sink
    def private(event):
        if event['event'] == 'response':
            raise RuntimeError('synthetic_audit_write_failed')
    if mode == 'audit_failure':
        b.audit.private_sink = private
    async def handler(request):
        calls.append(request)
        return raw
    with pytest.raises((ValueError, RuntimeError)):
        asyncio.run(b.audit.awrap_model_call(b.request, handler))
    assert b.store.received.call_args.args[-1] == 200
    b.store.unknown.assert_not_called()
    b.audit.private_sink = original_private
    b.store.reserve.return_value = {'status':'received', 'call_id':'durable-call',
                                   'response': {'messages': messages_to_dict(raw.result)}}
    if mode == 'truncated':
        with pytest.raises(ValueError, match='truncated_no_partial_acceptance'):
            asyncio.run(b.audit.awrap_model_call(b.request, handler))
    else:
        assert asyncio.run(b.audit.awrap_model_call(b.request, handler)).result == raw.result
    assert len(calls) == 1 and b.store.received.call_count == 1


def test_opt_out_retains_existing_audit_behavior(boundary):
    b = boundary
    b.audit.dispatch_guard = None
    async def handler(request):
        assert request.model.metadata['fin_call_id'] != 'durable-call'
        return response()
    assert asyncio.run(b.audit.awrap_model_call(b.request, handler)).result
    b.store.reserve.assert_not_called()
    assert [r['event'] for r in b.public] == ['started', 'outcome']
