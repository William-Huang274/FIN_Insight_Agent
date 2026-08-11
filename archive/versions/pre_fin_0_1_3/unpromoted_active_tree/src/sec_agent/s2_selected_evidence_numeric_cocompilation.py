from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_policy_v1_0"
)
INVENTORY_SCHEMA = (
    "fin_ia_0_1_3_s2_material_numeric_candidate_inventory_v1_0"
)
PRESENTATION_SCHEMA = (
    "fin_ia_0_1_3_s2_stable_numeric_fact_presentation_program_v1_0"
)
NODE_VIEW_SCHEMA = "fin_ia_0_1_3_s2_bounded_numeric_node_views_v1_0"
RESULT_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_cocompilation_result_v1_0"
)
CONTRACT_REF = "fin_0_1_3.S2.selected_evidence_numeric_candidate_cocompilation:v1"

AUTHORIZED_STATUSES = frozenset(
    {"authorized_fact", "authorized_formula_operand"}
)
ALL_STATUSES = frozenset(
    {
        "authorized_fact",
        "authorized_formula_operand",
        "descriptive_nonmaterial",
        "context_only_do_not_output",
        "forbidden_or_ambiguous",
    }
)
REQUIRED_CANDIDATE_FIELDS = frozenset(
    {
        "candidate_id",
        "case_key",
        "evidence_target_id",
        "evidence_alias",
        "source_record_id",
        "source_coordinate_or_span",
        "source_surface",
        "value_kind",
        "parsed_value_or_bounds",
        "canonical_unit",
        "currency",
        "scale",
        "entity_or_evidence_owner",
        "period_or_as_of",
        "slot_ids",
        "facet_ids",
        "relationship_directions",
        "semantic_metric_key",
        "claim_and_output_boundary",
        "adjudication_status",
        "decision_code",
    }
)

_NUMBER = r"(?:\(\s*)?-?\d[\d,]*(?:\.\d+)?(?:\s*\))?"
_MONEY_RANGE_RE = re.compile(
    rf"(?P<currency>US\$|USD|EUR|\$|€)\s*(?P<low>{_NUMBER})\s*"
    rf"(?P<scale1>billion|million|thousand|bn|mn|[BMK])?\s*"
    rf"(?:to|through|[-–—])\s*(?P<currency2>US\$|USD|EUR|\$|€)?\s*"
    rf"(?P<high>{_NUMBER})\s*(?P<scale2>billion|million|thousand|bn|mn|[BMK])",
    re.IGNORECASE,
)
_PERCENT_RANGE_RE = re.compile(
    rf"(?P<low>{_NUMBER})\s*%\s*(?:to|through|[-–—])\s*"
    rf"(?P<high>{_NUMBER})\s*%",
    re.IGNORECASE,
)
_MONEY_RE = re.compile(
    rf"(?P<currency>US\$|USD|EUR|\$|€)\s*(?P<number>{_NUMBER})\s*"
    rf"(?P<scale>billion|million|thousand|bn|mn|[BMK])?",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(rf"(?P<number>{_NUMBER})\s*%", re.IGNORECASE)
_COUNT_AFTER_RE = re.compile(
    rf"(?P<qualifier>more\s+than|over|at\s+least|approximately|about|nearly)?\s*"
    rf"(?P<number>{_NUMBER})\s+"
    r"(?P<noun>customers?|systems?|servers?|units?|shipments?|employees?|suppliers?)\b",
    re.IGNORECASE,
)
_COUNT_BEFORE_RE = re.compile(
    r"(?P<noun>customer\s+count|customers?|systems?|servers?|units?|shipments?)"
    r"[^.\n]{0,32}?"
    r"(?P<qualifier>surpass(?:es|ed|ing)?|exceed(?:s|ed|ing)?|"
    r"more\s+than|over|at\s+least|approximately|about|nearly)\s*"
    rf"(?P<number>{_NUMBER})",
    re.IGNORECASE,
)
_MULTIPLE_RE = re.compile(rf"(?P<number>{_NUMBER})\s*(?:x|times)\b", re.IGNORECASE)
_TEMPORAL_RE = re.compile(
    r"(?:(?:the\s+)?(?P<half>first|second)\s+half\s+of\s+"
    r"(?:(?P<calendar>calendar|fiscal)\s+)?(?P<year1>20\d{2})|"
    r"(?P<boundary>through|beyond|into|starting|beginning(?:\s+in)?|expected\s+(?:in|by))\s+"
    r"(?:(?:mid[-\s])?(?:calendar|fiscal)[-\s]+)?(?P<year2>20\d{2}))",
    re.IGNORECASE,
)
_QUALITATIVE_PERCENT_RANGE_RE = re.compile(
    r"(?P<band>low|mid|high|approximately|approximate)[-\s]*"
    r"(?P<anchor>\d[\d,.]*)\s*%\s*(?:percentage\s+)?(?:range)?",
    re.IGNORECASE,
)
_QUALITATIVE_BAND_RE = re.compile(
    r"(?P<band>low|mid|high)[-\s](?P<digits>single|double)[-\s]digit"
    r"(?:\s+(?P<metric>operating\s+(?:income\s+)?margin|gross\s+margin|growth))?",
    re.IGNORECASE,
)
_FALLBACK_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9_])")
_TABLE_RE = re.compile(
    r"\[TABLE_START\s+id=(?P<table_id>[^\s\]]+)[^\]]*\]"
    r"(?P<body>.*?)\[TABLE_END\]",
    re.IGNORECASE | re.DOTALL,
)
_ISO_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_FISCAL_LABEL_RE = re.compile(r"\b(?:FY\s*\d{2,4}|Q[1-4])\b", re.IGNORECASE)
_FALSE_TOKEN_CONTEXT_RE = re.compile(
    r"\b(?:Rule|Form|Item)\s*$|(?:GB|TB|nm|D)\b", re.IGNORECASE
)
_TECHNICAL_OR_PRODUCT_TOKEN_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*(?:GB|TB|nm|D)|"
    r"(?:RTX|DDR|HBM|SOCAMM|LPDDR|NVL|MI)\s*[- ]?\d[A-Za-z0-9-]*)\b",
    re.IGNORECASE,
)
_SEMANTIC_MAJOR_DELIMITER_RE = re.compile(
    r"(?<!\d)\.|\.(?!\d)|[;；。!?！？•]"
)
_SEMANTIC_CLAUSE_DELIMITER_RE = re.compile(
    r"(?<!\d),(?!\d)|(?<!\d)\.|\.(?!\d)|[;；。!?！？•]"
)


class SelectedEvidenceNumericCocompilationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SelectedEvidenceNumericCocompilationError(code)


def load_numeric_cocompilation_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF
        and policy.get("provider_neutral") is True
        and policy.get("case_specific_value_whitelists") is False
        and policy.get("full_source_regex_all_promotion") is False,
        "numeric_cocompilation_policy_identity_invalid",
    )
    _require(
        frozenset(policy.get("adjudication_statuses") or ()) == ALL_STATUSES,
        "numeric_cocompilation_status_contract_invalid",
    )
    boundary = dict(policy.get("hard_boundaries") or {})
    _require(
        all(int(boundary.get(key, -1)) == 0 for key in (
            "model_calls",
            "provider_calls",
            "network_calls",
            "source_calls",
        ))
        and boundary.get("automatic_rerun") is False
        and boundary.get("source_presence_bypasses_authority") is False
        and boundary.get("semantic_verifier_can_override_local_guard") is False,
        "numeric_cocompilation_zero_call_boundary_invalid",
    )
    _require(
        policy.get("semantic_metric_rules")
        and policy.get("table_row_rules")
        and policy.get("formula_specs"),
        "numeric_cocompilation_rule_set_missing",
    )
    serialized = json.dumps(policy, ensure_ascii=False)
    _require(
        not re.search(r"(?:DELL|NVDA|MU|ORCL|ASML|ANET):", serialized)
        and not re.search(r'"(?:exact_value|source_token|ticker)"\s*:', serialized),
        "numeric_cocompilation_case_specific_whitelist_detected",
    )
    return policy


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value or "unknown_metric"


def _decimal(value: Any) -> Decimal:
    raw = str(value or "").strip()
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("() ").replace(",", "").replace("$", "").replace("€", "")
    raw = re.sub(r"^(?:USD|EUR|US\$)\s*", "", raw, flags=re.IGNORECASE)
    raw = raw.rstrip("% ")
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise SelectedEvidenceNumericCocompilationError(
            "numeric_cocompilation_decimal_invalid"
        ) from exc
    return -number if negative and number > 0 else number


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def _currency(value: str) -> str:
    return "EUR" if value.upper() == "EUR" or value == "€" else "USD"


def _scale(value: str | None) -> str:
    token = str(value or "").lower()
    return {
        "b": "billion",
        "bn": "billion",
        "billion": "billion",
        "m": "million",
        "mn": "million",
        "million": "million",
        "k": "thousand",
        "thousand": "thousand",
    }.get(token, "unit")


def _scale_multiplier(scale: str) -> Decimal:
    return {
        "billion": Decimal("1000000000"),
        "million": Decimal("1000000"),
        "thousand": Decimal("1000"),
        "unit": Decimal("1"),
    }[scale]


def _period(evidence: Mapping[str, Any], context: str = "") -> str:
    fy = re.search(r"\bFY\s*(\d{2,4})\b", context, re.IGNORECASE)
    if fy and re.search(r"full[- ]year|guidance|outlook|expected", context, re.IGNORECASE):
        year = int(fy.group(1))
        return f"FY{year if year >= 100 else 2000 + year}"
    fiscal_quarter_context = re.search(
        r"(?:fiscal\s+)?Q(?P<q1>[1-4])[-\s]?(?P<y1>20\d{2})|"
        r"(?P<ordinal>first|second|third|fourth)\s+quarter\s+(?:of\s+)?"
        r"(?:fiscal\s+)?(?P<y2>20\d{2})",
        context,
        re.IGNORECASE,
    )
    if fiscal_quarter_context:
        quarter = fiscal_quarter_context.group("q1") or {
            "first": "1",
            "second": "2",
            "third": "3",
            "fourth": "4",
        }[str(fiscal_quarter_context.group("ordinal") or "").lower()]
        return f"FY{fiscal_quarter_context.group('y1') or fiscal_quarter_context.group('y2')}_Q{quarter}"
    target_id = str(evidence.get("target_id") or "")
    fiscal_quarter = re.search(
        r"(?:Q(?P<quarter>[1-4])FY(?P<year>\d{2,4})|"
        r"FY(?P<year_first>\d{2,4})[_-]?Q(?P<quarter_second>[1-4]))",
        target_id,
        re.IGNORECASE,
    )
    if fiscal_quarter:
        year_token = fiscal_quarter.group("year") or fiscal_quarter.group("year_first")
        quarter = fiscal_quarter.group("quarter") or fiscal_quarter.group("quarter_second")
        year = int(year_token)
        return f"FY{year if year >= 100 else 2000 + year}_Q{quarter}"
    for key in ("source_reporting_period_end", "publication_date", "research_as_of"):
        value = str(evidence.get(key) or "")
        if value:
            return value
    return "period_unknown"


def _evidence_indexes(
    pack: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    evidence = sorted(
        (deepcopy(dict(row)) for row in pack.get("evidence_items") or ()),
        key=lambda row: str(row.get("target_id") or ""),
    )
    _require(evidence, "numeric_cocompilation_selected_evidence_missing")
    by_material = {
        str(row.get("material_ref") or ""): deepcopy(dict(row))
        for row in pack.get("source_materials") or ()
    }
    aliases = {
        str(row.get("target_id") or ""): f"E{index:03d}"
        for index, row in enumerate(evidence, start=1)
    }
    _require(
        all(
            row.get("target_id")
            and row.get("writer_citable") is True
            and str(row.get("case_key") or "") == str(pack.get("case_key") or "")
            for row in evidence
        )
        and len(aliases) == len(evidence),
        "numeric_cocompilation_selected_evidence_identity_invalid",
    )
    return evidence, by_material, aliases


def _binding_values(evidence: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    slots: set[str] = set()
    facets: set[str] = set()
    for binding in evidence.get("slot_bindings") or ():
        if binding.get("slot_id"):
            slots.add(str(binding["slot_id"]))
        facets.update(str(value) for value in binding.get("facet_ids") or () if value)
    return sorted(slots), sorted(facets)


def _boundary_text(evidence: Mapping[str, Any]) -> str:
    boundaries = [
        str(evidence.get("numeric_use_boundary") or ""),
        *(str(row.get("claim_boundary_zh") or "") for row in evidence.get("slot_bindings") or ()),
    ]
    return " | ".join(value for value in boundaries if value)


def _source_scope(evidence: Mapping[str, Any]) -> str:
    return ":".join(
        (
            str(evidence.get("evidence_role") or "unknown_role"),
            str(evidence.get("disposition") or "unknown_disposition"),
        )
    )


def _candidate_body(
    *,
    case_key: str,
    evidence: Mapping[str, Any],
    evidence_alias: str,
    source_record_id: str,
    coordinate: str,
    source_surface: str,
    value_kind: str,
    parsed: Any,
    canonical_unit: str,
    currency: str,
    scale: str,
    entity: str,
    period: str,
    semantic_metric_key: str,
    status: str,
    decision_code: str,
    extractor_family: str,
    source_material_ref: str = "",
    source_start: int | None = None,
    source_end: int | None = None,
    context_excerpt: str = "",
    precision_rank: int = 0,
) -> dict[str, Any]:
    slots, facets = _binding_values(evidence)
    lineage = {
        "case_key": case_key,
        "evidence_target_id": str(evidence.get("target_id") or ""),
        "source_record_id": source_record_id,
        "coordinate": coordinate,
        "source_surface": source_surface,
        "value_kind": value_kind,
        "semantic_metric_key": semantic_metric_key,
    }
    body = {
        "candidate_id": "MNC:" + canonical_digest(lineage)[:24],
        "case_key": case_key,
        "evidence_target_id": lineage["evidence_target_id"],
        "evidence_alias": evidence_alias,
        "source_record_id": source_record_id,
        "source_coordinate_or_span": coordinate,
        "source_surface": source_surface,
        "value_kind": value_kind,
        "parsed_value_or_bounds": parsed,
        "canonical_unit": canonical_unit,
        "currency": currency,
        "scale": scale,
        "entity_or_evidence_owner": entity,
        "period_or_as_of": period,
        "slot_ids": slots,
        "facet_ids": facets,
        "relationship_directions": sorted(
            str(value) for value in evidence.get("relationship_directions") or ()
        ),
        "semantic_metric_key": semantic_metric_key,
        "claim_and_output_boundary": _boundary_text(evidence),
        "adjudication_status": status,
        "decision_code": decision_code,
        "extractor_family": extractor_family,
        "source_material_ref": source_material_ref,
        "source_start": source_start,
        "source_end": source_end,
        "context_excerpt": context_excerpt,
        "evidence_role": str(evidence.get("evidence_role") or ""),
        "authoritative_source_scope": _source_scope(evidence),
        "precision_rank": precision_rank,
    }
    _require(
        REQUIRED_CANDIDATE_FIELDS <= set(body)
        and body["adjudication_status"] in ALL_STATUSES,
        "numeric_cocompilation_candidate_shape_invalid",
    )
    return body


def _structured_candidate(
    *,
    case_key: str,
    evidence: Mapping[str, Any],
    evidence_alias: str,
) -> dict[str, Any]:
    metric = dict(evidence.get("structured_metric") or {})
    authority = dict(metric.get("currency_unit_authority") or {})
    table_path = metric.get("table_path")
    _require(
        metric
        and str(metric.get("raw_value") or "")
        and table_path
        and authority.get("status")
        in {"source_and_child_consistent", "non_monetary_dimension_preserved"},
        "numeric_cocompilation_structured_metric_authority_invalid",
    )
    unit = str(
        authority.get("canonical_unit")
        or metric.get("unit")
        or (metric.get("currency_unit_authority") or {}).get("unit")
        or ""
    )
    currency = str(authority.get("source_currency") or metric.get("currency") or "")
    lower_unit = unit.lower()
    if lower_unit == "percent":
        kind, canonical_unit, scale = "percentage_scalar", "percent", "unit"
    elif lower_unit == "count":
        kind, canonical_unit, scale = "count_scalar", "count", "unit"
        currency = ""
    elif "usd" in lower_unit or "eur" in lower_unit or currency:
        kind = "monetary_scalar"
        currency = currency or ("EUR" if "eur" in lower_unit else "USD")
        canonical_unit = currency
        scale = "million" if "million" in lower_unit else "unit"
    elif "ratio" in lower_unit or "multiple" in lower_unit:
        kind, canonical_unit, scale = "ratio_or_multiple", "ratio", "unit"
    else:
        kind, canonical_unit, scale = "count_scalar", unit or "count", "unit"
    raw_value = str(metric.get("normalized_value") or metric.get("raw_value") or "")
    value = _decimal(raw_value)
    parsed: dict[str, Any] = {"value": _decimal_text(value)}
    if kind == "monetary_scalar":
        parsed["base_value"] = _decimal_text(value * _scale_multiplier(scale))
    path = deepcopy(table_path)
    metric_name = str(metric.get("metric_name") or "")
    row_label = str(
        (path.get("row_label") if isinstance(path, Mapping) else "")
        or metric.get("row_label")
        or metric_name
        or ""
    )
    if "market_point_in_time" in _source_scope(evidence) and metric_name:
        row_label = metric_name
    period = str(
        (path.get("column_label") if isinstance(path, Mapping) else "")
        or metric.get("period")
        or _period(evidence)
    )
    coordinate = (
        json.dumps(path, ensure_ascii=False, sort_keys=True)
        if isinstance(path, Mapping)
        else str(path)
    )
    entity = str(
        evidence.get("evidence_owner_ticker")
        or evidence.get("case_key")
        or case_key
    )
    source_record_id = str(evidence.get("source_record_id") or "")
    return _candidate_body(
        case_key=case_key,
        evidence=evidence,
        evidence_alias=evidence_alias,
        source_record_id=source_record_id,
        coordinate=coordinate,
        source_surface=str(metric.get("raw_value") or raw_value),
        value_kind=kind,
        parsed=parsed,
        canonical_unit=canonical_unit,
        currency=currency,
        scale=scale,
        entity=entity,
        period=period,
        semantic_metric_key=_slug(row_label),
        status="authorized_fact",
        decision_code="structured_metric_direct_projection",
        extractor_family="structured_metric_direct_projection",
        source_material_ref=str(evidence.get("source_material_ref") or ""),
        precision_rank=6 if "market_point_in_time" in _source_scope(evidence) else 5,
    )


def _context_for(text: str, start: int, end: int, window: int) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def _semantic_span(
    context: str,
    candidate_center: int,
    *,
    delimiters: re.Pattern[str],
) -> tuple[str, int]:
    """Return the delimiter-bounded span containing one numeric surface.

    A broad evidence window is useful for discovery but is not sufficient authority
    for binding a number to a metric.  In particular, financial press releases often
    enumerate revenue, cash flow and shareholder returns in one sentence.  Treating
    the whole sentence as one metric span can bind a later cash-flow value to an
    earlier revenue label.  Non-numeric commas, sentence punctuation, semicolons and
    bullets therefore form deterministic micro-clause boundaries; commas and periods
    inside numeric tokens remain intact.
    """

    left = 0
    right = len(context)
    for delimiter in delimiters.finditer(context):
        if delimiter.end() <= candidate_center:
            left = delimiter.end()
        elif delimiter.start() >= candidate_center:
            right = delimiter.start()
            break
    clause = context[left:right]
    return clause, max(0, candidate_center - left)


def _semantic_clause(context: str, candidate_center: int) -> tuple[str, int]:
    return _semantic_span(
        context,
        candidate_center,
        delimiters=_SEMANTIC_CLAUSE_DELIMITER_RE,
    )


def _semantic_major_span(context: str, candidate_center: int) -> tuple[str, int]:
    return _semantic_span(
        context,
        candidate_center,
        delimiters=_SEMANTIC_MAJOR_DELIMITER_RE,
    )


def _candidate_matches_rule(
    raw: Mapping[str, Any],
    evidence: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> tuple[str, str, str]:
    boundary = str(evidence.get("numeric_use_boundary") or "").lower()
    if "cannot authorize" in boundary:
        return "context_only_do_not_output", "narrative_numeric_authority_denied", "unresolved_numeric_context"
    if raw.get("forced_forbidden"):
        return "forbidden_or_ambiguous", str(raw["forced_forbidden"]), "unresolved_numeric_context"
    _, facets = _binding_values(evidence)
    candidates: list[tuple[int, int, str]] = []
    context = str(raw.get("context") or "")
    surface = str(raw.get("surface") or "")
    surface_centers = [
        match.start() + (match.end() - match.start()) // 2
        for match in re.finditer(re.escape(surface), context, re.IGNORECASE)
    ]
    context_center = len(context) // 2
    candidate_center = (
        min(surface_centers, key=lambda value: abs(value - context_center))
        if surface_centers
        else context_center
    )
    local_context = context[
        max(0, candidate_center - 100) : min(len(context), candidate_center + 100)
    ]
    match_context, match_candidate_center = _semantic_clause(
        context,
        candidate_center,
    )
    major_context, major_candidate_center = _semantic_major_span(
        context,
        candidate_center,
    )
    candidate_is_guidance = bool(
        re.search(
            r"full[- ]year|guidance|outlook|expected|expectations?|midpoint",
            local_context,
            re.IGNORECASE,
        )
    )
    for rule in policy.get("semantic_metric_rules") or ():
        rule_key = str(rule["semantic_metric_key"])
        if candidate_is_guidance and raw.get("kind") in {
            "monetary_scalar",
            "numeric_range",
        } and "guidance" not in rule_key:
            continue
        required_scales = set(rule.get("required_scales") or ())
        if required_scales and str(raw.get("scale") or "") not in required_scales:
            continue
        if str(raw.get("kind") or "") not in set(rule.get("value_kinds") or ()):
            continue
        compatible = set(rule.get("compatible_facets") or ())
        if compatible and not (compatible & set(facets)):
            continue
        matches: list[tuple[int, int]] = []
        search_spans = [(match_context, match_candidate_center)]
        if rule.get("allow_cross_comma_context") is True:
            search_spans.append((major_context, major_candidate_center))
        for pattern in rule.get("context_patterns") or ():
            for search_context, search_center in search_spans:
                for match in re.finditer(str(pattern), search_context, re.IGNORECASE):
                    match_center = match.start() + (match.end() - match.start()) // 2
                    if "\\d" in str(pattern) and not (
                        match.start() <= search_center <= match.end()
                    ):
                        continue
                    distance = (
                        0
                        if match.start() <= search_center <= match.end()
                        else abs(match_center - search_center)
                    )
                    matches.append(
                        (distance, len(str(pattern)))
                    )
        if matches:
            distance, pattern_length = min(matches)
            if distance <= int(rule.get("max_proximity_chars") or 55):
                score = int(rule.get("proximity_priority") or 0) - distance
                candidates.append(
                    (score, pattern_length, rule_key)
                )
    if not candidates:
        direct_facet_metrics = {
            "capacity_release_timing": "capacity_release_timing",
            "supply_tightness_horizon": "supply_tightness_horizon",
            "ai_server_profitability_target": "operating_margin_target",
            "ai_system_margin": "operating_margin_target",
        }
        for facet, semantic_key in direct_facet_metrics.items():
            if facet in facets and (
                raw.get("kind") in {"temporal_range_or_boundary", "qualitative_numeric_band"}
            ):
                return (
                    "authorized_fact",
                    "typed_surface_bound_by_selected_evidence_facet",
                    semantic_key,
                )
        return "context_only_do_not_output", "no_target_compatible_semantic_metric", "unresolved_numeric_context"
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
    semantic_key = candidates[0][2]
    if raw.get("kind") == "numeric_range":
        semantic_key += "_range"
    elif re.search(r"\bmidpoint\b", match_context, re.IGNORECASE):
        semantic_key += "_midpoint"
    semantic_key = _semantic_context_modifier(
        semantic_key,
        context=major_context,
        candidate_center=major_candidate_center,
    )
    return "authorized_fact", "target_compatible_semantic_metric_bound", semantic_key


def _semantic_context_modifier(
    semantic_key: str,
    *,
    context: str,
    candidate_center: int,
) -> str:
    def nearest_label(patterns: Mapping[str, str]) -> str:
        hits: list[tuple[int, str]] = []
        for label, pattern in patterns.items():
            for match in re.finditer(pattern, context, re.IGNORECASE):
                center = match.start() + (match.end() - match.start()) // 2
                hits.append((abs(center - candidate_center), label))
        return min(hits)[1] if hits else ""

    if semantic_key in {
        "average_selling_price_change",
        "bit_shipment_change",
        "product_revenue_growth",
    }:
        product = nearest_label({"dram": r"\bDRAM\b", "nand": r"\bNAND\b"})
        if product:
            return product + "_" + semantic_key
    if semantic_key == "gross_margin":
        local_prefix = context[max(0, candidate_center - 120) : candidate_center]
        if re.search(
            r"gross margin[^.;]{0,90}(?:increased|decreased)\s+(?!to\b)",
            local_prefix,
            re.IGNORECASE,
        ):
            return "gross_margin_change"
        scope = nearest_label(
            {
                "services": r"services gross margin",
                "product": r"product gross margin",
                "isg": r"ISG gross margin",
                "csg": r"CSG gross margin",
                "consolidated": r"consolidated gross margin",
            }
        )
        if scope:
            return scope + "_gross_margin"
    if semantic_key == "reported_revenue":
        scope = nearest_label(
            {
                "data_center_compute": r"Data Center compute revenue",
                "data_center_networking": r"(?:Data Center )?networking revenue",
                "data_center": r"Data Center revenue",
                "gaming": r"Gaming revenue",
                "automotive": r"Automotive revenue",
                "total": r"(?:record|total) revenue",
            }
        )
        if scope:
            return scope + "_revenue"
    return semantic_key


def _relative_candidate_period(
    evidence: Mapping[str, Any],
    raw: Mapping[str, Any],
    *,
    default_period: str = "",
) -> str:
    context = str(raw.get("context") or "")
    surface = str(raw.get("surface") or "")
    centers = [
        match.start() + (match.end() - match.start()) // 2
        for match in re.finditer(re.escape(surface), context, re.IGNORECASE)
    ]
    center = min(centers, key=lambda value: abs(value - len(context) // 2)) if centers else len(context) // 2
    surface_end = center + len(surface) // 2
    after_full = context[surface_end : min(len(context), surface_end + 130)]
    next_numeric = _MONEY_RE.search(after_full)
    association_after = (
        after_full[: next_numeric.start()] if next_numeric is not None else after_full
    )
    base = _period(evidence, context)
    if not (base.startswith("FY") or base.startswith("9M")) and default_period:
        base = default_period
    explicit_quarter = re.search(
        r"for\s+(?:the\s+)?(?P<quarter>first|second|third|fourth)\s+"
        r"quarter\s+of\s+(?P<year>20\d{2})",
        association_after,
        re.IGNORECASE,
    )
    if explicit_quarter:
        quarter_number = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
        }[explicit_quarter.group("quarter").lower()]
        return f"FY{explicit_quarter.group('year')}_Q{quarter_number}"
    explicit_nine_months = re.search(
        r"for\s+(?:the\s+)?first\s+nine\s+months\s+of\s+(?P<year>20\d{2})",
        association_after,
        re.IGNORECASE,
    )
    if explicit_nine_months:
        return f"9M{explicit_nine_months.group('year')}"
    fiscal = re.fullmatch(r"FY(?P<year>20\d{2})_Q(?P<quarter>[1-4])", base)
    if fiscal and re.search(r"prior quarter", association_after, re.IGNORECASE):
        year, quarter = int(fiscal.group("year")), int(fiscal.group("quarter"))
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4
        return f"FY{year}_Q{quarter}"
    if fiscal and re.search(r"same period last year|year-ago", association_after, re.IGNORECASE):
        return f"FY{int(fiscal.group('year')) - 1}_Q{fiscal.group('quarter')}"
    nine_month_years = [
        int(match.group(1))
        for match in re.finditer(
            r"(?:first )?nine months (?:of|ended)?\s*(20\d{2})",
            context,
            re.IGNORECASE,
        )
    ]
    if nine_month_years:
        return f"9M{max(nine_month_years)}"
    return base


def _raw_candidate(
    *,
    text: str,
    match: re.Match[str],
    kind: str,
    parsed: Any,
    canonical_unit: str,
    currency: str,
    scale: str,
    window: int,
    extractor_family: str,
    forced_forbidden: str = "",
) -> dict[str, Any]:
    return {
        "start": match.start(),
        "end": match.end(),
        "surface": match.group(0),
        "kind": kind,
        "parsed": parsed,
        "canonical_unit": canonical_unit,
        "currency": currency,
        "scale": scale,
        "context": _context_for(text, match.start(), match.end(), window),
        "extractor_family": extractor_family,
        "forced_forbidden": forced_forbidden,
    }


def _overlaps(span: tuple[int, int], rows: Iterable[Mapping[str, Any]]) -> bool:
    return any(span[0] < int(row["end"]) and int(row["start"]) < span[1] for row in rows)


def _discover_raw_text_candidates(
    text: str,
    *,
    window: int,
) -> list[dict[str, Any]]:
    working = list(text)
    for table in _TABLE_RE.finditer(text):
        working[table.start() : table.end()] = " " * (table.end() - table.start())
    narrative = "".join(working)
    rows: list[dict[str, Any]] = []
    for match in _MONEY_RANGE_RE.finditer(narrative):
        currency = _currency(match.group("currency"))
        scale = _scale(match.group("scale2") or match.group("scale1"))
        low, high = _decimal(match.group("low")), _decimal(match.group("high"))
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="numeric_range",
            parsed={
                "lower": _decimal_text(low),
                "upper": _decimal_text(high),
                "lower_base_value": _decimal_text(low * _scale_multiplier(scale)),
                "upper_base_value": _decimal_text(high * _scale_multiplier(scale)),
            },
            canonical_unit=currency,
            currency=currency,
            scale=scale,
            window=window,
            extractor_family="bounded_narrative_numeric_range",
        ))
    for match in _PERCENT_RANGE_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="numeric_range",
            parsed={"lower": _decimal_text(_decimal(match.group("low"))), "upper": _decimal_text(_decimal(match.group("high")))},
            canonical_unit="percent",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_percentage_range",
        ))
    for match in _MONEY_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        currency = _currency(match.group("currency"))
        scale = _scale(match.group("scale"))
        value = _decimal(match.group("number"))
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="monetary_scalar",
            parsed={"value": _decimal_text(value), "base_value": _decimal_text(value * _scale_multiplier(scale))},
            canonical_unit=currency,
            currency=currency,
            scale=scale,
            window=window,
            extractor_family="bounded_narrative_monetary_surface",
        ))
    for match in _QUALITATIVE_PERCENT_RANGE_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="qualitative_numeric_band",
            parsed={
                "band": str(match.group("band")).lower(),
                "anchor_percent": _decimal_text(_decimal(match.group("anchor"))),
            },
            canonical_unit="qualitative_percent_band",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_qualitative_percent_range",
        ))
    for match in _PERCENT_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="percentage_scalar",
            parsed={"value": _decimal_text(_decimal(match.group("number")))},
            canonical_unit="percent",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_percentage_surface",
        ))
    for pattern in (_COUNT_AFTER_RE, _COUNT_BEFORE_RE):
        for match in pattern.finditer(narrative):
            if _overlaps((match.start(), match.end()), rows):
                continue
            value = _decimal(match.group("number"))
            rows.append(_raw_candidate(
                text=text,
                match=match,
                kind="count_scalar",
                parsed={
                    "value": _decimal_text(value),
                    "qualifier": str(match.groupdict().get("qualifier") or "exact").lower(),
                    "count_noun": str(match.groupdict().get("noun") or "count").lower(),
                },
                canonical_unit="count",
                currency="",
                scale="unit",
                window=window,
                extractor_family="bounded_narrative_count_surface",
            ))
    for match in _MULTIPLE_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="ratio_or_multiple",
            parsed={"value": _decimal_text(_decimal(match.group("number")))},
            canonical_unit="multiple",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_multiple_surface",
        ))
    for match in _TEMPORAL_RE.finditer(narrative):
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="temporal_range_or_boundary",
            parsed={
                "half": str(match.groupdict().get("half") or ""),
                "boundary": str(match.groupdict().get("boundary") or ""),
                "year": str(match.groupdict().get("year1") or match.groupdict().get("year2") or ""),
            },
            canonical_unit="calendar_period",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_temporal_surface",
        ))
    for match in _QUALITATIVE_BAND_RE.finditer(narrative):
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="qualitative_numeric_band",
            parsed={"band": str(match.group("band")).lower(), "digits": str(match.group("digits")).lower()},
            canonical_unit="qualitative_band",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_qualitative_band",
        ))
    for match in _TECHNICAL_OR_PRODUCT_TOKEN_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        numeric = _FALLBACK_NUMBER_RE.search(match.group(0))
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="count_scalar",
            parsed={
                "value": (
                    _decimal_text(_decimal(numeric.group(0)))
                    if numeric is not None
                    else "0"
                )
            },
            canonical_unit="unresolved_numeric",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_technical_or_product_token",
            forced_forbidden="product_or_technical_identifier_not_financial_fact",
        ))
    for match in _FALLBACK_NUMBER_RE.finditer(narrative):
        if _overlaps((match.start(), match.end()), rows):
            continue
        before = narrative[max(0, match.start() - 12) : match.start()]
        after = narrative[match.end() : min(len(narrative), match.end() + 8)]
        around = narrative[max(0, match.start() - 16) : min(len(narrative), match.end() + 16)]
        forbidden = ""
        if _ISO_DATE_RE.search(around):
            forbidden = "date_token_not_financial_fact"
        elif _FISCAL_LABEL_RE.search(around):
            forbidden = "fiscal_label_not_scalar_fact"
        elif re.search(r"(?:Rule|Form|Item)\s*$", before, re.IGNORECASE):
            forbidden = "filing_or_rule_identifier_not_financial_fact"
        elif re.match(r"(?:GB|TB|nm|D)\b", after, re.IGNORECASE):
            forbidden = "product_or_technical_identifier_not_financial_fact"
        rows.append(_raw_candidate(
            text=text,
            match=match,
            kind="count_scalar",
            parsed={"value": _decimal_text(_decimal(match.group(0)))},
            canonical_unit="unresolved_numeric",
            currency="",
            scale="unit",
            window=window,
            extractor_family="bounded_narrative_unresolved_numeric_surface",
            forced_forbidden=forbidden,
        ))
    rows.sort(key=lambda row: (int(row["start"]), int(row["end"]), str(row["extractor_family"])))
    return rows


def _table_candidates(
    *,
    case_key: str,
    evidence: Mapping[str, Any],
    evidence_alias: str,
    material: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    text = str(material.get("source_text") or "")
    _, facets = _binding_values(evidence)
    output: list[dict[str, Any]] = []
    for table in _TABLE_RE.finditer(text):
        body = table.group("body")
        lines = body.splitlines()
        header_lines: list[str] = []
        matched_in_table = False
        for line_index, line in enumerate(lines):
            if "|" not in line:
                if line.strip():
                    header_lines.append(line.strip())
                continue
            row_label = line.split("|", 1)[0].strip()
            selected_rule: Mapping[str, Any] | None = None
            for rule in policy.get("table_row_rules") or ():
                if not set(rule.get("compatible_facets") or ()) & set(facets):
                    continue
                if any(re.search(str(pattern), row_label, re.IGNORECASE) for pattern in rule.get("row_patterns") or ()):
                    selected_rule = rule
                    break
            if selected_rule is None:
                if not matched_in_table:
                    header_lines.append(line.strip())
                continue
            matched_in_table = True
            cells = [cell.strip() for cell in line.split("|")[1:]]
            numeric_cell = ""
            for cell in cells:
                stripped_cell = re.sub(
                    r"^(?:US\$|USD|EUR|\$|€)\s*",
                    "",
                    cell,
                    flags=re.IGNORECASE,
                )
                if re.fullmatch(_NUMBER, stripped_cell):
                    numeric_cell = stripped_cell
                    break
            _require(numeric_cell, "numeric_cocompilation_table_selected_row_value_missing")
            value = _decimal(numeric_cell)
            header = " ".join(header_lines[-5:])
            table_context = text[max(0, table.start() - 180) : table.end()]
            is_percent = bool(re.search(r"margin|%", row_label, re.IGNORECASE)) and (
                "%" in line or "percentage" in header.lower()
            )
            is_count = bool(re.search(r"\b(?:units?|systems?|customers?)\b", row_label, re.IGNORECASE))
            has_eur = "€" in table_context or "euros" in table_context.lower()
            has_currency = "$" in table_context or has_eur
            in_millions = bool(re.search(r"in millions|millions of", table_context, re.IGNORECASE))
            if is_percent:
                kind, unit, currency, scale = "percentage_scalar", "percent", "", "unit"
                parsed = {"value": _decimal_text(value)}
            elif is_count:
                kind, unit, currency, scale = "count_scalar", "count", "", "unit"
                parsed = {"value": _decimal_text(value)}
            elif has_currency:
                kind = "monetary_scalar"
                currency = "EUR" if has_eur else "USD"
                unit = currency
                scale = "million" if in_millions else "unit"
                parsed = {
                    "value": _decimal_text(value),
                    "base_value": _decimal_text(value * _scale_multiplier(scale)),
                }
            else:
                kind, unit, currency, scale = "count_scalar", "unresolved_numeric", "", "unit"
                parsed = {"value": _decimal_text(value)}
            relative_line_start = body.find(line)
            token_in_line = line.find(numeric_cell)
            start = table.start("body") + relative_line_start + token_in_line
            end = start + len(numeric_cell)
            period = _period(evidence)
            if not period.startswith("FY"):
                for header_line in reversed(header_lines):
                    date = re.search(r"(?:Q[1-4]\s+20\d{2}|[A-Z][a-z]+\s+\d{1,2},\s+20\d{2}|20\d{2})", header_line)
                    if date:
                        surface = date.group(0)
                        try:
                            period = datetime.strptime(surface, "%B %d, %Y").date().isoformat()
                        except ValueError:
                            period = surface
                        break
            semantic_metric_key = str(selected_rule["semantic_metric_key"])
            preceding_table_text = body[:relative_line_start]
            if semantic_metric_key in {
                "accounts_receivable",
                "inventory",
                "accounts_payable",
            } and re.search(
                r"cash flows? from operating activities|cash flow statement",
                preceding_table_text,
                re.IGNORECASE,
            ):
                semantic_metric_key = "change_in_" + semantic_metric_key
            if re.search(r"\bNon-GAAP\b", preceding_table_text, re.IGNORECASE):
                if semantic_metric_key in {
                    "net_income",
                    "gross_margin",
                    "gross_profit",
                    "operating_cash_flow",
                }:
                    semantic_metric_key = "non_gaap_" + semantic_metric_key
            coordinate = (
                f"table:{table.group('table_id')}:line:{line_index}:"
                f"row:{_slug(row_label)}:period:{period}:char:{start}:{end}"
            )
            output.append(_candidate_body(
                case_key=case_key,
                evidence=evidence,
                evidence_alias=evidence_alias,
                source_record_id=str(evidence.get("source_record_id") or material.get("source_record_id") or ""),
                coordinate=coordinate,
                source_surface=numeric_cell,
                value_kind=kind,
                parsed=parsed,
                canonical_unit=unit,
                currency=currency,
                scale=scale,
                entity=str(material.get("evidence_owner_ticker") or case_key),
                period=period,
                semantic_metric_key=semantic_metric_key,
                status=("authorized_fact" if unit != "unresolved_numeric" else "forbidden_or_ambiguous"),
                decision_code=("selected_table_row_parent_authority_bound" if unit != "unresolved_numeric" else "table_parent_unit_unresolved"),
                extractor_family="table_cell_with_parent_currency_unit_and_period",
                source_material_ref=str(evidence.get("source_material_ref") or ""),
                source_start=start,
                source_end=end,
                context_excerpt=re.sub(r"\s+", " ", line).strip(),
                precision_rank=4,
            ))
    return output


def _narrative_candidates(
    *,
    case_key: str,
    evidence: Mapping[str, Any],
    evidence_alias: str,
    material: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    text = str(material.get("source_text") or "")
    window = int((policy.get("candidate_limits") or {}).get("context_window_chars") or 220)
    raw_rows = _discover_raw_text_candidates(text, window=window)
    default_period = (
        _period(evidence, text[:1200])
        if str(material.get("evidence_owner_ticker") or case_key) == case_key
        else ""
    )
    unstructured_dense_table = (
        len(_FALLBACK_NUMBER_RE.findall(text)) >= 24
        and bool(
            re.search(
                r"Total assets.{0,300}Liabilities and equity|"
                r"Cash flows? from operating activities.{0,500}(?:Accounts receivable|Inventor(?:y|ies)|Accounts payable)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
        )
        and "[TABLE_START" not in text
    )
    output: list[dict[str, Any]] = []
    for raw in raw_rows:
        if unstructured_dense_table:
            raw = {
                **raw,
                "forced_forbidden": "unstructured_table_missing_row_column_unit_or_period_coordinate",
            }
        status, decision, semantic_key = _candidate_matches_rule(raw, evidence, policy)
        candidate_period = _relative_candidate_period(
            evidence,
            raw,
            default_period=default_period,
        )
        if raw["kind"] == "temporal_range_or_boundary":
            parsed = dict(raw["parsed"])
            candidate_period = ":".join(
                value
                for value in (
                    str(parsed.get("boundary") or parsed.get("half") or "temporal"),
                    str(parsed.get("year") or "unknown_year"),
                )
                if value
            )
        output.append(_candidate_body(
            case_key=case_key,
            evidence=evidence,
            evidence_alias=evidence_alias,
            source_record_id=str(evidence.get("source_record_id") or material.get("source_record_id") or ""),
            coordinate=f"char:{raw['start']}:{raw['end']}",
            source_surface=str(raw["surface"]),
            value_kind=str(raw["kind"]),
            parsed=deepcopy(raw["parsed"]),
            canonical_unit=str(raw["canonical_unit"]),
            currency=str(raw["currency"]),
            scale=str(raw["scale"]),
            entity=str(material.get("evidence_owner_ticker") or case_key),
            period=candidate_period,
            semantic_metric_key=semantic_key,
            status=status,
            decision_code=decision,
            extractor_family=str(raw["extractor_family"]),
            source_material_ref=str(evidence.get("source_material_ref") or ""),
            source_start=int(raw["start"]),
            source_end=int(raw["end"]),
            context_excerpt=str(raw["context"]),
            precision_rank=2,
        ))
    return output


def _downgrade_ambiguous_candidate_groups(
    candidates: list[dict[str, Any]],
) -> int:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in candidates:
        if row.get("adjudication_status") not in AUTHORIZED_STATUSES:
            continue
        key = (
            str(row.get("case_key") or ""),
            str(row.get("entity_or_evidence_owner") or ""),
            str(row.get("semantic_metric_key") or ""),
            str(row.get("period_or_as_of") or ""),
            str(row.get("canonical_unit") or ""),
            str(row.get("authoritative_source_scope") or ""),
        )
        groups.setdefault(key, []).append(row)
    downgraded = 0
    for rows in groups.values():
        if len(rows) < 2:
            continue
        scalar_values: list[Decimal] = []
        non_scalar_values: set[str] = set()
        for row in rows:
            parsed = row.get("parsed_value_or_bounds")
            if isinstance(parsed, Mapping) and parsed.get("base_value") not in (None, ""):
                scalar_values.append(_decimal(parsed["base_value"]))
            elif isinstance(parsed, Mapping) and parsed.get("value") not in (None, ""):
                scalar_values.append(_decimal(parsed["value"]))
            else:
                non_scalar_values.add(canonical_digest(parsed))
        conflict = len(non_scalar_values) > 1 or (
            scalar_values
            and any(
                abs(value - scalar_values[0])
                / max(abs(scalar_values[0]), Decimal("1"))
                > Decimal("0.005")
                for value in scalar_values[1:]
            )
        )
        if not conflict:
            continue
        for row in rows:
            row["adjudication_status"] = "context_only_do_not_output"
            row["decision_code"] = (
                "same_identity_non_equivalent_surface_downgraded_fail_closed"
            )
            downgraded += 1
    return downgraded


def compile_material_numeric_candidate_inventory(
    *,
    pack: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    case_key = str(pack.get("case_key") or "")
    _require(case_key, "numeric_cocompilation_case_key_missing")
    evidence, materials, aliases = _evidence_indexes(pack)
    candidates: list[dict[str, Any]] = []
    truncated_candidate_count = 0
    for row in evidence:
        alias = aliases[str(row["target_id"])]
        if row.get("structured_metric"):
            candidates.append(
                _structured_candidate(
                    case_key=case_key,
                    evidence=row,
                    evidence_alias=alias,
                )
            )
            continue
        material_ref = str(row.get("source_material_ref") or "")
        material = materials.get(material_ref)
        if material is None and row.get("object_type") == "claim" and (
            "cannot authorize" in str(row.get("numeric_use_boundary") or "").lower()
        ):
            continue
        _require(material is not None, "numeric_cocompilation_selected_source_material_missing")
        table_rows = _table_candidates(
            case_key=case_key,
            evidence=row,
            evidence_alias=alias,
            material=material,
            policy=policy,
        )
        narrative_rows = _narrative_candidates(
            case_key=case_key,
            evidence=row,
            evidence_alias=alias,
            material=material,
            policy=policy,
        )
        limit = int((policy.get("candidate_limits") or {}).get("max_candidates_per_evidence") or 64)
        combined = sorted(
            (*table_rows, *narrative_rows),
            key=lambda item: (
                0 if item["adjudication_status"] in AUTHORIZED_STATUSES else 1,
                0 if item["extractor_family"] != "bounded_narrative_unresolved_numeric_surface" else 1,
                str(item["source_coordinate_or_span"]),
                str(item["candidate_id"]),
            ),
        )
        _require(
            sum(row["adjudication_status"] in AUTHORIZED_STATUSES for row in combined)
            <= limit,
            "numeric_cocompilation_authorized_candidate_budget_exceeded",
        )
        truncated_candidate_count += max(0, len(combined) - limit)
        combined = combined[:limit]
        candidates.extend(combined)
    candidates.sort(
        key=lambda item: (
            str(item["evidence_target_id"]),
            int(item.get("source_start") or -1),
            str(item["source_coordinate_or_span"]),
            str(item["candidate_id"]),
        )
    )
    _require(
        len({row["candidate_id"] for row in candidates}) == len(candidates),
        "numeric_cocompilation_candidate_identity_collision",
    )
    ambiguity_downgraded_count = _downgrade_ambiguous_candidate_groups(candidates)
    body = {
        "schema_version": INVENTORY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": case_key,
        "selected_evidence_digest": canonical_digest(evidence),
        "source_material_digest_set": sorted(
            str(row.get("source_text_digest") or "") for row in materials.values()
        ),
        "evidence_aliases": aliases,
        "candidates": candidates,
        "summary": {
            "candidate_count": len(candidates),
            "authorized_count": sum(
                row["adjudication_status"] in AUTHORIZED_STATUSES for row in candidates
            ),
            "context_only_count": sum(
                row["adjudication_status"] == "context_only_do_not_output" for row in candidates
            ),
            "forbidden_count": sum(
                row["adjudication_status"] == "forbidden_or_ambiguous" for row in candidates
            ),
            "truncated_unresolved_candidate_count": truncated_candidate_count,
            "ambiguity_downgraded_count": ambiguity_downgraded_count,
            "value_kind_counts": {
                kind: sum(row["value_kind"] == kind for row in candidates)
                for kind in sorted({str(row["value_kind"]) for row in candidates})
            },
        },
    }
    return {**body, "inventory_digest": canonical_digest(body)}


def _base_value(candidate: Mapping[str, Any]) -> Decimal | None:
    parsed = candidate.get("parsed_value_or_bounds")
    if not isinstance(parsed, Mapping):
        return None
    if parsed.get("base_value") not in (None, ""):
        return _decimal(parsed["base_value"])
    if candidate.get("value_kind") in {
        "percentage_scalar",
        "count_scalar",
        "ratio_or_multiple",
    } and parsed.get("value") not in (None, ""):
        return _decimal(parsed["value"])
    return None


def _stable_fact_seed(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_key": str(candidate["case_key"]),
        "entity": str(candidate["entity_or_evidence_owner"]),
        "semantic_metric_key": str(candidate["semantic_metric_key"]),
        "period_or_as_of": str(candidate["period_or_as_of"]),
        "canonical_unit": str(candidate["canonical_unit"]),
        "authoritative_source_scope": str(candidate["authoritative_source_scope"]),
    }


def _presentation_receipt(
    *,
    numeric_ref: str,
    candidate: Mapping[str, Any],
    authoritative: Mapping[str, Any],
) -> dict[str, Any]:
    value = _base_value(candidate)
    authoritative_value = _base_value(authoritative)
    relation = "non_scalar_source_surface"
    if value is not None and authoritative_value is not None:
        if value == authoritative_value:
            relation = "exact_equivalent"
        else:
            denominator = max(abs(authoritative_value), Decimal("1"))
            delta = abs(value - authoritative_value) / denominator
            relation = (
                "official_rounded_equivalent"
                if delta <= Decimal("0.005")
                else "non_equivalent_conflicting_surface"
            )
    seed = {
        "numeric_ref": numeric_ref,
        "candidate_id": str(candidate["candidate_id"]),
        "source_surface": str(candidate["source_surface"]),
        "relation": relation,
    }
    return {
        "presentation_ref": "PRES:" + canonical_digest(seed)[:24],
        "numeric_ref": numeric_ref,
        "candidate_id": str(candidate["candidate_id"]),
        "source_surface": str(candidate["source_surface"]),
        "rendered": str(candidate["source_surface"]),
        "equivalence_relation": relation,
        "source_coordinate_or_span": str(candidate["source_coordinate_or_span"]),
        "evidence_alias": str(candidate["evidence_alias"]),
        "source_record_id": str(candidate["source_record_id"]),
        "candidate_value": None if value is None else _decimal_text(value),
        "authoritative_value": (
            None if authoritative_value is None else _decimal_text(authoritative_value)
        ),
    }


def compile_stable_fact_presentation_program(
    *,
    inventory: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for source in inventory.get("candidates") or ():
        row = deepcopy(dict(source))
        if row.get("adjudication_status") not in AUTHORIZED_STATUSES:
            continue
        seed = _stable_fact_seed(row)
        fact_id = "NF:" + canonical_digest(seed)[:24]
        groups.setdefault(fact_id, []).append(row)
    facts: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    candidate_to_ref: dict[str, str] = {}
    for fact_id, rows in sorted(groups.items()):
        rows.sort(
            key=lambda row: (
                -int(row.get("precision_rank") or 0),
                str(row["candidate_id"]),
            )
        )
        authoritative = rows[0]
        seed = _stable_fact_seed(authoritative)
        numeric_ref = (
            "NUM:"
            + _slug(str(seed["case_key"])).upper()
            + ":"
            + _slug(str(seed["semantic_metric_key"])).upper()
            + ":"
            + canonical_digest(seed)[:12].upper()
        )
        receipts = [
            _presentation_receipt(
                numeric_ref=numeric_ref,
                candidate=row,
                authoritative=authoritative,
            )
            for row in rows
        ]
        bad = [
            row for row in receipts
            if row["equivalence_relation"] == "non_equivalent_conflicting_surface"
        ]
        if bad:
            conflicts.append(
                {
                    "stable_fact_id": fact_id,
                    "semantic_metric_key": seed["semantic_metric_key"],
                    "candidate_ids": [str(row["candidate_id"]) for row in rows],
                    "decision_code": "same_identity_non_equivalent_numeric_surface",
                }
            )
            continue
        for row in rows:
            candidate_to_ref[str(row["candidate_id"])] = numeric_ref
        facts.append(
            {
                "stable_fact_id": fact_id,
                "numeric_ref": numeric_ref,
                **seed,
                "value_kind": str(authoritative["value_kind"]),
                "authoritative_candidate_id": str(authoritative["candidate_id"]),
                "authoritative_value": deepcopy(
                    authoritative["parsed_value_or_bounds"]
                ),
                "currency": str(authoritative["currency"]),
                "scale": str(authoritative["scale"]),
                "claim_and_output_boundary": str(
                    authoritative["claim_and_output_boundary"]
                ),
                "evidence_aliases": sorted(
                    {str(row["evidence_alias"]) for row in rows}
                ),
                "source_record_ids": sorted(
                    {str(row["source_record_id"]) for row in rows}
                ),
                "candidate_ids": [str(row["candidate_id"]) for row in rows],
                "presentation_receipts": receipts,
            }
        )
    formula_traces: list[dict[str, Any]] = []
    fact_by_metric: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        fact_by_metric.setdefault(str(fact["semantic_metric_key"]), []).append(fact)
    for spec in policy.get("formula_specs") or ():
        numerator_rows = fact_by_metric.get(str(spec.get("numerator") or ""), [])
        denominator_rows = fact_by_metric.get(str(spec.get("denominator") or ""), [])
        for numerator in numerator_rows:
            denominator = next(
                (
                    row
                    for row in denominator_rows
                    if row["case_key"] == numerator["case_key"]
                    and row["entity"] == numerator["entity"]
                    and row["period_or_as_of"] == numerator["period_or_as_of"]
                    and row["canonical_unit"] == numerator["canonical_unit"]
                    and row["authoritative_source_scope"]
                    == numerator["authoritative_source_scope"]
                ),
                None,
            )
            if denominator is None:
                continue
            left = _decimal(numerator["authoritative_value"]["base_value"])
            right = _decimal(denominator["authoritative_value"]["base_value"])
            if right == 0:
                continue
            output = (left / right * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            formula_seed = {
                "case_key": numerator["case_key"],
                "entity": numerator["entity"],
                "period": numerator["period_or_as_of"],
                "semantic_metric_key": str(spec["semantic_metric_key"]),
                "input_numeric_refs": [
                    numerator["numeric_ref"],
                    denominator["numeric_ref"],
                ],
            }
            formula_ref = "FORM:" + canonical_digest(formula_seed)[:24].upper()
            formula_traces.append(
                {
                    "formula_ref": formula_ref,
                    **formula_seed,
                    "operation": "ratio_percent",
                    "output_value": _decimal_text(output),
                    "output_unit": "percent",
                    "rendered": _decimal_text(output) + "%",
                    "lineage_complete": True,
                }
            )
    facts.sort(key=lambda row: str(row["numeric_ref"]))
    formula_traces.sort(key=lambda row: str(row["formula_ref"]))
    body = {
        "schema_version": PRESENTATION_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": str(inventory.get("case_key") or ""),
        "inventory_digest": str(inventory.get("inventory_digest") or ""),
        "stable_numeric_facts": facts,
        "formula_traces": formula_traces,
        "candidate_to_numeric_ref": candidate_to_ref,
        "conflicts": conflicts,
        "rules": {
            "source_presence_bypasses_authority": False,
            "deterministic_rendering_only": True,
            "free_arithmetic": "forbidden_fail_closed",
            "market_pit_authorizes_valuation_or_recommendation": False,
        },
        "summary": {
            "stable_fact_count": len(facts),
            "presentation_receipt_count": sum(
                len(row["presentation_receipts"]) for row in facts
            ),
            "formula_trace_count": len(formula_traces),
            "conflict_count": len(conflicts),
        },
    }
    return {**body, "presentation_program_digest": canonical_digest(body)}


def _mask_numeric_text(
    text: str,
    *,
    candidates: Sequence[Mapping[str, Any]],
    candidate_to_ref: Mapping[str, str],
    absolute_start: int,
) -> str:
    local = text
    replacements: list[tuple[int, int, str]] = []
    for row in candidates:
        start = row.get("source_start")
        end = row.get("source_end")
        if start is None or end is None:
            continue
        relative_start = int(start) - absolute_start
        relative_end = int(end) - absolute_start
        if relative_start < 0 or relative_end > len(local):
            continue
        status = str(row["adjudication_status"])
        if status in AUTHORIZED_STATUSES and row["candidate_id"] in candidate_to_ref:
            replacement = f"[NUM_REF:{candidate_to_ref[row['candidate_id']]}]"
        elif status == "context_only_do_not_output":
            replacement = "[CONTEXT_ONLY_NUMERIC_DO_NOT_OUTPUT]"
        else:
            replacement = "[MASKED_NUMERIC]"
        replacements.append((relative_start, relative_end, replacement))
    for start, end, replacement in sorted(replacements, reverse=True):
        local = local[:start] + replacement + local[end:]
    local = _FALLBACK_NUMBER_RE.sub("[MASKED_NUMERIC]", local)
    return re.sub(r"\s+", " ", local).strip()


def _bounded_evidence_contexts(
    *,
    evidence: Mapping[str, Any],
    material: Mapping[str, Any] | None,
    candidates: Sequence[Mapping[str, Any]],
    candidate_to_ref: Mapping[str, str],
    max_chars: int,
) -> list[str]:
    if material is None:
        return []
    text = str(material.get("source_text") or "")
    if not text:
        return []
    windows: list[tuple[int, int]] = [(0, min(len(text), min(max_chars, 900)))]
    for row in candidates:
        if row.get("adjudication_status") not in AUTHORIZED_STATUSES:
            continue
        start = int(row.get("source_start") or 0)
        end = int(row.get("source_end") or start)
        windows.append((max(0, start - 260), min(len(text), end + 360)))
    merged: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1] + 80:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    contexts: list[str] = []
    remaining = max_chars
    for start, end in merged:
        if remaining <= 0:
            break
        end = min(end, start + remaining)
        snippet = _mask_numeric_text(
            text[start:end],
            candidates=candidates,
            candidate_to_ref=candidate_to_ref,
            absolute_start=start,
        )
        if snippet and snippet not in contexts:
            contexts.append(snippet)
            remaining -= len(snippet)
    return contexts


def compile_bounded_numeric_node_views(
    *,
    pack: Mapping[str, Any],
    inventory: Mapping[str, Any],
    presentation_program: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    evidence, materials, aliases = _evidence_indexes(pack)
    candidate_to_ref = dict(presentation_program.get("candidate_to_numeric_ref") or {})
    by_target: dict[str, list[dict[str, Any]]] = {}
    for row in inventory.get("candidates") or ():
        by_target.setdefault(str(row["evidence_target_id"]), []).append(dict(row))
    max_chars = int(
        (policy.get("candidate_limits") or {}).get(
            "max_bounded_context_chars_per_evidence"
        )
        or 1800
    )
    research_evidence: list[dict[str, Any]] = []
    writer_evidence: list[dict[str, Any]] = []
    for row in evidence:
        target = str(row["target_id"])
        material = materials.get(str(row.get("source_material_ref") or ""))
        candidates = by_target.get(target, [])
        bindings = deepcopy(list(row.get("slot_bindings") or ()))
        contexts = _bounded_evidence_contexts(
            evidence=row,
            material=material,
            candidates=candidates,
            candidate_to_ref=candidate_to_ref,
            max_chars=max_chars,
        )
        authorized_refs = sorted(
            {
                candidate_to_ref[str(candidate["candidate_id"])]
                for candidate in candidates
                if str(candidate["candidate_id"]) in candidate_to_ref
            }
        )
        common = {
            "evidence_alias": aliases[target],
            "target_id": target,
            "evidence_role": str(row.get("evidence_role") or ""),
            "slot_bindings": bindings,
            "relationship_directions": deepcopy(
                list(row.get("relationship_directions") or ())
            ),
            "authorized_numeric_refs": authorized_refs,
            "source_text_digest": str(
                (material or {}).get("source_text_digest")
                or row.get("source_content_digest")
                or ""
            ),
        }
        research_evidence.append(
            {
                **common,
                "bounded_numeric_annotated_contexts": contexts,
                "context_only_candidate_count": sum(
                    candidate["adjudication_status"]
                    == "context_only_do_not_output"
                    for candidate in candidates
                ),
                "forbidden_candidate_count": sum(
                    candidate["adjudication_status"] == "forbidden_or_ambiguous"
                    for candidate in candidates
                ),
            }
        )
        writer_evidence.append(
            {
                **common,
                "bounded_nonnumeric_context": [
                    str(binding.get("business_meaning_zh") or "")
                    for binding in bindings
                    if binding.get("business_meaning_zh")
                ],
                "numeric_surface_rule": (
                    "Use only authorized_numeric_refs; never reconstruct a masked or "
                    "context-only source number."
                ),
            }
        )
    fact_view = [
        {
            "numeric_ref": row["numeric_ref"],
            "semantic_metric_key": row["semantic_metric_key"],
            "entity": row["entity"],
            "period_or_as_of": row["period_or_as_of"],
            "canonical_unit": row["canonical_unit"],
            "authoritative_value": deepcopy(row["authoritative_value"]),
            "evidence_aliases": deepcopy(row["evidence_aliases"]),
            "allowed_presentations": [
                {
                    "presentation_ref": receipt["presentation_ref"],
                    "rendered": receipt["rendered"],
                    "equivalence_relation": receipt["equivalence_relation"],
                }
                for receipt in row["presentation_receipts"]
            ],
            "claim_and_output_boundary": row["claim_and_output_boundary"],
        }
        for row in presentation_program.get("stable_numeric_facts") or ()
    ]
    formulas = deepcopy(list(presentation_program.get("formula_traces") or ()))
    body = {
        "schema_version": NODE_VIEW_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": str(pack.get("case_key") or ""),
        "inventory_digest": str(inventory.get("inventory_digest") or ""),
        "presentation_program_digest": str(
            presentation_program.get("presentation_program_digest") or ""
        ),
        "research_view": {
            "evidence": research_evidence,
            "numeric_facts": fact_view,
            "formula_traces": formulas,
            "rule": "Reason over authorized facts and masked bounded context; do not reconstruct masked values.",
        },
        "writer_view": {
            "evidence": writer_evidence,
            "numeric_facts": fact_view,
            "formula_traces": formulas,
            "rule": "Cite NUM/FORM refs; local rendering owns values, units, periods, currency, rounding and formulas.",
        },
        "verifier_view": {
            "numeric_facts": fact_view,
            "formula_traces": formulas,
            "evidence_ref_index": {
                row["evidence_alias"]: row["target_id"] for row in research_evidence
            },
            "rule": "Semantic verification cannot override the deterministic numeric gate.",
        },
    }
    view_char_counts = {
        key: len(canonical_bytes(body[key]).decode("utf-8"))
        for key in ("research_view", "writer_view", "verifier_view")
    }
    hard_limits = {
        str(key): int(value)
        for key, value in dict(
            policy.get("node_view_hard_char_limits") or {}
        ).items()
    }
    _require(
        set(hard_limits) == set(view_char_counts)
        and all(view_char_counts[key] <= hard_limits[key] for key in view_char_counts),
        "numeric_cocompilation_node_view_capacity_exceeded",
    )
    body["capacity_receipt"] = {
        "view_char_counts": view_char_counts,
        "hard_char_limits": hard_limits,
        "all_views_within_compiled_limits": True,
    }
    body["view_parity_digest"] = canonical_digest(
        {
            "inventory_digest": body["inventory_digest"],
            "presentation_program_digest": body["presentation_program_digest"],
            "fact_refs": sorted(row["numeric_ref"] for row in fact_view),
            "formula_refs": sorted(row["formula_ref"] for row in formulas),
        }
    )
    return {**body, "node_views_digest": canonical_digest(body)}


def _numeric_cores(value: str) -> set[str]:
    cores: set[str] = set()
    for match in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", str(value or "")):
        try:
            cores.add(_decimal_text(_decimal(match.group(0))))
        except SelectedEvidenceNumericCocompilationError:
            continue
    return cores


def _normalized_surface(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def evaluate_delivery_numeric_authority(
    *,
    delivery_text: str,
    used_numeric_refs: Sequence[str],
    used_formula_refs: Sequence[str],
    inventory: Mapping[str, Any],
    presentation_program: Mapping[str, Any],
    semantic_verifier_pass: bool,
) -> dict[str, Any]:
    facts = {
        str(row["numeric_ref"]): dict(row)
        for row in presentation_program.get("stable_numeric_facts") or ()
    }
    formulas = {
        str(row["formula_ref"]): dict(row)
        for row in presentation_program.get("formula_traces") or ()
    }
    unknown_refs = sorted(
        (set(used_numeric_refs) - set(facts))
        | (set(used_formula_refs) - set(formulas))
    )
    allowed_cores: set[str] = set()
    allowed_surfaces: set[str] = set()
    for ref in used_numeric_refs:
        fact = facts.get(str(ref))
        if fact is None:
            continue
        for receipt in fact.get("presentation_receipts") or ():
            if receipt.get("equivalence_relation") == "non_equivalent_conflicting_surface":
                continue
            surface = str(receipt.get("rendered") or "")
            allowed_surfaces.add(surface)
            allowed_cores.update(_numeric_cores(surface))
    for ref in used_formula_refs:
        formula = formulas.get(str(ref))
        if formula is None:
            continue
        allowed_surfaces.add(str(formula.get("rendered") or ""))
        allowed_cores.update(_numeric_cores(str(formula.get("rendered") or "")))
    presented_allowed_surfaces = {
        _normalized_surface(surface)
        for surface in allowed_surfaces
        if surface and _normalized_surface(surface) in _normalized_surface(delivery_text)
    }
    forbidden_literal_findings: list[dict[str, str]] = []
    for row in inventory.get("candidates") or ():
        if row.get("adjudication_status") in AUTHORIZED_STATUSES:
            continue
        surface = str(row.get("source_surface") or "")
        if surface and surface in delivery_text:
            normalized = _normalized_surface(surface)
            if any(
                normalized and normalized in allowed
                for allowed in presented_allowed_surfaces
            ):
                continue
            forbidden_literal_findings.append(
                {
                    "candidate_id": str(row["candidate_id"]),
                    "surface": surface,
                    "status": str(row["adjudication_status"]),
                }
            )
    observed_financial_cores: set[str] = set()
    observed_financial_surfaces: set[str] = set()
    for pattern in (_MONEY_RANGE_RE, _PERCENT_RANGE_RE, _MONEY_RE, _PERCENT_RE, _COUNT_AFTER_RE, _COUNT_BEFORE_RE):
        for match in pattern.finditer(delivery_text):
            observed_financial_cores.update(_numeric_cores(match.group(0)))
            observed_financial_surfaces.add(_normalized_surface(match.group(0)))
    unauthorized_cores = sorted(observed_financial_cores - allowed_cores)
    unauthorized_surfaces = sorted(
        surface
        for surface in observed_financial_surfaces
        if surface not in presented_allowed_surfaces
    )
    findings: list[dict[str, Any]] = []
    if unknown_refs:
        findings.append({"code": "unknown_numeric_or_formula_ref", "refs": unknown_refs})
    if forbidden_literal_findings:
        findings.append(
            {
                "code": "context_only_or_forbidden_candidate_emitted",
                "candidates": forbidden_literal_findings,
            }
        )
    if unauthorized_cores or unauthorized_surfaces:
        findings.append(
            {
                "code": "unauthorized_financial_numeric_surface",
                "normalized_numeric_cores": unauthorized_cores,
                "normalized_financial_surfaces": unauthorized_surfaces,
            }
        )
    if presentation_program.get("conflicts"):
        findings.append(
            {
                "code": "numeric_inventory_identity_conflict",
                "conflicts": deepcopy(list(presentation_program["conflicts"])),
            }
        )
    body = {
        "status": "pass" if not findings else "hard_fail",
        "semantic_verifier_pass": bool(semantic_verifier_pass),
        "local_numeric_gate_pass": not findings,
        "semantic_verifier_overrode_local_gate": False,
        "used_numeric_refs": sorted(set(used_numeric_refs)),
        "used_formula_refs": sorted(set(used_formula_refs)),
        "allowed_presentations": sorted(allowed_surfaces),
        "findings": findings,
    }
    return {**body, "guard_result_digest": canonical_digest(body)}


def validate_numeric_cocompilation_result(result: Mapping[str, Any]) -> None:
    _require(
        result.get("schema_version") == RESULT_SCHEMA
        and result.get("contract_ref") == CONTRACT_REF,
        "numeric_cocompilation_result_identity_invalid",
    )
    inventory = dict(result.get("candidate_inventory") or {})
    program = dict(result.get("presentation_program") or {})
    views = dict(result.get("node_views") or {})
    candidates = list(inventory.get("candidates") or ())
    _require(
        inventory.get("schema_version") == INVENTORY_SCHEMA
        and program.get("schema_version") == PRESENTATION_SCHEMA
        and views.get("schema_version") == NODE_VIEW_SCHEMA
        and candidates,
        "numeric_cocompilation_result_component_missing",
    )
    _require(
        all(
            REQUIRED_CANDIDATE_FIELDS <= set(row)
            and row.get("case_key") == result.get("case_key")
            and row.get("adjudication_status") in ALL_STATUSES
            for row in candidates
        )
        and len({row["candidate_id"] for row in candidates}) == len(candidates),
        "numeric_cocompilation_candidate_validation_failed",
    )
    candidate_ids = {str(row["candidate_id"]) for row in candidates}
    authorized_ids = {
        str(row["candidate_id"])
        for row in candidates
        if row.get("adjudication_status") in AUTHORIZED_STATUSES
    }
    candidate_to_ref = dict(program.get("candidate_to_numeric_ref") or {})
    conflict_ids = {
        str(candidate_id)
        for conflict in program.get("conflicts") or ()
        for candidate_id in conflict.get("candidate_ids") or ()
    }
    _require(
        set(candidate_to_ref) <= candidate_ids
        and authorized_ids == set(candidate_to_ref) | conflict_ids,
        "numeric_cocompilation_authorized_candidate_fact_parity_invalid",
    )
    fact_refs = {
        str(row["numeric_ref"])
        for row in program.get("stable_numeric_facts") or ()
    }
    _require(
        set(candidate_to_ref.values()) <= fact_refs
        and views.get("inventory_digest") == inventory.get("inventory_digest")
        and views.get("presentation_program_digest")
        == program.get("presentation_program_digest"),
        "numeric_cocompilation_node_view_parity_invalid",
    )
    serialized_views = json.dumps(views, ensure_ascii=False)
    _require(
        "source_text\"" not in serialized_views
        and "semantic verification cannot override" in serialized_views.lower(),
        "numeric_cocompilation_model_view_boundary_invalid",
    )
    _require(
        result.get("model_calls") == 0
        and result.get("provider_calls") == 0
        and result.get("network_calls") == 0
        and result.get("source_calls") == 0,
        "numeric_cocompilation_result_not_zero_call",
    )


def compile_selected_evidence_numeric_cocompilation(
    *,
    pack: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    inventory = compile_material_numeric_candidate_inventory(
        pack=pack,
        policy=policy,
    )
    program = compile_stable_fact_presentation_program(
        inventory=inventory,
        policy=policy,
    )
    views = compile_bounded_numeric_node_views(
        pack=pack,
        inventory=inventory,
        presentation_program=program,
        policy=policy,
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": str(pack.get("case_key") or ""),
        "source_pack_digest": str(
            pack.get("pack_payload_digest")
            or pack.get("pack_digest")
            or canonical_digest(pack)
        ),
        "candidate_inventory": inventory,
        "presentation_program": program,
        "node_views": views,
        "co_compilation_transaction_digest": canonical_digest(
            {
                "selected_evidence_digest": inventory["selected_evidence_digest"],
                "inventory_digest": inventory["inventory_digest"],
                "presentation_program_digest": program["presentation_program_digest"],
                "node_views_digest": views["node_views_digest"],
            }
        ),
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "automatic_rerun": False,
        "boundary": (
            "This zero-call result proves deterministic selected-Evidence numeric "
            "co-compilation only. It does not prove natural model compliance, report "
            "quality, Owner acceptance, release or production readiness."
        ),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    validate_numeric_cocompilation_result(result)
    return result


def compile_numeric_cocompilation_successor_input(
    *,
    base_case_input: Mapping[str, Any],
    pack: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    validate_numeric_cocompilation_result(result)
    _require(
        str(base_case_input.get("case_key") or "") == str(pack.get("case_key") or "")
        == str(result.get("case_key") or ""),
        "numeric_cocompilation_successor_case_identity_invalid",
    )
    evidence_by_target = {
        str(row.get("target_id") or ""): deepcopy(dict(row))
        for row in base_case_input.get("evidence_items") or ()
    }
    selected_targets = {
        str(row.get("target_id") or "") for row in pack.get("evidence_items") or ()
    }
    _require(
        selected_targets == set(evidence_by_target),
        "numeric_cocompilation_successor_evidence_set_drift",
    )
    model_input = {
        "case_key": str(result["case_key"]),
        "source_pack_digest": str(result["source_pack_digest"]),
        "selected_evidence": [
            {
                "evidence_alias": row.get("evidence_alias"),
                "target_id": row.get("target_id"),
                "object_type": row.get("object_type"),
                "evidence_role": row.get("evidence_role"),
                "slot_bindings": deepcopy(list(row.get("slot_bindings") or ())),
                "relationship_directions": deepcopy(
                    list(row.get("relationship_directions") or ())
                ),
                "numeric_use_boundary": row.get("numeric_use_boundary"),
                "source_text_digest": row.get("source_text_digest"),
            }
            for row in sorted(
                evidence_by_target.values(),
                key=lambda item: str(item.get("evidence_alias") or ""),
            )
        ],
        "residual_gaps": deepcopy(list(base_case_input.get("residual_gaps") or ())),
        "candidate_inventory_digest": result["candidate_inventory"]["inventory_digest"],
        "numeric_authority": deepcopy(result["presentation_program"]),
        "node_numeric_views": deepcopy(result["node_views"]),
        "model_rules": {
            "full_source_numeric_surfaces_visible": False,
            "research_uses_bounded_annotated_context": True,
            "writer_uses_only_num_and_form_refs": True,
            "local_renderer_owns_fact_surfaces": True,
            "model_owns_thesis_mechanism_counterthesis_and_prose": True,
            "semantic_verifier_can_override_local_numeric_gate": False,
        },
    }
    audit_binding = {
        "base_model_visible_digest": str(
            base_case_input.get("model_visible_digest") or canonical_digest(base_case_input)
        ),
        "raw_source_material_count": len(base_case_input.get("source_materials") or ()),
        "raw_source_material_digest_set": sorted(
            str(row.get("source_text_digest") or "")
            for row in base_case_input.get("source_materials") or ()
        ),
        "raw_source_content_in_successor_model_input": False,
    }
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s2_selected_evidence_numeric_cocompilation_"
            "successor_input_v1_0"
        ),
        "contract_ref": CONTRACT_REF,
        "case_key": str(result["case_key"]),
        "co_compilation_transaction_digest": result[
            "co_compilation_transaction_digest"
        ],
        "private_audit_binding": audit_binding,
        "model_input": model_input,
    }
    body["successor_model_input_digest"] = canonical_digest(model_input)
    body["successor_input_digest"] = canonical_digest(body)
    _require(
        not any("source_text" in row for row in model_input["selected_evidence"])
        and audit_binding["raw_source_content_in_successor_model_input"] is False,
        "numeric_cocompilation_successor_raw_source_leak",
    )
    return body


__all__ = [
    "ALL_STATUSES",
    "AUTHORIZED_STATUSES",
    "CONTRACT_REF",
    "INVENTORY_SCHEMA",
    "NODE_VIEW_SCHEMA",
    "POLICY_SCHEMA",
    "PRESENTATION_SCHEMA",
    "RESULT_SCHEMA",
    "SelectedEvidenceNumericCocompilationError",
    "canonical_digest",
    "compile_bounded_numeric_node_views",
    "compile_material_numeric_candidate_inventory",
    "compile_numeric_cocompilation_successor_input",
    "compile_selected_evidence_numeric_cocompilation",
    "compile_stable_fact_presentation_program",
    "evaluate_delivery_numeric_authority",
    "load_numeric_cocompilation_policy",
    "validate_numeric_cocompilation_result",
]
