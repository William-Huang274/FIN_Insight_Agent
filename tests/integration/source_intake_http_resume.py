"""Explicit retained immutable index -> current services qualification.

Does not claim a fresh publication or replay old query/authorization results.
The entire source generation is cold-verified with current implementation before
paid HTTP quality/load. Exact index files, Java contract and originals must agree.
"""
from hashlib import file_digest
import gc
import json
from pathlib import Path

import psycopg
import pytest

from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from tests.integration.source_intake_http import HttpNavigation, qualify_concurrency
from tests.integration.source_intake_quality import run_quality


def load_seal(path, *, intake_sha256, geometry_sha256):
    seal = json.loads(Path(path).read_bytes())
    if (seal.get('schema') != 'retained-http-index.v1'
            or seal['intake_sha256'] != intake_sha256 or seal['geometry_sha256'] != geometry_sha256):
        raise ValueError('retained_http_index_scope_changed')
    root = Path(seal['index_root']).resolve(strict=True)
    contract = seal['contract']
    from uuid import UUID
    directory = root/str(UUID(seal['organization_id']))/'releases'/str(UUID(contract['release_id']))
    if set(seal['files']) != {'index.json', 'vectors.npy', 'lexical.sqlite', 'navigation.sqlite', 'graph.sqlite'}:
        raise ValueError('retained_http_index_files_incomplete')
    for name, expected in seal['files'].items():
        target = (directory/name).resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError('retained_http_index_path_outside_root')
        with target.open('rb') as handle:
            if file_digest(handle, 'sha256').hexdigest() != expected:
                raise ValueError('retained_http_index_file_changed')
    return seal


def run(stack, seal, api, bundles, quality_data, quality_binding, budget, diagnostic, *, expected_chunks):
    from sec_agent.research_foundation.organization_index_release import load_release
    contract = seal['contract']
    indices = Path(seal['index_root'])
    org, release = seal['organization_id'], contract['release_id']
    assert load_release(indices, org, release)[3] == contract
    with psycopg.connect(host='127.0.0.1', port=stack.pg_port, dbname='business',
                         user='probe', password=stack.password) as db:
        rows = db.execute('SELECT b.id,b.draft_id,d.project_id,b.manifest_digest,d.manifest_text '
            'FROM organization_execution_binding b JOIN organization_research_draft d ON d.id=b.draft_id '
            'WHERE NOT b.closed').fetchall()
        spaces = db.execute("SELECT id FROM resource_space WHERE organization_id=%s AND kind='team'", (org,)).fetchall()
    matched = [row for row in rows if json.loads(row[4]).get('retrieval_index') == contract]
    if len(matched) != 1 or len(spaces) != 1:
        raise ValueError('retained_http_binding_ambiguous')
    execution, draft, project, manifest_digest, _ = matched[0]
    execution, draft, project = map(str, (execution, draft, project))
    prepared = api('GET', f'/projects/{project}/research-drafts/{draft}')
    reader = OrganizationExecutionReader(AssetWorkspace(stack.state/'project-library'/'organization-assets'),
        OrganizationExecutionAuthority(base_url=f'http://127.0.0.1:{stack.java_port}', secret=stack.runtime_secret,
            execution_id=execution, manifest_digest='sha256:'+manifest_digest))
    before, manifest, _ = reader._grant()
    assert manifest == prepared['manifest'] and len(manifest['inputs']) == len(bundles)
    navigation = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=indices)
    with diagnostic.phase('retained_index_current_cold_verification'):
        navigation.warm_release()
    candidate = navigation._candidate_index
    assert candidate.original_reads == len(bundles) and len(candidate.rows) == expected_chunks
    reader._after(before)
    stack.save('retained-index-current-verification', {'status': 'passed', 'sources': len(bundles),
        'chunks': expected_chunks, 'original_reads': candidate.original_reads,
        'publication_source_git': seal['publication_git'], 'same_version_republication': False,
        'current_permissions_rechecked': True, 'index_contract': contract})
    del candidate, navigation
    gc.collect()
    nav = HttpNavigation(stack, reader, project, draft)
    with diagnostic.phase('frozen_quality_replay_real_http'):
        requests = run_quality(quality_data, quality_binding, nav=nav, bundles=bundles,
                               save=stack.save, budget=budget)
    with diagnostic.phase('fixed_resource_http_concurrency'):
        load = qualify_concurrency(nav, requests, stack.save, budget,
            api=api, org=org, project=project, space=str(spaces[0][0]))
    nav.navigate(requests[-1])
    assert nav.navigate(requests[-1]).items[0]['retrieval']['response_cache_hit']
    selected = set(manifest['input_selection']['selected_resource_ids'])
    resource = next(i['resource_id'] for i in reversed(manifest['inputs']) if i['resource_id'] not in selected)
    current = stack.request(stack.bff, 'GET', f'/api/v1/asset-workspace/spaces/resources/{resource}')
    api('POST', f'/resources/{resource}/revoke', {'revision': current['permission_revision']})
    calls = dict(budget.calls)
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate(requests[-1])
    originals = contexts = 0
    for file in sorted(stack.output.glob('service-quality-question-*.json')):
        saved = json.loads(file.read_bytes())
        for row in saved['search']['items'][:10]:
            with pytest.raises(OrganizationExecutionUnavailable):
                nav.navigate(row['readback'])
            originals += 1
        for context in saved.get('verified_contexts', []):
            for request in context['readbacks']:
                with pytest.raises(OrganizationExecutionUnavailable):
                    nav.navigate(request)
                contexts += 1
    assert calls == budget.calls
    stack.save('service-quality-revocation', {'cached_search_denied': True,
        'non_selected_resource_revoked': resource, 'denied_original_readbacks': originals,
        'denied_context_readbacks': contexts, 'provider_calls_after_revocation': 0})
    stack.save('service-http-resume-result', {'status': 'completed', 'sources': len(bundles),
        'chunks': expected_chunks, 'publication_source_git': seal['publication_git'],
        'same_version_republication': False, 'quality_replay_passed': True,
        'load_all_requests_correct': load['all_requests_correct'], 'revocation_passed': True,
        'provider_calls': budget.calls, 'Agent_runs': 0, 'S2_passed': False})
