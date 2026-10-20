"""Copy exact historical chunk embeddings/query receipts for offline ACL tests.

No provider client or source mutation. Excerpts are marked as historical test
copies; they are not newly verified issuer documents or financial gold.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import numpy as np

from retrieval.library_vectors import ready_index
from retrieval.source_hybrid import CachedRetrieval
from scripts.data_retrieval.replay_cached_library_scenarios import ReadOnlyReceipts


def prepare(library, index, replay, cases, output):
    output.mkdir(parents=True, exist_ok=False)
    release = json.loads((index/'chunk-vector-manifest.json').read_text())
    with library.open('rb') as stream:
        from hashlib import file_digest
        assert file_digest(stream, 'sha256').hexdigest() == release['library_sha256']
    _, matrix, mapping = ready_index(index, release['library_sha256'])
    lookup = {row['id']:row for row in mapping}
    originals = json.loads(cases.read_text(encoding='utf8'))
    results = {r['id']:r for r in json.loads(replay.read_text(encoding='utf8'))['cases']}
    api = SimpleNamespace(embedding_model=release['embedding_model'], rerank_model='qwen3-rerank')
    prepared = []
    with sqlite3.connect(library.resolve().as_uri()+'?mode=ro', uri=True) as db, ReadOnlyReceipts(index/'query-cache') as cache:
        db.row_factory = sqlite3.Row
        client = CachedRetrieval(cache, api, 'library-child-query.v1')
        for case in originals:
            query_vector = np.asarray(client.embed_query(case['query']), dtype=np.float32)
            query_vector /= np.linalg.norm(query_vector)
            rows = []
            for candidate in results[case['id']]['result']['items'][:3]:
                row = dict(db.execute('SELECT id, source_id, context, body FROM retrieval_chunks WHERE id=?',
                    (candidate['node_id'],)).fetchone())
                assert sha256(row['body'].encode()).hexdigest() == candidate['digest']
                text = row['context']+'\n'+row['body']
                assert 0 < len(text) <= 6000
                vector = np.asarray(matrix[lookup[row['id']]['vector_index']], dtype=np.float32)
                rows.append((float(vector @ query_vector), row, text, vector))
            rows.sort(key=lambda r:r[0])
            assert len(rows) >= 2 and rows[-1][0] > rows[0][0]
            documents = []
            # Freeze the weaker match; the stronger match is an indexed but
            # unselected resource, detecting top-K-before-ACL mistakes.
            for position, (score, row, text, vector) in enumerate((rows[0], rows[-1])):
                name = case['id']+'-'+str(position)+'.txt'
                (output/name).write_bytes(text.encode())
                documents.append({'file':name, 'sha256':sha256(text.encode()).hexdigest(),
                    'vector':vector.tolist(), 'cosine':score, 'historical_chunk_id':row['id'],
                    'historical_source_id':row['source_id'], 'classification':'exact historical embedding-text excerpt; not financial gold'})
            prepared.append({'id':case['id'], 'query':case['query'], 'query_vector':query_vector.tolist(), 'documents':documents})
    result = {'model':release['embedding_model'], 'as_of':'2026-09-23', 'cases':prepared,
        'provenance':{'library_sha256':release['library_sha256'], 'matrix_sha256':release['matrix_sha256'],
            'embedding_text':'exact context + newline + body from the same immutable library release'}, 'provider_calls':0}
    (output/'cases.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'cases':len(prepared), 'documents':sum(len(c['documents']) for c in prepared), 'provider_calls':0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('library','index','replay','cases','output'):
        parser.add_argument('--'+key, type=Path, required=True)
    prepare(**vars(parser.parse_args()))
