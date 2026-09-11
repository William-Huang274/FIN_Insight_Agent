"""Two real Keycloak users through HTTPS BFF and native Agent Server. Zero LLM.

Requires identity_provider_pilot and the dedicated HTTPS BFF. Receipts contain
only resource identifiers and statuses; access tokens and passwords stay private.
"""
import argparse
import asyncio
import json
from pathlib import Path
import ssl
from uuid import uuid4

import httpx
from sec_agent.agent_runtime.studio_configuration import default_configuration


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    private = json.loads((args.identity/'connection.private.json').read_text(encoding='utf-8'))
    verify = ssl.create_default_context(cafile=str(args.identity/'ca.pem'))
    receipts, resources = [], {}
    async with httpx.AsyncClient(verify=verify, trust_env=False, timeout=30) as c:
        tokens = {}
        for name, password in private['users'].items():
            response = await c.post(private['environment']['FINSIGHT_OIDC_ISSUER']+'/protocol/openid-connect/token',
                data={'client_id': 'finsight-qualification', 'grant_type': 'password', 'username': name, 'password': password})
            if response.status_code != 200:
                raise RuntimeError(f'identity_issuance:{name}:{response.status_code}')
            tokens[name] = response.json()['access_token']

        async def request(owner, method, path, *, expected=200, **kwargs):
            headers = {'X-Workbench-Request': '1', 'Origin': 'https://localhost:18815'}
            if owner:
                headers['Authorization'] = 'Bearer '+tokens[owner]
            response = await c.request(method, 'https://localhost:18815'+path, headers=headers, **kwargs)
            receipts.append({'owner': owner, 'method': method, 'path': path, 'status': response.status_code, 'expected': expected})
            (args.output/'receipts.json').write_text(json.dumps({'receipts': receipts, 'resources': resources, 'model_calls': 0}, indent=2), encoding='utf-8')
            if response.status_code != expected:
                raise RuntimeError(f'product_identity_status:{method}:{path}:{response.status_code}:expected{expected}')
            return response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text

        await request(None, 'GET', '/api/v1/research-sessions', expected=401)
        for name in tokens:
            r = await request(name, 'POST', '/api/v1/research-sessions', json={'title': '208 identity · '+name,
                'mode': 'research', 'question': '只核对授权资料中的年度收入，不启动模型。', 'defer_start': True})
            resources[name] = r['thread_id']
            await request(name, 'GET', '/api/v1/research-sessions/'+r['thread_id'])
        a, b = resources['alice'], resources['bob']
        for owner, own, foreign in [('alice', a, b), ('bob', b, a)]:
            rows = await request(owner, 'GET', '/api/v1/research-sessions')
            assert own in [r['thread_id'] for r in rows] and foreign not in [r['thread_id'] for r in rows]
            for suffix in ['', '/attachments', '/working-notes', '/user-context', '/manual-review', '/report-versions', '/report/export/md']:
                await request(owner, 'GET', '/api/v1/research-sessions/'+foreign+suffix, expected=404)
            await request(owner, 'POST', '/api/v1/research-sessions/'+foreign+'/start', expected=404)
        await request('alice', 'PUT', f'/api/v1/research-sessions/{a}/user-context', json={'body': '仅属于 Alice 的年度收入范围。', 'version': 0})
        context = await request('alice', 'GET', f'/api/v1/research-sessions/{a}/user-context')
        assert 'Alice' in context['body']
        context = await request('bob', 'GET', f'/api/v1/research-sessions/{b}/user-context')
        assert 'Alice' not in context.get('body', '')
        studio = await request('alice', 'POST', '/api/v1/research-studio/configurations', json=default_configuration().model_dump(mode='json'))
        aid = studio['assistant_id']; resources['alice_configuration'] = aid
        await request('bob', 'GET', '/api/v1/research-studio/configurations/'+aid, expected=404)
        await request('bob', 'POST', '/api/v1/research-studio/configurations/'+aid+'/apply', expected=404, json={'thread_id': b})
        versions = await request('bob', 'GET', '/api/v1/research-studio/configurations')
        assert aid not in [r['assistant_id'] for r in versions['versions']]
        await request('alice', 'POST', '/api/v1/research-studio/configurations/'+aid+'/apply', json={'thread_id': a})
        # Real concurrent requests; identity scope must survive await boundaries.
        async def read_one(owner):
            rows = await request(owner, 'GET', '/api/v1/research-sessions')
            assert resources[owner] in [r['thread_id'] for r in rows]
            assert resources['bob' if owner == 'alice' else 'alice'] not in [r['thread_id'] for r in rows]
        await asyncio.gather(*(read_one(n) for n in ['alice', 'bob']*4))
        print(json.dumps({'passed_http_checks': len(receipts), 'real_users': 2, 'model_calls': 0}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--identity', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    asyncio.run(run(p.parse_args()))
