"""Replay saved anchor lookups through native tools without changing proposals."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from replay_review_argument_recovery import load, restored, SavedResponse
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
    agent=build_case_reviewer(role='verifier',model=model,tools=[],artifacts=artifacts,
        confirmation=entry['confirmation'],require_inspection=entry['require_inspection'],max_model_calls=1)
    inputs={k:v for k,v in seed.items() if k in ('messages','recorded_findings','recorded_inspections',
        'request_summary','request_summary_failure','author_change_projection')}
    ids={c['id'] for c in original.tool_calls}
    async for state in agent.astream(inputs,stream_mode='values'):
        receipts={m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
        if ids<=receipts.keys():break
    else:raise AssertionError('Original batch not completed')
    assert model.replay_count==1 and not state.get('review')
    assert all(receipts[i].status=='success' for i in ids)
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
    assert emitted.tool_calls==original.tool_calls
    recovered=[]
    for call in original.tool_calls:
        receipt=receipts[call['id']]
        if previous[call['id']].status!='error':continue
        value=receipt.artifact
        assert value['status']=='multiple_anchor_matches' and value['selected_match'] is None
        assert value['total_matches']==2 and len(value['candidates'])==2
        body=source_body(artifacts,value['source_id'])
        for c in value['candidates']:
            span=c['quote_span']
            assert body[span['start']:span['end']]==c['text']
            followup=read_source_span(artifacts,**c['readback']['arguments'])
            assert followup['source_digest']==value['source_digest']
        recovered.append({'tool_call_id':call['id'],'source_id':value['source_id'],
            'positions':[c['match_start'] for c in value['candidates']],
            'candidate_characters':sum(len(c['text']) for c in value['candidates']),
            'original_error':previous[call['id']].content})
    assert len(recovered)==3
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
    save('replayed-state.private.json',state)
    result={'provider_calls':0,'network_calls':0,'remaining_paid_calls':4,
        'original_hashes_unchanged':hashes,'original_proposal_unchanged':True,
        'all_papers_unchanged':len(papers),'counter_result_unchanged':True,
        'all_successful_receipts_preserved':len(successful),
        'same_batch_successful_receipts_preserved':sum(previous[i].status=='success' for i in ids),
        'recovered_navigation':recovered,'next_dispatch_allowed_by_tool_feedback':True,
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
