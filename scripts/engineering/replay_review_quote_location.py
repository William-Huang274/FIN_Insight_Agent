"""Offline replay of saved Counter offsets and its explicitly selected sentence.

Original tool proposals are replayed unchanged. The new quote-mode call is an
isolated diagnostic using the sentence explicitly quoted in the saved response;
it is not a new model action, a finding, or an injected recovery observation.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import socket
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from replay_review_argument_recovery import load, restored, SavedResponse
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer
from sec_agent.agent_runtime.review_inspection import bind_location


class Capture(SavedResponse):
    definitions: list = []
    def bind_tools(self, tools, **kwargs):
        self.definitions = [convert_to_openai_tool(t) for t in tools]
        return self


async def run(args):
    h, out = args.run_dir, args.output
    out.mkdir(parents=True, exist_ok=True)
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in h.rglob('*') if p.is_file()}
    parent = load(h/'parent-entry.private.json')
    convergence = load(h/'convergence-state.private.json')
    artifacts = current_task_artifacts(parent).with_revisions(convergence['revisions'])
    before = {p['paper_id']: artifacts.read_paper(p['paper_id']) for p in artifacts.catalog()['papers']}
    entry = load(h/'review-entry.private.json')
    original_receipts = {m.tool_call_id: m for m in restored(load(h/'actor-states/confirmation_counter.private.json'))['messages']
                         if isinstance(m, ToolMessage)}
    rows = []
    async def replay(response, seed, label):
        model = Capture(response=response)
        agent = build_case_reviewer(role='counter', model=model, artifacts=artifacts, tools=[],
            confirmation=entry['confirmation'], max_model_calls=1)
        result = await agent.ainvoke({k:v for k,v in seed.items()
            if k in ('messages','recorded_findings','recorded_inspections')})
        ids = {c['id'] for c in response.tool_calls}
        receipts = [m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id in ids]
        assert len(receipts) == len(ids) and all(m.status == 'success' for m in receipts)
        assert not result.get('review') and result.get('recorded_findings', {}) == seed.get('recorded_findings', {})
        assert any(isinstance(m, AIMessage) and m.tool_calls == response.tool_calls for m in result['messages'])
        prior = [m for m in seed['messages'] if isinstance(m, ToolMessage) and m.status == 'success']
        assert all(m in result['messages'] for m in prior)
        (out/(label+'.private.json')).write_text(json.dumps({
            'proposal':response.model_dump(mode='json'), 'receipts':[m.model_dump(mode='json') for m in receipts],
            'tools':model.definitions}, ensure_ascii=False, indent=2), encoding='utf8')
        rows.append({'label':label,'prior_successes_retained':len(prior),'tools_successful':len(receipts)})
        return receipts
    for n in (4,5):
        response = AIMessage.model_validate(load(h/f'model-responses/{n:03}.private.json')['raw_response'])
        seed = restored(load(h/f'request-states/{n:03}.private.json')['state'])
        receipts = await replay(response, seed, f'original-{n:03}')
        assert all(m.artifact == original_receipts[m.tool_call_id].artifact for m in receipts)
    response = load(h/'model-responses/004.private.json')['raw_response']
    reason = response['additional_kwargs']['reasoning_content']
    # Explicitly labelled by the model as its chosen current claim sentence.
    selected = re.findall(r'Yes from the claims read: "([^"\n]+)"', reason)
    assert len(selected) == 1, 'No unique explicit model selection; do not choose for the model.'
    quote = selected[0]
    original_args = response['tool_calls'][0]['args']
    proposal = AIMessage(content='', tool_calls=[{'name':'read_review_location','args':{
        'paper_id':original_args['paper_id'], 'field_path':original_args['field_path'], 'quote':quote},
        'id':'offline-quote-navigation','type':'tool_call'}])
    seed = restored(load(h/'request-states/004.private.json')['state'])
    assert any(isinstance(m,ToolMessage) and quote in str(m.content) for m in seed['messages'])
    receipts = await replay(proposal, seed, 'diagnostic-only-quote')
    value = receipts[0].artifact
    assert value['status']=='exact_quote_match' and value['text']==quote
    assert bind_location(artifacts, receipts, 'P08', value['location_id']) == quote
    assert before == {pid:artifacts.read_paper(pid) for pid in before}
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    result = {'provider_calls':0,'remaining_calls':0,'network_calls':0,'original_hashes':hashes,
        'replayed':rows, 'selected_quote_origin':'explicit saved model sentence, unchanged',
        'match_start':value['match_start'],'match_end':value['match_end'], 'total_matches':value['total_matches'],
        'quote_characters':len(quote), 'all_papers_preserved':len(before),
        'accepted_verifier_and_counter_history_preserved':True,
        'no_findings_or_review_created':True,'diagnostic_reads_not_in_recovery':True,
        'financial_quality_pass':False,'live_model_behavior_verified':False}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='original_hashes'},ensure_ascii=False))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Network prohibited in offline replay')):
            await run(args)
    asyncio.run(offline())
