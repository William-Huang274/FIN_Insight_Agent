import json
from types import SimpleNamespace

import pytest

from tests.integration import source_intake_warm


def test_warm_child_receives_secret_on_stdin_without_provider_key(monkeypatch):
    monkeypatch.setenv('QWEN_API_KEY', 'synthetic-not-a-real-key')
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'passed', 'sources': 1742}))
    monkeypatch.setattr(source_intake_warm.subprocess, 'run', run)
    assert source_intake_warm.run({'runtime_secret': 'synthetic-runtime'})['sources'] == 1742
    command, options = calls[0]
    assert 'synthetic-runtime' not in ' '.join(command)
    assert json.loads(options['input'])['runtime_secret'] == 'synthetic-runtime'
    assert 'QWEN_API_KEY' not in options['env']
    assert options['timeout'] == 900


@pytest.mark.parametrize('returncode,status', [(1, 'failed'), (0, 'incomplete')])
def test_warm_failure_is_not_retried_or_exposed_as_success(monkeypatch, returncode, status):
    calls = []
    def run(*args, **kwargs):
        calls.append(True)
        return SimpleNamespace(returncode=returncode, stdout=json.dumps({'status': status}), stderr='private-details')
    monkeypatch.setattr(source_intake_warm.subprocess, 'run', run)
    with pytest.raises((RuntimeError, ValueError), match='full_scope_verification_child_') as caught:
        source_intake_warm.run({})
    assert 'private-details' not in str(caught.value)
    assert len(calls) == 1
