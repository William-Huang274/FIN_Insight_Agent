"""Read-only organization research delivery with current all-input authorization."""
from copy import deepcopy
import json
import re
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from .authentication import service_owner
from .business_transport import space_business_request
from sec_agent.agent_runtime.organization_native_contract import validate_thread


async def read_authority(project_id, execution_id):
    grant = await space_business_request(service_owner(), 'GET',
        f'projects/{project_id}/execution-bindings/{execution_id}/read-access')
    try:
        if (grant['read_contract'] != 'organization_research_read.v1'
                or grant['reader'] != service_owner() or grant['project_id'] != str(project_id)
                or grant['execution_id'] != str(execution_id) or grant['thread_id'] != str(execution_id)):
            raise ValueError('scope')
        if grant['run_id'] is not None:
            UUID(grant['run_id'])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(502, '组织研究读取授权不匹配') from None
    return grant


class OrganizationReadScope:
    def __init__(self, service, project_id, execution_id):
        self.service, self.project, self.execution = service, project_id, execution_id

    async def open(self):
        self.grant = await read_authority(self.project, self.execution)
        self.thread = await self.service.sdk.threads.get(str(self.execution))
        try:
            frozen = validate_thread(self.thread, self.grant)
            if frozen['configuration_digest'] != self.grant['configuration_digest']:
                raise ValueError('configuration')
        except ValueError:
            raise HTTPException(409, '组织研究冻结记录不匹配') from None
        await self.check()
        return self

    async def check(self):
        if await read_authority(self.project, self.execution) != self.grant:
            raise HTTPException(409, '组织研究读取授权已变化，请重新读取')

    async def state(self, checkpoint_id=None):
        if self.grant['run_id'] is None:
            raise HTTPException(409, '研究尚无已关联运行')
        kwargs = {'checkpoint_id': str(checkpoint_id)} if checkpoint_id else {}
        result = await self.service.sdk.threads.get_state(str(self.execution), **kwargs)
        await self.check()
        return result

    async def response(self, value):
        # Serialize/render before the last authority check; never cache an ACL.
        result = JSONResponse(value, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
        await self.check()
        return result


def install_organization_read_routes(router, service):
    from .api.v1.report_sessions import public_state, public_event
    prefix = '/organization-projects/{project_id}/research/{execution_id}'

    async def opened(project, execution):
        return await OrganizationReadScope(service, project, execution).open()

    @router.get(prefix)
    async def snapshot(project_id: UUID, execution_id: UUID):
        scope = await opened(project_id, execution_id)
        state = await scope.state() if scope.grant['run_id'] else {'values': {}}
        projected = public_state(state)
        # Product mutations still need distinct organization commands.
        projected.update({key: False for key in projected if key.startswith('can_')})
        projected.update(thread_id=str(execution_id), project_id=str(project_id),
                         title=scope.grant['title'], run_id=scope.grant['run_id'],
                         status=scope.thread.get('status'), read_only=True)
        return await scope.response(projected)

    @router.get(prefix + '/report')
    async def report(project_id: UUID, execution_id: UUID, checkpoint_id: UUID | None = None):
        scope = await opened(project_id, execution_id)
        state = await scope.state(checkpoint_id)
        values = state.get('values', {})
        if not values.get('report'):
            raise HTTPException(409, '所选记录尚无报告')
        return await scope.response({'report': values['report'], 'report_version': values.get('report_version'),
                                     'phase': values.get('phase'), 'read_only': True})

    @router.get(prefix + '/source')
    async def source(project_id: UUID, execution_id: UUID, source_id: str, offset: int = 0,
                     checkpoint_id: UUID | None = None):
        scope = await opened(project_id, execution_id)
        if not 0 <= offset <= 10000000 or not 1 <= len(source_id) <= 512:
            raise HTTPException(422, '来源阅读范围不合法')
        values = (await scope.state(checkpoint_id)).get('values', {})
        # Read saved citation material only. Never resolve a personal/public
        # CaseArtifacts source using an organization's thread or creator identity.
        records = [s for name in ('report', 'synthesis', 'research_synthesis')
                   for c in (values.get(name) or {}).get('citations', {}).values()
                   for s in c.get('sources', []) if s.get('source_id') == source_id]
        if not records:
            raise HTTPException(404, '引用未与所选研究成果绑定')
        if any(row != records[0] for row in records[1:]):
            raise HTTPException(409, '同一来源标识存在不同快照，请明确报告版本')
        result = deepcopy(records[0])
        text = result.get('text', '')
        result.update(text=text[offset:offset + 16000],
                      next_offset=offset + 16000 if offset + 16000 < len(text) else None,
                      content_scope='saved_citation_snapshot')
        return await scope.response(result)

    @router.get(prefix + '/report/export/{format}')
    async def export(project_id: UUID, execution_id: UUID, format: Literal['md', 'pdf', 'docx', 'pptx'],
                     request: Request, checkpoint_id: UUID | None = None):
        scope = await opened(project_id, execution_id)
        values = (await scope.state(checkpoint_id)).get('values', {})
        if not values.get('report'):
            raise HTTPException(409, '所选记录尚无报告')
        from .application.report_delivery import export_report
        data, mime = await run_in_threadpool(export_report, values['report'], format,
            review_status='组织研究导出快照；不表示审批通过', public_base_url=str(request.base_url))
        result = Response(data, media_type=mime, headers={'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': f'attachment; filename="finsight-organization-research.{format}"'})
        await scope.check()
        return result

    @router.get(prefix + '/runs/{run_id}/events')
    async def events(project_id: UUID, execution_id: UUID, run_id: UUID, request: Request):
        scope = await opened(project_id, execution_id)
        if scope.grant['run_id'] != str(run_id):
            raise HTTPException(404, '运行不属于已授权研究')
        last_id = request.headers.get('last-event-id') or '0-0'
        if not re.fullmatch(r'[0-9]+-[0-9]+', last_id):
            raise HTTPException(422, '无效的事件续读位置')
        async def stream():
            try:
                await scope.check()
                async for part in service.sdk.runs.join_stream(str(execution_id), str(run_id), last_event_id=last_id):
                    # No event bytes follow a failed current authorization check.
                    await scope.check()
                    if part.event.split('|', 1)[0] != 'custom':
                        continue
                    data = public_event(part.data)
                    if data is None:
                        continue
                    event_id = f'id: {part.id}\n' if part.id and re.fullmatch(r'[0-9]+-[0-9]+', part.id) else ''
                    chunk = event_id + 'event: custom\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n'
                    await scope.check()
                    yield chunk
            except HTTPException:
                # Headers may already have been sent. Close without revealing
                # private authority details or replaying a denied buffered event.
                return
        return StreamingResponse(stream(), media_type='text/event-stream',
            headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})
