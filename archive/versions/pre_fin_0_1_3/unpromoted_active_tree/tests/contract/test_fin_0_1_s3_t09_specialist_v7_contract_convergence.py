from __future__ import annotations

from copy import deepcopy
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
    BoundedResearchProfile,
    ClaimScopeResolver,
    FactSupportAuthorityPolicy,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
    research_profile_for_ref,
    specialist_assembled_output_max_utf8_bytes,
    specialist_transport_contract,
    specialist_transport_refs,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _OwnerGradeFixtureNodeExecutor,
    _fixture_surfaces,
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
)
from test_fin_0_1_s3_t09_owner_grade_v3_specialist_v6_local_scope_assembly import (
    _V6FullFakeProvider,
)


def _v7_admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-specialist-v7-contract-convergence",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_enabled=True,
        execution_mode="fixture_only_specialist_v7_contract_convergence",
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF,
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
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


def _semantic_only_mutation(
    request: dict[str, Any], output: dict[str, Any]
) -> dict[str, Any]:
    if request.get("segment_id") == "owner_grade_claim_cards":
        for claim in output["judgment_layer"]:
            claim["scope"] = {
                "metric_or_mechanism": claim["scope"]["metric_or_mechanism"]
            }
    elif request.get("node_id") == "research_lead":
        output.pop("cell_heads")
    return output


def test_transport_registry_is_the_single_capability_source() -> None:
    assert S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_REFS == (
        specialist_transport_refs()
    )
    v6 = specialist_transport_contract(
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF
    )
    v7 = specialist_transport_contract(
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
    )
    assert v6.local_scope_assembly is True
    assert v6.field_local_fact_support_authority is False
    assert v7.local_scope_assembly is True
    assert v7.field_local_fact_support_authority is True


def test_assembled_output_capacity_is_resolved_from_capability_and_profile() -> None:
    profile = research_profile_for_ref(
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_REF
    )
    assert specialist_assembled_output_max_utf8_bytes(
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        research_profile=profile,
    ) == 8192
    assert specialist_assembled_output_max_utf8_bytes(
        transport_ref=(
            "fin01.s3.bounded_agent."
            "deepseek_segmented_owner_grade_specialist:v4"
        ),
        research_profile=profile,
    ) == 6000


def test_non_nvda_profile_and_nonstandard_period_are_domain_policy_inputs() -> None:
    profile = BoundedResearchProfile(
        profile_ref="fixture.research_profile.amd_margin:v1",
        company="AMD",
        program_cell_ids=("margin_bridge",),
        maximum_cell_count=1,
        maximum_narrative_characters=240,
        specialist_segment_max_utf8_bytes=4096,
        specialist_assembly_max_utf8_bytes=6144,
        specialist_segment_token_budgets=(
            ("facts_explanation_and_terminal", 800),
            ("owner_grade_claim_cards", 700),
            ("actionable_what_would_change_tasks", 700),
        ),
        owner_grade_stage_token_budgets=(
            ("specialist", 2200),
            ("lead", 800),
            ("writer", 800),
            ("verifier", 600),
        ),
        owner_grade_lead_v2_stage_token_budgets=(
            ("specialist", 2200),
            ("lead", 1000),
            ("writer", 800),
            ("verifier", 600),
        ),
        owner_grade_aggregate_output_tokens=8800,
        owner_grade_lead_v2_aggregate_output_tokens=9000,
    )
    profile.assert_scope(
        company="AMD",
        program_cell_ids=("margin_bridge",),
        maximum_cell_count=1,
    )
    claims = ClaimScopeResolver().assemble(
        claims=[
            {
                "claim_id": "claim:amd:margin",
                "support_fact_ids": ["fact:amd:margin"],
                "scope": {"metric_or_mechanism": "gross-margin bridge"},
            }
        ],
        facts={
            "fact:amd:margin": {
                "support_refs": ["numeric:amd:2027-q1"]
            }
        },
        numeric_scopes={
            "numeric:amd:2027-q1": {
                "entity_ref": "AMD",
                "business_scope_kind": "segment",
                "business_scope_ref": "data_center",
                "period": "2027-Q1-53W",
                "attribution_level": "segment",
            }
        },
    )
    assert claims[0]["scope"] == {
        "entity_ref": "AMD",
        "business_scope_kind": "segment",
        "business_scope_ref": "data_center",
        "period": "2027-Q1-53W",
        "metric_or_mechanism": "gross-margin bridge",
        "attribution_level": "segment",
    }


def test_v7_prompt_and_validator_share_exact_mixed_fact_authority() -> None:
    cells, specialists = _production_surfaces()
    cell = deepcopy(cells[0])
    cell["authority_refs"]["accepted_evidence_refs"] = [
        "evidence:official:amd:margin"
    ]
    cell["authority_refs"]["numeric_refs"] = [
        "numeric:official:amd:2027-q1"
    ]
    policy = FactSupportAuthorityPolicy.from_cell_input(cell)
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="facts_explanation_and_terminal",
        payload={
            "input_contract_ref": "fixture:input:v1",
            "input_digest": "fixture-input-digest",
            "cell_input": cell,
            "required_output_layers": [],
        },
        validated_segments={},
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    )
    assert request["fact_support_authority_contract"] == (
        policy.prompt_contract()
    )
    assert request["fact_support_authority_contract"][
        "allowed_refs_by_support_type"
    ] == {
        "Evidence": ["evidence:official:amd:margin"],
        "Numeric": ["numeric:official:amd:2027-q1"],
    }
    facts = deepcopy(
        specialists[str(cells[0]["program_cell_id"])]["fact_layer"]
    )
    facts[0]["support_type"] = "Numeric"
    facts[0]["support_refs"] = ["numeric:official:amd:2027-q1"]
    assert policy.first_violation(facts) is None


@pytest.mark.parametrize(
    ("support_type", "refs", "expected_subtype"),
    [
        ("Numeric", ["graph:context:1"], "candidate_or_graph_ref_misclassified_as_fact"),
        ("Numeric", ["evidence:1"], "evidence_or_numeric_cross_type"),
        ("Evidence", ["unknown:1"], "outside_current_cell_fact_authority"),
        ("Evidence", [], "support_refs_empty"),
        ("Evidence", ["evidence:1", "evidence:1"], "support_ref_duplicate"),
    ],
)
def test_fact_support_policy_classifies_without_repairing(
    support_type: str,
    refs: list[str],
    expected_subtype: str,
) -> None:
    original_refs = list(refs)
    policy = FactSupportAuthorityPolicy(
        evidence_refs=("evidence:1",),
        numeric_refs=("numeric:1",),
        candidate_refs=("candidate:1",),
        graph_context_refs=("graph:context:1",),
    )
    violation = policy.first_violation(
        [
            {
                "fact_id": "fact:1",
                "support_type": support_type,
                "support_refs": refs,
            }
        ]
    )
    assert violation is not None
    assert violation.subtype == expected_subtype
    assert refs == original_refs


def test_v6_request_remains_immutable_without_fact_support_contract() -> None:
    cells, _ = _production_surfaces()
    cell = cells[0]
    _, request, _ = DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
        node_id=f"domain_specialist:{cell['program_cell_id']}",
        segment_id="facts_explanation_and_terminal",
        payload={
            "input_contract_ref": "fixture:input:v1",
            "input_digest": "fixture-input-digest",
            "cell_input": cell,
            "required_output_layers": [],
        },
        validated_segments={},
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF,
    )
    assert "fact_support_authority_contract" not in request
    assert request["required_output_schema"]["fact_layer"][0][
        "support_refs"
    ] == ["exact authorized ref"]


def test_v7_full_fake_provider_reaches_six_nodes_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _v7_admission(input_pack)
    fake = _V6FullFakeProvider(
        specialists,
        mutation=_semantic_only_mutation,
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
            "research_run_id": "fixture-run-specialist-v7-full",
            "attempt_id": "fixture-attempt-specialist-v7-full",
        },
    )
    assert (
        result.terminal_reason
        == "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9


def test_v7_outer_revalidation_accepts_profile_bounded_output_above_6000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _v7_admission(input_pack)
    first_cell_id = str(cells[0]["program_cell_id"])

    def enlarge_first_cell_within_profile_capacity(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        output = _semantic_only_mutation(request, output)
        if request.get("node_id") != f"domain_specialist:{first_cell_id}":
            return output
        filler = "界" * 240
        if request.get("segment_id") == "facts_explanation_and_terminal":
            output["fact_layer"][0]["statement"] += filler
            output["fact_layer"][0]["boundary"] += filler
            output["explanation_layer"][0] += filler
            output["remaining_gaps"][0] += filler
        elif request.get("segment_id") == "owner_grade_claim_cards":
            output["judgment_layer"][0]["statement"] += filler
            output["judgment_layer"][0]["qualification"] = filler
        return output

    fake = _V6FullFakeProvider(
        specialists,
        mutation=enlarge_first_cell_within_profile_capacity,
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
            "research_run_id": "fixture-run-specialist-v7-over-6000",
            "attempt_id": "fixture-attempt-specialist-v7-over-6000",
        },
    )
    judgment_artifact = next(
        row
        for row in result.artifacts
        if row.artifact_type == "bounded_agent_judgment"
    )
    first_specialist = judgment_artifact.payload["specialist_outputs"][0]
    serialized_size = len(
        json.dumps(
            first_specialist,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    assert 6000 < serialized_size <= 8192
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9


class _PostNodeInvalidFixtureExecutor(_OwnerGradeFixtureNodeExecutor):
    def execute_node(
        self,
        node_id: str,
        payload: Any,
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Any,
    ) -> Any:
        raw = dict(
            super().execute_node(
                node_id,
                payload,
                admission,
                run_identity=run_identity,
            )
        )
        if node_id.startswith("domain_specialist:"):
            raw["output"] = dict(raw["output"])
            raw["output"]["program_cell_id"] = "wrong-cell"
            raw["usage_receipts"] = [
                {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "estimated_cost_usd": 0.00001,
                }
            ]
            raw["provider_output_captures"] = [
                {
                    "stage": node_id,
                    "assistant_output_text": "original answer",
                }
            ]
        return raw


def test_post_node_validation_preserves_accumulated_usage_and_answer_capture() -> None:
    cells, _, _, _ = _fixture_surfaces()
    input_pack = _input_pack(cells)
    admission = _v7_admission(input_pack)
    with pytest.raises(BoundedAgentExecutionError) as captured:
        S3ThreeCellBoundedAgentExecutor(
            _PostNodeInvalidFixtureExecutor()
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-run-post-node-capture",
                "attempt_id": "fixture-attempt-post-node-capture",
            },
        )
    error = captured.value
    assert error.stage.endswith(":post_node_validation")
    assert error.failure_observation["failure_codes"] == [
        "s3_bounded_post_node_validation_failed:specialist_output"
    ]
    assert error.failure_observation["observed_counts"][
        "model_calls"
    ] == 1
    assert error.failure_observation["estimated_cost_usd"] == 0.00001
    assert error.provider_output_captures == [
        {
            "stage": (
                "domain_specialist:demand_authenticity_and_sustainability"
            ),
            "assistant_output_text": "original answer",
        }
    ]
    assert "wrong-cell" not in json.dumps(
        error.failure_observation,
        ensure_ascii=False,
    )


def test_v7_graph_fact_support_stops_first_segment_with_typed_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    admission = _v7_admission(input_pack)

    def inject_graph_fact_support(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        if (
            request.get("segment_id") == "facts_explanation_and_terminal"
            and request.get("node_id")
            == "domain_specialist:demand_authenticity_and_sustainability"
        ):
            contract = request["fact_support_authority_contract"]
            numeric_refs = contract["allowed_refs_by_support_type"]["Numeric"]
            graph_refs = request["analysis_input"]["cell_input"][
                "authority_refs"
            ]["graph_context_refs_not_evidence"]
            output["fact_layer"][0]["support_type"] = "Numeric"
            output["fact_layer"][0]["support_refs"] = [
                numeric_refs[0],
                graph_refs[0],
            ]
        return _semantic_only_mutation(request, output)

    fake = _V6FullFakeProvider(
        specialists,
        mutation=inject_graph_fact_support,
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
                "research_run_id": "fixture-run-specialist-v7-graph-stop",
                "attempt_id": "fixture-attempt-specialist-v7-graph-stop",
            },
        )
    assert len(fake.calls) == 1
    assert len(captured.value.provider_output_captures) == 1
    telemetry = captured.value.failure_observation["failure_telemetry"][
        "segmented_specialist_fact_authority"
    ]
    assert telemetry == {
        "validator_contract": "closed_fact_support_authority:v1",
        "segment_id": "facts_explanation_and_terminal",
        "field_id": "fact_layer.support_refs",
        "authority_subtype": (
            "candidate_or_graph_ref_misclassified_as_fact"
        ),
        "failing_item_count": 1,
        "raw_ref_persisted": False,
        "ref_digest_persisted": False,
        "item_index_persisted": False,
        "arbitrary_key_names_persisted": False,
        "private_reasoning_persisted": False,
    }
    assert "graph:" not in json.dumps(telemetry)


def test_v7_requires_explicit_profile_while_v6_digest_remains_legacy() -> None:
    cells, _ = _production_surfaces()
    input_pack = _input_pack(cells)
    v7_payload = _v7_admission(input_pack).model_dump(mode="python")
    v7_payload.pop("research_profile_ref")
    with pytest.raises(
        ValueError,
        match="s3_bounded_admission_v7_explicit_research_profile_required",
    ):
        S3ThreeCellBoundedAgentAdmission.model_validate(
            v7_payload
        ).assert_profile_admissible()

    v6_payload = _v7_admission(input_pack).model_dump(mode="python")
    v6_payload["transport_ref"] = (
        S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V6_REF
    )
    v6_payload.pop("research_profile_ref")
    legacy_v6 = S3ThreeCellBoundedAgentAdmission.model_validate(v6_payload)
    legacy_v6.assert_profile_admissible()
    assert "research_profile_ref" not in legacy_v6.digest_payload()


def test_v7_zero_call_release_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_specialist_v7_contract_convergence_zero_call_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (
            ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == (
        "pass_zero_call_specialist_v7_contract_convergence_fixture_proven_"
        "fresh_agent_proof_decision_pending"
    )
    assert result["architecture"]["prompt_and_validator_share_policy"] is True
    assert result["compatibility"]["v1_through_v6_transport_refs_unchanged"] is True
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-SPECIALIST-V7-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"][
        "S3_T09_specialist_v7_fresh_exact_proof_decision_ref"
    ] == (
        "configs/releases/fin_ia_0_1_s3_t09_owner_grade_specialist_v7_"
        "fresh_exact_proof_decision_v1_0.json"
    )
    assert (
        backlog["next_action"]["specialist_v7_fresh_agent_proof_decision_authorized"]
        is True
    )
