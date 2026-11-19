"""Opt-in model boundary; native tasks own identity, PostgreSQL owns concurrency."""
import asyncio
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json

from langchain.agents.middleware.types import ModelResponse
from langchain_core.messages import AIMessage, messages_from_dict, messages_to_dict
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.config import get_config

from sec_agent.adapters.model_dispatch_store import amount, DispatchBlocked


@dataclass(frozen=True)
class TokenPrices:
    """Integer currency micros per million tokens; immutable dated price basis."""
    version: str
    model: str
    currency: str
    input_miss: int
    input_hit: int
    output: int

    def __post_init__(self):
        if not all((self.version, self.model, self.currency)):
            raise ValueError('price_identity_missing')
        for rate in (self.input_miss, self.input_hit, self.output):
            amount(rate)

    def cost(self, response):
        from .deepseek_structured_agents import _usage_audit_fields
        messages = [m for m in response.result if isinstance(m, AIMessage)]
        if len(messages) != 1:
            return None  # Do not undercount an unqualified multi-response handler.
        raw = messages[0]
        if raw.response_metadata.get('fin_usage_fields_complete') is False:
            return None
        usage = _usage_audit_fields(raw)
        provider = raw.response_metadata.get('token_usage') or {}
        # Match the audit extractor's source precedence. A second source must
        # not disguise fields missing from the selected usage record as zero.
        selected = raw.usage_metadata if isinstance(raw.usage_metadata, Mapping) else provider
        if (not usage.get('usage_reported')
                or not any(selected.get(k) is not None for k in ('input_tokens', 'prompt_tokens'))
                or not any(selected.get(k) is not None for k in ('output_tokens', 'completion_tokens'))):
            return None
        counts = [usage.get(k) for k in ('cache_miss_tokens', 'cache_hit_tokens', 'output_tokens')]
        if any(type(n) is not int or n < 0 for n in counts):
            return None  # Known response, unknown cost: keep the reservation.
        numerator = sum(n * rate for n, rate in zip(counts, (self.input_miss, self.input_hit, self.output)))
        return (numerator + 999_999) // 1_000_000


class ModelDispatchGuard:
    def __init__(self, store, *, owner, budget, prices, reservation_micros, reservation_basis, delivery=False):
        self.store, self.owner, self.budget, self.prices = store, owner, budget, prices
        self.reserved = amount(reservation_micros, positive=True)
        if not reservation_basis:
            raise ValueError('reservation_basis_required')
        self.reservation_basis, self.delivery = reservation_basis, delivery

    def prepare(self, request, *, actor, basis, profile):
        """Reserve using native execution identity; callers must preserve this context."""
        from .deepseek_structured_agents import ReasoningPreservingChatDeepSeek
        try:
            native = get_config().get('configurable', {})
        except RuntimeError as exc:
            raise DispatchBlocked('native_model_step_identity_missing') from exc
        identity = [native.get('thread_id'), native.get('checkpoint_ns', ''), native.get('__pregel_task_id'), actor]
        if not identity[0] or not identity[2] or not actor:
            raise DispatchBlocked('native_model_step_identity_missing')
        if profile.model != self.prices.model:
            raise DispatchBlocked('model_price_binding_mismatch')
        if request.response_format is not None:
            raise DispatchBlocked('structured_response_replay_not_qualified')
        if not isinstance(request.model, ReasoningPreservingChatDeepSeek):
            raise DispatchBlocked('provider_transport_not_qualified')
        if request.model.max_retries != 0:
            raise DispatchBlocked('provider_automatic_retry_forbidden')
        key = sha256(json.dumps(identity).encode()).hexdigest()
        messages = ([request.system_message] if request.system_message else []) + list(request.messages)
        settings = dict(request.model_settings)
        settings['tools'] = [convert_to_openai_tool(t) for t in request.tools]
        if request.tool_choice is not None:
            settings['tool_choice'] = request.tool_choice
        payload = request.model._get_request_payload(messages, **settings)
        if payload.get('model') != self.prices.model:
            raise DispatchBlocked('request_model_price_binding_mismatch')
        policy = {'token_budget': basis.model_dump(mode='json'), 'price': asdict(self.prices),
                  'reservation_micros': self.reserved, 'reservation_basis': self.reservation_basis,
                  'delivery': self.delivery}
        fingerprint = sha256(json.dumps({'payload': payload, 'policy': policy,
                                        'provider_base': str(request.model.openai_api_base)}, sort_keys=True,
                                       ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        prior = self.store.reserve(self.owner, self.budget, key, fingerprint,
                                  self.reserved, policy, currency=self.prices.currency, delivery=self.delivery)
        return {**prior, 'key': key, 'actor': actor, 'call_id': str(prior['call_id'])}

    def replay(self, prior, replay_sink):
        if prior['status'] == 'received':
            replay_sink({'event': 'replay', 'status': 'saved_response', 'actor': prior['actor'],
                         'call_id': prior['call_id'], 'provider_call_attempted': False})
            return ModelResponse(result=messages_from_dict(prior['response']['messages']))

    def settle(self, prior, result):
        if result.structured_response is not None:
            raise ValueError('typed_structured_response_replay_not_qualified')
        if any(isinstance(m, AIMessage) and m.response_metadata.get('finish_reason') not in {
                'stop', 'tool_calls', 'length', 'content_filter', 'insufficient_system_resource', 'aborted'} for m in result.result):
            raise DispatchBlocked('provider_terminal_response_missing')
        self.store.received(self.owner, self.budget, prior['key'],
                            {'messages': messages_to_dict(result.result)}, self.prices.cost(result))

    def run_sync(self, prior, handler, *, replay_sink):
        if (saved := self.replay(prior, replay_sink)) is not None:
            return saved
        try:
            result = handler(prior['call_id'])
            self.settle(prior, result)
            return result
        except BaseException:
            try:
                self.store.unknown(self.owner, self.budget, prior['key'])
            except Exception:
                pass  # Precommitted dispatched reservation remains durable.
            raise

    async def run_async(self, prior, handler, *, replay_sink):
        if (saved := self.replay(prior, replay_sink)) is not None:
            return saved
        try:
            result = await handler(prior['call_id'])
            await asyncio.to_thread(self.settle, prior, result)
            return result
        except BaseException:
            # Cancellation/process death cannot make the precommitted reservation
            # disappear. Failed reconciliation itself leaves dispatched durable.
            try:
                await asyncio.shield(asyncio.to_thread(self.store.unknown, self.owner, self.budget, prior['key']))
            except Exception:
                pass
            raise

    async def invoke(self, request, handler, *, actor, basis, profile, replay_sink):
        prior = await asyncio.to_thread(self.prepare, request, actor=actor, basis=basis, profile=profile)
        return await self.run_async(prior, handler, replay_sink=replay_sink)
