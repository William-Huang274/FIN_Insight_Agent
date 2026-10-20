"""Immutable host-owned organization index releases; Java freezes their identity."""
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID

import numpy as np

FORMAT = 'organization-prepared-vectors.v2'
PROJECTION = 'organization-text-6000.v1'
FIELDS = {'release_id', 'index_digest', 'matrix_sha256', 'model', 'dimensions', 'projection'}


def canonical_digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def validate_contract(contract):
    if (not isinstance(contract, dict) or set(contract) != FIELDS
            or str(UUID(contract['release_id'])) != contract['release_id']
            or contract['model'] not in {'text-embedding-v4', 'qwen3.7-text-embedding'}
            or type(contract['dimensions']) is not int or contract['dimensions'] != 1024
            or contract['projection'] != PROJECTION):
        raise ValueError('organization_index_release_contract_invalid')
    for field in ('index_digest', 'matrix_sha256'):
        value = contract[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('organization_index_release_digest_invalid')
    return contract


def load_release(root, organization_id, release_id, expected=None):
    """No implicit latest selection. Full integrity is checked before use."""
    org, identifier = str(UUID(organization_id)), str(UUID(release_id))
    directory = Path(root)/org/'releases'/identifier
    try:
        index = json.loads((directory/'index.json').read_bytes())
        if (index.get('format') != FORMAT or index.get('organization_id') != org
                or index.get('release_id') != identifier or index.get('projection') != PROJECTION):
            raise ValueError('organization_index_release_identity_mismatch')
        contract = validate_contract({'release_id':identifier, 'index_digest':canonical_digest(index),
            **{k:index[k] for k in ('matrix_sha256', 'model', 'dimensions', 'projection')}})
        if expected is not None and contract != validate_contract(expected):
            raise ValueError('organization_index_release_frozen_version_mismatch')
        with (directory/'vectors.npy').open('rb') as stream:
            from hashlib import file_digest
            if file_digest(stream, 'sha256').hexdigest() != contract['matrix_sha256']:
                raise ValueError('organization_index_release_matrix_integrity_failure')
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


def verify_release_inputs(workspace, org, inputs, contract, root, research_as_of):
    from .organization_source_navigation import OrganizationSourceNavigation
    from .project_source_captures import validate_metric_cutoff, financial_capture_text
    _, index, matrix, _ = load_release(root, org, contract['release_id'], contract)
    expected = {}
    for item in inputs:
        ref = item['binding']['ref']
        result = workspace.read('organization:'+org, ref)
        if result['version']['ref'] != ref or result.get('truncated') or result.get('needs_vision'):
            raise ValueError('organization_index_requires_complete_original')
        capture = result.get('capture') or {}
        validate_metric_cutoff(capture, research_as_of)
        text = financial_capture_text(capture) if capture.get('kind') == 'financial' else result['text']
        if not text.strip() or len(text) > 100000:
            raise ValueError('organization_index_projection_not_supported')
        document = OrganizationSourceNavigation._identity({'resource_id':item['resource_id'], 'ref':ref})
        for position, start in enumerate(range(0, len(text), 6000)):
            node = document.replace('ORGDOC::','ORGSECTION::')+f':{position}:leaf'
            expected[node] = (document, sha256(text[start:start+6000].encode()).hexdigest())
    actual = {r['node_id']:(r['document_id'], r['content_sha256']) for r in index['records']}
    if actual != expected:
        raise ValueError('organization_index_original_projection_mismatch')
    if (not np.isfinite(matrix).all()
            or not np.allclose(np.linalg.norm(matrix.astype(np.float64), axis=1), 1., rtol=1e-5, atol=1e-6)):
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
