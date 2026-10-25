"""Compare fixed candidate lists without providers or changes to serving policy.

Only development/historical records are accepted. Exact duplicate identity keeps
the frozen document/version and embedding context; identical text in different
documents or contexts is deliberately NOT treated as interchangeable evidence.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from retrieval.rank_fusion import reciprocal_rank_fusion
from scripts.engineering.qualify_retrieval_recall import ranking_metrics


def identity(record):
    fields = ('document_id', 'content_sha256', 'embedding_input_sha256')
    if any(not isinstance(record.get(k), str) or not record[k] for k in fields):
        raise ValueError('ablation_missing_frozen_identity')
    return tuple(record[k] for k in fields)


def variants(rankings, records):
    channels = [rankings['dense_candidates'], rankings['lexical_candidates']]
    if 'graph_candidates' in rankings:
        channels.append(rankings['graph_candidates'])
    for channel in channels:
        if len(channel) != len(set(channel)) or any(n not in records for n in channel):
            raise ValueError('ablation_invalid_candidate_identity')
    fused_key = 'graph_fused_candidates' if len(channels) == 3 else 'fused_candidates'
    baseline = reciprocal_rank_fusion(channels)
    if baseline != rankings[fused_key]:
        raise ValueError('ablation_baseline_order_mismatch')

    # No extra candidates are fetched, no gold labels affect selection. Doubling
    # one channel is exactly a weight of two, NOT a tuned production default.
    results = {'equal_rrf': baseline, 'dense_only': channels[0],
               'dense_weight_2_rrf': reciprocal_rank_fusion([channels[0], *channels])}
    canonical, aliases = {}, {}
    for node in baseline:
        representative = canonical.setdefault(identity(records[node]), node)
        aliases.setdefault(representative, []).append(node)
    dedup_channels = []
    for channel in channels:
        dedup_channels.append(list(dict.fromkeys(canonical[identity(records[n])] for n in channel)))
    results['exact_context_dedup_rrf'] = reciprocal_rank_fusion(dedup_channels)
    return results, aliases


def compare(result, index):
    samples = result.get('samples', [])
    if (result.get('status') != 'completed' or not samples
            or len(samples) != result.get('expected_questions')
            or len({s['id'] for s in samples}) != len(samples)):
        raise ValueError('ablation_requires_complete_results')
    historical = result.get('evaluation_role') == 'historical_regression'
    if not historical and (result.get('split') != 'development'
                           or any(s.get('split') != 'development' for s in samples)):
        raise ValueError('ablation_development_only')
    if (len(index['records']) != result['candidate_chunks']
            or len({r['document_id'] for r in index['records']}) != result['candidate_sources']):
        raise ValueError('ablation_scope_mismatch')
    records = {r['node_id']: r for r in index['records']}
    if len(records) != len(index['records']):
        raise ValueError('ablation_duplicate_index_id')
    counts = Counter(identity(r) for r in records.values())
    output = []
    for sample in samples:
        if sample.get('status') != 'completed' or any(n not in records for n in sample['gold']):
            raise ValueError('ablation_failed_sample_or_missing_label')
        # Keep non-graph and graph experiments separate; graph need not improve.
        for graph in (False, True):
            ranks = sample['rankings']
            if graph and 'graph_candidates' not in ranks:
                continue
            if not graph:
                ranks = {k: v for k, v in ranks.items() if not k.startswith('graph_')}
            ranked, aliases = variants(ranks, records)
            metrics = {k: ranking_metrics(v, sample['gold']) for k, v in ranked.items()}
            # Strict IDs remain the primary result. Alias-aware evidence is
            # separate, so collapsing a duplicate cannot silently inflate gold.
            equivalent_gold = {rep for rep, members in aliases.items()
                               if any(n in sample['gold'] for n in members)}
            output.append({'id': sample['id'], 'family': sample['family'], 'graph': graph,
                'gold': sample['gold'], 'rankings': ranked, 'strict_metrics': metrics,
                'duplicate_groups': {k: v for k, v in aliases.items() if len(v) > 1},
                'dedup_equivalent_hit10': any(n in equivalent_gold
                    for n in ranked['exact_context_dedup_rrf'][:10])})
    summary = {}
    for graph in (False, True):
        rows = [r for r in output if r['graph'] == graph]
        if not rows:
            continue
        channel_summary = {}
        for name in rows[0]['rankings']:
            hits = [r['strict_metrics'][name]['known_hit@10'] for r in rows]
            families = {}
            for r, hit in zip(rows, hits):
                families.setdefault(r['family'], []).append(hit)
            channel_summary[name] = {'known_hit10_count': sum(hits),
                'family_macro_known_hit10': sum(sum(v)/len(v) for v in families.values())/len(families),
                'gained_vs_equal': [r['id'] for r, h in zip(rows, hits)
                    if h > r['strict_metrics']['equal_rrf']['known_hit@10']],
                'lost_vs_equal': [r['id'] for r, h in zip(rows, hits)
                    if h < r['strict_metrics']['equal_rrf']['known_hit@10']]}
        summary['graph' if graph else 'hybrid'] = channel_summary
    return {'status': 'completed', 'diagnostic_only': True, 'S2_passed': False,
        'provider_calls': 0, 'serving_policy_changed': False,
        'limits': 'Fixed already-retrieved candidates; no refill, new recall, current ACL or service latency test. Strict original labels, not exhaustive relevance.',
        'candidate_sources': result['candidate_sources'], 'candidate_chunks': len(records),
        'questions': len(samples), 'families': len({s['family'] for s in samples}),
        'corpus_exact_context_duplicate_groups': sum(v > 1 for v in counts.values()),
        'corpus_exact_context_extra_nodes': sum(v-1 for v in counts.values()),
        'samples': output, 'summary': summary}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('result', 'index', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'failed', 'S2_passed': False, 'provider_calls': 0}
    try:
        raw_result, raw_index = args.result.read_bytes(), args.index.read_bytes()
        source = json.loads(raw_result)
        if sha256(raw_index).hexdigest() != source['index_sha256']:
            raise ValueError('ablation_index_hash_mismatch')
        report = compare(source, json.loads(raw_index))
        report['inputs'] = {'result': str(args.result), 'result_sha256': sha256(raw_result).hexdigest(),
                            'index': str(args.index), 'index_sha256': sha256(raw_index).hexdigest()}
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
