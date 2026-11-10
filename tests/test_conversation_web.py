import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from sec_agent.agent_runtime.conversation_web import public_web_tool
from sec_agent.research_foundation.external_sources import ConversationSourceScope
from test_web_source_navigation import _reader


def test_operation_mismatch_is_correctable_and_preserves_original_request(tmp_path):
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.tools import ToolException
    from sec_agent.agent_runtime.harness_business_tools import actionable_tool_feedback, restored_batch_feedback
    import pytest
    reader, fetcher, _ = _reader()
    grant = public_web_tool(thread_id=str(uuid4()), run_id=str(uuid4()),
        method_digest='a'*64, cache_root=tmp_path, reader=reader).tool
    async def run():
        raw, _ = await grant.coroutine(operation='search', query='public filing')
        doc = json.loads(raw)['items'][0]['document_id']
        original = dict(operation='read', document_id=doc, max_characters=14000, search_language='sr-RS')
        with pytest.raises(ToolException) as raised:
            await grant.coroutine(**original)
        feedback = json.loads(str(raised.value))
        assert feedback['submitted_arguments']['document_id'] == doc
        assert feedback['inapplicable_fields'] == ['search_language']
        assert feedback['request_dispatched'] is feedback['request_modified'] is False
        rejected = ToolMessage(name=grant.name, tool_call_id='failed', status='error', content=str(raised.value))
        assert actionable_tool_feedback(rejected)
        assert not fetcher.calls
        old = rejected.model_copy(update={'content':'公开来源读取未完成，不代表信息未披露：search_backend_and_language_require_global_search'})
        messages = [AIMessage(content='', tool_calls=[{'id':'failed','name':grant.name,'args':original}]), old]
        restored = restored_batch_feedback(messages, {'failed'})
        assert restored['failures'][0]['current_selection_feedback']['inapplicable_fields'] == ['search_language']
        assert 'search_backend_and_language' in messages[-1].content
        # Only the caller chooses to correct the request; no host auto-retry.
        actual, _ = await grant.coroutine(operation='read', document_id=doc, max_characters=14000)
        assert json.loads(actual)['items'][0]['document_id'] == doc
        assert len(fetcher.calls) == 1
        assert not actionable_tool_feedback(ToolMessage(name=grant.name, tool_call_id='auth',
            status='error', content='authorization_denied'))
    asyncio.run(run())


def test_unknown_web_locator_returns_real_readbacks_without_fetch_or_substitution(tmp_path):
    from langchain_core.messages import ToolMessage
    from langchain_core.tools import ToolException
    from sec_agent.agent_runtime.answer_review_provider import review_tool_feedback
    import pytest
    reader, fetcher, _ = _reader()
    grant = public_web_tool(thread_id=str(uuid4()), run_id=str(uuid4()),
        method_digest='a'*64, cache_root=tmp_path, reader=reader).tool
    async def run():
        visible, artifact = await grant.coroutine(operation='search', query='public filing')
        runtime = SimpleNamespace(state={'messages': [ToolMessage(name='read_public_source',
            tool_call_id='observed-search', content=visible, artifact=artifact)]})
        bad = 'WEB::' + 'f'*64
        with pytest.raises(ToolException) as raised:
            await grant.coroutine(operation='read', document_id=bad, runtime=runtime)
        feedback = json.loads(str(raised.value))
        assert feedback['submitted_document_id'] == bad
        assert feedback['request_modified'] is feedback['request_dispatched'] is False
        assert feedback['read_options'] == [{'tool':'read_saved_result',
            'arguments':{'tool_call_id':'observed-search'}}]
        assert not fetcher.calls
        message = ToolMessage(name='read_public_source', tool_call_id='bad',
            status='error', content=str(raised.value))
        assert json.loads(review_tool_feedback(message))['status'] == 'error'
        # The model, not the host, selects the actual ID on its following action.
        doc = json.loads(visible)['items'][0]['document_id']
        actual, _ = await grant.coroutine(operation='read', document_id=doc, runtime=runtime)
        assert json.loads(actual)['items'][0]['document_id'] == doc
        assert len(fetcher.calls) == 1
    asyncio.run(run())


def test_missing_web_locator_without_history_does_not_invent_a_readback(tmp_path):
    from langchain_core.tools import ToolException
    import pytest
    reader, fetcher, _ = _reader()
    grant = public_web_tool(thread_id=str(uuid4()), run_id=str(uuid4()),
        method_digest='a'*64, cache_root=tmp_path, reader=reader).tool
    with pytest.raises(ToolException) as raised:
        asyncio.run(grant.coroutine(operation='read', document_id='WEB::'+'f'*64))
    assert json.loads(str(raised.value))['read_options'] == []
    assert not fetcher.calls


def test_metering_fault_becomes_error_without_losing_partial_candidates(tmp_path):
    from sec_agent.agent_runtime.conversation_web import search_execution_faults
    from langchain_core.messages import ToolMessage
    from langgraph.prebuilt import ToolRuntime
    underlying, _, _ = _reader()
    class Reader:
        async def __call__(self, **kwargs):
            result = await underlying(**kwargs)
            receipt = result.execution_receipt.model_copy(update={'attempts': (
                {'provider_id':'deepseek_search', 'verification_failures':{
                    'deepseek_fetch:deepseek_web_response_unconfirmed':1}},)})
            return result.model_copy(update={'execution_receipt':receipt})
    grant = public_web_tool(thread_id=str(uuid4()), run_id=str(uuid4()), method_digest='a'*64,
        cache_root=tmp_path, reader=Reader()).tool
    output = asyncio.run(grant.ainvoke({'type':'tool_call','id':'call','name':'read_public_source',
        'args':{'operation':'search','query':'fixture',
                'runtime':ToolRuntime(tool_call_id='call',state={'messages':[]},context=None,
                                      config={},stream_writer=lambda _:None,store=None)}}))
    assert isinstance(output, ToolMessage)
    message = output
    assert message.status == 'error' and message.artifact['items']
    assert json.loads(message.content)['execution_stop']['codes'] == ['deepseek_web_response_unconfirmed']
    assert search_execution_faults({'execution_receipt': {'attempts': [
        {'failure_code':'deepseek_search_http_429'}, {'verification_failures':{'original_read:capture_http_status_403':1}}]}}) == []


def test_public_read_uses_shared_window_contract_without_hidden_wrapper_cap(tmp_path):
    reader, fetcher, text = _reader()
    grant = public_web_tool(thread_id=str(uuid4()), run_id=str(uuid4()),
        method_digest='a'*64, cache_root=tmp_path, reader=reader).tool
    async def run():
        visible, _ = await grant.coroutine(operation='search', query='public filing')
        doc = json.loads(visible)['items'][0]['document_id']
        visible, _ = await grant.coroutine(operation='read', document_id=doc, max_characters=50000)
        result = json.loads(visible)
        assert result['items'][0]['passage'] == text.strip()[:50000]
        assert result['items'][0]['source_locator']['character_start'] == 0
        assert not result['evidence_admission_performed']
        from langchain_core.tools import ToolException
        import pytest
        with pytest.raises(ToolException, match='80000'):
            await grant.coroutine(operation='read', document_id=doc, max_characters=80001)
    asyncio.run(run())


def test_publication_filters_are_disclosed_and_forwarded_without_rewriting_period(tmp_path):
    from datetime import date
    reader,_,_=_reader()
    seen=[]
    class RecordingReader:
        async def __call__(self, *, request, **kwargs):
            seen.append(request)
            return await reader(request=request, **kwargs)
    grant=public_web_tool(thread_id=str(uuid4()),run_id=str(uuid4()),method_digest='a'*64,
        cache_root=tmp_path,reader=RecordingReader(),research_as_of='2026-11-06').tool
    schema=grant.tool_call_schema.model_json_schema()['properties']
    assert 'start_published_date' in schema and 'end_published_date' in schema
    asyncio.run(grant.coroutine(operation='search',query='EX Q2 2027 results',
                start_published_date='2026-11-01',end_published_date='2026-11-06'))
    assert seen[0].query=='EX Q2 2027 results'
    assert seen[0].start_published_date==date(2026,11,1)
    assert seen[0].end_published_date==date(2026,11,6)


def test_public_web_restores_discovery_between_runs_and_uses_task_cutoff(tmp_path):
    from langchain_core.messages import ToolMessage
    tid = str(uuid4())
    first, _, _ = _reader()
    second, _, text = _reader()
    a = public_web_tool(thread_id=tid, run_id=str(uuid4()), method_digest='a'*64,
        cache_root=tmp_path, reader=first, research_as_of='2026-09-23').tool
    b = public_web_tool(thread_id=tid, run_id=str(uuid4()), method_digest='a'*64,
        cache_root=tmp_path, reader=second, research_as_of='2026-09-23').tool
    async def check():
        visible, artifact = await a.coroutine(operation='search', query='public filing')
        assert '2026-09-23' in json.loads(visible)['search_coverage']['research_as_of']
        assert 'web_navigation_receipts' not in json.loads(visible)
        doc = json.loads(visible)['items'][0]['document_id']
        runtime = SimpleNamespace(state={'messages': [ToolMessage(name='read_public_source',
            tool_call_id='search', content=visible, artifact=artifact)]})
        read, _ = await b.coroutine(operation='read', document_id=doc, max_characters=1000, runtime=runtime)
        assert json.loads(read)['items'][0]['passage'] == text[:1000]
        assert next(iter(second._candidates.values()))[0].research_as_of.startswith('2026-09-23')
    asyncio.run(check())


def test_explicit_import_restores_only_pinned_public_directories(tmp_path):
    from copy import deepcopy
    from langchain_core.messages import ToolMessage
    from langchain_core.tools import ToolException
    from sec_agent.agent_runtime.harness_legacy_import import imported_web_navigation
    import pytest
    old_tid, new_tid = str(uuid4()), str(uuid4())
    first, _, _ = _reader()
    a = public_web_tool(thread_id=old_tid, run_id=str(uuid4()), method_digest='a'*64,
        cache_root=tmp_path, reader=first, research_as_of='2026-09-23').tool
    async def check():
        visible, artifact = await a.coroutine(operation='search', query='public filing')
        original = deepcopy(artifact)
        message = ToolMessage(name='read_public_source', tool_call_id='search', content=visible, artifact=artifact)
        runtime = SimpleNamespace(state={'messages': [message]})
        authority = imported_web_navigation({'messages': [message]})
        doc = json.loads(visible)['items'][0]['document_id']
        for admitted in ({}, {key: 'another-task' for key in authority}):
            reader, _, _ = _reader()
            denied = public_web_tool(thread_id=new_tid, run_id=str(uuid4()), method_digest='b'*64,
                cache_root=tmp_path, reader=reader, research_as_of='2026-09-23', imported_navigation=admitted).tool
            with pytest.raises(ToolException, match='restore_task_mismatch'):
                await denied.coroutine(operation='read', document_id=doc, runtime=runtime)
        reader, _, text = _reader()
        allowed = public_web_tool(thread_id=new_tid, run_id=str(uuid4()), method_digest='b'*64,
            cache_root=tmp_path, reader=reader, research_as_of='2026-09-23', imported_navigation=authority).tool
        read, _ = await allowed.coroutine(operation='read', document_id=doc, max_characters=1000, runtime=runtime)
        assert json.loads(read)['items'][0]['passage'] == text[:1000]
        rebound = next(iter(reader._candidates.values()))[0]
        assert rebound.case_id == new_tid
        assert rebound.candidates[0].candidate_id == original['web_navigation_receipts'][0]['candidates'][0]['candidate_id']
        assert message.artifact == original
        # Importing a later task's directory cannot move its sources before cutoff.
        earlier, _, _ = _reader()
        restricted = public_web_tool(thread_id=new_tid, run_id=str(uuid4()), method_digest='b'*64,
            cache_root=tmp_path, reader=earlier, research_as_of='2026-06-30', imported_navigation=authority).tool
        with pytest.raises(ToolException):
            await restricted.coroutine(operation='read', document_id=doc, runtime=runtime)
        assert not earlier._candidates
        tampered = deepcopy(message)
        tampered.artifact['web_navigation_receipts'][0]['candidates'][0]['snippet'] = 'changed'
        with pytest.raises(ValueError, match='digest'):
            imported_web_navigation({'messages': [tampered]})
    asyncio.run(check())


def test_general_web_reuses_readers_without_claiming_financial_review(tmp_path):
    reader,fetcher,text=_reader()
    grant=public_web_tool(thread_id=str(uuid4()),run_id=str(uuid4()),method_digest="a"*64,
        cache_root=tmp_path,reader=reader)
    async def run():
        search=json.loads(await grant.tool.ainvoke({"operation":"search","query":"official HTTP caching"}))
        item=search["items"][0]
        assert item["result_state"]=="retrieval_candidate" and not item["writer_citable"]
        read=json.loads(await grant.tool.ainvoke({"operation":"read","document_id":item["document_id"],"max_characters":2000}))
        ambiguous=await grant.tool.ainvoke({"operation":"read","document_id":item["document_id"],"query":"ignored search"})
        assert json.loads(ambiguous)['inapplicable_fields'] == ['query']
        assert "operation=search, document_id and query" in json.loads(ambiguous)['next_step']
        assert read["items"][0]["passage"]==text[:2000]
        assert not read["items"][0]["numeric_fact_authority"]
        assert read["evidence_admission_performed"] is False
        within=json.loads(await grant.tool.ainvoke({"operation":"search","document_id":item["document_id"],"query":"source fixture"}))
        assert within["items"] and all(hit["writer_citable"] for hit in within["items"])
        start=within["items"][0]["source_locator"]["character_start"]
        for hit in within["items"]:
            locator=hit["source_locator"]
            assert hit["passage"]==text.strip()[locator["character_start"]:locator["character_end"]]
        from sec_agent.research_foundation.source_bound_calculator import source_items_from_tool
        assert len(source_items_from_tool("read_source_document",within))==len(within["items"])
        selected=json.loads(await grant.tool.ainvoke({"operation":"read","document_id":item["document_id"],"offset":start,"max_characters":2000}))
        assert selected["items"][0]["passage"]==text.strip()[start:start+2000]
        denied=await grant.tool.ainvoke({"operation":"read","document_id":"WEB::another-thread"})
        assert "not_discovered" in denied
        scope=next(iter(reader._candidates.values()))[0]
        assert scope.case_id and scope.data_snapshot_id=="conversation-public-sources-v1"
    asyncio.run(run())
    assert len(fetcher.calls)==1


def test_search_feedback_is_specific_and_the_method_is_callable():
    from sec_agent.agent_runtime.conversation_web import web_read_feedback
    from sec_agent.research_foundation.research_methods import get_research_method
    def feedback(*attempts, items=()):
        return web_read_feedback({'items':items,'execution_receipt':{'attempts':list(attempts)}})
    mixed = {'date_filter_counts':{'after_cutoff':3,'origin_403':2}}
    date_hint, denied = feedback(mixed)
    assert date_hint['count'] == 3
    assert get_research_method(**date_hint['method_readback']['arguments'])['selection'] == '数据版本与当前研究入口'
    assert denied['kind'] == 'origin_403' and 'method_readback' not in denied
    assert feedback({'failure_code':'capture_http_status_403'}) == [denied]
    assert feedback(mixed, items=[{'document_id':'ok'}]) == []
    assert feedback({}) == []
    reasons = feedback({'failure_code':'exa_mcp_rate_limited'}, {'failure_code':'ddgs_reported_no_results'})
    assert [r['kind'] for r in reasons] == ['search_rate_limited','fallback_empty']
    assert all('method_readback' not in r for r in reasons)


def test_exa_limit_switches_even_with_hits_and_survives_task_resume(tmp_path, monkeypatch):
    from contextlib import asynccontextmanager
    from sec_agent.research_foundation.external_sources import (
        ExaHostedMCPProvider, DDGSDiagnosticProvider, ProviderHit, ExaHostedMCPPageFetcher,
        PublicURLGuard, ExaTaskQuota, ExternalSourceError)
    import pytest
    calls = []
    class Limited:
        async def call_tool(self, name, arguments):
            calls.append('exa')
            raise RuntimeError("You've hit Exa's free MCP rate limit")
    @asynccontextmanager
    async def open_client(self, **kwargs):
        yield Limited()
    async def ddgs(self, req):
        calls.append('ddgs')
        return [ProviderHit(title='Release',url='https://example.com/release')]
    monkeypatch.setattr(ExaHostedMCPProvider, '_client', open_client)
    monkeypatch.setattr(DDGSDiagnosticProvider, 'search', ddgs)
    async def run():
        tid = str(uuid4())
        def new(task):
            return public_web_tool(thread_id=task,run_id=str(uuid4()),method_digest='a'*64,cache_root=tmp_path).tool
        tool = new(tid)
        for i, reader in enumerate((tool, tool, new(tid), new(str(uuid4())))):
            raw,_ = await reader.coroutine(operation='search',query='test')
            v=json.loads(raw)
            assert v['items'] and v['web_search_route']['active_provider']=='ddgs'
            assert any(h['kind']=='search_route_changed' for h in v.get('read_feedback',[])) == (i in (0,3))
            assert len(v['execution_receipt']['attempts']) == (2 if i in (0,3) else 1)
        assert calls == ['exa','ddgs','ddgs','ddgs','exa','ddgs']
        guard = SimpleNamespace(validate=lambda u:u)
        fetcher = ExaHostedMCPPageFetcher(guard=guard,quota=ExaTaskQuota(tmp_path/tid))
        with pytest.raises(ExternalSourceError,match='exa_skipped_after_task_limit'):
            await fetcher.fetch('https://example.com/release',timeout_seconds=1)
    asyncio.run(run())


def test_only_explicit_quota_disables_hosted_tools(tmp_path):
    from contextlib import asynccontextmanager
    from sec_agent.research_foundation.external_sources import ExaTaskQuota, _exa_call, ExternalSourceError
    import pytest
    quota = ExaTaskQuota(tmp_path)
    outcomes = [TimeoutError(), {'isError':True,'content':[{'type':'text','text':'Rate limit exceeded'}]}]
    class Client:
        async def call_tool(self, name, arguments):
            value=outcomes.pop(0)
            if isinstance(value,Exception):
                raise value
            return value
    @asynccontextmanager
    async def connect():
        yield Client()
    async def run():
        with pytest.raises(TimeoutError):
            await _exa_call(connect,'web_search_exa',{},quota)
        assert not quota.limited
        with pytest.raises(ExternalSourceError,match='exa_mcp_rate_limited'):
            await _exa_call(connect,'web_fetch_exa',{},quota)
        with pytest.raises(ExternalSourceError,match='exa_skipped_after_task_limit'):
            await _exa_call(connect,'web_search_exa',{},quota)
    asyncio.run(run())
