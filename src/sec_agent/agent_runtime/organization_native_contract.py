"""Canonical first-run contract shared by the BFF and native execution boundary."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from uuid import UUID

from .research_session import ResearchRequest
from .studio_configuration import StudioConfiguration
from .execution_options import ExecutionOptions


SURFACE = 'organization_research_workbench'


def on_demand(grant):
    """The immutable preparation selects the runtime, never a browser/run flag."""
    version = grant['prepare_request']['contract_version']
    if version not in {'organization_native_preparation.v1', 'organization_native_preparation.v2'}:
        raise ValueError('organization_preparation_contract_unsupported')
    return version == 'organization_native_preparation.v2'


def context(grant):
    return {key: grant[key] for key in ('execution_id', 'thread_id', 'project_id', 'draft_id', 'organization_id',
                                       'manifest_digest', 'prepare_operation_id', 'prepare_request_digest')}


def validate_thread(thread, grant):
    try:
        meta = thread['metadata']
        config = meta['organization_run_configuration']
        values = config['configurable']
        if (thread['thread_id'] != grant['execution_id'] or meta['surface'] != SURFACE
                or meta['owner_id'] != 'organization:' + grant['organization_id']
                or meta['graph'] != 'research_session' or meta['organization_prepared'] is not True
                or meta['native_execution_enabled'] is not False or meta['organization_execution'] != context(grant)
                or meta['title'] != grant['title'] or meta['pending_question'] != grant['question']
                or set(config) != {'configurable'} or set(values) != {'finsight_execution', 'finsight_studio', 'finsight_research_as_of', 'finsight_organization_execution'}
                or values['finsight_execution'] != grant['prepare_request']['execution']
                or values['finsight_organization_execution'] != context(grant)
                or meta['research_as_of'] != json.loads(grant['manifest_text'])['research_as_of']
                or values['finsight_research_as_of'] != meta['research_as_of']
                or meta['configuration_digest'] != digest(config)
                or any(key in meta for key in ('asset_context', 'business_intake', 'studio_assistant_id', 'project_materials_status'))):
            raise ValueError('native_binding')
        StudioConfiguration.model_validate(values['finsight_studio'])
        ExecutionOptions.model_validate(values['finsight_execution'])
        return {**context(grant), 'status': 'draft', 'configuration_digest': meta['configuration_digest'],
                'native_execution_enabled': False}
    except (ValueError, KeyError, TypeError):
        raise ValueError('organization_prepared_thread_mismatch') from None


def digest(value):
    return 'sha256:' + sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_start(grant):
    payload = grant['start_request']
    if (set(payload) != {'contract_version', 'execution_id', 'project_id', 'manifest_digest', 'configuration_digest',
                         'prepare_operation_id', 'research_as_of', 'stage'}
            or payload['contract_version'] != ('organization_native_start.v2' if on_demand(grant) else 'organization_native_start.v1')
            or payload['stage'] != ('work_session' if on_demand(grant) else 'orientation')
            or any(payload[key] != grant[key] for key in ('execution_id','project_id','manifest_digest','configuration_digest','prepare_operation_id'))):
        raise ValueError('organization_start_contract_mismatch')
    UUID(grant['start_operation_id'])
    cutoff = datetime.fromisoformat(payload['research_as_of'].replace('Z', '+00:00'))
    if cutoff.tzinfo is None or cutoff.utcoffset() is None or cutoff.date().isoformat() != json.loads(grant['manifest_text'])['research_as_of']:
        raise ValueError('organization_start_cutoff_mismatch')


def start_context(grant):
    return {key: grant[key] for key in ('execution_id', 'project_id', 'configuration_digest', 'start_operation_id', 'start_request_digest')}


def run_request(thread, grant):
    validate_start(grant)
    if digest(thread['metadata']['organization_run_configuration']) != grant['configuration_digest']:
        raise ValueError('organization_start_configuration_mismatch')
    config = deepcopy(thread['metadata']['organization_run_configuration'])
    config['configurable']['finsight_research_as_of'] = grant['start_request']['research_as_of']
    config['configurable']['finsight_organization_start'] = start_context(grant)
    initial = ({'question': grant['question'], 'messages': [{'role': 'user', 'content': grant['question']}]}
               if on_demand(grant) else ResearchRequest(question=grant['question'], research_stage='orientation').model_dump(mode='json'))
    arguments = dict(config=config, input=initial)
    return {**arguments, 'metadata':{'surface':'organization_research_workbench', 'organization_start':start_context(grant),
                                    'organization_dispatch_digest':digest(arguments)}}


def run_receipt(run, thread, grant):
    expected = run_request(thread, grant)
    if (run['thread_id'] != grant['execution_id'] or run['metadata'].get('organization_start') != start_context(grant)
            or run['metadata'].get('surface') != 'organization_research_workbench'
            or run['metadata'].get('organization_dispatch_digest') != expected['metadata']['organization_dispatch_digest']):
        raise ValueError('organization_native_run_mismatch')
    # Official Run receipts expose metadata, not kwargs/config. Actual config and
    # input are checked inside the native factory before any research/model call.
    return {**start_context(grant), 'thread_id':grant['execution_id'], 'run_id':str(UUID(run['run_id'])),
            'status':run['status']}
