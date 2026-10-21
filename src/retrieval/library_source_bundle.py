"""Lossless intake of legacy parsed sources, without granting runtime access.

Recovery supports explicit text windows whose complete UTF-8 digest can be
verified. Binary-document and read-envelope digests are not text digests.
"""
from __future__ import annotations

from hashlib import sha256
from collections import defaultdict
import re

import numpy as np

from retrieval.library_vectors import DIM, vector_key

FORMAT = 'library-source-bundle.v1'
COMPACT_FORMAT = 'library-source-offset-bundle.v1'
PROJECTION = 'library-context-body.v1'
STEP = 5200
OVERLAP = 250


def text_digest(text):
    return sha256(text.encode('utf-8')).hexdigest()


def validate_bundle_text(bundle):
    if 'node_recovery' in bundle:
        from .library_node_recovery import validate_bundle
        validate_bundle(bundle)
        return
    recovery = bundle.get('archive_recovery')
    expected = bundle['source']['digest']
    if recovery is not None:
        if (recovery['format'] != 'library-archive-recovery.v1'
                or recovery['parser'] not in {'legacy-html-table-text.v1','legacy-pypdf-pages.v1'}
                or recovery['raw_sha256'] != expected or recovery['separator'] != '\f'
                or not recovery['pages']):
            raise ValueError('archive_recovery_contract_invalid')
        cursor = 0
        for number, page in enumerate(recovery['pages'], 1):
            lo, hi = page['source_char_start'], page['source_char_end']
            if (page['number'] != number or type(lo) is not int or type(hi) is not int
                    or lo != cursor or not lo <= hi <= len(bundle['text'])
                    or text_digest(bundle['text'][lo:hi]) != page['sha256']
                    or (number < len(recovery['pages']) and bundle['text'][hi:hi+1] != '\f')):
                raise ValueError('archive_page_span_mismatch')
            cursor = hi+1
        if cursor-1 != len(bundle['text']):
            raise ValueError('archive_page_coverage_mismatch')
        expected = recovery['parsed_text_sha256']
    if text_digest(bundle['text']) != expected:
        raise ValueError('recovered_source_digest_mismatch')


def compact_source_bundle(bundle):
    """Store each source character once; original row IDs/digests stay intact."""
    from .library_node_recovery import FORMAT as NODE_FORMAT, compact_bundle
    if bundle['format'] == NODE_FORMAT:
        compact=compact_bundle(bundle)
        if expand_source_bundle(compact)!=bundle:
            raise ValueError('indexed_node_roundtrip_mismatch')
        return compact
    if bundle['format'] != FORMAT:
        raise ValueError('source_bundle_format_invalid')
    compact = {**bundle, 'format':COMPACT_FORMAT}
    for table in ('parents','chunks'):
        compact[table] = []
        for row in bundle[table]:
            lo,hi=row['source_char_start'],row['source_char_end']
            if bundle['text'][lo:hi] != row['body'] or text_digest(row['body']) != row['digest']:
                raise ValueError('source_bundle_offset_content_mismatch')
            compact[table].append({k:v for k,v in row.items() if k!='body'})
    if expand_source_bundle(compact) != bundle:
        raise ValueError('source_bundle_lossless_roundtrip_failed')
    return compact


def expand_source_bundle(bundle):
    from .library_node_recovery import COMPACT as NODE_COMPACT, FORMAT as NODE_FORMAT, expand_bundle, validate_bundle
    if bundle['format']==NODE_COMPACT:return expand_bundle(bundle)
    if bundle['format']==NODE_FORMAT:
        validate_bundle(bundle)
        return bundle
    if bundle['format'] == FORMAT:
        return bundle  # Existing immutable snapshots keep their original shape.
    if bundle['format'] != COMPACT_FORMAT:
        raise ValueError('source_bundle_format_invalid')
    text = bundle['text']
    validate_bundle_text(bundle)
    result = {**bundle, 'format':FORMAT}
    for table in ('parents','chunks'):
        result[table] = []
        for row in bundle[table]:
            lo,hi=row['source_char_start'],row['source_char_end']
            if ('body' in row or type(lo) is not int or type(hi) is not int
                    or not 0 <= lo < hi <= len(text) or text_digest(text[lo:hi]) != row['digest']):
                raise ValueError('source_bundle_offset_content_mismatch')
            result[table].append({**row,'body':text[lo:hi]})
    return result


def recover_source(source, parents):
    """Recover exact parsed text; reject gaps, unsupported locators or drift."""
    if source['access_state'] != 'readable' or not parents:
        raise ValueError('source_not_readable_or_empty')
    if all(re.fullmatch(r'raw text chars (0|[1-9][0-9]*)-([1-9][0-9]*)', p['locator']) for p in parents):
        return _recover_raw_text(source, parents)
    positions = {}
    ids = set()
    for parent in parents:
        match = re.fullmatch(r'text-part:(0|[1-9][0-9]*)', parent['locator'])
        if not match:
            raise ValueError('unsupported_parent_projection')
        part = int(match[1])
        if part in positions or parent['id'] in ids or parent['source_id'] != source['id']:
            raise ValueError('parent_identity_mismatch')
        if text_digest(parent['body']) != parent['digest']:
            raise ValueError('parent_digest_mismatch')
        positions[part] = parent
        ids.add(parent['id'])
    if sorted(positions) != list(range(len(parents))):
        raise ValueError('parent_sequence_gap')
    text = ''
    for part in range(len(parents)):
        body = positions[part]['body']
        start = max(0, part * STEP - OVERLAP)
        expected_end = (part + 1) * STEP
        if (not body or len(body) > expected_end - start
                or (part < len(parents) - 1 and len(body) != expected_end - start)
                or (part > 0 and len(body) <= OVERLAP)):
            raise ValueError('parent_window_length_mismatch')
        overlap = len(text) - start
        if overlap < 0 or text[start:] != body[:overlap]:
            raise ValueError('parent_overlap_mismatch')
        text += body[overlap:]
    if text_digest(text) != source['digest']:
        raise ValueError('recovered_source_digest_mismatch')
    return text, [dict(positions[i], source_char_start=max(0, i * STEP - OVERLAP),
                       source_char_end=min(len(text), (i + 1) * STEP))
                  for i in range(len(parents))]


def _recover_raw_text(source, parents):
    """Legacy external UTF-8 snapshots: explicit contiguous, nonoverlap spans.

    This accepts neither HTML/PDF extraction nor source archive paths. The
    final digest proves that no original byte/text tail or newline was lost.
    """
    ordered, ids = [], set()
    for parent in parents:
        match = re.fullmatch(r'raw text chars (0|[1-9][0-9]*)-([1-9][0-9]*)', parent['locator'])
        lo, hi = int(match[1]), int(match[2])
        if parent['id'] in ids or parent['source_id'] != source['id']:
            raise ValueError('parent_identity_mismatch')
        if text_digest(parent['body']) != parent['digest']:
            raise ValueError('parent_digest_mismatch')
        if hi <= lo or hi-lo != len(parent['body']):
            raise ValueError('parent_window_length_mismatch')
        ids.add(parent['id'])
        ordered.append(dict(parent, source_char_start=lo, source_char_end=hi))
    ordered.sort(key=lambda p: p['source_char_start'])
    end = 0
    for parent in ordered:
        if parent['source_char_start'] != end:
            raise ValueError('parent_sequence_gap_or_overlap')
        end = parent['source_char_end']
    text = ''.join(p['body'] for p in ordered)
    if text_digest(text) != source['digest']:
        raise ValueError('recovered_source_digest_mismatch')
    return text, ordered


def validated_stored_chunks(db, source_id, parents):
    """Verify local parent coverage only; never claim complete document recovery.

    Hierarchical parents may overlap. Their bytes and IDs are preserved here;
    this function neither concatenates them nor invents document offsets.
    """
    by_parent = {row['id']: row for row in parents}
    if not parents or len(by_parent) != len(parents) or any(p['source_id'] != source_id for p in parents):
        raise ValueError('parent_identity_mismatch')
    if any(text_digest(p['body']) != p['digest'] for p in parents):
        raise ValueError('parent_digest_mismatch')
    chunks = [dict(row) for row in db.execute(
        'SELECT * FROM retrieval_chunks WHERE source_id=? ORDER BY parent_id,char_start,id', (source_id,))]
    by_chunk = {}
    cursors = {pid: 0 for pid in by_parent}
    for row in chunks:
        parent = by_parent.get(row['parent_id'])
        lo, hi = row['char_start'], row['char_end']
        if (parent is None or row['id'] in by_chunk or type(lo) is not int or type(hi) is not int
                or not 0 <= lo < hi <= len(parent['body']) or parent['body'][lo:hi] != row['body']
                or text_digest(row['body']) != row['digest']):
            raise ValueError('chunk_parent_or_content_mismatch')
        if parent['body'][cursors[parent['id']]:lo].strip():
            raise ValueError('chunk_coverage_gap')
        cursors[parent['id']] = max(cursors[parent['id']], hi)
        by_chunk[row['id']] = row
    if any(parent['body'][cursors[parent['id']]:].strip() for parent in parents):
        raise ValueError('chunk_coverage_tail_missing')
    return chunks


def build_source_bundle(db, source_id, library_sha256, recovery_catalog=None, node_catalog=None):
    """Read a full selected source, never a relevance-label-selected subset."""
    found = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
    if found is None:
        raise ValueError('source_missing')
    source = dict(found)
    parents = [dict(row) for row in db.execute('SELECT * FROM passages WHERE source_id=?', (source_id,))]
    recovery = None; node_recovery = None
    import json
    if json.loads(source['metadata']).get('origin')=='existing_library':
        if node_catalog is None:raise ValueError('indexed_node_catalog_required')
        from .library_node_recovery import directory
        node_recovery=node_catalog.recover(source,parents,library_sha256)
        text=directory(node_recovery['nodes'])
    elif parents and all(re.fullmatch(r'(HTML text|PDF page [1-9][0-9]*) chars [0-9]+-[0-9]+', p['locator']) for p in parents):
        if recovery_catalog is None:
            raise ValueError('archive_recovery_catalog_required')
        text, parents, recovery = recovery_catalog.recover(source, parents, library_sha256)
    else:
        text, parents = recover_source(source, parents)
    by_parent = {row['id']: row for row in parents}
    chunks = validated_stored_chunks(db,source_id,parents)
    for row in chunks:
        if node_recovery is not None:
            row['embedding_input_sha256']=text_digest(row['context']+'\n'+row['body'])
            continue
        start = by_parent[row['parent_id']]['source_char_start']
        row.update(source_char_start=start+row['char_start'], source_char_end=start+row['char_end'],
                   embedding_input_sha256=text_digest(row['context']+'\n'+row['body']))
        if recovery is not None:
            row['original_page'] = by_parent[row['parent_id']]['original_page']
        if text[row['source_char_start']:row['source_char_end']] != row['body']:
            raise ValueError('chunk_source_offset_mismatch')
    by_chunk = {row['id']:row for row in chunks}
    edges = [dict(row) for row in db.execute('SELECT * FROM edges WHERE source_id=? ORDER BY id', (source_id,))]
    links = [dict(row) for row in db.execute(
        'SELECT l.* FROM edge_chunk_links l JOIN edges e ON e.id=l.edge_id '
        'WHERE e.source_id=? ORDER BY l.edge_id,l.chunk_id,l.evidence_index', (source_id,))]
    for link in links:
        chunk = by_chunk.get(link['chunk_id'])
        if chunk is None:
            raise ValueError('edge_chunk_source_mismatch')
        lo, hi = link['span_start'], link['span_end']
        if (lo is None) != (hi is None) or (lo is not None and (
                not 0 <= lo < hi <= len(by_parent[chunk['parent_id']]['body'])
                or lo >= chunk['char_end'] or hi <= chunk['char_start'])):
            raise ValueError('edge_chunk_span_mismatch')
    coverage = [dict(row) for row in db.execute(
        'SELECT c.* FROM edge_chunk_coverage c JOIN edges e ON e.id=c.edge_id '
        'WHERE e.source_id=? ORDER BY c.edge_id', (source_id,))]
    if {row['edge_id'] for row in coverage} != {row['id'] for row in edges}:
        raise ValueError('edge_coverage_record_missing')
    from .library_node_recovery import FORMAT as NODE_FORMAT
    return dict(format=NODE_FORMAT if node_recovery is not None else FORMAT, projection=PROJECTION, library_sha256=library_sha256,
                source=source, text=text, parents=parents, chunks=chunks, edges=edges,
                edge_chunk_links=links, edge_chunk_coverage=coverage,
                scope=(node_recovery['scope'] if node_recovery is not None else 'complete stored parsed text; original binary/graphics not recovered'),
                numeric_fact_authority=False, organization_authorization=False,
                **({'archive_recovery':recovery} if recovery is not None else {}),
                **({'node_recovery':node_recovery} if node_recovery is not None else {}))


def reusable_vectors(bundle, manifest, matrix, mapping, cache):
    """Verify old rows against exact embedding inputs and successful cache values.

    ready_index must first verify the immutable matrix/map hashes. Comparing the
    normalized cache value also catches a valid-shaped map pointing at wrong rows.
    No call to a provider and no cache mutation is possible here.
    """
    return VectorReuseVerifier(manifest, matrix, mapping, cache).verify(bundle)


class VectorReuseVerifier:
    """Batch immutable receipt/map lookup, never a runtime authorization cache.

    The caller owns a read-only transaction for the lifetime of this object.
    Values are still checked against each exact input and matrix row.
    """
    def __init__(self, manifest, matrix, mapping, cache):
        self.manifest, self.matrix, self.mapping, self.cache = manifest, matrix, mapping, cache
        self.completed = {r[0] for r in cache.execute(
            "SELECT DISTINCT i.key FROM request_items i JOIN requests r ON r.id=i.request_id "
            "WHERE r.status='completed'")}
        self.by_source, self.by_id = defaultdict(set), defaultdict(set)
        for i, row in enumerate(mapping):
            self.by_source[row['source_id']].add(i)
            self.by_id[row['id']].add(i)

    def verify(self, bundle):
        positions = set(self.by_source.get(bundle['source']['id'], ()))
        for chunk in bundle['chunks']:
            positions.update(self.by_id.get(chunk['id'], ()))
        rows = [self.mapping[i] for i in sorted(positions)]
        return _verify_vectors(bundle, self.manifest, self.matrix, rows, self.cache, self.completed)


def _verify_vectors(bundle, manifest, matrix, mapping, cache, completed_keys):
    if bundle['library_sha256'] != manifest['library_sha256'] or manifest['dimensions'] != DIM:
        raise ValueError('vector_source_version_mismatch')
    selected = {row['id']: row for row in bundle['chunks']}
    by_id = {}
    for row in mapping:
        if row['id'] in selected or row['source_id'] == bundle['source']['id']:
            if row['id'] in by_id:
                raise ValueError('duplicate_vector_mapping')
            by_id[row['id']] = row
    if set(by_id) != set(selected):
        raise ValueError('vector_mapping_coverage_mismatch')
    records, vectors = [], []
    for chunk in bundle['chunks']:
        row = by_id[chunk['id']]
        position = row['vector_index']
        if (row['source_id'] != bundle['source']['id'] or type(position) is not int
                or not 0 <= position < len(matrix)):
            raise ValueError('vector_mapping_identity_mismatch')
        text = chunk['context'] + '\n' + chunk['body']
        key = vector_key(text, manifest['embedding_model'])
        saved = cache.execute('SELECT vector FROM vectors WHERE key=?', (key,)).fetchone()
        if saved is None or key not in completed_keys:
            raise ValueError('exact_embedding_input_receipt_missing')
        vector = np.frombuffer(saved[0], dtype=np.float32)
        actual = matrix[position]
        norm = np.linalg.norm(vector)
        if (vector.shape != (DIM,) or not np.isfinite(vector).all()
                or not np.isfinite(actual).all() or not np.isfinite(norm) or norm == 0
                or not np.array_equal(actual, vector / norm)):
            raise ValueError('cached_vector_matrix_mismatch')
        records.append(dict(chunk_id=chunk['id'], source_id=row['source_id'],
                            embedding_input_sha256=text_digest(text), embedding_key=key,
                            source_vector_index=position, vector_index=len(vectors)))
        vectors.append(actual)
    return records, np.asarray(vectors, dtype=np.float32).reshape((-1, DIM))
