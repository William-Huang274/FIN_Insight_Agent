from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from sec_agent.s1_08_firecrawl_semantic_control import load_plan  # noqa: E402
from sec_agent.s1_08_provider_wire_projection import (  # noqa: E402
    compile_execution_units,
    compile_wire_requests,
    load_wire_projection_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (  # noqa: E402
    load_tencent_wsa_candidate_profile,
)


CATALOG_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
INTENT_POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_relationship_aware_search_intent_policy_v1_0.json"
WIRE_POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_domestic_provider_wire_projection_policy_v1_0.json"
PROFILE_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_tencent_wsa_candidate_provider_profile_v1_0.json"
VISIBLE_PATH = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
CONTROL_PLAN_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_plan_v1_0.json"
SCORING_PATH = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_scoring_v1_0.json"
FIRECRAWL_RESULT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_result_v1_0.json"
FIRECRAWL_ASSESSMENT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_assessment_v1_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_fresh_credential_and_same_matrix_comparator_decision_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_zero_call_proof_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential-attested-fresh-unexposed", action="store_true")
    args = parser.parse_args()
    id_present = bool(os.environ.get("TENCENTCLOUD_SECRET_ID", "").strip())
    key_present = bool(os.environ.get("TENCENTCLOUD_SECRET_KEY", "").strip())
    if not id_present or not key_present:
        raise RuntimeError("tencent_environment_credential_presence_missing")
    if not args.credential_attested_fresh_unexposed:
        raise RuntimeError("tencent_credential_freshness_attestation_missing")

    visible = _load(VISIBLE_PATH)
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    catalog = load_source_catalog(CATALOG_PATH)
    intent_policy = load_search_intent_policy(INTENT_POLICY_PATH)
    wire_policy = load_wire_projection_policy(WIRE_POLICY_PATH)
    profile = load_tencent_wsa_candidate_profile(PROFILE_PATH)
    control_plan = load_plan(CONTROL_PLAN_PATH)
    intents = compile_search_intents(
        catalog=catalog,
        policy=intent_policy,
        research_objectives=objectives,
    )
    requests = compile_wire_requests(
        intents=intents,
        policy=wire_policy,
        provider_ids=["tencent_wsa_searchpro_standard"],
    )
    semantic_units = [
        row
        for row in compile_execution_units(requests=requests)
        if row.route_class == "semantic_open_web"
    ]
    units_by_intent = {}
    for unit in semantic_units:
        if len(unit.consumer_intent_ids) != 1:
            raise RuntimeError("tencent_semantic_unit_consumer_count_invalid")
        units_by_intent[unit.consumer_intent_ids[0]] = unit
    proof_rows = []
    for control_row in control_plan["query_rows"]:
        intent_id = str(control_row["intent_id"])
        unit = units_by_intent.get(intent_id)
        if (
            unit is None
            or unit.compact_query_text != control_row["query_text"]
            or dict(unit.request_body) != {"Query": control_row["query_text"]}
            or unit.send_authorized is not False
        ):
            raise RuntimeError("tencent_firecrawl_same_matrix_parity_failed")
        proof_rows.append(
            {
                "ordinal": control_row["ordinal"],
                "intent_id": intent_id,
                "intent_digest": control_row["intent_digest"],
                "query_text_digest": canonical_digest(
                    {"query_text": control_row["query_text"]}
                ),
                "request_body_fields": ["Query"],
                "request_payload_digest": unit.request_payload_digest,
                "execution_unit_digest": unit.execution_unit_digest,
                "send_authorized": False,
            }
        )
    if (
        len(proof_rows) != 24
        or len({row["intent_id"] for row in proof_rows}) != 24
        or len({row["execution_unit_digest"] for row in proof_rows}) != 24
    ):
        raise RuntimeError("tencent_semantic_proof_matrix_invalid")

    decision_body = {
        "schema_version": "fin_ia_0_1_3_s1_08_tencent_fresh_credential_and_same_matrix_comparator_decision_v1_0",
        "recorded_at": "2026-08-08",
        "run_scope": "S1_08_DOMESTIC_PROVIDER_FRESH_CREDENTIAL_READINESS_AND_SAME_MATRIX_COMPARATOR_AUTHORITY_DECISION",
        "status": "tencent_hidden_credentials_present_semantic_same_matrix_selected_runner_proof_required_before_live",
        "credential_readiness": {
            "provider": "tencent_wsa_searchpro_standard",
            "environment_names_checked": [
                "TENCENTCLOUD_SECRET_ID",
                "TENCENTCLOUD_SECRET_KEY"
            ],
            "all_required_present": True,
            "user_attested_fresh_unexposed_after_rotation": True,
            "credential_values_read_back_logged_or_persisted": False,
            "chat_exposed_secret_reuse_allowed": False
        },
        "lane_decision": {
            "selected_lane": "semantic_open_web",
            "selected_execution_units": 24,
            "control_plan_digest": control_plan["plan_digest"],
            "query_text_parity_with_firecrawl_control": True,
            "precise_official_units_authorized": 0,
            "combined_46_unit_execution_authorized": False,
            "live_execution_authorized_by_this_decision": False
        },
        "required_successor": {
            "scope": "S1_08_TENCENT_RELATIONSHIP_AWARE_SEMANTIC_SAME_MATRIX_RUNNER_ZERO_CALL_IMPLEMENTATION_AND_PROOF",
            "requirements": [
                "bind all 24 Tencent Query-only requests to the immutable Firecrawl control intent identities",
                "read credentials from environment only and never persist values",
                "capture safe request and raw response or typed failure before normalization",
                "terminalize remaining identities without network after systemic authentication or entitlement refusal",
                "load evaluator-only target sources only after all 24 identities are terminal",
                "report useful@10 target-in-pool dates diversity standard-version cost and latency",
                "never fetch documents run a model use a reranker promote Evidence or integrate SourceHunter"
            ]
        },
        "known_boundary": "Credential presence and user freshness attestation make one bounded Tencent successor eligible for zero-call proof. They do not prove authentication, standard tier, recall, dates, SourceHunter integration or production quality."
    }
    decision = {**decision_body, "decision_digest": canonical_digest(decision_body)}
    _write(DECISION_PATH, decision)

    proof_body = {
        "schema_version": "fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_zero_call_proof_v1_0",
        "recorded_at": "2026-08-08",
        "status": "zero_call_same_matrix_wire_and_runner_input_binding_pass",
        "run_scope": "S1_08_TENCENT_RELATIONSHIP_AWARE_SEMANTIC_SAME_MATRIX_RUNNER_ZERO_CALL_IMPLEMENTATION_AND_PROOF",
        "provider_id": "tencent_wsa_searchpro_standard",
        "control_plan": {
            "query_count": 24,
            "control_plan_digest": control_plan["plan_digest"],
            "query_text_parity": True,
            "tencent_query_only_request_count": len(proof_rows),
            "precise_units_included": 0,
            "combined_units_included": 0
        },
        "wire_rows": proof_rows,
        "source_bindings": {
            "catalog_sha256": _sha256(CATALOG_PATH),
            "intent_policy_sha256": _sha256(INTENT_POLICY_PATH),
            "wire_policy_sha256": _sha256(WIRE_POLICY_PATH),
            "wire_projection_sha256": _sha256(ROOT / "src/sec_agent/s1_08_provider_wire_projection.py"),
            "provider_profile_sha256": _sha256(PROFILE_PATH),
            "provider_profile_digest": canonical_digest(profile),
            "control_plan_sha256": _sha256(CONTROL_PLAN_PATH),
            "scoring_contract_sha256": _sha256(SCORING_PATH),
            "firecrawl_result_sha256": _sha256(FIRECRAWL_RESULT_PATH),
            "firecrawl_assessment_sha256": _sha256(FIRECRAWL_ASSESSMENT_PATH),
            "credential_decision_sha256": _sha256(DECISION_PATH)
        },
        "credential_boundary": {
            "required_names_present": True,
            "values_read_back_logged_or_persisted": False,
            "environment_only_at_live_runtime": True
        },
        "authority": {
            "provider_calls": 0,
            "network_calls": 0,
            "model_calls": 0,
            "document_fetches": 0,
            "evidence_promotions": 0,
            "live_execution_authorized": False,
            "sourcehunter_integration_authorized": False
        },
        "next": "S1_08_TENCENT_RELATIONSHIP_AWARE_SEMANTIC_SAME_MATRIX_CLEAN_AUTHORITY_ISSUANCE",
        "known_boundary": "This proof establishes exact query parity and secret-safe runner inputs only. Tencent authentication, observed tier, live candidate recall, dates, diversity, cost, latency and SourceHunter readiness remain unproven."
    }
    proof = {**proof_body, "proof_digest": canonical_digest(proof_body)}
    _write(PROOF_PATH, proof)
    print(
        json.dumps(
            {
                "decision_status": decision["status"],
                "proof_status": proof["status"],
                "query_count": len(proof_rows),
                "external_calls": 0,
                "proof_digest": proof["proof_digest"]
            },
            ensure_ascii=True,
            indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
