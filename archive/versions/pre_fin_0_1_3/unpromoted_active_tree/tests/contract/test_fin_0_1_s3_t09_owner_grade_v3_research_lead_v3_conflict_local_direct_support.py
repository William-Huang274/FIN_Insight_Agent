from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ResearchLeadContractError,
    S3ResearchLeadV3ContractError,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_research_lead_v2_closed_output import (
    _provider_lead_segment,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_specialist_transport import (
    _SegmentedOwnerGradeFakeProvider,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
)


def _admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-research-lead-v3",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_research_lead_v3",
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1800,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


def _surfaces() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _, specialists_by_cell = _production_surfaces()
    specialists = deepcopy(list(specialists_by_cell.values()))
    return specialists, _provider_lead_segment(specialists)


def _set_direct_support(
    specialists: list[dict[str, Any]], support_by_claim: list[bool]
) -> None:
    claims = [
        claim
        for specialist in specialists
        for claim in specialist["judgment_layer"]
    ]
    assert len(claims) == len(support_by_claim)
    for index, (claim, supported) in enumerate(
        zip(claims, support_by_claim, strict=True), start=1
    ):
        claim["support_fact_ids"] = [f"fact:{index}"] if supported else []


def _validate_canonical(
    output: Mapping[str, Any], specialists: list[Mapping[str, Any]]
) -> None:
    digests = {
        str(specialist["program_cell_id"]): canonical_digest(specialist)
        for specialist in specialists
    }
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists, digests
    )
    S3ThreeCellBoundedAgentExecutor._validate_lead_output(
        {"cell_heads": heads, **output},
        digests,
        specialist_outputs=specialists,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    )


def _run_v3(monkeypatch: pytest.MonkeyPatch, mutation=None):
    cells, specialists_by_cell = _production_surfaces()
    specialists = deepcopy(specialists_by_cell)
    input_pack = _input_pack(cells)
    admission = _admission(input_pack)

    def remove_heads(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if request.get("node_id") == "research_lead":
            output.pop("cell_heads")
        if mutation is not None:
            return mutation(request, output)
        return output

    fake = _SegmentedOwnerGradeFakeProvider(
        specialists,
        mutation=remove_heads,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    )
    result = executor.execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-run-research-lead-v3",
            "attempt_id": "fixture-attempt-research-lead-v3",
        },
    )
    return result, fake


@pytest.mark.parametrize(
    ("support", "involved", "expected"),
    [
        ([True, True, True], ["claim:1", "claim:2", "claim:3"], "facts_present"),
        (
            [False, False, False],
            ["claim:1", "claim:2", "claim:3"],
            "no_facts_present",
        ),
        (
            [True, False, False],
            ["claim:1", "claim:2", "claim:3"],
            "mixed_fact_presence",
        ),
        ([True, False, False], ["claim:1"], "facts_present"),
        ([False, True, True], ["claim:1"], "no_facts_present"),
    ],
)
def test_research_lead_v3_direct_support_truth_table(
    support: list[bool], involved: list[str], expected: str
) -> None:
    specialists, output = _surfaces()
    _set_direct_support(specialists, support)
    conflict = output["conflict_adjudications"][0]
    conflict["involved_claim_ids"] = involved
    conflict["fact_presence_summary"] = expected
    DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v3_segment(
        output, specialists
    )
    _validate_canonical(output, specialists)


def test_unrelated_global_and_same_cell_facts_do_not_change_summary() -> None:
    specialists, output = _surfaces()
    _set_direct_support(specialists, [False, True, True])
    first_claim = specialists[0]["judgment_layer"][0]
    specialists[0]["fact_layer"].append(
        {
            **deepcopy(specialists[0]["fact_layer"][0]),
            "fact_id": "fact:unrelated_same_cell",
        }
    )
    first_claim["support_fact_ids"] = []
    conflict = output["conflict_adjudications"][0]
    conflict["involved_claim_ids"] = ["claim:1"]
    conflict["fact_presence_summary"] = "no_facts_present"
    DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v3_segment(
        output, specialists
    )
    _validate_canonical(output, specialists)


@pytest.mark.parametrize(
    ("mutation", "family", "subtype"),
    [
        (
            lambda conflict: conflict.update(
                {"involved_claim_ids": ["claim:1", "claim:1"]}
            ),
            "semantic",
            "involved_claim_ref_duplicate",
        ),
        (
            lambda conflict: conflict.update(
                {"involved_claim_ids": ["claim:unknown"]}
            ),
            "authority",
            "claim_ref_invalid",
        ),
        (
            lambda conflict: conflict.update(
                {"fact_presence_summary": "globally_some_facts"}
            ),
            "semantic",
            "fact_presence_summary_invalid",
        ),
        (
            lambda conflict: conflict.update(
                {"fact_presence_summary": "no_facts_present"}
            ),
            "semantic",
            "fact_presence_summary_mismatch",
        ),
        (
            lambda conflict: conflict.update(
                {
                    "terminal_state_summary": (
                        "All cells are in non-fact states despite the record."
                    )
                }
            ),
            "semantic",
            "explicit_global_fact_presence_statement_conflict",
        ),
    ],
)
def test_research_lead_v3_fails_closed_with_content_free_telemetry(
    mutation, family: str, subtype: str
) -> None:
    specialists, output = _surfaces()
    mutation(output["conflict_adjudications"][0])
    with pytest.raises(S3ResearchLeadV3ContractError) as captured:
        DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v3_segment(
            output, specialists
        )
    telemetry = captured.value.telemetry
    assert telemetry["validator_contract"] == "closed_research_lead_output:v3"
    assert telemetry["failure_family"] == family
    assert telemetry["failure_subtype"] == subtype
    assert all(
        telemetry[key] is False
        for key in (
            "raw_text_persisted",
            "ref_or_digest_persisted",
            "item_index_persisted",
            "arbitrary_key_names_persisted",
            "private_reasoning_persisted",
        )
    )


def test_restricted_live_replay_has_exactly_one_direct_support_mismatch() -> None:
    decision = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v2_conflict_fact_presence_scope_root_cause_decision_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    replay = decision["restricted_live_replay"]
    expected = []
    for counts in replay["involved_claim_direct_support_fact_counts"]:
        support = [count > 0 for count in counts]
        expected.append(
            "facts_present"
            if all(support)
            else "mixed_fact_presence"
            if any(support)
            else "no_facts_present"
        )
    mismatches = [
        observed != derived
        for observed, derived in zip(
            replay["observed_conflict_fact_presence_summaries"],
            expected,
            strict=True,
        )
    ]
    assert expected == replay["selected_scope_expected_summaries"]
    assert mismatches == replay["selected_scope_mismatch_flags"]
    assert sum(mismatches) == 1


def test_research_lead_v3_request_exposes_exact_local_truth_table() -> None:
    specialists, _ = _surfaces()
    digests = {
        str(specialist["program_cell_id"]): canonical_digest(specialist)
        for specialist in specialists
    }
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists, digests
    )
    _, request, binding = DeepSeekS3ThreeCellNodeExecutor._research_lead_v3_request(
        {"specialist_outputs": specialists}, heads
    )
    constraints = request["output_constraints"]
    assert request["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
    )
    assert binding["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF
    )
    assert constraints["conflict_fact_presence_truth_table"] == {
        "all_involved_claims_supported": "facts_present",
        "no_involved_claims_supported": "no_facts_present",
        "some_involved_claims_supported": "mixed_fact_presence",
    }
    assert constraints["unrelated_facts_affect_summary"] is False
    assert constraints["duplicate_involved_claim_ids_allowed"] is False


def test_research_lead_v3_local_and_canonical_reject_same_mismatch() -> None:
    specialists, output = _surfaces()
    output["conflict_adjudications"][0][
        "fact_presence_summary"
    ] = "no_facts_present"
    with pytest.raises(S3ResearchLeadV3ContractError) as local:
        DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v3_segment(
            output, specialists
        )
    with pytest.raises(
        ValueError,
        match="s3_owner_grade_lead_conflict_fact_presence_mismatch",
    ):
        _validate_canonical(output, specialists)
    assert local.value.telemetry["failure_subtype"] == (
        "fact_presence_summary_mismatch"
    )


def test_historical_research_lead_v2_contract_remains_versioned_and_unchanged() -> None:
    specialists, output = _surfaces()
    with pytest.raises(S3ResearchLeadContractError) as captured:
        output["remaining_gaps"] = []
        DeepSeekS3ThreeCellNodeExecutor._validate_research_lead_v2_segment(
            output, specialists
        )
    assert captured.value.telemetry["validator_contract"] == (
        "closed_research_lead_output:v2"
    )
    _, request, binding = DeepSeekS3ThreeCellNodeExecutor._research_lead_v2_request(
        {"specialist_outputs": specialists}, []
    )
    assert request["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
    )
    assert binding["research_lead_transport_ref"] == (
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V2_REF
    )
    assert "conflict_fact_presence_truth_table" not in request["output_constraints"]


def test_research_lead_v3_full_fake_provider_six_node_nine_artifact_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, fake = _run_v3(monkeypatch)
    assert len(fake.calls) == 12
    assert len(result.artifacts) == 9
    assert result.trace_events[-1]["event_payload"]["node_count"] == 6
    assert len(result.provider_output_captures) == 12
    assert all(
        capture["provider"] == "deepseek"
        for capture in result.provider_output_captures
    )


def test_research_lead_v3_mismatch_stops_at_lead_with_safe_v3_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mismatch(request: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        if request.get("node_id") == "research_lead":
            output["conflict_adjudications"][0][
                "fact_presence_summary"
            ] = "no_facts_present"
        return output

    with pytest.raises(BoundedAgentExecutionError) as captured:
        _run_v3(monkeypatch, mutation=mismatch)
    observation = captured.value.failure_observation
    telemetry = observation["failure_telemetry"]["research_lead_contract"]
    assert observation["observed_counts"]["model_calls"] == 10
    assert telemetry["validator_contract"] == "closed_research_lead_output:v3"
    assert telemetry["failure_family"] == "semantic"
    assert telemetry["failure_subtype"] == "fact_presence_summary_mismatch"
    assert telemetry["field_id"] == (
        "conflict_adjudications.fact_presence_summary"
    )


def test_research_lead_v3_zero_call_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_research_lead_v3_conflict_local_direct_support_zero_call_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"].startswith("pass_zero_call_research_lead_v3")
    assert result["deterministic_verification"][
        "restricted_live_replay_mismatch_count"
    ] == 1
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V3-FRESH-AGENT-PROOF-DECISION"
    )
