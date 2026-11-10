import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx

from sec_agent.agent_runtime.public_data import public_data_tool
from sec_agent.agent_runtime.regional_disclosures import regional_disclosure_tool
from sec_agent.agent_runtime.answer_review_provider import review_tool_names


def test_mcp_search_uses_native_interface_and_is_saved():
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def call_tool(self, name, args):
            assert name == 'search_interfaces' and args == {'keyword': '东方财富 新闻'}
            return SimpleNamespace(is_error=False, structured_content={'result': {'items': [{'name': 'stock_news_em'}], 'total': 1}})
    grant = public_data_tool(client_factory=Client)
    content, artifact = asyncio.run(grant.tool.coroutine(operation='search', query='东方财富 新闻'))
    assert artifact['status'] == 'ok' and artifact['result']['items'][0]['name'] == 'stock_news_em'
    assert json.loads(content) == artifact and not artifact['writer_citable']


def test_aktools_never_fetches_today_data_as_historical():
    def never(): raise AssertionError('no request allowed')
    grant = public_data_tool(research_as_of='2000-01-01', client_factory=never)
    _, data = asyncio.run(grant.tool.coroutine(operation='data', interface='stock_zyjs_ths'))
    assert data['status'] == 'historical_vintage_unverified'


def test_twse_navigation_cache_and_historical_withholding(tmp_path):
    calls = []
    def reply(req):
        calls.append(str(req.url))
        return httpx.Response(200, json=[{'公司代號': '2330', '公司名稱': '台積電', '網址': 'https://www.tsmc.com', '實收資本額': '123'}])
    grant = regional_disclosure_tool(thread_id=str(uuid4()), cache_root=tmp_path,
                                     research_as_of='2000-01-01', transport=httpx.MockTransport(reply))
    async def run():
        _, a = await grant.tool.coroutine(operation='issuers', query='2330')
        _, b = await grant.tool.coroutine(operation='issuers', query='2330')
        assert a == b and len(calls) == 1
        assert '實收資本額' not in a['rows'][0]
        _, c = await grant.tool.coroutine(operation='announcements')
        assert c['status'] == 'historical_vintage_unverified' and c['rows'] == []
    asyncio.run(run())


def test_review_gets_same_read_tools():
    names = ('query_public_data', 'read_regional_disclosures')
    assert set(review_tool_names(names)) == set(names)
