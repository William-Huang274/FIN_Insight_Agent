import pytest

from sec_agent.agent_runtime.harness_profile import profile_overlay


def make_patch(threshold=.8, **kwargs):
    return profile_overlay(model='deepseek-flash', protocol='deepseek_messages',
        endpoint='http://127.0.0.1:1234', prompt='fixture', context_window=1000000,
        output_tokens=65536, summary_tokens=16384, reasoning='high',
        dispatch_plugin='integrations/deepseek-harness/dispatch.mjs', compaction_threshold=threshold, **kwargs)


def test_business_mcp_uses_public_timeout_configuration_and_same_namespace():
    patch = make_patch(business_mcp={'Authorization': 'Bearer execution-private-fixture'})
    plugins = [p for row in patch for p in row.get('insert', [])]
    mcp = next(p for p in plugins if p['id'] == 'fin-business-mcp')
    assert mcp['name'] == '@deepseek-ai/dsh-mcp-client'
    assert mcp['config']['toolCallTimeoutMs'] == 300_000
    assert mcp['config']['serverName'] == 'financial'
    assert mcp['config']['url'] == 'http://127.0.0.1:1234/business/'
    assert mcp['config']['headers']['Authorization'] == 'Bearer execution-private-fixture'


def test_native_compaction_threshold_does_not_change_provider_capacity():
    patch = make_patch(.35)
    config = next(p['config'] for p in patch if p.get('id') == 'compaction-basic')
    assert config['thresholdRatio'] == .35
    assert config['maxTokens'] == 16384
    assert config['compactionRetries'] == 0
    provider = next(p['config'] for p in patch if p.get('id') == 'llm-deepseek')
    assert provider['models'][0]['contextWindow'] == 1000000
    assert provider['maxTokens'] == 65536


def test_sol_uses_258k_native_pressure_without_lowering_capacity_or_retrying():
    patch = profile_overlay(model='gpt-6.1-sol', protocol='openai_responses',
        endpoint='http://127.0.0.1:1234', prompt='fixture', context_window=524288,
        output_tokens=65536, summary_tokens=32768, reasoning='high',
        dispatch_plugin='integrations/deepseek-harness/dispatch.mjs', compaction_threshold=300000/524288)
    config = next(p['config'] for p in patch if p.get('id') == 'compaction-basic')
    assert config['thresholdRatio'] * 524288 == 258000
    assert config['maxTokens'] == 32768
    assert config['compactionRetries'] == config['maxOverflowRetries'] == 0
    provider = next(p for row in patch for p in row.get('insert', []) if p['id'] == 'fin-pi-ai')
    assert provider['config']['providers']['fin-openai']['models'][0]['contextWindow'] == 524288


@pytest.mark.parametrize('threshold', [0, 1, -1, 2])
def test_invalid_native_compaction_ratio_rejected(threshold):
    with pytest.raises(ValueError, match='harness_capacity_invalid'):
        make_patch(threshold)
