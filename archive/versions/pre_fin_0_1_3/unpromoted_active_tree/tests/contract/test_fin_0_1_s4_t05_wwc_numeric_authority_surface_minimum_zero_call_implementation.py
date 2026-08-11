from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

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
    CellAuthoritySurface,
    FactSupportAuthorityPolicy,
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
    WhatWouldChangeAuthorityPolicy,
    specialist_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s4_t05_dell_task_claim_link_policy_r3_exact_live_execution_failure_result import (
    _capture_path,
)
from test_fin_0_1_s4_t05_task_claim_link_policy_minimum_zero_call_implementation import (
    _CompactV5FullFakeProvider,
    _input_pack,
    _policy_admission,
    _shared_local_id_specialists,
    _task_alias_mutation,
)


R3_FAILURE_RESULT = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_task_claim_link_policy_r3_"
    "exact_live_execution_failure_result_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_minimum_"
    "zero_call_implementation_v1_0.json"
)
LATEST_RUNTIME_IMPLEMENTATION = (
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
PROOF = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_agent_"
    "proof_decision_v1_0.json"
)
ISSUANCE = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_wwc_numeric_authority_surface_fresh_exact_"
    "admission_issuance_v1_0.json"
)
AUTHORITY = (
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
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _synthetic_cell() -> dict[str, Any]:
    return {
        "program_cell_id": "cell-a",
        "authority_refs": {
            "accepted_evidence_refs": ["evidence:a"],
            "numeric_refs": ["numeric:a"],
            "candidate_refs_not_evidence": ["candidate:a"],
            "graph_context_refs_not_evidence": ["graph:a"],
        },
        "numeric_input": {
            "selected_rows": [
                {
                    "routing_ref": "numeric:legacy-only",
                    "scope": {"entity_ref": "DELL"},
                }
            ]
        },
    }


def _task(authority_refs: Any) -> dict[str, Any]:
    return {"authority_refs": authority_refs}


def test_shared_cell_projection_is_the_only_fact_and_WWC_membership_source() -> None:
    cell = _synthetic_cell()
    surface = CellAuthoritySurface.from_cell_input(cell)
    fact = FactSupportAuthorityPolicy.from_cell_input(cell)
    wwc = WhatWouldChangeAuthorityPolicy.from_cell_input(cell)

    assert surface.numeric_refs == ("numeric:a",)
    assert (
        fact.evidence_refs,
        fact.numeric_refs,
        fact.candidate_refs,
        fact.graph_context_refs,
    ) == (
        wwc.evidence_refs,
        wwc.numeric_refs,
        wwc.candidate_refs,
        wwc.graph_context_refs,
    )
    assert set(wwc.allowed_refs) == {
        "evidence:a",
        "numeric:a",
        "candidate:a",
        "graph:a",
    }
    assert "numeric:legacy-only" not in wwc.allowed_refs


def test_v7_request_and_validator_share_the_exact_WWC_contract_while_v6_does_not() -> None:
    cells, specialists = _shared_local_id_specialists()
    cell = cells[0]
    cell_id = str(cell["program_cell_id"])
    specialist = specialists[cell_id]
    payload = {
        "input_contract_ref": "fixture-input:v1",
        "input_digest": "fixture-digest",
        "cell_input": cell,
        "required_output_layers": [],
    }
    validated = {
        "facts_explanation_and_terminal": {
            key: deepcopy(specialist[key])
            for key in (
                "program_cell_id",
                "fact_layer",
                "explanation_layer",
                "remaining_gaps",
                "terminal_class",
            )
        },
        "owner_grade_claim_cards": {
            "program_cell_id": cell_id,
            "judgment_layer": deepcopy(specialist["judgment_layer"]),
        },
    }

    v7_system, v7_request, _ = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id=f"domain_specialist:{cell_id}",
            segment_id="actionable_what_would_change_tasks",
            payload=payload,
            validated_segments=validated,
            transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        )
    )
    _, v6_request, _ = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id=f"domain_specialist:{cell_id}",
            segment_id="actionable_what_would_change_tasks",
            payload=payload,
            validated_segments=validated,
            transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
        )
    )

    expected = WhatWouldChangeAuthorityPolicy.from_cell_input(
        cell
    ).prompt_contract()
    assert v7_request["what_would_change_authority_contract"] == expected
    assert expected["contract_ref"] == (
        S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF
    )
    assert "what_would_change_authority_contract" in v7_system
    assert (
        "what_would_change_authority_contract"
        not in v6_request
    )
    assert (
        specialist_transport_contract(
            S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF
        ).field_local_what_would_change_authority
        is False
    )


@pytest.mark.parametrize(
    "refs",
    (
        ["evidence:a"],
        ["numeric:a"],
        ["candidate:a"],
        ["graph:a"],
        ["evidence:a", "numeric:a", "candidate:a", "graph:a"],
    ),
)
def test_WWC_authority_accepts_each_declared_class_and_cross_class_subsets(
    refs: list[str],
) -> None:
    policy = WhatWouldChangeAuthorityPolicy.from_cell_input(
        _synthetic_cell()
    )
    assert policy.first_violation([_task(refs)]) is None


@pytest.mark.parametrize(
    ("refs", "subtype"),
    (
        (None, "authority_refs_not_nonempty_string_array"),
        ([], "authority_refs_not_nonempty_string_array"),
        ([""], "authority_refs_not_nonempty_string_array"),
        ([1], "authority_refs_not_nonempty_string_array"),
        (
            ["unknown:a"],
            "authority_ref_outside_current_cell_closed_surface",
        ),
        (
            [" numeric:a"],
            "authority_ref_outside_current_cell_closed_surface",
        ),
        (
            ["numeric:cross-cell"],
            "authority_ref_outside_current_cell_closed_surface",
        ),
        (
            ["numeric:legacy-only"],
            "authority_ref_outside_current_cell_closed_surface",
        ),
    ),
)
def test_WWC_authority_rejects_invalid_unknown_normalized_cross_cell_and_legacy_refs(
    refs: Any,
    subtype: str,
) -> None:
    violation = WhatWouldChangeAuthorityPolicy.from_cell_input(
        _synthetic_cell()
    ).first_violation([_task(refs)])
    assert violation is not None
    assert violation.subtype == subtype
    assert violation.failing_item_count == 1


def test_r3_DELL_capture_replays_through_the_canonical_numeric_surface() -> None:
    result = _load(R3_FAILURE_RESULT)
    evidence = result["runtime_evidence"]
    facts = json.loads(
        _load(
            _capture_path(evidence["facts_capture_object_digest"])
        )["assistant_output_text"]
    )
    claims = json.loads(
        _load(
            _capture_path(evidence["claim_capture_object_digest"])
        )["assistant_output_text"]
    )
    tasks = json.loads(
        _load(
            _capture_path(evidence["WWC_capture_object_digest"])
        )["assistant_output_text"]
    )
    input_head = _load(
        ROOT / result["authority_surface_replay"]["exact_input_object_ref"]
    )
    cell = next(
        row
        for row in input_head["input_pack"]["cell_inputs"]
        if row["program_cell_id"] == "demand_authenticity_and_sustainability"
    )
    expanded_claims = (
        DeepSeekS3ThreeCellNodeExecutor._expand_specialist_claim_fact_links(
            output=claims,
            cell_input=cell,
            validated_segments={
                "facts_explanation_and_terminal": facts,
            },
            policy_ref=S3_CLAIM_FACT_LINK_POLICY_REF,
        )
    )
    assembled_claims = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_specialist_claim_scopes_v6(
            output=expanded_claims,
            cell_input=cell,
            validated_segments={
                "facts_explanation_and_terminal": facts,
            },
        )
    )
    expanded_tasks = (
        DeepSeekS3ThreeCellNodeExecutor._expand_specialist_task_claim_links(
            output=tasks,
            cell_input=cell,
            validated_segments={
                "owner_grade_claim_cards": assembled_claims,
            },
            policy_ref=S3_TASK_CLAIM_LINK_POLICY_REF,
        )
    )
    claim_input = {
        "fact_layer": facts["fact_layer"],
        "judgment_layer": assembled_claims["judgment_layer"],
    }
    claim_by_id = (
        S3ThreeCellBoundedAgentExecutor._validate_owner_grade_claims(
            claim_input,
            cell,
        )
    )
    policy = WhatWouldChangeAuthorityPolicy.from_cell_input(cell)

    assert len(policy.numeric_refs) == 6
    assert policy.first_violation(
        expanded_tasks["what_would_change"]
    ) is None
    S3ThreeCellBoundedAgentExecutor._validate_owner_grade_tasks(
        expanded_tasks["what_would_change"],
        cell,
        claim_by_id,
    )


def test_full_fake_provider_proves_request_contract_and_nine_artifacts(
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
            "research_run_id": "fixture-run-WWC-authority-positive",
            "attempt_id": "fixture-attempt-WWC-authority-positive",
        },
    )
    task_requests = [
        row["request"]
        for row in fake.calls
        if row["request"].get("segment_id")
        == "actionable_what_would_change_tasks"
    ]

    assert len(fake.calls) == 12
    assert len(result.artifacts) == 9
    assert len(task_requests) == 3
    assert all(
        request["what_would_change_authority_contract"][
            "contract_ref"
        ]
        == S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF
        for request in task_requests
    )


def test_outside_ref_stops_at_WWC_with_content_free_typed_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _policy_admission(input_pack)
    alias_mutation = _task_alias_mutation(specialists)

    def mutation(
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        output = alias_mutation(request, output)
        if (
            request.get("segment_id")
            == "actionable_what_would_change_tasks"
        ):
            output["what_would_change"][0]["authority_refs"] = [
                "sensitive-outside-ref"
            ]
        return output

    fake = _CompactV5FullFakeProvider(
        specialists,
        mutation=mutation,
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
                "research_run_id": "fixture-run-WWC-authority-stop",
                "attempt_id": "fixture-attempt-WWC-authority-stop",
            },
        )

    observation = captured.value.failure_observation
    telemetry = observation["failure_telemetry"][
        "segmented_specialist_what_would_change_authority"
    ]
    assert len(fake.calls) == 3
    assert telemetry == {
        "validator_contract": S3_WHAT_WOULD_CHANGE_AUTHORITY_POLICY_REF,
        "segment_id": "actionable_what_would_change_tasks",
        "field_id": "what_would_change.authority_refs",
        "authority_subtype": (
            "authority_ref_outside_current_cell_closed_surface"
        ),
        "failing_item_count": 1,
        "raw_ref_persisted": False,
        "ref_digest_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }
    assert "sensitive-outside-ref" not in json.dumps(
        observation,
        ensure_ascii=False,
    )


def test_implementation_record_binds_current_code_and_next_separate_gate() -> None:
    implementation = _load(IMPLEMENTATION)
    latest = _load(R7_BINDING_IMPLEMENTATION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)

    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["fixture_proof"]["R3_DELL_numeric_ref_count"] == 6
    assert implementation["fixture_proof"][
        "full_fake_provider_callbacks"
    ] == 12
    assert implementation["fixture_proof"][
        "full_fake_provider_logical_artifacts"
    ] == 9
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
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            assert relative_path in latest[
                "historical_exact_binding_supersession"
            ]["allowed_changed_paths"]
            assert latest["exact_code_bindings"][
                relative_path
            ] == current_sha256
    assert implementation["next_action"] == (
        "S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    current_next = _load(
        ROOT / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
        if R7_BINDING_IMPLEMENTATION.exists()
        else CURRENT_PROOF
    )["next_action"]
    assert program["next_action"]["item_id"] == current_next
    assert detailed["current_next_action"] == current_next
