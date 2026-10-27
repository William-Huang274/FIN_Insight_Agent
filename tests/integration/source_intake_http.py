"""HTTP-only full-source qualification; no synthetic retrieval/provider output."""
from hashlib import sha256
import json
import os
from pathlib import Path

from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.source_document_navigation import SourceDocumentResult


def install_provider_budget():
    from retrieval.qwen_api import QwenRetrieval
    from tests.integration.source_intake_quality import PaidCallBudget
    root = Path(os.environ.get('FIN_COMPLETE_SOURCE_HTTP_EVIDENCE_ROOT',
                              str(Path(os.environ['FINSIGHT_LOCAL_STATE_ROOT']).parent)))
    def save(name, record):
        target = root/(name+'.json')
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')
        temporary.replace(target)
    budget = PaidCallBudget(80, save)
    QwenRetrieval.embed = budget.wrap('embedding', QwenRetrieval.embed)
    QwenRetrieval.rerank = budget.wrap('rerank', QwenRetrieval.rerank)


class RemoteBudget:
    limit = 80
    def __init__(self, root): self.root = root
    def record(self, status):
        path = self.root/'service-quality-provider-budget.json'
        return json.loads(path.read_bytes()) if path.exists() else {
            'calls': {'embedding': 0, 'rerank': 0}, 'failed': False, 'receipts': []}
    @property
    def calls(self): return self.record('observed')['calls']
    @property
    def failed(self): return self.record('observed')['failed']


class HttpNavigation:
    def __init__(self, stack, reader, project, draft):
        self.stack, self.reader = stack, reader
        self.path = (f'/api/v1/asset-workspace/organization-projects/{project}'
            f'/research-drafts/{draft}/executions/{reader.authority.execution_id}/navigate')
    def navigate(self, request):
        response = self.stack.bff.post(self.path, json=request, timeout=300)
        if response.status_code in (403, 404, 409):
            raise OrganizationExecutionUnavailable('http_navigation_denied')
        if response.status_code != 200:
            raise RuntimeError('http_navigation_status_'+str(response.status_code))
        return SourceDocumentResult.model_validate(response.json())


def qualify_concurrency(nav, requests, save, budget, *, api, org, project, space):
    """Closed-loop fixed compact profile; queue wait/failures retained.

    Cached searches and original reads are separate from paid search misses.
    This is local end-to-end latency, not exclusive-host/provider capacity.
    """
    import psutil
    from uuid import uuid4
    from scripts.engineering.qualification_load import measure
    report = {'status': 'running', 'profile': 'source_intake_compact', 'levels': [],
        'logical_cpus': psutil.cpu_count(), 'host_total_bytes': psutil.virtual_memory().total,
        'host_is_shared': True, 'external_provider_in_latency': True,
        'maximum_paid_calls_per_operation_including_quality': budget.limit,
        'cold_index_latency_included_in_load': False, 'capacity_ceiling_established': False}
    report['requests_per_level'] = {'cached_search': 32, 'original_read': 32, 'mixed_search': 8}
    report['percentile_scope'] = 'exploratory bounded samples, not a production SLA'
    save('service-http-concurrency', report)
    search = requests[-1]
    found = nav.navigate(search)
    if not found.items: raise ValueError('load_requires_verified_result')
    read = found.items[0]['readback']
    expected = nav.navigate(read).model_dump(mode='json')['items'][0]
    viewer = {'Authorization': 'Bearer qualification-viewer'}
    assert nav.stack.bff.post(nav.path, json=search, headers=viewer).status_code == 404
    invite = str(uuid4())
    api('POST', f'/organizations/{org}/invites', {'token': invite})
    joined = nav.stack.bff.post('/api/v1/business/workspaces/join', headers=viewer,
        json={'token': invite, 'display_name': 'Second retrieval researcher'})
    assert joined.status_code == 200
    api('POST', f'/spaces/{space}/members', {'subject': 'oidc:viewer', 'role': 'reader'})
    api('POST', f'/projects/{project}/members', {'revision': api('GET', f'/projects/{project}')['revision'],
        'subject': 'oidc:viewer', 'role': 'researcher'})
    warm = nav.stack.bff.post(nav.path, json=search, headers=viewer, timeout=300)
    assert warm.status_code == 200, warm.text[:300]
    report['authorized_identities'] = 2
    expected_by_query = {}
    for file in nav.stack.output.glob('service-quality-question-*.json'):
        saved = json.loads(file.read_bytes())['search']
        # The source protocol carries the exact original request query.
        rows = saved['items']
        expected_by_query[file.stem.removeprefix('service-quality-question-')] = [r['node_id'] for r in rows]
    quality = json.loads((nav.stack.output/'service-quality.json').read_bytes())
    expected_by_query = {row['request']['query']: expected_by_query[row['id']] for row in quality['rows']}
    for mode in ('cached_search', 'original_read', 'mixed_search'):
        for level in (1, 2, 4):
            memory = []
            def guard():
                free = psutil.virtual_memory().available
                memory.append(free)
                report['last_process_memory'] = [
                    {'pid': p.pid, 'rss_bytes': psutil.Process(p.pid).memory_info().rss,
                     'private_bytes': getattr(psutil.Process(p.pid).memory_info(), 'private', None)}
                    for p in nav.stack.processes if p.poll() is None]
                return free >= 800*2**20 and not budget.failed
            def operation(index, worker):
                body = read if mode == 'original_read' else search if mode == 'cached_search' else requests[index % 8]
                response = nav.stack.bff.post(nav.path, json=body, timeout=180,
                    headers=viewer if index % 2 else {'Authorization': 'Bearer qualification-alice'})
                if response.status_code != 200:
                    return {'ok': False, 'status': response.status_code}
                rows = response.json()['items']
                ok = bool(rows)
                if mode == 'original_read': ok = rows == [expected]
                elif mode == 'cached_search':
                    ok = [r['node_id'] for r in rows] == [r['node_id'] for r in found.items]
                else:
                    ok = [r['node_id'] for r in rows] == expected_by_query[body['query']]
                return {'ok': ok, 'status': response.status_code,
                    'response_cache_hit': rows[0].get('retrieval', {}).get('response_cache_hit') if rows else None}
            before = dict(budget.calls)
            result = measure(operation, concurrency=level,
                requests=report['requests_per_level'][mode], max_seconds=600, should_continue=guard)
            result.update(mode=mode, available_memory_min=min(memory) if memory else None,
                          provider_calls_before=before, provider_calls_after=dict(budget.calls))
            report['levels'].append(result)
            save('service-http-concurrency', report)
            if result['not_started'] or budget.failed:
                raise RuntimeError('concurrency_resource_or_provider_stop')
    report['status'] = 'completed'
    report['all_requests_correct'] = all(r['failed'] == 0 for r in report['levels'])
    api('POST', f'/organizations/{org}/remove-member', {'subject': 'oidc:viewer'})
    before = dict(budget.calls)
    for body in (search, read):
        assert nav.stack.bff.post(nav.path, json=body, headers=viewer).status_code == 404
    assert before == budget.calls
    assert nav.navigate(read).items[0]['passage'] == expected['passage']
    report['removed_member_denied_and_owner_still_authorized'] = True
    save('service-http-concurrency', report)
    return report
