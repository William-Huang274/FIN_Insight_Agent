from types import SimpleNamespace
import pytest
from sec_agent.agent_runtime.native_thread_header import thread_header


@pytest.mark.anyio
async def test_identity_read_uses_server_projection_not_full_thread():
    async def search(**kwargs):
        assert kwargs['ids'] == ['task'] and kwargs['limit'] == 1
        assert 'values' not in kwargs['select']
        return [dict(thread_id='task', status='idle', metadata={'owner':'a'}, values='large')]
    async def get(*args, **kwargs):
        raise AssertionError('must not transfer full checkpoint')
    value = await thread_header(SimpleNamespace(threads=SimpleNamespace(search=search,get=get)), 'task')
    assert value == dict(thread_id='task', status='idle', metadata={'owner':'a'})


@pytest.mark.anyio
@pytest.mark.parametrize('rows', [[], [{'thread_id':'another'}], [{'thread_id':'task'}]*2])
async def test_missing_or_mismatched_identity_is_not_guessed(rows):
    async def search(**kwargs): return rows
    with pytest.raises(ValueError, match='identity_not_found'):
        await thread_header(SimpleNamespace(threads=SimpleNamespace(search=search)), 'task')
