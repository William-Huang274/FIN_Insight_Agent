"""Historical documents through real Java authority and Python source tools.

Opt-in local case manifest; no model or embedding calls, no shared services.
Published historical reports are test documents, never issuer fact authority.
"""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest

from apps.workbench.backend.business_transport import delegate
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from tests.integration.test_organization_graph_native import OrganizationGraphStack
from tests.integration.test_java_intake_native import wait_for

pytestmark = pytest.mark.skipif(os.getenv('FIN_HISTORICAL_CASE_MANIFEST') is None,
    reason='explicit isolated historical case manifest required')


def test_historical_documents_authority_search_restart_and_revocation(monkeypatch):
    spec_path = Path(os.environ['FIN_HISTORICAL_CASE_MANIFEST']).resolve()
    spec = json.loads(spec_path.read_text(encoding='utf8'))
    documents = []
    for item in spec['documents']:
        path = (spec_path.parent/item['file']).resolve()
        assert path.is_relative_to(spec_path.parent)
        body = path.read_bytes()
        assert hashlib.sha256(body).hexdigest() == item['sha256']
        assert item['expected_text'] in body.decode('utf8')
        documents.append((item, body))
    assert len(documents) >= 2
    s = OrganizationGraphStack()
    environment = json.loads((s.output/'environment.json').read_text())
    environment.update(real_services=['BFF', 'Spring Boot', 'PostgreSQL'],
        synthetic=['qualification identity'], native_service_started=False,
        documents='hashed historical copies; not financial gold')
    s.save('environment', environment)
    monkeypatch.setenv('FINSIGHT_BUSINESS_SHARED_SECRET', s.shared)
    def api(method, path, body=None):
        return s.request(s.bff, method, '/api/v1/business/workspaces'+path,
            **({'json': body} if body is not None else {}))
    try:
        # This slice exercises data authorization without running an Agent.
        # Do not introduce an idle native worker/Redis dependency into it.
        s.compose('up', '-d', '--pull', 'never', 'postgres')
        def database_ready():
            try:
                with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe', user='probe',
                        password=s.password, connect_timeout=2):
                    return True
            except psycopg.OperationalError:
                return False
        wait_for(database_ready)
        with psycopg.connect(host='127.0.0.1', port=s.pg_port, dbname='probe', user='probe',
                password=s.password, autocommit=True) as db:
            db.execute('CREATE DATABASE business')
        business = s.boot('java'); s.boot('bff')
        org, space, project, private = [str(uuid4()) for _ in range(4)]
        api('POST', '/organizations', {'id': org, 'name': 'Historical qualification', 'display_name': 'Alice'})
        api('POST', '/spaces', {'id': space, 'organization_id': org, 'name': 'Historical material copies'})
        api('POST', '/projects', {'id': project, 'organization_id': org, 'name': 'Historical retrieval scenario',
            'description': 'Engineering copies; historical financial conclusions not endorsed'})
        assets = AssetWorkspace(s.state/'project-library')
        assets.library.save('oidc:alice', 0, {'projects': [{'id': private, 'name': 'Import copies'}],
            'assignments': {}, 'pinned': []})
        resources = []
        for item, body in documents:
            assets.library.documents.add(assets.library.scope('oidc:alice', private), item['file'], body)
            ref = next(x['current']['ref'] for x in assets.catalog('oidc:alice', private)['items']
                if x['current']['title'] == item['file'])
            rid = str(uuid4())
            s.request(s.bff, 'POST', '/api/v1/asset-workspace/spaces/publish',
                json={'id': rid, 'space_id': space, 'ref': ref})
            revision = api('GET', f'/projects/{project}')['revision']
            api('POST', f'/projects/{project}/resources/{rid}', {'revision': revision, 'linked': True})
            resources.append(rid)
        draft, execution = str(uuid4()), str(uuid4())
        prepared = api('POST', f'/projects/{project}/research-drafts', {'id': draft,
            'title': 'Read historical evidence', 'question': spec['question'],
            'research_as_of': spec['as_of'], 'resource_ids': [resources[0]]})
        path = f'/v1/workspaces/projects/{project}/research-drafts/{draft}/execution-bindings'
        body = json.dumps({'id': execution, 'manifest_digest': prepared['manifest_digest']}, separators=(',', ':')).encode()
        with httpx.Client(trust_env=False) as client:
            bound = client.post(f'http://127.0.0.1:{s.java_port}'+path, content=body,
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+delegate('oidc:alice', 'POST', path, body)})
            assert bound.status_code == 200, bound.text
        def navigator():
            authority = OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{s.java_port}',
                secret=s.runtime_secret, execution_id=execution, manifest_digest=prepared['manifest_digest'])
            return OrganizationSourceNavigation(OrganizationExecutionReader(
                AssetWorkspace(s.state/'project-library'/'organization-assets'), authority), workbench_url='http://localhost')
        nav = navigator()
        search = nav.navigate({'source_space': 'organization', 'operation': 'search', 'query': documents[0][0]['query']})
        assert search.items
        assert {x['organization_source']['resource_id'] for x in search.items} == {resources[0]}
        read = nav.navigate(search.items[0]['readback'])
        if read.items[0].get('read_status') == 'window_required':
            read = nav.navigate(read.items[0]['readback'])
        citation = read.items[0]
        assert citation['result_state'] == 'source_bound_passage'
        assert documents[0][0]['expected_text'] in citation['passage']
        assert citation['organization_source']['ref'] == prepared['manifest']['inputs'][0]['ref']
        assert not citation['numeric_fact_authority']
        saved = [{'status': 'success', 'content': [citation]}]
        # Restart only this scenario's Java process; reconstruct tool state from
        # historical observations and validate the original publication again.
        business.terminate(); business.wait(timeout=20); s.boot('java')
        restored = navigator(); restored.restore(saved)
        assert restored.source(citation['passage_id']) == citation
        with pytest.raises(OrganizationExecutionUnavailable):
            restored.navigate({'source_space': 'organization', 'operation': 'read',
                'document_id': 'ORGDOC::'+resources[1]+':foreign'})
        current = s.request(s.bff, 'GET', f'/api/v1/asset-workspace/spaces/resources/{resources[0]}')
        api('POST', f'/resources/{resources[0]}/revoke', {'revision': current['permission_revision']})
        with pytest.raises(OrganizationExecutionUnavailable):
            restored.source(citation['passage_id'])
        with pytest.raises(OrganizationExecutionUnavailable):
            restored.navigate({'source_space': 'organization', 'operation': 'search', 'query': documents[0][0]['query']})
        assert not (s.state/'native-create-observations.jsonl').exists()
        assert not (s.state/'native-start-observations.jsonl').exists()
        s.save('historical-result', {'status': 'passed', 'manifest': spec, 'project_id': project,
            'execution_id': execution, 'frozen_manifest_digest': prepared['manifest_digest'],
            'search': search.model_dump(mode='json'), 'citation': citation, 'java_restart': True,
            'excluded_other_project_resource': True, 'revoked_read_and_search_denied': True,
            'native_service_started': False, 'provider_calls': 0, 'vector_search': 'not_enabled_in_organization_path',
            'financial_quality': 'not_assessed'})
    finally:
        for process in s.processes:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=20)
        for log in s.logs:
            log.close()
        try:
            s.compose('logs', '--no-color')
        finally:
            s.compose('stop', '-t', '5'); s.bff.close(); s.native.close()
