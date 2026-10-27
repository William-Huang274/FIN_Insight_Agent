"""Summarize one frozen source-first batch without certifying full S2 delivery.

Scores accept alternate overlapping chunks only under the runner's checked
original source/version contract. Missing executions stay in the denominator.
Full product, permission, corpus-slice and capacity gates remain separate.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import mean


def summarize(dataset, report, plan, *, dataset_sha256, plan_sha256):
    if (plan['dataset_sha256'] != dataset_sha256
            or report['plan_sha256'] != plan_sha256):
        raise ValueError('evaluation_freeze_identity_mismatch')
    freeze = dataset['freeze']
    if (freeze['status'] != 'frozen'
            or freeze.get('heldout_prior_results_exposed') is not False
            or dataset['evaluation_role'] != 'independent_source_first'):
        raise ValueError('unexposed_independent_freeze_required')
    questions = dataset['questions']
    expected = {q['id']: q for q in questions}
    samples = {s['id']: s for s in report['samples']}
    if (not questions or len(expected) != len(questions)
            or len(samples) != len(report['samples']) or not set(samples) <= set(expected)):
        raise ValueError('duplicate_or_unexpected_evaluation_rows')
    label_errors = report.get('label_review_errors', [])
    if not isinstance(label_errors, list) or any(not isinstance(e, dict) or not e.get('reason') for e in label_errors):
        raise ValueError('invalid_label_review_errors')
    rows = []
    for q in questions:
        if q['question_kind'] not in ('positive_fact_request', 'false_premise_corrective_evidence'):
            raise ValueError('unsupported_question_kind')
        s = samples.get(q['id'])
        metric = s['span_metrics']['selected'] if s else None
        if metric is not None:
            hits = metric['groups']
            if (not hits or len(hits) != len(q['reviewed_spans'])
                    or any(type(h) is not bool for h in hits)
                    or type(metric['complete']) is not bool
                    or metric['complete'] != all(hits)
                    or not isfinite(metric['group_recall'])
                    or abs(metric['group_recall'] - mean(hits)) > 1e-12):
                raise ValueError('inconsistent_span_metrics')
        rows.append({'id':q['id'], 'family':q['family'], 'language':q['language'],
                     'kind':q['question_kind'], 'executed':s is not None,
                     'complete10':bool(metric and metric['complete']),
                     'span_recall10':metric['group_recall'] if metric else 0.,
                     'strict_minimum_cover_complete10':bool(s and s['metrics']['selected']['complete'])})
    by_kind = {}
    thresholds = freeze['acceptance']
    passed = report['status'] == 'completed' and len(samples) == len(expected) and not label_errors
    for kind, threshold_key in [('positive_fact_request','positive_complete_evidence_at10'),
                                ('false_premise_corrective_evidence','counterclaim_corrective_evidence_at10')]:
        subset = [r for r in rows if r['kind'] == kind]
        families = defaultdict(list)
        for r in subset:
            families[r['family']].append(r)
        complete = mean(mean(r['complete10'] for r in f) for f in families.values()) if families else 0.
        recall = mean(mean(r['span_recall10'] for r in f) for f in families.values()) if families else 0.
        by_kind[kind] = {'questions':len(subset), 'families':len(families),
                         'complete10':sum(r['complete10'] for r in subset),
                         'family_macro_complete10':complete, 'family_macro_span_recall10':recall}
        passed = passed and bool(subset) and complete >= thresholds[threshold_key] and recall >= thresholds['known_group_recall_at10']
    return {'scope':'one frozen source-first batch, not complete delivery gate',
            'batch_quality_passed':bool(passed), 'S2_passed':False,
            'execution_status':report['status'], 'expected':len(questions), 'executed':len(samples),
            'label_review_errors':label_errors,
            'families':len({q['family'] for q in questions}), 'by_kind':by_kind, 'rows':rows,
            'limits':['corrective evidence is not no-answer or answer correctness',
                      'source families and bilingual variants are correlated',
                      'no live permission or service capacity claim',
                      'full retrieval_delivery_gate remains required']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('attempt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = {name:(args.attempt/(name+'.json')).read_bytes() for name in ('dataset','plan','result')}
    result = summarize(json.loads(raw['dataset']), json.loads(raw['result']), json.loads(raw['plan']),
                       dataset_sha256=sha256(raw['dataset']).hexdigest(), plan_sha256=sha256(raw['plan']).hexdigest())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
