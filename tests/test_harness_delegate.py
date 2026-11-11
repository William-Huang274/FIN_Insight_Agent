from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sec_agent.agent_runtime import harness_delegate as module


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_native_delegate_uses_shared_host_and_isolated_native_session(tmp_path, monkeypatch):
    observed = {}
    options = dict(model='deepseek-flash', protocol='deepseek_messages', reasoning='high',
        provider='deepseek-official', provider_key_env='KEY', provider_endpoint='https://provider.invalid',
        context_window=1048576, output_tokens=65536, summary_tokens=16000,
        compaction_threshold=.33, token_budget_basis={'purpose':'fixture'},
        reservation_micros=400000, reservation_basis='same authorized budget')
    budget = SimpleNamespace(store=object(), owner='owner', budget='shared', prices={'deepseek-flash':object()})
    def dispatch(**kw):
        observed['dispatch']=kw
        return SimpleNamespace()
    def transport(*a, **kw):
        observed['transport']=kw
        return SimpleNamespace(meter=lambda _:None)
    @asynccontextmanager
    async def local(**kw):
        observed['local']=kw
        yield 'http://127.0.0.1:9000'
    @asynccontextmanager
    async def acp(**kw):
        observed['acp']=kw
        async def prompt(text):
            observed['input']=json.loads(text)
            return {'status':'completed', 'text':'Draft, evidence and unresolved questions'}
        yield SimpleNamespace(prompt=prompt)
    monkeypatch.setattr(module,'HarnessDispatchHost',dispatch)
    monkeypatch.setattr(module,'HarnessProviderTransport',transport)
    monkeypatch.setattr(module,'harness_local_services',local)
    monkeypatch.setattr(module,'admitted_acp_session',acp)
    bridge=SimpleNamespace(model_access=lambda:None, stop=object(), tools={})
    delegate=module.NativeResearchDelegate(options=options, parent_options={'binary_sha256':'release'},
        binary=tmp_path/'binary', root=tmp_path, grant={'manifest_digest':'manifest'}, authority=lambda:{},
        budget=budget, environment={'KEY':'secret', 'OTHER_SECRET':'secret2', 'PATH':'fixture'},
        tid='execution',rid='run',directory=tmp_path/'tasks',public_sink=None)
    request=dict(purpose='draft', as_of='2026-11-09', method_text='',
        question='Lead assignment', research_task={'question':'Original task'})
    result=await delegate(key='task',request=request,bridge=bridge)
    assert result.startswith('Draft')
    assert observed['dispatch']['budget']=='shared'
    assert observed['dispatch']['dispatch_lane']=='consult:task'
    assert observed['dispatch']['basis']==options['token_budget_basis']
    env=observed['acp']['environment']
    assert 'KEY' not in env and 'OTHER_SECRET' not in env
    assert observed['acp']['directory']==tmp_path/'tasks'/'task'
    assert observed['input']['research_task']==request['research_task']
    patch=Path(observed['acp']['arguments'][-1]).read_text(encoding='utf8')
    assert '完整草稿' in patch and '不会直接覆盖' in patch
    assert 'llm-retry' in patch and '"maxRetries": 0' in patch
    # Native completion can be reused without making another provider request.
    monkeypatch.setattr(module,'completed_recovery',lambda *a,**k:{'text':'Saved completed draft'})
    assert await delegate(key='task',request=request,bridge=bridge,previous_scope='execution:old')=='Saved completed draft'
    with pytest.raises(ValueError, match='execution_mismatch'):
        delegate.completed_result('task','other:old')
    monkeypatch.setattr(module,'completed_recovery',lambda *a,**k:None)
    assert delegate.completed_result('task','execution:old') is None


def test_role_guidance_keeps_review_and_draft_distinct():
    assert '完整草稿' in module.delegation_guidance('draft')
    assert '具体建议动作' in module.delegation_guidance('review')
    with pytest.raises(ValueError):
        module.delegation_guidance('publish')
