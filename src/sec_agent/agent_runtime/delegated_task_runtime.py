"""Thin child-task adapter over admitted commands and the native Agent Server.

No polling loop, local task table, retries, or inline model execution. A lost
create response is reconciled by operation metadata, never by creating again.
"""
from copy import deepcopy
from uuid import UUID

from .delegated_task_contract import TaskCommand, validate_fixed_input
from .research_graph_contracts import canonical_sha256


SURFACE = 'finsight_delegated_task'


def command_receipt(value):
    """A model sees progress and readback identities, not the frozen host envelope."""
    return {key: deepcopy(value[key]) for key in ('command_id', 'execution_id', 'operation_id',
        'child_thread_id', 'thread_id', 'run_id', 'status', 'cancel_requested') if key in value}


def dispatch_arguments(command):
    command = TaskCommand.model_validate(command)
    args = {'config': {'configurable': {'delegated_command_id': str(command.command_id),
                'delegated_execution_id': str(command.execution_id)}},
            'input': {'messages': [{'role': 'user', 'content': command.message
                if command.action == 'continue' else command.task.assignment.objective}]}}
    if command.checkpoint_id:
        args['checkpoint_id'] = str(command.checkpoint_id)
    return args


class DelegatedTaskRuntime:
    def __init__(self, *, sdk, authority):
        self.sdk, self.authority = sdk, authority

    async def _thread(self, grant):
        thread = await self.sdk.threads.get(grant['child_thread_id'])
        metadata = thread.get('metadata', {})
        if (metadata.get('surface') != SURFACE
                or metadata.get('owner_id') != grant['owner_id']
                or metadata.get('delegated_task') != grant['binding']):
            raise ValueError('delegated_thread_binding_mismatch')
        return thread

    async def execute(self, command, *, fixed_input=None):
        command = TaskCommand.model_validate(command)
        if command.action == 'create':
            validate_fixed_input(fixed_input)
        # The durable claim is acquired before any native side effect. Duplicate
        # and unknown commands return a read-only view, even after a restart.
        grant = await self.authority.claim(command.model_dump(mode='json'), fixed_input)
        if not grant['dispatch_allowed']:
            return await self.reconcile(grant)
        tid = grant['child_thread_id']
        if command.action == 'create':
            await self.sdk.threads.create(thread_id=tid, if_exists='do_nothing',
                metadata={'surface': SURFACE, 'owner_id': grant['owner_id'],
                          'delegated_task': grant['binding']})
        await self._thread(grant)
        if command.action == 'continue':
            state = await self.sdk.threads.get_state(tid)
            if state.get('checkpoint', {}).get('checkpoint_id') != str(command.checkpoint_id):
                raise ValueError('delegated_task_checkpoint_changed')
        await self.authority.check(grant)
        if command.action == 'cancel':
            # Cancel is durable first; provider/source guards will reject the
            # task even if the cancel transport is interrupted.
            for run in await self._runs(tid):
                if run['status'] in {'pending', 'running'}:
                    await self.sdk.runs.cancel(tid, run['run_id'], action='interrupt')
            return command_receipt(await self.authority.accept(grant, {'status': 'cancelled', 'thread_id': tid}))
        active = [r for r in await self._runs(tid) if r['status'] in {'pending', 'running'}]
        if active:
            raise ValueError('delegated_task_already_running')
        args = dispatch_arguments(command)
        metadata = {'surface': SURFACE, 'delegated_operation_id': grant['operation_id'],
                    'delegated_command_id': grant['command_id'], 'dispatch_digest': canonical_sha256(args)}
        run = await self.sdk.runs.create(tid, 'delegated_task', **args, metadata=metadata,
                                        multitask_strategy='reject')
        if run['thread_id'] != tid or any(run.get('metadata', {}).get(k) != v for k, v in metadata.items()):
            raise ValueError('delegated_dispatch_receipt_mismatch')
        await self.authority.check(grant)
        return command_receipt(await self.authority.accept(grant, {'thread_id': tid, 'run_id': run['run_id'],
                                                 'status': run['status']}))

    async def _runs(self, tid):
        rows, offset = [], 0
        while True:
            page = await self.sdk.runs.list(tid, limit=100, offset=offset)
            rows.extend(page)
            if len(page) < 100:
                return rows
            offset += len(page)

    async def reconcile(self, grant):
        await self.authority.check(grant)
        if grant['action'] == 'cancel':
            return {'command_id': grant['command_id'], 'status': 'cancel_requested',
                    'dispatch_repeated': False}
        # A thread may not have been created if dispatch was interrupted early.
        # The authority keeps the claim unknown; absence is not retry permission.
        try:
            await self._thread(grant)
        except Exception as exc:
            if getattr(getattr(exc, 'response', None), 'status_code', None) != 404:
                raise
            return {'command_id': grant['command_id'], 'status': 'unknown', 'dispatch_repeated': False}
        matches = [r for r in await self._runs(grant['child_thread_id'])
                   if r.get('metadata', {}).get('delegated_operation_id') == grant['operation_id']]
        if len(matches) != 1:
            return {'command_id': grant['command_id'], 'status': 'unknown', 'dispatch_repeated': False}
        run = matches[0]
        if (run['thread_id'] != grant['child_thread_id']
                or run['metadata'].get('delegated_command_id') != grant['command_id']
                or run['metadata'].get('dispatch_digest') != canonical_sha256(dispatch_arguments(grant['command']))):
            raise ValueError('delegated_reconciliation_identity_mismatch')
        return command_receipt(await self.authority.accept(grant, {'thread_id': run['thread_id'],
                                                 'run_id': run['run_id'], 'status': run['status']}))

    async def observe(self, child_thread_id):
        grant = await self.authority.read(str(UUID(str(child_thread_id))))
        await self._thread(grant)
        runs = await self._runs(grant['child_thread_id'])
        state = await self.sdk.threads.get_state(grant['child_thread_id'])
        values = state.get('values') or {}
        # A saved note, partial answer, or successful transport is not an
        # accepted delivery. Only the submitted result in this checkpoint is.
        results = [m.get('artifact') for m in values.get('messages', [])
                   if m.get('type') == 'tool' and m.get('name') == 'complete_delegated_task'
                   and m.get('status') != 'error' and isinstance(m.get('artifact'), dict)]
        latest = max(runs, key=lambda r: r.get('created_at', '')) if runs else None
        prior = results[-1] if results else None
        result = (prior if prior and latest and latest['status'] == 'success'
                  and prior.get('run_id') == latest['run_id'] else None)
        current = state.get('checkpoint', {}).get('checkpoint_id')
        await self.authority.check(grant, read_only=True)
        return {'child_thread_id': grant['child_thread_id'], 'checkpoint_id': current,
                'runs': [{'run_id': r['run_id'], 'status': r['status']} for r in runs],
                'outcome': deepcopy(result), 'input_digest': grant['binding']['input_digest'],
                'prior_artifact': deepcopy(prior.get('artifact')) if prior and result is None else None,
                'review_status': 'not_assessed_in_this_record'}
