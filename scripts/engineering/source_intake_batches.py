"""Serial, resumable per-source acceptance; never a substitute for unified retrieval.

No model calls. Plans reference existing immutable inputs without copying corpora.
Each attempt uses the existing real-service qualification and its own services.
"""
import argparse
from hashlib import file_digest, sha256
import json
import ipaddress
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


class WorkerCleanupPending(RuntimeError):
    """Keep the runner lock when a worker has not confirmed shutdown."""


def digest(path):
    with Path(path).open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    temporary.replace(path)


def plan_batches(root, *, max_sources=32, max_input_bytes=16 * 2**20):
    root = Path(root).resolve()
    intake = json.loads((root / 'result.json').read_text(encoding='utf8'))
    if intake['status'] != 'verified' or max_sources < 1 or max_input_bytes < 1:
        raise ValueError('invalid_batch_plan_input')
    ids = [row['source_id'] for row in intake['sources']]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('duplicate_or_empty_intake')
    batches, current, size = [], [], 0
    for row in intake['sources']:
        folder = (root / row['directory']).resolve()
        if not folder.is_relative_to(root):
            raise ValueError('source_path_outside_intake')
        source_size = sum((folder / name).stat().st_size for name in row['files'])
        if current and (len(current) >= max_sources or size + source_size > max_input_bytes):
            batches.append(current)
            current, size = [], 0
        current.append(row['source_id'])
        size += source_size
    if current:
        batches.append(current)
    return {'schema': 'source-intake-batches.v1', 'intake_root': str(root),
            'intake_sha256': digest(root / 'result.json'), 'source_ids': ids,
            'candidate_chunks': sum(row['chunks'] for row in intake['sources']),
            'source_chunks': {row['source_id']: row['chunks'] for row in intake['sources']},
            'max_sources': max_sources, 'max_input_bytes': max_input_bytes,
            'byte_limit_is_input_size_not_rss': True,
            'oversized_source_policy': 'single source, never truncate',
            'batches': batches, 'unified_scope_acceptance_required': True}


def select_batch(plan, intake, number, intake_sha256):
    ids = [row['source_id'] for row in intake['sources']]
    flattened = [sid for batch in plan['batches'] for sid in batch]
    if (plan['schema'] != 'source-intake-batches.v1' or intake['status'] != 'verified'
            or plan['intake_sha256'] != intake_sha256 or plan['source_ids'] != ids
            or plan['source_chunks'] != {row['source_id']: row['chunks'] for row in intake['sources']}
            or flattened != ids or len(set(ids)) != len(ids)
            or any(not batch for batch in plan['batches'])
            or not 0 <= number < len(plan['batches'])):
        raise ValueError('batch_plan_scope_mismatch')
    selected = set(plan['batches'][number])
    return [row for row in intake['sources'] if row['source_id'] in selected]


def verify_inputs(root, intake):
    root = Path(root).resolve()
    checked = 0
    for row in intake['sources']:
        for name, expected in row['files'].items():
            path = (root / row['directory'] / name).resolve()
            if not path.is_relative_to(root) or digest(path) != expected:
                raise ValueError('intake_file_changed')
            checked += 1
    return checked


def validate_result(plan, number, result, binding):
    expected = plan['batches'][number]
    expected_chunks = sum(plan['source_chunks'][sid] for sid in expected)
    ids = lambda field: [row['source_id'] for row in result[field]]
    if (result.get('status') != 'passed' or result.get('batch_binding') != binding
            or ids('sources') != expected or ids('captures') != expected
            or result.get('date_denials') or result.get('global_probe')
            or result.get('corpus_wide_retrieval')
            or result.get('full_intake_sources') != len(plan['source_ids'])
            or result.get('candidate_chunks') != expected_chunks
            or any(row.get('candidate_chunks') != plan['source_chunks'][row['source_id']]
                   for row in result['sources'])
            or result.get('provider_calls') != 0 or result.get('research_runs') != 0
            or result.get('per_source_filtered_readback_count') != len(expected)
            or not result.get('revoked_cache_and_readback_denied')
            or not all(row.get('cache_hit') and row.get('provider_calls') == 0
                       for row in result['sources'])):
        raise ValueError('batch_result_incomplete_or_different_scope')


def baseline():
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    if dirty.strip():
        raise ValueError('batch_execution_requires_clean_committed_worktree')
    jar = Path(os.environ['FINSIGHT_INTAKE_TEST_JAR'])
    configuration = {key: os.environ.get(key) for key in (
        'FIN_COMPLETE_SOURCE_QUESTIONS', 'FIN_COMPLETE_SOURCE_LIBRARY', 'FIN_COMPLETE_SOURCE_QUERY_CACHE',
        'FIN_PROBE_IMAGE', 'FINSIGHT_LIBRARY_NODE_CATALOG', 'FINSIGHT_LIBRARY_RECOVERY_CATALOG',
        'FINSIGHT_LIBRARY_NODE_SHA256', 'FINSIGHT_LIBRARY_RECOVERY_SHA256')}
    file_hashes = {key: digest(value) for key, value in configuration.items()
                   if value and key in ('FIN_COMPLETE_SOURCE_QUESTIONS',
                       'FINSIGHT_LIBRARY_NODE_CATALOG', 'FINSIGHT_LIBRARY_RECOVERY_CATALOG')}
    return {'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'jar_sha256': digest(jar), 'configuration': configuration, 'configuration_files': file_hashes}


def unused_subnet(docker):
    ids = subprocess.check_output([docker, 'network', 'ls', '-q'], text=True, timeout=20).split()
    rows = json.loads(subprocess.check_output([docker, 'network', 'inspect', *ids],
                                             text=True, timeout=30)) if ids else []
    occupied = [ipaddress.ip_network(config['Subnet']) for row in rows
                for config in (row.get('IPAM', {}).get('Config') or []) if config.get('Subnet')]
    for number in range(1, 255):
        candidate = ipaddress.ip_network(f'10.253.{number}.0/24')
        if not any(network.version == 4 and candidate.overlaps(network) for network in occupied):
            return str(candidate)
    raise ValueError('no_unused_qualification_subnet')


def worker(attempt):
    # Run the guardian in the pytest process so KeyboardInterrupt unwinds the
    # harness finally block. Never terminate a shared process by name.
    import _thread
    import threading
    import time
    import psutil
    stop = threading.Event()
    state = {'status': 'running', 'floor_bytes': 800 * 2**20, 'samples': []}
    record = Path(str(attempt) + '-memory.json')

    def watch():
        low = 0
        while not stop.wait(5):
            if Path(str(attempt) + '.stop').exists():
                state['status'] = 'requested_stop'
                write(record, state)
                _thread.interrupt_main()
                return
            available = psutil.virtual_memory().available
            state['samples'].append({'time': time.time(), 'available_bytes': available,
                                     'driver_rss_bytes': psutil.Process().memory_info().rss})
            write(record, state)
            low = low + 1 if available < state['floor_bytes'] else 0
            if low >= 2:
                state['status'] = 'memory_floor_interrupt'
                write(record, state)
                _thread.interrupt_main()
                return
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
    try:
        import pytest
        code = int(pytest.main(['-q', 'tests/integration/test_organization_complete_source_stack.py']))
        state['exit_code'] = code
        if state['status'] == 'running':
            state['status'] = 'completed' if code == 0 else 'failed'
        return code
    finally:
        stop.set()
        thread.join(timeout=6)
        write(record, state)


def run(plan_path, output, *, retry_failed=False, min_available_gib=4):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A crashed runner leaves its lock for explicit inspection, never stealing
    # another window's running acceptance or automatically deleting its files.
    lock = output / 'runner.lock'
    with lock.open('x', encoding='utf8') as handle:
        handle.write(str(os.getpid()))
    release_lock = True
    try:
        return _run(plan_path, output, retry_failed=retry_failed, min_available_gib=min_available_gib)
    except WorkerCleanupPending:
        release_lock = False
        raise
    finally:
        if release_lock:
            lock.unlink()


def _run(plan_path, output, *, retry_failed=False, min_available_gib=4):
    import psutil
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    if min_available_gib < 2:
        raise ValueError('startup_headroom_must_be_at_least_2_gib')
    plan = json.loads(plan_path.read_text(encoding='utf8'))
    intake_path = Path(plan['intake_root']) / 'result.json'
    intake = json.loads(intake_path.read_text(encoding='utf8'))
    select_batch(plan, intake, 0, digest(intake_path))
    output.mkdir(parents=True, exist_ok=True)
    execution_baseline = baseline()
    identity = {'plan_sha256': digest(plan_path), **execution_baseline}
    binding_file = output / 'baseline.json'
    if binding_file.exists():
        if json.loads(binding_file.read_text(encoding='utf8')) != identity:
            raise ValueError('resume_baseline_changed')
    else:
        write(binding_file, identity)
    checked = verify_inputs(plan['intake_root'], intake)
    write(output/'input-check.json', {'status': 'passed', 'files_checked': checked,
                                    'sources_checked': len(intake['sources']), **identity})
    passed = []
    def progress(status, **extra):
        write(output / 'progress.json', {'status': status, 'passed_batches': passed,
              'total_batches': len(plan['batches']), 'total_sources': len(plan['source_ids']),
              'verified_sources': sum(len(plan['batches'][i]) for i in passed),
              'unified_scope_acceptance': 'pending_separate_run', 'S2_passed': False, **extra})
    for number in range(len(plan['batches'])):
        binding = {**identity, 'batch_number': number, 'intake_sha256': plan['intake_sha256']}
        receipt = output / f'batch-{number:04d}-receipt.json'
        if receipt.exists():
            saved = json.loads(receipt.read_text(encoding='utf8'))
            result_path = output / saved['result_path']
            if not result_path.resolve().is_relative_to(output) or digest(result_path) != saved['result_sha256']:
                raise ValueError('batch_receipt_changed')
            validate_result(plan, number, json.loads(result_path.read_text(encoding='utf8')), binding)
            passed.append(number)
            continue
        attempts = list(output.glob(f'batch-{number:04d}-r*.log'))
        if attempts and not retry_failed:
            progress('failed_attempt_requires_explicit_retry', next_batch=number)
            return 2
        for sample in range(3):
            available = psutil.virtual_memory().available
            if available < min_available_gib * 2**30:
                progress('paused_memory', next_batch=number, available_bytes=available,
                         minimum_start_bytes=int(min_available_gib * 2**30))
                return 2
            if sample < 2:
                time.sleep(5)
        if baseline() != execution_baseline:
            raise ValueError('execution_baseline_changed')
        attempt = output / f'batch-{number:04d}-r{len(attempts)+1:02d}'
        env = os.environ.copy()
        env.update(FIN_COMPLETE_SOURCE_INTAKE=plan['intake_root'],
                   FIN_COMPLETE_SOURCE_BATCH_PLAN=str(plan_path),
                   FIN_COMPLETE_SOURCE_BATCH_NUMBER=str(number),
                   FIN_COMPLETE_SOURCE_BATCH_BINDING=json.dumps(binding),
                   FIN_COMPLETE_SOURCE_STORAGE_PROBE='1', FIN_COMPLETE_SOURCE_UNIFIED_SCOPE='0',
                   FIN_COMPLETE_SOURCE_GLOBAL_PROBE='0', FIN_NATIVE_ATTEMPT_DIR=str(attempt),
                   OPENBLAS_NUM_THREADS='1', PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT/'src')]))
        env['FIN_PROBE_SUBNET'] = unused_subnet(os.environ['FINSIGHT_TEST_DOCKER'])
        progress('running', next_batch=number)
        with Path(str(attempt)+'.log').open('x', encoding='utf8') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker',
                                        '--attempt', str(attempt)], cwd=ROOT, env=env, stdout=log,
                                        stderr=subprocess.STDOUT)
            try:
                code = process.wait()
            except KeyboardInterrupt:
                Path(str(attempt)+'.stop').touch()
                # The worker owns service cleanup. Do not kill it before finally.
                try:
                    code = process.wait(timeout=240)
                except subprocess.TimeoutExpired as exc:
                    progress('worker_cleanup_pending', next_batch=number, worker_pid=process.pid)
                    raise WorkerCleanupPending('inspect_own_worker_before_resuming') from exc
                progress('interrupted', next_batch=number, exit_code=code)
                return 130
        if code:
            progress('failed', next_batch=number, exit_code=code)
            return code
        result_path = attempt / 'complete-source-result.json'
        validate_result(plan, number, json.loads(result_path.read_text(encoding='utf8')), binding)
        write(receipt, {'result_path': str(result_path.relative_to(output)), 'result_sha256': digest(result_path)})
        passed.append(number)
        progress('running')
    progress('per_source_passed_unified_scope_pending')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('plan')
    create.add_argument('--intake', required=True)
    create.add_argument('--output', required=True)
    create.add_argument('--max-sources', type=int, default=32)
    create.add_argument('--max-input-mib', type=int, default=16)
    execute = sub.add_parser('run')
    execute.add_argument('--plan', required=True)
    execute.add_argument('--output', required=True)
    execute.add_argument('--retry-failed', action='store_true')
    execute.add_argument('--min-available-gib', type=float, default=4)
    child = sub.add_parser('worker')
    child.add_argument('--attempt', required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        plan = plan_batches(args.intake, max_sources=args.max_sources,
                            max_input_bytes=args.max_input_mib * 2**20)
        with Path(args.output).open('x', encoding='utf8') as handle:
            json.dump(plan, handle, ensure_ascii=False, indent=2)
        return 0
    if args.command == 'worker':
        return worker(args.attempt)
    return run(args.plan, args.output, retry_failed=args.retry_failed, min_available_gib=args.min_available_gib)


if __name__ == '__main__':
    raise SystemExit(main())
