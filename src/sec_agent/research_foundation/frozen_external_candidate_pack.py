from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from sec_agent.research.reviewed_evidence_pack import canonical_digest

from .external_sources import (
    CAPTURE_RECEIPT_SCHEMA_VERSION,
    CaptureAttempt,
    CaptureReceipt,
    DiscoveryReceipt,
    ExternalCaptureRequest,
    ExternalSearchRequest,
    ExternalSourceCapture,
    ExternalSourceError,
    ProviderHit,
    PublicURLGuard,
)


FROZEN_PACK_SCHEMA_VERSION = (
    "fin_ia_dell_external_exact_url_qualification_manifest_v1_0"
)
FROZEN_ROUTE_SCHEMA_VERSION = (
    "fin_ia_dell_external_exact_url_route_result_v1_0"
)
FROZEN_REPLAY_METHOD = "frozen_exact_url_candidate_replay"

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ROUTE_ID = re.compile(r"[A-Z0-9][A-Z0-9_]{0,127}\Z")
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class FrozenExternalCandidateRoute:
    route_id: str
    branch_id: str
    official_url: str
    document_title: str
    publisher: str
    source_period: str
    route_result_digest: str
    discovery_receipt_digest: str
    original_capture_receipt_digest: str
    original_captured_at: str
    text: str
    text_digest: str


class FrozenExternalCandidatePack:
    """Read-only, digest-bound view of one exact-URL qualification pack.

    This is deliberately a candidate replay adapter, not an Evidence store. It
    validates the frozen qualification files before exposing their locators or
    text to the existing external MCP lane.
    """

    def __init__(
        self,
        *,
        manifest_path: Path,
        manifest_file_sha256: str,
        manifest_digest: str,
        attempt_id: str,
        case_id: str,
        source_research_as_of: str,
        routes: tuple[FrozenExternalCandidateRoute, ...],
    ) -> None:
        self.manifest_path = manifest_path
        self.manifest_file_sha256 = manifest_file_sha256
        self.manifest_digest = manifest_digest
        self.attempt_id = attempt_id
        self.case_id = case_id
        self.source_research_as_of = source_research_as_of
        self.routes = routes
        self.provider_id = (
            f"frozen_exact_url_candidate_pack:{attempt_id}:"
            f"{manifest_digest}"
        )
        self._routes_by_branch_url = {
            (route.branch_id, route.official_url): route for route in routes
        }

    @classmethod
    def load(
        cls,
        manifest_path: Path,
        *,
        expected_sha256: str | None = None,
    ) -> "FrozenExternalCandidatePack":
        resolved = manifest_path.expanduser().resolve()
        raw = _read_bounded_bytes(
            resolved,
            label="frozen_candidate_pack_manifest",
            maximum_bytes=_MAX_MANIFEST_BYTES,
        )
        file_sha = sha256(raw).hexdigest()
        if expected_sha256 is not None:
            expected = str(expected_sha256).strip().lower()
            if not _DIGEST.fullmatch(expected):
                raise ExternalSourceError(
                    "frozen_candidate_pack_expected_sha256_invalid"
                )
            if file_sha != expected:
                raise ExternalSourceError(
                    "frozen_candidate_pack_manifest_sha256_mismatch"
                )
        manifest = _json_mapping(raw, "frozen_candidate_pack_manifest")
        _require_equal(
            manifest.get("schema_version"),
            FROZEN_PACK_SCHEMA_VERSION,
            "frozen_candidate_pack_schema_invalid",
        )
        for field, expected_value in (
            ("status", "PASS"),
            ("exact_url_mode", True),
            ("candidate_is_not_evidence", True),
            ("source_capture_authority", False),
            ("evidence_admission_authorized", False),
            ("mcp_promotion_authorized", False),
            ("production_status", "HOLD"),
            ("model_calls", 0),
            ("deepseek_calls", 0),
            ("paid_calls", 0),
        ):
            _require_equal(
                manifest.get(field),
                expected_value,
                f"frozen_candidate_pack_{field}_invalid",
            )
        manifest_digest = _require_digest(
            manifest.get("manifest_digest"),
            "frozen_candidate_pack_manifest_digest_invalid",
        )
        unsigned_manifest = dict(manifest)
        unsigned_manifest.pop("manifest_digest", None)
        if canonical_digest(unsigned_manifest) != manifest_digest:
            raise ExternalSourceError(
                "frozen_candidate_pack_manifest_digest_mismatch"
            )

        attempt_id = _require_nonempty(
            manifest.get("attempt_id"),
            "frozen_candidate_pack_attempt_id_invalid",
        )
        case_id = _require_nonempty(
            manifest.get("case_id"),
            "frozen_candidate_pack_case_id_invalid",
        )
        run_scope = manifest.get("run_scope")
        if not isinstance(run_scope, Mapping):
            raise ExternalSourceError("frozen_candidate_pack_run_scope_invalid")
        _require_equal(
            run_scope.get("case_id"),
            case_id,
            "frozen_candidate_pack_run_scope_case_mismatch",
        )
        source_research_as_of = _require_nonempty(
            run_scope.get("research_as_of"),
            "frozen_candidate_pack_research_as_of_invalid",
        )

        artifacts = _validate_artifacts(
            resolved.parent,
            manifest.get("artifacts"),
        )
        raw_route_results = manifest.get("route_results")
        if not isinstance(raw_route_results, list) or not raw_route_results:
            raise ExternalSourceError(
                "frozen_candidate_pack_route_results_invalid"
            )
        declared_count = manifest.get("declared_route_count")
        attempted_count = manifest.get("attempted_route_count")
        passed_count = manifest.get("passed_route_count")
        if (
            declared_count != len(raw_route_results)
            or attempted_count != len(raw_route_results)
            or passed_count != len(raw_route_results)
        ):
            raise ExternalSourceError("frozen_candidate_pack_route_count_mismatch")

        routes: list[FrozenExternalCandidateRoute] = []
        seen_route_ids: set[str] = set()
        seen_branch_urls: set[tuple[str, str]] = set()
        guard = PublicURLGuard()
        for raw_route in raw_route_results:
            if not isinstance(raw_route, Mapping):
                raise ExternalSourceError(
                    "frozen_candidate_pack_route_result_invalid"
                )
            route_result = dict(raw_route)
            route_id = _require_nonempty(
                route_result.get("route_id"),
                "frozen_candidate_pack_route_id_invalid",
            )
            if not _ROUTE_ID.fullmatch(route_id) or route_id in seen_route_ids:
                raise ExternalSourceError(
                    "frozen_candidate_pack_route_id_invalid"
                )
            seen_route_ids.add(route_id)
            route_base = f"routes/{route_id}"
            route_result_path = _require_artifact(
                artifacts,
                f"{route_base}/route_result.json",
            )
            discovery_path = _require_artifact(
                artifacts,
                f"{route_base}/discovery_receipt.json",
            )
            capture_path = _require_artifact(
                artifacts,
                f"{route_base}/capture_receipt.json",
            )
            text_path = _require_artifact(
                artifacts,
                f"{route_base}/captured_text.txt",
            )

            route_file = _json_mapping(
                _read_bounded_bytes(
                    route_result_path,
                    label="frozen_candidate_pack_route_result",
                    maximum_bytes=_MAX_ARTIFACT_BYTES,
                ),
                "frozen_candidate_pack_route_result",
            )
            if dict(route_file) != route_result:
                raise ExternalSourceError(
                    "frozen_candidate_pack_route_projection_mismatch"
                )
            _require_equal(
                route_result.get("schema_version"),
                FROZEN_ROUTE_SCHEMA_VERSION,
                "frozen_candidate_pack_route_schema_invalid",
            )
            for field, expected_value in (
                ("status", "PASS"),
                ("exact_url_bound", True),
                ("candidate_is_not_evidence", True),
                ("source_capture_authority", False),
                ("admission_required_before_citation", True),
            ):
                _require_equal(
                    route_result.get(field),
                    expected_value,
                    f"frozen_candidate_pack_route_{field}_invalid",
                )
            route_digest = _require_digest(
                route_result.get("route_result_digest"),
                "frozen_candidate_pack_route_digest_invalid",
            )
            unsigned_route = dict(route_result)
            unsigned_route.pop("route_result_digest", None)
            if canonical_digest(unsigned_route) != route_digest:
                raise ExternalSourceError(
                    "frozen_candidate_pack_route_digest_mismatch"
                )

            discovery = DiscoveryReceipt.model_validate(
                _json_mapping(
                    _read_bounded_bytes(
                        discovery_path,
                        label="frozen_candidate_pack_discovery_receipt",
                        maximum_bytes=_MAX_ARTIFACT_BYTES,
                    ),
                    "frozen_candidate_pack_discovery_receipt",
                )
            )
            original_capture = CaptureReceipt.model_validate(
                _json_mapping(
                    _read_bounded_bytes(
                        capture_path,
                        label="frozen_candidate_pack_capture_receipt",
                        maximum_bytes=_MAX_ARTIFACT_BYTES,
                    ),
                    "frozen_candidate_pack_capture_receipt",
                )
            )
            text_bytes = _read_bounded_bytes(
                text_path,
                label="frozen_candidate_pack_captured_text",
                maximum_bytes=_MAX_ARTIFACT_BYTES,
            )
            try:
                text = text_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ExternalSourceError(
                    "frozen_candidate_pack_captured_text_not_utf8"
                ) from exc
            text_digest = sha256(text_bytes).hexdigest()
            route_text_digest = _require_digest(
                route_result.get("bounded_text_sha256"),
                "frozen_candidate_pack_text_digest_invalid",
            )
            if text_digest != route_text_digest:
                raise ExternalSourceError(
                    "frozen_candidate_pack_text_digest_mismatch"
                )
            if len(text) != route_result.get("bounded_text_characters"):
                raise ExternalSourceError(
                    "frozen_candidate_pack_text_character_count_mismatch"
                )
            if len(text_bytes) != route_result.get("bounded_text_bytes"):
                raise ExternalSourceError(
                    "frozen_candidate_pack_text_byte_count_mismatch"
                )

            branch_id = _require_nonempty(
                route_result.get("branch_id"),
                "frozen_candidate_pack_route_branch_invalid",
            )
            official_url = guard.validate(
                _require_nonempty(
                    route_result.get("official_url"),
                    "frozen_candidate_pack_official_url_invalid",
                ),
                resolve=False,
            )
            source_identity = route_result.get("source_identity")
            if not isinstance(source_identity, Mapping):
                raise ExternalSourceError(
                    "frozen_candidate_pack_source_identity_invalid"
                )
            route_key = (branch_id, official_url)
            if route_key in seen_branch_urls:
                raise ExternalSourceError(
                    "frozen_candidate_pack_branch_url_duplicate"
                )
            seen_branch_urls.add(route_key)
            if (
                discovery.status != "ok"
                or discovery.branch_id != branch_id
                or discovery.case_id != case_id
                or len(discovery.candidates) != 1
                or guard.validate(
                    discovery.candidates[0].canonical_url,
                    resolve=False,
                )
                != official_url
                or original_capture.status != "captured"
                or original_capture.authority_state
                != "captured_source_candidate"
                or original_capture.captured_candidate_is_not_evidence is not True
                or original_capture.source_capture_authority is not False
                or original_capture.text != text
                or original_capture.text_digest
                != route_result.get("upstream_text_digest")
                or original_capture.extracted_characters
                != route_result.get("upstream_extracted_characters")
                or guard.validate(original_capture.requested_url, resolve=False)
                != official_url
            ):
                raise ExternalSourceError(
                    "frozen_candidate_pack_route_lineage_mismatch"
                )
            if (
                route_result.get("discovery_receipt_digest")
                != discovery.receipt_digest
                or route_result.get("capture_receipt_digest")
                != original_capture.receipt_digest
            ):
                raise ExternalSourceError(
                    "frozen_candidate_pack_receipt_digest_binding_mismatch"
                )

            routes.append(
                FrozenExternalCandidateRoute(
                    route_id=route_id,
                    branch_id=branch_id,
                    official_url=official_url,
                    document_title=_require_nonempty(
                        source_identity.get("document_title"),
                        "frozen_candidate_pack_document_title_invalid",
                    ),
                    publisher=_require_nonempty(
                        source_identity.get("publisher"),
                        "frozen_candidate_pack_publisher_invalid",
                    ),
                    source_period=_require_nonempty(
                        source_identity.get("source_period"),
                        "frozen_candidate_pack_source_period_invalid",
                    ),
                    route_result_digest=route_digest,
                    discovery_receipt_digest=discovery.receipt_digest,
                    original_capture_receipt_digest=original_capture.receipt_digest,
                    original_captured_at=original_capture.captured_at,
                    text=text,
                    text_digest=text_digest,
                )
            )

        return cls(
            manifest_path=resolved,
            manifest_file_sha256=file_sha,
            manifest_digest=manifest_digest,
            attempt_id=attempt_id,
            case_id=case_id,
            source_research_as_of=source_research_as_of,
            routes=tuple(routes),
        )

    def validate_runtime_binding(
        self,
        *,
        case_id: str,
        branch_ids: tuple[str, ...],
        research_as_of: datetime,
    ) -> None:
        if case_id != self.case_id:
            raise ExternalSourceError("frozen_candidate_pack_runtime_case_mismatch")
        allowed = set(branch_ids)
        if not allowed:
            raise ExternalSourceError(
                "frozen_candidate_pack_runtime_branches_empty"
            )
        if any(route.branch_id not in allowed for route in self.routes):
            raise ExternalSourceError(
                "frozen_candidate_pack_runtime_branch_mismatch"
            )
        source_as_of = _parse_datetime(
            self.source_research_as_of,
            "frozen_candidate_pack_research_as_of_invalid",
        )
        runtime_as_of = research_as_of
        if runtime_as_of.tzinfo is None:
            runtime_as_of = runtime_as_of.replace(tzinfo=timezone.utc)
        if source_as_of > runtime_as_of.astimezone(timezone.utc):
            raise ExternalSourceError(
                "frozen_candidate_pack_newer_than_runtime_as_of"
            )

    def routes_for_branch(
        self,
        branch_id: str,
    ) -> tuple[FrozenExternalCandidateRoute, ...]:
        return tuple(
            sorted(
                (
                    route
                    for route in self.routes
                    if route.branch_id == branch_id
                ),
                key=lambda route: route.route_id,
            )
        )

    def route_for_candidate(
        self,
        request: ExternalCaptureRequest,
    ) -> FrozenExternalCandidateRoute:
        if request.candidate.provider_id != self.provider_id:
            raise ExternalSourceError(
                "frozen_candidate_pack_provider_binding_mismatch"
            )
        route = self._routes_by_branch_url.get(
            (request.branch_id, request.candidate.canonical_url)
        )
        if route is None:
            raise ExternalSourceError(
                "frozen_candidate_pack_route_binding_invalid"
            )
        return route

    def manifest_binding(self) -> dict[str, Any]:
        return {
            "manifest_path": str(self.manifest_path),
            "manifest_file_sha256": self.manifest_file_sha256,
            "manifest_digest": self.manifest_digest,
            "attempt_id": self.attempt_id,
            "case_id": self.case_id,
            "source_research_as_of": self.source_research_as_of,
            "route_count": len(self.routes),
            "route_ids": [route.route_id for route in self.routes],
            "candidate_is_not_evidence": True,
            "source_capture_authority": False,
            "evidence_admission_authorized": False,
            "mcp_promotion_authorized": False,
            "s2_write_authorized": False,
            "numeric_fact_authority": False,
            "production_status": "HOLD",
        }


class FrozenExternalCandidatePackProvider:
    """Expose frozen exact URLs as the first discovery provider, without text."""

    def __init__(self, pack: FrozenExternalCandidatePack) -> None:
        self.pack = pack
        self.provider_id = pack.provider_id

    async def search(
        self,
        request: ExternalSearchRequest,
    ) -> tuple[ProviderHit, ...]:
        routes = self.pack.routes_for_branch(request.branch_id)
        if request.include_domains:
            routes = tuple(
                route
                for route in routes
                if _host_matches_domains(
                    str(urlsplit(route.official_url).hostname or "").lower(),
                    request.include_domains,
                )
            )
        return tuple(
            ProviderHit(
                title=route.document_title,
                url=route.official_url,
                snippet=(
                    "Frozen exact-URL locator candidate; capture through the "
                    "bound candidate pack before reading source text. This is "
                    "not Evidence and is not citation eligible."
                ),
                published_at=route.source_period,
            )
            for route in routes[: request.max_results]
        )


class FrozenFirstExternalSourceCapture:
    """Replay bound pack text, delegating all non-pack candidates unchanged."""

    def __init__(
        self,
        *,
        pack: FrozenExternalCandidatePack,
        fallback: ExternalSourceCapture,
    ) -> None:
        self.pack = pack
        self.fallback = fallback

    async def capture(self, request: ExternalCaptureRequest) -> CaptureReceipt:
        if request.candidate.provider_id != self.pack.provider_id:
            return await self.fallback.capture(request)
        route = self.pack.route_for_candidate(request)
        bounded_text = route.text[: request.max_characters]
        body = {
            "schema_version": CAPTURE_RECEIPT_SCHEMA_VERSION,
            "status": "captured",
            "authority_state": "captured_source_candidate",
            "branch_id": request.branch_id,
            "case_id": request.run_scope.case_id,
            "execution_attempt_id": request.run_scope.execution_attempt_id,
            "purpose": request.discovery_receipt.purpose,
            "research_as_of": _iso(request.run_scope.research_as_of),
            "source_policy": request.discovery_receipt.source_policy,
            "data_snapshot_id": request.run_scope.data_snapshot_id,
            "method_sha256": request.run_scope.method_sha256,
            "run_scope_digest": request.run_scope.run_scope_digest,
            "discovery_receipt_digest": request.discovery_receipt.receipt_digest,
            "candidate_id": request.candidate_id,
            "provider_id": request.candidate.provider_id,
            "query_digest": request.candidate.query_digest,
            "requested_url": request.candidate.canonical_url,
            "final_url": route.official_url,
            "source_domain": str(
                urlsplit(route.official_url).hostname or ""
            ).lower(),
            "capture_method": FROZEN_REPLAY_METHOD,
            "attempts": [
                CaptureAttempt(
                    method=FROZEN_REPLAY_METHOD,
                    status="ok",
                    extracted_characters=len(route.text),
                ).model_dump(mode="json")
            ],
            "text": bounded_text,
            "extracted_characters": len(route.text),
            "truncated": len(route.text) > len(bounded_text),
            "decoded_html_utf8_sha256": None,
            "text_digest": route.text_digest,
            "captured_at": route.original_captured_at,
            "elapsed_ms": 0,
            "captured_candidate_is_not_evidence": True,
            "admission_required_before_citation": True,
            "failure_is_not_public_information_gap": True,
            "archive_grade": False,
            "robots_enforced": False,
            "source_capture_authority": False,
            "transport_authority": "qualification_only",
            "production_status": "HOLD",
        }
        return CaptureReceipt(**body, receipt_digest=canonical_digest(body))


def _validate_artifacts(
    root: Path,
    raw_artifacts: Any,
) -> dict[str, Path]:
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ExternalSourceError("frozen_candidate_pack_artifacts_invalid")
    resolved_root = root.resolve()
    artifacts: dict[str, Path] = {}
    for raw in raw_artifacts:
        if not isinstance(raw, Mapping):
            raise ExternalSourceError("frozen_candidate_pack_artifact_invalid")
        relative = _require_nonempty(
            raw.get("relative_path"),
            "frozen_candidate_pack_artifact_path_invalid",
        ).replace("\\", "/")
        if relative.startswith("/") or relative in artifacts:
            raise ExternalSourceError(
                "frozen_candidate_pack_artifact_path_invalid"
            )
        path = (resolved_root / Path(relative)).resolve()
        if resolved_root != path and resolved_root not in path.parents:
            raise ExternalSourceError(
                "frozen_candidate_pack_artifact_path_escape"
            )
        payload = _read_bounded_bytes(
            path,
            label="frozen_candidate_pack_artifact",
            maximum_bytes=_MAX_ARTIFACT_BYTES,
        )
        expected_bytes = raw.get("bytes")
        expected_sha = _require_digest(
            raw.get("sha256"),
            "frozen_candidate_pack_artifact_sha256_invalid",
        )
        if len(payload) != expected_bytes:
            raise ExternalSourceError(
                "frozen_candidate_pack_artifact_size_mismatch"
            )
        if sha256(payload).hexdigest() != expected_sha:
            raise ExternalSourceError(
                "frozen_candidate_pack_artifact_sha256_mismatch"
            )
        artifacts[relative] = path
    return artifacts


def _require_artifact(artifacts: Mapping[str, Path], relative: str) -> Path:
    path = artifacts.get(relative)
    if path is None:
        raise ExternalSourceError("frozen_candidate_pack_artifact_missing")
    return path


def _read_bounded_bytes(path: Path, *, label: str, maximum_bytes: int) -> bytes:
    try:
        size = path.stat().st_size
        if size < 1 or size > maximum_bytes:
            raise ExternalSourceError(f"{label}_size_invalid")
        return path.read_bytes()
    except ExternalSourceError:
        raise
    except OSError as exc:
        raise ExternalSourceError(f"{label}_unreadable") from exc


def _json_mapping(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalSourceError(f"{label}_json_invalid") from exc
    if not isinstance(value, dict):
        raise ExternalSourceError(f"{label}_mapping_required")
    return value


def _require_nonempty(value: Any, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ExternalSourceError(code)
    return normalized


def _require_digest(value: Any, code: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _DIGEST.fullmatch(normalized):
        raise ExternalSourceError(code)
    return normalized


def _require_equal(value: Any, expected: Any, code: str) -> None:
    if value != expected or type(value) is not type(expected):
        raise ExternalSourceError(code)


def _parse_datetime(value: str, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExternalSourceError(code) from exc
    if parsed.tzinfo is None:
        raise ExternalSourceError(code)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _host_matches_domains(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


__all__ = [
    "FROZEN_PACK_SCHEMA_VERSION",
    "FROZEN_REPLAY_METHOD",
    "FROZEN_ROUTE_SCHEMA_VERSION",
    "FrozenExternalCandidatePack",
    "FrozenExternalCandidatePackProvider",
    "FrozenExternalCandidateRoute",
    "FrozenFirstExternalSourceCapture",
]
