from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_compiled_contract_implementation import (
    _compiled_runtime,
)


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_authority_decision_v1_0.json"
)
FRESH_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_deterministic_judgment_"
    "atom_planner_and_compiled_contract_invariant_hardening_fresh_"
    "agent_proof_decision_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_deterministic_judgment_"
    "atom_planner_and_compiled_contract_invariant_hardening_minimum_"
    "zero_call_implementation_v1_0.json"
)
PROSPECTIVE_R7 = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_deterministic_judgment_"
    "atom_planner_and_compiled_contract_invariant_hardening_fresh_"
    "exact_admission_r7.json"
)
NEXT_ACTION = (
    "S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-"
    "CANARIES-EXACT-ONCE-EXECUTION"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _derive_exact_templates() -> dict[str, Any]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
        input_pack, admission, fake = _compiled_runtime("MU")
        result = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-canary-authority-derive",
                "attempt_id": "fixture-canary-authority-derive",
            },
        )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9

    templates: dict[str, Any] = {}
    for call in fake.calls:
        request = call["request"]
        contract = request.get("compiled_judgment_atom_contract")
        if not isinstance(contract, dict):
            continue
        family_id = contract["family_id"]
        if family_id in templates:
            continue
        kwargs = call["kwargs"]
        system = kwargs["messages"][0]["content"]
        user = kwargs["messages"][1]["content"]
        templates[family_id] = {
            "family_id": family_id,
            "segment_id": request["segment_id"],
            "system_prompt_sha256": hashlib.sha256(
                system.encode("utf-8")
            ).hexdigest(),
            "user_payload_sha256": hashlib.sha256(
                user.encode("utf-8")
            ).hexdigest(),
            "canonical_request_sha256": canonical_digest(request),
            "compiled_contract_digest": contract["contract_digest"],
            "wire_schema_sha256": canonical_digest(
                request["required_output_schema"]
            ),
            "required_top_level_keys": request[
                "required_top_level_keys"
            ],
            "allowed_alias_counts": {
                "supports": len(contract.get("allowed_supports", [])),
                "facts": len(contract.get("allowed_facts", [])),
                "claims": len(contract.get("allowed_claims", [])),
                "authorities": len(
                    contract.get("allowed_authorities", [])
                ),
                "dates": len(contract.get("allowed_date_aliases", [])),
            },
            "input_utf8_bytes": len((system + user).encode("utf-8")),
            "estimated_input_tokens": estimate_provider_input_tokens(
                system + "\n" + user
            ),
            "maximum_output_tokens": kwargs["max_tokens"],
        }
    return {
        "input_digest": input_pack.input_digest,
        "templates": templates,
    }


def test_authority_rebinds_current_proof_and_implementation() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    source = authority["source_bindings"]
    assert _sha256(FRESH_PROOF) == source["fresh_proof_sha256"]
    assert _sha256(IMPLEMENTATION) == source["implementation_sha256"]
    proof = json.loads(FRESH_PROOF.read_text(encoding="utf-8"))
    assert source["MU_exact_input_digest"] == (
        proof["fresh_identity"]["input_digest"]
    )
    assert source["prospective_R7_admission_digest"] == (
        proof["prospective_R7_admission"]["digest"]
    )
    assert not PROSPECTIVE_R7.exists()


def test_three_exact_family_templates_are_recomputed_without_network() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    derived = _derive_exact_templates()
    assert derived["input_digest"] == (
        authority["source_bindings"]["MU_exact_input_digest"]
    )
    expected = {
        row["family_id"]: row
        for row in authority["exact_canary_requests"]
    }
    assert derived["templates"] == expected
    assert list(
        authority["canary_isolation_contract"]["execution_order"]
    ) == [
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    ]


def test_authority_is_bounded_to_three_calls_and_no_full_chain() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    allowed = authority["authority"]
    budget = authority["hard_budget"]
    assert allowed["future_exact_once_three_family_canary_execution_authorized"]
    assert not allowed["current_turn_model_or_provider_execution_authorized"]
    assert not allowed["full_chain_execution_authorized"]
    assert not allowed["R7_admission_issuance_authorized"]
    assert not allowed["R7_exact_live_authorized"]
    assert budget["maximum_semantic_model_calls"] == 3
    assert budget["maximum_provider_calls"] == 3
    assert budget["maximum_network_calls"] == 3
    assert budget["maximum_transport_attempts_per_call"] == 1
    assert budget["retry_budget"] == 0
    assert budget["maximum_output_tokens_total"] == 4200
    assert budget["maximum_total_cost_usd"] == 0.03
    assert budget["canonical_work_unit_attempt_run_writes"] == 0
    assert budget["business_artifact_writes"] == 0


def test_capture_failure_and_success_contracts_preserve_stop_boundary() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    capture = authority["capture_and_validation_contract"]
    failure = authority["failure_contract"]
    success = authority["success_contract"]
    assert capture["capture_before_local_validation_or_stop"]
    assert capture["preserve_exact_model_visible_request"]
    assert capture["preserve_final_assistant_output"]
    assert not capture["credential_headers_cookies_and_private_reasoning_persisted"]
    assert not capture["failed_output_business_promotion_allowed"]
    assert failure["first_credible_failure"] == "terminal_stop"
    assert failure["remaining_family_calls_after_failure"] == 0
    assert failure["retry"] == 0
    assert not failure["field_level_patch"]
    assert not failure["full_chain_after_failure"]
    assert success["success_does_not_authorize_R7_admission_or_exact_live"]


def test_current_turn_is_zero_call_and_next_execution_is_exactly_named() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    observed = authority["current_turn_observed_counts"]
    assert all(value == 0 for value in observed.values())
    assert authority["next_action"] == NEXT_ACTION
    assert authority["next_action_authorized"] is True
