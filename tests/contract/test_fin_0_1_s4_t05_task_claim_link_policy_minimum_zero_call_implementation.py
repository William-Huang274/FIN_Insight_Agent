from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
WWC_TRUNCATION_DISPOSITION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_specialist_v7_wwc_segment_"
    "output_truncation_zero_call_root_cause_disposition_v1_0.json"
)
GAP_PROJECTION_AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
GAP_PROJECTION_R5_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_"
    "projection_r5_exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_exact_admission_issuance_v1_0.json"
)
GAP_PROJECTION_FRESH_PROOF = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_research_lead_gap_atom_"
    "deterministic_projection_fresh_agent_proof_decision_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_TASK_CLAIM_LINK_POLICY_REF,
    TaskClaimLinkPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_specialist_v6_local_scope_assembly import (
    _first_segment,
)
from test_fin_0_1_s3_t09_research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation import (
    _CompactV5FullFakeProvider,
    _v5_admission,
)
from test_fin_0_1_s3_t09_specialist_v7_contract_convergence import (
    _semantic_only_mutation,
)

IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_minimum_"
    "zero_call_implementation_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
FRESH_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_agent_proof_decision_v1_0.json"
)
FRESH_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_task_claim_link_policy_"
    "fresh_exact_admission_issuance_v1_0.json"
)
R3_AUTHORITY_DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_and_paired_assessment_"
    "authority_decision_v1_0.json"
)
R3_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
NUMERIC_AUTHORITY_DISPOSITION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_surface_"
    "zero_call_root_cause_disposition_v1_0.json"
)
NUMERIC_AUTHORITY_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
CURRENT_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_case_runtime_binding_"
    "mismatch_zero_call_root_cause_disposition_v1_0.json"
)
NUMERIC_AUTHORITY_PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_agent_"
    "proof_decision_v1_0.json"
)
NUMERIC_AUTHORITY_ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_exact_"
    "admission_issuance_v1_0.json"
)
NUMERIC_AUTHORITY_DECISION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_exact_live_"
    "execution_and_paired_assessment_authority_decision_v1_0.json"
)
R4_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_wwc_numeric_authority_r4_"
    "exact_live_execution_failure_result_v1_0.json"
)
GAP_PROJECTION_DISPOSITION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_remaining_gaps_cardinality_"
    "zero_call_root_cause_disposition_v1_0.json"
)


def _claims() -> list[dict[str, Any]]:
    return [
        {
            "claim_id": "claim-b",
            "statement": "利润捕获仍受产品组合约束。",
            "epistemic_status": "bounded_inference",
            "scope": {
                "entity_ref": "AMD",
                "business_scope_kind": "segment",
                "business_scope_ref": "data_center",
                "period": "FY2027-Q1-53W",
                "metric_or_mechanism": "产品组合与毛利率",
                "attribution_level": "segment",
            },
        },
        {
            "claim_id": "claim-a",
            "statement": "订单转收入需要后续披露验证。",
            "epistemic_status": "cannot_infer",
            "scope": {
                "entity_ref": "AMD",
                "business_scope_kind": "company_total",
                "business_scope_ref": "AMD",
                "period": "FY2027-Q1-53W",
                "metric_or_mechanism": "订单转收入",
                "attribution_level": "company_total",
            },
        },
    ]


def _policy() -> TaskClaimLinkPolicy:
    return TaskClaimLinkPolicy.from_validated_claims(
        program_cell_id="amd-transfer",
        claims=_claims(),
    )


def _task_output(selection: Any, *, raw_claim_id: bool = False) -> dict[str, Any]:
    task = {
        "task_id": "provider-task-001",
        "claim_alias": selection,
    }
    if raw_claim_id:
        task.pop("claim_alias")
        task["claim_id"] = selection
    return {
        "program_cell_id": "amd-transfer",
        "what_would_change": [task],
    }


def _policy_admission(input_pack: Any):
    return _v5_admission(input_pack).model_copy(
        update={
            "task_claim_link_policy_ref": S3_TASK_CLAIM_LINK_POLICY_REF,
        }
    )


def _task_alias_mutation(
    specialists: Mapping[str, dict[str, Any]],
    *,
    force_unknown: bool = False,
):
    def mutate(
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        output = _semantic_only_mutation(request, output)
        if request.get("segment_id") != "actionable_what_would_change_tasks":
            return output
        cell_id = str(request["node_id"]).split(":", 1)[1]
        claim_ids = sorted(
            str(row["claim_id"])
            for row in specialists[cell_id]["judgment_layer"]
        )
        aliases = [
            str(row["claim_alias"])
            for row in request["task_claim_link_contract"]["allowed_claims"]
        ]
        alias_by_claim_id = dict(zip(claim_ids, aliases, strict=True))
        for task in output["what_would_change"]:
            claim_id = str(task.pop("claim_id"))
            task["claim_alias"] = alias_by_claim_id[claim_id]
        if force_unknown:
            output["what_would_change"][0]["claim_alias"] = "Q999"
        return output

    return mutate


def test_policy_aliases_are_deterministic_closed_and_provider_safe() -> None:
    policy = _policy()
    contract = policy.prompt_contract()
    prior = policy.provider_prior_claim_segment(
        {
            "program_cell_id": "amd-transfer",
            "judgment_layer": _claims(),
        }
    )

    assert policy.contract_ref == S3_TASK_CLAIM_LINK_POLICY_REF
    assert [row.alias for row in policy.alias_rows] == ["Q001", "Q002"]
    assert [row.claim_id for row in policy.alias_rows] == [
        "claim-a",
        "claim-b",
    ]
    assert set(contract["allowed_claims"][0]) == {
        "claim_alias",
        "statement",
        "epistemic_status",
        "locally_assembled_scope_summary",
    }
    serialized = json.dumps(
        {"contract": contract, "prior": prior},
        ensure_ascii=False,
    )
    assert "claim-a" not in serialized
    assert "claim-b" not in serialized
    assert "claim_id" not in json.dumps(prior, ensure_ascii=False)
    assert contract[
        "normalization_trim_casefold_prefix_guess_fuzzy_match_nearest_"
        "claim_relink_task_drop_or_rewrite_allowed"
    ] is False


def test_exact_alias_expands_to_original_claim_id_without_residue() -> None:
    output = _task_output("Q002")

    expanded, violation = _policy().expand_task_output(output)

    assert violation is None
    assert expanded is not None
    task = expanded["what_would_change"][0]
    assert task == {
        "task_id": "provider-task-001",
        "claim_id": "claim-b",
    }
    assert "Q002" not in json.dumps(expanded, ensure_ascii=False)
    assert output == _task_output("Q002")


@pytest.mark.parametrize(
    "output",
    (
        _task_output("Q003"),
        _task_output("Q001 "),
        _task_output("q001"),
        _task_output("claim-a", raw_claim_id=True),
        _task_output(""),
        _task_output(None),
    ),
)
def test_all_invalid_claim_selections_use_one_minimum_typed_failure(
    output: dict[str, Any],
) -> None:
    original = deepcopy(output)

    expanded, violation = _policy().expand_task_output(output)

    assert expanded is None
    assert violation is not None
    assert violation.subtype == "task_claim_alias_unknown"
    assert violation.failing_item_count == 1
    assert output == original


def test_WWC_request_uses_closed_alias_and_hides_raw_claim_ids() -> None:
    cells, specialists = _shared_local_id_specialists()
    cell = cells[0]
    cell_id = str(cell["program_cell_id"])
    specialist = specialists[cell_id]
    validated = {
        "facts_explanation_and_terminal": _first_segment(specialist),
        "owner_grade_claim_cards": {
            "program_cell_id": cell_id,
            "judgment_layer": deepcopy(specialist["judgment_layer"]),
        },
    }

    system, request, binding = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id=f"domain_specialist:{cell_id}",
            segment_id="actionable_what_would_change_tasks",
            payload={
                "input_contract_ref": "fixture:input:v1",
                "input_digest": "fixture-input-digest",
                "cell_input": cell,
                "required_output_layers": [],
            },
            validated_segments=validated,
            transport_ref=(
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
            ),
            task_claim_link_policy_ref=S3_TASK_CLAIM_LINK_POLICY_REF,
        )
    )

    task_schema = request["required_output_schema"]["what_would_change"][0]
    assert "claim_alias" in task_schema
    assert "claim_id" not in task_schema
    assert request["task_claim_link_contract"]["contract_ref"] == (
        S3_TASK_CLAIM_LINK_POLICY_REF
    )
    prior_claims = request["validated_prior_segments"][
        "owner_grade_claim_cards"
    ]["judgment_layer"]
    assert all(
        set(row)
        == {
            "claim_alias",
            "statement",
            "epistemic_status",
            "locally_assembled_scope_summary",
        }
        for row in prior_claims
    )
    raw_claim_ids = {
        str(row["claim_id"]) for row in specialist["judgment_layer"]
    }
    serialized = json.dumps(request, ensure_ascii=False)
    assert all(claim_id not in serialized for claim_id in raw_claim_ids)
    assert "do not emit claim_id" in system
    assert binding["task_claim_link_policy_ref"] == (
        S3_TASK_CLAIM_LINK_POLICY_REF
    )


def test_admission_binding_is_explicit_and_legacy_digest_is_unchanged() -> None:
    cells, _ = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    legacy = _v5_admission(input_pack)
    valid = _policy_admission(input_pack)

    assert "task_claim_link_policy_ref" not in legacy.digest_payload()
    valid.assert_profile_admissible()
    assert valid.digest_payload()["task_claim_link_policy_ref"] == (
        S3_TASK_CLAIM_LINK_POLICY_REF
    )

    unsupported = valid.model_copy(
        update={"task_claim_link_policy_ref": "unsupported:v1"}
    )
    with pytest.raises(
        ValueError,
        match="task_claim_link_policy_unsupported",
    ):
        unsupported.assert_profile_admissible()

    wrong_output = valid.model_copy(
        update={
            "output_contract_ref": (
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
            )
        }
    )
    with pytest.raises(
        ValueError,
        match="task_claim_link_policy_capability_binding_required",
    ):
        wrong_output.assert_profile_admissible()


def test_full_fake_provider_expands_before_downstream_and_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _policy_admission(input_pack)
    fake = _CompactV5FullFakeProvider(
        specialists,
        mutation=_task_alias_mutation(specialists),
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")

    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-run-task-claim-link-policy",
            "attempt_id": "fixture-attempt-task-claim-link-policy",
        },
    )

    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    task_requests = [
        row["request"]
        for row in fake.calls
        if row["request"].get("segment_id")
        == "actionable_what_would_change_tasks"
    ]
    assert len(task_requests) == 3
    assert all(
        "claim_alias"
        in request["required_output_schema"]["what_would_change"][0]
        for request in task_requests
    )
    artifact_text = json.dumps(
        [row.model_dump(mode="json") for row in result.artifacts],
        ensure_ascii=False,
    )
    assert "claim_alias" not in artifact_text
    assert '"Q001"' not in artifact_text
    assert '"Q002"' not in artifact_text


def test_unknown_alias_stops_at_WWC_with_content_free_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _policy_admission(input_pack)
    fake = _CompactV5FullFakeProvider(
        specialists,
        mutation=_task_alias_mutation(
            specialists,
            force_unknown=True,
        ),
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")

    with pytest.raises(BoundedAgentExecutionError) as captured:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-run-task-claim-link-stop",
                "attempt_id": "fixture-attempt-task-claim-link-stop",
            },
        )

    assert len(fake.calls) == 3
    assert len(captured.value.provider_output_captures) == 3
    telemetry = captured.value.failure_observation["failure_telemetry"][
        "segmented_specialist_task_claim_link"
    ]
    assert telemetry == {
        "validator_contract": S3_TASK_CLAIM_LINK_POLICY_REF,
        "segment_id": "actionable_what_would_change_tasks",
        "field_id": "what_would_change.claim_alias",
        "failure_subtype": "task_claim_alias_unknown",
        "failing_item_count": 1,
        "raw_alias_persisted": False,
        "claim_id_persisted": False,
        "program_cell_id_persisted": False,
        "item_index_persisted": False,
        "private_reasoning_persisted": False,
    }
    assert "Q999" not in json.dumps(telemetry, ensure_ascii=False)


def test_legacy_raw_task_validation_remains_unchanged() -> None:
    cells, specialists = _shared_local_id_specialists()
    cell = cells[0]
    cell_id = str(cell["program_cell_id"])
    specialist = specialists[cell_id]
    tasks = deepcopy(specialist["what_would_change"])
    claim_by_id = {
        str(row["claim_id"]): row
        for row in specialist["judgment_layer"]
    }

    S3ThreeCellBoundedAgentExecutor._validate_owner_grade_tasks(
        tasks,
        cell,
        claim_by_id,
    )
    tasks[0]["claim_id"] = "C3"
    with pytest.raises(
        ValueError,
        match="s3_owner_grade_WWC_task_incomplete",
    ):
        S3ThreeCellBoundedAgentExecutor._validate_owner_grade_tasks(
            tasks,
            cell,
            claim_by_id,
        )


def test_implementation_result_binds_current_code_scope_and_next_gate() -> None:
    implementation = json.loads(
        IMPLEMENTATION.read_text(encoding="utf-8")
    )
    program = json.loads(PROGRAM_BACKLOG.read_text(encoding="utf-8"))
    detailed = json.loads(DETAILED_BACKLOG.read_text(encoding="utf-8"))

    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["fixture_proof"][
        "full_fake_provider_logical_nodes"
    ] == 6
    assert implementation["fixture_proof"][
        "full_fake_provider_callbacks"
    ] == 12
    assert implementation["fixture_proof"][
        "full_fake_provider_logical_artifacts"
    ] == 9
    assert implementation["fixture_proof"][
        "full_fake_provider_Q_alias_residue"
    ] == 0
    assert {
        row["item"] for row in implementation["deferred_cross_sequence_items"]
    } == {
        "deterministic_locally_assembled_task_identity",
        "complete_typed_WWC_failure_taxonomy",
        "cross_stage_unified_claim_task_identity_redesign",
    }
    assert all(
        row["blocks_current_T05"] is False
        for row in implementation["deferred_cross_sequence_items"]
    )
    latest_implementation = json.loads(
        R7_BINDING_IMPLEMENTATION.read_text(encoding="utf-8")
    )
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            assert latest_implementation["exact_code_bindings"][
                relative_path
            ] == current_sha256

    expected_next = implementation["next_action"]
    assert expected_next == (
        "S4-T05-DELL-WWC-TASK-TO-CLAIM-CLOSED-IDENTITY-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    current_expected = json.loads(
        (
            ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
            if R7_BINDING_IMPLEMENTATION.exists()
            else CURRENT_PROOF
        ).read_text(encoding="utf-8")
    )["next_action"]
    assert program["next_action"]["item_id"] == current_expected
    assert detailed["current_next_action"] == current_expected
    implementation_sha256 = hashlib.sha256(
        IMPLEMENTATION.read_bytes()
    ).hexdigest()
    assert program["next_action"][
        "S4_T05_task_claim_implementation_sha256"
    ] == implementation_sha256
    detailed_t05 = next(
        row for row in detailed["tasks"] if row["item_id"] == "S4-T05"
    )
    assert detailed_t05[
        "task_claim_implementation_sha256"
    ] == implementation_sha256
    assert program["next_action"][
        "S4_T05_minimum_implementation_completed"
    ] is True
    assert program["next_action"][
        "current_S4_T05_task_claim_fresh_agent_proof_authorized"
    ] is FRESH_PROOF.exists()
