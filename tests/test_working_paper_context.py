import json

import pytest

from sec_agent.agent_runtime.user_workpaper_context import working_paper_context
from sec_agent.agent_runtime.working_memory import WorkingMemory, WorkingMemoryAccessDenied
from sec_agent.agent_runtime.working_memory_tools import execute_memory_tool, native_memory_scope


def setup_paper(tmp_path, monkeypatch):
    path = tmp_path / 'notes.sqlite'
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH', str(path))
    memory = WorkingMemory(path, owner='alice', workspace='study', actor='author')
    saved = memory.save('selected', 'original body')
    target = dict(id=saved['note_id'], title='selected', actor='author', workspace='study', version=1)
    return memory, target


def context(target, owner='alice'):
    return working_paper_context({}, 'author', owner=owner, workspace='study', target=target)


def reference(text):
    return json.JSONDecoder().raw_decode(text[text.index('{'):])[0]


def test_selected_note_tracks_model_and_human_changes_without_copying_body(tmp_path, monkeypatch):
    memory, target = setup_paper(tmp_path, monkeypatch)
    for version in range(1, 4):
        text = context(target)
        ref = reference(text)
        assert ref['baseline_version'] == 1 and ref['current_version'] == version
        assert ref['changed_since_baseline'] == (version != 1)
        assert 'original body' not in text and 'updated body' not in text
        for key, expected in [('read_current', version), ('read_baseline', 1)]:
            read = ref[key]
            result = execute_memory_tool(read['tool'], read['arguments'], {}, 'author', owner='alice', workspace='study')
            assert result['found'] and result['version'] == expected
        memory.save('selected', 'updated body ' + str(version), version, user_edit=version == 2)
    assert target['version'] == 1
    # Another user's edit stays discoverable, without repeating the selected note.
    memory.save('related', 'related prose', user_edit=True)
    text = context(target)
    assert 'related' in text and 'related prose' not in text
    assert '"title": "selected"' in text and text.count('"title": "selected"') == 1
    # A later write still faces real optimistic concurrency checks.
    stale = memory.save('selected', 'stale overwrite', 1)
    assert not stale['saved']


def test_missing_and_foreign_target_never_fall_back_to_another_note(tmp_path, monkeypatch):
    memory, target = setup_paper(tmp_path, monkeypatch)
    memory.save('other', 'do not select me')
    assert '无法读取选定底稿' in context(target, owner='bob')
    assert 'do not select me' not in context({**target, 'id': 'missing'})
    with pytest.raises(ValueError, match='scope_mismatch'):
        context({**target, 'workspace': 'another'})


def test_revocation_is_not_downgraded_to_optional_note_notice(tmp_path, monkeypatch):
    _, target = setup_paper(tmp_path, monkeypatch)
    allowed = [True]
    def check():
        if not allowed[0]:
            raise PermissionError('revoked')
    with native_memory_scope('alice', 'study', access_check=check):
        assert reference(context(target))['current_version'] == 1
        allowed[0] = False
        with pytest.raises(WorkingMemoryAccessDenied):
            context(target)
