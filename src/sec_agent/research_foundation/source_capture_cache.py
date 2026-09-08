"""Scoped public-source reuse over DiskCache, not an evidence or lineage store.

Only successful captured text is cached. Every replay receives the current run
binding while retaining the original capture time, text digest and limitations.
The caller supplies a trusted namespace; a URL or model argument is not access
authority. Durable evidence continues to belong to the existing run artifacts.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter
from uuid import UUID

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from .external_sources import CaptureReceipt, ExternalCaptureRequest, PublicURLGuard


class ScopedSourceCaptureCache:
    def __init__(self, *, root: Path, thread_id: str, capture,
                 lifetime_seconds: int = 3600, guard=None):
        from diskcache import Cache
        # Thread identity is assigned by Agent Server. No model-supplied path.
        namespace = str(UUID(thread_id))
        if not 1 <= lifetime_seconds <= 86400:
            raise ValueError("source_cache_lifetime_invalid")
        self.root = root.resolve() / namespace
        self.capture_service, self.lifetime = capture, lifetime_seconds
        self.guard = guard or PublicURLGuard()
        # Strings/bytes only: DiskCache never needs to unpickle source content.
        with Cache(str(self.root), size_limit=64 * 1024 * 1024) as cache:
            cache.stats(enable=True)

    def _read(self, key):
        from diskcache import Cache
        with Cache(str(self.root)) as cache:
            return cache.get(key)

    def _write(self, key, receipt):
        from diskcache import Cache
        with Cache(str(self.root)) as cache:
            cache.set(key, receipt.model_dump_json(), expire=self.lifetime)

    async def capture(self, request: ExternalCaptureRequest, *, force_refresh=False):
        started = perf_counter()
        # Validate on hits too. Cache reuse must not bypass URL/DNS restrictions.
        await asyncio.to_thread(self.guard.validate, request.url)
        key = canonical_digest({"url": request.url, "render": request.render_policy,
            "max_characters": request.max_characters, "minimum": request.minimum_useful_characters,
            "snapshot": request.run_scope.data_snapshot_id,
            "as_of": request.discovery_receipt.research_as_of, "cache_contract": 1})
        saved = None if force_refresh else await asyncio.to_thread(self._read, key)
        if saved is not None:
            original = CaptureReceipt.model_validate_json(saved)
            if original.status != "captured" or original.requested_url != request.url:
                raise ValueError("cached_capture_binding_invalid")
            await asyncio.to_thread(self.guard.validate, original.final_url)
            body = original.model_dump(mode="json", exclude={"receipt_digest"})
            receipt = request.discovery_receipt
            body.update(branch_id=request.branch_id, case_id=request.run_scope.case_id,
                execution_attempt_id=request.run_scope.execution_attempt_id, purpose=receipt.purpose,
                research_as_of=receipt.research_as_of, data_snapshot_id=receipt.data_snapshot_id,
                method_sha256=receipt.method_sha256, run_scope_digest=receipt.run_scope_digest,
                discovery_receipt_digest=receipt.receipt_digest, candidate_id=request.candidate_id,
                provider_id=request.candidate.provider_id, query_digest=receipt.query_digest,
                capture_method="cached_public_source_replay", attempts=[{
                    "method": "cached_public_source_replay", "status": "ok",
                    "extracted_characters": original.extracted_characters, "failure_code": None}],
                elapsed_ms=round((perf_counter() - started) * 1000))
            return CaptureReceipt(**body, receipt_digest=canonical_digest(body))
        result = await self.capture_service.capture(request)
        if result.status == "captured":
            await asyncio.to_thread(self._write, key, result)
        return result
