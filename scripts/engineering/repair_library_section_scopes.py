"""Reconcile SEC section scopes over every selected artifact in a frozen ledger.

Keeps non-SEC results and derived-only bindings. Only changed documents are
materialized; input identities and content conservation are checked before use.
"""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path
import shutil
import time

from build_library_structure_completion_ledger import digest, check_repair_preservation
from refine_document_chapters import refine
from validate_source_structure_audit import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'ledger', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    rows = [json.loads(line) for line in args.ledger.read_text(encoding='utf8').splitlines()]
    if (len(rows) != manifest['source_bindings'] or len({r['document_id'] for r in rows}) != len(rows)
            or {r['document_id'] for r in rows} != {s['document_id'] for s in manifest['sources']}):
        raise ValueError('ledger_scope_mismatch')
    expected = {binding: job['id'] for job in manifest['jobs'] for binding in job['bindings']}
    if any(row.get('original_id') != expected.get(row['document_id']) for row in rows):
        raise ValueError('ledger_original_binding_changed')
    originals = {}
    for row in rows:
        if row.get('original_id'):
            sid = row['original_id']
            if sid in originals and any(originals[sid][k] != row[k] for k in ('artifact_path','artifact_sha256')):
                raise ValueError('conflicting_original_artifacts')
            originals[sid] = row
    if set(originals) != {j['id'] for j in manifest['jobs']}:
        raise ValueError('original_scope_mismatch')
    root = Path(__file__).resolve().parents[2]
    identity = {'manifest_sha256': digest(args.manifest), 'ledger_sha256': digest(args.ledger),
                'code': {name: digest(root/name) for name in [
                    'scripts/engineering/repair_library_section_scopes.py',
                    'scripts/engineering/refine_document_chapters.py',
                    'scripts/engineering/source_structure_contract.py',
                    'scripts/engineering/build_library_structure_completion_ledger.py',
                    'scripts/engineering/validate_source_structure_audit.py',
                    'scripts/engineering/document_structure_audit.py',
                    'src/retrieval/narrative_chunks.py']}, 'provider_calls': 0}
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ('documents', 'receipts'):
        (args.output/name).mkdir(exist_ok=True)
    stamp = args.output/'identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes()) != identity:
        raise ValueError('scope_repair_identity_changed')
    stamp.write_text(json.dumps(identity, indent=2), encoding='utf8')
    receipts = {}; counts = Counter()
    for sid, parent in originals.items():
        started = time.perf_counter()
        path = Path(parent['artifact_path'])
        if digest(path) != parent['artifact_sha256']:
            raise ValueError('parent_artifact_changed:'+sid)
        target = args.output/'receipts'/f'{sid}.json'
        if target.exists():
            row = json.loads(target.read_bytes())
            if row['parent_artifact_sha256'] != parent['artifact_sha256'] or digest(Path(row['artifact_path'])) != row['artifact_sha256']:
                raise ValueError('resume_artifact_changed:'+sid)
        else:
            row = {'id': sid, 'route': parent['route'], 'status': 'parent_retained',
                   'parent_artifact_path': str(path), 'parent_artifact_sha256': parent['artifact_sha256'],
                   'artifact_path': str(path), 'artifact_sha256': parent['artifact_sha256'],
                   'issues': parent['issues'], 'headings': parent.get('headings')}
            if parent['route'] == 'edgartools':
                with gzip.open(path, 'rt', encoding='utf8') as stream:
                    before = json.load(stream)
                after = refine(before)
                check_repair_preservation(before, after)
                errors = validate(after)
                if errors:
                    raise ValueError('structure_validation:'+sid+':'+str(errors))
                changed = any(before.get(k) != after.get(k) for k in ('chapter_tree','outline','pre_chunks','issues'))
                row['scope_structure_checked'] = True
                if changed:
                    old_nodes = {n['id']: n for n in before['chapter_tree']}
                    updates = [{k: n.get(k) for k in ('id','title','parent_id','level','basis')}
                               for n in after['chapter_tree'] if any(
                                   old_nodes.get(n['id'],{}).get(k) != n.get(k) for k in ('parent_id','level','basis'))]
                    payload = gzip.compress(json.dumps(after,ensure_ascii=False).encode('utf8'), compresslevel=3, mtime=0)
                    if shutil.disk_usage(args.output).free < len(payload)+128*1024*1024:
                        raise RuntimeError('insufficient_space_before_artifact_write')
                    destination = args.output/'documents'/f'{sid}.json.gz'
                    destination.write_bytes(payload)
                    row.update(status='section_scope_repaired', artifact_path=str(destination),
                               artifact_sha256=digest(destination), issues=dict(Counter(i['kind'] for i in after['issues'])),
                               headings=len(after['outline']), chapter_changes=updates,
                               ordered_text_and_full_table_payload='preserved')
                    del payload
                del before, after
            row['elapsed_seconds'] = time.perf_counter()-started
            target.write_text(json.dumps(row,ensure_ascii=False),encoding='utf8')
        receipts[sid] = row; counts[row['status']] += 1
        gc.collect()
        if len(receipts)%100 == 0:
            print(json.dumps({'processed':len(receipts),**counts}),flush=True)
    for row in rows:
        if row.get('original_id'):
            receipt = receipts[row['original_id']]
            row['section_scope_check'] = receipt['status']
            if receipt['status']=='section_scope_repaired':
                for key in ('artifact_path','artifact_sha256','issues','headings','parent_artifact_path',
                            'parent_artifact_sha256','ordered_text_and_full_table_payload'):
                    row[key] = receipt[key]
                row['execution_state'] = 'section_scope_repaired'
                row['quality_state'] = 'diagnostics_require_review' if row['issues'] else 'type_quality_review_required'
    ledger = args.output/'bindings.jsonl'
    ledger.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf8')
    summary = {'source_bindings':len(rows),'unique_originals':len(originals),'original_results':dict(counts),
               'binding_execution':dict(Counter(r['execution_state'] for r in rows)),
               'remaining_issue_originals':dict(Counter(k for r in receipts.values() for k in r['issues'])),
               'changed_chapters':sum(len(r.get('chapter_changes',[])) for r in receipts.values()),
               'ledger_sha256':digest(ledger),'provider_calls':0,'final_semantic_quality':'not_established'}
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary),flush=True)


if __name__ == '__main__':
    main()
