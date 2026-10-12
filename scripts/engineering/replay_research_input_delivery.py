"""Offline SDK replay of current catalogs and real saved delegated source pages.

Network disabled. Requires local immutable request index, old SDK payloads and
the saved native state containing the four child artifacts. No model execution.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import socket
from unittest.mock import patch

from replay_source_context import digest, encoded, load_requests, messages
from replay_context_retirement import walk
from replay_research_working_view import wire_components
from sec_agent.agent_runtime.research_context_view import current_context, decode, public_operation


def run(baseline_path, old_dir, state_path, output):
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import (
        DeepSeekStructuredAgentAdapter, ReasoningPreservingChatDeepSeek,
        _NATIVE_SPECIALIST_TOOLS, _native_function_schema, specialist_tools_for_actions)
    from sec_agent.agent_runtime.research_working_state import UpdateResearchStateAction
    from sec_agent.agent_runtime.specialist_delegation import ReadDelegatedWorkAction, delegated_artifact_view
    from sec_agent.agent_runtime.model_context import project_tool_history, research_checkpoint_request
    from sec_agent.agent_runtime.source_result_view import source_result_view
    baseline = json.loads(baseline_path.read_text('utf-8'))
    records = load_requests([dict(request_file=b['file'], request_line=b['line'], call_id=b['call_id']) for b in baseline['basis']])
    state = json.loads(state_path.read_text('utf-8'))
    children = next(row['agent_state']['delegated_work'] for row in state['research_failed_workpapers']
                    if row.get('agent_state', {}).get('delegated_work'))
    saved_state_hash = digest(state)
    adapter = object.__new__(DeepSeekStructuredAgentAdapter)
    chat = ReasoningPreservingChatDeepSeek(model='deepseek-v4-flash', api_key=SecretStr('offline'),
        tool_context_policy='task_boundary', research_checkpoint_tokens=48000, max_retries=0, use_responses_api=False)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for basis in baseline['basis']:
        n = basis['round']; record = records[basis['call_id']]
        assert digest(record) == basis['record_digest']
        original = messages(record); saved = deepcopy(original)
        adapter._agentic_history = {record['actor']: original}
        current = current_context(original)
        native = specialist_tools_for_actions({**_NATIVE_SPECIALIST_TOOLS, 'UpdateResearchStateAction': UpdateResearchStateAction}, current['allowed_actions'])
        schemas = [_native_function_schema(t, runtime_context_binding=True) for t in native.values()]
        old = json.loads((old_dir/f'r{n}.payload.private.json').read_text('utf-8'))
        old_full_size = len(encoded(old))
        old['tools'] = [t for t in old['tools'] if t.get('name', t.get('function',{}).get('name')) in native]
        before = len(encoded(old))
        final = project_tool_history(original, policy='task_boundary')
        assert final == project_tool_history(final, policy='task_boundary') and original == saved
        v = next(decode(m.content) for m in final if m.additional_kwargs.get('fin_research_working_view'))
        for key in ('research_question', 'assignment', 'research_working_state', 'pending_working_state_update'):
            if key in current.get('task_context', {}):
                expected = current['task_context'][key]
                if key == 'research_working_state' and isinstance(expected, dict):
                    expected = {k: val for k,val in expected.items() if k != 'reference_issues'}
                assert v['current_context']['task_context'][key] == expected, key
        reads = []
        for _, row in walk(v['current_context']):
            args = row.get('arguments', {})
            if row.get('tool') == 'ReadResearchHistoryAction' and args.get('tool_call_id', '').startswith('runtime:context:'):
                cid = args['tool_call_id']
                result = adapter.read_public_operation(record['actor'], cid)
                assert result == public_operation(original, cid) and result is not None
                assert adapter.read_public_operation('unrelated-actor', cid) is None
                reads.append(cid)
            if row.get('columns', [])[-1:] == ['details_id']:
                for metric in row['rows']:
                    cid = metric[-1]
                    detail = adapter.read_public_operation(record['actor'], cid)
                    assert detail['receipt']['result']['metric_id'] == metric[0]
                    assert adapter.read_public_operation('unrelated-actor', cid) is None
                    reads.append(cid)
        prepared, _, _ = research_checkpoint_request(original, model=chat, native_tools=native,
            runtime_context_binding=True, schema=_native_function_schema, max_input_characters=2000000)
        payload = chat._get_request_payload(prepared, tools=schemas, tool_choice='auto')
        context_only_size = len(encoded(payload))
        fresh = deepcopy(original)
        last_ai = max(i for i,m in enumerate(original) if m.type == 'ai')
        handoffs=[]
        for call in original[last_ai].tool_calls:
            if call['name'] not in {'ReadDelegatedWorkAction'} or call['args'].get('section') != 'handoff':
                continue
            args=deepcopy(call['args']); args.setdefault('context_digest','0'*64)
            child=children[args['subtask_id']]['result']
            old_receipt=next(m for m in original if m.type=='tool' and m.tool_call_id==call['id'])
            old_body=decode(old_receipt.content)['result']
            page, _ = delegated_artifact_view(child, ReadDelegatedWorkAction.model_validate(args))
            assert page['version'] == old_body['version'], 'artifact version changed'
            first=deepcopy(page); pages=[]; refs=[]; rows=[]
            while True:
                pages.append(len(encoded(page)))
                refs.extend(r['source_id'] for r in page['source_materials'])
                rows.extend(r for o in page['source_observations'] for r in o['content'])
                if not page.get('next_read'):break
                next_args = {**page['next_read']['arguments'], 'action':'read_delegated_work',
                             'context_digest':'0'*64, 'reason_summary':'Offline page completeness check'}
                page,_=delegated_artifact_view(child, ReadDelegatedWorkAction.model_validate(next_args))
                assert len(pages)<=len(args['source_ids'])
            assert len(refs)==len(set(refs)) and set(refs)==set(args['source_ids'])
            expected_rows=[source_result_view(r) for o in old_body['source_observations'] for r in o['content']]
            assert all(r in expected_rows for r in rows), 'source row changed'
            # Selected page navigation and exact source rows, not only a success flag.
            for m in fresh:
                if m.type=='tool' and m.tool_call_id==call['id']:
                    b=decode(m.content);b['result']=first;m.content=json.dumps(b,ensure_ascii=False)
            handoffs.append({'call_id':call['id'],'subtask':args['subtask_id'],
                'before_characters':len(encoded(old_body)),'first_page_characters':pages[0],
                'all_pages_characters':sum(pages),'pages':len(pages),
                'requested_sources':len(args['source_ids']),'returned_sources':len(refs),
                'exact_source_rows':len(rows),'same_artifact_version':True})
        if handoffs:
            prepared,_,_=research_checkpoint_request(fresh,model=chat,native_tools=native,
                runtime_context_binding=True,schema=_native_function_schema,max_input_characters=2000000)
            payload=chat._get_request_payload(prepared,tools=schemas,tool_choice='auto')
        assert original==saved and digest(state)==saved_state_hash
        (output/f'r{n}.payload.private.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
        results.append({'round':n,'previous_report_all_tools_characters':old_full_size,
            'before_same_stage_menu_characters':before,'context_catalogs_only_characters':context_only_size,
            'after_first_delivery_characters':len(encoded(payload)),
            'tools_characters':len(encoded(payload['tools'])),'same_stage_tool_names':sorted(native),
            'exact_context_readbacks':len(reads),'handoffs':handoffs,
            'wire_components':wire_components(payload),'canonical_history_and_saved_artifacts_unchanged':True})
    return {'basis':baseline['basis'],'state_hash':saved_state_hash,'network_calls':0,'rounds':results,
        'limits':['Frozen historical decisions; no inference about future model choices or billing.',
                  'R15 first delivery is a counterfactual native-reader replay; all requested pages verified separately.',
                  'Prior all-tools menu measurement corrected; menu filtering was already active in production.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','baseline-payload-dir','saved-state','output-dir'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    def deny(*args,**kwargs):raise RuntimeError('Network forbidden in offline replay')
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),patch.object(socket,'create_connection',deny):
        result=run(a.baseline,a.baseline_payload_dir,a.saved_state,a.output_dir)
    (a.output_dir/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(encoded(result))


if __name__=='__main__': main()
