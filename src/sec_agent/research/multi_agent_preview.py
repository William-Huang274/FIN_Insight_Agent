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
MULTI_AGENT_EVALUATION_SCHEMA_VERSION = (
    "fin_ia_multi_agent_evaluation_v1_0"
)
MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_report_draft_v1_0"
)
TOKEN_BUDGET_BASIS_SCHEMA_VERSION = "fin_ia_token_budget_basis_v1_0"
SPECIALIST_PLAN_CHECKPOINT_SCHEMA_VERSION = (
    "fin_ia_multi_agent_specialist_plan_checkpoint_v1_0"
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
                        "minItems": 2,
                        "maxItems": 8,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 500},
                    },
                    "expected_information_boundaries": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 10,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 500},
                    },
                    "stop_conditions": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 8,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 8, "maxLength": 500},
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
                    "analysis_messages_digest": canonical_digest(
                        [dict(row) for row in analysis_messages]
                    ),
                    "required_output_fields": requirements,
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
            minimum=2,
            maximum=10,
            maximum_chars=500,
        )
    value["accepted_agent_ids"] = accepted
    value["ordered_agent_ids"] = ordered
    value["accepted_facets"] = accepted_facets
    value["lead_plan_digest"] = canonical_digest(value)
    return value


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
) -> dict[str, Any]:
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
        "schema_version": "fin_ia_specialist_context_v1_0",
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
        return {
            "type": "array",
            "maxItems": len(values),
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": list(values) if values else ["__NO_VALID_REF__"],
            },
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
        evidence = _strings(
            raw.get("evidence_refs"),
            "multi_agent_workpaper_evidence_refs_invalid",
            minimum=0,
            maximum=max(len(allowed_evidence), 1),
            maximum_chars=120,
        )
        numeric = _strings(
            raw.get("numeric_refs"),
            "multi_agent_workpaper_numeric_refs_invalid",
            minimum=0,
            maximum=max(len(allowed_numeric), 1),
            maximum_chars=120,
        )
        relations = _strings(
            raw.get("numeric_relation_refs"),
            "multi_agent_workpaper_relation_refs_invalid",
            minimum=0,
            maximum=max(len(allowed_relations), 1),
            maximum_chars=120,
        )
        _require(
            set(evidence).issubset(allowed_evidence)
            and set(numeric).issubset(allowed_numeric)
            and set(relations).issubset(allowed_relations),
            "multi_agent_workpaper_ref_out_of_scope",
        )
        _require(
            raw["authority"] == "not_inferable"
            or bool(evidence or numeric or relations),
            "multi_agent_workpaper_claim_unbound",
        )
    gaps = _strings(
        value.get("remaining_gap_refs"),
        "multi_agent_workpaper_gap_refs_invalid",
        minimum=0,
        maximum=max(len(allowed_gaps), 1),
        maximum_chars=120,
    )
    _require(set(gaps).issubset(allowed_gaps), "multi_agent_workpaper_gap_out_of_scope")
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


def evaluation_tool() -> dict[str, Any]:
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
                                "target_agent_id": {"type": "string", "enum": list(SPECIALIST_AGENT_IDS)},
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


def compile_evaluation_messages(
    *,
    workpapers: Sequence[Mapping[str, Any]],
    case_truth_model_view: Mapping[str, Any],
) -> tuple[dict[str, str], ...]:
    visible = {
        "workpapers": [deepcopy(dict(row)) for row in workpapers],
        "case_fact_presence": deepcopy(dict(case_truth_model_view)),
        "failure_owner_definitions": {
            "data_infrastructure_or_tool": "source, object, SQL, retrieval, ranking or executable route failure",
            "harness_control": "valid authority hidden, wrongly rejected, misbound or inconsistently projected",
            "agent_orchestration_and_role_design": "tool, feedback, role or stop-loop behavior is wrong",
            "model_judgment": "visible authority is materially misread or overclaimed",
        },
    }
    return (
        {
            "role": "system",
            "content": (
                "You are an independent financial research evaluator. Evaluate facts, "
                "scope, causal boundaries and cross-role consistency; never rewrite "
                "the workpapers. Attribute each defect to the earliest owning layer. "
                "Cell-local invisibility is not case-level absence. Submit exactly "
                "one evaluation tool call."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                visible, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        },
    )


def validate_evaluation(
    payload: Mapping[str, Any],
    *,
    workpapers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
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
    value["evaluation_digest"] = canonical_digest(value)
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


def lead_coordination_tool(
    *,
    challenge_catalog: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    challenge_ids = [str(row["challenge_id"]) for row in challenge_catalog]
    selectable = challenge_ids if challenge_ids else ["__NO_CHALLENGE__"]
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
                        "maxLength": 1200,
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
        }
        and 20
        <= len(str(value.get("coordination_rationale") or "").strip())
        <= 1200,
        "multi_agent_lead_coordination_identity_invalid",
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
    value["coordination_digest"] = canonical_digest(value)
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
        return {
            "type": "array",
            "maxItems": len(values),
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": list(values) if values else ["__NO_VALID_REF__"],
            },
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
        evidence_refs = _strings(
            section["evidence_refs"],
            "multi_agent_report_evidence_refs_invalid",
            minimum=0,
            maximum=max(len(evidence), 1),
            maximum_chars=120,
        )
        numeric_refs = _strings(
            section["numeric_refs"],
            "multi_agent_report_numeric_refs_invalid",
            minimum=0,
            maximum=max(len(numeric), 1),
            maximum_chars=120,
        )
        _require(
            set(source_agents).issubset(agents)
            and set(evidence_refs).issubset(evidence)
            and set(numeric_refs).issubset(numeric),
            "multi_agent_report_ref_out_of_scope",
        )
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
    """Flag risky absence language when case-level presence is non-empty.

    This deliberately does not decide whether a particular proposition is false.
    It forces the model Evaluator to reconcile any case-level absence statement
    with the complete presence catalog instead of treating cell-local visibility
    as authoritative.
    """

    presence_count = len(case_truth_model_view.get("presence_catalog") or ())
    if not presence_count:
        return []
    findings: list[dict[str, Any]] = []
    for workpaper in workpapers:
        agent_id = str(workpaper["agent_id"])
        surfaces = [str(workpaper["thesis"]), str(workpaper["mechanism"])]
        surfaces.extend(str(row["claim"]) for row in workpaper["sourced_claims"])
        for surface in surfaces:
            folded = surface.casefold()
            if any(term.casefold() in folded for term in _ABSENCE_TERMS):
                findings.append(
                    {
                        "finding_code": "case_absence_language_requires_presence_reconciliation",
                        "severity": "L1",
                        "target_agent_id": agent_id,
                        "failure_owner": "harness_control",
                        "explanation": (
                            "当前工作底稿使用了缺失／未披露语言；全案存在目录并非空，"
                            "必须先区分本单元未加载、S2 typed gap、来源路线未执行和真正未披露。"
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
    "LEAD_PLAN_SCHEMA_VERSION",
    "LEAD_COORDINATION_DECISION_SCHEMA_VERSION",
    "MULTI_AGENT_EVALUATION_SCHEMA_VERSION",
    "MULTI_AGENT_REPORT_DRAFT_SCHEMA_VERSION",
    "MULTI_AGENT_ROLE_TOPOLOGY_SCHEMA_VERSION",
    "MultiAgentPreviewError",
    "RESEARCH_LEAD_AGENT_ID",
    "SPECIALIST_AGENT_IDS",
    "SPECIALIST_PLAN_OPINION_SCHEMA_VERSION",
    "SPECIALIST_PLAN_CHECKPOINT_SCHEMA_VERSION",
    "SPECIALIST_WORKPAPER_SCHEMA_VERSION",
    "TOKEN_BUDGET_BASIS_SCHEMA_VERSION",
    "WRITER_AGENT_ID",
    "compile_planner_payload_from_role_opinions",
    "compile_evaluation_messages",
    "compile_challenge_catalog",
    "compile_analyzed_node_messages",
    "compile_analyzed_node_submission_messages",
    "compile_lead_coordination_messages",
    "compile_lead_plan_messages",
    "compile_report_messages",
    "compile_specialist_plan_messages",
    "compile_specialist_context",
    "compile_specialist_plan_checkpoint",
    "compile_specialist_workpaper_messages",
    "compile_token_budget_basis",
    "evaluation_tool",
    "lead_plan_tool",
    "lead_coordination_tool",
    "load_multi_agent_role_topology",
    "local_case_absence_findings",
    "report_draft_tool",
    "specialist_plan_tool",
    "specialist_workpaper_tool",
    "validate_evaluation",
    "validate_lead_plan",
    "validate_lead_coordination_decision",
    "validate_report_draft",
    "validate_specialist_plan_opinion",
    "validate_specialist_plan_checkpoint",
    "validate_specialist_workpaper",
]
