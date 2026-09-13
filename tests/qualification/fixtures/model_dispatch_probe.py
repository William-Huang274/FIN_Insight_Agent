"""Synthetic provider consumed by the REAL CaseModelAudit middleware."""
import asyncio
import os

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import SecretStr

from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
from sec_agent.agent_runtime.deepseek_structured_agents import (
    TokenBudgetBasis, DeepSeekModelProfile, ReasoningPreservingChatDeepSeek,
)
from sec_agent.agent_runtime.model_dispatch_guard import ModelDispatchGuard, TokenPrices


async def invoke_model(state, event):
    basis = TokenBudgetBasis(node_role='specialist', node_purpose='Synthetic dispatch/replay qualification',
        input_scale='One synthetic message, no financial sources', required_outputs=('one synthetic response',),
        schema_burden='AIMessage only', materiality_quality_risk='No financial quality claim; verify no duplicate dispatch',
        comparable_run_evidence='FIN014 E1 native queue a3 demonstrated unfinished node replay',
        reasoning_profile='agentic_message_history_thinking_disabled', max_input_characters=10000,
        max_output_tokens=1000, timeout_seconds=30, max_transport_attempts=1, retry_policy='none',
        truncation_stop_behavior='fail_closed_no_partial_promotion', input_ceiling_behavior='fail_before_transport')
    profile = DeepSeekModelProfile(model='deepseek-v4-pro', thinking='disabled')
    prices = TokenPrices('synthetic-not-a-real-tariff', profile.model, 'CNY', 1_000_000, 0, 2_000_000)
    guard = ModelDispatchGuard(ModelDispatchStore(os.environ['POSTGRES_URI']), owner=state['guard_owner'],
        budget=state['guard_budget'], prices=prices, reservation_micros=600,
        reservation_basis='Synthetic 600-micro reservation; deterministic returned usage costs 200 micros')
    def public(row):
        if row.get('event') == 'replay':
            event(state, 'saved_response_replayed')
    audit = CaseModelAudit(actor='synthetic-child', profile=profile, basis=basis,
                          public_sink=public, private_sink=lambda _: None, dispatch_guard=guard)
    model = ReasoningPreservingChatDeepSeek(model=profile.model, api_key=SecretStr('fixture-not-a-secret'),
                                          max_retries=0, use_responses_api=False)
    request = ModelRequest(model=model, messages=[HumanMessage(content='Synthetic input')],
                           tools=[], state={'messages': []})
    async def handler(_):
        event(state, 'provider_effect')
        if state['guard_mode'] == 'unknown':
            await asyncio.sleep(state['delay_seconds'])
        return ModelResponse(result=[AIMessage(content='Synthetic saved response',
            usage_metadata={'input_tokens':100,'output_tokens':50,'total_tokens':150,
                            'input_token_details':{'cache_read':0}}, response_metadata={'finish_reason':'stop'})])
    result = await audit.awrap_model_call(request, handler)
    assert result.result[-1].content == 'Synthetic saved response'
    event(state, 'guard_returned')
    if state['guard_mode'] == 'saved':
        # Crash outside the committed guard but before native node checkpoint.
        await asyncio.sleep(state['delay_seconds'])
