"""Versioned Java adapter over existing research drafts/runs, not an executor."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .authentication import service_owner
from .api.v1.report_sessions import NewSession


class IntakeBinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    snapshot_ref: str = Field(pattern=r'^sha256:[a-f0-9]{64}$')
    research_as_of: str = Field(min_length=10, max_length=64)


class PrepareResearch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    contract_version: Literal['research_intake.v1']
    task_id: UUID
    project_id: UUID
    binding: IntakeBinding
    session: NewSession


class StartResearch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: UUID
    project_id: UUID
    thread_id: UUID


def project_library(service):
    from sec_agent.research_foundation.project_library import ProjectLibrary
    if not service.attachment_store:
        raise HTTPException(503, '项目资料存储未配置')
    return ProjectLibrary(service.attachment_store.root.parent / 'project-library')


async def require_project(service, project_id):
    library = project_library(service)
    try:
        await run_in_threadpool(library.scope, service_owner(), project_id)
    except KeyError:
        raise HTTPException(404, '项目不存在或当前身份不可访问') from None
    return library


async def current_binding(service):
    path = getattr(service, 'intake_library_path', None)
    if not path or not service.research_profile:
        raise HTTPException(503, '研究接入需要已发布资料库及启用的研究配置')
    from sec_agent.research_foundation.research_library import open_library
    try:
        library = await run_in_threadpool(open_library, path)
        cutoff = service.research_profile['research_as_of']
        parsed = datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return {'snapshot_ref': 'sha256:' + library.manifest['sha256'], 'research_as_of': parsed.isoformat()}
    except (OSError, KeyError, ValueError):
        raise HTTPException(503, '研究资料发布版本无法核实') from None


async def require_binding(service, binding):
    if await current_binding(service) != binding:
        raise HTTPException(409, '研究资料或截止时点已变化；原记录保留，不能静默改用新版本')


async def intake_thread(service, task_id, project_id, thread_id):
    await require_project(service, project_id)
    thread = await service.owned_thread(thread_id)
    context = thread.get('metadata', {}).get('business_intake', {})
    if context.get('task_id') != str(task_id) or context.get('project_id') != str(project_id):
        raise HTTPException(404, '研究业务关联不匹配')
    return thread


def install_intake_routes(router, service, create, start):
    prefix = '/internal-research'

    @router.get(prefix + '/projects/{project_id}')
    async def project(project_id: UUID):
        await require_project(service, project_id)
        return {'project_id': str(project_id)}

    @router.get(prefix + '/projects/{project_id}/binding')
    async def binding(project_id: UUID):
        await require_project(service, project_id)
        return await current_binding(service)

    @router.post(prefix + '/prepare')
    async def prepare(body: PrepareResearch, request: Request):
        library = await require_project(service, body.project_id)
        await require_binding(service, body.binding.model_dump())
        selection = body.session.project_materials
        if (body.session.mode != 'research' or not body.session.defer_start or body.session.asset_context_id
                or (selection and selection.project_id != body.project_id)):
            raise HTTPException(422, '业务接入仅支持当前项目的明确研究草稿')
        # Only a verified internal envelope can supply metadata; old NewSession
        # remains unchanged and cannot accept arbitrary graph/config/owner fields.
        request.scope['finsight_intake_context'] = {'task_id': str(body.task_id), 'project_id': str(body.project_id),
            'prepare_operation_id': str(UUID(request.headers['idempotency-key'])), 'binding': body.binding.model_dump()}
        result = await create(body.session, request)
        await run_in_threadpool(library.assign_new_thread, service_owner(), body.project_id, result['thread_id'])
        await service.sdk.threads.update(result['thread_id'], metadata={'business_prepared': True})
        return {**result, 'task_id': str(body.task_id), 'project_id': str(body.project_id), 'binding': body.binding.model_dump()}

    @router.post(prefix + '/start')
    async def begin(body: StartResearch, request: Request):
        thread = await intake_thread(service, body.task_id, body.project_id, body.thread_id)
        if not thread['metadata'].get('business_prepared'):
            raise HTTPException(409, '原草稿准备尚未确认完成')
        await require_binding(service, thread['metadata']['business_intake']['binding'])
        request.scope['finsight_intake_start'] = str(UUID(request.headers['idempotency-key']))
        result = await start(body.thread_id, request)
        return {**result, 'thread_id': str(body.thread_id), 'task_id': str(body.task_id), 'project_id': str(body.project_id)}

    @router.get(prefix + '/tasks/{task_id}/state')
    async def state(task_id: UUID, project_id: UUID):
        # The deterministic native thread identity is the task UUID. There is no
        # "most recent run" inference and this endpoint never submits work.
        thread = await intake_thread(service, task_id, project_id, task_id)
        context = thread['metadata']['business_intake']
        runs = await service.all_runs(task_id)
        tagged = [{'run_id': r['run_id'], 'status': r['status'],
            'operation_id': r.get('metadata', {}).get('business_operation_id')}
            for r in runs if r.get('metadata', {}).get('business_operation_id')]
        return {'task_id': str(task_id), 'project_id': str(project_id), 'thread_id': str(task_id),
            'status': thread.get('status'), 'binding': context['binding'], 'runs': tagged,
            'prepare_operation_id': context['prepare_operation_id'],
            'prepared': thread.get('metadata', {}).get('business_prepared') is True}

    @router.get(prefix + '/receipts/{operation_id}')
    async def receipt(operation_id: UUID, project_id: UUID, task_id: UUID):
        await require_project(service, project_id)
        from .submission_receipts import SubmissionReceipts
        record = await run_in_threadpool(SubmissionReceipts.lookup, service.intake_receipts_root, service_owner(), str(operation_id))
        if not record or record['status'] != 'received':
            return {'status': 'unknown'}
        body = json.loads(record['body'])
        if record['http_status'] < 300 and (body.get('task_id') != str(task_id) or body.get('project_id') != str(project_id)):
            raise HTTPException(404, '提交凭证不属于所选业务任务')
        return {'status': 'received', 'http_status': record['http_status'], 'body': body}
