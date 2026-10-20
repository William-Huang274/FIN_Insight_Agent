"""Isolated multi-identity load through real business/queue/source/checkpoint.

Static model decisions read a real historical excerpt. This measures engineering
capacity, never paid LLM throughput or correctness of a financial conclusion.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from uuid import uuid4

import httpx
import psycopg
import pytest

from scripts.engineering.qualification_load import measure, distribution
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from tests.integration.test_organization_graph_native import OrganizationGraphStack, ROOT

pytestmark = pytest.mark.skipif(os.getenv('FIN_ORGANIZATION_CAPACITY_QUALIFICATION') != '1',
    reason='explicit isolated multi-identity capacity qualification required')


def available_memory():
    """Windows host stop line, not a substitute for recorded Docker resources."""
    if os.name != 'nt':
        return None
    import ctypes
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
            *[(name, ctypes.c_ulonglong) for name in (
                'total', 'available', 'total_page', 'available_page', 'total_virtual', 'available_virtual', 'extended')]]
    value = Memory()
    value.length = ctypes.sizeof(value)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
        raise OSError('host_memory_observation_failed')
    return value.available


class CapacityStack(OrganizationGraphStack):
    compose_files = (*OrganizationGraphStack.compose_files, ROOT/'deploy/qualification/capacity_limits.compose.yaml')

    def __init__(self):
        super().__init__()
        self.env['FIN_ORGANIZATION_CAPACITY_QUALIFICATION'] = '1'
        self.env['JAVA_TOOL_OPTIONS'] = '-Xms64m -Xmx256m -XX:ActiveProcessorCount=2'


def test_historical_source_multi_identity_research_load(monkeypatch):
    case_path = Path(os.environ['FIN_ORGANIZATION_HYBRID_CASES'])
    cases = json.loads(case_path.read_text(encoding='utf8'))
    case = next(c for c in cases['cases'] if c['id'] == 'nvidia_concentration')
    document = case['documents'][0]
    body = (case_path.parent/document['file']).read_bytes()
    assert sha256(body).hexdigest() == document['sha256']
    levels = [int(x) for x in os.getenv('FIN_CAPACITY_LEVELS', '1,4,8').split(',')]
    count = int(os.getenv('FIN_CAPACITY_REQUESTS_PER_LEVEL', '24'))
    assert levels and all(n in (1, 4, 8, 16) for n in levels)
    assert max(levels) <= count <= 500
    users = max(8, max(levels))
    memory = available_memory()
    assert memory is None or memory >= 2*1024**3, 'host_free_memory_below_2GiB_before_isolated_stack'
    s = CapacityStack()
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    clients = []
    def api(method, path, data=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces'+path,
                         **({'json': data} if data is not None else {}))
    try:
        s.save('load-contract', {'levels':levels, 'requests_per_level':count, 'identities':users,
            'source_sha256':document['sha256'], 'case':case['id'], 'paid_calls':0,
            'native_jobs_per_worker':1, 'java_heap_max_mib':256, 'initial_available_memory':memory,
            'meaning':'Closed-loop full orientation with scripted model decisions and real original readback',
            'source_hashes':{p:sha256((ROOT/p).read_bytes()).hexdigest() for p in [
                'tests/integration/test_organization_capacity_stack.py',
                'scripts/engineering/qualification_load.py',
                'deploy/qualification/capacity_limits.compose.yaml']}})
        s.compose('up', '-d', '--pull', 'never', 'api')
        s.healthy()
        s.audit_container()
        with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe',
                             user='probe', password=s.password, autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        s.boot('java')
        s.boot('bff')
        org, space, private, resource = [str(uuid4()) for _ in range(4)]
        projects = [str(uuid4()), str(uuid4())]
        api('POST', '/organizations', {'id':org, 'name':'Historical capacity qualification', 'display_name':'Owner'})
        api('POST', '/spaces', {'id':space, 'organization_id':org, 'name':'Shared historical originals'})
        for project in projects:
            api('POST', '/projects', {'id':project, 'organization_id':org,
                'name':'Historical load '+project[:8], 'description':'Static model decisions; real source/authority'})
        assets = AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice', 0, {'projects':[{'id':private, 'name':'Original'}], 'assignments':{}, 'pinned':[]})
        assets.library.documents.add(assets.library.scope('oidc:alice', private), 'Historical NVIDIA.txt', body)
        ref = assets.catalog('oidc:alice', private)['items'][0]['current']['ref']
        s.request(s.bff, 'POST', '/api/v1/asset-workspace/spaces/publish',
            json={'id':resource, 'space_id':space, 'ref':ref})
        for project in projects:
            api('POST', f'/projects/{project}/resources/{resource}', {'revision':1, 'linked':True})
        for number in range(users):
            client = httpx.Client(base_url=s.bff.base_url, timeout=50, trust_env=False,
                headers={'Authorization':f'Bearer qualification-user-{number}', 'X-Workbench-Request':'1'})
            clients.append(client)
            invite = str(uuid4())
            api('POST', f'/organizations/{org}/invites', {'token':invite})
            s.request(client, 'POST', '/api/v1/business/workspaces/join',
                json={'token':invite, 'display_name':f'Researcher {number}'})
            api('POST', f'/spaces/{space}/members', {'subject':f'oidc:load-user-{number}', 'role':'reader'})
            for project in projects:
                api('POST', f'/projects/{project}/members', {'revision':api('GET', f'/projects/{project}')['revision'],
                    'subject':f'oidc:load-user-{number}', 'role':'researcher'})
        for level in levels:
            memory = available_memory()
            assert memory is None or memory >= 512*1024**2, 'host_stop_line_512MiB'
            def operation(index, worker):
                number = worker if level > 1 else index % users
                client, project = clients[number], projects[number % len(projects)]
                draft, tid = str(uuid4()), str(uuid4())
                stage_ms = {}
                began = time.perf_counter()
                def step(name, method, path, data):
                    start = time.perf_counter()
                    try:
                        return s.request(client, method, path, json=data)
                    finally:
                        stage_ms[name] = (time.perf_counter()-start)*1000
                try:
                    preparation = step('draft', 'POST', f'/api/v1/business/workspaces/projects/{project}/research-drafts',
                        {'id':draft, 'title':f'Load {level}/{index}', 'question':'Read the fixed NVIDIA disclosure and preserve its source identity.',
                         'research_as_of':cases['as_of'], 'resource_ids':[resource]})
                    prepared = step('prepare', 'POST', f'/api/v1/organization-projects/{project}/research-drafts/{draft}/prepare',
                        {'execution_id':tid, 'manifest_digest':preparation['manifest_digest'],
                         'execution':{'mode':'auto', 'model':'default', 'branch_ids':[], 'continuation_scope':'original_plan'}})
                    assert prepared['status'] == 'received'
                    started = step('start', 'POST', f'/api/v1/organization-projects/{project}/research/{tid}/start', {})
                    assert started['status'] == 'received'
                    accepted_ms = (time.perf_counter()-began)*1000
                    rid = started['run_id']
                    wait_start = time.perf_counter()
                    s.terminal(tid, rid, seconds=180)
                    stage_ms['accepted_to_terminal'] = (time.perf_counter()-wait_start)*1000
                    snapshot = s.state_of(tid)
                    assert snapshot['values']['phase'] == 'research_orientation_submitted'
                    quote = snapshot['values']['research_orientation']['findings'][0]['evidence_spans'][0]['quote']
                    assert quote and quote in body.decode('utf8')
                    assert len(s.runs(tid)) == 1 and len(s.turns(tid)) == 3
                    with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='business',
                                         user='probe', password=s.password) as db:
                        owner = db.execute('SELECT created_by FROM organization_research_draft WHERE id=%s', (draft,)).fetchone()
                    assert owner == (f'oidc:load-user-{number}',)
                    return {'ok':True, 'identity':number, 'project':project, 'draft_id':draft,
                        'thread_id':tid, 'run_id':rid, 'stage_ms':stage_ms, 'accepted_ms':accepted_ms}
                except Exception as error:
                    return {'ok':False, 'identity':number, 'project':project, 'draft_id':draft,
                        'thread_id':tid, 'stage_ms':stage_ms, 'error_type':type(error).__name__}
            result = measure(operation, concurrency=level, requests=count, max_seconds=900)
            result['available_memory_before'] = memory
            result['available_memory_after'] = available_memory()
            result['stage_latency'] = {stage:distribution([
                r['result']['stage_ms'][stage] for r in result['samples'] if stage in r['result'].get('stage_ms', {})])
                for stage in ('draft', 'prepare', 'start', 'accepted_to_terminal')}
            result['acceptance_latency'] = distribution([r['result']['accepted_ms'] for r in result['samples'] if r['result'].get('ok')])
            s.save(f'load-{level}', result)
            assert result['failed'] == 0 and result['not_started'] == 0, 'load_errors_retained_in_samples'
        assert sha256((case_path.parent/document['file']).read_bytes()).hexdigest() == document['sha256']
    finally:
        for client in clients:
            client.close()
        for process in s.processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
        for log in s.logs:
            log.close()
        try:
            s.compose('logs', '--no-color')
        finally:
            s.compose('stop', '-t', '5')
            s.bff.close()
            s.native.close()
