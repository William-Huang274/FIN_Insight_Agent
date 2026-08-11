from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEEPSEEK_MAINLINE = (
    "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
    "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_replacement_"
    "fresh_engineering_proof_and_provider_capability_binding_"
    "decision_v1_0.json"
)
CURRENT_MU_PROOF = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_mu_deepseek_mainline_fresh_exact_"
    "admission_preparation_zero_call_proof_v1_0.json"
)
CURRENT_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)
CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    OpenAIStructuredOutputsSubsetCompiler,
    StrictTruthKernelPolicy,
)
from test_fin_0_1_s4_t06_entry_shared_runtime_blocker_minimum_zero_call_implementation import (
    _adapted_first_cell,
    _case_fixture_input_and_admission,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = _sha256(ROOT / relative_path)
    if observed == historical_sha256:
        return
    identity_boundary = json.loads(
        CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION.read_text(
            encoding="utf-8"
        )
    )
    if (
        identity_boundary["exact_code_bindings"].get(relative_path)
        == observed
    ):
        return
    current = json.loads(
        CURRENT_RUNTIME_IMPLEMENTATION.read_text(encoding="utf-8")
    )
    assert relative_path in current[
        "historical_exact_binding_supersession"
    ]["allowed_changed_paths"]
    assert current["exact_code_bindings"][relative_path] == observed


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _walk_schema(
    schema: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    result = [schema]
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        for nested in properties.values():
            result.extend(_walk_schema(nested))
    items = schema.get("items")
    if isinstance(items, Mapping):
        result.extend(_walk_schema(items))
    return result


def test_replacement_fresh_proof_recomputes_exact_code_bindings() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    proof = decision["fresh_engineering_proof"]

    assert decision["decision_label"] == (
        "bind_documented_request_contract_for_canary_candidate"
    )
    assert proof["frozen_code_bindings_match"]
    assert _sha256(
        ROOT / decision["source_implementation"]["ref"]
    ) == decision["source_implementation"]["sha256"]
    historical_executor = (
        "apps/workbench/backend/application/bounded_agent_executor.py"
    )
    historical_test = (
        "tests/contract/test_fin_0_1_s4_t06_entry_shared_runtime_blocker_"
        "server_subset_conformant_replacement_minimum_zero_call_"
        "implementation.py"
    )
    assert proof["exact_code_bindings"][historical_executor] == (
        "14da78cd02f0fc0e21652b060665cffab7f6487b27f707512b762ecb2bd508f6"
    )
    for relative_path, expected in proof["exact_code_bindings"].items():
        if relative_path not in {historical_executor, historical_test}:
            _assert_historical_or_current(relative_path, expected)
    current = json.loads(CURRENT_MU_PROOF.read_text(encoding="utf-8"))
    _assert_historical_or_current(
        historical_executor,
        current["code_bindings"][historical_executor],
    )


def test_three_case_server_schema_recomputation_matches_decision() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    expected = decision["fresh_engineering_proof"][
        "case_server_schema_recomputation"
    ]

    assert set(expected) == {"DELL", "MU", "NVDA"}
    for ticker in expected:
        input_pack, _ = _case_fixture_input_and_admission(ticker)
        policy = StrictTruthKernelPolicy.from_cell_input(
            _adapted_first_cell(input_pack)
        )
        semantic = policy.semantic_json_schema()
        server = policy.server_json_schema()
        nodes = _walk_schema(server)

        assert _canonical_sha256(server) == expected[ticker][
            "schema_sha256"
        ]
        assert "uniqueItems" in json.dumps(semantic)
        assert "uniqueItems" not in json.dumps(server)
        assert server == policy.json_schema()
        assert all(
            keyword
            in OpenAIStructuredOutputsSubsetCompiler.allowed_keywords
            for node in nodes
            for keyword in node
        )
        assert all(
            node.get("additionalProperties") is False
            and set(node.get("properties", {}))
            == set(node.get("required", []))
            for node in nodes
            if node.get("type") == "object"
        )


def test_documented_binding_is_not_inflated_into_live_authority() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    binding = decision["prospective_exact_provider_binding"]

    assert binding["provider"] == "openai"
    assert binding["model"] == "gpt-5.6-sol"
    assert binding[
        "model_level_capability_established_by_official_docs"
    ]
    assert binding["request_schema_subset_compatibility_established"]
    assert binding["provider_capability_ref_documented_request_bound"]
    assert not binding["credential_presence_or_access_established"]
    assert not binding["exact_endpoint_acceptance_established"]
    assert not binding["provider_capability_ref_live_bound"]
    assert binding["single_node_canary_authority_decision_admissible"]
    assert decision["program_disposition"]["single_node_canary"] == (
        "not_authorized_but_eligible_for_separate_authority_decision"
    )
    assert decision["observed_counts"]["actual_model_calls"] == 0
    assert decision["observed_counts"]["actual_provider_calls"] == 0
    assert decision["observed_counts"]["credential_reads_or_probes"] == 0
    assert decision["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-"
        "STRICT-SCHEMA-CANARY-AUTHORITY-DECISION"
    )


def test_backlogs_and_project_os_preserve_the_authority_decision_transition() -> None:
    authority_decision = (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-"
        "STRICT-SCHEMA-CANARY-AUTHORITY-DECISION"
    )
    exact_execution = (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-"
        "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
    )
    http_429_disposition = (
        "S4-T06-ENTRY-OPENAI-HTTP-429-RATE-OR-QUOTA-"
        "PROGRAM-DISPOSITION-DECISION"
    )
    sub2api_rebaseline = (
        "S4-T06-ENTRY-SUB2API-PROVIDER-ROUTE-AND-CAPABILITY-"
        "CONTRACT-REBASELINE-DECISION"
    )
    secure_transport = (
        "S4-T06-ENTRY-SUB2API-SECURE-TRANSPORT-ENDPOINT-CONFIRMATION"
    )
    diagnostic_authority = (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-"
        "DIAGNOSTIC-CANARY-AUTHORITY-DECISION"
    )
    diagnostic_implementation = (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-MINIMUM-ZERO-CALL-IMPLEMENTATION-AND-PREFLIGHT"
    )
    diagnostic_result = (
        "S4-T06-ENTRY-SUB2API-PUBLIC-NON-SENSITIVE-DIAGNOSTIC-"
        "CANARY-POST-RESULT-PROGRAM-DISPOSITION"
    )
    program = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    s4 = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    root_cause_rows = [
        json.loads(line)
        for line in (
            ROOT / "docs/project_os/root_cause_issue_ledger.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rc_070 = [
        row
        for row in root_cause_rows
        if row["issue_id"]
        == "RC-P36-070-s4-t06-strict-schema-unsupported-uniqueItems"
    ][-1]

    assert program["next_action"]["item_id"] in {
        authority_decision,
        exact_execution,
        http_429_disposition,
        sub2api_rebaseline,
        secure_transport,
        diagnostic_authority,
            diagnostic_implementation,
            diagnostic_result,
            DEEPSEEK_MAINLINE,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
        }
    assert s4["current_next_action"] == program["next_action"][
        "item_id"
    ]
    if program["next_action"]["item_id"] == authority_decision:
        assert not program["next_action"]["single_node_canary_authorized"]
        expected_scope = (
            "S4_T06_entry_shared_runtime_blocker_single_node_strict_"
            "schema_canary_authority_decision"
        )
    elif program["next_action"]["item_id"] == exact_execution:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"][
            "single_node_canary_authority_decision_ref"
        ].endswith(
            "single_node_strict_schema_canary_authority_decision_v1_0.json"
        )
        expected_scope = (
            "S4_T06_entry_shared_runtime_blocker_single_node_strict_"
            "schema_canary_exact_once_execution"
        )
    elif program["next_action"]["item_id"] == http_429_disposition:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"]["single_node_canary_consumed"]
        assert program["next_action"]["fresh_strict_schema_canary_consumed"]
        expected_scope = (
            "S4_T06_entry_openai_HTTP_429_rate_or_quota_program_"
            "disposition_decision"
        )
    elif program["next_action"]["item_id"] == sub2api_rebaseline:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"]["single_node_canary_consumed"]
        assert program["next_action"]["fresh_strict_schema_canary_consumed"]
        expected_scope = (
            "S4_T06_entry_Sub2API_provider_route_and_capability_contract_"
            "rebaseline_decision"
        )
    elif program["next_action"]["item_id"] == secure_transport:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"]["single_node_canary_consumed"]
        assert program["next_action"]["fresh_strict_schema_canary_consumed"]
        expected_scope = (
            "S4_T06_entry_Sub2API_secure_transport_endpoint_confirmation"
        )
    elif program["next_action"]["item_id"] == diagnostic_authority:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"]["single_node_canary_consumed"]
        assert program["next_action"]["fresh_strict_schema_canary_consumed"]
        expected_scope = (
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "authority_decision"
        )
    elif program["next_action"]["item_id"] == diagnostic_implementation:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"]["single_node_canary_consumed"]
        assert program["next_action"]["fresh_strict_schema_canary_consumed"]
        expected_scope = (
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "minimum_zero_call_implementation_and_preflight"
        )
    elif program["next_action"]["item_id"] == diagnostic_result:
        assert program["next_action"]["single_node_canary_authorized"]
        assert program["next_action"]["single_node_canary_consumed"]
        assert program["next_action"]["fresh_strict_schema_canary_consumed"]
        expected_scope = (
            "S4_T06_entry_Sub2API_public_non_sensitive_diagnostic_canary_"
            "post_result_program_disposition"
        )
    else:
        assert program["next_action"]["item_id"] in {
            DEEPSEEK_MAINLINE,
            "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
            "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
        }
        expected_scope = (
            "S4_T06_MU_DeepSeek_fresh_exact_admission_preparation_and_"
            "zero_call_proof"
        )
    assert rc_070["allowed_run_scopes"] == [
        expected_scope,
        "repository_and_git_hygiene",
    ]
