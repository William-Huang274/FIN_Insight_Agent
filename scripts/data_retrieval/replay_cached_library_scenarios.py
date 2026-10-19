"""Replay historical hybrid searches through current code without provider calls.

Published library/index are read-only. Provider receipts are read through a
read-only SQLite connection, never LocalRecords' migration/write constructor.
This qualifies retrieval execution, not Java authorization or answer quality.
"""
import argparse
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import socket
import sqlite3
import time
from unittest.mock import patch

from sec_agent.adapters.local_records import _unpack


class ReadOnlyReceipts:
    def __init__(self, directory):
        self.path = Path(directory).resolve() / 'records-v1.sqlite'
        self.db = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
        self.db.execute('PRAGMA query_only=ON')

    def get(self, key, default=None):
        row = self.db.execute('SELECT value,expires FROM records WHERE key=?', (key,)).fetchone()
        if row is None or (row[1] is not None and row[1] <= time.time()):
            return default
        return _unpack(json.loads(row[0]))

    def add(self, *args, **kwargs):
        raise RuntimeError('historical_receipt_miss_no_paid_fallback')

    def __setitem__(self, key, value):
        raise RuntimeError('historical_receipts_are_read_only')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()


def forbidden(*args, **kwargs):
    raise RuntimeError('offline_scenario_forbids_network_or_provider')


def run(library_path, index_path, cases_path, output, as_of):
    from retrieval import library_hybrid
    from retrieval.qwen_api import QwenRetrieval
    from sec_agent.research_foundation.research_library import ResearchLibrary
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads(cases_path.read_text(encoding='utf8'))
    assert cases and len({c['id'] for c in cases}) == len(cases)
    rows = []
    report = {'scope': 'current Python library tools; Java integration not assessed',
        'provider_calls': 0, 'network_calls': 0, 'answer_quality': 'not_assessed',
        'cases_sha256': sha256(cases_path.read_bytes()).hexdigest(), 'cases': rows}
    started = time.perf_counter()
    with ExitStack() as guards:
        guards.enter_context(patch.object(socket.socket, 'connect', forbidden))
        guards.enter_context(patch.object(socket.socket, 'connect_ex', forbidden))
        guards.enter_context(patch.object(QwenRetrieval, 'embed', forbidden))
        guards.enter_context(patch.object(QwenRetrieval, 'rerank', forbidden))
        guards.enter_context(patch.object(library_hybrid, 'Cache', ReadOnlyReceipts))
        guards.enter_context(patch.dict('os.environ', {'QWEN_API_KEY': 'offline-not-a-credential'}))
        library = ResearchLibrary(library_path, retrieval_environment={
            'FINSIGHT_LIBRARY_HYBRID': '1', 'FINSIGHT_LIBRARY_RAG_CACHE_PATH': str(index_path)})
        report['library_sha256'] = library.manifest['sha256']
        report['index_manifest'] = json.loads((index_path/'chunk-vector-manifest.json').read_text())
        report['initialization_seconds'] = time.perf_counter()-started
        try:
            for case in cases:
                before = time.perf_counter()
                request = SourceDocumentRequest(source_space='library', operation='search',
                    query=case['query'], limit=6,
                    **{k: case[k] for k in ('entity_id', 'document_id') if case.get(k)})
                result = library.navigate(request, as_of)
                data = result.model_dump(mode='json')
                # Retain actual tool output; expected IDs are historical development
                # expectations, not an independently reviewed recall benchmark.
                checks = {}
                for key, field in [('expected_source_id', 'document_id'), ('expected_parent_id', 'parent_node_id')]:
                    if key in case:
                        checks[key] = case[key] in {item.get(field) for item in result.items}
                if case.get('document_id'):
                    checks['document_scope'] = all(item['document_id'] == case['document_id'] for item in result.items)
                readbacks = []
                for item in result.items[:3]:
                    selection = item.get('readback') or {'source_space': 'library', 'operation': 'read',
                        'document_id': item['document_id'], 'node_id': item['node_id']}
                    read = library.navigate(SourceDocumentRequest.model_validate(selection), as_of)
                    assert read.items and read.items[0]['document_id'] == item['document_id']
                    passage = read.items[0]
                    assert passage['result_state'] == 'source_bound_passage'
                    assert sha256(passage['passage'].encode()).hexdigest() == item['digest']
                    readbacks.append(read.model_dump(mode='json'))
                if case.get('expected_late_text'):
                    checks['expected_late_text'] = any(case['expected_late_text'] in item['passage']
                        for read in readbacks for item in read['items'])
                row = {'id': case['id'], 'seconds': time.perf_counter()-before,
                    'expected_identity_checks': checks, 'result': data, 'readbacks': readbacks}
                rows.append(row)
                assert result.items, 'historical_query_returned_no_candidates'
                assert all(checks.values()), 'historical_expected_identity_missing'
                assert readbacks, 'historical_candidates_have_no_readback'
                print(json.dumps({'case': case['id'], 'readbacks': len(readbacks), 'checks': checks}), flush=True)
            report['status'] = 'passed'
        except Exception as error:
            report['status'] = 'failed'
            report['error'] = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            report['seconds'] = time.perf_counter()-started
            (output/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('library', 'index', 'cases', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args()
    run(args.library, args.index, args.cases, args.output, args.as_of)
