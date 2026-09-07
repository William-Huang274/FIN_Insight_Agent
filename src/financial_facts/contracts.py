from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


COMPANY_FACT_MART_SCHEMA_VERSION = "fin_ia_company_financial_fact_mart_v1_0"
NUMERIC_FACT_SCHEMA_VERSION = "fin_ia_numeric_fact_v1_0"
TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION = (
    "fin_ia_typed_fact_execution_result_v1_0"
)


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    unit_family: str
    concepts: tuple[tuple[str, str], ...]
    allowed_units: tuple[str, ...]
    formula: str | None = None


@dataclass(frozen=True)
class CompanyFactObservation:
    observation_id: str
    ticker: str
    cik: str
    legal_name: str
    metric_id: str
    unit_family: str
    taxonomy: str
    concept: str
    concept_priority: int
    value_decimal: str
    unit: str
    period_start: str | None
    period_end: str
    duration_days: int | None
    period_role: str
    fiscal_year: int | None
    fiscal_period: str | None
    reported_fiscal_year: int | None
    reported_fiscal_period: str | None
    form: str
    accession_number: str
    filed_at: str
    accepted_at: str
    frame: str | None
    primary_document: str
    citation_url: str
    companyfacts_ref: str
    companyfacts_sha256: str
    submissions_ref: str
    submissions_sha256: str
    captured_at: str
    superseded_by_observation_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NumericFact:
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
    formula_trace: Mapping[str, Any] | None
    numeric_fact_authority: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TypedFactExecutionResult:
    schema_version: str
    status: str
    fact_request_id: str
    ticker: str
    metric_id: str
    facts: tuple[NumericFact, ...]
    typed_gap: Mapping[str, Any] | None
    typed_conflict: Mapping[str, Any] | None
    fact_request_is_not_numeric_fact: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "fact_request_id": self.fact_request_id,
            "ticker": self.ticker,
            "metric_id": self.metric_id,
            "facts": [fact.as_dict() for fact in self.facts],
            "typed_gap": dict(self.typed_gap) if self.typed_gap else None,
            "typed_conflict": (
                dict(self.typed_conflict) if self.typed_conflict else None
            ),
            "fact_request_is_not_numeric_fact": self.fact_request_is_not_numeric_fact,
        }


__all__ = [
    "COMPANY_FACT_MART_SCHEMA_VERSION",
    "NUMERIC_FACT_SCHEMA_VERSION",
    "TYPED_FACT_EXECUTION_RESULT_SCHEMA_VERSION",
    "CompanyFactObservation",
    "MetricDefinition",
    "NumericFact",
    "TypedFactExecutionResult",
]
