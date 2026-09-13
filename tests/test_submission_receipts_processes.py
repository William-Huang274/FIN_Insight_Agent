"""Real OS-process qualification of the existing local BFF receipt boundary.

Synthetic dispatch only: no provider, Agent Server, or production records.
SQLite remains the owner of concurrency; this does not qualify multiple hosts.
"""
import asyncio
import multiprocessing
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.workbench.backend.authentication import _request_owner
from apps.workbench.backend.submission_receipts import SubmissionReceipts


def _request_process(root, key, owner, payload, result, entered=None,
                     release=None, saved=None):
    app = FastAPI()

    @app.post('/api/v1/dispatch')
    async def dispatch():
        # Record the synthetic external effect before a possible process death.
        effect = Path(root) / f'effect-{os.getpid()}.txt'
        with effect.open('x', encoding='utf-8') as stream:
            stream.write(owner)
            stream.flush()
            os.fsync(stream.fileno())
        if entered is not None:
            entered.set()
            assert await asyncio.to_thread(release.wait, 20), 'dispatch_release_timeout'
        return {'run_id': 'synthetic-native-id'}

    app.add_middleware(SubmissionReceipts, directory=Path(root) / 'receipts')

    async def ingress(scope, receive, send):
        # Emulate verified identity without contacting an identity server.
        token = _request_owner.set(owner)
        try:
            async def socket_send(message):
                if saved is not None and message['type'] == 'http.response.start':
                    # SubmissionReceipts persists BEFORE forwarding to the socket.
                    saved.set()
                    assert await asyncio.to_thread(release.wait, 20), 'socket_release_timeout'
                await send(message)
            await app(scope, receive, socket_send)
        finally:
            _request_owner.reset(token)

    with TestClient(ingress) as client:
        response = client.post('/api/v1/dispatch', json=payload, headers={
            'Idempotency-Key': key, 'X-Workbench-Request': '1',
        })
        result.put((os.getpid(), response.status_code,
                    response.headers.get('Idempotent-Replayed'), response.json()))


def _start(ctx, root, key, *, owner='alice', payload=None, **controls):
    result = ctx.Queue()
    process = ctx.Process(target=_request_process, args=(
        str(root), key, owner, payload or {}, result,
    ), kwargs=controls)
    process.start()
    return process, result


def _finish(worker):
    process, result = worker
    process.join(20)
    assert not process.is_alive(), 'request_process_timeout'
    assert process.exitcode == 0
    value = result.get(timeout=5)
    assert value[0] == process.pid
    return value


def _cleanup(workers):
    for process, result in workers:
        if process.is_alive():
            process.terminate()
        process.join(5)
        result.close()
        result.join_thread()


def test_separate_processes_reject_duplicate_and_replay_per_owner(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    entered, release = ctx.Event(), ctx.Event()
    key, workers = str(uuid4()), []
    try:
        first = _start(ctx, tmp_path, key, entered=entered, release=release)
        workers.append(first)
        assert entered.wait(15), 'dispatch_not_reached'
        second = _start(ctx, tmp_path, key)
        workers.append(second)
        duplicate = _finish(second)
        assert duplicate[1] == 409
        assert duplicate[0] != first[0].pid
        assert len(list(tmp_path.glob('effect-*'))) == 1
        release.set()
        assert _finish(first)[1] == 200
        for owner, payload, status, replay in [
            ('alice', {}, 200, 'true'),
            ('alice', {'changed': True}, 422, None),
            ('bob', {}, 200, None),
        ]:
            worker = _start(ctx, tmp_path, key, owner=owner, payload=payload)
            workers.append(worker)
            assert _finish(worker)[1:3] == (status, replay)
        effects = [p.read_text(encoding='utf-8') for p in tmp_path.glob('effect-*')]
        assert sorted(effects) == ['alice', 'bob']
    finally:
        release.set()
        _cleanup(workers)


def test_process_death_after_dispatch_keeps_unknown_without_retry(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    entered, release = ctx.Event(), ctx.Event()
    key, workers = str(uuid4()), []
    try:
        first = _start(ctx, tmp_path, key, entered=entered, release=release)
        workers.append(first)
        assert entered.wait(15), 'dispatch_not_reached'
        first[0].terminate()
        first[0].join(5)
        assert first[0].exitcode not in (None, 0)
        successor = _start(ctx, tmp_path, key)
        workers.append(successor)
        assert _finish(successor)[1] == 409
        assert len(list(tmp_path.glob('effect-*'))) == 1
    finally:
        release.set()
        _cleanup(workers)


def test_process_death_after_save_before_socket_delivery_replays(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    saved, release = ctx.Event(), ctx.Event()
    key, workers = str(uuid4()), []
    try:
        first = _start(ctx, tmp_path, key, saved=saved, release=release)
        workers.append(first)
        assert saved.wait(15), 'persisted_response_not_reached'
        first[0].terminate()
        first[0].join(5)
        assert first[0].exitcode not in (None, 0)
        successor = _start(ctx, tmp_path, key)
        workers.append(successor)
        replay = _finish(successor)
        assert replay[1:3] == (200, 'true')
        assert replay[3] == {'run_id': 'synthetic-native-id'}
        assert len(list(tmp_path.glob('effect-*'))) == 1
    finally:
        release.set()
        _cleanup(workers)
