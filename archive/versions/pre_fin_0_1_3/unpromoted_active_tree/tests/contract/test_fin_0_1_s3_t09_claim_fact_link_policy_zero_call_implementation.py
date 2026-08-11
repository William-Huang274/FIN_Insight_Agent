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
    ClaimFactLinkPolicy,
    S3_CLAIM_FACT_LINK_POLICY_REF,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_owner_grade_v3_segmented_transport_v3_closed_context_authority_repair import (
    _production_surfaces,
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


def _policy_admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return _v5_admission(input_pack).model_copy(
        update={
            "research_profile_ref": (
                S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V3_REF
            ),
            "claim_fact_link_policy_ref": S3_CLAIM_FACT_LINK_POLICY_REF,
        }
    )


def _emit_claim_fact_aliases(
    request: dict[str, Any], output: dict[str, Any]
) -> dict[str, Any]:
    output = _semantic_only_mutation(request, output)
    if request.get("segment_id") != "owner_grade_claim_cards":
        return output
    allowed_aliases = [
        row["fact_alias"]
        for row in request["claim_fact_link_contract"]["allowed_facts"]
    ]
    for claim in output["judgment_layer"]:
        had_support = bool(claim.pop("support_fact_ids"))
        claim["support_fact_aliases"] = (
            [allowed_aliases[0]] if had_support else []
        )
    return output


def _direct_policy() -> ClaimFactLinkPolicy:
    return ClaimFactLinkPolicy.from_validated_facts(
        program_cell_id="amd_margin",
        facts=[
            {
                "fact_id": "fact:amd:evidence",
                "statement": "AMD 发布了新产品路线图。",
                "support_type": "Evidence",
                "support_refs": ["evidence:amd:roadmap"],
                "boundary": "不代表已实现收入。",
            },
            {
                "fact_id": "fact:amd:numeric",
                "statement": "AMD 数据中心毛利率按固定口径计算。",
                "support_type": "Numeric",
                "support_refs": ["numeric:amd:2027-q1"],
                "boundary": "仅限数据中心分部。",
            },
        ],
        numeric_scopes={
            "numeric:amd:2027-q1": {
                "entity_ref": "AMD",
                "business_scope_kind": "segment",
                "business_scope_ref": "data_center",
                "period": "FY2027-Q1-53W",
                "attribution_level": "segment",
            }
        },
        additional_forbidden_refs=(
            "candidate:amd:channel",
            "graph:amd:supply",
            "routing:amd:followup",
        ),
    )


def _claim_output(
    support: Any,
    *,
    cell_id: str = "amd_margin",
    status: str = "fact_supported",
    provider_fact_ids_field: bool = False,
) -> dict[str, Any]:
    claim = {
        "claim_id": "claim:amd:margin",
        "statement": "数据中心毛利判断。",
        "epistemic_status": status,
        "context_refs": [],
        "scope": {"metric_or_mechanism": "毛利率"},
        "qualification": "",
        "cannot_support": [],
    }
    claim[
        "support_fact_ids"
        if provider_fact_ids_field
        else "support_fact_aliases"
    ] = support
    return {
        "program_cell_id": cell_id,
        "judgment_layer": [claim],
    }


def test_policy_generalizes_non_nvda_period_and_mixed_authority() -> None:
    policy = _direct_policy()
    contract = policy.prompt_contract()

    assert policy.contract_ref == S3_CLAIM_FACT_LINK_POLICY_REF
    assert [row["fact_alias"] for row in contract["allowed_facts"]] == [
        "F001",
        "F002",
    ]
    numeric = next(
        row
        for row in contract["allowed_facts"]
        if row["support_type"] == "Numeric"
    )
    assert numeric["locally_assembled_scope_summary"] == {
        "entity": "AMD",
        "business_scope_kind": "segment",
        "business_scope": "data_center",
        "period": "FY2027-Q1-53W",
        "attribution_level": "segment",
    }
    serialized = json.dumps(contract, ensure_ascii=False)
    assert "fact:amd:" not in serialized
    assert "numeric:amd:" not in serialized
    assert "evidence:amd:" not in serialized
    assert contract[
        "normalization_trim_prefix_guess_fuzzy_match_or_rewrite_allowed"
    ] is False


def test_provider_prior_and_model_view_hide_source_and_object_namespaces() -> None:
    policy = _direct_policy()
    prior = policy.provider_prior_segment(
        {
            "program_cell_id": "amd_margin",
            "fact_layer": [
                {
                    "fact_id": "fact:amd:numeric",
                    "statement": "statement",
                    "support_type": "Numeric",
                    "support_refs": ["numeric:amd:2027-q1"],
                    "boundary": "boundary",
                }
            ],
            "explanation_layer": ["explanation"],
            "remaining_gaps": ["gap"],
            "terminal_class": "bounded",
        }
    )
    redacted = policy.redact_claim_selection_model_view(
        {
            "program_cell_id": "amd_margin",
            "authority_refs": {"numeric_refs": ["numeric:amd:2027-q1"]},
            "numeric_view": {
                "derived_metric_id": "numeric:amd:2027-q1",
                "result_value": "51.2",
                "period_ref": "FY2027-Q1-53W",
            },
            "graph_view": {
                "edge_projection_id": "graph:amd:supply",
                "edge_type": "supply",
            },
        }
    )

    prior_text = json.dumps(prior, ensure_ascii=False)
    redacted_text = json.dumps(redacted, ensure_ascii=False)
    assert "support_refs" not in prior_text
    assert "fact:amd:" not in prior_text
    assert "numeric:amd:" not in redacted_text
    assert "graph:amd:" not in redacted_text
    assert redacted["program_cell_id"] == "amd_margin"
    assert redacted["numeric_view"]["result_value"] == "51.2"


def test_exact_alias_expands_to_canonical_fact_ids_without_residue() -> None:
    policy = _direct_policy()
    aliases = {
        row.support_type: row.alias for row in policy.alias_rows
    }
    expected = {
        row.support_type: row.fact_id for row in policy.alias_rows
    }
    output = _claim_output([aliases["Numeric"]])

    expanded, violation = policy.expand_claim_output(output)

    assert violation is None
    assert expanded is not None
    claim = expanded["judgment_layer"][0]
    assert claim["support_fact_ids"] == [expected["Numeric"]]
    assert "support_fact_aliases" not in claim
    assert "F00" not in json.dumps(expanded, ensure_ascii=False)


@pytest.mark.parametrize(
    ("output", "subtype"),
    [
        (_claim_output("F001"), "support_alias_not_array"),
        (_claim_output([""]), "support_alias_item_invalid"),
        (_claim_output([]), "support_alias_empty_when_required"),
        (_claim_output(["F999"]), "support_alias_unknown"),
        (_claim_output(["F001", "F001"]), "support_alias_duplicate"),
        (
            _claim_output(["F001"], cell_id="wrong_cell"),
            "support_alias_wrong_cell",
        ),
        (
            _claim_output(["fact:amd:numeric"]),
            "raw_fact_or_source_ref_used_in_alias_field",
        ),
        (
            _claim_output(
                ["fact:amd:numeric"],
                provider_fact_ids_field=True,
            ),
            "raw_fact_or_source_ref_used_in_alias_field",
        ),
    ],
)
def test_alias_contract_fails_closed_without_repair(
    output: dict[str, Any],
    subtype: str,
) -> None:
    original = deepcopy(output)
    expanded, violation = _direct_policy().expand_claim_output(output)

    assert expanded is None
    assert violation is not None
    assert violation.subtype == subtype
    assert output == original


def test_claim_request_uses_alias_schema_and_redacted_fact_surface() -> None:
    cells, specialists = _production_surfaces()
    cell = cells[1]
    cell_id = str(cell["program_cell_id"])
    specialist = specialists[cell_id]

    _, request, binding = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id=f"domain_specialist:{cell_id}",
            segment_id="owner_grade_claim_cards",
            payload={
                "input_contract_ref": "fixture:input:v1",
                "input_digest": "fixture-input-digest",
                "cell_input": cell,
                "required_output_layers": [],
            },
            validated_segments={
                "facts_explanation_and_terminal": _first_segment(
                    specialist
                )
            },
            transport_ref=(
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
            ),
            claim_fact_link_policy_ref=S3_CLAIM_FACT_LINK_POLICY_REF,
        )
    )

    claim_schema = request["required_output_schema"]["judgment_layer"][0]
    assert "support_fact_aliases" in claim_schema
    assert "support_fact_ids" not in claim_schema
    assert request["epistemic_status_contract"]["field_id"].startswith(
        "judgment_layer.epistemic_status_support_fact_aliases"
    )
    assert request["local_scope_assembly_contract"][
        "numeric_support_rule"
    ].endswith("all supported Numeric rows must agree.")
    assert binding["claim_fact_link_policy_ref"] == (
        S3_CLAIM_FACT_LINK_POLICY_REF
    )
    prior = request["validated_prior_segments"][
        "facts_explanation_and_terminal"
    ]
    serialized_prior = json.dumps(prior, ensure_ascii=False)
    serialized_contract = json.dumps(
        request["claim_fact_link_contract"], ensure_ascii=False
    )
    serialized_model_view = json.dumps(
        request["analysis_input"]["cell_input"], ensure_ascii=False
    )
    assert "support_refs" not in serialized_prior
    assert "fact_id" not in serialized_prior
    assert "numeric:" not in serialized_contract
    assert "evidence:" not in serialized_contract
    assert "numeric:" not in serialized_model_view
    assert "evidence:" not in serialized_model_view


def test_legacy_admission_digest_and_request_remain_unchanged() -> None:
    cells, specialists = _production_surfaces()
    input_pack = _input_pack(cells)
    legacy = _v5_admission(input_pack)
    assert "claim_fact_link_policy_ref" not in legacy.digest_payload()

    cell = cells[0]
    cell_id = str(cell["program_cell_id"])
    _, request, binding = (
        DeepSeekS3ThreeCellNodeExecutor._specialist_segment_request(
            node_id=f"domain_specialist:{cell_id}",
            segment_id="owner_grade_claim_cards",
            payload={
                "input_contract_ref": "fixture:input:v1",
                "input_digest": "fixture-input-digest",
                "cell_input": cell,
                "required_output_layers": [],
            },
            validated_segments={
                "facts_explanation_and_terminal": _first_segment(
                    specialists[cell_id]
                )
            },
            transport_ref=(
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
            ),
        )
    )
    assert "claim_fact_link_contract" not in request
    assert "support_fact_ids" in (
        request["required_output_schema"]["judgment_layer"][0]
    )
    assert "claim_fact_link_policy_ref" not in binding


def test_policy_binding_requires_supported_shared_capabilities() -> None:
    cells, _ = _production_surfaces()
    input_pack = _input_pack(cells)
    valid = _policy_admission(input_pack)
    valid.assert_profile_admissible()

    unsupported = valid.model_copy(
        update={"claim_fact_link_policy_ref": "unsupported:v1"}
    )
    with pytest.raises(
        ValueError,
        match="claim_fact_link_policy_unsupported",
    ):
        unsupported.assert_profile_admissible()

    wrong_output = valid.model_copy(
        update={
            "output_contract_ref": (
                "fin01.s3.bounded_agent_three_cell_output:v3"
            )
        }
    )
    with pytest.raises(
        ValueError,
        match="claim_fact_link_policy_capability_binding_required",
    ):
        wrong_output.assert_profile_admissible()


def test_full_fake_provider_reaches_six_nodes_twelve_calls_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _policy_admission(input_pack)
    fake = _CompactV5FullFakeProvider(
        specialists,
        mutation=_emit_claim_fact_aliases,
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
            "research_run_id": "fixture-run-claim-fact-link-policy",
            "attempt_id": "fixture-attempt-claim-fact-link-policy",
        },
    )

    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    claim_requests = [
        row["request"]
        for row in fake.calls
        if row["request"].get("segment_id") == "owner_grade_claim_cards"
    ]
    assert len(claim_requests) == 3
    assert {
        request["claim_fact_link_contract"]["allowed_facts"][0][
            "fact_alias"
        ]
        for request in claim_requests
    } == {"F001"}
    verifier_request = next(
        row["request"]
        for row in fake.calls
        if row["request"]["node_id"] == "verifier"
    )
    assert set(
        verifier_request["required_output_schema"]["findings"][0]
    ) == {
        "layer",
        "status",
        "issue_codes",
        "artifact_or_claim_refs",
        "repair_owner",
    }
    artifact_text = json.dumps(
        [row.model_dump(mode="json") for row in result.artifacts],
        ensure_ascii=False,
    )
    assert "support_fact_aliases" not in artifact_text
    assert '"F001"' not in artifact_text


def test_raw_fact_identity_stops_at_second_call_with_safe_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _policy_admission(input_pack)

    def emit_raw_fact_id(
        request: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        output = _semantic_only_mutation(request, output)
        if request.get("segment_id") == "owner_grade_claim_cards":
            for claim in output["judgment_layer"]:
                raw_fact_ids = claim.pop("support_fact_ids")
                claim["support_fact_aliases"] = raw_fact_ids
        return output

    fake = _CompactV5FullFakeProvider(
        specialists,
        mutation=emit_raw_fact_id,
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
                "research_run_id": "fixture-run-claim-fact-link-stop",
                "attempt_id": "fixture-attempt-claim-fact-link-stop",
            },
        )

    assert len(fake.calls) == 2
    assert len(captured.value.provider_output_captures) == 2
    telemetry = captured.value.failure_observation["failure_telemetry"][
        "segmented_specialist_claim_fact_link"
    ]
    assert telemetry["validator_contract"] == (
        S3_CLAIM_FACT_LINK_POLICY_REF
    )
    assert telemetry["failure_subtype"] == (
        "raw_fact_or_source_ref_used_in_alias_field"
    )
    assert telemetry["failing_item_count"] >= 1
    assert "fact:" not in json.dumps(telemetry, ensure_ascii=False)


def test_zero_call_implementation_result_and_backlog_are_frozen() -> None:
    result_path = (
        ROOT
        / "configs/releases/"
        "fin_ia_0_1_s3_t09_claim_fact_link_policy_closed_alias_"
        "zero_call_implementation_v1_0.json"
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    backlog = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )

    assert result["status"].startswith("pass_zero_call_")
    assert result["selected_contract_ref"] == (
        S3_CLAIM_FACT_LINK_POLICY_REF
    )
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-GENERALIZED-CLAIM-FACT-LINK-POLICY-FRESH-AGENT-"
        "PROOF-DECISION"
    )
    next_action = backlog["next_action"]
    assert next_action[
        "S3_T09_claim_fact_link_policy_fresh_agent_proof_decision_ref"
    ] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t09_claim_fact_link_policy_"
        "fresh_agent_proof_decision_v1_0.json"
    )
    assert next_action["claim_fact_link_fresh_proof_authorized"] is True
    assert backlog["next_action"][
        "claim_fact_link_policy_zero_call_implementation_authorized"
    ] is True
    assert backlog["next_action"]["agent_execution_authorized"] is False
