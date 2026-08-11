from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_firecrawl_semantic_control import (  # noqa: E402
    CONTRACT_REF,
    PLAN_SCHEMA,
    load_plan,
)
from sec_agent.s1_08_provider_wire_projection import (  # noqa: E402
    compile_execution_units,
    compile_wire_requests,
    load_wire_projection_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


CATALOG_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
INTENT_POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
WIRE_POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json"
VISIBLE_PATH = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
SCORING_PATH = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0.json"
A4_TERMINAL_PATH = ROOT / "artifacts/runtime/provider_market_scan/firecrawl_keyless_a4_customer_supply_en_20260808/terminal-result.json"
A4_ASSESSMENT_PATH = ROOT / "artifacts/runtime/provider_market_scan/firecrawl_keyless_a4_customer_supply_en_20260808/assessment.json"
PLAN_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_zero_call_proof_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    catalog = load_source_catalog(CATALOG_PATH)
    intent_policy = load_search_intent_policy(INTENT_POLICY_PATH)
    wire_policy = load_wire_projection_policy(WIRE_POLICY_PATH)
    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=catalog,
        policy=intent_policy,
        research_objectives=objectives,
    )
    intents_by_id = {row.intent_id: row for row in intents}
    requests = compile_wire_requests(
        intents=intents,
        policy=wire_policy,
        provider_ids=["firecrawl_keyless_search"],
    )
    units = [
        row
        for row in compile_execution_units(requests=requests)
        if row.route_class == "semantic_open_web"
    ]
    query_rows = []
    for ordinal, unit in enumerate(units, start=1):
        if len(unit.consumer_intent_ids) != 1:
            raise RuntimeError("semantic_control_unit_must_have_one_consumer")
        intent = intents_by_id[unit.consumer_intent_ids[0]]
        owner_profile = intent_policy["entity_search_profiles"][
            intent.evidence_owner_entity_key
        ]
        owner_markers = list(
            dict.fromkeys(
                [
                    wire_policy["compact_entity_terms"][
                        intent.evidence_owner_entity_key
                    ][intent.language],
                    *owner_profile["localized_aliases"][intent.language],
                ]
            )
        )
        topic_markers = list(
            dict.fromkeys(
                wire_policy["entity_slot_topic_terms"][
                    intent.evidence_owner_entity_key
                ][intent.evidence_slot_id][intent.language]
            )
        )
        query_rows.append(
            {
                "ordinal": ordinal,
                "provider_id": unit.provider_id,
                "route_class": unit.route_class,
                "intent_id": intent.intent_id,
                "intent_digest": intent.intent_digest,
                "execution_unit_digest": unit.execution_unit_digest,
                "request_payload_digest": unit.request_payload_digest,
                "case_key": intent.case_key,
                "evidence_slot_id": intent.evidence_slot_id,
                "subject_entity_key": intent.subject_entity_key,
                "evidence_owner_entity_key": intent.evidence_owner_entity_key,
                "claim_direction": intent.claim_direction,
                "source_families": list(intent.source_families),
                "language": intent.language,
                "query_text": unit.compact_query_text,
                "owner_markers": owner_markers,
                "topic_markers": topic_markers,
                "request_body": unit.request_body,
            }
        )
    plan_body = {
        "schema_version": PLAN_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "recorded_at": "2026-08-08",
        "status": "frozen_gold_blind_semantic_control_plan",
        "provider_id": "firecrawl_keyless_search",
        "endpoint": "https://api.firecrawl.dev/v2/search",
        "query_rows": query_rows,
        "execution_budget": {
            "planned_queries": 24,
            "provider_call_ceiling": 24,
            "network_call_ceiling": 24,
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
            "document_fetch_ceiling": 0,
            "evidence_promotion_ceiling": 0,
            "result_ceiling_per_query": 10,
            "combined_precise_and_semantic_run_allowed": False,
        },
        "capability_boundary": {
            "classification": "diagnostic_semantic_search_control_not_production",
            "gold_visible_to_query_compiler": False,
            "sourcehunter_integration_allowed": False,
            "ranking_or_reranker_allowed": False,
            "evidence_promotion_allowed": False,
            "domestic_provider_capability_established": False,
        },
    }
    plan = {**plan_body, "plan_digest": canonical_digest(plan_body)}
    _write(PLAN_PATH, plan)
    load_plan(PLAN_PATH)
    proof = {
        "schema_version": "fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_zero_call_proof_v1_0",
        "recorded_at": "2026-08-08",
        "status": "zero_call_runner_input_and_replay_binding_pass",
        "run_scope": "S1_08_FIRECRAWL_RELATIONSHIP_AWARE_SEMANTIC_CONTROL_EXACT_ONCE_RUNNER_ZERO_CALL_IMPLEMENTATION",
        "plan": {
            "query_count": len(query_rows),
            "unique_intent_ids": len({row["intent_id"] for row in query_rows}),
            "unique_execution_unit_digests": len(
                {row["execution_unit_digest"] for row in query_rows}
            ),
            "cases": sorted({row["case_key"] for row in query_rows}),
            "slots": sorted({row["evidence_slot_id"] for row in query_rows}),
            "languages": sorted({row["language"] for row in query_rows}),
            "plan_digest": plan["plan_digest"],
        },
        "historical_capture_replay_binding": {
            "attempt_id": "firecrawl_keyless_a4_customer_supply_en_20260808",
            "terminal_sha256": _sha256(A4_TERMINAL_PATH),
            "assessment_sha256": _sha256(A4_ASSESSMENT_PATH),
            "observed_exact_target_in_pool": [0, 6],
            "interpretation": "The old generic-query capture is immutable predecessor evidence, not a result that may be overwritten or reinterpreted as the repaired compiler output.",
        },
        "source_bindings": {
            "catalog_sha256": _sha256(CATALOG_PATH),
            "intent_policy_sha256": _sha256(INTENT_POLICY_PATH),
            "wire_policy_sha256": _sha256(WIRE_POLICY_PATH),
            "visible_objectives_sha256": _sha256(VISIBLE_PATH),
            "scoring_contract_sha256": _sha256(SCORING_PATH),
            "plan_sha256": _sha256(PLAN_PATH),
        },
        "authority": {
            "provider_calls": 0,
            "network_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
            "live_execution_authorized": False,
            "sourcehunter_integration_authorized": False,
        },
        "next": "S1_08_FIRECRAWL_RELATIONSHIP_AWARE_SEMANTIC_CONTROL_EXACT_LIVE_AUTHORITY_ISSUANCE",
        "known_boundary": "This proof freezes runner input and predecessor replay identity only. Live Firecrawl recall, dates, diversity, credits, latency, domestic provider capability, SourceHunter, research quality and release remain unproven.",
    }
    _write(PROOF_PATH, proof)
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
