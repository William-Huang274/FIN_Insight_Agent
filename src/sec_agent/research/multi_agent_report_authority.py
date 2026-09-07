from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from typing import Any, Mapping, Sequence

from .current_consumer import (
    CURRENT_RESEARCH_MODEL_TEXT_SERVER_PATTERN,
    CurrentResearchConsumerError,
    bind_current_research_model_text_schema_definition,
    compile_current_research_model_text_schema,
    validate_current_research_model_text,
)
from .reviewed_evidence_pack import canonical_digest
from .report_boundary import validate_report_boundary_disposition_register


MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION = (
    "fin_ia_multi_agent_report_authority_catalog_v1_0"
)
MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION = (
    "fin_ia_multi_agent_report_authority_catalog_v1_1"
)
MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_protected_report_draft_v1_1"
)
MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION = (
    "fin_ia_multi_agent_protected_report_draft_v1_0"
)
MULTI_AGENT_PROTECTED_RENDERED_REPORT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_protected_rendered_report_v1_1"
)
MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION = (
    "fin_ia_multi_agent_protected_report_reference_patch_v1_0"
)
MULTI_AGENT_REPORT_QUALITY_POLICY_LEGACY_VERSION = (
    "fin_ia_multi_agent_report_quality_policy_v1_0"
)
MULTI_AGENT_REPORT_QUALITY_POLICY_VERSION = (
    "fin_ia_multi_agent_report_quality_policy_v1_1"
)

_EMPTY_REF_PLACEHOLDER = "__NO_AUTHORIZED_REF__"
_CLAUSE_FIELDS = {
    "model_text",
    "source_workpaper_agent_ids",
    "source_claim_refs",
    "evidence_refs",
    "authority_refs",
    "gap_refs",
}
_ALIAS = re.compile(
    r"\b(?:EV|NUM|REL|GAP|QF|WPCLAIM)::[A-Z0-9:_-]{4,160}\b",
    re.IGNORECASE,
)
_PROTECTED_SURFACE = re.compile(
    r"(?:"
    r"\b20\d{2}-\d{2}-\d{2}\b"
    r"|\b(?:FY|CY)\s*\d{2,4}(?:\s*Q[1-4])?\b"
    r"|\bQ[1-4]\s*(?:FY|CY)?\s*\d{2,4}\b"
    r"|[$€£¥￥]\s*[-+]?\d[\d,]*(?:\.\d+)?(?:\s*[BMK])?"
    r"|[-+]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|bps?|pp)\b"
    r"|\b\d[\d,]*(?:\.\d+)?\s*[BMK]\b"
    r"|\b\d[\d,]*(?:\.\d+)?\b"
    r")",
    re.IGNORECASE,
)

# Recommended narrative density is a product-quality signal, not a financial
# truth boundary.  The larger safety capacities protect transport and artifact
# materialization while allowing a complete, well-supported paragraph to
# survive for later content-quality assessment.
_REPORT_TEXT_LIMITS = {
    "topic": {"minimum": 8, "recommended_maximum": 180, "safety_maximum": 720},
    "heading": {"minimum": 4, "recommended_maximum": 140, "safety_maximum": 560},
    "executive": {
        "minimum": 24,
        "recommended_maximum": 900,
        "safety_maximum": 2400,
    },
    "section": {
        "minimum": 12,
        "recommended_maximum": 900,
        "safety_maximum": 2400,
    },
    "gap": {"minimum": 12, "recommended_maximum": 700, "safety_maximum": 1800},
    "wwc": {"minimum": 12, "recommended_maximum": 700, "safety_maximum": 1800},
    "confidence": {
        "minimum": 20,
        "recommended_maximum": 700,
        "safety_maximum": 1800,
    },
}


class MultiAgentReportAuthorityError(ValueError):
    def __init__(
        self, code: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        self.code = code
        self.details = deepcopy(dict(details or {}))
        super().__init__(code)


def _require(
    condition: bool,
    code: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> None:
    if not condition:
        raise MultiAgentReportAuthorityError(code, details=details)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _decimal(value: object, code: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MultiAgentReportAuthorityError(code) from exc
    _require(parsed.is_finite(), code)
    return parsed


def _plain_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _rounded(value: Decimal, places: str = "0.01") -> str:
    return _plain_decimal(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def _format_currency(value: Decimal, currency: str) -> tuple[str, dict[str, Any]]:
    symbol = {"USD": "$", "CNY": "CN¥", "EUR": "€", "JPY": "¥"}.get(
        currency.upper(), currency.upper() + " "
    )
    absolute = abs(value)
    scales = (
        (Decimal("1000000000"), "B"),
        (Decimal("1000000"), "M"),
        (Decimal("1000"), "K"),
    )
    for divisor, suffix in scales:
        if absolute >= divisor:
            scaled = value / divisor
            rendered = _plain_decimal(scaled)
            compact_is_exactly_readable = (
                len(rendered.split(".")[-1]) <= 6 if "." in rendered else True
            )
            if compact_is_exactly_readable:
                return f"{symbol}{rendered}{suffix}", {
                    "rule": "exact_power_of_thousand_compaction",
                    "divisor": _plain_decimal(divisor),
                    "source_value": _plain_decimal(value),
                    "rendered_value": rendered,
                    "lossless": True,
                }
    rendered = f"{value:,.0f}" if value == value.to_integral() else f"{value:,f}"
    return f"{symbol}{rendered}", {
        "rule": "exact_unscaled_currency",
        "source_value": _plain_decimal(value),
        "lossless": True,
    }


def _format_value(value: object, unit: object) -> tuple[str, dict[str, Any]]:
    parsed = _decimal(value, "multi_agent_report_numeric_value_invalid")
    normalized_unit = str(unit or "").strip()
    if normalized_unit.upper() in {"USD", "CNY", "EUR", "JPY"}:
        return _format_currency(parsed, normalized_unit)
    if normalized_unit.casefold() in {"percent", "percentage", "%"}:
        rendered = _rounded(parsed)
        return f"{rendered}%", {
            "rule": "round_half_up_two_decimal_percent",
            "source_value": _plain_decimal(parsed),
            "rendered_value": rendered,
            "lossless": parsed == Decimal(rendered),
        }
    if normalized_unit.casefold() in {"count", "shares", "units"}:
        rendered = (
            f"{parsed:,.0f}"
            if parsed == parsed.to_integral()
            else _plain_decimal(parsed)
        )
        return rendered, {
            "rule": "exact_count",
            "source_value": _plain_decimal(parsed),
            "lossless": True,
        }
    suffix = f" {normalized_unit}" if normalized_unit else ""
    return _plain_decimal(parsed) + suffix, {
        "rule": "exact_decimal_with_declared_unit",
        "source_value": _plain_decimal(parsed),
        "lossless": True,
    }


def _period_label(row: Mapping[str, Any], *, relation_prefix: str = "") -> str:
    fiscal_year = row.get(f"{relation_prefix}fiscal_year")
    fiscal_period = str(row.get("fiscal_period") or "").strip()
    period_end = str(row.get(f"{relation_prefix}period_end") or "").strip()
    parts: list[str] = []
    if fiscal_year not in (None, ""):
        parts.append(f"FY{fiscal_year}")
    if fiscal_period:
        parts.append(fiscal_period)
    if not parts and period_end:
        parts.append(f"period ended {period_end}")
    elif period_end:
        parts.append(f"ended {period_end}")
    return " ".join(parts) or "declared period"


def _metric_label(value: object) -> str:
    return str(value or "metric").replace("_", " ").strip()


def _valid_authority_catalog_schema(value: object) -> bool:
    return value in {
        MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION,
        MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION,
    }


def _numeric_presentation(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(row.get("numeric_ref") or "")
    _require(ref.startswith("NUM::"), "multi_agent_report_numeric_ref_invalid")
    value_surface, receipt = _format_value(row.get("value_decimal"), row.get("unit"))
    surface = " ".join(
        part
        for part in (
            str(row.get("ticker") or "").strip(),
            _period_label(row),
            _metric_label(row.get("metric_id")) + ":",
            value_surface,
        )
        if part
    )
    return {
        "authority_ref": ref,
        "authority_kind": "numeric_fact",
        "display_surface": surface,
        "source_numeric_refs": [ref],
        "source_numeric_relation_refs": [],
        "presentation_receipt": {
            **receipt,
            "unit": str(row.get("unit") or ""),
            "period_start": row.get("period_start"),
            "period_end": row.get("period_end"),
            "authority_mode": row.get("authority_mode"),
            "formula_trace": deepcopy(row.get("formula_trace")),
        },
    }


def _relation_presentation(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(row.get("numeric_relation_ref") or "")
    _require(ref.startswith("REL::"), "multi_agent_report_relation_ref_invalid")
    change_kind = "absolute_change"
    raw_change = row.get("absolute_change_decimal")
    unit = str(row.get("unit") or "")
    suffix = ""
    if row.get("percentage_point_change_decimal") not in (None, ""):
        change_kind = "percentage_point_change"
        raw_change = row["percentage_point_change_decimal"]
        unit = "percentage_points"
        suffix = "pp"
    elif row.get("percent_change_decimal") not in (None, ""):
        change_kind = "percent_change"
        raw_change = row["percent_change_decimal"]
        unit = "percent"
        suffix = "%"
    parsed = _decimal(raw_change, "multi_agent_report_relation_value_invalid")
    if suffix:
        display_value = _rounded(parsed)
        change_surface = ("+" if parsed > 0 else "") + display_value + suffix
        receipt = {
            "rule": "round_half_up_two_decimal_relation",
            "source_value": _plain_decimal(parsed),
            "rendered_value": display_value,
            "lossless": parsed == Decimal(display_value),
        }
    else:
        rendered, receipt = _format_value(parsed, unit)
        change_surface = ("+" if parsed > 0 else "") + rendered
    current_period = str(row.get("current_period_end") or "current period")
    comparison_period = str(row.get("comparison_period_end") or "comparison period")
    surface = (
        f"{str(row.get('ticker') or '').strip()} "
        f"{_metric_label(row.get('metric_id'))}: {change_surface} "
        f"({current_period} versus {comparison_period})"
    ).strip()
    return {
        "authority_ref": ref,
        "authority_kind": "numeric_relation",
        "display_surface": surface,
        "source_numeric_refs": sorted(
            {
                str(row.get("current_numeric_ref") or ""),
                str(row.get("comparison_numeric_ref") or ""),
            }
            - {""}
        ),
        "source_numeric_relation_refs": [ref],
        "presentation_receipt": {
            **receipt,
            "change_kind": change_kind,
            "unit": unit,
            "relation_type": row.get("relation_type"),
            "direction": row.get("direction"),
            "current_period_end": row.get("current_period_end"),
            "comparison_period_end": row.get("comparison_period_end"),
            "authority_mode": row.get("authority_mode"),
        },
    }


def _hydrate_relation_presentation_row(
    row: Mapping[str, Any],
    *,
    numeric_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive the display change for current-runtime operand-only relations."""

    compiled = deepcopy(dict(row))
    if any(
        compiled.get(field) not in (None, "")
        for field in (
            "absolute_change_decimal",
            "percentage_point_change_decimal",
            "percent_change_decimal",
        )
    ):
        return compiled
    current_ref = str(compiled.get("current_numeric_ref") or "")
    comparison_ref = str(compiled.get("comparison_numeric_ref") or "")
    _require(
        current_ref in numeric_rows and comparison_ref in numeric_rows,
        "multi_agent_report_relation_operand_unresolved",
    )
    current = numeric_rows[current_ref]
    comparison = numeric_rows[comparison_ref]
    _require(
        str(current.get("ticker") or "")
        == str(comparison.get("ticker") or "")
        and str(current.get("metric_id") or "")
        == str(comparison.get("metric_id") or "")
        == str(compiled.get("metric_id") or "")
        and str(current.get("unit") or "")
        == str(comparison.get("unit") or ""),
        "multi_agent_report_relation_operand_semantics_invalid",
    )
    current_value = _decimal(
        current.get("value_decimal"),
        "multi_agent_report_relation_operand_value_invalid",
    )
    comparison_value = _decimal(
        comparison.get("value_decimal"),
        "multi_agent_report_relation_operand_value_invalid",
    )
    delta = current_value - comparison_value
    unit = str(current.get("unit") or "")
    if unit == "percent":
        compiled["percentage_point_change_decimal"] = _plain_decimal(delta)
    else:
        _require(
            comparison_value != 0,
            "multi_agent_report_relation_comparison_zero",
        )
        percent_change = delta / comparison_value * Decimal("100")
        compiled["percent_change_decimal"] = _plain_decimal(percent_change)
    compiled.update(
        {
            "ticker": str(current.get("ticker") or ""),
            "unit": unit,
            "current_period_end": current.get("period_end"),
            "comparison_period_end": comparison.get("period_end"),
            "authority_mode": "deterministically_hydrated_numeric_relation",
            "direction": (
                "positive" if delta > 0 else "negative" if delta < 0 else "flat"
            ),
        }
    )
    return compiled


def _bounded_presentation(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(row.get("authority_ref") or "")
    _require(ref.startswith("PRES::"), "multi_agent_report_bounded_ref_invalid")
    values = row.get("normalized_values")
    _require(
        isinstance(values, list) and bool(values),
        "multi_agent_report_bounded_values_invalid",
    )
    rendered_values = [_format_value(value, row.get("unit"))[0] for value in values]
    kind = str(row.get("value_kind") or "")
    if kind == "closed_range":
        _require(
            len(rendered_values) == 2,
            "multi_agent_report_bounded_range_invalid",
        )
        value_surface = rendered_values[0] + "–" + rendered_values[1]
    else:
        _require(
            len(rendered_values) == 1,
            "multi_agent_report_bounded_scalar_invalid",
        )
        prefix = {
            "greater_than": "more than ",
            "greater_than_or_equal": "at least ",
            "less_than": "less than ",
            "less_than_or_equal": "at most ",
            "approximate": "approximately ",
        }.get(kind)
        _require(prefix is not None, "multi_agent_report_bounded_kind_invalid")
        value_surface = prefix + rendered_values[0]
    period = _period_label(row)
    surface = " ".join(
        part
        for part in (
            str(row.get("ticker") or "").strip(),
            period,
            _metric_label(row.get("semantic_metric_key")) + ":",
            value_surface,
            "(" + str(row.get("fact_status") or "bounded source disclosure") + ")",
        )
        if part
    )
    return {
        "authority_ref": ref,
        "authority_kind": "bounded_source_presentation",
        "display_surface": surface,
        "source_numeric_refs": [],
        "source_numeric_relation_refs": [],
        "source_evidence_refs": [str(row.get("source_evidence_ref") or "")],
        "presentation_receipt": {
            "rule": "deterministic_bounded_source_presentation",
            "value_kind": kind,
            "normalized_values": [str(value) for value in values],
            "unit": str(row.get("unit") or ""),
            "period_start": row.get("period_start"),
            "period_end": row.get("period_end"),
            "fact_status": row.get("fact_status"),
            "qualifier": row.get("qualifier"),
            "point_estimate_forbidden": row.get("point_estimate_forbidden"),
            "source_receipt": deepcopy(row.get("source_receipt")),
            "claim_boundary": row.get("claim_boundary"),
        },
    }


def _temporal_presentation(row: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(row.get("authority_ref") or "")
    _require(ref.startswith("TEMP::"), "multi_agent_report_temporal_ref_invalid")
    date = str(row.get("date") or "")
    _require(
        bool(re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date)),
        "multi_agent_report_temporal_date_invalid",
    )
    kind = str(row.get("temporal_kind") or "")
    _require(
        kind == "source_reporting_period_end",
        "multi_agent_report_temporal_kind_invalid",
    )
    return {
        "authority_ref": ref,
        "authority_kind": "source_temporal_authority",
        "display_surface": "source reporting period ended " + date,
        "source_numeric_refs": [],
        "source_numeric_relation_refs": [],
        "source_evidence_refs": [str(row.get("source_evidence_ref") or "")],
        "presentation_receipt": {
            "rule": "typed_source_temporal_rendering",
            "temporal_kind": kind,
            "date": date,
        },
    }


def _context_agent_id(context: Mapping[str, Any]) -> str:
    direct = str(context.get("agent_id") or "")
    if direct:
        return direct
    agent = context.get("agent") or {}
    return str(agent.get("agent_id") or "") if isinstance(agent, Mapping) else ""


def _normalize_contexts(
    specialist_contexts: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if isinstance(specialist_contexts, Mapping):
        rows = {
            str(agent_id): deepcopy(dict(context))
            for agent_id, context in specialist_contexts.items()
        }
    else:
        rows = {}
        for raw in specialist_contexts:
            context = deepcopy(dict(raw))
            agent_id = _context_agent_id(context)
            _require(agent_id and agent_id not in rows, "multi_agent_report_context_agent_invalid")
            rows[agent_id] = context
    _require(bool(rows), "multi_agent_report_contexts_missing")
    for agent_id, context in rows.items():
        declared = _context_agent_id(context)
        _require(
            not declared or declared == agent_id,
            "multi_agent_report_context_agent_mismatch",
        )
    return rows


def _merge_catalog_row(
    target: dict[str, dict[str, Any]],
    *,
    ref: str,
    row: Mapping[str, Any],
    code: str,
) -> None:
    compiled = deepcopy(dict(row))
    if ref in target:
        _require(target[ref] == compiled, code)
    else:
        target[ref] = compiled


def _merge_numeric_catalog_row(
    target: dict[str, dict[str, Any]],
    *,
    ref: str,
    row: Mapping[str, Any],
) -> None:
    """Merge one semantic NUM authority across role-local projections.

    Current dynamic role contexts may assign different internal NumericFact ids
    to the same deterministic operands.  The public ``NUM`` ref and every
    financial semantic field remain identical.  Preserve the union of those
    internal lineage ids rather than treating role-local ids as a financial
    authority conflict.
    """

    compiled = deepcopy(dict(row))
    if ref not in target:
        target[ref] = compiled
        return
    existing = deepcopy(target[ref])
    if existing == compiled:
        return
    existing_trace = existing.get("formula_trace")
    compiled_trace = compiled.get("formula_trace")
    _require(
        isinstance(existing_trace, Mapping)
        and isinstance(compiled_trace, Mapping),
        "multi_agent_report_numeric_authority_conflict",
    )
    existing_trace_body = deepcopy(dict(existing_trace))
    compiled_trace_body = deepcopy(dict(compiled_trace))
    existing_ids = {
        str(value)
        for value in existing_trace_body.pop("input_numeric_fact_ids", ())
    }
    compiled_ids = {
        str(value)
        for value in compiled_trace_body.pop("input_numeric_fact_ids", ())
    }
    existing_without_trace = deepcopy(existing)
    compiled_without_trace = deepcopy(compiled)
    existing_without_trace["formula_trace"] = existing_trace_body
    compiled_without_trace["formula_trace"] = compiled_trace_body
    _require(
        existing_without_trace == compiled_without_trace
        and existing_ids
        and compiled_ids,
        "multi_agent_report_numeric_authority_conflict",
    )
    merged_trace = deepcopy(existing_trace_body)
    merged_trace["input_numeric_fact_ids"] = sorted(existing_ids | compiled_ids)
    existing["formula_trace"] = merged_trace
    target[ref] = existing


def compile_multi_agent_report_authority_catalog(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    specialist_contexts: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compile the only final-report surfaces the Harness may render.

    Raw Evidence excerpts remain visible to research agents but do not become
    numeric output authority here.  A material number must already be a typed
    ``NUM``/``REL`` (or a future typed presentation kind) before the Writer can
    select it.
    """

    contexts = _normalize_contexts(specialist_contexts)
    papers = [deepcopy(dict(row)) for row in workpapers]
    _require(bool(papers), "multi_agent_report_workpapers_missing")
    by_agent: dict[str, dict[str, Any]] = {}
    for workpaper in papers:
        agent_id = str(workpaper.get("agent_id") or "")
        _require(
            agent_id and agent_id not in by_agent and agent_id in contexts,
            "multi_agent_report_workpaper_agent_invalid",
        )
        context_digest = str(contexts[agent_id].get("context_digest") or "")
        _require(
            context_digest
            and context_digest == str(workpaper.get("context_digest") or ""),
            "multi_agent_report_workpaper_context_drift",
        )
        by_agent[agent_id] = workpaper
    _require(
        set(by_agent) == set(contexts),
        "multi_agent_report_workpaper_context_coverage_invalid",
    )

    identities = []
    evidence_rows: dict[str, dict[str, Any]] = {}
    numeric_rows: dict[str, dict[str, Any]] = {}
    estimate_rows: dict[str, dict[str, Any]] = {}
    relation_rows: dict[str, dict[str, Any]] = {}
    gap_rows: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(contexts):
        context = contexts[agent_id]
        view = _mapping(
            context.get("cell_analysis_view"),
            "multi_agent_report_cell_view_missing",
        )
        # Legacy preview contexts nested identity inside ``cell_analysis_view``;
        # the current dynamic runtime keeps the same identity at context top
        # level.  Both are immutable model-context surfaces, so accept either
        # location while still requiring all six contexts to agree below.
        identity = deepcopy(
            dict(
                _mapping(
                    view.get("case_identity") or context.get("case_identity"),
                    "multi_agent_report_case_identity_missing",
                )
            )
        )
        identities.append(identity)
        for raw in view.get("evidence_fact_catalog") or ():
            ref = str(raw.get("evidence_ref") or "")
            _require(ref.startswith("EV::"), "multi_agent_report_evidence_ref_invalid")
            _merge_catalog_row(
                evidence_rows,
                ref=ref,
                row=raw,
                code="multi_agent_report_evidence_authority_conflict",
            )
        for raw in view.get("numeric_fact_catalog") or ():
            ref = str(raw.get("numeric_ref") or "")
            if ref:
                _require(
                    ref.startswith("NUM::"),
                    "multi_agent_report_numeric_authority_ref_invalid",
                )
                _merge_numeric_catalog_row(
                    numeric_rows,
                    ref=ref,
                    row=raw,
                )
                continue
            # Research estimates share the model-visible numeric catalog in the
            # current runtime, but they explicitly carry no NumericFact output
            # authority.  Preserve their ids for lineage below and never admit
            # them to the deterministic report renderer.
            estimate_ref = str(raw.get("estimate_id") or "")
            _require(
                estimate_ref.startswith("ESTIMATE::")
                and raw.get("numeric_fact_authority") is False,
                "multi_agent_report_numeric_authority_ref_invalid",
            )
            _merge_catalog_row(
                estimate_rows,
                ref=estimate_ref,
                row=raw,
                code="multi_agent_report_estimate_authority_conflict",
            )
        for raw in view.get("numeric_relation_catalog") or ():
            ref = str(raw.get("numeric_relation_ref") or "")
            _merge_catalog_row(
                relation_rows,
                ref=ref,
                row=raw,
                code="multi_agent_report_relation_authority_conflict",
            )
        cell = _mapping(view.get("cell"), "multi_agent_report_cell_missing")
        for raw in cell.get("residual_gap_cards") or ():
            ref = str(raw.get("gap_ref") or "")
            _require(ref.startswith("GAP::"), "multi_agent_report_gap_ref_invalid")
            _merge_catalog_row(
                gap_rows,
                ref=ref,
                row=raw,
                code="multi_agent_report_gap_authority_conflict",
            )
    _require(
        identities and all(row == identities[0] for row in identities[1:]),
        "multi_agent_report_case_identity_drift",
    )

    selected_evidence: set[str] = set()
    selected_numeric: set[str] = set()
    selected_relations: set[str] = set()
    selected_estimates: set[str] = set()
    selected_gaps: set[str] = set()
    claims: list[dict[str, Any]] = []
    claim_refs_by_agent: dict[str, list[str]] = {}
    for agent_id in sorted(by_agent):
        workpaper = by_agent[agent_id]
        selected_gaps.update(str(ref) for ref in workpaper.get("remaining_gap_refs") or ())
        for index, raw_claim in enumerate(workpaper.get("sourced_claims") or ()):
            claim = _mapping(raw_claim, "multi_agent_report_claim_invalid")
            evidence_refs = sorted(str(ref) for ref in claim.get("evidence_refs") or ())
            raw_numeric_refs = sorted(
                str(ref) for ref in claim.get("numeric_refs") or ()
            )
            numeric_refs = [
                ref for ref in raw_numeric_refs if ref.startswith("NUM::")
            ]
            estimate_refs = [
                ref for ref in raw_numeric_refs if ref.startswith("ESTIMATE::")
            ]
            _require(
                len(numeric_refs) + len(estimate_refs) == len(raw_numeric_refs),
                "multi_agent_report_claim_numeric_ref_kind_invalid",
            )
            relation_refs = sorted(
                str(ref) for ref in claim.get("numeric_relation_refs") or ()
            )
            seed = {
                "agent_id": agent_id,
                "claim_index": index,
                "claim": str(claim.get("claim") or ""),
                "authority": str(claim.get("authority") or ""),
                "evidence_refs": evidence_refs,
                # Keep the historical claim-ref seed stable: it has always been
                # based on the workpaper's raw numeric-ref list.  The emitted
                # catalog separates typed output authority from non-authoritative
                # research estimates below.
                "numeric_refs": raw_numeric_refs,
                "numeric_relation_refs": relation_refs,
            }
            claim_ref = "WPCLAIM::" + canonical_digest(seed)[:20].upper()
            compiled_claim = {
                "claim_ref": claim_ref,
                **seed,
                "numeric_refs": numeric_refs,
                "authority_refs": sorted({*numeric_refs, *relation_refs}),
            }
            if estimate_refs:
                compiled_claim["research_estimate_refs"] = estimate_refs
            claims.append(compiled_claim)
            claim_refs_by_agent.setdefault(agent_id, []).append(claim_ref)
            selected_evidence.update(evidence_refs)
            selected_numeric.update(numeric_refs)
            selected_relations.update(relation_refs)
            selected_estimates.update(estimate_refs)

    _require(
        selected_evidence.issubset(evidence_rows)
        and selected_numeric.issubset(numeric_rows)
        and selected_relations.issubset(relation_rows)
        and selected_estimates.issubset(estimate_rows)
        and selected_gaps.issubset(gap_rows),
        "multi_agent_report_selected_authority_unresolved",
    )
    relation_operand_numeric_refs = {
        str(relation_rows[ref].get(field) or "")
        for ref in selected_relations
        for field in ("current_numeric_ref", "comparison_numeric_ref")
    } - {""}
    _require(
        relation_operand_numeric_refs.issubset(numeric_rows),
        "multi_agent_report_relation_operand_unresolved",
    )
    hydrated_relation_rows = {
        ref: _hydrate_relation_presentation_row(
            relation_rows[ref],
            numeric_rows=numeric_rows,
        )
        for ref in selected_relations
    }
    presentations = [
        *(_numeric_presentation(numeric_rows[ref]) for ref in sorted(selected_numeric)),
        *(
            _relation_presentation(hydrated_relation_rows[ref])
            for ref in sorted(selected_relations)
        ),
    ]
    presentation_refs = {str(row["authority_ref"]) for row in presentations}
    _require(
        presentation_refs == selected_numeric | selected_relations,
        "multi_agent_report_presentation_coverage_invalid",
    )
    case_identity = identities[0]
    unsigned = {
        "schema_version": MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION,
        "case_identity": case_identity,
        "workpaper_digests": sorted(
            str(row.get("workpaper_digest") or "") for row in papers
        ),
        "claims": sorted(claims, key=lambda row: str(row["claim_ref"])),
        "claim_refs_by_agent": {
            agent_id: sorted(refs)
            for agent_id, refs in sorted(claim_refs_by_agent.items())
        },
        "workpaper_gap_bindings": [
            {
                "agent_id": agent_id,
                "gap_refs": sorted(
                    str(ref)
                    for ref in by_agent[agent_id].get("remaining_gap_refs") or ()
                ),
            }
            for agent_id in sorted(by_agent)
        ],
        "evidence_authority": [
            {
                key: deepcopy(evidence_rows[ref].get(key))
                for key in (
                    "evidence_ref",
                    "evidence_owner_ticker",
                    "source_type",
                    "source_tier",
                    "publication_date",
                    "source_reporting_period_end",
                    "relationship_directions",
                )
            }
            for ref in sorted(selected_evidence)
        ],
        "presentation_authority": sorted(
            presentations, key=lambda row: str(row["authority_ref"])
        ),
        "gap_authority": [
            {
                key: deepcopy(gap_rows[ref].get(key))
                for key in (
                    "gap_ref",
                    "gap_code",
                    "slot_id",
                    "facet_id",
                    "business_reason_zh",
                    "supplement_direction_zh",
                )
            }
            for ref in sorted(selected_gaps)
        ],
        "authority_boundary": {
            "raw_evidence_numeric_surface_is_output_authority": False,
            "only_typed_presentation_refs_may_render_material_numbers": True,
            "model_owned_prose_must_be_numeric_date_alias_and_citation_free": True,
            "citations_are_rendered_from_selected_evidence_refs": True,
            "case_identity_and_research_as_of_are_harness_rendered": True,
            "semantic_evaluator_may_override_local_surface_gate": False,
        },
        "coverage_receipt": {
            "workpaper_count": len(papers),
            "claim_count": len(claims),
            "evidence_ref_count": len(selected_evidence),
            "numeric_ref_count": len(selected_numeric),
            "relation_operand_numeric_ref_count": len(
                relation_operand_numeric_refs
            ),
            "numeric_relation_ref_count": len(selected_relations),
            "research_estimate_ref_count": len(selected_estimates),
            "research_estimates_granted_output_authority": False,
            "gap_ref_count": len(selected_gaps),
            "all_selected_refs_resolved": True,
        },
    }
    return {**unsigned, "authority_catalog_digest": canonical_digest(unsigned)}


def extend_multi_agent_report_authority_catalog(
    *,
    authority_catalog: Mapping[str, Any],
    source_bound_program: Mapping[str, Any],
) -> dict[str, Any]:
    """Add qualified S2 source-bound surfaces without reopening workpaper prose.

    The extension is intentionally separate from the base compiler.  Historical
    workpapers remain immutable; a reviewed S2 program may only add typed
    authority to an exact claim scope.  It cannot create a new research claim.
    """

    from .source_bound_numeric_authority import (  # local import avoids a cycle
        SOURCE_BOUND_NUMERIC_PROGRAM_SCHEMA_VERSION,
    )

    _require(
        authority_catalog.get("schema_version")
        == MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION,
        "multi_agent_report_extension_base_catalog_invalid",
    )
    _require(
        source_bound_program.get("schema_version")
        == SOURCE_BOUND_NUMERIC_PROGRAM_SCHEMA_VERSION,
        "multi_agent_report_extension_program_invalid",
    )
    unsigned_program = {
        key: deepcopy(value)
        for key, value in source_bound_program.items()
        if key != "program_digest"
    }
    _require(
        source_bound_program.get("program_digest")
        == canonical_digest(unsigned_program),
        "multi_agent_report_extension_program_digest_invalid",
    )
    _require(
        source_bound_program.get("base_authority_catalog_digest")
        == authority_catalog.get("authority_catalog_digest"),
        "multi_agent_report_extension_base_catalog_drift",
    )
    _require(
        source_bound_program.get("case_identity")
        == authority_catalog.get("case_identity"),
        "multi_agent_report_extension_case_identity_drift",
    )

    compiled = deepcopy(dict(authority_catalog))
    claim_by_ref = {
        str(row["claim_ref"]): row for row in compiled.get("claims") or ()
    }
    _require(bool(claim_by_ref), "multi_agent_report_extension_claims_missing")
    presentations = {
        str(row["authority_ref"]): deepcopy(dict(row))
        for row in compiled.get("presentation_authority") or ()
    }
    additions = [
        *(
            _numeric_presentation(row)
            for row in source_bound_program.get("numeric_fact_additions") or ()
        ),
        *(
            _bounded_presentation(row)
            for row in source_bound_program.get("bounded_presentation_additions")
            or ()
        ),
        *(
            _temporal_presentation(row)
            for row in source_bound_program.get("temporal_authority_additions")
            or ()
        ),
    ]
    for row in additions:
        ref = str(row["authority_ref"])
        if ref in presentations:
            _require(
                presentations[ref] == row,
                "multi_agent_report_extension_presentation_conflict",
            )
        else:
            presentations[ref] = row

    added_refs = {
        str(ref)
        for row in source_bound_program.get("claim_authority_additions") or ()
        for ref in row.get("authority_refs") or ()
    }
    _require(
        added_refs.issubset(presentations),
        "multi_agent_report_extension_authority_unresolved",
    )
    seen_claim_additions: set[str] = set()
    for raw in source_bound_program.get("claim_authority_additions") or ():
        row = _mapping(raw, "multi_agent_report_extension_claim_addition_invalid")
        _require(
            set(row) == {"claim_ref", "authority_refs"},
            "multi_agent_report_extension_claim_addition_shape_invalid",
        )
        claim_ref = str(row.get("claim_ref") or "")
        _require(
            claim_ref in claim_by_ref and claim_ref not in seen_claim_additions,
            "multi_agent_report_extension_claim_ref_invalid",
        )
        seen_claim_additions.add(claim_ref)
        refs = {str(ref) for ref in row.get("authority_refs") or ()}
        _require(
            refs and refs.issubset(presentations),
            "multi_agent_report_extension_claim_authority_invalid",
        )
        claim = claim_by_ref[claim_ref]
        claim["authority_refs"] = sorted(
            {*claim.get("authority_refs", ()), *refs}
        )
        claim["source_bound_authority_refs"] = sorted(refs)

    compiled.pop("authority_catalog_digest", None)
    compiled["schema_version"] = (
        MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION
    )
    compiled["presentation_authority"] = sorted(
        presentations.values(), key=lambda row: str(row["authority_ref"])
    )
    compiled["base_authority_catalog_digest"] = authority_catalog[
        "authority_catalog_digest"
    ]
    compiled["source_bound_program_digest"] = source_bound_program["program_digest"]
    compiled["authority_boundary"] = {
        **deepcopy(dict(compiled.get("authority_boundary") or {})),
        "source_presence_bypasses_typed_admission": False,
        "source_bound_exact_and_bounded_surfaces_are_distinct": True,
        "historical_workpaper_claim_text_mutated": False,
    }
    compiled["coverage_receipt"] = {
        **deepcopy(dict(compiled.get("coverage_receipt") or {})),
        "source_bound_numeric_fact_addition_count": len(
            source_bound_program.get("numeric_fact_additions") or ()
        ),
        "source_bound_bounded_presentation_addition_count": len(
            source_bound_program.get("bounded_presentation_additions") or ()
        ),
        "source_temporal_authority_addition_count": len(
            source_bound_program.get("temporal_authority_additions") or ()
        ),
        "claim_with_source_bound_authority_count": len(seen_claim_additions),
        "all_source_bound_authority_refs_resolved": True,
    }
    return {**compiled, "authority_catalog_digest": canonical_digest(compiled)}


def _ref_array(values: Sequence[str]) -> dict[str, Any]:
    refs = sorted(set(str(value) for value in values))
    if refs:
        return {
            "type": "array",
            "maxItems": len(refs),
            "uniqueItems": True,
            "items": {"type": "string", "enum": refs},
        }
    return {
        "type": "array",
        "maxItems": 1,
        "uniqueItems": True,
        "items": {"type": "string", "enum": [_EMPTY_REF_PLACEHOLDER]},
        "description": "Submit [] or the transport placeholder; it normalizes to [].",
    }


def protected_report_draft_tool(
    *, authority_catalog: Mapping[str, Any]
) -> dict[str, Any]:
    claims = authority_catalog.get("claims") or []
    agents = sorted((authority_catalog.get("claim_refs_by_agent") or {}).keys())
    claim_refs = sorted(str(row["claim_ref"]) for row in claims)
    evidence_refs = sorted(
        str(row["evidence_ref"])
        for row in authority_catalog.get("evidence_authority") or ()
    )
    authority_refs = sorted(
        str(row["authority_ref"])
        for row in authority_catalog.get("presentation_authority") or ()
    )
    gap_refs = sorted(
        str(row["gap_ref"])
        for row in authority_catalog.get("gap_authority") or ()
    )
    clause = {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_CLAUSE_FIELDS),
        "properties": {
            "model_text": compile_current_research_model_text_schema(
                description=(
                    "Research prose only: no digits, dates, units, URLs, aliases, "
                    "citations or exact financial surfaces. Keep a normal clause "
                    "within the recommended narrative density; a longer supported "
                    "clause is assessed as a quality finding rather than silently "
                    "discarded, up to the documented safety capacity."
                )
            ),
            "source_workpaper_agent_ids": {
                "type": "array",
                "minItems": 1,
                "maxItems": len(agents),
                "uniqueItems": True,
                "items": {"type": "string", "enum": agents},
            },
            "source_claim_refs": _ref_array(claim_refs),
            "evidence_refs": _ref_array(evidence_refs),
            "authority_refs": _ref_array(authority_refs),
            "gap_refs": _ref_array(gap_refs),
        },
    }
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "report_topic",
            "executive_thesis",
            "sections",
            "remaining_gaps",
            "what_would_change",
            "confidence",
        ],
        "properties": {
            "schema_version": {
                "type": "string",
                "enum": [MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION],
            },
            "report_topic": compile_current_research_model_text_schema(
                description=(
                    "Flexible concise report topic without company identity, dates "
                    "or numbers."
                )
            ),
            "executive_thesis": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": clause,
            },
            "sections": {
                "type": "array",
                "minItems": 4,
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["heading", "clauses"],
                    "properties": {
                        "heading": compile_current_research_model_text_schema(
                            description="Section heading without numbers, dates or aliases."
                        ),
                        "clauses": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 10,
                            "items": clause,
                        },
                    },
                },
            },
            "remaining_gaps": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": clause,
            },
            "what_would_change": {
                "type": "array",
                "minItems": 2,
                "maxItems": 12,
                "items": clause,
            },
            "confidence": clause,
        },
    }
    return {
        "type": "function",
        "function": {
            "name": "submit_protected_report_draft",
            "description": (
                "Submit research prose separately from typed facts, dates, identity "
                "and citations; the Harness renders every protected surface."
            ),
            "parameters": bind_current_research_model_text_schema_definition(parameters),
        },
    }


def compile_protected_report_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    evaluation: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    _require(
        evaluation.get("report_may_proceed") is True,
        "multi_agent_protected_report_blocked_by_evaluation",
    )
    _require(
        _valid_authority_catalog_schema(authority_catalog.get("schema_version")),
        "multi_agent_report_authority_catalog_invalid",
    )
    visible = {
        "validated_workpapers": [deepcopy(dict(row)) for row in workpapers],
        "independent_evaluation": deepcopy(dict(evaluation)),
        "report_authority": {
            "case_identity": deepcopy(authority_catalog["case_identity"]),
            "claims": deepcopy(authority_catalog["claims"]),
            "presentation_authority": deepcopy(
                authority_catalog["presentation_authority"]
            ),
            "gap_authority": deepcopy(authority_catalog["gap_authority"]),
            "authority_boundary": deepcopy(
                authority_catalog["authority_boundary"]
            ),
            "authority_catalog_digest": authority_catalog[
                "authority_catalog_digest"
            ],
        },
        "writer_rules": [
            "Write the research judgment in model_text without any digit, date, unit, URL, alias, citation or exact financial surface.",
            "Select source_claim_refs to bind each clause to validated workpaper claims.",
            "Select evidence_refs only from those claims; the Harness renders citations.",
            "Select NUM or REL authority_refs for every material exact number or comparison; the Harness renders the exact surface.",
            "Raw Evidence text being visible does not authorize copying its numbers into the report.",
            "If a material numeric claim has no presentation authority, omit the number and preserve the limitation or typed gap.",
            "Preserve material counterarguments and what-would-change conditions.",
            "Do not turn the executive thesis into a gap inventory: state the judgment, the main driver, and at most one synthesized material uncertainty.",
            "Describe each material boundary once in remaining_gaps; sections may analyze its consequence but must not repeat the same boundary wording.",
            "Confidence must explain the confidence level and evidence mix, not repeat the remaining-gap register.",
            "Operational failures, pending Evidence admission, unexecuted source routes, stale NumericFact projection, and researcher-defined thresholds are not customer-facing information gaps.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the Writer in a financial multi-agent system. Synthesize "
                "validated specialist judgments, but keep research prose separate "
                "from protected facts. The Harness alone renders company identity, "
                "dates, exact numbers, comparisons and citations. Do not copy a "
                "number from raw Evidence. Submit one protected report tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def compile_protected_report_remap_messages(
    *,
    source_report: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    """Compile a terminal-only remap view from one immutable source report.

    Unlike ``compile_protected_report_messages``, this view does not expose the
    workpapers for fresh synthesis.  It asks the Writer to preserve the already
    completed report while replacing protected prose surfaces with typed refs.
    """

    _require(
        evaluation.get("report_may_proceed") is True,
        "multi_agent_protected_report_blocked_by_evaluation",
    )
    _require(
        _valid_authority_catalog_schema(authority_catalog.get("schema_version")),
        "multi_agent_report_authority_catalog_invalid",
    )
    source = deepcopy(
        dict(_mapping(source_report, "multi_agent_report_remap_source_invalid"))
    )
    audit = audit_legacy_report_protected_surfaces(source)
    _require(
        audit.get("status") == "hard_fail"
        and audit.get("local_surface_gate_pass") is False,
        "multi_agent_report_remap_source_not_legacy_negative",
    )
    source_sections = source.get("sections")
    source_gaps = source.get("remaining_gaps")
    source_wwc = source.get("what_would_change")
    _require(
        isinstance(source_sections, list)
        and 4 <= len(source_sections) <= 10
        and isinstance(source_gaps, list)
        and 1 <= len(source_gaps) <= 12
        and isinstance(source_wwc, list)
        and 2 <= len(source_wwc) <= 12,
        "multi_agent_report_remap_source_shape_invalid",
    )
    source_workpaper_digests = sorted(
        str(value) for value in source.get("workpaper_digests") or ()
    )
    _require(
        source_workpaper_digests
        == sorted(str(value) for value in authority_catalog["workpaper_digests"]),
        "multi_agent_report_remap_workpaper_lineage_drift",
    )
    visible = {
        "immutable_source_report": source,
        "independent_evaluation": deepcopy(dict(evaluation)),
        "report_authority": {
            "case_identity": deepcopy(authority_catalog["case_identity"]),
            "claims": deepcopy(authority_catalog["claims"]),
            "presentation_authority": deepcopy(
                authority_catalog["presentation_authority"]
            ),
            "gap_authority": deepcopy(authority_catalog["gap_authority"]),
            "authority_boundary": deepcopy(
                authority_catalog["authority_boundary"]
            ),
            "authority_catalog_digest": authority_catalog[
                "authority_catalog_digest"
            ],
        },
        "remap_contract": {
            "source_report_digest": str(source.get("report_digest") or ""),
            "required_section_count": len(source_sections),
            "required_section_agent_order": [
                [str(value) for value in row.get("source_workpaper_agent_ids") or ()]
                for row in source_sections
            ],
            "required_remaining_gap_count": len(source_gaps),
            "required_what_would_change_count": len(source_wwc),
            "new_research_or_changed_judgment_forbidden": True,
            "model_owned_protected_surface_forbidden": True,
            "source_visible_number_is_not_output_authority": True,
        },
        "writer_rules": [
            "Preserve the source report's substantive thesis, mechanisms, counterarguments, gaps, confidence and ordering.",
            "Do not add a new fact, causal claim, source, research conclusion or research section.",
            "Rewrite model_text without any digit, date, unit, URL, alias, citation or exact financial surface.",
            "Replace every retained amount, date or comparison with the matching typed authority_ref; omit it if no authority exists.",
            "Keep the source section count, source-agent order, gap count and what-would-change count exactly unchanged.",
            "Map each source section to one concise clause and keep the executive thesis to one concise clause.",
            "Select only the minimum claim, Evidence, authority and gap refs needed for each clause; never copy the full catalog into a clause.",
            "The Harness alone renders company identity, dates, numbers, comparisons and citations.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are performing a terminal contract remap, not new research. "
                "Preserve the immutable report's meaning and boundaries. Remove "
                "every protected surface from model-owned prose and select only "
                "typed refs that are authorized for the relevant claim. The "
                "Harness renders protected facts. Submit one protected report "
                "tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def _normalize_refs(
    value: object,
    *,
    allowed: set[str],
    code: str,
) -> list[str]:
    _require(isinstance(value, list), code)
    refs = [str(item or "") for item in value]
    if refs == [_EMPTY_REF_PLACEHOLDER]:
        refs = []
    _require(
        len(refs) == len(set(refs)) and set(refs).issubset(allowed),
        code,
    )
    return refs


def _contract_finding(
    *,
    field_path: str,
    finding_code: str,
    blocking: bool,
    repair_fields: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body = {
        "field_path": field_path,
        "finding_code": finding_code,
        "severity": "hard_contract" if blocking else "quality",
        "blocking": blocking,
        "repair_fields": sorted({str(value) for value in repair_fields}),
        "details": deepcopy(dict(details or {})),
    }
    return {**body, "finding_digest": canonical_digest(body)}


def _audit_model_text(
    *, field_path: str, value: object, limit_kind: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    limits = _REPORT_TEXT_LIMITS[limit_kind]
    text = str(value or "").strip()
    length = len(text)
    hard: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    if length < limits["minimum"]:
        hard.append(
            _contract_finding(
                field_path=field_path,
                finding_code="multi_agent_report_model_text_minimum_not_met",
                blocking=True,
                repair_fields=("model_text",),
                details={
                    "actual_characters": length,
                    "minimum_characters": limits["minimum"],
                },
            )
        )
    elif length > limits["safety_maximum"]:
        hard.append(
            _contract_finding(
                field_path=field_path,
                finding_code="multi_agent_report_model_text_safety_capacity_exceeded",
                blocking=True,
                repair_fields=("model_text",),
                details={
                    "actual_characters": length,
                    "safety_maximum_characters": limits["safety_maximum"],
                },
            )
        )
    elif (
        re.fullmatch(CURRENT_RESEARCH_MODEL_TEXT_SERVER_PATTERN, text) is None
    ):
        hard.append(
            _contract_finding(
                field_path=field_path,
                finding_code="multi_agent_report_model_text_unprotected_surface",
                blocking=True,
                repair_fields=("model_text",),
                details={
                    "protected_surface_present": True,
                    "surface_value_returned_to_model": False,
                },
            )
        )
    if (
        not hard
        and length > limits["recommended_maximum"]
        and length <= limits["safety_maximum"]
    ):
        quality.append(
            _contract_finding(
                field_path=field_path,
                finding_code="multi_agent_report_narrative_density_above_recommended",
                blocking=False,
                details={
                    "actual_characters": length,
                    "recommended_maximum_characters": limits[
                        "recommended_maximum"
                    ],
                    "safety_maximum_characters": limits["safety_maximum"],
                },
            )
        )
    return hard, quality


def _audit_clause_contract(
    raw: object,
    *,
    catalog: Mapping[str, Any],
    kind: str,
    field_path: str,
    limit_kind: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hard: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    if not isinstance(raw, Mapping) or set(raw) != _CLAUSE_FIELDS:
        hard.append(
            _contract_finding(
                field_path=field_path,
                finding_code="multi_agent_report_clause_fields_invalid",
                blocking=True,
                repair_fields=tuple(sorted(_CLAUSE_FIELDS)),
            )
        )
        return hard, quality
    clause = dict(raw)
    text_hard, text_quality = _audit_model_text(
        field_path=f"{field_path}.model_text",
        value=clause.get("model_text"),
        limit_kind=limit_kind,
    )
    hard.extend(text_hard)
    quality.extend(text_quality)

    claims = {str(row["claim_ref"]): row for row in catalog["claims"]}
    all_agents = set(catalog["claim_refs_by_agent"])
    all_evidence = {
        str(row["evidence_ref"]) for row in catalog["evidence_authority"]
    }
    all_authority = {
        str(row["authority_ref"])
        for row in catalog["presentation_authority"]
    }
    all_gaps = {str(row["gap_ref"]) for row in catalog["gap_authority"]}
    issues: list[str] = []
    offending: dict[str, list[str]] = {}

    normalized: dict[str, list[str]] = {}
    global_allowed = {
        "source_workpaper_agent_ids": all_agents,
        "source_claim_refs": set(claims),
        "evidence_refs": all_evidence,
        "authority_refs": all_authority,
        "gap_refs": all_gaps,
    }
    for name, allowed in global_allowed.items():
        raw_refs = clause.get(name)
        if not isinstance(raw_refs, list) or any(
            not isinstance(item, str) for item in raw_refs
        ):
            issues.append(f"{name}_shape_invalid")
            normalized[name] = []
            continue
        refs = [str(item) for item in raw_refs]
        normalized[name] = refs
        invalid = sorted(set(refs) - allowed)
        if len(refs) != len(set(refs)):
            issues.append(f"{name}_duplicate")
        if invalid:
            issues.append(f"{name}_unknown")
            offending[name] = invalid

    source_agents = [
        value
        for value in normalized.get("source_workpaper_agent_ids", [])
        if value in all_agents
    ]
    if not source_agents:
        issues.append("source_workpaper_agent_ids_empty")
    claim_refs = [
        value
        for value in normalized.get("source_claim_refs", [])
        if value in claims
    ]
    allowed_claim_refs = sorted(
        ref
        for ref, row in claims.items()
        if str(row["agent_id"]) in source_agents
    )
    cross_agent_claims = sorted(
        ref
        for ref in claim_refs
        if str(claims[ref]["agent_id"]) not in source_agents
    )
    if cross_agent_claims:
        issues.append("source_claim_refs_cross_agent")
        offending["source_claim_refs"] = sorted(
            set(offending.get("source_claim_refs", []))
            | set(cross_agent_claims)
        )

    selected_scoped_claims = [
        claims[ref] for ref in claim_refs if ref not in cross_agent_claims
    ]
    selected_evidence = {
        str(ref)
        for row in selected_scoped_claims
        for ref in row["evidence_refs"]
    }
    selected_authority = {
        str(ref)
        for row in selected_scoped_claims
        for ref in row["authority_refs"]
    }
    allowed_claim_rows = [claims[ref] for ref in allowed_claim_refs]
    allowed_evidence = sorted(
        {
            str(ref)
            for row in allowed_claim_rows
            for ref in row["evidence_refs"]
        }
    )
    allowed_authority = sorted(
        {
            str(ref)
            for row in allowed_claim_rows
            for ref in row["authority_refs"]
        }
    )
    for name, selected, scoped in (
        ("evidence_refs", normalized.get("evidence_refs", []), selected_evidence),
        (
            "authority_refs",
            normalized.get("authority_refs", []),
            selected_authority,
        ),
    ):
        out_of_scope = sorted(
            value for value in selected if value in global_allowed[name] and value not in scoped
        )
        if out_of_scope:
            issues.append(f"{name}_outside_selected_claims")
            offending[name] = sorted(
                set(offending.get(name, [])) | set(out_of_scope)
            )

    allowed_gaps = sorted(
        {
            str(ref)
            for binding in catalog.get("workpaper_gap_bindings", [])
            if binding.get("agent_id") in source_agents
            for ref in binding.get("gap_refs") or ()
        }
    )
    if not catalog.get("workpaper_gap_bindings"):
        allowed_gaps = sorted(all_gaps)
    out_of_scope_gaps = sorted(
        value
        for value in normalized.get("gap_refs", [])
        if value in all_gaps and value not in set(allowed_gaps)
    )
    if out_of_scope_gaps:
        issues.append("gap_refs_outside_source_agents")
        offending["gap_refs"] = sorted(
            set(offending.get("gap_refs", [])) | set(out_of_scope_gaps)
        )
    if kind == "content" and not claim_refs:
        issues.append("source_claim_refs_required")
    if kind == "gap" and not normalized.get("gap_refs"):
        issues.append("gap_refs_required")
    if kind == "wwc" and not any(
        normalized.get(name)
        for name in (
            "source_claim_refs",
            "evidence_refs",
            "authority_refs",
            "gap_refs",
        )
    ):
        issues.append("what_would_change_reference_required")

    if issues:
        issue_set = set(issues)
        primary_code = "multi_agent_report_clause_reference_scope_invalid"
        for field_name, field_code in (
            (
                "source_workpaper_agent_ids",
                "multi_agent_report_clause_agent_refs_invalid",
            ),
            ("source_claim_refs", "multi_agent_report_clause_claim_refs_invalid"),
            ("evidence_refs", "multi_agent_report_clause_evidence_refs_invalid"),
            (
                "authority_refs",
                "multi_agent_report_clause_authority_refs_invalid",
            ),
            ("gap_refs", "multi_agent_report_clause_gap_refs_invalid"),
        ):
            if {
                f"{field_name}_shape_invalid",
                f"{field_name}_duplicate",
                f"{field_name}_unknown",
            } & issue_set:
                primary_code = field_code
                break
        else:
            if "source_workpaper_agent_ids_empty" in issue_set:
                primary_code = "multi_agent_report_clause_agent_refs_invalid"
            elif "source_claim_refs_cross_agent" in issue_set:
                primary_code = "multi_agent_report_clause_claim_agent_scope_invalid"
            elif "source_claim_refs_required" in issue_set:
                primary_code = "multi_agent_report_content_clause_claim_missing"
            elif "gap_refs_required" in issue_set:
                primary_code = "multi_agent_report_gap_clause_gap_missing"
            elif "what_would_change_reference_required" in issue_set:
                primary_code = "multi_agent_report_wwc_clause_unbound"
        hard.append(
            _contract_finding(
                field_path=field_path,
                finding_code=primary_code,
                blocking=True,
                repair_fields=(
                    "source_claim_refs",
                    "evidence_refs",
                    "authority_refs",
                    "gap_refs",
                ),
                details={
                    "issues": sorted(set(issues)),
                    "offending_refs": offending,
                    "allowed_refs": {
                        "source_claim_refs": allowed_claim_refs,
                        "evidence_refs": allowed_evidence,
                        "authority_refs": allowed_authority,
                        "gap_refs": allowed_gaps,
                    },
                    "source_workpaper_agent_ids_immutable": source_agents,
                },
            )
        )
    return hard, quality


def audit_protected_report_draft(
    payload: Mapping[str, Any],
    *,
    authority_catalog: Mapping[str, Any],
    boundary_disposition_register: Mapping[str, Any] | None = None,
    quality_policy_version: str = MULTI_AGENT_REPORT_QUALITY_POLICY_VERSION,
) -> dict[str, Any]:
    """Collect every actionable contract failure before a correction attempt."""

    _require(
        quality_policy_version
        in {
            MULTI_AGENT_REPORT_QUALITY_POLICY_LEGACY_VERSION,
            MULTI_AGENT_REPORT_QUALITY_POLICY_VERSION,
        },
        "multi_agent_report_quality_policy_version_invalid",
    )

    value = deepcopy(dict(payload))
    hard: list[dict[str, Any]] = []
    quality: list[dict[str, Any]] = []
    expected = {
        "schema_version",
        "report_topic",
        "executive_thesis",
        "sections",
        "remaining_gaps",
        "what_would_change",
        "confidence",
    }
    if set(value) != expected or value.get("schema_version") not in {
        MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION,
    }:
        hard.append(
            _contract_finding(
                field_path="$",
                finding_code="multi_agent_protected_report_identity_invalid",
                blocking=True,
            )
        )
    else:
        topic_hard, topic_quality = _audit_model_text(
            field_path="report_topic",
            value=value.get("report_topic"),
            limit_kind="topic",
        )
        hard.extend(topic_hard)
        quality.extend(topic_quality)
        rows: list[tuple[str, object, str, str]] = []
        executive = value.get("executive_thesis")
        sections = value.get("sections")
        gaps = value.get("remaining_gaps")
        wwc = value.get("what_would_change")
        if not isinstance(executive, list) or not 1 <= len(executive) <= 6:
            hard.append(
                _contract_finding(
                    field_path="executive_thesis",
                    finding_code="multi_agent_report_executive_thesis_invalid",
                    blocking=True,
                )
            )
        else:
            rows.extend(
                (f"executive_thesis[{index}]", row, "content", "executive")
                for index, row in enumerate(executive)
            )
        if not isinstance(sections, list) or not 4 <= len(sections) <= 10:
            hard.append(
                _contract_finding(
                    field_path="sections",
                    finding_code="multi_agent_report_sections_invalid",
                    blocking=True,
                )
            )
        else:
            for section_index, section in enumerate(sections):
                if not isinstance(section, Mapping) or set(section) != {
                    "heading",
                    "clauses",
                }:
                    hard.append(
                        _contract_finding(
                            field_path=f"sections[{section_index}]",
                            finding_code="multi_agent_report_section_fields_invalid",
                            blocking=True,
                        )
                    )
                    continue
                heading_hard, heading_quality = _audit_model_text(
                    field_path=f"sections[{section_index}].heading",
                    value=section.get("heading"),
                    limit_kind="heading",
                )
                hard.extend(heading_hard)
                quality.extend(heading_quality)
                clauses = section.get("clauses")
                if not isinstance(clauses, list) or not 1 <= len(clauses) <= 10:
                    hard.append(
                        _contract_finding(
                            field_path=f"sections[{section_index}].clauses",
                            finding_code="multi_agent_report_section_clauses_invalid",
                            blocking=True,
                        )
                    )
                    continue
                rows.extend(
                    (
                        f"sections[{section_index}].clauses[{clause_index}]",
                        row,
                        "content",
                        "section",
                    )
                    for clause_index, row in enumerate(clauses)
                )
        for name, values, kind in (
            ("remaining_gaps", gaps, "gap"),
            ("what_would_change", wwc, "wwc"),
        ):
            minimum = 1 if kind == "gap" else 2
            if not isinstance(values, list) or not minimum <= len(values) <= 12:
                hard.append(
                    _contract_finding(
                        field_path=name,
                        finding_code=(
                            "multi_agent_report_remaining_gaps_invalid"
                            if kind == "gap"
                            else "multi_agent_report_what_would_change_invalid"
                        ),
                        blocking=True,
                    )
                )
            else:
                rows.extend(
                    (f"{name}[{index}]", row, kind, kind)
                    for index, row in enumerate(values)
                )
        rows.append(("confidence", value.get("confidence"), "content", "confidence"))
        for field_path, row, kind, limit_kind in rows:
            row_hard, row_quality = _audit_clause_contract(
                row,
                catalog=authority_catalog,
                kind=kind,
                field_path=field_path,
                limit_kind=limit_kind,
            )
            hard.extend(row_hard)
            quality.extend(row_quality)
        if quality_policy_version == MULTI_AGENT_REPORT_QUALITY_POLICY_VERSION:
            quality.extend(_audit_boundary_surface_density(value))
        if boundary_disposition_register is not None:
            boundary_register = validate_report_boundary_disposition_register(
                boundary_disposition_register
            )
            for blocker in boundary_register["pre_report_blockers"]:
                hard.append(
                    _contract_finding(
                        field_path="$",
                        finding_code=(
                            "multi_agent_report_pre_report_boundary_unresolved"
                        ),
                        blocking=True,
                        details={
                            "boundary_id": blocker["boundary_id"],
                            "owner_stage": blocker["owner_stage"],
                            "information_state": blocker["information_state"],
                        },
                    )
                )
    body = {
        "schema_version": "fin_ia_multi_agent_report_contract_finding_receipt_v1_0",
        "payload_digest": canonical_digest(value),
        "hard_finding_count": len(hard),
        "quality_finding_count": len(quality),
        "hard_findings": hard,
        "quality_findings": quality,
        "contract_valid": not hard,
    }
    return {**body, "receipt_digest": canonical_digest(body)}


def _clause_gap_refs(value: object) -> set[str]:
    if not isinstance(value, Mapping):
        return set()
    refs = value.get("gap_refs")
    if not isinstance(refs, list):
        return set()
    return {str(ref) for ref in refs if str(ref).startswith("GAP::")}


def _audit_boundary_surface_density(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Flag repeated boundary inventory without turning prose style into L1.

    A truthful material uncertainty may constrain a section and also appear in
    the boundary register.  Repeating the same gap through the executive,
    sections, gap register, what-would-change list and confidence statement is
    different: it makes an operationally safe report read like a refusal.  The
    finding remains non-blocking so the Harness never deletes or rewrites the
    model's research judgment.
    """

    grouped: dict[str, set[str]] = {
        "executive_thesis": set(),
        "sections": set(),
        "remaining_gaps": set(),
        "what_would_change": set(),
        "confidence": set(),
    }
    for row in payload.get("executive_thesis") or ():
        grouped["executive_thesis"].update(_clause_gap_refs(row))
    for section in payload.get("sections") or ():
        if not isinstance(section, Mapping):
            continue
        for row in section.get("clauses") or ():
            grouped["sections"].update(_clause_gap_refs(row))
    for row in payload.get("remaining_gaps") or ():
        grouped["remaining_gaps"].update(_clause_gap_refs(row))
    for row in payload.get("what_would_change") or ():
        grouped["what_would_change"].update(_clause_gap_refs(row))
    grouped["confidence"].update(_clause_gap_refs(payload.get("confidence")))

    findings: list[dict[str, Any]] = []
    if len(grouped["executive_thesis"]) > 1:
        findings.append(
            _contract_finding(
                field_path="executive_thesis",
                finding_code="multi_agent_report_executive_boundary_inventory_dense",
                blocking=False,
                details={
                    "unique_gap_ref_count": len(grouped["executive_thesis"]),
                    "recommended_maximum": 1,
                    "gap_refs": sorted(grouped["executive_thesis"]),
                },
            )
        )
    if grouped["confidence"]:
        findings.append(
            _contract_finding(
                field_path="confidence",
                finding_code="multi_agent_report_confidence_repeats_gap_inventory",
                blocking=False,
                details={"gap_refs": sorted(grouped["confidence"])},
            )
        )
    gap_rows = payload.get("remaining_gaps")
    if isinstance(gap_rows, list) and len(gap_rows) > 4:
        findings.append(
            _contract_finding(
                field_path="remaining_gaps",
                finding_code="multi_agent_report_customer_gap_register_too_dense",
                blocking=False,
                details={
                    "gap_clause_count": len(gap_rows),
                    "recommended_maximum": 4,
                },
            )
        )
    all_refs = sorted(set().union(*grouped.values()))
    for ref in all_refs:
        groups = sorted(name for name, refs in grouped.items() if ref in refs)
        if len(groups) <= 2:
            continue
        findings.append(
            _contract_finding(
                field_path="$",
                finding_code="multi_agent_report_gap_repeated_across_surface_groups",
                blocking=False,
                details={"gap_ref": ref, "surface_groups": groups},
            )
        )
    return findings


_EXECUTIVE_PATH = re.compile(r"^executive_thesis\[(\d+)\]$")
_SECTION_CLAUSE_PATH = re.compile(
    r"^sections\[(\d+)\]\.clauses\[(\d+)\]$"
)
_LIST_CLAUSE_PATH = re.compile(
    r"^(remaining_gaps|what_would_change)\[(\d+)\]$"
)


def _clause_at_path(payload: Mapping[str, Any], field_path: str) -> dict[str, Any]:
    if field_path == "confidence":
        clause = payload.get("confidence")
    elif match := _EXECUTIVE_PATH.fullmatch(field_path):
        rows = payload.get("executive_thesis")
        index = int(match.group(1))
        _require(
            isinstance(rows, list) and 0 <= index < len(rows),
            "multi_agent_report_patch_field_path_invalid",
        )
        clause = rows[index]
    elif match := _SECTION_CLAUSE_PATH.fullmatch(field_path):
        sections = payload.get("sections")
        section_index = int(match.group(1))
        clause_index = int(match.group(2))
        _require(
            isinstance(sections, list)
            and 0 <= section_index < len(sections)
            and isinstance(sections[section_index], Mapping)
            and isinstance(sections[section_index].get("clauses"), list)
            and 0
            <= clause_index
            < len(sections[section_index]["clauses"]),
            "multi_agent_report_patch_field_path_invalid",
        )
        clause = sections[section_index]["clauses"][clause_index]
    elif match := _LIST_CLAUSE_PATH.fullmatch(field_path):
        rows = payload.get(match.group(1))
        index = int(match.group(2))
        _require(
            isinstance(rows, list) and 0 <= index < len(rows),
            "multi_agent_report_patch_field_path_invalid",
        )
        clause = rows[index]
    else:
        raise MultiAgentReportAuthorityError(
            "multi_agent_report_patch_field_path_invalid"
        )
    _require(
        isinstance(clause, dict) and set(clause) == _CLAUSE_FIELDS,
        "multi_agent_report_patch_clause_invalid",
    )
    return clause


def compile_protected_report_reference_patch_receipt(
    base_payload: Mapping[str, Any],
    *,
    authority_catalog: Mapping[str, Any],
    quality_policy_version: str = MULTI_AGENT_REPORT_QUALITY_POLICY_VERSION,
) -> dict[str, Any]:
    """Freeze a complete failed draft into reference-only correction targets."""

    audit = audit_protected_report_draft(
        base_payload,
        authority_catalog=authority_catalog,
        quality_policy_version=quality_policy_version,
    )
    _require(
        audit["hard_finding_count"] > 0,
        "multi_agent_report_patch_base_already_valid",
    )
    allowed_patch_fields = {
        "source_claim_refs",
        "evidence_refs",
        "authority_refs",
        "gap_refs",
    }
    _require(
        all(
            set(finding["repair_fields"]).issubset(allowed_patch_fields)
            and finding["field_path"] != "$"
            for finding in audit["hard_findings"]
        ),
        "multi_agent_report_patch_non_reference_failure_present",
        details={"contract_finding_receipt": audit},
    )
    target_paths: list[str] = []
    for finding in audit["hard_findings"]:
        path = str(finding["field_path"])
        if path not in target_paths:
            target_paths.append(path)
    body = {
        "schema_version": "fin_ia_multi_agent_report_reference_patch_receipt_v1_0",
        "base_payload_schema_version": str(base_payload.get("schema_version") or ""),
        "base_payload_digest": canonical_digest(dict(base_payload)),
        "contract_finding_receipt_digest": audit["receipt_digest"],
        "target_paths": target_paths,
        "hard_findings": deepcopy(audit["hard_findings"]),
        "quality_findings_preserved_for_later_assessment": deepcopy(
            audit["quality_findings"]
        ),
        "model_text_patch_authorized": False,
        "source_agent_patch_authorized": False,
        "reference_patch_authorized": True,
    }
    return {**body, "patch_receipt_digest": canonical_digest(body)}


def protected_report_reference_patch_tool(
    *,
    patch_receipt: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    paths = [str(value) for value in patch_receipt.get("target_paths") or ()]
    _require(paths, "multi_agent_report_patch_target_paths_invalid")
    claims = sorted(
        str(row["claim_ref"]) for row in authority_catalog.get("claims") or ()
    )
    evidence = sorted(
        str(row["evidence_ref"])
        for row in authority_catalog.get("evidence_authority") or ()
    )
    authority = sorted(
        str(row["authority_ref"])
        for row in authority_catalog.get("presentation_authority") or ()
    )
    gaps = sorted(
        str(row["gap_ref"])
        for row in authority_catalog.get("gap_authority") or ()
    )
    patch = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "field_path",
            "source_claim_refs",
            "evidence_refs",
            "authority_refs",
            "gap_refs",
        ],
        "properties": {
            "field_path": {"type": "string", "enum": paths},
            "source_claim_refs": _ref_array(claims),
            "evidence_refs": _ref_array(evidence),
            "authority_refs": _ref_array(authority),
            "gap_refs": _ref_array(gaps),
        },
    }
    return {
        "type": "function",
        "function": {
            "name": "submit_protected_report_reference_patch",
            "description": (
                "Correct only the reference arrays at every listed failed field. "
                "The Harness preserves all model prose and all passing fields."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "base_payload_digest",
                    "patches",
                ],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "enum": [
                            MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION
                        ],
                    },
                    "base_payload_digest": {
                        "type": "string",
                        "enum": [str(patch_receipt["base_payload_digest"])],
                    },
                    "patches": {
                        "type": "array",
                        "minItems": len(paths),
                        "maxItems": len(paths),
                        "items": patch,
                    },
                },
            },
        },
    }


def compile_protected_report_reference_patch_messages(
    *,
    base_payload: Mapping[str, Any],
    patch_receipt: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    claims = {
        str(row["claim_ref"]): row
        for row in authority_catalog.get("claims") or ()
    }
    gaps = {
        str(row["gap_ref"]): row
        for row in authority_catalog.get("gap_authority") or ()
    }
    presentations = {
        str(row["authority_ref"]): row
        for row in authority_catalog.get("presentation_authority") or ()
    }
    finding_by_path = {
        str(row["field_path"]): row
        for row in patch_receipt.get("hard_findings") or ()
    }
    targets: list[dict[str, Any]] = []
    for path in patch_receipt["target_paths"]:
        finding = finding_by_path[str(path)]
        allowed = finding["details"]["allowed_refs"]
        clause = _clause_at_path(base_payload, str(path))
        current_allowed_claims = [
            ref
            for ref in clause["source_claim_refs"]
            if ref in set(allowed["source_claim_refs"])
        ]
        content_path = str(path).startswith(("executive_thesis", "sections")) or str(
            path
        ) == "confidence"
        visible_claim_refs = (
            current_allowed_claims
            if current_allowed_claims or not content_path
            else list(allowed["source_claim_refs"])
        )
        visible_authority_refs = {
            str(ref)
            for claim_ref in visible_claim_refs
            for ref in claims[claim_ref]["authority_refs"]
        }
        targets.append(
            {
                "field_path": str(path),
                "immutable_model_text": str(clause["model_text"]),
                "immutable_source_workpaper_agent_ids": list(
                    clause["source_workpaper_agent_ids"]
                ),
                "current_refs": {
                    name: list(clause[name])
                    for name in (
                        "source_claim_refs",
                        "evidence_refs",
                        "authority_refs",
                        "gap_refs",
                    )
                },
                "issues": list(finding["details"].get("issues") or ()),
                "offending_refs": deepcopy(
                    finding["details"].get("offending_refs") or {}
                ),
                "allowed_claims": [
                    {
                        "claim_ref": ref,
                        "claim": str(claims[ref]["claim"]),
                        "evidence_refs": list(claims[ref]["evidence_refs"]),
                        "authority_refs": list(claims[ref]["authority_refs"]),
                    }
                    for ref in visible_claim_refs
                ],
                "allowed_presentations": [
                    {
                        "authority_ref": ref,
                        "display_surface": str(presentations[ref]["display_surface"]),
                    }
                    for ref in allowed["authority_refs"]
                    if ref in visible_authority_refs
                ],
                "allowed_gaps": [
                    {
                        "gap_ref": ref,
                        "business_reason_zh": str(gaps[ref]["business_reason_zh"]),
                        "supplement_direction_zh": str(
                            gaps[ref]["supplement_direction_zh"]
                        ),
                    }
                    for ref in allowed["gap_refs"]
                ],
            }
        )
    visible = {
        "base_payload_digest": patch_receipt["base_payload_digest"],
        "patch_receipt_digest": patch_receipt["patch_receipt_digest"],
        "targets": targets,
        "rules": [
            "Return one patch for every target path and no other path.",
            "Do not rewrite model text, headings, topology or source-agent identity.",
            "Choose only refs allowed for the target's immutable source agents.",
            "Every selected Evidence or authority ref must be exposed by a selected claim.",
            "A remaining-gap target must select the matching allowed typed gap.",
            "Do not add new research, facts, judgment or source material.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are correcting reference bindings in an already completed "
                "financial report contract. Preserve every word of model prose. "
                "Select only claim-scoped and role-scoped refs, then submit the "
                "reference patch tool once."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def apply_protected_report_reference_patch(
    patch_payload: Mapping[str, Any],
    *,
    base_payload: Mapping[str, Any],
    patch_receipt: Mapping[str, Any],
    authority_catalog: Mapping[str, Any],
    source_report: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(patch_payload))
    _require(
        set(value) == {"schema_version", "base_payload_digest", "patches"}
        and value.get("schema_version")
        == MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION
        and value.get("base_payload_digest")
        == patch_receipt.get("base_payload_digest")
        == canonical_digest(dict(base_payload)),
        "multi_agent_report_reference_patch_identity_invalid",
    )
    patches = value.get("patches")
    target_paths = [str(path) for path in patch_receipt["target_paths"]]
    _require(
        isinstance(patches, list)
        and len(patches) == len(target_paths)
        and {
            str(row.get("field_path") or "")
            for row in patches
            if isinstance(row, Mapping)
        }
        == set(target_paths),
        "multi_agent_report_reference_patch_paths_invalid",
    )
    finding_by_path = {
        str(row["field_path"]): row
        for row in patch_receipt.get("hard_findings") or ()
    }
    corrected = deepcopy(dict(base_payload))
    corrected["schema_version"] = MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION
    for raw_patch in patches:
        patch = dict(_mapping(raw_patch, "multi_agent_report_reference_patch_invalid"))
        _require(
            set(patch)
            == {
                "field_path",
                "source_claim_refs",
                "evidence_refs",
                "authority_refs",
                "gap_refs",
            },
            "multi_agent_report_reference_patch_fields_invalid",
        )
        path = str(patch["field_path"])
        finding = finding_by_path[path]
        allowed = finding["details"]["allowed_refs"]
        clause = deepcopy(_clause_at_path(corrected, path))
        for name in (
            "source_claim_refs",
            "evidence_refs",
            "authority_refs",
            "gap_refs",
        ):
            clause[name] = _normalize_refs(
                patch.get(name),
                allowed=set(str(ref) for ref in allowed[name]),
                code="multi_agent_report_reference_patch_ref_invalid",
            )
        target = _clause_at_path(corrected, path)
        target.clear()
        target.update(clause)
    final_audit = audit_protected_report_draft(
        corrected, authority_catalog=authority_catalog
    )
    _require(
        final_audit["contract_valid"] is True,
        "multi_agent_report_reference_patch_still_invalid",
        details={"contract_finding_receipt": final_audit},
    )
    trusted = validate_protected_report_remap_draft(
        corrected,
        authority_catalog=authority_catalog,
        source_report=source_report,
    )
    receipt = {
        "base_payload_digest": patch_receipt["base_payload_digest"],
        "patch_receipt_digest": patch_receipt["patch_receipt_digest"],
        "patched_paths": target_paths,
        "model_text_unchanged": all(
            _clause_at_path(corrected, path)["model_text"]
            == _clause_at_path(base_payload, path)["model_text"]
            for path in target_paths
        ),
        "source_workpaper_agent_ids_unchanged": all(
            _clause_at_path(corrected, path)["source_workpaper_agent_ids"]
            == _clause_at_path(base_payload, path)["source_workpaper_agent_ids"]
            for path in target_paths
        ),
        "unlisted_paths_modified": False,
        "final_contract_finding_receipt_digest": final_audit["receipt_digest"],
    }
    trusted_body = {
        key: deepcopy(item)
        for key, item in trusted.items()
        if key != "draft_digest"
    }
    trusted_body["reference_patch_receipt"] = receipt
    return {**trusted_body, "draft_digest": canonical_digest(trusted_body)}


def _validate_clause(
    raw: object,
    *,
    catalog: Mapping[str, Any],
    kind: str,
    minimum_chars: int,
    maximum_chars: int,
) -> dict[str, Any]:
    clause = deepcopy(dict(_mapping(raw, "multi_agent_report_clause_invalid")))
    _require(set(clause) == _CLAUSE_FIELDS, "multi_agent_report_clause_fields_invalid")
    try:
        model_text = validate_current_research_model_text(
            clause.get("model_text"),
            minimum=minimum_chars,
            maximum=maximum_chars,
            code="multi_agent_report_model_text_unprotected_surface",
        )
    except CurrentResearchConsumerError as exc:
        raise MultiAgentReportAuthorityError(exc.code) from exc
    claims = {str(row["claim_ref"]): row for row in catalog["claims"]}
    agents = set(catalog["claim_refs_by_agent"])
    evidence = {str(row["evidence_ref"]) for row in catalog["evidence_authority"]}
    authority = {
        str(row["authority_ref"]) for row in catalog["presentation_authority"]
    }
    gaps = {str(row["gap_ref"]) for row in catalog["gap_authority"]}
    source_agents = _normalize_refs(
        clause.get("source_workpaper_agent_ids"),
        allowed=agents,
        code="multi_agent_report_clause_agent_refs_invalid",
    )
    _require(source_agents, "multi_agent_report_clause_agent_refs_invalid")
    claim_refs = _normalize_refs(
        clause.get("source_claim_refs"),
        allowed=set(claims),
        code="multi_agent_report_clause_claim_refs_invalid",
    )
    evidence_refs = _normalize_refs(
        clause.get("evidence_refs"),
        allowed=evidence,
        code="multi_agent_report_clause_evidence_refs_invalid",
    )
    authority_refs = _normalize_refs(
        clause.get("authority_refs"),
        allowed=authority,
        code="multi_agent_report_clause_authority_refs_invalid",
    )
    gap_refs = _normalize_refs(
        clause.get("gap_refs"),
        allowed=gaps,
        code="multi_agent_report_clause_gap_refs_invalid",
    )
    _require(
        all(str(claims[ref]["agent_id"]) in source_agents for ref in claim_refs),
        "multi_agent_report_clause_claim_agent_scope_invalid",
    )
    scoped_claims = [claims[ref] for ref in claim_refs]
    scoped_evidence = {
        str(ref) for row in scoped_claims for ref in row["evidence_refs"]
    }
    scoped_authority = {
        str(ref) for row in scoped_claims for ref in row["authority_refs"]
    }
    allowed_gaps_by_agent = {
        agent_id: {
            str(ref)
            for workpaper in catalog.get("workpaper_gap_bindings", [])
            if workpaper.get("agent_id") == agent_id
            for ref in workpaper.get("gap_refs") or ()
        }
        for agent_id in source_agents
    }
    if not catalog.get("workpaper_gap_bindings"):
        allowed_gaps = gaps
    else:
        allowed_gaps = set().union(*allowed_gaps_by_agent.values())
    _require(
        set(evidence_refs).issubset(scoped_evidence)
        and set(authority_refs).issubset(scoped_authority)
        and set(gap_refs).issubset(allowed_gaps),
        "multi_agent_report_clause_reference_scope_invalid",
    )
    if kind == "content":
        _require(claim_refs, "multi_agent_report_content_clause_claim_missing")
    elif kind == "gap":
        _require(gap_refs, "multi_agent_report_gap_clause_gap_missing")
    elif kind == "wwc":
        _require(
            bool(claim_refs or evidence_refs or authority_refs or gap_refs),
            "multi_agent_report_wwc_clause_unbound",
        )
    return {
        "model_text": model_text,
        "source_workpaper_agent_ids": source_agents,
        "source_claim_refs": claim_refs,
        "evidence_refs": evidence_refs,
        "authority_refs": authority_refs,
        "gap_refs": gap_refs,
    }


def validate_protected_report_draft(
    payload: Mapping[str, Any],
    *,
    authority_catalog: Mapping[str, Any],
    boundary_disposition_register: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _require(
        _valid_authority_catalog_schema(authority_catalog.get("schema_version")),
        "multi_agent_report_authority_catalog_invalid",
    )
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "report_topic",
        "executive_thesis",
        "sections",
        "remaining_gaps",
        "what_would_change",
        "confidence",
    }
    _require(
        set(value) == expected
        and value.get("schema_version")
        == MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "multi_agent_protected_report_identity_invalid",
    )
    contract_audit = audit_protected_report_draft(
        value,
        authority_catalog=authority_catalog,
        boundary_disposition_register=boundary_disposition_register,
    )
    _require(
        contract_audit["contract_valid"] is True,
        (
            contract_audit["hard_findings"][0]["finding_code"]
            if contract_audit["hard_findings"]
            else "multi_agent_protected_report_contract_invalid"
        ),
        details={"contract_finding_receipt": contract_audit},
    )
    try:
        topic = validate_current_research_model_text(
            value.get("report_topic"),
            minimum=_REPORT_TEXT_LIMITS["topic"]["minimum"],
            maximum=_REPORT_TEXT_LIMITS["topic"]["safety_maximum"],
            code="multi_agent_report_topic_unprotected_surface",
        )
    except CurrentResearchConsumerError as exc:
        raise MultiAgentReportAuthorityError(exc.code) from exc
    raw_executive = value.get("executive_thesis")
    _require(
        isinstance(raw_executive, list) and 1 <= len(raw_executive) <= 6,
        "multi_agent_report_executive_thesis_invalid",
    )
    executive = [
        _validate_clause(
            row,
            catalog=authority_catalog,
            kind="content",
            minimum_chars=_REPORT_TEXT_LIMITS["executive"]["minimum"],
            maximum_chars=_REPORT_TEXT_LIMITS["executive"]["safety_maximum"],
        )
        for row in raw_executive
    ]
    raw_sections = value.get("sections")
    _require(
        isinstance(raw_sections, list) and 4 <= len(raw_sections) <= 10,
        "multi_agent_report_sections_invalid",
    )
    sections: list[dict[str, Any]] = []
    seen_headings: set[str] = set()
    for raw_section in raw_sections:
        section = _mapping(raw_section, "multi_agent_report_section_invalid")
        _require(
            set(section) == {"heading", "clauses"},
            "multi_agent_report_section_fields_invalid",
        )
        try:
            heading = validate_current_research_model_text(
                section.get("heading"),
                minimum=_REPORT_TEXT_LIMITS["heading"]["minimum"],
                maximum=_REPORT_TEXT_LIMITS["heading"]["safety_maximum"],
                code="multi_agent_report_heading_unprotected_surface",
            )
        except CurrentResearchConsumerError as exc:
            raise MultiAgentReportAuthorityError(exc.code) from exc
        _require(heading not in seen_headings, "multi_agent_report_heading_duplicate")
        seen_headings.add(heading)
        raw_clauses = section.get("clauses")
        _require(
            isinstance(raw_clauses, list) and 1 <= len(raw_clauses) <= 10,
            "multi_agent_report_section_clauses_invalid",
        )
        sections.append(
            {
                "heading": heading,
                "clauses": [
                    _validate_clause(
                        row,
                        catalog=authority_catalog,
                        kind="content",
                        minimum_chars=_REPORT_TEXT_LIMITS["section"]["minimum"],
                        maximum_chars=_REPORT_TEXT_LIMITS["section"][
                            "safety_maximum"
                        ],
                    )
                    for row in raw_clauses
                ],
            }
        )
    raw_gaps = value.get("remaining_gaps")
    raw_wwc = value.get("what_would_change")
    _require(
        isinstance(raw_gaps, list) and 1 <= len(raw_gaps) <= 12,
        "multi_agent_report_remaining_gaps_invalid",
    )
    _require(
        isinstance(raw_wwc, list) and 2 <= len(raw_wwc) <= 12,
        "multi_agent_report_what_would_change_invalid",
    )
    remaining_gaps = [
        _validate_clause(
            row,
            catalog=authority_catalog,
            kind="gap",
            minimum_chars=_REPORT_TEXT_LIMITS["gap"]["minimum"],
            maximum_chars=_REPORT_TEXT_LIMITS["gap"]["safety_maximum"],
        )
        for row in raw_gaps
    ]
    what_would_change = [
        _validate_clause(
            row,
            catalog=authority_catalog,
            kind="wwc",
            minimum_chars=_REPORT_TEXT_LIMITS["wwc"]["minimum"],
            maximum_chars=_REPORT_TEXT_LIMITS["wwc"]["safety_maximum"],
        )
        for row in raw_wwc
    ]
    confidence = _validate_clause(
        value.get("confidence"),
        catalog=authority_catalog,
        kind="content",
        minimum_chars=_REPORT_TEXT_LIMITS["confidence"]["minimum"],
        maximum_chars=_REPORT_TEXT_LIMITS["confidence"]["safety_maximum"],
    )
    trusted = {
        "schema_version": MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION,
        "authority_catalog_digest": authority_catalog["authority_catalog_digest"],
        "report_topic": topic,
        "executive_thesis": executive,
        "sections": sections,
        "remaining_gaps": remaining_gaps,
        "what_would_change": what_would_change,
        "confidence": confidence,
        "surface_contract_receipt": {
            "all_model_prose_passed_shared_numeric_free_validator": True,
            "all_evidence_authority_and_gap_refs_are_claim_or_workpaper_scoped": True,
            "raw_evidence_numeric_surface_used_as_output_authority": False,
            "deterministic_rendering_required": True,
            "recommended_narrative_density_pass": not bool(
                contract_audit["quality_findings"]
            ),
            "quality_findings": deepcopy(
                contract_audit["quality_findings"]
            ),
            "contract_finding_receipt_digest": contract_audit[
                "receipt_digest"
            ],
        },
    }
    return {**trusted, "draft_digest": canonical_digest(trusted)}


def validate_protected_report_remap_draft(
    payload: Mapping[str, Any],
    *,
    authority_catalog: Mapping[str, Any],
    source_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the protected contract plus immutable report topology."""

    trusted = validate_protected_report_draft(
        payload,
        authority_catalog=authority_catalog,
    )
    source = _mapping(source_report, "multi_agent_report_remap_source_invalid")
    source_sections = source.get("sections")
    source_gaps = source.get("remaining_gaps")
    source_wwc = source.get("what_would_change")
    _require(
        isinstance(source_sections, list)
        and isinstance(source_gaps, list)
        and isinstance(source_wwc, list)
        and len(trusted["executive_thesis"]) == 1
        and len(trusted["sections"]) == len(source_sections)
        and all(len(section["clauses"]) == 1 for section in trusted["sections"])
        and len(trusted["remaining_gaps"]) == len(source_gaps)
        and len(trusted["what_would_change"]) == len(source_wwc),
        "multi_agent_report_remap_topology_drift",
    )
    expected_agent_order = [
        [str(value) for value in row.get("source_workpaper_agent_ids") or ()]
        for row in source_sections
    ]
    actual_agent_order = [
        list(row["clauses"][0]["source_workpaper_agent_ids"])
        for row in trusted["sections"]
    ]
    _require(
        all(row for row in expected_agent_order)
        and actual_agent_order == expected_agent_order
        and all(
            all(
                clause["source_workpaper_agent_ids"] == expected_agent_order[index]
                for clause in section["clauses"]
            )
            for index, section in enumerate(trusted["sections"])
        ),
        "multi_agent_report_remap_section_agent_order_drift",
    )
    receipt = {
        "source_report_digest": str(source.get("report_digest") or ""),
        "executive_thesis_clause_count_preserved": True,
        "section_count_preserved": True,
        "one_clause_per_source_section_preserved": True,
        "section_agent_order_preserved": True,
        "remaining_gap_count_preserved": True,
        "what_would_change_count_preserved": True,
        "new_research_authority_granted": False,
    }
    trusted_without_digest = {
        key: value for key, value in trusted.items() if key != "draft_digest"
    }
    body = {
        **trusted_without_digest,
        "remap_receipt": receipt,
    }
    return {**body, "draft_digest": canonical_digest(body)}


def _render_clause(
    clause: Mapping[str, Any],
    *,
    presentation_by_ref: Mapping[str, Mapping[str, Any]],
) -> tuple[str, dict[str, Any]]:
    parts = [str(clause["model_text"]).strip()]
    presentations = [
        str(presentation_by_ref[ref]["display_surface"])
        for ref in clause["authority_refs"]
    ]
    if presentations:
        parts.append("Facts: " + "; ".join(presentations) + ".")
    if clause["evidence_refs"]:
        parts.append("[Sources: " + ", ".join(clause["evidence_refs"]) + "]")
    if clause["gap_refs"]:
        parts.append("[Gaps: " + ", ".join(clause["gap_refs"]) + "]")
    rendered = " ".join(parts)
    receipt = {
        "source_claim_refs": list(clause["source_claim_refs"]),
        "source_workpaper_agent_ids": list(clause["source_workpaper_agent_ids"]),
        "rendered_evidence_refs": list(clause["evidence_refs"]),
        "rendered_authority_refs": list(clause["authority_refs"]),
        "rendered_gap_refs": list(clause["gap_refs"]),
        "model_text_digest": canonical_digest({"model_text": clause["model_text"]}),
        "rendered_text_digest": canonical_digest({"rendered_text": rendered}),
    }
    return rendered, receipt


def render_protected_report(
    draft: Mapping[str, Any],
    *,
    authority_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    if "draft_digest" in draft:
        trusted = deepcopy(dict(draft))
        supplied_digest = str(trusted.pop("draft_digest", ""))
        _require(
            trusted.get("authority_catalog_digest")
            == authority_catalog.get("authority_catalog_digest")
            and supplied_digest == canonical_digest(trusted),
            "multi_agent_protected_report_draft_digest_invalid",
        )
        trusted["draft_digest"] = supplied_digest
    else:
        trusted = validate_protected_report_draft(
            draft,
            authority_catalog=authority_catalog,
        )
    presentation_by_ref = {
        str(row["authority_ref"]): row
        for row in authority_catalog["presentation_authority"]
    }
    identity = authority_catalog["case_identity"]
    receipts: list[dict[str, Any]] = []

    def render(raw: Mapping[str, Any], path: str) -> str:
        text, receipt = _render_clause(raw, presentation_by_ref=presentation_by_ref)
        receipts.append({"field_path": path, **receipt})
        return text

    executive = [
        render(row, f"executive_thesis[{index}]")
        for index, row in enumerate(trusted["executive_thesis"])
    ]
    sections = []
    for section_index, section in enumerate(trusted["sections"]):
        sections.append(
            {
                "heading": section["heading"],
                "body": "\n\n".join(
                    render(
                        row,
                        f"sections[{section_index}].clauses[{clause_index}]",
                    )
                    for clause_index, row in enumerate(section["clauses"])
                ),
            }
        )
    report_title = (
        f"{identity['subject_legal_name']} research as of "
        f"{identity['research_as_of']}: {trusted['report_topic']}"
    )
    unsigned = {
        "schema_version": MULTI_AGENT_PROTECTED_RENDERED_REPORT_SCHEMA_VERSION,
        "status": "multi_agent_protected_report_rendered",
        "case_identity": deepcopy(identity),
        "authority_catalog_digest": authority_catalog["authority_catalog_digest"],
        "draft_digest": trusted["draft_digest"],
        "report_title": report_title,
        "executive_thesis": "\n\n".join(executive),
        "sections": sections,
        "remaining_gaps": [
            render(row, f"remaining_gaps[{index}]")
            for index, row in enumerate(trusted["remaining_gaps"])
        ],
        "what_would_change": [
            render(row, f"what_would_change[{index}]")
            for index, row in enumerate(trusted["what_would_change"])
        ],
        "confidence_statement": render(trusted["confidence"], "confidence"),
        "rendering_receipts": receipts,
        "rendering_authority": {
            "case_identity_period_numeric_and_citations_harness_rendered": True,
            "model_authored_research_judgment_and_prose": True,
            "raw_evidence_numeric_surface_promoted": False,
            "all_rendered_protected_surfaces_content_addressed": True,
            "qualified_human_review_required": True,
            "product_publication": False,
        },
    }
    return {**unsigned, "rendered_report_digest": canonical_digest(unsigned)}


def audit_legacy_report_protected_surfaces(report: Mapping[str, Any]) -> dict[str, Any]:
    """Show why a legacy free-prose report cannot satisfy the v1 contract."""

    fields: list[tuple[str, str]] = [
        ("report_title", str(report.get("report_title") or "")),
        ("executive_thesis", str(report.get("executive_thesis") or "")),
        ("confidence_statement", str(report.get("confidence_statement") or "")),
    ]
    for index, section in enumerate(report.get("sections") or ()):
        fields.extend(
            [
                (f"sections[{index}].heading", str(section.get("heading") or "")),
                (f"sections[{index}].body", str(section.get("body") or "")),
            ]
        )
    for key in ("remaining_gaps", "what_would_change"):
        for index, value in enumerate(report.get(key) or ()):
            fields.append((f"{key}[{index}]", str(value or "")))
    findings: list[dict[str, Any]] = []
    for field_path, text in fields:
        masked = _ALIAS.sub(" ", text)
        matches = [match.group(0) for match in _PROTECTED_SURFACE.finditer(masked)]
        if matches:
            findings.append(
                {
                    "field_path": field_path,
                    "unbound_surface_count": len(matches),
                    "sample_surfaces": matches[:12],
                    "finding_code": "legacy_free_prose_protected_surface_unbound",
                }
            )
    unsigned = {
        "status": "hard_fail" if findings else "pass",
        "local_surface_gate_pass": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "boundary": (
            "Matching a source value by inspection is not a binding receipt. "
            "Legacy prose must be remapped into model text plus typed authority refs."
        ),
    }
    return {**unsigned, "audit_digest": canonical_digest(unsigned)}


__all__ = [
    "MULTI_AGENT_PROTECTED_RENDERED_REPORT_SCHEMA_VERSION",
    "MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION",
    "MULTI_AGENT_PROTECTED_REPORT_DRAFT_LEGACY_SCHEMA_VERSION",
    "MULTI_AGENT_PROTECTED_REPORT_REFERENCE_PATCH_SCHEMA_VERSION",
    "MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION",
    "MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION",
    "MultiAgentReportAuthorityError",
    "audit_legacy_report_protected_surfaces",
    "audit_protected_report_draft",
    "apply_protected_report_reference_patch",
    "compile_protected_report_reference_patch_messages",
    "compile_protected_report_reference_patch_receipt",
    "compile_protected_report_remap_messages",
    "compile_multi_agent_report_authority_catalog",
    "compile_protected_report_messages",
    "extend_multi_agent_report_authority_catalog",
    "protected_report_draft_tool",
    "protected_report_reference_patch_tool",
    "render_protected_report",
    "validate_protected_report_draft",
    "validate_protected_report_remap_draft",
]
