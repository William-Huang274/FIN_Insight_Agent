from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .profiles import WorkbenchProfile, resolve_profile_path


REQUIRED_FULL_SOURCE_FORMS = ("10-K", "10-Q", "8-K")
REQUIRED_FULL_SOURCE_FILING_TIERS = (
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
)
REQUIRED_MARKET_FIELDS = (
    "close_price",
    "market_cap",
    "return_3m",
    "relative_return_vs_benchmark_3m",
    "max_drawdown_3m",
    "volatility_3m",
    "pe_ttm",
    "ev_sales_ttm",
    "latest_10q_filing_return_5d",
)


class ArtifactPathStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str | None
    exists: bool
    required: bool
    kind: str
    status: str
    reason: str = ""


class ManifestSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exists: bool
    path: str | None = None
    row_count: int = 0
    ticker_count: int = 0
    tickers_sample: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    form_counts: dict[str, int] = Field(default_factory=dict)
    source_tier_counts: dict[str, int] = Field(default_factory=dict)
    period_counts: dict[str, int] = Field(default_factory=dict)
    parse_errors: list[str] = Field(default_factory=list)


class MarketEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exists: bool
    path: str | None = None
    row_count: int = 0
    ticker_count: int = 0
    tickers_sample: list[str] = Field(default_factory=list)
    snapshot_ids: dict[str, int] = Field(default_factory=dict)
    as_of_dates: dict[str, int] = Field(default_factory=dict)
    providers: dict[str, int] = Field(default_factory=dict)
    field_counts: dict[str, int] = Field(default_factory=dict)
    valuation_non_null_counts: dict[str, int] = Field(default_factory=dict)
    parse_errors: list[str] = Field(default_factory=list)


class IndustryEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exists: bool
    path: str | None = None
    row_count: int = 0
    source_families: dict[str, int] = Field(default_factory=dict)
    providers: dict[str, int] = Field(default_factory=dict)
    as_of_dates: dict[str, int] = Field(default_factory=dict)
    parse_errors: list[str] = Field(default_factory=list)


class SourceReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    profile_id: str
    source_policy: str
    require_full_source: bool
    paths: list[ArtifactPathStatus]
    manifest: ManifestSummary
    market_evidence: MarketEvidenceSummary
    industry_evidence: IndustryEvidenceSummary
    missing_required_forms: list[str] = Field(default_factory=list)
    missing_required_filing_tiers: list[str] = Field(default_factory=list)
    missing_market_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def validate_profile_sources(
    profile: WorkbenchProfile,
    *,
    repo_root: str | Path | None = None,
    require_full_source: bool | None = None,
) -> SourceReadinessReport:
    root = Path(repo_root or Path.cwd()).resolve()
    require_full = _requires_full_source(profile) if require_full_source is None else bool(require_full_source)
    market_required = _requires_market_snapshot(profile) or bool(profile.sources.market_evidence_path)
    industry_required = _requires_industry_snapshot(profile) or bool(profile.sources.industry_evidence_path)

    path_checks = _path_checks(profile, root, market_required=market_required, industry_required=industry_required)
    manifest_path = resolve_profile_path(root, profile.sources.manifest_path)
    market_path = resolve_profile_path(root, profile.sources.market_evidence_path)
    industry_path = resolve_profile_path(root, profile.sources.industry_evidence_path)
    manifest_summary = _manifest_summary(manifest_path)
    market_summary = _market_evidence_summary(market_path)
    industry_summary = _industry_evidence_summary(industry_path)

    warnings: list[str] = []
    errors: list[str] = []
    for item in path_checks:
        if item.status == "warn":
            warnings.append(f"{item.name}: {item.reason}")
        elif item.status == "fail":
            errors.append(f"{item.name}: {item.reason}")

    if manifest_summary.parse_errors:
        errors.extend([f"manifest: {error}" for error in manifest_summary.parse_errors])
    if market_summary.parse_errors:
        errors.extend([f"market_evidence: {error}" for error in market_summary.parse_errors])
    if industry_summary.parse_errors:
        errors.extend([f"industry_evidence: {error}" for error in industry_summary.parse_errors])

    missing_forms: list[str] = []
    missing_tiers: list[str] = []
    missing_market_fields: list[str] = []
    if require_full and manifest_summary.exists and not manifest_summary.parse_errors:
        missing_forms = [
            form
            for form in REQUIRED_FULL_SOURCE_FORMS
            if manifest_summary.form_counts.get(form, 0) <= 0
        ]
        missing_tiers = [
            tier
            for tier in REQUIRED_FULL_SOURCE_FILING_TIERS
            if manifest_summary.source_tier_counts.get(tier, 0) <= 0
        ]
        if missing_forms:
            warnings.append(f"manifest missing required forms: {', '.join(missing_forms)}")
        if missing_tiers:
            warnings.append(f"manifest missing required filing tiers: {', '.join(missing_tiers)}")

    if market_required and market_summary.exists and not market_summary.parse_errors:
        missing_market_fields = [
            field
            for field in REQUIRED_MARKET_FIELDS
            if market_summary.field_counts.get(field, 0) <= 0
        ]
        if missing_market_fields:
            warnings.append(f"market evidence missing fields: {', '.join(missing_market_fields)}")

    status = "fail" if errors else "warn" if warnings else "pass"
    return SourceReadinessReport(
        status=status,
        profile_id=profile.profile_id,
        source_policy=profile.sources.source_policy,
        require_full_source=require_full,
        paths=path_checks,
        manifest=manifest_summary,
        market_evidence=market_summary,
        industry_evidence=industry_summary,
        missing_required_forms=missing_forms,
        missing_required_filing_tiers=missing_tiers,
        missing_market_fields=missing_market_fields,
        warnings=warnings,
        errors=errors,
    )


def _path_checks(
    profile: WorkbenchProfile,
    repo_root: Path,
    *,
    market_required: bool,
    industry_required: bool,
) -> list[ArtifactPathStatus]:
    specs = [
        ("manifest", profile.sources.manifest_path, "file", True),
        ("bm25_index", profile.sources.bm25_index_dir, "directory", True),
        ("object_bm25_index", profile.sources.object_bm25_index_dir, "directory", True),
        ("source_gap", profile.sources.source_gap_path, "file", False),
        ("market_evidence", profile.sources.market_evidence_path, "file", market_required),
        ("market_catalog", profile.sources.market_catalog_path, "file", bool(profile.sources.market_catalog_path)),
        ("industry_evidence", profile.sources.industry_evidence_path, "file", industry_required),
        ("industry_snapshot_db", profile.sources.industry_snapshot_db_path, "file", bool(profile.sources.industry_snapshot_db_path)),
    ]
    return [_path_status(name, value, kind, required, repo_root) for name, value, kind, required in specs]


def _path_status(name: str, value: str | None, kind: str, required: bool, repo_root: Path) -> ArtifactPathStatus:
    path = resolve_profile_path(repo_root, value)
    if path is None:
        return ArtifactPathStatus(
            name=name,
            path=None,
            exists=False,
            required=required,
            kind=kind,
            status="warn" if required else "pass",
            reason="not_configured" if required else "",
        )
    exists = path.exists()
    type_ok = path.is_dir() if kind == "directory" else path.is_file()
    if exists and type_ok:
        status = "pass"
        reason = ""
    elif exists:
        status = "fail"
        reason = f"expected_{kind}"
    elif required:
        status = "warn"
        reason = "missing"
    else:
        status = "pass"
        reason = "missing_optional"
    return ArtifactPathStatus(
        name=name,
        path=str(path),
        exists=exists and type_ok,
        required=required,
        kind=kind,
        status=status,
        reason=reason,
    )


def _manifest_summary(path: Path | None) -> ManifestSummary:
    if path is None or not path.exists():
        return ManifestSummary(exists=False, path=str(path) if path else None)
    rows, errors = _read_jsonl(path)
    form_counts = Counter(_normalize_form(row.get("form_type") or row.get("form") or row.get("source_type")) for row in rows)
    source_tiers = Counter(str(row.get("source_tier") or "") for row in rows)
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    years = sorted(
        {
            value
            for value in (
                _safe_int(row.get("fiscal_year") or row.get("document_fiscal_year_focus") or row.get("year"))
                for row in rows
            )
            if value is not None
        }
    )
    periods = Counter(str(row.get("period_role") or row.get("fiscal_period") or row.get("period_type") or "") for row in rows)
    return ManifestSummary(
        exists=True,
        path=str(path),
        row_count=len(rows),
        ticker_count=len(tickers),
        tickers_sample=tickers[:12],
        years=years,
        form_counts=dict(sorted((key, value) for key, value in form_counts.items() if key)),
        source_tier_counts=dict(sorted((key, value) for key, value in source_tiers.items() if key)),
        period_counts=dict(sorted((key, value) for key, value in periods.items() if key)),
        parse_errors=errors,
    )


def _market_evidence_summary(path: Path | None) -> MarketEvidenceSummary:
    if path is None or not path.exists():
        return MarketEvidenceSummary(exists=False, path=str(path) if path else None)
    rows, errors = _read_jsonl(path)
    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    snapshots = Counter(str(row.get("snapshot_id") or "") for row in rows)
    as_of_dates = Counter(str(row.get("as_of_date") or "") for row in rows)
    providers = Counter(str(row.get("provider") or "") for row in rows)
    field_counts: Counter[str] = Counter()
    valuation_non_null: Counter[str] = Counter()
    valuation_fields = {"pe_ttm", "ev_sales_ttm", "ev_ebitda_ttm"}
    for row in rows:
        for field, value in _iter_market_fields(row):
            field_counts[field] += 1
            if field in valuation_fields and value is not None:
                valuation_non_null[field] += 1
    return MarketEvidenceSummary(
        exists=True,
        path=str(path),
        row_count=len(rows),
        ticker_count=len(tickers),
        tickers_sample=tickers[:12],
        snapshot_ids=dict(sorted((key, value) for key, value in snapshots.items() if key)),
        as_of_dates=dict(sorted((key, value) for key, value in as_of_dates.items() if key)),
        providers=dict(sorted((key, value) for key, value in providers.items() if key)),
        field_counts=dict(sorted(field_counts.items())),
        valuation_non_null_counts=dict(sorted(valuation_non_null.items())),
        parse_errors=errors,
    )


def _industry_evidence_summary(path: Path | None) -> IndustryEvidenceSummary:
    if path is None or not path.exists():
        return IndustryEvidenceSummary(exists=False, path=str(path) if path else None)
    rows, errors = _read_jsonl(path)
    source_families = Counter(str(row.get("source_family") or "") for row in rows)
    providers = Counter(str(row.get("provider") or "") for row in rows)
    as_of_dates = Counter(str(row.get("as_of_date") or "") for row in rows)
    return IndustryEvidenceSummary(
        exists=True,
        path=str(path),
        row_count=len(rows),
        source_families=dict(sorted((key, value) for key, value in source_families.items() if key)),
        providers=dict(sorted((key, value) for key, value in providers.items() if key)),
        as_of_dates=dict(sorted((key, value) for key, value in as_of_dates.items() if key)),
        parse_errors=errors,
    )


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: {exc.msg}")
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        else:
            errors.append(f"line {line_number}: expected object")
    return rows, errors


def _iter_market_fields(row: dict[str, Any]) -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = []
    for ref in row.get("field_refs") or []:
        if isinstance(ref, dict) and ref.get("field_name"):
            fields.append((str(ref["field_name"]), ref.get("value")))
    for key in REQUIRED_MARKET_FIELDS:
        if key in row:
            fields.append((key, row.get(key)))
    return fields


def _requires_full_source(profile: WorkbenchProfile) -> bool:
    policy = str(profile.sources.source_policy or "").upper()
    return "WITH_8K" in policy or "FULL_SOURCE" in policy or "MARKET_SNAPSHOT" in policy


def _requires_market_snapshot(profile: WorkbenchProfile) -> bool:
    policy = str(profile.sources.source_policy or "").upper()
    return "MARKET" in policy


def _requires_industry_snapshot(profile: WorkbenchProfile) -> bool:
    policy = str(profile.sources.source_policy or "").upper()
    return "INDUSTRY" in policy


def _normalize_form(value: Any) -> str:
    return str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q").replace("8K", "8-K")


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except Exception:
        return None
