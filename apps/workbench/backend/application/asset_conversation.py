"""Thin native conversation adapters; no second session or memory engine."""
import json

from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetContextRequest
from sec_agent.research_foundation.task_asset_updates import TaskAssetUpdates, TaskAssetView
from sec_agent.agent_runtime.conversation_handoff import public_history, observed_sources


def submission_context(service, thread):
    """Freeze at submission, not when a queued worker eventually starts."""
    if not thread.get('metadata', {}).get('asset_context'):
        return {}
    root = service.attachment_store.root
    latest = TaskAssetUpdates(root).latest(thread['thread_id'])
    profile = AssetWorkspace(root.parent / 'project-library').profile(thread['metadata']['owner_id'])
    return {'finsight_asset_revision': latest['revision'] if latest else 0, 'finsight_asset_memory': profile}


def discussion_context(service, owner, thread, state, question):
    """Save a lossless public discussion/receipt snapshot as fallible project prose."""
    root = service.attachment_store.root
    view = TaskAssetView(root, thread['thread_id'])
    from sec_agent.research_foundation.project_asset_access import require_task_assets
    require_task_assets(view, thread['thread_id'])
    context = view.binding['body']['context'] if view.binding else thread['metadata']['asset_context']
    workspace = AssetWorkspace(root.parent / 'project-library')
    for ref in context['refs']:
        workspace.resolve(owner, ref)
    direct = [r for r in view.list(thread['thread_id']) if not r.get('project_origin', {}).get('project_id')]
    if len(context['refs']) + len(direct) >= 12:
        raise ValueError('交接包含讨论快照后超过12份资料，请先另建明确范围的对话')
    project = context['refs'][0]['project_id']
    scope = workspace.library.scope(owner, project)
    refs = list(context['refs'])
    source_bindings = []
    for item in view.list(thread['thread_id']):
        origin = item.get('project_origin', {})
        if origin.get('project_id'):
            source_bindings.append({'conversation_document_id': item['document_id'], 'project_origin': {
                k: origin[k] for k in ('project_id', 'document_id', 'raw_body_sha256') if k in origin}})
    for item in direct:
        raw = view.get(thread['thread_id'], item['document_id'])
        saved = workspace.library.documents.add(scope, item['name'], raw['body'], deduplicate=True)
        ref = {'project_id': project, 'kind': 'document', 'asset_id': saved['document_id'],
               'version_id': saved['document_id'], 'digest': saved['digest']}
        refs.append(ref)
        source_bindings.append({'conversation_document_id': item['document_id'], 'project_ref': ref})
    checkpoint = state['checkpoint']['checkpoint_id']
    snapshot = {'source_thread': thread['thread_id'], 'checkpoint_id': checkpoint,
                'authority': '用户与助手的未核验讨论。旧回答不是原始事实；工具凭证仍须核查来源、期间、单位。',
                'messages': public_history(state), 'observed_sources': observed_sources(state),
                'source_bindings': source_bindings,
                'reading_rule': '讨论中的旧UPLOAD标识属于原对话；新任务须从当前目录读取相应项目原件，引用本次工具返回的完整标识。'}
    text = '# 资产讨论交接\n\n' + json.dumps(snapshot, ensure_ascii=False, indent=2)
    if len(text.encode()) > 2 * 1024 * 1024:
        raise ValueError('讨论快照超过2MiB；请先用原生对话交接收束范围，不会静默截断')
    saved = workspace.library.documents.add(scope, '资产讨论-' + checkpoint + '.md', text.encode(), deduplicate=True)
    ref = next(a['current']['ref'] for a in workspace.catalog(owner, project)['items']
               if a['current']['ref']['version_id'] == saved['document_id'])
    return workspace.create_context(owner, AssetContextRequest.model_validate({
        'schema_version': 'asset_context.v1', 'question': question, 'refs': refs + [ref],
        'memory_version': workspace.profile(owner)['version']}))
