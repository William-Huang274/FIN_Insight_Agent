from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from ingestion.official_source_capture import (
    CAPTURE_PLAN_BROWSER_SCHEMA_VERSION,
    CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION,
    TransportFetcher,
    capture_plan,
)
from ingestion.source_intake import (
    SourceIntakeError,
    SourceIntakePolicy,
    SourceIntakeRoute,
    SourceIntakeStore,
    source_network_path_snapshot,
)
from sec_agent.runtime_bridge.paths import RuntimePathRegistry


NetworkSnapshotter = Callable[[str], Mapping[str, Any]]


class SourceIntakeService:
    """Workbench application service for bounded source acquisition and upload."""

    def __init__(
        self,
        *,
        policy: SourceIntakePolicy,
        private_root: str | Path,
        transport_fetchers: Mapping[str, TransportFetcher] | None = None,
        network_snapshotter: NetworkSnapshotter = source_network_path_snapshot,
    ) -> None:
        self.store = SourceIntakeStore(private_root, policy)
        self.transport_fetchers = dict(transport_fetchers or {})
        self.network_snapshotter = network_snapshotter

    @classmethod
    def from_runtime_paths(
        cls,
        repository_root: str | Path,
        runtime_paths: RuntimePathRegistry,
    ) -> "SourceIntakeService":
        root = Path(repository_root).resolve()
        policy = SourceIntakePolicy.from_path(
            root
            / "configs"
            / "retrieval"
            / "fin_ia_0_1_3_s1d_source_intake_policy_v1_0.json"
        )
        return cls(
            policy=policy,
            private_root=runtime_paths.workbench_private_root / "source_intake",
        )

    def routes(self) -> list[dict[str, Any]]:
        return self.store.routes()

    def attempts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.list_attempts(limit=limit)

    def upload(
        self,
        *,
        route_id: str,
        body: bytes,
        declared_content_type: str,
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        route = self.store.route(route_id)
        if not route.operator_upload_enabled:
            raise SourceIntakeError("source_intake_operator_upload_forbidden")
        return self.store.ingest_pdf_bytes(
            route_id=route_id,
            attempt_id=attempt_id or _new_attempt_id("upload"),
            body=body,
            acquisition_method="operator_upload",
            adapter_id="operator_upload_v1",
            declared_content_type=declared_content_type,
        )

    def acquire_automatic(
        self,
        *,
        route_id: str,
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        route = self.store.route(route_id)
        adapter = route.automatic_adapter
        if adapter.get("enabled") is not True:
            raise SourceIntakeError("source_intake_automatic_adapter_forbidden")
        resolved_attempt_id = attempt_id or _new_attempt_id("auto")
        self.store.assert_attempt_available(resolved_attempt_id)
        adapter_id = str(adapter["adapter_id"])
        transport = str(adapter.get("transport") or "requests")
        network_path = dict(self.network_snapshotter(route.source_url))
        plan = _capture_plan_for_route(route)
        transport_root = self.store.root / "automatic_transport"
        result = capture_plan(
            plan,
            output_root=transport_root,
            attempt_id=resolved_attempt_id,
            transport_fetchers=self.transport_fetchers,
        )
        row = result["sources"][0]
        transport_summary = _transport_summary(
            row,
            transport_root=transport_root,
            attempt_id=resolved_attempt_id,
            adapter_id=adapter_id,
            transport=transport,
        )
        if row["status"] != "captured":
            return self.store.record_automatic_failure(
                route_id=route_id,
                attempt_id=resolved_attempt_id,
                adapter_id=adapter_id,
                failure_code=str(row.get("failure_code") or "source_capture_failed"),
                transport=transport_summary,
                network_path=network_path,
            )
        response_capture = _load_capture(row["response_capture"])
        body = base64.b64decode(str(response_capture["body_base64"]), validate=True)
        content_type = str(row.get("content_type") or "application/octet-stream")
        return self.store.ingest_pdf_bytes(
            route_id=route_id,
            attempt_id=resolved_attempt_id,
            body=body,
            acquisition_method="automatic_adapter",
            adapter_id=adapter_id,
            declared_content_type=content_type,
            transport=transport_summary,
            network_path=network_path,
        )

    def route_byte_ceiling(self, route_id: str) -> int:
        return self.store.route(route_id).byte_ceiling


def _capture_plan_for_route(route: SourceIntakeRoute) -> dict[str, Any]:
    adapter = route.automatic_adapter
    transport = str(adapter.get("transport") or "requests")
    browser = transport == "playwright_browser_download"
    source: dict[str, Any] = {
        "case_key": route.case_key,
        "route_id": route.route_id,
        "url": route.source_url,
        "allowed_hosts": list(route.allowed_hosts),
        "expected_content_types": list(route.expected_content_types),
        "transport": transport,
        "max_transport_retries": 0,
        "timeout_seconds": int(adapter["timeout_seconds"]),
        "byte_ceiling": route.byte_ceiling,
    }
    if browser:
        source.update(
            {
                "discovery_url": route.discovery_url,
                "expected_download_url": route.source_url,
                "link_selector": str(adapter.get("link_selector") or ""),
                "browser_channel": str(adapter.get("browser_channel") or "msedge"),
            }
        )
    return {
        "schema_version": (
            CAPTURE_PLAN_BROWSER_SCHEMA_VERSION
            if browser
            else CAPTURE_PLAN_SUCCESSOR_SCHEMA_VERSION
        ),
        "status": "s1d_official_source_capture_plan",
        "policy": {
            "capture_before_parse": True,
            "https_only": True,
            "credentials_forbidden": True,
            "bounded_addendum_not_general_crawler": True,
            "source_body_is_not_evidence_until_gate": True,
            "zero_retry": True,
        },
        "sources": [source],
    }


def _transport_summary(
    row: Mapping[str, Any],
    *,
    transport_root: Path,
    attempt_id: str,
    adapter_id: str,
    transport: str,
) -> dict[str, Any]:
    response_capture = _load_capture(row.get("response_capture"))
    status_code = (
        int(response_capture.get("status_code"))
        if response_capture.get("status_code") is not None
        else None
    )
    failure_code = str(row.get("failure_code") or "") or None
    return {
        "adapter_id": adapter_id,
        "transport": transport,
        "attempts": int(
            row.get("transport_attempts")
            or row.get("transport_attempts_upper_bound")
            or 1
        ),
        "http_status": status_code,
        "failure_code": failure_code,
        "failure_category": _failure_category(failure_code, status_code),
        "transport_result_ref": (
            Path("automatic_transport") / attempt_id / "result.json"
        ).as_posix(),
        "raw_transport_capture_private": True,
        "credentials_persisted": False,
    }


def _load_capture(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    path = Path(str(value.get("object_ref") or ""))
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _failure_category(failure_code: str | None, status_code: int | None) -> str | None:
    if status_code in {401, 403}:
        return "access_control_or_origin_policy"
    if status_code == 429:
        return "rate_limited"
    if status_code is not None and status_code >= 500:
        return "origin_or_upstream_failure"
    value = str(failure_code or "")
    if "timeout" in value:
        return "transport_timeout"
    if "tls" in value or "ssl" in value:
        return "tls_failure"
    if "proxy" in value:
        return "proxy_path_failure"
    if "response_stream" in value:
        return "response_stream_failure"
    if "redirect" in value:
        return "redirect_failure"
    if "invalid_url" in value:
        return "request_policy_failure"
    if "connection" in value or "transport" in value:
        return "connection_failure"
    if value:
        return "capture_policy_failure"
    return None


def _new_attempt_id(prefix: str) -> str:
    return f"source-{prefix}-{uuid4().hex[:24]}"


__all__ = ["SourceIntakeService"]
