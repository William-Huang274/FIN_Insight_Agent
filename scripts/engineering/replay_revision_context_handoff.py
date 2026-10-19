"""Offline real-journal replay of accepted-paper to local-revision handoff.

No provider, scheduler, source network, proposal rewrite or new acceptance.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage, messages_from_dict

from sec_agent.agent_runtime.research_context_view import working_view, current_context, public_operation, material_ids
from sec_agent.agent_runtime.research_session import current_task_artifacts
from sec_agent.agent_runtime.revision_calculation_handoff import restore_revision_calculations
from sec_agent.agent_runtime.specialist_graph import _model_request, SpecialistNotebook
from sec_agent.agent_runtime.deepseek_structured_agents import _project_request
from sec_agent.research_foundation.source_bound_calculator import ObservedSourceRegistry


def load(p):
    return json.loads(p.read_text(encoding='utf8'))


def run(args):
    h, out = args.run_dir, args.output
    out.mkdir(parents=True, exist_ok=True)
    paths = [args.parent, h/'model-responses/001.private.json', h/'requests/001.private.json',
        h/'author-states/P08.private.json', h/'accepted-lead-decision.private.json', h/'convergence-state.private.json']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    event = load(h/'model-responses/001.private.json')
    journal = messages_from_dict([{'type': m['type'], 'data': m} for m in event['messages']])
    original = deepcopy(journal)
    old_wire = load(h/'requests/001.private.json')
    old_view = json.loads(next(m['content'] for m in old_wire['messages']
                              if m['role'] == 'user' and 'current_materials' in m['content']))
    assert 'user_revision_request' in old_view['current_context']['task_context']
    assert 'user_revision_request' not in event['semantic_input']['task_context']
    before = working_view(journal)
    view = json.loads(next(m.content for m in before if m.additional_kwargs.get('fin_research_working_view')))
    assert 'user_revision_request' not in view['current_context']['task_context']
    assert material_ids(view['current_materials']) == material_ids(old_view['current_materials'])
    assert view['current_materials'] == old_view['current_materials']
    assert current_context(journal)['task_context']['revision_feedback'] == event['semantic_input']['task_context']['revision_feedback']
    assert public_operation(journal, 'runtime:initial-context') == public_operation(original, 'runtime:initial-context')
    prior = next(row for row in view['operation_catalog'] if row['tool'] == 'PriorRevisionTaskContext')
    assert public_operation(journal, prior['tool_call_id'])['receipt']['result']['user_revision_request'] == old_view['current_context']['task_context']['user_revision_request']
    assert journal == original
    state = load(h/'author-states/P08.private.json')
    original_state = deepcopy(state)
    convergence = load(h/'convergence-state.private.json')
    artifacts = current_task_artifacts(load(args.parent)).with_revisions(convergence['revisions'])
    decision = load(h/'accepted-lead-decision.private.json')
    restored = restore_revision_calculations(state, decision, artifacts, 'P08')
    assert state == original_state
    assert restored['notebook']['observations'][:len(state['notebook']['observations'])] == state['notebook']['observations']
    for key in ('workpaper_draft', 'last_submission_attempt', 'final_submission', 'tool_results',
                'max_model_turns', 'max_tool_actions'):
        assert restored.get(key) == state.get(key)
    assert restore_revision_calculations(restored, decision, artifacts, 'P08') == restored
    # Reproduce normal native post-tool delivery, including every successful
    # original proposal/result and its exact call identity.
    raw = AIMessage.model_validate(event['raw_response'])
    journal.append(raw)
    notebook = SpecialistNotebook.model_validate_json(json.dumps(restored['notebook']))
    context = _model_request(state=restored, notebook=notebook, allow_workpaper_field_edits=True,
        working_state_enabled=True, authoring_enabled=True, remaining_model_requests=0)
    context = _project_request('specialist', context, specialist_mode='agentic_turn')
    context.pop('context_digest', None)
    context['task_context_snapshot'] = True
    context['progress'] = {**context['progress'], 'prior_actions': [], 'observations': []}
    context.pop('l0_context', None)
    context.pop('branch', None)
    results = restored['tool_results']
    assert len(results) == 6 and all(r['status'] == 'success' for r in results)
    assert [r['tool_call_id'] for r in results] == [c['id'] for c in raw.tool_calls]
    for i, r in enumerate(results):
        body = {'result': json.loads(r['content'])}
        if i == len(results)-1:
            body['current_context'] = context
        journal.append(ToolMessage(tool_call_id=r['tool_call_id'], name=r['name'],
            status=r['status'], content=json.dumps(body, ensure_ascii=False)))
    after = working_view(journal)
    after_view = json.loads(next(m.content for m in after if m.additional_kwargs.get('fin_research_working_view')))
    assert 'user_revision_request' not in after_view['current_context']['task_context']
    assert material_ids(old_view['current_materials']) <= material_ids(after_view['current_materials'])
    assert all(item in after_view['current_materials'] for item in old_view['current_materials'])
    for r in results:
        assert public_operation(journal, r['tool_call_id'])['receipt']['result'] == json.loads(r['content'])
    registry = ObservedSourceRegistry(restored['notebook']['observations'])
    rows = after_view['current_context']['task_context']['revision_calculation_handoff']['calculations']
    assert len(rows) == 2
    for row in rows:
        record = public_operation(journal, row['read']['arguments']['tool_call_id'])
        assert record['receipt']['result']['calculation'] == registry.get(row['calculation_id'])
        assert registry.get(row['calculation_id']) == next(s['calculation'] for s in
            decision['citations'][row['calculation_id']]['sources'] if s.get('calculation'))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest for p, digest in hashes.items())

    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
            default=lambda x: x.model_dump(mode='json')), encoding='utf8')
    save('first-request-view.private.json', before)
    save('post-read-view.private.json', after)
    save('recovery-state.private.json', restored)
    save('recovery-journal.private.json', journal)
    report = {'provider_calls': 0, 'network_calls': 0, 'original_hashes': hashes,
        'retired_request_absent_before_and_after_reads': True,
        'original_journal_and_proposal_unchanged': True, 'original_observations_preserved': len(state['notebook']['observations']),
        'initial_material_ids_preserved': sorted(material_ids(old_view['current_materials'])),
        'successful_tool_results_preserved': len(results), 'lead_calculations_reused': [r['calculation_id'] for r in rows],
        'full_material_bodies_preserved': True,
        'calculation_readbacks_and_registry_verified': True, 'candidate_unchanged': True,
        'first_view_characters_before': len(json.dumps(old_view, ensure_ascii=False)),
        'first_view_characters_after': len(json.dumps(view, ensure_ascii=False)),
        'budgets_unchanged': True, 'remaining_paid_calls': 0, 'scheduler_executed': False,
        'financial_quality_verified': False, 'P08_finalized': False}
    save('result.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in {'original_hashes','initial_material_ids_preserved'}}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline replay forbids network')):
        run(args)
