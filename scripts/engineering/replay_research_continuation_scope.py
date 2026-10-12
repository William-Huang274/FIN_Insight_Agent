"""Offline planning probe on saved papers/tasks; never a model quality replay."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket

from langgraph.checkpoint.memory import InMemorySaver
from sec_agent.agent_runtime.lead_research_graph import build_lead_research_graph
from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticInput


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saved-input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def forbidden(*a, **k):
        raise AssertionError('offline_scope_probe_forbids_network_and_workers')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = forbidden
    raw = args.saved_input.read_bytes()
    saved = json.loads(raw)
    seeds = {p['task']['task_id']: p for p in saved['completed_workpapers']}
    pending = saved['unfinished_tasks']
    first = next(iter(seeds.values()))
    value = SpecialistAgenticInput.model_validate_json(json.dumps({
        k: first[k] for k in SpecialistAgenticInput.model_fields if k in first}))
    question = (first.get('task_context') or {}).get('research_question') or first['task']['objective']
    catalog = json.loads(Path('configs/research/cases/growth_quality.json').read_text(encoding='utf-8'))['branch_topics']
    capability = next(r['capability_ref'] for r in first['l0_context']['capability_summaries'] if r.get('capability_ref'))
    probe = {'task_id': 'offline:scope-probe', 'owner_role': 'offline_probe',
        'objective': 'Offline synthetic scope probe, not an actual research assignment or conclusion.',
        'coverage_obligation_ids': [first['task']['branch_id']], 'dependency_ids': [first['task']['task_id']],
        'success_criteria': ['Verify preserved authority and dependency binding without running research.'],
        'requested_capability_refs': [capability], 'expected_output_kinds': ['branch_notebook', 'claim_ledger'],
        'materiality': 'medium', 'status': 'ready'}
    rows = []
    for bounded in (False, True):
        requests = []
        def turn(request):
            requests.append(deepcopy(request))
            return {'action': {'action': 'native_tool_batch', 'context_digest': request['context_digest'],
                'tool_calls': [{'id': 'offline-probe', 'name': 'DelegateResearchTasksAction',
                    'args': {'context_digest': request['context_digest'], 'reason_summary': 'Offline authorization probe only.',
                             'tasks': [probe]}}]}}
        graph = build_lead_research_graph(expected_input=value, research_question=question,
            branch_catalog=catalog, allowed_branch_ids=tuple(b['branch_id'] for b in catalog),
            seed_workpapers=seeds, recovery_tasks=pending, model_turn=turn, run_child=forbidden,
            max_tasks=24, unfinished_only=bounded, require_all_branches=False).compile(
                checkpointer=InMemorySaver(), interrupt_after=['bind_case', 'lead_tools'])
        config = {'configurable': {'thread_id': 'offline-scope-' + str(bounded)}}
        graph.invoke(value.model_dump(mode='json'), config)
        # Inspect the planning boundary before dispatching original pending tasks.
        # This is an explicit counterfactual probe, not the historical trajectory.
        graph.update_state(config, {'phase': 'lead_observing'}, as_node='bind_case')
        result = graph.invoke(None, config)
        assert len(requests) == 1
        tasks = result['tasks']
        assert [t['task_id'] for t in tasks[:len(pending)]] == [t['task_id'] for t in pending]
        assert len(tasks) == len(pending) + (0 if bounded else 1)
        if not bounded:
            assert tasks[-1]['dependency_ids'] == probe['dependency_ids']
        assert ('DelegateResearchTasksAction' in requests[0]['allowed_planning_tools']) is not bounded
        rows.append({'explicit_original_plan': bounded, 'submitted_papers_retained': len(seeds),
            'original_pending_tasks_retained': len(pending), 'synthetic_new_task_accepted': not bounded,
            'error': 'continuation_cannot_create_new_tasks_request_owner_scope_change' if bounded else None,
            'workers_executed': 0, 'model_calls': 0})
    assert args.saved_input.read_bytes() == raw
    assert saved == json.loads(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'saved_input': str(args.saved_input), 'sha256': hashlib.sha256(raw).hexdigest(),
        'kind': 'counterfactual_offline_planning_probe_not_model_output', 'source_file_unchanged': True,
        'cases': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
