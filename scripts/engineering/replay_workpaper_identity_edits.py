"""Network-disabled replay of a saved revision request and mechanical edit.

Refreshes the maintained revision contract/tool/prompt only. Private sources,
financial judgments and provider reasoning are never promoted or regenerated.
"""
import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import SecretStr
from replay_source_context import messages, digest
from sec_agent.agent_runtime.deepseek_structured_agents import (
    ReasoningPreservingChatDeepSeek, _native_function_schema,
    _NATIVE_SPECIALIST_SYSTEM_PROMPT, _SPECIALIST_COMMON_SYSTEM_PROMPT,
)
from sec_agent.agent_runtime.research_context_view import decode, working_view, public_operation
from sec_agent.agent_runtime.specialist_graph import (
    ReviseWorkpaperAction, apply_workpaper_edits, workpaper_revision_contract, canonical_sha256,
)


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def run(args):
    old = json.loads(args.wire.read_text(encoding='utf8'))
    records = [json.loads(line) for line in args.audit.read_text(encoding='utf8').splitlines()]
    record, = [r for r in records if r.get('event') == 'request' and r.get('call_id') == args.call_id]
    original = messages(record); saved = deepcopy(original)
    projected_input = deepcopy(original)
    source = subprocess.check_output(['git', 'show', args.baseline_ref + ':src/sec_agent/agent_runtime/deepseek_structured_agents.py'], cwd=ROOT).decode('utf8')
    assignment, = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == '_NATIVE_SPECIALIST_SYSTEM_PROMPT' for t in node.targets)]
    old_suffix = ast.literal_eval(assignment.value.right)
    new_suffix = _NATIVE_SPECIALIST_SYSTEM_PROMPT[len(_SPECIALIST_COMMON_SYSTEM_PROMPT):]
    # Runtime removes context_digest instructions elsewhere in this suffix.
    # Replace just the changed revision instructions; preserve those bindings.
    if old_suffix != new_suffix:
        prefix = 0
        limit = min(len(old_suffix), len(new_suffix))
        while prefix < limit and old_suffix[prefix] == new_suffix[prefix]: prefix += 1
        suffix = 0
        while suffix < limit-prefix and old_suffix[-suffix-1] == new_suffix[-suffix-1]: suffix += 1
        old_fragment = old_suffix[prefix:len(old_suffix)-suffix]
        new_fragment = new_suffix[prefix:len(new_suffix)-suffix]
        assert old_fragment and projected_input[0].content.count(old_fragment) == 1
        projected_input[0].content = projected_input[0].content.replace(old_fragment, new_fragment)
    # Saved context is an immutable historical request; reassemble only its
    # revision interface in this replay, as _model_request does in production.
    refreshed = 0
    def refresh(value):
        nonlocal refreshed
        if isinstance(value, dict):
            if isinstance(value.get('submission_to_repair'), dict):
                value['submission_to_repair']['submission_contract'] = workpaper_revision_contract()
                refreshed += 1
            for child in value.values(): refresh(child)
        elif isinstance(value, list):
            for child in value: refresh(child)
    for msg in projected_input:
        if isinstance(msg, HumanMessage):
            body = decode(msg.content)
            if isinstance(body, dict):
                refresh(body); msg.content = encoded(body)
    assert refreshed
    reminders = [m for m in old['messages'][1:] if m['role'] == 'system']
    projected_input.extend(SystemMessage(content=m['content'], additional_kwargs={'fin_context_checkpoint_instruction': True}) for m in reminders)
    tools = deepcopy(old['tools'])
    tool, = [t for t in tools if t['function']['name'] == 'ReviseWorkpaperAction']
    old_tool_chars = len(encoded(tool))
    tool['function'] = _native_function_schema(ReviseWorkpaperAction, runtime_context_binding=True)
    assert '"old_value"' not in encoded(tool)
    chat = ReasoningPreservingChatDeepSeek(model=old['model'], api_key=SecretStr('offline'),
        tool_context_policy='task_boundary', max_retries=0, use_responses_api=False)
    sdk = chat._get_request_payload(projected_input, tools=tools, tool_choice='auto')
    wire = {**old, 'messages': sdk['messages'], 'tools': sdk['tools']}
    def view(w):
        return next(decode(m['content']) for m in w['messages'] if m['role']=='user' and 'current_materials' in decode(m['content']))
    before, after = view(old), view(wire)
    for key in ('current_materials', 'current_material_bindings', 'material_focus'):
        assert before[key] == after[key], key
    for key in ('execution_budget', 'allowed_actions'):
        assert before['current_context'][key] == after['current_context'][key], key
    for key in ('research_question', 'revision_feedback', 'revision_instruction'):
        assert before['current_context']['task_context'].get(key) == after['current_context']['task_context'].get(key), key
    candidate = before['current_context']['submission_to_repair']['candidate']
    assert candidate == after['current_context']['submission_to_repair']['candidate']
    for binding in after['current_material_bindings']:
        for ref in binding['references']:
            if ref.get('authority_state') == 'non_authoritative_metric':
                assert after['current_reference_usage'][ref['ref_id']]['field'] == 'fact_ids'
    reads = []
    for op in after['operation_catalog']:
        cid = op['tool_call_id']; result = public_operation(projected_input, cid)
        assert result == public_operation(original, cid) and result is not None
        reads.append({'tool_call_id': cid, 'digest': digest(result)})
    for read in after['current_context']['task_context']['research_background']['reads'].values():
        cid = read['arguments']['tool_call_id']
        assert public_operation(projected_input,cid) == public_operation(original,cid)
        reads.append({'tool_call_id':cid,'digest':digest(public_operation(original,cid))})
    assert working_view(working_view(projected_input)) == working_view(projected_input)
    assert original == saved
    # Synthetic mechanical changes on the real object; never save as a paper.
    claim = candidate['claims'][-1]
    changes = {key: (claim.get(key) or '') + ' [OFFLINE MECHANICAL PROBE]'
               for key in ('statement', 'authority_note', 'reasoning_summary')}
    edits = [{'op':'update_claim','claim_id':claim['claim_id'],'changes':changes}]
    envelope = dict(action='revise_workpaper', context_digest=candidate['context_digest'], reason_summary='Offline mechanical probe only.',
        base_submission_digest=canonical_sha256(candidate))
    action = ReviseWorkpaperAction.model_validate_json(encoded({**envelope,'edits':edits}))
    assembled = apply_workpaper_edits(candidate, action)
    expected = deepcopy(candidate['claims']); expected[-1].update(changes)
    assert assembled['claims'] == expected
    assert assembled['narrative_markdown'] == candidate['narrative_markdown']
    legacy = [{'op':'replace','path':f'/claims/{len(candidate["claims"])-1}/{key}',
               'old_value':claim.get(key),'new_value':value} for key,value in changes.items()]
    assert apply_workpaper_edits(candidate,ReviseWorkpaperAction.model_validate_json(encoded({**envelope,'edits':legacy}))) == assembled
    report = dict(paid_calls=0, network_disabled=True, call_id=args.call_id,
        original_record_digest=digest(record), original_wire_digest=digest(old),
        materials_count=len(after['current_materials']), materials_and_bindings_exact=True,
        candidate_and_active_feedback_exact=True, permissions_and_budget_exact=True,
        history_unchanged=True, idempotent=True, readbacks=reads,
        new_identity_and_legacy_edits_same_result=True, nonchanged_claim_fields_retained=True,
        before_sdk_characters=len(encoded(old)), after_sdk_characters=len(encoded(wire)),
        before_revision_tool_characters=old_tool_chars, after_revision_tool_characters=len(encoded(tool)),
        probe_old_value_edits_characters=len(encoded(legacy)), probe_identity_edits_characters=len(encoded(edits)),
        limits='Offline request and mechanical editing only. No model behavior, financial judgment or cost improvement established.')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'request.private.json').write_text(encoded(wire),encoding='utf8')
    (args.output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(encoded({k:v for k,v in report.items() if k!='readbacks'}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','wire','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--call-id',required=True); p.add_argument('--baseline-ref',required=True)
    args=p.parse_args()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline replay forbids network')):
        run(args)
