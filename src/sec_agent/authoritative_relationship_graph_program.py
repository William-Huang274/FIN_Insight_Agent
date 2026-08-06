from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


POLICY_SCHEMA = "fin_ia_0_1_3_authoritative_relationship_graph_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_authoritative_relationship_graph_program_v1_0"
CASE_GRAPH_SCHEMA = "fin_ia_0_1_3_authoritative_relationship_case_graph_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.authoritative_relationship_graph_and_typed_empty:v1"
CASES = {"DELL", "MU", "NVDA"}


class AuthoritativeRelationshipGraphError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def load_authoritative_relationship_graph_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or set(policy.get("case_profiles") or {}) != CASES
        or not isinstance(policy.get("entity_registry"), Mapping)
        or not str(policy.get("as_of_date") or "")
    ):
        raise AuthoritativeRelationshipGraphError("relationship_graph_policy_invalid")
    rule_ids: set[str] = set()
    for case_key, profile in policy["case_profiles"].items():
        if not profile.get("issuer_id") or not profile.get("source_route_id"):
            raise AuthoritativeRelationshipGraphError("relationship_graph_case_profile_invalid")
        rules = profile.get("relationship_rules") or ()
        if not rules and not profile.get("typed_empty_reason"):
            raise AuthoritativeRelationshipGraphError("relationship_graph_empty_reason_missing")
        for rule in rules:
            rule_id = str(rule.get("rule_id") or "")
            if (
                not rule_id
                or rule_id in rule_ids
                or rule.get("target_entity_id") not in policy["entity_registry"]
                or rule.get("edge_type") not in policy.get("edge_types", ())
                or not rule.get("direction")
                or not rule.get("statement_pattern")
                or not rule.get("claim_boundary")
            ):
                raise AuthoritativeRelationshipGraphError("relationship_graph_rule_invalid")
            rule_ids.add(rule_id)
    return policy


def compile_authoritative_relationship_graph_program(
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    parsed_source_documents: Mapping[str, Mapping[str, Any]],
    date_authorities: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    official_cases = {
        str(row["case_key"]): row
        for row in official_source_program.get("case_results") or ()
    }
    if set(official_cases) != CASES or set(parsed_source_documents) != CASES:
        raise AuthoritativeRelationshipGraphError("relationship_graph_source_case_set_invalid")
    if set(date_authorities) != CASES:
        raise AuthoritativeRelationshipGraphError("relationship_graph_date_authority_set_invalid")

    case_graphs: list[dict[str, Any]] = []
    for case_key in sorted(CASES):
        profile = policy["case_profiles"][case_key]
        official_case = official_cases[case_key]
        route_id = str(profile["source_route_id"])
        route = next(
            (
                row
                for row in official_case.get("route_results") or ()
                if row.get("route_id") == route_id
            ),
            None,
        )
        document = parsed_source_documents[case_key]
        if (
            not isinstance(route, Mapping)
            or route.get("status") != "captured"
            or document.get("route_id") != route_id
            or document.get("source_capture_ref")
            != (route.get("response_capture") or {}).get("object_key")
            or document.get("source_capture_digest")
            != (route.get("response_capture") or {}).get("digest")
            or document.get("parser_text_digest")
            != (route.get("parser") or {}).get("text_sha256")
            or document.get("parser_adapter") != (route.get("parser") or {}).get("adapter")
        ):
            raise AuthoritativeRelationshipGraphError("relationship_graph_source_binding_invalid")
        source_text = _compact_whitespace(document.get("text"))
        if not source_text:
            raise AuthoritativeRelationshipGraphError("relationship_graph_source_text_missing")

        date_authority = date_authorities[case_key]
        published_at = str(date_authority.get("published_at") or "")
        if (
            not published_at
            or published_at > str(policy["as_of_date"])
            or not date_authority.get("authority_ref")
            or not date_authority.get("authority_digest")
        ):
            raise AuthoritativeRelationshipGraphError("relationship_graph_date_authority_invalid")

        edges: list[dict[str, Any]] = []
        for rule in profile.get("relationship_rules") or ():
            match = re.search(
                str(rule["statement_pattern"]), source_text, flags=re.IGNORECASE
            )
            if match is None:
                raise AuthoritativeRelationshipGraphError(
                    f"relationship_graph_required_rule_not_matched:{rule['rule_id']}"
                )
            target = policy["entity_registry"][rule["target_entity_id"]]
            statement = match.group(0).strip()
            if str(target["name"]).lower() not in statement.lower():
                raise AuthoritativeRelationshipGraphError(
                    "relationship_graph_target_not_explicit_in_statement"
                )
            edge_body = {
                "rule_id": rule["rule_id"],
                "source_case_key": case_key,
                "source_issuer_id": str(profile["issuer_id"]),
                "target_entity_id": rule["target_entity_id"],
                "target_ticker": target["ticker"],
                "target_name": target["name"],
                "edge_type": rule["edge_type"],
                "direction": rule["direction"],
                "statement": statement,
                "claim_boundary": rule["claim_boundary"],
                "published_at": published_at,
                "as_of_date": policy["as_of_date"],
                "date_authority_ref": date_authority["authority_ref"],
                "date_authority_digest": date_authority["authority_digest"],
                "source_route_id": route_id,
                "source_url": document["source_url"],
                "source_capture_ref": document["source_capture_ref"],
                "source_capture_digest": document["source_capture_digest"],
                "parser_adapter": document["parser_adapter"],
                "parser_text_digest": document["parser_text_digest"],
                "approval_status": "approved_current_official_relationship_edge",
                "relationship_fact_only": True,
                "financial_fact_authority": False,
                "model_authored": False,
            }
            digest = canonical_digest(edge_body)
            edges.append(
                {
                    **edge_body,
                    "edge_id": f"fin013_graph_edge_{digest[:24]}",
                    "edge_digest": digest,
                }
            )

        inspected_source = {
            "route_id": route_id,
            "source_url": document["source_url"],
            "source_capture_ref": document["source_capture_ref"],
            "source_capture_digest": document["source_capture_digest"],
            "parser_adapter": document["parser_adapter"],
            "parser_text_digest": document["parser_text_digest"],
            "published_at": published_at,
            "date_authority_ref": date_authority["authority_ref"],
            "date_authority_digest": date_authority["authority_digest"],
        }
        nodes = [
            {
                "node_id": f"issuer:{case_key}",
                "entity_id": case_key,
                "ticker": case_key,
                "node_role": "current_case_issuer",
            },
            *[
                {
                    "node_id": f"entity:{row['target_entity_id']}",
                    "entity_id": row["target_entity_id"],
                    "ticker": row["target_ticker"],
                    "node_role": "approved_named_counterparty",
                }
                for row in sorted(edges, key=lambda item: item["target_entity_id"])
            ],
        ]
        typed_empty = None
        status = "approved_edges_present"
        if not edges:
            status = "typed_empty_no_approved_current_relationship_evidence"
            typed_empty_body = {
                "case_key": case_key,
                "status": status,
                "reason": profile["typed_empty_reason"],
                "inspected_source_capture_digest": document["source_capture_digest"],
                "source_exhaustion_proven": False,
                "invented_edge_count": 0,
            }
            typed_empty = {
                **typed_empty_body,
                "typed_empty_digest": canonical_digest(typed_empty_body),
            }
        case_body = {
            "schema_version": CASE_GRAPH_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "case_key": case_key,
            "issuer_id": str(profile["issuer_id"]),
            "status": status,
            "inspected_source": inspected_source,
            "nodes": nodes,
            "edges": sorted(edges, key=lambda row: row["rule_id"]),
            "typed_empty": typed_empty,
            "approved_edge_count": len(edges),
            "model_provider_network_calls": [0, 0, 0],
        }
        case_graphs.append(
            {**case_body, "case_graph_digest": canonical_digest(case_body)}
        )

    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "official_source_program_digest": official_source_program["program_digest"],
        "case_graphs": case_graphs,
        "observed_counts": {
            "cases": len(case_graphs),
            "approved_edges": sum(row["approved_edge_count"] for row in case_graphs),
            "typed_empty_cases": sum(row["typed_empty"] is not None for row in case_graphs),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_runs": 0,
        },
        "stage_boundary": {
            "S1_04_graph_ready": True,
            "S1_05_retrieval_usefulness_ready": False,
            "S2_S3_research_content_ready": False,
            "model_or_full_chain_run": False,
            "release": False,
        },
    }
    result = {**body, "program_digest": canonical_digest(body)}
    validate_authoritative_relationship_graph_program(
        result,
        policy=policy,
        official_source_program=official_source_program,
        date_authorities=date_authorities,
    )
    return result


def validate_authoritative_relationship_graph_program(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    date_authorities: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    normalized = deepcopy(dict(program))
    digest = normalized.pop("program_digest", None)
    if (
        normalized.get("schema_version") != PROGRAM_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(normalized)
        or normalized.get("policy_digest") != canonical_digest(policy)
        or normalized.get("official_source_program_digest")
        != official_source_program.get("program_digest")
    ):
        raise AuthoritativeRelationshipGraphError("relationship_graph_program_invalid")
    case_graphs = normalized.get("case_graphs") or ()
    if {row.get("case_key") for row in case_graphs} != CASES:
        raise AuthoritativeRelationshipGraphError("relationship_graph_program_case_set_invalid")
    official_cases = {
        str(row["case_key"]): row
        for row in official_source_program.get("case_results") or ()
    }
    for graph in case_graphs:
        _validate_case_graph(
            graph,
            policy=policy,
            official_case=official_cases[graph["case_key"]],
            date_authority=date_authorities[graph["case_key"]],
        )
    expected_counts = {
        "cases": len(case_graphs),
        "approved_edges": sum(int(row["approved_edge_count"]) for row in case_graphs),
        "typed_empty_cases": sum(row.get("typed_empty") is not None for row in case_graphs),
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_runs": 0,
    }
    if normalized.get("observed_counts") != expected_counts:
        raise AuthoritativeRelationshipGraphError("relationship_graph_program_counts_invalid")
    if normalized.get("stage_boundary") != {
        "S1_04_graph_ready": True,
        "S1_05_retrieval_usefulness_ready": False,
        "S2_S3_research_content_ready": False,
        "model_or_full_chain_run": False,
        "release": False,
    }:
        raise AuthoritativeRelationshipGraphError("relationship_graph_stage_boundary_invalid")
    return deepcopy(dict(program))


def _validate_case_graph(
    graph: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    official_case: Mapping[str, Any],
    date_authority: Mapping[str, Any],
) -> None:
    normalized = deepcopy(dict(graph))
    digest = normalized.pop("case_graph_digest", None)
    case_key = str(normalized.get("case_key") or "")
    profile = policy["case_profiles"].get(case_key) or {}
    if (
        normalized.get("schema_version") != CASE_GRAPH_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(normalized)
        or normalized.get("issuer_id") != profile.get("issuer_id")
    ):
        raise AuthoritativeRelationshipGraphError("relationship_case_graph_invalid")
    route = next(
        (
            row
            for row in official_case.get("route_results") or ()
            if row.get("route_id") == profile.get("source_route_id")
        ),
        None,
    )
    inspected = normalized.get("inspected_source") or {}
    if (
        not isinstance(route, Mapping)
        or route.get("status") != "captured"
        or inspected.get("route_id") != profile.get("source_route_id")
        or not str(inspected.get("source_url") or "").startswith("https://")
        or inspected.get("source_capture_ref")
        != (route.get("response_capture") or {}).get("object_key")
        or inspected.get("source_capture_digest")
        != (route.get("response_capture") or {}).get("digest")
        or inspected.get("parser_adapter")
        != (route.get("parser") or {}).get("adapter")
        or inspected.get("parser_text_digest")
        != (route.get("parser") or {}).get("text_sha256")
        or inspected.get("published_at") != date_authority.get("published_at")
        or inspected.get("date_authority_ref") != date_authority.get("authority_ref")
        or inspected.get("date_authority_digest") != date_authority.get("authority_digest")
    ):
        raise AuthoritativeRelationshipGraphError("relationship_case_source_binding_invalid")
    rules = {row["rule_id"]: row for row in profile.get("relationship_rules") or ()}
    edges = normalized.get("edges") or ()
    if {row.get("rule_id") for row in edges} != set(rules):
        raise AuthoritativeRelationshipGraphError("relationship_case_rule_coverage_invalid")
    expected_nodes = [
        {
            "node_id": f"issuer:{case_key}",
            "entity_id": case_key,
            "ticker": case_key,
            "node_role": "current_case_issuer",
        },
        *[
            {
                "node_id": f"entity:{row['target_entity_id']}",
                "entity_id": row["target_entity_id"],
                "ticker": row["target_ticker"],
                "node_role": "approved_named_counterparty",
            }
            for row in sorted(edges, key=lambda item: item["target_entity_id"])
        ],
    ]
    if normalized.get("nodes") != expected_nodes:
        raise AuthoritativeRelationshipGraphError("relationship_case_nodes_invalid")
    for edge in edges:
        rule = rules[edge["rule_id"]]
        target = policy["entity_registry"][rule["target_entity_id"]]
        body = {
            key: value
            for key, value in edge.items()
            if key not in {"edge_id", "edge_digest"}
        }
        expected_digest = canonical_digest(body)
        if (
            edge.get("edge_digest") != expected_digest
            or edge.get("edge_id") != f"fin013_graph_edge_{expected_digest[:24]}"
            or edge.get("source_case_key") != case_key
            or edge.get("source_issuer_id") != profile.get("issuer_id")
            or edge.get("target_entity_id") != rule.get("target_entity_id")
            or edge.get("target_ticker") != target.get("ticker")
            or edge.get("target_name") != target.get("name")
            or edge.get("edge_type") != rule.get("edge_type")
            or edge.get("direction") != rule.get("direction")
            or edge.get("claim_boundary") != rule.get("claim_boundary")
            or edge.get("published_at") != inspected.get("published_at")
            or edge.get("as_of_date") != policy.get("as_of_date")
            or edge.get("date_authority_ref") != inspected.get("date_authority_ref")
            or edge.get("date_authority_digest")
            != inspected.get("date_authority_digest")
            or edge.get("source_route_id") != inspected.get("route_id")
            or edge.get("source_url") != inspected.get("source_url")
            or edge.get("source_capture_ref") != inspected.get("source_capture_ref")
            or edge.get("source_capture_digest") != inspected.get("source_capture_digest")
            or edge.get("parser_adapter") != inspected.get("parser_adapter")
            or edge.get("parser_text_digest") != inspected.get("parser_text_digest")
            or edge.get("approval_status")
            != "approved_current_official_relationship_edge"
            or edge.get("relationship_fact_only") is not True
            or edge.get("financial_fact_authority") is not False
            or edge.get("model_authored") is not False
            or str(target["name"]).lower() not in str(edge.get("statement") or "").lower()
            or re.fullmatch(
                str(rule["statement_pattern"]),
                str(edge.get("statement") or ""),
                flags=re.IGNORECASE,
            )
            is None
        ):
            raise AuthoritativeRelationshipGraphError("relationship_edge_invalid")
    typed_empty = normalized.get("typed_empty")
    if rules:
        if typed_empty is not None or normalized.get("status") != "approved_edges_present":
            raise AuthoritativeRelationshipGraphError("relationship_case_false_empty_invalid")
    else:
        if edges or not isinstance(typed_empty, Mapping):
            raise AuthoritativeRelationshipGraphError("relationship_case_typed_empty_missing")
        empty_body = {
            key: value for key, value in typed_empty.items() if key != "typed_empty_digest"
        }
        if (
            typed_empty.get("typed_empty_digest") != canonical_digest(empty_body)
            or typed_empty.get("case_key") != case_key
            or typed_empty.get("reason") != profile.get("typed_empty_reason")
            or typed_empty.get("inspected_source_capture_digest")
            != inspected.get("source_capture_digest")
            or typed_empty.get("source_exhaustion_proven") is not False
            or typed_empty.get("invented_edge_count") != 0
            or normalized.get("status")
            != "typed_empty_no_approved_current_relationship_evidence"
        ):
            raise AuthoritativeRelationshipGraphError("relationship_case_typed_empty_invalid")
    if normalized.get("approved_edge_count") != len(edges):
        raise AuthoritativeRelationshipGraphError("relationship_case_edge_count_invalid")
    if normalized.get("model_provider_network_calls") != [0, 0, 0]:
        raise AuthoritativeRelationshipGraphError("relationship_case_call_counts_invalid")


def _compact_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
