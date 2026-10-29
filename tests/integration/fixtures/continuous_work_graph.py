"""Scripted transport inside the production continuous organization runtime.

Authorization, source tools, native queue/checkpoints, memory and PostgreSQL
dispatch reservations are real. Only model transport and trace export are fake.
"""
import json
import os
from pathlib import Path

if os.getenv('FIN_CONTINUOUS_WORK_QUALIFICATION') != '1':
    raise RuntimeError('isolated_continuous_work_qualification_only')
if os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY'):
    raise RuntimeError('provider_credentials_forbidden')

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from sec_agent.agent_runtime import agent_server_entry, case_review_agent, research_session_runtime
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek


class ScriptedTransport(ReasoningPreservingChatDeepSeek):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        latest_user = next(m.content for m in reversed(messages) if m.type == 'human')
        tail = []
        for message in reversed(messages):
            if message.type == 'human':
                break
            tail.insert(0, message)
        tools = [m for m in tail if m.type == 'tool']
        calls = []
        content = ''
        if 'save a working paper' in latest_user:
            saved = next((m for m in tools if m.name == 'WriteWorkingNote'), None)
            delivered = any(m.name == 'deliver_working_note' for m in tools)
            if not saved:
                calls = [{'id': 'save', 'name': 'WriteWorkingNote', 'args': {
                    'title': 'Service qualification note',
                    'body': 'Engineering fixture only. The same authorized original and prior answer remain available.'}}]
            elif not delivered:
                receipt = json.loads(saved.content)
                assert receipt['saved'] is True, receipt
                calls = [{'id': 'deliver', 'name': 'deliver_working_note', 'args': {
                    'note_id': receipt['note_id'], 'version': receipt['version']}}]
            else:
                content = 'Engineering fixture: saved and delivered the current working paper.'
        elif not tools:
            calls = [{'id': 'catalog', 'name': 'read_source_document', 'args': {
                'request': {'source_space': 'organization', 'operation': 'catalog'}}}]
        elif len(tools) == 1:
            catalog = json.loads(tools[0].content)
            document = next(r['document_id'] for r in catalog['items'] if r.get('document_id'))
            calls = [{'id': 'read', 'name': 'read_source_document', 'args': {
                'request': {'source_space': 'organization', 'operation': 'read', 'document_id': document}}}]
        else:
            assert 'Synthetic pinned organization evidence.' in tools[-1].content
            content = 'Engineering fixture: the authorized original was read. No financial conclusion is assessed.'
        from langgraph.config import get_config
        native = get_config()['configurable']
        with (Path(os.environ['FIN_PROBE_EVIDENCE']) / 'scripted-transport.jsonl').open('a') as out:
            out.write(json.dumps({'thread_id': native['thread_id'], 'run_id': native['run_id'],
                'tool_names': [c['name'] for c in calls], 'provider_network_calls': 0}) + '\n')
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content, tool_calls=calls,
            usage_metadata={'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0,
                            'input_token_details': {'cache_read': 0}},
            response_metadata={'finish_reason': 'tool_calls' if calls else 'stop',
                               'qualification': 'scripted_transport_no_provider'}))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop, run_manager, **kwargs)


def model(profile, basis, settings, api_key, **kwargs):
    return ScriptedTransport(model=profile.model, api_key='offline-placeholder', max_retries=0,
        streaming=False, disable_streaming=True, use_responses_api=False)


case_review_agent.case_chat_model = model
agent_server_entry._require_langsmith_execution_environment = lambda config: None
os.environ['DEEPSEEK_API_KEY'] = 'offline-placeholder'
graph = research_session_runtime.research_session_graph
