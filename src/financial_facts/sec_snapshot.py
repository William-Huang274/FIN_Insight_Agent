from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
import requests


SEC_SNAPSHOT_INPUT_SCHEMA_VERSION = "fin_ia_sec_snapshot_input_v1_0"
SEC_SNAPSHOT_RESULT_SCHEMA_VERSION = "fin_ia_sec_snapshot_result_v1_0"
SEC_SNAPSHOT_SOURCE_METADATA_SCHEMA_VERSION = (
    "fin_ia_sec_snapshot_source_metadata_v1_0"
)
SEC_SNAPSHOT_FAILURE_SCHEMA_VERSION = "fin_ia_sec_snapshot_failure_v1_0"

COMPANYFACTS_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)
SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"

HARD_MAXIMUM_COMPANIES = 16
MINIMUM_TIMEOUT_SECONDS = 1
MAXIMUM_TIMEOUT_SECONDS = 60
MINIMUM_REQUESTS_PER_SECOND = 0.1
MAXIMUM_REQUESTS_PER_SECOND = 2.0
MINIMUM_RESPONSE_BYTES = 1_024
MAXIMUM_RESPONSE_BYTES = 32 * 1024 * 1024

_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_PLACEHOLDER_EMAIL_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "invalid",
        "localhost",
        "test.com",
    }
)


class SecSnapshotError(RuntimeError):
    """Typed, non-secret-bearing SEC snapshot failure."""

    def __init__(
        self,
        code: str,
        *,
        failure_receipt: Path | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.failure_receipt = failure_receipt


class SecSnapshotCompany(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,9}$")
    cik: str = Field(pattern=r"^[0-9]{10}$")
    legal_name: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_legal_name(self) -> "SecSnapshotCompany":
        if self.legal_name != self.legal_name.strip():
            raise ValueError("sec_snapshot_legal_name_not_trimmed")
        if any(ord(character) < 32 for character in self.legal_name):
            raise ValueError("sec_snapshot_legal_name_control_character")
        return self


class SecSnapshotInputManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    companies: tuple[SecSnapshotCompany, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> "SecSnapshotInputManifest":
        if self.schema_version != SEC_SNAPSHOT_INPUT_SCHEMA_VERSION:
            raise ValueError("sec_snapshot_input_schema_invalid")
        if not self.companies:
            raise ValueError("sec_snapshot_companies_empty")
        if len(self.companies) > HARD_MAXIMUM_COMPANIES:
            raise ValueError("sec_snapshot_company_hard_ceiling_exceeded")
        tickers = [company.ticker for company in self.companies]
        ciks = [company.cik for company in self.companies]
        if len(tickers) != len(set(tickers)):
            raise ValueError("sec_snapshot_ticker_duplicate")
        if len(ciks) != len(set(ciks)):
            raise ValueError("sec_snapshot_cik_duplicate")
        return self


class SecSnapshotRequestPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    timeout_seconds: int = Field(
        ge=MINIMUM_TIMEOUT_SECONDS,
        le=MAXIMUM_TIMEOUT_SECONDS,
    )
    requests_per_second: float = Field(
        ge=MINIMUM_REQUESTS_PER_SECOND,
        le=MAXIMUM_REQUESTS_PER_SECOND,
    )
    maximum_companies: int = Field(ge=1, le=HARD_MAXIMUM_COMPANIES)
    maximum_response_bytes: int = Field(
        ge=MINIMUM_RESPONSE_BYTES,
        le=MAXIMUM_RESPONSE_BYTES,
    )
    per_source_attempts: int = Field(default=1, ge=1, le=1)


class SecSnapshotArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ticker: str
    cik: str
    source_entity_name: str = Field(min_length=1, max_length=240)
    source_kind: str
    source_url: str
    raw_ref: str
    metadata_ref: str
    canonical_json_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_response_bytes: int = Field(gt=0)
    content_type: str
    downloaded_at_utc: str


class SecSnapshotBuilderSourceBinding(BaseModel):
    """Shape consumed by ``CompanySourceBinding`` in a successor policy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ticker: str
    cik: str
    legal_name: str
    companyfacts_ref: str
    companyfacts_metadata_ref: str
    companyfacts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    submissions_ref: str
    submissions_metadata_ref: str
    submissions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SecSnapshotResultManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str
    status: str
    attempt_id: str
    captured_at_utc: str
    input_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    official_hosts: tuple[str, ...]
    request_policy: SecSnapshotRequestPolicy
    company_count: int = Field(gt=0)
    source_count: int = Field(gt=0)
    artifacts: tuple[SecSnapshotArtifact, ...]
    builder_source_bindings: tuple[SecSnapshotBuilderSourceBinding, ...]
    capture_only_no_normalization: bool
    source_capture_authority: bool
    evidence_or_numeric_fact_admission_performed: bool
    contact_configured_not_persisted: bool
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result(self) -> "SecSnapshotResultManifest":
        if self.schema_version != SEC_SNAPSHOT_RESULT_SCHEMA_VERSION:
            raise ValueError("sec_snapshot_result_schema_invalid")
        if self.status != "complete":
            raise ValueError("sec_snapshot_result_status_invalid")
        if self.official_hosts != ("data.sec.gov",):
            raise ValueError("sec_snapshot_result_host_invalid")
        if self.source_count != self.company_count * 2:
            raise ValueError("sec_snapshot_result_source_count_invalid")
        if len(self.artifacts) != self.source_count:
            raise ValueError("sec_snapshot_result_artifact_count_invalid")
        if len(self.builder_source_bindings) != self.company_count:
            raise ValueError("sec_snapshot_result_binding_count_invalid")
        if not self.capture_only_no_normalization:
            raise ValueError("sec_snapshot_result_capture_boundary_invalid")
        if self.source_capture_authority:
            raise ValueError("sec_snapshot_result_authority_invalid")
        if self.evidence_or_numeric_fact_admission_performed:
            raise ValueError("sec_snapshot_result_admission_invalid")
        if not self.contact_configured_not_persisted:
            raise ValueError("sec_snapshot_result_contact_boundary_invalid")
        unsigned = self.model_dump(mode="json", exclude={"manifest_digest"})
        if self.manifest_digest != canonical_digest(unsigned):
            raise ValueError("sec_snapshot_result_digest_invalid")
        return self


class _Response(Protocol):
    status_code: int
    content: bytes
    headers: Mapping[str, str]
    url: str


class _Session(Protocol):
    def get(self, url: str, **kwargs: Any) -> _Response: ...

    def close(self) -> None: ...


def canonical_digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def canonical_sec_payload_digest(payload: Mapping[str, Any]) -> str:
    """Match the logical digest verified by ``sec_companyfacts.py``."""

    return sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def load_sec_snapshot_input_manifest(
    value: str | bytes | Path | Mapping[str, Any],
) -> SecSnapshotInputManifest:
    if isinstance(value, Path):
        return SecSnapshotInputManifest.model_validate_json(value.read_bytes())
    if isinstance(value, bytes):
        return SecSnapshotInputManifest.model_validate_json(value)
    if isinstance(value, str):
        return SecSnapshotInputManifest.model_validate_json(value)
    return SecSnapshotInputManifest.model_validate(value)


def load_sec_snapshot_result_manifest(
    value: str | bytes | Path | Mapping[str, Any],
) -> SecSnapshotResultManifest:
    if isinstance(value, Path):
        return SecSnapshotResultManifest.model_validate_json(value.read_bytes())
    if isinstance(value, bytes):
        return SecSnapshotResultManifest.model_validate_json(value)
    if isinstance(value, str):
        return SecSnapshotResultManifest.model_validate_json(value)
    return SecSnapshotResultManifest.model_validate(value)


def build_s2_successor_policy_from_sec_snapshot(
    baseline_policy: Mapping[str, Any],
    snapshot: SecSnapshotResultManifest,
    *,
    snapshot_root: str | Path,
    research_as_of: str,
) -> dict[str, Any]:
    """Bind a current SEC snapshot and explicitly advance S2 research time.

    The baseline remains the sole authority for metric definitions, qrels,
    temporal settings, and financial rules.  Snapshot-relative references are
    resolved against the exact attempt root supplied by the caller and emitted
    as absolute paths because the existing S2 builder executes from the
    repository root.
    """

    # Import locally to keep the capture module's dependency surface narrow and
    # to validate both predecessor and successor with the existing S2 contract.
    from .sec_companyfacts import load_company_fact_mart_policy

    load_company_fact_mart_policy(baseline_policy)
    root = Path(snapshot_root).resolve()
    if not root.is_dir():
        raise ValueError("sec_snapshot_s2_bridge_root_invalid")

    source_bindings: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()
    for binding in snapshot.builder_source_bindings:
        if binding.ticker in seen_tickers:
            raise ValueError("sec_snapshot_s2_bridge_ticker_duplicate")
        seen_tickers.add(binding.ticker)
        source_bindings.append(
            {
                "ticker": binding.ticker,
                "cik": binding.cik,
                # This is the CompanyFacts entityName observed and frozen by
                # the snapshot capture, not a bridge-time normalization.
                "legal_name": binding.legal_name,
                "companyfacts_ref": _snapshot_bound_ref(
                    root, binding.companyfacts_ref
                ),
                "companyfacts_metadata_ref": _snapshot_bound_ref(
                    root, binding.companyfacts_metadata_ref
                ),
                "companyfacts_sha256": binding.companyfacts_sha256,
                "submissions_ref": _snapshot_bound_ref(
                    root, binding.submissions_ref
                ),
                "submissions_metadata_ref": _snapshot_bound_ref(
                    root, binding.submissions_metadata_ref
                ),
                "submissions_sha256": binding.submissions_sha256,
            }
        )

    successor = {
        **dict(baseline_policy),
        "research_as_of": _policy_research_date(research_as_of).isoformat(),
        "source_bindings": source_bindings,
    }
    load_company_fact_mart_policy(successor)
    seal_s2_successor_policy_change_receipt(
        baseline_policy,
        successor,
        snapshot_root=root,
    )
    return successor


def seal_s2_successor_policy_change_receipt(
    baseline_policy: Mapping[str, Any],
    successor_policy: Mapping[str, Any],
    *,
    snapshot_root: str | Path,
) -> dict[str, Any]:
    """Fail closed unless only sources and top-level research time changed."""

    from .sec_companyfacts import (
        load_company_fact_mart_policy,
        parse_policy_sources,
    )

    baseline = dict(baseline_policy)
    successor = dict(successor_policy)
    load_company_fact_mart_policy(baseline)
    successor_contract = load_company_fact_mart_policy(successor)
    if set(baseline) != set(successor):
        raise ValueError("sec_snapshot_s2_bridge_policy_field_drift")
    changed_fields = tuple(
        sorted(key for key in baseline if baseline[key] != successor[key])
    )
    allowed_changes = ("research_as_of", "source_bindings")
    preserved_before = {
        key: baseline[key] for key in baseline if key not in allowed_changes
    }
    preserved_after = {
        key: successor[key] for key in successor if key not in allowed_changes
    }
    if preserved_before != preserved_after:
        raise ValueError("sec_snapshot_s2_bridge_policy_rule_drift")
    if changed_fields != allowed_changes:
        raise ValueError("sec_snapshot_s2_bridge_policy_field_drift")

    baseline_date = _policy_research_date(str(baseline["research_as_of"]))
    successor_date = _policy_research_date(str(successor["research_as_of"]))
    if successor_date < baseline_date:
        raise ValueError("sec_snapshot_s2_bridge_research_as_of_regressed")
    if successor_date == baseline_date:
        raise ValueError("sec_snapshot_s2_bridge_research_as_of_not_advanced")

    root = Path(snapshot_root).resolve()
    if not root.is_dir():
        raise ValueError("sec_snapshot_s2_bridge_root_invalid")
    observations, _ = parse_policy_sources(
        successor_contract,
        repository_root=root,
    )
    latest_accepted_at = max(
        (row.accepted_at for row in observations),
        key=_accepted_at_datetime,
        default=None,
    )
    if latest_accepted_at is not None:
        latest_accepted_date = _accepted_at_datetime(latest_accepted_at).date()
        if successor_date < latest_accepted_date:
            raise ValueError(
                "sec_snapshot_s2_bridge_research_as_of_before_snapshot_fact"
            )

    unsigned = {
        "schema_version": "fin_ia_sec_snapshot_s2_policy_change_receipt_v1_0",
        "allowed_changed_fields": list(allowed_changes),
        "changed_fields": list(changed_fields),
        "baseline_policy_digest": canonical_digest(baseline),
        "successor_policy_digest": canonical_digest(successor),
        "baseline_research_as_of": baseline_date.isoformat(),
        "successor_research_as_of": successor_date.isoformat(),
        "baseline_source_bindings_digest": canonical_digest(
            baseline["source_bindings"]
        ),
        "successor_source_bindings_digest": canonical_digest(
            successor["source_bindings"]
        ),
        "preserved_policy_fields": sorted(preserved_before),
        "preserved_policy_digest": canonical_digest(preserved_before),
        "latest_snapshot_fact_accepted_at": latest_accepted_at,
        "research_as_of_covers_latest_snapshot_fact": True,
        "metric_qrel_temporal_finance_rules_preserved": True,
    }
    return {**unsigned, "receipt_digest": canonical_digest(unsigned)}


def _policy_research_date(value: str) -> date:
    normalized = value.strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("sec_snapshot_s2_bridge_research_as_of_invalid") from exc
    if parsed.isoformat() != normalized:
        raise ValueError("sec_snapshot_s2_bridge_research_as_of_invalid")
    return parsed


def _accepted_at_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("sec_snapshot_s2_bridge_accepted_at_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("sec_snapshot_s2_bridge_accepted_at_timezone_required")
    return parsed


def _snapshot_bound_ref(snapshot_root: Path, value: str) -> str:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (snapshot_root / path).resolve()
    try:
        resolved.relative_to(snapshot_root)
    except ValueError as exc:
        raise ValueError("sec_snapshot_s2_bridge_ref_outside_snapshot") from exc
    if not resolved.is_file():
        raise ValueError("sec_snapshot_s2_bridge_ref_missing")
    return str(resolved)


def sec_user_agent_from_environment(
    environment: Mapping[str, str] | None = None,
) -> str:
    source = os.environ if environment is None else environment
    contact = str(source.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not _valid_contact_email(contact):
        raise SecSnapshotError("sec_snapshot_real_contact_email_required")
    return f"FIN-Insight-Agent/0.1.3 ({contact})"


def capture_sec_companyfacts_snapshot(
    manifest: SecSnapshotInputManifest,
    *,
    output_root: str | Path,
    request_policy: SecSnapshotRequestPolicy,
    environment: Mapping[str, str] | None = None,
    session: _Session | None = None,
    now_utc: Callable[[], datetime] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> SecSnapshotResultManifest:
    if len(manifest.companies) > request_policy.maximum_companies:
        raise SecSnapshotError("sec_snapshot_company_execution_ceiling_exceeded")

    root = Path(output_root).resolve()
    input_payload = manifest.model_dump(mode="json")
    input_digest = canonical_digest(input_payload)
    _claim_attempt_root(
        root,
        {
            "schema_version": "fin_ia_sec_snapshot_attempt_start_v1_0",
            "status": "started",
            "attempt_id": manifest.attempt_id,
            "input_manifest": input_payload,
            "input_manifest_digest": input_digest,
            "company_count": len(manifest.companies),
            "source_count": len(manifest.companies) * 2,
            "request_policy": request_policy.model_dump(mode="json"),
            "contact_required_not_persisted": True,
        },
    )

    clock = now_utc or (lambda: datetime.now(timezone.utc))
    client_session = session or requests.Session()
    owns_session = session is None
    artifacts: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    active_source: dict[str, str] | None = None
    try:
        user_agent = sec_user_agent_from_environment(environment)
        limiter = _RateLimiter(
            requests_per_second=request_policy.requests_per_second,
            monotonic=monotonic,
            sleep=sleep,
        )
        for company in sorted(manifest.companies, key=lambda row: row.ticker):
            by_kind: dict[str, dict[str, Any]] = {}
            for source_kind, url in _source_urls(company.cik):
                active_source = {
                    "ticker": company.ticker,
                    "cik": company.cik,
                    "source_kind": source_kind,
                    "source_url": url,
                }
                limiter.wait()
                capture = _capture_one_source(
                    session=client_session,
                    company=company,
                    source_kind=source_kind,
                    source_url=url,
                    output_root=root,
                    request_policy=request_policy,
                    user_agent=user_agent,
                    downloaded_at_utc=_iso_utc(clock()),
                )
                artifacts.append(capture["artifact"])
                by_kind[source_kind] = capture
            bindings.append(
                {
                    "ticker": company.ticker,
                    "cik": company.cik,
                    # The existing S2 parser binds this field to the exact
                    # CompanyFacts ``entityName``.  SEC display names are
                    # versioned metadata, not the CIK identity, so consume the
                    # observed official value instead of inventing a name
                    # normalization layer.
                    "legal_name": by_kind["sec_companyfacts"]["artifact"][
                        "source_entity_name"
                    ],
                    "companyfacts_ref": by_kind["sec_companyfacts"]["raw_path"],
                    "companyfacts_metadata_ref": by_kind["sec_companyfacts"][
                        "metadata_path"
                    ],
                    "companyfacts_sha256": by_kind["sec_companyfacts"][
                        "canonical_json_sha256"
                    ],
                    "submissions_ref": by_kind["sec_submissions"]["raw_path"],
                    "submissions_metadata_ref": by_kind["sec_submissions"][
                        "metadata_path"
                    ],
                    "submissions_sha256": by_kind["sec_submissions"][
                        "canonical_json_sha256"
                    ],
                }
            )

        captured_at = _iso_utc(clock())
        unsigned = {
            "schema_version": SEC_SNAPSHOT_RESULT_SCHEMA_VERSION,
            "status": "complete",
            "attempt_id": manifest.attempt_id,
            "captured_at_utc": captured_at,
            "input_manifest_digest": input_digest,
            "official_hosts": ("data.sec.gov",),
            "request_policy": request_policy.model_dump(mode="json"),
            "company_count": len(manifest.companies),
            "source_count": len(artifacts),
            "artifacts": tuple(artifacts),
            "builder_source_bindings": tuple(bindings),
            "capture_only_no_normalization": True,
            "source_capture_authority": False,
            "evidence_or_numeric_fact_admission_performed": False,
            "contact_configured_not_persisted": True,
        }
        result_payload = {**unsigned, "manifest_digest": canonical_digest(unsigned)}
        result = SecSnapshotResultManifest.model_validate(result_payload)
        _atomic_write_json(root / "snapshot-manifest.json", result.model_dump(mode="json"))
        return result
    except Exception as exc:
        code = exc.code if isinstance(exc, SecSnapshotError) else _failure_code(exc)
        receipt_path = root / "terminal-failure-receipt.json"
        unsigned_failure = {
            "schema_version": SEC_SNAPSHOT_FAILURE_SCHEMA_VERSION,
            "status": "failed",
            "attempt_id": manifest.attempt_id,
            "failed_at_utc": _iso_utc(clock()),
            "input_manifest_digest": input_digest,
            "failure_code": code,
            "failed_source": active_source,
            "completed_source_count": len(artifacts),
            "expected_source_count": len(manifest.companies) * 2,
            "complete_files_preserved": True,
            "snapshot_manifest_created": False,
            "contact_value_persisted": False,
        }
        _atomic_write_json(
            receipt_path,
            {
                **unsigned_failure,
                "receipt_digest": canonical_digest(unsigned_failure),
            },
        )
        raise SecSnapshotError(code, failure_receipt=receipt_path) from exc
    finally:
        if owns_session:
            client_session.close()


class _RateLimiter:
    def __init__(
        self,
        *,
        requests_per_second: float,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        self._minimum_interval = 1.0 / requests_per_second
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_request_at: float | None = None

    def wait(self) -> None:
        current = self._monotonic()
        if self._last_request_at is not None:
            remaining = self._minimum_interval - (current - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
                current = self._monotonic()
        self._last_request_at = current


def _capture_one_source(
    *,
    session: _Session,
    company: SecSnapshotCompany,
    source_kind: str,
    source_url: str,
    output_root: Path,
    request_policy: SecSnapshotRequestPolicy,
    user_agent: str,
    downloaded_at_utc: str,
) -> dict[str, Any]:
    try:
        response = session.get(
            source_url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": user_agent,
            },
            timeout=request_policy.timeout_seconds,
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise SecSnapshotError("sec_snapshot_transport_timeout") from exc
    except requests.RequestException as exc:
        raise SecSnapshotError("sec_snapshot_transport_failure") from exc
    except Exception as exc:
        raise SecSnapshotError("sec_snapshot_transport_failure") from exc

    if int(response.status_code) != 200:
        raise SecSnapshotError("sec_snapshot_http_status_invalid")
    response_url = str(getattr(response, "url", "") or source_url)
    if response_url != source_url:
        raise SecSnapshotError("sec_snapshot_response_url_drift")
    content_type = _header(response.headers, "content-type")
    if not content_type.lower().split(";", 1)[0].strip() == "application/json":
        raise SecSnapshotError("sec_snapshot_content_type_invalid")
    raw = bytes(response.content)
    if not raw:
        raise SecSnapshotError("sec_snapshot_response_empty")
    if len(raw) > request_policy.maximum_response_bytes:
        raise SecSnapshotError("sec_snapshot_response_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecSnapshotError("sec_snapshot_json_invalid") from exc
    if not isinstance(payload, Mapping):
        raise SecSnapshotError("sec_snapshot_json_object_required")
    source_entity_name = _validate_source_identity(
        payload,
        company=company,
        source_kind=source_kind,
    )

    canonical_json_sha256 = canonical_sec_payload_digest(payload)
    raw_response_sha256 = sha256(raw).hexdigest()
    company_root = output_root / "raw" / company.ticker
    stem = source_kind
    raw_path = company_root / f"{stem}.json"
    metadata_path = company_root / f"{stem}.metadata.json"
    metadata = {
        "schema_version": SEC_SNAPSHOT_SOURCE_METADATA_SCHEMA_VERSION,
        "plan_id": f"SEC-SNAPSHOT::{company.ticker}::{source_kind.upper()}",
        "ticker": company.ticker,
        "cik": company.cik,
        "cik10": company.cik,
        "legal_name": company.legal_name,
        "source_entity_name": source_entity_name,
        "fact_source": source_kind,
        "source_url": source_url,
        "content_type": content_type,
        "byte_count": len(raw),
        "raw_response_sha256": raw_response_sha256,
        "canonical_json_sha256": canonical_json_sha256,
        "sha256": canonical_json_sha256,
        "downloaded_at_utc": downloaded_at_utc,
        "http_status": 200,
        "redirects_followed": 0,
        "cache_status": "downloaded_new_attempt",
        "capture_only_no_normalization": True,
    }
    _atomic_write_bytes(raw_path, raw)
    _atomic_write_json(metadata_path, metadata)
    artifact = {
        "ticker": company.ticker,
        "cik": company.cik,
        "source_entity_name": source_entity_name,
        "source_kind": source_kind,
        "source_url": source_url,
        "raw_ref": raw_path.relative_to(output_root).as_posix(),
        "metadata_ref": metadata_path.relative_to(output_root).as_posix(),
        "canonical_json_sha256": canonical_json_sha256,
        "raw_response_sha256": raw_response_sha256,
        "raw_response_bytes": len(raw),
        "content_type": content_type,
        "downloaded_at_utc": downloaded_at_utc,
    }
    return {
        "artifact": artifact,
        "raw_path": str(raw_path),
        "metadata_path": str(metadata_path),
        "canonical_json_sha256": canonical_json_sha256,
    }


def _source_urls(cik: str) -> tuple[tuple[str, str], ...]:
    return (
        (
            "sec_companyfacts",
            COMPANYFACTS_URL_TEMPLATE.format(cik=cik),
        ),
        (
            "sec_submissions",
            SUBMISSIONS_URL_TEMPLATE.format(cik=cik),
        ),
    )


def _validate_source_identity(
    payload: Mapping[str, Any],
    *,
    company: SecSnapshotCompany,
    source_kind: str,
) -> str:
    try:
        payload_cik = str(int(str(payload.get("cik")))).zfill(10)
    except (TypeError, ValueError) as exc:
        raise SecSnapshotError("sec_snapshot_payload_cik_invalid") from exc
    if payload_cik != company.cik:
        raise SecSnapshotError("sec_snapshot_payload_cik_mismatch")
    if source_kind == "sec_companyfacts":
        name = str(payload.get("entityName") or "")
        if not isinstance(payload.get("facts"), Mapping):
            raise SecSnapshotError("sec_snapshot_companyfacts_shape_invalid")
    elif source_kind == "sec_submissions":
        name = str(payload.get("name") or "")
        filings = payload.get("filings")
        if not isinstance(filings, Mapping) or not isinstance(
            filings.get("recent"), Mapping
        ):
            raise SecSnapshotError("sec_snapshot_submissions_shape_invalid")
    else:  # pragma: no cover - source kinds are internal constants
        raise SecSnapshotError("sec_snapshot_source_kind_invalid")
    if not name or name != name.strip() or any(ord(character) < 32 for character in name):
        raise SecSnapshotError("sec_snapshot_payload_entity_name_invalid")
    return name


def _claim_attempt_root(root: Path, start_receipt: Mapping[str, Any]) -> None:
    if root.exists():
        if not root.is_dir():
            raise SecSnapshotError("sec_snapshot_output_root_not_directory")
        try:
            next(root.iterdir())
        except StopIteration:
            pass
        else:
            raise SecSnapshotError("sec_snapshot_output_root_not_empty")
    else:
        try:
            root.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise SecSnapshotError("sec_snapshot_output_root_race") from exc
    try:
        _exclusive_write_json(root / "attempt-start.json", start_receipt)
    except FileExistsError as exc:
        raise SecSnapshotError("sec_snapshot_output_root_claimed") from exc


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, encoded)


def _atomic_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SecSnapshotError("sec_snapshot_output_target_exists")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            raise SecSnapshotError("sec_snapshot_output_target_race")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _exclusive_write_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _valid_contact_email(value: str) -> bool:
    if not value or not _EMAIL_PATTERN.fullmatch(value):
        return False
    local, domain = value.rsplit("@", 1)
    lowered_domain = domain.lower()
    lowered_local = local.lower()
    if lowered_domain in _PLACEHOLDER_EMAIL_DOMAINS:
        return False
    if lowered_domain.endswith((".example", ".invalid", ".localhost", ".test")):
        return False
    if lowered_local in {"contact", "email", "name", "user", "your.email"}:
        return False
    return True


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return str(value)
    return ""


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise SecSnapshotError("sec_snapshot_clock_timezone_required")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, requests.Timeout):
        return "sec_snapshot_transport_timeout"
    if isinstance(exc, requests.RequestException):
        return "sec_snapshot_transport_failure"
    return "sec_snapshot_internal_failure"


__all__ = [
    "COMPANYFACTS_URL_TEMPLATE",
    "HARD_MAXIMUM_COMPANIES",
    "MAXIMUM_RESPONSE_BYTES",
    "MAXIMUM_REQUESTS_PER_SECOND",
    "MAXIMUM_TIMEOUT_SECONDS",
    "SEC_SNAPSHOT_FAILURE_SCHEMA_VERSION",
    "SEC_SNAPSHOT_INPUT_SCHEMA_VERSION",
    "SEC_SNAPSHOT_RESULT_SCHEMA_VERSION",
    "SEC_SNAPSHOT_SOURCE_METADATA_SCHEMA_VERSION",
    "SUBMISSIONS_URL_TEMPLATE",
    "SecSnapshotArtifact",
    "SecSnapshotBuilderSourceBinding",
    "SecSnapshotCompany",
    "SecSnapshotError",
    "SecSnapshotInputManifest",
    "SecSnapshotRequestPolicy",
    "SecSnapshotResultManifest",
    "canonical_digest",
    "canonical_sec_payload_digest",
    "build_s2_successor_policy_from_sec_snapshot",
    "capture_sec_companyfacts_snapshot",
    "load_sec_snapshot_input_manifest",
    "load_sec_snapshot_result_manifest",
    "seal_s2_successor_policy_change_receipt",
    "sec_user_agent_from_environment",
]
