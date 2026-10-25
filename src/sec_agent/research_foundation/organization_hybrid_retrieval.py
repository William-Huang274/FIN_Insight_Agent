"""Explicit prepared vectors, current Java authorization, and scoped ID caches.

New queries require an explicitly configured, audited embedding source and a
frozen release. No automatic corpus preparation, public-library fallback or
positive permission cache. NumPy ranks cosine; navigation owns BM25/readback.
Prepared files are host-owned artifacts, never supplied in Agent tool arguments.
"""
from hashlib import sha256
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from uuid import UUID

import numpy as np

from .organization_execution_access import OrganizationExecutionUnavailable

POLICY = 'organization-cosine-bm25-rrf.v1'
FORMAT = 'organization-prepared-vectors.v1'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def vector(value, dimensions):
    result = np.asarray(value, dtype=np.float32)
    if result.shape != (dimensions,) or not np.isfinite(result).all():
        raise ValueError('organization_retrieval_invalid_vector')
    magnitude = np.linalg.norm(result.astype(np.float64))
    if not np.isfinite(magnitude) or magnitude == 0:
        raise ValueError('organization_retrieval_invalid_vector')
    return (result / magnitude).astype(np.float32)


def preparation_nodes(reader, *, workbench_url):
    """Read exact projected leaf text through the same current-authority path.

    Host preparation utility, never a model tool or implicit embedding job.
    """
    from .organization_source_navigation import OrganizationSourceNavigation
    before, manifest, _ = reader._grant()
    nav = OrganizationSourceNavigation(reader, workbench_url=workbench_url)
    nodes = []
    by_resource = {item['resource_id']: item for item in manifest['inputs']}
    def project(resource_id, result):
        item = by_resource[resource_id]
        document = nav._identity(item)
        if result.get('source_bundle'):
            from .organization_source_projection import source_nodes
            return [row for row in source_nodes(result['source_bundle'], document, item, workbench_url)
                    if row['node_kind'] == 'text']
        projected = []
        offset = 0
        while True:
            outline = nav.navigate({'source_space':'organization', 'operation':'outline',
                'document_id':document, 'offset':offset})
            for section in outline.items:
                node_id = section['node_id'] + ':leaf'
                result = nav.navigate({'source_space':'organization', 'operation':'read',
                    'document_id':document, 'node_id':node_id, 'max_characters':16000})
                passage = result.items[0]
                if passage['result_state'] != 'source_bound_passage' or passage.get('truncated'):
                    raise ValueError('organization_retrieval_requires_complete_projection')
                projected.append({'node_id':node_id, 'parent_document_id':document, 'node_kind':'text',
                    'content':passage['passage'], 'content_sha256':passage['content_sha256']})
            if outline.next_offset is None:
                break
            offset = outline.next_offset
        return projected
    for projected in reader._project_sources(by_resource, project):
        nodes.extend(projected)
    reader._after(before)
    return manifest['organization_id'], nodes


def publish_prepared_index(root, organization_id, nodes, vectors, queries, *, model, provenance, release_id=None,
                           projection='organization-text-6000.v1', publish_lexical=True, publish_navigation=True,
                           graph_sources=None):
    """Host-side publication of exact prepared content/query embeddings.

    Caller must verify embedding text/model provenance before publication.
    Never overwrites a release; use a new root for a new version. No API calls.
    """
    organization_id = str(UUID(organization_id))
    if not model or not provenance or not nodes or len(nodes) != len(vectors) or (not queries and release_id is None):
        raise ValueError('organization_retrieval_preparation_incomplete')
    dimensions = len(vectors[0])
    if dimensions < 1 or dimensions > 8192:
        raise ValueError('organization_retrieval_invalid_dimensions')
    records = []
    from .organization_index_release import PROJECTIONS, CHUNK_PROJECTION
    navigation = bool(release_id is not None and publish_lexical and publish_navigation
                      and projection == CHUNK_PROJECTION)
    if graph_sources is not None and not navigation:
        raise ValueError('organization_graph_requires_candidate_release')
    if projection not in PROJECTIONS or (release_id is None and projection == CHUNK_PROJECTION):
        raise ValueError('organization_retrieval_projection_requires_supported_release')
    for i, row in enumerate(nodes):
        if row['node_kind'] == 'section' or sha256(row['content'].encode()).hexdigest() != row['content_sha256']:
            raise ValueError('organization_retrieval_preparation_content_mismatch')
        records.append({'node_id': row['node_id'], 'document_id': row['parent_document_id'],
            'content_sha256': row['content_sha256'], 'vector_index': i})
        if row.get('embedding_input_sha256') is not None:
            # Keep the body once in a full-corpus projection. Reconstruct only
            # this row's provider input while validating its pinned digest.
            embedding_text = (row['embedding_context'] + '\n' + row['content']
                              if 'embedding_context' in row else row['embedding_content'])
            if 'embedding_context' in row and 'embedding_content' in row and row['embedding_content'] != embedding_text:
                raise ValueError('organization_embedding_projection_mismatch')
            if (projection != CHUNK_PROJECTION
                    or sha256(embedding_text.encode()).hexdigest() != row['embedding_input_sha256']):
                raise ValueError('organization_embedding_projection_mismatch')
            records[-1]['embedding_input_sha256'] = row['embedding_input_sha256']
        if navigation:
            from .organization_candidate_index import encoded
            from retrieval.published_lexical_index import lexical_digest
            records[-1].update(navigation_sha256=sha256(encoded(row)).hexdigest(),
                               lexical_input_sha256=lexical_digest(row))
    if len({r['node_id'] for r in records}) != len(records):
        raise ValueError('organization_retrieval_duplicate_node')
    prepared_queries = {sha256(q.encode()).hexdigest(): vector(v, dimensions).tolist() for q, v in queries.items()}
    directory = Path(root) / organization_id
    if release_id is not None:
        release_id = str(UUID(str(release_id)))
        directory = directory/'releases'/release_id
        if dimensions != 1024 or model not in {'text-embedding-v4', 'qwen3.7-text-embedding'}:
            raise ValueError('organization_release_requires_supported_provider_model')
    directory.mkdir(parents=True, exist_ok=False)
    # Validate/normalize one row at a time, avoiding two extra corpus-sized
    # arrays. index.json is the publication marker and is written only after
    # every vector succeeds. A failed directory is retained and never reused.
    # A writable mmap still accumulates a corpus-sized resident working set on
    # Windows. Write the same NumPy format sequentially without mapping it.
    with (directory/'vectors.npy').open('xb') as stream:
        np.lib.format.write_array_header_1_0(stream, {
            'descr': np.lib.format.dtype_to_descr(np.dtype(np.float32)),
            'fortran_order': False, 'shape': (len(nodes), dimensions)})
        for position in range(len(nodes)):
            stream.write(vector(vectors[position], dimensions).tobytes(order='C'))
    with (directory/'vectors.npy').open('rb') as stream:
        from hashlib import file_digest
        matrix_sha256 = file_digest(stream, 'sha256').hexdigest()
    manifest = {'format': FORMAT, 'organization_id': organization_id, 'model': model,
        'dimensions': dimensions, 'records': records, 'provenance': provenance,
        'matrix_sha256': matrix_sha256,
        'queries': prepared_queries}
    if release_id is not None:
        from .organization_index_release import FORMAT as RELEASE_FORMAT
        manifest.update(format=RELEASE_FORMAT, release_id=release_id, projection=projection)
    if release_id is not None and publish_lexical:
        from retrieval.published_lexical_index import build, FORMAT as LEXICAL_FORMAT
        lexical_path = directory/'lexical.sqlite'
        count = build(lexical_path, nodes)
        with lexical_path.open('rb') as stream:
            lexical_sha256 = file_digest(stream, 'sha256').hexdigest()
        manifest['lexical_index'] = {'format': LEXICAL_FORMAT, 'sha256': lexical_sha256, 'nodes': count}
    if navigation:
        from .organization_candidate_index import build as build_navigation, FORMAT as NAVIGATION_FORMAT
        navigation_path = directory/'navigation.sqlite'
        build_navigation(navigation_path, nodes)
        with navigation_path.open('rb') as stream:
            navigation_sha256 = file_digest(stream, 'sha256').hexdigest()
        manifest['navigation_index'] = {'format':NAVIGATION_FORMAT, 'sha256':navigation_sha256, 'nodes':len(nodes)}
    if graph_sources is not None:
        from .organization_graph_index import build as build_graph, FORMAT as GRAPH_FORMAT
        graph_path=directory/'graph.sqlite'
        counts=build_graph(graph_path,graph_sources,records)
        with graph_path.open('rb') as stream:
            graph_sha256=file_digest(stream,'sha256').hexdigest()
        manifest['graph_index']={'format':GRAPH_FORMAT,'sha256':graph_sha256,**counts}
    # Publish the marker only after every file and its digest are complete.
    # The directory is newly reserved; a failed build is never overwritten.
    import os
    pending = directory/'index.json.pending'
    with pending.open('x', encoding='utf8') as stream:
        json.dump(manifest, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    pending.rename(directory/'index.json')
    return digest(manifest)


class OrganizationHybridRetrieval:
    def __init__(self, reader, root, query_source=None):
        self.reader, self.root = reader, Path(root)
        self.query_source = query_source
        import os
        from retrieval.candidate_policy import candidate_limits
        self.candidate_policy = os.environ.get('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY', 'balanced.v1')
        candidate_limits(self.candidate_policy)
        rerank = os.environ.get('FINSIGHT_ORGANIZATION_RERANK', '')
        if rerank not in ('', 'qwen'):
            raise ValueError('organization_rerank_configuration_invalid')
        from retrieval.scoped_reranking import ConfiguredReranker
        self.reranker = ConfiguredReranker(self.root/'rerank-cache') if rerank == 'qwen' else None
        from .organization_index_release import ReleaseLoadCache
        self.release_cache = ReleaseLoadCache()

    def load_frozen(self, manifest):
        """Explicit warm-up and query entry share one verified release lifetime."""
        from .organization_index_release import load_release
        pinned = manifest['retrieval_index']
        return load_release(self.root, manifest['organization_id'], pinned['release_id'], pinned,
                            cache=self.release_cache)

    def rank(self, rows, query, snapshot, literal, *, source_verifier=None, graph=None):
        from .organization_source_navigation import OrganizationSourceNavigation
        before, manifest, _ = self.reader._grant()
        if graph is not None and source_verifier is None:
            raise OrganizationExecutionUnavailable('organization_graph_requires_verified_sources')
        if source_verifier is not None:
            from .organization_candidate_index import VerifiedCandidateIndex
            if not isinstance(source_verifier, VerifiedCandidateIndex) or source_verifier.hybrid is not self:
                raise OrganizationExecutionUnavailable('organization_candidate_invalid_verifier')
            source_verifier.verify_rows(rows, before)
        if snapshot != before['manifest_digest'][7:]:
            raise OrganizationExecutionUnavailable('organization_retrieval_snapshot_mismatch')
        allowed = {OrganizationSourceNavigation._identity(item) for item in manifest['inputs']}
        if not rows or any(row['parent_document_id'] not in allowed for row in rows):
            raise OrganizationExecutionUnavailable('organization_retrieval_scope_mismatch')
        pinned = manifest.get('retrieval_index')
        if pinned is not None:
            directory, index, matrix, verified_contract = self.load_frozen(manifest)
            # The loader already hashes the full canonical manifest, checks the
            # pinned contract and verifies immutable file identities on reuse.
            # Do not allocate another whole-manifest string/bytes per query.
            index_digest = verified_contract['index_digest']
        else:
            directory = self.root / str(UUID(manifest['organization_id']))
            try:
                encoded = (directory/'index.json').read_bytes()
                index = json.loads(encoded)
                matrix_bytes = (directory/'vectors.npy').read_bytes()
            except (OSError, ValueError):
                raise ValueError('organization_retrieval_index_not_prepared_or_invalid') from None
            if index.get('format') != FORMAT or index.get('organization_id') != manifest['organization_id']:
                raise OrganizationExecutionUnavailable('organization_retrieval_index_scope_mismatch')
            if sha256(matrix_bytes).hexdigest() != index['matrix_sha256']:
                raise ValueError('organization_retrieval_index_integrity_failure')
            from io import BytesIO
            matrix = np.load(BytesIO(matrix_bytes), allow_pickle=False)
            index_digest = sha256(encoded).hexdigest()
        records = {r['node_id']: r for r in index['records']}
        if (len(records) != len(index['records']) or matrix.dtype != np.float32
                or matrix.shape != (len(records), index['dimensions'])):
            raise ValueError('organization_retrieval_index_shape_mismatch')
        by_id = {row['node_id']: row for row in rows}
        if len(by_id) != len(rows):
            raise ValueError('organization_retrieval_duplicate_input')
        selected = []
        for row in rows:
            record = records.get(row['node_id'])
            if (record is None or record['document_id'] != row['parent_document_id']
                    or (source_verifier is None and record['content_sha256'] != sha256(row['content'].encode()).hexdigest())
                    or record['content_sha256'] != row['content_sha256']):
                raise ValueError('organization_retrieval_version_not_prepared')
            if record.get('embedding_input_sha256') != row.get('embedding_input_sha256'):
                raise ValueError('organization_retrieval_embedding_projection_mismatch')
            position = record['vector_index']
            if type(position) is not int or not 0 <= position < len(matrix):
                raise ValueError('organization_retrieval_invalid_vector_position')
            selected.append(position)
        from .organization_vector_math import unit_vectors, cosine_scores, verified_cosine_scores
        if pinned is None and not unit_vectors(matrix, selected):
            raise ValueError('organization_retrieval_invalid_prepared_vectors')
        query_hash = sha256(query.encode()).hexdigest()
        query_receipt = {'provider_calls': 0, 'cache_hit': True, 'source': 'prepared_index'}
        if query_hash in index['queries']:
            query_vector = vector(index['queries'][query_hash], index['dimensions'])
        elif pinned is not None:
            from .organization_index_release import ConfiguredQuerySource
            self.reader._after(before)  # Recheck before any billable request.
            if source_verifier is not None:
                source_verifier.check()
            source = self.query_source or ConfiguredQuerySource(self.root/'query-cache')
            values, query_receipt = source.embed(query, scope='organization:'+manifest['organization_id'],
                index_digest=pinned['index_digest'], model=pinned['model'], dimensions=pinned['dimensions'])
            query_vector = vector(values, index['dimensions'])
        else:
            raise ValueError('organization_retrieval_query_not_prepared_no_provider_fallback')
        # Selection happens before cosine scoring/top-K. Unselected documents
        # cannot occupy quotas, produce previews, or influence lexical ranks.
        scope = {'policy': POLICY, 'grant': digest(before), 'index': index_digest,
            'query': query_hash, 'nodes': [(r['node_id'], r['content_sha256']) for r in rows]}
        from retrieval.candidate_policy import candidate_limits
        limits = candidate_limits(self.candidate_policy, has_graph=graph is not None)
        if self.candidate_policy != 'balanced.v1':
            scope['candidate_policy'] = self.candidate_policy
        if graph is not None:
            if 'graph_index' not in index or len(graph)>12 or len(set(graph))!=len(graph) or any(n not in by_id for n in graph):
                raise OrganizationExecutionUnavailable('organization_graph_candidate_outside_scope')
            scope.update(policy='organization-cosine-bm25-graph-rrf.v1',graph=graph)
        key = digest(scope)
        self.reader._after(before)
        with closing(sqlite3.connect(directory/'rank-cache.sqlite', timeout=10)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS ranks (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            saved = db.execute('SELECT value FROM ranks WHERE key=?', (key,)).fetchone()
            if saved:
                entry = json.loads(saved[0])
            else:
                scores = (verified_cosine_scores if pinned is not None else cosine_scores)(matrix, selected, query_vector)
                dense = [rows[i]['node_id'] for i in sorted(range(len(rows)),
                    key=lambda i: (-float(scores[i]), rows[i]['node_id']))[:limits['dense']]]
                lexical = [r['node_id'] for r in literal[:limits['lexical']]]
                from retrieval.rank_fusion import reciprocal_rank_fusion
                channels=[dense,lexical]+([graph] if graph is not None else [])
                for channel in channels:
                    for node_id in channel:
                        if node_id not in by_id:
                            raise OrganizationExecutionUnavailable('organization_retrieval_candidate_outside_scope')
                entry = {'ordered': reciprocal_rank_fusion(channels), 'dense': dense, 'lexical': lexical}
                if graph is not None:entry['graph']=graph
                self.reader._after(before)
                db.execute('INSERT OR IGNORE INTO ranks VALUES (?,?)', (key, json.dumps(entry)))
            if graph is not None and entry.get('graph')!=graph:
                raise OrganizationExecutionUnavailable('organization_graph_cache_scope_mismatch')
            for channel in ('ordered', 'dense', 'lexical', *(['graph'] if graph is not None else [])):
                ids = entry[channel]
                if (not isinstance(ids, list) or len(set(ids)) != len(ids)
                        or len(ids) > (sum(limits.values()) if channel == 'ordered' else limits[channel])
                        or any(n not in by_id for n in ids)):
                    raise OrganizationExecutionUnavailable('organization_retrieval_cache_scope_mismatch')
        self.reader._after(before)
        if pinned is not None:
            self.release_cache.check()
        if source_verifier is not None:
            source_verifier.check()
        return [by_id[n] for n in entry['ordered']], {'mode': scope['policy'], 'cache_hit': bool(saved),
            'vector_validation':'immutable_release_receipt' if pinned is not None else 'selected_rows_per_request',
            **({'candidate_policy':self.candidate_policy, 'candidate_limits':limits}
               if self.candidate_policy != 'balanced.v1' else {}),
            **({'graph_node_ids':entry['graph']} if graph is not None else {}),
            'index_digest': scope['index'], 'dense_node_ids': entry['dense'], 'lexical_node_ids': entry['lexical'],
            'candidate_node_ids': entry['ordered'], 'provider_calls': query_receipt['provider_calls'],
            'query_embedding': query_receipt, 'rerank': 'local_rrf_no_provider'}
