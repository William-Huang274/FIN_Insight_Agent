import pytest

from sec_agent.agent_runtime.harness_profile import profile_overlay


def make_patch(threshold=.8):
    return profile_overlay(model='deepseek-flash', protocol='deepseek_messages',
        endpoint='http://127.0.0.1:1234', prompt='fixture', context_window=1000000,
        output_tokens=65536, summary_tokens=16384, reasoning='high',
        dispatch_plugin='integrations/deepseek-harness/dispatch.mjs', compaction_threshold=threshold)


def test_native_compaction_threshold_does_not_change_provider_capacity():
    patch = make_patch(.35)
    config = next(p['config'] for p in patch if p.get('id') == 'compaction-basic')
    assert config['thresholdRatio'] == .35
    assert config['maxTokens'] == 16384
    assert config['compactionRetries'] == 0
    provider = next(p['config'] for p in patch if p.get('id') == 'llm-deepseek')
    assert provider['models'][0]['contextWindow'] == 1000000
    assert provider['maxTokens'] == 65536


@pytest.mark.parametrize('threshold', [0, 1, -1, 2])
def test_invalid_native_compaction_ratio_rejected(threshold):
    with pytest.raises(ValueError, match='harness_capacity_invalid'):
        make_patch(threshold)
