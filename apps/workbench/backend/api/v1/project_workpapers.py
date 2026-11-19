"""Project navigation to the existing native working-paper editor, not copies."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from ...authentication import current_owner
from sec_agent.research_foundation.project_library import ProjectLibrary


def build_project_workpapers_router(root, service):
    router = APIRouter(prefix='/asset-workspace/projects')
    library = ProjectLibrary(root)

    @router.get('/{project_id}/tasks')
    async def tasks(project_id: UUID, request: Request, response: Response, offset: int = Query(0, ge=0)):
        owner = current_owner(request)
        response.headers['Cache-Control'] = 'no-store'
        try:
            await run_in_threadpool(library.scope, owner, project_id)
        except KeyError:
            raise HTTPException(404, '项目不存在') from None
        index = await run_in_threadpool(library.index, owner)
        identifiers = [tid for tid, project in index['assignments'].items() if project == str(project_id)]

        async def read(tid):
            try:
                thread = await service.sdk.threads.get(tid)
            except Exception:
                return {'thread_id': tid, 'available': False, 'title': '任务暂不可读取',
                        'notice': '原记录保留；请检查原生运行服务，不代表任务或底稿已删除。'}
            metadata = thread.get('metadata', {})
            if metadata.get('owner_id', 'local-pilot') != owner:
                return None
            surface = {'research_session': 'research-sessions', 'conversation_session': 'conversations'}.get(metadata.get('graph'))
            if not surface:
                return None
            return {'thread_id': tid, 'available': True, 'title': metadata.get('title') or '未命名任务',
                    'status': thread.get('status'), 'surface': surface}

        rows = await asyncio.gather(*(read(tid) for tid in identifiers[offset:offset + 12]))
        return {'items': [r for r in rows if r], 'next_offset': offset + 12 if offset + 12 < len(identifiers) else None,
                'notice': '直接维护原任务的工作底稿；版本与责任角色不变。已有正式报告不会被静默覆盖。'}

    return router
