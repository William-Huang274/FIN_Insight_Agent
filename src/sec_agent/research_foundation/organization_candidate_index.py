"""Verified source generation and candidate-only published navigation reads.

Every original is checked on first warm-up and after any source-store change.
Subsequent queries rank metadata IDs, loading bodies only for fused candidates.
This object never grants permission: Java is checked on every operation.
"""
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import zlib

from .organization_execution_access import OrganizationExecutionUnavailable

FORMAT = 'organization-candidate-navigation.v1'


def payload(row):
    # URLs are rebuilt from the current server/project route. They are not
    # source identity and the preparation host may use a different origin.
    result = {key: row[key] for key in row if key not in {'stable_url', 'embedding_content'}}
    if 'embedding_content' in row and 'embedding_context' not in result:
        suffix = '\n' + row['content']
        if not row['embedding_content'].endswith(suffix):
            raise ValueError('organization_candidate_embedding_context_invalid')
        result['embedding_context'] = row['embedding_content'][:-len(suffix)]
    return result


def encoded(row):
    return json.dumps(payload(row), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


def build(path, nodes):
    with Path(path).open('xb'):
        pass
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('PRAGMA cache_size=-2048')
        db.execute('CREATE TABLE nodes(node_id TEXT PRIMARY KEY, payload BLOB NOT NULL)')
        for row in nodes:
            db.execute('INSERT INTO nodes VALUES (?,?)', (row['node_id'], zlib.compress(encoded(row), 1)))


class VerifiedCandidateIndex:
    def __init__(self, reader, hybrid, observer, workbench_url):
        self.reader, self.hybrid, self.observer = reader, hybrid, observer
        self.workbench_url = workbench_url
        self.generation = None
        self.rows = {}
        self.origins = {}
        self.original_reads = 0
        self.candidate_reads = 0

    def prepare(self, before, manifest, epoch):
        from .organization_hybrid_retrieval import digest
        from .organization_source_navigation import OrganizationSourceNavigation
        from .organization_source_projection import source_nodes
        key = digest(before), epoch
        if self.generation == key:
            self.check()
            self.original_reads = 0
            return
        self.generation = None
        self.rows, self.origins = {}, {}
        directory, index, _, _ = self.hybrid.load_frozen(manifest)
        if 'navigation_index' not in index:
            raise ValueError('organization_candidate_index_not_published')
        records = {record['node_id']: record for record in index['records']}
        bindings = {entry['resource_id']:entry['binding'] for entry in before['inputs']}
        allowed = {OrganizationSourceNavigation._identity(item):item for item in manifest['inputs']}
        expected = {node_id for node_id, record in records.items() if record['document_id'] in allowed}
        rows, origins = {}, {}
        self.original_reads = 0
        for document, item in allowed.items():
            result = self.reader._read_storage(item['resource_id'], manifest, bindings)
            self.original_reads += 1
            if result.get('needs_vision') or result.get('truncated') or not result.get('source_bundle'):
                raise ValueError('organization_candidate_index_requires_complete_source')
            url = self.workbench_url + f"/api/v1/asset-workspace/organization-projects/{manifest['project_id']}/resources/{item['resource_id']}"
            projected = source_nodes(result['source_bundle'], document, item, url)
            if 'graph_index' in index:
                from .organization_graph_index import verify_source
                verify_source(directory/'graph.sqlite',result['source_bundle'],document)
            for row in projected:
                if row['node_kind'] != 'text':
                    continue
                record = records.get(row['node_id'])
                if (record is None or row['node_id'] in rows or record['document_id'] != document
                        or record['navigation_sha256'] != sha256(encoded(row)).hexdigest()
                        or record['content_sha256'] != row['content_sha256']
                        or record['embedding_input_sha256'] != row['embedding_input_sha256']):
                    raise ValueError('organization_candidate_original_mismatch')
                rows[row['node_id']] = {'node_id':row['node_id'], 'parent_document_id':document,
                    'content_sha256':record['content_sha256'],
                    'embedding_input_sha256':record['embedding_input_sha256'],
                    'lexical_input_sha256':record['lexical_input_sha256'],
                    'navigation_sha256':record['navigation_sha256']}
            origin = {'resource_id':item['resource_id'], 'ref':deepcopy(item['ref']),
                'execution_id':self.reader.authority.execution_id,
                'manifest_digest':self.reader.authority.manifest_digest,
                'source_truncated':result['truncated'],
                'capture':{k:deepcopy(v) for k,v in (result.get('capture') or {}).items() if k != 'rows'}}
            if 'input_selection' in manifest:
                origin['input_role'] = ('selected' if item['resource_id'] in
                    manifest['input_selection']['selected_resource_ids'] else 'retrieval_candidate')
            origins[document] = origin
        if set(rows) != expected:
            raise ValueError('organization_candidate_population_mismatch')
        self.reader._after(before)
        self.hybrid.release_cache.check()
        if self.observer.epoch() != epoch:
            raise OrganizationExecutionUnavailable('organization_candidate_storage_changed_during_warmup')
        # No partially checked source generation becomes usable.
        self.rows, self.origins = rows, origins
        self.before, self.epoch, self.directory = before, epoch, directory
        self.generation = key

    def check(self):
        if self.generation is None or self.observer.epoch() != self.epoch:
            self.generation = None
            raise OrganizationExecutionUnavailable('organization_candidate_source_generation_changed')
        self.hybrid.release_cache.check()

    def verify_rows(self, rows, before):
        self.check()
        if before != self.before or any(self.rows.get(row['node_id']) is not row for row in rows):
            raise OrganizationExecutionUnavailable('organization_candidate_unverified_population')

    def select(self, request):
        self.check()
        if request.page_start is not None or request.page_end is not None:
            raise ValueError('organization_projection_has_no_pdf_page_locator')
        rows = list(self.rows.values())
        if request.document_id:
            if request.document_id not in self.origins:
                raise OrganizationExecutionUnavailable('所选原文不属于本次固定组织输入。')
            rows = [row for row in rows if row['parent_document_id'] == request.document_id]
        if request.node_id:
            rows = [row for row in rows if request.node_id in (row['node_id'],
                'PASSAGE::'+row['node_id']+'::'+row['content_sha256'][:16])]
            if not rows:
                raise ValueError('source_node_not_in_selected_document')
        return rows

    def materialize(self, rows, manifest):
        """Read only fused candidates; never populate a second corpus body cache."""
        self.check()
        result = []
        self.candidate_reads = 0
        uri = (self.directory/'navigation.sqlite').resolve().as_uri()+'?mode=ro'
        with closing(sqlite3.connect(uri, uri=True)) as db:
            for identity in rows:
                saved = db.execute('SELECT payload FROM nodes WHERE node_id=?', (identity['node_id'],)).fetchone()
                if saved is None:
                    raise ValueError('organization_candidate_body_missing')
                raw = zlib.decompress(saved[0])
                if sha256(raw).hexdigest() != identity['navigation_sha256']:
                    raise ValueError('organization_candidate_body_mismatch')
                row = json.loads(raw)
                if (row['node_id'] != identity['node_id']
                        or row['parent_document_id'] != identity['parent_document_id']
                        or sha256(row['content'].encode()).hexdigest() != identity['content_sha256']):
                    raise ValueError('organization_candidate_body_mismatch')
                resource = self.origins[row['parent_document_id']]['resource_id']
                row['stable_url'] = self.workbench_url + f"/api/v1/asset-workspace/organization-projects/{manifest['project_id']}/resources/{resource}"
                result.append(row)
                self.candidate_reads += 1
        self.check()
        return result
