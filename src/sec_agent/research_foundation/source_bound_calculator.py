"""Small FIN provenance adapter over simpleeval + decimal, never Python eval.

The mature evaluator parses arithmetic. FIN binds operands to source observations
or explicit assumptions. Arithmetic correctness does not validate financial
comparability, source reliability, units, extraction meaning or causality.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from decimal import Decimal, localcontext
import operator
import re
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field
from simpleeval import SimpleEval

from sec_agent.agent_runtime.dell_reference_vertical_contracts import canonical_sha256


class CalculationOperand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str | None = Field(default=None, min_length=1, max_length=500,
        description="Copy the passage_id from an actually read source, an observed SQL/Evidence ID, or a saved CALC ID. A CHUNK/node_id, UPLOAD/document_id, WEB/document_id or SOURCELOC candidate_id is a navigation locator, NOT a calculator source ID; read it and use the returned PASSAGE ID. For S2 or a saved calculation only source_id is needed; the host reads the number. A calculation never becomes S2 authority.")
    literal: str | None = Field(default=None, min_length=1, max_length=64,
        description="For prose copy the decimal numeric substring printed in the quote, including commas: quote 'Revenue $2,225 million' uses literal '2,225', not '2225' or '$2,225 million'. Exclude percent symbols, currency symbols, units and parentheses; no exponent notation. Do not put a derived difference/ratio here: bind originals and calculate in expression. For S2/saved CALC omit this. Parentheses/sign interpretation belongs explicitly in expression and rationale.")
    quote: str | None = Field(default=None, min_length=1, max_length=4000,
        description="Exact contiguous source quote containing the literal; no paraphrase or ellipsis.")
    assumption_note: str | None = Field(default=None, min_length=1, max_length=1000,
        description="Required for an unsourced scenario/scale/day-count input. It will remain an explicit assumption, never source truth.")


class SourceBoundCalculation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expression: str = Field(min_length=1, max_length=1000,
        description="Arithmetic using the operand KEYS, parentheses and + - * /. Example: expression '(a-b)-(c-d)' with operands a,b,c,d bound to original source numbers. Every declared operand key must occur; never substitute raw source numbers into the formula and leave their bindings unused. Small integer scale constants allowed; decimals use operands. No functions, attributes, powers or code.")
    operands: dict[str, CalculationOperand] = Field(min_length=1, max_length=16)
    result_unit: str = Field(min_length=1, max_length=80,
        description="Your declared result unit; this calculator does not prove dimensional or financial comparability.")
    rationale: str = Field(min_length=1, max_length=2000,
        description="Explain the financial formula and period/unit choices for independent review, not hidden reasoning.")


def _number(literal: str) -> Decimal:
    # Preserve decimal arithmetic; literal matching is separate from source meaning.
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", literal):
        raise ValueError("numeric_literal_requires_plain_decimal_no_percent_or_exponent")
    value = Decimal(literal.replace(",", ""))
    if not value.is_finite() or abs(value) > Decimal("1e36"):
        raise ValueError("numeric_operand_out_of_range")
    return value


def source_items_from_tool(tool_name: str, body: dict) -> dict[str, dict]:
    """Normalize successful MCP data responses, never model text or previews.

    Callers own their native messages/composition lifetime. This is a projection,
    not another source store or evidence-admission system.
    """
    if tool_name == "query_company_financial_facts" and body.get("authority_state") == "s2_numeric_fact_query_result":
        return {f["numeric_fact_id"]: {**f, "result_state": "numeric_fact"}
                for row in body.get("results", []) if row.get("status") == "resolved"
                for f in row.get("facts", []) if f.get("numeric_fact_authority") is True}
    if tool_name == "read_source_document" and body.get("operation") in {"read", "search"}:
        return {p["passage_id"]: dict(p) for p in body.get("items", [])
                if p.get("result_state") == "source_bound_passage" and p.get("writer_citable") is True
                and p.get("numeric_fact_authority") is False and p.get("passage_id") and p.get("passage")}
    if tool_name == "read_reviewed_evidence" and body.get("authority_state") == "reviewed_evidence_read":
        return {p["evidence_id"]: {**p, "result_state": "reviewed_evidence", "numeric_fact_authority": False}
                for p in body.get("evidence", []) if p.get("writer_citable") is True}
    if (tool_name == "calculate_research_metric" and body.get("result_state") == "non_authoritative_metric"
            and body.get("arithmetic_verified") is True and body.get("numeric_fact_authority") is False):
        return {body["calculation_id"]: deepcopy(body)}
    return {}


def calculate_from_sources(request: SourceBoundCalculation, source_lookup: Callable[[str], dict]) -> dict:
    values, bindings = {}, {}
    for name, operand in request.operands.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name):
            raise ValueError("operand_name_must_be_lowercase_identifier")
        if operand.source_id is None:
            if not operand.assumption_note or operand.literal is None or operand.quote is not None:
                raise ValueError("unsourced_operand_requires_literal_and_explicit_assumption")
            value = _number(operand.literal)
            binding = {"assumption_note": operand.assumption_note, "authority": "assumption"}
        else:
            item = source_lookup(operand.source_id)
            if operand.assumption_note is not None:
                raise ValueError("source_operand_cannot_be_relabelled_assumption")
            if item.get("result_state") == "numeric_fact" and item.get("numeric_fact_authority") is True:
                value = _number(str(item["value_decimal"]))
                if operand.literal is not None and _number(operand.literal) != value:
                    raise ValueError("operand_value_differs_from_observed_s2_fact")
                binding = {"source_id": operand.source_id, "authority": "s2_input", **{
                    key: item[key] for key in ("ticker", "metric_id", "period_start", "period_end", "unit", "fiscal_period",
                                              "formula_trace", "source_observation_ids", "citation_urls", "research_as_of") if key in item}}
            elif (item.get("result_state") == "non_authoritative_metric" and item.get("arithmetic_verified") is True
                    and item.get("numeric_fact_authority") is False and item.get("financial_semantics_verified") is False):
                if operand.source_id.startswith("CALC::") and operand.source_id != item.get("calculation_id"):
                    raise ValueError("calculation_source_id_mismatch")
                value = Decimal(str(item["value_decimal"]))
                if not value.is_finite() or abs(value) > Decimal("1e100"):
                    raise ValueError("saved_calculation_value_out_of_range")
                if operand.literal is not None and _number(operand.literal) != value:
                    raise ValueError("operand_value_differs_from_observed_calculation")
                if operand.quote is not None:
                    raise ValueError("calculated_operand_uses_saved_result_not_a_source_quote")
                binding = {"source_id": operand.source_id, "authority": "non_authoritative_calculation",
                    "source_calculation": {key: item[key] for key in ("calculation_id", "expression", "result_unit", "authority_note")}}
            elif item.get("result_state") in {"reviewed_evidence", "source_bound_passage"} and item.get("writer_citable") is True:
                text = str(item.get("passage") or item.get("bounded_excerpt") or "")
                if not operand.quote or operand.quote not in text or operand.literal is None:
                    raise ValueError("operand_quote_not_in_observed_source")
                if not re.search(r"(?<![\w.,])" + re.escape(operand.literal) + r"(?![\w.,])", operand.quote):
                    raise ValueError("numeric_literal_not_in_exact_source_quote")
                value = _number(operand.literal)
                binding = {"source_id": operand.source_id, "quote": operand.quote,
                    "literal": operand.literal, "authority": "non_authoritative_source_reported",
                    "extraction_meaning_verified": False}
            else:
                raise ValueError("operand_requires_observed_citable_source_or_s2_fact")
            binding["source_provenance"] = {key: item[key] for key in (
                "source_url", "citation_urls", "source_locator", "title", "ticker", "company", "issuer_id",
                "publication_date", "publication_date_status", "period_start", "period_end", "fiscal_period",
                "source_reporting_period_end", "unit", "numeric_fact_authority", "authority_note",
                "source_type", "source_tier", "source_role", "source_observation_ids", "content_sha256") if key in item}
        values[name] = value
        bindings[name] = {**binding, "value_decimal": str(value)}

    evaluator = SimpleEval(names=values, functions={}, operators={
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos})
    # Configure the library's supported nodes, not a second expression parser.
    evaluator.nodes = {key: evaluator.nodes[key] for key in (ast.Expr, ast.Name, ast.BinOp, ast.UnaryOp)}

    def integer_constant(node):
        if type(node.value) is not int or abs(node.value) > 10**12:
            raise ValueError("constant_must_be_small_integer_use_operand_for_decimal")
        return Decimal(node.value)

    evaluator.nodes[ast.Constant] = integer_constant
    try:
        with localcontext() as context:
            context.prec = 34
            parsed = ast.parse(request.expression, mode="eval").body
            used = {node.id for node in ast.walk(parsed) if isinstance(node, ast.Name)}
            if used != set(values):
                raise ValueError("formula_names_must_match_operands_no_unused_source_binding")
            value = evaluator.eval(request.expression, previously_parsed=parsed)
            if not isinstance(value, Decimal) or not value.is_finite() or abs(value) > Decimal("1e100"):
                raise ValueError("calculation_result_not_finite_or_out_of_range")
    except Exception as exc:
        raise ValueError(f"calculation_rejected:{type(exc).__name__}:{exc}") from None
    body = {"expression": request.expression, "operands": bindings, "value_decimal": str(value),
        "result_unit": request.result_unit, "rationale": request.rationale,
        "result_state": "non_authoritative_metric", "numeric_fact_authority": False,
        "arithmetic_verified": True, "financial_semantics_verified": False,
        "authority_note": "Locally calculated from bound inputs and explicit assumptions; NOT an S2 NumericFact or issuer-reported measure. "
            "Disclose non-authoritative inputs and assumptions wherever the result or its inference is used. "
            "Check units, periods, business scope and denominator meaning in financial review."}
    return {"calculation_id": "CALC::" + canonical_sha256(body)[:24], **body}


def register_source_calculator_tool(server, source_lookup, *, on_result=None):
    @server.tool(name="calculate_research_metric", structured_output=True)
    def calculate(request: SourceBoundCalculation) -> dict[str, Any]:
        """Evaluate arithmetic using observed archive/PASSAGE/Evidence/SQL or saved CALC IDs. Search previews cannot be operands. No shell/code or S2 write; output remains non-authoritative. financial_semantics_verified=false means not verified, not a failed financial review."""
        try:
            result = calculate_from_sources(request, source_lookup)
            if on_result is not None:
                on_result(result)
            return result
        except ValueError as exc:
            from mcp.server.mcpserver.exceptions import ToolError
            raise ToolError(str(exc) + ". For S2 or a saved CALC use {source_id: observed ID}; for prose use an observed PASSAGE/evidence/archive ID plus exact quote and literal. Re-query SQL or read the original passage if this tool session has not observed the ID. Do not remove source binding or relabel sourced numbers as assumptions.") from None
