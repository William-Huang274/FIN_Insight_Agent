from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .profiles import SourceArtifactsProfile, WorkbenchProfile
from .source_readiness import SourceReadinessReport


class SourceBundleArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_path: str | None = None
    bm25_index_dir: str | None = None
    object_bm25_index_dir: str | None = None
    source_gap_path: str | None = None
    market_evidence_path: str | None = None


class SourceBundleBuild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: str
    scripts: list[str] = Field(default_factory=list)
    status: str = "imported"


class SourceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "finsight_source_bundle_v1"
    bundle_id: str
    display_name: str
    market: str = "US"
    coverage_theme: str = ""
    ticker_count: int = 0
    tickers_sample: list[str] = Field(default_factory=list)
    source_families: list[str] = Field(default_factory=list)
    as_of_date: str | None = None
    artifacts: SourceBundleArtifacts = Field(default_factory=SourceBundleArtifacts)
    build: SourceBundleBuild


def source_bundle_from_profile(
    profile: WorkbenchProfile,
    *,
    readiness: SourceReadinessReport | None = None,
    bundle_id: str | None = None,
    display_name: str | None = None,
) -> SourceBundle:
    resolved_bundle_id = _slug(bundle_id or profile.sources.market_snapshot_id or profile.profile_id)
    resolved_display_name = display_name or _default_display_name(profile, readiness)
    source_families = _source_families(profile, readiness)
    return SourceBundle(
        bundle_id=resolved_bundle_id,
        display_name=resolved_display_name,
        market=_infer_market(profile),
        coverage_theme=_coverage_theme(profile),
        ticker_count=_ticker_count(readiness),
        tickers_sample=_tickers_sample(readiness),
        source_families=source_families,
        as_of_date=_as_of_date(profile, readiness),
        artifacts=SourceBundleArtifacts(
            manifest_path=profile.sources.manifest_path,
            bm25_index_dir=profile.sources.bm25_index_dir,
            object_bm25_index_dir=profile.sources.object_bm25_index_dir,
            source_gap_path=profile.sources.source_gap_path,
            market_evidence_path=profile.sources.market_evidence_path,
        ),
        build=SourceBundleBuild(
            created_at=datetime.now().isoformat(timespec="seconds"),
            scripts=_build_scripts(profile),
            status=readiness.status if readiness else "imported",
        ),
    )


def profile_from_source_bundle(bundle: SourceBundle) -> WorkbenchProfile:
    return WorkbenchProfile(
        profile_id=f"{bundle.bundle_id}_profile",
        display_name=f"{bundle.display_name} 运行配置",
        sources=SourceArtifactsProfile(
            source_policy=_source_policy_from_bundle(bundle),
            manifest_path=bundle.artifacts.manifest_path,
            bm25_index_dir=bundle.artifacts.bm25_index_dir,
            object_bm25_index_dir=bundle.artifacts.object_bm25_index_dir,
            source_gap_path=bundle.artifacts.source_gap_path,
            market_evidence_path=bundle.artifacts.market_evidence_path,
            market_as_of_date=bundle.as_of_date,
        ),
    )


def _default_display_name(profile: WorkbenchProfile, readiness: SourceReadinessReport | None) -> str:
    parts = [profile.display_name or profile.profile_id]
    families = _source_families(profile, readiness)
    if families:
        parts.append("、".join(families))
    as_of_date = _as_of_date(profile, readiness)
    if as_of_date:
        parts.append(as_of_date)
    return " · ".join(part for part in parts if part)


def _source_families(profile: WorkbenchProfile, readiness: SourceReadinessReport | None) -> list[str]:
    families: list[str] = []
    forms = readiness.manifest.form_counts if readiness else {}
    if forms:
        if forms.get("10-K", 0) or forms.get("10-Q", 0):
            families.append("SEC 10-K/10-Q")
        elif profile.sources.manifest_path:
            families.append("SEC filings")
        if forms.get("8-K", 0):
            families.append("8-K earnings release")
    elif profile.sources.manifest_path:
        families.append("SEC filings")
    if profile.sources.source_gap_path and "8-K earnings release" not in families:
        families.append("8-K source gap")
    if profile.sources.market_evidence_path:
        families.append("market snapshot")
    return families or [profile.sources.source_policy]


def _build_scripts(profile: WorkbenchProfile) -> list[str]:
    scripts: list[str] = []
    if profile.sources.manifest_path:
        scripts.extend(["download_sec_filings", "build_sec_manifest", "build_sec_chunks"])
    if profile.sources.bm25_index_dir:
        scripts.append("build_bm25_index")
    if profile.sources.object_bm25_index_dir:
        scripts.append("build_object_bm25_index")
    if profile.sources.source_gap_path:
        scripts.extend(["download_sec_8k_earnings", "merge_sec_source_gaps"])
    if profile.sources.market_evidence_path:
        scripts.append("market/40_build_market_evidence_pack")
    return scripts


def _ticker_count(readiness: SourceReadinessReport | None) -> int:
    if not readiness:
        return 0
    return max(readiness.manifest.ticker_count, readiness.market_evidence.ticker_count)


def _tickers_sample(readiness: SourceReadinessReport | None) -> list[str]:
    if not readiness:
        return []
    return readiness.manifest.tickers_sample or readiness.market_evidence.tickers_sample


def _as_of_date(profile: WorkbenchProfile, readiness: SourceReadinessReport | None) -> str | None:
    if profile.sources.market_as_of_date:
        return profile.sources.market_as_of_date
    if readiness and readiness.market_evidence.as_of_dates:
        return _largest_count_key(readiness.market_evidence.as_of_dates)
    return None


def _coverage_theme(profile: WorkbenchProfile) -> str:
    return (profile.display_name or profile.profile_id).strip()


def _infer_market(profile: WorkbenchProfile) -> str:
    policy = profile.sources.source_policy.upper()
    if "SEC" in policy:
        return "US"
    return "unknown"


def _source_policy_from_bundle(bundle: SourceBundle) -> str:
    families = {item.lower() for item in bundle.source_families}
    if "market snapshot" in families:
        return "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT"
    if any("8-k" in item for item in families):
        return "SEC_PRIMARY_MIXED_WITH_8K"
    return "SEC_PRIMARY_MIXED_RECENT"


def _largest_count_key(values: dict[str, Any]) -> str | None:
    non_empty = {str(key): int(value) for key, value in values.items() if str(key)}
    if not non_empty:
        return None
    return max(non_empty.items(), key=lambda item: item[1])[0]


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip().lower())
    text = re.sub(r"_+", "_", text).strip("_.-")
    return text or "source_bundle"
