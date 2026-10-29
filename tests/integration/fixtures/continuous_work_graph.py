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
        latest_user = next(m.content for m in reversed(messages)
            if m.type == 'human' and not m.additional_kwargs.get('finsight_runtime_receipt'))
        tail = []
        for message in reversed(messages):
            if message.type == 'human' and not message.additional_kwargs.get('finsight_runtime_receipt'):
                break
            tail.insert(0, message)
        tools = [m for m in tail if m.type == 'tool']
        calls = []
        content = ''
        available = {t['function']['name'] for t in kwargs.get('tools', [])}
        full_library = os.getenv('FIN_CONTINUOUS_LIBRARY_QUALIFICATION') == '1'
        if full_library and 'submit_case_report' in available:
            read = next((m for m in reversed(tools) if m.name == 'read_current_source'), None)
            found = next((m for m in reversed(tools) if m.name == 'search_research_sources'), None)
            if read:
                source = json.loads(read.content)
                ref = source['source_id']
                text = source['text']
                calls = [{'id':'report', 'name':'submit_case_report', 'args':{'report':{
                    'title':'冻结资料服务验证报告',
                    'narrative_markdown':'本报告仅用于实际服务、原文引用和导出格式验证，不作金融判断。\n\n'
                        + '以下内容为本次任务通过冻结检索发布找到并实际读取的原文片段。来源、版本与执行权限由正常服务处理。'
                        + '这份脚本化报告不代表模型研究效果，也不代表对全部材料的投资分析。\n\n'
                        + '## 原文摘录\n\n' + text + f' [{ref}]\n\n'
                        + '## 使用说明\n\n本次仅检验资料交接、网页阅读与下载后的格式和引用一致性。原文仍应按其披露主体与期间理解。',
                    'charts':[]}}}]
            elif found:
                row = json.loads(found.content)['matches'][0]
                calls = [{'id':'writer-read','name':'read_current_source','args':row['read_arguments']}]
            else:
                calls = [{'id':'writer-search','name':'search_research_sources','args':{'query':'revenue OR returns','limit':1}}]
        elif full_library and 'compose a report' in latest_user:
            catalogs = [json.loads(m.content) for m in tools if m.name == 'research_object_catalog']
            rows = catalogs[-1] if catalogs else []
            report = next((r for r in rows if r['id']=='report'), None)
            if report:
                calls=[{'id':'deliver-report','name':'deliver_research_result','args':{'object_id':'report','digest':report['digest']}}]
            elif rows and not any(m.name=='request_research_operation' for m in tools):
                calls=[{'id':'compose','name':'request_research_operation','args':{'request':{
                    'action':'compose','purpose':'Create a labelled service qualification report using the original already read.',
                    'basis':{r['id']:r['digest'] for r in rows}}}}]
            else:
                calls=[{'id':'catalog-'+str(len(messages)),'name':'research_object_catalog','args':{}}]
        elif 'save a working paper' in latest_user:
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
        elif full_library and not tools:
            calls=[{'id':'search','name':'read_source_document','args':{'request':{
                'source_space':'organization','operation':'search','query':os.environ['FIN_QUALIFICATION_QUERY'],'limit':3}}}]
        elif full_library and len(tools)==1:
            result=json.loads(tools[0].content)
            row=result['items'][0]
            assert row.get('retrieval'), result
            calls=[{'id':'original','name':'read_source_document','args':{'request':row['readback']}}]
        elif full_library:
            result=json.loads(tools[-1].content)
            assert any(i.get('result_state')=='source_bound_passage' for i in result['items']), result
            content='工程验证：已通过冻结索引检索并读取准确原文，未作金融判断。'
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
research_session_runtime.case_chat_model = model
agent_server_entry._require_langsmith_execution_environment = lambda config: None
os.environ['DEEPSEEK_API_KEY'] = 'offline-placeholder'
graph = research_session_runtime.research_session_graph
