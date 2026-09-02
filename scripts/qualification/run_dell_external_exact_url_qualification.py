from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402
from sec_agent.research_foundation.contracts import (  # noqa: E402
    DellResearchRunScope,
    canonical_sha256,
)
from sec_agent.research_foundation.external_sources import (  # noqa: E402
    ExternalCaptureRequest,
    ExternalSearchRequest,
    ExternalSourceCapture,
    ExternalSourceDiscovery,
    ProviderHit,
)


CONFIG_SCHEMA = "fin_ia_dell_external_exact_url_qualification_config_v1_0"
MANIFEST_SCHEMA = "fin_ia_dell_external_exact_url_qualification_manifest_v1_0"
ROUTE_RESULT_SCHEMA = "fin_ia_dell_external_exact_url_route_result_v1_0"
DEFAULT_CONFIG = (
    REPOSITORY_ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_external_exact_url_qualification_v1_3.json"
)
DEFAULT_OUTPUT_ROOT = Path(
    r"Z:\FIN_Insight_Agent_qualification\dell_reference_vertical"
    r"\external_exact_url_qualification"
)
ROUTE_ID_PATTERN = re.compile(r"^E\d{2}_[A-Z0-9_]+$")


class QualificationError(RuntimeError):
    """A frozen qualification input or output failed closed."""


class QualificationRunFailed(QualificationError):
    def __init__(self, code: str, manifest_path: Path) -> None:
        self.code = code
        self.manifest_path = manifest_path
        super().__init__(f"{code}; manifest={manifest_path}")


class MarkerGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(min_length=1, max_length=96)
    any_of: tuple[str, ...] = Field(min_length=1, max_length=12)

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("marker_group_id_empty")
        return normalized

    @field_validator("any_of")
    @classmethod
    def validate_markers(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(value).strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("marker_empty")
        if len({_normalize_match_text(value) for value in normalized}) != len(
            normalized
        ):
            raise ValueError("marker_duplicate")
        return normalized


class SourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publisher: str = Field(min_length=1, max_length=200)
    document_title: str = Field(min_length=1, max_length=300)
    source_period: str = Field(min_length=1, max_length=80)
    official_domain: str = Field(min_length=3, max_length=253)

    @field_validator("publisher", "document_title", "source_period")
    @classmethod
    def strip_identity_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_identity_value_empty")
        return normalized

    @field_validator("official_domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        domain = value.strip().lower().rstrip(".")
        if "://" in domain or "/" in domain or "." not in domain:
            raise ValueError("source_identity_domain_invalid")
        return domain


class ExactRouteSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str
    branch_id: str = Field(min_length=1, max_length=96)
    official_url: str
    source_identity: SourceIdentity
    identity_marker_groups: tuple[MarkerGroup, ...] = Field(min_length=2)
    content_marker_groups: tuple[MarkerGroup, ...] = Field(min_length=1)
    minimum_useful_characters: int = Field(ge=200, le=2_000)
    max_characters: int = Field(ge=500, le=50_000)

    @field_validator("route_id")
    @classmethod
    def validate_route_id(cls, value: str) -> str:
        normalized = value.strip()
        if not ROUTE_ID_PATTERN.fullmatch(normalized):
            raise ValueError("route_id_invalid")
        return normalized

    @field_validator("branch_id", "official_url")
    @classmethod
    def strip_route_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("route_value_empty")
        return normalized

    @model_validator(mode="after")
    def validate_exact_official_route(self) -> "ExactRouteSpec":
        parts = urlsplit(self.official_url)
        if (
            parts.scheme.lower() != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.fragment
        ):
            raise ValueError("official_url_invalid")
        if parts.hostname.lower().rstrip(".") != self.source_identity.official_domain:
            raise ValueError("official_url_domain_identity_mismatch")
        group_ids = [
            row.group_id
            for row in (*self.identity_marker_groups, *self.content_marker_groups)
        ]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("marker_group_id_duplicate")
        return self


class QualificationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "fin_ia_dell_external_exact_url_qualification_config_v1_0"
    ]
    status: Literal["frozen_zero_model_exact_url_qualification"]
    case_id: str = Field(min_length=1, max_length=160)
    research_as_of: datetime
    data_snapshot_id: str = Field(min_length=1, max_length=256)
    transport: Literal["exa_hosted_web_fetch"]
    capture_authority: Literal["qualification_only"]
    production_status: Literal["HOLD"]
    candidate_is_not_evidence: Literal[True]
    model_calls_authorized: Literal[False]
    fail_fast: Literal[True]
    routes: tuple[ExactRouteSpec, ...] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_frozen_route_set(self) -> "QualificationConfig":
        if self.research_as_of.tzinfo is None or self.research_as_of.utcoffset() is None:
            raise ValueError("research_as_of_timezone_required")
        route_ids = [row.route_id for row in self.routes]
        urls = [row.official_url for row in self.routes]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route_id_duplicate")
        if len(urls) != len(set(urls)):
            raise ValueError("official_url_duplicate")
        return self


class CapturePort(Protocol):
    async def capture(self, request: ExternalCaptureRequest): ...


class FrozenExactURLProvider:
    """Local registry adapter; it performs no search and grants no Evidence authority."""

    provider_id = "frozen_exact_url_registry"

    def __init__(self, route: ExactRouteSpec) -> None:
        self.route = route

    async def search(self, _request: ExternalSearchRequest) -> tuple[ProviderHit, ...]:
        return (
            ProviderHit(
                title=self.route.source_identity.document_title,
                url=self.route.official_url,
                snippet="Frozen exact official URL; locator only, not Evidence.",
                published_at=self.route.source_identity.source_period,
            ),
        )


def _normalize_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    for char in ("‐", "‑", "‒", "–", "—", "−"):
        normalized = normalized.replace(char, "-")
    return " ".join(normalized.split())


def _match_marker_groups(
    text: str,
    groups: Sequence[MarkerGroup],
) -> tuple[dict[str, str], tuple[str, ...]]:
    haystack = _normalize_match_text(text)
    matched: dict[str, str] = {}
    missing: list[str] = []
    for group in groups:
        marker = next(
            (
                candidate
                for candidate in group.any_of
                if _normalize_match_text(candidate) in haystack
            ),
            None,
        )
        if marker is None:
            missing.append(group.group_id)
        else:
            matched[group.group_id] = marker
    return matched, tuple(missing)


def _canonical_json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json_exclusive(path: Path, value: Any) -> None:
    _write_bytes_exclusive(path, _canonical_json_bytes(value, pretty=True))


def load_config(path: str | Path) -> tuple[QualificationConfig, str]:
    config_path = Path(path).expanduser().resolve()
    try:
        raw = config_path.read_bytes()
    except OSError as exc:
        raise QualificationError(f"config_unreadable:{config_path}") from exc
    try:
        return QualificationConfig.model_validate_json(raw), _sha256_bytes(raw)
    except Exception as exc:
        raise QualificationError(f"config_invalid:{config_path}") from exc


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_run_scope(
    config: QualificationConfig,
    *,
    attempt_id: str,
    config_contract_digest: str,
) -> DellResearchRunScope:
    branch_ids = tuple(dict.fromkeys(row.branch_id for row in config.routes))
    scope_body = {
        "schema_version": "fin_ia_dell_research_run_scope_v1_0",
        "case_id": config.case_id,
        "research_as_of": _iso(config.research_as_of),
        "data_snapshot_id": config.data_snapshot_id,
        "method_sha256": config_contract_digest,
        "selected_branch_ids": branch_ids,
        "execution_attempt_id": attempt_id,
        "source_policy": "frozen_local_reviewed_plus_public_web_locator_only",
    }
    return DellResearchRunScope(
        **{**scope_body, "research_as_of": config.research_as_of},
        run_scope_digest=canonical_sha256(scope_body),
    )


def _artifact_inventory(attempt_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(attempt_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        rows.append(
            {
                "relative_path": path.relative_to(attempt_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return rows


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, QualificationError):
        return str(exc).split(";", 1)[0]
    return f"unclassified_qualification_failure:{type(exc).__name__}"


async def run_qualification(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    attempt_id: str,
    capture: CapturePort | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Path:
    config, config_file_sha256 = load_config(config_path)
    now = clock or (lambda: datetime.now(timezone.utc))
    started_at = now()
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise QualificationError("clock_timezone_required")
    attempt_id = attempt_id.strip()
    if not attempt_id or any(char in attempt_id for char in "\\/:*?\"<>|"):
        raise QualificationError("attempt_id_invalid")
    attempt_dir = Path(output_root).expanduser().resolve() / attempt_id
    try:
        attempt_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise QualificationError(f"attempt_directory_exists:{attempt_dir}") from exc

    config_contract_digest = canonical_digest(config.model_dump(mode="json"))
    run_scope = _build_run_scope(
        config,
        attempt_id=attempt_id,
        config_contract_digest=config_contract_digest,
    )
    capture_port = capture or ExternalSourceCapture.with_default_transports()
    route_results: list[dict[str, Any]] = []
    terminal_failure_code: str | None = None

    for route in config.routes:
        route_dir = attempt_dir / "routes" / route.route_id
        route_dir.mkdir(parents=True, exist_ok=False)
        discovery_receipt = None
        capture_receipt = None
        bounded_text_bytes = b""
        exact_url_bound = False
        identity_matches: dict[str, str] = {}
        content_matches: dict[str, str] = {}
        identity_markers_passed = False
        content_markers_passed = False
        try:
            discovery = ExternalSourceDiscovery(
                primary=FrozenExactURLProvider(route),
                clock=now,
            )
            search_request = ExternalSearchRequest(
                query=f"Fetch frozen exact official route {route.route_id}",
                branch_id=route.branch_id,
                run_scope=run_scope,
                purpose=(
                    "Verify one frozen official exact URL through the hosted "
                    "qualification transport without granting Evidence authority."
                ),
                max_results=1,
                include_domains=(route.source_identity.official_domain,),
            )
            discovery_receipt = await discovery.search(search_request)
            if discovery_receipt.status != "ok" or len(discovery_receipt.candidates) != 1:
                raise QualificationError("exact_url_registry_binding_failed")
            candidate = discovery_receipt.candidates[0]
            if (
                candidate.canonical_url != route.official_url
                or candidate.source_domain != route.source_identity.official_domain
                or candidate.candidate_is_not_evidence is not True
            ):
                raise QualificationError("exact_url_candidate_identity_mismatch")

            capture_receipt = await capture_port.capture(
                ExternalCaptureRequest(
                    discovery_receipt=discovery_receipt,
                    candidate_id=candidate.candidate_id,
                    branch_id=route.branch_id,
                    run_scope=run_scope,
                    max_characters=route.max_characters,
                    render_policy="hosted",
                    minimum_useful_characters=route.minimum_useful_characters,
                    timeout_seconds=60.0,
                )
            )
            if capture_receipt.status != "captured":
                failure = next(
                    (
                        row.failure_code
                        for row in reversed(capture_receipt.attempts)
                        if row.failure_code
                    ),
                    "capture_not_captured",
                )
                raise QualificationError(str(failure))
            if (
                capture_receipt.capture_method != "exa_hosted_web_fetch"
                or capture_receipt.requested_url != route.official_url
                or capture_receipt.final_url != route.official_url
                or capture_receipt.source_domain
                != route.source_identity.official_domain
            ):
                raise QualificationError("captured_exact_url_binding_mismatch")
            if (
                capture_receipt.captured_candidate_is_not_evidence is not True
                or capture_receipt.admission_required_before_citation is not True
                or capture_receipt.source_capture_authority is not False
            ):
                raise QualificationError("capture_authority_ceiling_mismatch")
            exact_url_bound = True

            identity_matches, missing_identity = _match_marker_groups(
                capture_receipt.text,
                route.identity_marker_groups,
            )
            content_matches, missing_content = _match_marker_groups(
                capture_receipt.text,
                route.content_marker_groups,
            )
            bounded_text_bytes = capture_receipt.text.encode("utf-8")
            _write_bytes_exclusive(route_dir / "captured_text.txt", bounded_text_bytes)
            identity_markers_passed = not missing_identity
            content_markers_passed = not missing_content
            if missing_identity:
                raise QualificationError(
                    "source_identity_marker_missing:" + ",".join(missing_identity)
                )
            if missing_content:
                raise QualificationError(
                    "content_marker_missing:" + ",".join(missing_content)
                )

            route_result = {
                "schema_version": ROUTE_RESULT_SCHEMA,
                "status": "PASS",
                "route_id": route.route_id,
                "branch_id": route.branch_id,
                "official_url": route.official_url,
                "source_identity": route.source_identity.model_dump(mode="json"),
                "exact_url_bound": True,
                "identity_marker_groups_passed": True,
                "content_marker_groups_passed": True,
                "matched_identity_markers": identity_matches,
                "matched_content_markers": content_matches,
                "bounded_text_characters": len(capture_receipt.text),
                "bounded_text_bytes": len(bounded_text_bytes),
                "bounded_text_sha256": _sha256_bytes(bounded_text_bytes),
                "upstream_extracted_characters": capture_receipt.extracted_characters,
                "upstream_text_digest": capture_receipt.text_digest,
                "truncated_to_qualification_limit": capture_receipt.truncated,
                "discovery_receipt_digest": discovery_receipt.receipt_digest,
                "capture_receipt_digest": capture_receipt.receipt_digest,
                "capture_method": capture_receipt.capture_method,
                "candidate_is_not_evidence": True,
                "admission_required_before_citation": True,
                "source_capture_authority": False,
                "model_calls": 0,
                "failure_code": None,
            }
        except Exception as exc:
            terminal_failure_code = _failure_code(exc)
            if capture_receipt is not None and capture_receipt.text and not bounded_text_bytes:
                bounded_text_bytes = capture_receipt.text.encode("utf-8")
                _write_bytes_exclusive(
                    route_dir / "captured_text.txt",
                    bounded_text_bytes,
                )
            route_result = {
                "schema_version": ROUTE_RESULT_SCHEMA,
                "status": "FAIL",
                "route_id": route.route_id,
                "branch_id": route.branch_id,
                "official_url": route.official_url,
                "source_identity": route.source_identity.model_dump(mode="json"),
                "exact_url_bound": exact_url_bound,
                "identity_marker_groups_passed": identity_markers_passed,
                "content_marker_groups_passed": content_markers_passed,
                "matched_identity_markers": identity_matches,
                "matched_content_markers": content_matches,
                "bounded_text_characters": (
                    len(capture_receipt.text) if capture_receipt is not None else 0
                ),
                "bounded_text_bytes": len(bounded_text_bytes),
                "bounded_text_sha256": (
                    _sha256_bytes(bounded_text_bytes) if bounded_text_bytes else None
                ),
                "upstream_extracted_characters": (
                    capture_receipt.extracted_characters
                    if capture_receipt is not None
                    else 0
                ),
                "upstream_text_digest": (
                    capture_receipt.text_digest if capture_receipt is not None else None
                ),
                "truncated_to_qualification_limit": (
                    capture_receipt.truncated if capture_receipt is not None else False
                ),
                "discovery_receipt_digest": (
                    discovery_receipt.receipt_digest
                    if discovery_receipt is not None
                    else None
                ),
                "capture_receipt_digest": (
                    capture_receipt.receipt_digest
                    if capture_receipt is not None
                    else None
                ),
                "capture_method": (
                    capture_receipt.capture_method
                    if capture_receipt is not None
                    else None
                ),
                "candidate_is_not_evidence": True,
                "admission_required_before_citation": True,
                "source_capture_authority": False,
                "model_calls": 0,
                "failure_code": terminal_failure_code,
            }

        if discovery_receipt is not None:
            _write_json_exclusive(
                route_dir / "discovery_receipt.json",
                discovery_receipt.model_dump(mode="json"),
            )
        if capture_receipt is not None:
            _write_json_exclusive(
                route_dir / "capture_receipt.json",
                capture_receipt.model_dump(mode="json"),
            )
        route_result["route_result_digest"] = canonical_digest(route_result)
        _write_json_exclusive(route_dir / "route_result.json", route_result)
        route_results.append(route_result)
        if terminal_failure_code is not None:
            break

    completed_at = now()
    status = (
        "PASS"
        if terminal_failure_code is None and len(route_results) == len(config.routes)
        else "FAIL"
    )
    artifacts = _artifact_inventory(attempt_dir)
    manifest_body = {
        "schema_version": MANIFEST_SCHEMA,
        "status": status,
        "attempt_id": attempt_id,
        "case_id": config.case_id,
        "started_at": _iso(started_at),
        "completed_at": _iso(completed_at),
        "config_path": str(Path(config_path).expanduser().resolve()),
        "config_file_sha256": config_file_sha256,
        "config_contract_digest": config_contract_digest,
        "run_scope": run_scope.model_dump(mode="json"),
        "transport": config.transport,
        "exact_url_mode": True,
        "fail_fast": True,
        "declared_route_count": len(config.routes),
        "attempted_route_count": len(route_results),
        "passed_route_count": sum(row["status"] == "PASS" for row in route_results),
        "route_results": route_results,
        "terminal_failure_code": terminal_failure_code,
        "candidate_is_not_evidence": True,
        "admission_required_before_citation": True,
        "source_capture_authority": False,
        "evidence_admission_authorized": False,
        "mcp_promotion_authorized": False,
        "production_status": "HOLD",
        "model_calls_authorized": False,
        "model_calls": 0,
        "deepseek_calls": 0,
        "paid_calls": 0,
        "hosted_transport_internal_model_usage_observable": False,
        "implementation": {
            "runner_path": str(Path(__file__).resolve()),
            "runner_sha256": _sha256_file(Path(__file__).resolve()),
            "external_sources_path": str(
                SOURCE_ROOT
                / "sec_agent"
                / "research_foundation"
                / "external_sources.py"
            ),
            "external_sources_sha256": _sha256_file(
                SOURCE_ROOT
                / "sec_agent"
                / "research_foundation"
                / "external_sources.py"
            ),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
        },
        "artifacts": artifacts,
    }
    manifest = {
        **manifest_body,
        "manifest_digest": canonical_digest(manifest_body),
    }
    manifest_path = attempt_dir / "manifest.json"
    _write_json_exclusive(manifest_path, manifest)
    if status != "PASS":
        raise QualificationRunFailed(
            terminal_failure_code or "qualification_incomplete",
            manifest_path,
        )
    return manifest_path


def _default_attempt_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"dell_external_exact_url_zero_model_{timestamp}_r1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify four frozen Dell-case official URLs through Exa hosted "
            "full-text fetch without any model call or Evidence promotion."
        )
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--attempt-id", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    attempt_id = args.attempt_id or _default_attempt_id()
    try:
        manifest_path = asyncio.run(
            run_qualification(
                config_path=args.config,
                output_root=args.output_root,
                attempt_id=attempt_id,
            )
        )
    except QualificationRunFailed as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "failure_code": exc.code,
                    "manifest_path": str(exc.manifest_path),
                },
                ensure_ascii=False,
            )
        )
        return 2
    except QualificationError as exc:
        print(
            json.dumps(
                {"status": "FAIL", "failure_code": str(exc)},
                ensure_ascii=False,
            )
        )
        return 2
    print(
        json.dumps(
            {"status": "PASS", "manifest_path": str(manifest_path)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
