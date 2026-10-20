"""Bounded closed-loop load measurement, retaining failures and raw samples.

The caller supplies real operations with transport timeouts and correctness
checks. This is a measurement helper, not a queue or an open-loop capacity claim.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from math import ceil
import time
from threading import Barrier


def distribution(values):
    if not values:
        return {'n': 0}
    ordered = sorted(values)
    return {'n': len(ordered), **{f'p{p}_ms': ordered[max(0, ceil(len(ordered)*p/100)-1)]
        for p in (50, 95, 99)}, 'max_ms': ordered[-1], 'min_ms': ordered[0]}


def measure(operation, *, concurrency, requests, max_seconds=180):
    """Operation(index, worker) returns a dict whose ok field is strictly bool.

    Each worker sends its next request only after the previous one terminates.
    Request-index assignment is deterministic. Errors are measured, not retried.
    max_seconds bounds scheduling, NOT in-flight I/O; callers must set timeouts.
    """
    if not 1 <= concurrency <= 64 or not concurrency <= requests <= 100000 or not 0 < max_seconds <= 3600:
        raise ValueError('invalid_bounded_load')
    barrier = Barrier(concurrency)
    started = time.perf_counter()
    def worker(number):
        samples = []
        barrier.wait(timeout=30)
        for index in range(number, requests, concurrency):
            if time.perf_counter()-started >= max_seconds:
                break
            before = time.perf_counter()
            try:
                result = operation(index, number)
                if not isinstance(result, dict) or type(result.get('ok')) is not bool:
                    raise TypeError('load_operation_requires_explicit_correctness')
            except Exception as error:
                # Messages can contain URLs, credentials or private response text.
                result = {'ok': False, 'error_type': type(error).__name__}
            samples.append({'index': index, 'worker': number, 'start_ms': (before-started)*1000,
                'elapsed_ms': (time.perf_counter()-before)*1000, 'result': result})
        return samples
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker, number) for number in range(concurrency)]
        samples = sorted((row for future in futures for row in future.result()), key=lambda row: row['index'])
    elapsed = time.perf_counter()-started
    successes = [row for row in samples if row['result']['ok']]
    return {'load_model': 'closed_loop_no_think_time', 'concurrency': concurrency,
        'requested': requests, 'completed': len(samples), 'correct': len(successes),
        'failed': len(samples)-len(successes), 'not_started': requests-len(samples),
        'success_rate': len(successes)/len(samples) if samples else 0,
        'elapsed_seconds': elapsed, 'completed_per_second': len(samples)/elapsed,
        'correct_per_second': len(successes)/elapsed,
        'all_terminal_latency': distribution([row['elapsed_ms'] for row in samples]),
        'correct_latency': distribution([row['elapsed_ms'] for row in successes]),
        'outcomes': dict(Counter(str(row['result'].get('status', row['result'].get('error_type', 'validated'))) for row in samples)),
        'samples': samples}
