"""Replay saved dense scores with parser-only units removed; no provider calls.

This is not a new candidate, BM25 or rerank run. Do not report its rank changes
as final Precision/nDCG improvement. Preserve original runs and publications.
"""
import argparse
from collections import Counter
from contextlib import closing
from hashlib import sha256, file_digest
import json
from pathlib import Path
import sqlite3
import zlib

from retrieval.structural_surface import structural_only


def audit(catalog, run, judgments):
    catalog, run, judgments = map(Path, (catalog, run, judgments))
    excluded = {}
    with closing(sqlite3.connect(catalog.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        db.execute('PRAGMA cache_size=-2048')
        for identifier, parent, digest, input_digest, packed in db.execute(
                'SELECT id,parent,digest,input_digest,payload FROM units'):
            unit = json.loads(zlib.decompress(packed))
            if (unit['unit_id'] != identifier or unit['parent_node_id'] != parent
                    or sha256(unit['content'].encode()).hexdigest() != digest
                    or sha256((unit['embedding_context']+'\n'+unit['content']).encode()).hexdigest() != input_digest):
                raise ValueError('structural_audit_catalog_mismatch')
            if structural_only(unit['content']):
                excluded[identifier] = unit
    rows, counts = [], Counter()
    result_bytes = (run/'result.json').read_bytes()
    for sample in json.loads(result_bytes)['samples']:
        job_bytes = (run/(sample['id']+'.input.json')).read_bytes()
        job = json.loads(job_bytes)
        proof = job['retrieval_receipt']['full_dense_units_artifact']
        trace = (run/proof['file']).resolve()
        if not trace.is_relative_to(run.resolve()):
            raise ValueError('structural_audit_trace_outside_run')
        with trace.open('rb') as stream:
            if file_digest(stream, 'sha256').hexdigest() != proof['sha256']:
                raise ValueError('structural_audit_trace_changed')
        before, after = {}, {}
        with trace.open(encoding='utf8') as stream:
            for line in stream:
                unit = json.loads(line); parent = unit['parent_node_id']
                removed = excluded.get(unit['node_id'])
                if removed and (removed['parent_node_id'] != parent
                        or removed['source_interval'] != unit['source_interval']):
                    raise ValueError('structural_audit_trace_identity_mismatch')
                if parent not in before or unit['score'] > before[parent]['score']:
                    before[parent] = unit
                if not removed and (parent not in after or unit['score'] > after[parent]['score']):
                    after[parent] = unit
        label_bytes = (judgments/(sample['id']+'.json')).read_bytes()
        labels = {}
        for label in json.loads(label_bytes):
            if label['question_id'] != sample['id'] or label['query_sha256'] != sha256(job['query'].encode()).hexdigest():
                raise ValueError('structural_audit_judgment_question_changed')
            labels[(label['node_id'], label['content_sha256'])] = label
        bodies = {c['node_id']: c['content_sha256'] for c in job['candidates']}
        ranks = lambda values: {n:i+1 for i,(n,_) in enumerate(sorted(values.items(), key=lambda p:-p[1]['score']))}
        old_ranks, new_ranks = ranks(before), ranks(after)
        changes = []
        for parent, unit in before.items():
            if unit['node_id'] not in excluded:
                continue
            grade = labels.get((parent, bodies.get(parent)), {}).get('grade')
            selected = parent in sample['selected_ids'][:10]
            if selected:
                counts['selected_top10_marker_winner'] += 1
                counts['selected_grade_'+str(grade)] += 1
            changes.append({'node':parent, 'before_score':unit['score'],
                'after_score':after.get(parent, {}).get('score'),
                'before_dense_rank':old_ranks[parent], 'after_dense_rank':new_ranks.get(parent),
                'grade':grade, 'was_selected_top10':selected,
                'winning_content':excluded[unit['node_id']]['content']})
        rows.append({'question_id':sample['id'], 'changed_parents':changes,
            'input_sha256':sha256(job_bytes).hexdigest(), 'trace_sha256':proof['sha256'],
            'judgments_sha256':sha256(label_bytes).hexdigest()})
    with catalog.open('rb') as stream:
        catalog_digest = file_digest(stream, 'sha256').hexdigest()
    return {'scope':'saved_dense_scores_only_not_new_candidates_or_final_quality', 'provider_calls':0,
        'catalog_sha256':catalog_digest, 'result_sha256':sha256(result_bytes).hexdigest(),
        'excluded_units':len(excluded),
        'excluded_unique_inputs':len({u['embedding_input_sha256'] for u in excluded.values()}),
        'counts':dict(counts), 'queries':rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','run','judgments','output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.catalog, args.run, args.judgments)
    with args.output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='queries'}))
