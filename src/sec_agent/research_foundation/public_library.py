"""Read the operator-published public-source snapshot, using existing node contracts.

No user-upload promotion, mutable report evidence, or new retrieval engine.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


def library_path(attachments_root):
    return Path(attachments_root) / 'public-library' / 'retrieval_nodes.jsonl'


@lru_cache(maxsize=4)
def _read(path, modified, size):
    body = Path(path).read_bytes()
    rows = tuple(json.loads(line) for line in body.decode('utf-8').splitlines() if line.strip())
    return rows, sha256(body).hexdigest()


def library_nodes(attachments_root, as_of='9999-12-31'):
    path = library_path(attachments_root)
    if not path.is_file():
        return (), ''
    stat = path.stat()
    rows, digest = _read(str(path), stat.st_mtime_ns, stat.st_size)
    return tuple(r for r in rows if str(r.get('publication_date','9999')) <= as_of), digest


def document_catalog(rows):
    docs = {}
    for row in rows:
        identity = row['parent_document_id']
        if identity not in docs:
            docs[identity] = {k: row.get(k) for k in ('title','ticker','company','fiscal_period',
                'period_end','publication_date','source_role','stable_url','document_kind')}
            docs[identity].update(document_id=identity, sections=0, passages=0, preview='')
        doc = docs[identity]
        doc['sections' if row.get('node_kind') == 'section' else 'passages'] += 1
        if not doc['preview'] and row.get('node_kind') != 'section':
            doc['preview'] = str(row.get('content',''))[:320]
    return sorted(docs.values(), key=lambda d: (str(d['ticker']), str(d['publication_date'])), reverse=True)
