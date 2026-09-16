"""Immutable task input revisions, pinned at native-run submission.

SQLite owns source bindings only; Agent Server still owns scheduling/checkpoints.
Prepared copies never replace the source bytes of an existing run.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .asset_workspace import AssetRef, AssetWorkspace, AssetConflict, _digest
from .task_attachments import TaskAttachmentStore, task_material_catalog


class AssetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    base_revision: int = Field(ge=0, strict=True)
    ref: AssetRef


class TaskAssetUpdates:
    def __init__(self, root):
        self.store = TaskAttachmentStore(root)
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS task_asset_updates '
                       '(thread TEXT, revision INTEGER, request_id TEXT UNIQUE, state TEXT, body TEXT, '
                       'PRIMARY KEY(thread,revision))')
            db.execute('CREATE TABLE IF NOT EXISTS task_asset_runs '
                       '(thread TEXT, run TEXT, revision INTEGER, recorded_at TEXT, PRIMARY KEY(thread,run))')

    def rows(self, thread):
        with self.store.connect() as db:
            return [dict(r) | {'body': json.loads(r['body'])} for r in db.execute(
                'SELECT * FROM task_asset_updates WHERE thread=? ORDER BY revision', (str(thread),))]

    def latest(self, thread):
        return next((r for r in reversed(self.rows(thread)) if r['state'] == 'ready'), None)

    def baseline(self, owner, thread, metadata):
        """Backfill old project drafts from their actual copied source identities."""
        if metadata.get('asset_context'):
            return deepcopy(metadata['asset_context'])
        workspace = AssetWorkspace(self.store.root.parent / 'project-library')
        origins = [r['project_origin'] for r in self.store.list(thread) if r.get('project_origin', {}).get('project_id')]
        from .project_financial_facts import task_financial_snapshot
        financial = task_financial_snapshot(self.store.root, thread)
        if financial:
            origins.append(financial[1]['project_origin'])
        projects = {r['project_id'] for r in origins}
        if len(projects) != 1:
            raise AssetConflict('当前任务没有唯一的项目资料绑定，请从资产区准备任务')
        catalog = workspace.catalog(owner, projects.pop())['items']
        ids = {r.get('document_id', r.get('sec_version')) for r in origins}
        versions = [v for a in catalog for v in a['versions'] if v['ref']['version_id'] in ids]
        if len(versions) != len(ids) or len({(v['ref']['kind'], v['ref']['asset_id']) for v in versions}) != len(versions):
            raise AssetConflict('旧任务资料版本不唯一，请从资产区明确选版准备任务')
        body = {'schema_version': 'asset_context.v1', 'context_id': str(uuid4()), 'version_policy': 'pinned',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'question': metadata.get('pending_question') or metadata.get('title', '研究任务'),
                'refs': [v['ref'] for v in versions], 'titles': [v['title'] for v in versions],
                'memory': {'version': 0, 'body': ''}}
        return body | {'digest': _digest(body)}

    def prepare(self, owner, thread, metadata, request):
        thread = str(UUID(str(thread)))
        payload = request.model_dump(mode='json')
        # Idempotency is owned by this immutable source operation, not model dispatch.
        for row in self.rows(thread):
            if row['request_id'] == str(request.request_id):
                if row['body']['request'] != payload:
                    raise AssetConflict('相同请求标识不能改变资料选择')
                return row
        previous = self.latest(thread)
        base = previous['body']['context'] if previous else self.baseline(owner, thread, metadata)
        ref = request.ref.model_dump(mode='json')
        matches = [i for i, r in enumerate(base['refs']) if all(r[k] == ref[k] for k in ('project_id', 'kind', 'asset_id'))]
        if len(matches) != 1:
            raise AssetConflict('仅可更新当前任务已绑定的同一资产；新增研究范围请另行明确选择')
        index = matches[0]
        if base['refs'][index] == ref:
            raise AssetConflict('此版本已经是待采用的任务输入')
        workspace = AssetWorkspace(self.store.root.parent / 'project-library')
        context = deepcopy(base)
        context['refs'][index] = ref
        versions = [workspace.resolve(owner, r)[0] for r in context['refs']]
        context.update(context_id=str(uuid4()), created_at=datetime.now(timezone.utc).isoformat(),
                       titles=[v['title'] for v in versions])
        context.pop('digest', None)
        context['digest'] = _digest(context)
        scope = str(uuid4())
        body = {'request': payload, 'scope': scope, 'context': context, 'previous_ref': base['refs'][index],
                'selected_ref': ref, 'impact': 'requires_reassessment', 'created_at': context['created_at']}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('SELECT revision,state,request_id,body FROM task_asset_updates WHERE thread=? ORDER BY revision', (thread,)).fetchall()
            same = next((r for r in rows if r['request_id'] == str(request.request_id)), None)
            if same:
                if json.loads(same['body'])['request'] != payload:
                    raise AssetConflict('相同请求标识不能改变资料选择')
                return dict(same) | {'body': json.loads(same['body'])}
            current = next((r['revision'] for r in reversed(rows) if r['state'] == 'ready'), 0)
            if current != request.base_revision or any(r['state'] == 'preparing' for r in rows):
                raise AssetConflict('任务资料已变化或正在准备，请刷新后再提交')
            if len(rows) >= 64:
                raise AssetConflict('本任务已达到64次资料更新记录，请保留历史并建立后续任务')
            revision = max((r['revision'] for r in rows), default=0) + 1
            db.execute('INSERT INTO task_asset_updates VALUES(?,?,?,?,?)',
                       (thread, revision, str(request.request_id), 'preparing', json.dumps(body, ensure_ascii=False)))
        try:
            docs = [workspace.resolve(owner, r)[1] for r in context['refs'] if r['kind'] == 'document']
            direct = [r for r in self.store.list(thread) if not r.get('project_origin', {}).get('project_id')]
            if len(docs) + len(direct) > 12 or sum(len(r['body']) for r in docs) + sum(r['bytes'] for r in direct) > 80 * 1024 * 1024:
                raise AssetConflict('当前选择与任务上传资料合计超过12份或80MiB')
            if docs:
                self.store.copy_project_materials(scope, context['refs'][0]['project_id'], docs)
            sec = next((r for r in context['refs'] if r['kind'] == 'sec'), None)
            if sec:
                from .project_financial_facts import prepare_task_financial_snapshot
                prepare_task_financial_snapshot(workspace.sec, owner, sec['project_id'], sec['version_id'], self.store.root, scope)
            # Revalidate after copying, before publication; a concurrent revocation cannot grant access.
            for r in context['refs']:
                workspace.resolve(owner, r)
            state = 'ready'
        except Exception:
            with self.store.connect() as db:
                db.execute("UPDATE task_asset_updates SET state=? WHERE thread=? AND revision=? AND state='preparing'", ('failed', thread, revision))
            raise
        with self.store.connect() as db:
            changed = db.execute("UPDATE task_asset_updates SET state=? WHERE thread=? AND revision=? AND state='preparing'", (state, thread, revision))
            if not changed.rowcount:
                raise AssetConflict('该准备请求已放弃，原任务输入未改变')
        return {'thread': thread, 'revision': revision, 'request_id': str(request.request_id), 'state': state, 'body': body}

    def abandon_preparation(self, thread, revision):
        """Explicit recovery for a worker that died between reserve and publish."""
        with self.store.connect() as db:
            changed = db.execute("UPDATE task_asset_updates SET state='abandoned' WHERE thread=? AND revision=? AND state='preparing'",
                                 (str(thread), revision))
            if not changed.rowcount:
                raise AssetConflict('该请求不在准备中；已经就绪或采用的输入不能撤销')

    def pin(self, thread, run, revision):
        """Run config chooses the revision; delayed workers cannot adopt a newer request."""
        thread, run = str(UUID(str(thread))), str(UUID(str(run)))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if revision and not db.execute('SELECT 1 FROM task_asset_updates WHERE thread=? AND revision=? AND state=?',
                                          (thread, revision, 'ready')).fetchone():
                raise AssetConflict('task_asset_revision_not_ready')
            old = db.execute('SELECT revision FROM task_asset_runs WHERE thread=? AND run=?', (thread, run)).fetchone()
            if old and old[0] != revision:
                raise AssetConflict('native_run_asset_revision_is_immutable')
            db.execute('INSERT OR IGNORE INTO task_asset_runs VALUES(?,?,?,?)',
                       (thread, run, revision, datetime.now(timezone.utc).isoformat()))

    def revision_for(self, thread, run=None):
        with self.store.connect() as db:
            if run:
                row = db.execute('SELECT revision FROM task_asset_runs WHERE thread=? AND run=?', (str(thread), str(run))).fetchone()
            else:
                row = db.execute('SELECT revision FROM task_asset_runs WHERE thread=? ORDER BY rowid DESC LIMIT 1', (str(thread),)).fetchone()
        return row[0] if row else 0

    def binding(self, thread, run=None):
        revision = self.revision_for(thread, run)
        return next((r for r in self.rows(thread) if r['revision'] == revision and r['state'] == 'ready'), None)


class TaskAssetView(TaskAttachmentStore):
    """Current catalog plus explicit historical citation reads in the same task."""
    def __init__(self, root, thread, run=None, *, validate=True):
        super().__init__(root)
        self.thread = str(thread)
        updates = TaskAssetUpdates(root)
        self.binding = updates.binding(thread, run)
        # Only adopted sources can have entered historical model context. A
        # superseded preparation must not widen tool access or block a later run.
        with self.connect() as db:
            ceiling = db.execute('SELECT rowid FROM task_asset_runs WHERE thread=? AND run=?', (self.thread, str(run))).fetchone() if run else None
            adopted = {r[0] for r in db.execute('SELECT revision FROM task_asset_runs WHERE thread=?'
                + (' AND rowid<=?' if run else ''), (self.thread, ceiling[0] if ceiling else 0) if run else (self.thread,))}
        self.scopes = [self.thread, *[r['body']['scope'] for r in updates.rows(thread)
                                    if r['state'] == 'ready' and r['revision'] in adopted]]
        self.financial_scope = self.binding['body']['scope'] if self.binding else self.thread
        if self.binding and validate:
            context = self.binding['body']['context']
            if context['digest'] != _digest({k: v for k, v in context.items() if k != 'digest'}):
                raise AssetConflict('task_asset_context_integrity_failure')
            current = super().list(self.financial_scope)
            actual = {(r.get('project_origin', {}).get('document_id'), r['digest']) for r in current}
            expected = {(r['version_id'], r['digest']) for r in context['refs'] if r['kind'] == 'document'}
            if actual != expected:
                raise AssetConflict('task_asset_prepared_documents_incomplete')
            from .project_financial_facts import task_financial_snapshot
            financial = task_financial_snapshot(self.root, self.financial_scope)
            sec = next((r for r in context['refs'] if r['kind'] == 'sec'), None)
            if bool(sec) != bool(financial) or (sec and financial[1]['project_origin']['sec_version'] != sec['version_id']):
                raise AssetConflict('task_asset_prepared_financial_binding_incomplete')
            selected = self.list(self.thread)
            if len(selected) > 12 or sum(r['bytes'] for r in selected) > 80 * 1024 * 1024:
                raise AssetConflict('task_asset_current_input_exceeds_capacity')

    def list(self, thread_id, *, ids=None):
        if str(thread_id) != self.thread or not self.binding:
            return super().list(thread_id, ids=ids)
        # Direct user uploads stay in the task; only project inputs change.
        direct = [r for r in super().list(self.thread, ids=ids) if not r.get('project_origin', {}).get('project_id')]
        return direct + super().list(self.financial_scope, ids=ids)

    def get(self, thread_id, object_id):
        if str(thread_id) != self.thread:
            return super().get(thread_id, object_id)
        with self.connect() as db:
            row = db.execute('SELECT thread FROM attachments WHERE id=?', (object_id,)).fetchone()
        if not row or row[0] not in self.scopes:
            raise ValueError('attachment_not_in_current_task')
        result = super().get(row[0], object_id)
        if sha256(result['body']).hexdigest() != result['digest']:
            raise AssetConflict('task_asset_document_integrity_failure')
        return result


def asset_update_prompt(view):
    if not view.binding:
        return ''
    body = view.binding['body']
    return ('\n用户已明确更新任务资料，当前原生运行固定输入修订 r' + str(view.binding['revision']) + '。'
            '本次选择替代旧版本用于后续研究；旧底稿、报告、工具回执仍基于当时版本，不能当作已更新。'
            '先读取新版并比较相关旧依据，检查受影响主张、数字、期间、单位、计算及上下游结论；'
            '在任务状态说明中列明实际检查与仍未解决的影响。不能声称仅采用资料就已完成复核。'
            '历史引用可按原文档ID回读，目录只列当前选择。研究截止日不自动改变。\n'
            + json.dumps({'previous_ref': body['previous_ref'], 'selected_ref': body['selected_ref'],
                          'context': body['context'], 'current_materials': task_material_catalog(view.list(view.thread))}, ensure_ascii=False))


def task_asset_view(environment):
    return TaskAssetView(environment['FINSIGHT_TASK_ATTACHMENTS_ROOT'], environment['FINSIGHT_TASK_THREAD_ID'],
                         environment.get('FINSIGHT_TASK_RUN_ID'))
