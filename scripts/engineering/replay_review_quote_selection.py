"""Replay an unchanged source quote/span conflict as explicit selection feedback."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from replay_review_argument_recovery import load, restored, SavedResponse
from mcp.server.mcpserver import MCPServer
from mcp import Client
from sec_agent.agent_runtime.case_artifacts import register_case_artifact_tools
from sec_agent.agent_runtime.case_review_agent import case_mcp_tools
from langchain_core.messages import AIMessage, ToolMessage
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_execution import ReviewExecutionControl
from sec_agent.agent_runtime.evidence_resolution import source_body, read_source_span


async def run(args):
    h=args.run_dir; out=args.output; out.mkdir(parents=True,exist_ok=True)
    paths=[args.parent,*h.glob('*.json'),*h.glob('requests/*.json'),
        *h.glob('request-states/*.json'),*h.glob('model-responses/*.json'),
        *h.glob('actor-states/*.json'),*h.glob('audit/**/*.jsonl')]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    seed=restored(load(h/'request-states/001.private.json')['state'])
    observed=restored(load(h/'actor-states/confirmation_verifier.private.json'))
    original=AIMessage.model_validate(load(h/'model-responses/001.private.json')['raw_response'])
    entry=load(h/'review-entry.private.json')
    artifacts=current_task_artifacts(load(args.parent)).with_revisions(load(h/'convergence-state.private.json')['revisions'])
    papers=load(h/'confirmation-current-input.private.json')['papers']
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    model=SavedResponse(response=original)
    server=MCPServer('offline-calculator-layout')
    register_case_artifact_tools(server,artifacts)
    async with Client(server,raise_exceptions=False) as client:
        tools=await case_mcp_tools(client)
        from langchain.tools import tool
        prior_progress = next(m for m in observed['messages'] if isinstance(m,ToolMessage)
            and m.name=='report_research_progress' and m.tool_call_id in {c['id'] for c in original.tool_calls})
        progress_call = next(c for c in original.tool_calls if c['name']=='report_research_progress')
        @tool
        def report_research_progress(message: str):
            """Reuse an already delivered progress receipt, without sending it again."""
            assert message==progress_call['args']['message']
            return prior_progress.content
        tools.append(report_research_progress)
        agent=build_case_reviewer(role='verifier',model=model,tools=tools,artifacts=artifacts,
            confirmation=entry['confirmation'],require_inspection=entry['require_inspection'],max_model_calls=1)
        inputs={k:v for k,v in seed.items() if k in ('messages','recorded_findings','recorded_inspections',
            'request_summary','request_summary_failure','author_change_projection')}
        ids={c['id'] for c in original.tool_calls}
        async for state in agent.astream(inputs,stream_mode='values'):
            receipts={m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
            if ids<=receipts.keys():break
        else:raise AssertionError('Original batch not completed')
    assert model.replay_count==1 and not state.get('review')
    assert all(receipts[i].status=='success' for i in ids), [(receipts[i].name,receipts[i].content) for i in ids if receipts[i].status!='success']
    previous={m.tool_call_id:m for m in observed['messages'] if isinstance(m,ToolMessage)}
    successful=[m for m in previous.values() if m.status=='success']
    for m in successful:
        new=receipts[m.tool_call_id]
        # LangGraph allocates a fresh message UUID on replay. Validate every
        # actual result field, then reuse the original successful receipt.
        assert new.model_dump(exclude={'id'})==m.model_dump(exclude={'id'})
    retained={m.tool_call_id:m for m in successful}
    state['messages']=[retained.get(m.tool_call_id,m) if isinstance(m,ToolMessage) else m
        for m in state['messages']]
    receipts={m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
    assert all(receipts[m.tool_call_id]==m for m in successful)
    emitted=next(m for m in state['messages'] if isinstance(m,AIMessage) and m.id==original.id)
    from copy import deepcopy
    expected_calls=deepcopy(original.tool_calls)
    for call in expected_calls:
        if call['name']=='record_case_finding' and isinstance(call['args']['finding'],str):
            call['args']['finding']=json.loads(call['args']['finding'])
    assert emitted.tool_calls==expected_calls
    recovered=[]
    for call in original.tool_calls:
        receipt=receipts[call['id']]
        if previous[call['id']].status!='error':continue
        value=receipt.artifact
        assert value['status']=='source_quote_selection_required'
        assert value['accepted'] is False
        feedback=value['source_quote_recovery'][0]
        assert feedback['reason']=='quote_span_conflict' and feedback['selected_match'] is None
        assert feedback['original_input']['quote_span']['start']==63
        assert feedback['quote_candidates'][0]['quote_span']['start']==60
        assert feedback['quote_candidates'][0]['quote_span']['end']==170
        assert feedback['supplied_span_characters']==600
        recovered.append({'tool_call_id':call['id'],'feedback':feedback,
            'original_error':previous[call['id']].content})
    assert len(recovered)==1
    assert state.get('recorded_findings')==seed.get('recorded_findings')
    ReviewExecutionControl(stop_on_tool_error=True).before_dispatch(state)
    assert state.get('recorded_findings')==seed.get('recorded_findings')
    assert state.get('recorded_inspections')==seed.get('recorded_inspections')
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    # Offline replay consumes no request and must preserve real lifetime usage.
    for key in ('thread_model_call_count','run_model_call_count','thread_tool_call_count','run_tool_call_count'):
        if key in observed:state[key]=observed[key]
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,
            default=lambda x:x.model_dump(mode='json')),encoding='utf8')
    save('replayed-feedback-state.private.json',state)
    result={'provider_calls':0,'network_calls':0,'remaining_paid_calls':2,
        'original_hashes_unchanged':hashes,'original_proposal_unchanged':True,
        'all_papers_unchanged':len(papers),'counter_result_unchanged':True,
        'all_successful_receipts_preserved':len(successful),
        'same_batch_successful_receipts_preserved':sum(previous[i].status=='success' for i in ids),
        'selection_feedback':recovered,'next_dispatch_allowed_by_tool_feedback':True,
        'host_selected_matches':0,'host_classification_changes':0,'review_accepted':False,
        'research_quality_pass':False,'historical_counters_preserved':{k:v for k,v in state.items() if k.endswith('_call_count')}}
    save('result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='original_hashes_unchanged'},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
