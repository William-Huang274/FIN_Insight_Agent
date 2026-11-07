"""Offline ACP process: DS tool history -> native Responses takeover -> resume.

Uses loopback fixture providers only. No provider keys or research conclusions.
Run inside the qualification image with --binary /opt/fin-dsh --output <new dir>.
"""
import argparse, asyncio, json, os, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4
from acp.schema import McpServerStdio
from sec_agent.agent_runtime.harness_profile import profile_overlay
from sec_agent.agent_runtime.harness_acp_session import admitted_acp_session


async def probe(binary, output, fixture, plugin):
    output.mkdir(parents=True,exist_ok=False)
    requests=[]; accounts=[]; steps={'ds':0,'sol':0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path.startswith('/calls/'):
                accounts.append({'path':self.path,'body':body})
                data=json.dumps({'status':'reserved' if self.path.endswith('reserve') else 'saved','stopRequired':False}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data);return
            requests.append({'path':self.path,'body':body})
            (output/'requests.json').write_text(json.dumps(requests),encoding='utf8')
            ds=self.path=='/v1/messages';kind='ds' if ds else 'sol';step=steps[kind];steps[kind]+=1
            name='read_source' if ds and step==0 else 'save' if not ds and step==0 else None
            args={} if ds else {'title':'Fixture','body':'Native takeover retained source 120 USD million.','base_version':0}
            if name:
                full=next(t.get('function',t)['name'] for t in body['tools'] if t.get('function',t)['name'].endswith(name))
            identity='call_'+str(len(requests));text='Native fixture complete.'
            if ds:
                rows=[{'type':'message_start','message':{'id':'msg_fixture','type':'message','role':'assistant','model':body['model'],'content':[],'usage':{'input_tokens':100,'output_tokens':0}}},
                    {'type':'content_block_start','index':0,'content_block':{'type':'tool_use','id':identity,'name':full,'input':{}} if name else {'type':'text','text':''}},
                    {'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps(args)} if name else {'type':'text_delta','text':text}},
                    {'type':'content_block_stop','index':0},
                    {'type':'message_delta','delta':{'stop_reason':'tool_use' if name else 'end_turn'},'usage':{'output_tokens':20}}, {'type':'message_stop'}]
            else:
                item=({'type':'function_call','id':'fc_'+identity,'call_id':identity,'name':full,'arguments':'','status':'in_progress'} if name else
                    {'type':'message','id':'msg_'+identity,'role':'assistant','status':'in_progress','content':[]})
                rows=[{'type':'response.created','response':{'id':'resp_'+identity,'status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':item.copy()}]
                if name:
                    rows.append({'type':'response.function_call_arguments.delta','output_index':0,'item_id':item['id'],'delta':json.dumps(args)})
                    item['arguments']=json.dumps(args)
                else:
                    part={'type':'output_text','text':'','annotations':[]}
                    rows += [{'type':'response.content_part.added','output_index':0,'content_index':0,'item_id':item['id'],'part':part},
                             {'type':'response.output_text.delta','output_index':0,'content_index':0,'item_id':item['id'],'delta':text}]
                    item['content']=[{**part,'text':text}]
                item['status']='completed'
                rows += [{'type':'response.output_item.done','output_index':0,'item':item.copy()},
                    {'type':'response.completed','response':{'id':'resp_'+identity,'status':'completed','output':[item],
                        'usage':{'input_tokens':100,'input_tokens_details':{'cached_tokens':0},'output_tokens':20,'output_tokens_details':{'reasoning_tokens':0}}}}]
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            for row in rows:self.wfile.write(('event: '+row['type']+'\ndata: '+json.dumps(row)+'\n\n').encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    endpoint=f'http://127.0.0.1:{server.server_port}'
    env={k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','TEMP','TMP')}
    env.update(DSH_HOME=str(output/'native'),HOME=str(output),FIN_HARNESS_LOCAL_TOKEN='fixture-token-not-provider-secret')
    base={'execution_id':str(uuid4()),'manifest_digest':'fixture','release':'pinned','model':'deepseek-flash'}
    servers=[McpServerStdio(name='fixture',command='/usr/local/bin/python',args=[str(fixture),'--mcp',str(output)],
        env=[{'name':'PYTHONPATH','value':os.environ.get('PYTHONPATH','')}])]
    common=dict(binary=binary,environment=env,directory=output,authority=lambda:None,stop=lambda:None,mcp_servers=servers)
    def patch(protocol,model,restore=None):
        p=output/(protocol+'.json')
        p.write_text(json.dumps(profile_overlay(model=model,protocol=protocol,endpoint=endpoint,prompt='Synthetic fixture only.',
            context_window=1050000,output_tokens=4096,summary_tokens=2048,reasoning='high',dispatch_plugin=plugin,restore_route=restore)))
        return ['--profile','sdk-minimal','--patch',str(p)]
    try:
        async with admitted_acp_session(**common,arguments=patch('deepseek_messages','deepseek-flash'),binding=base,run_id=str(uuid4())) as s:
            await s.prompt('Read the fixture source.');identity=s.session_id
        transition={'session_id':identity,'from_model':'deepseek-flash','to_model':'gpt-6.1-sol'}
        arguments=patch('openai_responses','gpt-6.1-sol',{'protocol':'deepseek_messages','model':'deepseek-flash'})
        for task in ('Save the retained source as a note.','Continue the same saved work.'):
            async with admitted_acp_session(**common,arguments=arguments,binding={**base,'model':'gpt-6.1-sol'},run_id=str(uuid4()),
                transition=transition,model_selection=('fin-openai','gpt-6.1-sol','high')) as s:
                assert s.session_id==identity
                result=await s.prompt(task);assert result['status']=='completed'
        sol=[r['body'] for r in requests if r['path']=='/v1/responses']
        assert len(sol)==3 and all(r['model']=='gpt-6.1-sol' and r['reasoning']['effort']=='high' for r in sol)
        assert any(i.get('type')=='function_call_output' and '120' in i.get('output','') for i in sol[0]['input'])
        assert all(r['max_output_tokens']==4096 for r in sol)
        assert sum(json.loads(x)['name']=='save' for x in (output/'tool-results.jsonl').read_text().splitlines())==1
        (output/'result.json').write_text(json.dumps({'passed':True,'session_id':identity,'requests':len(requests),'paid_calls':0,'native_takeover':True,'resume':True}))
        print((output/'result.json').read_text())
    finally:
        (output/'accounting.json').write_text(json.dumps(accounts));server.shutdown()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fixture',type=Path,default=Path(__file__).with_name('probe_dsh_acp.py'))
    p.add_argument('--plugin',type=Path,default=Path(__file__).resolve().parents[2]/'integrations/deepseek-harness/dispatch.mjs')
    a=p.parse_args();asyncio.run(probe(a.binary,a.output,a.fixture,a.plugin))
