"""Serial source-purpose and original Item-title repair over the whole ledger."""
import argparse
from collections import Counter
import gc
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from audit_source_binding_lineage import digest
from qualify_source_locations import memory_requirement, save


def worker(input_path, output):
    from qualify_embedded_section_titles import original
    from source_display_purpose import repair as apply_display, verify as verify_display
    from source_item_title_evidence import repair as apply_items, verify as verify_items
    from source_location_alignment import verify as verify_locations
    from validate_source_structure_audit import validate
    from finalize_structure_prechunks import classify
    job = json.loads(Path(input_path).read_bytes()); a = job['artifact']; out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    payload = Path(a['path']).read_bytes()
    if digest(payload) != a['sha256']:
        raise ValueError('parent_artifact_changed')
    old = json.loads(gzip.decompress(payload))
    raw = original(job['source'])
    updated, display = apply_display(old, raw)
    updated, titles, findings = apply_items(updated, raw)
    verify_display(updated, raw); verify_items(updated, raw); verify_locations(updated, raw)
    if validate(updated):
        raise ValueError('source_structure_contract_failed')
    if len(old['blocks']) != len(updated['blocks']) or old['pre_chunks'] != updated['pre_chunks']:
        raise ValueError('physical_blocks_or_prechunk_spans_changed')
    for before, after in zip(old['blocks'], updated['blocks']):
        if {k: v for k, v in before.items() if k != 'candidate_role'} != {k: v for k, v in after.items() if k != 'candidate_role'}:
            raise ValueError('physical_content_or_ownership_changed')
    for key in ('source_sha256', 'source_heading_units', 'source_scope_repairs', 'source_heading_scope_deferrals',
                'source_role_repairs', 'source_part_proofs', 'native_section_coverage'):
        if old.get(key) != updated.get(key):
            raise ValueError('prior_repair_changed:' + key)
    if [(n['id'], n.get('parent_id'), n.get('block'), n.get('native_section')) for n in old['chapter_tree']] != [
        (n['id'], n.get('parent_id'), n.get('block'), n.get('native_section')) for n in updated['chapter_tree']]:
        raise ValueError('chapter_identity_or_scope_changed')
    selected = a
    if updated != old:
        path = out / 'document.json.gz'
        path.write_bytes(gzip.compress(json.dumps(updated, ensure_ascii=False).encode(), compresslevel=6, mtime=0))
        selected = dict(a, path=str(path), sha256=digest(path.read_bytes()), version=out.parent.name)
        chunk_path = out / 'prechunks.json.gz'; chunks = classify(updated)
        chunk_path.write_bytes(gzip.compress(json.dumps(chunks, ensure_ascii=False).encode(), compresslevel=6, mtime=0))
        selected['prechunks'] = dict(path=str(chunk_path), sha256=digest(chunk_path.read_bytes()))
        for proof in titles:
            consumed = [c for c in chunks['records'] if c['block'] == proof['block']]
            if proof['table_row']:
                if not consumed or not all(proof in c.get('original_item_title_rows', []) for c in consumed):
                    raise ValueError('table_item_title_not_consumed')
            elif consumed and not all(c['role'] == 'retained_structure' for c in consumed):
                raise ValueError('original_item_title_not_consumed')
        for change in updated.get('source_display_block_repairs', []):
            b = updated['blocks'][change['block']]
            if b.get('candidate_role') == 'retained_metadata' and any(c['block'] == change['block'] and c['role'] != 'retained_metadata' for c in chunks['records']):
                raise ValueError('machine_metadata_remains_prose')
    import psutil
    memory = psutil.Process().memory_info()
    save(out / 'receipt.json', dict(status='qualified', parent=a, artifact=selected,
         source_sha256=old['source_sha256'], display_sources=len(display), title_repairs=len(titles),
         native_item_disagreements=sum(p['native_item_disagrees'] for p in titles),
         display_purposes=dict(Counter(p['evidence']['purpose'] for p in display)),
         block_policy_repairs=len(updated.get('source_display_block_repairs', [])), title_findings=findings,
         peak_rss_mib=getattr(memory, 'peak_wset', memory.rss) / 2**20, provider_calls=0))


def run(ledger, output, limit=None, prior=None):
    import psutil
    jobs = {}
    with Path(ledger).open(encoding='utf8') as stream:
        for line in stream:
            row = json.loads(line); a = row.get('current_parser_artifact') or {}
            if a.get('lane') in {'sec', 'web'}:
                jobs.setdefault(a['path'], dict(artifact=a, source=row['current_source']))
    jobs = sorted(jobs.values(), key=lambda job: (memory_requirement(job), job['artifact']['path']))
    if limit is not None:
        jobs = jobs[:limit]
    del row, line; gc.collect()
    out = Path(output); out.mkdir(parents=True, exist_ok=False); (out / 'inputs').mkdir()
    # Freeze transitive engineering helpers as well as the direct adapters.
    identity = dict(ledger_sha256=digest(Path(ledger).read_bytes()), planned=len(jobs), full_scope=limit is None,
                    code={str(p): digest(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))})
    save(out / 'identity.json', identity); reused = {}
    if prior:
        previous = Path(prior)
        if json.loads((previous / 'identity.json').read_bytes()) != identity:
            raise ValueError('prior_identity_changed')
        reused = {r['parent']['path']: r for r in json.loads((previous / 'summary.json').read_bytes())['rows'] if r['status'] == 'qualified'}
    results = []; selected = {}; pause = None
    def summary(state):
        save(out / 'summary.json', dict(status=state, planned=len(jobs), processed=len(results), rows=results,
             statuses=dict(Counter(r['status'] for r in results)), full_scope=limit is None, quality_pass=False, provider_calls=0))
    for index, job in enumerate(jobs):
        a = job['artifact']; result = reused.get(a['path'])
        if result:
            if result['parent'] != a or digest(Path(result['artifact']['path']).read_bytes()) != result['artifact']['sha256']:
                raise ValueError('prior_receipt_changed')
        else:
            required = memory_requirement(job); deadline = time.monotonic() + 60
            while psutil.virtual_memory().available < required and time.monotonic() < deadline:
                time.sleep(5)
            if psutil.virtual_memory().available < required or shutil.disk_usage(out).free < 650 * 2**20:
                pause = 'resource_pause'; break
            path = out / 'inputs' / f'{index:04d}.json'; save(path, job); folder = out / f'{index:04d}'
            print(json.dumps(dict(launch=index, required_mib=required // 2**20)), flush=True)
            started = time.monotonic()
            try:
                child = subprocess.run([sys.executable, __file__, '--worker', str(path), '--output', str(folder)],
                    capture_output=True, text=True, encoding='utf8', errors='replace', timeout=600)
                (out / f'{index:04d}.log').write_text(child.stdout + child.stderr, encoding='utf8')
                if child.returncode:
                    raise RuntimeError('child_exit_' + str(child.returncode))
                result = json.loads((folder / 'receipt.json').read_bytes()); result['receipt'] = str(folder / 'receipt.json')
            except Exception as error:
                result = dict(status='failed', parent=a, error=repr(error), output=str(folder))
            result['elapsed_seconds'] = time.monotonic() - started
        results.append(result)
        if result['status'] == 'qualified':
            selected[a['path']] = result['artifact']
        summary('running')
        print(json.dumps(dict(processed=len(results), planned=len(jobs), status=result['status'], titles=result.get('title_repairs', 0))), flush=True)
    assert digest(Path(ledger).read_bytes()) == identity['ledger_sha256']
    assert all(digest(Path(path).read_bytes()) == h for path, h in identity['code'].items())
    state = pause or ('failed' if any(r['status'] == 'failed' for r in results) else 'completed'); summary(state)
    if state == 'completed' and limit is None:
        seen = set()
        with Path(ledger).open(encoding='utf8') as source, (out / 'library-bindings.jsonl').open('w', encoding='utf8') as target:
            for line in source:
                row = json.loads(line); a = row.get('current_parser_artifact') or {}
                if row['document_id'] in seen:
                    raise ValueError('duplicate_binding')
                seen.add(row['document_id'])
                if a.get('path') in selected:
                    row['current_parser_artifact'] = selected[a['path']]; row['processing']['current_parser_artifact'] = selected[a['path']]
                target.write(json.dumps(row, ensure_ascii=False) + '\n')
        assert len(seen) == 1742
    return 0 if state == 'completed' else 75 if pause else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger'); p.add_argument('--output', required=True); p.add_argument('--limit', type=int)
    p.add_argument('--prior'); p.add_argument('--worker'); a = p.parse_args()
    if a.worker:
        worker(a.worker, a.output)
    else:
        raise SystemExit(run(a.ledger, a.output, a.limit, a.prior))
