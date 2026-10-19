"""Offline original Lead batch replay: numeric search, no research decisions."""
import argparse
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage
from langchain.tools import tool

from replay_review_argument_recovery import load, restored, SavedResponse
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_execution import ReviewExecutionControl


async def run(args):
    h, out = args.run_dir, args.output
    out.mkdir(parents=True, exist_ok=True)
    originals = [args.parent, *h.glob('*.json'), *h.glob('requests/*.json'),
        *h.glob('request-states/*.json'), *h.glob('model-responses/*.json'),
        *h.glob('actor-states/*.json'), *h.glob('audit/**/*.jsonl')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    seed = restored(load(h/'request-states/001.private.json')['state'])
    observed = restored(load(h/'actor-states/lead_decision.private.json'))
    original = AIMessage.model_validate(load(h/'model-responses/001.private.json')['raw_response'])
    papers = load(h/'confirmation-current-input.private.json')['papers']
    artifacts = current_task_artifacts(load(args.parent)).with_revisions(
        load(h/'convergence-state.private.json')['revisions'])
    assert {pid: artifacts.read_paper(pid) for pid in papers} == papers
    receipts = {m.tool_call_id: m for m in observed['messages'] if isinstance(m, ToolMessage)}
    method_call = next(c for c in original.tool_calls if c['name'] == 'get_research_method')
    assert method_call['args'] == {} and receipts[method_call['id']].status == 'success'

    @tool
    def get_research_method() -> ToolMessage:
        """Reuse the unchanged successful method-catalog receipt; no service call."""
        return deepcopy(receipts[method_call['id']])

    task = json.loads(next(m.content for m in seed['messages'] if m.type == 'human'))
    model = SavedResponse(response=original)
    agent = build_case_output_agent(role='decision', model=model, tools=[get_research_method],
        artifacts=artifacts, feedback=task['findings_to_handle'], limits={'model_calls': 1, 'tool_calls': 20})
    ids = {c['id'] for c in original.tool_calls}
    async for state in agent.astream(seed, stream_mode='values'):
        new = {m.tool_call_id: m for m in state['messages'] if isinstance(m, ToolMessage)}
        if ids <= new.keys():
            break
    else:
        raise AssertionError('Original batch did not finish')
    assert model.replay_count == 1
    assert next(m for m in state['messages'] if isinstance(m, AIMessage)).tool_calls == original.tool_calls
    successful = {i: m for i, m in receipts.items() if m.status == 'success'}
    assert len(successful) == 5
    for i, m in successful.items():
        assert new[i].model_dump(exclude={'id'}) == m.model_dump(exclude={'id'}), m.name
    state['messages'] = [successful.get(m.tool_call_id, m) if isinstance(m, ToolMessage) else m
        for m in state['messages']]
    search_call = next(c for c in original.tool_calls if c['name'] == 'search_research_sources')
    result = new[search_call['id']]
    assert result.status == 'success'
    navigation = json.loads(result.content)
    assert navigation['query'] == search_call['args']['query']
    assert navigation['query_interpretation']['fts_query'] == '"24,461"'
    assert 'selected_source' not in navigation
    for hit in navigation['matches']:
        window = artifacts.read_source(**hit['read_arguments'])
        item = artifacts.source_item(hit['source_id'])
        assert window['source_id'] == hit['source_id']
        if 'text' in window:
            assert window['text'] == artifacts._source_text(item)[window['offset']:window['offset']+2000]
    ReviewExecutionControl(stop_on_tool_error=True).before_dispatch(state)
    assert not state.get('output'), 'Navigation must not complete Lead disposition'
    assert state.get('revisions') == observed.get('revisions')
    for key in ('thread_model_call_count', 'run_model_call_count', 'thread_tool_call_count', 'run_tool_call_count'):
        if key in observed:
            state[key] = observed[key]
    assert {pid: artifacts.read_paper(pid) for pid in papers} == papers
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())

    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
            default=lambda x: x.model_dump(mode='json')), encoding='utf8')
    save('replayed-state.private.json', state)
    save('search-navigation.json', navigation)
    summary = {'provider_calls': 0, 'network_calls': 0, 'remaining_paid_calls': 0,
        'original_proposal_unchanged': True, 'original_hashes_unchanged': hashes,
        'successful_receipts_preserved': len(successful), 'papers_unchanged': len(papers),
        'complete_review_unchanged': True, 'search_status': result.status,
        'search_candidates': len(navigation['matches']), 'candidate_read_arguments_verified': True,
        'host_source_selection': False, 'host_judgment_changes': False,
        'lead_decision_submitted': False, 'research_quality_pass': False}
    save('result.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'original_hashes_unchanged'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    async def offline():
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline replay forbids network')):
            await run(args)
    asyncio.run(offline())
