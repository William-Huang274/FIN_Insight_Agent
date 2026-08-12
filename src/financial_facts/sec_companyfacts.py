from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from retrieval.query_plan import canonical_digest

from .contracts import CompanyFactObservation, MetricDefinition


POLICY_SCHEMA_VERSION = "fin_ia_s2_company_financial_fact_mart_policy_v1_0"


class CompanyFactSourceError(ValueError):
    """Raised when a source capture cannot support authoritative facts."""


@dataclass(frozen=True)
class CompanySourceBinding:
    ticker: str
    cik: str
    legal_name: str
    companyfacts_ref: str
    companyfacts_metadata_ref: str
    companyfacts_sha256: str
    submissions_ref: str
    submissions_metadata_ref: str
    submissions_sha256: str


@dataclass(frozen=True)
class CompanyFactMartPolicy:
    recorded_at: str
    research_as_of: str
    minimum_period_end: str
    allowed_forms: tuple[str, ...]
    sources: tuple[CompanySourceBinding, ...]
    metrics: tuple[MetricDefinition, ...]
    acceptance_qrels: tuple[Mapping[str, Any], ...]
    authority: Mapping[str, Any]


@dataclass(frozen=True)
class FilingIdentity:
    accession_number: str
    filed_at: str
    accepted_at: str
    report_date: str
    form: str
    primary_document: str


def load_company_fact_mart_policy(
    payload: Mapping[str, Any],
) -> CompanyFactMartPolicy:
    _require(
        payload.get("schema_version") == POLICY_SCHEMA_VERSION,
        "company_fact_policy_schema_invalid",
    )
    _require(
        payload.get("status") == "zero_network_source_bound_company_fact_mart_policy",
        "company_fact_policy_status_invalid",
    )
    source_rows = payload.get("source_bindings")
    metric_rows = payload.get("metric_definitions")
    _require(isinstance(source_rows, list) and source_rows, "company_fact_sources_invalid")
    _require(isinstance(metric_rows, list) and metric_rows, "company_fact_metrics_invalid")
    sources: list[CompanySourceBinding] = []
    seen_tickers: set[str] = set()
    for row in source_rows:
        _require(isinstance(row, Mapping), "company_fact_source_invalid")
        ticker = str(row.get("ticker") or "").strip().upper()
        _require(ticker and ticker not in seen_tickers, "company_fact_source_ticker_invalid")
        values = {
            key: str(row.get(key) or "").strip()
            for key in (
                "cik",
                "legal_name",
                "companyfacts_ref",
                "companyfacts_metadata_ref",
                "companyfacts_sha256",
                "submissions_ref",
                "submissions_metadata_ref",
                "submissions_sha256",
            )
        }
        _require(
            all(values.values())
            and len(values["companyfacts_sha256"]) == 64
            and len(values["submissions_sha256"]) == 64,
            "company_fact_source_binding_invalid",
        )
        seen_tickers.add(ticker)
        sources.append(CompanySourceBinding(ticker=ticker, **values))
    metrics: list[MetricDefinition] = []
    seen_metrics: set[str] = set()
    for row in metric_rows:
        _require(isinstance(row, Mapping), "company_fact_metric_invalid")
        metric_id = str(row.get("metric_id") or "").strip()
        concepts_raw = row.get("concepts")
        allowed_units = _unique(row.get("allowed_units") or ())
        formula = row.get("formula")
        _require(
            metric_id
            and metric_id not in seen_metrics
            and isinstance(concepts_raw, list)
            and (concepts_raw or formula)
            and bool(str(row.get("unit_family") or "").strip()),
            "company_fact_metric_contract_invalid",
        )
        concepts: list[tuple[str, str]] = []
        for concept in concepts_raw:
            _require(
                isinstance(concept, Mapping)
                and bool(str(concept.get("taxonomy") or "").strip())
                and bool(str(concept.get("concept") or "").strip()),
                "company_fact_metric_concept_invalid",
            )
            concepts.append((str(concept["taxonomy"]), str(concept["concept"])))
        _require(
            formula is None or bool(str(formula).strip()),
            "company_fact_metric_formula_invalid",
        )
        if not formula:
            _require(bool(allowed_units), "company_fact_metric_units_invalid")
        seen_metrics.add(metric_id)
        metrics.append(
            MetricDefinition(
                metric_id=metric_id,
                unit_family=str(row["unit_family"]),
                concepts=tuple(concepts),
                allowed_units=allowed_units,
                formula=str(formula).strip() if formula else None,
            )
        )
    allowed_forms = _unique(payload.get("allowed_forms") or ())
    authority = payload.get("authority")
    _require(
        allowed_forms == ("10-K", "10-Q")
        and isinstance(authority, Mapping)
        and authority.get("raw_capture_digest_required") is True
        and authority.get("accepted_at_required") is True
        and authority.get("preserve_all_vintages") is True
        and authority.get("fact_signal_context_mixed_table_forbidden") is True
        and authority.get("typed_conflict_fails_closed") is True,
        "company_fact_authority_invalid",
    )
    qrels = payload.get("acceptance_qrels")
    _require(isinstance(qrels, list) and qrels, "company_fact_qrels_invalid")
    return CompanyFactMartPolicy(
        recorded_at=str(payload["recorded_at"]),
        research_as_of=str(payload["research_as_of"]),
        minimum_period_end=str(payload["minimum_period_end"]),
        allowed_forms=allowed_forms,
        sources=tuple(sources),
        metrics=tuple(metrics),
        acceptance_qrels=tuple(dict(row) for row in qrels if isinstance(row, Mapping)),
        authority=dict(authority),
    )


def parse_policy_sources(
    policy: CompanyFactMartPolicy,
    *,
    repository_root: Path,
) -> tuple[tuple[CompanyFactObservation, ...], dict[str, Any]]:
    observations: list[CompanyFactObservation] = []
    source_summaries: list[dict[str, Any]] = []
    for source in policy.sources:
        rows, summary = parse_company_source(
            policy,
            source,
            repository_root=repository_root,
        )
        observations.extend(rows)
        source_summaries.append(summary)
    deduplicated = {row.observation_id: row for row in observations}
    with_supersession = _apply_current_supersession(tuple(deduplicated.values()))
    summary = {
        "source_count": len(source_summaries),
        "sources": source_summaries,
        "raw_observation_count": len(observations),
        "deduplicated_observation_count": len(with_supersession),
        "duplicate_observation_count": len(observations) - len(with_supersession),
    }
    return tuple(sorted(with_supersession, key=_observation_sort_key)), summary


def parse_company_source(
    policy: CompanyFactMartPolicy,
    source: CompanySourceBinding,
    *,
    repository_root: Path,
) -> tuple[tuple[CompanyFactObservation, ...], dict[str, Any]]:
    companyfacts_path = _resolve(repository_root, source.companyfacts_ref)
    submissions_path = _resolve(repository_root, source.submissions_ref)
    companyfacts_metadata = _read_json(
        _resolve(repository_root, source.companyfacts_metadata_ref)
    )
    submissions_metadata = _read_json(
        _resolve(repository_root, source.submissions_metadata_ref)
    )
    _verify_capture(
        companyfacts_path,
        companyfacts_metadata,
        expected_sha256=source.companyfacts_sha256,
        expected_ticker=source.ticker,
        expected_kind="sec_companyfacts",
    )
    _verify_capture(
        submissions_path,
        submissions_metadata,
        expected_sha256=source.submissions_sha256,
        expected_ticker=source.ticker,
        expected_kind="sec_submissions",
    )
    companyfacts = _read_json_decimal(companyfacts_path)
    submissions = _read_json(submissions_path)
    cik = str(int(companyfacts.get("cik"))).zfill(10)
    _require(cik == source.cik, "company_fact_cik_mismatch")
    _require(
        str(companyfacts.get("entityName") or "") == source.legal_name,
        "company_fact_legal_name_mismatch",
    )
    filings = _filing_identities(submissions)
    facts = companyfacts.get("facts")
    _require(isinstance(facts, Mapping), "company_fact_payload_facts_invalid")
    observations: list[CompanyFactObservation] = []
    counters = {
        "facts_seen": 0,
        "accepted_observations": 0,
        "missing_filing_identity": 0,
        "unsupported_form": 0,
        "unsupported_period": 0,
        "outside_period_window": 0,
    }
    for metric in policy.metrics:
        if metric.formula:
            continue
        for priority, (taxonomy, concept) in enumerate(metric.concepts):
            taxonomy_facts = facts.get(taxonomy)
            concept_payload = (
                taxonomy_facts.get(concept)
                if isinstance(taxonomy_facts, Mapping)
                else None
            )
            if not isinstance(concept_payload, Mapping):
                continue
            units = concept_payload.get("units")
            if not isinstance(units, Mapping):
                continue
            for unit, unit_rows in units.items():
                if str(unit) not in metric.allowed_units or not isinstance(unit_rows, list):
                    continue
                for raw in unit_rows:
                    if not isinstance(raw, Mapping):
                        continue
                    counters["facts_seen"] += 1
                    accession = str(raw.get("accn") or "")
                    filing = filings.get(accession)
                    if filing is None:
                        counters["missing_filing_identity"] += 1
                        continue
                    if filing.form not in policy.allowed_forms:
                        counters["unsupported_form"] += 1
                        continue
                    period_end = str(raw.get("end") or "")
                    if not period_end or period_end < policy.minimum_period_end:
                        counters["outside_period_window"] += 1
                        continue
                    role, duration = _period_role(
                        start=str(raw.get("start") or "") or None,
                        end=period_end,
                        form=filing.form,
                        fiscal_period=str(raw.get("fp") or "") or None,
                    )
                    if role is None:
                        counters["unsupported_period"] += 1
                        continue
                    value = raw.get("val")
                    if not isinstance(value, Decimal):
                        counters["unsupported_period"] += 1
                        continue
                    period_start = str(raw.get("start") or "") or None
                    reported_fy = _optional_int(raw.get("fy"))
                    fiscal_year = _period_fiscal_year(
                        reported_fiscal_year=reported_fy,
                        report_date=filing.report_date,
                        period_end=period_end,
                    )
                    identity = {
                        "ticker": source.ticker,
                        "metric_id": metric.metric_id,
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "unit": str(unit),
                        "value": _decimal_text(value),
                        "period_start": period_start,
                        "period_end": period_end,
                        "accession_number": accession,
                    }
                    observations.append(
                        CompanyFactObservation(
                            observation_id=(
                                "CFOBS::" + canonical_digest(identity)[:32]
                            ),
                            ticker=source.ticker,
                            cik=source.cik,
                            legal_name=source.legal_name,
                            metric_id=metric.metric_id,
                            unit_family=metric.unit_family,
                            taxonomy=taxonomy,
                            concept=concept,
                            concept_priority=priority,
                            value_decimal=_decimal_text(value),
                            unit=str(unit),
                            period_start=period_start,
                            period_end=period_end,
                            duration_days=duration,
                            period_role=role,
                            fiscal_year=fiscal_year,
                            fiscal_period=str(raw.get("fp") or "") or None,
                            reported_fiscal_year=reported_fy,
                            reported_fiscal_period=str(raw.get("fp") or "") or None,
                            form=filing.form,
                            accession_number=accession,
                            filed_at=filing.filed_at,
                            accepted_at=filing.accepted_at,
                            frame=str(raw.get("frame") or "") or None,
                            primary_document=filing.primary_document,
                            citation_url=_filing_url(
                                source.cik,
                                accession,
                                filing.primary_document,
                            ),
                            companyfacts_ref=source.companyfacts_ref,
                            companyfacts_sha256=source.companyfacts_sha256,
                            submissions_ref=source.submissions_ref,
                            submissions_sha256=source.submissions_sha256,
                            captured_at=str(companyfacts_metadata["downloaded_at_utc"]),
                        )
                    )
                    counters["accepted_observations"] += 1
    return tuple(observations), {
        "ticker": source.ticker,
        "cik": source.cik,
        "companyfacts_sha256": source.companyfacts_sha256,
        "submissions_sha256": source.submissions_sha256,
        **counters,
    }


def _filing_identities(payload: Mapping[str, Any]) -> dict[str, FilingIdentity]:
    filings = payload.get("filings")
    recent = filings.get("recent") if isinstance(filings, Mapping) else None
    _require(isinstance(recent, Mapping), "company_fact_submissions_recent_invalid")
    keys = (
        "accessionNumber",
        "filingDate",
        "acceptanceDateTime",
        "reportDate",
        "form",
        "primaryDocument",
    )
    arrays = [recent.get(key) for key in keys]
    _require(
        all(isinstance(value, list) for value in arrays)
        and len({len(value) for value in arrays}) == 1,
        "company_fact_submissions_columns_invalid",
    )
    output: dict[str, FilingIdentity] = {}
    for values in zip(*arrays):
        accession, filed, accepted, report, form, primary = (
            str(value or "") for value in values
        )
        if not accession or not accepted or not form:
            continue
        output[accession] = FilingIdentity(
            accession_number=accession,
            filed_at=filed,
            accepted_at=_normalize_datetime(accepted),
            report_date=report,
            form=form,
            primary_document=primary,
        )
    return output


def _apply_current_supersession(
    rows: Sequence[CompanyFactObservation],
) -> tuple[CompanyFactObservation, ...]:
    grouped: dict[tuple[Any, ...], list[CompanyFactObservation]] = {}
    for row in rows:
        grouped.setdefault(
            (
                row.ticker,
                row.metric_id,
                row.period_start,
                row.period_end,
                row.period_role,
                row.unit,
            ),
            [],
        ).append(row)
    output: list[CompanyFactObservation] = []
    for values in grouped.values():
        ordered = sorted(
            values,
            key=lambda row: (
                row.accepted_at,
                -row.concept_priority,
                row.observation_id,
            ),
        )
        successor = ordered[-1]
        for row in ordered:
            output.append(
                row
                if row.observation_id == successor.observation_id
                else replace(
                    row,
                    superseded_by_observation_id=successor.observation_id,
                )
            )
    return tuple(output)


def _period_role(
    *, start: str | None, end: str, form: str, fiscal_period: str | None
) -> tuple[str | None, int | None]:
    if not start:
        return "instant", None
    try:
        duration = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return None, None
    if duration <= 0:
        return None, duration
    if form == "10-K" and fiscal_period == "FY" and 300 <= duration <= 400:
        return "fiscal_year", duration
    if form == "10-Q" and duration <= 120:
        return "quarter_discrete", duration
    if form == "10-Q" and 120 < duration <= 300:
        return "fiscal_ytd", duration
    return None, duration


def _period_fiscal_year(
    *, reported_fiscal_year: int | None, report_date: str, period_end: str
) -> int | None:
    if reported_fiscal_year is None:
        return None
    try:
        delta = date.fromisoformat(report_date).year - date.fromisoformat(period_end).year
    except ValueError:
        return reported_fiscal_year
    return reported_fiscal_year - max(delta, 0)


def _verify_capture(
    path: Path,
    metadata: Mapping[str, Any],
    *,
    expected_sha256: str,
    expected_ticker: str,
    expected_kind: str,
) -> None:
    _require(path.is_file(), "company_fact_capture_missing")
    observed = _canonical_json_sha256(path)
    _require(
        observed == expected_sha256
        and str(metadata.get("sha256") or "") == expected_sha256
        and str(metadata.get("ticker") or "").upper() == expected_ticker
        and str(metadata.get("fact_source") or "") == expected_kind
        and bool(str(metadata.get("downloaded_at_utc") or "")),
        "company_fact_capture_digest_or_metadata_drift",
    )


def _filing_url(cik: str, accession: str, primary_document: str) -> str:
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession.replace('-', '')}/{primary_document}"
    )


def _normalize_datetime(value: str) -> str:
    normalized = value.strip().replace("/", "-")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CompanyFactSourceError("company_fact_accepted_at_invalid") from exc
    if parsed.tzinfo is None:
        normalized = parsed.isoformat(timespec="seconds") + "+00:00"
    else:
        normalized = parsed.isoformat(timespec="seconds")
    return normalized


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise CompanyFactSourceError("company_fact_decimal_non_finite")
    return format(value, "f")


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _observation_sort_key(row: CompanyFactObservation) -> tuple[Any, ...]:
    return (
        row.ticker,
        row.metric_id,
        row.period_end,
        row.period_start or "",
        row.accepted_at,
        row.concept_priority,
        row.observation_id,
    )


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not path.is_absolute():
        resolved.relative_to(root.resolve())
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "company_fact_json_object_required")
    return value


def _read_json_decimal(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_float=Decimal,
        parse_int=Decimal,
    )
    _require(isinstance(value, dict), "company_fact_json_object_required")
    return value


def _canonical_json_sha256(path: Path) -> str:
    """Reproduce the logical JSON digest written by the source downloader.

    The legacy downloader stored compact unsorted JSON on disk but recorded a
    digest over the same payload with sorted keys.  Re-serializing the parsed
    payload is therefore required to verify the recorded immutable identity;
    hashing the physical file bytes would reject an otherwise identical
    capture solely because of key order.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _unique(values: Iterable[object]) -> tuple[str, ...]:
    output = tuple(str(value).strip() for value in values)
    _require(all(output) and len(output) == len(set(output)), "company_fact_values_invalid")
    return output


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CompanyFactSourceError(code)


__all__ = [
    "POLICY_SCHEMA_VERSION",
    "CompanyFactMartPolicy",
    "CompanyFactSourceError",
    "CompanySourceBinding",
    "load_company_fact_mart_policy",
    "parse_company_source",
    "parse_policy_sources",
]
