"""Fixed organization tools, real custody and fake model transport; no paid calls."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import httpx
import jwt
import pytest

from apps.workbench.backend.space_assets import SpaceAssets
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable,
    build_organization_evidence_server,
)
from test_organization_research_inputs import fixture
from test_model_dispatch_guard import boundary, response
from test_project_source_captures import setup, selections, save, reference, source_library

SECRET = 'synthetic-independent-runtime-secret-at-least-32-bytes'


def runtime_grant(preparation):
    encoded = json.dumps(preparation['manifest'], ensure_ascii=False, separators=(',', ':'))
    execution = str(uuid4())
    return {'contract_version': 'organization_execution_binding.v1', 'execution_id': execution,
            'thread_id': execution, 'draft_id': preparation['id'], 'project_id': preparation['project_id'],
            'organization_id': preparation['organization_id'], 'manifest_text': encoded,
            'manifest_digest': 'sha256:' + sha256(encoded.encode()).hexdigest(), 'status': 'bound',
            'native_execution_enabled': False, 'inputs': preparation['inputs']}


def runtime_at(shared, grant):
    state = {'status': 200, 'grant': deepcopy(grant), 'calls': 0}
    def handler(request):
        state['calls'] += 1
        claims = jwt.decode(request.headers['authorization'][7:], SECRET, algorithms=['HS256'],
                            issuer='finsight-agent-runtime', audience='finsight-java-organization-runtime')
        assert claims['sub'] == 'finsight-agent-runtime' and claims['path'] == request.url.path
        assert claims['method'] == 'POST' and claims['body_sha256'] == sha256(request.content).hexdigest()
        assert claims['exp'] - claims['iat'] == 60
        assert json.loads(request.content) == {'thread_id': grant['execution_id'], 'manifest_digest': grant['manifest_digest']}
        if state.get('timeout'):
            raise httpx.ReadTimeout('synthetic outage')
        return httpx.Response(state['status'], json=state['grant'])
    authority = OrganizationExecutionAuthority(base_url='http://127.0.0.1:9', secret=SECRET,
        execution_id=grant['execution_id'], manifest_digest=grant['manifest_digest'], transport=httpx.MockTransport(handler))
    return OrganizationExecutionReader(shared.workspace, authority), state


@pytest.mark.parametrize('fault', ['execution', 'thread', 'manifest', 'digest', 'project', 'duplicate', 'missing', 'ref', 'organization'])
def test_malformed_authority_cannot_read_originals(tmp_path, monkeypatch, fault):
    shared, preparation = fixture(tmp_path)
    grant = runtime_grant(preparation)
    reader, state = runtime_at(shared, grant)
    calls = []
    monkeypatch.setattr(shared.workspace, 'read', lambda *args: calls.append(args))
    changed = state['grant']
    if fault in {'execution', 'thread', 'project', 'organization'}: changed[fault + '_id'] = str(uuid4())
    if fault == 'manifest': changed['manifest_text'] += ' '
    if fault == 'digest': changed['manifest_digest'] = 'sha256:' + '0' * 64
    if fault == 'duplicate': changed['inputs'] *= 2
    if fault == 'missing': changed['inputs'] = []
    if fault == 'ref': changed['inputs'][0]['binding']['ref']['version_id'] = 'UPLOAD::different'
    with pytest.raises(OrganizationExecutionUnavailable): reader.read_text(grant['inputs'][0]['resource_id'])
    assert calls == [] and state['calls'] == 1


def test_mcp_connection_checks_current_rights_on_every_read_and_has_no_arbitrary_tools(tmp_path):
    from mcp import Client
    shared, preparation = fixture(tmp_path)
    grant = runtime_grant(preparation)
    reader, state = runtime_at(shared, grant)
    resource = grant['inputs'][0]['resource_id']
    async def exercise():
        async with Client(build_organization_evidence_server(reader), raise_exceptions=False) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools.tools} == {'list_organization_evidence', 'read_organization_evidence', 'read_organization_evidence_rows'}
            for tool in tools.tools:
                assert not {'owner_id', 'project_id', 'thread_id', 'execution_id', 'sql', 'path'} & tool.input_schema.get('properties', {}).keys()
            first = await client.call_tool('read_organization_evidence', {'resource_id': resource, 'limit': 6})
            assert not first.is_error, first
            assert first.structured_content['text'] == 'Pinned' and first.structured_content['next_offset'] == 6
            assert first.structured_content['version']['ref'] == grant['inputs'][0]['binding']['ref']
            assert (await client.call_tool('read_organization_evidence', {'resource_id': str(uuid4())})).is_error
            state['status'] = 404
            assert (await client.call_tool('list_organization_evidence', {})).is_error
            assert (await client.call_tool('read_organization_evidence', {'resource_id': resource})).is_error
            state['status'] = 200
            assert not (await client.call_tool('read_organization_evidence', {'resource_id': resource})).is_error
    asyncio.run(exercise())


def test_permission_loss_during_storage_and_original_corruption_never_return_content(tmp_path, monkeypatch):
    shared, preparation = fixture(tmp_path)
    grant = runtime_grant(preparation)
    reader, state = runtime_at(shared, grant)
    resource = grant['inputs'][0]['resource_id']
    read = shared.workspace.read
    def revoke(*args):
        result = read(*args)
        state['status'] = 404
        return result
    monkeypatch.setattr(shared.workspace, 'read', revoke)
    with pytest.raises(OrganizationExecutionUnavailable): reader.read_text(resource)
    assert state['calls'] == 2
    monkeypatch.setattr(shared.workspace, 'read', read)
    state['status'] = 200
    get = shared.workspace.library.documents.get
    monkeypatch.setattr(shared.workspace.library.documents, 'get', lambda *a, **k: {**get(*a, **k), 'body': b'corrupted'})
    with pytest.raises(OrganizationExecutionUnavailable): reader.read_text(resource)
    monkeypatch.setattr(shared.workspace.library.documents, 'get', get)
    assert reader.read_text(resource)['text'] == 'Pinned original evidence.'


@pytest.mark.parametrize('fault', [401, 404, 500, 302, 'timeout'])
def test_authority_failure_never_retries_or_reuses_previous_success(tmp_path, fault):
    shared, preparation = fixture(tmp_path)
    reader, state = runtime_at(shared, runtime_grant(preparation))
    reader.check()
    if fault == 'timeout': state['timeout'] = True
    else: state['status'] = fault
    with pytest.raises(OrganizationExecutionUnavailable): reader.check()
    assert state['calls'] == 2


def test_model_boundary_refuses_old_context_after_organization_revocation(tmp_path, boundary):
    shared, preparation = fixture(tmp_path)
    reader, state = runtime_at(shared, runtime_grant(preparation))
    boundary.audit.source_access_check = reader.check
    transmitted = []
    async def provider(request):
        transmitted.append(True)
        return response()
    asyncio.run(boundary.audit.awrap_model_call(boundary.request, provider))
    reserved = boundary.store.reserve.call_count
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        asyncio.run(boundary.audit.awrap_model_call(boundary.request, provider))
    assert transmitted == [True] and boundary.store.reserve.call_count == reserved
    assert boundary.public[-1]['provider_call_attempted'] is False


def test_fixed_financial_rows_keep_exact_value_period_unit_and_source(tmp_path, source_library):
    client, provider, _, _, _, _, source, project = setup(tmp_path, source_library)
    saved = save(client, project, selections(provider)[1])
    ref = reference(source, project, saved)
    shared, preparation = fixture(tmp_path/'base')
    item = preparation['manifest']['inputs'][0]
    binding = shared.publish(source, 'local-pilot', str(uuid4()), preparation['organization_id'], item['space_id'], ref)
    item.update(resource_id=str(uuid4()), resource_type='database', ref=binding['ref'])
    preparation['inputs'] = [{'resource_id': item['resource_id'], 'binding': binding}]
    reader, _ = runtime_at(shared, runtime_grant(preparation))
    result = reader.read_rows(item['resource_id'])
    assert result['rows'] == source.read('local-pilot', ref)['capture']['rows']
    row = result['rows'][0]
    assert row['value_decimal'] == '100' and row['unit'] == 'USD'
    assert row['period_end'] == '2025-06-30' and row['filed_at'] == '2025-09-01'
    assert result['total'] == 1 and result['next_offset'] is None
    assert reader.read_text(item['resource_id'])['structured_rows_available']
    assert reader.read_rows(item['resource_id'], offset=1)['rows'] == []
