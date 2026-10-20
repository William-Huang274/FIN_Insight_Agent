"""Explicit paid query source with durable, scoped receipts and no retries.

Authorization and immutable index selection belong to the caller. This adapter
cannot select an endpoint from a tool argument, prepare corpus vectors, rerank,
or fall back to another model. Successful embeddings are not access grants.
"""
from hashlib import sha256
import json
import math

from sec_agent.adapters.local_records import LocalRecords
from retrieval.source_hybrid import CachedRetrieval


class QueryEmbeddingSource:
    def __init__(self, path, api, *, model, dimensions=1024, max_query_bytes=8192):
        if model not in {'text-embedding-v4', 'qwen3.7-text-embedding'}:
            raise ValueError('query_embedding_unsupported_model')
        if api.embedding_model != model or dimensions != 1024:
            raise ValueError('query_embedding_configuration_mismatch')
        if type(max_query_bytes) is not int or not 1 <= max_query_bytes <= 8192:
            raise ValueError('query_embedding_invalid_input_limit')
        self.path, self.api = path, api
        self.model, self.dimensions = model, dimensions
        self.max_query_bytes = max_query_bytes

    def embed(self, query, *, scope, index_digest, model, dimensions):
        """Use only after resolving the current authorized source/index scope.

        scope is a server-owned namespace (organization or public qualification).
        index_digest identifies the immutable index; neither value is a grant.
        Bytes bound input conservatively, without silently truncating the query.
        Pending/failed calls remain blocked even after a process restart.
        """
        if model != self.model or dimensions != self.dimensions:
            raise ValueError('query_embedding_index_model_mismatch')
        if (not isinstance(scope, str) or not scope or len(scope) > 256
                or not isinstance(index_digest, str) or len(index_digest) != 64
                or any(c not in '0123456789abcdef' for c in index_digest)):
            raise ValueError('query_embedding_requires_server_scope_and_index_digest')
        if (not isinstance(query, str) or not query.strip()
                or len(query.encode('utf8')) > self.max_query_bytes):
            raise ValueError('query_embedding_query_outside_input_limit')
        namespace = sha256(json.dumps(
            ['index-query.v1', scope, index_digest, self.model, self.dimensions],
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        with LocalRecords(self.path) as cache:
            client = CachedRetrieval(cache, self.api, namespace)
            result = client.call('embedding', [query])
        values = result.get('values')
        if (result.get('model') != self.model or not isinstance(values, list) or len(values) != 1
                or len(values[0]) != self.dimensions
                or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
                           for x in values[0]) or not any(values[0])):
            raise ValueError('query_embedding_invalid_cached_response')
        return values[0], {'model': self.model, 'dimensions': self.dimensions,
            'index_digest': index_digest, 'query_sha256': sha256(query.encode()).hexdigest(),
            'provider_calls': client.calls, 'cache_hit': bool(client.hits),
            'request_id': result.get('request_id'), 'usage': result.get('usage', {}),
            'usage_origin': 'original_provider_receipt',
            'newly_reported_usage': result.get('usage', {}) if client.calls else {}}
