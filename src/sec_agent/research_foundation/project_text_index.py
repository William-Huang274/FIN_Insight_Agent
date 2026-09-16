"""SQLite FTS5 trigram candidate index; exact substring semantics remain authoritative."""
import json


def index_document(db, object_id, name, pages):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='project_text_index'").fetchone():
        return  # Task-only stores do not need a project-wide search index.
    if db.execute('SELECT 1 FROM project_text_indexed WHERE id=?',(object_id,)).fetchone():
        return
    text='\n'.join(p['text'] for p in (json.loads(pages) if isinstance(pages,str) else pages))
    db.execute('INSERT INTO project_text_index(object_id,name,text) VALUES(?,?,?)',
               (object_id,name.casefold(),text.casefold()))
    db.execute('INSERT INTO project_text_indexed VALUES(?)',(object_id,))


def ensure_index(db):
    db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS project_text_index USING fts5(object_id UNINDEXED,name,text,tokenize="trigram")')
    db.execute('CREATE TABLE IF NOT EXISTS project_text_indexed(id TEXT PRIMARY KEY)')
    for row in db.execute('SELECT id,name,pages FROM attachments WHERE id NOT IN (SELECT id FROM project_text_indexed)'):
        index_document(db,row['id'],row['name'],row['pages'])
