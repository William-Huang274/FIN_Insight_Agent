from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Mapping, Sequence

from .case_truth_reconciliation import compile_case_truth_model_view
from .five_cell_runtime import compile_five_cell_analysis_view
from .reviewed_evidence_pack import canonical_digest


MULTI_AGENT_ROLE_TOPOLOGY_SCHEMA_VERSION = (
    "fin_ia_multi_agent_role_topology_v1_0"
)
SPECIALIST_PLAN_OPINION_SCHEMA_VERSION = (
    "fin_ia_specialist_plan_opinion_v1_0"
)
LEAD_PLAN_SCHEMA_VERSION = "fin_ia_multi_agent_lead_plan_v1_0"
LEAD_COORDINATION_DECISION_SCHEMA_VERSION = (
    "fin_ia_multi_agent_lead_coordination_decision_v1_0"
)
SPECIALIST_WORKPAPER_SCHEMA_VERSION = (
    "fin_ia_specialist_workpaper_v1_0"
)
SPECIALIST_CONTEXT_SCHEMA_VERSION = "fin_ia_specialist_context_v1_0"
SPECIALIST_REPAIR_CONTEXT_SCHEMA_VERSION = (
    "fin_ia_specialist_repair_context_v1_0"
)
MULTI_AGENT_EVALUATION_SCHEMA_VERSION = (
    "fin_ia_multi_agent_evaluation_v1_0"
)
MULTI_AGENT_EVALUATION_CONTENT_VIEW_SCHEMA_VERSION = (
    "fin_ia_multi_agent_evaluation_content_view_v1_0"
)
MULTI_AGENT_CROSS_ROLE_EVALUATION_VIEW_SCHEMA_VERSION = (
    "fin_ia_multi_agent_cross_role_evaluation_view_v1_0"
)
MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_report_draft_v1_0"
)
TOKEN_BUDGET_BASIS_SCHEMA_VERSION = "fin_ia_token_budget_basis_v1_0"
SPECIALIST_PLAN_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_specialist_plan_checkpoint_v1_0"
)
SPECIALIST_WORKPAPER_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_specialist_workpaper_checkpoint_v1_0"
)
ANALYSIS_FRAGMENT_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_analysis_fragment_checkpoint_v1_0"
)
ANALYSIS_COMPLETION_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_analysis_completion_checkpoint_v1_0"
)
DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_downstream_repair_progress_checkpoint_v1_0"
)
DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_V2_SCHEMA_VERSION = (
    "fin_ia_multi_agent_downstream_repair_progress_checkpoint_v1_1"
)
LEAD_PLAN_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_lead_plan_checkpoint_v1_0"
)
LEAD_COORDINATION_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_lead_coordination_checkpoint_v1_0"
)
LEAD_PLAN_CARDINALITY_POLICY_SCHEMA_VERSION = (
    "fin_ia_multi_agent_lead_plan_cardinality_policy_v1_0"
)

RESEARCH_LEAD_AGENT_ID = "AGENT::RESEARCH_LEAD"
WRITER_AGENT_ID = "AGENT::WRITER"
SPECIALIST_AGENT_IDS = (
    "AGENT::DEMAND_QUALITY",
    "AGENT::OPERATING_PERFORMANCE",
    "AGENT::VALUE_CAPTURE",
    "AGENT::CASH_CONVERSION",
    "AGENT::SUPPLY_RELATIONSHIP",
    "AGENT::COUNTEREVIDENCE",
)

_MODEL_INTENT_DIGIT = re.compile(r"[0-9０-９]")
_ABSENCE_TERMS = (
    "不存在",
    "没有披露",
    "未披露",
    "缺失",
    "不可得",
    "absent",
    "not disclosed",
    "unavailable",
)
_EMPTY_REF_PLACEHOLDER = "__NO_VALID_REF__"


class MultiAgentPreviewError(ValueError):
    """Fail-closed contract error for the diagnostic multi-agent preview."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise MultiAgentPreviewError(code)


def _strings(
    value: object,
    code: str,
    *,
    minimum: int = 1,
    maximum: int = 12,
    maximum_chars: int = 600,
) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(item or "").strip() for item in value]
    _require(
        minimum <= len(rows) <= maximum
        and all(rows)
        and len(rows) == len(set(rows))
        and all(len(row) <= maximum_chars for row in rows),
        code,
    )
    return rows


def _authorized_ref_strings(
    value: object,
    code: str,
    *,
    allowed: set[str],
    maximum_chars: int = 120,
    scope_code: str | None = None,
) -> list[str]:
    """Validate refs while treating the transport placeholder as an empty set."""

    rows = _strings(
        value,
        code,
        minimum=0,
        maximum=max(len(allowed), 1),
        maximum_chars=maximum_chars,
    )
    if rows == [_EMPTY_REF_PLACEHOLDER]:
        _require(not allowed, scope_code or code)
        return []
    _require(
        _EMPTY_REF_PLACEHOLDER not in rows and set(rows).issubset(allowed),
        scope_code or code,
    )
    return rows


def _model_intents(value: object, code: str) -> list[str]:
    rows = _strings(
        value,
        code,
        minimum=1,
        maximum=4,
        maximum_chars=220,
    )
    _require(
        all(
            not _MODEL_INTENT_DIGIT.search(row)
            and "http://" not in row.casefold()
            and "https://" not in row.casefold()
            and "::" not in row
            for row in rows
        ),
        code,
    )
    return rows


def _agent_index(topology: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["agent_id"]): deepcopy(dict(row))
        for row in topology["preview_agents"]
    }


def compile_lead_plan_cardinality_policy(
    *, topology: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive bounded Lead-plan capacities from the current role topology.

    The Lead contract used to carry three unrelated literals in its JSON Schema
    and a fourth shared literal in the local validator.  A topology change could
    therefore make a natural plan invalid even when it covered the approved
    research surface.  Capacities are now derived once and consumed by every
    contract surface.
    """

    trusted = load_multi_agent_role_topology(topology)
    facet_count = len(trusted["facet_catalog"])
    tool_count = len(trusted["tools"])
    required_slot_count = len(
        {
            str(row["slot_id"])
            for row in trusted["facet_catalog"].values()
        }
    )
    fields = {
        # At most one primary cross-role coordination question per accepted
        # facet.  Questions may cover several facets, so this is a ceiling, not
        # a quota.
        "coordination_questions": {
            "minimum": 2,
            "maximum": max(2, facet_count),
            "maximum_chars": 500,
            "basis": "one_primary_cross_role_question_per_topology_facet",
        },
        # Allow one explicit authority boundary per tool plus one
        # evidence/content boundary per required Evidence Slot.
        "expected_information_boundaries": {
            "minimum": 2,
            "maximum": max(2, tool_count + required_slot_count),
            "maximum_chars": 500,
            "basis": "tool_authorities_plus_required_evidence_slots",
        },
        # A bounded plan may state one closure condition per required slot and
        # two case-wide controls: cross-role conflict closure and final judgment
        # completeness.
        "stop_conditions": {
            "minimum": 2,
            "maximum": max(2, required_slot_count + 2),
            "maximum_chars": 500,
            "basis": "required_evidence_slots_plus_two_case_closure_controls",
        },
    }
    body = {
        "schema_version": LEAD_PLAN_CARDINALITY_POLICY_SCHEMA_VERSION,
        "facet_count": facet_count,
        "tool_count": tool_count,
        "required_slot_count": required_slot_count,
        "fields": fields,
    }
    return {**body, "policy_digest": canonical_digest(body)}


def compile_tool_contract_constraints(
    tool: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose the actionable top-level part of a model-visible tool schema."""

    function = dict(tool.get("function") or {})
    parameters = dict(function.get("parameters") or {})
    properties = dict(parameters.get("properties") or {})
    supported = {
        "type",
        "enum",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "maxLength",
    }
    field_constraints: dict[str, Any] = {}
    for field, raw in properties.items():
        schema = dict(raw or {})
        projected = {key: deepcopy(schema[key]) for key in supported if key in schema}
        item_schema = dict(schema.get("items") or {})
        item_projection = {
            key: deepcopy(item_schema[key])
            for key in supported
            if key in item_schema
        }
        if item_projection:
            projected["items"] = item_projection
        field_constraints[str(field)] = projected
    return {
        "tool_name": str(function.get("name") or ""),
        "additional_properties_allowed": parameters.get("additionalProperties")
        is not False,
        "required_fields": [str(row) for row in parameters.get("required") or ()],
        "field_constraints": field_constraints,
    }


def compile_tool_contract_failure_feedback(
    *,
    tool: Mapping[str, Any],
    payload: Mapping[str, Any] | None,
    failure_code: str,
) -> dict[str, Any]:
    """Compile one deterministic, model-actionable contract failure receipt.

    This is deliberately diagnostic rather than a replacement validator.  The
    authoritative local validator still decides acceptance; this projection
    tells the model *what* was structurally wrong instead of returning only an
    opaque code.
    """

    contract = compile_tool_contract_constraints(tool)
    value = dict(payload or {})
    violations: list[dict[str, Any]] = []
    required = set(contract["required_fields"])
    for field in sorted(required - set(value)):
        violations.append({"field": field, "rule": "required", "observed": "missing"})
    if not contract["additional_properties_allowed"]:
        for field in sorted(set(value) - set(contract["field_constraints"])):
            violations.append(
                {"field": field, "rule": "additionalProperties", "observed": "present"}
            )
    for field, constraints in contract["field_constraints"].items():
        if field not in value:
            continue
        observed = value[field]
        expected_type = constraints.get("type")
        if expected_type == "array" and not isinstance(observed, list):
            violations.append(
                {
                    "field": field,
                    "rule": "type",
                    "observed": type(observed).__name__,
                    "allowed": "array",
                }
            )
            continue
        if expected_type == "string" and not isinstance(observed, str):
            violations.append(
                {
                    "field": field,
                    "rule": "type",
                    "observed": type(observed).__name__,
                    "allowed": "string",
                }
            )
            continue
        if "enum" in constraints and observed not in constraints["enum"]:
            violations.append(
                {
                    "field": field,
                    "rule": "enum",
                    "observed": observed,
                    "allowed": deepcopy(constraints["enum"]),
                }
            )
        if isinstance(observed, list):
            count = len(observed)
            if "minItems" in constraints and count < int(constraints["minItems"]):
                violations.append(
                    {
                        "field": field,
                        "rule": "minItems",
                        "observed": count,
                        "allowed_minimum": int(constraints["minItems"]),
                    }
                )
            if "maxItems" in constraints and count > int(constraints["maxItems"]):
                violations.append(
                    {
                        "field": field,
                        "rule": "maxItems",
                        "observed": count,
                        "allowed_maximum": int(constraints["maxItems"]),
                    }
                )
            if constraints.get("uniqueItems") is True:
                serialized = [
                    json.dumps(row, ensure_ascii=False, sort_keys=True)
                    for row in observed
                ]
                if len(serialized) != len(set(serialized)):
                    violations.append(
                        {
                            "field": field,
                            "rule": "uniqueItems",
                            "observed": "duplicates_present",
                        }
                    )
            item_constraints = dict(constraints.get("items") or {})
            for index, item in enumerate(observed):
                if "enum" in item_constraints and item not in item_constraints["enum"]:
                    violations.append(
                        {
                            "field": field,
                            "index": index,
                            "rule": "item.enum",
                            "observed": item,
                        }
                    )
                if isinstance(item, str):
                    length = len(item)
                    if "minLength" in item_constraints and length < int(
                        item_constraints["minLength"]
                    ):
                        violations.append(
                            {
                                "field": field,
                                "index": index,
                                "rule": "item.minLength",
                                "observed": length,
                                "allowed_minimum": int(item_constraints["minLength"]),
                            }
                        )
                    if "maxLength" in item_constraints and length > int(
                        item_constraints["maxLength"]
                    ):
                        violations.append(
                            {
                                "field": field,
                                "index": index,
                                "rule": "item.maxLength",
                                "observed": length,
                                "allowed_maximum": int(item_constraints["maxLength"]),
                            }
                        )
        elif isinstance(observed, str):
            length = len(observed)
            if "minLength" in constraints and length < int(constraints["minLength"]):
                violations.append(
                    {
                        "field": field,
                        "rule": "minLength",
                        "observed": length,
                        "allowed_minimum": int(constraints["minLength"]),
                    }
                )
            if "maxLength" in constraints and length > int(constraints["maxLength"]):
                violations.append(
                    {
                        "field": field,
                        "rule": "maxLength",
                        "observed": length,
                        "allowed_maximum": int(constraints["maxLength"]),
                    }
                )
    nested_violations: list[dict[str, Any]] = []

    def collect_nested(
        schema: Mapping[str, Any], observed: object, path: str
    ) -> None:
        expected_type = schema.get("type")
        if expected_type == "object":
            if not isinstance(observed, Mapping):
                return
            properties = dict(schema.get("properties") or {})
            for field in sorted(set(schema.get("required") or ()) - set(observed)):
                nested_violations.append(
                    {
                        "field": f"{path}.{field}" if path else str(field),
                        "rule": "required",
                        "observed": "missing",
                    }
                )
            if schema.get("additionalProperties") is False:
                for field in sorted(set(observed) - set(properties)):
                    nested_violations.append(
                        {
                            "field": f"{path}.{field}" if path else str(field),
                            "rule": "additionalProperties",
                            "observed": "present",
                        }
                    )
            for field, child in properties.items():
                if field in observed:
                    collect_nested(
                        dict(child or {}),
                        observed[field],
                        f"{path}.{field}" if path else str(field),
                    )
            return
        if expected_type == "array":
            if not isinstance(observed, list):
                return
            item_schema = dict(schema.get("items") or {})
            for index, item in enumerate(observed):
                collect_nested(item_schema, item, f"{path}[{index}]")
            return
        if expected_type == "string" and isinstance(observed, str):
            if "enum" in schema and observed not in schema["enum"]:
                nested_violations.append(
                    {
                        "field": path,
                        "rule": "enum",
                        "observed": observed,
                        "allowed": deepcopy(schema["enum"]),
                    }
                )
            length = len(observed)
            if "minLength" in schema and length < int(schema["minLength"]):
                nested_violations.append(
                    {
                        "field": path,
                        "rule": "minLength",
                        "observed": length,
                        "allowed_minimum": int(schema["minLength"]),
                    }
                )
            if "maxLength" in schema and length > int(schema["maxLength"]):
                nested_violations.append(
                    {
                        "field": path,
                        "rule": "maxLength",
                        "observed": length,
                        "allowed_maximum": int(schema["maxLength"]),
                    }
                )

    collect_nested(
        dict(tool.get("function", {}).get("parameters") or {}), value, ""
    )
    violations.extend(
        row
        for row in nested_violations
        if "." in str(row["field"]) or "[" in str(row["field"])
    )
    if not violations:
        violations.append(
            {
                "field": "$local_validator",
                "rule": "semantic_or_cross_field_validation",
                "observed": failure_code,
            }
        )
    body = {
        "schema_version": "fin_ia_tool_contract_failure_feedback_v1_0",
        "tool_name": contract["tool_name"],
        "failure_code": str(failure_code),
        "violations": violations,
        "correction_rule": (
            "Correct every listed violation in one submission. Preserve the completed "
            "analysis and authority; merge or select distinct items when a bounded "
            "array is over capacity, and do not add facts."
        ),
    }
    return {**body, "feedback_digest": canonical_digest(body)}


def load_multi_agent_role_topology(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    required = {
        "schema_version",
        "status",
        "case_key",
        "research_as_of",
        "classification_rule",
        "current_runtime_finding",
        "preview_agents",
        "facet_catalog",
        "tools",
        "evaluators",
        "label_only_roles",
        "harness_components",
        "source_readiness_by_role",
        "preview_acceptance",
    }
    _require(
        set(value) == required
        and value.get("schema_version")
        == MULTI_AGENT_ROLE_TOPOLOGY_SCHEMA_VERSION
        and value.get("status")
        == "preview_topology_audited_not_product_qualified"
        and value.get("case_key") == "DELL"
        and value.get("research_as_of") == "2026-08-06",
        "multi_agent_topology_identity_invalid",
    )
    agents = value.get("preview_agents")
    _require(
        isinstance(agents, list)
        and [row.get("agent_id") for row in agents]
        == [RESEARCH_LEAD_AGENT_ID, *SPECIALIST_AGENT_IDS, WRITER_AGENT_ID],
        "multi_agent_topology_agents_invalid",
    )
    facets = value.get("facet_catalog")
    _require(isinstance(facets, Mapping) and bool(facets), "multi_agent_facets_invalid")
    for facet in facets.values():
        _require(
            isinstance(facet, Mapping)
            and set(facet)
            == {"slot_id", "target_entity", "metric_ids", "business_scope_zh"}
            and bool(str(facet.get("slot_id") or ""))
            and facet.get("target_entity") == "DELL"
            and isinstance(facet.get("metric_ids"), list),
            "multi_agent_facet_contract_invalid",
        )
    seen_facets: set[str] = set()
    for agent in agents:
        allowed = agent.get("allowed_facet_ids")
        if agent["agent_id"] in SPECIALIST_AGENT_IDS:
            _require(
                isinstance(allowed, list)
                and bool(allowed)
                and set(allowed).issubset(facets),
                "multi_agent_specialist_facets_invalid",
            )
            seen_facets.update(str(row) for row in allowed)
            _require(
                str(agent.get("cell_id") or "").startswith("CELL::"),
                "multi_agent_specialist_cell_invalid",
            )
        else:
            _require(allowed is None, "multi_agent_non_specialist_facets_invalid")
    _require(seen_facets == set(facets), "multi_agent_facet_coverage_invalid")
    current = value.get("current_runtime_finding") or {}
    _require(
        current.get("old_five_cell_is_true_multi_agent") is False
        and int(current.get("independent_agent_sessions") or 0) == 0
        and current.get("evidence_request_inside_model_loop_executes_s1")
        is False,
        "multi_agent_historical_finding_invalid",
    )
    evaluation_ids = {
        str(row.get("evaluator_id") or "")
        for row in value.get("evaluators") or ()
    }
    _require(
        {
            "EVAL::L1_FINANCIAL_TRUTH",
            "EVAL::CONTENT_QUALITY_EIGHT_DIMENSION",
            "EVAL::MULTI_AGENT_COLLABORATION",
            "EVAL::PAIRED_GAIN",
            "EVAL::QUALIFIED_HUMAN",
        }
        == evaluation_ids,
        "multi_agent_evaluator_inventory_invalid",
    )
    return value


def specialist_plan_tool(
    topology: Mapping[str, Any], agent_id: str
) -> dict[str, Any]:
    trusted = load_multi_agent_role_topology(topology)
    agent = _agent_index(trusted).get(agent_id)
    _require(
        agent_id in SPECIALIST_AGENT_IDS and agent is not None,
        "multi_agent_specialist_unknown",
    )
    allowed = list(agent["allowed_facet_ids"])
    return {
        "type": "function",
        "function": {
            "name": "submit_specialist_plan_opinion",
            "description": (
                "Submit one independent specialist research opinion. This is a "
                "proposal, not Evidence or a research conclusion."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "agent_id",
                    "mandate_interpretation",
                    "hypotheses",
                    "requested_atoms",
                    "dependencies",
                    "failure_risks",
                    "stop_condition",
                ],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "enum": [SPECIALIST_PLAN_OPINION_SCHEMA_VERSION],
                    },
                    "agent_id": {"type": "string", "enum": [agent_id]},
                    "mandate_interpretation": {
                        "type": "string",
                        "minLength": 20,
                        "maxLength": 800,
                    },
                    "hypotheses": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 5,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 400},
                    },
                    "requested_atoms": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": len(allowed),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["facet_id", "product_intents"],
                            "properties": {
                                "facet_id": {"type": "string", "enum": allowed},
                                "product_intents": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 4,
                                    "uniqueItems": True,
                                    "items": {
                                        "type": "string",
                                        "minLength": 8,
                                        "maxLength": 220,
                                    },
                                },
                            },
                        },
                    },
                    "dependencies": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "enum": [
                                "S1 reviewed Evidence",
                                "S1 official source route",
                                "S2 NumericFact",
                                "case fact presence",
                                "relationship graph context",
                                "another specialist workpaper",
                            ],
                        },
                    },
                    "failure_risks": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 6,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 400},
                    },
                    "stop_condition": {
                        "type": "string",
                        "minLength": 12,
                        "maxLength": 600,
                    },
                },
            },
        },
    }


def compile_specialist_plan_messages(
    *,
    topology: Mapping[str, Any],
    agent_id: str,
    objective: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    trusted = load_multi_agent_role_topology(topology)
    agent = _agent_index(trusted).get(agent_id)
    _require(
        agent_id in SPECIALIST_AGENT_IDS and agent is not None,
        "multi_agent_specialist_unknown",
    )
    visible = {
        "case_key": objective.get("case_key"),
        "research_as_of": objective.get("research_as_of") or objective.get("period", {}).get("end_date"),
        "user_question": objective.get("raw_question"),
        "agent": agent,
        "source_readiness": next(
            (
                deepcopy(dict(row))
                for row in trusted["source_readiness_by_role"]
                if str(row.get("agent_id") or "") == agent_id
            ),
            {},
        ),
        "available_tools": trusted["tools"],
        "failure_owner_rule": {
            "source_or_object_missing": "data_infrastructure_or_tool",
            "valid_data_hidden_or_wrongly_rejected": "harness_control",
            "tool_not_called_or_feedback_ignored": "agent_orchestration_and_role_design",
            "visible_evidence_misinterpreted": "model_judgment",
        },
    }
    return (
        {
            "role": "system",
            "content": (
                "You are one independent financial-research specialist in a true "
                "multi-agent preview. Propose only the research facets owned by "
                "your role. Distinguish data/tool, Harness, orchestration and model "
                "failures. Do not write findings and do not invent sources, facts "
                "or numbers. Submit exactly one specialist plan opinion tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def validate_specialist_plan_opinion(
    payload: Mapping[str, Any],
    *,
    topology: Mapping[str, Any],
    expected_agent_id: str,
) -> dict[str, Any]:
    trusted = load_multi_agent_role_topology(topology)
    agent = _agent_index(trusted).get(expected_agent_id)
    expected = {
        "schema_version",
        "agent_id",
        "mandate_interpretation",
        "hypotheses",
        "requested_atoms",
        "dependencies",
        "failure_risks",
        "stop_condition",
    }
    value = deepcopy(dict(payload))
    _require(
        set(value) == expected
        and value.get("schema_version")
        == SPECIALIST_PLAN_OPINION_SCHEMA_VERSION
        and value.get("agent_id") == expected_agent_id
        and expected_agent_id in SPECIALIST_AGENT_IDS
        and agent is not None,
        "multi_agent_specialist_plan_identity_invalid",
    )
    _require(
        20 <= len(str(value["mandate_interpretation"]).strip()) <= 800
        and 12 <= len(str(value["stop_condition"]).strip()) <= 600,
        "multi_agent_specialist_plan_text_invalid",
    )
    value["hypotheses"] = _strings(
        value["hypotheses"],
        "multi_agent_specialist_hypotheses_invalid",
        minimum=2,
        maximum=5,
        maximum_chars=400,
    )
    value["dependencies"] = _strings(
        value["dependencies"],
        "multi_agent_specialist_dependencies_invalid",
        minimum=1,
        maximum=8,
        maximum_chars=80,
    )
    value["failure_risks"] = _strings(
        value["failure_risks"],
        "multi_agent_specialist_risks_invalid",
        minimum=1,
        maximum=6,
        maximum_chars=400,
    )
    allowed_dependencies = {
        "S1 reviewed Evidence",
        "S1 official source route",
        "S2 NumericFact",
        "case fact presence",
        "relationship graph context",
        "another specialist workpaper",
    }
    _require(
        set(value["dependencies"]).issubset(allowed_dependencies),
        "multi_agent_specialist_dependencies_invalid",
    )
    atoms = value.get("requested_atoms")
    _require(
        isinstance(atoms, list)
        and 1 <= len(atoms) <= len(agent["allowed_facet_ids"]),
        "multi_agent_specialist_atoms_invalid",
    )
    normalized_atoms = []
    seen: set[str] = set()
    for raw in atoms:
        _require(
            isinstance(raw, Mapping)
            and set(raw) == {"facet_id", "product_intents"},
            "multi_agent_specialist_atom_fields_invalid",
        )
        facet_id = str(raw.get("facet_id") or "")
        _require(
            facet_id in agent["allowed_facet_ids"] and facet_id not in seen,
            "multi_agent_specialist_facet_invalid",
        )
        seen.add(facet_id)
        normalized_atoms.append(
            {
                "facet_id": facet_id,
                "product_intents": _model_intents(
                    raw.get("product_intents"),
                    "multi_agent_specialist_product_intents_invalid",
                ),
            }
        )
    value["requested_atoms"] = normalized_atoms
    value["plan_opinion_digest"] = canonical_digest(value)
    return value


def lead_plan_tool(*, topology: Mapping[str, Any]) -> dict[str, Any]:
    trusted = load_multi_agent_role_topology(topology)
    allowed_facets = list(trusted["facet_catalog"])
    cardinality = compile_lead_plan_cardinality_policy(topology=trusted)["fields"]
    return {
        "type": "function",
        "function": {
            "name": "submit_lead_plan",
            "description": "Integrate independent specialist opinions without writing their conclusions.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "lead_agent_id",
                    "accepted_agent_ids",
                    "ordered_agent_ids",
                    "accepted_facets",
                    "coordination_questions",
                    "expected_information_boundaries",
                    "stop_conditions",
                ],
                "properties": {
                    "schema_version": {"type": "string", "enum": [LEAD_PLAN_SCHEMA_VERSION]},
                    "lead_agent_id": {"type": "string", "enum": [RESEARCH_LEAD_AGENT_ID]},
                    "accepted_agent_ids": {
                        "type": "array",
                        "minItems": len(SPECIALIST_AGENT_IDS),
                        "maxItems": len(SPECIALIST_AGENT_IDS),
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": list(SPECIALIST_AGENT_IDS)},
                    },
                    "ordered_agent_ids": {
                        "type": "array",
                        "minItems": len(SPECIALIST_AGENT_IDS),
                        "maxItems": len(SPECIALIST_AGENT_IDS),
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": list(SPECIALIST_AGENT_IDS)},
                    },
                    "accepted_facets": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": len(allowed_facets),
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": allowed_facets},
                    },
                    "coordination_questions": {
                        "type": "array",
                        "minItems": cardinality["coordination_questions"]["minimum"],
                        "maxItems": cardinality["coordination_questions"]["maximum"],
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "minLength": 8,
                            "maxLength": cardinality["coordination_questions"][
                                "maximum_chars"
                            ],
                        },
                    },
                    "expected_information_boundaries": {
                        "type": "array",
                        "minItems": cardinality[
                            "expected_information_boundaries"
                        ]["minimum"],
                        "maxItems": cardinality[
                            "expected_information_boundaries"
                        ]["maximum"],
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "minLength": 8,
                            "maxLength": cardinality[
                                "expected_information_boundaries"
                            ]["maximum_chars"],
                        },
                    },
                    "stop_conditions": {
                        "type": "array",
                        "minItems": cardinality["stop_conditions"]["minimum"],
                        "maxItems": cardinality["stop_conditions"]["maximum"],
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "minLength": 8,
                            "maxLength": cardinality["stop_conditions"][
                                "maximum_chars"
                            ],
                        },
                    },
                },
            },
        },
    }


def compile_lead_plan_messages(
    *,
    topology: Mapping[str, Any],
    objective: Mapping[str, Any],
    opinions: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], ...]:
    trusted = load_multi_agent_role_topology(topology)
    visible = {
        "case_key": objective.get("case_key"),
        "research_as_of": objective.get("research_as_of") or objective.get("period", {}).get("end_date"),
        "user_question": objective.get("raw_question"),
        "required_slot_ids": objective.get("required_slot_ids"),
        "specialist_opinions": [deepcopy(dict(row)) for row in opinions],
        "facet_catalog": trusted["facet_catalog"],
        "available_tools": trusted["tools"],
        "lead_plan_cardinality_policy": compile_lead_plan_cardinality_policy(
            topology=trusted
        ),
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the Research Lead. Integrate all independent specialist "
                "opinions into one bounded research plan. Preserve role ownership, "
                "cover every required Evidence Slot, identify cross-role consistency "
                "questions and explicit stop conditions. Do not write research "
                "conclusions. Submit exactly one lead plan tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def compile_analyzed_node_messages(
    *,
    messages: Sequence[Mapping[str, Any]],
    tool_name: str,
    required_outputs: Sequence[str],
) -> tuple[dict[str, str], ...]:
    """Project a strict node into a visible analysis-only phase.

    The original role brief remains visible, but any sentence asking for a tool
    call is explicitly inactive in this phase.  The draft is model output for
    the later contract mapper; it is never Evidence or business authority.
    """

    _require(bool(messages), "multi_agent_analysis_messages_missing")
    rows = [
        {
            "role": str(row.get("role") or ""),
            "content": str(row.get("content") or ""),
        }
        for row in messages
    ]
    _require(
        all(
            row["role"] in {"system", "user", "assistant"}
            and row["content"].strip()
            for row in rows
        ),
        "multi_agent_analysis_messages_invalid",
    )
    original_system = "\n\n".join(
        row["content"] for row in rows if row["role"] == "system"
    )
    original_context = [row for row in rows if row["role"] != "system"]
    _require(
        bool(original_system) and bool(original_context),
        "multi_agent_analysis_role_context_missing",
    )
    requirements = [str(item).strip() for item in required_outputs]
    _require(
        bool(requirements) and all(requirements),
        "multi_agent_analysis_required_outputs_invalid",
    )
    return (
        {
            "role": "system",
            "content": (
                "ANALYSIS PHASE. Do not call tools and do not emit JSON. Form a "
                "visible, concise research draft that a later non-thinking "
                "contract mapper can submit without doing new research. Any "
                "sentence in the original role brief asking for a tool call is "
                "inactive during this phase. Preserve exact role IDs, facet IDs, "
                "Evidence/NumericFact/Gap refs and allowed enum values when they "
                "are needed by the final fields. Do not invent facts or authority. "
                f"The later tool is {tool_name}; its required fields are "
                f"{', '.join(requirements)}.\n\nORIGINAL ROLE BRIEF:\n"
                + original_system
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phase": "analysis_only_not_business_authority",
                    "task_context": original_context,
                    "required_draft_sections": requirements,
                    "later_tool_name": tool_name,
                    "rules": [
                        "cover every required field in the draft",
                        "keep identifiers and references exact",
                        "separate known facts, hypotheses and information boundaries",
                        "do not add a fact absent from task_context",
                        "end with a compact submission checklist",
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def compile_analyzed_node_submission_messages(
    *,
    analysis_draft: str,
    analysis_messages: Sequence[Mapping[str, Any]],
    tool_name: str,
    required_outputs: Sequence[str],
    analysis_messages_digest: str | None = None,
    tool_contract_constraints: Mapping[str, Any] | None = None,
) -> tuple[dict[str, str], ...]:
    draft = str(analysis_draft or "").strip()
    _require(
        20 <= len(draft) <= 120_000,
        "multi_agent_analysis_draft_invalid",
    )
    requirements = [str(item).strip() for item in required_outputs]
    _require(
        bool(requirements) and all(requirements),
        "multi_agent_submission_required_outputs_invalid",
    )
    context_digest = str(analysis_messages_digest or "") or canonical_digest(
        [dict(row) for row in analysis_messages]
    )
    _require(
        len(context_digest) == 64
        and all(ch in "0123456789abcdef" for ch in context_digest),
        "multi_agent_submission_analysis_context_digest_invalid",
    )
    return (
        {
            "role": "system",
            "content": (
                "CONTRACT SUBMISSION PHASE. Map the supplied analysis draft into "
                f"exactly one {tool_name} tool call. Do not redo the research, "
                "add facts, broaden authority or copy explanatory prose outside "
                "the tool call. The tool schema and local validator are "
                "authoritative. If the draft is more cautious than the schema "
                "permits, preserve the caution rather than strengthen the claim."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phase": "strict_contract_mapping_only",
                    "analysis_draft": draft,
                    "analysis_messages_digest": context_digest,
                    "required_output_fields": requirements,
                    "tool_contract_constraints": deepcopy(
                        dict(tool_contract_constraints or {})
                    ),
                    "rules": [
                        "use only identifiers and claims present in the draft",
                        "emit one tool call and no free prose",
                        "do not create Evidence NumericFact Gap date or company authority",
                    ],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def compile_analysis_fragment_checkpoint(
    *,
    case_key: str,
    run_id: str,
    node_id: str,
    source_authority_ref: str,
    source_authority_sha256: str,
    source_public_result_ref: str,
    source_public_result_sha256: str,
    source_public_result_digest: str,
    request_capture_ref: str,
    request_capture_sha256: str,
    request_digest: str,
    response_capture_ref: str,
    response_capture_sha256: str,
    response_digest: str,
    partial_draft: str,
    required_outputs: Sequence[str],
    completed_required_outputs: Sequence[str],
    partial_required_outputs: Sequence[str],
    missing_required_outputs: Sequence[str],
    usage: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Bind a length-truncated visible draft without promoting its content."""

    draft = str(partial_draft or "").strip()
    required = [str(item).strip() for item in required_outputs]
    completed = [str(item).strip() for item in completed_required_outputs]
    partial = [str(item).strip() for item in partial_required_outputs]
    missing = [str(item).strip() for item in missing_required_outputs]
    _require(
        20 <= len(draft) <= 120_000,
        "multi_agent_analysis_checkpoint_draft_invalid",
    )
    _require(
        bool(required)
        and len(required) == len(set(required))
        and all(required)
        and len(partial) <= 1
        and not (set(completed) & set(partial))
        and not (set(completed) & set(missing))
        and not (set(partial) & set(missing))
        and set(completed) | set(partial) | set(missing) == set(required)
        and bool(partial or missing),
        "multi_agent_analysis_checkpoint_coverage_invalid",
    )
    digests = (
        source_authority_sha256,
        source_public_result_sha256,
        source_public_result_digest,
        request_capture_sha256,
        request_digest,
        response_capture_sha256,
        response_digest,
    )
    _require(
        all(
            len(str(value)) == 64
            and all(ch in "0123456789abcdef" for ch in str(value))
            for value in digests
        ),
        "multi_agent_analysis_checkpoint_digest_binding_invalid",
    )
    body = {
        "schema_version": ANALYSIS_FRAGMENT_CHECKPOINT_SCHEMA_VERSION,
        "status": "length_truncated_visible_analysis_bound_for_one_continuation",
        "case_key": str(case_key).upper(),
        "run_id": str(run_id),
        "node_id": str(node_id),
        "source_authority_ref": str(source_authority_ref),
        "source_authority_sha256": str(source_authority_sha256),
        "source_public_result_ref": str(source_public_result_ref),
        "source_public_result_sha256": str(source_public_result_sha256),
        "source_public_result_digest": str(source_public_result_digest),
        "request_capture_ref": str(request_capture_ref),
        "request_capture_sha256": str(request_capture_sha256),
        "request_digest": str(request_digest),
        "response_capture_ref": str(response_capture_ref),
        "response_capture_sha256": str(response_capture_sha256),
        "response_digest": str(response_digest),
        "finish_reason": "length",
        "partial_draft_digest": canonical_digest(draft),
        "partial_draft_character_count": len(draft),
        "required_outputs": required,
        "completed_required_outputs": completed,
        "partial_required_outputs": partial,
        "missing_required_outputs": missing,
        "usage": deepcopy(dict(usage)),
        "continuation_policy": {
            "maximum_continuation_calls": 1,
            "continue_missing_content_only": True,
            "repeat_completed_sections_forbidden": True,
            "new_fact_or_authority_forbidden": True,
            "partial_draft_business_promotion": False,
            "complete_merged_draft_required_before_submission": True,
        },
        "claims": {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "recorded_at": str(recorded_at),
    }
    _require(
        bool(re.fullmatch(r"[A-Z0-9._-]+", body["case_key"]))
        and all(
            str(body[field]).strip()
            for field in (
                "run_id",
                "node_id",
                "source_authority_ref",
                "source_public_result_ref",
                "request_capture_ref",
                "response_capture_ref",
                "recorded_at",
            )
        ),
        "multi_agent_analysis_checkpoint_identity_invalid",
    )
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_analysis_fragment_checkpoint(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "status",
        "case_key",
        "run_id",
        "node_id",
        "source_authority_ref",
        "source_authority_sha256",
        "source_public_result_ref",
        "source_public_result_sha256",
        "source_public_result_digest",
        "request_capture_ref",
        "request_capture_sha256",
        "request_digest",
        "response_capture_ref",
        "response_capture_sha256",
        "response_digest",
        "finish_reason",
        "partial_draft_digest",
        "partial_draft_character_count",
        "required_outputs",
        "completed_required_outputs",
        "partial_required_outputs",
        "missing_required_outputs",
        "usage",
        "continuation_policy",
        "claims",
        "recorded_at",
        "checkpoint_digest",
    }
    _require(
        set(value) == expected
        and value.get("schema_version")
        == ANALYSIS_FRAGMENT_CHECKPOINT_SCHEMA_VERSION
        and value.get("status")
        == "length_truncated_visible_analysis_bound_for_one_continuation"
        and bool(re.fullmatch(r"[A-Z0-9._-]+", str(value.get("case_key") or "")))
        and value.get("finish_reason") == "length"
        and value.get("continuation_policy")
        == {
            "maximum_continuation_calls": 1,
            "continue_missing_content_only": True,
            "repeat_completed_sections_forbidden": True,
            "new_fact_or_authority_forbidden": True,
            "partial_draft_business_promotion": False,
            "complete_merged_draft_required_before_submission": True,
        }
        and value.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "multi_agent_analysis_checkpoint_shape_invalid",
    )
    digest_fields = (
        "source_authority_sha256",
        "source_public_result_sha256",
        "source_public_result_digest",
        "request_capture_sha256",
        "request_digest",
        "response_capture_sha256",
        "response_digest",
        "partial_draft_digest",
    )
    _require(
        all(
            len(str(value.get(field) or "")) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(value.get(field) or "")
            )
            for field in digest_fields
        )
        and all(
            str(value.get(field) or "").strip()
            for field in (
                "run_id",
                "node_id",
                "source_authority_ref",
                "source_public_result_ref",
                "request_capture_ref",
                "response_capture_ref",
                "recorded_at",
            )
        ),
        "multi_agent_analysis_checkpoint_binding_invalid",
    )
    required = list(value.get("required_outputs") or [])
    completed = list(value.get("completed_required_outputs") or [])
    partial = list(value.get("partial_required_outputs") or [])
    missing = list(value.get("missing_required_outputs") or [])
    _require(
        bool(required)
        and len(required) == len(set(required))
        and len(partial) <= 1
        and set(completed) | set(partial) | set(missing) == set(required)
        and not (set(completed) & set(partial))
        and not (set(completed) & set(missing))
        and not (set(partial) & set(missing))
        and bool(partial or missing)
        and int(value.get("partial_draft_character_count") or 0) >= 20,
        "multi_agent_analysis_checkpoint_coverage_invalid",
    )
    checkpoint_digest = str(value.pop("checkpoint_digest", ""))
    _require(
        checkpoint_digest == canonical_digest(value),
        "multi_agent_analysis_checkpoint_digest_invalid",
    )
    return {**value, "checkpoint_digest": checkpoint_digest}


def compile_downstream_repair_progress_checkpoint(
    *,
    case_key: str,
    source_run_id: str,
    source_authority_ref: str,
    source_authority_sha256: str,
    source_public_result_ref: str,
    source_public_result_sha256: str,
    source_public_result_digest: str,
    source_terminal_result_ref: str,
    source_terminal_result_sha256: str,
    source_terminal_result_digest: str,
    lead_coordination_checkpoint_ref: str,
    lead_coordination_checkpoint_sha256: str,
    lead_coordination_checkpoint_digest: str,
    accepted_challenge_ids: Sequence[str],
    completed_challenge_repairs: Sequence[Mapping[str, Any]],
    pending_challenge_ids: Sequence[str],
    active_analysis_fragment_checkpoint_ref: str,
    active_analysis_fragment_checkpoint_sha256: str,
    active_analysis_fragment_checkpoint_digest: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Bind completed downstream work and one resumable analysis fragment.

    This is deliberately provider-neutral. It records progress through an
    ordered challenge list without promoting a truncated analysis draft or
    granting permission to rerun already completed Agent nodes.
    """

    accepted = [str(item) for item in accepted_challenge_ids]
    completed = [deepcopy(dict(item)) for item in completed_challenge_repairs]
    pending = [str(item) for item in pending_challenge_ids]
    required_completed_fields = {
        "challenge_id",
        "target_agent_id",
        "node_id",
        "workpaper_digest",
    }
    digest_values = (
        source_authority_sha256,
        source_public_result_sha256,
        source_public_result_digest,
        source_terminal_result_sha256,
        source_terminal_result_digest,
        lead_coordination_checkpoint_sha256,
        lead_coordination_checkpoint_digest,
        active_analysis_fragment_checkpoint_sha256,
        active_analysis_fragment_checkpoint_digest,
    )
    _require(
        bool(accepted)
        and len(accepted) == len(set(accepted))
        and bool(completed)
        and all(set(row) == required_completed_fields for row in completed)
        and all(
            str(row[field]).strip()
            for row in completed
            for field in required_completed_fields
        )
        and all(
            str(row["node_id"])
            == f"{str(row['target_agent_id'])}::COUNTER_REPAIR"
            and len(str(row["workpaper_digest"])) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(row["workpaper_digest"])
            )
            for row in completed
        )
        and len({str(row["challenge_id"]) for row in completed})
        == len(completed)
        and len({str(row["node_id"]) for row in completed}) == len(completed)
        and [str(row["challenge_id"]) for row in completed]
        == accepted[: len(completed)]
        and pending == accepted[len(completed) :]
        and bool(pending)
        and all(
            len(str(value)) == 64
            and all(ch in "0123456789abcdef" for ch in str(value))
            for value in digest_values
        ),
        "multi_agent_downstream_repair_checkpoint_inputs_invalid",
    )
    body = {
        "schema_version": DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_SCHEMA_VERSION,
        "status": (
            "completed_repairs_and_active_analysis_fragment_bound_for_"
            "downstream_resume"
        ),
        "case_key": str(case_key).upper(),
        "source_run_id": str(source_run_id),
        "source_authority_ref": str(source_authority_ref),
        "source_authority_sha256": str(source_authority_sha256),
        "source_public_result_ref": str(source_public_result_ref),
        "source_public_result_sha256": str(source_public_result_sha256),
        "source_public_result_digest": str(source_public_result_digest),
        "source_terminal_result_ref": str(source_terminal_result_ref),
        "source_terminal_result_sha256": str(source_terminal_result_sha256),
        "source_terminal_result_digest": str(source_terminal_result_digest),
        "lead_coordination_checkpoint_ref": str(
            lead_coordination_checkpoint_ref
        ),
        "lead_coordination_checkpoint_sha256": str(
            lead_coordination_checkpoint_sha256
        ),
        "lead_coordination_checkpoint_digest": str(
            lead_coordination_checkpoint_digest
        ),
        "accepted_challenge_ids": accepted,
        "completed_challenge_repairs": completed,
        "pending_challenge_ids": pending,
        "active_analysis_fragment_checkpoint_ref": str(
            active_analysis_fragment_checkpoint_ref
        ),
        "active_analysis_fragment_checkpoint_sha256": str(
            active_analysis_fragment_checkpoint_sha256
        ),
        "active_analysis_fragment_checkpoint_digest": str(
            active_analysis_fragment_checkpoint_digest
        ),
        "resume_policy": {
            "maximum_analysis_continuation_calls": 1,
            "completed_repair_reruns_forbidden": True,
            "lead_coordination_rerun_forbidden": True,
            "workpaper_reruns_forbidden": True,
            "continue_from_active_fragment_only": True,
            "new_fact_or_authority_forbidden": True,
        },
        "claims": {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "recorded_at": str(recorded_at),
    }
    _require(
        bool(re.fullmatch(r"[A-Z0-9._-]+", body["case_key"]))
        and all(
            str(body[field]).strip()
            for field in (
                "source_run_id",
                "source_authority_ref",
                "source_public_result_ref",
                "source_terminal_result_ref",
                "lead_coordination_checkpoint_ref",
                "active_analysis_fragment_checkpoint_ref",
                "recorded_at",
            )
        ),
        "multi_agent_downstream_repair_checkpoint_identity_invalid",
    )
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_downstream_repair_progress_checkpoint(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "status",
        "case_key",
        "source_run_id",
        "source_authority_ref",
        "source_authority_sha256",
        "source_public_result_ref",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_ref",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "lead_coordination_checkpoint_ref",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "accepted_challenge_ids",
        "completed_challenge_repairs",
        "pending_challenge_ids",
        "active_analysis_fragment_checkpoint_ref",
        "active_analysis_fragment_checkpoint_sha256",
        "active_analysis_fragment_checkpoint_digest",
        "resume_policy",
        "claims",
        "recorded_at",
        "checkpoint_digest",
    }
    _require(
        set(value) == expected
        and value.get("schema_version")
        == DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_SCHEMA_VERSION
        and value.get("status")
        == (
            "completed_repairs_and_active_analysis_fragment_bound_for_"
            "downstream_resume"
        )
        and bool(
            re.fullmatch(r"[A-Z0-9._-]+", str(value.get("case_key") or ""))
        )
        and value.get("resume_policy")
        == {
            "maximum_analysis_continuation_calls": 1,
            "completed_repair_reruns_forbidden": True,
            "lead_coordination_rerun_forbidden": True,
            "workpaper_reruns_forbidden": True,
            "continue_from_active_fragment_only": True,
            "new_fact_or_authority_forbidden": True,
        }
        and value.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "multi_agent_downstream_repair_checkpoint_shape_invalid",
    )
    accepted = list(value.get("accepted_challenge_ids") or ())
    completed = list(value.get("completed_challenge_repairs") or ())
    pending = list(value.get("pending_challenge_ids") or ())
    completed_fields = {
        "challenge_id",
        "target_agent_id",
        "node_id",
        "workpaper_digest",
    }
    digest_fields = (
        "source_authority_sha256",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "active_analysis_fragment_checkpoint_sha256",
        "active_analysis_fragment_checkpoint_digest",
    )
    _require(
        bool(accepted)
        and len(accepted) == len(set(accepted))
        and bool(completed)
        and all(isinstance(row, Mapping) for row in completed)
        and all(set(row) == completed_fields for row in completed)
        and [str(row["challenge_id"]) for row in completed]
        == accepted[: len(completed)]
        and pending == accepted[len(completed) :]
        and bool(pending)
        and len({str(row["node_id"]) for row in completed}) == len(completed)
        and all(
            str(row["node_id"])
            == f"{str(row['target_agent_id'])}::COUNTER_REPAIR"
            and len(str(row["workpaper_digest"])) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(row["workpaper_digest"])
            )
            for row in completed
        )
        and all(
            len(str(value.get(field) or "")) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(value.get(field) or "")
            )
            for field in digest_fields
        )
        and all(
            str(value.get(field) or "").strip()
            for field in (
                "source_run_id",
                "source_authority_ref",
                "source_public_result_ref",
                "source_terminal_result_ref",
                "lead_coordination_checkpoint_ref",
                "active_analysis_fragment_checkpoint_ref",
                "recorded_at",
            )
        ),
        "multi_agent_downstream_repair_checkpoint_binding_invalid",
    )
    checkpoint_digest = str(value.pop("checkpoint_digest", ""))
    _require(
        checkpoint_digest == canonical_digest(value),
        "multi_agent_downstream_repair_checkpoint_digest_invalid",
    )
    return {**value, "checkpoint_digest": checkpoint_digest}


def compile_downstream_repair_progress_checkpoint_v2(
    *,
    case_key: str,
    source_run_id: str,
    source_authority_ref: str,
    source_authority_sha256: str,
    source_public_result_ref: str,
    source_public_result_sha256: str,
    source_public_result_digest: str,
    source_terminal_result_ref: str,
    source_terminal_result_sha256: str,
    source_terminal_result_digest: str,
    predecessor_progress_checkpoint_ref: str,
    predecessor_progress_checkpoint_sha256: str,
    predecessor_progress_checkpoint_digest: str,
    predecessor_analysis_fragment_checkpoint_ref: str,
    predecessor_analysis_fragment_checkpoint_sha256: str,
    predecessor_analysis_fragment_checkpoint_digest: str,
    lead_coordination_checkpoint_ref: str,
    lead_coordination_checkpoint_sha256: str,
    lead_coordination_checkpoint_digest: str,
    accepted_challenge_ids: Sequence[str],
    completed_challenge_repairs: Sequence[Mapping[str, Any]],
    inherited_completed_repair_count: int,
    pending_challenge_repairs: Sequence[Mapping[str, Any]],
    repair_context_policy_digest: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Bind completed repair progress when the next node has no fragment.

    V1.0 always required an active truncated fragment.  A reasoning-only
    terminal failure has no visible fragment to continue, so the successor
    must begin one fresh, role-scoped pending repair while reusing every
    completed repair from its exact source context.
    """

    accepted = [str(value) for value in accepted_challenge_ids]
    completed = [deepcopy(dict(row)) for row in completed_challenge_repairs]
    pending = [deepcopy(dict(row)) for row in pending_challenge_repairs]
    completed_fields = {
        "challenge_id",
        "target_agent_id",
        "node_id",
        "workpaper_digest",
        "source_run_id",
        "context_session_run_id",
    }
    pending_fields = {"challenge_id", "target_agent_id", "node_id"}
    digest_values = (
        source_authority_sha256,
        source_public_result_sha256,
        source_public_result_digest,
        source_terminal_result_sha256,
        source_terminal_result_digest,
        predecessor_progress_checkpoint_sha256,
        predecessor_progress_checkpoint_digest,
        predecessor_analysis_fragment_checkpoint_sha256,
        predecessor_analysis_fragment_checkpoint_digest,
        lead_coordination_checkpoint_sha256,
        lead_coordination_checkpoint_digest,
        repair_context_policy_digest,
    )
    ordered_ids = [
        *[str(row.get("challenge_id") or "") for row in completed],
        *[str(row.get("challenge_id") or "") for row in pending],
    ]
    _require(
        bool(accepted)
        and len(accepted) == len(set(accepted))
        and completed
        and pending
        and ordered_ids == accepted
        and len(completed) == len(
            {str(row.get("challenge_id") or "") for row in completed}
        )
        and len(pending) == len(
            {str(row.get("challenge_id") or "") for row in pending}
        )
        and all(set(row) == completed_fields for row in completed)
        and all(set(row) == pending_fields for row in pending)
        and 0 < int(inherited_completed_repair_count) < len(completed)
        and all(
            str(row["node_id"])
            == f"{str(row['target_agent_id'])}::COUNTER_REPAIR"
            and len(str(row["workpaper_digest"])) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(row["workpaper_digest"])
            )
            and str(row["source_run_id"]).strip()
            and str(row["context_session_run_id"]).strip()
            for row in completed
        )
        and all(
            str(row["node_id"])
            == f"{str(row['target_agent_id'])}::COUNTER_REPAIR"
            for row in pending
        )
        and all(
            len(str(value)) == 64
            and all(ch in "0123456789abcdef" for ch in str(value))
            for value in digest_values
        ),
        "multi_agent_downstream_repair_checkpoint_v2_inputs_invalid",
    )
    body = {
        "schema_version": (
            DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_V2_SCHEMA_VERSION
        ),
        "status": (
            "completed_repairs_bound_for_one_fresh_role_scoped_pending_repair"
        ),
        "case_key": str(case_key).upper(),
        "source_run_id": str(source_run_id),
        "source_authority_ref": str(source_authority_ref),
        "source_authority_sha256": str(source_authority_sha256),
        "source_public_result_ref": str(source_public_result_ref),
        "source_public_result_sha256": str(source_public_result_sha256),
        "source_public_result_digest": str(source_public_result_digest),
        "source_terminal_result_ref": str(source_terminal_result_ref),
        "source_terminal_result_sha256": str(source_terminal_result_sha256),
        "source_terminal_result_digest": str(source_terminal_result_digest),
        "predecessor_progress_checkpoint_ref": str(
            predecessor_progress_checkpoint_ref
        ),
        "predecessor_progress_checkpoint_sha256": str(
            predecessor_progress_checkpoint_sha256
        ),
        "predecessor_progress_checkpoint_digest": str(
            predecessor_progress_checkpoint_digest
        ),
        "predecessor_analysis_fragment_checkpoint_ref": str(
            predecessor_analysis_fragment_checkpoint_ref
        ),
        "predecessor_analysis_fragment_checkpoint_sha256": str(
            predecessor_analysis_fragment_checkpoint_sha256
        ),
        "predecessor_analysis_fragment_checkpoint_digest": str(
            predecessor_analysis_fragment_checkpoint_digest
        ),
        "lead_coordination_checkpoint_ref": str(
            lead_coordination_checkpoint_ref
        ),
        "lead_coordination_checkpoint_sha256": str(
            lead_coordination_checkpoint_sha256
        ),
        "lead_coordination_checkpoint_digest": str(
            lead_coordination_checkpoint_digest
        ),
        "accepted_challenge_ids": accepted,
        "completed_challenge_repairs": completed,
        "inherited_completed_repair_count": int(
            inherited_completed_repair_count
        ),
        "pending_challenge_repairs": pending,
        "repair_context_policy_digest": str(repair_context_policy_digest),
        "resume_policy": {
            "maximum_analysis_continuation_calls": 0,
            "completed_repair_reruns_forbidden": True,
            "lead_coordination_rerun_forbidden": True,
            "workpaper_reruns_forbidden": True,
            "begin_at_first_pending_repair_with_fresh_analysis": True,
            "pending_repair_context_must_be_role_scoped": True,
            "new_fact_or_authority_forbidden": True,
        },
        "claims": {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "recorded_at": str(recorded_at),
    }
    _require(
        bool(re.fullmatch(r"[A-Z0-9._-]+", body["case_key"]))
        and all(
            str(body[field]).strip()
            for field in (
                "source_run_id",
                "source_authority_ref",
                "source_public_result_ref",
                "source_terminal_result_ref",
                "predecessor_progress_checkpoint_ref",
                "predecessor_analysis_fragment_checkpoint_ref",
                "lead_coordination_checkpoint_ref",
                "recorded_at",
            )
        ),
        "multi_agent_downstream_repair_checkpoint_v2_identity_invalid",
    )
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_downstream_repair_progress_checkpoint_v2(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    checkpoint_digest = str(value.pop("checkpoint_digest", ""))
    expected = {
        "schema_version",
        "status",
        "case_key",
        "source_run_id",
        "source_authority_ref",
        "source_authority_sha256",
        "source_public_result_ref",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_ref",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "predecessor_progress_checkpoint_ref",
        "predecessor_progress_checkpoint_sha256",
        "predecessor_progress_checkpoint_digest",
        "predecessor_analysis_fragment_checkpoint_ref",
        "predecessor_analysis_fragment_checkpoint_sha256",
        "predecessor_analysis_fragment_checkpoint_digest",
        "lead_coordination_checkpoint_ref",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "accepted_challenge_ids",
        "completed_challenge_repairs",
        "inherited_completed_repair_count",
        "pending_challenge_repairs",
        "repair_context_policy_digest",
        "resume_policy",
        "claims",
        "recorded_at",
    }
    _require(
        set(value) == expected
        and checkpoint_digest == canonical_digest(value)
        and value.get("schema_version")
        == DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_V2_SCHEMA_VERSION
        and value.get("status")
        == "completed_repairs_bound_for_one_fresh_role_scoped_pending_repair"
        and bool(
            re.fullmatch(r"[A-Z0-9._-]+", str(value.get("case_key") or ""))
        )
        and value.get("resume_policy")
        == {
            "maximum_analysis_continuation_calls": 0,
            "completed_repair_reruns_forbidden": True,
            "lead_coordination_rerun_forbidden": True,
            "workpaper_reruns_forbidden": True,
            "begin_at_first_pending_repair_with_fresh_analysis": True,
            "pending_repair_context_must_be_role_scoped": True,
            "new_fact_or_authority_forbidden": True,
        }
        and value.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "multi_agent_downstream_repair_checkpoint_v2_shape_invalid",
    )
    completed = list(value.get("completed_challenge_repairs") or ())
    pending = list(value.get("pending_challenge_repairs") or ())
    accepted = list(value.get("accepted_challenge_ids") or ())
    completed_fields = {
        "challenge_id",
        "target_agent_id",
        "node_id",
        "workpaper_digest",
        "source_run_id",
        "context_session_run_id",
    }
    pending_fields = {"challenge_id", "target_agent_id", "node_id"}
    ordered_ids = [
        *[str(row.get("challenge_id") or "") for row in completed],
        *[str(row.get("challenge_id") or "") for row in pending],
    ]
    digest_fields = (
        "source_authority_sha256",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "predecessor_progress_checkpoint_sha256",
        "predecessor_progress_checkpoint_digest",
        "predecessor_analysis_fragment_checkpoint_sha256",
        "predecessor_analysis_fragment_checkpoint_digest",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "repair_context_policy_digest",
    )
    _require(
        accepted
        and len(accepted) == len(set(accepted))
        and completed
        and pending
        and ordered_ids == accepted
        and all(isinstance(row, Mapping) for row in completed + pending)
        and all(set(row) == completed_fields for row in completed)
        and all(set(row) == pending_fields for row in pending)
        and 0
        < int(value.get("inherited_completed_repair_count") or 0)
        < len(completed)
        and all(
            str(row["node_id"])
            == f"{str(row['target_agent_id'])}::COUNTER_REPAIR"
            and len(str(row["workpaper_digest"])) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(row["workpaper_digest"])
            )
            and str(row["source_run_id"]).strip()
            and str(row["context_session_run_id"]).strip()
            for row in completed
        )
        and all(
            str(row["node_id"])
            == f"{str(row['target_agent_id'])}::COUNTER_REPAIR"
            for row in pending
        )
        and all(
            len(str(value.get(field) or "")) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(value.get(field) or "")
            )
            for field in digest_fields
        ),
        "multi_agent_downstream_repair_checkpoint_v2_binding_invalid",
    )
    return {**value, "checkpoint_digest": checkpoint_digest}


def compile_analysis_continuation_messages(
    *,
    checkpoint: Mapping[str, Any],
    partial_draft: str,
    tool_name: str,
    original_analysis_messages: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, str], ...]:
    trusted = validate_analysis_fragment_checkpoint(checkpoint)
    draft = str(partial_draft or "").strip()
    _require(
        canonical_digest(draft) == trusted["partial_draft_digest"]
        and len(draft) == trusted["partial_draft_character_count"],
        "multi_agent_analysis_checkpoint_content_drift",
    )
    remaining = [
        *trusted["partial_required_outputs"],
        *trusted["missing_required_outputs"],
    ]
    continuation_instruction = json.dumps(
        {
            "phase": "analysis_continuation_only_not_business_authority",
            "checkpoint_digest": trusted["checkpoint_digest"],
            "completed_outputs_do_not_repeat": trusted[
                "completed_required_outputs"
            ],
            "partial_outputs_finish_in_place": trusted[
                "partial_required_outputs"
            ],
            "missing_outputs_add": trusted["missing_required_outputs"],
            "remaining_output_order": remaining,
            "required_output_headings": [
                f"OUTPUT::{field}" for field in trusted["missing_required_outputs"]
            ],
            "required_completion_receipt": (
                "COMPLETED_OUTPUTS::" + "|".join(remaining)
            ),
            "rules": [
                (
                    "start by finishing the exact truncated sentence"
                    if trusted["partial_required_outputs"]
                    else "start with the first required missing-output heading"
                ),
                (
                    "continue the single partial output in place without repeating "
                    "its OUTPUT heading"
                    if trusted["partial_required_outputs"]
                    else "there is no partial output to finish in place"
                ),
                "do not restate already completed analysis",
                "use only authority visible in the preserved original conversation",
                "do not call tools or emit JSON in this continuation",
                "keep the continuation concise enough to finish in one call",
                (
                    "write one exact OUTPUT::<field> heading for each field in "
                    "missing_outputs_add only, in the declared order"
                ),
                (
                    "end with exact completion receipt COMPLETED_OUTPUTS::"
                    + "|".join(remaining)
                ),
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if original_analysis_messages is not None:
        original = [deepcopy(dict(row)) for row in original_analysis_messages]
        _require(
            bool(original)
            and all(
                set(row) >= {"role", "content"}
                and str(row["role"]) in {"system", "user"}
                and bool(str(row["content"]).strip())
                for row in original
            )
            and all(str(row["role"]) != "assistant" for row in original),
            "multi_agent_analysis_continuation_original_messages_invalid",
        )
        return tuple(
            [
                *original,
                {"role": "assistant", "content": draft},
                {"role": "user", "content": continuation_instruction},
            ]
        )
    return (
        {
            "role": "system",
            "content": (
                "ANALYSIS CONTINUATION PHASE. Continue the preserved visible "
                "draft exactly where it stopped. Do not call tools or emit JSON. "
                "Do not repeat completed sections or redo the completed analysis, "
                "add facts or broaden authority. Complete only the partial and "
                "missing outputs, then end with a compact submission checklist. "
                f"The later tool remains {tool_name}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "phase": "analysis_continuation_only_not_business_authority",
                    "checkpoint_digest": trusted["checkpoint_digest"],
                    "preserved_partial_draft": draft,
                    "completed_outputs_do_not_repeat": trusted[
                        "completed_required_outputs"
                    ],
                    "partial_outputs_finish_in_place": trusted[
                        "partial_required_outputs"
                    ],
                    "missing_outputs_add": trusted["missing_required_outputs"],
                    "remaining_output_order": remaining,
                    "required_output_headings": [
                        f"OUTPUT::{field}"
                        for field in trusted["missing_required_outputs"]
                    ],
                    "required_completion_receipt": (
                        "COMPLETED_OUTPUTS::" + "|".join(remaining)
                    ),
                    "rules": json.loads(continuation_instruction)["rules"],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def validate_analysis_continuation_completion(
    *,
    checkpoint: Mapping[str, Any],
    continuation_draft: str,
) -> str:
    trusted = validate_analysis_fragment_checkpoint(checkpoint)
    continuation = str(continuation_draft or "").strip()
    remaining = [
        *trusted["partial_required_outputs"],
        *trusted["missing_required_outputs"],
    ]
    partial = list(trusted["partial_required_outputs"])
    missing = list(trusted["missing_required_outputs"])
    completed = list(trusted["completed_required_outputs"])
    expected_receipt = "COMPLETED_OUTPUTS::" + "|".join(remaining)
    receipt_index = continuation.rfind(expected_receipt)
    missing_markers = [f"OUTPUT::{field}" for field in missing]
    marker_indexes = [continuation.find(marker) for marker in missing_markers]
    partial_prefix_end = marker_indexes[0] if marker_indexes else receipt_index
    partial_prefix = (
        continuation[:partial_prefix_end].strip()
        if partial_prefix_end >= 0
        else ""
    )
    ordered_missing_sections = bool(
        all(index >= 0 for index in marker_indexes)
        and marker_indexes == sorted(marker_indexes)
        and all(continuation.count(marker) == 1 for marker in missing_markers)
    )
    missing_sections_nonempty = True
    for index, marker_index in enumerate(marker_indexes):
        section_start = marker_index + len(missing_markers[index])
        section_end = (
            marker_indexes[index + 1]
            if index + 1 < len(marker_indexes)
            else receipt_index
        )
        if section_end <= section_start or not continuation[
            section_start:section_end
        ].strip():
            missing_sections_nonempty = False
            break
    partial_completion_valid = (
        bool(partial)
        and bool(partial_prefix)
        and "OUTPUT::" not in partial_prefix
        and not any(
            f"OUTPUT::{field}" in continuation for field in partial
        )
    ) or (
        not partial
        and (
            (not missing and not partial_prefix)
            or (
                bool(missing_markers)
                and continuation.startswith(missing_markers[0])
            )
        )
    )
    _require(
        20 <= len(continuation) <= 60_000
        and bool(remaining)
        and receipt_index >= 0
        and ordered_missing_sections
        and missing_sections_nonempty
        and partial_completion_valid
        and not any(f"OUTPUT::{field}" in continuation for field in completed)
        and continuation.splitlines()[-1].strip() == expected_receipt,
        "multi_agent_analysis_continuation_semantically_incomplete",
    )
    return continuation


def merge_analysis_draft_fragments(
    *,
    checkpoint: Mapping[str, Any],
    partial_draft: str,
    continuation_draft: str,
) -> str:
    trusted = validate_analysis_fragment_checkpoint(checkpoint)
    partial = str(partial_draft or "").strip()
    continuation = validate_analysis_continuation_completion(
        checkpoint=trusted,
        continuation_draft=continuation_draft,
    )
    _require(
        canonical_digest(partial) == trusted["partial_draft_digest"]
        and len(partial) == trusted["partial_draft_character_count"]
        and 20 <= len(continuation) <= 60_000,
        "multi_agent_analysis_fragment_merge_invalid",
    )
    return partial + "\n\n" + continuation


def compile_analysis_completion_checkpoint(
    *,
    fragment_checkpoint: Mapping[str, Any],
    fragment_checkpoint_ref: str,
    fragment_checkpoint_sha256: str,
    partial_draft: str,
    source_continuation_run_id: str,
    source_continuation_authority_ref: str,
    source_continuation_authority_sha256: str,
    source_continuation_result_ref: str,
    source_continuation_result_sha256: str,
    source_continuation_result_digest: str,
    continuation_request_capture_ref: str,
    continuation_request_capture_sha256: str,
    continuation_request_digest: str,
    continuation_response_capture_ref: str,
    continuation_response_capture_sha256: str,
    continuation_response_digest: str,
    continuation_messages_digest: str,
    continuation_draft: str,
    finish_reason: str,
    usage: Mapping[str, Any],
    source_analysis_token_budget_basis: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    """Bind a semantically complete analysis without granting business authority."""

    fragment = validate_analysis_fragment_checkpoint(fragment_checkpoint)
    partial = str(partial_draft or "").strip()
    continuation = validate_analysis_continuation_completion(
        checkpoint=fragment,
        continuation_draft=continuation_draft,
    )
    merged = merge_analysis_draft_fragments(
        checkpoint=fragment,
        partial_draft=partial,
        continuation_draft=continuation,
    )
    basis = deepcopy(dict(source_analysis_token_budget_basis))
    basis_digest = str(basis.pop("token_budget_basis_digest", ""))
    digest_values = (
        fragment_checkpoint_sha256,
        source_continuation_authority_sha256,
        source_continuation_result_sha256,
        source_continuation_result_digest,
        continuation_request_capture_sha256,
        continuation_request_digest,
        continuation_response_capture_sha256,
        continuation_response_digest,
        continuation_messages_digest,
        basis_digest,
    )
    _require(
        str(finish_reason) == "stop"
        and canonical_digest(partial) == fragment["partial_draft_digest"]
        and len(partial) == fragment["partial_draft_character_count"]
        and all(
            len(str(value)) == 64
            and all(ch in "0123456789abcdef" for ch in str(value))
            for value in digest_values
        )
        and basis.get("schema_version") == TOKEN_BUDGET_BASIS_SCHEMA_VERSION
        and basis_digest == canonical_digest(basis),
        "multi_agent_analysis_completion_binding_invalid",
    )
    body = {
        "schema_version": ANALYSIS_COMPLETION_CHECKPOINT_SCHEMA_VERSION,
        "status": "visible_analysis_fragments_complete_bound_for_submission",
        "case_key": fragment["case_key"],
        "source_fragment_run_id": fragment["run_id"],
        "source_continuation_run_id": str(source_continuation_run_id),
        "node_id": fragment["node_id"],
        "fragment_checkpoint_ref": str(fragment_checkpoint_ref),
        "fragment_checkpoint_sha256": str(fragment_checkpoint_sha256),
        "fragment_checkpoint_digest": fragment["checkpoint_digest"],
        "source_continuation_authority_ref": str(
            source_continuation_authority_ref
        ),
        "source_continuation_authority_sha256": str(
            source_continuation_authority_sha256
        ),
        "source_continuation_result_ref": str(source_continuation_result_ref),
        "source_continuation_result_sha256": str(
            source_continuation_result_sha256
        ),
        "source_continuation_result_digest": str(
            source_continuation_result_digest
        ),
        "continuation_request_capture_ref": str(
            continuation_request_capture_ref
        ),
        "continuation_request_capture_sha256": str(
            continuation_request_capture_sha256
        ),
        "continuation_request_digest": str(continuation_request_digest),
        "continuation_response_capture_ref": str(
            continuation_response_capture_ref
        ),
        "continuation_response_capture_sha256": str(
            continuation_response_capture_sha256
        ),
        "continuation_response_digest": str(continuation_response_digest),
        "continuation_messages_digest": str(continuation_messages_digest),
        "finish_reason": "stop",
        "continuation_draft_digest": canonical_digest(continuation),
        "continuation_draft_character_count": len(continuation),
        "merged_analysis_draft_digest": canonical_digest(merged),
        "merged_analysis_draft_character_count": len(merged),
        "required_outputs": list(fragment["required_outputs"]),
        "completed_outputs": list(fragment["required_outputs"]),
        "continuation_completed_outputs": [
            *fragment["partial_required_outputs"],
            *fragment["missing_required_outputs"],
        ],
        "completion_receipt": (
            "COMPLETED_OUTPUTS::"
            + "|".join(
                [
                    *fragment["partial_required_outputs"],
                    *fragment["missing_required_outputs"],
                ]
            )
        ),
        "usage": deepcopy(dict(usage)),
        "source_analysis_token_budget_basis": {
            **basis,
            "token_budget_basis_digest": basis_digest,
        },
        "submission_policy": {
            "analysis_rerun_forbidden": True,
            "continuation_rerun_forbidden": True,
            "strict_submission_required": True,
            "new_fact_or_authority_forbidden": True,
            "merged_draft_business_promotion": False,
        },
        "claims": {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "recorded_at": str(recorded_at),
    }
    _require(
        all(
            str(body[field]).strip()
            for field in (
                "source_continuation_run_id",
                "node_id",
                "fragment_checkpoint_ref",
                "source_continuation_authority_ref",
                "source_continuation_result_ref",
                "continuation_request_capture_ref",
                "continuation_response_capture_ref",
                "recorded_at",
            )
        ),
        "multi_agent_analysis_completion_identity_invalid",
    )
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_analysis_completion_checkpoint(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "status",
        "case_key",
        "source_fragment_run_id",
        "source_continuation_run_id",
        "node_id",
        "fragment_checkpoint_ref",
        "fragment_checkpoint_sha256",
        "fragment_checkpoint_digest",
        "source_continuation_authority_ref",
        "source_continuation_authority_sha256",
        "source_continuation_result_ref",
        "source_continuation_result_sha256",
        "source_continuation_result_digest",
        "continuation_request_capture_ref",
        "continuation_request_capture_sha256",
        "continuation_request_digest",
        "continuation_response_capture_ref",
        "continuation_response_capture_sha256",
        "continuation_response_digest",
        "continuation_messages_digest",
        "finish_reason",
        "continuation_draft_digest",
        "continuation_draft_character_count",
        "merged_analysis_draft_digest",
        "merged_analysis_draft_character_count",
        "required_outputs",
        "completed_outputs",
        "continuation_completed_outputs",
        "completion_receipt",
        "usage",
        "source_analysis_token_budget_basis",
        "submission_policy",
        "claims",
        "recorded_at",
        "checkpoint_digest",
    }
    basis = deepcopy(dict(value.get("source_analysis_token_budget_basis") or {}))
    basis_digest = str(basis.pop("token_budget_basis_digest", ""))
    required_outputs = list(value.get("required_outputs") or [])
    continuation_outputs = list(
        value.get("continuation_completed_outputs") or []
    )
    digest_fields = (
        "fragment_checkpoint_sha256",
        "fragment_checkpoint_digest",
        "source_continuation_authority_sha256",
        "source_continuation_result_sha256",
        "source_continuation_result_digest",
        "continuation_request_capture_sha256",
        "continuation_request_digest",
        "continuation_response_capture_sha256",
        "continuation_response_digest",
        "continuation_messages_digest",
        "continuation_draft_digest",
        "merged_analysis_draft_digest",
    )
    _require(
        set(value) == expected
        and value.get("schema_version")
        == ANALYSIS_COMPLETION_CHECKPOINT_SCHEMA_VERSION
        and value.get("status")
        == "visible_analysis_fragments_complete_bound_for_submission"
        and value.get("finish_reason") == "stop"
        and value.get("required_outputs") == value.get("completed_outputs")
        and bool(required_outputs)
        and bool(continuation_outputs)
        and len(required_outputs) == len(set(required_outputs))
        and len(continuation_outputs) == len(set(continuation_outputs))
        and all(item in required_outputs for item in continuation_outputs)
        and value.get("completion_receipt")
        == "COMPLETED_OUTPUTS::" + "|".join(continuation_outputs)
        and value.get("submission_policy")
        == {
            "analysis_rerun_forbidden": True,
            "continuation_rerun_forbidden": True,
            "strict_submission_required": True,
            "new_fact_or_authority_forbidden": True,
            "merged_draft_business_promotion": False,
        }
        and value.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        }
        and all(
            len(str(value.get(field) or "")) == 64
            and all(
                ch in "0123456789abcdef"
                for ch in str(value.get(field) or "")
            )
            for field in digest_fields
        )
        and basis.get("schema_version") == TOKEN_BUDGET_BASIS_SCHEMA_VERSION
        and basis_digest == canonical_digest(basis)
        and int(value.get("continuation_draft_character_count") or 0) >= 20
        and int(value.get("merged_analysis_draft_character_count") or 0) >= 40,
        "multi_agent_analysis_completion_shape_invalid",
    )
    checkpoint_digest = str(value.pop("checkpoint_digest", ""))
    _require(
        checkpoint_digest == canonical_digest(value),
        "multi_agent_analysis_completion_digest_invalid",
    )
    return {**value, "checkpoint_digest": checkpoint_digest}


def compile_specialist_plan_checkpoint(
    *,
    topology: Mapping[str, Any],
    predecessor_authority_ref: str,
    predecessor_authority_sha256: str,
    predecessor_result_ref: str,
    predecessor_result_sha256: str,
    predecessor_result_digest: str,
    terminal_failure: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract immutable, contract-valid specialist plans from a failed run."""

    trusted = load_multi_agent_role_topology(topology)
    terminal_body = deepcopy(dict(terminal_failure))
    preserved_full_digest = str(terminal_body.pop("full_result_digest", ""))
    _require(
        preserved_full_digest == canonical_digest(terminal_body),
        "multi_agent_plan_checkpoint_full_result_digest_invalid",
    )
    _require(
        terminal_failure.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and terminal_failure.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted",
        "multi_agent_plan_checkpoint_predecessor_failure_invalid",
    )
    execution = terminal_failure.get("execution") or {}
    nodes = terminal_failure.get("node_executions") or []
    terminal_attempts = terminal_failure.get("terminal_node_attempts") or []
    _require(
        execution.get("model_nodes_started") == 7
        and execution.get("provider_attempts_preserved") == 11
        and execution.get("external_source_network_calls") == 0
        and execution.get("candidate_promotions") == 0
        and len(nodes) == len(SPECIALIST_AGENT_IDS)
        and len(terminal_attempts) == 2
        and all(
            row.get("failure_code") == "model_gateway_reasoning_budget_exhausted"
            for row in terminal_attempts
        ),
        "multi_agent_plan_checkpoint_predecessor_shape_invalid",
    )
    by_agent: dict[str, dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    for node in nodes:
        agent_id = str(node.get("agent_id") or "")
        _require(
            agent_id in SPECIALIST_AGENT_IDS
            and str(node.get("node_id") or "") == f"{agent_id}::PLAN"
            and agent_id not in by_agent,
            "multi_agent_plan_checkpoint_node_identity_invalid",
        )
        preserved_payload = deepcopy(dict(node.get("validated_payload") or {}))
        preserved_plan_digest = preserved_payload.pop("plan_opinion_digest", "")
        payload = validate_specialist_plan_opinion(
            preserved_payload,
            topology=trusted,
            expected_agent_id=agent_id,
        )
        _require(
            preserved_plan_digest == payload["plan_opinion_digest"],
            "multi_agent_plan_checkpoint_plan_digest_invalid",
        )
        attempts = node.get("attempts") or []
        _require(
            bool(attempts)
            and attempts[-1].get("status") == "contract_valid"
            and attempts[-1].get("validated_payload_digest")
            == canonical_digest(payload),
            "multi_agent_plan_checkpoint_attempt_invalid",
        )
        by_agent[agent_id] = payload
        receipts.append(
            {
                "agent_id": agent_id,
                "node_id": str(node["node_id"]),
                "attempt_ids": [str(row["attempt_id"]) for row in attempts],
                "request_digests": [str(row.get("request_digest") or "") for row in attempts],
                "response_digests": [str(row.get("response_digest") or "") for row in attempts],
                "validated_payload_digest": canonical_digest(payload),
            }
        )
    _require(
        set(by_agent) == set(SPECIALIST_AGENT_IDS),
        "multi_agent_plan_checkpoint_agent_set_invalid",
    )
    body = {
        "schema_version": SPECIALIST_PLAN_CHECKPOINT_SCHEMA_VERSION,
        "status": "six_R3_specialist_plans_valid_for_Lead_successor_resume",
        "case_key": "DELL",
        "predecessor_run_id": (
            "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R3_20260820"
        ),
        "predecessor_authority_ref": str(predecessor_authority_ref),
        "predecessor_authority_sha256": str(predecessor_authority_sha256),
        "predecessor_result_ref": str(predecessor_result_ref),
        "predecessor_result_sha256": str(predecessor_result_sha256),
        "predecessor_result_digest": str(predecessor_result_digest),
        "predecessor_full_result_digest": str(
            preserved_full_digest
        ),
        "specialist_plans": [
            deepcopy(by_agent[agent_id]) for agent_id in SPECIALIST_AGENT_IDS
        ],
        "plan_attempt_receipts": receipts,
        "reused_specialist_plan_count": len(SPECIALIST_AGENT_IDS),
        "new_model_calls": 0,
        "new_network_calls": 0,
        "new_candidate_promotions": 0,
        "checkpoint_authority": (
            "Validated plan payloads may resume at Research Lead only; they are "
            "not Evidence, NumericFact, research conclusions or stage acceptance."
        ),
    }
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_specialist_plan_checkpoint(
    payload: Mapping[str, Any],
    *,
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "status",
        "case_key",
        "predecessor_run_id",
        "predecessor_authority_ref",
        "predecessor_authority_sha256",
        "predecessor_result_ref",
        "predecessor_result_sha256",
        "predecessor_result_digest",
        "predecessor_full_result_digest",
        "specialist_plans",
        "plan_attempt_receipts",
        "reused_specialist_plan_count",
        "new_model_calls",
        "new_network_calls",
        "new_candidate_promotions",
        "checkpoint_authority",
        "checkpoint_digest",
    }
    value = deepcopy(dict(payload))
    _require(
        set(value) == expected
        and value.get("schema_version")
        == SPECIALIST_PLAN_CHECKPOINT_SCHEMA_VERSION
        and value.get("status")
        == "six_R3_specialist_plans_valid_for_Lead_successor_resume"
        and value.get("case_key") == "DELL"
        and value.get("reused_specialist_plan_count") == len(SPECIALIST_AGENT_IDS)
        and value.get("new_model_calls") == 0
        and value.get("new_network_calls") == 0
        and value.get("new_candidate_promotions") == 0,
        "multi_agent_plan_checkpoint_identity_invalid",
    )
    plans = value.get("specialist_plans") or []
    _require(
        len(plans) == len(SPECIALIST_AGENT_IDS)
        and len(value.get("plan_attempt_receipts") or [])
        == len(SPECIALIST_AGENT_IDS),
        "multi_agent_plan_checkpoint_count_invalid",
    )
    normalized = []
    for row, agent_id in zip(plans, SPECIALIST_AGENT_IDS, strict=True):
        preserved = deepcopy(dict(row))
        preserved_digest = preserved.pop("plan_opinion_digest", "")
        plan = validate_specialist_plan_opinion(
            preserved,
            topology=topology,
            expected_agent_id=agent_id,
        )
        _require(
            preserved_digest == plan["plan_opinion_digest"],
            "multi_agent_plan_checkpoint_plan_digest_invalid",
        )
        normalized.append(plan)
    receipt_by_agent = {
        str(row.get("agent_id") or ""): row
        for row in value["plan_attempt_receipts"]
    }
    _require(
        set(receipt_by_agent) == set(SPECIALIST_AGENT_IDS)
        and all(
            receipt_by_agent[agent_id].get("validated_payload_digest")
            == canonical_digest(plan)
            and receipt_by_agent[agent_id].get("attempt_ids")
            and all(receipt_by_agent[agent_id].get("request_digests") or [])
            and all(receipt_by_agent[agent_id].get("response_digests") or [])
            for agent_id, plan in zip(
                SPECIALIST_AGENT_IDS, normalized, strict=True
            )
        ),
        "multi_agent_plan_checkpoint_receipt_invalid",
    )
    digest = value.pop("checkpoint_digest")
    _require(
        digest == canonical_digest(value),
        "multi_agent_plan_checkpoint_digest_invalid",
    )
    value["specialist_plans"] = normalized
    return {**value, "checkpoint_digest": digest}


def validate_lead_plan(
    payload: Mapping[str, Any],
    *,
    opinions: Sequence[Mapping[str, Any]],
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = load_multi_agent_role_topology(topology)
    cardinality = compile_lead_plan_cardinality_policy(topology=trusted)["fields"]
    expected = {
        "schema_version",
        "lead_agent_id",
        "accepted_agent_ids",
        "ordered_agent_ids",
        "accepted_facets",
        "coordination_questions",
        "expected_information_boundaries",
        "stop_conditions",
    }
    value = deepcopy(dict(payload))
    _require(
        set(value) == expected
        and value.get("schema_version") == LEAD_PLAN_SCHEMA_VERSION
        and value.get("lead_agent_id") == RESEARCH_LEAD_AGENT_ID,
        "multi_agent_lead_plan_identity_invalid",
    )
    proposed_agents = {str(row["agent_id"]) for row in opinions}
    _require(
        proposed_agents == set(SPECIALIST_AGENT_IDS),
        "multi_agent_lead_plan_opinion_set_invalid",
    )
    accepted = _strings(
        value["accepted_agent_ids"],
        "multi_agent_lead_agents_invalid",
        minimum=len(SPECIALIST_AGENT_IDS),
        maximum=len(SPECIALIST_AGENT_IDS),
        maximum_chars=80,
    )
    ordered = _strings(
        value["ordered_agent_ids"],
        "multi_agent_lead_order_invalid",
        minimum=len(SPECIALIST_AGENT_IDS),
        maximum=len(SPECIALIST_AGENT_IDS),
        maximum_chars=80,
    )
    _require(
        set(accepted) == set(SPECIALIST_AGENT_IDS)
        and set(ordered) == set(SPECIALIST_AGENT_IDS),
        "multi_agent_lead_agents_invalid",
    )
    proposed_facets = {
        str(atom["facet_id"])
        for opinion in opinions
        for atom in opinion["requested_atoms"]
    }
    accepted_facets = _strings(
        value["accepted_facets"],
        "multi_agent_lead_facets_invalid",
        minimum=5,
        maximum=len(trusted["facet_catalog"]),
        maximum_chars=80,
    )
    _require(
        set(accepted_facets).issubset(proposed_facets)
        and set(accepted_facets).issubset(trusted["facet_catalog"]),
        "multi_agent_lead_facets_invalid",
    )
    covered_slots = {
        str(trusted["facet_catalog"][facet_id]["slot_id"])
        for facet_id in accepted_facets
    }
    required_slots = {
        str(row["slot_id"])
        for row in trusted["facet_catalog"].values()
    }
    _require(
        required_slots.issubset(covered_slots),
        "multi_agent_lead_required_slot_uncovered",
    )
    for field in (
        "coordination_questions",
        "expected_information_boundaries",
        "stop_conditions",
    ):
        value[field] = _strings(
            value[field],
            f"multi_agent_lead_{field}_invalid",
            minimum=int(cardinality[field]["minimum"]),
            maximum=int(cardinality[field]["maximum"]),
            maximum_chars=int(cardinality[field]["maximum_chars"]),
        )
    value["accepted_agent_ids"] = accepted
    value["ordered_agent_ids"] = ordered
    value["accepted_facets"] = accepted_facets
    value["lead_plan_digest"] = canonical_digest(value)
    return value


def compile_lead_plan_checkpoint(
    *,
    case_key: str,
    node_id: str,
    source_run_id: str,
    source_authority_ref: str,
    source_authority_sha256: str,
    source_public_result_ref: str,
    source_public_result_sha256: str,
    source_public_result_digest: str,
    source_failure_code: str,
    selected_attempt_id: str,
    request_capture_ref: str,
    request_capture_sha256: str,
    request_digest: str,
    response_capture_ref: str,
    response_capture_sha256: str,
    response_digest: str,
    specialist_plan_checkpoint_ref: str,
    specialist_plan_checkpoint_sha256: str,
    specialist_plan_checkpoint_digest: str,
    lead_plan_payload: Mapping[str, Any],
    opinions: Sequence[Mapping[str, Any]],
    topology: Mapping[str, Any],
    predecessor_contract_feedback: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Bind one captured, newly revalidated Lead submission for successor use.

    The predecessor run remains a terminal failure.  This checkpoint is a new
    local artifact proving that the captured payload satisfies the corrected,
    topology-derived contract without a model or network call.
    """

    trusted_topology = load_multi_agent_role_topology(topology)
    validated = validate_lead_plan(
        lead_plan_payload,
        opinions=opinions,
        topology=trusted_topology,
    )
    policy = compile_lead_plan_cardinality_policy(topology=trusted_topology)
    hashes = (
        source_authority_sha256,
        source_public_result_sha256,
        source_public_result_digest,
        request_capture_sha256,
        request_digest,
        response_capture_sha256,
        response_digest,
        specialist_plan_checkpoint_sha256,
        specialist_plan_checkpoint_digest,
    )
    _require(
        case_key == "DELL"
        and node_id == "AGENT::RESEARCH_LEAD::LEAD_PLAN"
        and all(
            len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
            for value in hashes
        )
        and bool(source_run_id)
        and bool(source_failure_code)
        and bool(selected_attempt_id)
        and bool(created_at),
        "multi_agent_lead_plan_checkpoint_identity_invalid",
    )
    body = {
        "schema_version": LEAD_PLAN_CHECKPOINT_SCHEMA_VERSION,
        "case_key": case_key,
        "node_id": node_id,
        "source_run_id": source_run_id,
        "source_authority_ref": source_authority_ref,
        "source_authority_sha256": source_authority_sha256,
        "source_public_result_ref": source_public_result_ref,
        "source_public_result_sha256": source_public_result_sha256,
        "source_public_result_digest": source_public_result_digest,
        "source_failure_code": source_failure_code,
        "source_run_status_preserved_as_failure": True,
        "selected_attempt_id": selected_attempt_id,
        "request_capture_ref": request_capture_ref,
        "request_capture_sha256": request_capture_sha256,
        "request_digest": request_digest,
        "response_capture_ref": response_capture_ref,
        "response_capture_sha256": response_capture_sha256,
        "response_digest": response_digest,
        "specialist_plan_checkpoint_ref": specialist_plan_checkpoint_ref,
        "specialist_plan_checkpoint_sha256": specialist_plan_checkpoint_sha256,
        "specialist_plan_checkpoint_digest": specialist_plan_checkpoint_digest,
        "cardinality_policy": policy,
        "predecessor_contract_feedback": deepcopy(
            dict(predecessor_contract_feedback)
        ),
        "lead_plan": validated,
        "new_model_calls": 0,
        "new_network_calls": 0,
        "new_candidate_promotions": 0,
        "created_at": created_at,
    }
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_lead_plan_checkpoint(
    payload: Mapping[str, Any],
    *,
    opinions: Sequence[Mapping[str, Any]],
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "case_key",
        "node_id",
        "source_run_id",
        "source_authority_ref",
        "source_authority_sha256",
        "source_public_result_ref",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_failure_code",
        "source_run_status_preserved_as_failure",
        "selected_attempt_id",
        "request_capture_ref",
        "request_capture_sha256",
        "request_digest",
        "response_capture_ref",
        "response_capture_sha256",
        "response_digest",
        "specialist_plan_checkpoint_ref",
        "specialist_plan_checkpoint_sha256",
        "specialist_plan_checkpoint_digest",
        "cardinality_policy",
        "predecessor_contract_feedback",
        "lead_plan",
        "new_model_calls",
        "new_network_calls",
        "new_candidate_promotions",
        "created_at",
        "checkpoint_digest",
    }
    value = deepcopy(dict(payload))
    _require(
        set(value) == expected
        and value.get("schema_version") == LEAD_PLAN_CHECKPOINT_SCHEMA_VERSION
        and value.get("case_key") == "DELL"
        and value.get("node_id") == "AGENT::RESEARCH_LEAD::LEAD_PLAN"
        and value.get("source_run_status_preserved_as_failure") is True
        and value.get("new_model_calls") == 0
        and value.get("new_network_calls") == 0
        and value.get("new_candidate_promotions") == 0,
        "multi_agent_lead_plan_checkpoint_identity_invalid",
    )
    trusted_topology = load_multi_agent_role_topology(topology)
    expected_policy = compile_lead_plan_cardinality_policy(
        topology=trusted_topology
    )
    _require(
        value.get("cardinality_policy") == expected_policy,
        "multi_agent_lead_plan_checkpoint_policy_drift",
    )
    preserved_lead = deepcopy(dict(value["lead_plan"]))
    preserved_digest = preserved_lead.pop("lead_plan_digest", "")
    lead = validate_lead_plan(
        preserved_lead,
        opinions=opinions,
        topology=trusted_topology,
    )
    _require(
        preserved_digest == lead["lead_plan_digest"],
        "multi_agent_lead_plan_checkpoint_plan_digest_invalid",
    )
    digest = str(value.pop("checkpoint_digest") or "")
    _require(
        digest == canonical_digest(value),
        "multi_agent_lead_plan_checkpoint_digest_invalid",
    )
    value["lead_plan"] = lead
    return {**value, "checkpoint_digest": digest}


def compile_planner_payload_from_role_opinions(
    *,
    objective_id: str,
    opinions: Sequence[Mapping[str, Any]],
    lead_plan: Mapping[str, Any],
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    trusted = load_multi_agent_role_topology(topology)
    accepted = set(lead_plan["accepted_facets"])
    by_facet: dict[str, dict[str, Any]] = {}
    for opinion in opinions:
        agent_id = str(opinion["agent_id"])
        for raw in opinion["requested_atoms"]:
            facet_id = str(raw["facet_id"])
            if facet_id not in accepted:
                continue
            catalog = trusted["facet_catalog"][facet_id]
            row = by_facet.setdefault(
                facet_id,
                {
                    "facet_id": facet_id,
                    "target_entity": str(catalog["target_entity"]),
                    "metric_ids": list(catalog["metric_ids"]),
                    "product_intents": [],
                    "proposing_agent_ids": [],
                },
            )
            row["proposing_agent_ids"].append(agent_id)
            for intent in raw["product_intents"]:
                executable_intents = _compile_executable_product_intents(
                    str(intent)
                )
                for executable_intent in executable_intents:
                    if executable_intent not in row["product_intents"]:
                        row["product_intents"].append(executable_intent)
            _require(
                len(row["product_intents"]) <= 4,
                "multi_agent_compiled_product_intent_budget_invalid",
            )
    _require(
        5 <= len(by_facet) <= len(trusted["facet_catalog"])
        and all(row["product_intents"] for row in by_facet.values()),
        "multi_agent_compiled_planner_atoms_invalid",
    )
    atoms = [
        {
            key: deepcopy(row[key])
            for key in (
                "facet_id",
                "target_entity",
                "metric_ids",
                "product_intents",
            )
        }
        for row in by_facet.values()
    ]
    role_bindings = [
        {
            "facet_id": facet_id,
            "proposing_agent_ids": sorted(set(row["proposing_agent_ids"])),
        }
        for facet_id, row in sorted(by_facet.items())
    ]
    payload = {
        "schema_version": "fin_ia_research_planner_atoms_v1_0",
        "objective_id": str(objective_id),
        "atoms": atoms,
    }
    return {
        "planner_payload": payload,
        "role_facet_bindings": role_bindings,
        "planner_payload_digest": canonical_digest(payload),
    }


def _compile_executable_product_intents(
    value: str,
    *,
    maximum_chars: int = 120,
) -> tuple[str, ...]:
    """Losslessly split plan prose into EvidenceRequest-sized query atoms."""

    text = str(value or "").strip()
    _require(bool(text), "multi_agent_product_intent_missing")
    if len(text) <= maximum_chars:
        return (text,)
    without_terminal = text.rstrip(".。；;")
    if len(without_terminal) <= maximum_chars:
        return (without_terminal,)
    chunks: list[str] = []
    remaining = text
    preferred = ("。", ";", "；", ",", "，", " ")
    while len(remaining) > maximum_chars:
        window = remaining[: maximum_chars + 1]
        split_at = -1
        for delimiter in preferred:
            candidate = window.rfind(delimiter)
            if candidate >= max(20, maximum_chars // 2):
                split_at = candidate + (0 if delimiter == " " else 1)
                break
        if split_at <= 0:
            split_at = maximum_chars
        chunk = remaining[:split_at].strip(" ,，;；")
        _require(
            bool(chunk) and len(chunk) <= maximum_chars,
            "multi_agent_product_intent_split_invalid",
        )
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining.rstrip(".。；;").strip())
    _require(
        all(0 < len(chunk) <= maximum_chars for chunk in chunks),
        "multi_agent_product_intent_split_invalid",
    )
    return tuple(chunks)


def compile_specialist_context(
    *,
    topology: Mapping[str, Any],
    agent_id: str,
    research_input: Mapping[str, Any],
    tool_execution_input: Mapping[str, Any] | None = None,
    case_truth_packet: Mapping[str, Any],
    plan_opinion: Mapping[str, Any],
    lead_plan: Mapping[str, Any],
    feedback_receipts: Sequence[Mapping[str, Any]] = (),
    prior_workpaper: Mapping[str, Any] | None = None,
    context_scope: str = "initial_workpaper",
) -> dict[str, Any]:
    _require(
        context_scope in {"initial_workpaper", "role_repair"},
        "multi_agent_specialist_context_scope_invalid",
    )
    trusted = load_multi_agent_role_topology(topology)
    agent = _agent_index(trusted).get(agent_id)
    _require(
        agent_id in SPECIALIST_AGENT_IDS and agent is not None,
        "multi_agent_specialist_unknown",
    )
    cell_view = compile_five_cell_analysis_view(
        research_input=research_input,
        cell_id=str(agent["cell_id"]),
    )
    role_slots = {
        str(trusted["facet_catalog"][atom["facet_id"]]["slot_id"])
        for atom in plan_opinion["requested_atoms"]
    }
    evidence_slots = {
        str(card["evidence_ref"]): {
            str(binding.get("slot_id") or "")
            for binding in card.get("slot_bindings") or ()
            if isinstance(binding, Mapping)
        }
        for card in research_input.get("evidence_cards") or ()
        if isinstance(card, Mapping)
    }
    allowed_role_evidence = {
        ref for ref, slots in evidence_slots.items() if slots.intersection(role_slots)
    }
    cell_view["cell"]["cell_evidence_views"] = [
        row
        for row in cell_view["cell"]["cell_evidence_views"]
        if str(row.get("evidence_ref") or "") in allowed_role_evidence
    ]
    catalog = cell_view.get("evidence_fact_catalog")
    if isinstance(catalog, list):
        cell_view["evidence_fact_catalog"] = [
            row
            for row in catalog
            if str(row.get("evidence_ref") or "") in allowed_role_evidence
        ]
    elif isinstance(catalog, Mapping):
        cell_view["evidence_fact_catalog"] = {
            ref: row
            for ref, row in catalog.items()
            if str(ref) in allowed_role_evidence
        }
    cell_view["cell"]["residual_gap_cards"] = [
        row
        for row in cell_view["cell"]["residual_gap_cards"]
        if str(row.get("slot_id") or "") in role_slots
    ]
    cell_view["cell"]["selected_planner_facets"] = [
        str(atom["facet_id"]) for atom in plan_opinion["requested_atoms"]
    ]
    if agent_id == "AGENT::SUPPLY_RELATIONSHIP":
        cell_view["cell"]["allowed_numeric_refs"] = []
        cell_view["cell"]["allowed_numeric_relation_refs"] = []
        cell_view["numeric_fact_catalog"] = []
        cell_view["numeric_relation_catalog"] = []
        cell_view["cell"]["role_method_pack"] = deepcopy(
            agent["preview_method_pack"]
        )
    cell_view["projection_receipt"]["role_slot_ids"] = sorted(role_slots)
    cell_view["projection_receipt"]["role_evidence_ref_count"] = len(
        cell_view["cell"]["cell_evidence_views"]
    )
    model_truth = compile_case_truth_model_view(case_truth_packet)
    tool_receipts = []
    if tool_execution_input is not None:
        for raw in tool_execution_input.get("dynamic_evidence_response_cards") or ():
            if not isinstance(raw, Mapping):
                continue
            bindings = raw.get("request_bindings") or ()
            if any(
                str(binding.get("slot_id") or "") in role_slots
                for binding in bindings
                if isinstance(binding, Mapping)
            ):
                tool_receipts.append(deepcopy(dict(raw)))
    body = {
        "schema_version": SPECIALIST_CONTEXT_SCHEMA_VERSION,
        "agent": {
            key: deepcopy(agent[key])
            for key in (
                "agent_id",
                "name_zh",
                "cell_id",
                "responsibilities",
                "allowed_facet_ids",
            )
        },
        "plan_opinion": deepcopy(dict(plan_opinion)),
        "lead_plan": deepcopy(dict(lead_plan)),
        "cell_analysis_view": cell_view,
        "case_fact_presence": model_truth,
        "tool_execution_receipts": tool_receipts,
        "feedback_receipts": [deepcopy(dict(row)) for row in feedback_receipts],
        "prior_workpaper": (
            deepcopy(dict(prior_workpaper)) if prior_workpaper is not None else None
        ),
        "rules": [
            "Cell-local invisibility is not case-level absence.",
            "A typed gap proves only the named tool or authority boundary; it does not prove public non-disclosure.",
            "Candidate, graph edge, Skill text and model memory are not Evidence.",
            "Company-level financial movement does not prove AI product causality without a direct bridge.",
            "Use the full case-fact-presence catalog before asserting that a fact is absent.",
            "Return a bounded workpaper, not a publishable report.",
        ],
        "authority": {
            "working_draft_not_business_truth": True,
            "model_owns_judgment": True,
            "harness_may_validate_but_not_invent": True,
        },
    }
    body["context_digest"] = canonical_digest(body)
    if context_scope == "role_repair":
        return compile_specialist_repair_context(body)
    return body


def _truth_aliases(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(alias)
            for row in rows
            for alias in row.get("truth_aliases") or ()
            if str(alias)
        }
    )


def _project_repair_presence_catalog(
    *,
    full_presence: Sequence[Mapping[str, Any]],
    current_cell_presence_aliases: set[str],
    role_slot_ids: set[str],
    allowed_evidence_refs: set[str],
    allowed_numeric_refs: set[str],
    allowed_relation_refs: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    allowed_numeric_aliases = {
        f"TRUTH::NUMERIC::{ref}" for ref in allowed_numeric_refs
    }
    allowed_relation_aliases = {
        f"TRUTH::RELATION::{ref}" for ref in allowed_relation_refs
    }
    for raw in full_presence:
        row = deepcopy(dict(raw))
        kind = str(row.get("truth_kind") or "")
        aliases = {
            str(alias)
            for alias in row.get("truth_aliases") or ()
            if str(alias) in current_cell_presence_aliases
        }
        if kind == "reviewed_evidence_facet":
            aliases = {
                alias
                for alias in aliases
                if any(
                    alias.startswith(f"TRUTH::FACET::{slot_id}::")
                    for slot_id in role_slot_ids
                )
            }
            if not allowed_evidence_refs.intersection(
                str(ref) for ref in row.get("evidence_refs") or ()
            ):
                aliases = set()
        elif kind == "numeric_fact":
            aliases &= allowed_numeric_aliases
        elif kind == "numeric_relation":
            aliases &= allowed_relation_aliases
        elif kind == "source_bound_qualitative_fact":
            # Qualitative facts are already cell-scoped by the canonical truth
            # packet.  No such facts are present in the current DELL Preview,
            # but preserving the branch keeps the projection provider-neutral.
            aliases = set(aliases)
        else:
            raise MultiAgentPreviewError(
                "multi_agent_specialist_repair_truth_kind_invalid"
            )
        if not aliases:
            continue
        compact = {
            key: deepcopy(value)
            for key, value in row.items()
            if key
            not in {
                "truth_aliases",
                "business_meanings_zh",
                "claim_boundaries_zh",
            }
        }
        compact["truth_aliases"] = sorted(aliases)
        selected.append(compact)
    return sorted(
        selected,
        key=lambda row: (str(row["truth_kind"]), row["truth_aliases"]),
    )


def _project_specialist_repair_case_truth(
    *,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    full = deepcopy(dict(context["case_fact_presence"]))
    full_truth_digest = str(
        full.get("case_truth_model_view_digest") or ""
    )
    _require(
        full_truth_digest
        and full_truth_digest
        == canonical_digest(
            {
                key: value
                for key, value in full.items()
                if key != "case_truth_model_view_digest"
            }
        ),
        "multi_agent_specialist_repair_case_truth_invalid",
    )
    cell_view = context["cell_analysis_view"]
    cell = cell_view["cell"]
    agent = context["agent"]
    role_slot_ids = {
        str(value)
        for value in cell_view["projection_receipt"].get("role_slot_ids") or ()
    }
    allowed_evidence_refs = {
        str(row["evidence_ref"])
        for row in cell.get("cell_evidence_views") or ()
    }
    allowed_numeric_refs = {
        str(value) for value in cell.get("allowed_numeric_refs") or ()
    }
    allowed_relation_refs = {
        str(value)
        for value in cell.get("allowed_numeric_relation_refs") or ()
    }
    allowed_gap_refs = {
        str(row["gap_ref"])
        for row in cell.get("residual_gap_cards") or ()
    }
    cell_id = str(agent["cell_id"])
    visibility_rows = [
        deepcopy(dict(row))
        for row in full.get("cell_visibility_matrix") or ()
        if str(row.get("cell_id") or "") == cell_id
    ]
    _require(
        len(visibility_rows) == 1 and role_slot_ids,
        "multi_agent_specialist_repair_visibility_invalid",
    )
    visibility = visibility_rows[0]
    current_cell_presence_aliases = {
        str(value) for value in visibility.get("visible_presence_aliases") or ()
    }
    selected_presence = _project_repair_presence_catalog(
        full_presence=full.get("presence_catalog") or (),
        current_cell_presence_aliases=current_cell_presence_aliases,
        role_slot_ids=role_slot_ids,
        allowed_evidence_refs=allowed_evidence_refs,
        allowed_numeric_refs=allowed_numeric_refs,
        allowed_relation_refs=allowed_relation_refs,
    )
    selected_presence_aliases = set(_truth_aliases(selected_presence))

    selected_gaps = []
    for raw in full.get("typed_gap_catalog") or ():
        row = deepcopy(dict(raw))
        matching_refs = sorted(
            allowed_gap_refs.intersection(
                str(ref) for ref in row.get("gap_refs") or ()
            )
        )
        if not matching_refs:
            continue
        row["gap_refs"] = matching_refs
        selected_gaps.append(row)
    selected_gaps.sort(key=lambda row: str(row["truth_alias"]))
    selected_gap_aliases = {
        str(row["truth_alias"]) for row in selected_gaps
    }

    visible_bridge_aliases = {
        str(value)
        for value in visibility.get("visible_bridge_boundary_aliases") or ()
    }
    selected_bridges = [
        deepcopy(dict(row))
        for row in full.get("typed_bridge_boundary_catalog") or ()
        if str(row.get("truth_alias") or "") in visible_bridge_aliases
        and set(str(ref) for ref in row.get("required_gap_refs") or ()).issubset(
            allowed_gap_refs
        )
    ]
    selected_bridges.sort(key=lambda row: str(row["truth_alias"]))
    selected_bridge_aliases = {
        str(row["truth_alias"]) for row in selected_bridges
    }

    all_presence_aliases = set(
        _truth_aliases(full.get("presence_catalog") or ())
    )
    all_gap_aliases = {
        str(row["truth_alias"])
        for row in full.get("typed_gap_catalog") or ()
    }
    all_bridge_aliases = {
        str(row["truth_alias"])
        for row in full.get("typed_bridge_boundary_catalog") or ()
    }
    omitted_presence_aliases = sorted(
        all_presence_aliases - selected_presence_aliases
    )
    omitted_gap_aliases = sorted(all_gap_aliases - selected_gap_aliases)
    omitted_bridge_aliases = sorted(
        all_bridge_aliases - selected_bridge_aliases
    )
    omitted_receipt = {
        "presence_alias_count": len(omitted_presence_aliases),
        "presence_alias_digest": canonical_digest(omitted_presence_aliases),
        "typed_gap_alias_count": len(omitted_gap_aliases),
        "typed_gap_alias_digest": canonical_digest(omitted_gap_aliases),
        "typed_bridge_alias_count": len(omitted_bridge_aliases),
        "typed_bridge_alias_digest": canonical_digest(
            omitted_bridge_aliases
        ),
        "omission_semantics": (
            "not_role_authorized_or_not_needed_for_this_local_repair; "
            "omission_never_proves_case_absence"
        ),
    }
    unsigned = {
        "schema_version": "fin_ia_specialist_repair_case_truth_view_v1_0",
        "source_case_truth_packet_digest": str(
            full["case_truth_packet_digest"]
        ),
        "source_case_truth_model_view_digest": str(
            full_truth_digest
        ),
        "case_identity": deepcopy(full["case_identity"]),
        "role_scope": {
            "agent_id": str(agent["agent_id"]),
            "cell_id": cell_id,
            "role_slot_ids": sorted(role_slot_ids),
            "allowed_evidence_refs": sorted(allowed_evidence_refs),
            "allowed_numeric_refs": sorted(allowed_numeric_refs),
            "allowed_numeric_relation_refs": sorted(
                allowed_relation_refs
            ),
            "allowed_gap_refs": sorted(allowed_gap_refs),
        },
        "role_presence_catalog": selected_presence,
        "role_typed_gap_catalog": selected_gaps,
        "role_typed_bridge_boundary_catalog": selected_bridges,
        "role_visibility": {
            "cell_id": cell_id,
            "visible_presence_aliases": sorted(selected_presence_aliases),
            "visible_gap_aliases": sorted(selected_gap_aliases),
            "visible_bridge_boundary_aliases": sorted(
                selected_bridge_aliases
            ),
        },
        "omitted_case_truth_receipt": omitted_receipt,
        "authority": {
            "full_case_truth_remains_harness_bound": True,
            "role_prompt_omission_is_not_case_absence": True,
            "case_absence_requires_visible_typed_gap_or_bridge_boundary": True,
            "cell_local_invisibility_is_not_case_level_absence": True,
        },
    }
    return {
        **unsigned,
        "repair_case_truth_view_digest": canonical_digest(unsigned),
    }


def _project_specialist_repair_lead_plan(
    *,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    lead = deepcopy(dict(context["lead_plan"]))
    lead_digest = str(lead.get("lead_plan_digest") or "")
    _require(
        lead_digest
        and lead_digest
        == canonical_digest(
            {
                key: value
                for key, value in lead.items()
                if key != "lead_plan_digest"
            }
        ),
        "multi_agent_specialist_repair_lead_plan_invalid",
    )
    agent_id = str(context["agent"]["agent_id"])
    requested_facets = [
        str(row["facet_id"])
        for row in context["plan_opinion"].get("requested_atoms") or ()
    ]
    accepted_facets = [
        facet
        for facet in lead.get("accepted_facets") or ()
        if str(facet) in requested_facets
    ]
    accepted_agents = [
        str(value) for value in lead.get("accepted_agent_ids") or ()
    ]
    ordered_agents = [
        str(value) for value in lead.get("ordered_agent_ids") or ()
    ]
    _require(
        agent_id in accepted_agents
        and agent_id in ordered_agents
        and set(accepted_facets) == set(requested_facets),
        "multi_agent_specialist_repair_lead_scope_invalid",
    )
    feedback_ids = [
        str(row.get("feedback_id") or "")
        for row in context.get("feedback_receipts") or ()
    ]
    _require(
        feedback_ids
        and all(feedback_ids)
        and all(
            str(row.get("target_node_id") or "") == agent_id
            for row in context.get("feedback_receipts") or ()
        ),
        "multi_agent_specialist_repair_feedback_scope_invalid",
    )
    global_fields = {
        field: list(lead.get(field) or ())
        for field in (
            "coordination_questions",
            "expected_information_boundaries",
            "stop_conditions",
        )
    }
    unsigned = {
        "schema_version": "fin_ia_specialist_repair_lead_scope_v1_0",
        "source_lead_plan_digest": lead_digest,
        "lead_agent_id": str(lead["lead_agent_id"]),
        "target_agent_id": agent_id,
        "target_agent_order": ordered_agents.index(agent_id),
        "target_accepted_facet_ids": sorted(accepted_facets),
        "active_feedback_ids": feedback_ids,
        "global_plan_receipt": {
            field: {
                "count": len(values),
                "digest": canonical_digest(values),
            }
            for field, values in global_fields.items()
        },
        "authority": {
            "feedback_receipt_is_the_only_active_repair_instruction": True,
            "omitted_global_plan_text_is_not_new_research_authority": True,
            "repair_may_not_expand_facets_or_agent_scope": True,
        },
    }
    return {
        **unsigned,
        "repair_lead_scope_digest": canonical_digest(unsigned),
    }


def compile_specialist_repair_context(
    full_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a complete initial context into one local repair view.

    The role keeps every claimable Evidence/NumericFact/Gap object, its prior
    workpaper and the actionable feedback.  Whole-case truth and Lead planning
    remain digest-bound in the Harness but are not repeated as prose in every
    local repair prompt.
    """

    source = deepcopy(dict(full_context))
    source_digest = str(source.get("context_digest") or "")
    _require(
        source.get("schema_version") == SPECIALIST_CONTEXT_SCHEMA_VERSION
        and source_digest
        == canonical_digest(
            {
                key: value
                for key, value in source.items()
                if key != "context_digest"
            }
        )
        and source.get("prior_workpaper") is not None
        and bool(source.get("feedback_receipts")),
        "multi_agent_specialist_repair_source_context_invalid",
    )
    repair_truth = _project_specialist_repair_case_truth(context=source)
    repair_lead = _project_specialist_repair_lead_plan(context=source)
    body = {
        key: deepcopy(value)
        for key, value in source.items()
        if key
        not in {
            "schema_version",
            "context_digest",
            "case_fact_presence",
            "lead_plan",
            "rules",
        }
    }
    body.update(
        {
            "schema_version": SPECIALIST_REPAIR_CONTEXT_SCHEMA_VERSION,
            "context_scope": "role_repair",
            "source_full_context_digest": source_digest,
            "lead_plan": repair_lead,
            "case_fact_presence": repair_truth,
            "rules": [
                "Revise only the judgments named by the active FeedbackReceipt.",
                "All claimable role facts remain in cell_analysis_view; omitted whole-case rows remain Harness-bound and are not absent.",
                "A typed gap proves only the visible named tool or authority boundary; it does not prove public non-disclosure.",
                "Candidate, graph edge, Skill text and model memory are not Evidence.",
                "Company-level financial movement does not prove AI product causality without a direct bridge.",
                "Use only role_presence_catalog or visible typed boundaries for fact-presence claims; omission receipts are not business facts.",
                "Return a bounded workpaper, not a publishable report.",
            ],
            "repair_projection_receipt": {
                "source_full_context_digest": source_digest,
                "repair_case_truth_view_digest": repair_truth[
                    "repair_case_truth_view_digest"
                ],
                "repair_lead_scope_digest": repair_lead[
                    "repair_lead_scope_digest"
                ],
                "claimable_cell_evidence_count": len(
                    body["cell_analysis_view"]["cell"][
                        "cell_evidence_views"
                    ]
                ),
                "claimable_gap_count": len(
                    body["cell_analysis_view"]["cell"][
                        "residual_gap_cards"
                    ]
                ),
                "candidate_or_evidence_promotion_count": 0,
            },
        }
    )
    body["context_digest"] = canonical_digest(body)
    return body


def specialist_workpaper_tool(
    *,
    agent_id: str,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    view = context["cell_analysis_view"]
    evidence_refs = sorted(
        {
            str(row["evidence_ref"])
            for row in view["cell"]["cell_evidence_views"]
        }
    )
    numeric_refs = sorted(view["cell"]["allowed_numeric_refs"])
    relation_refs = sorted(view["cell"]["allowed_numeric_relation_refs"])
    gap_refs = sorted(
        str(row["gap_ref"])
        for row in view["cell"]["residual_gap_cards"]
    )

    def ref_array(values: Sequence[str]) -> dict[str, Any]:
        empty = not values
        return {
            "type": "array",
            "maxItems": max(len(values), 1),
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": list(values) if values else [_EMPTY_REF_PLACEHOLDER],
            },
            **(
                {
                    "description": (
                        "No business ref is authorized. Submit [] or the single "
                        "transport placeholder; the local validator normalizes the "
                        "placeholder to []."
                    )
                }
                if empty
                else {}
            ),
        }

    return {
        "type": "function",
        "function": {
            "name": "submit_specialist_workpaper",
            "description": "Submit one bounded specialist workpaper using only current authority.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "agent_id",
                    "thesis",
                    "confidence",
                    "sourced_claims",
                    "mechanism",
                    "alternative_explanations",
                    "strongest_counterarguments",
                    "remaining_gap_refs",
                    "what_would_change",
                    "cross_role_challenges",
                    "stop_reason",
                ],
                "properties": {
                    "schema_version": {"type": "string", "enum": [SPECIALIST_WORKPAPER_SCHEMA_VERSION]},
                    "agent_id": {"type": "string", "enum": [agent_id]},
                    "thesis": {"type": "string", "minLength": 30, "maxLength": 1800},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low", "insufficient_evidence"]},
                    "sourced_claims": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 10,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["claim", "authority", "evidence_refs", "numeric_refs", "numeric_relation_refs"],
                            "properties": {
                                "claim": {"type": "string", "minLength": 12, "maxLength": 900},
                                "authority": {"type": "string", "enum": ["sourced_fact", "bounded_inference", "not_inferable"]},
                                "evidence_refs": ref_array(evidence_refs),
                                "numeric_refs": ref_array(numeric_refs),
                                "numeric_relation_refs": ref_array(relation_refs),
                            },
                        },
                    },
                    "mechanism": {"type": "string", "minLength": 30, "maxLength": 2200},
                    "alternative_explanations": {
                        "type": "array", "minItems": 1, "maxItems": 6, "uniqueItems": True,
                        "items": {"type": "string", "minLength": 12, "maxLength": 700},
                    },
                    "strongest_counterarguments": {
                        "type": "array", "minItems": 1, "maxItems": 6, "uniqueItems": True,
                        "items": {"type": "string", "minLength": 12, "maxLength": 700},
                    },
                    "remaining_gap_refs": ref_array(gap_refs),
                    "what_would_change": {
                        "type": "array", "minItems": 1, "maxItems": 6, "uniqueItems": True,
                        "items": {"type": "string", "minLength": 12, "maxLength": 700},
                    },
                    "cross_role_challenges": {
                        "type": "array",
                        "minItems": (1 if agent_id == "AGENT::COUNTEREVIDENCE" else 0),
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "target_agent_id",
                                "challenge",
                                "material_reason",
                                "requested_action"
                            ],
                            "properties": {
                                "target_agent_id": {
                                    "type": "string",
                                    "enum": [
                                        value
                                        for value in SPECIALIST_AGENT_IDS
                                        if value != agent_id
                                    ]
                                },
                                "challenge": {
                                    "type": "string",
                                    "minLength": 12,
                                    "maxLength": 700
                                },
                                "material_reason": {
                                    "type": "string",
                                    "minLength": 12,
                                    "maxLength": 700
                                },
                                "requested_action": {
                                    "type": "string",
                                    "enum": [
                                        "recheck_judgment",
                                        "request_new_evidence",
                                        "clarify_scope"
                                    ]
                                }
                            }
                        }
                    },
                    "stop_reason": {"type": "string", "minLength": 12, "maxLength": 700},
                },
            },
        },
    }


def compile_specialist_workpaper_messages(
    *,
    context: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    return (
        {
            "role": "system",
            "content": (
                "You are the independent specialist named in this context. Produce "
                "a decision-ready workpaper, not a report. Use only visible reviewed "
                "Evidence, NumericFacts and typed relations. Tool execution receipts "
                "describe what the tools did; a failed retrieval is not proof of "
                "public non-disclosure. Explicitly analyze mechanism, alternative "
                "explanations, strongest counterarguments and what would change. "
                "If FeedbackReceipts and a prior workpaper are present, revise only "
                "the affected judgment. Submit exactly one workpaper tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def validate_specialist_workpaper(
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    expected_agent_id: str,
) -> dict[str, Any]:
    expected = {
        "schema_version",
        "agent_id",
        "thesis",
        "confidence",
        "sourced_claims",
        "mechanism",
        "alternative_explanations",
        "strongest_counterarguments",
        "remaining_gap_refs",
        "what_would_change",
        "cross_role_challenges",
        "stop_reason",
    }
    value = deepcopy(dict(payload))
    _require(
        set(value) == expected
        and value.get("schema_version") == SPECIALIST_WORKPAPER_SCHEMA_VERSION
        and value.get("agent_id") == expected_agent_id
        and value.get("confidence")
        in {"high", "medium", "low", "insufficient_evidence"},
        "multi_agent_workpaper_identity_invalid",
    )
    _require(
        30 <= len(str(value["thesis"]).strip()) <= 1800
        and 30 <= len(str(value["mechanism"]).strip()) <= 2200
        and 12 <= len(str(value["stop_reason"]).strip()) <= 700,
        "multi_agent_workpaper_text_invalid",
    )
    view = context["cell_analysis_view"]
    allowed_evidence = {
        str(row["evidence_ref"])
        for row in view["cell"]["cell_evidence_views"]
    }
    allowed_numeric = set(view["cell"]["allowed_numeric_refs"])
    allowed_relations = set(view["cell"]["allowed_numeric_relation_refs"])
    allowed_gaps = {
        str(row["gap_ref"])
        for row in view["cell"]["residual_gap_cards"]
    }
    claims = value.get("sourced_claims")
    _require(
        isinstance(claims, list) and 1 <= len(claims) <= 10,
        "multi_agent_workpaper_claims_invalid",
    )
    for raw in claims:
        _require(
            isinstance(raw, Mapping)
            and set(raw)
            == {
                "claim",
                "authority",
                "evidence_refs",
                "numeric_refs",
                "numeric_relation_refs",
            }
            and raw.get("authority")
            in {"sourced_fact", "bounded_inference", "not_inferable"}
            and 12 <= len(str(raw.get("claim") or "").strip()) <= 900,
            "multi_agent_workpaper_claim_invalid",
        )
        evidence = _authorized_ref_strings(
            raw.get("evidence_refs"),
            "multi_agent_workpaper_evidence_refs_invalid",
            allowed=allowed_evidence,
            scope_code="multi_agent_workpaper_ref_out_of_scope",
        )
        numeric = _authorized_ref_strings(
            raw.get("numeric_refs"),
            "multi_agent_workpaper_numeric_refs_invalid",
            allowed=allowed_numeric,
            scope_code="multi_agent_workpaper_ref_out_of_scope",
        )
        relations = _authorized_ref_strings(
            raw.get("numeric_relation_refs"),
            "multi_agent_workpaper_relation_refs_invalid",
            allowed=allowed_relations,
            scope_code="multi_agent_workpaper_ref_out_of_scope",
        )
        raw["evidence_refs"] = evidence
        raw["numeric_refs"] = numeric
        raw["numeric_relation_refs"] = relations
        _require(
            raw["authority"] == "not_inferable"
            or bool(evidence or numeric or relations),
            "multi_agent_workpaper_claim_unbound",
        )
    gaps = _authorized_ref_strings(
        value.get("remaining_gap_refs"),
        "multi_agent_workpaper_gap_refs_invalid",
        allowed=allowed_gaps,
        scope_code="multi_agent_workpaper_gap_out_of_scope",
    )
    value["remaining_gap_refs"] = gaps
    for field, minimum in (
        ("alternative_explanations", 1),
        ("strongest_counterarguments", 1),
        ("what_would_change", 1),
    ):
        value[field] = _strings(
            value[field],
            f"multi_agent_workpaper_{field}_invalid",
            minimum=minimum,
            maximum=6,
            maximum_chars=700,
        )
    challenges = value.get("cross_role_challenges")
    _require(
        isinstance(challenges, list)
        and len(challenges) <= 4
        and (
            expected_agent_id != "AGENT::COUNTEREVIDENCE"
            or bool(challenges)
        ),
        "multi_agent_workpaper_challenges_invalid",
    )
    normalized_challenges: list[dict[str, str]] = []
    seen_challenges: set[tuple[str, str]] = set()
    for raw in challenges:
        _require(
            isinstance(raw, Mapping)
            and set(raw)
            == {
                "target_agent_id",
                "challenge",
                "material_reason",
                "requested_action",
            },
            "multi_agent_workpaper_challenge_invalid",
        )
        target = str(raw.get("target_agent_id") or "")
        challenge = str(raw.get("challenge") or "").strip()
        reason = str(raw.get("material_reason") or "").strip()
        action = str(raw.get("requested_action") or "")
        identity = (target, challenge)
        _require(
            target in SPECIALIST_AGENT_IDS
            and target != expected_agent_id
            and 12 <= len(challenge) <= 700
            and 12 <= len(reason) <= 700
            and action
            in {
                "recheck_judgment",
                "request_new_evidence",
                "clarify_scope",
            }
            and identity not in seen_challenges,
            "multi_agent_workpaper_challenge_invalid",
        )
        seen_challenges.add(identity)
        normalized_challenges.append(
            {
                "target_agent_id": target,
                "challenge": challenge,
                "material_reason": reason,
                "requested_action": action,
            }
        )
    value["cross_role_challenges"] = normalized_challenges
    value["remaining_gap_refs"] = gaps
    value["context_digest"] = str(context["context_digest"])
    value["workpaper_digest"] = canonical_digest(value)
    return value


def revalidate_bound_specialist_workpaper(
    payload: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    expected_agent_id: str,
) -> dict[str, Any]:
    """Revalidate persisted content without treating derived digests as model fields."""

    raw = deepcopy(dict(payload))
    supplied_workpaper_digest = str(raw.pop("workpaper_digest", ""))
    supplied_context_digest = str(raw.pop("context_digest", ""))
    _require(
        bool(supplied_workpaper_digest) and bool(supplied_context_digest),
        "multi_agent_bound_workpaper_digest_missing",
    )
    validated = validate_specialist_workpaper(
        raw,
        context=context,
        expected_agent_id=expected_agent_id,
    )
    _require(
        supplied_workpaper_digest == validated["workpaper_digest"],
        "multi_agent_bound_workpaper_digest_invalid",
    )
    _require(
        supplied_context_digest == validated["context_digest"],
        "multi_agent_bound_workpaper_context_invalid",
    )
    return validated


def _revalidate_r7_workpaper_terminal(
    *,
    terminal_failure: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    terminal = deepcopy(dict(terminal_failure))
    preserved_full_digest = str(terminal.pop("full_result_digest", ""))
    _require(
        preserved_full_digest == canonical_digest(terminal)
        and terminal_failure.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and terminal_failure.get("failure_code")
        == "multi_agent_workpaper_ref_out_of_scope",
        "multi_agent_workpaper_checkpoint_terminal_invalid",
    )
    execution = terminal_failure.get("execution") or {}
    nodes = list(terminal_failure.get("node_executions") or ())
    terminal_attempts = list(terminal_failure.get("terminal_node_attempts") or ())
    _require(
        execution.get("new_model_nodes_started") == 5
        and execution.get("analysis_calls_preserved") == 5
        and execution.get("submission_attempts_preserved") == 6
        and execution.get("provider_attempts_preserved") == 11
        and execution.get("external_source_network_calls") == 0
        and execution.get("candidate_promotions") == 0
        and len(nodes) == 4
        and len(terminal_attempts) == 3,
        "multi_agent_workpaper_checkpoint_terminal_shape_invalid",
    )

    workpapers: dict[str, dict[str, Any]] = {}
    receipts: list[dict[str, Any]] = []
    for node in nodes:
        agent_id = str(node.get("agent_id") or "")
        _require(
            agent_id in SPECIALIST_AGENT_IDS[:4]
            and agent_id not in workpapers
            and str(node.get("node_id") or "")
            == f"{agent_id}::WORKPAPER_R1"
            and agent_id in contexts,
            "multi_agent_workpaper_checkpoint_node_identity_invalid",
        )
        raw = deepcopy(dict(node.get("validated_payload") or {}))
        stored_workpaper_digest = str(raw.pop("workpaper_digest", ""))
        stored_context_digest = str(raw.pop("context_digest", ""))
        validated = validate_specialist_workpaper(
            raw,
            context=contexts[agent_id],
            expected_agent_id=agent_id,
        )
        attempts = list(node.get("attempts") or ())
        _require(
            stored_workpaper_digest == validated["workpaper_digest"]
            and stored_context_digest == validated["context_digest"]
            and bool(attempts)
            and attempts[-1].get("status") == "contract_valid"
            and attempts[-1].get("validated_payload_digest")
            == canonical_digest(validated),
            "multi_agent_workpaper_checkpoint_completed_node_invalid",
        )
        workpapers[agent_id] = validated
        receipts.append(
            {
                "agent_id": agent_id,
                "source": "R7_contract_valid_node",
                "node_id": str(node["node_id"]),
                "attempt_ids": [str(row["attempt_id"]) for row in attempts],
                "request_digests": [
                    str(row.get("request_digest") or "") for row in attempts
                ],
                "response_digests": [
                    str(row.get("response_digest") or "") for row in attempts
                ],
                "workpaper_digest": validated["workpaper_digest"],
            }
        )

    analysis_attempt, first_submission, final_submission = terminal_attempts
    _require(
        analysis_attempt.get("phase") == "analysis"
        and analysis_attempt.get("status") == "analysis_draft_valid"
        and analysis_attempt.get("finish_reason") == "stop"
        and first_submission.get("failure_code")
        == "multi_agent_workpaper_text_invalid"
        and final_submission.get("failure_code")
        == "multi_agent_workpaper_ref_out_of_scope"
        and final_submission.get("status")
        == "provider_completed_local_contract_failed",
        "multi_agent_workpaper_checkpoint_terminal_attempts_invalid",
    )
    tool_calls = list(final_submission.get("tool_calls") or ())
    _require(
        len(tool_calls) == 1
        and str((tool_calls[0].get("function") or {}).get("name") or "")
        == "submit_specialist_workpaper",
        "multi_agent_workpaper_checkpoint_terminal_tool_invalid",
    )
    try:
        terminal_payload = json.loads(
            str((tool_calls[0].get("function") or {}).get("arguments") or "")
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MultiAgentPreviewError(
            "multi_agent_workpaper_checkpoint_terminal_payload_invalid"
        ) from exc
    supply_agent_id = "AGENT::SUPPLY_RELATIONSHIP"
    _require(
        isinstance(terminal_payload, Mapping) and supply_agent_id in contexts,
        "multi_agent_workpaper_checkpoint_terminal_payload_invalid",
    )
    supply = validate_specialist_workpaper(
        terminal_payload,
        context=contexts[supply_agent_id],
        expected_agent_id=supply_agent_id,
    )
    workpapers[supply_agent_id] = supply
    receipts.append(
        {
            "agent_id": supply_agent_id,
            "source": "R7_provider_output_revalidated_after_empty_ref_contract_fix",
            "node_id": f"{supply_agent_id}::WORKPAPER_R1",
            "attempt_ids": [str(row["attempt_id"]) for row in terminal_attempts],
            "request_digests": [
                str(row.get("request_digest") or "") for row in terminal_attempts
            ],
            "response_digests": [
                str(row.get("response_digest") or "") for row in terminal_attempts
            ],
            "workpaper_digest": supply["workpaper_digest"],
        }
    )
    ordered_ids = list(SPECIALIST_AGENT_IDS[:5])
    _require(
        set(workpapers) == set(ordered_ids),
        "multi_agent_workpaper_checkpoint_agent_set_invalid",
    )
    return [workpapers[agent_id] for agent_id in ordered_ids], receipts, preserved_full_digest


def compile_specialist_workpaper_checkpoint(
    *,
    case_key: str,
    source_run_id: str,
    source_authority_ref: str,
    source_authority_sha256: str,
    source_public_result_ref: str,
    source_public_result_sha256: str,
    source_public_result_digest: str,
    source_terminal_result_ref: str,
    source_terminal_result_sha256: str,
    terminal_failure: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    workpapers, receipts, full_digest = _revalidate_r7_workpaper_terminal(
        terminal_failure=terminal_failure,
        contexts=contexts,
    )
    body = {
        "schema_version": SPECIALIST_WORKPAPER_CHECKPOINT_SCHEMA_VERSION,
        "status": "five_R7_specialist_workpapers_valid_for_downstream_resume",
        "case_key": str(case_key),
        "source_run_id": str(source_run_id),
        "source_authority_ref": str(source_authority_ref),
        "source_authority_sha256": str(source_authority_sha256),
        "source_public_result_ref": str(source_public_result_ref),
        "source_public_result_sha256": str(source_public_result_sha256),
        "source_public_result_digest": str(source_public_result_digest),
        "source_terminal_result_ref": str(source_terminal_result_ref),
        "source_terminal_result_sha256": str(source_terminal_result_sha256),
        "source_terminal_result_digest": full_digest,
        "source_failure_code": "multi_agent_workpaper_ref_out_of_scope",
        "completed_agent_ids": list(SPECIALIST_AGENT_IDS[:5]),
        "pending_agent_ids": [SPECIALIST_AGENT_IDS[5]],
        "reused_workpaper_count": 5,
        "workpaper_digests": {
            str(row["agent_id"]): str(row["workpaper_digest"])
            for row in workpapers
        },
        "source_receipts": receipts,
        "resume_policy": {
            "completed_workpaper_rerun_forbidden": True,
            "pending_counterevidence_workpaper_required": True,
            "lead_coordination_must_wait_for_all_six_workpapers": True,
            "research_inputs_unchanged": True,
            "new_fact_or_authority_forbidden": True,
        },
        "claims": {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
    }
    return {**body, "checkpoint_digest": canonical_digest(body)}


def validate_specialist_workpaper_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    terminal_failure: Mapping[str, Any],
    contexts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    value = deepcopy(dict(checkpoint))
    checkpoint_digest = str(value.pop("checkpoint_digest", ""))
    expected = {
        "schema_version",
        "status",
        "case_key",
        "source_run_id",
        "source_authority_ref",
        "source_authority_sha256",
        "source_public_result_ref",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_ref",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "source_failure_code",
        "completed_agent_ids",
        "pending_agent_ids",
        "reused_workpaper_count",
        "workpaper_digests",
        "source_receipts",
        "resume_policy",
        "claims",
    }
    _require(
        set(value) == expected
        and checkpoint_digest == canonical_digest(value)
        and value.get("schema_version")
        == SPECIALIST_WORKPAPER_CHECKPOINT_SCHEMA_VERSION
        and value.get("status")
        == "five_R7_specialist_workpapers_valid_for_downstream_resume"
        and value.get("case_key") == "DELL"
        and value.get("source_failure_code")
        == "multi_agent_workpaper_ref_out_of_scope"
        and value.get("completed_agent_ids") == list(SPECIALIST_AGENT_IDS[:5])
        and value.get("pending_agent_ids") == [SPECIALIST_AGENT_IDS[5]]
        and value.get("reused_workpaper_count") == 5
        and value.get("resume_policy")
        == {
            "completed_workpaper_rerun_forbidden": True,
            "pending_counterevidence_workpaper_required": True,
            "lead_coordination_must_wait_for_all_six_workpapers": True,
            "research_inputs_unchanged": True,
            "new_fact_or_authority_forbidden": True,
        }
        and value.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "multi_agent_workpaper_checkpoint_shape_invalid",
    )
    for field in (
        "source_authority_sha256",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
    ):
        digest = str(value.get(field) or "")
        _require(
            len(digest) == 64 and all(ch in "0123456789abcdef" for ch in digest),
            "multi_agent_workpaper_checkpoint_binding_invalid",
        )
    workpapers, receipts, full_digest = _revalidate_r7_workpaper_terminal(
        terminal_failure=terminal_failure,
        contexts=contexts,
    )
    _require(
        value["source_terminal_result_digest"] == full_digest
        and value["source_receipts"] == receipts
        and value["workpaper_digests"]
        == {
            str(row["agent_id"]): str(row["workpaper_digest"])
            for row in workpapers
        },
        "multi_agent_workpaper_checkpoint_replay_drift",
    )
    return {
        **value,
        "checkpoint_digest": checkpoint_digest,
        "revalidated_workpapers": workpapers,
    }


def evaluation_tool(
    *, allowed_agent_ids: Sequence[str] | None = None
) -> dict[str, Any]:
    allowed_agents = tuple(allowed_agent_ids or SPECIALIST_AGENT_IDS)
    _require(
        bool(allowed_agents)
        and len(allowed_agents) == len(set(allowed_agents))
        and set(allowed_agents).issubset(SPECIALIST_AGENT_IDS),
        "multi_agent_evaluation_tool_agent_scope_invalid",
    )
    return {
        "type": "function",
        "function": {
            "name": "submit_multi_agent_evaluation",
            "description": "Evaluate workpapers without rewriting research conclusions.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "findings", "cross_role_conflicts", "report_may_proceed"],
                "properties": {
                    "schema_version": {"type": "string", "enum": [MULTI_AGENT_EVALUATION_SCHEMA_VERSION]},
                    "findings": {
                        "type": "array", "maxItems": 20,
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "required": ["finding_code", "severity", "target_agent_id", "failure_owner", "explanation", "evidence_refs", "permitted_repair", "blocks_report"],
                            "properties": {
                                "finding_code": {"type": "string", "minLength": 4, "maxLength": 100},
                                "severity": {"type": "string", "enum": ["L1", "L2", "L3", "L4"]},
                                "target_agent_id": {"type": "string", "enum": list(allowed_agents)},
                                "failure_owner": {"type": "string", "enum": ["data_infrastructure_or_tool", "harness_control", "agent_orchestration_and_role_design", "model_judgment"]},
                                "explanation": {"type": "string", "minLength": 12, "maxLength": 1000},
                                "evidence_refs": {"type": "array", "maxItems": 12, "uniqueItems": True, "items": {"type": "string"}},
                                "permitted_repair": {"type": "string", "minLength": 12, "maxLength": 800},
                                "blocks_report": {"type": "boolean"},
                            },
                        },
                    },
                    "cross_role_conflicts": {
                        "type": "array", "maxItems": 12, "uniqueItems": True,
                        "items": {"type": "string", "minLength": 12, "maxLength": 800},
                    },
                    "report_may_proceed": {"type": "boolean"},
                },
            },
        },
    }


def compile_evaluation_content_view(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    case_truth_model_view: Mapping[str, Any],
    specialist_contexts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Project only claim-bound authority into the model content review.

    Full CaseFactPresence remains available to deterministic Harness checks.  A
    content evaluator does not need every unreferenced case alias or the five
    visibility matrices repeated beside six complete workpapers.  It does need
    every Evidence, NumericFact, relation and typed gap actually cited by those
    workpapers, including exact numeric values from the role contexts.
    """

    rows = [deepcopy(dict(row)) for row in workpapers]
    _require(bool(rows), "multi_agent_evaluation_workpapers_missing")
    by_agent = {
        str(row.get("agent_id") or ""): row for row in rows
    }
    _require(
        len(by_agent) == len(rows)
        and set(by_agent).issubset(SPECIALIST_AGENT_IDS)
        and set(by_agent).issubset(specialist_contexts),
        "multi_agent_evaluation_context_coverage_invalid",
    )

    evidence_refs: set[str] = set()
    numeric_refs: set[str] = set()
    relation_refs: set[str] = set()
    gap_refs: set[str] = set()
    role_views: list[dict[str, Any]] = []
    for agent_id in sorted(by_agent):
        workpaper = by_agent[agent_id]
        for claim in workpaper.get("sourced_claims") or ():
            evidence_refs.update(str(ref) for ref in claim.get("evidence_refs") or ())
            numeric_refs.update(str(ref) for ref in claim.get("numeric_refs") or ())
            relation_refs.update(
                str(ref) for ref in claim.get("numeric_relation_refs") or ()
            )
        gap_refs.update(
            str(ref) for ref in workpaper.get("remaining_gap_refs") or ()
        )
        role_views.append(
            {
                key: deepcopy(workpaper[key])
                for key in (
                    "agent_id",
                    "confidence",
                    "thesis",
                    "sourced_claims",
                    "mechanism",
                    "strongest_counterarguments",
                    "remaining_gap_refs",
                    "what_would_change",
                )
            }
        )

    selected_presence = []
    seen_evidence: set[str] = set()
    seen_numeric: set[str] = set()
    seen_relations: set[str] = set()
    for raw in case_truth_model_view.get("presence_catalog") or ():
        row = deepcopy(dict(raw))
        row_evidence = {str(ref) for ref in row.get("evidence_refs") or ()}
        aliases = {str(alias) for alias in row.get("truth_aliases") or ()}
        matched_numeric = {
            ref for ref in numeric_refs if any(alias.endswith(ref) for alias in aliases)
        }
        matched_relations = {
            ref for ref in relation_refs if any(alias.endswith(ref) for alias in aliases)
        }
        matched_evidence = evidence_refs & row_evidence
        if matched_evidence or matched_numeric or matched_relations:
            selected_presence.append(row)
            seen_evidence.update(matched_evidence)
            seen_numeric.update(matched_numeric)
            seen_relations.update(matched_relations)

    selected_gaps = []
    seen_gaps: set[str] = set()
    for raw in case_truth_model_view.get("typed_gap_catalog") or ():
        row = deepcopy(dict(raw))
        matched = gap_refs & {
            str(ref) for ref in row.get("gap_refs") or ()
        }
        if matched:
            selected_gaps.append(row)
            seen_gaps.update(matched)

    numeric_catalog: dict[str, dict[str, Any]] = {}
    relation_catalog: dict[str, dict[str, Any]] = {}
    evidence_catalog: dict[str, dict[str, Any]] = {}
    evidence_role_catalog: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(by_agent):
        context = specialist_contexts[agent_id]
        view = context.get("cell_analysis_view") or {}
        cell = view.get("cell") or {}
        for raw in cell.get("cell_evidence_views") or ():
            ref = str(raw.get("evidence_ref") or "")
            if ref not in evidence_refs:
                continue
            compiled = evidence_role_catalog.setdefault(
                ref,
                {
                    "business_meanings_zh": [],
                    "claim_boundaries_zh": [],
                    "numeric_use_boundaries": [],
                },
            )
            for field in ("business_meanings_zh", "claim_boundaries_zh"):
                for value in raw.get(field) or ():
                    text = str(value)
                    if text and text not in compiled[field]:
                        compiled[field].append(text)
            numeric_boundary = str(raw.get("numeric_use_boundary") or "")
            if (
                numeric_boundary
                and numeric_boundary not in compiled["numeric_use_boundaries"]
            ):
                compiled["numeric_use_boundaries"].append(numeric_boundary)
        for raw in view.get("numeric_fact_catalog") or ():
            ref = str(raw.get("numeric_ref") or "")
            if ref in numeric_refs:
                numeric_catalog.setdefault(ref, deepcopy(dict(raw)))
        for raw in view.get("numeric_relation_catalog") or ():
            ref = str(raw.get("numeric_relation_ref") or "")
            if ref in relation_refs:
                relation_catalog.setdefault(ref, deepcopy(dict(raw)))
        for raw in view.get("evidence_fact_catalog") or ():
            ref = str(raw.get("evidence_ref") or "")
            if ref in evidence_refs:
                evidence_catalog.setdefault(ref, deepcopy(dict(raw)))

    _require(
        seen_evidence == evidence_refs
        and seen_numeric == numeric_refs
        and seen_relations == relation_refs
        and seen_gaps == gap_refs
        and set(evidence_catalog) == evidence_refs
        and set(evidence_role_catalog) == evidence_refs
        and set(numeric_catalog) == numeric_refs
        and set(relation_catalog) == relation_refs,
        "multi_agent_evaluation_reference_projection_incomplete",
    )
    unsigned = {
        "schema_version": MULTI_AGENT_EVALUATION_CONTENT_VIEW_SCHEMA_VERSION,
        "source_case_truth_model_view_digest": str(
            case_truth_model_view.get("case_truth_model_view_digest") or ""
        ),
        "case_identity": deepcopy(case_truth_model_view.get("case_identity") or {}),
        "role_workpaper_views": role_views,
        "referenced_authority": {
            "evidence_authority_catalog": [
                {
                    "evidence_ref": ref,
                    **{
                        key: deepcopy(evidence_catalog[ref].get(key))
                        for key in (
                            "evidence_owner_ticker",
                            "source_type",
                            "source_tier",
                            "publication_date",
                            "source_reporting_period_end",
                            "relationship_directions",
                        )
                    },
                    **deepcopy(evidence_role_catalog[ref]),
                }
                for ref in sorted(evidence_catalog)
            ],
            "numeric_fact_catalog": [
                {
                    key: deepcopy(numeric_catalog[ref].get(key))
                    for key in (
                        "numeric_ref",
                        "ticker",
                        "metric_id",
                        "value_decimal",
                        "unit",
                        "period_start",
                        "period_end",
                        "fiscal_year",
                        "fiscal_period",
                        "authority_mode",
                        "formula_trace",
                    )
                }
                for ref in sorted(numeric_catalog)
            ],
            "numeric_relation_catalog": [
                {
                    key: deepcopy(relation_catalog[ref].get(key))
                    for key in (
                        "numeric_relation_ref",
                        "ticker",
                        "metric_id",
                        "current_numeric_ref",
                        "comparison_numeric_ref",
                        "current_period_end",
                        "comparison_period_end",
                        "relation_type",
                        "direction",
                        "unit",
                        "absolute_change_decimal",
                        "percent_change_decimal",
                        "percentage_point_change_decimal",
                        "authority_mode",
                    )
                }
                for ref in sorted(relation_catalog)
            ],
            "typed_gap_catalog": [
                {
                    key: deepcopy(row.get(key))
                    for key in (
                        "gap_refs",
                        "gap_codes",
                        "slot_id",
                        "facet_id",
                        "coverage_state",
                        "business_reasons_zh",
                        "case_absence_authorized",
                    )
                }
                for row in selected_gaps
            ],
        },
        "reference_coverage_receipt": {
            "evidence_ref_count": len(evidence_refs),
            "numeric_ref_count": len(numeric_refs),
            "numeric_relation_ref_count": len(relation_refs),
            "typed_gap_ref_count": len(gap_refs),
            "all_workpaper_refs_resolved": True,
            "unreferenced_case_authority_deliberately_omitted": True,
        },
        "evaluation_boundary": {
            "identity_period_reference_and_numeric_contracts_are_local_l1": True,
            "case_absence_language_is_checked_against_full_case_truth_locally": True,
            "model_evaluator_assesses_judgment_mechanism_counterargument_and_cross_role_consistency": True,
            "alternative_explanations_challenges_and_stop_receipts_remain_local_and_are_not_repeated": True,
            "omitted_unreferenced_authority_is_not_evidence_of_absence": True,
            "model_may_not_rewrite_workpapers": True,
        },
        "failure_owner_definitions": {
            "data_infrastructure_or_tool": "source, object, SQL, retrieval, ranking or executable route failure",
            "harness_control": "valid authority hidden, wrongly rejected, misbound or inconsistently projected",
            "agent_orchestration_and_role_design": "tool, feedback, role or stop-loop behavior is wrong",
            "model_judgment": "visible authority is materially misread or overclaimed",
        },
    }
    return {
        **unsigned,
        "evaluation_content_view_digest": canonical_digest(unsigned),
    }


def compile_evaluation_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    case_truth_model_view: Mapping[str, Any],
    specialist_contexts: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], ...]:
    visible = compile_evaluation_content_view(
        workpapers=workpapers,
        case_truth_model_view=case_truth_model_view,
        specialist_contexts=specialist_contexts,
    )
    return (
        {
            "role": "system",
            "content": (
                "You are an independent financial research evaluator. Evaluate facts, "
                "scope, causal boundaries, economic mechanism, counterarguments and "
                "cross-role consistency; never rewrite the workpapers. Deterministic "
                "L1 identity, period, reference, exact-number and full-case absence "
                "checks remain local. The supplied authority view contains every ref "
                "actually used by the workpapers and deliberately omits unrelated case "
                "rows; omission is not absence. Attribute each defect to the earliest "
                "owning layer and submit exactly one evaluation tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def compile_role_evaluation_messages(
    *,
    workpaper: Mapping[str, Any],
    case_truth_model_view: Mapping[str, Any],
    specialist_context: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    """Compile one independent content audit over one role and its used authority."""

    agent_id = str(workpaper.get("agent_id") or "")
    _require(
        agent_id in SPECIALIST_AGENT_IDS,
        "multi_agent_role_evaluation_agent_invalid",
    )
    visible = compile_evaluation_content_view(
        workpapers=[workpaper],
        case_truth_model_view=case_truth_model_view,
        specialist_contexts={agent_id: specialist_context},
    )
    visible["evaluation_scope"] = {
        "scope_type": "single_role_content_audit",
        "target_agent_id": agent_id,
        "cross_role_conflicts_must_be_empty": True,
    }
    return (
        {
            "role": "system",
            "content": (
                "You are an independent financial research content evaluator. Audit "
                "only the supplied specialist workpaper and the authority it actually "
                "uses. Check judgment discipline, economic mechanism, alternative "
                "explanations, strongest counterarguments and observable what-would-change "
                "conditions. Deterministic identity, period, exact-number, reference and "
                "unbound case-absence checks remain local. Audit whether gap-bound "
                "absence language is narrower than the visible typed boundary and does "
                "not erase coexisting evidence. Do not add research, rewrite the "
                "workpaper, compare other roles or infer that omitted case authority is "
                "absent. Every finding must target the supplied agent; cross_role_conflicts "
                "must be empty. Submit exactly one evaluation tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def validate_role_evaluation(
    payload: Mapping[str, Any],
    *,
    workpaper: Mapping[str, Any],
) -> dict[str, Any]:
    agent_id = str(workpaper.get("agent_id") or "")
    value = validate_evaluation(payload, workpapers=[workpaper])
    _require(
        not value["cross_role_conflicts"]
        and all(
            str(finding.get("target_agent_id") or "") == agent_id
            for finding in value["findings"]
        ),
        "multi_agent_role_evaluation_scope_invalid",
    )
    return value


def compile_cross_role_evaluation_content_view(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    role_evaluations: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Compile an authority-light cross-role audit after every role was reviewed."""

    rows = [deepcopy(dict(row)) for row in workpapers]
    by_agent = {str(row.get("agent_id") or ""): row for row in rows}
    _require(
        len(rows) == len(SPECIALIST_AGENT_IDS)
        and set(by_agent) == set(SPECIALIST_AGENT_IDS)
        and set(role_evaluations) == set(SPECIALIST_AGENT_IDS),
        "multi_agent_cross_role_evaluation_coverage_invalid",
    )
    role_review_receipts: list[dict[str, Any]] = []
    coordination_views: list[dict[str, Any]] = []
    for agent_id in sorted(by_agent):
        workpaper = by_agent[agent_id]
        evaluation = validate_role_evaluation(
            role_evaluations[agent_id], workpaper=workpaper
        )
        role_review_receipts.append(
            {
                "agent_id": agent_id,
                "evaluation_digest": evaluation["evaluation_digest"],
                "findings": deepcopy(evaluation["findings"]),
                "role_content_may_proceed": evaluation["report_may_proceed"],
            }
        )
        coordination_views.append(
            {
                "agent_id": agent_id,
                "confidence": deepcopy(workpaper["confidence"]),
                "thesis": deepcopy(workpaper["thesis"]),
                "sourced_claims": deepcopy(workpaper["sourced_claims"]),
                "mechanism": deepcopy(workpaper["mechanism"]),
                "alternative_explanations": deepcopy(
                    workpaper["alternative_explanations"]
                ),
                "strongest_counterarguments": deepcopy(
                    workpaper["strongest_counterarguments"]
                ),
                "remaining_gap_refs": deepcopy(workpaper["remaining_gap_refs"]),
                "what_would_change": deepcopy(workpaper["what_would_change"]),
            }
        )
    unsigned = {
        "schema_version": MULTI_AGENT_CROSS_ROLE_EVALUATION_VIEW_SCHEMA_VERSION,
        "case_key": "DELL",
        "role_review_receipts": role_review_receipts,
        "coordination_views": coordination_views,
        "evaluation_boundary": {
            "all_role_content_audits_are_complete": True,
            "full_financial_authority_remains_in_local_L1": True,
            "cross_role_task_is_consistency_not_research": True,
            "new_facts_numbers_sources_or_causal_claims_forbidden": True,
            "role_workpaper_rewrite_forbidden": True,
            "omitted_authority_is_not_absence": True,
        },
    }
    return {
        **unsigned,
        "cross_role_evaluation_view_digest": canonical_digest(unsigned),
    }


def compile_cross_role_evaluation_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    role_evaluations: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], ...]:
    visible = compile_cross_role_evaluation_content_view(
        workpapers=workpapers,
        role_evaluations=role_evaluations,
    )
    return (
        {
            "role": "system",
            "content": (
                "You are the independent cross-role financial research evaluator. Every "
                "specialist workpaper has already received its own content audit, while "
                "deterministic financial L1 remains local. Check only contradictions, "
                "double counting, incompatible periods or scopes expressed across claims, "
                "mechanism inconsistency, unresolved challenge boundaries and whether the "
                "six roles can be synthesized without overstating confidence. Do not "
                "repeat role-level review, add facts, rewrite workpapers or treat omitted "
                "authority as absence. Route each finding to the earliest owning role and "
                "submit exactly one evaluation tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def merge_hierarchical_evaluations(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    role_evaluations: Mapping[str, Mapping[str, Any]],
    cross_role_evaluation: Mapping[str, Any],
    local_findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Merge role, cross-role and local L1 findings without losing any defect."""

    rows = [deepcopy(dict(row)) for row in workpapers]
    by_agent = {str(row.get("agent_id") or ""): row for row in rows}
    _require(
        set(by_agent) == set(SPECIALIST_AGENT_IDS)
        and set(role_evaluations) == set(SPECIALIST_AGENT_IDS),
        "multi_agent_hierarchical_evaluation_coverage_invalid",
    )
    normalized_roles = {
        agent_id: validate_role_evaluation(
            role_evaluations[agent_id], workpaper=by_agent[agent_id]
        )
        for agent_id in sorted(by_agent)
    }
    cross = validate_evaluation(cross_role_evaluation, workpapers=rows)
    findings: list[dict[str, Any]] = []
    seen_findings: set[str] = set()
    for raw in (
        *(
            finding
            for agent_id in sorted(normalized_roles)
            for finding in normalized_roles[agent_id]["findings"]
        ),
        *cross["findings"],
        *local_findings,
    ):
        finding = deepcopy(dict(raw))
        digest = canonical_digest(finding)
        if digest not in seen_findings:
            findings.append(finding)
            seen_findings.add(digest)
    _require(
        len(findings) <= 20,
        "multi_agent_hierarchical_evaluation_findings_overflow",
    )
    conflicts: list[str] = []
    for value in (
        *(
            conflict
            for agent_id in sorted(normalized_roles)
            for conflict in normalized_roles[agent_id]["cross_role_conflicts"]
        ),
        *cross["cross_role_conflicts"],
    ):
        text = str(value)
        if text not in conflicts:
            conflicts.append(text)
    _require(
        len(conflicts) <= 12,
        "multi_agent_hierarchical_evaluation_conflicts_overflow",
    )
    merged = {
        "schema_version": MULTI_AGENT_EVALUATION_SCHEMA_VERSION,
        "findings": findings,
        "cross_role_conflicts": conflicts,
        "report_may_proceed": not any(
            bool(finding.get("blocks_report")) for finding in findings
        ),
    }
    return validate_evaluation(merged, workpapers=rows)


def validate_evaluation(
    payload: Mapping[str, Any],
    *,
    workpapers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    supplied_digest = str(value.pop("evaluation_digest", ""))
    _require(
        set(value)
        == {"schema_version", "findings", "cross_role_conflicts", "report_may_proceed"}
        and value.get("schema_version") == MULTI_AGENT_EVALUATION_SCHEMA_VERSION
        and isinstance(value.get("report_may_proceed"), bool),
        "multi_agent_evaluation_identity_invalid",
    )
    workpaper_agents = {str(row["agent_id"]) for row in workpapers}
    allowed_refs = {
        str(ref)
        for workpaper in workpapers
        for claim in workpaper["sourced_claims"]
        for ref in (
            list(claim["evidence_refs"])
            + list(claim["numeric_refs"])
            + list(claim["numeric_relation_refs"])
        )
    }
    findings = value.get("findings")
    _require(isinstance(findings, list) and len(findings) <= 20, "multi_agent_findings_invalid")
    for finding in findings:
        _require(
            isinstance(finding, Mapping)
            and set(finding)
            == {
                "finding_code",
                "severity",
                "target_agent_id",
                "failure_owner",
                "explanation",
                "evidence_refs",
                "permitted_repair",
                "blocks_report",
            }
            and finding.get("severity") in {"L1", "L2", "L3", "L4"}
            and finding.get("target_agent_id") in workpaper_agents
            and finding.get("failure_owner")
            in {
                "data_infrastructure_or_tool",
                "harness_control",
                "agent_orchestration_and_role_design",
                "model_judgment",
            }
            and isinstance(finding.get("blocks_report"), bool),
            "multi_agent_finding_invalid",
        )
        refs = _strings(
            finding.get("evidence_refs"),
            "multi_agent_finding_refs_invalid",
            minimum=0,
            maximum=12,
            maximum_chars=120,
        )
        _require(set(refs).issubset(allowed_refs), "multi_agent_finding_ref_out_of_scope")
    value["cross_role_conflicts"] = _strings(
        value.get("cross_role_conflicts"),
        "multi_agent_cross_role_conflicts_invalid",
        minimum=0,
        maximum=12,
        maximum_chars=800,
    )
    blocking = any(bool(row["blocks_report"]) for row in findings)
    _require(
        value["report_may_proceed"] is (not blocking),
        "multi_agent_evaluation_disposition_inconsistent",
    )
    computed_digest = canonical_digest(value)
    _require(
        not supplied_digest or supplied_digest == computed_digest,
        "multi_agent_evaluation_digest_invalid",
    )
    value["evaluation_digest"] = computed_digest
    return value


def compile_challenge_catalog(
    *,
    workpapers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for workpaper in workpapers:
        source_agent_id = str(workpaper["agent_id"])
        for raw in workpaper.get("cross_role_challenges") or ():
            body = {
                "source_agent_id": source_agent_id,
                "target_agent_id": str(raw["target_agent_id"]),
                "challenge": str(raw["challenge"]),
                "material_reason": str(raw["material_reason"]),
                "requested_action": str(raw["requested_action"]),
                "source_workpaper_digest": str(workpaper["workpaper_digest"]),
            }
            catalog.append(
                {
                    "challenge_id": "CHALLENGE::"
                    + canonical_digest(body)[:24].upper(),
                    **body,
                }
            )
    return catalog


def lead_coordination_rationale_max_chars(
    *, challenge_catalog: Sequence[Mapping[str, Any]]
) -> int:
    """Compile a task-sized rationale surface from the routed challenge set."""

    challenge_count = len(challenge_catalog)
    return min(4000, max(1200, 600 + 400 * challenge_count))


def lead_coordination_tool(
    *,
    challenge_catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    challenge_ids = [str(row["challenge_id"]) for row in challenge_catalog]
    selectable = challenge_ids if challenge_ids else ["__NO_CHALLENGE__"]
    rationale_max_chars = lead_coordination_rationale_max_chars(
        challenge_catalog=challenge_catalog
    )
    return {
        "type": "function",
        "function": {
            "name": "submit_lead_coordination_decision",
            "description": (
                "Select bounded cross-role repairs or proceed to independent "
                "evaluation. This decision does not create research facts."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "lead_agent_id",
                    "accepted_challenge_ids",
                    "deferred_challenge_ids",
                    "coordination_rationale",
                    "next_state",
                ],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "enum": [LEAD_COORDINATION_DECISION_SCHEMA_VERSION],
                    },
                    "lead_agent_id": {
                        "type": "string",
                        "enum": [RESEARCH_LEAD_AGENT_ID],
                    },
                    "accepted_challenge_ids": {
                        "type": "array",
                        "maxItems": min(3, len(challenge_ids)),
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": selectable},
                    },
                    "deferred_challenge_ids": {
                        "type": "array",
                        "maxItems": len(challenge_ids),
                        "uniqueItems": True,
                        "items": {"type": "string", "enum": selectable},
                    },
                    "coordination_rationale": {
                        "type": "string",
                        "minLength": 20,
                        "maxLength": rationale_max_chars,
                    },
                    "next_state": {
                        "type": "string",
                        "enum": [
                            "continue_local_repairs",
                            "proceed_to_evaluation",
                            "pause_for_data_or_tool",
                        ],
                    },
                },
            },
        },
    }


def compile_lead_coordination_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    challenge_catalog: Sequence[Mapping[str, Any]],
    local_failure_receipts: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, str], ...]:
    visible = {
        "validated_workpapers": [deepcopy(dict(row)) for row in workpapers],
        "challenge_catalog": [deepcopy(dict(row)) for row in challenge_catalog],
        "local_failure_receipts": [
            deepcopy(dict(row)) for row in local_failure_receipts
        ],
        "routing_rules": [
            "Accept at most three material role-local repairs in this preview.",
            "A data/tool or Harness failure must not be repaired by rewriting a conclusion.",
            "If no challenge is material, proceed directly to independent evaluation.",
            "Do not invent new EvidenceRequest results, facts, numbers or citations.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the Research Lead coordinating independent specialist "
                "workpapers. Select only material, locally repairable challenges; "
                "defer infrastructure or Harness defects to their owning layer. "
                "Submit exactly one lead coordination decision tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def validate_lead_coordination_decision(
    payload: Mapping[str, Any],
    *,
    challenge_catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    rationale = str(value.get("coordination_rationale") or "").strip()
    rationale_max_chars = lead_coordination_rationale_max_chars(
        challenge_catalog=challenge_catalog
    )
    expected = {
        "schema_version",
        "lead_agent_id",
        "accepted_challenge_ids",
        "deferred_challenge_ids",
        "coordination_rationale",
        "next_state",
    }
    _require(
        set(value) == expected
        and value.get("schema_version")
        == LEAD_COORDINATION_DECISION_SCHEMA_VERSION
        and value.get("lead_agent_id") == RESEARCH_LEAD_AGENT_ID
        and value.get("next_state")
        in {
            "continue_local_repairs",
            "proceed_to_evaluation",
            "pause_for_data_or_tool",
        },
        "multi_agent_lead_coordination_identity_invalid",
    )
    _require(
        20 <= len(rationale) <= rationale_max_chars,
        "multi_agent_lead_coordination_rationale_length_invalid:"
        f"actual={len(rationale)}:maximum={rationale_max_chars}",
    )
    allowed = {str(row["challenge_id"]) for row in challenge_catalog}
    accepted = _strings(
        value["accepted_challenge_ids"],
        "multi_agent_lead_coordination_accepted_invalid",
        minimum=0,
        maximum=3,
        maximum_chars=80,
    )
    deferred = _strings(
        value["deferred_challenge_ids"],
        "multi_agent_lead_coordination_deferred_invalid",
        minimum=0,
        maximum=max(len(allowed), 1),
        maximum_chars=80,
    )
    _require(
        not set(accepted).intersection(deferred)
        and set(accepted).union(deferred) == allowed,
        "multi_agent_lead_coordination_partition_invalid",
    )
    _require(
        (value["next_state"] == "continue_local_repairs") is bool(accepted),
        "multi_agent_lead_coordination_state_invalid",
    )
    value["accepted_challenge_ids"] = accepted
    value["deferred_challenge_ids"] = deferred
    value["coordination_rationale"] = rationale
    value["coordination_digest"] = canonical_digest(value)
    return value


def compile_lead_coordination_checkpoint(
    *,
    case_key: str,
    source_run_id: str,
    source_authority_ref: str,
    source_authority_sha256: str,
    source_public_result_ref: str,
    source_public_result_sha256: str,
    source_public_result_digest: str,
    source_terminal_result_ref: str,
    source_terminal_result_sha256: str,
    source_terminal_result_digest: str,
    predecessor_workpaper_checkpoint_ref: str,
    predecessor_workpaper_checkpoint_sha256: str,
    predecessor_workpaper_checkpoint_digest: str,
    workpapers: Sequence[Mapping[str, Any]],
    challenge_catalog: Sequence[Mapping[str, Any]],
    coordination_decision: Mapping[str, Any],
    source_receipts: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind six workpapers and one natural Lead decision for downstream reuse."""

    ordered_workpapers = [deepcopy(dict(row)) for row in workpapers]
    _require(
        [row.get("agent_id") for row in ordered_workpapers]
        == list(SPECIALIST_AGENT_IDS),
        "multi_agent_coordination_checkpoint_workpaper_order_invalid",
    )
    catalog = [deepcopy(dict(row)) for row in challenge_catalog]
    decision_input = deepcopy(dict(coordination_decision))
    supplied_decision_digest = str(
        decision_input.pop("coordination_digest", "")
    )
    decision = validate_lead_coordination_decision(
        decision_input, challenge_catalog=catalog
    )
    _require(
        not supplied_decision_digest
        or supplied_decision_digest == decision["coordination_digest"],
        "multi_agent_coordination_checkpoint_decision_digest_invalid",
    )
    receipts = _validate_lead_coordination_checkpoint_source_receipts(
        source_receipts,
        source_run_id=str(source_run_id),
        counter_workpaper_digest=str(
            ordered_workpapers[-1]["workpaper_digest"]
        ),
        coordination_decision_digest=decision["coordination_digest"],
    )
    body = {
        "schema_version": LEAD_COORDINATION_CHECKPOINT_SCHEMA_VERSION,
        "status": "six_workpapers_and_R9_lead_coordination_valid_for_downstream_resume",
        "case_key": str(case_key),
        "source_run_id": str(source_run_id),
        "source_authority_ref": str(source_authority_ref),
        "source_authority_sha256": str(source_authority_sha256),
        "source_public_result_ref": str(source_public_result_ref),
        "source_public_result_sha256": str(source_public_result_sha256),
        "source_public_result_digest": str(source_public_result_digest),
        "source_terminal_result_ref": str(source_terminal_result_ref),
        "source_terminal_result_sha256": str(source_terminal_result_sha256),
        "source_terminal_result_digest": str(source_terminal_result_digest),
        "source_failure_code": "multi_agent_lead_coordination_identity_invalid",
        "predecessor_workpaper_checkpoint_ref": str(
            predecessor_workpaper_checkpoint_ref
        ),
        "predecessor_workpaper_checkpoint_sha256": str(
            predecessor_workpaper_checkpoint_sha256
        ),
        "predecessor_workpaper_checkpoint_digest": str(
            predecessor_workpaper_checkpoint_digest
        ),
        "completed_agent_ids": list(SPECIALIST_AGENT_IDS),
        "reused_workpaper_count": 6,
        "workpaper_digests": {
            str(row["agent_id"]): str(row["workpaper_digest"])
            for row in ordered_workpapers
        },
        "challenge_ids": [str(row["challenge_id"]) for row in catalog],
        "challenge_catalog_digest": canonical_digest(catalog),
        "coordination_decision_digest": decision["coordination_digest"],
        "accepted_challenge_ids": list(decision["accepted_challenge_ids"]),
        "deferred_challenge_ids": list(decision["deferred_challenge_ids"]),
        "source_receipts": receipts,
        "resume_policy": {
            "completed_workpaper_rerun_forbidden": True,
            "lead_coordination_rerun_forbidden": True,
            "downstream_starts_at_accepted_challenge_repairs": True,
            "research_inputs_unchanged": True,
            "new_fact_or_authority_forbidden": True,
        },
        "claims": {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
    }
    return {**body, "checkpoint_digest": canonical_digest(body)}


def _validate_lead_coordination_checkpoint_source_receipts(
    source_receipts: Mapping[str, Any],
    *,
    source_run_id: str,
    counter_workpaper_digest: str,
    coordination_decision_digest: str,
) -> dict[str, Any]:
    receipts = deepcopy(dict(source_receipts))
    _require(
        set(receipts) == {"counter_workpaper", "lead_coordination"},
        "multi_agent_coordination_checkpoint_receipt_set_invalid",
    )
    counter = receipts["counter_workpaper"]
    lead = receipts["lead_coordination"]
    _require(
        isinstance(counter, Mapping)
        and set(counter)
        == {
            "source_run_id",
            "node_id",
            "attempt_ids",
            "request_digests",
            "response_digests",
            "validated_payload_digest",
        }
        and counter.get("source_run_id") == source_run_id
        and counter.get("node_id")
        == "AGENT::COUNTEREVIDENCE::WORKPAPER_R1"
        and counter.get("validated_payload_digest")
        == counter_workpaper_digest,
        "multi_agent_coordination_checkpoint_counter_receipt_invalid",
    )
    attempt_ids = _strings(
        counter.get("attempt_ids"),
        "multi_agent_coordination_checkpoint_counter_attempts_invalid",
        minimum=2,
        maximum=3,
        maximum_chars=220,
    )
    request_digests = _strings(
        counter.get("request_digests"),
        "multi_agent_coordination_checkpoint_counter_requests_invalid",
        minimum=len(attempt_ids),
        maximum=len(attempt_ids),
        maximum_chars=64,
    )
    response_digests = _strings(
        counter.get("response_digests"),
        "multi_agent_coordination_checkpoint_counter_responses_invalid",
        minimum=len(attempt_ids),
        maximum=len(attempt_ids),
        maximum_chars=64,
    )
    _require(
        all(
            len(digest) == 64
            and all(ch in "0123456789abcdef" for ch in digest)
            for digest in (*request_digests, *response_digests)
        ),
        "multi_agent_coordination_checkpoint_counter_digest_invalid",
    )
    _require(
        isinstance(lead, Mapping)
        and set(lead)
        == {
            "source_run_id",
            "node_id",
            "accepted_attempt_id",
            "request_capture_ref",
            "request_capture_sha256",
            "request_digest",
            "response_capture_ref",
            "response_capture_sha256",
            "response_digest",
            "tool_name",
            "coordination_decision_digest",
        }
        and lead.get("source_run_id") == source_run_id
        and lead.get("node_id")
        == "AGENT::RESEARCH_LEAD::COORDINATION_R1"
        and lead.get("tool_name")
        == "submit_lead_coordination_decision"
        and lead.get("coordination_decision_digest")
        == coordination_decision_digest
        and all(
            isinstance(lead.get(field), str)
            and bool(str(lead[field]).strip())
            for field in (
                "accepted_attempt_id",
                "request_capture_ref",
                "response_capture_ref",
            )
        ),
        "multi_agent_coordination_checkpoint_lead_receipt_invalid",
    )
    for field in (
        "request_capture_sha256",
        "request_digest",
        "response_capture_sha256",
        "response_digest",
    ):
        digest = str(lead.get(field) or "")
        _require(
            len(digest) == 64
            and all(ch in "0123456789abcdef" for ch in digest),
            "multi_agent_coordination_checkpoint_lead_digest_invalid:" + field,
        )
    counter["attempt_ids"] = attempt_ids
    counter["request_digests"] = request_digests
    counter["response_digests"] = response_digests
    return receipts


def validate_lead_coordination_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    workpapers: Sequence[Mapping[str, Any]],
    contexts: Mapping[str, Mapping[str, Any]],
    challenge_catalog: Sequence[Mapping[str, Any]],
    coordination_decision: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(checkpoint))
    checkpoint_digest = str(value.pop("checkpoint_digest", ""))
    expected = {
        "schema_version",
        "status",
        "case_key",
        "source_run_id",
        "source_authority_ref",
        "source_authority_sha256",
        "source_public_result_ref",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_ref",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "source_failure_code",
        "predecessor_workpaper_checkpoint_ref",
        "predecessor_workpaper_checkpoint_sha256",
        "predecessor_workpaper_checkpoint_digest",
        "completed_agent_ids",
        "reused_workpaper_count",
        "workpaper_digests",
        "challenge_ids",
        "challenge_catalog_digest",
        "coordination_decision_digest",
        "accepted_challenge_ids",
        "deferred_challenge_ids",
        "source_receipts",
        "resume_policy",
        "claims",
    }
    _require(
        set(value) == expected
        and checkpoint_digest == canonical_digest(value)
        and value.get("schema_version")
        == LEAD_COORDINATION_CHECKPOINT_SCHEMA_VERSION
        and value.get("status")
        == "six_workpapers_and_R9_lead_coordination_valid_for_downstream_resume"
        and value.get("case_key") == "DELL"
        and value.get("source_failure_code")
        == "multi_agent_lead_coordination_identity_invalid"
        and value.get("completed_agent_ids") == list(SPECIALIST_AGENT_IDS)
        and value.get("reused_workpaper_count") == 6
        and value.get("resume_policy")
        == {
            "completed_workpaper_rerun_forbidden": True,
            "lead_coordination_rerun_forbidden": True,
            "downstream_starts_at_accepted_challenge_repairs": True,
            "research_inputs_unchanged": True,
            "new_fact_or_authority_forbidden": True,
        }
        and value.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        },
        "multi_agent_coordination_checkpoint_shape_invalid",
    )
    for field in (
        "source_authority_sha256",
        "source_public_result_sha256",
        "source_public_result_digest",
        "source_terminal_result_sha256",
        "source_terminal_result_digest",
        "predecessor_workpaper_checkpoint_sha256",
        "predecessor_workpaper_checkpoint_digest",
        "challenge_catalog_digest",
        "coordination_decision_digest",
    ):
        digest = str(value.get(field) or "")
        _require(
            len(digest) == 64
            and all(ch in "0123456789abcdef" for ch in digest),
            "multi_agent_coordination_checkpoint_binding_invalid:" + field,
        )
    ordered_workpapers: list[dict[str, Any]] = []
    for row in workpapers:
        raw_workpaper = deepcopy(dict(row))
        supplied_workpaper_digest = str(
            raw_workpaper.pop("workpaper_digest", "")
        )
        supplied_context_digest = str(
            raw_workpaper.pop("context_digest", "")
        )
        validated_workpaper = validate_specialist_workpaper(
            raw_workpaper,
            context=contexts[str(raw_workpaper["agent_id"])],
            expected_agent_id=str(raw_workpaper["agent_id"]),
        )
        _require(
            not supplied_workpaper_digest
            or supplied_workpaper_digest
            == validated_workpaper["workpaper_digest"],
            "multi_agent_coordination_checkpoint_workpaper_digest_invalid",
        )
        _require(
            not supplied_context_digest
            or supplied_context_digest
            == validated_workpaper["context_digest"],
            "multi_agent_coordination_checkpoint_context_digest_invalid",
        )
        ordered_workpapers.append(validated_workpaper)
    _require(
        [row["agent_id"] for row in ordered_workpapers]
        == list(SPECIALIST_AGENT_IDS)
        and value.get("workpaper_digests")
        == {
            row["agent_id"]: row["workpaper_digest"]
            for row in ordered_workpapers
        },
        "multi_agent_coordination_checkpoint_workpapers_invalid",
    )
    catalog = [deepcopy(dict(row)) for row in challenge_catalog]
    _require(
        catalog == compile_challenge_catalog(workpapers=ordered_workpapers)
        and value.get("challenge_ids")
        == [row["challenge_id"] for row in catalog]
        and value.get("challenge_catalog_digest") == canonical_digest(catalog),
        "multi_agent_coordination_checkpoint_catalog_invalid",
    )
    decision_input = deepcopy(dict(coordination_decision))
    supplied_decision_digest = str(
        decision_input.pop("coordination_digest", "")
    )
    decision = validate_lead_coordination_decision(
        decision_input, challenge_catalog=catalog
    )
    _require(
        not supplied_decision_digest
        or supplied_decision_digest == decision["coordination_digest"],
        "multi_agent_coordination_checkpoint_decision_digest_invalid",
    )
    receipts = _validate_lead_coordination_checkpoint_source_receipts(
        value.get("source_receipts") or {},
        source_run_id=str(value["source_run_id"]),
        counter_workpaper_digest=ordered_workpapers[-1]["workpaper_digest"],
        coordination_decision_digest=decision["coordination_digest"],
    )
    _require(
        value.get("coordination_decision_digest")
        == decision["coordination_digest"]
        and value.get("accepted_challenge_ids")
        == decision["accepted_challenge_ids"]
        and value.get("deferred_challenge_ids")
        == decision["deferred_challenge_ids"],
        "multi_agent_coordination_checkpoint_decision_invalid",
    )
    _require(
        value.get("source_receipts") == receipts,
        "multi_agent_coordination_checkpoint_receipts_invalid",
    )
    value["checkpoint_digest"] = checkpoint_digest
    value["revalidated_workpapers"] = ordered_workpapers
    value["challenge_catalog"] = catalog
    value["coordination_decision"] = decision
    return value


def report_draft_tool(
    *,
    workpapers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    agent_ids = sorted(str(row["agent_id"]) for row in workpapers)
    evidence_refs = sorted(
        {
            str(ref)
            for workpaper in workpapers
            for claim in workpaper["sourced_claims"]
            for ref in claim["evidence_refs"]
        }
    )
    numeric_refs = sorted(
        {
            str(ref)
            for workpaper in workpapers
            for claim in workpaper["sourced_claims"]
            for ref in claim["numeric_refs"]
        }
    )

    def ref_array(values: Sequence[str]) -> dict[str, Any]:
        empty = not values
        return {
            "type": "array",
            "maxItems": max(len(values), 1),
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": list(values) if values else [_EMPTY_REF_PLACEHOLDER],
            },
            **(
                {
                    "description": (
                        "No business ref is authorized. Submit [] or the single "
                        "transport placeholder; the local validator normalizes the "
                        "placeholder to []."
                    )
                }
                if empty
                else {}
            ),
        }

    return {
        "type": "function",
        "function": {
            "name": "submit_report_draft",
            "description": "Compile a flexible report from validated workpapers without adding facts.",
            "parameters": {
                "type": "object", "additionalProperties": False,
                "required": ["schema_version", "report_title", "executive_thesis", "sections", "remaining_gaps", "what_would_change", "confidence_statement"],
                "properties": {
                    "schema_version": {"type": "string", "enum": [MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION]},
                    "report_title": {"type": "string", "minLength": 8, "maxLength": 180},
                    "executive_thesis": {"type": "string", "minLength": 40, "maxLength": 2400},
                    "sections": {
                        "type": "array", "minItems": 4, "maxItems": 10,
                        "items": {
                            "type": "object", "additionalProperties": False,
                            "required": ["heading", "body", "source_workpaper_agent_ids", "evidence_refs", "numeric_refs"],
                            "properties": {
                                "heading": {"type": "string", "minLength": 2, "maxLength": 120},
                                "body": {"type": "string", "minLength": 40, "maxLength": 4000},
                                "source_workpaper_agent_ids": {"type": "array", "minItems": 1, "maxItems": len(agent_ids), "uniqueItems": True, "items": {"type": "string", "enum": agent_ids}},
                                "evidence_refs": ref_array(evidence_refs),
                                "numeric_refs": ref_array(numeric_refs),
                            },
                        },
                    },
                    "remaining_gaps": {"type": "array", "minItems": 1, "maxItems": 12, "uniqueItems": True, "items": {"type": "string", "minLength": 12, "maxLength": 800}},
                    "what_would_change": {"type": "array", "minItems": 2, "maxItems": 12, "uniqueItems": True, "items": {"type": "string", "minLength": 12, "maxLength": 800}},
                    "confidence_statement": {"type": "string", "minLength": 20, "maxLength": 800},
                },
            },
        },
    }


def compile_report_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    evaluation: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    _require(
        evaluation.get("report_may_proceed") is True,
        "multi_agent_report_blocked_by_evaluation",
    )
    visible = {
        "validated_workpapers": [deepcopy(dict(row)) for row in workpapers],
        "independent_evaluation": deepcopy(dict(evaluation)),
        "writer_boundaries": [
            "Use only the validated workpapers and their authority references.",
            "Do not turn a typed gap or tool failure into public non-disclosure.",
            "Do not strengthen bounded inference into sourced fact.",
            "Preserve material counterarguments and what-would-change conditions.",
            "Write a flexible research report rather than a fixed five-cell template.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are the Writer in a financial multi-agent preview. Compile a "
                "coherent report only from validated specialist workpapers. You may "
                "reorganize and synthesize, but may not add facts, numbers, citations "
                "or causal claims. Preserve uncertainty, counterevidence and decision "
                "conditions. Submit exactly one report draft tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def validate_report_draft(
    payload: Mapping[str, Any],
    *,
    workpapers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    expected = {
        "schema_version",
        "report_title",
        "executive_thesis",
        "sections",
        "remaining_gaps",
        "what_would_change",
        "confidence_statement",
    }
    _require(
        set(value) == expected
        and value.get("schema_version") == MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION,
        "multi_agent_report_identity_invalid",
    )
    agents = {str(row["agent_id"]) for row in workpapers}
    evidence = {
        str(ref)
        for workpaper in workpapers
        for claim in workpaper["sourced_claims"]
        for ref in claim["evidence_refs"]
    }
    numeric = {
        str(ref)
        for workpaper in workpapers
        for claim in workpaper["sourced_claims"]
        for ref in claim["numeric_refs"]
    }
    sections = value.get("sections")
    _require(isinstance(sections, list) and 4 <= len(sections) <= 10, "multi_agent_report_sections_invalid")
    seen_headings: set[str] = set()
    for section in sections:
        _require(
            isinstance(section, Mapping)
            and set(section)
            == {"heading", "body", "source_workpaper_agent_ids", "evidence_refs", "numeric_refs"}
            and 2 <= len(str(section.get("heading") or "").strip()) <= 120
            and 40 <= len(str(section.get("body") or "").strip()) <= 4000,
            "multi_agent_report_section_invalid",
        )
        heading = str(section["heading"]).strip()
        _require(heading not in seen_headings, "multi_agent_report_heading_duplicate")
        seen_headings.add(heading)
        source_agents = _strings(
            section["source_workpaper_agent_ids"],
            "multi_agent_report_agent_refs_invalid",
            minimum=1,
            maximum=len(agents),
            maximum_chars=80,
        )
        evidence_refs = _authorized_ref_strings(
            section["evidence_refs"],
            "multi_agent_report_evidence_refs_invalid",
            allowed=evidence,
            scope_code="multi_agent_report_ref_out_of_scope",
        )
        numeric_refs = _authorized_ref_strings(
            section["numeric_refs"],
            "multi_agent_report_numeric_refs_invalid",
            allowed=numeric,
            scope_code="multi_agent_report_ref_out_of_scope",
        )
        _require(
            set(source_agents).issubset(agents),
            "multi_agent_report_ref_out_of_scope",
        )
        section["evidence_refs"] = evidence_refs
        section["numeric_refs"] = numeric_refs
    for field, minimum in (("remaining_gaps", 1), ("what_would_change", 2)):
        value[field] = _strings(
            value[field],
            f"multi_agent_report_{field}_invalid",
            minimum=minimum,
            maximum=12,
            maximum_chars=800,
        )
    _require(
        8 <= len(str(value["report_title"]).strip()) <= 180
        and 40 <= len(str(value["executive_thesis"]).strip()) <= 2400
        and 20 <= len(str(value["confidence_statement"]).strip()) <= 800,
        "multi_agent_report_text_invalid",
    )
    value["workpaper_digests"] = sorted(
        str(row["workpaper_digest"]) for row in workpapers
    )
    value["report_digest"] = canonical_digest(value)
    return value


def compile_token_budget_basis(
    *,
    node_id: str,
    purpose: str,
    input_characters: int,
    input_reference_count: int,
    required_outputs: Sequence[str],
    schema_burden: str,
    materiality_quality_risk: str,
    comparable_run_evidence: Sequence[str],
    reasoning_profile: str,
    output_token_ceiling: int,
    stop_truncation_behavior: str,
) -> dict[str, Any]:
    _require(
        bool(str(node_id).strip())
        and 20 <= len(str(purpose).strip()) <= 1000
        and input_characters >= 0
        and input_reference_count >= 0
        and 256 <= output_token_ceiling <= 64_000
        and required_outputs
        and comparable_run_evidence,
        "multi_agent_token_budget_basis_invalid",
    )
    body = {
        "schema_version": TOKEN_BUDGET_BASIS_SCHEMA_VERSION,
        "node_id": str(node_id),
        "node_purpose": str(purpose),
        "input_scale": {
            "model_visible_characters": int(input_characters),
            "authority_reference_count": int(input_reference_count),
        },
        "required_outputs": list(required_outputs),
        "schema_burden": str(schema_burden),
        "materiality_and_quality_risk": str(materiality_quality_risk),
        "comparable_run_evidence": list(comparable_run_evidence),
        "reasoning_profile": str(reasoning_profile),
        "output_token_ceiling": int(output_token_ceiling),
        "stop_and_truncation_behavior": str(stop_truncation_behavior),
        "cost_and_latency_are_secondary_constraints": True,
    }
    return {**body, "token_budget_basis_digest": canonical_digest(body)}


def local_case_absence_findings(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    case_truth_model_view: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Fail closed when absence language has no structured gap boundary.

    Natural-language matching cannot decide whether a statement such as "no
    product-level amount is disclosed" correctly narrows a coexisting fact. The
    local control therefore verifies the part it can prove deterministically:
    absence language must be accompanied by a workpaper gap reference that is
    present in the full CaseTruth gap or bridge catalogs. Semantic overreach
    inside a bound statement remains visible to the role-scoped content audit.
    """

    presence_count = len(case_truth_model_view.get("presence_catalog") or ())
    if not presence_count:
        return []
    known_gap_refs = {
        str(ref)
        for row in case_truth_model_view.get("typed_gap_catalog") or ()
        for ref in row.get("gap_refs") or ()
    }
    known_gap_refs.update(
        str(ref)
        for row in case_truth_model_view.get("typed_bridge_boundary_catalog")
        or ()
        for ref in row.get("required_gap_refs") or ()
    )
    findings: list[dict[str, Any]] = []
    for workpaper in workpapers:
        agent_id = str(workpaper["agent_id"])
        workpaper_gap_refs = {
            str(ref) for ref in workpaper.get("remaining_gap_refs") or ()
        }
        has_bound_gap = bool(workpaper_gap_refs & known_gap_refs)
        surfaces = [str(workpaper["thesis"]), str(workpaper["mechanism"])]
        surfaces.extend(str(row["claim"]) for row in workpaper["sourced_claims"])
        for surface in surfaces:
            folded = surface.casefold()
            if (
                any(term.casefold() in folded for term in _ABSENCE_TERMS)
                and not has_bound_gap
            ):
                findings.append(
                    {
                        "finding_code": "case_absence_language_missing_typed_boundary",
                        "severity": "L1",
                        "target_agent_id": agent_id,
                        "failure_owner": "harness_control",
                        "explanation": (
                            "当前工作底稿使用了缺失／未披露语言，但没有绑定任何全案 "
                            "typed gap 或 bridge boundary；必须先区分本单元未加载、"
                            "来源路线未执行和真正未披露。"
                        ),
                        "evidence_refs": [],
                        "permitted_repair": (
                            "读取完整 CaseFactPresence 后把断言改成精确的可见性或信息边界描述；"
                            "不得补写新事实。"
                        ),
                        "blocks_report": True,
                    }
                )
                break
    return findings


__all__ = [
    "ANALYSIS_COMPLETION_CHECKPOINT_SCHEMA_VERSION",
    "ANALYSIS_FRAGMENT_CHECKPOINT_SCHEMA_VERSION",
    "DOWNSTREAM_REPAIR_PROGRESS_CHECKPOINT_SCHEMA_VERSION",
    "LEAD_PLAN_SCHEMA_VERSION",
    "LEAD_COORDINATION_DECISION_SCHEMA_VERSION",
    "LEAD_COORDINATION_CHECKPOINT_SCHEMA_VERSION",
    "MULTI_AGENT_CROSS_ROLE_EVALUATION_VIEW_SCHEMA_VERSION",
    "MULTI_AGENT_EVALUATION_CONTENT_VIEW_SCHEMA_VERSION",
    "MULTI_AGENT_EVALUATION_SCHEMA_VERSION",
    "MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION",
    "MULTI_AGENT_ROLE_TOPOLOGY_SCHEMA_VERSION",
    "MultiAgentPreviewError",
    "RESEARCH_LEAD_AGENT_ID",
    "SPECIALIST_AGENT_IDS",
    "SPECIALIST_PLAN_OPINION_SCHEMA_VERSION",
    "SPECIALIST_PLAN_CHECKPOINT_SCHEMA_VERSION",
    "SPECIALIST_WORKPAPER_CHECKPOINT_SCHEMA_VERSION",
    "SPECIALIST_WORKPAPER_SCHEMA_VERSION",
    "TOKEN_BUDGET_BASIS_SCHEMA_VERSION",
    "WRITER_AGENT_ID",
    "compile_planner_payload_from_role_opinions",
    "compile_evaluation_content_view",
    "compile_evaluation_messages",
    "compile_cross_role_evaluation_content_view",
    "compile_cross_role_evaluation_messages",
    "compile_role_evaluation_messages",
    "compile_challenge_catalog",
    "compile_analyzed_node_messages",
    "compile_analyzed_node_submission_messages",
    "compile_analysis_fragment_checkpoint",
    "compile_analysis_completion_checkpoint",
    "compile_downstream_repair_progress_checkpoint",
    "compile_analysis_continuation_messages",
    "compile_lead_coordination_messages",
    "compile_lead_coordination_checkpoint",
    "compile_lead_plan_messages",
    "compile_report_messages",
    "compile_specialist_plan_messages",
    "compile_specialist_context",
    "compile_specialist_plan_checkpoint",
    "compile_specialist_workpaper_checkpoint",
    "compile_specialist_workpaper_messages",
    "compile_token_budget_basis",
    "merge_analysis_draft_fragments",
    "merge_hierarchical_evaluations",
    "evaluation_tool",
    "lead_plan_tool",
    "lead_coordination_tool",
    "lead_coordination_rationale_max_chars",
    "load_multi_agent_role_topology",
    "local_case_absence_findings",
    "report_draft_tool",
    "specialist_plan_tool",
    "specialist_workpaper_tool",
    "validate_evaluation",
    "validate_role_evaluation",
    "validate_analysis_fragment_checkpoint",
    "validate_analysis_completion_checkpoint",
    "validate_downstream_repair_progress_checkpoint",
    "validate_analysis_continuation_completion",
    "validate_lead_plan",
    "validate_lead_coordination_decision",
    "validate_lead_coordination_checkpoint",
    "validate_report_draft",
    "validate_specialist_plan_opinion",
    "validate_specialist_plan_checkpoint",
    "validate_specialist_workpaper_checkpoint",
    "validate_specialist_workpaper",
    "revalidate_bound_specialist_workpaper",
]
