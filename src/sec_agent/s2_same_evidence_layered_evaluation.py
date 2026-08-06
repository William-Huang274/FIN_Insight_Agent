from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Mapping, Sequence


NUMERIC_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|[kKmMbBtT]|x)?(?![A-Za-z0-9_.])"
)
_HYPOTHETICAL_PATHS = (".stop_condition", ".what_would_change")
_CONDITIONAL_MARKERS = (
    "if ", "scenario", "assumption", "threshold", "would change",
    "若", "如果", "假设", "情景", "阈值", "触发",
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
        if unit == "percent":
            suffixes.append("%")
        if unit == "usd_billion":
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

    writer_text = json.dumps(writer, ensure_ascii=False).lower() if isinstance(writer, Mapping) else ""
    semantic_codes = _financial_semantic_codes(writer_text, case_input)
    for code in semantic_codes:
        _finding(findings, "L1", code, "writer")
    verifier_text = json.dumps(verifier, ensure_ascii=False).lower() if isinstance(verifier, Mapping) else ""
    if semantic_codes and not any(code.lower() in verifier_text for code in semantic_codes):
        _finding(findings, "L2", "verifier_missed_material_financial_semantics", "verifier")

    material = any(row["severity"] == "L1" for row in findings)
    verifier_accepts = isinstance(verifier, Mapping) and verifier.get("decision") == "accept_raw_candidate"
    return {
        "schema_version": "fin_ia_0_1_3_s2_05_layered_raw_evaluation_v1_0",
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
        unbound = sorted({_normalize(token) for token in NUMERIC_TOKEN.findall(value)} - allowed)
        if not unbound:
            return
        # The field path is the authority boundary.  Wording quality (whether
        # the prose visibly says "if"/"假设") is scored separately; it must not
        # turn a planning threshold into an asserted financial fact.
        conditional = path.endswith(_HYPOTHETICAL_PATHS)
        _finding(
            findings,
            "L3" if conditional else "L1",
            "hypothetical_planning_threshold" if conditional else "unbound_material_numeric_surface",
            node_ref,
            path=path,
            tokens=unbound,
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
