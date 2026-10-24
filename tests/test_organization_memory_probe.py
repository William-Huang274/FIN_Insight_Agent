from hashlib import sha256
import json
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.engineering.profile_organization_retrieval_memory import profile


def files(tmp_path):
    matrix = tmp_path/'vectors.npy'
    values = np.zeros((5, 1024), dtype=np.float32)
    values[:, 0] = 1.
    np.save(matrix, values, allow_pickle=False)
    index = tmp_path/'index.json'
    index.write_text(json.dumps({'records': [{'node_id': str(i), 'vector_index': i} for i in range(5)],
        'dimensions': 1024, 'matrix_sha256': sha256(matrix.read_bytes()).hexdigest(),
        'queries': {'synthetic': values[0].tolist()}}), encoding='utf8')
    return index, matrix


def test_probe_reports_equivalent_scores_and_released_mapping_without_modifying_input(tmp_path, monkeypatch):
    # This deterministic fixture proves the probe's assertions, not capacity.
    monkeypatch.setattr('psutil.virtual_memory', lambda: SimpleNamespace(available=4 * 2**30))
    index, matrix = files(tmp_path)
    before = index.read_bytes(), matrix.read_bytes()
    reports = [profile(index, matrix, tmp_path/variant, variant=variant) for variant in ('baseline', 'optimized')]
    score_rows = [next(r for r in report['phases'] if r['name']=='vector_scoring') for report in reports]
    assert score_rows[0]['scores_sha256'] == score_rows[1]['scores_sha256']
    assert score_rows[0]['top24'] == score_rows[1]['top24']
    for report in reports:
        assert report['status']=='passed' and report['records']==5
        assert report['provider_calls']==0
        assert next(r for r in report['phases'] if r['name']=='release_query_temporaries')['mapping_released']
    assert before == (index.read_bytes(), matrix.read_bytes())


def test_probe_keeps_startup_failure_and_never_loads_insufficient_memory_input(tmp_path, monkeypatch):
    monkeypatch.setattr('psutil.virtual_memory', lambda: SimpleNamespace(available=799 * 2**20))
    index, matrix = files(tmp_path)
    with pytest.raises(RuntimeError, match='startup_headroom'):
        profile(index, matrix, tmp_path/'blocked', variant='optimized')
    result = json.loads((tmp_path/'blocked/result.json').read_text())
    assert result['status']=='failed' and result['phases']==[]


def test_probe_rejects_corrupt_matrix_and_retains_completed_phases(tmp_path, monkeypatch):
    monkeypatch.setattr('psutil.virtual_memory', lambda: SimpleNamespace(available=4 * 2**30))
    index, matrix = files(tmp_path)
    with matrix.open('ab') as handle:
        handle.write(b'changed')
    with pytest.raises(AssertionError):
        profile(index, matrix, tmp_path/'corrupt', variant='optimized')
    result=json.loads((tmp_path/'corrupt/result.json').read_text())
    assert result['status']=='failed'
    assert result['phases'][0]['status']=='passed'
    assert result['phases'][-1]['name']=='matrix_file_integrity'
    assert result['phases'][-1]['status']=='failed'
