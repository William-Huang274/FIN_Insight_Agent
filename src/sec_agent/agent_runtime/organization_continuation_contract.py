"""Frozen orientation-to-research command shared by transport and native admission."""
from copy import deepcopy
from datetime import datetime
import json
from uuid import UUID

from .organization_native_contract import digest, validate_thread, SURFACE
from .research_session import ResearchRequest


def validate_continuation(grant):
    payload = grant['continuation_request']
    fields = {'contract_version', 'execution_id', 'project_id', 'manifest_digest', 'configuration_digest',
              'prepare_operation_id', 'research_as_of', 'action', 'previous_run_id', 'checkpoint_id', 'state_digest'}
    if (set(payload) != fields or payload['contract_version'] != 'organization_native_continuation.v1'
            or payload['action'] != 'begin_research'
            or any(payload[key] != grant[key] for key in ('execution_id', 'project_id', 'manifest_digest',
                                                        'configuration_digest', 'prepare_operation_id'))):
        raise ValueError('organization_continuation_contract_mismatch')
    for value in (grant['continuation_operation_id'], payload['previous_run_id'], payload['checkpoint_id']):
        UUID(value)
    cutoff = datetime.fromisoformat(payload['research_as_of'].replace('Z', '+00:00'))
    if (cutoff.tzinfo is None or cutoff.utcoffset() is None
            or cutoff.date().isoformat() != json.loads(grant['manifest_text'])['research_as_of']):
        raise ValueError('organization_continuation_cutoff_mismatch')


def continuation_context(grant):
    return {key: grant[key] for key in ('execution_id', 'project_id', 'configuration_digest',
                                      'continuation_operation_id', 'continuation_request_digest')}


def baseline_digest(state):
    # Values AND pending tasks/interrupts are frozen; server timestamps are not.
    return digest({key: state.get(key) for key in ('values', 'next', 'tasks', 'checkpoint')})


def validate_baseline(state, grant):
    p = grant['continuation_request']
    v = state.get('values') or {}
    if (state.get('checkpoint', {}).get('checkpoint_id') != p['checkpoint_id']
            or baseline_digest(state) != p['state_digest'] or state.get('next')
            or v.get('phase') != 'research_orientation_submitted'
            or v.get('research_stage') != 'orientation' or v.get('orientation_run_id') != p['previous_run_id']
            or v.get('question') != grant['question'] or not v.get('research_orientation')
            or v.get('case_papers') or v.get('research_tasks') or v.get('report')):
        raise ValueError('organization_continuation_baseline_mismatch')


def continuation_request(thread, grant):
    validate_continuation(grant)
    if validate_thread(thread, grant)['configuration_digest'] != grant['configuration_digest']:
        raise ValueError('organization_continuation_configuration_mismatch')
    config = deepcopy(thread['metadata']['organization_run_configuration'])
    config['configurable']['finsight_research_as_of'] = grant['continuation_request']['research_as_of']
    config['configurable']['finsight_organization_continuation'] = continuation_context(grant)
    # Agent Server merges checkpoint configuration into subsequent runs. Clear
    # the preceding command explicitly; absence would inherit its authority.
    config['configurable']['finsight_organization_start'] = None
    args = {'config': config, 'input': ResearchRequest(question=grant['question'], research_stage='full').model_dump(mode='json'),
            'checkpoint_id': grant['continuation_request']['checkpoint_id']}
    return {**args, 'metadata': {'surface': SURFACE, 'organization_continuation': continuation_context(grant),
                                'organization_dispatch_digest': digest(args)}}


def continuation_receipt(run, thread, grant):
    expected = continuation_request(thread, grant)
    if (run['thread_id'] != grant['execution_id'] or run['metadata'].get('surface') != SURFACE
            or run['metadata'].get('organization_continuation') != continuation_context(grant)
            or run['metadata'].get('organization_dispatch_digest') != expected['metadata']['organization_dispatch_digest']
            or run['run_id'] == grant['continuation_request']['previous_run_id']):
        raise ValueError('organization_continuation_run_mismatch')
    return {**continuation_context(grant), 'thread_id': grant['execution_id'],
            'run_id': str(UUID(run['run_id'])), 'status': run['status']}
