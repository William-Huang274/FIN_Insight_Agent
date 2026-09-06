"""Small FIN provenance adapter over simpleeval + decimal, never Python eval.

The mature evaluator parses arithmetic. FIN binds operands to source observations
or explicit assumptions. Arithmetic correctness does not validate financial
comparability, source reliability, units, extraction meaning or causality.
"""
from __future__ import annotations

import ast
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
        description="Observed archive Pxx:Sxxx ID, or numeric_fact_id returned by a successful SQL query in this tool session. Never invent IDs. For S2 only source_id is needed; the host reads the number.")
    literal: str | None = Field(default=None, min_length=1, max_length=64,
        description="For a source-reported number, copy its exact numeric literal, including commas. For S2 omit this: host reads value_decimal.")
    quote: str | None = Field(default=None, min_length=1, max_length=4000,
        description="Exact contiguous source quote containing the literal; no paraphrase or ellipsis.")
    assumption_note: str | None = Field(default=None, min_length=1, max_length=1000,
        description="Required for an unsourced scenario/scale/day-count input. It will remain an explicit assumption, never source truth.")


class SourceBoundCalculation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expression: str = Field(min_length=1, max_length=1000,
        description="Arithmetic using named operands, parentheses and + - * /. Integer constants allowed; pass decimals as operands. No functions, attributes, powers or code.")
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
                    key: item[key] for key in ("ticker", "metric_id", "period_start", "period_end", "unit", "fiscal_period") if key in item}}
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


def register_source_calculator_tool(server, source_lookup):
    @server.tool(name="calculate_research_metric", structured_output=True)
    def calculate(request: SourceBoundCalculation) -> dict[str, Any]:
        """Evaluate arithmetic using archive source IDs or numeric_fact_id from this session's successful SQL query. No shell/code or S2 write; output remains non-authoritative."""
        try:
            return calculate_from_sources(request, source_lookup)
        except ValueError as exc:
            from mcp.server.mcpserver.exceptions import ToolError
            raise ToolError(str(exc) + ". For S2 use {source_id: observed numeric_fact_id} or an archive Pxx:Sxxx ID from paper sources. Re-query SQL if this tool session has not observed the ID. Do not remove source binding or relabel sourced numbers as assumptions.") from None
