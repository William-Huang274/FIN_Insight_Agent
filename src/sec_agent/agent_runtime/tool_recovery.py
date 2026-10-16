"""Explicit host recheck of a failed local calculation, not a paid retry policy.

Historical tool messages remain immutable. A separate, source-bound execution
receipt states what now works; a successful result is restored like other CALCs.
"""
from copy import deepcopy
import json
from time import perf_counter

from sec_agent.agent_runtime.research_graph_contracts import RuntimeReceipt, canonical_sha256
from sec_agent.research_foundation.source_bound_calculator import (
    ObservedSourceRegistry, SourceBoundCalculation, calculate_from_sources,
)


def recheck_failed_calculation(state, tool_call_id):
    """Run the exact saved calculation once against the current saved sources.

    Host-only, explicitly invoked after repair. No model, network, source read,
    quota extension, manuscript edit or historical receipt replacement occurs.
    The caller persists the returned state before resuming its normal workflow.
    """
    from sec_agent.agent_runtime.specialist_graph import SpecialistNotebook, SpecialistToolObservation

    notebook = SpecialistNotebook.model_validate_json(json.dumps(state['notebook']))
    for key in ('run_id', 'run_invocation_id', 'agent_id'):
        if state.get(key) != getattr(notebook, key):
            raise ValueError('recovery_notebook_identity_mismatch')
    if state.get('task', {}).get('task_id') != notebook.task_id:
        raise ValueError('recovery_notebook_task_mismatch')
    if state.get('pending_action') or state.get('final_submission'):
        raise ValueError('recovery_requires_settled_nonterminal_state')
    if not notebook.model_turn_records:
        raise ValueError('recovery_requires_current_failed_calculation')
    calls = notebook.model_turn_records[-1].action.model_dump(mode='json').get('tool_calls', [])
    call = next((c for c in calls if c.get('id') == tool_call_id), None)
    rows = [r for r in state.get('tool_results', []) if r.get('tool_call_id') == tool_call_id]
    if not call or call.get('name') != 'RequestCalculationAction' or len(rows) != 1 or rows[0].get('status') != 'error':
        raise ValueError('recovery_requires_current_failed_calculation')
    prior = rows[0]
    if 'source_id_not_observed_in_this_tool_session' not in prior['content']:
        raise ValueError('recovery_requires_source_registration_failure')
    request = SourceBoundCalculation.model_validate(call['args']['request'])
    registry = ObservedSourceRegistry(state['notebook']['observations'])
    source_snapshot = {op.source_id: registry.get(op.source_id) for op in request.operands.values() if op.source_id}
    binding = {k: getattr(notebook, k) for k in ('run_id', 'run_invocation_id', 'agent_id', 'task_id')}
    binding.update(tool_call_id=tool_call_id, request_digest=canonical_sha256(call['args']['request']),
                   prior_receipt_digest=canonical_sha256(prior), sources_digest=canonical_sha256(source_snapshot))
    check_id = canonical_sha256(binding)
    checks = (state.get('task_context') or {}).get('tool_recovery_checks', [])
    if any(c.get('check_id') == check_id for c in checks):
        return deepcopy(state)  # Already executed for these exact sources.
    start = perf_counter()
    try:
        result = calculate_from_sources(request, lambda key: registry.get(key) or {})
        outcome = {'status': 'success', 'result': result}
    except ValueError as exc:
        outcome = {'status': 'failure', 'error': str(exc)}
    receipt = RuntimeReceipt(receipt_id='local-calculation-recheck:' + check_id,
        kind='tool', actor='finance_tool', status=outcome['status'],
        request_digest=binding['request_digest'], output_digest=canonical_sha256(outcome),
        elapsed_ms=(perf_counter() - start) * 1000).model_dump(mode='json')
    check = {'check_id': check_id, 'binding': binding, 'execution': 'local_source_bound_calculator',
             'scope': 'Exact saved request and restored source snapshot only; not global tool health or financial validation.',
             'outcome': outcome, 'runtime_receipt': receipt}
    restored = deepcopy(state)
    if restored.get('task_context') is None:
        restored['task_context'] = {}
    restored.setdefault('task_context', {}).setdefault('tool_recovery_checks', []).append(check)
    if outcome['status'] == 'success':
        payload = dict(schema_version='fin_ia_specialist_tool_observation_v1_0',
            action_attempt_id='host-calculation-recheck:' + check_id, kind='finance', provenance_kind='direct_tool',
            status='success', request_digest=binding['request_digest'], references=[{
                'ref_id': result['calculation_id'], 'artifact_digest': canonical_sha256(result),
                'authority_state': 'non_authoritative_metric', 'writer_citable': False, 'numeric_fact_authority': False}],
            content=[result], route_completions=[], failure=None, source_runtime_receipt=None)
        payload['runtime_receipt'] = {**receipt, 'receipt_id': receipt['receipt_id'] + ':observation',
                                      'output_digest': canonical_sha256(payload)}
        payload['observation_digest'] = canonical_sha256(payload)
        observation = SpecialistToolObservation.model_validate_json(json.dumps(payload)).model_dump(mode='json')
        restored['notebook']['observations'].append(observation)
        restored['notebook']['notebook_digest'] = canonical_sha256({k: v for k, v in restored['notebook'].items() if k != 'notebook_digest'})
        SpecialistNotebook.model_validate_json(json.dumps(restored['notebook']))
    return restored


def project_recovery_receipts(recent, current, calls):
    """Label an old failed reply alongside the latest real check, in view only."""
    from langchain_core.messages import ToolMessage

    checks = (current.get('task_context') or {}).get('tool_recovery_checks', [])
    for message in recent:
        if not isinstance(message, ToolMessage) or message.status != 'error':
            continue
        pair = calls.get(message.tool_call_id)
        if not pair:
            continue
        call = pair[1]
        matching = [c for c in checks if c['binding']['tool_call_id'] == message.tool_call_id
                    and c['binding'].get('request_fingerprint', c['binding'].get('request_digest'))
                    == canonical_sha256(call.get('args', {}).get('request'))]
        if not matching:
            continue
        body = json.loads(message.content)
        check = matching[-1]
        original = body.get('result')
        if not isinstance(original, dict) or 'historical_failure' in original:
            continue
        # ToolMessage.status remains error: the ORIGINAL call did fail.
        body['result'] = {'historical_failure': original, 'current_execution_check': {
            'check_id': check['check_id'], 'status': check['outcome']['status'],
            'receipt_at': '/current_context/task_context/tool_recovery_checks/' + str(checks.index(check)),
            'calculation_id': check['outcome'].get('result', {}).get('calculation_id'),
            'error': check['outcome'].get('error')}}
        message.content = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
