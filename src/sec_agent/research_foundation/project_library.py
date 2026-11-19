"""Owner-bound project organization and document copies on existing SQLite/parser.

No new retrieval service: this bounded slice searches saved text literally.
Projects do not grant access to native research threads or promote source truth.
"""
import json
import os
from uuid import UUID, uuid5, NAMESPACE_URL

from .task_attachments import TaskAttachmentStore
from .project_asset_access import access_state


class ProjectConflict(ValueError):
    pass


class ProjectLibrary:
    def __init__(self, root):
        max_files = int(os.environ.get('FINSIGHT_PROJECT_MAX_VERSIONS', '2000'))
        max_bytes = int(os.environ.get('FINSIGHT_PROJECT_MAX_BYTES', str(2 * 1024**3)))
        if not 1 <= max_files <= 10000 or not 20 * 1024**2 <= max_bytes <= 1024**4:
            raise ValueError('invalid_project_storage_limits')
        self.documents = TaskAttachmentStore(root, max_files=max_files, max_bytes=max_bytes)
        with self.documents.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            from .project_text_index import ensure_index
            ensure_index(db)
            db.execute('CREATE TABLE IF NOT EXISTS project_asset_access(scope TEXT,kind TEXT,asset TEXT,revoked INTEGER,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            db.execute('CREATE TABLE IF NOT EXISTS project_indexes(owner TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS project_access_lookup ON project_asset_access(scope,kind,asset)')

    def usage(self, owner, project_id):
        scope = self.scope(owner, project_id)
        with self.documents.connect() as db:
            count, size = db.execute('SELECT count(*),coalesce(sum(s.bytes),0) FROM attachments a '
                                    'JOIN attachment_summaries s ON s.object_id=a.id WHERE a.thread=?', (scope,)).fetchone()
        return {'versions':count, 'original_bytes':size, 'max_versions':self.documents.max_files,
                'max_original_bytes':self.documents.max_bytes, 'automatic_history_deletion':False}

    def set_access(self, owner, project, kind, asset, revoked):
        scope = self.scope(owner, project)
        with self.documents.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if kind == 'document':
                exists = db.execute('SELECT 1 FROM attachments WHERE thread=? AND id=?', (scope, asset)).fetchone()
            elif kind == 'sec':
                exists = db.execute('SELECT 1 FROM project_sec_versions WHERE scope=? AND version=?', (scope, asset)).fetchone()
            else:
                raise KeyError('asset_kind_invalid')
            if not exists:
                raise KeyError('asset_not_in_project')
            state = 'revoked' if revoked else 'active'
            if access_state(db, scope, kind, asset) != state:
                db.execute('INSERT INTO project_asset_access(scope,kind,asset,revoked) VALUES(?,?,?,?)', (scope, kind, asset, int(revoked)))
        return {'access_status': state}

    def index(self, owner):
        with self.documents.connect() as db:
            row=db.execute('SELECT revision,body FROM project_indexes WHERE owner=?',(owner,)).fetchone()
        return {'revision':row['revision'],**json.loads(row['body'])} if row else {
            'revision':0,'projects':[],'assignments':{},'pinned':[]}

    def save(self, owner, revision, body):
        with self.documents.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT revision,body FROM project_indexes WHERE owner=?',(owner,)).fetchone()
            if (row['revision'] if row else 0) != revision:
                raise ProjectConflict('项目已在其他窗口更新，请重新载入后再整理。')
            old=json.loads(row['body']) if row else {'projects':[]}
            # Older clients only send id/name. Preserve additive project settings.
            previous={p['id']:p for p in old['projects']}
            body={**body,'projects':[{**previous.get(p['id'],{}),**p} for p in body['projects']]}
            if {p['id'] for p in old['projects']} - {p['id'] for p in body['projects']}:
                raise ProjectConflict('本切片保留已有项目及资料，不支持移除项目。')
            db.execute('INSERT INTO project_indexes VALUES(?,?,?) ON CONFLICT(owner) DO UPDATE SET revision=excluded.revision,body=excluded.body',
                       (owner,revision+1,json.dumps(body,ensure_ascii=False)))
        return {'revision':revision+1,**body}

    def scope(self, owner, project_id):
        project_id=str(UUID(str(project_id)))
        if not any(p['id']==project_id for p in self.index(owner)['projects']):
            raise KeyError('项目不存在')
        # Separate owner/project namespace, even if two owners choose the same UUID.
        return str(uuid5(NAMESPACE_URL,json.dumps(['fin-project',owner,project_id])))

    def search(self, owner, project_id, query='', offset=0, limit=50):
        scope=self.scope(owner,project_id)
        from .project_asset_versions import document_versions
        if not 0 <= offset or not 1 <= limit <= 100:
            raise ValueError('invalid_project_page')
        # Keep exact Unicode substring semantics. Only search requests inspect text;
        # browsing uses summaries and only a bounded result page is materialized.
        candidates = None
        if len(query.casefold()) >= 3:
            with self.documents.connect() as db:
                candidates = [r[0] for r in db.execute('SELECT id FROM attachments WHERE thread=? AND id IN '
                    '(SELECT object_id FROM project_text_index WHERE project_text_index MATCH ?)',
                    (scope,'"'+query.casefold().replace('"','""')+'"'))]
        active = [r['document_id'] for r in self.documents.list(scope,ids=candidates) if r['access_status']=='active'] if query else []
        with self.documents.connect() as db:
            db.create_function('casefold', 1, lambda value: (value or '').casefold(), deterministic=True)
            db.execute('BEGIN')
            if query:
                db.execute('CREATE TEMP TABLE searchable_ids(id TEXT PRIMARY KEY)')
                db.executemany('INSERT INTO searchable_ids VALUES(?)', [(i,) for i in active])
            clause = " AND (instr(casefold(name),?)>0 OR (id IN (SELECT id FROM searchable_ids) AND EXISTS(SELECT 1 FROM json_each(pages) WHERE instr(casefold(json_extract(value,'$.text')),?)>0)))" if query else ''
            args = (scope, query.casefold(), query.casefold()) if query else (scope,)
            if len(query.casefold()) >= 3:
                clause += ' AND id IN (SELECT object_id FROM project_text_index WHERE project_text_index MATCH ?)'
                args += ('"'+query.casefold().replace('"','""')+'"',)
            total = db.execute('SELECT count(*) FROM attachments WHERE thread=?'+clause, args).fetchone()[0]
            ids = [r[0] for r in db.execute('SELECT id FROM attachments WHERE thread=?'+clause+' ORDER BY rowid LIMIT ? OFFSET ?', (*args,limit,offset))]
        items=document_versions(self.documents,scope,ids=ids)
        result=[]
        for item in items:
            if item['access_status'] != 'active':
                if not query or query.casefold() in item['name'].casefold():
                    result.append({**item, 'excerpt': '', 'matched_sections': 0, 'text_status': item['access_status']})
                continue
            if not query:
                result.append({**item,'matched_sections':item['sections'],
                               'text_status':'needs_vision' if item['needs_vision'] else 'searchable',
                               'source_role':item.get('project_origin',{}).get('source_role','user_upload_unverified')})
                continue
            row=self.documents.get(scope,item['document_id'])
            sections=json.loads(row['pages'])
            matching=[s for s in sections if query.casefold() in s['text'].casefold()]
            title_match=query.casefold() in row['name'].casefold()
            if query and not matching and not title_match:
                continue
            chosen=matching or sections
            text=(chosen[0]['text'] if chosen else '')
            at=max(0,text.casefold().find(query.casefold())-100) if query else 0
            result.append({**item,'excerpt':text[at:at+600],'matched_sections':len(matching),
                           'text_status':'needs_vision' if item['needs_vision'] else 'searchable',
                           'source_role':row.get('project_origin', {}).get('source_role','user_upload_unverified')})
        return {'items':result,'query':query,'search_mode':'saved_text_substring','search_index':'sqlite_fts5_trigram' if len(query.casefold())>=3 else 'scoped_scan','total':total,
                'offset':offset,'next_offset':offset+limit if offset+limit<total else None,
                'usage':self.usage(owner,project_id)}

    def assign_new_thread(self, owner, project_id, thread_id):
        """Merge a server-created thread without overwriting concurrent UI edits."""
        with self.documents.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision,body FROM project_indexes WHERE owner=?', (owner,)).fetchone()
            body = json.loads(row['body']) if row else {}
            if not any(p['id'] == str(project_id) for p in body.get('projects', [])):
                raise ValueError('project_not_found')
            if len(body['assignments']) >= 1000:
                raise ValueError('project_assignment_limit_1000')
            body['assignments'][str(thread_id)] = str(project_id)
            db.execute('UPDATE project_indexes SET revision=?,body=? WHERE owner=?',
                       (row['revision'] + 1, json.dumps(body, ensure_ascii=False), owner))

    def detail(self, owner, project_id, document_id):
        row=self.documents.get(self.scope(owner,project_id),document_id)
        return {'document_id':row['id'],'name':row['name'],'digest':row['digest'],
                'sections':json.loads(row['pages']),'source_role':row.get('project_origin', {}).get('source_role','user_upload_unverified'),
                **({'project_origin':row['project_origin']} if row.get('project_origin') else {})}
