"""Verified source generation and candidate-only published navigation reads.

Each immutable source is checked once per content revision and projection code.
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
    def __init__(self, reader, hybrid, observer, workbench_url, *, preparation_cancel=None):
        self.reader, self.hybrid, self.observer = reader, hybrid, observer
        self.workbench_url = workbench_url
        self.generation = None
        self.rows = {}
        self.origins = {}
        self.source_metadata = {}
        self.original_source_metadata = {}
        self.original_reads = 0
        self.candidate_reads = 0
        self.neighbors = {}
        self.window_neighbors = {}
        self.structures = {}
        self.locations = {}
        self.verification_hits = 0
        self.preparation_cancel = preparation_cancel

    def _check_cancelled(self):
        if self.preparation_cancel is not None and self.preparation_cancel():
            raise OrganizationExecutionUnavailable('organization_retrieval_cancelled')

    def prepare(self, before, manifest, epoch):
        from filelock import FileLock
        from .source_verification_cache import PendingSourceReceipts
        self._check_cancelled()
        from .organization_hybrid_retrieval import digest
        # SQLite owns receipts; a maintained OS file lock serializes cold
        # verification across workers. A timeout never starts a second scan.
        lock_key = digest([str(self.observer.path), manifest['organization_id'],
                           manifest['retrieval_index']['release_id']])
        with FileLock(str(self.hybrid.root/f'.source-verify-{lock_key}.lock'), timeout=60), PendingSourceReceipts() as pending:
            self._prepare(before, manifest, epoch, pending)

    def _prepare(self, before, manifest, epoch, pending):
        self._check_cancelled()
        from .organization_hybrid_retrieval import digest
        from .organization_source_navigation import OrganizationSourceNavigation
        from .organization_source_projection import source_nodes
        key = digest(before), epoch
        if self.generation == key:
            self.check()
            self.original_reads = 0
            return
        self.generation = None
        self.rows, self.origins, self.source_metadata = {}, {}, {}
        self.original_source_metadata = {}
        directory, index, _, _ = self.hybrid.load_frozen(manifest)
        if 'navigation_index' not in index:
            raise ValueError('organization_candidate_index_not_published')
        records = {record['node_id']: record for record in index['records']}
        bindings = {entry['resource_id']:entry['binding'] for entry in before['inputs']}
        allowed = {OrganizationSourceNavigation._identity(item):item for item in manifest['inputs']}
        expected = {node_id for node_id, record in records.items() if record['document_id'] in allowed}
        rows, origins, metadata, original_metadata, neighbors = {}, {}, {}, {}, {}
        structures, window_neighbors, locations = {}, {}, {}
        self.original_reads = 0
        self.verification_hits = 0
        from .source_verification_cache import SourceVerificationCache, versions
        proofs = SourceVerificationCache(self.hybrid.root)
        revision = versions(self.observer)
        from collections import defaultdict
        by_space = defaultdict(set)
        for item in allowed.values():
            by_space[item['ref']['project_id']].add(item['ref']['version_id'])
        current_versions = {space: self.reader.workspace.document_version_batch(
            'organization:'+manifest['organization_id'], space, sorted(ids))
            for space, ids in by_space.items()}
        from .prepared_source_metadata import prepare as prepare_metadata, restore as restore_metadata
        for document, item in allowed.items():
            self._check_cancelled()
            proof_key = proofs.key(revision, item, manifest)
            saved = proofs.get(proof_key)
            if saved is not None:
                # This is a content proof, never a current local/Java grant.
                version = current_versions[item['ref']['project_id']][item['ref']['version_id']]
                if version['access_status'] != 'active':
                    raise OrganizationExecutionUnavailable('organization_candidate_current_local_access_denied')
                if version != saved['version'] or version['ref'] != item['ref']:
                    saved = None
            if saved is None:
                result = self.reader._read_storage(item['resource_id'], manifest, bindings)
                self._check_cancelled()
                self.original_reads += 1
                if result.get('needs_vision') or result.get('truncated') or not result.get('source_bundle'):
                    raise ValueError('organization_candidate_index_requires_complete_source')
                from .organization_source_filter import source_metadata, original_source_metadata
                url = self.workbench_url + f"/api/v1/asset-workspace/organization-projects/{manifest['project_id']}/resources/{item['resource_id']}"
                projected = source_nodes(result['source_bundle'], document, item, url)
                from retrieval.source_structure import organization_structure
                structure = organization_structure(result['source_bundle'], document)
                if 'graph_index' in index:
                    from .organization_graph_index import verify_source
                    verify_source(directory/'graph.sqlite', result['source_bundle'], document)
                saved = {'version': result['version'], 'metadata': source_metadata(result['source_bundle']),
                    'original_metadata': original_source_metadata(result['source_bundle']),
                    'capture': {k:deepcopy(v) for k,v in (result.get('capture') or {}).items() if k != 'rows'},
                    'nodes': [], 'locations': [], 'structures':structure}
                for row in projected:
                    if row['node_kind'] != 'text':
                        continue
                    record = records.get(row['node_id'])
                    if (record is None or record['document_id'] != document
                            or record['navigation_sha256'] != sha256(encoded(row)).hexdigest()
                            or record['content_sha256'] != row['content_sha256']
                            or record['embedding_input_sha256'] != row['embedding_input_sha256']):
                        raise ValueError('organization_candidate_original_mismatch')
                    saved['nodes'].append(row['node_id'])
                    origin = row['original_source']
                    start = origin.get('source_char_start', origin.get('char_start'))
                    end = origin.get('source_char_end', origin.get('char_end'))
                    parent = origin.get('original_node_id') if 'source_char_start' not in origin else document
                    if type(start) is int and type(end) is int and parent and 0 <= start < end:
                        saved['locations'].append([parent, start, end, row['node_id']])
                saved = prepare_metadata(saved)
                pending.append((proof_key, saved))
            else:
                self.verification_hits += 1
            metadata[document], original_metadata[document] = saved['metadata'], saved['original_metadata']
            # Restore verified compressed blocks directly, not a full decode /
            # recompress of the whole corpus on every process/session start.
            structures[document], locations[document], links, windows = restore_metadata(saved)
            neighbors.update(links)
            if self.hybrid.candidate_policy in {'needs_window.v2', 'needs_window.v3', 'needs_window.v4'}:
                window_neighbors.update(windows)
            scope_complete = set(saved.get('evidence_scope_complete', []))
            for node_id in saved['nodes']:
                record = records.get(node_id)
                if record is None or node_id in rows or record['document_id'] != document:
                    raise ValueError('organization_candidate_original_mismatch')
                rows[node_id] = {'node_id':node_id, 'parent_document_id':document,
                    'content_sha256':record['content_sha256'],
                    'embedding_input_sha256':record['embedding_input_sha256'],
                    'lexical_input_sha256':record['lexical_input_sha256'],
                    'navigation_sha256':record['navigation_sha256']}
                rows[node_id]['evidence_scopes'] = saved.get('evidence_scopes', {}).get(node_id, [])
                rows[node_id]['period_evidence'] = saved.get('period_evidence', {}).get(node_id, [])
                rows[node_id]['evidence_scope_complete'] = node_id in scope_complete
                rows[node_id]['source_interval'] = saved['source_intervals'].get(node_id)
            origin = {'resource_id':item['resource_id'], 'ref':deepcopy(item['ref']),
                'execution_id':self.reader.authority.execution_id,
                'manifest_digest':self.reader.authority.manifest_digest,
                'source_truncated':False, 'capture':deepcopy(saved['capture'])}
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
        for proof_key, saved in pending:
            self._check_cancelled()
            proofs.put(proof_key, saved)
        self._check_cancelled()
        # No partially checked source generation becomes usable.
        self.rows, self.origins = rows, origins
        self.source_metadata = metadata
        self.original_source_metadata = original_metadata
        self.neighbors = neighbors
        self.window_neighbors = window_neighbors
        self.structures = structures
        self.locations = locations
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

    def contextualize(self, rows, manifest):
        """Attach exact adjacent readbacks, never replace an immutable chunk.

        Context is loaded only for incomplete fragments, from this verified
        generation. Same-document/source offsets were checked at publication
        verification. Citation identity and original vector input stay intact.
        """
        from retrieval.fragment_context import needs_context, attach_context
        wanted = {r['node_id']: self.neighbors.get(r['node_id'], []) for r in rows if needs_context(r['content'])}
        ids = list(dict.fromkeys(n for adjacent in wanted.values() for n in adjacent))
        before_reads = self.candidate_reads
        neighbors = self.materialize([self.rows[n] for n in ids], manifest) if ids else []
        if ids:
            self.candidate_reads += before_reads
        by_id = {r['node_id']:r for r in neighbors}
        result = [attach_context(r, [by_id[n] for n in wanted[r['node_id']]])
                  if r['node_id'] in wanted else dict(r) for r in rows]
        selected_structures = {}
        for row in result:
            document = row['parent_document_id']
            if document not in selected_structures:
                selected_structures[document] = json.loads(zlib.decompress(self.structures[document]))
            row['source_structure'] = selected_structures[document][row['node_id']]
        return result

    def complete_tables(self, rows, eligible, manifest, *, independent_candidates=False):
        """Business scope selects anchors; authorization bounds exact context.

        A trusted same-table header need not independently match the business
        query. Its original must still be part of this verified current grant.
        Supplemental ranges never become independently ranked candidates.
        """
        from retrieval.table_completion import complete_tables, read_span
        permitted = {r['node_id'] for r in eligible}
        documents = {r['parent_document_id'] for r in eligible}
        before = self.reader._grant()[0]
        loaded = {}
        def load(anchor, span):
            document = anchor['parent_document_id']
            if document not in documents or anchor['node_id'] not in permitted:
                raise OrganizationExecutionUnavailable('table_completion_outside_current_scope')
            coordinate_space=anchor['original_source'].get('original_node_id',document)
            positions = [(a,b,n) for p,a,b,n in json.loads(zlib.decompress(self.locations[document]))
                         if p==coordinate_space and n in self.rows
                         and self.rows[n]['parent_document_id']==document]
            def node(identifier):
                self.reader._after(before)
                if identifier not in loaded:
                    previous = self.candidate_reads
                    loaded[identifier] = self.materialize([self.rows[identifier]],manifest)[0]
                    self.candidate_reads += previous
                return loaded[identifier]
            value = read_span(anchor,span,positions,node)
            self.reader._after(before);self.check()
            return value
        result, receipt = complete_tables(rows,load,top_k=len(rows),independent_candidates=independent_candidates)
        self.reader._after(before);self.check()
        return result, receipt
