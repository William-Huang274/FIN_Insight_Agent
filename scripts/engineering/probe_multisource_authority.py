"""Persistent production MCP session across real browser ACL mutations; no graph.

May run in the native container or against the same frozen code on the host.
The caller must record which transport/runtime was actually exercised.
"""
import argparse
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import traceback

from mcp import Client
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation, build_organization_source_server


async def probe(directory):
    assert not any(os.getenv(key) for key in ('FINSIGHT_ORGANIZATION_QUERY_EMBEDDING', 'QWEN_API_KEY', 'DASHSCOPE_API_KEY', 'OPENAI_API_KEY'))
    binding = json.loads((directory / 'binding.json').read_text(encoding='utf8'))
    reader = OrganizationExecutionReader(AssetWorkspace(os.environ['FINSIGHT_ORGANIZATION_ASSETS_ROOT']),
        OrganizationExecutionAuthority(base_url=os.environ['FINSIGHT_BUSINESS_API_URL'],
            network_profile=os.environ['FINSIGHT_ORGANIZATION_AUTHORITY_NETWORK'],
            secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'], execution_id=binding['frozen_execution'],
            manifest_digest=binding['frozen_manifest_digest']))
    nav = OrganizationSourceNavigation(reader, workbench_url='https://localhost:18866',
        retrieval_root=os.environ['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT'])
    expected = {s['resource']: s['content_sha256'] for s in binding['sources']}
    search = {'source_space': 'organization', 'operation': 'search', 'query': binding['question']}
    rows, readbacks = [], []

    def checkpoint(name, row):
        rows.append({'stage': name, **row})
        (directory / (name + '.done.json')).write_text(json.dumps(rows[-1]), encoding='utf8')

    async def signal(name):
        deadline = time.monotonic() + 150
        while not (directory / (name + '.go')).exists():
            if time.monotonic() > deadline:
                raise TimeoutError('browser_acl_signal_timeout:' + name)
            await asyncio.sleep(.2)

    async with Client(build_organization_source_server(nav)) as client:
        async def visible(name):
            result = await client.call_tool('read_source_document', {'request': search})
            assert not result.is_error
            items = result.structured_content['items']
            assert {item['organization_source']['resource_id'] for item in items} == set(expected)
            for item in items:
                assert not item['writer_citable'] and item['retrieval']['provider_calls'] == 0
                read = await client.call_tool('read_source_document', {'request': item['readback']})
                assert not read.is_error
                original = read.structured_content['items'][0]
                assert original['writer_citable']
                assert original['content_sha256'] == sha256(original['passage'].encode()).hexdigest() == expected[item['organization_source']['resource_id']]
            return items

        await visible('cold')
        warm = await visible('warm')
        assert all(item['retrieval']['cache_hit'] for item in warm)
        readbacks = [item['readback'] for item in warm]
        checkpoint('warm', {'sources': len(warm), 'cache_hit': True})
        for scope in ('space', 'project'):
            await signal(scope + '-revoked')
            denied = 0
            for request in [search, *readbacks]:
                result = await client.call_tool('read_source_document', {'request': request})
                assert result.is_error, 'cached_read_allowed_after_' + scope + '_revocation'
                assert not (result.structured_content or {}).get('items'), 'error_contains_source_items'
                denied += 1
            checkpoint(scope + '-revoked', {'denied_operations': denied, 'source_items_returned': 0})
            await signal(scope + '-restored')
            await visible(scope + '-restored')
            # Read the very same original citation addresses observed before revocation.
            for request in readbacks:
                result = await client.call_tool('read_source_document', {'request': request})
                assert not result.is_error
            checkpoint(scope + '-restored', {'sources': 2, 'original_readback_ids_preserved': True})
    result = {'rows': rows, 'same_mcp_session': True, 'provider_calls': 0,
        'scope': 'current ACL of one two-source preparation, existing exact vectors; no graph or financial-quality assessment'}
    (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({'stages': len(rows), 'provider_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(probe(args.directory))
    except Exception as error:
        def leaves(exc):
            if isinstance(exc, BaseExceptionGroup):
                return [leaf for child in exc.exceptions for leaf in leaves(child)]
            return [{'error': type(exc).__name__,
                'frames': [{'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
                           for frame in traceback.extract_tb(exc.__traceback__)]}]
        # Structural traceback only: never serialize request headers or credentials.
        (args.directory / 'failure.json').write_text(json.dumps({'error': type(error).__name__,
            'summary': str(error).split('\n')[0][:300], 'leaves': leaves(error)}), encoding='utf8')
        raise
