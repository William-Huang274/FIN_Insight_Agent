"""Immutable host-owned organization index releases; Java freezes their identity."""
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID
from threading import RLock

import numpy as np
from .organization_source_projection import PROJECTION as CHUNK_PROJECTION

FORMAT = 'organization-prepared-vectors.v2'
PROJECTION = 'organization-text-6000.v1'
PROJECTIONS = {PROJECTION, CHUNK_PROJECTION}
FIELDS = {'release_id', 'index_digest', 'matrix_sha256', 'model', 'dimensions', 'projection'}


def canonical_digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def validate_contract(contract):
    if (not isinstance(contract, dict) or set(contract) != FIELDS
            or str(UUID(contract['release_id'])) != contract['release_id']
            or contract['model'] not in {'text-embedding-v4', 'qwen3.7-text-embedding'}
            or type(contract['dimensions']) is not int or contract['dimensions'] != 1024
            or contract['projection'] not in PROJECTIONS):
        raise ValueError('organization_index_release_contract_invalid')
    for field in ('index_digest', 'matrix_sha256'):
        value = contract[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('organization_index_release_digest_invalid')
    return contract


def load_release(root, organization_id, release_id, expected=None, *, cache=None):
    if cache is not None:
        return cache.load(root, organization_id, release_id, expected)
    return _load_release(root, organization_id, release_id, expected)


def _load_release(root, organization_id, release_id, expected=None):
    """No implicit latest selection. Full integrity is checked before use."""
    org, identifier = str(UUID(organization_id)), str(UUID(release_id))
    directory = Path(root)/org/'releases'/identifier
    try:
        index = json.loads((directory/'index.json').read_bytes())
        if (index.get('format') != FORMAT or index.get('organization_id') != org
                or index.get('release_id') != identifier or index.get('projection') not in PROJECTIONS):
            raise ValueError('organization_index_release_identity_mismatch')
        contract = validate_contract({'release_id':identifier, 'index_digest':canonical_digest(index),
            **{k:index[k] for k in ('matrix_sha256', 'model', 'dimensions', 'projection')}})
        if expected is not None and contract != validate_contract(expected):
            raise ValueError('organization_index_release_frozen_version_mismatch')
        with (directory/'vectors.npy').open('rb') as stream:
            from hashlib import file_digest
            if file_digest(stream, 'sha256').hexdigest() != contract['matrix_sha256']:
                raise ValueError('organization_index_release_matrix_integrity_failure')
        if 'lexical_index' in index:
            from retrieval.published_lexical_index import FORMAT as LEXICAL_FORMAT
            lexical = index['lexical_index']
            if (set(lexical) != {'format', 'sha256', 'nodes'} or lexical['format'] != LEXICAL_FORMAT
                    or lexical['nodes'] != len(index['records'])):
                raise ValueError('organization_index_release_lexical_contract_invalid')
            if any((directory/('lexical.sqlite'+suffix)).exists() for suffix in ('-wal', '-journal')):
                raise ValueError('organization_index_release_lexical_unsealed')
            with (directory/'lexical.sqlite').open('rb') as stream:
                if file_digest(stream, 'sha256').hexdigest() != lexical['sha256']:
                    raise ValueError('organization_index_release_lexical_integrity_failure')
        if 'navigation_index' in index:
            from .organization_candidate_index import FORMAT as NAVIGATION_FORMAT
            navigation = index['navigation_index']
            if (index.get('projection') != CHUNK_PROJECTION or 'lexical_index' not in index
                    or set(navigation) != {'format', 'sha256', 'nodes'}
                    or navigation['format'] != NAVIGATION_FORMAT or navigation['nodes'] != len(index['records'])
                    or any(not all(isinstance(row.get(field), str) and len(row[field]) == 64
                        for field in ('navigation_sha256','lexical_input_sha256','embedding_input_sha256'))
                        for row in index['records'])):
                raise ValueError('organization_index_release_navigation_contract_invalid')
            if any((directory/('navigation.sqlite'+suffix)).exists() for suffix in ('-wal', '-journal')):
                raise ValueError('organization_index_release_navigation_unsealed')
            with (directory/'navigation.sqlite').open('rb') as stream:
                if file_digest(stream, 'sha256').hexdigest() != navigation['sha256']:
                    raise ValueError('organization_index_release_navigation_integrity_failure')
        if 'graph_index' in index:
            from .organization_graph_index import FORMAT as GRAPH_FORMAT
            graph=index['graph_index']
            if ('navigation_index' not in index or set(graph)!={'format','sha256','documents','edges','links'}
                    or graph['format']!=GRAPH_FORMAT
                    or any(type(graph[k]) is not int or graph[k]<0 for k in ('documents','edges','links'))):
                raise ValueError('organization_graph_release_contract_invalid')
            if any((directory/('graph.sqlite'+suffix)).exists() for suffix in ('-wal','-journal')):
                raise ValueError('organization_graph_release_unsealed')
            with (directory/'graph.sqlite').open('rb') as stream:
                if file_digest(stream,'sha256').hexdigest()!=graph['sha256']:
                    raise ValueError('organization_graph_release_integrity_failure')
        matrix = np.load(directory/'vectors.npy', mmap_mode='r', allow_pickle=False)
        records = index['records']
        if (matrix.dtype != np.float32 or matrix.shape != (len(records), 1024)
                or len({r['node_id'] for r in records}) != len(records)
                or any(type(r['vector_index']) is not int for r in records)
                or sorted(r['vector_index'] for r in records) != list(range(len(records)))):
            raise ValueError('organization_index_release_shape_mismatch')
        return directory, index, matrix, contract
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('organization_index_release_unavailable') from None


class ReleaseLoadCache:
    """One verified host-owned release, not an authorization cache.

    Immutable publication is the storage contract. File identities before and
    after every use detect ordinary replacement, mutation, deletion and races;
    full hashes remain mandatory on first load. This is not protection against
    a malicious host able to forge filesystem metadata or mutate this process.
    Never rewrite a published release, even while the service is stopped.
    """
    def __init__(self):
        self._lock = RLock()
        self._entry = None

    @staticmethod
    def _signature(directory):
        values = []
        for name in ('index.json', 'vectors.npy', 'lexical.sqlite', 'navigation.sqlite', 'graph.sqlite'):
            path = directory/name
            try:
                stat = path.stat()
            except FileNotFoundError:
                if name in {'lexical.sqlite', 'navigation.sqlite', 'graph.sqlite'}:
                    values.append(None)
                    continue
                raise ValueError('organization_index_release_unavailable') from None
            values.append((stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        # A published SQLite artifact is sealed, never a WAL database. Reject
        # journals so a base-file digest cannot hide unvalidated sidecar writes.
        if any((directory/('lexical.sqlite'+suffix)).exists() for suffix in ('-wal', '-journal')):
            raise ValueError('organization_index_release_lexical_unsealed')
        if any((directory/('navigation.sqlite'+suffix)).exists() for suffix in ('-wal', '-journal')):
            raise ValueError('organization_index_release_navigation_unsealed')
        if any((directory/('graph.sqlite'+suffix)).exists() for suffix in ('-wal', '-journal')):
            raise ValueError('organization_graph_release_unsealed')
        return tuple(values)

    def check(self):
        with self._lock:
            if self._entry is None:
                raise ValueError('organization_index_release_not_loaded')
            _, signature, value = self._entry
            if self._signature(value[0]) != signature:
                self._entry = None
                raise ValueError('organization_index_release_changed_after_load')

    def load(self, root, organization_id, release_id, expected):
        if expected is None:
            raise ValueError('organization_index_cache_requires_frozen_contract')
        validate_contract(expected)
        directory = Path(root).resolve()/str(UUID(organization_id))/'releases'/str(UUID(release_id))
        key = (str(directory), tuple(sorted(expected.items())))
        with self._lock:
            if self._entry is not None and self._entry[0] == key:
                self.check()
                directory, index, _, contract = self._entry[2]
                return directory, index, np.load(directory/'vectors.npy', mmap_mode='r', allow_pickle=False), contract
            # New releases never inherit another release's verification. Failed
            # warm-up does not publish a partially validated value.
            self._entry = None
            before = self._signature(directory)
            value = _load_release(root, organization_id, release_id, expected)
            if self._signature(directory) != before:
                raise ValueError('organization_index_release_changed_during_load')
            # Do not retain a corpus-sized mapped working set between calls.
            # Reopening an already verified read-only mapping is cheap; the
            # immutable index metadata, not the mapped pages, is cached.
            self._entry = key, before, (value[0], value[1], None, value[3])
            return value


def verify_release_inputs(workspace, org, inputs, contract, root, research_as_of):
    from .organization_source_navigation import OrganizationSourceNavigation
    from .project_source_captures import validate_metric_cutoff, financial_capture_text
    _, index, matrix, _ = load_release(root, org, contract['release_id'], contract)
    expected = {}
    for item in inputs:
        ref = item['binding']['ref']
        result = workspace.read_source('organization:'+org, ref)
        if result['version']['ref'] != ref or result.get('truncated') or result.get('needs_vision'):
            raise ValueError('organization_index_requires_complete_original')
        capture = result.get('capture') or {}
        validate_metric_cutoff(capture, research_as_of)
        document = OrganizationSourceNavigation._identity({'resource_id':item['resource_id'], 'ref':ref})
        if result.get('source_bundle'):
            from .organization_source_projection import source_nodes, validate_source_cutoff
            if contract['projection'] != CHUNK_PROJECTION:
                raise ValueError('organization_complete_source_requires_chunk_projection')
            validate_source_cutoff(result['source_bundle'], research_as_of)
            for row in source_nodes(result['source_bundle'], document, {'ref':ref,'title':item.get('title','')}, 'http://localhost'):
                if row['node_kind'] == 'text':
                    expected[row['node_id']] = (document, row['content_sha256'], row['embedding_input_sha256'])
            continue
        text = financial_capture_text(capture) if capture.get('kind') == 'financial' else result['text']
        if not text.strip() or len(text) > 100000:
            raise ValueError('organization_index_projection_not_supported')
        for position, start in enumerate(range(0, len(text), 6000)):
            node = document.replace('ORGDOC::','ORGSECTION::')+f':{position}:leaf'
            expected[node] = (document, sha256(text[start:start+6000].encode()).hexdigest(), None)
    actual = {r['node_id']:(r['document_id'], r['content_sha256'], r.get('embedding_input_sha256')) for r in index['records']}
    if actual != expected:
        raise ValueError('organization_index_original_projection_mismatch')
    from .organization_vector_math import unit_vectors
    if not unit_vectors(matrix):
        raise ValueError('organization_index_invalid_prepared_vectors')


class ConfiguredQuerySource:
    """Explicit server opt-in. Nothing in a model tool can select a provider URL."""
    def __init__(self, root):
        self.root = Path(root)

    def embed(self, query, *, scope, index_digest, model, dimensions):
        import os
        from contextlib import closing
        from retrieval.query_embeddings import QueryEmbeddingSource
        from retrieval.qwen_api import QwenRetrieval
        if os.getenv('FINSIGHT_ORGANIZATION_QUERY_EMBEDDING') != 'qwen' or not os.getenv('QWEN_API_KEY'):
            raise ValueError('organization_query_embedding_not_configured')
        # Per-query lifetime; the durable cache owns concurrency and failed receipts.
        with closing(QwenRetrieval(os.environ['QWEN_API_KEY'], embedding_model=model)) as api:
            return QueryEmbeddingSource(self.root, api, model=model, dimensions=dimensions,
                                        wait_inflight_seconds=45).embed(
                query, scope=scope, index_digest=index_digest, model=model, dimensions=dimensions)
