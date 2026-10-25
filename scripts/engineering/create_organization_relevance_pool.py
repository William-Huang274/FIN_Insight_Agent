"""Anonymized development judgment pool; never alters a query or its gold labels.

Pool all submitted strategies and original anchors before reviewing relevance.
The review file deliberately omits strategy names, original ranks and whether a
passage was an anchor. The separate audit file preserves their provenance.
"""
from contextlib import closing
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sqlite3
import zlib


def build(dataset_path, result_paths, index_path):
    dataset_raw = dataset_path.read_bytes()
    dataset = json.loads(dataset_raw)
    questions = {q['id']: q for q in dataset['questions'] if q['split'] == 'development'}
    index_raw = index_path.read_bytes()
    index = json.loads(index_raw)
    records = {r['node_id']: r for r in index['records']}
    if len(records) != len(index['records']):
        raise ValueError('pool_duplicate_index_identity')
    pooled = {identifier: set() for identifier in questions}
    provenance = []
    for path in result_paths:
        raw = path.read_bytes(); result = json.loads(raw)
        if (result.get('status') != 'completed' or result.get('split') != 'development'
                or result.get('dataset_sha256') != sha256(dataset_raw).hexdigest()
                or result.get('index_sha256') != sha256(index_raw).hexdigest()
                or len(result['samples']) != len(questions)
                or {s['id'] for s in result['samples']} != set(questions)):
            raise ValueError('pool_requires_complete_same_development_dataset_and_index')
        for sample in result['samples']:
            if sample['status'] != 'completed' or sample['split'] != 'development':
                raise ValueError('pool_failed_or_non_development_sample')
            nodes = set(sample['gold'])
            for ranking in sample['rankings'].values():
                if len(ranking) != len(set(ranking)):
                    raise ValueError('pool_duplicate_ranked_identity')
                nodes.update(ranking)
            if not nodes <= records.keys():
                raise ValueError('pool_unknown_candidate')
            pooled[sample['id']].update(nodes)
        provenance.append({'path': str(path), 'sha256': sha256(raw).hexdigest()})
    if not provenance:
        raise ValueError('pool_requires_candidate_results')
    review = []
    with closing(sqlite3.connect(index_path.parent.joinpath('navigation.sqlite').resolve().as_uri()+'?mode=ro', uri=True)) as db:
        for identifier, question in questions.items():
            passages = []
            # Content-independent, reproducible order. No score or original
            # rank is an input to this order or to subsequent human judgments.
            for node in sorted(pooled[identifier], key=lambda n: sha256((identifier+'|'+n).encode()).hexdigest()):
                row = db.execute('SELECT payload FROM nodes WHERE node_id=?', (node,)).fetchone()
                if row is None:
                    raise ValueError('pool_candidate_missing')
                payload = zlib.decompress(row[0])
                if sha256(payload).hexdigest() != records[node]['navigation_sha256']:
                    raise ValueError('pool_candidate_changed')
                candidate = json.loads(payload)
                if candidate['node_id'] != node or sha256(candidate['content'].encode()).hexdigest() != records[node]['content_sha256']:
                    raise ValueError('pool_candidate_body_identity_mismatch')
                passages.append({'node_id': node, 'document_id': records[node]['document_id'],
                    'content_sha256': records[node]['content_sha256'], 'context': candidate.get('embedding_context', ''),
                    'content': candidate['content'], 'judgment': None, 'evidence_group': None, 'reason': ''})
            review.append({'id': identifier, 'family': question['family'], 'query': question['query'],
                           'as_of': question['as_of'], 'passages': passages})
    return {'status': 'pending_review', 'evaluation_role': 'development_pooled_judgments',
        'dataset_sha256': sha256(dataset_raw).hexdigest(), 'index_sha256': sha256(index_raw).hexdigest(),
        'instructions': 'Judge original evidence, issuer, period, units and revision. Use complete, partial, irrelevant or conflicting. Different document versions are not equivalent merely because wording matches. Review cannot certify exhaustive corpus relevance.',
        'questions': review}, {'inputs': provenance, 'labels_changed': False, 'provider_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dataset', 'index', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--result', type=Path, action='append', required=True)
    args = parser.parse_args()
    review, audit = build(args.dataset, args.result, args.index)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in [('review', review), ('audit', audit)]:
        (args.output/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'status': review['status'], 'questions': len(review['questions']),
                      'passages': sum(len(q['passages']) for q in review['questions'])}))


if __name__ == '__main__':
    main()
