"""Provider mapping checks; synthetic responses do not establish research quality."""
import json
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from openai import OpenAI
from pydantic import SecretStr, ValidationError

from sec_agent.agent_runtime.deepseek_structured_agents import (
    DeepSeekStructuredAgentConfig, DeepSeekStructuredAgentAdapter,
)


def configuration():
    value = json.loads(Path('configs/research/model_routing.json').read_text(encoding='utf8'))
    value.update(provider='qwen', model='qwen3.8-max',
                 base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
                 agentic_message_history=True, runtime_context_binding=True, thinking='disabled')
    for profile in value.get('model_profiles', {}).values():
        profile.update(model='qwen3.8-max', thinking='disabled')
    return value


def test_qwen_transport_and_returned_usage_are_preserved_without_paid_call():
    config = DeepSeekStructuredAgentConfig.model_validate_json(json.dumps(configuration()))
    adapter = DeepSeekStructuredAgentAdapter.from_config(config=config, api_key=SecretStr('test-only'))
    model = adapter._chat_models['lead']
    captured = []
    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 1,
            'model': 'qwen3.8-max', 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'content': '', 'reasoning_content': 'synthetic',
                    'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{}'}}]}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 5, 'total_tokens': 105,
                      'prompt_tokens_details': {'cached_tokens': 60}}})
    client = OpenAI(api_key='test-only', base_url=config.base_url, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(respond)))
    model.client = client.chat.completions
    model.root_client = client
    reply = model.bind_tools([{'name': 'lookup', 'description': 'test', 'parameters': {'type': 'object', 'properties': {}}}]).invoke([HumanMessage(content='test')])
    assert reply.tool_calls[0]['name'] == 'lookup'
    assert reply.usage_metadata['input_token_details']['cache_read'] == 60
    assert reply.additional_kwargs['reasoning_content'] == 'synthetic'
    assert captured[0]['model'] == 'qwen3.8-max'
    assert captured[0]['enable_thinking'] is False
    assert 'thinking' not in captured[0] and 'reasoning_effort' not in captured[0]
    assert model.max_retries == 0
    history = [HumanMessage(content='test'), reply, ToolMessage(content='result', tool_call_id='c1')]
    assert model._get_request_payload(history)['messages'][1]['reasoning_content'] == 'synthetic'


@pytest.mark.parametrize('change', [
    {'base_url': 'https://api.deepseek.com'}, {'provider': 'deepseek'},
    {'model_profiles': {'lead': {'model': 'deepseek-v4-flash'}}},
])
def test_provider_endpoint_and_role_mismatch_rejected(change):
    with pytest.raises(ValidationError, match='model_provider_endpoint_mismatch|mixed_provider_credentials_not_supported'):
        DeepSeekStructuredAgentConfig.model_validate_json(json.dumps({**configuration(), **change}))


@pytest.mark.parametrize('provider,effort', [('qwen', 'medium'), ('deepseek', 'high'), ('deepseek', 'max')])
def test_thinking_continuation_preserves_all_reasoning_and_omits_client_cap(provider, effort):
    value = configuration() if provider == 'qwen' else json.loads(
        Path('configs/research/model_routing.json').read_text(encoding='utf8'))
    value.update(thinking='enabled', reasoning_effort=effort,
                 agentic_message_history=True, runtime_context_binding=True)
    for profile in value['model_profiles'].values():
        profile.update(thinking='enabled', reasoning_effort=effort)
    value['token_budget_basis']['lead']['max_output_tokens'] = None
    value['token_budget_basis']['lead']['reasoning_profile'] = 'agentic_message_history_thinking_enabled'
    config = DeepSeekStructuredAgentConfig.model_validate_json(json.dumps(value))
    adapter = DeepSeekStructuredAgentAdapter.from_config(config=config, api_key=SecretStr('test-only'))
    model = adapter._chat_models['lead']
    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 1,
            'model': config.profile_for('lead').model, 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                'message': {'role': 'assistant', 'content': '', 'reasoning_content': 'synthetic-private',
                    'tool_calls': [{'id': 'c1', 'type': 'function', 'function': {'name': 'lookup', 'arguments': '{}'}}]}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
                      'completion_tokens_details': {'reasoning_tokens': 25}}})

    client = OpenAI(api_key='test-only', base_url=config.base_url, max_retries=0,
                    http_client=httpx.Client(transport=httpx.MockTransport(respond)))
    model.client = client.chat.completions
    model.root_client = client
    bound = model.bind_tools([{'name': 'lookup', 'description': 'test',
                              'parameters': {'type': 'object', 'properties': {}}}], tool_choice='auto')
    first = bound.invoke([HumanMessage(content='test')])
    bound.invoke([HumanMessage(content='test'),
                  AIMessage(content='Earlier public note', additional_kwargs={'reasoning_content': 'earlier-private'}),
                  first, ToolMessage(content='result', tool_call_id='c1')])
    for payload in payloads:
        assert payload['reasoning_effort'] == effort
        assert 'max_tokens' not in payload and 'max_completion_tokens' not in payload
        assert payload['tool_choice'] == 'auto'
        if provider == 'qwen':
            assert payload['enable_thinking'] is True and payload['preserve_thinking'] is True
            assert 'thinking' not in payload
        else:
            assert payload['thinking'] == {'type': 'enabled'}
            assert 'enable_thinking' not in payload
    assistant_rows = [m for m in payloads[1]['messages'] if m['role'] == 'assistant']
    assert [m['reasoning_content'] for m in assistant_rows] == ['earlier-private', 'synthetic-private']
    assert all('private' not in (m.get('content') or '') for m in assistant_rows)
    assert first.usage_metadata['output_token_details']['reasoning'] == 25
