from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
import re
import socket
import subprocess
from typing import Any, Mapping
from urllib.parse import urlparse

from pypdf import PdfReader
import requests


SOURCE_INTAKE_POLICY_SCHEMA_VERSION = "fin_ia_source_intake_policy_v1_0"
SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION = "fin_ia_source_intake_attempt_v1_0"
NETWORK_PATH_SCHEMA_VERSION = "fin_ia_source_network_path_snapshot_v1_0"
_ATTEMPT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_ROUTE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")


class SourceIntakeError(RuntimeError):
    """Raised when source bytes or identity cannot enter the private intake store."""


@dataclass(frozen=True)
class SourceIntakeRoute:
    route_id: str
    case_key: str
    issuer_name: str
    document_type: str
    title: str
    publication_date: str
    source_url: str
    discovery_url: str | None
    allowed_hosts: tuple[str, ...]
    expected_content_types: tuple[str, ...]
    byte_ceiling: int
    automatic_adapter: Mapping[str, Any]
    operator_upload_enabled: bool

    def public_projection(self) -> dict[str, Any]:
        automatic_enabled = bool(self.automatic_adapter.get("enabled"))
        return {
            "route_id": self.route_id,
            "case_key": self.case_key,
            "issuer_name": self.issuer_name,
            "document_type": self.document_type,
            "title": self.title,
            "publication_date": self.publication_date,
            "source_url": self.source_url,
            "discovery_url": self.discovery_url,
            "allowed_hosts": list(self.allowed_hosts),
            "expected_content_types": list(self.expected_content_types),
            "byte_ceiling": self.byte_ceiling,
            "automatic_enabled": automatic_enabled,
            "automatic_adapter_id": (
                str(self.automatic_adapter.get("adapter_id") or "")
                if automatic_enabled
                else None
            ),
            "operator_upload_enabled": self.operator_upload_enabled,
            "promotion_status": "source_only_not_evidence",
        }


@dataclass(frozen=True)
class SourceIntakePolicy:
    routes: Mapping[str, SourceIntakeRoute]
    policy_id: str

    @classmethod
    def from_path(cls, path: str | Path) -> "SourceIntakePolicy":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_mapping(payload)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SourceIntakePolicy":
        if payload.get("schema_version") != SOURCE_INTAKE_POLICY_SCHEMA_VERSION:
            raise SourceIntakeError("source_intake_policy_schema_invalid")
        if payload.get("status") != "active_bounded_source_intake_policy":
            raise SourceIntakeError("source_intake_policy_status_invalid")
        raw_routes = payload.get("routes")
        if not isinstance(raw_routes, list) or not raw_routes:
            raise SourceIntakeError("source_intake_policy_routes_invalid")
        routes: dict[str, SourceIntakeRoute] = {}
        for raw in raw_routes:
            route = _validate_route(raw)
            if route.route_id in routes:
                raise SourceIntakeError("source_intake_policy_route_duplicate")
            routes[route.route_id] = route
        return cls(
            routes=routes,
            policy_id=str(payload.get("policy_id") or "").strip(),
        )

    def require_route(self, route_id: str) -> SourceIntakeRoute:
        route = self.routes.get(route_id)
        if route is None:
            raise SourceIntakeError("source_intake_route_not_found")
        return route


class SourceIntakeStore:
    """Private immutable raw-source intake shared by all acquisition drivers."""

    def __init__(self, root: str | Path, policy: SourceIntakePolicy):
        self.root = Path(root).resolve()
        self.policy = policy

    def assert_attempt_available(self, attempt_id: str) -> None:
        _validate_attempt_id(attempt_id)
        if self._attempt_path(attempt_id).exists():
            raise SourceIntakeError("source_intake_attempt_already_exists")

    def routes(self) -> list[dict[str, Any]]:
        return [
            self.policy.routes[key].public_projection()
            for key in sorted(self.policy.routes)
        ]

    def route(self, route_id: str) -> SourceIntakeRoute:
        return self.policy.require_route(route_id)

    def list_attempts(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise SourceIntakeError("source_intake_attempt_limit_invalid")
        root = self.root / "attempts"
        if not root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for path in root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("schema_version") == SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION:
                rows.append(public_attempt_projection(payload))
        rows.sort(
            key=lambda row: (str(row.get("recorded_at") or ""), str(row["attempt_id"])),
            reverse=True,
        )
        return rows[:limit]

    def ingest_pdf_bytes(
        self,
        *,
        route_id: str,
        attempt_id: str,
        body: bytes,
        acquisition_method: str,
        adapter_id: str,
        declared_content_type: str,
        transport: Mapping[str, Any] | None = None,
        network_path: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        route = self.policy.require_route(route_id)
        self.assert_attempt_available(attempt_id)
        if acquisition_method not in {"operator_upload", "automatic_adapter"}:
            raise SourceIntakeError("source_intake_acquisition_method_invalid")
        if acquisition_method == "operator_upload" and not route.operator_upload_enabled:
            raise SourceIntakeError("source_intake_operator_upload_forbidden")
        if not body:
            raise SourceIntakeError("source_intake_body_empty")
        if len(body) > route.byte_ceiling:
            raise SourceIntakeError("source_intake_body_too_large")
        _validate_bound_source_url(route, route.source_url)

        digest = hashlib.sha256(body).hexdigest()
        raw_ref, reused = self._persist_raw(digest, body)
        validation = _inspect_pdf(body, declared_content_type=declared_content_type)
        status = (
            "captured_ready_for_parse"
            if validation["accepted"]
            else "captured_rejected"
        )
        payload = {
            "schema_version": SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION,
            "attempt_id": attempt_id,
            "recorded_at": _utc_now(),
            "policy_id": self.policy.policy_id,
            "route_id": route.route_id,
            "case_key": route.case_key,
            "issuer_name": route.issuer_name,
            "document_type": route.document_type,
            "title": route.title,
            "publication_date": route.publication_date,
            "source_url": route.source_url,
            "source_host": (urlparse(route.source_url).hostname or "").lower(),
            "acquisition_method": acquisition_method,
            "adapter_id": adapter_id,
            "status": status,
            "failure_code": validation.get("failure_code"),
            "raw_object_ref": raw_ref,
            "raw_object_sha256": digest,
            "raw_object_bytes": len(body),
            "raw_object_reused": reused,
            "declared_content_type": declared_content_type.split(";", 1)[0].lower(),
            "detected_content_type": validation["detected_content_type"],
            "pdf_signature_valid": validation["pdf_signature_valid"],
            "pdf_eof_valid": validation["pdf_eof_valid"],
            "pdf_page_count": validation["pdf_page_count"],
            "pdf_encrypted": validation["pdf_encrypted"],
            "transport": dict(transport or {}),
            "network_path": dict(network_path or {}),
            "capture_before_parse": True,
            "source_body_is_evidence": False,
            "promotion_status": "source_only_not_evidence",
            "credential_cookie_authorization_present": False,
        }
        manifest_ref = self._persist_attempt(attempt_id, payload)
        return {
            **public_attempt_projection(payload),
            "manifest_ref": manifest_ref,
        }

    def record_automatic_failure(
        self,
        *,
        route_id: str,
        attempt_id: str,
        adapter_id: str,
        failure_code: str,
        transport: Mapping[str, Any],
        network_path: Mapping[str, Any],
    ) -> dict[str, Any]:
        route = self.policy.require_route(route_id)
        self.assert_attempt_available(attempt_id)
        payload = {
            "schema_version": SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION,
            "attempt_id": attempt_id,
            "recorded_at": _utc_now(),
            "policy_id": self.policy.policy_id,
            "route_id": route.route_id,
            "case_key": route.case_key,
            "issuer_name": route.issuer_name,
            "document_type": route.document_type,
            "title": route.title,
            "publication_date": route.publication_date,
            "source_url": route.source_url,
            "source_host": (urlparse(route.source_url).hostname or "").lower(),
            "acquisition_method": "automatic_adapter",
            "adapter_id": adapter_id,
            "status": "acquisition_failed",
            "failure_code": failure_code,
            "raw_object_ref": None,
            "raw_object_sha256": None,
            "raw_object_bytes": 0,
            "raw_object_reused": False,
            "declared_content_type": None,
            "detected_content_type": None,
            "pdf_signature_valid": False,
            "pdf_eof_valid": False,
            "pdf_page_count": 0,
            "pdf_encrypted": False,
            "transport": dict(transport),
            "network_path": dict(network_path),
            "capture_before_parse": True,
            "source_body_is_evidence": False,
            "promotion_status": "source_only_not_evidence",
            "credential_cookie_authorization_present": False,
        }
        manifest_ref = self._persist_attempt(attempt_id, payload)
        return {
            **public_attempt_projection(payload),
            "manifest_ref": manifest_ref,
        }

    def _persist_raw(self, digest: str, body: bytes) -> tuple[str, bool]:
        relative = Path("raw") / "sha256" / digest[:2] / digest[2:4] / f"{digest}.bin"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        reused = path.exists()
        if reused:
            if path.read_bytes() != body:
                raise SourceIntakeError("source_intake_raw_cas_collision")
        else:
            try:
                with path.open("xb") as handle:
                    handle.write(body)
            except FileExistsError:
                if path.read_bytes() != body:
                    raise SourceIntakeError("source_intake_raw_cas_collision")
                reused = True
        return relative.as_posix(), reused

    def _attempt_path(self, attempt_id: str) -> Path:
        return self.root / "attempts" / f"{attempt_id}.json"

    def _persist_attempt(self, attempt_id: str, payload: Mapping[str, Any]) -> str:
        path = self._attempt_path(attempt_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _canonical_json_bytes(payload)
        try:
            with path.open("xb") as handle:
                handle.write(data)
        except FileExistsError as exc:
            raise SourceIntakeError("source_intake_attempt_already_exists") from exc
        return path.relative_to(self.root).as_posix()


def public_attempt_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    network_path = payload.get("network_path")
    transport = payload.get("transport")
    return {
        "attempt_id": payload["attempt_id"],
        "recorded_at": payload["recorded_at"],
        "route_id": payload["route_id"],
        "case_key": payload["case_key"],
        "issuer_name": payload["issuer_name"],
        "document_type": payload["document_type"],
        "title": payload["title"],
        "publication_date": payload["publication_date"],
        "source_url": payload["source_url"],
        "acquisition_method": payload["acquisition_method"],
        "adapter_id": payload["adapter_id"],
        "status": payload["status"],
        "failure_code": payload.get("failure_code"),
        "raw_object_sha256": payload.get("raw_object_sha256"),
        "raw_object_bytes": int(payload.get("raw_object_bytes") or 0),
        "raw_object_reused": bool(payload.get("raw_object_reused")),
        "detected_content_type": payload.get("detected_content_type"),
        "pdf_page_count": int(payload.get("pdf_page_count") or 0),
        "promotion_status": payload["promotion_status"],
        "transport": _public_transport_projection(transport),
        "network_path": _public_network_projection(network_path),
    }


def source_network_path_snapshot(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        raise SourceIntakeError("source_intake_network_url_invalid")
    addresses: list[str] = []
    resolution_status = "resolved"
    try:
        addresses = sorted(
            {
                str(row[4][0])
                for row in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
            }
        )
    except OSError:
        resolution_status = "dns_resolution_failed"
    address_classes = sorted({_address_class(value) for value in addresses})
    route_interface = _windows_route_interface(addresses[0]) if addresses else None
    environment_proxies = requests.utils.get_environ_proxies(url)
    windows_proxy = _windows_user_proxy_flags()
    fake_ip = "benchmark_fake_ip" in address_classes
    return {
        "schema_version": NETWORK_PATH_SCHEMA_VERSION,
        "hostname": hostname,
        "resolution_status": resolution_status,
        "resolved_address_count": len(addresses),
        "resolved_address_classes": address_classes,
        "environment_proxy_configured": bool(environment_proxies),
        "windows_user_proxy_enabled": windows_proxy["proxy_enabled"],
        "windows_pac_configured": windows_proxy["pac_configured"],
        "route_interface": route_interface,
        "transparent_tun_likely": bool(fake_ip and route_interface),
        "diagnostic_boundary": (
            "fake_ip_and_tunnel_route_observed_application_clients_share_transparent_path"
            if fake_ip and route_interface
            else "application_path_observed_without_transparent_tun_proof"
        ),
    }


def _public_network_projection(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    allowed = {
        "schema_version",
        "hostname",
        "resolution_status",
        "resolved_address_count",
        "resolved_address_classes",
        "environment_proxy_configured",
        "windows_user_proxy_enabled",
        "windows_pac_configured",
        "route_interface",
        "transparent_tun_likely",
        "diagnostic_boundary",
    }
    return {str(key): value[key] for key in allowed if key in value}


def _public_transport_projection(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or not value:
        return None
    allowed = {
        "adapter_id",
        "transport",
        "attempts",
        "http_status",
        "failure_code",
        "failure_category",
    }
    return {str(key): value[key] for key in allowed if key in value}


def _validate_route(value: Any) -> SourceIntakeRoute:
    if not isinstance(value, Mapping):
        raise SourceIntakeError("source_intake_policy_route_invalid")
    route_id = str(value.get("route_id") or "").strip()
    case_key = str(value.get("case_key") or "").strip().upper()
    issuer_name = str(value.get("issuer_name") or "").strip()
    document_type = str(value.get("document_type") or "").strip()
    title = str(value.get("title") or "").strip()
    publication_date = str(value.get("publication_date") or "").strip()
    source_url = str(value.get("source_url") or "").strip()
    discovery_url = str(value.get("discovery_url") or "").strip() or None
    allowed_hosts = tuple(
        sorted({str(item).strip().lower() for item in value.get("allowed_hosts") or []})
    )
    expected_types = tuple(
        sorted(
            {
                str(item).strip().lower()
                for item in value.get("expected_content_types") or []
            }
        )
    )
    adapter = value.get("automatic_adapter")
    if not isinstance(adapter, Mapping):
        adapter = {}
    if not (
        _ROUTE_ID_RE.fullmatch(route_id)
        and re.fullmatch(r"[A-Z0-9._-]{1,24}", case_key)
        and issuer_name
        and document_type
        and title
        and len(title) <= 300
        and allowed_hosts
        and expected_types == ("application/pdf",)
        and 1 <= int(value.get("byte_ceiling") or 0) <= 100 * 1024 * 1024
    ):
        raise SourceIntakeError("source_intake_policy_route_invalid")
    try:
        date.fromisoformat(publication_date)
    except ValueError as exc:
        raise SourceIntakeError("source_intake_publication_date_invalid") from exc
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in allowed_hosts:
        raise SourceIntakeError("source_intake_policy_source_url_invalid")
    if discovery_url:
        discovery = urlparse(discovery_url)
        if (
            discovery.scheme != "https"
            or (discovery.hostname or "").lower() not in allowed_hosts
        ):
            raise SourceIntakeError("source_intake_policy_discovery_url_invalid")
    if adapter.get("enabled") is True:
        max_retries = adapter.get("max_retries")
        if str(adapter.get("adapter_id") or "") not in {
            "official_http_capture_v1",
            "official_browser_download_v1",
        }:
            raise SourceIntakeError("source_intake_automatic_adapter_invalid")
        if int(adapter.get("timeout_seconds") or 0) not in range(1, 121):
            raise SourceIntakeError("source_intake_automatic_adapter_invalid")
        if int(max_retries if max_retries is not None else -1) != 0:
            raise SourceIntakeError("source_intake_automatic_adapter_invalid")
    return SourceIntakeRoute(
        route_id=route_id,
        case_key=case_key,
        issuer_name=issuer_name,
        document_type=document_type,
        title=title,
        publication_date=publication_date,
        source_url=source_url,
        discovery_url=discovery_url,
        allowed_hosts=allowed_hosts,
        expected_content_types=expected_types,
        byte_ceiling=int(value["byte_ceiling"]),
        automatic_adapter=dict(adapter),
        operator_upload_enabled=value.get("operator_upload_enabled") is True,
    )


def _validate_bound_source_url(route: SourceIntakeRoute, value: str) -> None:
    parsed = urlparse(value)
    if (
        value != route.source_url
        or parsed.scheme != "https"
        or (parsed.hostname or "").lower() not in route.allowed_hosts
    ):
        raise SourceIntakeError("source_intake_source_url_not_policy_bound")


def _validate_attempt_id(value: str) -> None:
    if not _ATTEMPT_ID_RE.fullmatch(value):
        raise SourceIntakeError("source_intake_attempt_id_invalid")


def _inspect_pdf(body: bytes, *, declared_content_type: str) -> dict[str, Any]:
    declared = declared_content_type.split(";", 1)[0].strip().lower()
    signature_valid = body[:1024].find(b"%PDF-") >= 0
    eof_valid = b"%%EOF" in body[-4096:]
    detected_type = "application/pdf" if signature_valid else "application/octet-stream"
    if declared != "application/pdf":
        return _pdf_rejection(
            "source_intake_declared_content_type_invalid",
            detected_type,
            signature_valid,
            eof_valid,
        )
    if not signature_valid:
        return _pdf_rejection(
            "source_intake_pdf_signature_invalid",
            detected_type,
            signature_valid,
            eof_valid,
        )
    if not eof_valid:
        return _pdf_rejection(
            "source_intake_pdf_truncated",
            detected_type,
            signature_valid,
            eof_valid,
        )
    try:
        reader = PdfReader(BytesIO(body), strict=False)
        encrypted = bool(reader.is_encrypted)
        page_count = 0 if encrypted else len(reader.pages)
    except Exception:  # pypdf has several parser-specific exception classes
        return _pdf_rejection(
            "source_intake_pdf_parse_invalid",
            detected_type,
            signature_valid,
            eof_valid,
        )
    if encrypted:
        return {
            **_pdf_rejection(
                "source_intake_pdf_encrypted",
                detected_type,
                signature_valid,
                eof_valid,
            ),
            "pdf_encrypted": True,
        }
    if page_count < 1:
        return _pdf_rejection(
            "source_intake_pdf_page_count_invalid",
            detected_type,
            signature_valid,
            eof_valid,
        )
    return {
        "accepted": True,
        "failure_code": None,
        "detected_content_type": detected_type,
        "pdf_signature_valid": signature_valid,
        "pdf_eof_valid": eof_valid,
        "pdf_page_count": page_count,
        "pdf_encrypted": False,
    }


def _pdf_rejection(
    failure_code: str,
    detected_type: str,
    signature_valid: bool,
    eof_valid: bool,
) -> dict[str, Any]:
    return {
        "accepted": False,
        "failure_code": failure_code,
        "detected_content_type": detected_type,
        "pdf_signature_valid": signature_valid,
        "pdf_eof_valid": eof_valid,
        "pdf_page_count": 0,
        "pdf_encrypted": False,
    }


def _address_class(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return "invalid"
    if address in _FAKE_IP_NETWORK:
        return "benchmark_fake_ip"
    if address.is_loopback:
        return "loopback"
    if address.is_private:
        return "private"
    if address.version == 6:
        return "public_ipv6"
    return "public_ipv4"


def _windows_route_interface(address: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        ipaddress.ip_address(address)
        command = (
            "Find-NetRoute -RemoteIPAddress '"
            + address
            + "' | Select-Object -First 1 -ExpandProperty InterfaceAlias"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            check=False,
            timeout=5,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    value = completed.stdout.strip().splitlines()
    return value[0].strip()[:128] if completed.returncode == 0 and value else None


def _windows_user_proxy_flags() -> dict[str, bool]:
    if os.name != "nt":
        return {"proxy_enabled": False, "pac_configured": False}
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as key:
            try:
                proxy_enabled = bool(winreg.QueryValueEx(key, "ProxyEnable")[0])
            except OSError:
                proxy_enabled = False
            try:
                pac_configured = bool(str(winreg.QueryValueEx(key, "AutoConfigURL")[0]))
            except OSError:
                pac_configured = False
    except OSError:
        return {"proxy_enabled": False, "pac_configured": False}
    return {"proxy_enabled": proxy_enabled, "pac_configured": pac_configured}


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "NETWORK_PATH_SCHEMA_VERSION",
    "SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION",
    "SOURCE_INTAKE_POLICY_SCHEMA_VERSION",
    "SourceIntakeError",
    "SourceIntakePolicy",
    "SourceIntakeRoute",
    "SourceIntakeStore",
    "public_attempt_projection",
    "source_network_path_snapshot",
]
