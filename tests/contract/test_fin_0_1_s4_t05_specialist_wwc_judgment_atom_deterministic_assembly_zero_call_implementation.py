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
R8_CAPACITY_DISPOSITION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_assembled_output_byte_budget_"
    "zero_call_root_cause_disposition_v1_0.json"
)
R8_CAPACITY_IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_"
    "capacity_and_safe_byte_telemetry_minimum_zero_call_"
    "implementation_v1_0.json"
)
R8_CAPACITY_FRESH_PROOF = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_"
    "capacity_fresh_agent_proof_decision_v1_0.json"
)
R9_CAPACITY_ISSUANCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_"
    "capacity_fresh_exact_admission_issuance_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2,
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    SpecialistWWCJudgmentAtomPolicy,
    research_profile_for_ref,
    specialist_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    build_s4_source_grounded_bounded_agent_input,
)
from sec_agent.s4_case_runtime import (
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_claim_fact_link_policy_zero_call_implementation import (
    _emit_claim_fact_aliases,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_zero_call_implementation import (
    _GapAtomV6FullFakeProvider,
)


R5_ADMISSION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_research_lead_gap_atom_projection_"
    "fresh_exact_admission_r5.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)
CURRENT_PROOF = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r6_research_profile_v2_case_runtime_binding_"
    "mismatch_zero_call_root_cause_disposition_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)


def _dell_input():
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "DELL")
    built = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        case_id="case-s4-t05-dell-v8-WWC-atom-fixture",
        case_version=1,
        decision_surface_contract_ref="surface-s4-t05-dell-v8-WWC:v1",
        query="Exercise the zero-call DELL Specialist v8 WWC atom path.",
    )
    legacy_lineage = {
        key: {
            "version_ref": f"fixture:{key}:v1",
            "digest": canonical_digest({"fixture_lineage_key": key}),
        }
        for key in (
            "T02_runtime_plan",
            "T03_evidence_route_plan",
            "T04_financial_pack",
            "T05_graph_pack",
            "T06_judgment_contract",
            "T07_presentation_contract",
        )
    }
    return built.model_copy(
        update={
            "s4_case_runtime": None,
            "lineage": legacy_lineage,
        }
    )


def _claims_by_cell() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    cells, specialists = _shared_local_id_specialists()
    return {str(row["program_cell_id"]): row for row in cells}, specialists


def _policy_by_cell(input_pack, specialists):
    cells = {
        str(row["program_cell_id"]): row
        for row in input_pack.cell_inputs
    }
    return {
        cell_id: SpecialistWWCJudgmentAtomPolicy.from_cell_input(
            cell_input=cells[cell_id],
            claims=specialist["judgment_layer"],
            as_of=input_pack.as_of,
        )
        for cell_id, specialist in specialists.items()
    }


def _v8_admission(input_pack) -> S3ThreeCellBoundedAgentAdmission:
    base = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(R5_ADMISSION.read_text(encoding="utf-8"))
    )
    return base.model_copy(
        update={
            "admission_id": "fixture-s4-t05-dell-v8-WWC-atom",
            "execution_mode": "zero_call_fake_provider_s4_dell_v8_WWC_atom",
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "as_of": input_pack.as_of,
            "input_digest": input_pack.input_digest,
            "transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
            ),
            "research_profile_ref": (
                S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
            ),
            "wwc_judgment_atom_policy_ref": (
                S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
            ),
            "specialist_max_output_tokens": 4600,
        }
    )


def test_v8_registry_and_dell_v2_capacity_are_versioned() -> None:
    v7 = specialist_transport_contract(
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    v8 = specialist_transport_contract(
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
    )
    assert v7.what_would_change_judgment_atom_assembly is False
    assert v8.what_would_change_judgment_atom_assembly is True
    assert v8.field_local_what_would_change_authority is True
    profile = research_profile_for_ref(
        S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2_REF
    )
    assert profile == S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2
    assert profile.segment_token_budgets[
        "actionable_what_would_change_tasks"
    ] == 1800
    assert profile.stage_token_budgets(expanded_lead=True)[
        "specialist"
    ] == 4600
    assert profile.aggregate_output_tokens(expanded_lead=True) == 18000


def test_v8_admission_requires_atom_policy_and_capacity_binding() -> None:
    input_pack = _dell_input()
    admission = _v8_admission(input_pack)
    admission.assert_profile_admissible()
    with pytest.raises(
        ValueError,
        match="v8_WWC_judgment_atom_policy_required",
    ):
        admission.model_copy(
            update={"wwc_judgment_atom_policy_ref": None}
        ).assert_profile_admissible()
    with pytest.raises(
        ValueError,
        match="WWC_judgment_atom_capability_binding_required",
    ):
        admission.model_copy(
            update={
                "research_profile_ref": (
                    "fin01.s4.research_profile.dell_oem_three_cell:v1"
                ),
                "specialist_max_output_tokens": 4200,
            }
        ).assert_profile_admissible()


def test_contract_owned_max_shape_fits_and_assembles_canonical_tasks() -> None:
    input_pack = _dell_input()
    _, specialists = _claims_by_cell()
    policies = _policy_by_cell(input_pack, specialists)
    for policy in policies.values():
        provider_output = policy.fake_provider_output(
            atom_count=3,
            narrative_characters=160,
        )
        serialized = json.dumps(
            provider_output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        assert len(serialized) <= 4800
        assembled, violation = policy.assemble(
            provider_output,
            provider_output_utf8_bytes=len(serialized),
        )
        assert violation is None
        assert assembled is not None
        assert len(assembled["what_would_change"]) == 3
        for ordinal, task in enumerate(
            assembled["what_would_change"], 1
        ):
            assert task["task_id"].endswith(f":{ordinal:03d}")
            assert task["time_window"]["as_of"] == input_pack.as_of
            assert set(task) == {
                "task_id",
                "claim_id",
                "source_target",
                "metric_or_observation",
                "decision_rule",
                "time_window",
                "expected_claim_transition",
                "fallback_stop_condition",
                "authority_refs",
            }
        serialized_canonical = json.dumps(
            assembled, ensure_ascii=False
        )
        assert '"Q001"' not in serialized_canonical
        assert '"A001"' not in serialized_canonical


@pytest.mark.parametrize(
    ("mutation", "subtype"),
    (
        (
            lambda atom: atom.update({"claim_alias": "A001"}),
            "claim_alias_wrong_kind",
        ),
        (
            lambda atom: atom.update(
                {"primary_authority_alias": "Q001"}
            ),
            "authority_alias_wrong_kind",
        ),
        (
            lambda atom: atom.update(
                {"metric_or_observation": "x" * 161}
            ),
            "atom_narrative_invalid",
        ),
        (
            lambda atom: atom.update({"rule_type": "free_text_rule"}),
            "rule_type_unknown",
        ),
    ),
)
def test_atom_contract_fails_closed_without_raw_content(
    mutation,
    subtype: str,
) -> None:
    input_pack = _dell_input()
    _, specialists = _claims_by_cell()
    policy = next(iter(_policy_by_cell(input_pack, specialists).values()))
    output = policy.fake_provider_output(atom_count=1)
    mutation(output["what_would_change_judgment_atoms"][0])
    serialized = json.dumps(output, ensure_ascii=False).encode("utf-8")
    assembled, violation = policy.assemble(
        output,
        provider_output_utf8_bytes=len(serialized),
    )
    assert assembled is None
    assert violation is not None
    assert violation.subtype == subtype


def test_v8_request_exposes_only_atom_schema_and_closed_alias_contract() -> None:
    input_pack = _dell_input()
    _, specialists = _claims_by_cell()
    admission = _v8_admission(input_pack)
    first_cell = input_pack.cell_inputs[0]
    cell_id = str(first_cell["program_cell_id"])
    specialist = specialists[cell_id]
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
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell_id}",
        segment_id="actionable_what_would_change_tasks",
        payload={
            "input_contract_ref": input_pack.input_contract_ref,
            "input_digest": input_pack.input_digest,
            "cell_input": first_cell,
            "required_output_layers": ["what_would_change"],
        },
        validated_segments=validated,
        transport_ref=admission.transport_ref,
        research_profile=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2,
        task_claim_link_policy_ref=S3_TASK_CLAIM_LINK_POLICY_REF,
        wwc_judgment_atom_policy_ref=(
            S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
        ),
        as_of=input_pack.as_of,
    )
    assert set(request["required_output_schema"]) == {
        "program_cell_id",
        "what_would_change_judgment_atoms",
    }
    atom = request["required_output_schema"][
        "what_would_change_judgment_atoms"
    ][0]
    assert "task_id" not in atom
    assert "source_target" not in atom
    assert "decision_rule" not in atom
    assert "time_window" not in atom
    assert "authority_refs" not in atom
    assert "WWC_judgment_atom_contract" in request
    assert "task_claim_link_contract" not in request
    assert "what_would_change_authority_contract" not in request
    assert "authority_refs" not in request["analysis_input"]["cell_input"]
    assert request["output_constraints"] == {
        "what_would_change_judgment_atom_cardinality": "1..3",
        "maximum_narrative_item_unicode_characters": 160,
        "maximum_serialized_utf8_bytes": 4800,
    }


def test_full_fake_provider_reaches_twelve_callbacks_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack = _dell_input()
    _, specialists = _claims_by_cell()
    policies = _policy_by_cell(input_pack, specialists)
    admission = _v8_admission(input_pack)

    def mutation(
        request: dict[str, Any],
        output: dict[str, Any],
    ) -> dict[str, Any]:
        output = _emit_claim_fact_aliases(request, output)
        segment_id = request.get("segment_id")
        if segment_id == "facts_explanation_and_terminal":
            allowed = request["fact_support_authority_contract"][
                "allowed_refs_by_support_type"
            ]["Evidence"]
            for fact in output["fact_layer"]:
                fact["support_type"] = "Evidence"
                fact["support_refs"] = [allowed[0]]
        elif segment_id == "actionable_what_would_change_tasks":
            cell_id = str(request["node_id"]).split(":", 1)[1]
            return policies[cell_id].fake_provider_output(
                atom_count=3,
                narrative_characters=32,
            )
        return output

    fake = _GapAtomV6FullFakeProvider(
        specialists,
        mutation=mutation,
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
            "research_run_id": "fixture-s4-t05-dell-v8-WWC-atoms",
            "attempt_id": "fixture-s4-t05-dell-v8-WWC-atoms",
        },
    )
    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    artifact_text = json.dumps(
        [row.model_dump(mode="json") for row in result.artifacts],
        ensure_ascii=False,
    )
    assert "what_would_change_judgment_atoms" not in artifact_text
    assert '"Q001"' not in artifact_text
    assert '"A001"' not in artifact_text


def test_unknown_atom_alias_stops_at_specialist_with_typed_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack = _dell_input()
    _, specialists = _claims_by_cell()
    policies = _policy_by_cell(input_pack, specialists)
    admission = _v8_admission(input_pack)

    def mutation(request, output):
        output = _emit_claim_fact_aliases(request, output)
        segment_id = request.get("segment_id")
        if segment_id == "facts_explanation_and_terminal":
            allowed = request["fact_support_authority_contract"][
                "allowed_refs_by_support_type"
            ]["Evidence"]
            for fact in output["fact_layer"]:
                fact["support_type"] = "Evidence"
                fact["support_refs"] = [allowed[0]]
        elif segment_id == "actionable_what_would_change_tasks":
            cell_id = str(request["node_id"]).split(":", 1)[1]
            atom_output = policies[cell_id].fake_provider_output(atom_count=1)
            atom_output["what_would_change_judgment_atoms"][0][
                "primary_authority_alias"
            ] = "Q001"
            return atom_output
        return output

    fake = _GapAtomV6FullFakeProvider(
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
                "research_run_id": "fixture-s4-t05-v8-WWC-typed-stop",
                "attempt_id": "fixture-s4-t05-v8-WWC-typed-stop",
            },
        )
    telemetry = captured.value.failure_observation["failure_telemetry"][
        "segmented_specialist_WWC_judgment_atom"
    ]
    assert telemetry["validator_contract"] == (
        S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF
    )
    assert telemetry["failure_subtype"] == "authority_alias_wrong_kind"
    assert telemetry["raw_atom_persisted"] is False
    assert "Q001" not in json.dumps(telemetry, ensure_ascii=False)


def test_implementation_record_binds_code_zero_calls_and_next_gate() -> None:
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
    expected_next = (
        "S4-T05-DELL-SPECIALIST-WWC-JUDGMENT-ATOM-AND-"
        "DETERMINISTIC-TASK-ASSEMBLY-FRESH-AGENT-PROOF-DECISION"
    )
    assert implementation["next_action"] == expected_next
    current_next = json.loads(
        (
            R9_CAPACITY_ISSUANCE
            if R9_CAPACITY_ISSUANCE.exists()
            else R8_CAPACITY_FRESH_PROOF
            if R8_CAPACITY_FRESH_PROOF.exists()
            else R8_CAPACITY_IMPLEMENTATION
            if R8_CAPACITY_IMPLEMENTATION.exists()
            else R8_CAPACITY_DISPOSITION
            if R8_CAPACITY_DISPOSITION.exists()
            else ROOT
            / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
            if R7_BINDING_IMPLEMENTATION.exists()
            else CURRENT_PROOF
        ).read_text(encoding="utf-8")
    )["next_action"]
    active_next = program["next_action"]["item_id"]
    assert detailed["current_next_action"] == active_next
    if active_next != current_next:
        assert active_next.startswith(("S4-T05-DELL-", "S4-T06-MU-"))
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            r7_failure = (
                ROOT
                / "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_binding_exact_live_execution_failure_result_v1_0.json"
            )
            if r7_failure.exists():
                assert json.loads(r7_failure.read_text(encoding="utf-8"))[
                    "status"
                ].startswith("terminal_failed_post_verifier")
            else:
                latest = json.loads(
                    R7_BINDING_IMPLEMENTATION.read_text(encoding="utf-8")
                )
                supersession = latest["historical_exact_binding_supersession"]
                assert relative_path in supersession["allowed_changed_paths"]
                assert latest["exact_code_bindings"][
                    relative_path
                ] == current_sha256
