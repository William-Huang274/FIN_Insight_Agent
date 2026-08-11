from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "post_proof_program_scope_replace_decision_v1_0.json"
)
SOURCE_DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "fresh_engineering_proof_and_provider_capability_binding_decision_v1_0.json"
)
POLICY = ROOT / (
    "apps/workbench/backend/application/"
    "bounded_agent_contract_policies.py"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_replace_is_grounded_and_does_not_grant_execution() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    assert decision["decision_label"] == "scope_replace"
    assert decision["source_decision"]["sha256"] == _sha256(
        SOURCE_DECISION
    )
    authority = decision["authority_boundary"]
    assert authority["program_scope_replace_decision_authorized"] is True
    for key in (
        "runtime_or_business_code_change_authorized",
        "replacement_implementation_authorized",
        "credential_read_probe_or_configuration_authorized",
        "model_or_provider_execution_authorized",
        "single_node_canary_authorized",
        "admission_issuance_authorized",
        "MU_T06_execution_authorized",
        "DELL_R12_authorized",
        "provider_hopping_authorized",
    ):
        assert authority[key] is False
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["stage_disposition"]["S4_T06"] == "not_entered"
    assert decision["next_action_authorized"] is False


def test_server_subset_and_local_semantic_rules_are_separated() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_DECISION.read_text(encoding="utf-8"))
    contract = decision["replacement_contract"]
    server = contract["server_wire_schema"]
    local = contract["local_semantic_validator"]
    assert server["allowed_keywords"] == [
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "enum",
    ]
    assert server["array_rules"]["uniqueItems_forbidden_on_server_wire"]
    assert local["numeric_alias_uniqueness_required"]
    assert local["counterevidence_alias_uniqueness_required"]
    assert local["failure_before_business_artifact_commit"]
    checks = decision["replacement_bundle_acceptance"]
    assert "uniqueItems_is_absent" in checks["server_schema_checks"]
    assert (
        "duplicate_counterevidence_alias_rejected_before_artifact"
        in checks["local_validator_mutations"]
    )

    assert source["fresh_engineering_proof"]["schema_common_blocker"][
        "keyword"
    ] == "uniqueItems"
    policy_text = POLICY.read_text(encoding="utf-8")
    assert (
        "if len(counterevidence) != len(set(counterevidence))"
        in policy_text
    )
    assert '"counterevidence_alias_duplicate"' in policy_text


def test_replacement_has_a_hard_anti_loop_ceiling() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    ceiling = decision["anti_loop_ceiling"]
    assert ceiling["replacement_zero_call_implementation_bundles_maximum"] == 1
    assert ceiling["replacement_bundle_requires_separate_authority"]
    assert ceiling["automatic_follow_on_repair_bundles"] == 0
    assert (
        ceiling["field_by_field_prompt_regex_allowlist_patch_iterations"]
        == 0
    )
    assert ceiling["single_node_canary_after_fresh_proof_maximum"] == 1
    assert ceiling["single_node_canary_requires_separate_authority"]
    assert ceiling["DELL_R12"] is False
    assert decision["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-"
        "SERVER-SUBSET-CONFORMANT-REPLACEMENT-MINIMUM-ZERO-CALL-"
        "IMPLEMENTATION"
    )
    assert decision["root_cause_status"][
        "RC-P36-069-s4-R11-case-numeric-failure-telemetry-not-allowlisted"
    ] == "closed_remains_closed"
