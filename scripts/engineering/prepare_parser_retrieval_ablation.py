"""Freeze an exposed-regression parser ablation; never change a live index."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import zlib


def freeze(run, judgments, inventory, captures, output):
    output.mkdir(parents=True, exist_ok=False)
    (output / 'raw').mkdir()
    result = json.loads((run / 'result.json').read_bytes())
    inventory_rows = {r['document_id']: r for r in
                      map(json.loads, inventory.read_text(encoding='utf8').splitlines())}
    selected, metadata, questions, unavailable = {}, {}, [], []
    # Include both successful evidence and all prior top-ten errors. Selection
    # is frozen before parsing; it does not discard difficult negative sources.
    for sample in result['samples']:
        data = json.loads((run / (sample['id'] + '.input.json')).read_bytes())
        candidates = {r['node_id']: r for r in data['candidates']}
        metadata.update(data['metadata'])
        labels = json.loads((judgments / (sample['id'] + '.json')).read_bytes())
        ids = set(sample['selected_ids'][:10]) | {r['node_id'] for r in labels if r['grade'] >= 2}
        for node in ids:
            document = (candidates[node]['parent_document_id'] if node in candidates else
                        'ORGDOC::' + node.split('::', 1)[1].split(':chunk-')[0])
            selected.setdefault(document, set()).add(sample['id'])
        questions.append({'id': sample['id'], 'query': data['query'],
                          'prior_top10': sample['selected_ids'][:10],
                          'prior_scope': sorted(data['metadata']), 'labels': labels})
    samples = []
    with sqlite3.connect(captures.resolve().as_uri() + '?mode=ro', uri=True) as db:
        for document in sorted(selected):
            inv = inventory_rows.get(document)
            if not inv:
                unavailable.append({'document_id': document, 'reason': 'no_frozen_inventory'}); continue
            rows = db.execute('SELECT digest,body_zlib FROM raw_captures WHERE url=? AND status=200 ORDER BY captured_at DESC', (inv['url'],)).fetchall()
            if not rows:
                unavailable.append({'document_id': document, 'reason': 'no_original_capture', 'url': inv['url']}); continue
            digest, packed = rows[0]
            raw = zlib.decompress(packed)
            if sha256(raw).hexdigest() != digest:
                raise ValueError('raw_capture_digest_mismatch')
            sid = 'source-' + sha256(document.encode()).hexdigest()[:16]
            path = output / 'raw' / (sid + '.html')
            path.write_bytes(raw)
            samples.append({'id': sid, 'document_id': document, 'path': str(path.resolve()),
                            'title': inv['title'], 'url': inv['url'], 'raw_sha256': digest,
                            'bytes': len(raw), 'form': metadata.get(document, {}).get('form') or '',
                            'prior_parser': inv.get('parser'), 'questions': sorted(selected[document]),
                            'capture_selection': 'latest_archived_http_200_not_refetched',
                            'family': 'sec' if 'sec.gov/' in inv['url'] else 'web'})
    manifest = {'scope': 'exposed 44-question source-parser ablation; prior positive and top10 negative documents',
                'inputs': {str(p): sha256(p.read_bytes()).hexdigest() for p in [run / 'result.json', inventory]},
                'samples': samples, 'unavailable': unavailable, 'live_migration': False}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    (output / 'questions.json').write_text(json.dumps({'questions': questions}, ensure_ascii=False), encoding='utf8')
    (output / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False), encoding='utf8')
    print(json.dumps({'sources': len(samples), 'unavailable': unavailable, 'bytes': sum(s['bytes'] for s in samples),
                      'families': dict(Counter(s['family'] for s in samples)), 'questions': len(questions)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('run', 'judgments', 'inventory', 'captures', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    a = parser.parse_args()
    freeze(a.run, a.judgments, a.inventory, a.captures, a.output)
