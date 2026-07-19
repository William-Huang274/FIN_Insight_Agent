from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import Field

from .candidate_bundle import CandidateBundle
from .models import StrictModel, canonical_digest


class ParserNumericError(ValueError):
    """Raised when fixture-only table metadata cannot form an exact unpromoted numeric trace."""


class ParserNumericPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    allowed_units: tuple[str, ...] = Field(min_length=1)
    allowed_scales: tuple[int, ...] = Field(min_length=1)


class NumericFixtureObservation(StrictModel):
    candidate_id: str = Field(min_length=1)
    raw_value: str = Field(min_length=1)
    row_label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    period: str = Field(min_length=1)
    source_coordinate: str = Field(min_length=1)
    scale_multiplier: int = Field(ge=1)


class ParserCandidate(StrictModel):
    parser_candidate_id: str = Field(min_length=1)
    parser_candidate_digest: str = Field(min_length=1)
    candidate_bundle_id: str = Field(min_length=1)
    candidate_bundle_digest: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    table_or_section_ref: str = Field(min_length=1)
    parse_policy_ref: str = Field(min_length=1)
    fixture_only: bool = True
    parse_status: str = "parsed_unpromoted"


class NormalizedNumericFact(StrictModel):
    normalized_fact_id: str = Field(min_length=1)
    normalized_fact_digest: str = Field(min_length=1)
    parser_candidate_id: str = Field(min_length=1)
    parser_candidate_digest: str = Field(min_length=1)
    row_label: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    period: str = Field(min_length=1)
    source_coordinate: str = Field(min_length=1)
    scale_multiplier: int = Field(ge=1)
    promotion_status: str = "unpromoted"


class NumericProgramTrace(StrictModel):
    numeric_trace_id: str = Field(min_length=1)
    trace_digest: str = Field(min_length=1)
    normalized_fact_id: str = Field(min_length=1)
    normalized_fact_digest: str = Field(min_length=1)
    metric_definition_ref: str = Field(min_length=1)
    input_digest: str = Field(min_length=1)
    program_steps: tuple[str, ...] = Field(min_length=1)
    output_value: str = Field(min_length=1)
    promotion_status: str = "unpromoted"


class ParserNumericResult(StrictModel):
    status: str
    parser_candidate: ParserCandidate
    normalized_fact: NormalizedNumericFact
    trace: NumericProgramTrace
    model_call_count: int = 0
    external_call_count: int = 0
    store_write_count: int = 0


class ParserNumericFixtureCompiler:
    """M6.5 parses a supplied fixture observation only; no document read/OCR/promotion occurs."""

    def __init__(self, *, policy: ParserNumericPolicy):
        self.policy = policy

    def compile(self, *, bundle: CandidateBundle, observation: NumericFixtureObservation, metric_definition_ref: str) -> ParserNumericResult:
        if bundle.status != "metadata_fixture_compiled":
            raise ParserNumericError("parser_requires_nonexhausted_candidate_bundle")
        candidate = next((item for item in bundle.candidates if item.candidate_id == observation.candidate_id), None)
        if candidate is None or candidate.candidate_kind != "table_context":
            raise ParserNumericError("parser_requires_exact_table_context_candidate")
        if observation.unit not in self.policy.allowed_units:
            raise ParserNumericError("numeric_unit_not_allowed")
        if observation.scale_multiplier not in self.policy.allowed_scales:
            raise ParserNumericError("numeric_scale_not_allowed")
        if observation.period not in candidate.period_ref.split("|") and observation.period != candidate.period_ref:
            raise ParserNumericError("numeric_period_does_not_match_candidate")
        if not observation.source_coordinate.startswith(candidate.section_or_table_ref):
            raise ParserNumericError("numeric_coordinate_does_not_match_table_context")
        try:
            value = Decimal(observation.raw_value.replace(",", ""))
        except InvalidOperation as exc:
            raise ParserNumericError("numeric_raw_value_invalid") from exc
        candidate_payload = {"candidate_bundle_id": bundle.bundle_id, "candidate_bundle_digest": bundle.bundle_digest, "candidate_id": candidate.candidate_id, "source_ref": candidate.content_ref, "table_or_section_ref": candidate.section_or_table_ref, "parse_policy_ref": self.policy.policy_ref, "fixture_only": True, "parse_status": "parsed_unpromoted"}
        candidate_digest = canonical_digest(candidate_payload)
        parser_candidate = ParserCandidate(parser_candidate_id=f"parser_candidate_{candidate_digest[:20]}", parser_candidate_digest=candidate_digest, **candidate_payload)
        fact_payload = {"parser_candidate_id": parser_candidate.parser_candidate_id, "parser_candidate_digest": parser_candidate.parser_candidate_digest, "row_label": observation.row_label, "normalized_value": format(value, "f"), "unit": observation.unit, "period": observation.period, "source_coordinate": observation.source_coordinate, "scale_multiplier": observation.scale_multiplier, "promotion_status": "unpromoted"}
        fact_digest = canonical_digest(fact_payload)
        fact = NormalizedNumericFact(normalized_fact_id=f"normalized_numeric_fact_{fact_digest[:20]}", normalized_fact_digest=fact_digest, **fact_payload)
        trace_payload = {"normalized_fact_id": fact.normalized_fact_id, "normalized_fact_digest": fact.normalized_fact_digest, "metric_definition_ref": metric_definition_ref, "input_digest": canonical_digest({"raw": observation.raw_value, "fact": fact_digest}), "program_steps": ("decimal_parse", "unit_preserved", "scale_preserved"), "output_value": fact.normalized_value, "promotion_status": "unpromoted"}
        trace_digest = canonical_digest(trace_payload)
        trace = NumericProgramTrace(numeric_trace_id=f"numeric_trace_{trace_digest[:20]}", trace_digest=trace_digest, **trace_payload)
        return ParserNumericResult(status="pass", parser_candidate=parser_candidate, normalized_fact=fact, trace=trace)
