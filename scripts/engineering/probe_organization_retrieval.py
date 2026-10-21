"""Read-only MCP probe inside the native container; no graph or provider calls.

Input is an operator-owned binding file from authenticated browser preparation,
never a synthetic identity. Environment supplies the current Java authority.
"""
import argparse
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import time

from mcp import Client
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation, build_organization_source_server


async def probe(binding, original_digest):
    # This probe only exercises a pre-published query. Refuse an environment
    # able to bill a new embedding on a miss; do not monkeypatch production code.
    if os.getenv('FINSIGHT_ORGANIZATION_QUERY_EMBEDDING') or os.getenv('QWEN_API_KEY'):
        raise ValueError('probe_requires_paid_query_source_disabled')
    reader = OrganizationExecutionReader(AssetWorkspace(os.environ['FINSIGHT_ORGANIZATION_ASSETS_ROOT']),
        OrganizationExecutionAuthority(base_url=os.environ['FINSIGHT_BUSINESS_API_URL'],
            network_profile=os.environ.get('FINSIGHT_ORGANIZATION_AUTHORITY_NETWORK','loopback'),
            secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'],
            execution_id=binding['frozen_execution'],manifest_digest=binding['frozen_manifest_digest']))
    nav = OrganizationSourceNavigation(reader, workbench_url='https://localhost:18866',
        retrieval_root=os.environ['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT'])
    rows = []
    async with Client(build_organization_source_server(nav)) as client:
        for ordinal in range(2):
            start = time.perf_counter()
            result = await client.call_tool('read_source_document',{'request':{'source_space':'organization',
                'operation':'search','query':binding['payload']['question']}})
            assert not result.is_error
            items = result.structured_content['items']
            assert len(items) == 1 and items[0]['organization_source']['resource_id'] == binding['resource']
            assert items[0]['retrieval']['provider_calls'] == 0
            assert not items[0]['writer_citable']
            read = await client.call_tool('read_source_document',{'request':items[0]['readback']})
            assert not read.is_error
            original = read.structured_content['items'][0]
            assert original['writer_citable'] and original['content_sha256'] == original_digest
            assert sha256(original['passage'].encode()).hexdigest() == original_digest
            rows.append({'ordinal':ordinal,'elapsed_ms':(time.perf_counter()-start)*1000,
                'retrieval':items[0]['retrieval'],'original_sha256':original_digest})
        assert rows[-1]['retrieval']['cache_hit']
        unsupported = await client.call_tool('read_source_document',{'request':{'source_space':'organization',
            'operation':'search','query':'Unprepared query must not trigger an embedding request.'}})
        assert unsupported.is_error
    return {'scope':'production MCP adapter in native container, no graph execution',
        'rows':rows,'provider_calls':0,'unknown_query_refused':True,'financial_quality':'not_assessed'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--original-digest',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError('fresh_probe_output_required')
    result=asyncio.run(probe(json.loads(args.binding.read_text(encoding='utf8')),args.original_digest))
    args.output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'read_rounds':len(result['rows']),'provider_calls':0,'unknown_query_refused':True}))
