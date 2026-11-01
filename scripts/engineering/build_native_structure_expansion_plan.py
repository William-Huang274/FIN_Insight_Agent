"""Freeze every original for staged native adaptation, without selecting away failures."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path


CHECKS = {
    'all': ['source_identity', 'content_and_table_preservation', 'heading_precision_and_recall',
            'parent_child_hierarchy', 'body_ownership', 'reading_order', 'prechunk_boundaries'],
    'sec': ['native_section_vs_original', 'cross_references', 'signature_scope', 'layout_table_role'],
    'markdown': ['source_line_roundtrip', 'frontmatter_role', 'table_cells', 'embedded_html'],
    'web': ['page_purpose', 'main_title', 'navigation_vs_body', 'empty_extraction', 'comments_role'],
    'pdf': ['visual_page_comparison', 'columns', 'rotation', 'borderless_tables', 'header_footnote_scope'],
    'structured': ['schema_identity', 'record_and_field_preservation'],
    'unsupported': ['original_format_and_route'],
}


def lane(route):
    if route == 'edgartools': return 'sec', 'ready_for_candidate_adaptation'
    if route == 'markdown_or_plain_text': return 'markdown', 'ready_for_candidate_adaptation'
    if route == 'trafilatura_xml': return 'web', 'native_consumer_required'
    if route and 'pdf' in route: return 'pdf', 'layout_adapter_required'
    if route in ('structured_json', 'structured_xml'): return 'structured', 'existing_structured_route_review'
    return 'unsupported', 'route_review_required'


def digest_file(path):
    digest = sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


def build(bindings, prior_rows=(), digest=digest_file):
    grouped = defaultdict(list); missing = []
    for binding in bindings:
        if binding.get('original_id'): grouped[binding['original_id']].append(binding)
        else:
            missing.append(dict(document_id=binding['document_id'], title=binding.get('title'),
                                state='original_unavailable', quality_state='insufficient_evidence'))
    prior = {r['source_sha256']: r for r in prior_rows}
    rows = []
    for original, aliases in sorted(grouped.items()):
        first = aliases[0]; routes = {b.get('route') for b in aliases}
        baselines = {(b.get('artifact_path'), b.get('artifact_sha256')) for b in aliases}
        route = first.get('route'); category, state = lane(route); problems = []
        if len(routes) != 1: problems.append('conflicting_source_routes')
        if len({h for _, h in baselines}) != 1: problems.append('conflicting_baseline_digests')
        for path, expected in sorted(baselines, key=str):
            if not path or not expected: problems.append('baseline_identity_missing'); continue
            try:
                if digest(path) != expected: problems.append('baseline_digest_mismatch')
            except OSError as exc:
                problems.append('baseline_unreadable:' + type(exc).__name__)
        if problems: state = 'baseline_repair_required'
        # Prior execution is context only: it is not a quality pass or permission
        # to skip a rerun under a changed implementation.
        prior_row = prior.get(original, {})
        rows.append(dict(original_id=original, title=first.get('title'), route=route,
                         family=first.get('provisional_family', 'unclassified'),
                         bindings=[b['document_id'] for b in aliases],
                         artifact_path=first.get('artifact_path'), artifact_sha256=first.get('artifact_sha256'),
                         baseline_variants=[dict(path=p, sha256=h) for p, h in sorted(baselines, key=str)],
                         lane=category, admission_state=state, baseline_problems=sorted(set(problems)),
                         required_checks=CHECKS['all'] + CHECKS[category],
                         review_stratum='flagged' if any(b.get('issues') for b in aliases) else 'no_current_diagnostic',
                         existing_issues=dict(Counter(k for b in aliases for k in b.get('issues', {}))),
                         previous_execution_state=prior_row.get('status', 'not_run'),
                         quality_state='insufficient_evidence', published=False))
    summary = dict(source_bindings=len(bindings), available_originals=len(rows),
                   missing_original_bindings=len(missing),
                   accounted_bindings=sum(len(r['bindings']) for r in rows)+len(missing),
                   lanes=dict(Counter(r['lane'] for r in rows)),
                   states=dict(Counter(r['admission_state'] for r in rows)),
                   review_strata=dict(Counter(r['review_stratum'] for r in rows)),
                   provider_calls=0, candidate_adaptation_executed=False, full_library_quality_pass=False)
    if summary['accounted_bindings'] != len(bindings): raise ValueError('lost_source_bindings')
    return rows, missing, summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bindings', type=Path, required=True)
    p.add_argument('--prior-results', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raw = a.bindings.read_bytes()
    prior_raw = a.prior_results.read_bytes() if a.prior_results else None
    rows, missing, report = build([json.loads(l) for l in raw.decode('utf-8-sig').splitlines() if l.strip()],
                                 json.loads(prior_raw)['rows'] if prior_raw else [])
    a.output.mkdir(parents=True, exist_ok=False)
    for name, records in [('all-originals', rows), ('missing-originals', missing)]:
        (a.output/(name+'.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
    for category in CHECKS.keys() - {'all'}:
        records = [r for r in rows if r['lane'] == category and r['admission_state'] == 'ready_for_candidate_adaptation']
        if records:
            (a.output/(category+'-ready-plan.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), encoding='utf-8')
    report.update(bindings_sha256=sha256(raw).hexdigest(),
                  prior_results_sha256=sha256(prior_raw).hexdigest() if prior_raw else None,
                  implementation_sha256=digest_file(__file__))
    (a.output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__': main()
