"""Replay an unchanged saved final-call read batch without provider or network.

Case reads use the native MCP implementation. Source-document arguments use
the maintained request type; a backend read is deliberately unavailable here.
This is validation evidence, not a recoverable paid continuation checkpoint.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from typing import Any
from unittest.mock import patch

from replay_review_argument_recovery import load, restored, SavedResponse
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage
from langchain.agents.middleware.types import ModelRequest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, case_mcp_tools, ReviewCallAllowance
from sec_agent.agent_runtime.case_artifacts import register_case_artifact_tools
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_execution import ReviewExecutionControl, ReviewExecutionStopped
from sec_agent.research_foundation.source_document_navigation import SourceDocumentToolRequest


async def run(args):
    h=args.run_dir; out=args.output; out.mkdir(parents=True,exist_ok=True)
    paths=[args.parent,*h.glob('*.json'),*h.glob('requests/*.json'),
           *h.glob('request-states/*.json'),*h.glob('model-responses/*.json'),
           *h.glob('actor-states/*.json'),*h.glob('audit/**/*.jsonl')]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    seed=restored(load(h/'request-states/002.private.json')['state'])
    original=AIMessage.model_validate(load(h/'model-responses/002.private.json')['raw_response'])
    first=AIMessage.model_validate(load(h/'model-responses/001.private.json')['raw_response'])
    artifacts=current_task_artifacts(load(args.parent)).with_revisions(load(h/'convergence-state.private.json')['revisions'])
    papers=load(h/'confirmation-current-input.private.json')['papers']
    entry=load(h/'review-entry.private.json')
    counter=entry['previous_review']['counter']
    wires=[load(h/'requests'/f'{n:03}.private.json') for n in (1,2)]
    reasoning=original.additional_kwargs.get('reasoning_content','')
    trace_markers={phrase:reasoning.find(phrase) for phrase in
        ('this one + final','this is #1',"I don't know the exact tool schema",'meaning next call is final')}
    assert counter
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    saved={m.tool_call_id:m for m in seed['messages'] if isinstance(m,ToolMessage)}
    first_ids={c['id'] for c in first.tool_calls}
    assert len(first_ids)==6 and all(saved[i].status=='success' for i in first_ids)

    server=MCPServer('offline-review-allowance')
    register_case_artifact_tools(server,artifacts)
    @server.tool(name='read_source_document',structured_output=True)
    def source_document(request: SourceDocumentToolRequest, branch_id: str) -> dict[str, Any]:
        """Validate maintained source-document arguments; never fetch in this replay."""
        raise AssertionError('A valid document read needs a separate offline source backend')

    model=SavedResponse(response=original)
    async with Client(server,raise_exceptions=False) as client:
        tools=await case_mcp_tools(client)
        # Real second-request counters are inspected separately from the fake
        # one-call graph. The replay must not renew the paid allowance.
        request=ModelRequest(model=model,tools=tools,messages=seed['messages'],
            system_message=SystemMessage(content='Stable reviewer'),
            state={**seed,'run_model_call_count':1})
        projected=ReviewCallAllowance(2).request_with_budget(request)
        assert projected.tools==tools and projected.messages[:-1]==seed['messages']
        allowance=json.loads(projected.messages[-1].content)
        assert allowance['current_request_number']==2
        assert allowance['additional_requests_after_this_response']==0
        wire_request=request.override(tools=wires[0]['tools'])
        wire_projection=ReviewCallAllowance(2).request_with_budget(wire_request)
        assert wire_projection.tools==wires[0]['tools']
        agent=build_case_reviewer(role='verifier',model=model,tools=tools,artifacts=artifacts,
            confirmation=entry['confirmation'],require_inspection=entry['require_inspection'],max_model_calls=1)
        inputs={k:v for k,v in seed.items() if k in ('messages','recorded_findings',
            'recorded_inspections','request_summary','request_summary_failure','author_change_projection')}
        batch_state=None
        ids={c['id'] for c in original.tool_calls}
        async for state in agent.astream(inputs,stream_mode='values'):
            received={m.tool_call_id for m in state['messages'] if isinstance(m,ToolMessage)}
            if batch_state is None and ids<=received:
                batch_state=state
        assert batch_state is not None
    assert model.replay_count==1 and not state.get('review')
    receipts={m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
    ids={c['id'] for c in original.tool_calls}
    assert ids<=receipts.keys()
    assert all('closeout reserve' not in receipts[i].content for i in ids)
    assert all(receipts[i]==saved[i] for i in first_ids)
    replayed=next(m for m in state['messages'] if isinstance(m,AIMessage) and m.id==original.id)
    assert replayed.tool_calls==original.tool_calls
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    assert load(h/'review-entry.private.json')['previous_review']['counter']==counter
    control=ReviewExecutionControl(stop_on_tool_error=True)
    errors=any(receipts[i].status=='error' for i in ids)
    if errors:
        # Inspect immediately after the real batch, before the native budget
        # terminator appends its synthetic final assistant message.
        try:control.before_dispatch(batch_state)
        except ReviewExecutionStopped as exc:
            assert exc.error['reason']=='review_tool_batch_error_before_dispatch'
        else:raise AssertionError('Native batch error should stop next dispatch')
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    result={'provider_calls':0,'network_calls':0,'remaining_paid_calls':0,
        'offline_model_replays':model.replay_count,'original_hashes_unchanged':hashes,
        'current_allowance':allowance,'authorized_tools_retained':[t.name for t in tools],
        'original_proposal_unchanged':True,'counter_result_unchanged':True,
        'all_papers_unchanged':len(papers),'successful_prior_receipts_preserved':len(first_ids),
        'batch':[{'name':c['name'],'id':c['id'],'status':receipts[c['id']].status,
            'content':receipts[c['id']].content} for c in original.tool_calls],
        'review_complete':False,'research_quality_pass':False,
        'not_a_continuation_checkpoint':True}
    result['historical_input_diagnosis']={
        'tool_counts':[len(w['tools']) for w in wires],
        'second_request_tools':[t['function']['name'] for t in wires[1]['tools']],
        'full_first_tool_schemas_survive_final_allowance_projection':True,
        'reasoning_characters':len(reasoning),'reasoning_marker_offsets':trace_markers,
        'interpretation':'Model miscounted the second request as first, interpreted final-call withdrawal as next-call policy, and guessed unavailable source-document parameters. Repaired input behavior is not yet paid-model validated.'}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'replayed-state.private.json').write_text(json.dumps(state,ensure_ascii=False,
        default=lambda x:x.model_dump(mode='json')),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='original_hashes_unchanged'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
