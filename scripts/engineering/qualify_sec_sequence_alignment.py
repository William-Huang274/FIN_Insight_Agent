"""Re-adapt a frozen SEC selection and prove compatibility with repaired output.

Serial child processes bound memory lifetime. Resume only successful receipts
under identical inputs/code; failed attempts are never retried implicitly.
"""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def checked_document(path, expected):
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('input_digest_changed:' + str(path))
    return json.loads(gzip.decompress(raw))


def compare(previous, result):
    if previous.get('source_containers') != result.get('source_containers'):
        raise ValueError('original_containers_changed')
    if len(previous['blocks']) != len(result['blocks']):
        raise ValueError('block_count_changed')
    delta = Counter()
    for old, new in zip(previous['blocks'], result['blocks']):
        for key in ('text', 'kind', 'headers', 'rows', 'footer', 'raw_text', 'source_lines', 'native_xml', 'structural_role'):
            if old.get(key) != new.get(key):
                raise ValueError('content_or_role_changed:' + key)
        if old.get('source_location_status') == 'unique_complete_container':
            if (new.get('source_location_status') != old['source_location_status']
                    or new.get('source_container_id') != old.get('source_container_id')):
                raise ValueError('previous_unique_location_lost')
        elif new.get('source_location_status') == 'unique_complete_container':
            delta['new_unique_original_locations'] += 1
        before = old.get('native_section_binding', {})
        after = new.get('native_section_binding', {})
        if before.get('status') == 'unique_native_membership':
            if after.get('status') != before['status'] or after['candidates'] != before['candidates']:
                raise ValueError('previous_unique_section_lost')
        elif after.get('status') == 'unique_native_membership':
            delta['new_unique_section_blocks'] += 1
    fields = ('start_block', 'end_block_exclusive', 'heading_source_id', 'attestation_source_id')
    old_scopes = {tuple(r[k] for k in fields) for r in previous.get('source_scope_repairs', [])}
    new_scopes = {tuple(r[k] for k in fields) for r in result.get('source_scope_repairs', [])}
    if not old_scopes <= new_scopes:
        raise ValueError('previous_signature_proof_lost')
    def bound(d):
        return {c for b in d['blocks'] for c in b.get('native_section_binding', {}).get('candidates', [])
                if b.get('native_section_binding', {}).get('status') == 'unique_native_membership'}
    delta['new_sections_with_blocks'] = len(bound(result) - bound(previous))
    return dict(delta)


def worker(a):
    from native_document_capture import read_capture
    from native_document_adaptation import adapt
    from document_structure_repairs import repair_sec_signatures
    from document_role_repairs import repair_context_roles
    from finalize_structure_prechunks import classify
    from validate_source_structure_audit import validate
    row = next(r for r in map(json.loads, a.plan.read_text(encoding='utf8').splitlines()) if r['id'] == a.worker)
    oid = row['id']; target = a.output / oid
    target.mkdir(exist_ok=False)
    receipt_path = a.adapted / oid / 'receipt.json'
    receipt = json.loads(receipt_path.read_bytes())
    if receipt['source_sha256'] != oid:
        raise ValueError('source_identity_mismatch')
    native = read_capture(a.captures / oid / 'native.json.gz', expected_sha256=receipt['native_sha256'], expected_source_sha256=oid)
    parent = checked_document(receipt['parent_fin_path'], receipt['parent_fin_sha256'])
    previous = checked_document(row['artifact_path'], row['artifact_sha256'])
    result = repair_context_roles(repair_sec_signatures(adapt(native, parent, native_paths_verified=receipt['native_paths_verified'])))
    changes = compare(previous, result)
    errors = validate(result)
    if errors:
        raise ValueError('invalid_structure:' + str(errors))
    chunks = classify(result)
    for name, content in [('document', result), ('prechunks', chunks)]:
        (target / (name + '.json.gz')).write_bytes(gzip.compress(json.dumps(content, ensure_ascii=False).encode(), mtime=0))
    bound = {c for b in result['blocks'] for c in b.get('native_section_binding', {}).get('candidates', [])
             if b.get('native_section_binding', {}).get('status') == 'unique_native_membership'}
    report = dict(id=oid, title=row['title'], changes=changes,
                  old_coverage=previous.get('native_section_coverage'), new_coverage=result.get('native_section_coverage'),
                  unbound_sections=sorted(set(native['native']['sections']) - bound),
                  alignments=result.get('native_sequence_alignments', []),
                  artifact_sha256=digest(target / 'document.json.gz'), prechunks_sha256=digest(target / 'prechunks.json.gz'),
                  input_receipt_sha256=digest(receipt_path), parent_sha256=receipt['parent_fin_sha256'],
                  comparison_sha256=row['artifact_sha256'], native_sha256=receipt['native_sha256'],
                  engineering_pass=True, quality_pass=False, provider_calls=0)
    save(target / 'receipt.json', report)


def run(a):
    import psutil
    files = ['native_section_alignment.py', 'native_document_adaptation.py', 'native_document_capture.py',
             'document_structure_repairs.py', 'document_role_repairs.py', 'source_structure_contract.py',
             'validate_source_structure_audit.py', 'finalize_structure_prechunks.py', Path(__file__).name]
    identity = dict(plan_sha256=digest(a.plan), captures=str(a.captures.resolve()), adapted=str(a.adapted.resolve()),
                    code={n:digest(HERE / n) for n in files}, python=sys.executable,
                    sentence_splitter_sha256=digest(HERE.parents[1] / 'src/retrieval/narrative_chunks.py'))
    a.output.mkdir(parents=True, exist_ok=True)
    stamp = a.output / 'identity.json'
    if stamp.exists() and json.loads(stamp.read_bytes()) != identity:
        raise ValueError('resume_identity_changed')
    save(stamp, identity)
    rows = list(map(json.loads, a.plan.read_text(encoding='utf8').splitlines()))
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('duplicate_plan_identity')
    completed = []; totals = Counter(); stop = None
    for row in rows:
        oid = row['id']; target = a.output / oid
        if not (target / 'receipt.json').exists():
            if target.exists() or (a.output / (oid + '.log')).exists():
                stop = dict(reason='incomplete_attempt_requires_review', id=oid); break
            free = psutil.virtual_memory().available // 1024**2
            if free < a.minimum_available_mib or shutil.disk_usage(a.output).free < 2*1024**3:
                stop = dict(reason='resource_pause', available_mib=free, id=oid); break
            command = [sys.executable, str(Path(__file__)), '--plan', str(a.plan), '--captures', str(a.captures),
                       '--adapted', str(a.adapted), '--output', str(a.output), '--worker', oid]
            started = time.monotonic()
            from run_native_structure_qualification import run_child
            code = run_child(command, a.output / (oid + '.log'), 600)
            if code:
                stop = dict(reason='worker_failure', id=oid, exit_code=code); break
            print(json.dumps(dict(id=oid, seconds=round(time.monotonic()-started,2))), flush=True)
        report = json.loads((target / 'receipt.json').read_bytes())
        if not report['engineering_pass'] or report['id'] != oid or report['comparison_sha256'] != row['artifact_sha256']:
            raise ValueError('invalid_prior_receipt:' + oid)
        for name in ('artifact', 'prechunks'):
            filename = 'document.json.gz' if name == 'artifact' else 'prechunks.json.gz'
            if digest(target / filename) != report[name + '_sha256']:
                raise ValueError('resume_artifact_changed:' + oid)
        if digest(a.adapted / oid / 'receipt.json') != report['input_receipt_sha256']:
            raise ValueError('resume_parent_receipt_changed:' + oid)
        original_receipt = json.loads((a.adapted / oid / 'receipt.json').read_bytes())
        if digest(original_receipt['parent_fin_path']) != report['parent_sha256']:
            raise ValueError('resume_parent_artifact_changed:' + oid)
        if digest(a.captures / oid / 'native.json.gz') != report['native_sha256'] or digest(row['artifact_path']) != row['artifact_sha256']:
            raise ValueError('resume_input_changed:' + oid)
        completed.append(report); totals.update(report['changes'])
        save(a.output / 'summary.json', dict(planned=len(rows), processed=len(completed), counts=dict(totals), rows=completed, stop_reason='running', quality_pass=False))
    changed = [n for n,h in identity['code'].items() if digest(HERE / n) != h]
    if digest(HERE.parents[1] / 'src/retrieval/narrative_chunks.py') != identity['sentence_splitter_sha256']:
        changed.append('narrative_chunks.py')
    final = dict(planned=len(rows), processed=len(completed), counts=dict(totals), rows=completed, stop_reason=stop,
                 changed_code=changed, engineering_pass=len(rows)==len(completed) and not stop and not changed,
                 quality_pass=False, provider_calls=0, published=False)
    save(a.output / 'summary.json', final)
    print(json.dumps({k:v for k,v in final.items() if k != 'rows'}), flush=True)
    return 0 if final['engineering_pass'] else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('plan', 'captures', 'adapted', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--worker'); p.add_argument('--minimum-available-mib', type=int, default=1024)
    args = p.parse_args()
    if args.minimum_available_mib < 1024:
        raise ValueError('insufficient_memory_guard')
    if args.worker:
        worker(args)
    else:
        raise SystemExit(run(args))
