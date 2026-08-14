from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
import json
import re
from typing import Any, Callable, Mapping, Sequence

from retrieval.contracts import (
    EVIDENCE_REQUEST_SCHEMA_VERSION,
    FinancialResearchKernel,
    RetrievalContractError,
    load_evidence_request,
)
from retrieval.route_compiler import (
    QueryObjectFactRoutePolicy,
    compile_retrieval_execution_plan,
)

from sec_agent.providers.agent_protocol import AgentToolStepResult

from .current_consumer import (
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    validate_current_research_output,
)
from .finance_tool_contract import (
    CHAT_COMPLETIONS_WIRE,
    FINANCE_TOOL_NAMES,
    READ_NUMERIC_FACTS_TOOL,
    READ_REVIEWED_EVIDENCE_TOOL,
    SUBMIT_EVIDENCE_REQUEST_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    FinanceToolContract,
    compile_finance_tool_contract,
)
from .planning import ResearchPlanningPolicy
from .reviewed_evidence_pack import canonical_digest


BOUNDED_FINANCE_LOOP_POLICY_SCHEMA_VERSION = (
    "fin_ia_bounded_finance_agent_loop_policy_v1_1"
)
_LEGACY_BOUNDED_FINANCE_LOOP_POLICY_SCHEMA_VERSION = (
    "fin_ia_bounded_finance_agent_loop_policy_v1_0"
)
BOUNDED_FINANCE_LOOP_RESULT_SCHEMA_VERSION = (
    "fin_ia_bounded_finance_agent_loop_result_v1_0"
)

_DISALLOWED_SAMPLING_FIELDS = frozenset(
    {"temperature", "top_p", "presence_penalty", "frequency_penalty"}
)
_MODEL_TEXT_DIGITS = re.compile(r"[0-9０-９]")
_REPAIRABLE_EVIDENCE_REQUEST_CODES = frozenset(
    {
        "finance_loop_evidence_request_fields_invalid",
        "finance_loop_evidence_request_source_class_invalid",
        "finance_loop_evidence_request_facet_out_of_cell",
        "finance_loop_evidence_request_metrics_invalid",
        "finance_loop_evidence_request_intents_invalid",
        "finance_loop_evidence_request_intent_mode_mismatch",
        "finance_loop_evidence_request_forbidden_intent",
        "finance_loop_evidence_request_metric_family_mismatch",
        "finance_loop_evidence_request_route_not_executable",
    }
)


class BoundedFinanceLoopError(RuntimeError):
    """Fail-closed error at the four-tool financial research boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BoundedFinanceLoopError(code)


def _strings(
    value: object,
    code: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    rows = tuple(str(item).strip() for item in value)
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _parse_json_object(value: str, code: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError as exc:
        raise BoundedFinanceLoopError(code) from exc
    _require(isinstance(parsed, dict), code)
    return parsed


def _json_message(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _strict_object(
    properties: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class BoundedFinanceLoopPolicy:
    maximum_steps: int
    maximum_tool_calls: int
    maximum_no_progress_steps: int
    maximum_parallel_tool_calls: int
    maximum_calls_by_tool: Mapping[str, int]
    evidence_request_max_metric_intents: int
    evidence_request_max_product_intents: int
    evidence_request_max_product_intent_chars: int
    required_profile_defaults: Mapping[str, Any]
    authority: Mapping[str, bool]


@dataclass(frozen=True)
class BoundedFinanceLoopResult:
    status: str
    provider_id: str
    model: str
    selected_cell_ids: tuple[str, ...]
    step_count: int
    tool_call_count: int
    tool_counts: Mapping[str, int]
    proposed_evidence_requests: tuple[Mapping[str, Any], ...]
    judgment_output: Mapping[str, Any]
    structured_deliverable: Mapping[str, Any]
    step_receipts: tuple[Mapping[str, Any], ...]
    authority: Mapping[str, bool]

    def as_dict(self) -> dict[str, Any]:
        unsigned = {
            "schema_version": BOUNDED_FINANCE_LOOP_RESULT_SCHEMA_VERSION,
            "status": self.status,
            "provider_id": self.provider_id,
            "model": self.model,
            "selected_cell_ids": list(self.selected_cell_ids),
            "step_count": self.step_count,
            "tool_call_count": self.tool_call_count,
            "tool_counts": dict(self.tool_counts),
            "proposed_evidence_requests": [
                deepcopy(row) for row in self.proposed_evidence_requests
            ],
            "judgment_output": deepcopy(self.judgment_output),
            "structured_deliverable": deepcopy(
                self.structured_deliverable
            ),
            "step_receipts": [deepcopy(row) for row in self.step_receipts],
            "authority": dict(self.authority),
        }
        return {**unsigned, "result_digest": canonical_digest(unsigned)}


ToolStepExecutor = Callable[
    [Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]], int],
    AgentToolStepResult,
]
StepReceiptRecorder = Callable[[Mapping[str, Any]], None]


def scope_bounded_finance_loop_policy(
    policy: BoundedFinanceLoopPolicy,
    *,
    cell_count: int,
    maximum_evidence_requests: int,
) -> BoundedFinanceLoopPolicy:
    """Narrow the shared five-cell safety ceiling for one authorized run.

    Every selected cell may read Evidence once, read NumericFacts once and
    submit one Judgment.  EvidenceRequest remains optional and proposal-only.
    The scoped policy can only reduce the checked-in provider-neutral policy.
    """

    _require(1 <= cell_count <= 5, "finance_loop_scope_cell_count_invalid")
    _require(
        0 <= maximum_evidence_requests
        <= policy.maximum_calls_by_tool[SUBMIT_EVIDENCE_REQUEST_TOOL],
        "finance_loop_scope_evidence_request_budget_invalid",
    )
    per_tool = {
        READ_REVIEWED_EVIDENCE_TOOL: cell_count,
        READ_NUMERIC_FACTS_TOOL: cell_count,
        SUBMIT_EVIDENCE_REQUEST_TOOL: maximum_evidence_requests,
        SUBMIT_RESEARCH_JUDGMENT_TOOL: cell_count,
    }
    maximum_calls = sum(per_tool.values())
    _require(
        maximum_calls <= policy.maximum_tool_calls
        and maximum_calls <= policy.maximum_steps,
        "finance_loop_scope_exceeds_base_policy",
    )
    return replace(
        policy,
        maximum_steps=maximum_calls,
        maximum_tool_calls=maximum_calls,
        maximum_calls_by_tool=per_tool,
    )


def load_bounded_finance_loop_policy(
    payload: Mapping[str, Any],
) -> BoundedFinanceLoopPolicy:
    expected = {
        "schema_version",
        "status",
        "tool_names",
        "budgets",
        "evidence_request_limits",
        "required_profile_defaults",
        "authority",
    }
    _require(set(payload) == expected, "finance_loop_policy_fields_invalid")
    schema_version = str(payload.get("schema_version") or "")
    _require(
        schema_version
        in {
            _LEGACY_BOUNDED_FINANCE_LOOP_POLICY_SCHEMA_VERSION,
            BOUNDED_FINANCE_LOOP_POLICY_SCHEMA_VERSION,
        },
        "finance_loop_policy_schema_invalid",
    )
    _require(
        payload.get("status")
        == "provider_neutral_bounded_financial_research_loop",
        "finance_loop_policy_status_invalid",
    )
    tools = _strings(payload.get("tool_names"), "finance_loop_tools_invalid")
    _require(tools == FINANCE_TOOL_NAMES, "finance_loop_tools_invalid")
    budgets = payload.get("budgets")
    limits = payload.get("evidence_request_limits")
    defaults = payload.get("required_profile_defaults")
    authority = payload.get("authority")
    _require(
        isinstance(budgets, Mapping)
        and set(budgets)
        == {
            "maximum_steps",
            "maximum_tool_calls",
            "maximum_no_progress_steps",
            "maximum_parallel_tool_calls",
            "maximum_calls_by_tool",
        },
        "finance_loop_budgets_invalid",
    )
    raw_per_tool = budgets.get("maximum_calls_by_tool")
    _require(
        isinstance(raw_per_tool, Mapping)
        and set(raw_per_tool) == set(FINANCE_TOOL_NAMES),
        "finance_loop_budgets_invalid",
    )
    per_tool = {name: int(raw_per_tool[name]) for name in FINANCE_TOOL_NAMES}
    maximum_steps = int(budgets.get("maximum_steps") or 0)
    maximum_tool_calls = int(budgets.get("maximum_tool_calls") or 0)
    maximum_no_progress = int(
        budgets.get("maximum_no_progress_steps") or 0
    )
    maximum_parallel = int(budgets.get("maximum_parallel_tool_calls") or 0)
    _require(
        1 <= maximum_steps <= 64
        and 1 <= maximum_tool_calls <= 128
        and maximum_tool_calls <= sum(per_tool.values())
        and 1 <= maximum_no_progress <= 4
        and maximum_parallel
        == (
            2
            if schema_version == BOUNDED_FINANCE_LOOP_POLICY_SCHEMA_VERSION
            else 1
        )
        and all(1 <= value <= 64 for value in per_tool.values()),
        "finance_loop_budgets_invalid",
    )
    _require(
        isinstance(limits, Mapping)
        and set(limits)
        == {
            "maximum_metric_intents",
            "maximum_product_intents",
            "maximum_product_intent_chars",
        },
        "finance_loop_request_limits_invalid",
    )
    metric_limit = int(limits.get("maximum_metric_intents") or 0)
    product_limit = int(limits.get("maximum_product_intents") or 0)
    product_chars = int(limits.get("maximum_product_intent_chars") or 0)
    _require(
        1 <= metric_limit <= 6
        and 1 <= product_limit <= 4
        and 12 <= product_chars <= 120,
        "finance_loop_request_limits_invalid",
    )
    _require(
        isinstance(defaults, Mapping)
        and set(defaults)
        == {"stream", "thinking", "reasoning_effort"}
        and defaults.get("stream") is False
        and defaults.get("thinking") == {"type": "enabled"}
        and defaults.get("reasoning_effort") == "max",
        "finance_loop_profile_defaults_invalid",
    )
    required_authority = {
        "reviewed_evidence_only": True,
        "numeric_fact_only": True,
        "evidence_request_is_proposal_only": True,
        "evidence_request_does_not_execute_retrieval": True,
        "gap_remains_open_after_evidence_request": True,
        "judgment_requires_local_validation": True,
        "candidate_cannot_become_evidence": True,
        "harness_owns_identity_date_numeric_citation_rendering": True,
        "private_reasoning_persistence_forbidden": True,
    }
    _require(
        isinstance(authority, Mapping)
        and dict(authority) == required_authority,
        "finance_loop_authority_invalid",
    )
    return BoundedFinanceLoopPolicy(
        maximum_steps=maximum_steps,
        maximum_tool_calls=maximum_tool_calls,
        maximum_no_progress_steps=maximum_no_progress,
        maximum_parallel_tool_calls=maximum_parallel,
        maximum_calls_by_tool=per_tool,
        evidence_request_max_metric_intents=metric_limit,
        evidence_request_max_product_intents=product_limit,
        evidence_request_max_product_intent_chars=product_chars,
        required_profile_defaults=dict(defaults),
        authority=dict(authority),
    )


def validate_deepseek_ga_profile(
    profile: object,
    *,
    strict_tools: bool,
) -> None:
    """Qualify only the replaceable DeepSeek wire profile, not finance truth."""

    base_url = str(getattr(profile, "base_url", "") or "").rstrip("/")
    defaults = dict(getattr(profile, "request_defaults", {}) or {})
    _require(
        str(getattr(profile, "provider_id", "")) == "deepseek"
        and str(getattr(profile, "model", "")) == "deepseek-v4-pro"
        and str(getattr(profile, "endpoint", "")) == "/chat/completions",
        "finance_loop_deepseek_ga_profile_identity_invalid",
    )
    _require(
        base_url
        == (
            "https://api.deepseek.com/beta"
            if strict_tools
            else "https://api.deepseek.com"
        ),
        "finance_loop_deepseek_ga_profile_endpoint_invalid",
    )
    _require(
        not set(defaults).intersection(_DISALLOWED_SAMPLING_FIELDS)
        and defaults.get("stream") is False
        and defaults.get("thinking") == {"type": "enabled"}
        and defaults.get("reasoning_effort") == "max"
        and isinstance(defaults.get("max_tokens"), int)
        and 1 <= int(defaults["max_tokens"]) <= 384_000
        and "response_format" not in defaults,
        "finance_loop_deepseek_ga_profile_defaults_invalid",
    )


def validate_deepseek_ga_json_profile(profile: object) -> None:
    """Qualify the GA JSON-control lane without leaking it into core logic."""

    base_url = str(getattr(profile, "base_url", "") or "").rstrip("/")
    defaults = dict(getattr(profile, "request_defaults", {}) or {})
    _require(
        str(getattr(profile, "provider_id", "")) == "deepseek"
        and str(getattr(profile, "model", "")) == "deepseek-v4-pro"
        and str(getattr(profile, "endpoint", "")) == "/chat/completions",
        "finance_loop_deepseek_ga_json_profile_identity_invalid",
    )
    _require(
        base_url == "https://api.deepseek.com",
        "finance_loop_deepseek_ga_json_profile_endpoint_invalid",
    )
    _require(
        not set(defaults).intersection(_DISALLOWED_SAMPLING_FIELDS)
        and defaults.get("stream") is False
        and defaults.get("thinking") == {"type": "enabled"}
        and defaults.get("reasoning_effort") == "max"
        and isinstance(defaults.get("max_tokens"), int)
        and 1 <= int(defaults["max_tokens"]) <= 384_000
        and defaults.get("response_format") == {"type": "json_object"},
        "finance_loop_deepseek_ga_json_profile_defaults_invalid",
    )


def _selected_cells(
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
) -> tuple[Mapping[str, Any], ...]:
    requested = tuple(str(value) for value in required_cell_ids)
    all_cells = {
        str(row["cell_id"]): row for row in research_input["cells"]
    }
    _require(
        bool(requested)
        and len(requested) == len(set(requested))
        and set(requested).issubset(all_cells),
        "finance_loop_cell_scope_invalid",
    )
    return tuple(all_cells[cell_id] for cell_id in requested)


def _judgment_parameters(
    *,
    cell_ids: Sequence[str],
    evidence_refs: Sequence[str],
    numeric_refs: Sequence[str],
    numeric_relation_refs: Sequence[str],
    method_step_refs: Sequence[str],
    graph_edge_refs: Sequence[str],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_use = _strict_object(
        {
            "evidence_ref": {
                "type": "string",
                "enum": list(evidence_refs),
                "description": "Reviewed Evidence ref allowed in this run.",
            },
            "use_role": {
                "type": "string",
                "enum": list(contract["allowed_evidence_use_roles"]),
            },
        }
    )
    threshold_values = ["", *numeric_refs]
    numeric_item: dict[str, Any] = (
        {"type": "string", "enum": list(numeric_refs)}
        if numeric_refs
        else {
            "type": "string",
            "pattern": "^$",
            "description": "No NumericFact is available; the array must stay empty.",
        }
    )

    def ref_array(refs: Sequence[str], *, description: str) -> dict[str, Any]:
        item: dict[str, Any] = (
            {"type": "string", "enum": list(refs)}
            if refs
            else {"type": "string", "pattern": "^$"}
        )
        schema = {
            "type": "array",
            "items": item,
            "uniqueItems": True,
            "description": description,
        }
        if not refs:
            schema["maxItems"] = 0
        return schema
    wwc = _strict_object(
        {
            "observable": {
                "type": "string",
                "description": "Observable variable without digits or refs.",
            },
            "direction": {
                "type": "string",
                "enum": list(contract["allowed_wwc_directions"]),
            },
            "time_horizon": {
                "type": "string",
                "description": "Bounded non-numeric horizon.",
            },
            "evidence_route": {
                "type": "string",
                "description": "Where to verify without URL or citation.",
            },
            "threshold_numeric_ref": {
                "type": "string",
                "enum": threshold_values,
                "description": "Allowed NumericFact ref or empty string.",
            },
        }
    )
    properties = {
            "cell_id": {"type": "string", "enum": list(cell_ids)},
            "judgment_status": {
                "type": "string",
                "enum": list(contract["allowed_judgment_statuses"]),
            },
            "confidence_basis": {
                "type": "string",
                "enum": list(contract["allowed_confidence_bases"]),
            },
            "inference_authority": {
                "type": "string",
                "enum": list(contract["allowed_inference_authorities"]),
            },
            **(
                {
                    "claim_scope": {
                        "type": "string",
                        "enum": list(contract["allowed_claim_scopes"]),
                    },
                    "financial_scope": {
                        "type": "string",
                        "enum": list(contract["allowed_financial_scopes"]),
                    },
                    "causal_bridge_authority": {
                        "type": "string",
                        "enum": list(
                            contract["allowed_causal_bridge_authorities"]
                        ),
                    },
                }
                if "allowed_claim_scopes" in contract
                else {}
            ),
            "evidence_uses": {"type": "array", "items": evidence_use},
            "numeric_refs": {
                "type": "array",
                "items": numeric_item,
                **({"maxItems": 0} if not numeric_refs else {}),
            },
            "numeric_relation_refs": ref_array(
                numeric_relation_refs,
                description="Same-basis numeric relations actually used.",
            ),
            "method_step_refs": ref_array(
                method_step_refs,
                description="Injected RoleMethodPack steps actually used.",
            ),
            "graph_edge_refs": ref_array(
                graph_edge_refs,
                description="Current GraphContextPack edges actually used.",
            ),
            "thesis_atom": {
                "type": "string",
                "description": "Company-specific conclusion without digits or refs.",
            },
            "mechanism_atom": {
                "type": "string",
                "description": "Economic mechanism without digits or refs.",
            },
            "counterargument_atom": {
                "type": "string",
                "description": "Strongest bounded alternative without digits or refs.",
            },
            "what_would_change": wwc,
        }
    return _strict_object(properties)


def compile_finance_loop_tools(
    *,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    policy: BoundedFinanceLoopPolicy,
    strict: bool,
) -> tuple[dict[str, Any], ...]:
    return compile_finance_loop_tool_contract(
        research_input=research_input,
        required_cell_ids=required_cell_ids,
        kernel=kernel,
        route_policy=route_policy,
        policy=policy,
        strict=strict,
    ).project(CHAT_COMPLETIONS_WIRE)


def compile_finance_loop_tool_contract(
    *,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    policy: BoundedFinanceLoopPolicy,
    strict: bool,
) -> FinanceToolContract:
    cells = _selected_cells(research_input, required_cell_ids)
    cell_ids = [str(row["cell_id"]) for row in cells]
    evidence_refs = sorted(
        {str(ref) for row in cells for ref in row["allowed_evidence_refs"]}
    )
    numeric_refs = sorted(
        {str(ref) for row in cells for ref in row["allowed_numeric_refs"]}
    )
    numeric_relation_refs = sorted(
        {
            str(ref)
            for row in cells
            for ref in row["allowed_numeric_relation_refs"]
        }
    )
    method_step_refs = sorted(
        {
            str(step["method_step_ref"])
            for row in cells
            for step in (row.get("role_method_pack") or {}).get(
                "method_steps", ()
            )
        }
    )
    graph_edge_refs = sorted(
        {
            str(edge["graph_edge_ref"])
            for row in cells
            for edge in row["graph_context_pack"]["edges"]
        }
    )
    return compile_finance_tool_contract(
        research_input=research_input,
        selected_cells=cells,
        kernel=kernel,
        route_policy=route_policy,
        judgment_schema=_judgment_parameters(
            cell_ids=cell_ids,
            evidence_refs=evidence_refs,
            numeric_refs=numeric_refs,
            numeric_relation_refs=numeric_relation_refs,
            method_step_refs=method_step_refs,
            graph_edge_refs=graph_edge_refs,
            contract=research_input["model_output_contract"],
        ),
        maximum_metric_intents=policy.evidence_request_max_metric_intents,
        maximum_product_intents=policy.evidence_request_max_product_intents,
        maximum_product_intent_chars=(
            policy.evidence_request_max_product_intent_chars
        ),
        strict=strict,
    )


def compile_finance_judgment_tool(
    *,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
    strict: bool,
) -> dict[str, Any]:
    """Compile the legacy paired lane's final tool without proposal surfaces."""

    cells = _selected_cells(research_input, required_cell_ids)
    function: dict[str, Any] = {
        "name": SUBMIT_RESEARCH_JUDGMENT_TOOL,
        "description": (
            "Submit one provider-neutral v1.2 judgment for local validation and rendering."
        ),
        "parameters": _judgment_parameters(
            cell_ids=[str(row["cell_id"]) for row in cells],
            evidence_refs=sorted(
                {str(ref) for row in cells for ref in row["allowed_evidence_refs"]}
            ),
            numeric_refs=sorted(
                {str(ref) for row in cells for ref in row["allowed_numeric_refs"]}
            ),
            numeric_relation_refs=sorted(
                {
                    str(ref)
                    for row in cells
                    for ref in row["allowed_numeric_relation_refs"]
                }
            ),
            method_step_refs=sorted(
                {
                    str(step["method_step_ref"])
                    for row in cells
                    for step in (row.get("role_method_pack") or {}).get(
                        "method_steps", ()
                    )
                }
            ),
            graph_edge_refs=sorted(
                {
                    str(edge["graph_edge_ref"])
                    for row in cells
                    for edge in row["graph_context_pack"]["edges"]
                }
            ),
            contract=research_input["model_output_contract"],
        ),
    }
    if strict:
        function["strict"] = True
    return {"type": "function", "function": function}


def compile_finance_loop_messages(
    *,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
    execution_budget: Mapping[str, int] | None = None,
) -> tuple[dict[str, str], ...]:
    cells = _selected_cells(research_input, required_cell_ids)
    route_decisions = {
        str(row["gap_ref"]): row
        for row in research_input["evidence_request_route_catalog"][
            "gap_route_decisions"
        ]
    }
    visible = {
        "case_identity": deepcopy(research_input["case_identity"]),
        "research_question": research_input["objective"]["raw_question"],
        "required_cells": [
            {
                "cell_id": row["cell_id"],
                "title_zh": row["title_zh"],
                "research_intents": sorted(
                    {
                        intent
                        for atom in row["planner_atoms"]
                        for intent in atom.get("product_intents", ())
                    }
                ),
                "visible_gap_refs": list(row["visible_gap_refs"]),
                "allowed_numeric_relation_refs": list(
                    row["allowed_numeric_relation_refs"]
                ),
                "role_method_pack": deepcopy(row.get("role_method_pack")),
                "graph_context_pack": deepcopy(row["graph_context_pack"]),
                "context_consumption_contract": deepcopy(
                    row["context_consumption_contract"]
                ),
                **(
                    {
                        "claim_authority_card": deepcopy(
                            row["claim_authority_card"]
                        )
                    }
                    if "claim_authority_card" in row
                    else {}
                ),
                "gap_route_decisions": [
                    deepcopy(route_decisions[str(ref)])
                    for ref in row["visible_gap_refs"]
                ],
            }
            for row in cells
        ],
        "research_context_injection_receipt": deepcopy(
            research_input["research_context_receipts"]
        ),
        "workflow": [
            (
                "Before submitting each cell Judgment, call both the reviewed "
                "Evidence reader and the NumericFact reader for that same cell."
            ),
            (
                "Those two read-only calls may be issued together for the same "
                "cell; never combine, duplicate or parallelize any other tools."
            ),
            "Submit an EvidenceRequest only for a material visible gap whose route_decision is requestable_on_current_runtime; it remains open in this run.",
            "Submit exactly one locally valid judgment per required cell.",
        ],
        "boundaries": [
            "Never treat a retrieval proposal, model memory or gap as Evidence.",
            "Use reviewed Evidence for claims and NumericFacts for exact values.",
            "Do not write digits, units, dates, citations or refs inside prose atoms.",
            "The harness renders identity, exact numbers, periods, units and citations.",
            "Explicit year-over-year language requires one same-basis NumericRelation and both endpoint NumericFacts.",
            "Cite the injected method steps and current graph edges actually used; graph context never grants fact or causal authority.",
        ],
    }
    if "claim_authority_contract" in research_input:
        visible["claim_authority_contract"] = deepcopy(
            research_input["claim_authority_contract"]
        )
        visible["boundaries"].extend(
            [
                "Declare claim scope, financial scope and causal bridge authority using the cell ClaimAuthorityCard.",
                "A management assertion is not an audited product-to-company bridge; multi-driver context does not allocate profit to one product.",
                "This fixed-pack unit test performs no retrieval and is not Agentic Research.",
            ]
        )
    if execution_budget is not None:
        expected_budget = {
            "maximum_steps",
            "maximum_evidence_requests",
            "maximum_reads_per_cell",
            "maximum_parallel_read_tools",
            "maximum_judgments_per_cell",
            "retry_count",
        }
        _require(
            set(execution_budget) == expected_budget
            and all(
                isinstance(execution_budget[key], int)
                for key in expected_budget
            )
            and execution_budget["maximum_steps"] >= 3 * len(cells)
            and execution_budget["maximum_evidence_requests"] >= 0
            and execution_budget["maximum_reads_per_cell"] == 1
            and execution_budget["maximum_parallel_read_tools"] == 2
            and execution_budget["maximum_judgments_per_cell"] == 1
            and execution_budget["retry_count"] == 0,
            "finance_loop_visible_execution_budget_invalid",
        )
        visible["execution_budget"] = dict(execution_budget)
    return (
        {
            "role": "system",
            "content": (
                "You are a bounded financial research analyst. Use only the four "
                "provided tools. Preserve evidence boundaries, limiting evidence "
                "and unresolved gaps; never convert correlation into causation."
            ),
        },
        {"role": "user", "content": _json_message(visible)},
    )


def _evidence_tool_result(
    *,
    research_input: Mapping[str, Any],
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    cards = {
        str(row["evidence_ref"]): row for row in research_input["evidence_cards"]
    }
    slot_ids = {
        str(cell["primary_slot_id"]),
        *(str(value) for value in cell["supplemental_context_slot_ids"]),
    }
    output = []
    maximum = int(research_input["model_input_contract"]["maximum_evidence_excerpt_chars"])
    for ref in cell["allowed_evidence_refs"]:
        row = cards[str(ref)]
        bindings = [
            binding
            for binding in row["slot_bindings"]
            if str(binding["slot_id"]) in slot_ids
        ]
        output.append(
            {
                "evidence_ref": ref,
                "evidence_owner_ticker": row["evidence_owner_ticker"],
                "source_type": row["source_type"],
                "source_tier": row["source_tier"],
                "publication_date": row["publication_date"],
                "source_reporting_period_end": row["source_reporting_period_end"],
                "relationship_directions": deepcopy(row["relationship_directions"]),
                "source_visible_fact_excerpt": str(
                    row["source_visible_fact_excerpt"]
                )[:maximum],
                "business_meanings_zh": [
                    binding["business_meaning_zh"] for binding in bindings
                ],
                "claim_boundaries_zh": [
                    binding["claim_boundary_zh"] for binding in bindings
                ],
                "numeric_use_boundary": row["numeric_use_boundary"],
            }
        )
    gaps = {
        str(row["gap_ref"]): row for row in research_input["residual_gap_cards"]
    }
    return {
        "status": "reviewed_evidence_read",
        "cell_id": cell["cell_id"],
        "evidence": output,
        "residual_gaps": [deepcopy(gaps[str(ref)]) for ref in cell["visible_gap_refs"]],
        "role_method_pack": deepcopy(cell.get("role_method_pack")),
        "graph_context_pack": deepcopy(cell["graph_context_pack"]),
        **(
            {"claim_authority_card": deepcopy(cell["claim_authority_card"])}
            if "claim_authority_card" in cell
            else {}
        ),
        "candidate_or_rejected_item_included": False,
    }


def _numeric_tool_result(
    *,
    research_input: Mapping[str, Any],
    cell: Mapping[str, Any],
) -> dict[str, Any]:
    cards = {
        str(row["numeric_ref"]): row
        for row in research_input["numeric_fact_cards"]
    }
    relations = {
        str(row["numeric_relation_ref"]): row
        for row in research_input["numeric_relation_cards"]
    }
    return {
        "status": "authoritative_numeric_facts_read",
        "cell_id": cell["cell_id"],
        "numeric_facts": [deepcopy(cards[str(ref)]) for ref in cell["allowed_numeric_refs"]],
        "same_basis_numeric_relations": [
            deepcopy(relations[str(ref)])
            for ref in cell["allowed_numeric_relation_refs"]
        ],
        "model_generated_numeric_authority": False,
    }


def _compile_proposed_evidence_request(
    *,
    arguments: Mapping[str, Any],
    research_input: Mapping[str, Any],
    cell: Mapping[str, Any],
    tool_contract: FinanceToolContract,
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    planning_policy: ResearchPlanningPolicy,
) -> dict[str, Any]:
    expected = {
        "cell_id",
        "gap_ref",
        "target_entity",
        "requested_facet_id",
        "requested_source_class",
        "metric_intents",
        "product_intents",
    }
    _require(
        set(arguments) == expected
        and str(arguments.get("cell_id")) == str(cell["cell_id"]),
        "finance_loop_evidence_request_fields_invalid",
    )
    gap_ref = str(arguments.get("gap_ref") or "")
    facet_id = str(arguments.get("requested_facet_id") or "")
    source_class = str(arguments.get("requested_source_class") or "")
    target_entity = str(arguments.get("target_entity") or "").upper()
    _require(
        gap_ref in set(cell["visible_gap_refs"]),
        "finance_loop_evidence_request_gap_out_of_cell",
    )
    branch = tool_contract.branch_for(
        cell_id=str(cell["cell_id"]),
        facet_id=facet_id,
        gap_ref=gap_ref,
        source_class=source_class,
    )
    _require(
        branch is not None,
        "finance_loop_evidence_request_source_class_invalid",
    )
    assert branch is not None
    _require(
        target_entity in branch.target_entities,
        "finance_loop_evidence_request_target_out_of_scope",
    )
    metrics = _strings(
        arguments.get("metric_intents"),
        "finance_loop_evidence_request_metrics_invalid",
        allow_empty=True,
    )
    intents = _strings(
        arguments.get("product_intents"),
        "finance_loop_evidence_request_intents_invalid",
        allow_empty=True,
    )
    _require(
        len(metrics) <= tool_contract.maximum_metric_intents
        and len(intents) <= tool_contract.maximum_product_intents
        and all(
            len(value) <= tool_contract.maximum_product_intent_chars
            and not _MODEL_TEXT_DIGITS.search(value)
            and "http://" not in value.casefold()
            and "https://" not in value.casefold()
            and "::" not in value
            for value in intents
        ),
        "finance_loop_evidence_request_intents_invalid",
    )
    if branch.intent_mode == "metric_intent_required_product_intent_forbidden":
        _require(
            bool(metrics) and not intents,
            "finance_loop_evidence_request_intent_mode_mismatch",
        )
    else:
        _require(
            bool(intents),
            "finance_loop_evidence_request_intent_mode_mismatch",
        )
    folded_intents = " ".join(intents).casefold()
    _require(
        not any(
            forbidden.casefold() in folded_intents
            for forbidden in branch.forbidden_intent_terms
        ),
        "finance_loop_evidence_request_forbidden_intent",
    )
    family = route_policy.family_by_facet().get(facet_id)
    _require(family is not None, "finance_loop_evidence_request_facet_unrouted")
    binding = planning_policy.binding_by_family().get(family.family_id)
    _require(binding is not None, "finance_loop_evidence_request_family_unbound")
    _require(
        all(metric_id in branch.metric_ids for metric_id in metrics),
        "finance_loop_evidence_request_metric_family_mismatch",
    )
    slot = next(
        slot
        for slot in kernel.slots
        if any(facet.facet_id == facet_id for facet in slot.facets)
    )
    objective = research_input["objective"]
    acceptable_sources = [
        source
        for source in branch.acceptable_source_types
        if source in slot.source_types
        and source in objective["allowed_source_types"]
        and source not in objective["forbidden_source_types"]
    ]
    _require(
        bool(acceptable_sources),
        "finance_loop_evidence_request_no_acceptable_source",
    )
    identity = {
        "research_input_digest": research_input["research_input_digest"],
        "cell_id": cell["cell_id"],
        "gap_ref": gap_ref,
        "target_entity": target_entity,
        "facet_id": facet_id,
        "source_class": source_class,
        "metrics": metrics,
        "intents": intents,
    }
    request_id = f"REQ::{canonical_digest(identity)[:24]}"
    payload = {
        "schema_version": EVIDENCE_REQUEST_SCHEMA_VERSION,
        "request_id": request_id,
        "cell_id": f"CELLREQ::{canonical_digest(identity)[:24]}",
        "requester_role": binding.requester_role,
        "evidence_domain": binding.evidence_domain,
        "case_key": objective["case_key"],
        "subject_ticker": objective["subject_ticker"],
        "research_as_of": objective["research_as_of"],
        "target_entities": [target_entity],
        "requested_facet_ids": [facet_id],
        "metric_intents": list(metrics),
        "product_intents": list(intents),
        "period": deepcopy(objective["period"]),
        "granularity": planning_policy.defaults["granularity"],
        "unit": planning_policy.defaults["unit"],
        "acceptable_sources": acceptable_sources,
        "acceptable_proxy": False,
        "forbidden_proxy": list(planning_policy.forbidden_proxy),
        "stop_condition": planning_policy.defaults["stop_condition"],
        "clarification_policy": objective["gap_policy"],
    }
    try:
        request = load_evidence_request(payload, kernel)
        compiled = request.as_dict()
        execution_plan = compile_retrieval_execution_plan(
            route_policy,
            request,
            fact_store_availability={
                "company_financial_fact_mart": True,
                "market_snapshot_fact_mart": False,
            },
        )
    except RetrievalContractError as exc:
        raise BoundedFinanceLoopError(
            f"finance_loop_evidence_request_invalid:{exc}"
        ) from exc
    narrative_routes = sorted(
        {
            route_id
            for row in execution_plan.narrative_requests
            for route_id in row.candidate_routes
            if route_id in branch.executable_route_ids
        }
    )
    ready_fact_requests = [
        row.as_dict()
        for row in execution_plan.typed_fact_requests
        if row.execution_status == "ready_for_typed_fact_executor"
    ]
    if source_class == "typed_company_financial_fact":
        _require(
            bool(ready_fact_requests),
            "finance_loop_evidence_request_route_not_executable",
        )
        selected_route_ids = list(branch.executable_route_ids)
    else:
        _require(
            bool(narrative_routes),
            "finance_loop_evidence_request_route_not_executable",
        )
        selected_route_ids = narrative_routes
    return {
        "status": "recorded_not_executed",
        "research_cell_id": cell["cell_id"],
        "gap_ref": gap_ref,
        "gap_status": "open",
        "requested_source_class": source_class,
        "compiled_evidence_request": compiled,
        "compiled_route_projection": {
            "execution_plan_digest": execution_plan.plan_digest,
            "selected_executable_route_ids": selected_route_ids,
            "ready_typed_fact_requests": ready_fact_requests,
            "narrative_route_request_ids": [
                row.route_request_id
                for row in execution_plan.narrative_requests
                if any(
                    route_id in branch.executable_route_ids
                    for route_id in row.candidate_routes
                )
            ],
        },
        "retrieval_executed": False,
        "candidate_promoted_to_evidence": False,
        "numeric_fact_created": False,
    }


def _rejected_evidence_request_result(
    *,
    code: str,
    arguments: Mapping[str, Any],
    cell_id: str,
    tool_contract: FinanceToolContract,
) -> dict[str, Any]:
    return {
        "status": "rejected_not_executed",
        "failure_code": code,
        "repairable": True,
        "research_cell_id": cell_id,
        "gap_ref": str(arguments.get("gap_ref") or ""),
        "gap_status": "open",
        "attempted_arguments_digest": canonical_digest(arguments),
        "repair_contract": tool_contract.repair_surface_for_cell(cell_id),
        "retrieval_executed": False,
        "candidate_promoted_to_evidence": False,
        "numeric_fact_created": False,
    }


def _receipt(
    *,
    step: AgentToolStepResult,
    step_index: int,
    receipt_sequence: int,
    tool_name: str,
    tool_call_id: str,
    tool_result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "receipt_sequence": receipt_sequence,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "tool_result_digest": canonical_digest(tool_result),
        "provider_step": step.as_dict(),
        "private_reasoning_persisted": False,
    }


def run_bounded_finance_loop(
    *,
    policy: BoundedFinanceLoopPolicy,
    research_input: Mapping[str, Any],
    required_cell_ids: Sequence[str],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    planning_policy: ResearchPlanningPolicy,
    tools: Sequence[Mapping[str, Any]],
    step_executor: ToolStepExecutor,
    receipt_recorder: StepReceiptRecorder | None = None,
    visible_execution_budget: Mapping[str, int] | None = None,
) -> BoundedFinanceLoopResult:
    """Run an exact bounded loop; no tool can create trusted financial truth."""

    cells = _selected_cells(research_input, required_cell_ids)
    cell_by_id = {str(row["cell_id"]): row for row in cells}
    strict_values = {
        bool(row.get("function", {}).get("strict"))
        for row in tools
        if isinstance(row, Mapping)
    }
    _require(
        len(strict_values) == 1,
        "finance_loop_tool_definition_strict_mode_invalid",
    )
    strict_mode = next(iter(strict_values))
    tool_contract = compile_finance_loop_tool_contract(
        research_input=research_input,
        required_cell_ids=required_cell_ids,
        kernel=kernel,
        route_policy=route_policy,
        policy=policy,
        strict=strict_mode,
    )
    expected_tool_definitions = tool_contract.project(CHAT_COMPLETIONS_WIRE)
    _require(
        canonical_digest(list(tools))
        == canonical_digest(list(expected_tool_definitions)),
        "finance_loop_tool_definition_contract_drift",
    )
    expected_tools = {str(row["function"]["name"]) for row in tools}
    _require(
        expected_tools == set(FINANCE_TOOL_NAMES),
        "finance_loop_tool_definition_set_invalid",
    )
    messages: list[dict[str, Any]] = [
        dict(row)
        for row in compile_finance_loop_messages(
            research_input=research_input,
            required_cell_ids=required_cell_ids,
            execution_budget=visible_execution_budget,
        )
    ]
    counts: Counter[str] = Counter()
    no_progress = 0
    seen_calls: set[str] = set()
    seen_call_ids: set[str] = set()
    proposed_requests: list[dict[str, Any]] = []
    judgments: dict[str, dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    evidence_reads: set[str] = set()
    numeric_reads: set[str] = set()
    provider_id = ""
    model = ""

    for step_index in range(1, policy.maximum_steps + 1):
        step = step_executor(messages, tools, step_index)
        provider_id = step.provider_id
        model = step.model
        _require(
            len(step.tool_calls) <= policy.maximum_parallel_tool_calls,
            "finance_loop_parallel_tool_calls_exceeded",
        )
        _require(
            bool(step.tool_calls),
            "finance_loop_step_without_tool_call",
        )
        parsed_calls: list[
            tuple[Mapping[str, Any], str, str, dict[str, Any], str, bool]
        ] = []
        batch_names: list[str] = []
        batch_ids: list[str] = []
        for call in step.tool_calls:
            name = str(call["function"]["name"])
            call_id = str(call["id"])
            _require(name in expected_tools, "finance_loop_tool_unknown")
            _require(
                bool(call_id)
                and call_id not in seen_call_ids
                and call_id not in batch_ids,
                "finance_loop_tool_call_id_duplicate",
            )
            arguments = _parse_json_object(
                str(call["function"]["arguments"]),
                "finance_loop_tool_arguments_invalid_json",
            )
            signature = canonical_digest(
                {"name": name, "arguments": arguments}
            )
            parsed_calls.append(
                (
                    call,
                    name,
                    call_id,
                    arguments,
                    signature,
                    signature in seen_calls,
                )
            )
            batch_names.append(name)
            batch_ids.append(call_id)

        if len(parsed_calls) == 2:
            _require(
                set(batch_names)
                == {READ_REVIEWED_EVIDENCE_TOOL, READ_NUMERIC_FACTS_TOOL},
                "finance_loop_parallel_tool_set_invalid",
            )
            read_cells = []
            for _, _, _, arguments, _, _ in parsed_calls:
                _require(
                    set(arguments) == {"cell_id"}
                    and str(arguments.get("cell_id")) in cell_by_id,
                    "finance_loop_read_scope_invalid",
                )
                read_cells.append(str(arguments["cell_id"]))
            _require(
                len(set(read_cells)) == 1,
                "finance_loop_parallel_read_cell_mismatch",
            )

        batch_counts = Counter(batch_names)
        _require(
            sum(counts.values()) + len(parsed_calls)
            <= policy.maximum_tool_calls
            and all(
                counts[name] + increment
                <= policy.maximum_calls_by_tool[name]
                for name, increment in batch_counts.items()
            ),
            "finance_loop_tool_budget_exceeded",
        )
        counts.update(batch_counts)
        seen_call_ids.update(batch_ids)
        step_progress = False
        tool_messages: list[dict[str, Any]] = []

        for _, name, call_id, arguments, signature, duplicate in parsed_calls:
            seen_calls.add(signature)
            progress = False

            if name in {
                READ_REVIEWED_EVIDENCE_TOOL,
                READ_NUMERIC_FACTS_TOOL,
            }:
                _require(
                    set(arguments) == {"cell_id"}
                    and str(arguments.get("cell_id")) in cell_by_id,
                    "finance_loop_read_scope_invalid",
                )
                cell = cell_by_id[str(arguments["cell_id"])]
                tool_result = (
                    _evidence_tool_result(
                        research_input=research_input,
                        cell=cell,
                    )
                    if name == READ_REVIEWED_EVIDENCE_TOOL
                    else _numeric_tool_result(
                        research_input=research_input,
                        cell=cell,
                    )
                )
                if name == READ_REVIEWED_EVIDENCE_TOOL:
                    evidence_reads.add(str(arguments["cell_id"]))
                else:
                    numeric_reads.add(str(arguments["cell_id"]))
                progress = not duplicate
            elif name == SUBMIT_EVIDENCE_REQUEST_TOOL:
                cell_id = str(arguments.get("cell_id") or "")
                _require(
                    cell_id in cell_by_id,
                    "finance_loop_evidence_request_cell_invalid",
                )
                try:
                    tool_result = _compile_proposed_evidence_request(
                        arguments=arguments,
                        research_input=research_input,
                        cell=cell_by_id[cell_id],
                        tool_contract=tool_contract,
                        kernel=kernel,
                        route_policy=route_policy,
                        planning_policy=planning_policy,
                    )
                except BoundedFinanceLoopError as exc:
                    if exc.code not in _REPAIRABLE_EVIDENCE_REQUEST_CODES:
                        raise
                    tool_result = _rejected_evidence_request_result(
                        code=exc.code,
                        arguments=arguments,
                        cell_id=cell_id,
                        tool_contract=tool_contract,
                    )
                if tool_result["status"] == "recorded_not_executed":
                    proposal_digest = canonical_digest(
                        tool_result["compiled_evidence_request"]
                    )
                    if proposal_digest not in {
                        canonical_digest(row["compiled_evidence_request"])
                        for row in proposed_requests
                    }:
                        proposed_requests.append(tool_result)
                        progress = True
            else:
                cell_id = str(arguments.get("cell_id") or "")
                _require(
                    cell_id in cell_by_id and cell_id not in judgments,
                    "finance_loop_judgment_cell_invalid_or_duplicate",
                )
                _require(
                    cell_id in evidence_reads and cell_id in numeric_reads,
                    "finance_loop_required_cell_reads_incomplete",
                )
                normalized = deepcopy(arguments)
                threshold = normalized.get("what_would_change", {}).get(
                    "threshold_numeric_ref"
                )
                if threshold == "":
                    normalized["what_would_change"][
                        "threshold_numeric_ref"
                    ] = None
                try:
                    validated = validate_current_research_output(
                        {"cells": [normalized]},
                        research_input=research_input,
                        required_cell_ids=[cell_id],
                    )
                except CurrentResearchConsumerError as exc:
                    raise BoundedFinanceLoopError(
                        f"finance_loop_judgment_invalid:{exc.code}"
                    ) from exc
                judgments[cell_id] = normalized
                tool_result = {
                    "status": "judgment_accepted_by_local_validator",
                    "cell_id": cell_id,
                    "judgment_output_digest": validated[
                        "judgment_output_digest"
                    ],
                    "harness_rendered_identity_numeric_and_citations": True,
                }
                progress = True

            step_progress = step_progress or progress
            receipt = _receipt(
                step=step,
                step_index=step_index,
                receipt_sequence=len(receipts) + 1,
                tool_name=name,
                tool_call_id=call_id,
                tool_result=tool_result,
            )
            receipts.append(receipt)
            if receipt_recorder is not None:
                receipt_recorder(deepcopy(receipt))
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": _json_message(tool_result),
                }
            )

        no_progress = 0 if step_progress else no_progress + 1
        _require(
            no_progress < policy.maximum_no_progress_steps,
            "finance_loop_no_progress_stop",
        )
        messages.append(step.continuation_assistant_message())
        messages.extend(tool_messages)
        if set(judgments) == set(cell_by_id):
            ordered = [judgments[cell_id] for cell_id in required_cell_ids]
            judgment_output = {"cells": ordered}
            deliverable = compile_current_research_deliverable(
                research_input=research_input,
                judgment_output=judgment_output,
                required_cell_ids=required_cell_ids,
            )
            return BoundedFinanceLoopResult(
                status="completed_all_required_cells",
                provider_id=provider_id,
                model=model,
                selected_cell_ids=tuple(required_cell_ids),
                step_count=step_index,
                tool_call_count=sum(counts.values()),
                tool_counts=dict(counts),
                proposed_evidence_requests=tuple(proposed_requests),
                judgment_output=judgment_output,
                structured_deliverable=deliverable,
                step_receipts=tuple(receipts),
                authority=policy.authority,
            )

    raise BoundedFinanceLoopError("finance_loop_step_budget_exhausted")


__all__ = [
    "BOUNDED_FINANCE_LOOP_POLICY_SCHEMA_VERSION",
    "BOUNDED_FINANCE_LOOP_RESULT_SCHEMA_VERSION",
    "BoundedFinanceLoopError",
    "BoundedFinanceLoopPolicy",
    "BoundedFinanceLoopResult",
    "FINANCE_TOOL_NAMES",
    "READ_NUMERIC_FACTS_TOOL",
    "READ_REVIEWED_EVIDENCE_TOOL",
    "SUBMIT_EVIDENCE_REQUEST_TOOL",
    "SUBMIT_RESEARCH_JUDGMENT_TOOL",
    "compile_finance_loop_messages",
    "compile_finance_loop_tools",
    "load_bounded_finance_loop_policy",
    "run_bounded_finance_loop",
    "scope_bounded_finance_loop_policy",
    "validate_deepseek_ga_profile",
    "validate_deepseek_ga_json_profile",
]
