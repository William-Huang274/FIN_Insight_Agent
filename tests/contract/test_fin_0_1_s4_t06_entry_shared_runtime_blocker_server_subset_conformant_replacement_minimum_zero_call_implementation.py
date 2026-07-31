from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "server_subset_conformant_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)
SOURCE_DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "post_proof_program_scope_replace_decision_v1_0.json"
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
    S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF,
    S4_STRICT_TRUTH_KERNEL_LOCAL_VALIDATOR_REF,
    S4_STRICT_TRUTH_KERNEL_POLICY_REF,
    StrictTruthKernelPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    StrictTruthKernelJsonSchemaAdapter,
)
from test_fin_0_1_s4_t06_entry_shared_runtime_blocker_minimum_zero_call_implementation import (
    _adapted_first_cell,
    _case_fixture_input_and_admission,
)


def _schema_keyword_paths(
    schema: Mapping[str, Any],
    *,
    path: str = "$",
) -> list[tuple[str, str]]:
    result = [(path, str(keyword)) for keyword in schema]
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        for field, field_schema in properties.items():
            result.extend(
                _schema_keyword_paths(
                    field_schema,
                    path=f"{path}.properties.{field}",
                )
            )
    items = schema.get("items")
    if isinstance(items, Mapping):
        result.extend(
            _schema_keyword_paths(items, path=f"{path}.items")
        )
    return result


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = hashlib.sha256(
        (ROOT / relative_path).read_bytes()
    ).hexdigest()
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


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_server_schema_is_compiled_from_supported_subset(
    ticker: str,
) -> None:
    input_pack, _ = _case_fixture_input_and_admission(ticker)
    policy = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(input_pack)
    )
    semantic = policy.semantic_json_schema()
    server = policy.server_json_schema()
    server_serialized = json.dumps(server, ensure_ascii=False)

    assert '"uniqueItems": true' in json.dumps(
        semantic,
        ensure_ascii=False,
    )
    assert "uniqueItems" not in server_serialized
    assert all(
        keyword
        in OpenAIStructuredOutputsSubsetCompiler.allowed_keywords
        for _, keyword in _schema_keyword_paths(server)
    )
    assert server == policy.json_schema()
    assert (
        StrictTruthKernelJsonSchemaAdapter.text_format(policy)[
            "format"
        ]["schema"]
        == server
    )
    assert all(
        field not in server_serialized
        for field in (
            "statement",
            "boundary",
            "exact_value",
            "currency",
            "period",
            "entity_ref",
            "lineage",
        )
    )


def test_prompt_schema_and_local_validator_share_versioned_owner() -> None:
    input_pack, _ = _case_fixture_input_and_admission("DELL")
    policy = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(input_pack)
    )
    prompt = policy.prompt_contract()
    assert S4_STRICT_TRUTH_KERNEL_POLICY_REF.endswith(":v2")
    assert prompt["contract_ref"] == S4_STRICT_TRUTH_KERNEL_POLICY_REF
    assert prompt["server_schema_compiler_ref"] == (
        S4_OPENAI_STRUCTURED_OUTPUTS_SUBSET_COMPILER_REF
    )
    assert prompt["local_validator_ref"] == (
        S4_STRICT_TRUTH_KERNEL_LOCAL_VALIDATOR_REF
    )
    assert prompt["strict_json_schema"] == policy.server_json_schema()
    assert prompt["local_semantic_rules"] == {
        "numeric_alias_uniqueness_required": True,
        "counterevidence_alias_uniqueness_required": True,
        "cross_case_alias_rejected": True,
        "closed_enum_membership_required": True,
    }
    assert "uniqueItems" not in json.dumps(
        prompt,
        ensure_ascii=False,
    )


def test_compiler_rejects_unknown_keywords_and_invalid_object_contract() -> None:
    with pytest.raises(
        ValueError,
        match="strict_server_schema_keyword_not_allowlisted",
    ):
        OpenAIStructuredOutputsSubsetCompiler.compile(
            {"type": "string", "pattern": "forbidden"}
        )
    with pytest.raises(
        ValueError,
        match="strict_server_schema_object_contract_invalid",
    ):
        OpenAIStructuredOutputsSubsetCompiler.compile(
            {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            }
        )


def test_duplicate_counterevidence_remains_local_L1_hard_failure() -> None:
    input_pack, _ = _case_fixture_input_and_admission("DELL")
    policy = StrictTruthKernelPolicy.from_cell_input(
        _adapted_first_cell(input_pack)
    )
    evidence_alias = policy.evidence_aliases[0]
    rendered, violation = policy.render_provider_output(
        {
            "program_cell_id": policy.program_cell_id,
            "fact_judgments": [
                {
                    "numeric_alias": policy.strict_numeric_aliases[0],
                    "direction": "supports",
                    "materiality": "high",
                    "confidence": "high",
                    "interpretation_code": "directional_support",
                    "counterevidence_aliases": [
                        evidence_alias,
                        evidence_alias,
                    ],
                }
            ],
            "terminal_class": "supported",
        }
    )
    assert rendered is None
    assert violation is not None
    assert violation.subtype == "counterevidence_alias_duplicate"
    assert violation.telemetry()["acceptance_layer"] == (
        "L1_hard_integrity"
    )


def test_implementation_record_binds_current_code_and_zero_call_boundary() -> None:
    implementation = json.loads(
        IMPLEMENTATION.read_text(encoding="utf-8")
    )
    source_decision = json.loads(
        SOURCE_DECISION.read_text(encoding="utf-8")
    )
    assert implementation["status"] == (
        "pass_zero_call_replacement_implementation_fixture_proven_"
        "fresh_engineering_proof_pending"
    )
    assert implementation["source_decision"]["sha256"] == hashlib.sha256(
        SOURCE_DECISION.read_bytes()
    ).hexdigest()
    assert implementation["replacement_contract"] == source_decision[
        "replacement_contract"
    ]
    assert implementation["fixture_proof"][
        "per_case_nodes_callbacks_captures_artifacts"
    ] == [6, 12, 12, 9]
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["scope_limit"][
        "replacement_zero_call_implementation_bundles_consumed"
    ] == 1
    assert implementation["scope_limit"][
        "automatic_follow_on_repair_bundles"
    ] == 0
    assert implementation["next_action"] == (
        "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-REPLACEMENT-"
        "FRESH-ENGINEERING-PROOF-AND-PROVIDER-CAPABILITY-BINDING-"
        "DECISION"
    )
    assert implementation["next_action_authorized"] is False
    historical_executor = (
        "apps/workbench/backend/application/bounded_agent_executor.py"
    )
    historical_test = (
        "tests/contract/test_fin_0_1_s4_t06_entry_shared_runtime_blocker_"
        "server_subset_conformant_replacement_minimum_zero_call_"
        "implementation.py"
    )
    assert implementation["exact_code_bindings"][historical_executor] == (
        "14da78cd02f0fc0e21652b060665cffab7f6487b27f707512b762ecb2bd508f6"
    )
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        if relative_path in {historical_executor, historical_test}:
            continue
        _assert_historical_or_current(relative_path, expected_sha256)
    current = json.loads(CURRENT_MU_PROOF.read_text(encoding="utf-8"))
    _assert_historical_or_current(
        historical_executor,
        current["code_bindings"][historical_executor],
    )
