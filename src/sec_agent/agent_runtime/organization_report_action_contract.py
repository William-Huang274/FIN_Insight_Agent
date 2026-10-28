"""Version-bound human actions authorized by Java, executed by the native graph."""
from copy import deepcopy
from datetime import datetime
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .organization_native_contract import digest, validate_thread, SURFACE, on_demand
from .organization_continuation_contract import baseline_digest
from .report_session import ReviewAction
from .targeted_revision import RevisionTarget, report_digest, validate_revision_target


class ReportCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    previous_run_id: UUID
    checkpoint_id: UUID
    state_digest: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    report_version: int = Field(ge=1, strict=True)
    report_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    action: Literal['ask', 'revise']
    message: str = Field(min_length=1, max_length=16000)
    answer_mode: Literal['quick', 'deep']
    target: RevisionTarget | None = None

    @model_validator(mode='after')
    def consistent_action(self):
        if not self.message.strip() or (self.action == 'revise' and self.answer_mode != 'deep'):
            raise ValueError('organization_report_action_invalid')
        if self.target and (self.action != 'revise' or self.target.request_id != self.id
                or self.target.base_version != self.report_version or self.target.base_digest != self.report_digest
                or self.target.base_checkpoint != self.checkpoint_id):
            raise ValueError('organization_report_target_mismatch')
        return self


class RootCommand(BaseModel):
    """A new user turn, not an implicit report-stage transition."""
    model_config = ConfigDict(extra='forbid')
    id: UUID
    previous_run_id: UUID
    checkpoint_id: UUID
    state_digest: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    action: Literal['continue'] = 'continue'
    message: str = Field(min_length=1, max_length=16000)
    delivery_intent: Literal['answer', 'workpaper', 'report'] = 'answer'
    require_report_review: bool = Field(default=False, strict=True)

    @model_validator(mode='after')
    def nonempty(self):
        if not self.message.strip():
            raise ValueError('empty_root_message')
        if self.require_report_review and self.delivery_intent != 'report':
            raise ValueError('report_review_requires_report_delivery')
        return self


def review_interrupts(state):
    items = list(state.get('interrupts') or [])
    for task in state.get('tasks') or []:
        items.extend(task.get('interrupts') or [])
    return [i for i in items if isinstance(i, dict) and isinstance(i.get('value'), dict)
            and i['value'].get('kind') == 'dell_report_review']


def validate_action(grant):
    p = grant['report_action_request']
    identity = {'contract_version', 'command_id', 'execution_id', 'project_id', 'manifest_digest',
                'configuration_digest', 'prepare_operation_id', 'research_as_of'}
    command = RootCommand if on_demand(grant) else ReportCommand
    if (set(p) != identity | (set(command.model_fields) - {'id'})
            or p['contract_version'] != ('organization_root_action.v1' if on_demand(grant) else 'organization_report_action.v1')
            or p['command_id'] != grant['report_command_id']
            or any(p[k] != grant[k] for k in identity - {'contract_version', 'command_id', 'research_as_of'})):
        raise ValueError('organization_report_action_contract_mismatch')
    command.model_validate({'id': p['command_id'], **{k: v for k, v in p.items() if k not in identity}})
    UUID(grant['report_action_operation_id'])
    cutoff = datetime.fromisoformat(p['research_as_of'].replace('Z', '+00:00'))
    if (cutoff.tzinfo is None or cutoff.utcoffset() is None
            or cutoff.date().isoformat() != json.loads(grant['manifest_text'])['research_as_of']):
        raise ValueError('organization_report_action_cutoff_mismatch')


def action_context(grant):
    return {k: grant[k] for k in ('execution_id', 'project_id', 'configuration_digest',
                                 'report_command_id', 'report_action_operation_id', 'report_action_request_digest')}


def authorized_action(grant):
    p = grant['report_action_request']
    return ReviewAction.model_validate({k: p[k] for k in ('action', 'message', 'answer_mode', 'target')})


def validate_report(values, grant):
    p = grant['report_action_request']
    if (not values.get('report') or values.get('report_version') != p['report_version']
            or report_digest(values['report']) != p['report_digest'] or values.get('question') != grant['question']):
        raise ValueError('organization_report_baseline_mismatch')
    if p.get('target'):
        validate_revision_target(values, authorized_action(grant).target)


def validate_baseline(state, grant):
    p = grant['report_action_request']
    if on_demand(grant):
        values = state.get('values') or {}
        if (state.get('checkpoint', {}).get('checkpoint_id') != p['checkpoint_id']
                or baseline_digest(state) != p['state_digest'] or state.get('next')
                or values.get('question') != grant['question']
                or values.get('task_outcome', {}).get('run_id') != p['previous_run_id']):
            raise ValueError('organization_root_checkpoint_mismatch')
        return
    validate_report(state.get('values') or {}, grant)
    if (state.get('checkpoint', {}).get('checkpoint_id') != p['checkpoint_id']
            or baseline_digest(state) != p['state_digest'] or not review_interrupts(state)
            or tuple(state.get('next') or ()) != ('human_review',)):
        raise ValueError('organization_report_checkpoint_mismatch')


def check_resumed_action(values, actual, grant):
    """Check the real Command.resume before any branch, including accept/manual."""
    validate_report(values, grant)
    if actual.model_dump(mode='json', exclude_none=True) != authorized_action(grant).model_dump(mode='json', exclude_none=True):
        raise ValueError('organization_report_resumed_action_mismatch')


def action_request(thread, grant):
    validate_action(grant)
    if validate_thread(thread, grant)['configuration_digest'] != grant['configuration_digest']:
        raise ValueError('organization_report_configuration_mismatch')
    config = deepcopy(thread['metadata']['organization_run_configuration'])
    config['configurable'].update(finsight_research_as_of=grant['report_action_request']['research_as_of'],
        finsight_organization_report_action=action_context(grant),
        finsight_organization_start=None, finsight_organization_continuation=None)
    args = {'config': config, 'checkpoint_id': grant['report_action_request']['checkpoint_id']}
    if on_demand(grant):
        args['input'] = {'question': grant['question'], 'messages': [{'role': 'user', 'content': grant['report_action_request']['message']}]}
    else:
        args['command'] = {'resume': authorized_action(grant).model_dump(mode='json', exclude_none=True)}
    return {**args, 'metadata': {'surface': SURFACE, 'organization_report_action': action_context(grant),
                                'organization_dispatch_digest': digest(args)}}


def action_receipt(run, thread, grant):
    expected = action_request(thread, grant)
    if (run['thread_id'] != grant['execution_id'] or run['metadata'].get('surface') != SURFACE
            or run['metadata'].get('organization_report_action') != action_context(grant)
            or run['metadata'].get('organization_dispatch_digest') != expected['metadata']['organization_dispatch_digest']
            or run['run_id'] == grant['report_action_request']['previous_run_id']):
        raise ValueError('organization_report_run_mismatch')
    return {**action_context(grant), 'thread_id': grant['execution_id'],
            'run_id': str(UUID(run['run_id'])), 'status': run['status']}
