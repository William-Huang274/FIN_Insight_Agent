"""Project asset use rights on the existing SQLite store, checked at each read.

Revocation stops future use, not already delivered content or historical audit.
No distributed lease, deletion, or generic authorization engine is introduced.
"""
import json
from pathlib import Path
import sqlite3
from contextlib import closing


class ProjectAssetUnavailable(ValueError):
    pass


def access_state(db, scope, kind, asset):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='project_asset_access'").fetchone():
        return 'active'  # Existing stores predate the additive access table.
    row = db.execute('SELECT revoked FROM project_asset_access WHERE scope=? AND kind=? AND asset=? ORDER BY rowid DESC LIMIT 1',
                     (scope, kind, asset)).fetchone()
    return 'revoked' if row and row[0] else 'active'


def require_active(state):
    if state != 'active':
        raise ProjectAssetUnavailable('项目资料已撤销或使用状态不可核实；请在原项目恢复使用后再继续。')


def bind_project_store(db, thread, path):
    # Host-only location, separate from public provenance and browser fields.
    db.execute('CREATE TABLE IF NOT EXISTS task_project_stores(thread TEXT PRIMARY KEY, path TEXT NOT NULL)')
    prior = db.execute('SELECT path FROM task_project_stores WHERE thread=?', (thread,)).fetchone()
    path = str(Path(path).resolve())
    if prior and prior[0] != path:
        raise ValueError('task_project_store_mismatch')
    db.execute('INSERT OR IGNORE INTO task_project_stores VALUES(?,?)', (thread, path))


def project_store_path(store, thread):
    with store.connect() as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='task_project_stores'").fetchone():
            row = db.execute('SELECT path FROM task_project_stores WHERE thread=?', (str(thread),)).fetchone()
            if row:
                return Path(row[0])
    # Existing product layout; missing authority never creates an empty database.
    return store.root.parent / 'project-library' / 'attachments.sqlite'


def origin_access(store, thread, origin, kind='document', source_path=None):
    if origin and origin.get('research_origin', {}).get('source_dependencies'):
        path = source_path or (project_store_path(store, thread) if origin.get('project_id') else store.path)
        for dependency in origin['research_origin']['source_dependencies']:
            if origin_access(store, thread, dependency, dependency.get('asset_kind', 'document'), path) != 'active':
                return 'dependency_unavailable'
    if not origin or not origin.get('project_id'):
        return 'active'
    asset = origin['document_id'] if kind == 'document' else origin['sec_version']
    try:
        path = source_path or project_store_path(store, thread)
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
            if kind == 'document':
                rows = db.execute('SELECT thread,digest FROM attachments WHERE id=?', (asset,)).fetchall()
                if len(rows) != 1 or rows[0][1] != origin['raw_body_sha256']:
                    return 'unavailable'
            else:
                rows = db.execute('SELECT scope,body FROM project_sec_versions WHERE version=?', (asset,)).fetchall()
                if origin.get('source_scope'):
                    rows = [r for r in rows if r[0] == origin['source_scope']]
                if len(rows) != 1 or json.loads(rows[0][1])['status'] != 'complete':
                    return 'unavailable'
            scope = rows[0][0]
            if origin.get('source_scope') and origin['source_scope'] != scope:
                return 'unavailable'
            return access_state(db, scope, kind, asset)
    except (OSError, sqlite3.Error, ValueError, KeyError):
        return 'unavailable'


def task_source_dependencies(store, thread, *, _source_scope=False):
    if not _source_scope and not hasattr(store, 'binding'):
        from .task_asset_updates import TaskAssetView
        store = TaskAssetView(store.root, thread)
    if len(getattr(store, 'scopes', [])) > 1:
        from .task_attachments import TaskAttachmentStore
        base = TaskAttachmentStore(store.root)
        return [item for scope in store.scopes for item in task_source_dependencies(base, scope, _source_scope=True)]
    require_task_assets(store, thread)
    dependencies = [item['project_origin'] for item in store.list(thread) if item.get('project_origin')]
    with store.connect() as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='task_financial_snapshots'").fetchone():
            row = db.execute('SELECT body FROM task_financial_snapshots WHERE thread=?', (str(thread),)).fetchone()
            if row:
                dependencies.append({**json.loads(row[0])['project_origin'], 'asset_kind': 'sec'})
    return dependencies


def require_task_assets(store, thread):
    """Also stops reuse of prior context before a new provider request."""
    if len(getattr(store, 'scopes', [])) > 1:
        from .task_attachments import TaskAttachmentStore
        base = TaskAttachmentStore(store.root)
        for scope in store.scopes:
            require_task_assets(base, scope)
        return
    for item in store.list(thread):
        require_active(item['access_status'])
    with store.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='task_financial_snapshots'").fetchone():
            return
        row = db.execute('SELECT body FROM task_financial_snapshots WHERE thread=?', (str(thread),)).fetchone()
    if row:
        info = json.loads(row[0])
        if info['status'] != 'ready':
            raise ProjectAssetUnavailable('项目财务资料准备未完成，不能继续使用。')
        require_active(origin_access(store, thread, info['project_origin'], 'sec'))


def task_access_check(environment):
    if not environment.get('FINSIGHT_TASK_ATTACHMENTS_ROOT') or not environment.get('FINSIGHT_TASK_THREAD_ID'):
        return None
    from .task_asset_updates import task_asset_view
    store = task_asset_view(environment)
    thread = environment['FINSIGHT_TASK_THREAD_ID']
    return lambda: require_task_assets(store, thread)
