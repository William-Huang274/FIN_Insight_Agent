"""Disk-backed original reference for complete-source qualification only.

Build from current-authority originals, never the published navigation/lexical
indexes or candidate results under test. SQLite bounds body residency; the same
maintained navigator, rank_bm25 and cosine/RRF path compute the reference.
"""
from collections.abc import Mapping
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import zlib

from sec_agent.research_foundation.organization_source_projection import source_nodes
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest, navigate_source_nodes


class OriginalRow(Mapping):
    __slots__ = ('db', 'key', 'identity')

    def __init__(self, db, key, row):
        self.db, self.key = db, key
        self.identity = {k: row[k] for k in ('node_id', 'node_kind', 'parent_document_id',
                                           'content_sha256', 'embedding_input_sha256')}

    def payload(self):
        saved = self.db.execute('SELECT payload FROM originals WHERE position=?', (self.key,)).fetchone()
        if saved is None:
            raise ValueError('reference_original_missing')
        return json.loads(zlib.decompress(saved[0]))

    def __getitem__(self, key):
        if key in self.identity:
            return self.identity[key]
        return self.payload()[key]

    def __iter__(self):
        return iter(self.payload())

    def __len__(self):
        return len(self.payload())

    def lexical_counts(self):
        from collections import Counter
        from retrieval.query_bm25 import TokenCounts
        from retrieval.text import tokenize
        tokens = tokenize(self['content'])
        return TokenCounts(len(tokens), Counter(tokens))


def original_reference(nav, request, path):
    """Full-corpus search with bounded per-source projection/body residency.

    Scratch files remain as failure evidence; callers own their eventual cleanup.
    Nothing is returned before current authorization is checked again. A failed
    or revoked original is an error, never silently omitted from the reference.
    """
    request = SourceDocumentRequest.model_validate(request)
    if (request.source_space != 'organization' or request.operation != 'search'
            or request.entity_id or request.document_id or request.node_id
            or request.page_start is not None or request.page_end is not None):
        raise ValueError('reference_requires_full_organization_search')
    if nav.hybrid is None:
        raise ValueError('reference_requires_frozen_retriever')
    before, manifest, bindings = nav.reader._grant()
    if manifest.get('retrieval_index') is None:
        raise ValueError('reference_requires_frozen_release')
    path = Path(path)
    with path.open('xb'):
        pass
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA cache_size=-2048')
        db.execute('CREATE TABLE originals(position INTEGER PRIMARY KEY, payload BLOB NOT NULL)')
        rows, provenance = [], {}
        with db:
            for item in manifest['inputs']:
                resource = item['resource_id']
                result = nav.reader._read_storage(resource, manifest, bindings)
                if result.get('truncated') or result.get('needs_vision') or not result.get('source_bundle'):
                    raise ValueError('reference_requires_complete_source')
                document = nav._identity(item)
                origin = {'resource_id':resource, 'ref':deepcopy(item['ref']),
                    'execution_id':nav.reader.authority.execution_id,
                    'manifest_digest':nav.reader.authority.manifest_digest,
                    'source_truncated':result['truncated'],
                    'capture':{k:deepcopy(v) for k,v in (result.get('capture') or {}).items() if k != 'rows'}}
                if 'input_selection' in manifest:
                    origin['input_role'] = ('selected' if resource in
                        manifest['input_selection']['selected_resource_ids'] else 'retrieval_candidate')
                provenance[document] = origin
                url = nav.workbench_url + f"/api/v1/asset-workspace/organization-projects/{manifest['project_id']}/resources/{resource}"
                projected = source_nodes(result['source_bundle'], document, item, url)
                for row in projected:
                    if row['node_kind'] != 'text':
                        continue
                    key = len(rows)
                    raw = json.dumps(dict(row), ensure_ascii=False, separators=(',', ':')).encode()
                    db.execute('INSERT INTO originals VALUES (?,?)', (key, zlib.compress(raw, 1)))
                    rows.append(OriginalRow(db, key, row))
                del projected, result
        nav.reader._after(before)
        # No published lexical scorer or verified-candidate shortcut: body
        # tokenization and every source/vector identity are independently checked.
        def rank(*args):
            ranked, receipt = nav.hybrid.rank(*args)
            receipt['lexical_source'] = 'query_prepared'
            return ranked, receipt
        result = navigate_source_nodes(rows, request, snapshot=nav.reader.authority.manifest_digest[7:],
            allowed_space='organization', hybrid_enabled=False, ranker=rank)
        selected = {row['node_id'] for row in result.items}
        originals = {row['node_id']:row['original_source'] for row in rows if row['node_id'] in selected}
        result = nav._decorate(result, provenance, originals)
        nav.reader._after(before)
        return result
