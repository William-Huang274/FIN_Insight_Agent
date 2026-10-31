import importlib.util
import copy
import gzip
import json
from hashlib import sha256
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / 'scripts/engineering/build_library_structure_completion_ledger.py'
spec = importlib.util.spec_from_file_location('completion_ledger', path)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


def test_repair_preserves_table_caption_metadata_and_text_order():
    old = {'blocks': [{'kind': 'text', 'text': 'Title'},
                      {'kind': 'table', 'text': '12', 'caption': 'Amounts in millions',
                       'metadata': {'period': '2025'}, 'chapter_ids': ['old'], 'stage_input_blocks': [9]}]}
    new = copy.deepcopy(old)
    new['blocks'][0]['kind'] = 'heading'
    new['blocks'][1]['chapter_ids'] = ['new']
    new['blocks'][1]['stage_input_blocks'] = [1]
    ledger.check_repair_preservation(old, new)
    new['blocks'][1]['stage_input_blocks'] = [5]
    with pytest.raises(ValueError, match='table_stage_parent_index_changed'):
        ledger.check_repair_preservation(old, new)
    new['blocks'][1]['stage_input_blocks'] = [1]
    new['blocks'][1]['caption'] = 'Amounts in thousands'
    with pytest.raises(ValueError, match='repair_changed_table_payload'):
        ledger.check_repair_preservation(old, new)
    with pytest.raises(ValueError, match='repair_changed_block_text_or_order'):
        ledger.check_repair_preservation(old, {'blocks': list(reversed(old['blocks']))})


def test_every_binding_remains_in_denominator_and_missing_original_is_not_success():
    manifest = {'source_bindings': 3,
                'sources': [{'document_id': key} for key in ('a', 'b', 'c')],
                'jobs': [{'id': 'raw', 'bindings': ['a', 'b']}]}
    rows = list(ledger.rows_for_manifest(manifest, {'raw': {'execution_state': 'checked'}}))
    assert len(rows) == 3
    assert rows[0]['original_id'] == rows[1]['original_id'] == 'raw'
    assert rows[2]['quality_state'] == 'original_structure_unverified'
    manifest['jobs'].append({'id': 'raw2', 'bindings': ['a']})
    with pytest.raises(ValueError, match='duplicate_or_unknown_binding'):
        list(ledger.rows_for_manifest(manifest, {}))


def test_derived_results_are_reused_without_upgrading_original_qualification(tmp_path):
    source = {'document_id': 'a', 'source_digest': 'source'}
    manifest = {'source_bindings': 1, 'sources': [source], 'jobs': []}
    name = sha256(b'a').hexdigest() + '.json.gz'
    (tmp_path/'summary.json').write_text(json.dumps({'manifest_sha256': 'manifest', 'bindings': 1}))
    entry = dict(source, artifact=name, route='structured_json', issues={})
    (tmp_path/'bindings.jsonl').write_text(json.dumps(entry) + '\n')
    with gzip.open(tmp_path/name, 'wt') as stream:
        json.dump({'document_id': 'a', 'original_structure_verified': False}, stream)
    derived = ledger.derived_records(tmp_path, manifest, 'manifest')
    row = list(ledger.rows_for_manifest(manifest, {}, derived))[0]
    assert row['execution_state'] == 'derived_parse_retained_original_unverified'
    assert row['quality_state'] == 'original_structure_unverified'
    assert row['derived_route'] == 'structured_json'
    with pytest.raises(ValueError, match='derived_manifest_changed'):
        ledger.derived_records(tmp_path, manifest, 'other')


def test_integrity_is_not_quality_and_overlay_tampering_is_rejected(tmp_path):
    base, overlay = tmp_path/'base', tmp_path/'overlay'
    for folder in (base, overlay):
        (folder/'receipts').mkdir(parents=True)
        (folder/'documents').mkdir()
    artifact = base/'documents/raw.json.gz'
    artifact.write_bytes(b'original')
    parent = {'route': 'edgartools', 'issues': {}, 'headings': 2,
              'artifact_sha256': sha256(b'original').hexdigest()}
    (base/'receipts/raw.json').write_text(json.dumps(parent))
    row = ledger.original_record('raw', base, overlay)
    assert row['artifact_integrity'] == 'verified'
    assert row['quality_state'] == 'type_quality_review_required'
    assert row['repair_state'] == 'pending'
    changed = {'parent_artifact_sha256': parent['artifact_sha256'],
               'status': 'repaired_structure_checked', 'artifact_sha256': sha256(b'new').hexdigest(),
               'issues': {}, 'headings': 3, 'promoted_headings': ['heading']}
    (overlay/'receipts/raw.json').write_text(json.dumps(changed))
    (overlay/'documents/raw.json.gz').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='selected_artifact_changed'):
        ledger.original_record('raw', base, overlay)


def test_failed_repair_retains_parent_and_visible_failure(tmp_path):
    base, overlay = tmp_path/'base', tmp_path/'overlay'
    for folder in (base, overlay):
        (folder/'receipts').mkdir(parents=True)
        (folder/'documents').mkdir()
    (base/'documents/raw.json.gz').write_bytes(b'x')
    sha = sha256(b'x').hexdigest()
    (base/'receipts/raw.json').write_text(json.dumps({'route':'edgartools', 'artifact_sha256':sha}))
    (overlay/'receipts/raw.json').write_text(json.dumps({
        'parent_artifact_sha256':sha,'status':'failed','detail':'incomplete original'}))
    row = ledger.original_record('raw', base, overlay)
    assert row['quality_state'] == 'repair_failed_parent_retained'
    assert row['artifact_path'] == str(base/'documents/raw.json.gz')
