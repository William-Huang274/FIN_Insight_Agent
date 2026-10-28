"""On-demand task tools. Decisions come from the model; authority from the host."""
from copy import deepcopy
import json
from uuid import UUID, uuid5

from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime

from .conversation_agent import GrantedTool
from .delegated_task_contract import DelegateTask, TaskCommand, freeze_input
from .research_graph_contracts import canonical_sha256
from .task_outcome import TaskOutcome


def delegation_tools(*, controller, parent_thread_id, parent_run_id, root_budget_id,
                     manifest_digest, allowed_methods, note_reader, child_note_reader, access_check, runtime_configuration):
    """One root host binding; there is no model-supplied owner, budget or run ID."""
    parent_thread_id, parent_run_id = str(UUID(parent_thread_id)), str(UUID(parent_run_id))

    async def command(runtime, action, *, task=None, child=None, checkpoint=None, message=''):
        await access_check()
        state = await controller.sdk.threads.get_state(parent_thread_id)
        key = uuid5(UUID(parent_run_id), str(runtime.tool_call_id))
        body = TaskCommand(command_id=key, execution_id=parent_thread_id,
            parent_thread_id=parent_thread_id, parent_run_id=parent_run_id,
            parent_checkpoint_id=state['checkpoint']['checkpoint_id'],
            child_thread_id=child or uuid5(key, 'child'), action=action,
            root_budget_id=root_budget_id, manifest_digest=manifest_digest, task=task,
            checkpoint_id=checkpoint, message=message)
        try:
            fixed = freeze_input(body, state, allowed_methods=allowed_methods, note_reader=note_reader,
                                 runtime_configuration=runtime_configuration) if task else None
        except ValueError as exc:
            if str(exc) not in {'delegated_material_not_observed_in_selected_receipt',
                                'delegated_note_version_mismatch', 'delegated_method_not_available'}:
                raise
            raise ToolException('尚未派发：所选材料、笔记版本或方法不在当前交接目录中。请核对准确入口。原因：'+str(exc)) from exc
        return await controller.execute(body, fixed_input=fixed)

    @tool
    async def reconcile_delegated_task(child_thread_id: str, command_id: str):
        """Read-only reconciliation by original command ID. Never resubmits a run."""
        await access_check()
        grant = await controller.authority.command(str(UUID(child_thread_id)), str(UUID(command_id)))
        return await controller.reconcile(grant)

    @tool
    async def delegate_research_task(request: DelegateTask, runtime: ToolRuntime):
        """Start a bounded independent task when useful. Select exact read receipts and note versions.

        Returns a durable child identity promptly; no research is executed in
        this tool. You retain integration. Observation does not repeat dispatch.
        """
        return await command(runtime, 'create', task=request)

    @tool
    async def list_delegated_tasks():
        """Recover this root's durable child identities. Status here is command transport, not task completion."""
        await access_check()
        return await controller.authority.catalog()

    @tool
    async def observe_research_task(child_thread_id: str):
        """Read child progress, current checkpoint and submitted outcome; no model call."""
        await access_check()
        return await controller.observe(child_thread_id)

    @tool
    async def continue_research_task(child_thread_id: str, checkpoint_id: str, message: str, runtime: ToolRuntime):
        """Continue an existing child at its observed checkpoint. Reuses originals and saved work."""
        return await command(runtime, 'continue', child=child_thread_id, checkpoint=checkpoint_id, message=message)

    @tool
    async def stop_research_task(child_thread_id: str, checkpoint_id: str, runtime: ToolRuntime):
        """Stop this child, retaining its checkpoint, saved artifacts and usage records."""
        return await command(runtime, 'cancel', child=child_thread_id, checkpoint=checkpoint_id)

    @tool
    async def read_delegated_note(child_thread_id: str, note_id: str, version: int, offset: int = 0):
        """Read a child's exact saved note version. Prose is analysis, not a source receipt."""
        await access_check()
        grant = await controller.authority.read(str(UUID(child_thread_id)))
        await controller._thread(grant)
        result = child_note_reader(grant, note_id, version, offset)
        await controller.authority.check(grant, read_only=True)
        return result

    @tool(response_format='content_and_artifact')
    async def read_delegated_evidence(child_thread_id: str, checkpoint_id: str,
                                     source_id: str = '', tool_call_id: str = '', offset: int = 0):
        """List a child's original source/compute receipts, or read one exact receipt.

        Supply its observed checkpoint and returned tool_call_id/source_id. Note
        prose is not evidence. Large receipts have an exact paged display;
        the original artifact remains available to source-bound calculations.
        """
        from .conversation_handoff import observed_sources
        await access_check()
        if offset < 0:
            raise ToolException('offset必须非负')
        grant = await controller.authority.read(str(UUID(child_thread_id)))
        await controller._thread(grant)
        state = await controller.sdk.threads.get_state(grant['child_thread_id'],
            checkpoint={'checkpoint_id': str(UUID(checkpoint_id)), 'checkpoint_ns': ''})
        rows = state.get('values', {}).get('messages', [])
        entries = [(m.get('tool_call_id'), key, item) for m in rows
            for key, item in observed_sources({'values': {'messages': [m]}}).items()]
        if not source_id and not tool_call_id:
            body = {'items': [{'source_id': key, 'tool_call_id': call} for call, key, _ in entries[offset:offset+20]],
                    'next_offset': offset+20 if offset+20 < len(entries) else None,
                    'child_thread_id': child_thread_id, 'checkpoint_id': checkpoint_id}
            await controller.authority.check(grant, read_only=True)
            return json.dumps(body, ensure_ascii=False), body
        matches = [item for call, key, item in entries if call == tool_call_id and key == source_id]
        if len(matches) != 1:
            raise ToolException('请从该checkpoint的目录选择唯一的source_id和tool_call_id')
        body = {'source_items': {source_id: deepcopy(matches[0])}, 'child_thread_id': child_thread_id,
                'checkpoint_id': checkpoint_id, 'original_tool_call_id': tool_call_id}
        text = json.dumps(body, ensure_ascii=False)
        view = {'text': text[offset:offset+12000], 'offset': offset, 'total_characters': len(text),
                'next_offset': offset+12000 if offset+12000 < len(text) else None}
        await controller.authority.check(grant, read_only=True)
        return json.dumps(view, ensure_ascii=False), body

    grants = [GrantedTool(t, 'read' if t in (reconcile_delegated_task, list_delegated_tasks, observe_research_task, read_delegated_note, read_delegated_evidence) else 'delegated_task_control',
                        '宿主独立准入的子任务；固定资料、根预算和原生运行')
            for t in (delegate_research_task, list_delegated_tasks, observe_research_task, reconcile_delegated_task, continue_research_task, stop_research_task,
                      read_delegated_note, read_delegated_evidence)]
    for grant in grants:
        grant.tool.handle_tool_error = True
    return grants


def completion_tool(*, fixed_input, child_thread_id, run_id, memory, access_check):
    """Commit an answer or exact saved note using the existing native tool result."""
    intent = fixed_input['task']['delivery_intent']

    @tool(response_format='content_and_artifact', return_direct=True)
    def complete_delegated_task(answer: str = '', note_id: str = '', version: int | None = None):
        """Return the completed work. For a workpaper supply its saved note_id and version;
        for an answer supply answer text. Saving alone does not complete the task.
        Existing facts/checks keep their identities; this is not independent review.
        """
        access_check()
        if intent == 'answer':
            if not answer.strip() or note_id or version is not None:
                raise ToolException('回答交付需要answer，不需要底稿字段')
            artifact = {'kind': 'answer', 'text': answer, 'run_id': run_id}
        else:
            if answer or not note_id or type(version) is not int or version < 1:
                raise ToolException('底稿交付需要已保存的note_id和version；不要重新抄写正文')
            page = memory.read(note_id, version=version)
            if not page.get('found') or not page.get('is_current'):
                raise ToolException('指定底稿不是当前保存版本，请读取当前版本后决定')
            text, offset = page['body'], page['next_offset']
            while offset is not None:
                part = memory.read(note_id, version=version, offset=offset)
                if not part.get('found') or not part.get('is_current'):
                    raise ToolException('底稿版本读取未完成，尚未提交')
                text += part['body']; offset = part['next_offset']
            latest = memory.read(note_id)
            if not latest.get('found') or latest['version'] != version:
                raise ToolException('底稿在提交期间已更新；已有保存保留，请读取当前版本后决定')
            artifact = {'kind': 'workpaper', 'id': note_id, 'version': version,
                        'digest': canonical_sha256(text), 'workspace': child_thread_id,
                        'readback': {'tool': 'read_delegated_note', 'arguments': {
                            'child_thread_id': child_thread_id, 'note_id': note_id, 'version': version}}}
        access_check()
        result = TaskOutcome(task_id=fixed_input['task']['assignment']['subtask_id'], run_id=run_id,
            execution_status='submitted', phase='delegated_task_submitted', artifact_status='submitted',
            artifact_kind=intent, artifact_digest=artifact.get('digest') or canonical_sha256(artifact),
            author_note_status='missing', success_criteria=fixed_input['task']['assignment']['success_criteria'])
        body = {'outcome': result.model_dump(mode='json'), 'artifact': artifact,
                'input_digest': fixed_input['input_digest'], 'run_id': run_id}
        return json.dumps(body, ensure_ascii=False), body

    complete_delegated_task.handle_tool_error = True
    return GrantedTool(complete_delegated_task, 'working_note_write', '提交自己的回答或已保存底稿，不授予独立复核状态')
