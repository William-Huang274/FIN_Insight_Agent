"""Public projection for version adoption; no model dispatch or checkpoint edits."""
from sec_agent.research_foundation.task_asset_updates import TaskAssetUpdates
from sec_agent.research_foundation.asset_workspace import AssetWorkspace, AssetConflict


def update_status(root, owner, thread, metadata):
    updates = TaskAssetUpdates(root)
    latest = updates.latest(thread)
    try:
        context = latest['body']['context'] if latest else updates.baseline(owner, thread, metadata)
    except (AssetConflict, KeyError, ValueError):
        return {'supported': False, 'notice': '此任务尚无可更新的项目资料绑定。'}
    workspace = AssetWorkspace(updates.store.root.parent / 'project-library')
    catalog = workspace.catalog(owner, context['refs'][0]['project_id'])['items']
    items = []
    for index, ref in enumerate(context['refs']):
        group = next((g for g in catalog if g['kind'] == ref['kind'] and g['asset_id'] == ref['asset_id']), None)
        current = group['current'] if group else None
        items.append({'ref': ref, 'title': context['titles'][index], 'current': current,
                      'has_newer': bool(current and current['ref'] != ref)})
    active = updates.revision_for(thread)
    revision = latest['revision'] if latest else 0
    with updates.store.connect() as db:
        adopted = [dict(r) for r in db.execute('SELECT run,revision,recorded_at FROM task_asset_runs WHERE thread=? ORDER BY rowid', (str(thread),))]
    return {'supported': True, 'revision': revision, 'active_revision': active, 'pending': revision != active,
            'items': items, 'adoptions': adopted,
            'history': [{'revision': r['revision'], 'state': r['state'], 'previous_ref': r['body']['previous_ref'],
                         'selected_ref': r['body']['selected_ref'], 'created_at': r['body']['created_at']}
                        for r in updates.rows(thread)],
            'notice': '资料在下一次运行采用；不启动模型、不改旧报告，结果影响仍须核查。研究截止日保持原值。'}
