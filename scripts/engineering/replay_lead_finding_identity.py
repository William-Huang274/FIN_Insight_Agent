"""Replay an unchanged saved Lead decision through native tools without transport."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from replay_review_argument_recovery import load, restored, SavedResponse
from sec_agent.agent_runtime.lead_issue_decision import LeadIssueDecision
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_execution import ReviewExecutionControl


async def run(args):
    h, out = args.run_dir, args.output
    out.mkdir(parents=True, exist_ok=True)
    paths = [args.parent, *h.glob('*.json'), *h.glob('requests/*.json'),
        *h.glob('request-states/*.json'), *h.glob('model-responses/*.json'),
        *h.glob('actor-states/*.json'), *h.glob('audit/**/*.jsonl')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    seed = restored(load(h/f'request-states/{args.response:03d}.private.json')['state'])
    original = AIMessage.model_validate(load(h/f'model-responses/{args.response:03d}.private.json')['raw_response'])
    observed = restored(load(h/'actor-states/lead_decision.private.json'))
    assert len(original.tool_calls) == 1 and original.tool_calls[0]['name'] == 'submit_lead_issue_decision'
    proposal = original.tool_calls[0]['args']['decision']
    parsed = LeadIssueDecision.model_validate(proposal).model_dump(mode='json')
    convergence = load(h/'convergence-state.private.json')
    artifacts = current_task_artifacts(load(args.parent)).with_revisions(convergence['revisions'])
    papers = {p['paper_id']: artifacts.read_paper(p['paper_id']) for p in artifacts.catalog()['papers']}
    task = json.loads(next(m.content for m in seed['messages'] if m.type == 'human'))
    assert task['findings_to_handle'] == convergence['pending_feedback']
    model = SavedResponse(response=original)
    # No provider, reviewer or author can execute; just the original response and
    # the maintained native decision tool. Do not advance the scheduling graph.
    agent = build_case_output_agent(role='decision', model=model, tools=[], artifacts=artifacts,
        feedback=task['findings_to_handle'], limits={'model_calls': seed.get('run_model_call_count', 0)+1, 'tool_calls': 100})
    state = await agent.ainvoke(seed)
    assert model.replay_count == 1 and state.get('output')
    saved = state['output']
    resolutions = saved['finding_id_resolutions']
    expected = json.loads(json.dumps(parsed))
    for item in resolutions:
        index = int(item['field_path'].split('/')[2])
        assert expected['dispositions'][index]['finding_id'] == item['submitted_id']
        expected['dispositions'][index]['finding_id'] = item['resolved_id']
    assert {k: saved[k] for k in LeadIssueDecision.model_fields} == expected
    assert state['messages'][:len(seed['messages'])] == seed['messages']
    response = next(m for m in state['messages'][len(seed['messages']):] if isinstance(m, AIMessage))
    assert response.model_dump() == original.model_dump()
    receipt = next(m for m in state['messages'][len(seed['messages']):] if isinstance(m, ToolMessage))
    assert receipt.status == 'success'
    ReviewExecutionControl(stop_on_tool_error=True).before_dispatch(state)
    assert state.get('revisions') == observed.get('revisions')
    assert {pid: artifacts.read_paper(pid) for pid in papers} == papers
    successful = [m for m in seed['messages'] if isinstance(m, ToolMessage) and m.status == 'success']
    calculations = [m for m in successful if m.name == 'calculate_research_metric']
    for key in ('thread_model_call_count', 'run_model_call_count', 'thread_tool_call_count', 'run_tool_call_count'):
        if key in observed: state[key] = observed[key]
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())

    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
            default=lambda x: x.model_dump(mode='json')), encoding='utf8')
    save('replayed-state.private.json', state)
    save('accepted-decision.private.json', saved)
    summary = {'provider_calls': 0, 'network_calls': 0, 'original_hashes_unchanged': hashes,
        'original_proposal_unchanged': True, 'original_messages_unchanged': True,
        'successful_receipts_preserved': len(successful), 'calculations_preserved': len(calculations),
        'papers_unchanged': len(papers), 'complete_review_unchanged': True,
        'finding_id_resolutions': resolutions, 'decision_saved': True,
        'host_judgment_changes': False, 'scheduler_executed': False,
        'author_or_reviewer_rerun': False, 'research_quality_pass': False}
    save('result.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'original_hashes_unchanged'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--response', type=int, default=2)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    async def offline():
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
