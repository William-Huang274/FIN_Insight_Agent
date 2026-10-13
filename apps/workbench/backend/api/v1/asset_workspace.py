"""Asset workspace transport; original project stores own content and versions."""
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field

from ...authentication import current_owner
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetRef, AssetContextRequest, AssetConflict
from sec_agent.research_foundation.project_asset_access import ProjectAssetUnavailable
from sec_agent.research_foundation.project_asset_versions import RevisionConflict
from sec_agent.research_foundation.project_source_captures import CaptureRequest, save_capture, read_capture, render_capture


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


class CaptureNoteEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_ref: AssetRef
    note: str = Field(max_length=10000)


class SpacePublication(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: UUID
    space_id: UUID
    ref: AssetRef


def build_asset_workspace_router(root, *, attachments_root=None, fact_mart=None):
    workspace = AssetWorkspace(root)
    from ...space_assets import SpaceAssets
    from ...business_transport import space_business_request
    from starlette.concurrency import run_in_threadpool
    shared = SpaceAssets(root / 'organization-assets')
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
        except ValueError as exc: raise HTTPException(422, str(exc) if str(exc).startswith('选择内容超过') else '资产内容或版本参数不适用') from None
        except OSError: raise HTTPException(409, '保存的原件暂不可读取，请保留记录并检查存储') from None

    @router.get('/projects/{project_id}')
    def catalog(project_id: UUID, request: Request, response: Response):
        return call(workspace.catalog, identity(request, response), project_id)

    @router.post('/spaces/publish')
    async def publish(body: SpacePublication, request: Request, response: Response):
        actor = identity(request, response, True)
        scope = await space_business_request(actor, 'POST', f'spaces/{body.space_id}/access', {'action': 'publish'})
        if str(scope.get('id')) != str(body.space_id):
            raise HTTPException(502, '空间授权结果不匹配')
        binding = await run_in_threadpool(call, shared.publish, workspace, actor, body.id, scope['organization_id'], body.space_id, body.ref)
        return await space_business_request(actor, 'POST', 'resources', {'id': str(body.id), 'space_id': str(body.space_id),
            'title': binding['title'], 'resource_type': binding['resource_type'], 'binding': binding})

    @router.get('/spaces/resources/{resource_id}')
    async def shared_read(resource_id: UUID, request: Request, response: Response):
        actor = identity(request, response)
        grant = await space_business_request(actor, 'POST', f'resources/{resource_id}/access')
        if str(grant.get('id')) != str(resource_id):
            raise HTTPException(502, '资料授权结果不匹配')
        result = await run_in_threadpool(call, shared.read, grant['binding'])
        return {**result, 'resource_id': str(resource_id), 'permission_revision': grant['revision']}

    @router.get('/catalog')
    def catalog_page(request: Request, response: Response, project_id: UUID | None = None,
                     query: str = Query('', max_length=200), role: str = Query('', pattern='^(document|report|database)?$'),
                     offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
        return call(workspace.catalog_page, identity(request, response), project_id, query, role, offset, limit)

    @router.post('/read')
    def read(ref: AssetRef, request: Request, response: Response):
        return call(workspace.read, identity(request, response), ref)

    @router.get('/profile')
    def profile(request: Request, response: Response):
        return call(workspace.profile, identity(request, response))

    @router.put('/profile')
    def save_profile(body: ProfileEdit, request: Request, response: Response):
        return call(workspace.save_profile, identity(request, response, True), body.body, body.version)

    @router.get('/profile/history')
    def profile_history(request: Request, response: Response, offset: int = Query(0, ge=0)):
        return call(workspace.profile_history, identity(request, response), offset)

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

    @router.post('/captures')
    def capture(body: CaptureRequest, request: Request, response: Response):
        owner = identity(request, response, True)
        if attachments_root is None:
            raise HTTPException(503, '来源接入尚未配置')
        return call(save_capture, workspace, owner, body, attachments_root, fact_mart)

    @router.put('/captures/note')
    def note(body: CaptureNoteEdit, request: Request, response: Response):
        owner = identity(request, response, True)
        _, row = call(workspace.resolve, owner, body.base_ref)
        if not row:
            raise HTTPException(422, '所选资产不支持来源批注')
        captured = call(read_capture, workspace.library.documents, row)
        if not captured:
            raise HTTPException(422, '所选资产不是固定来源快照')
        manifest = row['project_origin']['asset_capture']
        return call(lambda: workspace.library.documents.add(row['thread'], row['name'],
            render_capture(captured['snapshot'], body.note).encode(),
            source_capture={'snapshot':captured['snapshot'],'note':body.note},
            revision={'parent':row['id'],'change_kind':'correction','note':'用户修改批注，原始来源保持不变',
                      'capture_digest':manifest['snapshot_digest']}))

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
