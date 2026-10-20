"""Opt-in real BFF/Java reads and MCP tools over fixed historical organizations."""
import asyncio
import time
from threading import Event

from mcp import Client
from scripts.engineering.qualification_load import measure, distribution
from sec_agent.research_foundation.organization_source_navigation import (
    OrganizationSourceNavigation, build_organization_source_server)
from tests.integration.test_organization_capacity_stack import available_memory


def qualify(stack, tenants, root, *, count):
    assert 8 <= count <= 500
    for level in (1, 4, 8):
        stopped = Event()
        resource_samples = []
        def guard():
            free = available_memory()
            resource_samples.append({'time':time.monotonic(), 'free_bytes':free})
            if free is not None and free < 512*1024**2:
                stopped.set()
            return not stopped.is_set()
        def operation(index, worker):
            tenant = tenants[index % len(tenants)]
            stage = {}
            started = time.perf_counter()
            page = stack.request(stack.bff, 'GET',
                '/api/v1/asset-workspace/spaces/resources/'+tenant['selected'])
            stage['web_original'] = (time.perf_counter()-started)*1000
            assert page['publication']['organization_id'] == tenant['org']
            assert tenant['citation']['passage'] in page['text']
            async def tool_roundtrip():
                nav = OrganizationSourceNavigation(tenant['reader'],
                    workbench_url='http://localhost', retrieval_root=root)
                start = time.perf_counter()
                async with Client(build_organization_source_server(nav), raise_exceptions=False) as client:
                    stage['mcp_session_setup'] = (time.perf_counter()-start)*1000
                    start = time.perf_counter()
                    search = await client.call_tool('read_source_document', {'request':tenant['request']})
                    stage['mcp_search'] = (time.perf_counter()-start)*1000
                    assert not search.is_error
                    items = search.structured_content['items']
                    assert {r['organization_source']['resource_id'] for r in items} == {tenant['selected']}
                    assert items[0]['retrieval']['provider_calls'] == 0
                    start = time.perf_counter()
                    read = await client.call_tool('read_source_document', {'request':items[0]['readback']})
                    stage['mcp_original'] = (time.perf_counter()-start)*1000
                    assert not read.is_error
                    assert read.structured_content['items'][0]['content_sha256'] == tenant['citation']['content_sha256']
            asyncio.run(tool_roundtrip())
            return {'ok':True, 'organization_id':tenant['org'], 'stages':stage}
        result = measure(operation, concurrency=level, requests=count, max_seconds=1800,
                         should_continue=guard)
        result.update(resource_samples=resource_samples, resource_stop=stopped.is_set(),
            scope='Two fixed historical originals per index; two organization execution scopes; same user',
            transport='Real HTTP BFF/Java/PostgreSQL; MCP SDK in-process transport; fresh MCP session per operation',
            paid_calls=0, scenario='Warm historical vectors/query/rank cache; current authority rechecked every request')
        result['stage_latency'] = {key:distribution([r['result']['stages'][key] for r in result['samples']
            if r['result'].get('ok')]) for key in ('web_original','mcp_session_setup','mcp_search','mcp_original')}
        stack.save('retrieval-load-'+str(level), result)
        assert result['failed']==0 and result['not_started']==0, 'retrieval_load_failures_retained'
