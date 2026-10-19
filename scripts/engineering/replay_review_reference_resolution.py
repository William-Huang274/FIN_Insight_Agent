"""Replay a saved review submission against current case-local source navigation.

No provider, network, proposal rewriting or model-authored reference confirmation.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from replay_review_argument_recovery import load, restored, SavedResponse
from langchain_core.messages import AIMessage, ToolMessage
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, CaseReview
from sec_agent.agent_runtime.evidence_resolution import citation_inventory, review_reference_state
from sec_agent.agent_runtime.research_session import current_task_artifacts


async def run(args):
    h=args.run_dir; out=args.output; out.mkdir(parents=True,exist_ok=True)
    paths=[args.parent,*h.glob('*.json'),*h.glob('model-responses/*.json'),
           *h.glob('request-states/*.json'),*h.glob('actor-states/*.json'),*h.glob('audit/**/*.jsonl')]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    seed=restored(load(h/'request-states/001.private.json')['state'])
    observed=restored(load(h/'actor-states/confirmation_counter.private.json'))
    original=AIMessage.model_validate(load(h/'model-responses/001.private.json')['raw_response'])
    artifacts=current_task_artifacts(load(args.parent)).with_revisions(load(h/'convergence-state.private.json')['revisions'])
    papers=load(h/'confirmation-current-input.private.json')['papers']
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    historical_error=next(m for m in reversed(observed['messages'])
        if isinstance(m,ToolMessage) and m.name=='submit_case_review' and m.status=='error')
    missing=json.loads(historical_error.content)['unconfirmed_references']
    resolutions=[]
    for ref in missing:
        row=next(r for r in citation_inventory(artifacts,ref['paper_id']) if r['reference_id']==ref['reference_id'])
        assert row['status']=='exact'
        source_id=row['candidates'][0]['source_id']
        assert source_id==ref['original_reference']
        source=artifacts.source_item(source_id)
        resolutions.append({'original_reference':source_id,'reference_id':row['reference_id'],
            'source_digest':hashlib.sha256(json.dumps(source,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            'canonical_ids':row['candidates'][0]['canonical_ids'],
            'identity':row['candidates'][0]['identity'],'financial_semantics_verified':False})
    entry=load(h/'review-entry.private.json')
    model=SavedResponse(response=original)
    agent=build_case_reviewer(role='counter',model=model,tools=[],artifacts=artifacts,
        confirmation=entry['confirmation'],require_inspection=entry['require_inspection'],max_model_calls=2)
    input_state={k:v for k,v in seed.items() if k in ('messages','recorded_findings',
        'recorded_inspections','request_summary','request_summary_failure','author_change_projection')}
    ids={c['id'] for c in original.tool_calls}
    async for state in agent.astream(input_state,stream_mode='values'):
        receipts={m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
        if ids<=receipts.keys():break
    else:raise AssertionError('Saved submission was not executed')
    assert model.replay_count==1
    replayed=next(m for m in state['messages'] if isinstance(m,AIMessage) and m.id==original.id)
    assert replayed.tool_calls==original.tool_calls
    sources=[m for m in seed['messages'] if isinstance(m,ToolMessage)
        and m.name in {'read_research_source','read_review_source_span'} and m.status=='success']
    assert all(receipts[m.tool_call_id]==m for m in sources)
    assert state.get('recorded_findings')==seed.get('recorded_findings')
    assert not any(m.name=='confirm_review_reference' for m in state['messages'][len(seed['messages']):]
                   if isinstance(m,ToolMessage))
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    proposal=original.tool_calls[0]['args']['review']
    if state.get('review'):
        # Native schema adds optional defaults; compare model values in that
        # same schema rather than mistaking default fields for author edits.
        expected=CaseReview.model_validate({k:v for k,v in proposal.items() if k!='completion'}).model_dump(mode='json')
        for key in ['research_limitations','unresolved_data_requests','summary','finding_checks','assessments']:
            assert state['review'][key]==expected[key],key
    # The scripted replay is not another paid turn. Keep the actual historical
    # counters when persisting a recoverable state; never reset its allowance.
    for key in ('thread_model_call_count','run_model_call_count','thread_tool_call_count','run_tool_call_count'):
        if key in observed:
            state[key]=observed[key]
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,
            default=lambda x:x.model_dump(mode='json')),encoding='utf-8')
    save('replayed-state.private.json',state)
    result={'provider_calls':0,'network_calls':0,'original_hashes_unchanged':hashes,
        'resolutions':resolutions,'pending_references':review_reference_state(artifacts,state['messages']),
        'all_papers_unchanged':len(papers),'source_receipts_preserved':len(sources),
        'saved_finding_unchanged':True,'original_proposal_unchanged':True,'host_confirmations':0,
        'submission_receipts':[{'status':receipts[i].status,'content':receipts[i].content} for i in ids],
        'review_accepted_in_offline_replay':bool(state.get('review')),
        'historical_counters_preserved':{key:state[key] for key in observed if key.endswith('_call_count')},
        'research_quality_pass':False,'new_paid_calls':0,'remaining_paid_calls_untouched':True}
    save('result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='original_hashes_unchanged'},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
