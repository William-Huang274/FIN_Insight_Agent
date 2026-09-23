"""Offline read-only replay: local query latency and explicit expected identities.

No embedding, reranker or answer-model requests. Cases and outputs are local
artifacts; mechanical expectations are not independently reviewed answer gold.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import platform
import statistics
import time

from sec_agent.research_foundation.research_library import ResearchLibrary
from sec_agent.research_foundation.metric_workspace import query_metrics


def execute(library, case):
    args = case['arguments']
    if case['operation'] == 'search':
        return library.search(**args)
    if case['operation'] == 'graph':
        return library.graph_search(**args)
    if case['operation'] == 'metric':
        return query_metrics(library.path, **args)
    if case['operation'] == 'read':
        return library.read(**args)
    raise ValueError('unsupported_offline_operation')


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100:
        parser.error('repeats must be 1..100')
    spec = json.loads(args.cases.read_text(encoding='utf8'))
    if not spec['cases'] or len({c['id'] for c in spec['cases']}) != len(spec['cases']):
        raise ValueError('empty_or_duplicate_cases')
    started = time.perf_counter()
    library = ResearchLibrary(args.library, retrieval_environment={})
    if library.manifest['sha256'] != spec['library_sha256']:
        raise ValueError('benchmark_snapshot_mismatch')
    report = {'version':'library-query-replay.v1','library_sha256':library.manifest['sha256'],
              'cases_sha256':digest(spec),'platform':platform.platform(),'paid_calls':0,
              'initialization_seconds':time.perf_counter()-started,'samples':[],
              'scope':'local read-only execution; OS page cache may be warm; no result cache or external APIs'}
    timings = defaultdict(list)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for iteration in range(args.repeats):
        # Rotate cases so one operation does not always receive the coldest read.
        cases = spec['cases'][iteration % len(spec['cases']):] + spec['cases'][:iteration % len(spec['cases'])]
        for case in cases:
            start = time.perf_counter()
            result = execute(library, case)
            elapsed = time.perf_counter()-start
            actual = digest(result)
            row = {'case_id':case['id'],'operation':case['operation'],'iteration':iteration,
                   'seconds':elapsed,'result_sha256':actual}
            expected = case.get('expected_sha256')
            if expected:
                row['expected_match'] = actual == expected
            timings[case['operation']].append(elapsed)
            report['samples'].append(row)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'completed_iterations':iteration+1,'samples':len(report['samples'])}),flush=True)
    report['latency'] = {op:{'n':len(values),'p50_seconds':statistics.median(values),
        'p95_seconds':sorted(values)[max(0, (95*len(values)+99)//100-1)],'max_seconds':max(values)}
        for op, values in timings.items()}
    report['all_declared_expectations_match'] = all(r.get('expected_match',True) for r in report['samples'])
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'latency':report['latency'],'expectations_match':report['all_declared_expectations_match']}))
    if not report['all_declared_expectations_match']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
