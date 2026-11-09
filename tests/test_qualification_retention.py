from pathlib import Path
from types import SimpleNamespace
import pytest
from tests.integration.resource_retention import finish


def stack(tmp_path):
    root = tmp_path/'attempt'
    root.mkdir()
    s = SimpleNamespace(project='fin-intake-native-abcdef123456', owned_project='fin-intake-native-abcdef123456',
                        output=root, state=root/'state', disposable_copies=[], commands=[], receipts=[])
    s.compose = lambda *args: s.commands.append(args)
    s.save = lambda name, value: s.receipts.append((name, dict(value)))
    return s


def test_success_retires_only_owned_stack_and_registered_copy(tmp_path):
    s = stack(tmp_path)
    original = tmp_path/'original'; original.write_text('source')
    copy = s.output/'copy'; copy.hardlink_to(original)
    evidence = s.output/'report.json'; evidence.write_text('keep')
    s.disposable_copies = [str(copy)]
    result = finish(s, failed=False)
    assert s.commands == [('down','--volumes','--remove-orphans','--timeout','5')]
    assert not copy.exists() and original.read_text() == 'source' and evidence.exists()
    assert result['status'] == 'retired'


@pytest.mark.parametrize('kind', ['failure', 'reason', 'pin', 'adopted', 'paid'])
def test_preserves_recoverable_and_explicitly_retained_cases(tmp_path, monkeypatch, kind):
    s = stack(tmp_path)
    if kind == 'reason': monkeypatch.setenv('FIN_NATIVE_RETAIN_REASON', 'browser acceptance')
    if kind == 'pin': (s.output/'retention-pin.json').write_text('{}')
    if kind == 'adopted': s.project = 'fin-intake-native-123456abcdef'
    if kind == 'paid':
        p=s.state/'calls'/'run'/'model-call-events.jsonl';p.parent.mkdir(parents=True);p.write_text('{"event":"started"}')
    result=finish(s, failed=kind=='failure')
    assert s.commands == [('stop','-t','5')]
    assert result['status']=='retained_stopped' and result['review_after']


def test_active_exception_retains_without_masking_original(tmp_path):
    s=stack(tmp_path)
    with pytest.raises(RuntimeError, match='source failed'):
        try: raise RuntimeError('source failed')
        finally: finish(s)
    assert s.commands == [('stop','-t','5')]


def test_foreign_project_not_touched(tmp_path):
    s=stack(tmp_path);s.project='production'
    with pytest.raises(ValueError, match='foreign'): finish(s, failed=False)
    assert s.commands == []


def test_zero_price_scripted_ledger_does_not_pin_every_success(tmp_path):
    s=stack(tmp_path);s.deterministic_model_fixture=True
    p=s.state/'calls'/'run'/'model-call-events.jsonl';p.parent.mkdir(parents=True);p.write_text('scripted')
    assert finish(s, failed=False)['status']=='retired'


def test_real_provider_observation_retains_even_with_scripted_graph(tmp_path):
    s=stack(tmp_path);s.deterministic_model_fixture=True;s.preserve_model_storage=True
    assert finish(s, failed=False)['status']=='retained_stopped'
