from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal, Mapping

from pydantic import Field

from sec_agent.s4_case_runtime import (
    S4CaseRuntimeBinding,
    consume_s4_case_runtime_binding,
)

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


S3_FINANCIAL_NUMERIC_PACK_CONTRACT_REF = (
    "fin01.s3.financial_numeric_and_fundamental_cell_pack:v1"
)
S3_PARSER_NUMERIC_OWNER_REF = (
    "src.sec_agent.canonical_runtime.parser_numeric:"
    "compile_s3_financial_numeric_and_fundamental_pack"
)


class S3FinancialRowSelector(StrictModel):
    program_cell_id: Literal["value_and_profit_capture"]
    entity_ref: Literal["NVDA"]
    segment_ref: Literal["__company_total__"]
    period: str = Field(min_length=1)
    currency: Literal["USD"]
    unit: Literal["USD"]
    row_label: str = Field(min_length=1)
    metric_family: Literal["revenue", "gross_profit", "operating_income"]


class S3SelectedFinancialRowVersion(StrictModel):
    financial_row_id: str = Field(min_length=1)
    financial_row_digest: str = Field(min_length=1)
    selector: S3FinancialRowSelector
    source_candidate_id: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    source_coordinate: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    scale_multiplier: Literal[1] = 1
    exact_value_authority: Literal[True] = True
    selection_status: Literal["exact_selector_match"] = "exact_selector_match"
    authority_scope: Literal["company_total_exact_fact_fixture"] = (
        "company_total_exact_fact_fixture"
    )
    writer_citable: Literal[False] = False


class S3DerivedMetricInput(StrictModel):
    financial_row_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    metric_family: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    entity_ref: Literal["NVDA"] = "NVDA"
    segment_ref: Literal["__company_total__"] = "__company_total__"
    period: str = Field(min_length=1)
    currency: Literal["USD"] = "USD"
    unit: Literal["USD"] = "USD"


class S3DerivedFinancialMetricVersion(StrictModel):
    derived_metric_id: str = Field(min_length=1)
    derived_metric_digest: str = Field(min_length=1)
    program_cell_id: Literal["value_and_profit_capture"]
    metric_family: Literal["gross_margin", "operating_margin"]
    formula: str = Field(min_length=1)
    formula_version_ref: str = Field(min_length=1)
    inputs: tuple[S3DerivedMetricInput, ...] = Field(min_length=2, max_length=2)
    evidence_refs: tuple[str, ...] = Field(min_length=2, max_length=2)
    rounding_rule: Literal["decimal_half_up_2dp"] = "decimal_half_up_2dp"
    result_value: str = Field(min_length=1)
    result_unit: Literal["percent"] = "percent"
    support_boundary: str = Field(min_length=1)
    cannot_support: tuple[str, ...] = Field(min_length=1)
    specialist_input_eligible: Literal[True] = True
    writer_citable: Literal[False] = False


class S3FundamentalDecisionCellVersion(StrictModel):
    fundamental_cell_id: str = Field(min_length=1)
    fundamental_cell_digest: str = Field(min_length=1)
    program_cell_id: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    selected_financial_row_refs: tuple[str, ...]
    derived_metric_refs: tuple[str, ...]
    availability: Literal[
        "typed_cannot_infer_financial_rows_do_not_prove_demand_durability",
        "bounded_company_total_numeric_support_segment_profit_unattributed",
        "typed_cannot_infer_no_probability_or_impact_numeric",
    ]
    typed_cannot_infer: tuple[str, ...] = Field(min_length=1)
    support_boundary: str = Field(min_length=1)
    specialist_input_eligible: bool
    narrative_fill_authorized: Literal[False] = False


class S3DownstreamDependencyRef(StrictModel):
    dependency_type: Literal["claim", "judgment", "report"]
    dependency_ref: str = Field(min_length=1)
    derived_metric_ref: str = Field(min_length=1)
    authority_scope: Literal["fixture_dependency_anchor_not_canonical_head"] = (
        "fixture_dependency_anchor_not_canonical_head"
    )


class S3NumericCorrectionImpactVersion(StrictModel):
    correction_impact_id: str = Field(min_length=1)
    correction_impact_digest: str = Field(min_length=1)
    corrected_financial_row_ref: str = Field(min_length=1)
    invalidated_derived_metric_refs: tuple[str, ...] = Field(min_length=1)
    invalidated_downstream_refs: tuple[S3DownstreamDependencyRef, ...] = Field(
        min_length=1
    )
    preserved_derived_metric_refs: tuple[str, ...] = Field(min_length=1)
    preserved_downstream_refs: tuple[S3DownstreamDependencyRef, ...] = Field(
        min_length=1
    )
    invalidation_rule: Literal["exact_dependency_closure_only"] = (
        "exact_dependency_closure_only"
    )
    execution_status: Literal["deterministic_fixture_plan_not_business_head_mutation"] = (
        "deterministic_fixture_plan_not_business_head_mutation"
    )


class S3FinancialNumericAndFundamentalPackVersion(StrictModel):
    financial_pack_id: str = Field(min_length=1)
    financial_pack_version_ref: str = Field(min_length=1)
    financial_pack_digest: str = Field(min_length=1)
    financial_pack_contract_ref: str = S3_FINANCIAL_NUMERIC_PACK_CONTRACT_REF
    parser_numeric_owner_ref: str = S3_PARSER_NUMERIC_OWNER_REF
    case_id: str = Field(min_length=1)
    work_unit_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    research_run_id: str = Field(min_length=1)
    execution_profile_version_ref: str = Field(min_length=1)
    decision_surface_contract_ref: str = Field(min_length=1)
    runtime_plan_version_ref: str = Field(min_length=1)
    runtime_plan_digest: str = Field(min_length=1)
    evidence_route_plan_version_ref: str = Field(min_length=1)
    evidence_route_plan_digest: str = Field(min_length=1)
    financial_route_id: Literal["local_gold_sql_financial_table"]
    financial_route_candidate_bundle_ref: str = Field(min_length=1)
    financial_route_promotion_assessment_ref: str = Field(min_length=1)
    selected_financial_rows: tuple[S3SelectedFinancialRowVersion, ...] = Field(
        min_length=3, max_length=3
    )
    derived_metrics: tuple[S3DerivedFinancialMetricVersion, ...] = Field(
        min_length=2, max_length=2
    )
    fundamental_decision_cells: tuple[S3FundamentalDecisionCellVersion, ...] = Field(
        min_length=3, max_length=3
    )
    correction_impact: S3NumericCorrectionImpactVersion
    local_financial_route_read_count: Literal[1] = 1
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    execution_network_calls: Literal[0] = 0
    source_network_calls: Literal[0] = 0
    external_tool_calls: Literal[0] = 0
    live_business_writes: Literal[0] = 0
    runtime_evidence_promotions: Literal[0] = 0
    canonical_head_invalidations: Literal[0] = 0


_S3_EXPECTED_FINANCIAL_ROWS = (
    ("revenue", "Revenues"),
    ("gross_profit", "Gross Profit"),
    ("operating_income", "Operating Income (Loss)"),
)


def _s3_model_digest(model: StrictModel, *excluded: str) -> str:
    payload = model.model_dump(mode="json")
    for field in excluded:
        payload.pop(field, None)
    return canonical_digest(payload)


def _s3_dependency_refs(
    metric: S3DerivedFinancialMetricVersion,
) -> tuple[S3DownstreamDependencyRef, ...]:
    return tuple(
        S3DownstreamDependencyRef(
            dependency_type=dependency_type,
            dependency_ref=(
                f"s3_t04_fixture_{dependency_type}_dependency:"
                f"{metric.derived_metric_id}"
            ),
            derived_metric_ref=metric.derived_metric_id,
        )
        for dependency_type in ("claim", "judgment", "report")
    )


def plan_s3_numeric_correction_invalidation(
    *,
    selected_rows: tuple[S3SelectedFinancialRowVersion, ...],
    derived_metrics: tuple[S3DerivedFinancialMetricVersion, ...],
    corrected_financial_row_ref: str,
) -> S3NumericCorrectionImpactVersion:
    row_refs = {row.financial_row_id for row in selected_rows}
    if corrected_financial_row_ref not in row_refs:
        raise ParserNumericError("s3_numeric_correction_unknown_financial_row")
    invalidated = tuple(
        metric
        for metric in derived_metrics
        if corrected_financial_row_ref
        in {row.financial_row_ref for row in metric.inputs}
    )
    preserved = tuple(metric for metric in derived_metrics if metric not in invalidated)
    if not invalidated or not preserved:
        raise ParserNumericError("s3_numeric_correction_not_selective")
    invalidated_refs = tuple(
        ref for metric in invalidated for ref in _s3_dependency_refs(metric)
    )
    preserved_refs = tuple(
        ref for metric in preserved for ref in _s3_dependency_refs(metric)
    )
    payload = {
        "corrected_financial_row_ref": corrected_financial_row_ref,
        "invalidated_derived_metric_refs": tuple(
            row.derived_metric_id for row in invalidated
        ),
        "invalidated_downstream_refs": tuple(
            row.model_dump(mode="json") for row in invalidated_refs
        ),
        "preserved_derived_metric_refs": tuple(
            row.derived_metric_id for row in preserved
        ),
        "preserved_downstream_refs": tuple(
            row.model_dump(mode="json") for row in preserved_refs
        ),
        "invalidation_rule": "exact_dependency_closure_only",
        "execution_status": (
            "deterministic_fixture_plan_not_business_head_mutation"
        ),
    }
    digest = canonical_digest(payload)
    return S3NumericCorrectionImpactVersion(
        correction_impact_id=f"s3_numeric_correction_impact_{digest[:24]}",
        correction_impact_digest=digest,
        **payload,
    )


def _s3_selected_financial_rows(
    numeric_preview: Mapping[str, Any],
) -> tuple[S3SelectedFinancialRowVersion, ...]:
    if (
        numeric_preview.get("status") != "exact_local_facts_computed"
        or numeric_preview.get("writer_citable") is not False
    ):
        raise ParserNumericError("s3_financial_preview_not_exact_internal_fixture")
    raw_rows = list(numeric_preview.get("facts") or ())
    selected: list[S3SelectedFinancialRowVersion] = []
    periods: set[str] = set()
    for metric_family, expected_label in _S3_EXPECTED_FINANCIAL_ROWS:
        matches = [
            row for row in raw_rows if row.get("metric_family") == metric_family
        ]
        if len(matches) != 1:
            raise ParserNumericError("s3_financial_row_exact_cardinality_required")
        raw = matches[0]
        selector_payload = {
            "program_cell_id": "value_and_profit_capture",
            "entity_ref": str(raw.get("entity_ref") or ""),
            "segment_ref": str(raw.get("segment_ref") or ""),
            "period": str(raw.get("period") or ""),
            "currency": str(raw.get("currency") or ""),
            "unit": str(raw.get("unit") or ""),
            "row_label": str(raw.get("row_label") or ""),
            "metric_family": metric_family,
        }
        if (
            selector_payload["entity_ref"] != "NVDA"
            or selector_payload["segment_ref"] != "__company_total__"
            or selector_payload["currency"] != "USD"
            or selector_payload["unit"] != "USD"
            or selector_payload["row_label"] != expected_label
            or not selector_payload["period"]
            or raw.get("exact_value_authority") is not True
            or int(raw.get("scale_multiplier") or 0) != 1
            or not str(raw.get("candidate_id") or "")
            or not str(raw.get("source_ref") or "")
            or not str(raw.get("source_coordinate") or "")
        ):
            raise ParserNumericError("s3_financial_row_selector_or_authority_mismatch")
        try:
            normalized_value = format(Decimal(str(raw.get("value") or "")), "f")
        except InvalidOperation as exc:
            raise ParserNumericError("s3_financial_row_value_invalid") from exc
        selector = S3FinancialRowSelector.model_validate(selector_payload)
        row_payload = {
            "selector": selector.model_dump(mode="json"),
            "source_candidate_id": str(raw["candidate_id"]),
            "evidence_ref": str(raw["source_ref"]),
            "source_coordinate": str(raw["source_coordinate"]),
            "normalized_value": normalized_value,
            "scale_multiplier": 1,
            "exact_value_authority": True,
            "selection_status": "exact_selector_match",
            "authority_scope": "company_total_exact_fact_fixture",
            "writer_citable": False,
        }
        digest = canonical_digest(row_payload)
        selected.append(
            S3SelectedFinancialRowVersion(
                financial_row_id=f"s3_financial_row_{digest[:24]}",
                financial_row_digest=digest,
                **row_payload,
            )
        )
        periods.add(selector.period)
    if len(periods) != 1:
        raise ParserNumericError("s3_financial_rows_same_period_required")
    return tuple(selected)


def _s3_derived_metric(
    *,
    metric_family: Literal["gross_margin", "operating_margin"],
    numerator: S3SelectedFinancialRowVersion,
    denominator: S3SelectedFinancialRowVersion,
) -> S3DerivedFinancialMetricVersion:
    numerator_value = Decimal(numerator.normalized_value)
    denominator_value = Decimal(denominator.normalized_value)
    if denominator_value <= 0:
        raise ParserNumericError("s3_financial_metric_denominator_invalid")
    result = (numerator_value / denominator_value * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    formula = f"{numerator.selector.metric_family}/revenue*100"
    inputs = tuple(
        S3DerivedMetricInput(
            financial_row_ref=row.financial_row_id,
            evidence_ref=row.evidence_ref,
            metric_family=row.selector.metric_family,
            normalized_value=row.normalized_value,
            period=row.selector.period,
        )
        for row in (numerator, denominator)
    )
    payload = {
        "program_cell_id": "value_and_profit_capture",
        "metric_family": metric_family,
        "formula": formula,
        "formula_version_ref": f"fin01.s3.formula.{metric_family}:v1",
        "inputs": tuple(row.model_dump(mode="json") for row in inputs),
        "evidence_refs": tuple(row.evidence_ref for row in inputs),
        "rounding_rule": "decimal_half_up_2dp",
        "result_value": format(result, "f"),
        "result_unit": "percent",
        "support_boundary": (
            "Supports only NVDA FY2025 company-total reported profitability; "
            "it does not attribute Data Center, accelerator, or cross-chain economics."
        ),
        "cannot_support": (
            "segment_or_product_gross_margin",
            "incremental_AI_profit_capture",
            "supplier_or_customer_economic_allocation",
        ),
        "specialist_input_eligible": True,
        "writer_citable": False,
    }
    digest = canonical_digest(payload)
    return S3DerivedFinancialMetricVersion(
        derived_metric_id=f"s3_derived_financial_metric_{digest[:24]}",
        derived_metric_digest=digest,
        **payload,
    )


def _s3_fundamental_cell(
    *,
    program_cell_id: str,
    owner_role: str,
    selected_financial_row_refs: tuple[str, ...],
    derived_metric_refs: tuple[str, ...],
    availability: str,
    typed_cannot_infer: tuple[str, ...],
    support_boundary: str,
    specialist_input_eligible: bool,
) -> S3FundamentalDecisionCellVersion:
    payload = {
        "program_cell_id": program_cell_id,
        "owner_role": owner_role,
        "selected_financial_row_refs": selected_financial_row_refs,
        "derived_metric_refs": derived_metric_refs,
        "availability": availability,
        "typed_cannot_infer": typed_cannot_infer,
        "support_boundary": support_boundary,
        "specialist_input_eligible": specialist_input_eligible,
        "narrative_fill_authorized": False,
    }
    digest = canonical_digest(payload)
    return S3FundamentalDecisionCellVersion(
        fundamental_cell_id=f"s3_fundamental_cell_{digest[:24]}",
        fundamental_cell_digest=digest,
        **payload,
    )


def compile_s3_financial_numeric_and_fundamental_pack(
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    numeric_preview: Mapping[str, Any],
) -> S3FinancialNumericAndFundamentalPackVersion:
    """Compile the T04 financial pack from one approved local SQL read only."""

    required_runtime_fields = (
        "case_id",
        "work_unit_id",
        "attempt_id",
        "research_run_id",
        "execution_profile_version_ref",
        "decision_surface_contract_ref",
        "runtime_plan_version_ref",
        "runtime_plan_digest",
    )
    if any(not str(runtime_plan.get(field) or "") for field in required_runtime_fields):
        raise ParserNumericError("s3_financial_pack_runtime_identity_required")
    if (
        evidence_route_plan.get("case_id") != runtime_plan["case_id"]
        or evidence_route_plan.get("work_unit_id") != runtime_plan["work_unit_id"]
        or evidence_route_plan.get("attempt_id") != runtime_plan["attempt_id"]
        or evidence_route_plan.get("research_run_id") != runtime_plan["research_run_id"]
        or evidence_route_plan.get("runtime_plan_version_ref")
        != runtime_plan["runtime_plan_version_ref"]
        or evidence_route_plan.get("runtime_plan_digest")
        != runtime_plan["runtime_plan_digest"]
    ):
        raise ParserNumericError("s3_financial_pack_evidence_route_lineage_mismatch")
    value_routes = [
        row
        for row in evidence_route_plan.get("cell_routes") or ()
        if row.get("program_cell_id") == "value_and_profit_capture"
    ]
    if len(value_routes) != 1:
        raise ParserNumericError("s3_financial_pack_value_route_required")
    value_route = value_routes[0]
    steps = list(value_route.get("tool_selection_plan", {}).get("steps") or ())
    if (
        not steps
        or steps[0].get("selected_route_id")
        != "local_gold_sql_financial_table"
        or any(row.get("invocation_status") != "not_executed" for row in value_route.get("tool_gateway_preflights") or ())
        or value_route.get("promotion_assessment", {}).get("decision")
        != "candidate_only_pending_T04_parser_numeric_lineage"
        or value_route.get("promotion_assessment", {}).get("accepted_evidence_refs")
    ):
        raise ParserNumericError("s3_financial_pack_T03_route_boundary_invalid")

    rows = _s3_selected_financial_rows(numeric_preview)
    by_metric = {row.selector.metric_family: row for row in rows}
    metrics = (
        _s3_derived_metric(
            metric_family="gross_margin",
            numerator=by_metric["gross_profit"],
            denominator=by_metric["revenue"],
        ),
        _s3_derived_metric(
            metric_family="operating_margin",
            numerator=by_metric["operating_income"],
            denominator=by_metric["revenue"],
        ),
    )
    row_refs = tuple(row.financial_row_id for row in rows)
    metric_refs = tuple(row.derived_metric_id for row in metrics)
    cells = (
        _s3_fundamental_cell(
            program_cell_id="demand_authenticity_and_sustainability",
            owner_role="industry_analyst",
            selected_financial_row_refs=(),
            derived_metric_refs=(),
            availability=(
                "typed_cannot_infer_financial_rows_do_not_prove_demand_durability"
            ),
            typed_cannot_infer=(
                "company_total_revenue_and_margin_do_not_establish_demand_durability",
            ),
            support_boundary=(
                "No financial row is leaked into the demand cell as a substitute for "
                "deployment, conversion, or counterindicator evidence."
            ),
            specialist_input_eligible=False,
        ),
        _s3_fundamental_cell(
            program_cell_id="value_and_profit_capture",
            owner_role="financial_analyst",
            selected_financial_row_refs=row_refs,
            derived_metric_refs=metric_refs,
            availability=(
                "bounded_company_total_numeric_support_segment_profit_unattributed"
            ),
            typed_cannot_infer=(
                "data_center_or_accelerator_segment_margin_not_disclosed",
                "incremental_AI_profit_capture_not_attributable_from_company_total_rows",
                "cross_chain_economic_allocation_unavailable",
            ),
            support_boundary=(
                "Three exact FY2025 company-total rows support gross and operating "
                "margin only; product, segment, incremental, and cross-chain value "
                "capture remain typed cannot-infer."
            ),
            specialist_input_eligible=True,
        ),
        _s3_fundamental_cell(
            program_cell_id="bottleneck_counterevidence_and_what_would_change",
            owner_role="risk_reviewer",
            selected_financial_row_refs=(),
            derived_metric_refs=(),
            availability="typed_cannot_infer_no_probability_or_impact_numeric",
            typed_cannot_infer=(
                "no_capacity_probability_or_impact_numeric_from_graph_context",
            ),
            support_boundary=(
                "Graph navigation context has no Numeric authority and cannot allocate "
                "capacity, probability, price, revenue, margin, or share."
            ),
            specialist_input_eligible=False,
        ),
    )
    correction = plan_s3_numeric_correction_invalidation(
        selected_rows=rows,
        derived_metrics=metrics,
        corrected_financial_row_ref=by_metric["gross_profit"].financial_row_id,
    )
    plan_ref = str(evidence_route_plan.get("evidence_route_plan_version_ref") or "")
    plan_digest = str(evidence_route_plan.get("evidence_route_plan_digest") or "")
    if not plan_ref or not plan_digest:
        raise ParserNumericError("s3_financial_pack_evidence_route_identity_required")
    payload = {
        "financial_pack_contract_ref": S3_FINANCIAL_NUMERIC_PACK_CONTRACT_REF,
        "parser_numeric_owner_ref": S3_PARSER_NUMERIC_OWNER_REF,
        "case_id": str(runtime_plan["case_id"]),
        "work_unit_id": str(runtime_plan["work_unit_id"]),
        "attempt_id": str(runtime_plan["attempt_id"]),
        "research_run_id": str(runtime_plan["research_run_id"]),
        "execution_profile_version_ref": str(
            runtime_plan["execution_profile_version_ref"]
        ),
        "decision_surface_contract_ref": str(
            runtime_plan["decision_surface_contract_ref"]
        ),
        "runtime_plan_version_ref": str(runtime_plan["runtime_plan_version_ref"]),
        "runtime_plan_digest": str(runtime_plan["runtime_plan_digest"]),
        "evidence_route_plan_version_ref": plan_ref,
        "evidence_route_plan_digest": plan_digest,
        "financial_route_id": "local_gold_sql_financial_table",
        "financial_route_candidate_bundle_ref": str(
            value_route["candidate_bundle"]["bundle_id"]
        ),
        "financial_route_promotion_assessment_ref": str(
            value_route["promotion_assessment"]["assessment_id"]
        ),
        "selected_financial_rows": tuple(
            row.model_dump(mode="json") for row in rows
        ),
        "derived_metrics": tuple(row.model_dump(mode="json") for row in metrics),
        "fundamental_decision_cells": tuple(
            row.model_dump(mode="json") for row in cells
        ),
        "correction_impact": correction.model_dump(mode="json"),
        "local_financial_route_read_count": 1,
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_business_writes": 0,
        "runtime_evidence_promotions": 0,
        "canonical_head_invalidations": 0,
    }
    digest = canonical_digest(payload)
    pack_id = f"s3_financial_numeric_pack_{digest[:24]}"
    return S3FinancialNumericAndFundamentalPackVersion(
        financial_pack_id=pack_id,
        financial_pack_version_ref=f"{pack_id}:v1",
        financial_pack_digest=digest,
        **payload,
    )


def consume_s3_financial_numeric_and_fundamental_pack(
    pack: S3FinancialNumericAndFundamentalPackVersion,
    *,
    runtime_plan_version_ref: str,
    runtime_plan_digest: str,
    evidence_route_plan: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Fail closed on T04 lineage, arithmetic, authority and cell isolation."""

    if (
        pack.runtime_plan_version_ref != runtime_plan_version_ref
        or pack.runtime_plan_digest != runtime_plan_digest
        or pack.evidence_route_plan_version_ref
        != evidence_route_plan.get("evidence_route_plan_version_ref")
        or pack.evidence_route_plan_digest
        != evidence_route_plan.get("evidence_route_plan_digest")
    ):
        raise ParserNumericError("s3_financial_pack_lineage_mismatch")
    value_routes = [
        row
        for row in evidence_route_plan.get("cell_routes") or ()
        if row.get("program_cell_id") == "value_and_profit_capture"
    ]
    if len(value_routes) != 1:
        raise ParserNumericError("s3_financial_pack_value_route_lineage_missing")
    value_route = value_routes[0]
    if (
        pack.financial_route_candidate_bundle_ref
        != value_route.get("candidate_bundle", {}).get("bundle_id")
        or pack.financial_route_promotion_assessment_ref
        != value_route.get("promotion_assessment", {}).get("assessment_id")
        or value_route.get("promotion_assessment", {}).get("decision")
        != "candidate_only_pending_T04_parser_numeric_lineage"
        or value_route.get("promotion_assessment", {}).get("accepted_evidence_refs")
    ):
        raise ParserNumericError("s3_financial_pack_T03_route_refs_mismatch")
    if any(
        (
            pack.model_calls,
            pack.provider_calls,
            pack.execution_network_calls,
            pack.source_network_calls,
            pack.external_tool_calls,
            pack.live_business_writes,
            pack.runtime_evidence_promotions,
            pack.canonical_head_invalidations,
        )
    ):
        raise ParserNumericError("s3_financial_pack_zero_call_boundary_violated")
    digest = _s3_model_digest(
        pack,
        "financial_pack_id",
        "financial_pack_version_ref",
        "financial_pack_digest",
    )
    expected_id = f"s3_financial_numeric_pack_{digest[:24]}"
    if (
        digest != pack.financial_pack_digest
        or pack.financial_pack_id != expected_id
        or pack.financial_pack_version_ref != f"{expected_id}:v1"
    ):
        raise ParserNumericError("s3_financial_pack_digest_or_identity_mismatch")
    rows_by_ref = {row.financial_row_id: row for row in pack.selected_financial_rows}
    if len(rows_by_ref) != 3:
        raise ParserNumericError("s3_financial_pack_row_cardinality_invalid")
    expected_labels = dict(_S3_EXPECTED_FINANCIAL_ROWS)
    if (
        tuple(row.selector.metric_family for row in pack.selected_financial_rows)
        != tuple(row[0] for row in _S3_EXPECTED_FINANCIAL_ROWS)
        or len({row.selector.period for row in pack.selected_financial_rows}) != 1
    ):
        raise ParserNumericError("s3_financial_row_selector_set_invalid")
    for row in pack.selected_financial_rows:
        if (
            _s3_model_digest(row, "financial_row_id", "financial_row_digest")
            != row.financial_row_digest
            or row.financial_row_id
            != f"s3_financial_row_{row.financial_row_digest[:24]}"
            or not row.evidence_ref
            or row.writer_citable
            or row.selector.row_label
            != expected_labels[row.selector.metric_family]
        ):
            raise ParserNumericError("s3_financial_row_digest_or_authority_invalid")
    metrics_by_ref = {row.derived_metric_id: row for row in pack.derived_metrics}
    if len(metrics_by_ref) != 2:
        raise ParserNumericError("s3_financial_pack_metric_cardinality_invalid")
    expected_metric_contract = {
        "gross_margin": (
            "gross_profit/revenue*100",
            "fin01.s3.formula.gross_margin:v1",
            ("gross_profit", "revenue"),
        ),
        "operating_margin": (
            "operating_income/revenue*100",
            "fin01.s3.formula.operating_margin:v1",
            ("operating_income", "revenue"),
        ),
    }
    for metric in pack.derived_metrics:
        expected_formula, expected_formula_ref, expected_inputs = (
            expected_metric_contract[metric.metric_family]
        )
        if (
            _s3_model_digest(metric, "derived_metric_id", "derived_metric_digest")
            != metric.derived_metric_digest
            or metric.derived_metric_id
            != f"s3_derived_financial_metric_{metric.derived_metric_digest[:24]}"
            or tuple(row.evidence_ref for row in metric.inputs)
            != metric.evidence_refs
            or any(row.financial_row_ref not in rows_by_ref for row in metric.inputs)
            or metric.formula != expected_formula
            or metric.formula_version_ref != expected_formula_ref
            or tuple(row.metric_family for row in metric.inputs) != expected_inputs
            or metric.writer_citable
        ):
            raise ParserNumericError("s3_derived_metric_digest_or_lineage_invalid")
        for metric_input in metric.inputs:
            selected_row = rows_by_ref[metric_input.financial_row_ref]
            if (
                metric_input.evidence_ref != selected_row.evidence_ref
                or metric_input.metric_family != selected_row.selector.metric_family
                or metric_input.normalized_value != selected_row.normalized_value
                or metric_input.entity_ref != selected_row.selector.entity_ref
                or metric_input.segment_ref != selected_row.selector.segment_ref
                or metric_input.period != selected_row.selector.period
                or metric_input.currency != selected_row.selector.currency
                or metric_input.unit != selected_row.selector.unit
            ):
                raise ParserNumericError("s3_derived_metric_input_row_mismatch")
        numerator, denominator = metric.inputs
        recomputed = (
            Decimal(numerator.normalized_value)
            / Decimal(denominator.normalized_value)
            * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if format(recomputed, "f") != metric.result_value:
            raise ParserNumericError("s3_derived_metric_result_mismatch")
    expected_cells = (
        "demand_authenticity_and_sustainability",
        "value_and_profit_capture",
        "bottleneck_counterevidence_and_what_would_change",
    )
    if tuple(row.program_cell_id for row in pack.fundamental_decision_cells) != expected_cells:
        raise ParserNumericError("s3_fundamental_cell_order_or_cardinality_invalid")
    for cell in pack.fundamental_decision_cells:
        if (
            _s3_model_digest(cell, "fundamental_cell_id", "fundamental_cell_digest")
            != cell.fundamental_cell_digest
            or cell.fundamental_cell_id
            != f"s3_fundamental_cell_{cell.fundamental_cell_digest[:24]}"
            or cell.narrative_fill_authorized
        ):
            raise ParserNumericError("s3_fundamental_cell_digest_or_boundary_invalid")
        if cell.program_cell_id == "value_and_profit_capture":
            if (
                set(cell.selected_financial_row_refs) != set(rows_by_ref)
                or set(cell.derived_metric_refs) != set(metrics_by_ref)
                or not cell.specialist_input_eligible
            ):
                raise ParserNumericError("s3_value_cell_financial_pack_incomplete")
        elif (
            cell.selected_financial_row_refs
            or cell.derived_metric_refs
            or cell.specialist_input_eligible
        ):
            raise ParserNumericError("s3_financial_rows_leaked_to_nonvalue_cell")
    correction = pack.correction_impact
    if (
        _s3_model_digest(
            correction, "correction_impact_id", "correction_impact_digest"
        )
        != correction.correction_impact_digest
        or correction.correction_impact_id
        != f"s3_numeric_correction_impact_{correction.correction_impact_digest[:24]}"
    ):
        raise ParserNumericError("s3_numeric_correction_impact_digest_invalid")
    expected_correction = plan_s3_numeric_correction_invalidation(
        selected_rows=pack.selected_financial_rows,
        derived_metrics=pack.derived_metrics,
        corrected_financial_row_ref=correction.corrected_financial_row_ref,
    )
    if expected_correction != correction:
        raise ParserNumericError("s3_numeric_correction_dependency_closure_mismatch")
    return tuple(
        {
            "program_cell_id": cell.program_cell_id,
            "fundamental_cell_id": cell.fundamental_cell_id,
            "selected_financial_row_refs": list(cell.selected_financial_row_refs),
            "derived_metric_refs": list(cell.derived_metric_refs),
            "availability": cell.availability,
            "specialist_input_eligible": cell.specialist_input_eligible,
            "consumption_mode": (
                "deterministic_parser_numeric_and_fundamental_cell_validation"
            ),
            "model_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
            "business_writes": 0,
        }
        for cell in pack.fundamental_decision_cells
    )


def consume_s4_case_runtime_financial_numeric(
    binding: S4CaseRuntimeBinding,
) -> dict[str, Any]:
    """Inject exact issuer/scope/formula rules into the Numeric owner."""

    return consume_s4_case_runtime_binding(
        binding, "financial_numeric_pack"
    ).model_dump(mode="json")
