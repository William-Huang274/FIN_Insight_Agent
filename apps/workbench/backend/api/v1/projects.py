"""Authenticated persistent project index and a bounded private document library."""
from urllib.parse import unquote, quote
from uuid import UUID
from datetime import date
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Request, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from ...authentication import current_owner
from sec_agent.research_foundation.project_library import ProjectLibrary, ProjectConflict
from sec_agent.research_foundation.task_attachments import MAX_BYTES
from sec_agent.research_foundation.project_asset_access import ProjectAssetUnavailable
from sec_agent.research_foundation.project_sec_sources import ProjectSecSources
from sec_agent.research_foundation import project_asset_versions as asset_versions
from typing import Literal


class Project(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: UUID
    name: str=Field(min_length=1,max_length=60)
    description: str=Field(default='',max_length=500)
    archived: bool=Field(default=False,strict=True)


class SecRefresh(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: UUID
    ticker: str=Field(pattern=r'^[A-Z][A-Z0-9.-]{0,9}$')
    cik: str=Field(pattern=r'^[0-9]{10}$')


class AssetAccess(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revoked: bool=Field(strict=True)


class SaveReport(BaseModel):
    model_config=ConfigDict(extra='forbid')
    thread_id: UUID
    checkpoint_id: UUID | None = None
    report_digest: str=Field(pattern=r'^[a-f0-9]{64}$')


class ProjectIndex(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(ge=0,strict=True)
    projects: list[Project]=Field(max_length=200)
    assignments: dict[UUID,str]=Field(max_length=1000)
    pinned: list[UUID]=Field(max_length=1000)

    @model_validator(mode='after')
    def valid_references(self):
        ids={str(p.id) for p in self.projects}
        if len(ids)!=len(self.projects) or len(set(self.pinned))!=len(self.pinned):
            raise ValueError('duplicate_project_or_pin')
        if any(not p.name.strip() for p in self.projects) or any(v and v not in ids for v in self.assignments.values()):
            raise ValueError('invalid_project_reference')
        return self


def build_projects_router(root, service):
    library=ProjectLibrary(root)
    sec=ProjectSecSources(library)
    router=APIRouter(prefix='/projects')

    def owner(request, write=False):
        identity=current_owner(request)
        if write:
            allowed={str(request.base_url).rstrip('/'),'http://127.0.0.1:5173','http://localhost:5173'}
            if request.headers.get('x-workbench-request')!='1' or (
                    request.headers.get('origin') and request.headers['origin'] not in allowed):
                raise HTTPException(403,'拒绝跨站点项目写入')
        return identity

    def scope(identity, project_id):
        try: return library.scope(identity,project_id)
        except KeyError: raise HTTPException(404,'项目不存在') from None

    @router.get('')
    def get_index(request: Request, response: Response):
        response.headers['Cache-Control']='no-store'
        return library.index(owner(request))

    @router.put('')
    async def save_index(body: ProjectIndex, request: Request):
        identity=owner(request,True)
        prior=await run_in_threadpool(library.index,identity)
        data=body.model_dump(mode='json',exclude_unset=True); data.pop('revision')
        prior_refs=set(prior['assignments'])|set(prior['pinned'])
        for thread in (set(data['assignments'])|set(data['pinned']))-prior_refs:
            await service.owned_thread(thread)
        try: return await run_in_threadpool(library.save,identity,body.revision,data)
        except ProjectConflict as exc: raise HTTPException(409,str(exc)) from None

    @router.put('/{project_id}/assets/{kind}/{asset}/access')
    def set_access(project_id: UUID, kind: str, asset: str, body: AssetAccess, request: Request, response: Response):
        identity=owner(request,True); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return library.set_access(identity,project_id,kind,asset,body.revoked)
        except KeyError: raise HTTPException(404,'项目资产不存在') from None

    @router.get('/{project_id}/documents')
    def search(project_id: UUID, request: Request, response: Response, query: str=Query('',max_length=200),
               offset: int=Query(0,ge=0), limit: int=Query(50,ge=1,le=100)):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        return library.search(identity,project_id,query,offset,limit)

    @router.get('/{project_id}/storage')
    def storage(project_id: UUID, request: Request, response: Response):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        return library.usage(identity,project_id)

    @router.post('/{project_id}/reports')
    async def save_report(project_id: UUID, body: SaveReport, request: Request, response: Response):
        identity=owner(request,True)
        target=await run_in_threadpool(scope,identity,project_id)
        # Source report, review status and provenance are always server-owned.
        state=await service.report_state(body.thread_id,body.checkpoint_id)
        from .report_sessions import report_snapshot
        from sec_agent.agent_runtime.targeted_revision import report_digest
        from ...application.report_delivery import export_report
        if not report_snapshot(state):
            raise HTTPException(409,'报告尚未完成当前修订，请选择已完成的历史版本或稍后保存。')
        from sec_agent.research_foundation.project_asset_access import require_task_assets, ProjectAssetUnavailable
        if getattr(service, 'attachment_store', None):
            try: await run_in_threadpool(require_task_assets, service.attachment_store, body.thread_id)
            except ProjectAssetUnavailable as exc: raise HTTPException(409,str(exc)) from None
        values=state['values']; report=values['report']
        if report_digest(report)!=body.report_digest:
            raise HTTPException(409,'报告已更新，请重新载入并核对要保存的版本。')
        origin={'thread_id':str(body.thread_id),'checkpoint_id':state['checkpoint']['checkpoint_id'],
                'report_version':values['report_version'],'report_digest':body.report_digest,
                'phase':values.get('phase'),'human_edit_count':len(values.get('human_edits',[])),
                'reason':values.get('report_revision_reason') or '原版本未记录修改说明',
                'authority':'Research artifact, not independently verified disclosure or NumericFact. User confirmation is not model verification.'}
        if getattr(service, 'attachment_store', None):
            from sec_agent.research_foundation.project_asset_access import task_source_dependencies
            try: origin['source_dependencies']=await run_in_threadpool(task_source_dependencies, service.attachment_store, body.thread_id)
            except ProjectAssetUnavailable as exc: raise HTTPException(409,str(exc)) from None
        status='人工修改/确认的研究成果，仍须核对原始依据' if values.get('phase') in {'human_completed','human_reviewed_not_released'} else '研究草稿，待人工审阅'
        content,_=await run_in_threadpool(export_report,report,'md',review_status=status)
        import json
        content+=('\n\n## 研究成果出处\n\n'+json.dumps(origin,ensure_ascii=False,indent=2)+'\n').encode()
        import re
        name=re.sub(r'[/\\:\x00\r\n]','_',report['title'])[:120]+f" · v{values['report_version']}.md"
        try:
            saved=await run_in_threadpool(library.documents.add,target,name,content,research_origin=origin)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from None
        response.headers['Cache-Control']='no-store'
        return {**saved,'search_status':'saved_text_searchable','notice':'正文与查找文本已一同保存；保留原版本。研究成果不等于已核验的原始事实。'}

    @router.post('/{project_id}/documents')
    async def upload(project_id: UUID, request: Request,
                     parent: str=Query('',max_length=100),
                     change_kind: Literal['correction','new_period']='correction',
                     note: str=Query('',max_length=500)):
        identity=owner(request,True); target=await run_in_threadpool(scope,identity,project_id)
        body=bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body)>MAX_BYTES: raise HTTPException(413,'单个文件最多20 MiB')
        filename=unquote(request.headers.get('x-file-name',''))
        revision={'parent':parent,'change_kind':change_kind,'note':note} if parent else None
        try: return await run_in_threadpool(library.documents.add,target,filename,bytes(body),revision=revision)
        except KeyError: raise HTTPException(404,'原资料不属于当前项目') from None
        except (asset_versions.RevisionConflict,ProjectAssetUnavailable) as exc: raise HTTPException(409,str(exc)) from None
        except ValueError as exc: raise HTTPException(422,str(exc)) from None

    @router.get('/{project_id}/assets/{kind}/{asset}/history')
    def asset_history(project_id: UUID, kind: str, asset: str, request: Request, response: Response):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return asset_versions.history(library,sec,identity,project_id,kind,asset)
        except KeyError: raise HTTPException(404,'项目资产不存在') from None

    @router.get('/{project_id}/assets/{kind}/{asset}/compare')
    def asset_compare(project_id: UUID, kind: str, asset: str, request: Request, response: Response,
                      other: str=Query(...,max_length=100), offset: int=Query(0,ge=0,le=1000000)):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return asset_versions.compare(library,sec,identity,project_id,kind,asset,other,offset)
        except KeyError: raise HTTPException(404,'项目资产不存在') from None
        except (ValueError,OSError): raise HTTPException(409,'版本不可比较：请选择同组的不同可用版本，并检查保存原件。') from None

    @router.get('/{project_id}/assets/{kind}/{asset}/dependencies')
    async def asset_dependencies(project_id: UUID, kind: str, asset: str, request: Request, response: Response):
        identity=owner(request); target=await run_in_threadpool(scope,identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: await run_in_threadpool(asset_versions.history,library,sec,identity,project_id,kind,asset)
        except KeyError: raise HTTPException(404,'项目资产不存在') from None
        matches=lambda d: asset_versions.matches_dependency(d,project_id,target,kind,asset)
        index=await run_in_threadpool(library.index,identity)
        tasks=[]; unknown_tasks=0; native_available=True
        store=getattr(service,'attachment_store',None)
        for thread in index['assignments']:
            # Owner index is only a candidate set, never a substitute for native ownership.
            if not native_available:
                unknown_tasks+=1; continue
            try: await asyncio.wait_for(service.owned_thread(thread),timeout=5)
            except HTTPException as exc:
                if exc.status_code not in (403,404): raise
                unknown_tasks+=1; continue
            except httpx.HTTPStatusError as exc:
                unknown_tasks+=1
                if exc.response.status_code not in (403,404): native_available=False
                continue
            except (httpx.RequestError,TimeoutError):
                # Do not retry a disconnected backend once per archived task.
                unknown_tasks+=1; native_available=False; continue
            bindings=await run_in_threadpool(asset_versions.task_bindings,store,thread) if store else []
            if any(matches(d) for d in bindings): tasks.append({'thread_id':thread})
            if not bindings or any(not d.get('source_scope') for d in bindings): unknown_tasks+=1
        reports=[]; unknown_reports=0
        documents=await run_in_threadpool(library.documents.list,target)
        for doc in documents:
            origin=doc.get('project_origin',{}).get('research_origin')
            if origin is None: continue
            dependencies=origin.get('source_dependencies')
            if dependencies is None or any(not d.get('source_scope') for d in dependencies): unknown_reports+=1
            if any(matches(d) for d in dependencies or []):
                reports.append({'document_id':doc['document_id'],'name':doc['name'],
                                'report_version':origin['report_version'],'access_status':doc['access_status']})
        return {'tasks':tasks,'reports':reports,'unknown_tasks':unknown_tasks,'unknown_reports':unknown_reports,
                'coverage':'recorded_direct_bindings_only',
                'notice':'仅列出当前账户已归档任务与本项目成果中记录的直接来源绑定；不推断间接引用或具体结论影响。未列出不等于未受影响，历史依赖缺失时无法判断。'}

    @router.get('/{project_id}/documents/{document_id}')
    def detail(project_id: UUID, document_id: str, request: Request, response: Response):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return library.detail(identity,project_id,document_id)
        except ProjectAssetUnavailable as exc: raise HTTPException(409,str(exc)) from None
        except ValueError: raise HTTPException(404,'项目资料不存在') from None

    @router.get('/{project_id}/documents/{document_id}/download')
    def download(project_id: UUID, document_id: str, request: Request):
        target=scope(owner(request),project_id)
        try: row=library.documents.get(target,document_id)
        except ProjectAssetUnavailable as exc: raise HTTPException(409,str(exc)) from None
        except ValueError: raise HTTPException(404,'项目资料不存在') from None
        return Response(row['body'],media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['name'],safe=''),
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.get('/{project_id}/sec')
    def sec_versions(project_id: UUID, request: Request, response: Response):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        return sec.versions(identity,project_id)

    @router.post('/{project_id}/sec')
    def sec_refresh(project_id: UUID, body: SecRefresh, request: Request, response: Response):
        identity=owner(request,True); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return sec.capture(identity,project_id,body.version,body.ticker,body.cik)
        except ValueError as exc: raise HTTPException(409,str(exc)) from None

    @router.get('/{project_id}/sec/{version}')
    def sec_read(project_id: UUID, version: UUID, request: Request, response: Response,
                 taxonomy: str=Query('',max_length=100), tag: str=Query('',max_length=240),
                 as_of: date|None=None, offset: int=Query(0,ge=0,le=100000)):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return sec.observations(identity,project_id,version,taxonomy,tag,as_of.isoformat() if as_of else '',offset)
        except KeyError as exc: raise HTTPException(404,str(exc)) from None
        except (ValueError,OSError): raise HTTPException(409,'该版本不可读取，请检查同步状态和原件。') from None

    @router.get('/{project_id}/sec/{version}/download/{kind}')
    def sec_download(project_id: UUID, version: UUID, kind: str, request: Request):
        identity=owner(request); scope(identity,project_id)
        if kind not in ('sec_companyfacts','sec_submissions'): raise HTTPException(404,'数据原件不存在')
        try: raw,_=sec.raw(identity,project_id,version,kind)
        except KeyError: raise HTTPException(404,'数据版本不存在') from None
        except (ValueError,OSError): raise HTTPException(409,'该版本不可读取，请检查同步状态和原件。') from None
        return Response(raw,media_type='application/json',headers={
            'Content-Disposition':f'attachment; filename="{kind}.json"',
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    return router
