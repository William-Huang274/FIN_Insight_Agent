from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from tests.integration.source_intake_profile import profiled


def test_parallel_profiles_do_not_capture_arguments_or_results(tmp_path):
    def work(secret):
        return secret + 'private-result'
    wrapped = profiled(work, tmp_path)
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(wrapped, ['secret-a', 'secret-b'])) == [
            'secret-aprivate-result', 'secret-bprivate-result']
    paths = list(tmp_path.glob('*.json'))
    assert len(paths) == 2
    for path in paths:
        raw = path.read_text()
        assert 'secret-a' not in raw and 'secret-b' not in raw and 'private-result' not in raw
        result = json.loads(raw)
        assert result['status'] == 'completed' and result['seconds'] >= 0
        assert any(row['function'] == 'work' and row['calls'] == 1 for row in result['functions'])


def test_profile_retains_failure_type_without_error_message(tmp_path):
    def fail():
        raise ValueError('private exception detail')
    with pytest.raises(ValueError, match='private exception detail'):
        profiled(fail, tmp_path)()
    raw = next(tmp_path.glob('*.json')).read_text()
    assert 'private exception detail' not in raw
    assert json.loads(raw)['status'] == 'ValueError'
