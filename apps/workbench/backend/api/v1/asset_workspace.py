"""Asset workspace transport; original project stores own content and versions."""
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ...authentication import current_owner
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetRef, AssetContextRequest, AssetConflict
from sec_agent.research_foundation.project_asset_access import ProjectAssetUnavailable
from sec_agent.research_foundation.project_asset_versions import RevisionConflict


class ProfileEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(max_length=4000)
    version: int = Field(ge=0, strict=True)


class DocumentEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=100000)
    base_ref: AssetRef | None = None


def build_asset_workspace_router(root):
    workspace = AssetWorkspace(root)
    router = APIRouter(prefix='/asset-workspace')

    def identity(request, response, write=False):
        owner = current_owner(request)
        response.headers['Cache-Control'] = 'no-store'
        if write and (request.headers.get('x-workbench-request') != '1' or
                      request.headers.get('origin', str(request.base_url).rstrip('/')) not in {
                          str(request.base_url).rstrip('/'), 'http://127.0.0.1:5173', 'http://localhost:5173'}):
            raise HTTPException(403, '拒绝跨站点资产写入')
        return owner

    def call(fn, *args):
        try: return fn(*args)
        except KeyError: raise HTTPException(404, '项目、资产或交接记录不存在') from None
        except (AssetConflict, ProjectAssetUnavailable, RevisionConflict) as exc: raise HTTPException(409, str(exc)) from None
        except ValueError: raise HTTPException(422, '资产内容或版本参数不适用') from None
        except OSError: raise HTTPException(409, '保存的原件暂不可读取，请保留记录并检查存储') from None

    @router.get('/projects/{project_id}')
    def catalog(project_id: UUID, request: Request, response: Response):
        return call(workspace.catalog, identity(request, response), project_id)

    @router.post('/read')
    def read(ref: AssetRef, request: Request, response: Response):
        return call(workspace.read, identity(request, response), ref)

    @router.get('/profile')
    def profile(request: Request, response: Response):
        return call(workspace.profile, identity(request, response))

    @router.put('/profile')
    def save_profile(body: ProfileEdit, request: Request, response: Response):
        return call(workspace.save_profile, identity(request, response, True), body.body, body.version)

    @router.post('/documents')
    def save_document(body: DocumentEdit, request: Request, response: Response):
        owner = identity(request, response, True)
        scope = call(workspace.library.scope, owner, body.project_id)
        revision = None
        if body.base_ref:
            if body.base_ref.kind != 'document' or body.base_ref.project_id != body.project_id:
                raise HTTPException(422, '修订必须属于当前项目文档')
            existing = call(workspace.read, owner, body.base_ref)
            if not existing['editable']:
                raise HTTPException(409, '此资产请通过原始资料或报告编辑入口维护')
            revision = {'parent': body.base_ref.version_id, 'change_kind': 'correction', 'note': '用户在资产工作区编辑'}
        filename = body.title if body.title.lower().endswith(('.md', '.txt')) else body.title + '.md'
        return call(lambda: workspace.library.documents.add(scope, filename, body.text.encode(), revision=revision))

    @router.post('/contexts')
    def save_context(body: AssetContextRequest, request: Request, response: Response):
        return call(workspace.create_context, identity(request, response, True), body)

    @router.get('/contexts/{context_id}')
    def context(context_id: UUID, request: Request, response: Response):
        owner = identity(request, response)
        value = call(lambda: workspace.context(owner, context_id, validate=False))
        changes = []
        for ref in value['refs']:
            try:
                workspace.resolve(owner, ref)
                group = next(r for r in workspace.catalog(owner, ref['project_id'])['items'] if r['asset_id'] == ref['asset_id'] and r['kind'] == ref['kind'])
                changes.append({'ref': ref, 'status': 'newer_version_available' if group['current']['ref']['version_id'] != ref['version_id'] else 'current'})
            except (KeyError, ValueError, OSError):
                changes.append({'ref': ref, 'status': 'unavailable'})
        return {**value, 'source_status': changes}

    return router
