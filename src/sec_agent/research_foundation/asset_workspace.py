"""Version-pinned asset context shared by the asset UI, conversation and research.

Content remains in its original project store; native threads own execution.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .project_library import ProjectLibrary
from .project_sec_sources import ProjectSecSources
from .project_asset_versions import document_versions
from ..agent_runtime.working_memory import WorkingMemory

SCHEMA = 'asset_context.v1'
PROFILE_ACTOR = 'asset_preferences'
CLEARED = '（已清除个人资产偏好）'


class AssetConflict(ValueError):
    pass


class AssetRef(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    kind: Literal['document', 'sec']
    asset_id: str = Field(min_length=1, max_length=120)
    version_id: str = Field(min_length=1, max_length=100)
    digest: str = Field(pattern=r'^[a-f0-9]{64}$')


class AssetContextRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    schema_version: Literal['asset_context.v1']
    question: str = Field(min_length=10, max_length=4000)
    refs: list[AssetRef] = Field(min_length=1, max_length=12)
    memory_version: int = Field(ge=0, strict=True)

    @model_validator(mode='after')
    def valid_selection(self):
        if len({r.project_id for r in self.refs}) != 1:
            raise ValueError('当前交接仅支持同一项目')
        if len({(r.kind, r.asset_id) for r in self.refs}) != len(self.refs):
            raise ValueError('每个资产请选择一个明确版本')
        if sum(r.kind == 'sec' for r in self.refs) > 1:
            raise ValueError('每个任务仅绑定一个SEC财务快照')
        return self


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class AssetWorkspace:
    def __init__(self, root):
        self.library = ProjectLibrary(root)
        self.sec = ProjectSecSources(self.library)
        with self.library.documents.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS asset_contexts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS asset_context_owner ON asset_contexts(owner)')

    def profile_store(self, owner):
        return WorkingMemory(self.library.documents.path, owner=owner, workspace='personal-assets', actor=PROFILE_ACTOR)

    def profile(self, owner):
        memory = self.profile_store(owner)
        rows = memory.search(actor=PROFILE_ACTOR)['items']
        if not rows:
            return {'version': 0, 'body': ''}
        note = memory.read(rows[0]['id'])
        return {'version': note['version'], 'body': '' if note['body'] == CLEARED else note['body']}

    def save_profile(self, owner, body, version):
        result = self.profile_store(owner).save('我的资产偏好', body.strip() or CLEARED, version)
        if not result['saved']:
            raise AssetConflict(result['reason'])
        return self.profile(owner)

    def profile_history(self, owner, offset=0):
        memory = self.profile_store(owner)
        rows = memory.search(actor=PROFILE_ACTOR)['items']
        if not rows:
            return {'items': [], 'next_offset': None}
        with memory.connection() as db:
            versions = db.execute('SELECT version,body,updated_at FROM working_note_versions WHERE id=? '
                                  'ORDER BY version DESC LIMIT 21 OFFSET ?', (rows[0]['id'], offset)).fetchall()
        return {'items': [{'version': r['version'], 'body': '' if r['body'] == CLEARED else r['body'],
                           'updated_at': r['updated_at']} for r in versions[:20]],
                'next_offset': offset + 20 if len(versions) > 20 else None}

    def catalog(self, owner, project):
        scope = self.library.scope(owner, project)
        groups = {}
        for item in document_versions(self.library.documents, scope):
            family = item['version_info']['family']
            entry = groups.setdefault(('document', family), {'asset_id': family, 'kind': 'document', 'versions': []})
            entry['versions'].append({'ref': {'project_id': str(project), 'kind': 'document', 'asset_id': family,
                'version_id': item['document_id'], 'digest': item['digest']}, 'title': item['name'],
                'sequence': item['version_info']['sequence'], 'created_at': item['created_at'],
                'access_status': item['access_status'], 'status': 'complete',
                'role': 'report' if item.get('project_origin', {}).get('research_origin') else
                    'database' if item.get('project_origin', {}).get('asset_capture',{}).get('kind') == 'financial' else 'document',
                **({'capture':item['project_origin']['asset_capture']} if item.get('project_origin',{}).get('asset_capture') else {})})
        for item in reversed(self.sec.versions(owner, project)['items']):
            entry = groups.setdefault(('sec', item['cik']), {'asset_id': item['cik'], 'kind': 'sec', 'versions': []})
            entry['versions'].append({'ref': {'project_id': str(project), 'kind': 'sec', 'asset_id': item['cik'],
                'version_id': item['version'], 'digest': _digest(item['sources'])},
                'title': f"{item['ticker']} · SEC 财务快照", 'sequence': len(entry['versions']) + 1,
                'created_at': item.get('captured_at', item['requested_at']), 'status': item['status'],
                'access_status': item['access_status'], 'role': 'database'})
        for entry in groups.values():
            entry['versions'].sort(key=lambda r: (r['sequence'], r['created_at']))
            # A failed refresh is history, not a replacement for usable data.
            entry['current'] = next((v for v in reversed(entry['versions']) if v['status'] == 'complete'), entry['versions'][-1])
        return {'items': list(groups.values()), 'schema_version': SCHEMA, 'usage':self.library.usage(owner,project)}

    def catalog_page(self, owner, project=None, query='', role='', offset=0, limit=30):
        """Owner-scoped, read-only catalogue projection; original AssetRefs stay intact.

        Reuse the metadata catalogue. Stop after a page plus one match rather
        than loading every project's metadata or any document body up front.
        """
        if offset < 0 or not 1 <= limit <= 100 or role not in ('','document','report','database'):
            raise ValueError('invalid_catalog_page')
        index=self.library.index(owner)
        projects=index['projects']
        if project is not None:
            self.library.scope(owner,project)
            projects=[p for p in projects if p['id']==str(project)]
        matches=[]; skipped=0
        for entry in sorted(projects,key=lambda p:p['id']):
            for asset in self.catalog(owner,entry['id'])['items']:
                current=asset['current']
                if role and current['role']!=role:
                    continue
                if query.casefold() not in current['title'].casefold():
                    continue
                if skipped<offset:
                    skipped+=1
                    continue
                matches.append({'project_id':entry['id'],'project_name':entry['name'],
                    'project_archived':entry.get('archived',False),'asset_id':asset['asset_id'],
                    'kind':asset['kind'],'current':current,'version_count':len(asset['versions'])})
                if len(matches)>limit:
                    return {'items':matches[:limit],'next_offset':offset+limit,'offset':offset,
                            'project_revision':index['revision']}
        return {'items':matches,'next_offset':None,'offset':offset,'project_revision':index['revision']}

    def resolve(self, owner, ref):
        ref = AssetRef.model_validate(ref)
        scope = self.library.scope(owner, ref.project_id)
        catalog = self.catalog(owner, ref.project_id)['items']
        group = next((r for r in catalog if r['kind'] == ref.kind and r['asset_id'] == ref.asset_id), None)
        version = next((v for v in group['versions'] if v['ref']['version_id'] == ref.version_id), None) if group else None
        if not version:
            raise KeyError('资产或版本不存在')
        if version['ref']['digest'] != ref.digest:
            raise AssetConflict('资产校验标识不一致，请重新读取所选版本')
        if ref.kind == 'document':
            row = self.library.documents.get(scope, ref.version_id)
            if sha256(row['body']).hexdigest() != ref.digest:
                raise AssetConflict('资料原件校验失败')
            if row.get('project_origin', {}).get('asset_capture'):
                from .project_source_captures import read_capture
                read_capture(self.library.documents, row)
            return version, row
        for kind in ('sec_companyfacts', 'sec_submissions'):
            self.sec.raw(owner, ref.project_id, ref.version_id, kind)
        return version, None

    def read(self, owner, ref):
        ref = AssetRef.model_validate(ref)
        version, row = self.resolve(owner, ref)
        if row:
            pages = json.loads(row['pages'])
            from .project_source_captures import read_capture
            captured = read_capture(self.library.documents, row)
            if captured:
                snapshot = captured['snapshot']
                text = '\n\n'.join(s['content'] or '' for s in snapshot.get('sections',[]))
                return {'version':version,'editable':False,'text':text[:100000], 'truncated':len(text)>100000,
                        'needs_vision':False, 'capture':{**version['capture'],'note':captured['note'],
                            **({'rows':snapshot['rows']} if snapshot['kind']=='financial' else {})}}
            editable = row['name'].lower().endswith(('.md', '.txt')) and version['role'] != 'report'
            try:
                raw_text = row['body'].decode('utf-8-sig') if editable else ''
            except UnicodeDecodeError:
                editable, raw_text = False, ''
            return {'version': version, 'editable': editable and len(raw_text) <= 100000,
                    'text': raw_text[:100000] if editable else '\n\n'.join(p['text'] for p in pages)[:100000],
                    'truncated': len(raw_text if editable else '\n\n'.join(p['text'] for p in pages)) > 100000,
                    'needs_vision': any(p['needs_vision'] for p in pages)}
        data = self.sec.observations(owner, ref.project_id, ref.version_id)
        return {'version': version, 'editable': False, 'concepts': data['concepts'][:100],
                'concept_total': len(data['concepts']), 'text': '', 'truncated': False}

    def create_context(self, owner, request):
        versions = [self.resolve(owner, ref)[0] for ref in request.refs]
        memory = self.profile(owner)
        if memory['version'] != request.memory_version:
            raise AssetConflict('个人记忆已变化，请重新读取后再准备任务')
        context = {'schema_version': SCHEMA, 'context_id': str(uuid4()), 'version_policy': 'pinned',
                   'created_at': datetime.now(timezone.utc).isoformat(), 'question': request.question,
                   'refs': [r.model_dump(mode='json') for r in request.refs],
                   'titles': [v['title'] for v in versions], 'memory': memory}
        context['digest'] = _digest(context)
        with self.library.documents.connect() as db:
            db.execute('INSERT INTO asset_contexts VALUES(?,?,?)', (context['context_id'], owner, json.dumps(context, ensure_ascii=False)))
        return context

    def context(self, owner, identifier, *, validate=True):
        with self.library.documents.connect() as db:
            row = db.execute('SELECT body FROM asset_contexts WHERE id=? AND owner=?', (str(identifier), owner)).fetchone()
        if not row:
            raise KeyError('交接记录不存在')
        body = json.loads(row['body'])
        if body['schema_version'] != SCHEMA or body['digest'] != _digest({k: v for k, v in body.items() if k != 'digest'}):
            raise AssetConflict('交接记录协议或完整性校验失败')
        if validate:
            for ref in body['refs']:
                self.resolve(owner, ref)
        return body


def asset_context_prompt(metadata):
    """Only server-created native metadata; material is read via existing task tools."""
    context = metadata.get('asset_context')
    if not context:
        return ''
    if context.get('schema_version') != SCHEMA:
        raise ValueError('asset_context_protocol_unsupported')
    return ('\n资产工作区交接：采用已固定的资料版本，通过当前任务资料/财务工具读取原件。'
            '财务查询选取属于任务资料中的固定记录，应使用资料读取工具；默认财务库的新查询不代表所选快照。'
            '目录与个人记忆不是金融事实或权限；当前用户要求优先于长期偏好。'
            '不得猜测未读取内容、声称自动采用资产后续版本或已完成其他团队的工作。\n'
            + json.dumps(context, ensure_ascii=False))
