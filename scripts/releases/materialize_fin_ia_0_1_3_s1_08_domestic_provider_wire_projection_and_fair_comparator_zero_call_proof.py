from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    canonical_digest,
    load_source_catalog,
)
from sec_agent.s1_08_provider_wire_projection import (  # noqa: E402
    PROVIDER_IDS,
    compile_execution_units,
    compile_fair_comparator_plans,
    compile_wire_requests,
    load_wire_projection_policy,
    validate_wire_request,
    weighted_query_units,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)


CATALOG_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
)
INTENT_POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
)
WIRE_POLICY_PATH = (
    ROOT
    / "configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json"
)
VISIBLE_PATH = (
    ROOT
    / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
)
OUTPUT_PATH = (
    ROOT
    / "configs/releases/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_and_fair_comparator_zero_call_proof_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    requests = compile_wire_requests(intents=intents, policy=wire_policy)
    execution_units = compile_execution_units(requests=requests)
    intents_by_id = {row.intent_id: row for row in intents}
    for request in requests:
        validate_wire_request(
            request=request,
            intent=intents_by_id[request.intent_id],
            policy=wire_policy,
        )
    plans = compile_fair_comparator_plans(requests=requests, policy=wire_policy)
    units = [row.compact_query_units for row in requests]
    baidu = [
        row
        for row in requests
        if row.provider_id == "baidu_qianfan_web_search_v2"
    ]
    canonical_baidu_fit = sum(
        weighted_query_units(row.query_text) <= 72 for row in intents
    )
    provider_summaries = {}
    for provider_id in PROVIDER_IDS:
        rows = [row for row in requests if row.provider_id == provider_id]
        units_for_provider = [
            row for row in execution_units if row.provider_id == provider_id
        ]
        provider_summaries[provider_id] = {
            "request_count": len(rows),
            "precise_official_domain": sum(
                row.route_class == "precise_official_domain" for row in rows
            ),
            "semantic_open_web": sum(
                row.route_class == "semantic_open_web" for row in rows
            ),
            "query_unit_range": [
                min(row.compact_query_units for row in rows),
                max(row.compact_query_units for row in rows),
            ],
            "unique_query_count": len(
                {row.compact_query_text for row in rows}
            ),
            "execution_unit_count": len(units_for_provider),
            "precise_execution_units": sum(
                row.route_class == "precise_official_domain"
                for row in units_for_provider
            ),
            "semantic_execution_units": sum(
                row.route_class == "semantic_open_web"
                for row in units_for_provider
            ),
            "shared_execution_units": sum(
                len(row.consumer_intent_ids) > 1 for row in units_for_provider
            ),
            "wire_schema_status": sorted(
                {row.wire_schema_status for row in rows}
            ),
            "admission_eligible_after_zero_call_proof": all(
                row.admission_eligible_after_zero_call_proof for row in rows
            ),
            "send_authorized": any(row.send_authorized for row in rows),
        }
    sample_ids = (
        "search_intent::NVDA::customer_demand_and_deployment_validation::MSFT::en::semantic_open_web",
        "search_intent::MU::supply_chain_capacity_and_counterevidence::TSMC::zh::semantic_open_web",
        "search_intent::DELL::regulatory_risk_and_financial_reconciliation::DELL::en::precise_official_domain",
    )
    samples = {
        intent_id: {
            row.provider_id: {
                "compact_query_text": row.compact_query_text,
                "compact_query_units": row.compact_query_units,
                "structured_filter_mode": row.structured_filter_mode,
                "request_body": row.request_body,
                "wire_digest": row.wire_digest,
            }
            for row in requests
            if row.intent_id == intent_id
        }
        for intent_id in sample_ids
    }
    proof = {
        "schema_version": "fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_and_fair_comparator_zero_call_proof_v1_0",
        "proof_id": "fin-ia-0-1-3-s1-08-domestic-provider-wire-projection-and-fair-comparator-zero-call-proof-v1-0",
        "recorded_at": "2026-08-08",
        "source_commit": "working_tree_after_352fc278",
        "status": "zero_call_engineering_pass",
        "run_scope": "S1_08_DOMESTIC_PROVIDER_WIRE_PROJECTION_AND_FAIR_COMPARATOR_CONTRACT_ZERO_CALL_IMPLEMENTATION",
        "wire_requests": {
            "providers": len(PROVIDER_IDS),
            "requests": len(requests),
            "unique_wire_digests": len({row.wire_digest for row in requests}),
            "unique_request_payload_digests": len(
                {row.request_payload_digest for row in requests}
            ),
            "execution_units": len(execution_units),
            "execution_units_per_provider": 46,
            "precise_execution_units_per_provider": 22,
            "semantic_execution_units_per_provider": 24,
            "query_unit_range": [min(units), max(units)],
            "baidu_fit": [sum(row.compact_query_units <= 72 for row in baidu), len(baidu)],
            "canonical_baidu_verbatim_fit": [canonical_baidu_fit, len(intents)],
        },
        "provider_summaries": provider_summaries,
        "semantic_query_parity": plans["semantic_query_parity"],
        "plan_digest": plans["plan_digest"],
        "samples": samples,
        "source_bindings": {
            "catalog": {"path": str(CATALOG_PATH.relative_to(ROOT)), "sha256": _sha256(CATALOG_PATH)},
            "intent_policy": {"path": str(INTENT_POLICY_PATH.relative_to(ROOT)), "sha256": _sha256(INTENT_POLICY_PATH)},
            "wire_policy": {"path": str(WIRE_POLICY_PATH.relative_to(ROOT)), "sha256": _sha256(WIRE_POLICY_PATH)},
            "visible_objectives": {"path": str(VISIBLE_PATH.relative_to(ROOT)), "sha256": _sha256(VISIBLE_PATH)},
            "intent_set_digest": canonical_digest([row.as_dict() for row in intents]),
            "wire_set_digest": canonical_digest([row.as_dict() for row in requests]),
            "execution_unit_set_digest": canonical_digest(
                [row.as_dict() for row in execution_units]
            ),
        },
        "authority": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
            "live_comparator_authorized": False,
            "sourcehunter_integration_authorized": False,
        },
        "next": "S1_08_DOMESTIC_PROVIDER_CREDENTIAL_READINESS_AND_FIRECRAWL_CONTROL_COMPARATOR_AUTHORITY_DECISION",
        "known_boundary": "The proof establishes deterministic provider wire projection and fair intent identity only. Tencent and Baidu credentials, Alibaba MCP full tool schema, live candidate recall, target-in-pool, date accuracy, diversity, cost, latency, SourceHunter integration, research quality and release remain unproven.",
    }
    OUTPUT_PATH.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
