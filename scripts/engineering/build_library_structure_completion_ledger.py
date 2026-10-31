"""Account for every frozen source binding without equating execution with quality.

Overlay receipts select repaired artifacts; inherited artifacts remain explicit.
All selected artifacts are hashed once, streaming, before accounting for bindings.
No provider calls, source writes or product publication.
"""
import argparse
from collections import Counter
from hashlib import sha256
import gzip
import json
from pathlib import Path


def digest(path):
    value = sha256()
    with path.open('rb') as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(piece)
    return value.hexdigest()


def check_repair_preservation(parent, repaired):
    """Chapter links may change; table payload and ordered block text may not."""
    old, new = parent['blocks'], repaired['blocks']
    if [b['text'] for b in old] != [b['text'] for b in new]:
        raise ValueError('repair_changed_block_text_or_order')
    chapter_fields = {'chapter_ids', 'chapter_blocks', 'embedded_chapter_ids', 'stage_input_blocks'}
    for index, (before, after) in enumerate(zip(old, new)):
        if before['kind'] != after['kind'] and (before['kind'], after['kind']) != ('text', 'heading'):
            raise ValueError('unexpected_block_role_change')
        if before['kind'] == 'table':
            # refine() starts a new stage. Its input is this parent artifact,
            # not the older parser artifact referenced by the parent's index.
            if 'stage_input_blocks' in after and after['stage_input_blocks'] != [index]:
                raise ValueError('table_stage_parent_index_changed')
            if ({k: v for k, v in before.items() if k not in chapter_fields}
                    != {k: v for k, v in after.items() if k not in chapter_fields}):
                raise ValueError('repair_changed_table_payload')


def rows_for_manifest(manifest, originals, derived=None):
    sources = manifest['sources']
    ids = [s['document_id'] for s in sources]
    if len(set(ids)) != len(ids) or len(ids) != manifest['source_bindings']:
        raise ValueError('source_denominator_mismatch')
    by_binding = {}
    for job in manifest['jobs']:
        for binding in job['bindings']:
            if binding in by_binding or binding not in ids:
                raise ValueError('duplicate_or_unknown_binding')
            by_binding[binding] = job['id']
    for source in sources:
        binding = source['document_id']
        row = {k: source.get(k) for k in ('document_id', 'title', 'url', 'source_digest',
                                         'original_resolution', 'provisional_family')}
        original = by_binding.get(binding)
        if original is None:
            row.update(execution_state='original_not_in_frozen_manifest',
                       quality_state='original_structure_unverified',
                       next_action='resolve_original_identity_or_retain_derived_only')
            if derived and binding in derived:
                row.update(derived[binding], execution_state='derived_parse_retained_original_unverified')
        else:
            row.update(original_id=original, **originals[original])
        yield row


def derived_records(directory, manifest, manifest_hash):
    summary = json.loads((directory / 'summary.json').read_bytes())
    if summary['manifest_sha256'] != manifest_hash:
        raise ValueError('derived_manifest_changed')
    sources = {s['document_id']: s for s in manifest['sources']}
    linked = {b for j in manifest['jobs'] for b in j['bindings']}
    rows = {}
    for line in (directory / 'bindings.jsonl').read_text(encoding='utf8').splitlines():
        entry = json.loads(line)
        binding = entry['document_id']
        if binding in rows or binding in linked or binding not in sources:
            raise ValueError('derived_binding_mismatch')
        if entry['source_digest'] != sources[binding]['source_digest']:
            raise ValueError('derived_source_changed')
        filename = sha256(binding.encode()).hexdigest() + '.json.gz'
        if entry['artifact'] != filename:
            raise ValueError('derived_artifact_identity_changed')
        path = directory / filename
        with gzip.open(path, 'rt', encoding='utf8') as stream:
            document = json.load(stream)
        if document['document_id'] != binding or document.get('original_structure_verified') is not False:
            raise ValueError('derived_document_identity_or_scope_changed')
        rows[binding] = {'derived_route': entry['route'], 'derived_issues': entry['issues'],
                         'derived_artifact_path': str(path), 'derived_artifact_sha256': digest(path),
                         'derived_hash_basis': 'current_snapshot_legacy_receipt_has_no_content_hash'}
    if len(rows) != summary['bindings']:
        raise ValueError('derived_binding_count_mismatch')
    return rows


def original_record(sid, baseline, overlay):
    receipt_file = baseline / 'receipts' / f'{sid}.json'
    parent = json.loads(receipt_file.read_bytes())
    row = dict(route=parent['route'], issues=parent.get('issues', {}),
               headings=parent.get('headings'),
               execution_state='prior_parse_retained',
               quality_state='type_quality_review_required',
               next_action='qualify_document_structure_and_remaining_diagnostics')
    selected = baseline / 'documents' / f'{sid}.json.gz'
    expected = parent['artifact_sha256']
    change_file = overlay / 'receipts' / f'{sid}.json'
    if not change_file.exists():
        row['repair_state'] = 'pending'
    else:
        change = json.loads(change_file.read_bytes())
        if change['parent_artifact_sha256'] != expected:
            raise ValueError('overlay_parent_changed:' + sid)
        row['repair_state'] = change['status']
        if change['status'] == 'failed':
            row.update(quality_state='repair_failed_parent_retained',
                       next_action='resolve_repair_failure', repair_error=change.get('detail'))
        elif change['status'] == 'repaired_structure_checked':
            selected = overlay / 'documents' / f'{sid}.json.gz'
            expected = change['artifact_sha256']
            row.update(execution_state='repaired_structure_checked',
                       issues=change['issues'], headings=change['headings'],
                       promoted_headings=len(change['promoted_headings']))
    if digest(selected) != expected:
        raise ValueError('selected_artifact_changed:' + sid)
    if row['execution_state'] == 'repaired_structure_checked':
        parent_path = baseline / 'documents' / f'{sid}.json.gz'
        if digest(parent_path) != parent['artifact_sha256']:
            raise ValueError('parent_artifact_changed:' + sid)
        with gzip.open(parent_path, 'rt', encoding='utf8') as stream:
            before = json.load(stream)
        with gzip.open(selected, 'rt', encoding='utf8') as stream:
            after = json.load(stream)
        check_repair_preservation(before, after)
        row['ordered_text_and_full_table_payload'] = 'preserved'
    row.update(artifact_path=str(selected), artifact_sha256=expected,
               artifact_integrity='verified')
    if row['quality_state'] != 'repair_failed_parent_retained':
        if row['issues'] or parent.get('unmatched_explicit_headings'):
            row['quality_state'] = 'diagnostics_require_review'
        if row['route'] == 'pypdf_text_diagnostic':
            row.update(quality_state='pdf_layout_unqualified',
                       next_action='qualify_layout_tables_reading_order_and_orientation')
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'baseline', 'overlay', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--derived', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    originals = {}
    for job in manifest['jobs']:
        originals[job['id']] = original_record(job['id'], args.baseline, args.overlay)
    derived = derived_records(args.derived, manifest, digest(args.manifest)) if args.derived else {}
    rows = list(rows_for_manifest(manifest, originals, derived))
    args.output.mkdir(parents=True, exist_ok=True)
    ledger = args.output / 'bindings.jsonl'
    ledger.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
    summary = {
        'source_bindings': len(rows), 'unique_originals': len(originals),
        'binding_execution': dict(Counter(r['execution_state'] for r in rows)),
        'binding_quality': dict(Counter(r['quality_state'] for r in rows)),
        'original_repair': dict(Counter(r['repair_state'] for r in originals.values())),
        'original_routes': dict(Counter(r['route'] for r in originals.values())),
        'binding_routes': dict(Counter(r.get('route', 'original_unresolved') for r in rows)),
        'derived_routes': dict(Counter(r['derived_route'] for r in rows if 'derived_route' in r)),
        'remaining_issue_originals': dict(Counter(
            issue for r in originals.values() for issue in r['issues'])),
        'remaining_issue_bindings': dict(Counter(
            issue for r in rows for issue in r.get('issues', {}))),
        'promoted_headings': sum(r.get('promoted_headings', 0) for r in originals.values()),
        'manifest_sha256': digest(args.manifest), 'ledger_sha256': digest(ledger),
        'baseline_identity_sha256': digest(args.baseline / 'execution-identity.json'),
        'overlay_identity_sha256': digest(args.overlay / 'identity.json'),
        'derived_summary_sha256': digest(args.derived / 'summary.json') if args.derived else None,
        'code_sha256': digest(Path(__file__)), 'provider_calls': 0,
        'scope': 'Integrity and execution accounting, not final semantic qualification or publication.',
    }
    (args.output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
