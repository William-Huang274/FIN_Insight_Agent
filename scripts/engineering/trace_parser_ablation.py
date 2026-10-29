"""Paired parser/chunk ablation with unchanged background and full score traces.

This isolates representation using shared BM25/fusion primitives, not a live
authorization or final production-policy acceptance test. No model calls here.
"""
import argparse
from collections import Counter
import gc
import gzip
from hashlib import sha256, file_digest
import json
from pathlib import Path
import sqlite3
import zlib
import numpy as np
from retrieval.query_bm25 import TokenCounts, lexical_scores
from retrieval.text import tokenize
from retrieval.organization_search_needs import lexical_surfaces, interleave
from retrieval.candidate_pipeline import fuse_channels


def run(base, index_path, query_vectors, embeddings, output, resume=False, arms=('old', 'parsed')):
    if not arms or len(set(arms)) != len(arms) or set(arms) - {'old', 'parsed'}:
        raise ValueError('invalid_ablation_arms')
    output.mkdir(parents=True, exist_ok=resume)
    index = json.loads(index_path.read_bytes())
    with (index_path.parent / 'vectors.npy').open('rb') as stream:
        if file_digest(stream, 'sha256').hexdigest() != index['matrix_sha256']:
            raise ValueError('old_matrix_changed')
    old_matrix = np.load(index_path.parent / 'vectors.npy', mmap_mode='r')
    for filename, field in [('navigation.sqlite', 'navigation_index'), ('lexical.sqlite', 'lexical_index')]:
        with (index_path.parent / filename).open('rb') as stream:
            if file_digest(stream, 'sha256').hexdigest() != index[field]['sha256']:
                raise ValueError('published_support_index_changed')
    replacement = json.loads((embeddings / 'units.json').read_bytes())
    ids = json.loads((embeddings / 'identities.json').read_bytes())
    new_matrix = np.load(embeddings / 'vectors.npy', mmap_mode='r')
    new_positions = {key: i for i, key in enumerate(ids)}
    replaced = {u['document_id'] for u in replacement}
    vectors = {q['id']: q['vector'] for q in json.loads(query_vectors.read_bytes())['questions']}
    questions = json.loads((base / 'questions.json').read_bytes())['questions']
    summary = {'status': 'running', 'samples': [], 'provider_calls': 0,
               'scope': 'paired representation ablation; frozen original planner population; no graph or financial fact filters',
               'changed_documents': sorted(replaced), 'background_removed': False,
               'inputs': {str(p): sha256(p.read_bytes()).hexdigest() for p in [index_path, query_vectors, embeddings / 'plan.json', embeddings / 'units.json', embeddings / 'identities.json', base / 'questions.json']}}
    with (embeddings / 'vectors.npy').open('rb') as stream:
        summary['inputs'][str(embeddings / 'vectors.npy')] = file_digest(stream, 'sha256').hexdigest()
    if resume:
        previous = json.loads((output / 'summary.json').read_bytes())
        if previous['inputs'] != summary['inputs'] or previous['changed_documents'] != summary['changed_documents']:
            raise ValueError('resume_input_identity_changed')
        summary['samples'] = previous['samples']
    complete = {(s['id'], s['arm']) for s in summary['samples']}
    with sqlite3.connect((index_path.parent / 'navigation.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db, \
         sqlite3.connect((index_path.parent / 'lexical.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as lex:
        db.execute('PRAGMA cache_size=-2048')
        lex.execute('PRAGMA cache_size=-2048')

        def materialize(record):
            if record['vector_origin'] != 'old':
                return record
            packed = db.execute('SELECT payload FROM nodes WHERE node_id=?', (record['node_id'],)).fetchone()
            raw = zlib.decompress(packed[0])
            if sha256(raw).hexdigest() != record['navigation_sha256']:
                raise ValueError('original_navigation_changed')
            source = json.loads(raw)
            return {k: v for k, v in record.items() if k not in ('navigation_sha256', 'lexical_input_sha256')} | {
                'content': source['content'], 'embedding_context': source.get('embedding_context', ''),
                'original_source': source['original_source']}

        def lexical_corpus(rows):
            for row in rows:
                if row['vector_origin'] == 'old' and row['lexical_input_sha256'] == row['content_sha256']:
                    saved = lex.execute('SELECT content_digest,lexical_digest,length,counts FROM nodes WHERE node_id=?',
                                        (row['node_id'],)).fetchone()
                    if saved is None or saved[:2] != (row['content_sha256'], row['lexical_input_sha256']):
                        raise ValueError('published_lexical_identity_mismatch')
                    yield TokenCounts(saved[2], json.loads(zlib.decompress(saved[3])))
                else:
                    source = materialize(row)
                    counts = Counter(tokenize(source.get('lexical_input', source['content'])))
                    yield TokenCounts(sum(counts.values()), counts)

        cached_scope, cached_old = None, None
        for q in questions:
            if all((q['id'], arm) in complete for arm in arms):
                continue
            scope = frozenset(q['prior_scope'])
            if scope != cached_scope:
                old = []
                for record in index['records']:
                    if record['document_id'] not in scope:
                        continue
                    old.append({'node_id': record['node_id'], 'document_id': record['document_id'],
                                'content_sha256': record['content_sha256'],
                                'navigation_sha256': record['navigation_sha256'],
                                'lexical_input_sha256': record['lexical_input_sha256'], 'kind': 'old_chunk',
                                'vector_index': record['vector_index'], 'vector_origin': 'old'})
                cached_scope, cached_old = scope, old
            old = cached_old
            added = [{'node_id': u['id'], 'document_id': u['document_id'], 'content': u['body'],
                      'lexical_input': u.get('lexical_input', u['body']),
                      'content_sha256': sha256(u['body'].encode()).hexdigest(),
                      'embedding_context': u['embedding_input'][:-len(u['body'])].strip(),
                      'original_source': {'raw_sha256': u['source_sha256'], 'url': u['url'], 'derived_references': u['derived_references']},
                      'kind': u['kind'], 'vector_index': new_positions[u['input_sha256']], 'vector_origin': 'new'}
                     for u in replacement if u['document_id'] in scope]
            # Duplicate exact input/body within one original should not consume
            # extra slots. Different originals/versions remain distinct.
            seen = set(); unique = []
            for row in added:
                key = (row['document_id'], row['content_sha256'], row['embedding_context'])
                if key not in seen:
                    unique.append(row); seen.add(key)
            paired = {'old': old, 'parsed': [r for r in old if r['document_id'] not in replaced] + unique}
            query = np.asarray(vectors[q['id']], dtype=np.float32)
            query /= np.linalg.norm(query)
            routes, translations = lexical_surfaces(q['query'])
            for arm, rows in paired.items():
                if arm not in arms:
                    continue
                dense = np.zeros(len(rows), dtype=np.float32)
                for start in range(0, len(rows), 512):
                    rs = rows[start:start+512]
                    matrix = np.stack([(old_matrix if r['vector_origin'] == 'old' else new_matrix)[r['vector_index']] for r in rs])
                    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
                    dense[start:start+len(rs)] = matrix @ query
                lexical, raw_scores = [], []
                for route in routes:
                    scores, overlap, _ = lexical_scores(lexical_corpus(rows), route)
                    scores = list(scores); raw_scores.append(scores)
                    lexical.append([rows[i]['node_id'] for i in sorted(overlap, key=lambda i: (-scores[i], rows[i]['node_id']))])
                candidates, order, limits = fuse_channels(rows, dense, interleave(lexical), policy='needs_units.v1', lexical_policy='organization-financial-needs.v2')
                chosen = set(candidates['ordered']); selected = [materialize(r) for r in rows if r['node_id'] in chosen]
                with gzip.open(output / (q['id'] + '.' + arm + '.scores.jsonl.gz'), 'wt', encoding='utf8') as stream:
                    for i, row in enumerate(rows):
                        stream.write(json.dumps({'id': row['node_id'], 'document_id': row['document_id'],
                                                'dense': float(dense[i]), 'bm25': [float(s[i]) for s in raw_scores]}, ensure_ascii=False) + '\n')
                result = {'id': q['id'], 'query': q['query'], 'arm': arm, 'population': len(rows), 'scope': sorted(scope),
                          'channels': candidates, 'limits': limits, 'translations': translations,
                          'candidates': selected, 'dense_top10': [rows[i]['node_id'] for i in order[:10]],
                          'complete_prequota_scores': True}
                (output / (q['id'] + '.' + arm + '.json')).write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
                summary['samples'].append({'id': q['id'], 'arm': arm, 'population': len(rows), 'candidates': len(selected)})
            (output / 'summary.json').write_text(json.dumps(summary), encoding='utf8')
            print(json.dumps({'queries_completed': len({s['id'] for s in summary['samples']}), 'total': len(questions)}), flush=True)
            gc.collect()
    summary['status'] = 'completed'
    (output / 'summary.json').write_text(json.dumps(summary), encoding='utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--arms', nargs='+', choices=('old', 'parsed'), default=['old', 'parsed'])
    for key in ('base', 'index', 'query-vectors', 'embeddings', 'output'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    run(a.base, a.index, a.query_vectors, a.embeddings, a.output, resume=a.resume, arms=tuple(a.arms))
