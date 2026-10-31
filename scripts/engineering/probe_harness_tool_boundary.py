"""Opt-in, no-model Codex process probe using existing FIN artifact/calculation code.

All inference is a deterministic loopback Responses fixture. This is execution
qualification, not evidence of model compatibility or research quality. Requires
an explicitly supplied Codex binary; never reads the user's Codex credentials.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources


def run(binary: str, output: Path):
    output.mkdir(parents=True, exist_ok=False)
    work = output / 'workspace'
    work.mkdir()
    home = output / 'isolated-home'
    home.mkdir()
    requests, events, results = [], [], []
    state = {'step': 0, 'hold': False}
    arrived = threading.Event()
    release = threading.Event()
    source = {'numeric_fact_id': 'NUMFACT::synthetic_revenue', 'result_state': 'numeric_fact',
              'numeric_fact_authority': True, 'value_decimal': '120', 'unit': 'USD million',
              'ticker': 'SYNTHETIC', 'fiscal_period': 'FY2025', 'period_start': '2025-01-01',
              'period_end': '2025-12-31', 'source_observation_ids': ['fixture:1']}
    memory = lambda: WorkingMemory(output/'notes.sqlite', owner='fixture-owner', workspace='fixture-project',
                                   actor='lead', allow_remote_search=False)

    def execute(name, args):
        if name == 'fin_read': return source
        if name == 'fin_calculate':
            value = calculate_from_sources(SourceBoundCalculation.model_validate(args),
                                           lambda ref: source if ref == source['numeric_fact_id'] else {})
            state['calculation'] = value
            return value
        if name == 'fin_save':
            value = memory().save(**args)
            state['note'] = value
            return value
        if name == 'fin_read_note': return memory().read(**args)
        raise ValueError('unexpected_tool:'+name)

    def next_output():
        step=state['step'];state['step']+=1
        if step == 0: name,args='fin_read',{}
        elif step == 1:
            name,args='fin_calculate',{'expression':'revenue / 2', 'operands':{'revenue':{'source_id':source['numeric_fact_id']}},
                                     'result_unit':'USD million', 'rationale':'Synthetic arithmetic fixture, not a financial conclusion.'}
        elif step == 2:
            name,args='fin_save',{'title':'Synthetic working paper','body':'Fixture calculation '+state['calculation']['calculation_id']+' = 60 USD million.','base_version':0}
        elif step in (4,10): name,args='fin_read_note',{'note_id':state['note']['note_id']}
        elif step == 5:
            name,args='fin_save',{'title':'Synthetic working paper','body':'Fixture clarification; calculation remains non-authoritative.',
                                 'base_version':1,'mode':'append'}
        else:
            return {'id':f'msg_{step}', 'type':'message','role':'assistant','status':'completed',
                    'content':[{'type':'output_text','text':'Synthetic checkpoint: saved work remains readable; no financial judgment certified.','annotations':[]}]}
        return {'id':f'fc_{step}','call_id':f'call_{step}','type':'function_call','name':name,
                'arguments':json.dumps(args),'status':'completed'}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
            requests.append({'path':self.path,'body':body})
            if state['hold']:
                arrived.set();release.wait(15)
            item=next_output()
            response={'id':f'resp_{state["step"]}','object':'response','status':'completed','output':[item],
                      'usage':{'input_tokens':100,'output_tokens':20,'total_tokens':120}}
            rows=[{'type':'response.created','response':{'id':response['id'],'status':'in_progress','output':[]}},
                  {'type':'response.output_item.added','output_index':0,'item':item},
                  {'type':'response.output_item.done','output_index':0,'item':item},
                  {'type':'response.completed','response':response}]
            data=''.join('event: '+r['type']+'\ndata: '+json.dumps(r)+'\n\n' for r in rows).encode()
            try:
                self.send_response(200);self.send_header('Content-Type','text/event-stream')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass

    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    port=server.server_address[1]
    (home/'config.toml').write_text(f'''model = "fixture-model"
model_provider = "fixture"
approval_policy = "never"
sandbox_mode = "read-only"
web_search = "disabled"
model_context_window = 262144
model_auto_compact_token_limit = 240000
[model_providers.fixture]
name = "Loopback deterministic fixture"
base_url = "http://127.0.0.1:{port}/v1"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 0
stream_max_retries = 0
''',encoding='utf8')
    env={k:v for k,v in os.environ.items() if not any(t in k.upper() for t in ['API_KEY','ACCESS_TOKEN','AUTH_TOKEN'])}
    env['CODEX_HOME']=str(home)
    env['NO_PROXY']='127.0.0.1,localhost'
    proc=None;err=None

    def start():
        nonlocal proc,err
        inbox=queue.Queue()
        err=(output/f'process-{len(list(output.glob("process-*.log")))}.log').open('w',encoding='utf8')
        proc=subprocess.Popen([binary,'app-server','--stdio'],cwd=work,env=env,stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf8')
        def consume():
            for line in proc.stdout:
                try: inbox.put(json.loads(line))
                except ValueError: pass
        threading.Thread(target=consume,daemon=True).start()
        return inbox

    def send(row):
        proc.stdin.write(json.dumps(row)+'\n');proc.stdin.flush()

    def wait(inbox, predicate, timeout=40):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            row=inbox.get(timeout=max(.1,deadline-time.monotonic()));events.append(row)
            if 'method' in row and 'id' in row:
                if row['method']=='item/tool/call':
                    p=row['params'];args=p['arguments']
                    if isinstance(args,str): args=json.loads(args)
                    value=execute(p['tool'],args);results.append({'tool':p['tool'],'result':value})
                    send({'jsonrpc':'2.0','id':row['id'],'result':{'success':True,'contentItems':[{'type':'inputText','text':json.dumps(value)}]}})
                else: raise AssertionError('unexpected server request '+row['method'])
            if predicate(row): return row
        raise TimeoutError('protocol wait')

    def rpc(inbox, rid, method, params):
        send({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
        row=wait(inbox,lambda x:x.get('id')==rid and 'method' not in x)
        if 'error' in row: raise AssertionError(row)
        return row['result']

    def stop():
        if proc and proc.poll() is None:
            proc.stdin.close()
            try: proc.wait(timeout=8)
            except subprocess.TimeoutExpired: proc.terminate();proc.wait(timeout=8)
        if err: err.close()

    schemas={
        'fin_read':{'type':'object','properties':{}},
        'fin_calculate':SourceBoundCalculation.model_json_schema(),
        'fin_save':{'type':'object','properties':{'title':{'type':'string'},'body':{'type':'string'},'base_version':{'type':'integer'},'mode':{'type':'string'}},'required':['title','body','base_version']},
        'fin_read_note':{'type':'object','properties':{'note_id':{'type':'string'}},'required':['note_id']}}
    try:
        inbox=start()
        rpc(inbox,1,'initialize',{'clientInfo':{'name':'fin-offline-probe','version':'0.1'},'capabilities':{'experimentalApi':True}})
        send({'method':'initialized'})
        thread=rpc(inbox,2,'thread/start',{'cwd':str(work),'baseInstructions':'Use supplied FIN tools. Synthetic execution test only.',
                   'dynamicTools':[{'name':n,'description':'Synthetic FIN tool boundary probe','inputSchema':s} for n,s in schemas.items()]})
        tid=thread['thread']['id']
        rpc(inbox,3,'turn/start',{'threadId':tid,'input':[{'type':'text','text':'Run synthetic read, calculation, and save.'}]})
        end=wait(inbox,lambda x:x.get('method')=='turn/completed')
        assert end['params']['turn']['status']=='completed',end
        assert state['note']['version']==1
        before=len(results);stop();inbox=start()
        rpc(inbox,4,'initialize',{'clientInfo':{'name':'fin-offline-probe','version':'0.1'},'capabilities':{'experimentalApi':True}})
        send({'method':'initialized'})
        rpc(inbox,5,'thread/resume',{'threadId':tid})
        rpc(inbox,6,'turn/start',{'threadId':tid,'input':[{'type':'text','text':'Read the saved note and append the clarification.'}]})
        end=wait(inbox,lambda x:x.get('method')=='turn/completed')
        assert end['params']['turn']['status']=='completed',end
        assert state['note']['version']==2
        assert [x['tool'] for x in results[before:]]==['fin_read_note','fin_save']
        note=memory().read(state['note']['note_id'])
        assert state['calculation']['calculation_id'] in json.dumps(note)
        for rid in (7,8,9):
            rpc(inbox,rid,'thread/compact/start',{'threadId':tid})
            wait(inbox,lambda x:x.get('method')=='thread/compacted' or (x.get('method')=='item/completed' and x.get('params',{}).get('item',{}).get('type')=='contextCompaction'))
            # Item completion precedes the compact task's terminal lifecycle event.
            wait(inbox,lambda x:x.get('method')=='turn/completed')
        rpc(inbox,10,'turn/start',{'threadId':tid,'input':[{'type':'text','text':'Read saved work after compaction.'}]})
        wait(inbox,lambda x:x.get('method')=='turn/completed')
        assert results[-1]['tool']=='fin_read_note'
        assert state['calculation']['calculation_id'] in json.dumps(results[-1]['result'])
        stale=memory().save('Synthetic working paper','Must not overwrite.',base_version=1)
        assert not stale['saved'] and stale['current_version']==2
        assert memory().read(state['note']['note_id'],version=1)['version']==1
        denied=WorkingMemory(output/'notes.sqlite',owner='other',workspace='fixture-project',actor='lead').read(state['note']['note_id'])
        assert denied['found'] is False and 'body' not in denied
        state['hold']=True
        turn=rpc(inbox,11,'turn/start',{'threadId':tid,'input':[{'type':'text','text':'Synthetic cancellation probe.'}]})
        assert arrived.wait(15)
        rpc(inbox,12,'turn/interrupt',{'threadId':tid,'turnId':turn['turn']['id']})
        end=wait(inbox,lambda x:x.get('method')=='turn/completed')
        assert end['params']['turn']['status']=='interrupted',end
        summary={'status':'passed','binary_version':subprocess.check_output([binary,'--version'],text=True).strip(),
                 'paid_model_calls':0,'fixture_requests':len(requests),'tool_calls':[x['tool'] for x in results],
                 'note_version':2,'restart_resume':True,'manual_compactions':3,'post_compaction_readback':True,
                 'stale_write_rejected':True,'cross_owner_read_rejected':True,'interrupt':True,
                 'scope':'real Codex app-server, deterministic loopback inference, existing FIN calculation and working memory; synthetic source reader; no model-quality or production Java/BFF proof'}
    except Exception as exc:
        summary={'status':'failed','error':repr(exc),'paid_model_calls':0,'fixture_requests':len(requests)}
        raise
    finally:
        release.set();stop();server.shutdown();server.server_close()
        for filename,value in [('summary.json',summary),('requests.json',requests),('events.json',events),('tools.json',results)]:
            (output/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.codex,args.output.resolve()),ensure_ascii=False))
