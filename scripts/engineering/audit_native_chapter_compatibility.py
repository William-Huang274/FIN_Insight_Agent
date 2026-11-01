"""Compare chapter compatibility against a frozen native adaptation run.

Engineering invariants only: preserved prior links are not original-based gold.
"""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re


def read_document(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def internal_key_displayed(node):
    if node.get('native_section_key') != node['title']:
        return False
    if node.get('title_binding', {}).get('status') == 'bound_heading':
        return False
    # An explicitly unresolved identifier-only placeholder is allowed by the
    # contract. It can legitimately equal the upstream key (e.g. "Item 5").
    return re.fullmatch(r'Item \d+(?:\.\d+)?[A-Za-z]?|Signatures|Section', node['title']) is None


def audit(directory, previous_directory):
    summary = json.loads((directory / 'summary.json').read_bytes())
    previous_rows = {r['source_sha256']: r for r in json.loads((previous_directory / 'summary.json').read_bytes())['rows']}
    findings = []; counts = Counter(); details = []
    for row in summary['rows']:
        sid = row['source_sha256']
        if row['status'] != 'adapted_requires_quality_review':
            findings.append(dict(source=sid, problem='failed_row')); continue
        old_row = previous_rows[sid]
        if old_row['receipt']['parent_fin_sha256'] != row['receipt']['parent_fin_sha256']:
            findings.append(dict(source=sid, problem='different_repaired_baseline')); continue
        parent = Path(row['receipt']['parent_fin_path'])
        if sha256(parent.read_bytes()).hexdigest() != row['receipt']['parent_fin_sha256']:
            findings.append(dict(source=sid, problem='baseline_digest_changed')); continue
        baseline = read_document(parent)
        before = read_document(previous_directory / 'adapted' / sid / 'document.json.gz')
        after = read_document(directory / 'adapted' / sid / 'document.json.gz')
        if len(before['blocks']) != len(after['blocks']) or len(baseline['blocks']) != len(after['blocks']):
            findings.append(dict(source=sid, problem='block_count_changed')); continue
        replacements = after.get('chapter_replacements', {})
        restored = 0
        for i, (old, new, original) in enumerate(zip(before['blocks'], after['blocks'], baseline['blocks'])):
            if old.get('native_section_binding') != new.get('native_section_binding'):
                findings.append(dict(source=sid, block=i, problem='native_membership_changed'))
            if len(new.get('native_section_binding', {}).get('candidates', [])) != 1:
                expected = {replacements.get(cid, cid) for cid in original.get('chapter_ids', [])}
                if not expected.issubset(new.get('chapter_ids', [])):
                    findings.append(dict(source=sid, block=i, problem='prior_link_dropped'))
                if expected and not old.get('chapter_ids') and new.get('chapter_ids'):
                    restored += 1
                if replacements and expected and new.get('chapter_binding_status') != 'prior_scope_unverified':
                    findings.append(dict(source=sid, block=i, problem='prior_link_presented_as_verified'))
        labels = Counter(n.get('title_binding', {}).get('status') for n in after['chapter_tree'] if 'native_section_key' in n)
        visible_blocks = {n['block'] for n in after['outline']}
        for node in after['outline']:
            if node['parent_block'] is not None and node['parent_block'] not in visible_blocks:
                findings.append(dict(source=sid, block=node['block'], problem='outline_parent_not_visible'))
        for node in after['chapter_tree']:
            if 'native_section_key' in node and internal_key_displayed(node):
                findings.append(dict(source=sid, problem='internal_key_displayed', section=node['native_section_key']))
        counts.update(labels); counts['documents'] += 1; counts['blocks_with_restored_prior_links'] += restored
        details.append(dict(source=sid, title=row['title'], restored_prior_link_blocks=restored,
                            title_statuses=dict(labels), visible_headings=len(after['outline'])))
    return dict(planned_originals=summary['planned_originals'], processed_rows=summary['processed_rows'],
                counts=dict(counts), findings=findings, details=details,
                compatibility_pass=not findings and summary['processed_rows']==summary['planned_originals'],
                structural_quality_pass=False, provider_calls=0)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--previous-directory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a=p.parse_args(); result=audit(a.directory, a.previous_directory)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='details'},ensure_ascii=False))
    raise SystemExit(0 if result['compatibility_pass'] else 1)
