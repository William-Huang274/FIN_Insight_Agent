"""Host-selected public DS profile overlay; no fork of the upstream loop."""
from pathlib import Path


def profile_overlay(*, model, protocol, endpoint, prompt, context_window,
                    output_tokens, summary_tokens, reasoning, dispatch_plugin,
                    compaction_threshold=.8):
    if protocol not in {'deepseek_messages', 'qwen_chat'}:
        raise ValueError('harness_protocol_not_qualified')
    if (not 0 < compaction_threshold < 1 or not 0 < output_tokens < context_window
            or not 0 < summary_tokens < context_window):
        raise ValueError('harness_capacity_invalid')
    disabled = ['sdk-app-startup', 'sdk-jsonrpc-server', 'session-log-deepseek',
                'plugin-package-inventory-deepseek', 'tool-fs', 'tool-working-directory',
                'persistent-bash', 'persistent-pwsh', 'llm-retry']
    patch = [{'id': name, 'disabled': True} for name in disabled]
    provider = 'deepseek-official' if protocol == 'deepseek_messages' else 'fin-qwen'
    patch += [{'id': 'system-prompt', 'config': {'includeHarnessIdentity': False,
        'includeRuntimeContext': False, 'personaPrefix': prompt}},
        {'id': 'compaction-basic', 'config': {'thresholdRatio': compaction_threshold,
         'maxTokens': summary_tokens, 'compactionRetries': 0, 'maxOverflowRetries': 0}}]
    if protocol == 'deepseek_messages':
        if reasoning not in {'low', 'high', 'max'}:
            raise ValueError('harness_deepseek_reasoning_invalid')
        patch += [{'id': 'llm-deepseek', 'config': {'apiKeyEnv': 'FIN_HARNESS_LOCAL_TOKEN',
            'baseURL': endpoint + '/v1', 'thinking': 'enabled', 'reasoningEffort': reasoning,
            'maxTokens': output_tokens, 'models': [{'id': model, 'contextWindow': context_window,
                                                   'maxTokens': output_tokens}],
            'retryPolicy': {'mode': 'normal', 'maxRetries': 0}}}]
    else:
        patch += [{'id': 'llm-deepseek', 'disabled': True}, {'insert': [{
            'id': 'fin-pi-ai', 'name': '@deepseek-ai/dsh-llm-pi-ai', 'config': {'providers': {provider: {
                'api': 'openai-completions', 'apiKeyEnv': 'FIN_HARNESS_LOCAL_TOKEN', 'baseURL': endpoint + '/v1',
                'reasoning': reasoning, 'retryPolicy': {'mode': 'normal', 'maxRetries': 0},
                'compat': {'thinkingFormat': 'qwen', 'supportsDeveloperRole': False,
                           'supportsReasoningEffort': False, 'maxTokensField': 'max_tokens'},
                'models': [{'id': model, 'contextWindow': context_window, 'maxTokens': output_tokens,
                            'reasoningEfforts': {'off': None, reasoning: reasoning}}]}}}}]}]
    patch += [{'insert': [
        {'id': 'fin-dispatch', 'name': str(Path(dispatch_plugin).resolve()),
         'config': {'endpoint': endpoint, 'tokenEnv': 'FIN_HARNESS_LOCAL_TOKEN'}},
        {'id': 'fin-acp', 'name': '@deepseek-ai/dsh-acp', 'config': {'provider': provider, 'model': model}}]}]
    return patch
