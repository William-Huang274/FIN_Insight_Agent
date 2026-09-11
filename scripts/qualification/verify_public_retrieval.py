"""Recompute public top-five retrieval aggregates; no model, credentials or source text."""
from collections import defaultdict
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2] / 'docs/public'
    queries = {q['id']: q for q in json.loads((root/'evaluation/retrieval-queries.json').read_text(encoding='utf-8'))}
    rows = json.loads((root/'evaluation/retrieval-results.json').read_text(encoding='utf-8'))
    expected = json.loads((root/'evaluation-metrics.json').read_text(encoding='utf-8'))['retrieval']
    assert len(rows) == len(queries) == len({r['id'] for r in rows}) == 28
    totals = defaultdict(list)
    for row in rows:
        q = queries[row['id']]
        assert row['query'] == q['query']
        anchors = set(q['relevant_node_ids'])
        assert row['answerable'] == bool(anchors)
        if not anchors:
            continue
        for mode in ('bm25', 'dense', 'hybrid'):
            candidates = set(row[mode]['top5'])
            overlap = candidates & anchors
            hit, recall = bool(overlap), len(overlap) / len(anchors)
            assert hit == row[mode]['hit_at_5'], (row['id'], mode, 'hit')
            assert abs(recall - row[mode]['anchor_recall_at_5']) < 1e-9, (row['id'], mode, 'recall')
            totals[(q['split'], mode)].append((hit, recall))
    result = []
    for (split, mode), values in sorted(totals.items()):
        hit = sum(v[0] for v in values) / len(values)
        recall = sum(v[1] for v in values) / len(values)
        assert len(values) == expected[split]['positive_queries']
        for key, value in [('hit_at_5', hit), ('anchor_recall_at_5', recall)]:
            assert abs(expected[split]['metrics'][mode][key] - value) < 1e-9
        result.append({'split': split, 'mode': mode, 'n': len(values), 'hit_at_5': hit, 'anchor_recall_at_5': recall})
    print(json.dumps({'verified': result, 'provider_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
