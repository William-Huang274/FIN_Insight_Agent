"""Thin asset-context adapter for existing native draft creation endpoints."""
from fastapi import HTTPException
from sec_agent.research_foundation.asset_workspace import AssetWorkspace


def load_asset_context(service, owner, identifier):
    if service.attachment_store is None:
        raise HTTPException(503, '本部署未配置资产存储')
    workspace = AssetWorkspace(service.attachment_store.root.parent / 'project-library')
    try:
        return workspace.context(owner, identifier)
    except KeyError:
        raise HTTPException(404, '资产交接不属于当前用户或来源不存在') from None
    except (ValueError, OSError):
        raise HTTPException(409, '交接资料当前不可使用，请回资产区检查版本与权限') from None


def context_materials(context):
    return {'project_id': context['refs'][0]['project_id'],
            'document_ids': [r['version_id'] for r in context['refs'] if r['kind'] == 'document'],
            'sec_version': next((r['version_id'] for r in context['refs'] if r['kind'] == 'sec'), None)}


def copy_context_materials(service, owner, context, thread):
    workspace = AssetWorkspace(service.attachment_store.root.parent / 'project-library')
    selection = context_materials(context)
    rows = [workspace.resolve(owner, r)[1] for r in context['refs'] if r['kind'] == 'document']
    if rows:
        service.attachment_store.copy_project_materials(thread, selection['project_id'], rows)
    financial = None
    if selection['sec_version']:
        from sec_agent.research_foundation.project_financial_facts import prepare_task_financial_snapshot
        financial = prepare_task_financial_snapshot(workspace.sec, owner, selection['project_id'], selection['sec_version'], service.attachment_store.root, thread)
    return financial
