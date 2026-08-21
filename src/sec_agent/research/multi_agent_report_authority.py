from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
from typing import Any, Mapping, Sequence

from .current_consumer import (
    CurrentResearchConsumerError,
    bind_current_research_model_text_schema_definition,
    compile_current_research_model_text_schema,
    validate_current_research_model_text,
)
from .reviewed_evidence_pack import canonical_digest


MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION = (
    "fin_ia_multi_agent_report_authority_catalog_v1_0"
)
MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION = (
    "fin_ia_multi_agent_report_authority_catalog_v1_1"
)
MULTI_AGENT_PROTECTED_REPORT_DRAFT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_protected_report_draft_v1_0"
)
MULTI_AGENT_PROTECTED_RENDERED_REPORT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_protected_rendered_report_v1_0"
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


class MultiAgentReportAuthorityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MultiAgentReportAuthorityError(code)


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
    relation_rows: dict[str, dict[str, Any]] = {}
    gap_rows: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(contexts):
        context = contexts[agent_id]
        view = _mapping(
            context.get("cell_analysis_view"),
            "multi_agent_report_cell_view_missing",
        )
        identity = deepcopy(
            dict(
                _mapping(
                    view.get("case_identity"),
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
            _merge_catalog_row(
                numeric_rows,
                ref=ref,
                row=raw,
                code="multi_agent_report_numeric_authority_conflict",
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
    selected_gaps: set[str] = set()
    claims: list[dict[str, Any]] = []
    claim_refs_by_agent: dict[str, list[str]] = {}
    for agent_id in sorted(by_agent):
        workpaper = by_agent[agent_id]
        selected_gaps.update(str(ref) for ref in workpaper.get("remaining_gap_refs") or ())
        for index, raw_claim in enumerate(workpaper.get("sourced_claims") or ()):
            claim = _mapping(raw_claim, "multi_agent_report_claim_invalid")
            evidence_refs = sorted(str(ref) for ref in claim.get("evidence_refs") or ())
            numeric_refs = sorted(str(ref) for ref in claim.get("numeric_refs") or ())
            relation_refs = sorted(
                str(ref) for ref in claim.get("numeric_relation_refs") or ()
            )
            seed = {
                "agent_id": agent_id,
                "claim_index": index,
                "claim": str(claim.get("claim") or ""),
                "authority": str(claim.get("authority") or ""),
                "evidence_refs": evidence_refs,
                "numeric_refs": numeric_refs,
                "numeric_relation_refs": relation_refs,
            }
            claim_ref = "WPCLAIM::" + canonical_digest(seed)[:20].upper()
            claims.append(
                {
                    "claim_ref": claim_ref,
                    **seed,
                    "authority_refs": sorted({*numeric_refs, *relation_refs}),
                }
            )
            claim_refs_by_agent.setdefault(agent_id, []).append(claim_ref)
            selected_evidence.update(evidence_refs)
            selected_numeric.update(numeric_refs)
            selected_relations.update(relation_refs)

    _require(
        selected_evidence.issubset(evidence_rows)
        and selected_numeric.issubset(numeric_rows)
        and selected_relations.issubset(relation_rows)
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
    presentations = [
        *(_numeric_presentation(numeric_rows[ref]) for ref in sorted(selected_numeric)),
        *(
            _relation_presentation(relation_rows[ref])
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
                    "citations or exact financial surfaces."
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
                description="Flexible report topic without company identity, dates or numbers."
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
    try:
        topic = validate_current_research_model_text(
            value.get("report_topic"),
            minimum=8,
            maximum=180,
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
            minimum_chars=24,
            maximum_chars=900,
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
                minimum=4,
                maximum=140,
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
                        minimum_chars=12,
                        maximum_chars=900,
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
            minimum_chars=12,
            maximum_chars=700,
        )
        for row in raw_gaps
    ]
    what_would_change = [
        _validate_clause(
            row,
            catalog=authority_catalog,
            kind="wwc",
            minimum_chars=12,
            maximum_chars=700,
        )
        for row in raw_wwc
    ]
    confidence = _validate_clause(
        value.get("confidence"),
        catalog=authority_catalog,
        kind="content",
        minimum_chars=20,
        maximum_chars=700,
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
        },
    }
    return {**trusted, "draft_digest": canonical_digest(trusted)}


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
    "MULTI_AGENT_REPORT_AUTHORITY_CATALOG_SCHEMA_VERSION",
    "MULTI_AGENT_REPORT_AUTHORITY_CATALOG_EXTENDED_SCHEMA_VERSION",
    "MultiAgentReportAuthorityError",
    "audit_legacy_report_protected_surfaces",
    "compile_multi_agent_report_authority_catalog",
    "compile_protected_report_messages",
    "extend_multi_agent_report_authority_catalog",
    "protected_report_draft_tool",
    "render_protected_report",
    "validate_protected_report_draft",
]
