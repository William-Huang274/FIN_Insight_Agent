from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


SOURCE_BOUND_NUMERIC_REVIEW_SCHEMA_VERSION = (
    "fin_ia_source_bound_numeric_authority_review_v1_0"
)
SOURCE_BOUND_NUMERIC_PROGRAM_SCHEMA_VERSION = (
    "fin_ia_source_bound_numeric_authority_program_v1_0"
)

_ALLOWED_DECISIONS = {
    "bind_existing_numeric_fact",
    "admit_exact_numeric_fact",
    "admit_bounded_presentation",
    "context_only_do_not_output",
    "forbidden_or_ambiguous",
}
_EXACT_FACT_STATUSES = {
    "company_reported_actual",
    "management_reported_actual",
    "filed_reported_actual",
}
_BOUNDED_FACT_STATUSES = {
    "company_guidance",
    "management_approximation",
    "management_threshold",
    "reported_approximation",
}
_BOUNDED_VALUE_KINDS = {
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "approximate",
    "closed_range",
}
_SCALE_MULTIPLIERS = {
    "": Decimal("1"),
    "unit": Decimal("1"),
    "ones": Decimal("1"),
    "thousand": Decimal("1000"),
    "million": Decimal("1000000"),
    "billion": Decimal("1000000000"),
}
_NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_EXPLICIT_SCALE = re.compile(
    r"(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>billion|million|thousand|[BMK])\b",
    re.IGNORECASE,
)


class SourceBoundNumericAuthorityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SourceBoundNumericAuthorityError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _decimal(value: object, code: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SourceBoundNumericAuthorityError(code) from exc
    _require(parsed.is_finite(), code)
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _normalized_scale(value: object) -> str:
    raw = str(value or "").strip().casefold()
    aliases = {
        "b": "billion",
        "bn": "billion",
        "billions": "billion",
        "m": "million",
        "mm": "million",
        "millions": "million",
        "k": "thousand",
        "thousands": "thousand",
    }
    normalized = aliases.get(raw, raw)
    _require(
        normalized in _SCALE_MULTIPLIERS,
        "source_bound_numeric_scale_invalid",
    )
    return normalized


def _surface_value(surface: object, *, declared_scale: object) -> Decimal:
    text = str(surface or "").strip()
    _require(bool(text), "source_bound_numeric_source_value_surface_missing")
    numbers = _NUMBER.findall(text)
    _require(
        len(numbers) == 1,
        "source_bound_numeric_source_value_surface_ambiguous",
    )
    base = _decimal(numbers[0].replace(",", ""), "source_bound_numeric_value_invalid")
    explicit = _EXPLICIT_SCALE.search(text)
    if explicit:
        scale = _normalized_scale(explicit.group("scale"))
    else:
        scale = _normalized_scale(declared_scale)
    return base * _SCALE_MULTIPLIERS[scale]


def _claim_index(authority_catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for raw in authority_catalog.get("claims") or ():
        row = deepcopy(dict(_mapping(raw, "source_bound_numeric_claim_invalid")))
        ref = str(row.get("claim_ref") or "")
        _require(
            ref.startswith("WPCLAIM::") and ref not in output,
            "source_bound_numeric_claim_ref_invalid",
        )
        output[ref] = row
    _require(bool(output), "source_bound_numeric_claim_catalog_missing")
    return output


def _context_index(
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
            agent = context.get("agent") or {}
            agent_id = str(
                context.get("agent_id")
                or (agent.get("agent_id") if isinstance(agent, Mapping) else "")
                or ""
            )
            _require(
                agent_id and agent_id not in rows,
                "source_bound_numeric_context_agent_invalid",
            )
            rows[agent_id] = context
    _require(bool(rows), "source_bound_numeric_contexts_missing")
    return rows


def _context_catalogs(
    contexts: Mapping[str, Mapping[str, Any]],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    evidence: dict[str, dict[str, Any]] = {}
    numeric: dict[str, dict[str, Any]] = {}
    evidence_agents: dict[str, set[str]] = {}
    numeric_agents: dict[str, set[str]] = {}
    for agent_id in sorted(contexts):
        view = _mapping(
            contexts[agent_id].get("cell_analysis_view"),
            "source_bound_numeric_cell_view_missing",
        )
        for raw in view.get("evidence_fact_catalog") or ():
            row = deepcopy(dict(_mapping(raw, "source_bound_numeric_evidence_invalid")))
            ref = str(row.get("evidence_ref") or "")
            _require(ref.startswith("EV::"), "source_bound_numeric_evidence_ref_invalid")
            if ref in evidence:
                _require(
                    evidence[ref] == row,
                    "source_bound_numeric_evidence_conflict",
                )
            else:
                evidence[ref] = row
            evidence_agents.setdefault(ref, set()).add(agent_id)
        for raw in view.get("numeric_fact_catalog") or ():
            row = deepcopy(dict(_mapping(raw, "source_bound_numeric_fact_invalid")))
            ref = str(row.get("numeric_ref") or "")
            _require(ref.startswith("NUM::"), "source_bound_numeric_ref_invalid")
            if ref in numeric:
                _require(
                    numeric[ref] == row,
                    "source_bound_numeric_fact_conflict",
                )
            else:
                numeric[ref] = row
            numeric_agents.setdefault(ref, set()).add(agent_id)
    return evidence, numeric, evidence_agents, numeric_agents


def _validated_bindings(
    raw: object,
    *,
    claims: Mapping[str, Mapping[str, Any]],
    evidence_ref: str = "",
) -> list[dict[str, str]]:
    _require(isinstance(raw, list) and bool(raw), "source_bound_numeric_bindings_missing")
    output: list[dict[str, str]] = []
    for item in raw:
        binding = _mapping(item, "source_bound_numeric_binding_invalid")
        _require(
            set(binding) == {"agent_id", "claim_ref"},
            "source_bound_numeric_binding_shape_invalid",
        )
        agent_id = str(binding.get("agent_id") or "")
        claim_ref = str(binding.get("claim_ref") or "")
        _require(claim_ref in claims, "source_bound_numeric_binding_claim_unknown")
        claim = claims[claim_ref]
        _require(
            str(claim.get("agent_id") or "") == agent_id,
            "source_bound_numeric_binding_agent_mismatch",
        )
        if evidence_ref:
            _require(
                evidence_ref in set(claim.get("evidence_refs") or ()),
                "source_bound_numeric_binding_evidence_out_of_scope",
            )
        compiled = {"agent_id": agent_id, "claim_ref": claim_ref}
        _require(
            compiled not in output,
            "source_bound_numeric_binding_duplicate",
        )
        output.append(compiled)
    return sorted(output, key=lambda row: (row["agent_id"], row["claim_ref"]))


def _source_receipt(
    *,
    evidence: Mapping[str, Any],
    source_quote: str,
    source_value_surfaces: Sequence[str],
) -> dict[str, Any]:
    excerpt = str(evidence.get("source_visible_fact_excerpt") or "")
    _require(bool(excerpt), "source_bound_numeric_source_excerpt_missing")
    _require(
        excerpt.count(source_quote) == 1,
        "source_bound_numeric_source_quote_not_unique",
    )
    quote_start = excerpt.index(source_quote)
    value_spans: list[dict[str, Any]] = []
    for surface in source_value_surfaces:
        _require(
            source_quote.count(surface) == 1,
            "source_bound_numeric_value_surface_not_unique_in_quote",
        )
        relative_start = source_quote.index(surface)
        value_spans.append(
            {
                "source_value_surface": surface,
                "excerpt_start": quote_start + relative_start,
                "excerpt_end": quote_start + relative_start + len(surface),
            }
        )
    return {
        "evidence_ref": str(evidence.get("evidence_ref") or ""),
        "evidence_owner_ticker": str(evidence.get("evidence_owner_ticker") or ""),
        "source_type": str(evidence.get("source_type") or ""),
        "source_tier": str(evidence.get("source_tier") or ""),
        "publication_date": evidence.get("publication_date"),
        "source_reporting_period_end": evidence.get("source_reporting_period_end"),
        "source_quote": source_quote,
        "source_quote_start": quote_start,
        "source_quote_end": quote_start + len(source_quote),
        "source_quote_digest": canonical_digest({"source_quote": source_quote}),
        "value_spans": value_spans,
    }


def _period(raw: object) -> dict[str, Any]:
    row = _mapping(raw, "source_bound_numeric_period_missing")
    expected = {
        "period_start",
        "period_end",
        "fiscal_year",
        "fiscal_period",
        "period_role",
    }
    _require(set(row) == expected, "source_bound_numeric_period_shape_invalid")
    period_end = str(row.get("period_end") or "")
    fiscal_year = row.get("fiscal_year")
    fiscal_period = str(row.get("fiscal_period") or "")
    _require(
        bool(period_end) or (fiscal_year not in (None, "") and bool(fiscal_period)),
        "source_bound_numeric_period_identity_missing",
    )
    return {
        "period_start": row.get("period_start"),
        "period_end": period_end or None,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_role": str(row.get("period_role") or ""),
    }


def _claim_add(
    target: dict[str, set[str]],
    bindings: Sequence[Mapping[str, str]],
    authority_ref: str,
) -> None:
    for binding in bindings:
        target.setdefault(str(binding["claim_ref"]), set()).add(authority_ref)


def _existing_binding(
    decision: Mapping[str, Any],
    *,
    claims: Mapping[str, Mapping[str, Any]],
    numeric_rows: Mapping[str, Mapping[str, Any]],
    numeric_agents: Mapping[str, set[str]],
    claim_additions: dict[str, set[str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = {
        "decision_id",
        "decision",
        "claim_bindings",
        "numeric_ref",
        "claim_value_surface",
        "reason_code",
    }
    _require(set(decision) == expected, "source_bound_existing_binding_shape_invalid")
    ref = str(decision.get("numeric_ref") or "")
    _require(ref in numeric_rows, "source_bound_existing_numeric_ref_unknown")
    bindings = _validated_bindings(decision.get("claim_bindings"), claims=claims)
    _require(
        all(binding["agent_id"] in numeric_agents[ref] for binding in bindings),
        "source_bound_existing_numeric_agent_out_of_scope",
    )
    surface = str(decision.get("claim_value_surface") or "")
    row = deepcopy(dict(numeric_rows[ref]))
    parsed = _surface_value(surface, declared_scale="")
    expected_value = _decimal(
        row.get("value_decimal"), "source_bound_existing_numeric_value_invalid"
    )
    _require(parsed == expected_value, "source_bound_existing_numeric_surface_mismatch")
    for binding in bindings:
        claim_text = str(claims[binding["claim_ref"]].get("claim") or "")
        _require(
            surface in claim_text,
            "source_bound_existing_numeric_surface_not_in_claim",
        )
    _claim_add(claim_additions, bindings, ref)
    return row, {
        "decision_id": str(decision["decision_id"]),
        "decision": "bind_existing_numeric_fact",
        "authority_ref": ref,
        "claim_bindings": bindings,
        "claim_value_surface": surface,
        "reason_code": str(decision.get("reason_code") or ""),
        "new_numeric_fact_created": False,
    }


def _admitted_decision(
    decision: Mapping[str, Any],
    *,
    claims: Mapping[str, Mapping[str, Any]],
    evidence_rows: Mapping[str, Mapping[str, Any]],
    evidence_agents: Mapping[str, set[str]],
    case_identity: Mapping[str, Any],
    claim_additions: dict[str, set[str]],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    common = {
        "decision_id",
        "decision",
        "claim_bindings",
        "evidence_ref",
        "source_quote",
        "source_value_surfaces",
        "semantic_metric_key",
        "fact_status",
        "value_kind",
        "unit",
        "source_scale",
        "period",
        "claim_boundary",
        "qualifier",
        "point_estimate_forbidden",
        "normalized_values",
    }
    _require(set(decision) == common, "source_bound_admission_shape_invalid")
    evidence_ref = str(decision.get("evidence_ref") or "")
    _require(evidence_ref in evidence_rows, "source_bound_admission_evidence_unknown")
    bindings = _validated_bindings(
        decision.get("claim_bindings"),
        claims=claims,
        evidence_ref=evidence_ref,
    )
    _require(
        all(binding["agent_id"] in evidence_agents[evidence_ref] for binding in bindings),
        "source_bound_admission_evidence_agent_out_of_scope",
    )
    source_quote = str(decision.get("source_quote") or "")
    surfaces = decision.get("source_value_surfaces")
    _require(
        isinstance(surfaces, list)
        and bool(surfaces)
        and all(isinstance(item, str) and item for item in surfaces),
        "source_bound_admission_source_surfaces_invalid",
    )
    receipt = _source_receipt(
        evidence=evidence_rows[evidence_ref],
        source_quote=source_quote,
        source_value_surfaces=surfaces,
    )
    normalized = decision.get("normalized_values")
    _require(
        isinstance(normalized, list)
        and len(normalized) == len(surfaces),
        "source_bound_admission_normalized_values_invalid",
    )
    parsed_values = [
        _surface_value(surface, declared_scale=decision.get("source_scale"))
        for surface in surfaces
    ]
    expected_values = [
        _decimal(value, "source_bound_admission_normalized_value_invalid")
        for value in normalized
    ]
    _require(
        parsed_values == expected_values,
        "source_bound_admission_surface_value_mismatch",
    )
    period = _period(decision.get("period"))
    owner = str(evidence_rows[evidence_ref].get("evidence_owner_ticker") or "")
    semantic_metric = str(decision.get("semantic_metric_key") or "")
    unit = str(decision.get("unit") or "")
    fact_status = str(decision.get("fact_status") or "")
    value_kind = str(decision.get("value_kind") or "")
    _require(
        owner and semantic_metric and unit and fact_status and value_kind,
        "source_bound_admission_semantics_missing",
    )
    seed = {
        "case_key": str(case_identity.get("case_key") or ""),
        "evidence_ref": evidence_ref,
        "source_quote_digest": receipt["source_quote_digest"],
        "semantic_metric_key": semantic_metric,
        "fact_status": fact_status,
        "value_kind": value_kind,
        "unit": unit,
        "normalized_values": [_decimal_text(value) for value in expected_values],
        "period": period,
        "qualifier": str(decision.get("qualifier") or ""),
    }
    if decision["decision"] == "admit_exact_numeric_fact":
        _require(
            fact_status in _EXACT_FACT_STATUSES
            and value_kind == "exact_scalar"
            and len(expected_values) == 1
            and decision.get("point_estimate_forbidden") is False,
            "source_bound_exact_fact_semantics_invalid",
        )
        authority_ref = "NUM::" + canonical_digest(seed)[:16].upper()
        authority = {
            "numeric_ref": authority_ref,
            "ticker": owner,
            "metric_id": semantic_metric,
            "value_decimal": _decimal_text(expected_values[0]),
            "unit": unit,
            **period,
            "authority_mode": "source_bound_" + fact_status + "_numeric_fact",
            "formula_trace": None,
            "source_evidence_ref": evidence_ref,
            "source_receipt": receipt,
            "fact_status": fact_status,
            "qualifier": str(decision.get("qualifier") or ""),
            "claim_boundary": str(decision.get("claim_boundary") or ""),
        }
        kind = "numeric_fact"
    else:
        _require(
            fact_status in _BOUNDED_FACT_STATUSES
            and value_kind in _BOUNDED_VALUE_KINDS
            and (
                (value_kind == "closed_range" and len(expected_values) == 2)
                or (value_kind != "closed_range" and len(expected_values) == 1)
            )
            and decision.get("point_estimate_forbidden") is True,
            "source_bound_bounded_presentation_semantics_invalid",
        )
        authority_ref = "PRES::" + canonical_digest(seed)[:16].upper()
        authority = {
            "authority_ref": authority_ref,
            "authority_kind": "bounded_source_presentation",
            "ticker": owner,
            "semantic_metric_key": semantic_metric,
            "normalized_values": [_decimal_text(value) for value in expected_values],
            "unit": unit,
            **period,
            "value_kind": value_kind,
            "fact_status": fact_status,
            "qualifier": str(decision.get("qualifier") or ""),
            "point_estimate_forbidden": True,
            "source_evidence_ref": evidence_ref,
            "source_receipt": receipt,
            "claim_boundary": str(decision.get("claim_boundary") or ""),
        }
        kind = "bounded_presentation"
    _claim_add(claim_additions, bindings, authority_ref)
    decision_receipt = {
        "decision_id": str(decision["decision_id"]),
        "decision": str(decision["decision"]),
        "authority_ref": authority_ref,
        "claim_bindings": bindings,
        "source_receipt": receipt,
        "surface_value_validation_pass": True,
        "source_presence_alone_granted_authority": False,
        "semantic_metric_key": semantic_metric,
        "fact_status": fact_status,
        "value_kind": value_kind,
    }
    return kind, authority, decision_receipt


def _non_admitted_decision(
    decision: Mapping[str, Any],
    *,
    evidence_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected = {
        "decision_id",
        "decision",
        "evidence_ref",
        "source_quote",
        "reason_code",
    }
    _require(set(decision) == expected, "source_bound_nonadmission_shape_invalid")
    evidence_ref = str(decision.get("evidence_ref") or "")
    _require(evidence_ref in evidence_rows, "source_bound_nonadmission_evidence_unknown")
    source_quote = str(decision.get("source_quote") or "")
    excerpt = str(evidence_rows[evidence_ref].get("source_visible_fact_excerpt") or "")
    _require(
        source_quote and excerpt.count(source_quote) == 1,
        "source_bound_nonadmission_source_quote_invalid",
    )
    return {
        "decision_id": str(decision["decision_id"]),
        "decision": str(decision["decision"]),
        "evidence_ref": evidence_ref,
        "source_quote_digest": canonical_digest({"source_quote": source_quote}),
        "reason_code": str(decision.get("reason_code") or ""),
        "authority_ref": None,
        "source_presence_alone_granted_authority": False,
    }


def _temporal_decision(
    decision: Mapping[str, Any],
    *,
    claims: Mapping[str, Mapping[str, Any]],
    evidence_rows: Mapping[str, Mapping[str, Any]],
    evidence_agents: Mapping[str, set[str]],
    claim_additions: dict[str, set[str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = {
        "decision_id",
        "decision",
        "claim_bindings",
        "evidence_ref",
        "date",
        "reason_code",
    }
    _require(set(decision) == expected, "source_bound_temporal_decision_shape_invalid")
    _require(
        decision.get("decision") == "admit_source_reporting_period_end",
        "source_bound_temporal_decision_invalid",
    )
    evidence_ref = str(decision.get("evidence_ref") or "")
    _require(evidence_ref in evidence_rows, "source_bound_temporal_evidence_unknown")
    bindings = _validated_bindings(
        decision.get("claim_bindings"),
        claims=claims,
        evidence_ref=evidence_ref,
    )
    _require(
        all(binding["agent_id"] in evidence_agents[evidence_ref] for binding in bindings),
        "source_bound_temporal_evidence_agent_out_of_scope",
    )
    date = str(decision.get("date") or "")
    _require(
        bool(re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date))
        and date == str(evidence_rows[evidence_ref].get("source_reporting_period_end") or ""),
        "source_bound_temporal_date_not_bound",
    )
    seed = {
        "evidence_ref": evidence_ref,
        "temporal_kind": "source_reporting_period_end",
        "date": date,
    }
    ref = "TEMP::" + canonical_digest(seed)[:16].upper()
    _claim_add(claim_additions, bindings, ref)
    authority = {
        "authority_ref": ref,
        "authority_kind": "source_temporal_authority",
        "source_evidence_ref": evidence_ref,
        "temporal_kind": "source_reporting_period_end",
        "date": date,
    }
    receipt = {
        "decision_id": str(decision["decision_id"]),
        "decision": "admit_source_reporting_period_end",
        "authority_ref": ref,
        "evidence_ref": evidence_ref,
        "claim_bindings": bindings,
        "date": date,
        "reason_code": str(decision.get("reason_code") or ""),
        "evidence_metadata_automatically_promoted": False,
    }
    return authority, receipt


def compile_source_bound_numeric_authority_program(
    *,
    authority_catalog: Mapping[str, Any],
    specialist_contexts: Mapping[str, Mapping[str, Any]]
    | Sequence[Mapping[str, Any]],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile reviewed source-visible numbers into typed report authority.

    The compiler deliberately does not discover or promote arbitrary numbers.
    It verifies a qualified decision against the exact immutable Evidence span,
    the owning Specialist claim and the existing S2 catalog.  This keeps raw
    visibility, semantic admission and final rendering as separate steps.
    """

    _require(
        review.get("schema_version") == SOURCE_BOUND_NUMERIC_REVIEW_SCHEMA_VERSION
        and review.get("status")
        == "qualified_engineering_source_bound_numeric_review",
        "source_bound_numeric_review_header_invalid",
    )
    _require(
        review.get("base_authority_catalog_digest")
        == authority_catalog.get("authority_catalog_digest"),
        "source_bound_numeric_base_catalog_drift",
    )
    case_identity = deepcopy(
        dict(
            _mapping(
                authority_catalog.get("case_identity"),
                "source_bound_numeric_case_identity_missing",
            )
        )
    )
    _require(
        dict(_mapping(review.get("case_identity"), "source_bound_numeric_review_identity_missing"))
        == case_identity,
        "source_bound_numeric_case_identity_drift",
    )
    claims = _claim_index(authority_catalog)
    contexts = _context_index(specialist_contexts)
    evidence_rows, numeric_rows, evidence_agents, numeric_agents = _context_catalogs(
        contexts
    )
    decisions = review.get("decisions")
    _require(
        isinstance(decisions, list) and bool(decisions),
        "source_bound_numeric_review_decisions_missing",
    )
    seen_decision_ids: set[str] = set()
    claim_additions: dict[str, set[str]] = {}
    numeric_additions: dict[str, dict[str, Any]] = {}
    bounded_additions: dict[str, dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    for raw in decisions:
        decision = _mapping(raw, "source_bound_numeric_review_decision_invalid")
        decision_id = str(decision.get("decision_id") or "")
        outcome = str(decision.get("decision") or "")
        _require(
            decision_id and decision_id not in seen_decision_ids,
            "source_bound_numeric_decision_id_invalid",
        )
        _require(outcome in _ALLOWED_DECISIONS, "source_bound_numeric_decision_invalid")
        seen_decision_ids.add(decision_id)
        if outcome == "bind_existing_numeric_fact":
            row, receipt = _existing_binding(
                decision,
                claims=claims,
                numeric_rows=numeric_rows,
                numeric_agents=numeric_agents,
                claim_additions=claim_additions,
            )
            ref = str(row["numeric_ref"])
            numeric_additions.setdefault(ref, row)
            receipts.append(receipt)
            continue
        if outcome in {"admit_exact_numeric_fact", "admit_bounded_presentation"}:
            kind, authority, receipt = _admitted_decision(
                decision,
                claims=claims,
                evidence_rows=evidence_rows,
                evidence_agents=evidence_agents,
                case_identity=case_identity,
                claim_additions=claim_additions,
            )
            if kind == "numeric_fact":
                ref = str(authority["numeric_ref"])
                _require(ref not in numeric_additions, "source_bound_numeric_ref_collision")
                numeric_additions[ref] = authority
            else:
                ref = str(authority["authority_ref"])
                _require(
                    ref not in bounded_additions,
                    "source_bound_bounded_ref_collision",
                )
                bounded_additions[ref] = authority
            receipts.append(receipt)
            continue
        receipts.append(_non_admitted_decision(decision, evidence_rows=evidence_rows))

    raw_temporal = review.get("temporal_decisions")
    _require(
        isinstance(raw_temporal, list),
        "source_bound_temporal_decisions_invalid",
    )
    temporal: list[dict[str, Any]] = []
    for raw in raw_temporal:
        decision = _mapping(raw, "source_bound_temporal_decision_invalid")
        decision_id = str(decision.get("decision_id") or "")
        _require(
            decision_id and decision_id not in seen_decision_ids,
            "source_bound_numeric_decision_id_invalid",
        )
        seen_decision_ids.add(decision_id)
        authority, receipt = _temporal_decision(
            decision,
            claims=claims,
            evidence_rows=evidence_rows,
            evidence_agents=evidence_agents,
            claim_additions=claim_additions,
        )
        temporal.append(authority)
        receipts.append(receipt)
    existing_refs = {
        str(row.get("authority_ref") or "")
        for row in authority_catalog.get("presentation_authority") or ()
    }
    new_refs = set(numeric_additions) | set(bounded_additions) | {
        str(row["authority_ref"]) for row in temporal
    }
    _require(
        not (new_refs - set(numeric_rows)) & existing_refs,
        "source_bound_numeric_existing_presentation_collision",
    )
    unsigned = {
        "schema_version": SOURCE_BOUND_NUMERIC_PROGRAM_SCHEMA_VERSION,
        "base_authority_catalog_digest": authority_catalog[
            "authority_catalog_digest"
        ],
        "case_identity": case_identity,
        "numeric_fact_additions": [
            numeric_additions[ref] for ref in sorted(numeric_additions)
        ],
        "bounded_presentation_additions": [
            bounded_additions[ref] for ref in sorted(bounded_additions)
        ],
        "temporal_authority_additions": sorted(
            temporal, key=lambda row: str(row["authority_ref"])
        ),
        "claim_authority_additions": [
            {
                "claim_ref": claim_ref,
                "authority_refs": sorted(refs),
            }
            for claim_ref, refs in sorted(claim_additions.items())
        ],
        "decision_receipts": sorted(
            receipts, key=lambda row: str(row["decision_id"])
        ),
        "authority_boundary": {
            "raw_source_presence_bypasses_admission": False,
            "source_span_and_normalized_value_verified": True,
            "claim_and_agent_scope_verified": True,
            "guidance_or_approximation_becomes_exact_fact": False,
            "point_estimate_forbidden_for_bounded_presentations": True,
            "model_calls": 0,
            "network_calls": 0,
        },
        "coverage_receipt": {
            "decision_count": len(decisions) + len(raw_temporal),
            "numeric_or_bounded_decision_count": len(decisions),
            "temporal_decision_count": len(raw_temporal),
            "admitted_exact_or_existing_numeric_count": len(numeric_additions),
            "admitted_bounded_presentation_count": len(bounded_additions),
            "temporal_authority_count": len(temporal),
            "nonadmitted_decision_count": sum(
                row["decision"]
                in {"context_only_do_not_output", "forbidden_or_ambiguous"}
                for row in receipts
            ),
            "claim_with_added_authority_count": len(claim_additions),
        },
    }
    return {**unsigned, "program_digest": canonical_digest(unsigned)}


__all__ = [
    "SOURCE_BOUND_NUMERIC_PROGRAM_SCHEMA_VERSION",
    "SOURCE_BOUND_NUMERIC_REVIEW_SCHEMA_VERSION",
    "SourceBoundNumericAuthorityError",
    "compile_source_bound_numeric_authority_program",
]
