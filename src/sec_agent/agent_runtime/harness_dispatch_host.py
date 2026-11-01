"""Internal HTTP accounting adapter for one Java-admitted harness execution.

No research loop, retries, session recovery, or compression scheduler. The host
composition supplies the existing Java admission callable and raw-wire meter;
neither model arguments nor normalized upstream chunks can grant authority or
declare paid usage. Not mounted in production until transport qualification.
"""
from dataclasses import asdict
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
from threading import Lock
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from sec_agent.adapters.model_dispatch_store import DispatchBlocked, amount
from .deepseek_structured_agents import TokenBudgetBasis


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(',', ':')).encode('utf8')


class HarnessDispatchHost:
    def __init__(self, *, store, owner, budget, execution_id, run_id, manifest_digest,
                 authority, prices, basis, provider, reservation_micros,
                 reservation_basis, receipts, wire_usage):
        self.store, self.owner, self.budget = store, owner, budget
        self.store.require_runtime_role()
        self.execution_id, self.run_id = str(UUID(execution_id)), str(UUID(run_id))
        self.scope = self.execution_id + ':' + self.run_id
        self.manifest_digest, self.authority = manifest_digest, authority
        # Reuse the maintained task budget contract, with per-run limits chosen
        # from the actual model capacity; no fixed call/compaction count here.
        self.basis = TokenBudgetBasis.model_validate_json(_bytes(basis)).model_dump(mode='json')
        self.prices, self.provider = prices, provider
        self.reservation = amount(reservation_micros, positive=True)
        if not reservation_basis:
            raise ValueError('reservation_basis_required')
        self.reservation_basis = reservation_basis
        self.receipts = Path(receipts).resolve()
        self.receipts.mkdir(parents=True, exist_ok=True)
        self.wire_usage = wire_usage
        self.lock = Lock()
        self._wire_pending = None

    def _key(self, request_id):
        return self.scope + ':' + str(UUID(request_id))

    def _persist(self, request_id, kind, value):
        """Immutable content-addressed receipts outside Git, before DB ack.

        Large original streams stay here; the existing DB stores a small ref.
        A failed write never authorizes a provider request or a completion.
        """
        blob = _bytes(value)
        digest = sha256(blob).hexdigest()
        path = self.receipts / (str(UUID(request_id)) + '.' + kind + '.' + digest + '.json')
        if path.exists():
            if path.read_bytes() != blob:
                raise DispatchBlocked('harness_receipt_content_mismatch')
        else:
            with path.open('xb') as stream:
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
        return {'path': str(path), 'sha256': digest, 'bytes': len(blob)}

    def reserve(self, request_id, request):
        key = self._key(request_id)
        with self.lock:
            # Use the maintained Java *run admission*, not a cached ACL boolean.
            grant = self.authority()
            if (grant.get('execution_id') != self.execution_id
                    or grant.get('authorized_run_id') != self.run_id
                    or grant.get('manifest_digest') != self.manifest_digest):
                raise DispatchBlocked('harness_java_run_binding_mismatch')
            if request.get('model') != self.prices.model or request.get('provider') != self.provider:
                raise DispatchBlocked('harness_model_price_binding_mismatch')
            if len(_bytes(request).decode('utf8')) > self.basis['max_input_characters']:
                raise DispatchBlocked('harness_request_exceeds_declared_input_basis')
            output_limit = self.basis['max_output_tokens']
            requested_output = request.get('maxTokens')
            if output_limit is not None and (type(requested_output) is not int
                                            or not 0 < requested_output <= output_limit):
                raise DispatchBlocked('harness_output_basis_mismatch')
            policy = {'harness_execution_scope': self.scope, 'token_budget': self.basis,
                      'price': asdict(self.prices), 'provider': self.provider,
                      'reservation_micros': self.reservation,
                      'reservation_basis': self.reservation_basis}
            saved = self._persist(request_id, 'request', request)
            fingerprint = sha256(_bytes({'request': saved['sha256'], 'policy': policy})).hexdigest()
            prior = self.store.reserve(self.owner, self.budget, key, fingerprint,
                self.reservation, {**policy, 'request_receipt': saved},
                currency=self.prices.currency, execution_scope=self.scope)
            # Upstream cannot replay by obtaining another provider grant. Saved
            # responses need explicit session restoration at the host boundary.
            if prior['status'] != 'dispatched':
                raise DispatchBlocked('harness_request_already_received_no_resend')
            self._wire_pending = (str(UUID(request_id)), request)
            return {'status': 'reserved', 'call_id': str(prior['call_id'])}

    def claim_wire(self, body):
        """Bind exactly one HTTP inference to this execution's admitted call.

        The profile points at an execution-private loopback proxy. Provider keys
        never enter the harness process. The existing store serializes calls;
        this exclusive receipt also prevents a provider SDK retry or host restart
        from forwarding the same reservation twice. No model-supplied call ID.
        """
        with self.lock:
            if self._wire_pending is None:
                raise DispatchBlocked('harness_wire_without_reservation')
            request_id, request = self._wire_pending
            grant = self.authority()
            if (grant.get('execution_id') != self.execution_id
                    or grant.get('authorized_run_id') != self.run_id
                    or grant.get('manifest_digest') != self.manifest_digest):
                raise DispatchBlocked('harness_java_run_binding_mismatch')
            row = self.store.lookup(self.owner, self.budget, self._key(request_id))
            if row is None or row['status'] != 'dispatched':
                raise DispatchBlocked('harness_wire_reservation_not_active')
            if (body.get('model') != request['model'] or body.get('stream') is not True
                    or body.get('max_tokens') != request.get('maxTokens')):
                self._persist(request_id, 'wire_rejected', {'reason': 'request_binding_mismatch', 'body': body})
                raise DispatchBlocked('harness_wire_request_binding_mismatch')
            # Provider serialization includes schemas and protocol wrappers.
            if len(_bytes(body).decode('utf8')) > self.basis['max_input_characters']:
                raise DispatchBlocked('harness_wire_exceeds_declared_input_basis')
            saved = self._persist(request_id, 'wire_request', body)
            claim = self.receipts / (request_id + '.wire-claimed.json')
            try:
                with claim.open('xb') as stream:
                    stream.write(_bytes(saved))
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                raise DispatchBlocked('harness_wire_already_dispatched_no_resend') from None
            self._wire_pending = None
            return request_id

    def settle(self, request_id, chunks, terminal=None, *, unknown=False):
        key = self._key(request_id)
        with self.lock:
            row = self.store.lookup(self.owner, self.budget, key)
            if row is None:
                raise DispatchBlocked('harness_request_not_reserved')
            payload = {'chunks': chunks, 'terminal': terminal, 'unknown': unknown}
            payload_digest = sha256(_bytes(payload)).hexdigest()
            if row['status'] == 'received':
                response = row['response']
                if response.get('payload_digest') != payload_digest:
                    raise DispatchBlocked('harness_settlement_payload_changed')
                return {'status': 'saved', 'stopRequired': response['stop_required']}
            if row['status'] != 'dispatched':
                raise DispatchBlocked('harness_settlement_state_conflict')
            saved = self._persist(request_id, 'response', payload)
            # Only the trusted provider-wire observer supplies usage. Missing
            # meter != zero. ACP occupancy and normalized default zeros ignored.
            meter = self.wire_usage(request_id)
            usage = meter.reported() if meter is not None else None
            actual = usage.cost_micros(self.prices) if usage else None
            finish = chunks[-1] if chunks else {}
            finished = (finish.get('type') == 'finish'
                        and finish.get('reason', {}).get('kind') == terminal)
            wire_success = meter is not None and meter.finish_reason in {'stop', 'tool_calls', 'end_turn', 'tool_use'}
            stop = (unknown or not finished or terminal not in {'stop', 'tool-calls'}
                    or not wire_success or actual is None)
            response = {'receipt': saved, 'payload_digest': payload_digest,
                        'wire_usage': meter.receipt() if meter is not None else None,
                        'stop_required': stop}
            # A received partial is not an accepted artifact. NULL actual keeps
            # its financial hold; the durable stop flag survives host restart.
            self.store.received(self.owner, self.budget, key, response, actual)
            return {'status': 'saved', 'stopRequired': stop}


class _Reserve(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str
    request: dict


class _Settlement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str
    chunks: list[dict]
    terminal: str
    stopRequired: bool


class _Unknown(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requestId: str
    chunks: list[dict]


def dispatch_router(host, *, token):
    """Mount only on the per-execution loopback service, never on browser BFF."""
    if len(token.encode()) < 32:
        raise ValueError('harness_dispatch_token_requires_32_bytes')
    router = APIRouter()

    def invoke(authorization, method, *args, **kwargs):
        if not hmac.compare_digest(authorization or '', 'Bearer ' + token):
            raise HTTPException(401, 'harness_dispatch_unauthorized')
        try:
            return method(*args, **kwargs)
        except DispatchBlocked as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError:
            raise HTTPException(422, 'harness_dispatch_invalid_payload') from None

    @router.post('/calls/reserve')
    def reserve(body: _Reserve, authorization: str | None = Header(default=None)):
        return invoke(authorization, host.reserve, body.requestId, body.request)

    @router.post('/calls/settle')
    def settle(body: _Settlement, authorization: str | None = Header(default=None)):
        return invoke(authorization, host.settle, body.requestId, body.chunks, body.terminal)

    @router.post('/calls/unknown')
    def unknown(body: _Unknown, authorization: str | None = Header(default=None)):
        return invoke(authorization, host.settle, body.requestId, body.chunks, unknown=True)

    return router
