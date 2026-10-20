"""One explicitly executed query-embedding probe; no research or rerank call.

Output and SQLite receipts must live outside Git. Reusing output/cache preserves
successful results and blocks unknown/failed requests; no automatic retry flag.
"""
import argparse
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from retrieval.query_embeddings import QueryEmbeddingSource
from retrieval.qwen_api import QwenRetrieval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--model', required=True, choices=['text-embedding-v4', 'qwen3.7-text-embedding'])
    parser.add_argument('--index-digest', required=True)
    parser.add_argument('--scope', required=True)
    parser.add_argument('--query', required=True, help='Public qualification text only; never put credentials here')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--concurrency', type=int, default=1, choices=[1, 4, 8, 16])
    args = parser.parse_args()
    size = len(args.query.encode('utf8'))
    if not args.query.strip() or size > 8192:
        parser.error('query must be nonempty and at most 8192 UTF-8 bytes')
    if len(args.index_digest) != 64 or any(c not in '0123456789abcdef' for c in args.index_digest):
        parser.error('index digest must be a lowercase SHA-256')
    if args.execute and not os.environ.get('QWEN_API_KEY'):
        parser.error('QWEN_API_KEY is absent')
    args.output.mkdir(parents=True, exist_ok=True)
    attempt = args.output / str(uuid4())
    attempt.mkdir()
    basis = {'purpose': 'Verify a new query vector, exact index model identity, durable receipt and reuse',
        'input_scale': {'texts': 1, 'concurrent_identical_callers':args.concurrency,
                        'utf8_bytes': size, 'query_sha256': sha256(args.query.encode()).hexdigest()},
        'required_output': 'One finite nonzero 1024-dimensional vector and provider usage receipt',
        'quality_risk': 'Connectivity and vector integrity only; no recall or financial quality claim',
        'reasoning_profile': 'Non-generative embedding; no rerank or research model',
        'limits': {'max_requests': 1, 'sdk_retries': 0, 'timeout_seconds': 45, 'max_input_utf8_bytes': 8192},
        'stop_behavior': 'Preserve pending/failed/unknown requests; no automatic resubmission',
        'model': args.model, 'dimensions': 1024, 'scope': args.scope, 'index_digest': args.index_digest,
        'execution_authorization': 'User explicitly authorized paid vector generation on 2026-10-20',
        'started_at': datetime.now(timezone.utc).isoformat()}
    (attempt/'TokenBudgetBasis.json').write_text(json.dumps(basis, indent=2), encoding='utf8')
    if not args.execute:
        print(json.dumps({'executed': False, 'basis_path': str(attempt/'TokenBudgetBasis.json')}))
        return
    started = time.perf_counter()
    try:
        with closing(QwenRetrieval(os.environ['QWEN_API_KEY'], embedding_model=args.model, timeout=45)) as api:
            source = QueryEmbeddingSource(args.output/'cache', api, model=args.model, wait_inflight_seconds=45)
            def invoke(_):
                start = time.perf_counter()
                vector, metadata = source.embed(args.query, scope=args.scope,
                    index_digest=args.index_digest, model=args.model, dimensions=1024)
                return vector, {**metadata, 'caller_elapsed_ms':(time.perf_counter()-start)*1000}
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                results = list(pool.map(invoke, range(args.concurrency)))
            vector, metadata = next((r for r in results if r[1]['provider_calls']), results[0])
            assert all(r[0] == vector for r in results)
            assert sum(r[1]['provider_calls'] for r in results) <= 1
            output = {'status': 'completed', **metadata, 'elapsed_ms': (time.perf_counter()-started)*1000}
            output['concurrent_callers'] = [r[1] for r in results]
            (attempt/'vector.json').write_text(json.dumps(vector), encoding='utf8')
            # Confirm persisted reuse through a new adapter, without another request.
            restored = QueryEmbeddingSource(args.output/'cache', api, model=args.model)
            again, replay = restored.embed(args.query, scope=args.scope,
                index_digest=args.index_digest, model=args.model, dimensions=1024)
            assert again == vector and replay['cache_hit'] and replay['provider_calls'] == 0
            output['persisted_replay'] = replay
    except Exception as error:
        output = {'status': 'failed_or_pending', 'error_type': type(error).__name__,
            'usage': 'unknown_or_not_dispatched_check_cache_receipt', 'elapsed_ms': (time.perf_counter()-started)*1000}
    (attempt/'result.json').write_text(json.dumps(output, indent=2), encoding='utf8')
    print(json.dumps({**output, 'artifact_directory': str(attempt)}))
    if output['status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
