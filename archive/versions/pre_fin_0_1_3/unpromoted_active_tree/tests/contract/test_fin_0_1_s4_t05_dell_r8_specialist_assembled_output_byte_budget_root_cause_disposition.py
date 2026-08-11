from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2,
    SpecialistWWCJudgmentAtomPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentExecutor,
)
from test_fin_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_assembly_zero_call_implementation import (
    _claims_by_cell,
    _dell_input,
)


DECISION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_assembled_output_byte_budget_"
    "zero_call_root_cause_disposition_v1_0.json"
)
IMPLEMENTATION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_"
    "capacity_and_safe_byte_telemetry_minimum_zero_call_"
    "implementation_v1_0.json"
)
FRESH_PROOF = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_specialist_validated_segment_union_"
    "capacity_fresh_agent_proof_decision_v1_0.json"
)
R9_ISSUANCE = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r9_specialist_validated_segment_union_"
    "capacity_fresh_exact_admission_issuance_v1_0.json"
)
R8_RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r8_typed_failure_envelope_"
    "exact_live_execution_failure_result_v1_0.json"
)
LAYERED_STANDARD = ROOT / (
    "configs/releases/fin_ia_0_1_layered_agent_acceptance_standard_v1_0.json"
)
PROGRAM_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
DETAILED_BACKLOG = ROOT / (
    "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
CURRENT_WHOLE_CAP = 8192
SELECTED_WHOLE_CAP = 3 * 8192


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _maximum_cardinality_surfaces() -> list[dict[str, Any]]:
    input_pack = _dell_input()
    cells = {
        str(cell["program_cell_id"]): cell
        for cell in input_pack.cell_inputs
    }
    _, specialists = _claims_by_cell()
    measurements: list[dict[str, Any]] = []
    for cell_id, source in specialists.items():
        cell = cells[cell_id]
        specialist = deepcopy(source)
        evidence_ref = str(
            cell["authority_refs"]["accepted_evidence_refs"][0]
        )
        fact_template = deepcopy(specialist["fact_layer"][0])
        facts = []
        for ordinal in range(1, 4):
            fact = deepcopy(fact_template)
            fact.update(
                {
                    "fact_id": f"fact-{ordinal:03d}",
                    "support_type": "Evidence",
                    "support_refs": [evidence_ref],
                    "statement": "x" * 320,
                    "boundary": "x" * 320,
                }
            )
            facts.append(fact)
        claim_template = deepcopy(specialist["judgment_layer"][0])
        claims = []
        for ordinal in range(1, 3):
            claim = deepcopy(claim_template)
            claim.update(
                {
                    "claim_id": f"claim-{ordinal:03d}",
                    "statement": "x" * 320,
                    "support_fact_ids": [f"fact-{ordinal:03d}"],
                    "qualification": "x" * 320,
                }
            )
            claim["scope"].update(
                {
                    "entity_ref": "DELL",
                    "business_scope_kind": "unknown",
                    "business_scope_ref": "unknown",
                    "period": input_pack.as_of,
                    "metric_or_mechanism": "x" * 320,
                    "attribution_level": "none",
                }
            )
            claims.append(claim)
        specialist["fact_layer"] = facts
        specialist["explanation_layer"] = ["x" * 320] * 3
        specialist["remaining_gaps"] = ["x" * 320] * 4
        specialist["judgment_layer"] = claims

        policy = SpecialistWWCJudgmentAtomPolicy.from_cell_input(
            cell_input=cell,
            claims=claims,
            as_of=input_pack.as_of,
        )
        provider_WWC = policy.fake_provider_output(
            atom_count=3,
            narrative_characters=160,
        )
        tasks, violation = policy.assemble(
            provider_WWC,
            provider_output_utf8_bytes=_canonical_size(provider_WWC),
        )
        assert violation is None
        assert tasks is not None

        first = {
            key: deepcopy(specialist[key])
            for key in (
                "program_cell_id",
                "fact_layer",
                "explanation_layer",
                "remaining_gaps",
                "terminal_class",
            )
        }
        claim_segment = {
            "program_cell_id": cell_id,
            "judgment_layer": deepcopy(claims),
        }
        validated: dict[str, dict[str, Any]] = {}
        for segment_id, output in (
            ("facts_explanation_and_terminal", first),
            ("owner_grade_claim_cards", claim_segment),
            ("actionable_what_would_change_tasks", tasks),
        ):
            DeepSeekS3ThreeCellNodeExecutor._validate_specialist_segment(
                segment_id=segment_id,
                output=output,
                cell_input=cell,
                validated_segments=validated,
                transport_ref=(
                    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
                ),
                research_profile=S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2,
            )
            validated[segment_id] = output

        whole = {
            "program_cell_id": cell_id,
            "fact_layer": first["fact_layer"],
            "explanation_layer": first["explanation_layer"],
            "judgment_layer": claim_segment["judgment_layer"],
            "remaining_gaps": first["remaining_gaps"],
            "what_would_change": tasks["what_would_change"],
            "terminal_class": first["terminal_class"],
        }
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            whole,
            cell,
            output_contract_ref=(
                S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF
            ),
            max_serialized_utf8_bytes=100_000,
        )
        measurements.append(
            {
                "program_cell_id": cell_id,
                "facts_segment_utf8_bytes": _canonical_size(first),
                "claim_segment_utf8_bytes": _canonical_size(claim_segment),
                "WWC_provider_atom_utf8_bytes": _canonical_size(provider_WWC),
                "WWC_locally_expanded_segment_utf8_bytes": (
                    _canonical_size(tasks)
                ),
                "whole_canonical_specialist_utf8_bytes": (
                    _canonical_size(whole)
                ),
                "excess_over_current_whole_cap_utf8_bytes": (
                    _canonical_size(whole) - CURRENT_WHOLE_CAP
                ),
            }
        )
    return measurements


def test_decision_binds_immutable_R8_and_preserves_zero_call_scope() -> None:
    decision = _load(DECISION)
    source = decision["source_failure"]
    authority = decision["authority"]

    assert source["result_sha256"] == _sha256(R8_RESULT)
    assert source["provider_segment_calls_completed_ok_stop"] == 9
    assert source["exact_R8_assembled_utf8_byte_count_persisted"] is False
    assert source["restricted_R8_text_read_in_this_decision"] is False
    assert source["model_noncompliance_established"] is False
    assert source["historical_terminal_states"] == ["failed"] * 3
    assert source["historical_artifact_count"] == 0
    assert authority["zero_call_root_cause_disposition_authorized"] is True
    assert authority["restricted_provider_output_or_capture_read_authorized"] is False
    assert authority["new_admission_R9_execution_or_paired_assessment_authorized"] is False
    assert all(value == 0 for value in decision["observed_counts"].values())


def test_current_profile_conflates_local_segment_and_whole_union_capacity() -> None:
    decision = _load(DECISION)
    audit = decision["zero_call_code_audit"]

    assert S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2.specialist_segment_max_utf8_bytes == 6000
    assert S4_DELL_THREE_CELL_RESEARCH_PROFILE_V2.specialist_assembly_max_utf8_bytes == 8192
    assert audit["post_local_expansion_segment_max_utf8_bytes"] == 8192
    assert audit["whole_specialist_output_max_utf8_bytes"] == 8192
    assert audit["current_profile_post_init_proves_three_segment_union_closure"] is False
    assert audit["existing_full_fake_chain_WWC_narrative_characters"] == 32
    assert audit["existing_full_fake_chain_proves_contract_maximum_whole_output_closure"] is False


def test_public_maximum_cardinality_fixture_proves_non_closing_union() -> None:
    decision = _load(DECISION)
    expected = decision["deterministic_capacity_audit"][
        "per_cell_measurements"
    ]
    observed = _maximum_cardinality_surfaces()

    assert observed == expected
    assert all(
        max(
            row["facts_segment_utf8_bytes"],
            row["claim_segment_utf8_bytes"],
            row["WWC_provider_atom_utf8_bytes"],
        )
        <= 6000
        for row in observed
    )
    assert all(
        row["WWC_locally_expanded_segment_utf8_bytes"] <= 8192
        for row in observed
    )
    assert all(
        row["whole_canonical_specialist_utf8_bytes"] > CURRENT_WHOLE_CAP
        for row in observed
    )


def test_selected_contract_separates_three_capacity_levels_and_remains_hard() -> None:
    decision = _load(DECISION)
    selected = decision["selected_minimum_implementation_contract"]
    capacity = selected["three_level_capacity"]
    layered = decision["layered_acceptance_disposition"]

    assert selected["contract_ref"] == (
        "fin01.s3.specialist_local_assembly_capacity."
        "validated_segment_union_upper_bound:v1"
    )
    assert selected["versioning"]["new_DELL_research_profile_ref"].endswith(
        ":v3"
    )
    assert selected["versioning"]["new_specialist_transport_v9_required"] is False
    assert capacity["provider_raw_segment_limit_utf8_bytes"] == 6000
    assert capacity["post_local_expansion_segment_limit_utf8_bytes"] == 8192
    assert capacity["validated_segment_count"] == 3
    assert capacity["whole_union_limit_utf8_bytes"] == SELECTED_WHOLE_CAP
    assert capacity["provider_output_token_caps_changed"] is False
    assert capacity["aggregate_output_token_or_cost_cap_changed"] is False
    assert layered["acceptance_standard_sha256"] == _sha256(
        LAYERED_STANDARD
    )
    assert layered["classification"] == (
        "L1_hard_capacity_contract_remains_fail_closed"
    )


def test_decision_rejects_field_patch_and_stays_inside_T05() -> None:
    decision = _load(DECISION)
    rejected = {
        row["option"]: row["decision"]
        for row in decision["rejected_and_deferred_alternatives"]
    }
    sequence = decision["sequence_boundary"]
    stage = decision["stage_acceptance"]

    assert rejected["raise_8192_to_the_next_number_observed_in_R8"] == "rejected"
    assert rejected[
        "truncate_compress_drop_or_rewrite_valid_Facts_Claims_or_WWC_tasks"
    ] == "rejected"
    assert rejected[
        "downgrade_whole_output_capacity_to_quality_finding"
    ] == "rejected"
    assert rejected[
        "atomize_Facts_Claims_dependency_conflict_Writer_and_Verifier_in_T05"
    ] == "deferred_to_S4_T10_to_S5"
    assert sequence["implementation_in_this_decision"] is False
    assert stage["DELL_R2"] == "not_proven"
    assert stage["S4_T06"] == "not_entered"
    assert decision["next_action"] == (
        "S4-T05-DELL-R8-SPECIALIST-VALIDATED-SEGMENT-UNION-CAPACITY-"
        "AND-SAFE-BYTE-TELEMETRY-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )


def test_backlogs_route_only_to_the_separately_authorized_implementation() -> None:
    decision = _load(DECISION)
    program = _load(PROGRAM_BACKLOG)
    detailed = _load(DETAILED_BACKLOG)
    task = next(
        item for item in detailed["tasks"] if item["item_id"] == "S4-T05"
    )

    current_next = program["next_action"]["item_id"]
    assert detailed["current_next_action"] == current_next
    assert task["RC_P36_065_disposition_sha256"] == _sha256(DECISION)
    assert (
        program["next_action"]["S4_T05_RC_P36_065_disposition_sha256"]
        == _sha256(DECISION)
    )
    assert task["selected_whole_union_limit_utf8_bytes"] == 24576
    assert (
        program["next_action"][
            "S4_T05_selected_whole_union_limit_utf8_bytes"
        ]
        == 24576
    )
    assert task["restricted_R8_text_read_for_disposition"] is False
    if IMPLEMENTATION.exists():
        assert task["RC_P36_065_implementation_sha256"] == _sha256(
            IMPLEMENTATION
        )
        assert (
            program["next_action"][
                "S4_T05_RC_P36_065_implementation_sha256"
            ]
            == _sha256(IMPLEMENTATION)
        )
