"""No-network replay of saved reviewer requests, preserving their research data.

Measures the changed content projection with historical system/tools held fixed;
it does not estimate provider tokens, accept the rejected review or run a model.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from langchain_core.messages import SystemMessage, messages_from_dict, ToolMessage
from pydantic import SecretStr, ValidationError
from sec_agent.agent_runtime.case_review_agent import ReviewHandoff
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.review_context import working_messages, history_page, handoff_page


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def size(value):
    return len(json.dumps(value, ensure_ascii=False))


def restored(state):
    result = deepcopy(state)
    result['messages'] = messages_from_dict([
        m if 'data' in m else {'type': m['type'], 'data': m} for m in state['messages']])
    return result


def expand_quotes(value):
    result = deepcopy(value)
    table = result.pop('citation_quote_table', None)
    if table is None:
        return result
    result.pop('quote_view_notice')
    claims = result['content']['claims'] if result['section'] == 'workpaper' else result['content']
    for claim in claims:
        if 'citation_quote_refs' not in claim:
            continue
        refs = claim.pop('citation_quote_refs')
        claim['citation_quotes'] = {}
        for source, ids in refs.items():
            scalar = isinstance(ids, str)
            if scalar:ids = [ids]
            assert all(table[i]['source_id'] == source for i in ids)
            claim['citation_quotes'][source] = [table[i]['quote'] for i in ids]
            if scalar:claim['citation_quotes'][source] = claim['citation_quotes'][source][0]
    return result


def run(run_dir, parent, output):
    paths = [parent, run_dir/'convergence-state.private.json', run_dir/'review-entry.private.json',
        run_dir/'confirmation-current-input.private.json', run_dir/'reviewer-last-observed-state.private.json']
    paths += sorted((run_dir/'requests').glob('*.private.json'))
    paths += sorted((run_dir/'request-states').glob('*.private.json'))
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    artifacts = current_task_artifacts(load(parent)).with_revisions(load(run_dir/'convergence-state.private.json')['revisions'])
    papers = load(run_dir/'confirmation-current-input.private.json')['papers']
    assert {pid:artifacts.read_paper(pid) for pid in papers} == papers
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    chat = ReasoningPreservingChatDeepSeek(model='deepseek-flash', api_key=SecretStr('offline'),
        max_retries=0, use_responses_api=False)
    confirmation = None
    for wire_path in sorted((run_dir/'requests').glob('*.private.json')):
        wire = load(wire_path)
        saved = load(run_dir/'request-states'/wire_path.name)['state']
        state = restored(saved)
        before = deepcopy(state)
        packet = next(json.loads(m['content']) for m in wire['messages']
            if m['role']=='user' and '"review_handoff_contract_v2"' in str(m['content']))
        confirmation = packet['revision_confirmation']
        projected = working_messages(state, artifacts, confirmation)
        assert state == before
        assert working_messages(state, artifacts, confirmation) == projected
        new_packet = next(json.loads(m.content) for m in projected if m.id=='review-working-state-v2')
        assert new_packet['question'] == packet['question']
        assert new_packet['current_full_paper_reads'] == packet['current_full_paper_reads']
        assert new_packet['revision_confirmation']['findings_to_confirm'] == confirmation['findings_to_confirm']
        assert new_packet['revision_confirmation']['author_responses'] == confirmation['author_responses']
        original_tools = {m.tool_call_id:m for m in state['messages'] if isinstance(m,ToolMessage)}
        quote_savings = {}
        for m in projected:
            if not isinstance(m,ToolMessage):continue
            original = original_tools[m.tool_call_id]
            if m.name=='read_research_artifact' and m.status=='success':
                assert expand_quotes(json.loads(m.content)) == json.loads(original.content)
                quote_savings[json.loads(original.content)['paper_id']] = len(original.content)-len(m.content)
            elif m.name=='read_research_source' or m.status=='error':
                assert m.content == original.content
            assert m.artifact == original.artifact
        sdk = chat._get_request_payload([SystemMessage(content=wire['messages'][0]['content']),*projected], tools=wire['tools'])
        after = {**wire, 'messages':sdk['messages']}
        assert [m['role'] for m in after['messages']] == [m['role'] for m in wire['messages']]
        for old, new in zip(wire['messages'], after['messages']):
            if old['role']=='assistant':
                assert old.get('tool_calls') == new.get('tool_calls')
                assert old.get('reasoning_content') == new.get('reasoning_content')
            if old['role']=='tool':assert old['tool_call_id']==new['tool_call_id']
        rows.append({'request':wire_path.name, 'before_characters':size(wire), 'after_characters':size(after),
            'packet_before':len(wire['messages'][1]['content']), 'packet_after':len(after['messages'][1]['content']),
            'per_paper_quote_savings':quote_savings, 'full_paper_reads':new_packet['current_full_paper_reads'],
            'original_message_sizes':[{'role':m['role'], 'content':len(m.get('content') or ''),
                'reasoning':len(m.get('reasoning_content') or '')} for m in wire['messages']]})
        (output/wire_path.name).write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf8')

    state = restored(load(run_dir/'reviewer-last-observed-state.private.json'))
    before = deepcopy(state)
    projected = working_messages(state, artifacts, confirmation)
    assert projected[-1].status == 'error' and projected[-1] == state['messages'][-1]
    proposal = next(c['args']['review'] for m in reversed(state['messages'])
        for c in getattr(m,'tool_calls',[]) if c['name']=='submit_case_review')
    try:
        ReviewHandoff.model_validate(proposal)
    except ValidationError as error:
        assert 'completion_must_match' in str(error)
    else:
        raise AssertionError('Replay must not reclassify or accept the rejected proposal')
    assert state == before
    # Every native tool receipt remains exactly readable, including errors.
    for i,m in enumerate(state['messages']):
        if not isinstance(m,ToolMessage):continue
        text=''; offset=0
        while True:
            page=history_page(state['messages'],index=i,offset=offset)
            text+=page['text']
            if page['next_offset'] is None:break
            offset=page['next_offset']
        assert json.loads(text)['content']==m.content
    for pid in confirmation['changes']:
        text=''; offset=0
        while True:
            page=handoff_page(artifacts,confirmation,section='revision_confirmation',paper_id=pid,offset=offset)
            text+=page['text']
            if page['next_offset'] is None:break
            offset=page['next_offset']
        assert json.loads(text)['changes']==confirmation['changes'][pid]
    assert hashes == {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result={'paid_calls':0,'network_disabled':True,'rows':rows,'unchanged_artifact_hashes':hashes,
        'papers_unchanged':len(papers),'rejected_proposal_still_rejected':True,
        'pending_proposal_and_error_preserved':True,'all_receipts_readback_exact':True,
        'limits':'Character projection with historical system/tools held fixed, not provider token or quality measurement.'}
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='unchanged_artifact_hashes'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('offline replay forbids network')):
        run(args.run_dir,args.parent,args.output)
