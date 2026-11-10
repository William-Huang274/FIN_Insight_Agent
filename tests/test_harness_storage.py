from pathlib import Path
import pytest
from sec_agent.agent_runtime.harness_storage import native_home, process_environment


def test_default_paths_and_secret_isolation(tmp_path):
    env = process_environment({'PATH': 'bin', 'OPENAI_API_KEY': 'not-forwarded'}, tmp_path, 'local')
    assert env['DSH_HOME'] == str(tmp_path / 'native')
    assert env['HOME'] == str(tmp_path)
    assert 'OPENAI_API_KEY' not in env


def test_shared_packages_isolated_sessions_and_stable_identity(tmp_path):
    root = tmp_path / 'volume'; root.mkdir()
    setting = {'FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT': str(root)}
    first = process_environment(setting, tmp_path / 'author', 'one')
    child = process_environment(setting, tmp_path / 'author/child', 'two')
    assert first['HOME'] == child['HOME']
    assert first['DSH_HOME'] != child['DSH_HOME']
    assert native_home(setting, tmp_path / 'author') == Path(first['DSH_HOME'])
    assert Path(first['DSH_HOME']).is_relative_to(root)


def test_existing_session_requires_explicit_migration(tmp_path):
    root = tmp_path / 'volume'; root.mkdir()
    session = tmp_path / 'session'; session.mkdir()
    (session / 'session-binding.json').write_text('{}')
    setting = {'FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT': str(root)}
    with pytest.raises(ValueError, match='verified_migration'):
        process_environment(setting, session, 'local')
    native_home(setting, session).mkdir(parents=True)
    assert process_environment(setting, session, 'local')['DSH_HOME'] == str(native_home(setting, session))


def test_unmigrated_existing_history_keeps_legacy_location(tmp_path):
    root = tmp_path / 'volume'; root.mkdir()
    session = tmp_path / 'session'; session.mkdir()
    (session / 'session-binding.json').write_text('{}')
    (session / 'native').mkdir()
    (session / 'native' / 'history.jsonl').write_text('original')
    env = process_environment({'FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT': str(root)}, session, 'local')
    assert env['DSH_HOME'] == str(session / 'native')
    assert env['HOME'] == str(session)
    assert (session / 'native' / 'history.jsonl').read_text() == 'original'
