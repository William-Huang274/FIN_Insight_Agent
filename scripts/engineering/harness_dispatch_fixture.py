"""Opt-in real PostgreSQL + HTTP host for the ACP qualification fixture.

Credentials are supplied by the operator through environment, not CLI/output.
This uses synthetic authority and prices, never claims Java service acceptance.
The provisioner must already have created a dedicated qualification database.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
import secrets
import socket
import threading
import time
from uuid import uuid4

from fastapi import FastAPI
import uvicorn

from sec_agent.adapters.model_dispatch_store import ModelDispatchStore
from sec_agent.agent_runtime.harness_dispatch_host import HarnessDispatchHost, dispatch_router
from sec_agent.agent_runtime.harness_provider_transport import HarnessProviderTransport


@dataclass(frozen=True)
class FixturePrices:
    version: str = 'synthetic-no-paid-requests'
    model: str = 'fixture-model'
    currency: str = 'USD'
    input_miss: int = 1_000_000
    input_hit: int = 100_000
    output: int = 2_000_000


@contextmanager
def metered_fixture(output, upstream_port, protocol, accounting):
    worker = ModelDispatchStore(os.environ['FIN_HARNESS_FIXTURE_WORKER_DSN'])
    provisioner = ModelDispatchStore(os.environ['FIN_HARNESS_FIXTURE_PROVISIONER_DSN'])
    owner, budget = 'harness-fixture', str(uuid4())
    provisioner.create_budget(owner, budget, 'USD', 1_000_000, 0)
    grant = dict(execution_id=str(uuid4()), authorized_run_id=str(uuid4()), manifest_digest='sha256:'+'a'*64)
    basis = dict(node_role='lead', node_purpose='No-model ACP, tool, resume and compaction qualification',
        input_scale='Synthetic histories only', required_outputs=['tool observations and durable checkpoints'],
        schema_burden='ACP and MCP fixture', materiality_quality_risk='No real research evidence',
        comparable_run_evidence='Prior full ACP fixture', reasoning_profile='agentic_message_history_thinking_enabled',
        max_input_characters=1_000_000, max_output_tokens=2048, timeout_seconds=90,
        max_transport_attempts=1, retry_policy='none', truncation_stop_behavior='fail_closed_no_partial_promotion',
        input_ceiling_behavior='fail_before_transport')
    host = HarnessDispatchHost(store=worker, owner=owner, budget=budget,
        execution_id=grant['execution_id'], run_id=grant['authorized_run_id'],
        manifest_digest=grant['manifest_digest'], authority=lambda: dict(grant),
        prices=FixturePrices(), provider='fin-qwen' if protocol == 'qwen' else 'deepseek-official',
        basis=basis, reservation_micros=10_000, reservation_basis='Synthetic fixture bound; not a provider price',
        receipts=output / 'wire', wire_usage=lambda _: None)
    token = secrets.token_urlsafe(32)
    path = '/v1/chat/completions' if protocol == 'qwen' else '/v1/messages'
    transport = HarnessProviderTransport(host, protocol='qwen_chat' if protocol == 'qwen' else 'deepseek_messages',
        endpoint=f'http://127.0.0.1:{upstream_port}{path}', provider_headers={'Authorization':'Bearer fixture-only'},
        token=token, allow_loopback_fixture=True)
    host.wire_usage = transport.meter
    app = FastAPI()
    @app.middleware('http')
    async def log_calls(request, call_next):
        if request.url.path.startswith('/calls/'):
            accounting.append({'path': request.url.path, 'body': await request.json()})
        return await call_next(request)
    app.include_router(dispatch_router(host, token=token))
    app.include_router(transport.router())
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError('harness_fixture_host_not_ready')
        time.sleep(.05)
    try:
        yield port, token
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        sock.close()
        snapshot = worker.snapshot(owner, budget)
        (output / 'database-budget.json').write_text(json.dumps(snapshot, default=str, indent=2), encoding='utf8')
        (output / 'accounting.json').write_text(json.dumps(accounting, indent=2), encoding='utf8')
