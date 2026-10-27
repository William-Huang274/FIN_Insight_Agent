import json
from copy import deepcopy

import pytest

from tests.integration import source_intake_quality_checkpoint as checkpoint


def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, 'product_tree', lambda revision='HEAD': 'same-product')
    monkeypatch.setattr(checkpoint.subprocess, 'check_output', lambda *a, **k: b'')
    root = tmp_path/'attempt-1'
    root.mkdir()
    baseline = {'git_head': 'old-harness', 'jar_sha256': 'built-java',
                'configuration': {'profile': 'compact'}, 'configuration_files': {'catalog': 'fixed'}}
    (tmp_path/'baseline.json').write_text(json.dumps(baseline))
    quality = {'status': 'completed', 'batch_quality_passed': True, 'binding': {'dataset': 'fixed'},
        'rows': [{'id': 'q1', 'request': {'query': 'cash'}, 'complete10': True}]}
    (root/'service-quality.json').write_text(json.dumps(quality))
    (root/'retained-index-current-verification.json').write_text(json.dumps(
        {'status': 'passed', 'index_contract': {'release': 'fixed'}}))
    (root/'service-quality-question-q1.json').write_text(json.dumps(
        {'search': {'source_snapshot_sha256': 'manifest'}}))
    path = checkpoint.seal(root)
    options = dict(binding={'dataset': 'fixed'}, question_ids=['q1'], manifest_digest='manifest',
        contract={'release': 'fixed'}, baseline={**baseline, 'git_head': 'new-harness'}, save=lambda *args: None)
    return root, path, options


def test_quality_phase_resume_allows_harness_change_but_not_artifact_tampering(tmp_path, monkeypatch):
    root, path, options = prepared(tmp_path, monkeypatch)
    saved = {}
    options['save'] = lambda name, value: saved.update({name: value})
    assert checkpoint.restore(path, **options) == (root, [{'query': 'cash'}])
    assert saved['quality-phase-resume']['interrupted_between_phases']
    (root/'service-quality-question-q1.json').write_text('{}')
    with pytest.raises(ValueError, match='artifact_changed'):
        checkpoint.restore(path, **options)


@pytest.mark.parametrize('fault', ['product', 'dirty', 'jar', 'config', 'catalog', 'scope', 'manifest', 'binding', 'release'])
def test_quality_phase_resume_rejects_changed_execution_basis(tmp_path, monkeypatch, fault):
    _, path, original = prepared(tmp_path, monkeypatch)
    options = deepcopy(original)
    if fault == 'product': monkeypatch.setattr(checkpoint, 'product_tree', lambda: 'changed')
    elif fault == 'dirty': monkeypatch.setattr(checkpoint.subprocess, 'check_output', lambda *a, **k: b' M src/file.py')
    elif fault == 'jar': options['baseline']['jar_sha256'] = 'changed'
    elif fault == 'config': options['baseline']['configuration']['profile'] = 'changed'
    elif fault == 'catalog': options['baseline']['configuration_files']['catalog'] = 'changed'
    elif fault == 'scope': options['question_ids'] = []
    elif fault == 'manifest': options['manifest_digest'] = 'changed'
    elif fault == 'binding': options['binding'] = {'dataset': 'changed'}
    else: options['contract'] = {'release': 'changed'}
    with pytest.raises(ValueError, match='quality_checkpoint_'):
        checkpoint.restore(path, **options)
