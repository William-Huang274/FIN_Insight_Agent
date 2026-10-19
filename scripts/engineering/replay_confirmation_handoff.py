"""Replay ten saved reviewer turns through native tools, without a provider.

Private inputs stay outside Git. Saved responses are replay fixtures, not new
model decisions. No replay output is installed as an accepted live review.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from typing import Any
from unittest.mock import patch
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from mcp import Client
from mcp.server.mcpserver import MCPServer
from replay_review_argument_recovery import load, restored, SavedResponse
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.case_artifacts import register_case_artifact_tools
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, case_mcp_tools
from sec_agent.agent_runtime.workpaper_changes import confirmation_context
from sec_agent.agent_runtime.confirmation_reading import missing_reads, with_reading_targets
from sec_agent.agent_runtime.review_context import handoff_page
from sec_agent.research_foundation.research_methods import get_research_method


class Capture(SavedResponse):
    seen: list = []
    definitions: list = []
    def bind_tools(self, tools, **kwargs):
        self.definitions=[convert_to_openai_tool(t) for t in tools]
        return self
    def _generate(self,messages,stop=None,run_manager=None,**kwargs):
        self.seen=list(messages)
        return super()._generate(messages,stop=stop,run_manager=run_manager,**kwargs)


async def run(args):
    h,out=args.run_dir,args.output;out.mkdir(parents=True,exist_ok=True)
    manifest={}
    def read(p):
        manifest[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        return load(p)
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,
            default=lambda x:x.model_dump(mode='json')),encoding='utf8')
    parent=read(h/'live-native100/parent-entry.private.json')
    state=read(h/'offline-native98-merge/convergence-state.private.json')
    entry=read(h/'live-native100/review-entry.private.json')
    original=current_task_artifacts(parent)
    artifacts=original.with_revisions(state['revisions'])
    snapshot={p['paper_id']:artifacts.read_paper(p['paper_id']) for p in artifacts.catalog()['papers']}
    context=confirmation_context(original,state['revisions'],entry['confirmation']['findings_to_confirm'],
        artifact_history=state.get('artifact_history',()),confirmation_history=state.get('confirmation_history',()))
    assert 'claim_changes' in context['changes']['P08'], 'Exact baseline must be recovered; do not guess.'
    assert len(context['author_responses']['P08'])==1
    assert len(context['historical_author_responses']['P08'])==6
    context=with_reading_targets(artifacts,context)
    save('new-full-handoff.private.json',context)
    rows=[]
    for run in (100,101):
        for n in range(1,6):
            prefix=f'native{run}-{n:03}'
            source=h/f'live-native{run}'
            wire=read(source/f'requests/{n:03}.private.json')
            seed=restored(read(source/f'request-states/{n:03}.private.json')['state'])
            response=AIMessage.model_validate(read(source/f'model-responses/{n:03}.private.json')['raw_response'])
            model=Capture(response=response)
            server=MCPServer('offline-confirmation-handoff')
            register_case_artifact_tools(server,artifacts)
            @server.tool(name='get_research_method',structured_output=True)
            def method(method_id: str='') -> dict[str, Any]:
                return get_research_method(method_id)
            async with Client(server,raise_exceptions=False) as client:
                agent=build_case_reviewer(role='verifier',model=model,artifacts=artifacts,
                    tools=await case_mcp_tools(client),confirmation=context,max_model_calls=1)
                result=await agent.ainvoke({k:v for k,v in seed.items()
                    if k in ('messages','recorded_findings','recorded_inspections')})
            assert model.replay_count==1 and not result.get('review')
            ids={t['id'] for t in response.tool_calls}
            receipts=[m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id in ids]
            assert len(receipts)==len(ids) and all(m.status=='success' for m in receipts)
            assert any(isinstance(m,AIMessage) and m.tool_calls==response.tool_calls for m in result['messages'])
            prior=[m for m in seed['messages'] if isinstance(m,ToolMessage) and m.status=='success']
            assert all(m in result['messages'] and m in model.seen for m in prior)
            actual=next(json.loads(m.content)['revision_confirmation'] for m in model.seen
                if m.type=='human' and 'revision_confirmation' in m.content)
            assert len(actual['author_responses']['P08'])==1
            assert actual['historical_author_responses']['P08']['count']==6
            assert actual['changes']['P08']['claim_changes']
            assert actual['calculation_readbacks']['P08']
            definitions={t['function']['name']:t['function'] for t in model.definitions}
            assert 'CALC::' in definitions['read_research_source']['description']
            assert 'read_review_handoff' in definitions
            assert all(name in definitions for name in ['read_research_artifact','read_review_location',
                'read_research_source','record_case_finding','submit_case_review'])
            save(prefix+'-request.private.json',{'messages':model.seen,'tools':model.definitions})
            save(prefix+'-replayed-tools.private.json',receipts)
            rows.append({'run':run,'call':n,'native_replayed_actions':len(receipts),
                'retained_prior_successes':len(prior),'original_proposal_unchanged':True,
                'reading_targets_before':missing_reads(artifacts,context,'P08',seed['messages']),
                'reading_targets_after':missing_reads(artifacts,context,'P08',result['messages']),
                'old_request_characters':len(json.dumps(wire,ensure_ascii=False)),
                'new_message_characters':sum(len(str(m.content)) for m in model.seen)})
            print(prefix+' native batch verified',flush=True)
    # Diagnostic readback only: never place these reads in a recovery journal.
    navs=context['calculation_readbacks']['P08'];calc_views=[]
    for nav in navs:
        a=nav['arguments'];v=artifacts.read_source(**a)
        assert v['result_state']=='non_authoritative_metric'
        calc_views.append(v)
    history_args={'section':'historical_author_responses','paper_id':'P08'}
    text='';offset=0
    while True:
        page=handoff_page(artifacts,context,**history_args,offset=offset);text+=page['text']
        if page['next_offset'] is None:break
        offset=page['next_offset']
    assert json.loads(text)==context['historical_author_responses']['P08']
    assert snapshot=={pid:artifacts.read_paper(pid) for pid in snapshot}
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in manifest.items())
    save('diagnostic-only-calculation-readbacks.private.json',calc_views)
    result={'provider_calls':0,'network_calls':0,'remaining_calls':0,'rounds':rows,
        'native_actions_replayed':sum(r['native_replayed_actions'] for r in rows),
        'historical_answers_exact_readback':True,'all_papers_preserved':len(snapshot),
        'original_hashes':manifest,'accepted_review_created':False,'financial_quality_pass':False,
        'model_convergence_verified':False,'diagnostic_reads_not_in_recovery':True}
    save('result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rounds','original_hashes')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network in offline replay')):
            await run(args)
    asyncio.run(offline())
