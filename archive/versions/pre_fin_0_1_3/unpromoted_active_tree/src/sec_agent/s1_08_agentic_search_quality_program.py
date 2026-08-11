from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


POLICY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_agentic_search_quality_evaluation_policy_v1_0"
)
PROGRAM_SCHEMA = "fin_ia_0_1_3_s1_08_agentic_search_entry_audit_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.agentic_search_quality_evaluation:v1"
CASES = ("DELL", "MU", "NVDA")
EXPECTED_METRICS = {
    "target_in_pool_recall": 1.0,
    "required_slot_recall_at_8": 1.0,
    "ndcg_at_8": 0.85,
    "mean_reciprocal_rank": 0.75,
    "currentness_compliance": 1.0,
    "source_diversity_or_typed_exception": 1.0,
    "accepted_rejected_gap_reconciliation": 1.0,
    "false_promotion_count": 0,
    "selected_pack_required_slot_coverage": 1.0,
}


class S108AgenticSearchQualityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def load_s1_08_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or policy.get("contract_ref") != CONTRACT_REF
        or tuple(policy.get("cases") or ()) != CASES
        or policy.get("as_of") != "2026-08-06"
    ):
        raise S108AgenticSearchQualityError("s1_08_policy_identity_invalid")
    observed_metrics = {
        name: row.get("threshold")
        for name, row in (policy.get("metrics") or {}).items()
    }
    if observed_metrics != EXPECTED_METRICS or not all(
        bool(row.get("hard_gate"))
        for row in (policy.get("metrics") or {}).values()
    ):
        raise S108AgenticSearchQualityError("s1_08_metric_gate_drift")
    revisions = policy.get("query_revision") or {}
    stops = policy.get("stop_conditions") or {}
    if (
        revisions.get("maximum_revisions_per_target_group") != 2
        or not revisions.get("blind_identical_retry_forbidden")
        or revisions.get("gold_expected_insight_or_evidence_ids_visible_to_planner")
        is not False
        or stops.get("candidate_pool_first") is not True
        or stops.get("model_provider_calls_allowed") != 0
    ):
        raise S108AgenticSearchQualityError("s1_08_governance_gate_invalid")
    return policy


def compile_s1_08_entry_audit(
    *,
    policy: Mapping[str, Any],
    freeze: Mapping[str, Any],
    visible_pack: Mapping[str, Any],
    hidden_scoring: Mapping[str, Any],
    governed_pack_result: Mapping[str, Any],
    source_runtime_result: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_inputs(
        policy=policy,
        freeze=freeze,
        visible_pack=visible_pack,
        hidden_scoring=hidden_scoring,
    )
    evidence_by_case = {
        str(row["case_key"]): {
            str(evidence["evidence_id"]): evidence
            for evidence in row.get("evidence_items") or ()
        }
        for row in visible_pack["cases"]
    }
    target_groups: list[dict[str, Any]] = []
    mandatory_evidence_ids: set[str] = set()
    for case_row in hidden_scoring["cases"]:
        case_key = str(case_row["case_key"])
        for target in case_row.get("required_insights") or ():
            evidence_ids = tuple(str(value) for value in target.get("evidence_ids") or ())
            if not evidence_ids or any(
                value not in evidence_by_case[case_key] for value in evidence_ids
            ):
                raise S108AgenticSearchQualityError(
                    "s1_08_hidden_target_evidence_binding_invalid"
                )
            mandatory_evidence_ids.update(evidence_ids)
            target_groups.append(
                {
                    "case_key": case_key,
                    "target_id": str(target["target_id"]),
                    "dimensions": list(target.get("dimensions") or ()),
                    "required_evidence_count": len(evidence_ids),
                    "evaluator_only_evidence_ids_digest": canonical_digest(
                        list(evidence_ids)
                    ),
                    "planner_visible_gold_content": False,
                }
            )

    benchmark_sources = list(visible_pack["source_registry"])
    benchmark_http_urls = {
        _normalize_url(str(row.get("url") or ""))
        for row in benchmark_sources
        if row.get("url")
    }
    governed_urls = _governed_pack_urls(governed_pack_result)
    live_urls = _source_runtime_urls(source_runtime_result)
    active_urls = governed_urls | live_urls
    exact_source_matches = benchmark_http_urls & active_urls
    source_match_recall = (
        len(exact_source_matches) / len(benchmark_http_urls)
        if benchmark_http_urls
        else 0.0
    )
    legacy = (
        governed_pack_result.get("retrieval_usefulness_program", {})
        .get("legacy_bm25_current_qualification", {})
    )
    current_contract = str(
        policy["active_product_inputs"]["legacy_agentic_search_contract_ref"]
    )
    old_contract_only = current_contract.startswith("fin_0_1_2.")
    has_query_revision_runtime = False

    blockers: list[dict[str, Any]] = []
    if not legacy or legacy.get("current_authority_allowed") is not False:
        raise S108AgenticSearchQualityError(
            "s1_08_legacy_bm25_boundary_missing"
        )
    if source_match_recall < EXPECTED_METRICS["target_in_pool_recall"]:
        blockers.append(
            {
                "code": "s1_08_gold_source_candidate_ceiling_unproven",
                "owner": "S1_08_candidate_generation_and_current_source_catalog",
                "observed": round(source_match_recall, 6),
                "required": EXPECTED_METRICS["target_in_pool_recall"],
                "effect": "ranking_and_reranker_evaluation_not_admitted",
            }
        )
    if old_contract_only:
        blockers.append(
            {
                "code": "s1_08_current_provider_neutral_search_contract_missing",
                "owner": "S1_08_search_runtime_contract",
                "observed": current_contract,
                "required": CONTRACT_REF,
                "effect": "FIN_0_1_2_search_output_cannot_be_promoted_as_FIN_0_1_3_eval",
            }
        )
    if not has_query_revision_runtime:
        blockers.append(
            {
                "code": "s1_08_query_revision_runtime_missing",
                "owner": "S1_08_evidence_tool_planner",
                "observed": False,
                "required": True,
                "effect": "query_revision_quality_not_measurable",
            }
        )

    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": "upstream_blocked_candidate_generation_before_ranking",
        "policy_digest": canonical_digest(policy),
        "benchmark_binding": {
            "shared_pack_digest": visible_pack["pack_digest"],
            "hidden_scoring_digest": hidden_scoring["hidden_scoring_digest"],
            "as_of": visible_pack["as_of"],
            "cases": list(CASES),
            "sources": len(benchmark_sources),
            "http_sources": len(benchmark_http_urls),
            "evidence_items": sum(len(rows) for rows in evidence_by_case.values()),
            "mandatory_evidence_items": len(mandatory_evidence_ids),
            "target_groups": len(target_groups),
            "target_group_manifest": target_groups,
        },
        "candidate_ceiling_audit": {
            "governed_pack_distinct_source_urls": len(governed_urls),
            "live_source_runtime_distinct_urls": len(live_urls),
            "active_distinct_source_urls": len(active_urls),
            "benchmark_http_source_exact_url_matches": len(exact_source_matches),
            "benchmark_http_source_exact_url_match_recall": round(
                source_match_recall, 6
            ),
            "exact_match_is_conservative_lower_bound": True,
            "semantic_alternative_source_equivalence_proven": False,
            "legacy_bm25_current_authority": False,
            "current_provider_neutral_executable_search_contract": False,
            "query_revision_runtime": False,
            "ranking_metrics_admitted": False,
        },
        "blockers": blockers,
        "decision": {
            "label": "upstream_blocked",
            "next_bundle": (
                "S1_08_CURRENT_SOURCE_CATALOG_CANDIDATE_GENERATION_"
                "QUERY_REVISION_AND_GOLD_SLOT_MATCH_RUNTIME"
            ),
            "reranker_training_or_tuning": False,
            "model_provider_network_calls": [0, 0, 0],
            "reason": (
                "The current candidate ceiling cannot support the preregistered "
                "Gold-slot recall target, so ranking scores would be misleading."
            ),
        },
        "known_boundary": (
            "This is an entry and candidate-ceiling audit, not a live retrieval run. "
            "Exact source URL overlap is a conservative lower bound and does not "
            "claim that alternative authoritative sources are impossible."
        ),
    }
    result = {**body, "program_digest": canonical_digest(body)}
    validate_s1_08_entry_audit(result, policy=policy)
    return result


def validate_s1_08_entry_audit(
    program: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> None:
    normalized = deepcopy(dict(program))
    observed_digest = normalized.pop("program_digest", None)
    if (
        normalized.get("schema_version") != PROGRAM_SCHEMA
        or normalized.get("contract_ref") != CONTRACT_REF
        or observed_digest != canonical_digest(normalized)
        or normalized.get("policy_digest") != canonical_digest(policy)
        or normalized.get("status")
        != "upstream_blocked_candidate_generation_before_ranking"
    ):
        raise S108AgenticSearchQualityError("s1_08_entry_audit_invalid")
    binding = normalized.get("benchmark_binding") or {}
    ceiling = normalized.get("candidate_ceiling_audit") or {}
    decision = normalized.get("decision") or {}
    if (
        binding.get("cases") != list(CASES)
        or binding.get("sources") != 10
        or binding.get("evidence_items") != 33
        or binding.get("mandatory_evidence_items") != 32
        or binding.get("target_groups") != 12
        or ceiling.get("ranking_metrics_admitted") is not False
        or ceiling.get("legacy_bm25_current_authority") is not False
        or decision.get("reranker_training_or_tuning") is not False
        or decision.get("model_provider_network_calls") != [0, 0, 0]
    ):
        raise S108AgenticSearchQualityError(
            "s1_08_entry_audit_boundary_invalid"
        )
    blocker_codes = {row.get("code") for row in normalized.get("blockers") or ()}
    required_codes = {
        "s1_08_gold_source_candidate_ceiling_unproven",
        "s1_08_current_provider_neutral_search_contract_missing",
        "s1_08_query_revision_runtime_missing",
    }
    if not required_codes.issubset(blocker_codes):
        raise S108AgenticSearchQualityError("s1_08_entry_blocker_set_invalid")


def _validate_inputs(
    *,
    policy: Mapping[str, Any],
    freeze: Mapping[str, Any],
    visible_pack: Mapping[str, Any],
    hidden_scoring: Mapping[str, Any],
) -> None:
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise S108AgenticSearchQualityError("s1_08_policy_not_loaded")
    benchmark = policy["benchmark"]
    if (
        freeze.get("shared_pack_digest") != benchmark["shared_pack_digest"]
        or freeze.get("hidden_scoring_digest")
        != benchmark["hidden_scoring_digest"]
        or visible_pack.get("pack_digest") != benchmark["shared_pack_digest"]
        or hidden_scoring.get("hidden_scoring_digest")
        != benchmark["hidden_scoring_digest"]
        or hidden_scoring.get("shared_pack_digest")
        != visible_pack.get("pack_digest")
        or visible_pack.get("as_of") != policy.get("as_of")
    ):
        raise S108AgenticSearchQualityError("s1_08_benchmark_binding_invalid")
    visible_cases = tuple(row.get("case_key") for row in visible_pack.get("cases") or ())
    hidden_cases = tuple(row.get("case_key") for row in hidden_scoring.get("cases") or ())
    if visible_cases != CASES or hidden_cases != CASES:
        raise S108AgenticSearchQualityError("s1_08_benchmark_case_set_invalid")
    as_of = date.fromisoformat(str(policy["as_of"]))
    if any(
        date.fromisoformat(str(row["published_on"])) > as_of
        for row in visible_pack.get("source_registry") or ()
    ):
        raise S108AgenticSearchQualityError("s1_08_future_source_invalid")


def _governed_pack_urls(result: Mapping[str, Any]) -> set[str]:
    queries = (
        result.get("retrieval_usefulness_program", {}).get("query_results") or ()
    )
    return {
        _normalize_url(str(candidate.get("source_url") or ""))
        for query in queries
        for candidate in query.get("selected_candidates") or ()
        if candidate.get("source_url")
    }


def _source_runtime_urls(result: Mapping[str, Any]) -> set[str]:
    return {
        _normalize_url(str(row.get("final_url") or ""))
        for row in (result.get("results") or {}).values()
        if row.get("status") == "ok" and row.get("final_url")
    }


def _normalize_url(value: str) -> str:
    return value.strip().rstrip("/")


__all__ = [
    "CONTRACT_REF",
    "PROGRAM_SCHEMA",
    "S108AgenticSearchQualityError",
    "canonical_digest",
    "compile_s1_08_entry_audit",
    "load_s1_08_policy",
    "validate_s1_08_entry_audit",
]
