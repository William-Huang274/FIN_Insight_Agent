import json
from types import SimpleNamespace

import pytest

from tests.integration import source_intake_retained as module


def fixture(tmp_path, monkeypatch, *, running=False, present=False):
    root = tmp_path/'prior'
    root.mkdir()
    files = {}
    for name in ('state/project-library/attachments.sqlite',
                 'state/project-library/organization-assets/attachments.sqlite',
                 'complete-source-publication-progress.json', 'business-after-publication.dump'):
        p = root/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'synthetic sealed fixture')
        files[name] = module.digest(p)
    (root/'environment.json').write_text(json.dumps({'project': 'fin-intake-native-owned',
        'ports': {'postgres': 59999}, 'git_head': 'prior-code'}))
    for service in ('java', 'bff'):
        (root/(service+'-fixed-process-resources.json')).write_text(json.dumps({'pid': 12345678}))
    seal = root/'retained.json'
    seal.write_text(json.dumps({'schema': 'retained-source-publication.v1', 'container_id': 'own',
        'intake_sha256': 'intake', 'geometry_sha256': 'geometry', 'files': files}))
    output = tmp_path/'new'
    output.mkdir()
    (output/'environment.json').write_text(json.dumps({'ports': {}}))
    stack = SimpleNamespace(docker='synthetic-docker', project='fin-intake-native-new',
        output=output, env={}, redactions=[], save=lambda name, value:
            (output/(name+'.json')).write_text(json.dumps(value)))
    def command(args, **_):
        if args[1] == 'inspect':
            return json.dumps([{'State': {'Running': running}, 'Config': {
                'Labels': {'com.docker.compose.project': 'fin-intake-native-owned',
                           'com.docker.compose.service': 'postgres'},
                'Env': ['POSTGRES_PASSWORD=synthetic-only']},
                'NetworkSettings': {'Networks': {'owned-network': {}}}}])
        return json.dumps([{'IPAM': {'Config': [{'Subnet': '10.99.2.0/24'}]}}])
    monkeypatch.setattr(module.subprocess, 'check_output', command)
    monkeypatch.setattr('psutil.pid_exists', lambda _: present)
    return stack, seal


def test_retained_fixture_requires_exact_seal_and_exclusive_stopped_owner(tmp_path, monkeypatch):
    stack, path = fixture(tmp_path, monkeypatch)
    result = module.adopt(stack, path, intake_sha256='intake', geometry_sha256='geometry')
    assert stack.project == 'fin-intake-native-owned' and stack.pg_port == 59999
    assert stack.state == path.parent/'state'
    assert result['source_git'] == 'prior-code'
    assert stack.env['FIN_COMPLETE_SOURCE_HTTP_EVIDENCE_ROOT'] == str(stack.output)
    assert 'synthetic-only' not in (stack.output/'environment.json').read_text()
    with pytest.raises(FileExistsError):
        module.adopt(stack, path, intake_sha256='intake', geometry_sha256='geometry')


@pytest.mark.parametrize('fault', ['running', 'process', 'changed_file', 'wrong_scope'])
def test_retained_fixture_rejects_before_adoption(tmp_path, monkeypatch, fault):
    stack, path = fixture(tmp_path, monkeypatch, running=fault=='running', present=fault=='process')
    if fault == 'changed_file':
        (path.parent/'state/project-library/attachments.sqlite').write_bytes(b'changed')
    with pytest.raises(ValueError):
        module.adopt(stack, path, intake_sha256='wrong' if fault=='wrong_scope' else 'intake',
                     geometry_sha256='geometry')
    assert not (path.parent/'retained-publication.lease').exists()
    assert not stack.env
