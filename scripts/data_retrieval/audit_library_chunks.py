"""Read-only full-corpus chunk/provenance audit; no model or source requests."""
import argparse
from collections import Counter
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from retrieval.library_chunks import MAX_BODY


def fingerprint(db, table):
    name='"'+table.replace('"','""')+'"'
    result=sha256();count=0
    primary=sorted((r[5],r[1]) for r in db.execute(f'PRAGMA table_info({name})') if r[5])
    order=','.join('"'+column.replace('"','""')+'"' for _,column in primary) if primary else 'rowid'
    for row in db.execute(f'SELECT * FROM {name} ORDER BY {order}'):
        encoded=json.dumps(tuple(row),ensure_ascii=False,separators=(',',':'),default=lambda v:bytes(v).hex()).encode()
        result.update(len(encoded).to_bytes(8,'big'));result.update(encoded);count+=1
    return {'rows':count,'sha256':result.hexdigest()}


def audit(original,candidate):
    with closing(sqlite3.connect(f'file:{Path(original).as_posix()}?mode=ro',uri=True)) as old, closing(sqlite3.connect(f'file:{Path(candidate).as_posix()}?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        tables=[r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        preserved={}
        for table in tables:
            before=fingerprint(old,table);after=fingerprint(db,table)
            if before!=after:raise ValueError('original_table_changed:'+table)
            preserved[table]=after
        counts=Counter();max_input=0
        for p in db.execute("SELECT p.* FROM passages p JOIN sources s ON s.id=p.source_id WHERE s.access_state='readable'"):
            cursor=0
            for c in db.execute('SELECT * FROM retrieval_chunks WHERE parent_id=? ORDER BY char_start',(p['id'],)):
                if c['source_id']!=p['source_id'] or p['body'][c['char_start']:c['char_end']]!=c['body']:
                    raise ValueError('child_source_or_text_mismatch:'+c['id'])
                if len(c['body'])>MAX_BODY or sha256(c['body'].encode()).hexdigest()!=c['digest']:
                    raise ValueError('child_size_or_digest_mismatch:'+c['id'])
                if p['body'][cursor:c['char_start']].strip():raise ValueError('uncovered_parent_text:'+p['id'])
                cursor=max(cursor,c['char_end']);counts['chunks']+=1;counts[c['kind']]+=1
                max_input=max(max_input,len(c['context'])+1+len(c['body']))
            if p['body'][cursor:].strip():raise ValueError('uncovered_parent_tail:'+p['id'])
            counts['parents']+=1
        # FTS UNINDEXED identity columns cannot support an indexed nested join.
        # Stream and hash both sides instead of quadratic ID probing.
        fts={r['id']:(r['source_id'],sha256((r['context']+'\0'+r['body']).encode()).hexdigest())
             for r in db.execute('SELECT id,source_id,context,body FROM chunk_search')}
        if len(fts)!=counts['chunks']:raise ValueError('fts_chunk_count_mismatch')
        for c in db.execute('SELECT id,source_id,context,body FROM retrieval_chunks'):
            if fts.pop(c['id'],None)!=(c['source_id'],sha256((c['context']+'\0'+c['body']).encode()).hexdigest()):
                raise ValueError('fts_does_not_cover_chunk:'+c['id'])
        if fts:raise ValueError('unexpected_fts_chunks')
        invalid=db.execute('SELECT count(*) FROM edge_chunk_links l JOIN retrieval_chunks c ON c.id=l.chunk_id JOIN edges e ON e.id=l.edge_id WHERE e.source_id!=c.source_id OR (l.span_start IS NOT NULL AND (l.span_start>=c.char_end OR l.span_end<=c.char_start))').fetchone()[0]
        if invalid:raise ValueError('edge_link_source_or_overlap_invalid')
        uncovered=db.execute('SELECT count(*) FROM edges e LEFT JOIN edge_chunk_coverage c ON c.edge_id=e.id WHERE c.edge_id IS NULL').fetchone()[0]
        if uncovered:raise ValueError('edge_coverage_missing')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('sqlite_integrity_failed')
        if max_input>6000:raise ValueError('rerank_input_limit_exceeded')
        return {'preserved_original_tables':preserved,'coverage':dict(counts),'max_rerank_input_characters':max_input,
                'edge_binding':dict(db.execute('SELECT status,count(*) FROM edge_chunk_coverage GROUP BY status')),
                'integrity':'ok','fts_complete':True,'all_nonwhitespace_parent_text_covered':True,
                'semantic_accuracy_evaluated':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--candidate',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=audit(a.original,a.candidate)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='preserved_original_tables'},ensure_ascii=False))


if __name__=='__main__':main()
