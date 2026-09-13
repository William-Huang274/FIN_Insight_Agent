"""Local pinned Hermes native HTTP API with task-scoped FIN working-paper tools.

Launch in the qualified Hermes venv; upstream owns HTTP, SSE, sessions and runs.
No built-in shell/filesystem/network tools are registered for this pilot.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4


def main():
    p=argparse.ArgumentParser();p.add_argument('--hermes',type=Path,required=True);p.add_argument('--home',type=Path,required=True);p.add_argument('--port',type=int,default=18806);p.add_argument('--check-session')
    args=p.parse_args();os.environ['HERMES_HOME']=str(args.home.resolve());sys.path.insert(0,str(args.hermes.resolve()))
    from gateway.config import PlatformConfig
    from gateway.platforms.api_server import APIServerAdapter
    from run_agent import AIAgent
    from tools.registry import registry
    from langchain_core.tools import ToolException
    from sec_agent.agent_runtime.working_memory import WorkingMemory
    from sec_agent.agent_runtime.working_memory_tools import WORKING_MEMORY_MODELS, execute_memory_tool
    from sec_agent.agent_runtime.hermes_context_tools import CONTEXT_MODELS, execute_context_tool
    args.home.mkdir(parents=True,exist_ok=True)
    def binding(session):
        reader=WorkingMemory(os.environ['FINSIGHT_WORKING_MEMORY_PATH'],owner='host',workspace='host',actor='host')
        with reader.connection() as db:
            row=db.execute('SELECT * FROM working_hermes_bindings WHERE session=?',(session,)).fetchone()
            if not row: raise ValueError('host_session_binding_required')
            return dict(row)
    for name,model in WORKING_MEMORY_MODELS.items():
        def handler(parameters,_name=name,**kwargs):
            row=binding(kwargs.get('session_id'))
            target=json.loads(row['target'])
            if target and _name=='WriteWorkingNote' and parameters.get('title')!=target['title']:
                return json.dumps({'saved':False,'notice':'只能修改用户选定的底稿'})
            return json.dumps(execute_memory_tool(_name,parameters,{},row['actor'],owner=row['owner'],workspace=row['workspace']),ensure_ascii=False)
        registry.register(name=name,toolset='fin_working_memory',schema={'name':name,'description':model.__doc__,'parameters':model.model_json_schema()},handler=handler)

    adapter_ref = {}
    for name, model in CONTEXT_MODELS.items():
        def reader(parameters, _name=name, **kwargs):
            session = kwargs.get('session_id')
            binding(session)  # Tool caller cannot choose another user's session.
            db = adapter_ref['adapter']._ensure_session_db()
            rows = db.get_messages(session, include_compacted=True)
            try:
                return json.dumps(execute_context_tool(_name, parameters, rows), ensure_ascii=False)
            except (ValueError, ToolException) as exc:
                return json.dumps({'error':str(exc)}, ensure_ascii=False)
        registry.register(name=name,toolset='fin_working_memory',schema={'name':name,'description':model.__doc__,'parameters':model.model_json_schema()},handler=reader)

    class FinAPI(APIServerAdapter):
        def _create_agent(self,**kwargs):
            binding(kwargs['session_id'])
            model=kwargs.get('requested_model') or 'deepseek-v4-flash'
            if model not in {'deepseek-v4-flash','deepseek-v4-pro','deepseek-flash'}: raise ValueError('model_not_enabled')
            agent=AIAgent(model=model,provider='deepseek',base_url='https://api.deepseek.com',api_key=os.environ['DEEPSEEK_API_KEY'],
                session_id=kwargs['session_id'],session_db=self._ensure_session_db(),enabled_toolsets=['fin_working_memory'],
                max_iterations=5,max_tokens=2400,reasoning_config={'enabled':False},
                request_overrides={'max_tokens':2400,'extra_body':{'thinking':{'type':'disabled'}}},
                skip_context_files=True,skip_memory=True,skip_background_review=True,load_soul_identity=False,
                quiet_mode=True,run_budget_seconds=180,ephemeral_system_prompt=kwargs.get('ephemeral_system_prompt'),
                stream_delta_callback=kwargs.get('stream_delta_callback'),tool_progress_callback=kwargs.get('tool_progress_callback'))
            if set(agent.valid_tool_names)!=set(WORKING_MEMORY_MODELS)|set(CONTEXT_MODELS): raise ValueError('hermes_tool_scope_mismatch')
            import httpx
            audit_dir=args.home/'fin-audit'/kwargs['session_id']/uuid4().hex
            audit_dir.mkdir(parents=True)
            basis={'node_purpose':'Hermes native task working-memory loop, at most five model requests per turn',
                'input_scale':'Current Hermes session, three scoped working-paper and two native transcript reader tools, user-selected revisions',
                'required_outputs':['Public answer','Save/read/update relevant working paper'],
                'schema_burden':'Five simple tools; no finance template',
                'materiality_quality_risk':'Fallible notes, not financial acceptance; no user file or external-change tools',
                'comparable_run_evidence':'Native two-turn five-call memory proof used 8480 tokens; no forecast of savings',
                'reasoning_profile':'thinking_disabled; matched native conversation default',
                'max_input_characters':40000,'max_output_tokens':2400,'maximum_calls':5,
                'stop_truncation_behavior':'No retry; preserve original transcript and partial notes'}
            (audit_dir/'TokenBudgetBasis.json').write_text(json.dumps(basis,ensure_ascii=False),encoding='utf-8')
            calls=[]
            def before(request):
                body=json.loads(request.content)
                if len(calls)>=5 or len(request.content.decode())>40000 or body.get('max_tokens')!=2400:
                    raise RuntimeError('hermes_task_budget_before_transport')
                index=len(calls);calls.append({'status':'started','started':time.time()});request.extensions['fin_index']=index
                (audit_dir/f'{index}-request.private.json').write_text(json.dumps(body,ensure_ascii=False),encoding='utf-8')
                (audit_dir/'calls.json').write_text(json.dumps(calls),encoding='utf-8')
            def after(response):
                index=response.request.extensions['fin_index']
                original=response.stream
                class AuditStream(httpx.SyncByteStream):
                    def __iter__(self):
                        pieces=[]
                        try:
                            for piece in original:
                                pieces.append(piece)
                                yield piece
                        finally:
                            raw=b''.join(pieces).decode('utf-8',errors='replace')
                            (audit_dir/f'{index}-response.private.txt').write_text(raw,encoding='utf-8')
                            usage=None
                            try:
                                if 'text/event-stream' in response.headers.get('content-type',''):
                                    chunks=[json.loads(line[5:]) for line in raw.splitlines() if line.startswith('data:') and line[5:].strip()!='[DONE]']
                                    usage=next((c['usage'] for c in reversed(chunks) if c.get('usage')),None)
                                else: usage=json.loads(raw).get('usage')
                            except (ValueError,TypeError): pass
                            calls[index].update(status=response.status_code,usage=usage,elapsed_seconds=time.time()-calls[index]['started'])
                            (audit_dir/'calls.json').write_text(json.dumps(calls),encoding='utf-8')
                    def close(self): original.close()
                response.stream=AuditStream()
            client=httpx.Client(timeout=75,event_hooks={'request':[before],'response':[after]})
            agent.client=agent.client.with_options(http_client=client,max_retries=0)
            agent._client_kwargs.update(http_client=client,max_retries=0)
            agent._primary_runtime['client_kwargs'].update(http_client=client,max_retries=0)
            if agent._api_max_retries!=1: raise ValueError('hermes_retry_profile_not_locked')
            return agent
    async def serve():
        adapter=FinAPI(PlatformConfig(enabled=True,extra={'host':'127.0.0.1','port':args.port,'key':os.environ['FINSIGHT_HERMES_TOKEN']}))
        adapter_ref['adapter'] = adapter
        if args.check_session:
            agent=adapter._create_agent(session_id=args.check_session,requested_model='deepseek-v4-flash')
            print(json.dumps({'tools':sorted(agent.valid_tool_names),'api_attempts':agent._api_max_retries,'model_calls':0}))
            agent.client.close()
            return
        if not await adapter.connect(): raise RuntimeError('hermes_api_start_failed')
        try: await asyncio.Event().wait()
        finally: await adapter.disconnect()
    asyncio.run(serve())


if __name__=='__main__':main()
