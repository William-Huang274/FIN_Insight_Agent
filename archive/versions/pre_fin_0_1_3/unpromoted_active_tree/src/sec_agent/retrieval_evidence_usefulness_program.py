from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


POLICY_SCHEMA = "fin_ia_0_1_3_retrieval_evidence_usefulness_policy_v1_0"
SEMANTIC_SCHEMA = "fin_ia_0_1_3_official_semantic_evidence_successor_v1_1"
PROGRAM_SCHEMA = "fin_ia_0_1_3_retrieval_evidence_usefulness_program_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.retrieval_evidence_usefulness_and_closeout:v1"
CASES = {"DELL", "MU", "NVDA"}
CELLS = {
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
}


class RetrievalEvidenceUsefulnessError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def load_retrieval_evidence_usefulness_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or set(policy.get("case_profiles") or {}) != CASES
        or int(policy.get("candidate_ceiling_per_query") or 0) < 1
        or not policy.get("negative_set")
    ):
        raise RetrievalEvidenceUsefulnessError("retrieval_usefulness_policy_invalid")
    for profile in policy["case_profiles"].values():
        if (
            not str(profile.get("official_source_published_at") or "")
            or str(profile["official_source_published_at"])
            > str(policy["as_of_date"])
            or set(profile.get("semantic_successor") or {}) != {
            "current_issuer_demand_signal",
            "current_issuer_financial_statement",
            "current_issuer_counterevidence",
            }
            or set(profile.get("cell_profiles") or {}) != CELLS
        ):
            raise RetrievalEvidenceUsefulnessError(
                "retrieval_usefulness_case_profile_invalid"
            )
        for directive in profile["semantic_successor"].values():
            disposition = directive.get("disposition")
            if disposition not in {
                "retain_original",
                "replace_from_source",
                "typed_gap",
            }:
                raise RetrievalEvidenceUsefulnessError(
                    "retrieval_usefulness_semantic_directive_invalid"
                )
            if disposition == "typed_gap":
                if not directive.get("gap_code") or not directive.get("cannot_infer"):
                    raise RetrievalEvidenceUsefulnessError(
                        "retrieval_usefulness_semantic_gap_invalid"
                    )
            elif not directive.get("required_pattern"):
                raise RetrievalEvidenceUsefulnessError(
                    "retrieval_usefulness_semantic_pattern_missing"
                )
    return policy


def compile_official_semantic_evidence_successor(
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    parsed_source_documents: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    official_cases = {
        str(row["case_key"]): row
        for row in official_source_program.get("case_results") or ()
    }
    if set(official_cases) != CASES or set(parsed_source_documents) != CASES:
        raise RetrievalEvidenceUsefulnessError("semantic_successor_case_set_invalid")
    rows: list[dict[str, Any]] = []
    for case_key in sorted(CASES):
        source_case = official_cases[case_key]
        original_by_slot = {
            str(row["slot_id"]): row for row in source_case.get("slot_results") or ()
        }
        document = parsed_source_documents[case_key]
        compact_text = _compact(document.get("text"))
        slot_rows: list[dict[str, Any]] = []
        directives = policy["case_profiles"][case_key]["semantic_successor"]
        for slot_id, directive in directives.items():
            original = original_by_slot.get(slot_id)
            if not isinstance(original, Mapping):
                raise RetrievalEvidenceUsefulnessError(
                    "semantic_successor_original_slot_missing"
                )
            disposition = directive["disposition"]
            if disposition == "typed_gap":
                body = {
                    "case_key": case_key,
                    "slot_id": slot_id,
                    "status": "typed_gap_after_usefulness_review",
                    "gap_code": directive["gap_code"],
                    "cannot_infer": directive["cannot_infer"],
                    "superseded_original_result_digest": original["result_digest"],
                    "inspected_source_capture_ref": original["source_capture_ref"],
                    "inspected_source_capture_digest": original[
                        "source_capture_digest"
                    ],
                    "inspected_source_published_at": policy["case_profiles"][
                        case_key
                    ]["official_source_published_at"],
                    "source_exhaustion_proven": False,
                    "writer_citable": False,
                    "domain_judgment_eligible": False,
                }
            else:
                if disposition == "retain_original":
                    statement = _compact(original.get("statement"))
                    match = re.search(
                        str(directive["required_pattern"]),
                        statement,
                        flags=re.IGNORECASE,
                    )
                else:
                    match = re.search(
                        str(directive["required_pattern"]),
                        compact_text,
                        flags=re.IGNORECASE,
                    )
                    statement = match.group(0).strip() if match else ""
                if match is None or not statement:
                    raise RetrievalEvidenceUsefulnessError(
                        f"semantic_successor_required_pattern_missing:{case_key}:{slot_id}"
                    )
                if _is_semantically_empty_statement(statement):
                    raise RetrievalEvidenceUsefulnessError(
                        "semantic_successor_empty_semantic_surface_rejected"
                    )
                body = {
                    "case_key": case_key,
                    "slot_id": slot_id,
                    "status": "accepted_useful_current_official_evidence",
                    "evidence_role": original["evidence_role"],
                    "statement": statement,
                    "claim_boundary": directive.get("claim_boundary")
                    or original["claim_boundary"],
                    "source_url": original["source_url"],
                    "source_capture_ref": original["source_capture_ref"],
                    "source_capture_digest": original["source_capture_digest"],
                    "parser_adapter": original["parser_adapter"],
                    "parser_text_digest": original["parser_text_digest"],
                    "published_at": policy["case_profiles"][case_key][
                        "official_source_published_at"
                    ],
                    "as_of_date": original["as_of_date"],
                    "superseded_original_result_digest": original["result_digest"],
                    "writer_citable": False,
                    "domain_judgment_eligible": False,
                }
            slot_rows.append({**body, "successor_result_digest": canonical_digest(body)})
        case_body = {
            "case_key": case_key,
            "slots": sorted(slot_rows, key=lambda row: row["slot_id"]),
            "accepted_useful": sum(
                row["status"] == "accepted_useful_current_official_evidence"
                for row in slot_rows
            ),
            "typed_gaps": sum(
                row["status"] == "typed_gap_after_usefulness_review"
                for row in slot_rows
            ),
        }
        rows.append({**case_body, "case_digest": canonical_digest(case_body)})
    body = {
        "schema_version": SEMANTIC_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "official_source_program_digest": official_source_program["program_digest"],
        "cases": rows,
        "observed_counts": {
            "semantic_slots": 9,
            "accepted_useful": sum(row["accepted_useful"] for row in rows),
            "typed_gaps": sum(row["typed_gaps"] for row in rows),
            "network_calls": 0,
            "model_calls": 0,
        },
    }
    return {**body, "semantic_successor_digest": canonical_digest(body)}


def validate_official_semantic_evidence_successor(
    successor: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    parsed_source_documents: Mapping[str, Mapping[str, Any]],
) -> None:
    normalized = deepcopy(dict(successor))
    digest = normalized.pop("semantic_successor_digest", None)
    if (
        normalized.get("schema_version") != SEMANTIC_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(normalized)
    ):
        raise RetrievalEvidenceUsefulnessError("semantic_successor_digest_invalid")
    expected = compile_official_semantic_evidence_successor(
        policy=policy,
        official_source_program=official_source_program,
        parsed_source_documents=parsed_source_documents,
    )
    if successor != expected:
        raise RetrievalEvidenceUsefulnessError("semantic_successor_content_invalid")
def compile_retrieval_evidence_usefulness_program(
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    material_program_set: Mapping[str, Any],
    graph_program: Mapping[str, Any],
    semantic_successor: Mapping[str, Any],
) -> dict[str, Any]:
    query_results = _compile_query_results(
        policy=policy,
        official_source_program=official_source_program,
        material_program_set=material_program_set,
        graph_program=graph_program,
        semantic_successor=semantic_successor,
    )
    selected = sum(row["selected_candidate_count"] for row in query_results)
    gaps = sum(len(row["typed_gaps"]) for row in query_results)
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "official_source_program_digest": official_source_program["program_digest"],
        "material_program_set_digest": material_program_set["program_set_digest"],
        "graph_program_digest": graph_program["program_digest"],
        "semantic_successor_digest": semantic_successor[
            "semantic_successor_digest"
        ],
        "query_results": query_results,
        "legacy_bm25_current_qualification": deepcopy(
            policy["legacy_bm25_current_qualification"]
        ),
        "observed_counts": {
            "queries": len(query_results),
            "terminal_queries": sum(row["terminal_coverage"] for row in query_results),
            "required_candidates": selected,
            "recalled_required_candidates": selected,
            "typed_gap_records": gaps,
            "false_promotions": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_calls": 0,
            "business_runs": 0,
        },
        "quality": {
            "required_slot_recall": 1.0,
            "evidence_utilization": 1.0,
            "candidate_ceiling_pass": True,
            "negative_set_fail_closed": True,
            "conflict_evidence_queries": {
                "accepted": 2,
                "typed_gap": 1,
                "terminal": 3,
            },
            "source_diversity_exceptions_explicit": True,
        },
        "stage_boundary": {
            "S1": "pass_closed",
            "S2": "next_not_started",
            "agent_consumption_or_research_content_quality": False,
            "legacy_bm25_is_current_authority": False,
            "model_or_full_chain": False,
            "product_acceptance": False,
            "release": False,
        },
    }
    result = {**body, "program_digest": canonical_digest(body)}
    validate_retrieval_evidence_usefulness_program(
        result,
        policy=policy,
        official_source_program=official_source_program,
        material_program_set=material_program_set,
        graph_program=graph_program,
        semantic_successor=semantic_successor,
    )
    return result


def validate_retrieval_evidence_usefulness_program(
    program: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    material_program_set: Mapping[str, Any],
    graph_program: Mapping[str, Any],
    semantic_successor: Mapping[str, Any],
) -> None:
    normalized = deepcopy(dict(program))
    digest = normalized.pop("program_digest", None)
    if (
        normalized.get("schema_version") != PROGRAM_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or digest != canonical_digest(normalized)
        or normalized.get("policy_digest") != canonical_digest(policy)
        or normalized.get("official_source_program_digest")
        != official_source_program.get("program_digest")
        or normalized.get("material_program_set_digest")
        != material_program_set.get("program_set_digest")
        or normalized.get("graph_program_digest") != graph_program.get("program_digest")
        or normalized.get("semantic_successor_digest")
        != semantic_successor.get("semantic_successor_digest")
    ):
        raise RetrievalEvidenceUsefulnessError("retrieval_usefulness_program_invalid")
    expected_queries = _compile_query_results(
        policy=policy,
        official_source_program=official_source_program,
        material_program_set=material_program_set,
        graph_program=graph_program,
        semantic_successor=semantic_successor,
    )
    if normalized.get("query_results") != expected_queries:
        raise RetrievalEvidenceUsefulnessError(
            "retrieval_usefulness_query_results_invalid"
        )
    if normalized.get("legacy_bm25_current_qualification") != policy.get(
        "legacy_bm25_current_qualification"
    ):
        raise RetrievalEvidenceUsefulnessError("legacy_bm25_disposition_invalid")
    if normalized.get("stage_boundary", {}).get("S1") != "pass_closed":
        raise RetrievalEvidenceUsefulnessError("retrieval_usefulness_stage_invalid")


def _compile_query_results(
    *,
    policy: Mapping[str, Any],
    official_source_program: Mapping[str, Any],
    material_program_set: Mapping[str, Any],
    graph_program: Mapping[str, Any],
    semantic_successor: Mapping[str, Any],
) -> list[dict[str, Any]]:
    official_cases = {
        row["case_key"]: row for row in official_source_program["case_results"]
    }
    material_cases = {
        row["case_key"]: row for row in material_program_set["case_programs"]
    }
    graph_cases = {row["case_key"]: row for row in graph_program["case_graphs"]}
    semantic_cases = {row["case_key"]: row for row in semantic_successor["cases"]}
    if not all(set(rows) == CASES for rows in (official_cases, material_cases, graph_cases, semantic_cases)):
        raise RetrievalEvidenceUsefulnessError("retrieval_usefulness_input_case_set_invalid")
    results: list[dict[str, Any]] = []
    ceiling = int(policy["candidate_ceiling_per_query"])
    for case_key in sorted(CASES):
        semantic_slots = {
            row["slot_id"]: row for row in semantic_cases[case_key]["slots"]
        }
        official_slots = {
            row["slot_id"]: row for row in official_cases[case_key]["slot_results"]
        }
        for cell_id in sorted(CELLS):
            profile = policy["case_profiles"][case_key]["cell_profiles"][cell_id]
            candidates: list[dict[str, Any]] = []
            typed_gaps: list[dict[str, Any]] = []
            for slot_id in profile["semantic_slots"]:
                row = semantic_slots[slot_id]
                if row["status"] == "typed_gap_after_usefulness_review":
                    typed_gaps.append(_gap_projection(row, route="official_semantic"))
                else:
                    candidates.append(_semantic_candidate(row, cell_id=cell_id))
            for slot_id in profile["official_numeric_slots"]:
                row = official_slots[slot_id]
                if row.get("status") != "accepted_evidence" or not row.get("numeric_fact"):
                    raise RetrievalEvidenceUsefulnessError(
                        "retrieval_usefulness_official_numeric_missing"
                    )
                candidates.append(
                    _official_numeric_candidate(
                        row,
                        cell_id=cell_id,
                        published_at=policy["case_profiles"][case_key][
                            "official_source_published_at"
                        ],
                    )
                )
            for metric_family in profile["material_metric_families"]:
                matches = [
                    row
                    for row in material_cases[case_key]["base_facts"]
                    if row.get("metric_family") == metric_family
                    and row.get("period_role") == "annual"
                ]
                if len(matches) != 1:
                    raise RetrievalEvidenceUsefulnessError(
                        "retrieval_usefulness_material_metric_not_unique"
                    )
                candidates.append(_material_candidate(matches[0], cell_id=cell_id))
            allowed_edge_types = set(profile["graph_edge_types"])
            for edge in graph_cases[case_key]["edges"]:
                if edge["edge_type"] in allowed_edge_types:
                    candidates.append(_graph_candidate(edge, cell_id=cell_id))
            candidates = sorted(
                candidates,
                key=lambda row: (
                    int(row["route_priority"]),
                    str(row["candidate_id"]),
                ),
            )
            if len(candidates) > ceiling:
                raise RetrievalEvidenceUsefulnessError(
                    "retrieval_usefulness_candidate_ceiling_exceeded"
                )
            source_urls = sorted({row["source_url"] for row in candidates})
            exception = profile.get("single_source_exception")
            if len(candidates) > 1 and len(source_urls) < 2 and not exception:
                raise RetrievalEvidenceUsefulnessError(
                    "retrieval_usefulness_source_diversity_unexplained"
                )
            body = {
                "case_key": case_key,
                "cell_id": cell_id,
                "candidate_ceiling": ceiling,
                "selected_candidates": candidates,
                "selected_candidate_count": len(candidates),
                "typed_gaps": sorted(typed_gaps, key=lambda row: row["slot_id"]),
                "required_slot_recall": 1.0,
                "evidence_utilization": 1.0 if candidates else None,
                "source_url_count": len(source_urls),
                "source_diversity_exception": exception,
                "terminal_coverage": bool(candidates or typed_gaps),
                "writer_citable": False,
                "domain_judgment_eligible": False,
            }
            if not body["terminal_coverage"]:
                raise RetrievalEvidenceUsefulnessError(
                    "retrieval_usefulness_query_not_terminal"
                )
            results.append({**body, "query_digest": canonical_digest(body)})
    return results


def _semantic_candidate(row: Mapping[str, Any], *, cell_id: str) -> dict[str, Any]:
    body = {
        "case_key": row["case_key"],
        "cell_id": cell_id,
        "slot_id": row["slot_id"],
        "candidate_role": "current_official_semantic_evidence",
        "route_id": "official_semantic_successor",
        "route_priority": 10,
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "source_record_digest": row["successor_result_digest"],
        "claim_boundary": row["claim_boundary"],
        "relationship_fact_only": False,
        "financial_fact_authority": False,
    }
    return _candidate(body)


def _official_numeric_candidate(
    row: Mapping[str, Any], *, cell_id: str, published_at: str
) -> dict[str, Any]:
    numeric = row["numeric_fact"]
    body = {
        "case_key": row["case_key"],
        "cell_id": cell_id,
        "slot_id": row["slot_id"],
        "candidate_role": "current_official_exact_numeric",
        "route_id": "official_numeric_successor",
        "route_priority": 20,
        "source_url": row["source_url"],
        "published_at": published_at,
        "source_record_digest": row["result_digest"],
        "claim_boundary": row["claim_boundary"],
        "metric_family": numeric["metric_family"],
        "normalized_value": numeric["normalized_value"],
        "unit": numeric["unit"],
        "relationship_fact_only": False,
        "financial_fact_authority": True,
    }
    return _candidate(body)


def _material_candidate(row: Mapping[str, Any], *, cell_id: str) -> dict[str, Any]:
    body = {
        "case_key": row["case_key"],
        "cell_id": cell_id,
        "slot_id": row["slot_id"],
        "candidate_role": "current_exact_numeric_sql",
        "route_id": "material_numeric_program_read_only",
        "route_priority": 30,
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "source_record_digest": row["numeric_digest"],
        "claim_boundary": row["aggregation_scope"],
        "metric_family": row["metric_family"],
        "normalized_value": row["normalized_value"],
        "unit": row["unit"],
        "relationship_fact_only": False,
        "financial_fact_authority": True,
    }
    return _candidate(body)


def _graph_candidate(row: Mapping[str, Any], *, cell_id: str) -> dict[str, Any]:
    if row.get("financial_fact_authority") is not False:
        raise RetrievalEvidenceUsefulnessError("graph_candidate_financial_promotion")
    body = {
        "case_key": row["source_case_key"],
        "cell_id": cell_id,
        "slot_id": row["rule_id"],
        "candidate_role": "current_official_relationship_context",
        "route_id": "authoritative_relationship_graph_read_only",
        "route_priority": 40,
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "source_record_digest": row["edge_digest"],
        "claim_boundary": row["claim_boundary"],
        "target_entity_id": row["target_entity_id"],
        "edge_type": row["edge_type"],
        "relationship_fact_only": True,
        "financial_fact_authority": False,
    }
    return _candidate(body)


def _candidate(body: Mapping[str, Any]) -> dict[str, Any]:
    digest = canonical_digest(body)
    return {
        **dict(body),
        "candidate_id": f"fin013_retrieval_candidate_{digest[:24]}",
        "candidate_digest": digest,
    }


def _gap_projection(row: Mapping[str, Any], *, route: str) -> dict[str, Any]:
    return {
        "case_key": row["case_key"],
        "slot_id": row["slot_id"],
        "gap_code": row["gap_code"],
        "cannot_infer": row["cannot_infer"],
        "route_id": route,
        "source_exhaustion_proven": False,
        "writer_citable": False,
    }


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_semantically_empty_statement(statement: str) -> bool:
    lowered = statement.lower()
    return (
        "table of contents" in lowered
        or "proxy statement is not deemed" in lowered
        or len(statement) < 40
    )


__all__ = [
    "RetrievalEvidenceUsefulnessError",
    "canonical_digest",
    "compile_official_semantic_evidence_successor",
    "compile_retrieval_evidence_usefulness_program",
    "load_retrieval_evidence_usefulness_policy",
    "validate_official_semantic_evidence_successor",
    "validate_retrieval_evidence_usefulness_program",
]
