"""Measure actual public HTTP routes, Agent data layer and full vector matrix.

No research model, new embeddings, Java service or shared deployment is started.
Organization/Java/MCP integration has a separate pressure workload. The caller
must state these boundaries when using results.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from threading import Event

import httpx
from retrieval.library_vectors import ready_index, dense_search
from retrieval.query_embeddings import QueryEmbeddingSource
from sec_agent.research_foundation.metric_workspace import query_metrics
from sec_agent.research_foundation.research_library import ResearchLibrary
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from scripts.engineering.qualification_load import measure, distribution


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class CacheOnly:
    rerank_model = 'qwen3-rerank'
    def __init__(self, model):
        self.embedding_model = model
    def embed(self, texts):
        raise AssertionError('qualification_must_not_dispatch_provider')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('library', 'index', 'dataset', 'sql-cases', 'query-cache', 'output'):
        parser.add_argument('--'+key, required=True, type=Path)
    parser.add_argument('--requests', type=int, default=100)
    args = parser.parse_args()
    assert 8 <= args.requests <= 500
    root = Path(__file__).resolve().parents[2]
    args.output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (args.output/(name+'.json')).write_text(json.dumps(value, indent=2), encoding='utf8')
    began = time.perf_counter()
    library = ResearchLibrary(args.library, retrieval_environment={})
    manifest, _, _ = ready_index(args.index, library.manifest['sha256'])
    dataset = json.loads(args.dataset.read_text(encoding='utf8'))
    cards = json.loads(args.sql_cases.read_text(encoding='utf8'))
    assert dataset['library_sha256'] == cards['library_sha256'] == library.manifest['sha256']
    queries = dataset['questions'][::3]  # One natural-language query per family.
    cached = QueryEmbeddingSource(args.query_cache, CacheOnly(manifest['embedding_model']),
                                  model=manifest['embedding_model'])
    eligible = {s['id'] for s in library.catalog('2026-09-23') if s['eligible']}
    prepared = []
    for query in queries:
        vector, receipt = cached.embed(query['query'], scope='public-recall-qualification',
            index_digest=manifest['matrix_sha256'], model=manifest['embedding_model'], dimensions=1024)
        assert receipt['provider_calls'] == 0
        prepared.append((query, vector, dense_search(args.index, manifest['library_sha256'], vector, eligible, k=40)))
    metric_cases = []
    for case in cards['cases']:
        record = case['snapshot']['rows'][0]
        request = {'entity_ids':[case['entity_id']], 'section':'card',
                   'record_id':record['id'], 'as_of':cards['as_of']}
        expected = query_metrics(args.library, **request)['items']
        assert expected
        metric_cases.append((request, fingerprint(expected)))
    save('contract', {'library_sha256':library.manifest['sha256'], 'vector_manifest':manifest,
        'dataset_sha256':sha256(args.dataset.read_bytes()).hexdigest(), 'query_families':len(queries),
        'sql_scenarios':len(metric_cases), 'paid_calls':0, 'requests_per_level':args.requests,
        'initialization_ms':(time.perf_counter()-began)*1000,
        'cache_condition':'Process validation and reference warmup complete; OS cache not flushed; query embeddings reused',
        'boundary':'Actual loopback HTTP public read router, Agent library.navigate data layer, exact full matrix cosine. Not organization auth or native graph throughput.',
        'blas_threads':os.getenv('OPENBLAS_NUM_THREADS'), 'python':sys.version})
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    assert port not in (18165, 18765)
    env = {k:v for k,v in os.environ.items() if not k.startswith(('FINSIGHT_', 'LANGSMITH_', 'LANGCHAIN_'))
           and not any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET'))}
    env.update(FIN_LIBRARY_READ_QUALIFICATION='1', FIN_LIBRARY_READ_STATE=str(args.output/'state'),
        FIN_LIBRARY_READ_DATABASE=str(args.library), PYTHONPATH=os.pathsep.join([str(root/'src'), str(root)]),
        PYTHONDONTWRITEBYTECODE='1')
    from tests.integration.test_organization_capacity_stack import available_memory
    log = (args.output/'http.log').open('w', encoding='utf8')
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn',
        'scripts.engineering.qualification_library_web:app', '--host','127.0.0.1','--port',str(port),
        '--no-access-log'], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=45, trust_env=False) as client:
            for _ in range(120):
                assert process.poll() is None
                try:
                    if client.get('/openapi.json').status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(.25)
            else:
                raise RuntimeError('qualification_http_start_timeout')
            for level in (1, 4, 8):
                stopped = Event()
                resources = []
                def guard():
                    free = available_memory()
                    resources.append({'time':time.monotonic(), 'free_bytes':free})
                    if free is not None and free < 512*1024**2:
                        stopped.set()
                    return not stopped.is_set()
                def operation(index, worker):
                    query, vector, expected_dense = prepared[index % len(prepared)]
                    evidence = query['evidence'][0]
                    metric, expected_metric = metric_cases[index % len(metric_cases)]
                    stages = {}
                    def timed(name, action):
                        start = time.perf_counter()
                        try:
                            return action()
                        finally:
                            stages[name] = (time.perf_counter()-start)*1000
                    web = timed('web_knowledge_original', lambda:client.get(
                        '/api/v1/data-library/research-sources/'+evidence['source_id'],
                        params={'passage_id':evidence['chunk_id'], 'limit':1}))
                    assert web.status_code == 200
                    assert web.json()['items'][0]['digest'] == evidence['body_sha256']
                    original = timed('agent_knowledge_original', lambda:library.navigate(SourceDocumentRequest(
                        source_space='library', operation='read', document_id=evidence['source_id'],
                        node_id=evidence['chunk_id'], max_characters=16000),query['as_of']))
                    assert original.items[0]['content_sha256'] == evidence['body_sha256']
                    result = timed('web_sql_card', lambda:client.post('/api/v1/data-library/metrics/query', json=metric))
                    assert result.status_code == 200
                    assert fingerprint(result.json()['items']) == expected_metric
                    result = timed('agent_sql_card', lambda:library.navigate(SourceDocumentRequest(
                        source_space='library', operation='data', data_kind='metrics', entity_id=metric['entity_ids'][0],
                        metric_section='card', metric_record_id=metric['record_id']), metric['as_of']))
                    assert fingerprint(result.items[0]['items']) == expected_metric
                    result = timed('dense_full_index', lambda:dense_search(args.index, manifest['library_sha256'],
                                                                          vector, eligible, k=40))
                    assert result == expected_dense
                    return {'ok':True, 'stages':stages, 'query_id':query['id'], 'metric_id':metric['record_id']}
                result = measure(operation, concurrency=level, requests=args.requests,
                                 max_seconds=1800, should_continue=guard)
                result.update(resource_samples=resources, resource_stop=stopped.is_set())
                result['stage_latency'] = {key:distribution([r['result']['stages'][key] for r in result['samples']
                    if r['result'].get('ok')]) for key in ('web_knowledge_original','agent_knowledge_original',
                                                         'web_sql_card','agent_sql_card','dense_full_index')}
                save('load-'+str(level), result)
                print(json.dumps({'concurrency':level, 'correct':result['correct'], 'failed':result['failed'],
                                  'stage_latency':result['stage_latency']}), flush=True)
                assert result['failed']==0 and result['not_started']==0, 'read_load_failures_retained'
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
        log.close()


if __name__ == '__main__':
    main()
