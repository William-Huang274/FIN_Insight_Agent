"""Batching may bound memory, but must not silently lose coverage or reuse stale proof."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from scripts.engineering import source_intake_batches as batches


def input_fixture(tmp_path, sizes=(3, 3, 20, 2)):
    root = tmp_path / 'intake'
    root.mkdir()
    rows = []
    for i, size in enumerate(sizes):
        folder = root / str(i)
        folder.mkdir()
        source = folder / 'source.json'
        source.write_text('x' * size)
        rows.append({'source_id': str(i), 'directory': str(i), 'chunks': i + 1,
                     'files': {'source.json': batches.digest(source)}})
    intake = {'status': 'verified', 'sources': rows}
    batches.write(root / 'result.json', intake)
    return root, intake


def test_all_sources_retained_in_order_even_oversized_single_source(tmp_path):
    root, intake = input_fixture(tmp_path)
    plan = batches.plan_batches(root, max_sources=2, max_input_bytes=8)
    assert plan['batches'] == [['0', '1'], ['2'], ['3']]
    assert plan['candidate_chunks'] == 10
    selected = [row['source_id'] for i in range(3) for row in
                batches.select_batch(plan, intake, i, batches.digest(root/'result.json'))]
    assert selected == ['0', '1', '2', '3']


@pytest.mark.parametrize('broken', [[['0', '1']], [['0', '1'], ['1', '2', '3']],
                                  [['1', '0'], ['2', '3']], [['0', '1', '2', '3'], []]])
def test_plan_missing_duplicate_reordered_or_empty_batch_rejected(tmp_path, broken):
    root, intake = input_fixture(tmp_path)
    plan = batches.plan_batches(root)
    plan['batches'] = broken
    with pytest.raises(ValueError, match='scope_mismatch'):
        batches.select_batch(plan, intake, 0, batches.digest(root/'result.json'))


def test_changed_manifest_rejected(tmp_path):
    root, intake = input_fixture(tmp_path)
    with pytest.raises(ValueError, match='scope_mismatch'):
        batches.select_batch(batches.plan_batches(root), intake, 0, 'changed')


def passed_result(ids, binding):
    return {'status': 'passed', 'batch_binding': binding,
            'sources': [{'source_id': i, 'cache_hit': True, 'provider_calls': 0,
                         'candidate_chunks': int(i)+1} for i in ids],
            'captures': [{'source_id': i} for i in ids], 'date_denials': [], 'global_probe': False,
            'provider_calls': 0, 'research_runs': 0, 'per_source_filtered_readback_count': len(ids),
            'full_intake_sources': 4, 'corpus_wide_retrieval': False,
            'candidate_chunks': sum(int(i)+1 for i in ids),
            'revoked_cache_and_readback_denied': True}


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'sampled', 'paid', 'binding', 'revocation'])
def test_partial_or_different_result_cannot_be_resumed(tmp_path, change):
    root, _ = input_fixture(tmp_path)
    plan = batches.plan_batches(root)
    binding = {'identity': 'fixed'}
    result = passed_result(plan['batches'][0], binding)
    if change == 'missing': result['sources'].pop()
    if change == 'duplicate': result['sources'].append(result['sources'][0])
    if change == 'sampled': result['global_probe'] = True
    if change == 'paid': result['provider_calls'] = 1
    if change == 'binding': result['batch_binding'] = {}
    if change == 'revocation': result['revoked_cache_and_readback_denied'] = False
    with pytest.raises(ValueError, match='incomplete_or_different_scope'):
        batches.validate_result(plan, 0, result, binding)


def test_resume_checks_receipts_and_never_promotes_batches_to_unified_pass(tmp_path, monkeypatch):
    root, _ = input_fixture(tmp_path)
    plan = batches.plan_batches(root, max_sources=2)
    plan_path = tmp_path / 'plan.json'
    batches.write(plan_path, plan)
    output = tmp_path / 'output'
    output.mkdir()
    code = {'git_head': 'fixed', 'jar_sha256': 'fixed'}
    identity = {'plan_sha256': batches.digest(plan_path), **code}
    monkeypatch.setattr(batches, 'baseline', lambda: code)
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=0)))
    for number, ids in enumerate(plan['batches']):
        binding = {**identity, 'batch_number': number, 'intake_sha256': plan['intake_sha256']}
        result_path = output / f'result-{number}.json'
        batches.write(result_path, passed_result(ids, binding))
        batches.write(output / f'batch-{number:04d}-receipt.json',
                      {'result_path': result_path.name, 'result_sha256': batches.digest(result_path)})
    assert batches.run(plan_path, output) == 0
    progress = json.loads((output/'progress.json').read_text())
    assert progress['verified_sources'] == 4
    assert progress['S2_passed'] is False
    assert progress['unified_scope_acceptance'] == 'pending_separate_run'
    (output/'result-0.json').write_text('{}')
    with pytest.raises(ValueError, match='receipt_changed'):
        batches.run(plan_path, output)


def test_low_memory_stops_before_starting_any_service(tmp_path, monkeypatch):
    root, _ = input_fixture(tmp_path)
    plan_path = tmp_path / 'plan.json'
    batches.write(plan_path, batches.plan_batches(root))
    monkeypatch.setattr(batches, 'baseline', lambda: {'git_head': 'fixed', 'jar_sha256': 'fixed'})
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=900*2**20)))
    def forbidden(*args, **kwargs): raise AssertionError('must_not_start_services')
    monkeypatch.setattr(batches.subprocess, 'Popen', forbidden)
    output = tmp_path / 'output'
    assert batches.run(plan_path, output) == 2
    progress = json.loads((output/'progress.json').read_text())
    assert progress['verified_sources'] == 0 and progress['status'] == 'paused_memory'


def test_network_selection_handles_null_config_and_existing_stopped_networks(monkeypatch):
    calls = iter(['a b', json.dumps([{'IPAM': {'Config': None}},
                                   {'IPAM': {'Config': [{'Subnet': '10.253.1.0/24'}]}}])])
    monkeypatch.setattr(batches.subprocess, 'check_output', lambda *a, **kw: next(calls))
    assert batches.unused_subnet('docker') == '10.253.2.0/24'


def test_serial_worker_results_are_saved_then_skipped_on_resume(tmp_path, monkeypatch):
    root, _ = input_fixture(tmp_path)
    plan = batches.plan_batches(root, max_sources=2)
    plan_path = tmp_path/'plan.json'
    batches.write(plan_path, plan)
    monkeypatch.setattr(batches, 'baseline', lambda: {'git_head': 'fixed', 'jar_sha256': 'fixed'})
    monkeypatch.setattr(batches, 'unused_subnet', lambda _: '10.253.1.0/24')
    monkeypatch.setattr(batches.time, 'sleep', lambda _: None)
    monkeypatch.setenv('FINSIGHT_TEST_DOCKER', 'unused')
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=5*2**30)))
    seen = []
    def launch(*args, **kwargs):
        env = kwargs['env']
        number = int(env['FIN_COMPLETE_SOURCE_BATCH_NUMBER'])
        seen.append(number)
        assert env['FIN_COMPLETE_SOURCE_GLOBAL_PROBE'] == '0'
        path = Path(env['FIN_NATIVE_ATTEMPT_DIR'])
        path.mkdir()
        batches.write(path/'complete-source-result.json', passed_result(
            plan['batches'][number], json.loads(env['FIN_COMPLETE_SOURCE_BATCH_BINDING'])))
        return SimpleNamespace(wait=lambda: 0)
    monkeypatch.setattr(batches.subprocess, 'Popen', launch)
    output = tmp_path/'output'
    assert batches.run(plan_path, output) == 0
    assert seen == [0, 1]
    assert batches.run(plan_path, output) == 0
    assert seen == [0, 1]


def test_failed_attempt_and_existing_runner_are_not_silently_restarted(tmp_path, monkeypatch):
    root, _ = input_fixture(tmp_path)
    plan_path = tmp_path/'plan.json'
    batches.write(plan_path, batches.plan_batches(root))
    monkeypatch.setattr(batches, 'baseline', lambda: {'git_head': 'fixed', 'jar_sha256': 'fixed'})
    monkeypatch.setitem(sys.modules, 'psutil', SimpleNamespace())
    output = tmp_path/'output'
    output.mkdir()
    (output/'batch-0000-r01.log').write_text('previous failure')
    assert batches.run(plan_path, output) == 2
    assert json.loads((output/'progress.json').read_text())['status'] == 'failed_attempt_requires_explicit_retry'
    (output/'runner.lock').write_text('other runner')
    with pytest.raises(FileExistsError):
        batches.run(plan_path, output)
    assert (output/'runner.lock').read_text() == 'other runner'


def test_original_file_change_invalidates_resume_even_if_manifest_is_unchanged(tmp_path):
    root, intake = input_fixture(tmp_path)
    assert batches.verify_inputs(root, intake) == 4
    (root/'3'/'source.json').write_text('changed')
    with pytest.raises(ValueError, match='intake_file_changed'):
        batches.verify_inputs(root, intake)
