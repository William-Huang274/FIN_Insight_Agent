"""Fixed child inputs and versioned readbacks; no queue or second task store.

Java owns command admission, the native thread owns progress, and working memory
owns notes. Model arguments contain research choices, never runtime credentials.
"""
from copy import deepcopy
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .research_graph_contracts import canonical_sha256
from .specialist_delegation import ResearchSubtask


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MaterialReference(Contract):
    source_id: str = Field(min_length=1, max_length=400)
    tool_call_id: str = Field(min_length=1, max_length=400)


class NoteReference(Contract):
    id: str = Field(min_length=1, max_length=160)
    version: int = Field(ge=1, strict=True)


class DelegateTask(Contract):
    assignment: ResearchSubtask
    delivery_intent: Literal['answer', 'workpaper']
    method_ids: list[str] = Field(default_factory=list, max_length=7)
    materials: list[MaterialReference] = Field(default_factory=list, max_length=64)
    working_notes: list[NoteReference] = Field(default_factory=list, max_length=16)

    @model_validator(mode='after')
    def unique_selections(self):
        if self.assignment.professional is not None:
            raise ValueError('professional_executor_not_qualified_for_this_action')
        if len(set(self.method_ids)) != len(self.method_ids):
            raise ValueError('duplicate_delegated_method')
        for rows in (self.materials, self.working_notes):
            if len({canonical_sha256(r.model_dump()) for r in rows}) != len(rows):
                raise ValueError('duplicate_delegated_reference')
        if len({r.source_id for r in self.materials}) != len(self.materials):
            raise ValueError('source_identity_requires_one_selected_receipt')
        return self


class TaskCommand(Contract):
    """Host-filled command envelope, independently admitted for each operation."""
    command_id: UUID
    execution_id: UUID
    parent_thread_id: UUID
    parent_run_id: UUID
    parent_checkpoint_id: UUID
    child_thread_id: UUID
    action: Literal['create', 'continue', 'cancel']
    root_budget_id: str = Field(min_length=1, max_length=160)
    manifest_digest: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    task: DelegateTask | None = None
    checkpoint_id: UUID | None = None
    message: str = Field(default='', max_length=16000)

    @model_validator(mode='after')
    def operation_shape(self):
        if self.parent_thread_id != self.execution_id or self.child_thread_id == self.execution_id:
            raise ValueError('only_root_may_delegate')
        if self.action == 'create':
            if self.task is None or self.checkpoint_id is not None or self.message:
                raise ValueError('create_requires_only_fixed_task')
        elif self.task is not None or self.checkpoint_id is None:
            raise ValueError('existing_task_requires_checkpoint_not_new_assignment')
        if self.action == 'continue' and not self.message.strip():
            raise ValueError('continuation_requires_current_request')
        if self.action == 'cancel' and self.message:
            raise ValueError('cancel_does_not_replace_task')
        return self


def freeze_input(command, parent_state, *, allowed_methods, note_reader, runtime_configuration):
    """Validate selections against the exact checkpoint, without copying history.

    Full source receipts stay at their original checkpoint. The child's readers
    recheck authority and hydrate the selected originals into its native state.
    """
    from .conversation_handoff import observed_sources
    command = TaskCommand.model_validate(command)
    if command.action != 'create':
        raise ValueError('only_create_freezes_input')
    if parent_state.get('checkpoint', {}).get('checkpoint_id') != str(command.parent_checkpoint_id):
        raise ValueError('delegation_parent_checkpoint_changed')
    task = command.task
    if not set(task.method_ids) <= set(allowed_methods):
        raise ValueError('delegated_method_not_available')
    messages = parent_state.get('values', {}).get('messages', [])
    for ref in task.materials:
        candidates = [m for m in messages if m.get('type') == 'tool'
                      and m.get('tool_call_id') == ref.tool_call_id and m.get('status') != 'error']
        if len(candidates) != 1 or ref.source_id not in observed_sources({'values': {'messages': candidates}}):
            raise ValueError('delegated_material_not_observed_in_selected_receipt')
    for ref in task.working_notes:
        note = note_reader(ref.id, ref.version)
        if not note.get('found') or note['id'] != ref.id or note['version'] != ref.version:
            raise ValueError('delegated_note_version_mismatch')
    from sec_agent.research_foundation.research_methods import get_research_method
    body = {'task': task.model_dump(mode='json'),
            'source_thread': str(command.parent_thread_id),
            'checkpoint_id': str(command.parent_checkpoint_id),
            'root_budget_id': command.root_budget_id,
            'manifest_digest': command.manifest_digest,
            # Parent-selected methods are starting guidance, not a ban on
            # choosing another host-approved method as the question evolves.
            'method_digests': {key: canonical_sha256(get_research_method(key)) for key in sorted(set(allowed_methods))},
            'runtime_configuration': deepcopy(runtime_configuration)}
    return {**body, 'input_digest': canonical_sha256(body)}


def validate_fixed_input(body):
    value = deepcopy(body)
    digest = value.pop('input_digest')
    if canonical_sha256(value) != digest:
        raise ValueError('delegated_input_digest_mismatch')
    DelegateTask.model_validate(value['task'])
    from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    config = value['runtime_configuration']
    DeepSeekModelProfile.model_validate(config['profile'])
    TokenBudgetBasis.model_validate_json(json.dumps(config['budget']))
    if set(config) - {'profile', 'budget', 'limits', 'summary', 'context_editing'}:
        raise ValueError('delegated_configuration_not_model_policy')
    limits = config['limits']
    if (set(limits) != {'model_calls', 'tool_calls'} or any(type(v) is not int for v in limits.values())
            or not 1 <= limits['model_calls'] <= 32 or not 1 <= limits['tool_calls'] <= 64):
        raise ValueError('delegated_configuration_limits_invalid')
    if not set(value['task']['method_ids']) <= set(value['method_digests']):
        raise ValueError('delegated_method_versions_missing')
    if 'summary' not in config:
        raise ValueError('delegated_summary_policy_missing')
    DeepSeekModelProfile.model_validate(config['summary']['profile'])
    TokenBudgetBasis.model_validate_json(json.dumps(config['summary']['budget']))
    return value


def child_task_context(fixed_input):
    """One current assignment, not the parent's past plans or acceptance prompts."""
    value = validate_fixed_input(fixed_input)
    task = value['task']
    return {'assignment': deepcopy(task['assignment']),
            'delivery_intent': task['delivery_intent'],
            'method_ids': list(task['method_ids']),
            'materials': deepcopy(task['materials']),
            'working_notes': deepcopy(task['working_notes']),
            'input_digest': fixed_input['input_digest'],
            'history': {'source_thread': value['source_thread'], 'checkpoint_id': value['checkpoint_id']}}
