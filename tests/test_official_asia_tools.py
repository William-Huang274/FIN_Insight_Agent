import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from jsonschema import Draft202012Validator, ValidationError

from sec_agent.agent_runtime.hithink_data import hithink_data_tool, openapi_nullable_schema, DOMAINS
from sec_agent.agent_runtime.korean_disclosures import korean_disclosure_tool


def test_nullable_bridge_preserves_original_and_other_constraints():
    schema = {'type': 'object', 'required': ['x'], 'properties': {'x': {'type': 'number', 'nullable': True, 'minimum': 0}}}
    validator = Draft202012Validator(openapi_nullable_schema(schema))
    for value in [None, 0, 1.2]: validator.validate({'x': value})
    for value in ['1', -1]:
        with pytest.raises(ValidationError): validator.validate({'x': value})
    with pytest.raises(ValidationError): validator.validate({})
    assert schema['properties']['x']['type'] == 'number' and schema['properties']['x']['nullable']


def factory(calls, result):
    class Item:
        name = 'get_data'
        def model_dump(self, **kwargs):
            return dict(name=self.name, description='data', input_schema={'type': 'object', 'required': ['symbol'],
                        'properties': {'symbol': {'type': 'string'}}})
    class Client:
        def __init__(self, domain): self.domain = domain
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def list_tools(self):
            calls.append(('list', self.domain))
            return SimpleNamespace(tools=[Item()], next_cursor=None)
        async def call_tool(self, name, arguments):
            calls.append(('call', self.domain, name, arguments))
            return SimpleNamespace(is_error=False, structured_content=result)
    return Client


def test_six_domains_native_schemas_cached_and_parameters_not_rewritten():
    calls = []
    t = hithink_data_tool(client_factory=factory(calls, {'code': 0, 'data': None})).tool
    async def run():
        for domain in DOMAINS:
            _, a = await t.coroutine(operation='catalog', domain=domain)
            _, b = await t.coroutine(operation='describe', domain=domain, tool_name='get_data')
            _, c = await t.coroutine(operation='call', domain=domain, tool_name='get_data', arguments={'symbol': 'X'})
            assert a['status'] == b['status'] == c['status'] == 'ok'
        assert len([x for x in calls if x[0] == 'list']) == 6
        assert calls[-1][-1] == {'symbol': 'X'}
    asyncio.run(run())


def test_invalid_and_historical_calls_never_dispatch_data():
    calls = []
    t = hithink_data_tool(research_as_of='2000-01-01', client_factory=factory(calls, {})).tool
    async def run():
        _, r = await t.coroutine(operation='call', tool_name='get_data', arguments={})
        assert r['status'] == 'invalid_parameters'
        _, r = await t.coroutine(operation='call', domain='a-share', tool_name='get_data', arguments={'symbol': 'X'})
        assert r['status'] == 'historical_vintage_unverified'
        assert not any(x[0] == 'call' for x in calls)
    asyncio.run(run())


def test_business_failure_not_empty_success_and_full_artifact_retained():
    for code in [0, 2003]:
        data = {'code': code, 'data': {'text': 'x'*30000}, 'request_id': 'request'}
        t = hithink_data_tool(client_factory=factory([], data)).tool
        content, artifact = asyncio.run(t.coroutine(operation='call', tool_name='get_data', arguments={'symbol': 'X'}))
        assert artifact['status'] == ('ok' if code == 0 else 'provider_error')
        assert artifact['result'] == data
        assert len(content) < 24000 and json.loads(content)['preview_truncated']


def test_dart_cutoff_revision_identity_and_no_secret_in_receipt(monkeypatch):
    monkeypatch.setenv('OPENDART_API_KEY', 'private-test-key')
    def reply(request):
        assert request.url.params['last_reprt_at'] == 'N'
        return httpx.Response(200, json={'status': '000', 'list': [
            {'rcept_dt': '20260101', 'rcept_no': '20260101000001', 'report_nm': 'amended'},
            {'rcept_dt': '20260201', 'rcept_no': '20260201000001', 'report_nm': 'future'}]})
    t = korean_disclosure_tool(research_as_of='2026-01-10', transport=httpx.MockTransport(reply)).tool
    async def run():
        _, r = await t.coroutine(start_date='2026-01-01', end_date='2026-01-10')
        assert len(r['rows']) == 1 and '20260101000001' in r['rows'][0]['original_url']
        assert 'private-test-key' not in json.dumps(r)
        _, r = await t.coroutine(start_date='2026-01-01', end_date='2026-02-01')
        assert r['status'] == 'invalid_parameters'
    asyncio.run(run())


def test_both_tools_registered_for_review_and_readback():
    from sec_agent.agent_runtime.answer_review_provider import review_tool_names
    from sec_agent.agent_runtime.conversation_tools import SAVED_RESULT_TOOLS
    from sec_agent.agent_runtime.conversation_agent import research_system_prompt
    names = ['query_hithink', 'search_korean_disclosures']
    assert set(review_tool_names(names)) == set(names)
    assert set(names) <= SAVED_RESULT_TOOLS
    assert all(n in research_system_prompt(names) for n in names)
