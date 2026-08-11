from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3_THREE_CELL_PROGRAM_CELL_IDS,
    BoundedAgentAdmission,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
)
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import (
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-s3-t08-adapter"
PROJECT_ID = "project-fin01-s3-t08-adapter"
ACTOR_ID = "analyst-fin01-s3-t08-adapter"
PERMISSIONS = frozenset(
    {
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    }
)
RESULT = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s3_t08_three_cell_bounded_agent_adapter_repair_v1_0.json"
)
BACKLOG = ROOT / "configs" / "releases" / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


class _ReadinessNodeExecutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute_node(
        self,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> Mapping[str, Any]:
        del admission
        self.calls.append(
            {
                "node_id": node_id,
                "payload": dict(payload),
                "run_identity": dict(run_identity),
            }
        )
        if node_id.startswith("domain_specialist:"):
            cell_input = dict(payload["cell_input"])
            cell_id = str(cell_input["program_cell_id"])
            numeric_refs = list(cell_input["authority_refs"]["numeric_refs"])
            facts = (
                [
                    {
                        "fact_id": f"fact:{cell_id}:company-total-numeric",
                        "statement": "Exact company-total numeric input is available within its stated boundary.",
                        "support_type": "Numeric",
                        "support_refs": numeric_refs[:1],
                        "boundary": "Company-total fact only; no product or incremental-profit attribution.",
                    }
                ]
                if numeric_refs
                else []
            )
            output: dict[str, Any] = {
                "program_cell_id": cell_id,
                "fact_layer": facts,
                "explanation_layer": ["The supplied scoped inputs preserve the authority boundary."],
                "judgment_layer": ["No conclusion may exceed the admitted Evidence and Numeric refs."],
                "remaining_gaps": ["Independent exact evidence remains required."],
                "what_would_change": ["Admit an exact source or numeric input through its owner."],
                "terminal_class": (
                    "bounded_company_total_answer_with_typed_attribution_gap"
                    if numeric_refs
                    else "typed_cannot_infer"
                ),
            }
        elif node_id == "research_lead":
            specialist_digests = dict(payload["specialist_output_digests"])
            output = {
                "cell_heads": [
                    {
                        "program_cell_id": cell_id,
                        "specialist_output_digest": specialist_digests[cell_id],
                    }
                    for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS
                ],
                "cross_cell_dependencies": [
                    "Demand durability and bottleneck impact remain prerequisites for an Alpha conclusion."
                ],
                "conflict_adjudications": [
                    "Company-total numeric facts do not resolve product value capture."
                ],
                "variant_view": "Company-total profitability is exact while all three decision-cell attribution gaps remain explicit.",
                "remaining_gaps": ["No market-consensus or independent deployment evidence is admitted."],
            }
        elif node_id == "memo_writer":
            output = {
                "title_zh_cn": "NVDA 三单元内部研究草稿",
                "executive_summary_zh_cn": "公司整体数值可核验，但需求、产品归因及瓶颈影响仍有限定缺口。",
                "sections": [
                    {
                        "program_cell_id": cell_id,
                        "content_zh_cn": "仅陈述已裁决的事实、判断与 cannot-infer 边界。",
                    }
                    for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS
                ],
                "limitations_zh_cn": ["不得把 Candidate、Graph context 或公司整体数值扩写为产品结论。"],
                "consumed_lead_digest": str(payload["cross_cell_lead_digest"]),
                "source_calls": 0,
                "tool_calls": 0,
            }
        elif node_id == "verifier":
            output = {
                "findings": [
                    {
                        "layer": layer,
                        "status": (
                            "review_required" if layer == "visual_delivery" else "pass"
                        ),
                        "issues": (
                            ["Browser and human visual acceptance are outside this fixture."]
                            if layer == "visual_delivery"
                            else []
                        ),
                    }
                    for layer in S3_FOUR_LAYER_VERIFIER_LAYERS
                ],
                "bound_lead_digest": str(payload["cross_cell_lead_digest"]),
                "bound_writer_digest": str(payload["writer_digest"]),
                "decision": "accept_for_internal_review",
            }
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
                "agent_definition_version_ref": f"fixture:{node_id}:v1",
                "skill_pack_version_ref": f"fixture:{node_id}:v1",
                "fixture_only": True,
            },
        }


def _execute_zero_call_three_cell_profile(
    tmp_path: Path,
) -> tuple[CaseService, _ReadinessNodeExecutor, dict[str, Any]]:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=ROOT
    )
    node_executor = _ReadinessNodeExecutor()
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s3-t08-three-cell-readiness-probe-not-live-admission",
        execution_mode="zero_call_three_cell_adapter_readiness_probe",
    )
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=case_service,
        s3_three_cell_bounded_agent_admission=admission,
        s3_three_cell_bounded_agent_executor=S3ThreeCellBoundedAgentExecutor(
            node_executor
        ),
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/cases",
            headers=_headers(),
            json={
                "query": "Execute the FIN 0.1 NVDA S3 T08 three-cell adapter readiness fixture",
                "as_of": "2026-07-21T00:00:00Z",
                "language": "en",
                "source_policy_ref": "fixture:internal-only",
                "idempotency_key": "t08-three-cell-adapter-case",
            },
        )
        assert created.status_code == 202, created.text
        case = created.json()
        compiled = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/compile",
            headers=_headers(),
            json={
                "expected_case_version": case["case_version"],
                "expected_summary_version": case["summary_version"],
                "compiler_policy_ref": "fixture:p36-three-cell-v1",
                "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t08-three-cell-adapter-compile",
            },
        )
        assert compiled.status_code == 202, compiled.text
        accepted = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
            headers=_headers(),
            json={
                "decision": "accept",
                "expected_case_version": case["case_version"],
                "expected_decision_surface_contract_version": compiled.json()["contract_version"],
                "expected_checkpoint_version": compiled.json()["checkpoint_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t08-three-cell-adapter-accept",
            },
        )
        assert accepted.status_code == 202, accepted.text
        plan = accepted.json()
        executed = client.post(
            f"/api/v1/cases/{case['case_id']}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                "expected_case_version": case["case_version"],
                "input_head_digest": canonical_digest((plan["contract_version_id"],)),
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t08-three-cell-adapter-execute",
            },
        )
        assert executed.status_code == 202, executed.text
    return case_service, node_executor, case


def _artifact_payloads(case_service: CaseService, case_id: str) -> dict[str, dict[str, Any]]:
    rows = case_service._facade.store.list_latest(
        "canonical_artifact_versions", case_id=case_id
    )
    return {
        str(row["artifact_type"]): case_service._facade.object_store.get_json(
            row["object_key"], expected_digest=row["object_digest"]
        )
        for row in rows
    }


def test_repair_result_history_is_preserved_after_T09_decision_advances_backlog() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert result["status"] == (
        "pass_adapter_repair_and_readiness_rerun_T09_ready_pending_separate_exact_admission_authority"
    )
    assert result["readiness_rerun"]["owned_three_cell_profile_input_output_adapter_gap_closed"] is True
    assert result["readiness_rerun"]["T09_admission_issued"] is False
    assert result["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_business_writes": 0,
        "human_review_writes": 0,
        "new_exact_admissions": 0,
        "paid_runs": 0,
    }
    assert result["next_action"] == "S3-T09-EXACT-THREE-CELL-LIVE-ADMISSION-DECISION"
    assert backlog["next_action"]["S3_T08_result_ref"] == (
        "configs/releases/fin_ia_0_1_s3_t08_three_cell_bounded_agent_adapter_repair_v1_0.json"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_decision_authorized"] is True
    assert backlog["next_action"]["S3_T09_admission_issuance_authorized"] is True
    recorded: list[dict[str, Any]] = []
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            recorded.append(json.loads(line))
    repaired = result["root_cause_reconciliation"]["adapter_blocker_count_before_repair"]
    assert repaired == 12
    relevant = [
        row
        for row in recorded
        if row.get("recorded_at") == "2026-07-22T01:30:00+08:00"
    ]
    assert len(relevant) == repaired
    assert all(row["full_chain_blocker"] is True for row in relevant)
    assert all(
        row["verification_result"]["blocks_current_exact_live_readiness"] is False
        for row in relevant
    )


def test_s3_profile_is_versioned_without_mutating_s2_single_cell_contract() -> None:
    s2 = BoundedAgentAdmission(
        admission_id="fin01-s3-t08-s2-compatibility-probe",
        execution_mode="zero_call_probe",
        maximum_cell_count=3,
    )
    with pytest.raises(ValueError, match="bounded_admission_single_cell_required"):
        s2.assert_profile_admissible()
    s3 = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s3-t08-three-cell-readiness-probe-not-live-admission",
        execution_mode="zero_call_three_cell_adapter_readiness_probe",
    )
    s3.assert_profile_admissible()
    assert s3.execution_profile_version_ref == S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
    assert s3.program_cell_ids == S3_THREE_CELL_PROGRAM_CELL_IDS
    assert s3.maximum_cell_count == 3


def test_s3_runtime_executes_exact_three_specialists_lead_writer_verifier(
    tmp_path: Path,
) -> None:
    case_service, node_executor, case = _execute_zero_call_three_cell_profile(tmp_path)
    payloads = _artifact_payloads(case_service, case["case_id"])
    assert set(payloads) == set(BOUNDED_AGENT_ARTIFACT_TYPES)
    manifest = payloads["bounded_agent_manifest"]
    assert manifest["execution_profile_version_ref"] == S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
    assert manifest["program_cell_ids"] == list(S3_THREE_CELL_PROGRAM_CELL_IDS)
    assert manifest["node_topology"] == [
        *(f"domain_specialist:{cell_id}" for cell_id in S3_THREE_CELL_PROGRAM_CELL_IDS),
        "research_lead",
        "memo_writer",
        "verifier",
    ]
    assert [row["node_id"] for row in node_executor.calls] == manifest["node_topology"]
    assert manifest["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "evaluation_evidence_promotions": 0,
    }
    trace = payloads["bounded_agent_trace"]
    assert tuple(trace["lineage"]) == (
        "T02_runtime_plan",
        "T03_evidence_route_plan",
        "T04_financial_pack",
        "T05_graph_pack",
        "T06_judgment_contract",
        "T07_presentation_contract",
    )
    assert all(row["version_ref"] and row["digest"] for row in trace["lineage"].values())


def test_s3_writer_and_verifier_preserve_no_source_and_four_layer_boundaries(
    tmp_path: Path,
) -> None:
    case_service, node_executor, case = _execute_zero_call_three_cell_profile(tmp_path)
    payloads = _artifact_payloads(case_service, case["case_id"])
    report = payloads["bounded_agent_report"]
    verification = payloads["bounded_agent_verification"]
    comparison = payloads["agent_fallback_comparison"]
    assert report["writer_source_calls"] == report["writer_tool_calls"] == 0
    assert [row["layer"] for row in verification["verification"]["findings"]] == list(
        S3_FOUR_LAYER_VERIFIER_LAYERS
    )
    assert verification["machine_verifier_is_human_acceptance"] is False
    assert verification["verification"]["findings"][-1]["status"] == "review_required"
    assert comparison["paired_baseline_contract"]["automatic_fallback_allowed"] is False
    assert comparison["baseline_output_body_exposed_to_agent"] is False
    specialist_payloads = [
        row["payload"]
        for row in node_executor.calls
        if row["node_id"].startswith("domain_specialist:")
    ]
    assert len(specialist_payloads) == 3
    assert all("specialist_judgments" not in json.dumps(row) for row in specialist_payloads)


def test_s3_exact_live_binding_is_fail_closed_until_call_budget_is_exact() -> None:
    invalid = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s3-t09-not-issued-probe",
        execution_mode="exact_live_three_cell",
        execution_enabled=True,
        case_id="case",
        case_version=1,
        as_of="2026-07-21T00:00:00Z",
        input_digest="digest",
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/beta",
        max_semantic_model_calls=5,
        max_provider_calls=5,
        max_network_calls=5,
        max_total_cost_usd=1.0,
        specialist_max_output_tokens=1,
        lead_max_output_tokens=1,
        writer_max_output_tokens=1,
        verifier_max_output_tokens=1,
    )
    with pytest.raises(ValueError, match="exact_call_budget_required"):
        invalid.assert_profile_admissible()
