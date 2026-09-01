"""Typed read-only domain ports for the DELL reference vertical.

The ports in this module deliberately reuse the existing FIN authorities:

* reviewed Evidence remains owned by ``ResearchEvidencePackService``;
* NumericFacts remain owned by the frozen S2 company-fact mart executor.

They replace cell-bound delivery with small ID/query based reads.  The module
does not admit Evidence, execute retrieval, mutate S2, or invent a second fact
schema.  It is therefore suitable for injection into the thin MCP transport.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rank_bm25 import BM25Okapi

from financial_facts import FactLookup, execute_fact_lookup
from sec_agent.research.reviewed_evidence_pack import canonical_digest
from retrieval.text import evidence_search_text, tokenize
from sec_agent.research_foundation.contracts import DellResearchRunScope


EVIDENCE_READ_SCHEMA_VERSION = "fin_ia_reviewed_evidence_id_read_v1_0"
EVIDENCE_SEARCH_SCHEMA_VERSION = "fin_ia_reviewed_evidence_search_v1_0"
FINANCIAL_FACT_QUERY_SCHEMA_VERSION = "fin_ia_company_financial_fact_query_v1_0"
LOCAL_KNOWLEDGE_READ_SCHEMA_VERSION = (
    "fin_ia_frozen_legacy_local_knowledge_read_v1_0"
)
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")
_METRIC_RE = re.compile(r"^[a-z][a-z0-9_]{1,95}$")
_GRANULARITIES = frozenset(
    {
        "quarter_discrete",
        "fiscal_ytd",
        "fiscal_year",
        "instant",
        "quarter",
        "quarter_and_fiscal_year",
    }
)


class DataPortContractError(ValueError):
    """An agent supplied a request outside the typed read contract."""


class _StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def __getitem__(self, field: str) -> Any:
        return getattr(self, field)


class CompanyFinancialFactQuery(BaseModel):
    """Provider-neutral query envelope for the existing S2 fact executor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: str = Field(min_length=1, max_length=16)
    metric_ids: tuple[str, ...] = Field(min_length=1, max_length=12)
    research_as_of: date
    period_start: date | None = None
    period_end: date | None = None
    fiscal_years: tuple[int, ...] = Field(default_factory=tuple, max_length=4)
    granularity: str
    requested_unit: str = Field(
        default="reported_source_unit", min_length=1, max_length=64
    )
    unit_family: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not _TICKER_RE.fullmatch(normalized):
            raise ValueError("financial_fact_ticker_invalid")
        return normalized

    @field_validator("metric_ids")
    @classmethod
    def normalize_metrics(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(str(value).strip() for value in values))
        if len(normalized) != len(values) or any(
            not _METRIC_RE.fullmatch(value) for value in normalized
        ):
            raise ValueError("financial_fact_metric_ids_invalid")
        return normalized

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in _GRANULARITIES:
            raise ValueError("financial_fact_granularity_invalid")
        return normalized

    @field_validator("fiscal_years")
    @classmethod
    def validate_fiscal_years(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        normalized = tuple(dict.fromkeys(values))
        if len(normalized) != len(values) or any(
            value < 1990 or value > 2200 for value in normalized
        ):
            raise ValueError("financial_fact_fiscal_years_invalid")
        return normalized

    @model_validator(mode="after")
    def validate_period(self) -> "CompanyFinancialFactQuery":
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("financial_fact_period_inverted")
        if self.period_end and self.period_end > self.research_as_of:
            raise ValueError("financial_fact_period_after_research_as_of")
        return self


class LocalKnowledgeCandidate(_StrictOutputModel):
    authority_state: Literal["retrieval_candidate"]
    candidate_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    owner_ticker: str
    source_type: str
    source_tier: str
    publication_date: str
    period_end: str
    section: str
    source_url: str
    source_locator_available: bool
    citation_eligible: Literal[False]
    excerpt: str
    excerpt_truncated: bool
    bm25_score: float
    candidate_is_not_evidence: Literal[True]
    legacy_read_only_bridge: Literal[True]


class LocalKnowledgeReadResult(_StrictOutputModel):
    schema_version: Literal[
        "fin_ia_frozen_legacy_local_knowledge_read_v1_0"
    ]
    authority_state: Literal["retrieval_candidate_set"]
    branch_id: str
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    query: str
    research_as_of: str
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    physical_record_count: int = Field(ge=0)
    visible_record_count: int = Field(ge=0)
    candidates: tuple[LocalKnowledgeCandidate, ...]
    candidate_is_not_evidence: Literal[True]
    evidence_admission_performed: Literal[False]
    target_route: Literal[
        "postgres_pgvector_exact_after_capture_lineage_import"
    ]
    read_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewedEvidenceProjection(_StrictOutputModel):
    authority_state: Literal["reviewed_evidence"]
    writer_citable: Literal[True]
    evidence_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    evidence_role: Literal[
        "issuer_direct_source",
        "counterparty_or_ecosystem_readthrough",
    ]
    publication_date: str = Field(min_length=1)
    source_reporting_period_end: str | None
    research_as_of: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_tier: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    source_record_id: str = Field(min_length=1)
    source_locator: dict[str, Any] | None = None
    source_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    bounded_excerpt: str = Field(min_length=1)
    excerpt_truncated: bool
    numeric_use_boundary: str = Field(min_length=1)
    causal_attribution_authorized: Literal[False]
    evidence_item_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewedEvidenceSearchHit(_StrictOutputModel):
    authority_state: Literal["reviewed_evidence_locator"]
    evidence_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    evidence_role: Literal[
        "issuer_direct_source",
        "counterparty_or_ecosystem_readthrough",
    ]
    publication_date: str = Field(min_length=1)
    source_reporting_period_end: str | None
    source_type: str = Field(min_length=1)
    source_tier: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https://")
    bounded_preview: str = Field(min_length=1)
    bm25_score: float
    writer_citable_source: Literal[True]
    requires_id_read_before_citation: Literal[True]
    candidate_promotion_performed: Literal[False]
    evidence_item_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewedEvidenceSearchResult(_StrictOutputModel):
    schema_version: Literal["fin_ia_reviewed_evidence_search_v1_0"]
    authority_state: Literal["reviewed_evidence_locator_set"]
    case_key: str
    branch_id: str
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    query: str
    hits: tuple[ReviewedEvidenceSearchHit, ...]
    writer_citable_sources_only: Literal[True]
    candidate_promotion_performed: Literal[False]
    source_pack_projection_digest: str
    search_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewedEvidenceReadResult(_StrictOutputModel):
    schema_version: Literal["fin_ia_reviewed_evidence_id_read_v1_0"]
    authority_state: Literal["reviewed_evidence_read"]
    case_key: str
    branch_id: str
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_evidence_ids: tuple[str, ...]
    evidence: tuple[ReviewedEvidenceProjection, ...]
    missing_evidence_ids: tuple[str, ...]
    missing_id_is_not_public_information_gap: Literal[True]
    candidate_promotion_performed: Literal[False]
    source_pack_projection_digest: str
    read_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class NumericFormulaTrace(_StrictOutputModel):
    formula: str
    operation: str
    input_numeric_fact_ids: tuple[str, ...]
    input_metrics: tuple[str, ...]


class NumericFactProjection(_StrictOutputModel):
    schema_version: str
    numeric_fact_id: str
    fact_request_id: str
    ticker: str
    metric_id: str
    value_decimal: str
    unit: str
    unit_family: str
    period_start: str | None
    period_end: str
    period_role: str
    fiscal_year: int | None
    fiscal_period: str | None
    research_as_of: str
    authority_mode: str
    accession_numbers: tuple[str, ...]
    accepted_at: str
    source_observation_ids: tuple[str, ...]
    citation_urls: tuple[str, ...]
    source_digests: tuple[str, ...]
    formula_trace: NumericFormulaTrace | None
    numeric_fact_authority: Literal[True]


class TypedFinancialGap(_StrictOutputModel):
    gap_code: str = Field(min_length=1)
    detail_json: str
    detail_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TypedFinancialConflict(_StrictOutputModel):
    conflict_code: str = Field(min_length=1)
    conflicts_json: str
    conflicts_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FinancialMetricResult(_StrictOutputModel):
    schema_version: str
    status: Literal["resolved", "typed_gap", "typed_conflict"]
    fact_request_id: str
    ticker: str
    metric_id: str
    facts: tuple[NumericFactProjection, ...]
    typed_gap: TypedFinancialGap | None
    typed_conflict: TypedFinancialConflict | None
    fact_request_is_not_numeric_fact: Literal[True]

    @model_validator(mode="after")
    def validate_state(self) -> "FinancialMetricResult":
        if self.status == "resolved" and (
            not self.facts or self.typed_gap is not None or self.typed_conflict is not None
        ):
            raise ValueError("resolved_financial_metric_state_invalid")
        if self.status == "typed_gap" and (
            self.facts or self.typed_gap is None or self.typed_conflict is not None
        ):
            raise ValueError("typed_gap_financial_metric_state_invalid")
        if self.status == "typed_conflict" and (
            self.facts or self.typed_gap is not None or self.typed_conflict is None
        ):
            raise ValueError("typed_conflict_financial_metric_state_invalid")
        return self


class CompanyFinancialFactQueryResult(_StrictOutputModel):
    schema_version: Literal["fin_ia_company_financial_fact_query_v1_0"]
    authority_state: Literal["s2_numeric_fact_query_result"]
    branch_id: str
    run_scope_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    query: CompanyFinancialFactQuery
    results: tuple[FinancialMetricResult, ...]
    resolved_metric_count: int = Field(ge=0)
    typed_gap_count: int = Field(ge=0)
    typed_conflict_count: int = Field(ge=0)
    read_only: Literal[True]
    query_is_not_numeric_fact: Literal[True]
    narrative_numeric_fallback_performed: Literal[False]
    fact_mart_sha256_before: str = Field(pattern=r"^[0-9a-f]{64}$")
    fact_mart_sha256_after: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_counts_and_snapshot(self) -> "CompanyFinancialFactQueryResult":
        if self.fact_mart_sha256_before != self.fact_mart_sha256_after:
            raise ValueError("s2_fact_mart_digest_drift_during_query")
        counts = {
            "resolved": self.resolved_metric_count,
            "typed_gap": self.typed_gap_count,
            "typed_conflict": self.typed_conflict_count,
        }
        if any(
            counts[state] != sum(row.status == state for row in self.results)
            for state in counts
        ):
            raise ValueError("financial_fact_result_counts_invalid")
        return self


def _evidence_id(case_key: str, item: Mapping[str, Any]) -> str:
    identity = {
        "case_key": case_key,
        "target_id": item.get("target_id"),
        "evidence_item_digest": item.get("evidence_item_digest"),
    }
    return f"EV::{canonical_digest(identity)[:16].upper()}"


def _validate_reviewed_evidence_item(item: Mapping[str, Any]) -> None:
    source = item.get("source")
    if not isinstance(source, Mapping):
        raise DataPortContractError("reviewed_evidence_source_invalid")
    disposition = item.get("disposition")
    role = item.get("evidence_role")
    if item.get("writer_citable") is not True:
        raise DataPortContractError("reviewed_evidence_not_writer_citable")
    if item.get("causal_attribution_authorized") is not False:
        raise DataPortContractError(
            "reviewed_evidence_causal_attribution_boundary_invalid"
        )
    if (disposition, role) not in {
        ("accepted_direct_source_evidence", "issuer_direct_source"),
        (
            "accepted_bounded_context_evidence",
            "counterparty_or_ecosystem_readthrough",
        ),
    }:
        raise DataPortContractError("reviewed_evidence_role_boundary_invalid")
    required_values = (
        item.get("target_id"),
        item.get("publication_date"),
        item.get("research_as_of"),
        item.get("numeric_use_boundary"),
        source.get("source_type"),
        source.get("source_tier"),
        source.get("reviewed_source_excerpt"),
    )
    if any(not str(value or "").strip() for value in required_values):
        raise DataPortContractError("reviewed_evidence_required_field_missing")
    digest = str(item.get("evidence_item_digest") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise DataPortContractError("reviewed_evidence_item_digest_invalid")
    source_url = str(source.get("source_url") or "").strip()
    parts = urlsplit(source_url)
    if parts.scheme != "https" or not parts.netloc:
        raise DataPortContractError("reviewed_evidence_source_url_invalid")


def _reviewed_evidence_index(
    *, case_key: str, rows: Any
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(rows, list):
        raise DataPortContractError("reviewed_evidence_items_invalid")
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise DataPortContractError("reviewed_evidence_item_invalid")
        _validate_reviewed_evidence_item(row)
        evidence_id = _evidence_id(case_key, row)
        if evidence_id in by_id:
            raise DataPortContractError("reviewed_evidence_id_duplicate")
        by_id[evidence_id] = row
    return by_id


def _require_branch_in_scope(
    *, branch_id: str, run_scope: DellResearchRunScope
) -> str:
    normalized = str(branch_id).strip()
    if normalized not in run_scope.selected_branch_ids:
        raise DataPortContractError("research_branch_outside_run_scope")
    return normalized


def _stream_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _bounded_evidence_projection(
    *,
    case_key: str,
    item: Mapping[str, Any],
    maximum_excerpt_characters: int,
) -> ReviewedEvidenceProjection:
    source = item.get("source")
    if not isinstance(source, Mapping):
        raise DataPortContractError("reviewed_evidence_source_invalid")
    excerpt = str(source.get("reviewed_source_excerpt") or "").strip()
    if not excerpt:
        raise DataPortContractError("reviewed_evidence_excerpt_empty")
    bounded = excerpt[:maximum_excerpt_characters]
    return ReviewedEvidenceProjection.model_validate({
        "authority_state": "reviewed_evidence",
        "writer_citable": item.get("writer_citable"),
        "evidence_id": _evidence_id(case_key, item),
        "target_id": str(item.get("target_id") or ""),
        "evidence_role": str(item.get("evidence_role") or ""),
        "publication_date": str(item.get("publication_date") or ""),
        "source_reporting_period_end": (
            str(item.get("source_reporting_period_end"))
            if item.get("source_reporting_period_end")
            else None
        ),
        "research_as_of": str(item.get("research_as_of") or ""),
        "source_type": str(source.get("source_type") or ""),
        "source_tier": str(source.get("source_tier") or ""),
        "source_url": str(source.get("source_url") or ""),
        "source_record_id": str(item.get("source_record_id") or ""),
        "source_locator": (
            dict(source["source_locator"])
            if isinstance(source.get("source_locator"), Mapping)
            else None
        ),
        "source_content_digest": str(
            item.get("source_content_digest")
            or source.get("source_text_digest")
            or ""
        ),
        "bounded_excerpt": bounded,
        "excerpt_truncated": len(bounded) < len(excerpt)
        or bool(source.get("excerpt_truncated")),
        "numeric_use_boundary": str(item.get("numeric_use_boundary") or ""),
        "causal_attribution_authorized": item.get(
            "causal_attribution_authorized"
        ),
        "evidence_item_digest": str(item.get("evidence_item_digest") or ""),
    })


@dataclass(frozen=True)
class CurrentReviewedEvidenceReader:
    """Read selected reviewed Evidence without exposing a cell contract."""

    case_reader: Callable[[str], Mapping[str, Any]]
    case_key: str = "DELL"
    maximum_excerpt_characters: int = 1_200

    def __post_init__(self) -> None:
        normalized = self.case_key.strip().upper()
        if not _TICKER_RE.fullmatch(normalized):
            raise DataPortContractError("reviewed_evidence_case_key_invalid")
        if not 200 <= self.maximum_excerpt_characters <= 4_000:
            raise DataPortContractError("reviewed_evidence_excerpt_limit_invalid")
        object.__setattr__(self, "case_key", normalized)

    def __call__(
        self,
        *,
        evidence_ids: Sequence[str],
        branch_id: str,
        run_scope: DellResearchRunScope,
    ) -> ReviewedEvidenceReadResult:
        branch_id = _require_branch_in_scope(
            branch_id=branch_id,
            run_scope=run_scope,
        )
        requested = tuple(str(value).strip() for value in evidence_ids)
        if (
            not requested
            or len(requested) > 24
            or any(not value for value in requested)
            or len(set(requested)) != len(requested)
        ):
            raise DataPortContractError("reviewed_evidence_id_count_invalid")
        case = self.case_reader(self.case_key)
        by_id = _reviewed_evidence_index(
            case_key=self.case_key,
            rows=case.get("evidence_items"),
        )
        found = [
            _bounded_evidence_projection(
                case_key=self.case_key,
                item=by_id[evidence_id],
                maximum_excerpt_characters=self.maximum_excerpt_characters,
            )
            for evidence_id in requested
            if evidence_id in by_id
        ]
        missing = [value for value in requested if value not in by_id]
        body = {
            "schema_version": EVIDENCE_READ_SCHEMA_VERSION,
            "authority_state": "reviewed_evidence_read",
            "case_key": self.case_key,
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "requested_evidence_ids": list(requested),
            "evidence": [row.model_dump(mode="json") for row in found],
            "missing_evidence_ids": missing,
            "missing_id_is_not_public_information_gap": True,
            "candidate_promotion_performed": False,
            "source_pack_projection_digest": str(case.get("projection_digest") or ""),
        }
        return ReviewedEvidenceReadResult(
            **body,
            read_digest=canonical_digest(body),
        )

    def search(
        self,
        *,
        query: str,
        branch_id: str,
        limit: int,
        run_scope: DellResearchRunScope,
    ) -> ReviewedEvidenceSearchResult:
        branch_id = _require_branch_in_scope(
            branch_id=branch_id,
            run_scope=run_scope,
        )
        normalized_query = re.sub(r"\s+", " ", str(query)).strip()
        if len(normalized_query) < 3 or len(normalized_query) > 600:
            raise DataPortContractError("reviewed_evidence_search_query_invalid")
        if not 1 <= limit <= 12:
            raise DataPortContractError("reviewed_evidence_search_limit_invalid")
        tokens = tokenize(normalized_query)
        if not tokens:
            raise DataPortContractError("reviewed_evidence_search_tokens_empty")

        case = self.case_reader(self.case_key)
        by_id = _reviewed_evidence_index(
            case_key=self.case_key,
            rows=case.get("evidence_items"),
        )
        indexed = tuple(sorted(by_id.items()))
        corpus = []
        for _, item in indexed:
            source = item["source"]
            corpus.append(
                tokenize(
                    " ".join(
                        (
                            str(item.get("target_id") or ""),
                            str(item.get("evidence_role") or ""),
                            str(source.get("source_type") or ""),
                            str(source.get("source_tier") or ""),
                            str(source.get("reviewed_source_excerpt") or ""),
                        )
                    )
                )
            )
        scores = BM25Okapi(corpus).get_scores(tokens) if corpus else ()
        ranked = sorted(
            enumerate(scores),
            key=lambda pair: (-float(pair[1]), indexed[pair[0]][0]),
        )
        hits: list[ReviewedEvidenceSearchHit] = []
        for row_index, raw_score in ranked:
            if float(raw_score) <= 0:
                continue
            evidence_id, item = indexed[row_index]
            source = item["source"]
            excerpt = re.sub(
                r"\s+", " ", str(source.get("reviewed_source_excerpt") or "")
            ).strip()
            hits.append(
                ReviewedEvidenceSearchHit(
                    authority_state="reviewed_evidence_locator",
                    evidence_id=evidence_id,
                    target_id=str(item.get("target_id") or ""),
                    evidence_role=str(item.get("evidence_role") or ""),
                    publication_date=str(item.get("publication_date") or ""),
                    source_reporting_period_end=(
                        str(item.get("source_reporting_period_end"))
                        if item.get("source_reporting_period_end")
                        else None
                    ),
                    source_type=str(source.get("source_type") or ""),
                    source_tier=str(source.get("source_tier") or ""),
                    source_url=str(source.get("source_url") or ""),
                    bounded_preview=excerpt[:400],
                    bm25_score=round(float(raw_score), 8),
                    writer_citable_source=True,
                    requires_id_read_before_citation=True,
                    candidate_promotion_performed=False,
                    evidence_item_digest=str(
                        item.get("evidence_item_digest") or ""
                    ),
                )
            )
            if len(hits) >= limit:
                break
        body = {
            "schema_version": EVIDENCE_SEARCH_SCHEMA_VERSION,
            "authority_state": "reviewed_evidence_locator_set",
            "case_key": self.case_key,
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "query": normalized_query,
            "hits": [row.model_dump(mode="json") for row in hits],
            "writer_citable_sources_only": True,
            "candidate_promotion_performed": False,
            "source_pack_projection_digest": str(case.get("projection_digest") or ""),
        }
        return ReviewedEvidenceSearchResult(
            **body,
            search_digest=canonical_digest(body),
        )


@dataclass(frozen=True)
class ExistingS2FinancialFactReader:
    """Execute bounded generic queries against the frozen read-only S2 mart."""

    sqlite_path: Path
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        resolved = self.sqlite_path.resolve()
        if not resolved.is_file():
            raise DataPortContractError("s2_fact_mart_unavailable")
        expected = self.expected_sha256
        if expected is not None and (
            re.fullmatch(r"[0-9a-f]{64}", expected) is None
            or _stream_sha256(resolved) != expected
        ):
            raise DataPortContractError("s2_fact_mart_expected_digest_mismatch")
        object.__setattr__(self, "sqlite_path", resolved)

    def __call__(
        self,
        *,
        request: Mapping[str, Any] | CompanyFinancialFactQuery,
        branch_id: str,
        run_scope: DellResearchRunScope,
    ) -> CompanyFinancialFactQueryResult:
        branch_id = _require_branch_in_scope(
            branch_id=branch_id,
            run_scope=run_scope,
        )
        query = (
            request
            if isinstance(request, CompanyFinancialFactQuery)
            else CompanyFinancialFactQuery.model_validate(dict(request))
        )
        if query.research_as_of > run_scope.research_as_of.date():
            raise DataPortContractError("financial_fact_query_after_run_as_of")
        period: dict[str, Any] = {
            "end_date": (query.period_end or query.research_as_of).isoformat(),
            "fiscal_years": list(query.fiscal_years),
        }
        if query.period_start is not None:
            period["start_date"] = query.period_start.isoformat()

        fact_mart_sha256_before = _stream_sha256(self.sqlite_path)
        if (
            self.expected_sha256 is not None
            and fact_mart_sha256_before != self.expected_sha256
        ):
            raise DataPortContractError("s2_fact_mart_digest_drift_before_query")
        results: list[FinancialMetricResult] = []
        for metric_id in query.metric_ids:
            identity = {
                "query_schema_version": FINANCIAL_FACT_QUERY_SCHEMA_VERSION,
                "ticker": query.ticker,
                "metric_id": metric_id,
                "research_as_of": query.research_as_of.isoformat(),
                "period": period,
                "granularity": query.granularity,
                "requested_unit": query.requested_unit,
                "unit_family": query.unit_family,
            }
            fact_request_id = "MCPFACT::" + canonical_digest(identity)[:32].upper()
            result = execute_fact_lookup(
                self.sqlite_path,
                FactLookup(
                    fact_request_id=fact_request_id,
                    ticker=query.ticker,
                    metric_id=metric_id,
                    research_as_of=query.research_as_of.isoformat(),
                    period=period,
                    granularity=query.granularity,
                    requested_unit=query.requested_unit,
                    unit_family=query.unit_family,
                ),
            )
            raw_result = result.as_dict()
            typed_gap = raw_result.get("typed_gap")
            gap_projection = None
            if isinstance(typed_gap, Mapping):
                detail = dict(typed_gap)
                gap_code = str(detail.pop("gap_code", ""))
                detail_json = _canonical_json_text(detail)
                gap_projection = TypedFinancialGap(
                    gap_code=gap_code,
                    detail_json=detail_json,
                    detail_sha256=sha256(detail_json.encode("utf-8")).hexdigest(),
                )
            typed_conflict = raw_result.get("typed_conflict")
            conflict_projection = None
            if isinstance(typed_conflict, Mapping):
                conflict_code = str(typed_conflict.get("conflict_code") or "")
                conflicts_json = _canonical_json_text(
                    typed_conflict.get("conflicts") or []
                )
                conflict_projection = TypedFinancialConflict(
                    conflict_code=conflict_code,
                    conflicts_json=conflicts_json,
                    conflicts_sha256=sha256(
                        conflicts_json.encode("utf-8")
                    ).hexdigest(),
                )
            results.append(
                FinancialMetricResult(
                    schema_version=str(raw_result["schema_version"]),
                    status=str(raw_result["status"]),
                    fact_request_id=str(raw_result["fact_request_id"]),
                    ticker=str(raw_result["ticker"]),
                    metric_id=str(raw_result["metric_id"]),
                    facts=tuple(
                        NumericFactProjection.model_validate(row)
                        for row in raw_result["facts"]
                    ),
                    typed_gap=gap_projection,
                    typed_conflict=conflict_projection,
                    fact_request_is_not_numeric_fact=raw_result[
                        "fact_request_is_not_numeric_fact"
                    ],
                )
            )

        fact_mart_sha256_after = _stream_sha256(self.sqlite_path)
        if fact_mart_sha256_before != fact_mart_sha256_after:
            raise DataPortContractError("s2_fact_mart_digest_drift_during_query")
        if (
            self.expected_sha256 is not None
            and fact_mart_sha256_after != self.expected_sha256
        ):
            raise DataPortContractError("s2_fact_mart_digest_drift_after_query")
        body = {
            "schema_version": FINANCIAL_FACT_QUERY_SCHEMA_VERSION,
            "authority_state": "s2_numeric_fact_query_result",
            "branch_id": branch_id,
            "run_scope_digest": run_scope.run_scope_digest,
            "query": query.model_dump(mode="json"),
            "results": [row.model_dump(mode="json") for row in results],
            "resolved_metric_count": sum(row.status == "resolved" for row in results),
            "typed_gap_count": sum(row.status == "typed_gap" for row in results),
            "typed_conflict_count": sum(
                row.status == "typed_conflict" for row in results
            ),
            "read_only": True,
            "query_is_not_numeric_fact": True,
            "narrative_numeric_fallback_performed": False,
            "fact_mart_sha256_before": fact_mart_sha256_before,
            "fact_mart_sha256_after": fact_mart_sha256_after,
        }
        return CompanyFinancialFactQueryResult(
            **body,
            query_digest=canonical_digest(body),
        )


class FrozenLegacyLocalKnowledgeReader:
    """Qualification-only BM25 adapter over the frozen legacy S1 snapshot.

    This gives the new non-cell MCP surface a real local-data reader while the
    same source locators are prepared for PostgreSQL.  It reuses ``rank_bm25``
    and FIN's existing tokenizer, exposes no private paths, and never upgrades
    a candidate to Evidence.
    """

    def __init__(
        self,
        *,
        records_path: str | Path,
        expected_sha256: str,
        expected_record_count: int,
        research_as_of: date,
        allowed_branch_ids: Sequence[str],
        maximum_excerpt_characters: int = 1_200,
    ) -> None:
        path = Path(records_path).resolve()
        if not path.is_file():
            raise DataPortContractError("legacy_local_records_unavailable")
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_sha256:
            raise DataPortContractError("legacy_local_records_digest_drift")
        branches = frozenset(str(value).strip() for value in allowed_branch_ids)
        if not branches or any(not value for value in branches):
            raise DataPortContractError("legacy_local_branch_contract_invalid")
        if not 200 <= maximum_excerpt_characters <= 4_000:
            raise DataPortContractError("legacy_local_excerpt_limit_invalid")

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as stream:
            for ordinal, line in enumerate(stream, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DataPortContractError(
                        f"legacy_local_record_json_invalid:{ordinal}"
                    ) from exc
                if not isinstance(row, dict):
                    raise DataPortContractError(
                        f"legacy_local_record_shape_invalid:{ordinal}"
                    )
                publication = str(row.get("publication_date") or "")
                try:
                    publication_date = date.fromisoformat(publication)
                except ValueError as exc:
                    raise DataPortContractError(
                        f"legacy_local_publication_date_invalid:{ordinal}"
                    ) from exc
                text = str(row.get("text") or "").strip()
                source_record_id = str(row.get("evidence_id") or "").strip()
                source_url = str(row.get("source_url") or "").strip()
                parts = urlsplit(source_url)
                url_invalid = bool(source_url) and (
                    parts.scheme not in {"http", "https"} or not parts.netloc
                )
                if not text or not source_record_id or url_invalid:
                    raise DataPortContractError(
                        f"legacy_local_record_identity_invalid:{ordinal}"
                    )
                if publication_date <= research_as_of:
                    rows.append(row)
        if len(rows) > expected_record_count:
            raise DataPortContractError("legacy_local_visible_count_invalid")
        with path.open("r", encoding="utf-8") as stream:
            physical_count = sum(1 for _ in stream)
        if physical_count != expected_record_count:
            raise DataPortContractError("legacy_local_record_count_drift")

        tokenized = [tokenize(evidence_search_text(row)) for row in rows]
        self._index = BM25Okapi(tokenized)
        self._rows = tuple(rows)
        self._path_digest = expected_sha256
        self._physical_record_count = physical_count
        self._research_as_of = research_as_of
        self._allowed_branch_ids = branches
        self._maximum_excerpt_characters = maximum_excerpt_characters

    def __call__(
        self,
        *,
        query: str,
        branch_id: str,
        limit: int,
        run_scope: DellResearchRunScope,
    ) -> LocalKnowledgeReadResult:
        normalized_query = str(query).strip()
        normalized_branch = _require_branch_in_scope(
            branch_id=branch_id,
            run_scope=run_scope,
        )
        if len(normalized_query) < 3 or len(normalized_query) > 600:
            raise DataPortContractError("legacy_local_query_invalid")
        if normalized_branch not in self._allowed_branch_ids:
            raise DataPortContractError("legacy_local_branch_unknown")
        if self._research_as_of > run_scope.research_as_of.date():
            raise DataPortContractError("legacy_local_snapshot_after_run_as_of")
        if not 1 <= limit <= 12:
            raise DataPortContractError("legacy_local_limit_invalid")
        tokens = tokenize(normalized_query)
        if not tokens:
            raise DataPortContractError("legacy_local_query_tokens_empty")

        scores = self._index.get_scores(tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda item: (
                -float(item[1]),
                str(self._rows[item[0]].get("evidence_id") or ""),
            ),
        )
        candidates: list[LocalKnowledgeCandidate] = []
        for row_index, raw_score in ranked:
            if float(raw_score) <= 0:
                continue
            row = self._rows[row_index]
            text = re.sub(r"\s+", " ", str(row["text"])).strip()
            source_record_id = str(row["evidence_id"])
            identity = {
                "snapshot_sha256": self._path_digest,
                "branch_id": normalized_branch,
                "query": normalized_query,
                "source_record_id": source_record_id,
            }
            candidates.append(
                LocalKnowledgeCandidate.model_validate({
                    "authority_state": "retrieval_candidate",
                    "candidate_id": "LEGACYCAND::"
                    + canonical_digest(identity)[:24].upper(),
                    "source_record_id": source_record_id,
                    "owner_ticker": str(row.get("ticker") or "").upper(),
                    "source_type": str(row.get("source_type") or ""),
                    "source_tier": str(row.get("source_tier") or ""),
                    "publication_date": str(row.get("publication_date") or ""),
                    "period_end": str(row.get("period_end") or ""),
                    "section": str(row.get("section") or ""),
                    "source_url": str(row.get("source_url") or ""),
                    "source_locator_available": bool(row.get("source_url")),
                    "citation_eligible": False,
                    "excerpt": text[: self._maximum_excerpt_characters],
                    "excerpt_truncated": len(text) > self._maximum_excerpt_characters,
                    "bm25_score": round(float(raw_score), 8),
                    "candidate_is_not_evidence": True,
                    "legacy_read_only_bridge": True,
                })
            )
            if len(candidates) >= limit:
                break
        body = {
            "schema_version": LOCAL_KNOWLEDGE_READ_SCHEMA_VERSION,
            "authority_state": "retrieval_candidate_set",
            "branch_id": normalized_branch,
            "run_scope_digest": run_scope.run_scope_digest,
            "query": normalized_query,
            "research_as_of": self._research_as_of.isoformat(),
            "snapshot_sha256": self._path_digest,
            "physical_record_count": self._physical_record_count,
            "visible_record_count": len(self._rows),
            "candidates": [row.model_dump(mode="json") for row in candidates],
            "candidate_is_not_evidence": True,
            "evidence_admission_performed": False,
            "target_route": "postgres_pgvector_exact_after_capture_lineage_import",
        }
        return LocalKnowledgeReadResult(
            **body,
            read_digest=canonical_digest(body),
        )


__all__ = [
    "EVIDENCE_READ_SCHEMA_VERSION",
    "EVIDENCE_SEARCH_SCHEMA_VERSION",
    "FINANCIAL_FACT_QUERY_SCHEMA_VERSION",
    "LOCAL_KNOWLEDGE_READ_SCHEMA_VERSION",
    "CompanyFinancialFactQuery",
    "CompanyFinancialFactQueryResult",
    "CurrentReviewedEvidenceReader",
    "DataPortContractError",
    "ExistingS2FinancialFactReader",
    "FinancialMetricResult",
    "FrozenLegacyLocalKnowledgeReader",
    "LocalKnowledgeReadResult",
    "ReviewedEvidenceReadResult",
    "ReviewedEvidenceSearchResult",
]
