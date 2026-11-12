"""Host-selected public DS profile overlay; no fork of the upstream loop."""
from pathlib import Path


def profile_overlay(*, model, protocol, endpoint, prompt, context_window,
                    output_tokens, summary_tokens, reasoning, dispatch_plugin,
                    compaction_threshold=.8, wait_for_consultations=False, restore_route=None,
                    business_mcp=None):
    if protocol not in {'deepseek_messages', 'qwen_chat', 'openai_responses'}:
        raise ValueError('harness_protocol_not_qualified')
    if (not 0 < compaction_threshold < 1 or not 0 < output_tokens < context_window
            or not 0 < summary_tokens < context_window):
        raise ValueError('harness_capacity_invalid')
    disabled = ['sdk-app-startup', 'sdk-jsonrpc-server', 'session-log-deepseek',
                'plugin-package-inventory-deepseek', 'tool-fs', 'tool-working-directory',
                'persistent-bash', 'persistent-pwsh', 'llm-retry']
    patch = [{'id': name, 'disabled': True} for name in disabled]
    provider = {'deepseek_messages': 'deepseek-official', 'qwen_chat': 'fin-qwen', 'openai_responses': 'fin-openai'}[protocol]
    # Research pressure target, not model capacity. The native pre-step meter
    # includes the latest committed tool batch and keeps protocol-balanced tails.
    # Legacy run options must not silently keep future Sol runs at 300k+.
    if protocol == 'openai_responses' and 'sol' in model.lower():
        compaction_threshold = min(compaction_threshold, 258_000 / context_window)
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
                'api': 'openai-responses' if protocol == 'openai_responses' else 'openai-completions', 'apiKeyEnv': 'FIN_HARNESS_LOCAL_TOKEN', 'baseURL': endpoint + '/v1',
                'reasoning': reasoning, 'retryPolicy': {'mode': 'normal', 'maxRetries': 0},
                'compat': {} if protocol == 'openai_responses' else {'thinkingFormat': 'qwen', 'supportsDeveloperRole': False,
                           'supportsReasoningEffort': False, 'maxTokensField': 'max_tokens'},
                'models': [{'id': model, 'contextWindow': context_window, 'maxTokens': output_tokens,
                            'reasoningEfforts': {'off': None, reasoning: reasoning}}]}}}}]}]
    if restore_route:
        # Restore needs the previous route's catalog before ACP can select the
        # new model. The host admits only the new model; the old route has no
        # paid transport endpoint or provider credential.
        previous = profile_overlay(model=restore_route['model'], protocol=restore_route['protocol'],
            endpoint=endpoint, prompt=prompt, context_window=context_window, output_tokens=output_tokens,
            summary_tokens=summary_tokens, reasoning=reasoning, dispatch_plugin=dispatch_plugin)
        if restore_route['protocol'] == 'deepseek_messages' and protocol != 'deepseek_messages':
            patch = [p for p in patch if p.get('id') != 'llm-deepseek']
            patch.extend(p for p in previous if p.get('id') == 'llm-deepseek')
        else:
            raise ValueError('harness_restore_route_not_qualified')
    if business_mcp is not None:
        # ACP's transport-only mount drops upstream MCP timeout settings. This
        # execution-private process uses the public MCP plugin directly instead;
        # keep the same tool namespace, auth and native session history.
        patch += [{'insert': [{'id': 'fin-business-mcp',
            'name': '@deepseek-ai/dsh-mcp-client', 'config': {
                'transport': 'streamable-http', 'serverName': 'financial',
                'url': endpoint + '/business/', 'headers': business_mcp,
                'toolCallTimeoutMs': 300_000, 'failOnStartupError': True}}]}]
    if wait_for_consultations:
        patch += [{'insert': [{'id': 'fin-session-query', 'name': '@deepseek-ai/dsh-session-query'}]}]
    patch += [{'insert': [
        {'id': 'fin-dispatch', 'name': str(Path(dispatch_plugin).resolve()),
         'config': {'endpoint': endpoint, 'tokenEnv': 'FIN_HARNESS_LOCAL_TOKEN',
                    'requireBusinessTools': business_mcp is not None,
                    'concludeDelivery': business_mcp is not None,
                    'waitForConsultations': wait_for_consultations}},
        {'id': 'fin-acp', 'name': '@deepseek-ai/dsh-acp', 'config': {'provider': provider, 'model': model}}]}]
    return patch
