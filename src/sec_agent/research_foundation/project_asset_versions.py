"""Immutable source versions and mechanical differences, not financial impact inference.

SQLite owns revision concurrency; difflib owns text alignment. SEC observations
are compared as exact multisets, preserving duplicate filings and decimal values.
"""
from collections import Counter
from decimal import Decimal
from difflib import unified_diff
import json
from itertools import islice

from .project_asset_access import access_state, require_active


class RevisionConflict(ValueError):
    pass


def register_revision(db, scope, child, revision):
    """Called inside the attachment insert transaction, so failure leaves no orphan."""
    parent = revision['parent']
    if revision['change_kind'] not in {'correction', 'new_period'} or len(revision.get('note', '')) > 500:
        raise ValueError('invalid_revision_metadata')
    row = db.execute('SELECT id FROM attachments WHERE thread=? AND id=?', (scope, parent)).fetchone()
    if not row:
        raise KeyError('资料不属于当前项目')
    require_active(access_state(db, scope, 'document', parent))
    origin = db.execute('SELECT origin FROM attachment_origins WHERE object_id=?', (parent,)).fetchone()
    if origin and json.loads(origin[0]).get('research_origin'):
        raise RevisionConflict('研究成果请在原任务修订后另存，保留原生报告版本记录。')
    captured = json.loads(origin[0]).get('asset_capture') if origin else None
    if captured and revision.get('capture_digest') != captured['snapshot_digest']:
        raise RevisionConflict('固定来源不可替换，请使用批注编辑；新披露需另存来源快照。')
    db.execute('CREATE TABLE IF NOT EXISTS attachment_revisions '
               '(child TEXT PRIMARY KEY,parent TEXT UNIQUE NOT NULL,root TEXT NOT NULL,sequence INTEGER NOT NULL,change_kind TEXT NOT NULL,note TEXT NOT NULL)')
    if db.execute('SELECT 1 FROM attachment_revisions WHERE parent=?', (parent,)).fetchone():
        raise RevisionConflict('该版本已有后续版本，请重新载入并选择最新版本；本次文件未保存。')
    previous = db.execute('SELECT root,sequence FROM attachment_revisions WHERE child=?', (parent,)).fetchone()
    db.execute('INSERT INTO attachment_revisions VALUES(?,?,?,?,?,?)',
               (child, parent, previous['root'] if previous else parent, previous['sequence'] + 1 if previous else 2,
                revision['change_kind'], revision.get('note', '')))


def document_versions(store, scope, *, ids=None):
    items = store.list(scope, ids=ids)
    with store.connect() as db:
        revisions = {r['child']: dict(r) for r in db.execute(
            'SELECT r.* FROM attachment_revisions r JOIN attachments a ON a.id=r.child WHERE a.thread=?', (scope,))} if db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='attachment_revisions'").fetchone() else {}
    for item in items:
        origin = item.get('project_origin', {}).get('research_origin')
        r = revisions.get(item['document_id'], {})
        item['version_info'] = {'family': 'report:' + origin['thread_id'] if origin else r.get('root', item['document_id']),
                                'sequence': origin['report_version'] if origin else r.get('sequence', 1),
                                'parent': r.get('parent'), 'change_kind': 'report' if origin else r.get('change_kind', 'original'),
                                'note': origin.get('reason', '') if origin else r.get('note', '')}
    return items


def history(library, sec, owner, project, kind, asset):
    scope = library.scope(owner, project)
    if kind == 'document':
        items = document_versions(library.documents, scope)
        selected = next((r for r in items if r['document_id'] == asset), None)
        if not selected:
            raise KeyError('项目资料不存在')
        return {'items': [r for r in items if r['version_info']['family'] == selected['version_info']['family']]}
    if kind == 'sec':
        items = sec.versions(owner, project)['items']
        selected = next((r for r in items if r['version'] == asset), None)
        if not selected:
            raise KeyError('数据版本不存在')
        return {'items': list(reversed([r for r in items if r['cik'] == selected['cik']]))}
    raise KeyError('资产类型不存在')


def compare(library, sec, owner, project, kind, before, after, offset=0):
    versions = history(library, sec, owner, project, kind, before)['items']
    key = 'document_id' if kind == 'document' else 'version'
    if before == after or not any(r[key] == after for r in versions):
        raise ValueError('请选择同一资料或同一公司的两个不同版本。')
    if kind == 'document':
        scope = library.scope(owner, project)
        old, new = [library.documents.get(scope, value) for value in (before, after)]
        old_pages, new_pages = [json.loads(r['pages']) for r in (old, new)]
        # Bound worst-case difflib cost; original files remain downloadable.
        texts = ['\n'.join(p['text'] for p in pages) for pages in (old_pages, new_pages)]
        incomplete = any(p['needs_vision'] for p in old_pages + new_pages)
        too_large = any(len(t) > 300_000 or len(t.splitlines()) > 8000 for t in texts)
        lines = list(islice(unified_diff(texts[0].splitlines(), texts[1].splitlines(),
                           fromfile=old['name'], tofile=new['name'], lineterm=''), 2001)) if not too_large else []
        return {'kind': kind, 'before': before, 'after': after, 'raw_equal': old['digest'] == new['digest'],
                'before_digest': old['digest'], 'after_digest': new['digest'], 'lines': lines[:2000],
                'truncated': too_large or len(lines) > 2000, 'unread_pages': incomplete,
                'notice': '仅比较已解析正文；图片、表格布局和解析遗漏不在比较范围内。无文本差异不代表原件相同。'}
    payloads, sources = [], []
    for value in (before, after):
        raw, source = sec.raw(owner, project, value, 'sec_companyfacts')
        payloads.append(json.loads(raw, parse_float=Decimal))
        sources.append(source)
    def observations(payload):
        counter = Counter()
        for taxonomy, tags in payload['facts'].items():
            for tag, fact in tags.items():
                for unit, rows in fact['units'].items():
                    for row in rows:
                        record = {'taxonomy': taxonomy, 'tag': tag, 'unit': unit, 'observation': {**row, 'val': str(row['val'])}}
                        counter[json.dumps(record, sort_keys=True, default=str)] += 1
        return counter
    old, new = map(observations, payloads)
    added, removed = new - old, old - new
    changes = [('removed', removed), ('added', added)]
    entries = [{'change': change, 'count': count, **json.loads(record)}
               for change, counter in changes for record, count in sorted(counter.items())]
    return {'kind': kind, 'before': before, 'after': after, 'raw_equal': sources[0]['sha256'] == sources[1]['sha256'],
            'before_digest': sources[0]['sha256'], 'after_digest': sources[1]['sha256'],
            'added': sum(added.values()), 'removed': sum(removed.values()), 'total': len(entries),
            'items': entries[offset:offset + 50], 'offset': offset,
            'next_offset': offset + 50 if offset + 50 < len(entries) else None,
            'notice': '比较 companyfacts 原始观测（含重复次数）。修订显示为移除旧记录、加入新记录；不合并期间、单位或申报号，不判断财务影响。披露目录及指标描述不在此比较范围内。'}


def matches_dependency(dependency, project, scope, kind, asset):
    # Exact recorded binding only: never infer dependencies from prose or names.
    return (dependency.get('project_id') == str(project) and dependency.get('source_scope') == scope
            and dependency.get('asset_kind', 'document') == kind
            and dependency.get('document_id' if kind == 'document' else 'sec_version') == asset)


def task_bindings(store, thread):
    """Metadata-only inspection also works when an old source was revoked."""
    with store.connect() as db:
        origins = [json.loads(row[0]) for row in db.execute(
            'SELECT o.origin FROM attachment_origins o JOIN attachments a ON a.id=o.object_id WHERE a.thread=?', (thread,))]
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='task_financial_snapshots'").fetchone():
            row = db.execute('SELECT body FROM task_financial_snapshots WHERE thread=?', (thread,)).fetchone()
            if row:
                origin = json.loads(row[0]).get('project_origin')
                if origin:
                    origins.append({**origin, 'asset_kind': 'sec'})
    return origins
