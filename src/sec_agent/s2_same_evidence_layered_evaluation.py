from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Mapping, Sequence


NUMERIC_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|[kKmMbBtT]|x)?(?![A-Za-z0-9_.]|-(?:K|Q|F)\b)"
)
_HYPOTHETICAL_PATHS = (".stop_condition", ".what_would_change")
_CONDITIONAL_MARKERS = (
    "if ", "scenario", "assumption", "threshold", "would change",
    " would ", " could ", "below ", "above ", "drop ", "decline ",
    "trigger", "若", "如果", "假设", "情景", "阈值", "触发",
)
_PERCENT_RANGE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<low>\d(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<high>\d(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)
_DIRECTIONAL_PERCENT_TERMS = (
    "mid-single-digit", "mid single digit", "中个位数",
)
_DIRECTIONAL_PERCENT_CONTEXT_TERMS = (
    "margin", "profit", "profitability", "营业利润", "利润率", "盈利",
)


def compile_output_contract(
    node_type: str,
    policy: Mapping[str, Any],
    section_ids: Sequence[str],
) -> dict[str, Any]:
    """Return the single model-visible typed contract used by prompt and tests."""

    identity = {
        "case_key": {"type": "string", "const": "exact case ticker"},
        "as_of": {"type": "string", "const": "exact case as_of"},
    }
    if node_type == "lead_planning":
        unit = _object(
            {
                "unit_id": _string(), "family": _string(), "question": _string(),
                "why_material": _string(), "evidence_ids": _string_array(),
                "gap_ids": _string_array(), "stop_condition": _string(),
            }
        )
        return _object({**identity, "research_units": {"type": "array", "minItems": 6, "maxItems": 8, "items": unit}}, extra={
            "mandatory_families": list(policy["mandatory_research_families"]),
            "numeric_semantics": "Only stop_condition may contain an explicitly conditional hypothetical threshold; it is not a fact.",
        })
    if node_type == "specialist_judgment":
        return _object(
            {
                **identity,
                "unit_id": _string(),
                "epistemic_state": {"type": "string", "enum": list(policy["epistemic_states"])},
                "judgment": _string(), "mechanism": _string(),
                "financial_or_valuation_link": _string(),
                "evidence_ids": _string_array(), "counterevidence_ids": _string_array(),
                "gap_ids": _string_array(), "what_would_change": _string(),
            },
            extra={"numeric_semantics": "Only what_would_change may contain an explicitly conditional hypothetical threshold; never present it as evidence or a forecast."},
        )
    if node_type == "cross_cell_synthesis":
        dependency = _object({"from_unit_id": _string(), "to_unit_id": _string(), "relationship": _string()})
        conflict = _object({"unit_ids": {"type": "array", "minItems": 2, "items": _string()}, "resolution": _string()})
        return _object(
            {
                **identity, "thesis": _string(), "confidence": _string(),
                "unit_ids": _string_array(),
                "dependencies": {"type": "array", "items": dependency},
                "conflicts": {"type": "array", "items": conflict},
                "material_gap_ids": _string_array(), "counter_thesis": _string(),
                "what_would_change": _string(),
            },
            extra={"numeric_semantics": "Only what_would_change may contain an explicitly conditional hypothetical threshold."},
        )
    if node_type == "writer":
        section = _object(
            {
                "section_id": {"type": "string", "enum": list(section_ids)},
                "heading": _string(), "narrative": _string(),
                "evidence_ids": _string_array(), "unit_ids": _string_array(),
                "gap_ids": _string_array(),
            }
        )
        return _object(
            {
                **identity, "title": _string(),
                "sections": {"type": "array", "minItems": len(section_ids), "maxItems": len(section_ids), "items": section},
                "overall_boundary": _string(),
            },
            extra={"required_section_order": list(section_ids)},
        )
    if node_type == "verifier":
        finding = _object(
            {
                "severity": {"type": "string", "enum": ["L1", "L2", "L3", "L4"]},
                "code": _string(), "node_refs": _string_array(),
                "evidence_ids": _string_array(), "explanation": _string(),
            }
        )
        return _object(
            {
                **identity,
                "decision": {"type": "string", "enum": ["accept_raw_candidate", "return_material_failure"]},
                "material_failure": {"type": "boolean"},
                "findings": {"type": "array", "items": finding},
                "checked_unit_ids": _string_array(), "checked_section_ids": _string_array(),
            },
            extra={"state_invariant": "material_failure is true iff any finding has severity L1; return_material_failure iff material_failure is true."},
        )
    raise ValueError("experiment_a_unknown_node_type")


def allowed_numeric_surfaces(case_input: Mapping[str, Any]) -> set[str]:
    """Compile acceptable natural renderings from structured case numerics."""

    allowed = {_normalize(token) for token in NUMERIC_TOKEN.findall(json.dumps(case_input, ensure_ascii=False))}
    rows: list[Mapping[str, Any]] = []
    rows.extend(row for row in case_input.get("derived_numeric", []) if isinstance(row, Mapping))
    for evidence in case_input.get("evidence_items", []):
        if isinstance(evidence, Mapping):
            rows.extend(row for row in evidence.get("numeric_facts", []) if isinstance(row, Mapping))
    for row in rows:
        raw = str(row.get("value") or "").replace(",", "")
        unit = str(row.get("unit") or "").lower()
        try:
            value = Decimal(raw)
        except InvalidOperation:
            continue
        variants = {_decimal(value), _decimal(value.quantize(Decimal("0.1")))}
        if abs(value) >= 10:
            variants.add(_decimal(value.quantize(Decimal("1"))))
        suffixes = [""]
        if unit.startswith("percent"):
            suffixes.append("%")
        if unit.startswith("usd_billion"):
            suffixes.extend(["b", "B"])
        if unit in {"multiple", "ratio"}:
            suffixes.append("x")
        for variant in variants:
            for suffix in suffixes:
                allowed.add(_normalize(variant + suffix))
    return allowed


def evaluate_raw_chain(
    outputs: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    policy: Mapping[str, Any],
    section_ids: Sequence[str],
) -> dict[str, Any]:
    """Evaluate a captured raw chain without repairing or promoting its content."""

    findings: list[dict[str, Any]] = []
    lead = outputs.get("lead")
    specialists = outputs.get("specialists")
    synthesis = outputs.get("synthesis")
    writer = outputs.get("writer")
    verifier = outputs.get("verifier")
    complete = (
        isinstance(lead, Mapping)
        and isinstance(specialists, list)
        and 6 <= len(specialists) <= 8
        and all(isinstance(row, Mapping) for row in specialists)
        and isinstance(synthesis, Mapping)
        and isinstance(writer, Mapping)
        and isinstance(verifier, Mapping)
    )
    nodes: list[tuple[str, Any]] = [("lead", lead)]
    nodes.extend((f"specialist[{index}]", value) for index, value in enumerate(specialists or []))
    nodes.extend((("synthesis", synthesis), ("writer", writer), ("verifier", verifier)))
    for node_ref, value in nodes:
        if not isinstance(value, Mapping):
            _finding(findings, "L1", "raw_node_missing_or_unparseable", node_ref)
            continue
        if value.get("case_key") != case_input.get("case_key") or value.get("as_of") != case_input.get("as_of"):
            _finding(findings, "L1", "raw_node_identity_missing_or_mismatched", node_ref)
        _walk_numeric(value, "$", node_ref, case_input, findings)

    _shape_findings(synthesis, writer, verifier, findings)
    for index, specialist in enumerate(specialists or []):
        if isinstance(specialist, Mapping) and not specialist.get("counterevidence_ids"):
            _finding(findings, "L3", "explicit_counterevidence_surface_empty", f"specialist[{index}]")

    semantic_codes: set[str] = set()
    if isinstance(writer, Mapping):
        for path, text in _text_surfaces(writer):
            for code in _financial_semantic_codes(text.lower(), case_input):
                severity = (
                    "L3"
                    if code == "unsupported_historical_valuation_comparison"
                    and _is_conditional_surface(path, text)
                    else "L1"
                )
                if severity == "L1":
                    semantic_codes.add(code)
                _finding(findings, severity, code, "writer", path=path)

    content_nodes: list[tuple[str, Any]] = [
        (f"specialist[{index}]", value)
        for index, value in enumerate(specialists or [])
    ]
    content_nodes.extend((("synthesis", synthesis), ("writer", writer)))
    for node_ref, value in content_nodes:
        if not isinstance(value, Mapping):
            continue
        for path, text in _text_surfaces(value):
            for code in _financial_invariant_codes(text.lower(), case_input):
                semantic_codes.add(code)
                _finding(findings, "L1", code, node_ref, path=path)

    verifier_l1 = False
    if isinstance(verifier, Mapping) and isinstance(verifier.get("findings"), list):
        verifier_l1 = any(
            isinstance(row, Mapping) and row.get("severity") == "L1"
            for row in verifier["findings"]
        )
    upstream_l1 = any(row["severity"] == "L1" and row["node_ref"] != "verifier" for row in findings)
    if semantic_codes and not verifier_l1:
        _finding(findings, "L2", "verifier_missed_material_financial_semantics", "verifier")
    if upstream_l1 and not verifier_l1:
        _finding(findings, "L2", "verifier_missed_material_failure", "verifier")

    material = any(row["severity"] == "L1" for row in findings)
    verifier_accepts = isinstance(verifier, Mapping) and verifier.get("decision") == "accept_raw_candidate"
    return {
        "schema_version": "fin_ia_0_1_3_s2_05_layered_raw_evaluation_v1_3",
        "case_key": case_input.get("case_key"),
        "raw_chain_complete": complete,
        "raw_experiment_candidate": complete,
        "hidden_scoring_eligible": complete,
        "business_promotion_gate_pass": complete and not material and verifier_accepts,
        # S2-05 is an isolated raw-model experiment.  Passing its local gate
        # never by itself authorizes a product/business promotion.
        "business_promotable": False,
        "status": "complete_with_material_findings" if complete and material else ("complete_without_material_findings" if complete else "incomplete"),
        "material_failure": material,
        "finding_count": len(findings),
        "findings": findings,
        "compiled_contracts": {
            node: compile_output_contract(node, policy, section_ids)
            for node in ("lead_planning", "specialist_judgment", "cross_cell_synthesis", "writer", "verifier")
        },
    }


def _walk_numeric(value: Any, path: str, node_ref: str, case_input: Mapping[str, Any], findings: list[dict[str, Any]]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _walk_numeric(child, f"{path}.{key}", node_ref, case_input, findings)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_numeric(child, f"{path}[{index}]", node_ref, case_input, findings)
    elif isinstance(value, str):
        allowed = allowed_numeric_surfaces(case_input)
        occurrences = [
            (match.start(), match.end(), _normalize(match.group(0)))
            for match in NUMERIC_TOKEN.finditer(value)
            if _normalize(match.group(0)) not in allowed
        ]
        unbound = {token for _, _, token in occurrences}
        if not unbound:
            return

        sharpened = _directional_percent_range_tokens(value, case_input) & unbound
        if sharpened:
            _finding(
                findings, "L1", "directional_margin_sharpened_to_unsupported_range",
                node_ref, path=path, tokens=sorted(sharpened),
            )
            unbound -= sharpened
        if not unbound:
            return

        conditional: set[str] = set()
        asserted: set[str] = set()
        for start, end, token in occurrences:
            if token not in unbound:
                continue
            context = value[max(0, start - 96):min(len(value), end + 96)].lower()
            if path.endswith(_HYPOTHETICAL_PATHS) or any(marker in context for marker in _CONDITIONAL_MARKERS):
                conditional.add(token)
            else:
                asserted.add(token)
        if conditional:
            _finding(
                findings, "L3", "hypothetical_planning_threshold", node_ref,
                path=path, tokens=sorted(conditional),
            )
        if asserted:
            _finding(
                findings, "L1", "unbound_material_numeric_surface", node_ref,
                path=path, tokens=sorted(asserted),
            )


def _shape_findings(synthesis: Any, writer: Any, verifier: Any, findings: list[dict[str, Any]]) -> None:
    if isinstance(synthesis, Mapping):
        if not _typed_rows(synthesis.get("dependencies"), {"from_unit_id", "to_unit_id", "relationship"}):
            _finding(findings, "L2", "synthesis_dependencies_not_typed_rows", "synthesis")
        if not _typed_rows(synthesis.get("conflicts"), {"unit_ids", "resolution"}):
            _finding(findings, "L2", "synthesis_conflicts_not_typed_rows", "synthesis")
    if isinstance(writer, Mapping) and not isinstance(writer.get("overall_boundary"), str):
        _finding(findings, "L2", "writer_overall_boundary_not_string", "writer")
    if isinstance(verifier, Mapping):
        if not isinstance(verifier.get("material_failure"), bool):
            _finding(findings, "L1", "verifier_material_failure_not_boolean", "verifier")
        if not isinstance(verifier.get("findings"), list):
            _finding(findings, "L1", "verifier_findings_not_array", "verifier")


def _financial_semantic_codes(text: str, case_input: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    cash = any(term in text for term in ("operating cash flow", "ocf", "经营现金流"))
    earnings = any(term in text for term in ("net income", "净利润", "eps", "每股收益", "p/e", "市盈率"))
    if cash and earnings:
        codes.append("cash_flow_margin_used_in_earnings_or_valuation_bridge")
    backlog = "backlog" in text or "积压" in text
    price_bridge = any(term in text for term in ("eps", "每股收益", "stock downside", "股价下跌", "股价跌幅"))
    if backlog and price_bridge:
        codes.append("unsupported_backlog_to_eps_or_price_bridge")
    historical = any(term in text for term in ("historical average", "历史平均", "历史均值"))
    input_text = json.dumps(case_input, ensure_ascii=False).lower()
    if historical and not any(term in input_text for term in ("historical average", "历史平均", "历史均值")):
        codes.append("unsupported_historical_valuation_comparison")
    return codes


def _financial_invariant_codes(text: str, case_input: Mapping[str, Any]) -> list[str]:
    codes: list[str] = []
    metrics = _numeric_metric_names(case_input)
    pe_terms = ("trailing p/e", "trailing pe", "static p/e", "静态 p/e", "静态p/e")
    single_period_terms = ("single-quarter", "single quarter", "单季")
    basis_terms = ("based on", "basis", "基于")
    if (
        "trailing_pe" in metrics
        and any(term in text for term in pe_terms)
        and any(term in text for term in single_period_terms)
        and any(term in text for term in basis_terms)
    ):
        codes.append("trailing_pe_recast_as_single_quarter_earnings_multiple")

    deposit_terms = ("deposit", "prepayment", "预付款", "客户押金")
    cash_or_refund_terms = (
        "cash buffer", "liquidity buffer", "write-down", "writedown", "refund",
        "现金缓冲", "流动性缓冲", "减值", "退款",
    )
    if (
        "deposits_and_commitments" in metrics
        and any(term in text for term in deposit_terms)
        and any(term in text for term in cash_or_refund_terms)
    ):
        codes.append("combined_deposits_commitments_recast_as_cash_or_refundable_prepayment")

    fcf_terms = ("fcf", "free cash flow", "自由现金流")
    lost_revenue_terms = ("lost revenue", "revenue decline", "收入减少", "收入下降")
    marginal_terms = ("every $1", "each $1", "每1美元", "每 1 美元")
    if (
        "adjusted_fcf_margin" in metrics
        and any(term in text for term in fcf_terms)
        and any(term in text for term in lost_revenue_terms)
        and any(term in text for term in marginal_terms)
    ):
        codes.append("average_fcf_margin_recast_as_marginal_revenue_sensitivity")
    return codes


def _numeric_metric_names(case_input: Mapping[str, Any]) -> set[str]:
    metrics = {
        str(row.get("metric") or "")
        for row in case_input.get("derived_numeric", [])
        if isinstance(row, Mapping)
    }
    for evidence in case_input.get("evidence_items", []):
        if not isinstance(evidence, Mapping):
            continue
        metrics.update(
            str(row.get("metric") or "")
            for row in evidence.get("numeric_facts", [])
            if isinstance(row, Mapping)
        )
    return metrics


def _directional_percent_range_tokens(text: str, case_input: Mapping[str, Any]) -> set[str]:
    input_text = json.dumps(case_input, ensure_ascii=False).lower()
    if not any(term in input_text for term in _DIRECTIONAL_PERCENT_TERMS):
        return set()
    tokens: set[str] = set()
    for match in _PERCENT_RANGE.finditer(text):
        context = text[max(0, match.start() - 96):min(len(text), match.end() + 96)].lower()
        if not any(term in context for term in _DIRECTIONAL_PERCENT_CONTEXT_TERMS):
            continue
        tokens.add(_normalize(match.group("low")))
        tokens.add(_normalize(match.group("high") + "%"))
    return tokens


def _is_conditional_surface(path: str, text: str) -> bool:
    lowered = text.lower()
    return path.endswith(_HYPOTHETICAL_PATHS) or any(
        marker in lowered for marker in _CONDITIONAL_MARKERS
    )


def _text_surfaces(value: Any, path: str = "$") -> list[tuple[str, str]]:
    surfaces: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            surfaces.extend(_text_surfaces(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            surfaces.extend(_text_surfaces(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        surfaces.append((path, value))
    return surfaces


def _typed_rows(value: Any, keys: set[str]) -> bool:
    return isinstance(value, list) and all(isinstance(row, Mapping) and set(row) == keys for row in value)


def _finding(findings: list[dict[str, Any]], severity: str, code: str, node_ref: str, **extra: Any) -> None:
    row = {"severity": severity, "code": code, "node_ref": node_ref, **extra}
    if row not in findings:
        findings.append(row)


def _object(properties: Mapping[str, Any], *, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = {"type": "object", "additionalProperties": False, "required": list(properties), "properties": dict(properties)}
    if extra:
        result.update(extra)
    return result


def _string() -> dict[str, Any]:
    return {"type": "string", "minLength": 1}


def _string_array() -> dict[str, Any]:
    return {"type": "array", "items": _string(), "uniqueItems": True}


def _decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _normalize(value: str) -> str:
    compact = value.replace(",", "").lstrip("+").lower()
    match = re.fullmatch(r"([-+]?\d+(?:\.\d+)?)(%|[kmbtx])?", compact)
    if not match:
        return compact
    try:
        number = _decimal(Decimal(match.group(1)))
    except InvalidOperation:
        return compact
    return number + (match.group(2) or "")
