"""Immutable child retrieval units and source-bound graph evidence projection.

Original passages are never rewritten. All offsets are Python character offsets
into that exact parent. Heading/table context is navigation, not extra evidence.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from langchain_text_splitters import RecursiveCharacterTextSplitter

VERSION = 'library-chunks.v1'
MAX_BODY = 4200
OVERLAP = 240
SCHEMA = '''
CREATE TABLE retrieval_chunks(
 id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES sources(id),
 parent_id TEXT NOT NULL REFERENCES passages(id),ordinal INTEGER NOT NULL,
 char_start INTEGER NOT NULL,char_end INTEGER NOT NULL,body TEXT NOT NULL,
 digest TEXT NOT NULL,locator TEXT NOT NULL,context TEXT NOT NULL,
 kind TEXT NOT NULL,flags TEXT NOT NULL);
CREATE INDEX retrieval_chunks_parent ON retrieval_chunks(parent_id,char_start);
CREATE INDEX retrieval_chunks_source ON retrieval_chunks(source_id);
CREATE VIRTUAL TABLE chunk_search USING fts5(id UNINDEXED,source_id UNINDEXED,context,body);
CREATE TABLE edge_chunk_links(
 edge_id TEXT NOT NULL REFERENCES edges(id),chunk_id TEXT NOT NULL REFERENCES retrieval_chunks(id),
 binding TEXT NOT NULL,evidence_index INTEGER NOT NULL,span_start INTEGER,span_end INTEGER,
 PRIMARY KEY(edge_id,chunk_id,evidence_index));
CREATE INDEX edge_chunk_links_chunk ON edge_chunk_links(chunk_id);
CREATE TABLE edge_chunk_coverage(edge_id TEXT PRIMARY KEY REFERENCES edges(id),status TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE retrieval_chunk_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
'''


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def split_parent(parent, title):
    body = parent['body']
    # Explicit document headings only. Do not interpret arbitrary financial row
    # labels/capitalized lines as sections. No headings means inherited locator.
    heads = list(re.finditer(r'(?m)^(?:#{1,6}\s+[^\n]{1,160}|(?:PART\s+[IVX]+|ITEM\s+\d+[A-Z]?)[. :\t]+[^\n]{0,130}|第[一二三四五六七八九十\d]+[章节][^\n]{0,130})\s*$', body))
    boundaries = sorted(set([0, *[m.start() for m in heads], len(body)]))
    splitter = RecursiveCharacterTextSplitter(chunk_size=MAX_BODY, chunk_overlap=OVERLAP,
        separators=['\n\n', '\n', '. ', '。', '; ', ' ', ''],
        keep_separator=True, strip_whitespace=False, add_start_index=True)
    ordinal = 0
    for lo, hi in zip(boundaries, boundaries[1:]):
        heading = next((m.group().strip() for m in reversed(heads) if m.start() <= lo), '')
        section = body[lo:hi]
        for doc in splitter.create_documents([section]):
            start = lo + doc.metadata['start_index']
            text = doc.page_content
            if not text.strip():
                continue
            end = start + len(text)
            if start < lo or body[start:end] != text or len(text) > MAX_BODY:
                raise ValueError('chunk_offset_or_size_invalid:' + parent['id'])
            flags = []
            table_header = ''
            # A Markdown table may be split into row groups. Repeat its actual
            # header in context; preserve untouched row text in the child body.
            previous = body[lo:start]
            table_matches = list(re.finditer(r'(?m)^([^\n]*\|[^\n]*)\n([ :|\-]+)\n', previous))
            if table_matches:
                last = table_matches[-1]
                after = previous[last.end():]
                if all(not line.strip() or '|' in line for line in after.splitlines()):
                    table_header = last.group()[:400]
                    flags.append('table_header_in_context')
            kind = 'table_rows' if table_header or re.search(r'(?m)^\s*\|.*\|\s*$', text) else 'text'
            if body.lstrip().startswith(('{','[')) and not heads:
                kind = 'structured_text'
                flags.append('raw_serialized_data_not_article')
            if kind == 'table_rows':
                flags.append('consult_parent_for_table_footnotes')
            if not heads:
                flags.append('inherited_parent_locator')
            if len(text) == MAX_BODY:
                flags.append('hard_boundary_possible_long_row')
            context = '\n'.join(x for x in [title[:300], parent['locator'][:250], heading[:180], table_header] if x)
            digest = sha256(text.encode()).hexdigest()
            cid = 'CHUNK::' + sha256(encoded([VERSION,parent['id'],start,end,digest]).encode()).hexdigest()[:40]
            yield dict(id=cid,source_id=parent['source_id'],parent_id=parent['id'],ordinal=ordinal,
                char_start=start,char_end=end,body=text,digest=digest,
                locator=f"{parent['locator']} / chars {start}:{end}",context=context,kind=kind,flags=encoded(flags))
            ordinal += 1


def quote_spans(body, evidence):
    quote = str(evidence.get('quote') or '')
    start, end = evidence.get('start'), evidence.get('end')
    if quote and isinstance(start,int) and isinstance(end,int) and body[start:end] == quote:
        return [(start,end,'exact_quote')]
    if not quote:
        return []
    for candidate in dict.fromkeys([quote,quote.replace('\\n','\n')]):
        matches = [(m.start(),m.end(),'exact_quote') for m in re.finditer(re.escape(candidate),body)]
        if matches:
            return matches
    # Ignore whitespace only; never fuzzy-match numbers, punctuation or names.
    pattern = r'\s+'.join(re.escape(p) for p in quote.replace('\\n','\n').split())
    return [(m.start(),m.end(),'whitespace_quote') for m in re.finditer(pattern,body)] if pattern else []


def bind_edges(db):
    parents = {r['id']:dict(r) for r in db.execute('SELECT id,source_id,locator FROM passages')}
    by_locator = defaultdict(list)
    for p in parents.values():
        by_locator[(p['source_id'],p['locator'])].append(p['id'])
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assertions = {r['id']:json.loads(r['payload']) for r in db.execute('SELECT id,payload FROM relationship_assertions')} if 'relationship_assertions' in tables else {}
    counts = Counter()
    for edge in db.execute('SELECT * FROM edges').fetchall():
        qualifier = json.loads(edge['qualifiers'])
        evidence = assertions.get(edge['id'],{}).get('evidence',[]) or qualifier.get('evidence',[])
        if isinstance(evidence,dict): evidence=[evidence]
        links, issues = [], []
        if evidence:
            for i, e in enumerate(evidence):
                pid = e.get('passage_id') or e.get('node_id')
                parent = parents.get(pid)
                if not parent or parent['source_id'] != edge['source_id']:
                    issues.append({'evidence_index':i,'reason':'parent_identity_mismatch'});continue
                body = db.execute('SELECT body FROM passages WHERE id=?',(pid,)).fetchone()[0]
                spans = quote_spans(body,e)
                if not spans:
                    issues.append({'evidence_index':i,'reason':'quote_not_located','parent_id':pid});continue
                for start,end,binding in spans:
                    children = db.execute('SELECT id,char_start,char_end FROM retrieval_chunks WHERE parent_id=? AND char_start<? AND char_end>?',(pid,end,start)).fetchall()
                    for child in children:
                        links.append((edge['id'],child['id'],binding,i,start,end))
                    if not children:issues.append({'evidence_index':i,'reason':'source_not_readable_or_child_missing'})
        else:
            pid = qualifier.get('source_passage_id')
            pids = [pid] if pid in parents and parents[pid]['source_id']==edge['source_id'] else by_locator.get((edge['source_id'],edge['locator']),[])
            for pid in pids:
                for child in db.execute('SELECT id,char_start,char_end FROM retrieval_chunks WHERE parent_id=?',(pid,)):
                    links.append((edge['id'],child['id'],'parent_locator_only',0,None,None))
            if not links: issues.append({'reason':'document_only_locator_unresolved'})
        db.executemany('INSERT OR IGNORE INTO edge_chunk_links VALUES(?,?,?,?,?,?)',links)
        status = 'partial' if issues and links else 'unresolved' if issues or not links else 'quote_bound' if evidence else 'parent_locator_bound'
        payload = {'issues':issues,'linked_chunks':len({r[1] for r in links}),
                   'relationship_status':edge['status'],'semantic_review_changed':False}
        db.execute('INSERT INTO edge_chunk_coverage VALUES(?,?,?)',(edge['id'],status,encoded(payload)))
        counts[status] += 1
    return dict(counts)


def build_chunks(path):
    """Caller supplies an unpublished SQLite copy. Original tables stay intact."""
    with closing(sqlite3.connect(path)) as db:
        db.row_factory=sqlite3.Row
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='retrieval_chunks'").fetchone():
            raise ValueError('chunk_index_already_exists_build_new_version')
        db.executescript(SCHEMA)
        count=0; parents=0; length=0
        with db:
            for parent in db.execute("SELECT p.*,s.title FROM passages p JOIN sources s ON s.id=p.source_id WHERE s.access_state='readable' ORDER BY p.rowid"):
                rows=list(split_parent(dict(parent),parent['title']))
                db.executemany('INSERT INTO retrieval_chunks VALUES(:id,:source_id,:parent_id,:ordinal,:char_start,:char_end,:body,:digest,:locator,:context,:kind,:flags)',rows)
                db.executemany('INSERT INTO chunk_search VALUES(:id,:source_id,:context,:body)',rows)
                count+=len(rows);parents+=1;length+=sum(len(r['body'])+len(r['context'])+1 for r in rows)
                if parents % 5000 == 0:print(encoded({'parents':parents,'chunks':count}),flush=True)
            bindings=bind_edges(db)
            report={'version':VERSION,'parents':parents,'chunks':count,'embedding_characters':length,
                    'max_body_characters':MAX_BODY,'overlap_characters':OVERLAP,'edge_binding':bindings}
            db.execute('INSERT INTO retrieval_chunk_metadata VALUES(?,?)',('contract',encoded(report)))
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('chunk_database_integrity_failed')
        return report


def has_chunks(library):
    return bool(library._query("SELECT 1 FROM sqlite_master WHERE name='retrieval_chunks'"))


def edge_evidence(library, edge_id, limit=8):
    rows=library._query('SELECT c.id,c.source_id,c.parent_id,c.locator,c.digest,c.char_start,c.char_end,l.binding,l.evidence_index,l.span_start,l.span_end FROM edge_chunk_links l JOIN retrieval_chunks c ON c.id=l.chunk_id WHERE l.edge_id=? ORDER BY l.evidence_index,c.parent_id,c.char_start LIMIT ?', (edge_id,limit))
    coverage=library._query('SELECT status,payload FROM edge_chunk_coverage WHERE edge_id=?',(edge_id,))
    return rows,({'status':coverage[0]['status'],**json.loads(coverage[0]['payload'])} if coverage else {'status':'dynamic_relation_document_readback_required'})


def edge_evidence_batch(library, edge_ids, limit=8):
    """Same per-edge evidence window as edge_evidence, in bounded SQL batches."""
    ids = list(dict.fromkeys(edge_ids))
    result = {eid: ([], {'status':'dynamic_relation_document_readback_required'}) for eid in ids}
    for start in range(0, len(ids), 400):
        batch = ids[start:start+400]
        marks = ','.join('?' for _ in batch)
        rows = library._query('SELECT * FROM (SELECT l.edge_id,c.id,c.source_id,c.parent_id,c.locator,c.digest,'
            'c.char_start,c.char_end,l.binding,l.evidence_index,l.span_start,l.span_end,'
            'row_number() OVER (PARTITION BY l.edge_id ORDER BY l.evidence_index,c.parent_id,c.char_start) AS position '
            'FROM edge_chunk_links l JOIN retrieval_chunks c ON c.id=l.chunk_id '
            f'WHERE l.edge_id IN ({marks})) WHERE position<=? ORDER BY edge_id,position', (*batch, limit))
        for row in rows:
            eid = row.pop('edge_id'); row.pop('position')
            result[eid][0].append(row)
        for row in library._query(f'SELECT edge_id,status,payload FROM edge_chunk_coverage WHERE edge_id IN ({marks})', batch):
            result[row['edge_id']] = (result[row['edge_id']][0], {'status':row['status'], **json.loads(row['payload'])})
    return result


def add_reviewed_bindings(db,records,reviewer):
    """Supplement legacy document-only locators on a new unpublished copy."""
    if not reviewer:raise ValueError('binding_reviewer_required')
    db.execute('CREATE TABLE IF NOT EXISTS edge_chunk_binding_reviews(edge_id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
    for record in records:
        edge=db.execute('SELECT source_id FROM edges WHERE id=?',(record['edge_id'],)).fetchone()
        if not edge or edge['source_id']!=record['source_id']:raise ValueError('review_edge_source_mismatch')
        links=[]
        for i,e in enumerate(record['evidence']):
            parent=db.execute('SELECT source_id,body FROM passages WHERE id=?',(e['passage_id'],)).fetchone()
            if not parent or parent['source_id']!=edge['source_id']:raise ValueError('review_parent_source_mismatch')
            spans=quote_spans(parent['body'],e)
            if len(spans)!=1:raise ValueError('review_quote_missing_or_ambiguous')
            start,end,binding=spans[0]
            for child in db.execute('SELECT id FROM retrieval_chunks WHERE parent_id=? AND char_start<? AND char_end>?',(e['passage_id'],end,start)):
                links.append((record['edge_id'],child['id'],binding,i,start,end))
        if not links:raise ValueError('review_no_child_evidence')
        db.executemany('INSERT OR IGNORE INTO edge_chunk_links VALUES(?,?,?,?,?,?)',links)
        db.execute('INSERT INTO edge_chunk_binding_reviews VALUES(?,?)',(record['edge_id'],encoded({**record,'reviewer':reviewer})))
        db.execute('UPDATE edge_chunk_coverage SET status=?,payload=? WHERE edge_id=?',('quote_bound',encoded({'issues':[],
           'linked_chunks':len({l[1] for l in links}),'binding_review':reviewer,'semantic_review_changed':False}),record['edge_id']))
