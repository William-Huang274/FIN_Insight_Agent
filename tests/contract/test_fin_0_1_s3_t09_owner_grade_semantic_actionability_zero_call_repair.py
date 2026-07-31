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


from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
    S3_OWNER_GRADE_CLAIM_STATUSES,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
    S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    S3_THREE_CELL_PROGRAM_CELL_IDS,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    S3ThreeCellBoundedAgentInputPack,
    S3VerifierStateMachineError,
)
from sec_agent.canonical_runtime.models import canonical_digest


def _cell_input(cell_id: str, index: int) -> dict[str, Any]:
    numeric_ref = f"numeric:{index}"
    candidate_ref = f"candidate:{index}"
    graph_ref = f"graph:{index}"
    return {
        "program_cell_id": cell_id,
        "runtime_branch": {"owner_role": "financial_analyst"},
        "role_contexts": [],
        "evidence_input": {},
        "numeric_input": {
            "fundamental_decision_cell": {
                "typed_cannot_infer": ["segment_revenue_not_supported"],
                "support_boundary": "Company-total revenue does not support segment attribution.",
            },
            "selected_financial_rows": [
                {
                    "financial_row_id": numeric_ref,
                    "selector": {
                        "entity_ref": "NVDA",
                        "segment_ref": "__company_total__",
                        "period": "FY2025-FY",
                        "metric_family": "revenue",
                    },
                    "normalized_value": str(100 + index),
                }
            ],
            "derived_metrics": [],
        },
        "graph_context_input": {},
        "authority_refs": {
            "accepted_evidence_refs": [],
            "numeric_refs": [numeric_ref],
            "candidate_refs_not_evidence": [candidate_ref],
            "graph_context_refs_not_evidence": [graph_ref],
        },
    }


def _specialist_output(cell: Mapping[str, Any], index: int) -> dict[str, Any]:
    cell_id = str(cell["program_cell_id"])
    numeric_ref = str(cell["authority_refs"]["numeric_refs"][0])
    claim_id = f"claim:{index}"
    return {
        "program_cell_id": cell_id,
        "fact_layer": [
            {
                "fact_id": f"fact:{index}",
                "statement": f"NVDA FY2025 company-total revenue fixture {index} is admitted.",
                "support_type": "Numeric",
                "support_refs": [numeric_ref],
                "boundary": "This fact does not support segment or product attribution.",
            }
        ],
        "explanation_layer": ["The conclusion remains inside company-total authority."],
        "judgment_layer": [
            {
                "claim_id": claim_id,
                "statement": "The admitted fact supports only NVDA company-total revenue.",
                "epistemic_status": "fact_supported",
                "support_fact_ids": [f"fact:{index}"],
                "context_refs": [],
                "scope": {
                    "entity_ref": "NVDA",
                    "business_scope_kind": "company_total",
                    "business_scope_ref": "__company_total__",
                    "period": "FY2025-FY",
                    "metric_or_mechanism": "revenue",
                    "attribution_level": "company_total",
                },
                "qualification": "",
                "cannot_support": ["segment_revenue_not_supported"],
            }
        ],
        "remaining_gaps": ["Segment revenue authority remains absent."],
        "what_would_change": [
            {
                "task_id": f"task:{index}",
                "claim_id": claim_id,
                "source_target": {
                    "source_type": "issuer_filing",
                    "entity_or_owner": "NVDA",
                    "document_event_or_dataset": "next reviewed segment disclosure",
                },
                "metric_or_observation": "reported segment revenue",
                "decision_rule": {
                    "rule_type": "qualitative_observation",
                    "comparator_or_condition": "explicit segment attribution is disclosed",
                    "threshold_or_observation": "reviewed value and period are both present",
                },
                "time_window": {
                    "as_of": "2026-07-22",
                    "start_or_trigger": "next issuer filing",
                    "deadline_or_review_date": "2026-10-31",
                },
                "expected_claim_transition": "company_total_to_segment_fact_supported",
                "fallback_stop_condition": "stop if no reviewed segment disclosure appears",
                "authority_refs": [numeric_ref],
            }
        ],
        "terminal_class": "bounded_fact_supported",
    }


def _lead_output(specialists: list[Mapping[str, Any]]) -> dict[str, Any]:
    claims = [str(row["judgment_layer"][0]["claim_id"]) for row in specialists]
    tasks = [str(row["what_would_change"][0]["task_id"]) for row in specialists]
    return {
        "cell_heads": [
            {
                "program_cell_id": row["program_cell_id"],
                "specialist_output_digest": canonical_digest(row),
                "terminal_class": row["terminal_class"],
                "evidence_fact_count": 0,
                "numeric_fact_count": 1,
                "claim_state_counts": {
                    status: 1 if status == "fact_supported" else 0
                    for status in S3_OWNER_GRADE_CLAIM_STATUSES
                },
            }
            for row in specialists
        ],
        "cross_cell_dependencies": [
            {
                "dependency_id": "dependency:1",
                "statement": "Company-total claims share the same attribution boundary.",
                "claim_ids": claims,
            }
        ],
        "conflict_adjudications": [
            {
                "adjudication_id": "adjudication:1",
                "involved_claim_ids": claims,
                "terminal_state_summary": "All cells terminate with bounded claims.",
                "fact_presence_summary": "facts_present",
                "resolution_status": "no_cross_cell_conflict",
                "statement": "Facts exist, but none authorizes segment attribution.",
            }
        ],
        "variant_view": {
            "statement": "The variant view is limited to company-total facts.",
            "claim_ids": claims,
            "what_would_change_task_ids": tasks,
        },
        "remaining_gaps": [
            {
                "gap_id": "gap:1",
                "statement": "Reviewed segment attribution remains missing.",
                "claim_ids": claims,
                "what_would_change_task_ids": tasks,
            }
        ],
    }


def _writer_output(
    specialists: list[Mapping[str, Any]], lead: Mapping[str, Any]
) -> dict[str, Any]:
    claim_surface = S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(
        specialists
    )
    claim_ids = [str(row["judgment_layer"][0]["claim_id"]) for row in specialists]
    task_ids = [str(row["what_would_change"][0]["task_id"]) for row in specialists]
    rendered_texts = [
        "已支持的判断仅限 NVDA 公司整体收入。" for _ in specialists
    ]
    return {
        "title_zh_cn": "NVDA 三单元内部研究备忘录",
        "executive_summary_zh_cn": "；".join(rendered_texts),
        "sections": [
            {
                "program_cell_id": row["program_cell_id"],
                "claim_renderings": [
                    {
                        "claim_id": row["judgment_layer"][0]["claim_id"],
                        "rendered_text_zh_cn": "已支持的判断仅限 NVDA 公司整体收入。",
                        "epistemic_status": "fact_supported",
                        "scope_digest": canonical_digest(
                            row["judgment_layer"][0]["scope"]
                        ),
                        "qualification_preserved": True,
                    }
                ],
                "what_would_change_task_refs": [
                    row["what_would_change"][0]["task_id"]
                ],
            }
            for row in specialists
        ],
        "limitations_zh_cn": ["segment_revenue_not_supported"],
        "consumed_lead_digest": canonical_digest(lead),
        "consumed_claim_surface_digest": canonical_digest(claim_surface),
        "exact_claim_ids": claim_ids,
        "exact_WWC_task_ids": task_ids,
        "source_calls": 0,
        "tool_calls": 0,
    }


def _verifier_output(lead: Mapping[str, Any], writer: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "findings": [
            {
                "layer": layer,
                "status": "pass",
                "issue_codes": [],
                "artifact_or_claim_refs": [],
                "repair_owner": None,
            }
            for layer in S3_FOUR_LAYER_VERIFIER_LAYERS
        ],
        "bound_lead_digest": canonical_digest(lead),
        "bound_writer_digest": canonical_digest(writer),
        "decision": "accept_for_internal_review",
    }


def _fixture_surfaces() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]
]:
    cells = [_cell_input(cell_id, index) for index, cell_id in enumerate(S3_THREE_CELL_PROGRAM_CELL_IDS, 1)]
    specialists = [_specialist_output(cell, index) for index, cell in enumerate(cells, 1)]
    lead = _lead_output(specialists)
    writer = _writer_output(specialists, lead)
    return cells, specialists, lead, writer


class _OwnerGradeFixtureNodeExecutor:
    def execute_node(
        self,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> Mapping[str, Any]:
        if node_id.startswith("domain_specialist:"):
            index = S3_THREE_CELL_PROGRAM_CELL_IDS.index(node_id.split(":", 1)[1]) + 1
            output = _specialist_output(payload["cell_input"], index)
        elif node_id == "research_lead":
            output = _lead_output(list(payload["specialist_outputs"]))
        elif node_id == "memo_writer":
            output = _writer_output(
                list(payload["specialist_heads"]), payload["cross_cell_lead"]
            )
        elif node_id == "verifier":
            output = _verifier_output(
                payload["cross_cell_lead"], payload["writer_output"]
            )
        else:
            raise AssertionError(node_id)
        return {
            "node_id": node_id,
            "output": output,
            "observed_counts": {
                "model_calls": 0,
                "provider_calls": 0,
                "network_calls": 0,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "live_case_head_writes": 0,
                "evaluation_evidence_promotions": 0,
            },
            "usage_receipts": [],
            "version_bindings": {
                "agent_definition_version_ref": f"fixture:{node_id}:v3",
                "skill_pack_version_ref": f"fixture:{node_id}:v3",
                "model_view_contract_ref": S3_SPECIALIST_MODEL_VIEW_CONTRACT_REF,
                "model_view_digest": "0" * 64,
                "fixture_only": True,
            },
        }


def _input_pack(cells: list[dict[str, Any]]) -> S3ThreeCellBoundedAgentInputPack:
    return S3ThreeCellBoundedAgentInputPack(
        case_id="case:s3-t09-owner-grade-fixture",
        case_version=1,
        query="Test owner-grade semantic actionability without calls",
        as_of="2026-07-22T00:00:00Z",
        decision_surface_contract_ref="fixture:decision-surface:v1",
        input_head_digest="1" * 64,
        lineage={
            key: {
                "version_ref": f"fixture:{key}:v1",
                "digest": canonical_digest(("fixture", key)),
            }
            for key in (
                "T02_runtime_plan",
                "T03_evidence_route_plan",
                "T04_financial_pack",
                "T05_graph_pack",
                "T06_judgment_contract",
                "T07_presentation_contract",
            )
        },
        cell_inputs=tuple(cells),
        lead_contract={"contract_ref": "fixture:lead:v2"},
        writer_contract={"contract_ref": "fixture:writer:v2"},
        verifier_contract={"contract_ref": "fixture:verifier:v2"},
        paired_baseline_contract={"status": "not_materialized"},
        hard_boundaries={"model_calls": 0, "network_calls": 0},
        input_digest="2" * 64,
    )


def test_v3_positive_six_node_zero_call_fixture_preserves_nine_artifact_families() -> None:
    cells, _, _, _ = _fixture_surfaces()
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="s3-t09-owner-grade-zero-call-fixture",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        execution_mode="zero_call_owner_grade_contract_fixture",
    )
    result = S3ThreeCellBoundedAgentExecutor(
        _OwnerGradeFixtureNodeExecutor()
    ).execute(
        _input_pack(cells),
        admission,
        run_identity={"research_run_id": "run:fixture", "attempt_id": "attempt:fixture"},
    )
    assert result.terminal_reason == "s3_bounded_agent_three_cell_execution_succeeded"
    assert tuple(row.artifact_type for row in result.artifacts) == BOUNDED_AGENT_ARTIFACT_TYPES
    manifest = result.artifacts[0].payload
    assert len(manifest["node_topology"]) == 6
    assert set(manifest["observed_counts"].values()) == {0}


def test_v3_rejects_unsupported_segment_revenue_from_company_total_numeric() -> None:
    cells, specialists, _, _ = _fixture_surfaces()
    bad = deepcopy(specialists[0])
    bad["judgment_layer"][0]["scope"].update(
        {
            "business_scope_kind": "segment",
            "business_scope_ref": "Data Center",
            "attribution_level": "segment",
        }
    )
    with pytest.raises(ValueError, match="s3_owner_grade_claim_scope_exceeds_fact_authority"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            bad, cells[0], output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
        )


def test_v3_rejects_candidate_or_graph_as_supported_claim_authority() -> None:
    cells, specialists, _, _ = _fixture_surfaces()
    bad = deepcopy(specialists[0])
    bad["judgment_layer"][0]["support_fact_ids"] = []
    bad["judgment_layer"][0]["context_refs"] = ["candidate:1"]
    with pytest.raises(ValueError, match="s3_owner_grade_context_promoted_to_claim_authority"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            bad, cells[0], output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
        )


def test_v3_rejects_positive_supported_claim_encoded_as_cannot_infer() -> None:
    cells, specialists, _, _ = _fixture_surfaces()
    bad = deepcopy(specialists[0])
    bad["judgment_layer"][0]["epistemic_status"] = "cannot_infer"
    with pytest.raises(ValueError, match="s3_owner_grade_epistemic_status_statement_conflict"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            bad, cells[0], output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
        )


def test_v3_rejects_incomplete_what_would_change_task() -> None:
    cells, specialists, _, _ = _fixture_surfaces()
    bad = deepcopy(specialists[0])
    del bad["what_would_change"][0]["time_window"]["deadline_or_review_date"]
    with pytest.raises(ValueError, match="s3_owner_grade_WWC_task_incomplete"):
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output(
            bad, cells[0], output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF
        )


def test_v3_rejects_lead_non_fact_summary_when_numeric_fact_exists() -> None:
    _, specialists, lead, _ = _fixture_surfaces()
    bad = deepcopy(lead)
    bad["conflict_adjudications"][0]["statement"] = (
        "All cells are in non-fact states."
    )
    digests = {str(row["program_cell_id"]): canonical_digest(row) for row in specialists}
    with pytest.raises(
        ValueError,
        match=(
            "s3_owner_grade_lead_explicit_global_fact_presence_"
            "statement_conflict"
        ),
    ):
        S3ThreeCellBoundedAgentExecutor._validate_lead_output(
            bad,
            digests,
            specialist_outputs=specialists,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        )


def test_v3_rejects_writer_unknown_claim_identity() -> None:
    _, specialists, lead, writer = _fixture_surfaces()
    bad = deepcopy(writer)
    bad["sections"][0]["claim_renderings"][0]["claim_id"] = "claim:unknown"
    with pytest.raises(ValueError, match="s3_owner_grade_writer_claim_surface_violation"):
        S3ThreeCellBoundedAgentExecutor._validate_writer_output(
            bad,
            canonical_digest(lead),
            specialist_outputs=specialists,
            cross_cell_lead=lead,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        )


def test_v3_rejects_graph_context_mistranslated_as_chart() -> None:
    _, specialists, lead, writer = _fixture_surfaces()
    bad = deepcopy(writer)
    bad["sections"][0]["claim_renderings"][0]["rendered_text_zh_cn"] = "图表假设支持该结论。"
    with pytest.raises(ValueError, match="s3_owner_grade_writer_graph_terminology_invalid"):
        S3ThreeCellBoundedAgentExecutor._validate_writer_output(
            bad,
            canonical_digest(lead),
            specialist_outputs=specialists,
            cross_cell_lead=lead,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        )


def test_v3_rejects_writer_dropped_hypothesis_qualification() -> None:
    _, specialists, lead, _ = _fixture_surfaces()
    hypothesis_specialists = deepcopy(specialists)
    claim = hypothesis_specialists[0]["judgment_layer"][0]
    claim["epistemic_status"] = "hypothesis"
    claim["support_fact_ids"] = []
    claim["context_refs"] = ["graph:1"]
    claim["qualification"] = "关系图谱仅为待验证假设"
    writer = _writer_output(hypothesis_specialists, lead)
    writer["sections"][0]["claim_renderings"][0]["epistemic_status"] = "hypothesis"
    writer["sections"][0]["claim_renderings"][0]["qualification_preserved"] = False
    with pytest.raises(ValueError, match="s3_owner_grade_writer_qualification_dropped"):
        S3ThreeCellBoundedAgentExecutor._validate_writer_output(
            writer,
            canonical_digest(lead),
            specialist_outputs=hypothesis_specialists,
            cross_cell_lead=lead,
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        )


def test_writer_v2_provider_emits_only_narrative_and_runtime_assembles_authority() -> None:
    _, specialists, lead, _ = _fixture_surfaces()
    payload = {
        "input_digest": "2" * 64,
        "specialist_heads": specialists,
        "cross_cell_lead": lead,
        "cross_cell_lead_digest": canonical_digest(lead),
    }
    _, request, binding = DeepSeekS3ThreeCellNodeExecutor._memo_writer_v2_request(
        payload
    )
    assert set(request["required_output_schema"]) == {"claim_renderings"}
    assert binding["memo_writer_transport_ref"] == (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF
    )
    provider_output = {
        "claim_renderings": [
            {
                "claim_id": claim["claim_id"],
                "analysis_text_zh_cn": f"该判断严格受上游事实与边界约束（{claim['claim_id']}）。",
            }
            for specialist in specialists
            for claim in specialist["judgment_layer"]
        ]
    }
    writer = DeepSeekS3ThreeCellNodeExecutor._assemble_memo_writer_v2_output(
        provider_output, payload
    )
    S3ThreeCellBoundedAgentExecutor._validate_writer_output(
        writer,
        canonical_digest(lead),
        specialist_outputs=specialists,
        cross_cell_lead=lead,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
    )
    assert writer["consumed_claim_surface_digest"] == canonical_digest(
        S3ThreeCellBoundedAgentExecutor._owner_grade_claim_surface(specialists)
    )
    assert writer["source_calls"] == writer["tool_calls"] == 0


def test_writer_v2_returns_closed_typed_subtype_for_unknown_claim() -> None:
    _, specialists, lead, _ = _fixture_surfaces()
    payload = {
        "input_digest": "2" * 64,
        "specialist_heads": specialists,
        "cross_cell_lead": lead,
        "cross_cell_lead_digest": canonical_digest(lead),
    }
    with pytest.raises(
        ValueError,
        match="s3_bounded_memo_writer_v2_authority_claim_ref_invalid",
    ) as error:
        DeepSeekS3ThreeCellNodeExecutor._assemble_memo_writer_v2_output(
            {
                "claim_renderings": [
                    {
                        "claim_id": "claim:unknown",
                        "analysis_text_zh_cn": "未知 Claim 不得进入本地组装。",
                    }
                    for _ in range(
                        sum(len(row["judgment_layer"]) for row in specialists)
                    )
                ]
            },
            payload,
        )
    telemetry = error.value.telemetry
    assert telemetry["failure_subtype"] == "claim_ref_invalid"
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


def test_writer_v2_admission_is_explicit_and_historical_digest_stays_unchanged() -> None:
    historical = S3ThreeCellBoundedAgentAdmission(
        admission_id="historical-writer-transport-probe",
        execution_mode="zero_call_contract_identity_probe",
    )
    assert "memo_writer_transport_ref" not in historical.digest_payload()
    repaired = S3ThreeCellBoundedAgentAdmission(
        admission_id="writer-v2-transport-probe",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V5_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V3_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF,
        execution_mode="zero_call_writer_v2_contract_probe",
    )
    repaired.assert_profile_admissible()
    assert repaired.digest_payload()["memo_writer_transport_ref"] == (
        S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V2_REF
    )


def _verifier_payload(
    cells: list[dict[str, Any]],
    specialists: list[dict[str, Any]],
    lead: dict[str, Any],
    writer: dict[str, Any],
) -> dict[str, Any]:
    return {
        "authority_surface_by_cell": {
            str(cell["program_cell_id"]): S3ThreeCellBoundedAgentExecutor._owner_grade_authority_surface(cell)
            for cell in cells
        },
        "specialist_claim_cards": {
            str(row["program_cell_id"]): {
                "fact_layer": row["fact_layer"],
                "claim_cards": row["judgment_layer"],
                "what_would_change": row["what_would_change"],
            }
            for row in specialists
        },
        "specialist_output_digests": {
            str(row["program_cell_id"]): canonical_digest(row) for row in specialists
        },
        "cross_cell_lead": lead,
        "cross_cell_lead_digest": canonical_digest(lead),
        "writer_output": writer,
        "writer_digest": canonical_digest(writer),
    }


def test_v3_rejects_verifier_input_without_full_authority_body() -> None:
    cells, specialists, lead, writer = _fixture_surfaces()
    payload = _verifier_payload(cells, specialists, lead, writer)
    del payload["authority_surface_by_cell"]
    with pytest.raises(ValueError, match="s3_owner_grade_verifier_authority_surface_missing"):
        S3ThreeCellBoundedAgentExecutor._validate_owner_grade_verifier_input(payload)


def test_v3_forbids_verifier_false_green_when_local_issue_exists() -> None:
    _, _, lead, writer = _fixture_surfaces()
    verifier = _verifier_output(lead, writer)
    with pytest.raises(
        S3VerifierStateMachineError,
        match="s3_bounded_verifier_state_machine_invalid",
    ) as caught:
        S3ThreeCellBoundedAgentExecutor._validate_verifier_output(
            verifier,
            canonical_digest(lead),
            canonical_digest(writer),
            output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V3_REF,
            local_semantic_issues=["s3_owner_grade_claim_scope_exceeds_fact_authority"],
        )
    assert (
        caught.value.telemetry["failure_subtype"]
        == "decision_findings_state_conflict"
    )


def test_v1_v2_contract_identities_remain_admissible_and_unchanged() -> None:
    assert S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF.endswith(":v1")
    assert S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF.endswith(":v2")
    for contract_ref in (
        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_REF,
        S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V2_REF,
    ):
        S3ThreeCellBoundedAgentAdmission(
            admission_id=f"historical-contract-probe:{contract_ref}",
            output_contract_ref=contract_ref,
            execution_mode="zero_call_contract_identity_probe",
        ).assert_profile_admissible()
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == (
        "pass_zero_call_v3_contract_and_earliest_owner_fixtures_verified_fresh_agent_proof_pending"
    )
    assert set(result["observed_counts"].values()) == {0}
    assert result["deterministic_proof"]["negative_fixture_count"] == 10
    assert backlog["next_action"][
        "S3_T09_owner_grade_semantic_actionability_zero_call_repair_result_ref"
    ] == (
        "configs/releases/"
        "fin_ia_0_1_s3_t09_owner_grade_semantic_actionability_"
        "zero_call_repair_v1_0.json"
    )
    assert backlog["next_action"]["deterministic_baseline_materialization_authorized"] is True
    assert backlog["next_action"]["fresh_v3_agent_proof_decision_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issuance_authorized"] is True
    assert backlog["next_action"]["fresh_v3_exact_admission_issued"] is True
    assert backlog["next_action"]["fresh_v3_exact_live_execution_authorized"] is True
    assert backlog["next_action"]["agent_rerun_authorized"] is False
