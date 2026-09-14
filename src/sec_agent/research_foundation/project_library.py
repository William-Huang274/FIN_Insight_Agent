"""Owner-bound project organization and document copies on existing SQLite/parser.

No new retrieval service: this bounded slice searches saved text literally.
Projects do not grant access to native research threads or promote source truth.
"""
import json
from uuid import UUID, uuid5, NAMESPACE_URL

from .task_attachments import TaskAttachmentStore


class ProjectConflict(ValueError):
    pass


class ProjectLibrary:
    def __init__(self, root):
        self.documents = TaskAttachmentStore(root)
        with self.documents.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS project_indexes(owner TEXT PRIMARY KEY, revision INTEGER NOT NULL, body TEXT NOT NULL)')

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

    def search(self, owner, project_id, query=''):
        scope=self.scope(owner,project_id)
        items=self.documents.list(scope)
        result=[]
        for item in items:
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
        return {'items':result,'query':query,'search_mode':'saved_text_substring'}

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
