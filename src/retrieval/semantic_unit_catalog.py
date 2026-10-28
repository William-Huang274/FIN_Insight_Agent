"""Sealed, streaming original-unit publication plan. No provider calls here."""
from collections import Counter
from contextlib import closing
from hashlib import sha256,file_digest
import json
from pathlib import Path
import sqlite3
import zlib
from .semantic_units import FORMAT,split_original


def build(path,rows):
    """rows yields (verified contextualized original node, parent vector index).

    A failed exclusive build remains unsealed. Publication cannot mistake a
    partial dry run for a complete unit set or fill missing vectors with zeros.
    """
    path=Path(path)
    with path.open('xb'):pass
    stats=Counter();max_bytes=0
    with closing(sqlite3.connect(path)) as db,db:
        db.executescript('''PRAGMA journal_mode=DELETE; PRAGMA cache_size=-2048;
            CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE parents(node TEXT PRIMARY KEY,document TEXT NOT NULL,digest TEXT NOT NULL,
                input_digest TEXT NOT NULL,vector_index INTEGER NOT NULL);
            CREATE TABLE units(position INTEGER PRIMARY KEY,id TEXT UNIQUE NOT NULL,parent TEXT NOT NULL,
                document TEXT NOT NULL,digest TEXT NOT NULL,input_digest TEXT NOT NULL,
                reuse_vector INTEGER,payload BLOB NOT NULL);
            CREATE INDEX units_by_parent ON units(parent); CREATE INDEX units_by_document ON units(document);''')
        for row,vector_index in rows:
            if type(vector_index) is not int or vector_index<0:raise ValueError('semantic_unit_parent_vector_invalid')
            db.execute('INSERT INTO parents VALUES (?,?,?,?,?)',(row['node_id'],row['parent_document_id'],
                row['content_sha256'],row['embedding_input_sha256'],vector_index))
            planned=split_original(row);stats['parents']+=1
            stats['partitioned_parents']+=len(planned)>1
            for unit in planned:
                stats['all_intervals']+=1
                if not unit['retrievable']:
                    stats['whitespace_intervals']+=1;continue
                text=unit['embedding_context']+'\n'+unit['content'];size=len(text.encode())
                max_bytes=max(size,max_bytes)
                reuse=vector_index if unit['reusable_parent_vector'] else None
                stats['reused_vectors' if reuse is not None else 'new_vectors_required']+=1
                if reuse is None:stats['new_embedding_utf8_bytes']+=size
                raw=json.dumps(unit,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                db.execute('INSERT INTO units VALUES (?,?,?,?,?,?,?,?)',(stats['retrievable_units'],unit['unit_id'],
                    unit['parent_node_id'],unit['parent_document_id'],unit['content_sha256'],
                    unit['embedding_input_sha256'],reuse,zlib.compress(raw,1)))
                stats['retrievable_units']+=1
        summary={**dict(stats),'max_embedding_utf8_bytes':max_bytes,'provider_calls':0,'format':FORMAT}
        db.execute('INSERT INTO metadata VALUES (?,?)',('summary',json.dumps(summary,sort_keys=True)))
        db.execute('INSERT INTO metadata VALUES (?,?)',('sealed',FORMAT))
    with path.open('rb') as stream:summary['catalog_sha256']=file_digest(stream,'sha256').hexdigest()
    return summary


def iter_units(path,*,require_new_vector=False):
    uri=Path(path).resolve().as_uri()+'?mode=ro'
    with closing(sqlite3.connect(uri,uri=True)) as db:
        if db.execute("SELECT value FROM metadata WHERE key='sealed'").fetchone()!=(FORMAT,):
            raise ValueError('semantic_unit_catalog_not_sealed')
        where=' WHERE reuse_vector IS NULL' if require_new_vector else ''
        for position,identifier,parent,document,digest,input_digest,reuse,packed in db.execute(
                'SELECT * FROM units'+where+' ORDER BY position'):
            unit=json.loads(zlib.decompress(packed));text=unit['embedding_context']+'\n'+unit['content']
            if (unit['unit_id']!=identifier or unit['parent_node_id']!=parent or unit['parent_document_id']!=document
                    or sha256(unit['content'].encode()).hexdigest()!=digest
                    or sha256(text.encode()).hexdigest()!=input_digest):
                raise ValueError('semantic_unit_catalog_content_mismatch')
            yield position,unit,reuse
