"""Build replayable parser supplement cases; a route recommendation is not a fix.

Read one frozen artifact at a time. Do not change documents, publish projections,
call models, or interpret an absence of diagnostic flags as correct recognition.
"""
import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import json
from pathlib import Path


POLICIES = {
    'long_document_without_recognized_heading': 'inspect_source_headings_then_format_specific_parser',
    'heading_level_unknown': 'reconcile_native_level_bookmarks_numbering_and_style',
    'heading_level_jump': 'compare_source_level_and_canonical_parent_do_not_compress_blindly',
    'explicit_heading_not_retained_as_heading': 'compare_body_selection_navigation_and_heading_role',
    'pdf_font_heading_hierarchy_not_qualified': 'pdf_layout_parser_with_page_grounded_hierarchy',
    'short_heading_requires_review': 'verify_complete_source_container_not_length_only',
    'fewer_tables_than_dom_requires_layout_table_review': 'compare_physical_table_roles_and_content',
    'oversize_complete_sentence': 'inspect_sentence_boundary_and_source_container',
}


def diagnose(document):
    blocks = document['blocks']; containers = document.get('source_containers', [])
    sources = {s['id']: s for s in containers}
    source_roles = Counter(s['role'] for s in containers if not s.get('excluded_navigation'))
    findings = []
    for issue in document.get('issues', []):
        kind = issue['kind']; block_index = issue.get('block')
        block = blocks[block_index] if isinstance(block_index, int) and 0 <= block_index < len(blocks) else {}
        candidates = [sources[s] for s in block.get('source_container_candidates', []) if s in sources]
        location = block.get('source_container_id')
        if location in sources and all(s['id'] != location for s in candidates):
            candidates.append(sources[location])
        evidence = {k: block.get(k) for k in ('kind', 'level', 'heading_basis', 'native_role',
                    'native_parent_id', 'source_location_status', 'chapter_ids') if k in block}
        evidence['text_excerpt'] = block.get('text', '')[:320]
        evidence['source_candidates'] = [{k: s.get(k) for k in (
            'id', 'tag', 'role', 'level', 'role_basis', 'table_id', 'excluded_navigation')}
            for s in candidates[:8]]
        evidence['source_candidate_count'] = len(candidates)
        findings.append({'kind': kind, 'source_issue': issue, 'evidence': evidence,
                         'next_action': POLICIES.get(kind, 'inspect_unclassified_diagnostic'),
                         'state': 'requires_evidence_review', 'automatic_repair_authorized': False})
    locations = Counter(b.get('source_location_status', 'not_applicable') for b in blocks)
    matched_heading_count = sum(s['role'] == 'heading' for s in containers if not s.get('excluded_navigation'))
    missing_explicit = []
    source_by_path = {s['xpath']: s for s in containers}
    for h in document.get('unmatched_explicit_headings', []):
        s = source_by_path.get(h['xpath'], {})
        missing_explicit.append({**h, 'source_role': s.get('role'),
                                 'excluded_navigation': s.get('excluded_navigation'),
                                 'table_id': s.get('table_id')})
    return {'route': document['route'], 'finding_count': len(findings), 'findings': findings,
            'source_roles': dict(source_roles), 'original_explicit_heading_count': matched_heading_count,
            'recognized_headings': len(document.get('outline', [])),
            'source_location_counts': dict(locations), 'unmatched_explicit_headings': missing_explicit,
            'body_excerpt': next((b['text'][:700] for b in blocks if b['kind'] == 'text' and len(b['text']) > 100), ''),
            'recognition_correctness': 'not_established_by_diagnostic'}


def run(manifest, directory, output):
    frozen = json.loads(manifest.read_bytes()); output.mkdir(parents=True, exist_ok=False)
    counts = Counter(); route_counts = defaultdict(Counter); states = Counter(); rows = []
    with (output / 'cases.jsonl').open('w', encoding='utf8') as stream:
        for ordinal, job in enumerate(frozen['jobs'], 1):
            receipt = json.loads((directory / 'receipts' / (job['id'] + '.json')).read_bytes())
            if receipt['status'] != 'inspected':
                raise ValueError('uninspected_frozen_input:' + job['id'])
            path = directory / 'documents' / (job['id'] + '.json.gz')
            packed = path.read_bytes()
            if sha256(packed).hexdigest() != receipt['artifact_sha256']:
                raise ValueError('artifact_digest_mismatch:' + job['id'])
            document = json.loads(gzip.decompress(packed)); del packed
            result = diagnose(document)
            result.update(id=job['id'], title=job['title'], url=job['url'], bindings=job['bindings'],
                          artifact_sha256=receipt['artifact_sha256'])
            stream.write(json.dumps(result, ensure_ascii=False) + '\n')
            kinds = sorted({f['kind'] for f in result['findings']})
            for kind in kinds: counts[kind] += 1; route_counts[kind][result['route']] += 1
            rows.append({'id': job['id'], 'title': job['title'], 'route': result['route'], 'kinds': kinds,
                         'recognized_headings': result['recognized_headings'],
                         'original_explicit_heading_count': result['original_explicit_heading_count'],
                         'source_roles': result['source_roles']})
            states.update(result['source_location_counts'])
            del document, result
            if ordinal % 100 == 0: print(json.dumps({'processed': ordinal}), flush=True)
    # Stratified negative-control review candidates. Selection is deterministic;
    # it is not a claim that unflagged documents were manually reviewed.
    controls = defaultdict(list)
    for row in sorted(rows, key=lambda r: r['id']):
        if not row['kinds'] and len(controls[row['route']]) < 4: controls[row['route']].append(row['id'])
    report = {'manifest_sha256': sha256(manifest.read_bytes()).hexdigest(),
              'implementation_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'originals_inspected': len(rows), 'source_bindings': len(frozen['sources']),
              'documents_with_findings': sum(bool(r['kinds']) for r in rows),
              'documents_without_flags_not_gold_pass': sum(not r['kinds'] for r in rows),
              'issue_document_counts': dict(counts), 'issue_route_counts': dict(route_counts),
              'source_location_counts': dict(states), 'negative_controls_pending_review': dict(controls),
              'documents': rows, 'provider_calls': 0, 'production_enabled': False}
    (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'documents','negative_controls_pending_review'}}, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'directory', 'output'): p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); run(a.manifest, a.directory, a.output)
