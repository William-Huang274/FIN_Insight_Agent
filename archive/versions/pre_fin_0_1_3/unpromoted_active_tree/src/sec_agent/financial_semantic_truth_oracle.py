from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping


LAYER_SHAPE = "shape_integrity"
LAYER_FINANCIAL_TRUTH = "financial_truth"
LAYER_ANALYSIS_QUALITY = "analysis_quality"
LAYER_PRODUCT_USABILITY = "product_usability"

LAYER_OWNERS = {
    LAYER_SHAPE: "S0_contract_and_integrity",
    LAYER_FINANCIAL_TRUTH: "S1_financial_truth_chain",
    LAYER_ANALYSIS_QUALITY: "S2_S3_research_quality",
    LAYER_PRODUCT_USABILITY: "S4_product_workflow",
}

_REQUIRED_FIELDS = (
    "record_id",
    "case_key",
    "entity_ref",
    "issuer_id",
    "metric_family",
    "aggregation_scope",
    "raw_value",
    "normalized_value",
    "currency",
    "unit",
    "scale_multiplier",
    "fiscal_year",
    "fiscal_period",
    "period_role",
    "period_end",
    "source_filed_at",
    "as_of_date",
    "snapshot_at",
    "source_ref",
    "source_locator",
)
_TRUTH_FIELDS = (
    "case_key",
    "entity_ref",
    "issuer_id",
    "metric_family",
    "aggregation_scope",
    "raw_value",
    "normalized_value",
    "currency",
    "unit",
    "scale_multiplier",
    "fiscal_year",
    "fiscal_period",
    "period_role",
    "period_start",
    "period_end",
    "duration_days",
    "source_filed_at",
    "published_at",
    "as_of_date",
    "snapshot_at",
    "source_ref",
    "source_locator",
)
_PERIOD_ROLES = {"annual", "quarter", "ytd", "instant"}


@dataclass(frozen=True)
class OracleFinding:
    code: str
    layer: str
    owner: str
    field: str | None
    expected: Any
    observed: Any
    detail: str

    @property
    def blocks_financial_truth_entry(self) -> bool:
        return self.layer in {LAYER_SHAPE, LAYER_FINANCIAL_TRUTH}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "layer": self.layer,
            "owner": self.owner,
            "field": self.field,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "blocks_financial_truth_entry": self.blocks_financial_truth_entry,
        }


def classify_stage_finding(*, code: str, layer: str, detail: str) -> OracleFinding:
    if layer not in LAYER_OWNERS:
        raise ValueError(f"unknown_oracle_layer:{layer}")
    return OracleFinding(
        code=code,
        layer=layer,
        owner=LAYER_OWNERS[layer],
        field=None,
        expected=None,
        observed=None,
        detail=detail,
    )


def evaluate_financial_truth(
    candidate: Mapping[str, Any],
    reviewed_truth: Mapping[str, Any],
) -> dict[str, Any]:
    findings = [*_shape_findings(candidate), *_truth_findings(candidate, reviewed_truth)]
    findings.extend(_semantic_invariant_findings(candidate))
    findings.extend(_formula_findings(candidate))
    findings = _dedupe_findings(findings)
    blocking = [row for row in findings if row.blocks_financial_truth_entry]
    return {
        "record_id": str(candidate.get("record_id") or ""),
        "reviewed_truth_id": str(reviewed_truth.get("record_id") or ""),
        "status": "blocked_before_s1_s3" if blocking else "pass_financial_truth_ceiling",
        "financial_truth_entry_allowed": not blocking,
        "finding_count": len(findings),
        "findings_by_layer": {
            layer: sum(1 for row in findings if row.layer == layer)
            for layer in LAYER_OWNERS
        },
        "findings": [row.as_dict() for row in findings],
    }


def _shape_findings(candidate: Mapping[str, Any]) -> list[OracleFinding]:
    findings: list[OracleFinding] = []
    for field in _REQUIRED_FIELDS:
        if candidate.get(field) in (None, ""):
            findings.append(_finding("required_field_missing", LAYER_SHAPE, field, "non_empty", candidate.get(field)))
    role = candidate.get("period_role")
    if role not in _PERIOD_ROLES:
        findings.append(_finding("period_role_invalid", LAYER_SHAPE, "period_role", sorted(_PERIOD_ROLES), role))
    for field in ("period_start", "period_end", "source_filed_at", "published_at", "as_of_date", "snapshot_at"):
        value = candidate.get(field)
        if value not in (None, "") and _parse_date(value) is None:
            findings.append(_finding("date_value_invalid", LAYER_SHAPE, field, "ISO_date_or_datetime", value))
    for field in ("raw_value", "normalized_value", "scale_multiplier"):
        value = candidate.get(field)
        if value not in (None, "") and _decimal(value) is None:
            findings.append(_finding("numeric_value_invalid", LAYER_SHAPE, field, "decimal", value))
    scale = _decimal(candidate.get("scale_multiplier"))
    if scale is not None and scale <= 0:
        findings.append(_finding("scale_multiplier_not_positive", LAYER_SHAPE, "scale_multiplier", ">0", candidate.get("scale_multiplier")))
    return findings


def _truth_findings(candidate: Mapping[str, Any], reviewed: Mapping[str, Any]) -> list[OracleFinding]:
    findings: list[OracleFinding] = []
    for field in _TRUTH_FIELDS:
        expected = reviewed.get(field)
        observed = candidate.get(field)
        if field in {"raw_value", "normalized_value", "scale_multiplier"}:
            equal = _decimal(expected) is not None and _decimal(expected) == _decimal(observed)
        else:
            equal = expected == observed
        if not equal:
            findings.append(_finding(f"{field}_mismatch", LAYER_FINANCIAL_TRUTH, field, expected, observed))
    return findings


def _semantic_invariant_findings(candidate: Mapping[str, Any]) -> list[OracleFinding]:
    findings: list[OracleFinding] = []
    role = candidate.get("period_role")
    fiscal_period = str(candidate.get("fiscal_period") or "")
    start = _parse_date(candidate.get("period_start"))
    end = _parse_date(candidate.get("period_end"))
    observed_duration = candidate.get("duration_days")
    calculated_duration = (end - start).days + 1 if start and end else None
    if role == "instant":
        if start is not None:
            findings.append(_finding("instant_fact_has_period_start", LAYER_FINANCIAL_TRUTH, "period_start", None, candidate.get("period_start")))
    elif start is None:
        findings.append(_finding("duration_fact_missing_period_start", LAYER_FINANCIAL_TRUTH, "period_start", "ISO_date", candidate.get("period_start")))
    if calculated_duration is not None and observed_duration != calculated_duration:
        findings.append(_finding("duration_days_mismatch", LAYER_FINANCIAL_TRUTH, "duration_days", calculated_duration, observed_duration))
    if role == "annual":
        if fiscal_period != "FY":
            findings.append(_finding("annual_fiscal_period_not_FY", LAYER_FINANCIAL_TRUTH, "fiscal_period", "FY", fiscal_period))
        if calculated_duration is not None and not 330 <= calculated_duration <= 380:
            findings.append(_finding("annual_duration_out_of_range", LAYER_FINANCIAL_TRUTH, "duration_days", "330..380", calculated_duration))
    if role == "quarter":
        if fiscal_period not in {"Q1", "Q2", "Q3", "Q4"}:
            findings.append(_finding("quarter_fiscal_period_invalid", LAYER_FINANCIAL_TRUTH, "fiscal_period", "Q1..Q4", fiscal_period))
        if calculated_duration is not None and not 75 <= calculated_duration <= 110:
            findings.append(_finding("quarter_duration_out_of_range", LAYER_FINANCIAL_TRUTH, "duration_days", "75..110", calculated_duration))
    raw = _decimal(candidate.get("raw_value"))
    normalized = _decimal(candidate.get("normalized_value"))
    scale = _decimal(candidate.get("scale_multiplier"))
    if raw is not None and normalized is not None and scale is not None and raw * scale != normalized:
        findings.append(_finding("normalized_value_scale_mismatch", LAYER_FINANCIAL_TRUTH, "normalized_value", str(raw * scale), candidate.get("normalized_value")))
    return findings


def _formula_findings(candidate: Mapping[str, Any]) -> list[OracleFinding]:
    formula = candidate.get("formula")
    if formula in (None, {}):
        return []
    if not isinstance(formula, Mapping):
        return [_finding("formula_shape_invalid", LAYER_SHAPE, "formula", "object", type(formula).__name__)]
    operator = formula.get("operator")
    inputs = formula.get("input_values")
    output = _decimal(formula.get("output_value"))
    if operator not in {"add", "subtract", "multiply", "divide"} or not isinstance(inputs, list) or len(inputs) < 2 or output is None:
        return [_finding("formula_shape_invalid", LAYER_SHAPE, "formula", "typed_operator_inputs_output", formula)]
    values = [_decimal(value) for value in inputs]
    if any(value is None for value in values):
        return [_finding("formula_input_invalid", LAYER_SHAPE, "formula.input_values", "decimals", inputs)]
    exact = [value for value in values if value is not None]
    if operator == "add":
        recomputed = sum(exact, Decimal("0"))
    elif operator == "subtract":
        recomputed = exact[0] - sum(exact[1:], Decimal("0"))
    elif operator == "multiply":
        recomputed = Decimal("1")
        for value in exact:
            recomputed *= value
    else:
        if any(value == 0 for value in exact[1:]):
            return [_finding("formula_division_by_zero", LAYER_FINANCIAL_TRUTH, "formula.input_values", "nonzero_denominator", inputs)]
        recomputed = exact[0]
        for value in exact[1:]:
            recomputed /= value
    tolerance = _decimal(formula.get("tolerance", "0")) or Decimal("0")
    if abs(recomputed - output) > tolerance:
        return [_finding("formula_recalculation_mismatch", LAYER_FINANCIAL_TRUTH, "formula.output_value", str(recomputed), str(output))]
    return []


def _finding(code: str, layer: str, field: str, expected: Any, observed: Any) -> OracleFinding:
    return OracleFinding(
        code=code,
        layer=layer,
        owner=LAYER_OWNERS[layer],
        field=field,
        expected=expected,
        observed=observed,
        detail=f"{field}: expected {expected!r}, observed {observed!r}",
    )


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _dedupe_findings(findings: Iterable[OracleFinding]) -> list[OracleFinding]:
    rows: list[OracleFinding] = []
    seen: set[tuple[str, str | None]] = set()
    for finding in findings:
        key = (finding.code, finding.field)
        if key not in seen:
            seen.add(key)
            rows.append(finding)
    return rows
