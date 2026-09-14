"""Authenticated persistent project index and a bounded private document library."""
from urllib.parse import unquote, quote
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from ...authentication import current_owner
from sec_agent.research_foundation.project_library import ProjectLibrary, ProjectConflict
from sec_agent.research_foundation.task_attachments import MAX_BYTES


class Project(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: UUID
    name: str=Field(min_length=1,max_length=60)


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
        data=body.model_dump(mode='json'); data.pop('revision')
        prior_refs=set(prior['assignments'])|set(prior['pinned'])
        for thread in (set(data['assignments'])|set(data['pinned']))-prior_refs:
            await service.owned_thread(thread)
        try: return await run_in_threadpool(library.save,identity,body.revision,data)
        except ProjectConflict as exc: raise HTTPException(409,str(exc)) from None

    @router.get('/{project_id}/documents')
    def search(project_id: UUID, request: Request, response: Response, query: str=Query('',max_length=200)):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        return library.search(identity,project_id,query)

    @router.post('/{project_id}/documents')
    async def upload(project_id: UUID, request: Request):
        identity=owner(request,True); target=await run_in_threadpool(scope,identity,project_id)
        body=bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body)>MAX_BYTES: raise HTTPException(413,'单个文件最多20 MiB')
        filename=unquote(request.headers.get('x-file-name',''))
        try: return await run_in_threadpool(library.documents.add,target,filename,bytes(body))
        except ValueError as exc: raise HTTPException(422,str(exc)) from None

    @router.get('/{project_id}/documents/{document_id}')
    def detail(project_id: UUID, document_id: str, request: Request, response: Response):
        identity=owner(request); scope(identity,project_id)
        response.headers['Cache-Control']='no-store'
        try: return library.detail(identity,project_id,document_id)
        except ValueError: raise HTTPException(404,'项目资料不存在') from None

    @router.get('/{project_id}/documents/{document_id}/download')
    def download(project_id: UUID, document_id: str, request: Request):
        target=scope(owner(request),project_id)
        try: row=library.documents.get(target,document_id)
        except ValueError: raise HTTPException(404,'项目资料不存在') from None
        return Response(row['body'],media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['name'],safe=''),
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    return router
