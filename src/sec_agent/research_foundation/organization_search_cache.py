"""One bounded, process-local search response; never an authorization lease.

SQLite data_version is compared on the SAME read-only connection, outside any
transaction. Every committed write invalidates the response, including WAL
writes, deletion, local access changes and restored originals. File identities
also detect replacement. No source body or projection corpus is kept here.
"""
from copy import deepcopy
from pathlib import Path
import sqlite3
import weakref
import zlib

from .organization_hybrid_retrieval import digest


class OrganizationSearchCache:
    # One page per user/session, bounded both while retained and while decoded.
    MAX_COMPRESSED_BYTES = 512 * 1024
    MAX_DECODED_BYTES = 8 * 1024 * 1024

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True,
                                  isolation_level=None, check_same_thread=False, timeout=3)
        weakref.finalize(self, self.db.close)
        self.entry = None

    def epoch(self):
        def signature(path):
            stat = path.stat()
            return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        # Let SQLite observe a changed journal mode/open its WAL before taking
        # file identities. Otherwise the observer itself can create the WAL
        # after we recorded its absence and falsely report a concurrent write.
        version = self.db.execute('PRAGMA data_version').fetchone()[0]
        # Missing original DB is an error, never a reusable empty generation.
        database = signature(self.path)
        wal = Path(str(self.path) + '-wal')
        try:
            journal = signature(wal)
        except FileNotFoundError:
            journal = None
        return database, journal, version

    @staticmethod
    def key(grant, request):
        return digest({'grant': grant, 'request': request.model_dump(mode='json')})

    def get(self, key, epoch):
        if self.entry is None:
            return None
        saved_key, saved_epoch, packed = self.entry
        if saved_key != key or saved_epoch != epoch:
            self.entry = None
            return None
        from .source_document_navigation import SourceDocumentResult
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, self.MAX_DECODED_BYTES + 1)
        if len(raw) > self.MAX_DECODED_BYTES or not decoder.eof or decoder.unused_data:
            self.entry = None
            raise ValueError('organization_search_cache_invalid_payload')
        result = SourceDocumentResult.model_validate_json(raw)
        items, notice = [], result.notice
        for item in result.items:
            old = item.get('retrieval')
            if old is not None:
                receipt = deepcopy(old)
                receipt.update(cache_hit=True, response_cache_hit=True, provider_calls=0)
                if 'projection_cache_hits' in receipt:
                    receipt['projection_cache_hits'] = 0
                if receipt.get('candidate_only'):
                    receipt.update(source_generation_original_reads=0, candidate_body_reads=0)
                receipt['query_embedding'] = {'provider_calls': 0, 'cache_hit': True,
                                              'source': 'validated_response_cache'}
                if 'rerank_response' in receipt:
                    receipt['rerank_response'].update(provider_calls=0, cache_hit=True, newly_reported_usage={})
                notice = notice.replace(str(old), str(receipt))
                item['retrieval'] = receipt
            items.append(item)
        return result.model_copy(update={'items': tuple(items), 'notice': notice})

    def put(self, key, epoch, result):
        # The navigator owns a single page, not an unbounded query/body cache.
        self.entry = None
        raw = result.model_dump_json().encode()
        if len(raw) <= self.MAX_DECODED_BYTES:
            packed = zlib.compress(raw, 1)
            if len(packed) <= self.MAX_COMPRESSED_BYTES:
                self.entry = (key, epoch, packed)
