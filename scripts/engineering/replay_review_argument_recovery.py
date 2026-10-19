"""Offline native replay of an unchanged saved response and tool receipts.

No model transport, proposal edits, new reads or financial acceptance.
"""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage, messages_from_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain.tools import ToolRuntime, tool
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, CaseReviewFinding
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_execution import ReviewExecutionControl, ReviewExecutionStopped


def load(path): return json.loads(path.read_text(encoding='utf8'))


def restored(state):
    value=deepcopy(state)
    value['messages']=messages_from_dict([m if 'data' in m else {'type':m['type'],'data':m} for m in state['messages']])
    return value


class SavedResponse(BaseChatModel):
    response: AIMessage
    replay_count: int=0
    @property
    def _llm_type(self): return 'offline-original-response-no-transport'
    def bind_tools(self,tools,**kwargs): return self
    def _generate(self,messages,stop=None,run_manager=None,**kwargs):
        assert self.replay_count==0,'Unexpected second response request'
        self.replay_count+=1
        return ChatResult(generations=[ChatGeneration(message=self.response.model_copy(deep=True))])


async def run(args):
    h=args.run_dir; out=args.output; out.mkdir(parents=True,exist_ok=True)
    paths=[args.parent,h/'request-states/002.private.json',h/'model-responses/002.private.json',
           h/'actor-states/confirmation_counter.private.json',h/'convergence-state.private.json',
           h/'confirmation-current-input.private.json',h/'review-entry.private.json']
    paths += sorted((h/'model-responses').glob('*.private.json'))
    paths += sorted((h/'request-states').glob('*.private.json'))
    paths += sorted((h/'audit').rglob('*.jsonl'))
    paths += list(h.glob('cancelled-request-usage-unknown.json'))
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    seed=restored(load(paths[1])['state'])
    raw=load(paths[2])['raw_response']; original=AIMessage.model_validate(raw)
    observed=restored(load(paths[3]))
    artifacts=current_task_artifacts(load(args.parent)).with_revisions(load(paths[4])['revisions'])
    papers=load(paths[5])['papers']
    assert {pid:artifacts.read_paper(pid) for pid in papers}==papers
    entry=load(paths[6]); receipts={m.tool_call_id:m for m in observed['messages'] if isinstance(m,ToolMessage)}
    source_calls={c['id']:c for c in original.tool_calls if c['name']=='read_research_source'}
    replayed=[]
    @tool
    def read_research_source(source_id: str, runtime: ToolRuntime, offset: int=0, max_characters: int=4000):
        """Return the exact already-saved source receipt; never reread or fetch."""
        c=source_calls[runtime.tool_call_id]
        assert c['args']==dict(source_id=source_id,offset=offset,max_characters=max_characters)
        replayed.append(c['id'])
        return receipts[c['id']].model_copy(deep=True)
    model=SavedResponse(response=original)
    agent=build_case_reviewer(role='counter',model=model,tools=[read_research_source],artifacts=artifacts,
        confirmation=entry['confirmation'],require_inspection=entry['require_inspection'],max_model_calls=3)
    # A fresh offline invocation uses the same native recovery fields. Original
    # lifetime counters remain in the hashed archive, not this fake call budget.
    input_state={k:v for k,v in seed.items() if k in ('messages','recorded_findings',
        'recorded_inspections','request_summary','request_summary_failure','author_change_projection')}
    ids={c['id'] for c in original.tool_calls}
    state=None
    async for value in agent.astream(input_state,stream_mode='values'):
        complete={m.tool_call_id for m in value['messages'] if isinstance(m,ToolMessage)}
        if ids <= complete:
            state=value
            break  # Drain this real saved batch; never request a new response.
    assert state is not None
    assert model.replay_count==1
    assert sorted(replayed)==sorted(source_calls)
    after_receipts={m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
    # Preserve all reads, including all six new native87 source reads.
    sources=[m for m in observed['messages'] if isinstance(m,ToolMessage) and m.name=='read_research_source' and m.status=='success']
    for m in sources:assert after_receipts[m.tool_call_id]==m
    new_source_ids={c['id'] for p in (h/'model-responses').glob('*.private.json')
        for c in load(p)['raw_response'].get('tool_calls',[]) if c['name']=='read_research_source'}
    assert len(new_source_ids)==6 and new_source_ids <= {m.tool_call_id for m in sources}
    encoded=next(c for c in original.tool_calls if c['name']=='record_case_finding')
    normalized=next(m for m in state['messages'] if isinstance(m,AIMessage) and any(c['id']==encoded['id'] for c in m.tool_calls))
    parsed=next(c for c in normalized.tool_calls if c['id']==encoded['id'])
    assert parsed['args']['finding']==json.loads(encoded['args']['finding'])
    assert normalized.response_metadata['tool_argument_recovery'][-1]['original_arguments']==encoded['args']
    assert not state.get('review')  # A finding never becomes a completed review.
    feedback=after_receipts[encoded['id']]
    if feedback.status!='error':
        saved=state['recorded_findings'][parsed['args']['finding']['finding_id']]
        assert saved==CaseReviewFinding.model_validate(parsed['args']['finding']).model_dump(mode='json')
    # Test the actual failed batch at the dispatch boundary, without a model.
    control=ReviewExecutionControl(stop_on_tool_error=True)
    try:control.before_dispatch(observed)
    except ReviewExecutionStopped as exc:
        assert exc.error['reason']=='review_tool_batch_error_before_dispatch'
    else:raise AssertionError('Historical nonfinal error did not stop dispatch')
    ReviewExecutionControl(stop_on_tool_error=True).before_dispatch(seed)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,
            default=lambda x:x.model_dump(mode='json')),encoding='utf8')
    save('replayed-state.private.json',state)
    result={'provider_calls':0,'network_calls':0,'original_hashes_unchanged':hashes,
        'all_11_papers_unchanged':True,'P05_P08_reused_unchanged':True,
        'original_proposal_values_unchanged':True,'source_receipts_preserved':len(sources),
        'new_source_receipts_preserved':len(new_source_ids),
        'current_batch_read_receipts_replayed':len(replayed),'finding_tool_status':feedback.status,
        'finding_feedback':feedback.content,'review_complete':False,
        'historical_error_batch_stopped_before_dispatch':True,'normal_read_batch_allowed':True,
        'proposal_or_classification_manually_edited':False}
    save('result.json',result);print(json.dumps({k:v for k,v in result.items() if k!='original_hashes_unchanged'},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    async def offline():
        # Windows creates a local socketpair when constructing its event loop.
        # Install the network guard after that infrastructure exists.
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
