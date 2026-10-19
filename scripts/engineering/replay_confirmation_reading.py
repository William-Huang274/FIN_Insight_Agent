"""Replay saved confirmation without provider calls or accepting a financial verdict."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch
from langchain_core.messages import AIMessage, ToolMessage
from mcp import Client
from mcp.server.mcpserver import MCPServer
from replay_review_argument_recovery import load, restored, SavedResponse
from sec_agent.agent_runtime.case_artifacts import register_case_artifact_tools
from sec_agent.agent_runtime.case_review_agent import (
    CaseReview, build_case_reviewer, case_mcp_tools, validate_case_review, validate_finding_confirmation)
from sec_agent.agent_runtime.confirmation_reading import missing_reads
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_inspection import read_location, read_structured_location


class Capture(SavedResponse):
    seen: list = []
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen = list(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


async def run(args):
    h, out = args.run_dir, args.output
    out.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
            default=lambda x:x.model_dump(mode='json')), encoding='utf8')
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in h.rglob('*') if p.is_file()}
    artifacts = current_task_artifacts(load(h/'parent-entry.private.json')).with_revisions(
        load(h/'convergence-state.private.json')['revisions'])
    papers = {p['paper_id']:artifacts.read_paper(p['paper_id']) for p in artifacts.catalog()['papers']}
    entry = load(h/'review-entry.private.json'); confirmation = entry['confirmation']
    seed = restored(load(h/'request-states/002.private.json')['state'])
    original = AIMessage.model_validate(load(h/'model-responses/002.private.json')['raw_response'])
    observed = restored(load(h/'actor-states/confirmation_verifier.private.json'))
    model = Capture(response=original)
    server = MCPServer('offline-confirmation-reading')
    register_case_artifact_tools(server, artifacts)
    async with Client(server, raise_exceptions=False) as client:
        agent = build_case_reviewer(role='verifier', model=model, artifacts=artifacts,
            tools=await case_mcp_tools(client), confirmation=confirmation, max_model_calls=1)
        inputs = {k:v for k,v in seed.items() if k in ('messages','recorded_findings','recorded_inspections')}
        state = await agent.ainvoke(inputs)
    assert model.replay_count == 1 and not state.get('review')
    latest = next(m for m in reversed(state['messages']) if isinstance(m,ToolMessage))
    assert 'read_current_revision_before_review' in latest.content
    emitted = next(m for m in reversed(state['messages']) if isinstance(m,AIMessage) and m.tool_calls)
    assert emitted.tool_calls == original.tool_calls
    assert not any('runtime_model_call_allowance' in str(m.content) or 'Budget: up to' in str(m.content) for m in model.seen)
    system = str(model.seen[0].content)
    assert 'Read every submitted workpaper' not in system and 'current_reading_targets' in system
    original_receipts = [m for m in observed['messages'] if isinstance(m,ToolMessage) and m.status=='success']
    for m in original_receipts:
        assert any(n == m for n in state['messages'])
    # Mechanical test: native read functions, never inserted into a live recovery
    # state. These reads show the gate works; they are not model verification.
    diagnostic = list(seed['messages']); new_reads=[]
    for pid in confirmation['findings_to_confirm']:
        for _ in range(100):
            todo=missing_reads(artifacts,confirmation,pid,diagnostic)
            assert todo is not None
            if not todo: break
            for row in todo:
                a=row['arguments']
                if row['tool']=='read_review_location':
                    reader=read_structured_location if a.get('view')=='json' else read_location
                    result=reader(artifacts,pid,a['field_path'],a['offset'],a['max_characters'])
                else:
                    result={**a,'content':[c for c in artifacts.read_paper(pid,'claims') if c['claim_id'] in a['claim_ids']]}
                message=ToolMessage(content=json.dumps(result,ensure_ascii=False),artifact=result,
                    name=row['tool'],tool_call_id='diagnostic-only-'+str(len(new_reads)))
                diagnostic.append(message);new_reads.append(message)
        else:raise AssertionError('Read pagination did not converge')
    proposal=next(c['args']['review'] for c in original.tool_calls if c['name']=='submit_case_review')
    parsed=CaseReview.model_validate(proposal)
    validate_case_review(parsed,artifacts,diagnostic,paper_ids=list(confirmation['findings_to_confirm']),confirmation=confirmation)
    validate_finding_confirmation(parsed,confirmation,artifacts)
    assert papers == {pid:artifacts.read_paper(pid) for pid in papers}
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==v for p,v in hashes.items())
    save('actual-request-messages.private.json',model.seen)
    save('replayed-rejection.private.json',state)
    save('diagnostic-only-windows.private.json',new_reads)
    save('original-proposal.private.json',proposal)
    result={'provider_calls':0,'network_calls':0,'remaining_paid_calls':0,
        'original_record_still_rejected':True,'precise_missing_reads':latest.content,
        'bounded_reads_satisfy_structural_gate':True,'required_additional_reads':len(new_reads),
        'bounded_text_characters':sum(len(m.artifact.get('text','')) for m in new_reads),
        'countdown_removed_from_actual_native_request':True,'full_read_prompt_removed':True,
        'successful_receipts_preserved':len(original_receipts),'all_papers_preserved':len(papers),
        'original_hashes':hashes,'original_proposal_unmodified':True,
        'accepted_live_review_created':False,'financial_quality_pass':False,
        'note':'Diagnostic-only reads must not be inserted into a model recovery checkpoint. The model has not read or confirmed them.'}
    save('result.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('original_hashes','precise_missing_reads')},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    async def offline():
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
