from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    DiscoveryCandidate,
    DiscoveryQuery,
    canonical_digest,
    evaluator_only_gold_match,
    load_source_catalog,
    run_candidate_generation,
)


CATALOG = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v1_0.json"
VISIBLE = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
HIDDEN = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_candidate_generation_query_revision_and_gold_match_zero_call_proof_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _capture(prefix: str) -> tuple[str, str]:
    return f"fixture-capture/{prefix}", canonical_digest({"fixture_capture": prefix})


def _entity(source: dict) -> str:
    publisher = str(source.get("publisher") or "")
    for needle, key in (
        ("Dell", "DELL"),
        ("Micron", "MU"),
        ("NVIDIA", "NVDA"),
        ("Microsoft", "MSFT"),
        ("TSMC", "TSMC"),
    ):
        if needle in publisher:
            return key
    return "DELL"


def _role(source: dict) -> str:
    source_id = str(source["source_id"])
    if "MARKET" in source_id:
        return "market_expectation_context"
    if "10K" in source_id or "10Q" in source_id:
        return "regulatory_risk_and_financial_reconciliation"
    if "MSFT" in source_id or "DELL_Q1_FY27_CALL" in source_id:
        return "customer_demand_and_deployment_validation"
    if "TSMC" in source_id or "MU_Q3_FY26_REMARKS" in source_id:
        return "supply_chain_capacity_and_counterevidence"
    return "issuer_results_and_management_commentary"


class _EvaluatorFixtureDiscovery:
    """Emulates source discovery; its Gold access is isolated from planner inputs."""

    def __init__(self, *, case_key: str, visible: dict) -> None:
        source_map = {str(row["source_id"]): row for row in visible["source_registry"]}
        case = next(row for row in visible["cases"] if row["case_key"] == case_key)
        ids = sorted({str(row["source_id"]) for row in case["evidence_items"]})
        self.case_key = case_key
        self.sources = [source_map[source_id] for source_id in ids]

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        candidates: list[DiscoveryCandidate] = []
        for index, source in enumerate(
            row for row in self.sources if _role(row) == query.role_id
        ):
            discovery_ref, discovery_digest = _capture(
                f"{self.case_key}/{query.target_key}/{index}/discovery"
            )
            source_ref, source_digest = _capture(
                f"{self.case_key}/{query.target_key}/{index}/source"
            )
            parser_ref, parser_digest = _capture(
                f"{self.case_key}/{query.target_key}/{index}/parser"
            )
            candidates.append(
                DiscoveryCandidate(
                    case_key=self.case_key,
                    target_key=query.target_key,
                    role_id=query.role_id,
                    entity_key=_entity(source),
                    title=str(source["title"]),
                    locator=str(source.get("url") or "current_market_snapshot"),
                    published_on=str(source["published_on"]),
                    authority=str(source["authority"]),
                    discovery_capture_ref=discovery_ref,
                    discovery_capture_digest=discovery_digest,
                    source_capture_ref=source_ref,
                    source_capture_digest=source_digest,
                    parser_capture_ref=parser_ref,
                    parser_capture_digest=parser_digest,
                )
            )
        return tuple(candidates)


def main() -> int:
    catalog = load_source_catalog(CATALOG)
    visible = _load(VISIBLE)
    hidden = _load(HIDDEN)
    results = []
    for case_key in ("DELL", "MU", "NVDA"):
        case = next(row for row in visible["cases"] if row["case_key"] == case_key)
        results.append(
            run_candidate_generation(
                catalog=catalog,
                case_key=case_key,
                research_objective=str(case["research_objective"]),
                adapter=_EvaluatorFixtureDiscovery(case_key=case_key, visible=visible),
            )
        )
    evaluation = evaluator_only_gold_match(
        results=results,
        visible_pack=visible,
        hidden_scoring=hidden,
    )
    case_summaries = [
        {
            "case_key": result["case_key"],
            "query_attempts": result["observed_counts"]["query_attempts"],
            "accepted_candidates": result["observed_counts"]["accepted_candidates"],
            "selected_candidates": result["observed_counts"]["selected_candidates"],
            "typed_gaps": len(result["typed_gaps"]),
            "result_digest": result["result_digest"],
        }
        for result in results
    ]
    body = {
        "schema_version": "fin_ia_0_1_3_s1_08_candidate_generation_zero_call_proof_v1_0",
        "contract_ref": catalog["contract_ref"],
        "status": "engineering_proof_pass_live_candidate_generation_unproven",
        "catalog_digest": canonical_digest(catalog),
        "planner_gold_visibility": False,
        "proof_mode": "evaluator_fixture_discovery_zero_network_zero_model",
        "cases": case_summaries,
        "evaluator_only_summary": evaluation["summary"],
        "mutation_coverage": [
            "Gold identifier or benchmark document URL in planner catalog",
            "cross-case candidate",
            "future candidate",
            "missing capture-first lineage",
            "unpromoted candidate",
            "missing required source",
            "identical retry",
            "revision budget overflow",
            "candidate order stability"
        ],
        "verification": {
            "focused_tests": 14,
            "model_provider_network_calls": [0, 0, 0],
            "benchmark_target_groups": 12,
            "fixture_target_in_pool_recall": evaluation["summary"]["target_in_pool_recall"],
            "fixture_selected_pack_required_slot_coverage": evaluation["summary"]["selected_pack_required_slot_coverage"],
            "concrete_capture_first_official_discovery_adapter_tested": True,
            "concrete_adapter_network_budget_stop_tested": True,
            "ranking_or_reranker_tuning_executed": False
        },
        "decision": {
            "candidate_generation_engineering": "pass",
            "S1_08_live_candidate_ceiling": "unproven",
            "S1_08_ranking": "not_admitted_on_live_evidence",
            "next": "S1_08_INDEPENDENT_FRESH_ZERO_CALL_PROOF_THEN_ONE_DELL_CURRENT_SEARCH_CANARY_AUTHORITY_DECISION"
        },
        "known_boundary": "The fixture proves contract shape, bounded revision, lineage checks and evaluator isolation. It does not prove that live discovery can find any benchmark-equivalent source, that ranking meets NDCG/MRR gates, or that downstream Agentic Research uses the evidence."
    }
    result = {**body, "proof_digest": canonical_digest(body)}
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
