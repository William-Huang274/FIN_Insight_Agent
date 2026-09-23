"""Authorized feedback cards; user opinions never modify source or graph records."""
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from ...authentication import service_owner
from sec_agent.agent_runtime.research_feedback import ResearchFeedbackStore, FeedbackChoice


def build_research_feedback_router(service):
    router = APIRouter(prefix='/research-sessions')

    def store():
        if not service.audit_root:
            raise HTTPException(503, '研究反馈存储未配置')
        return ResearchFeedbackStore(Path(service.audit_root) / 'research-feedback.sqlite')

    async def authorize(thread_id):
        thread = await service.owned_thread(thread_id)
        if service.attachment_store:
            from sec_agent.research_foundation.project_asset_access import require_task_assets, ProjectAssetUnavailable
            from sec_agent.research_foundation.task_asset_updates import TaskAssetView
            try:
                await run_in_threadpool(require_task_assets, TaskAssetView(service.attachment_store.root, thread_id), thread_id)
            except (ProjectAssetUnavailable, ValueError, OSError):
                raise HTTPException(409, '资料权限或版本不可用，请检查任务资料') from None
        return thread

    def browser_write(request):
        if request.headers.get('x-workbench-request') != '1':
            raise HTTPException(403, '缺少工作台请求标识')
        if request.headers.get('origin') not in (None, str(request.base_url).rstrip('/'),
                                                'http://127.0.0.1:5173', 'http://localhost:5173'):
            raise HTTPException(403, '拒绝跨站请求')

    @router.get('/{thread_id}/research-feedback')
    async def read(thread_id: UUID, response: Response, run_id: UUID | None = None):
        await authorize(thread_id)
        response.headers['Cache-Control'] = 'no-store'
        rows = await run_in_threadpool(store().list, service_owner(), str(thread_id), str(run_id) if run_id else None)
        state = await service.state(thread_id)
        values = state.get('values', {})
        orientation = values.get('research_orientation') if not run_id or values.get('orientation_run_id') == str(run_id) else None
        return {'items': rows, 'orientation': orientation,
                'notice': '疑点与用户意见尚待核查；不会自动改写关系库或启动模型。'}

    @router.post('/{thread_id}/research-feedback/{record_id}')
    async def choose(thread_id: UUID, record_id: str, body: FeedbackChoice, request: Request):
        browser_write(request)
        await authorize(thread_id)
        try:
            saved = await run_in_threadpool(store().choose, service_owner(), str(thread_id), record_id, body)
        except KeyError:
            raise HTTPException(404, '反馈不存在') from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return {'saved': True, 'opinion': saved,
                'notice': '意见已保存，Lead 后续调用可读取；本次提交不启动补查或修改资料库。'}

    @router.post('/{thread_id}/start-orientation')
    async def start(thread_id: UUID, request: Request):
        browser_write(request)
        thread = await authorize(thread_id)
        from .report_sessions import graph_for_thread, RESEARCH_GRAPH, SURFACE
        from .research_studio import run_configuration
        metadata = thread.get('metadata', {})
        question = metadata.get('pending_question')
        if graph_for_thread(thread) != RESEARCH_GRAPH or not service.research_profile or not question:
            raise HTTPException(409, '需要尚未启动的研究草稿')
        if metadata.get('project_materials_status') not in (None, 'ready'):
            raise HTTPException(409, '项目资料尚未准备完成')
        if await service.sdk.runs.list(str(thread_id), limit=1):
            raise HTTPException(409, '任务已有运行记录，请查看现有结果；不会重新执行')
        from sec_agent.agent_runtime.research_session import ResearchRequest
        payload = ResearchRequest(question=question, research_stage='orientation').model_dump(mode='json')
        run = await service.sdk.runs.create(str(thread_id), RESEARCH_GRAPH,
            input=payload, config=await run_configuration(service, thread),
            stream_mode='custom', stream_subgraphs=True, stream_resumable=True, multitask_strategy='reject',
            metadata={'surface': SURFACE, 'human_action': 'orientation', 'request_message': question})
        return {'run_id': run['run_id'], 'status': run['status']}

    return router
