from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from retrieval.contracts import FinancialResearchKernel
from retrieval.route_compiler import QueryObjectFactRoutePolicy

from sec_agent.providers.agent_protocol import (
    ANTHROPIC_MESSAGES_WIRE,
    CHAT_COMPLETIONS_WIRE,
    RESPONSES_WIRE,
    SUPPORTED_AGENT_WIRES,
    project_tool_definitions,
)

from .reviewed_evidence_pack import canonical_digest


READ_REVIEWED_EVIDENCE_TOOL = "read_reviewed_evidence_for_cell"
READ_NUMERIC_FACTS_TOOL = "read_numeric_facts_for_cell"
SUBMIT_EVIDENCE_REQUEST_TOOL = "submit_evidence_request"
SUBMIT_RESEARCH_JUDGMENT_TOOL = "submit_research_judgment"
FINANCE_TOOL_NAMES = (
    READ_REVIEWED_EVIDENCE_TOOL,
    READ_NUMERIC_FACTS_TOOL,
    SUBMIT_EVIDENCE_REQUEST_TOOL,
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
)

class FinanceToolContractError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FinanceToolContractError(code)


def _strict_object(properties: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": deepcopy(dict(properties)),
        "required": list(properties),
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class EvidenceRequestBranch:
    cell_id: str
    gap_refs: tuple[str, ...]
    facet_id: str
    source_class: str
    target_entities: tuple[str, ...]
    metric_ids: tuple[str, ...]
    intent_mode: str
    acceptable_source_types: tuple[str, ...]
    executable_route_ids: tuple[str, ...]
    forbidden_intent_terms: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "gap_refs": list(self.gap_refs),
            "facet_id": self.facet_id,
            "source_class": self.source_class,
            "target_entities": list(self.target_entities),
            "metric_ids": list(self.metric_ids),
            "intent_mode": self.intent_mode,
            "acceptable_source_types": list(self.acceptable_source_types),
            "executable_route_ids": list(self.executable_route_ids),
            "forbidden_intent_terms": list(self.forbidden_intent_terms),
        }


@dataclass(frozen=True)
class FinanceToolContract:
    canonical_tools: tuple[Mapping[str, Any], ...]
    evidence_request_branches: tuple[EvidenceRequestBranch, ...]
    maximum_metric_intents: int
    maximum_product_intents: int
    maximum_product_intent_chars: int

    @property
    def contract_digest(self) -> str:
        return canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_tools": [deepcopy(dict(row)) for row in self.canonical_tools],
            "evidence_request_branches": [
                row.as_dict() for row in self.evidence_request_branches
            ],
            "limits": {
                "maximum_metric_intents": self.maximum_metric_intents,
                "maximum_product_intents": self.maximum_product_intents,
                "maximum_product_intent_chars": (
                    self.maximum_product_intent_chars
                ),
            },
        }

    def branch_for(
        self,
        *,
        cell_id: str,
        facet_id: str,
        gap_ref: str,
        source_class: str,
    ) -> EvidenceRequestBranch | None:
        return next(
            (
                row
                for row in self.evidence_request_branches
                if row.cell_id == cell_id
                and row.facet_id == facet_id
                and gap_ref in row.gap_refs
                and row.source_class == source_class
            ),
            None,
        )

    def repair_surface_for_cell(self, cell_id: str) -> dict[str, Any]:
        branches = [
            row for row in self.evidence_request_branches if row.cell_id == cell_id
        ]
        return {
            "cell_id": cell_id,
            "allowed_gap_refs": sorted(
                {value for row in branches for value in row.gap_refs}
            ),
            "allowed_target_entities_by_facet": {
                row.facet_id: list(row.target_entities) for row in branches
            },
            "allowed_metrics_by_facet": {
                row.facet_id: list(row.metric_ids) for row in branches
            },
            "available_source_classes_by_gap": {
                gap_ref: sorted(
                    {
                        row.source_class
                        for row in branches
                        if gap_ref in row.gap_refs
                    }
                )
                for gap_ref in sorted(
                    {value for row in branches for value in row.gap_refs}
                )
            },
            "executable_routes_by_source_class": {
                row.source_class: list(row.executable_route_ids) for row in branches
            },
            "limits": {
                "maximum_metric_intents": self.maximum_metric_intents,
                "maximum_product_intents": self.maximum_product_intents,
                "maximum_product_intent_chars": (
                    self.maximum_product_intent_chars
                ),
            },
            "resubmit_cross_family_needs_as_separate_requests": True,
        }

    def project(self, wire_api: str) -> tuple[dict[str, Any], ...]:
        _require(wire_api in SUPPORTED_AGENT_WIRES, "finance_tool_wire_invalid")
        return project_tool_definitions(
            self.canonical_tools,
            wire_api=wire_api,
        )


def _allowed_targets(
    *,
    evidence_owner_scope: str,
    related_economic_roles: Sequence[str],
    subject_ticker: str,
    related_entities: Sequence[Any],
) -> tuple[str, ...]:
    role_filter = set(related_economic_roles)
    related = [
        str(row.ticker)
        for row in related_entities
        if not role_filter or str(row.economic_role) in role_filter
    ]
    if evidence_owner_scope == "subject":
        values = [subject_ticker]
    elif evidence_owner_scope == "related_only":
        values = related
    else:
        values = [subject_ticker, *related]
    return tuple(sorted(set(values)))


def _proposal_schema(
    *,
    branches: Sequence[EvidenceRequestBranch],
    maximum_metric_intents: int,
    maximum_product_intents: int,
    maximum_product_intent_chars: int,
) -> dict[str, Any]:
    if not branches:
        return _strict_object(
            {
                "cell_id": {"type": "string", "pattern": "^NO_VISIBLE_GAP$"},
                "gap_ref": {"type": "string", "pattern": "^NO_VISIBLE_GAP$"},
                "target_entity": {
                    "type": "string",
                    "pattern": "^NO_VISIBLE_GAP$",
                },
                "requested_facet_id": {
                    "type": "string",
                    "pattern": "^NO_VISIBLE_GAP$",
                },
                "requested_source_class": {
                    "type": "string",
                    "pattern": "^NO_EXECUTABLE_ROUTE$",
                },
                "metric_intents": {"type": "array", "maxItems": 0},
                "product_intents": {"type": "array", "maxItems": 0},
            }
        )

    branch_schemas: list[dict[str, Any]] = []
    for branch in branches:
        metric_items: dict[str, Any] = {"type": "string"}
        if branch.metric_ids:
            metric_items["enum"] = list(branch.metric_ids)
        metric_schema: dict[str, Any] = {
            "type": "array",
            "items": metric_items,
            "uniqueItems": True,
            "maxItems": maximum_metric_intents,
        }
        if not branch.metric_ids:
            metric_schema["maxItems"] = 0
        product_schema: dict[str, Any] = {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": maximum_product_intent_chars,
                "description": "One evidence intent without digits, URL, source id or answer.",
            },
            "uniqueItems": True,
            "maxItems": maximum_product_intents,
        }
        if branch.intent_mode == "metric_intent_required_product_intent_forbidden":
            metric_schema["minItems"] = 1
            product_schema["maxItems"] = 0
        else:
            product_schema["minItems"] = 1
        branch_schemas.append(
            {
                "properties": {
                    "cell_id": {"const": branch.cell_id},
                    "gap_ref": {"const": branch.gap_refs[0]},
                    "target_entity": {"enum": list(branch.target_entities)},
                    "requested_facet_id": {"const": branch.facet_id},
                    "requested_source_class": {"const": branch.source_class},
                    "metric_intents": metric_schema,
                    "product_intents": product_schema,
                }
            }
        )
    base = _strict_object(
        {
            "cell_id": {
                "type": "string",
                "enum": sorted({row.cell_id for row in branches}),
            },
            "gap_ref": {
                "type": "string",
                "enum": sorted({value for row in branches for value in row.gap_refs}),
            },
            "target_entity": {
                "type": "string",
                "enum": sorted(
                    {value for row in branches for value in row.target_entities}
                ),
            },
            "requested_facet_id": {
                "type": "string",
                "enum": sorted({row.facet_id for row in branches}),
            },
            "requested_source_class": {
                "type": "string",
                "enum": sorted({row.source_class for row in branches}),
            },
            "metric_intents": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": sorted({value for row in branches for value in row.metric_ids}),
                },
                "uniqueItems": True,
                "maxItems": maximum_metric_intents,
            },
            "product_intents": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": maximum_product_intent_chars,
                },
                "uniqueItems": True,
                "maxItems": maximum_product_intents,
            },
        }
    )
    base["oneOf"] = branch_schemas
    return base


def compile_finance_tool_contract(
    *,
    research_input: Mapping[str, Any],
    selected_cells: Sequence[Mapping[str, Any]],
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    judgment_schema: Mapping[str, Any],
    maximum_metric_intents: int,
    maximum_product_intents: int,
    maximum_product_intent_chars: int,
    strict: bool,
) -> FinanceToolContract:
    _require(bool(selected_cells), "finance_tool_contract_cells_empty")
    _require(
        maximum_metric_intents >= 1
        and maximum_product_intents >= 1
        and maximum_product_intent_chars >= 1,
        "finance_tool_contract_limits_invalid",
    )
    case_key = str(research_input.get("case_identity", {}).get("case_key") or "")
    _require(case_key in kernel.cases, "finance_tool_contract_case_invalid")
    case = kernel.cases[case_key]
    family_by_facet = route_policy.family_by_facet()
    metric_routes = {row.metric_id: row for row in route_policy.metric_routes}
    slot_by_id = kernel.slot_by_id()
    gap_routes = {
        str(row["gap_ref"]): row
        for row in research_input["evidence_request_route_catalog"][
            "gap_route_decisions"
        ]
    }
    branches: list[EvidenceRequestBranch] = []

    for cell in selected_cells:
        cell_id = str(cell["cell_id"])
        gap_refs = tuple(sorted(str(value) for value in cell["visible_gap_refs"]))
        if not gap_refs:
            continue
        slot_ids = {
            str(cell["primary_slot_id"]),
            *(str(value) for value in cell["supplemental_context_slot_ids"]),
        }
        _require(
            slot_ids.issubset(slot_by_id),
            "finance_tool_contract_cell_slot_invalid",
        )
        for gap_ref in gap_refs:
            route_decision = gap_routes[gap_ref]
            slot_id = str(route_decision["slot_id"])
            if slot_id not in slot_ids:
                continue
            requested_facets = set(route_decision["requested_query_facet_ids"])
            gap_metric_ids = set(route_decision["typed_metric_ids"])
            for facet in slot_by_id[slot_id].facets:
                if facet.facet_id not in requested_facets:
                    continue
                family = family_by_facet.get(facet.facet_id)
                _require(
                    family is not None,
                    "finance_tool_contract_facet_unrouted",
                )
                targets = _allowed_targets(
                    evidence_owner_scope=facet.evidence_owner_scope,
                    related_economic_roles=facet.related_economic_roles,
                    subject_ticker=case.subject_ticker,
                    related_entities=case.related_entities,
                )
                _require(
                    bool(targets),
                    "finance_tool_contract_facet_targets_empty",
                )
                metrics = tuple(
                    sorted(
                        metric_id
                        for metric_id, route in metric_routes.items()
                        if metric_id in gap_metric_ids
                        and family.family_id in route.allowed_query_families
                    )
                )
                for source_route in route_decision["available_source_routes"]:
                    executable = tuple(
                        route_id
                        for route_id in source_route["executable_route_ids"]
                        if route_id in family.candidate_routes
                    )
                    if not executable:
                        continue
                    if (
                        source_route["intent_mode"]
                        == "metric_intent_required_product_intent_forbidden"
                        and not metrics
                    ):
                        continue
                    branches.append(
                        EvidenceRequestBranch(
                            cell_id=cell_id,
                            gap_refs=(gap_ref,),
                            facet_id=facet.facet_id,
                            source_class=str(source_route["source_class"]),
                            target_entities=targets,
                            metric_ids=metrics,
                            intent_mode=str(source_route["intent_mode"]),
                            acceptable_source_types=tuple(
                                source_route["acceptable_source_types"]
                            ),
                            executable_route_ids=executable,
                            forbidden_intent_terms=tuple(
                                source_route["forbidden_intent_terms"]
                            ),
                        )
                    )

    read_schema = _strict_object(
        {
            "cell_id": {
                "type": "string",
                "enum": [str(row["cell_id"]) for row in selected_cells],
            }
        }
    )
    proposal_schema = _proposal_schema(
        branches=branches,
        maximum_metric_intents=maximum_metric_intents,
        maximum_product_intents=maximum_product_intents,
        maximum_product_intent_chars=maximum_product_intent_chars,
    )

    def tool(name: str, description: str, input_schema: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "input_schema": deepcopy(dict(input_schema)),
            "strict": strict,
        }

    canonical_tools = (
        tool(
            READ_REVIEWED_EVIDENCE_TOOL,
            "Read reviewed writer-citable Evidence and declared gaps for one research cell.",
            read_schema,
        ),
        tool(
            READ_NUMERIC_FACTS_TOOL,
            "Read authoritative NumericFacts with period, unit and formula lineage for one research cell.",
            read_schema,
        ),
        tool(
            SUBMIT_EVIDENCE_REQUEST_TOOL,
            (
                "Submit one bounded, family-compatible proposal for a visible gap. "
                "This never runs retrieval or creates Evidence. Split needs that use "
                "different facets into separate calls."
            ),
            proposal_schema,
        ),
        tool(
            SUBMIT_RESEARCH_JUDGMENT_TOOL,
            "Submit one provider-neutral v1.2 judgment for local validation and rendering.",
            judgment_schema,
        ),
    )
    return FinanceToolContract(
        canonical_tools=canonical_tools,
        evidence_request_branches=tuple(branches),
        maximum_metric_intents=maximum_metric_intents,
        maximum_product_intents=maximum_product_intents,
        maximum_product_intent_chars=maximum_product_intent_chars,
    )


__all__ = [
    "ANTHROPIC_MESSAGES_WIRE",
    "CHAT_COMPLETIONS_WIRE",
    "FINANCE_TOOL_NAMES",
    "READ_NUMERIC_FACTS_TOOL",
    "READ_REVIEWED_EVIDENCE_TOOL",
    "RESPONSES_WIRE",
    "SUBMIT_EVIDENCE_REQUEST_TOOL",
    "SUBMIT_RESEARCH_JUDGMENT_TOOL",
    "EvidenceRequestBranch",
    "FinanceToolContract",
    "FinanceToolContractError",
    "compile_finance_tool_contract",
]
