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
    assert '问题理解、定向取证、比较或计算、条件判断与自查' in patch
    assert '来源仅部分读取且关键段未查时继续分页或定位' in patch
    assert '主研究负责人和最终作者' not in patch
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


def test_handoff_deduplicates_only_identical_source_metadata():
    source = {'source_id': 'source', 'title': 'Company', 'period': '2026Q2', 'unit': 'USD', 'revision': 'v1'}
    revised = {**source, 'revision': 'v2'}
    other_unit = {**source, 'unit': 'USD million'}
    request = {'purpose': 'review', 'question': 'Original scope', 'as_of': '2026-11-12',
        'report': {'title': 'Current', 'narrative_markdown': 'Current claim', 'charts': [],
                   'citations': {'a': {'sources': [source, source, revised]},
                                 'b': {'sources': [source, other_unit]}}}}
    view = module.delegation_payload(request)
    assert len(view['source_catalog']) == 3
    assert len(view['report']['citations']['a']['source_refs']) == 2
    assert len(view['report']['citations']['b']['source_refs']) == 2


def test_claim_catalog_deduplicates_exact_claims_without_changing_authority():
    from copy import deepcopy
    claim = {'kind': 'source_reference', 'statement': 'Navigation only', 'numeric_authority': 'none'}
    calculated = {**claim, 'numeric_authority': 'calculation'}
    request = {'purpose': 'review', 'question': 'Original scope', 'as_of': '2026-11-13',
        'report': {'narrative_markdown': 'Current answer', 'citations': {
            'one': {'claim': claim}, 'two': {'claim': claim}, 'three': {'claim': calculated}}}}
    before = deepcopy(request)
    view = module.delegation_payload(request)
    assert request == before and len(view['claim_catalog']) == 2
    for key, citation in request['report']['citations'].items():
        projected = view['report']['citations'][key]
        assert view['claim_catalog'][projected['claim_ref']] == citation['claim']
        assert projected['readback']['arguments']['source_id'] == key


def test_report_handoff_preserves_body_and_binding_without_snapshot_copies():
    from copy import deepcopy
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    source = 'PASSAGE::WEB::document::0::revision'
    request = dict(purpose='review', question='Challenge the investment relation',
        as_of='2026-11-11', method_text='guidance', research_task={'question': 'Original scope'},
        report={'title': 'Current report', 'narrative_markdown': 'Actual unchanged wording',
                'charts': [{'title': 'Scenario', 'points': [1, 2]}],
                'citations': {source: {'claim': {'statement': 'Observed change'},
                    'sources': [{'source_id': source, 'title': 'Original', 'unit': 'USD',
                                 'publication_date': '2026-11-10', 'text': 'large original' * 1000}]}}})
    original = deepcopy(request)
    payload = module.delegation_payload(request)
    assert request == original
    assert payload['report']['narrative_markdown'] == request['report']['narrative_markdown']
    assert payload['report']['charts'] == request['report']['charts']
    assert payload['research_task'] == request['research_task']
    citation = payload['report']['citations'][source]
    assert citation['readback'] == {'tool': 'read_research_source', 'arguments': {'source_id': source}}
    original_source = payload['source_catalog'][citation['source_refs'][0]]
    assert original_source['unit'] == 'USD'
    assert original_source['publication_date'] == '2026-11-10'
    assert 'text' not in original_source
    assert payload['reviewed_report_digest'] == canonical_sha256(request['report'])
    assert len(json.dumps(payload)) < len(json.dumps(request)) / 5
    recovery = {'pending_receipt': 'exact-receipt'}
    resumed = module.delegation_payload(request, previous_scope='thread:run', recovery_receipt=recovery)
    assert 'report' not in resumed and 'research_task' not in resumed
    assert resumed['question'] == request['question']
    assert resumed['reviewed_report_digest'] == payload['reviewed_report_digest']
    assert resumed['runtime_recovery'] == recovery
    assert 'method_text' not in payload
