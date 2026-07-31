from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.execution_service import VT1_WORK_UNIT_TYPE
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.parser_numeric import (
    ParserNumericError,
    S3FinancialNumericAndFundamentalPackVersion,
    consume_s3_financial_numeric_and_fundamental_pack,
    plan_s3_numeric_correction_invalidation,
)


RELEASES = ROOT / "configs" / "releases"
T04 = (
    RELEASES
    / "fin_ia_0_1_s3_t04_financial_numeric_fundamental_pack_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
ROOT_CAUSES = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"

TENANT_ID = "tenant-fin01-s3-t04"
PROJECT_ID = "project-fin01-s3-t04"
ACTOR_ID = "analyst-fin01-s3-t04"
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


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _run_payload(tmp_path: Path) -> dict[str, Any]:
    case_service = CaseService.for_fixture_root(
        tmp_path / "canonical-runtime", repo_root=ROOT
    )
    app = create_app(tmp_path / "workbench.sqlite", p02_case_service=case_service)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/cases",
            headers=_headers(),
            json={
                "query": "Execute the FIN 0.1 NVDA three-cell T04 numeric fixture",
                "as_of": "2026-07-21T00:00:00Z",
                "language": "en",
                "source_policy_ref": "fixture:internal-only",
                "idempotency_key": "t04-case",
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
                "idempotency_key": "t04-compile",
            },
        )
        assert compiled.status_code == 202, compiled.text
        accepted = client.post(
            f"/api/v1/cases/{case['case_id']}/planning/checkpoint",
            headers=_headers(),
            json={
                "decision": "accept",
                "expected_case_version": case["case_version"],
                "expected_decision_surface_contract_version": compiled.json()[
                    "contract_version"
                ],
                "expected_checkpoint_version": compiled.json()["checkpoint_version"],
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t04-accept",
            },
        )
        assert accepted.status_code == 202, accepted.text
        plan = accepted.json()
        executed = client.post(
            f"/api/v1/cases/{case['case_id']}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": VT1_WORK_UNIT_TYPE,
                "expected_case_version": case["case_version"],
                "input_head_digest": canonical_digest(
                    (plan["contract_version_id"],)
                ),
                "actor_ref": ACTOR_ID,
                "idempotency_key": "t04-execute",
            },
        )
        assert executed.status_code == 202, executed.text
    artifact = case_service._facade.store.list_latest(
        "canonical_artifact_versions", case_id=case["case_id"]
    )[0]
    return case_service._facade.object_store.get_json(
        artifact["object_key"], expected_digest=artifact["object_digest"]
    )


def _latest_root_causes() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line in ROOT_CAUSES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["issue_id"]] = row
    return latest


def test_t04_contract_advances_only_to_unapproved_t05() -> None:
    contract = json.loads(T04.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    roots = _latest_root_causes()
    assert contract["status"] == (
        "pass_after_independent_review_T05_ready_pending_separate_authorization"
    )
    assert contract["authority"]["S3_T04_zero_call_deterministic_fixture_authorized"] is True
    assert contract["authority"]["S3_T05_execution_authorized"] is False
    assert contract["implementation"]["selected_financial_row_count"] == 3
    assert contract["implementation"]["derived_metric_count"] == 2
    assert contract["method_to_runtime"]["method_id"] == "three_statement_peer_panel"
    assert contract["method_to_runtime"]["full_method_claimed_active_for_S3"] is False
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-LIVE-EXECUTION"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is False
    for issue_id in (
        "RC-P36-023-foundation-financials-exist-but-business-line-economics-and-numeric-sanity-promotion-gap",
        "RC-P36-025-fundamental-specialist-input-pack-not-decision-cell-ready",
    ):
        assert roots[issue_id]["verification_result"]["runtime_injected"] is True
        assert roots[issue_id]["verification_result"]["node_level_consumed"] is True


def test_t04_runtime_persists_and_consumes_exact_pack(tmp_path: Path) -> None:
    payload = _run_payload(tmp_path)
    runtime_plan = payload["s3_runtime_plan"]
    evidence_plan = payload["s3_evidence_route_plan"]
    pack = S3FinancialNumericAndFundamentalPackVersion.model_validate(
        payload["s3_financial_numeric_and_fundamental_pack"]
    )
    receipts = consume_s3_financial_numeric_and_fundamental_pack(
        pack,
        runtime_plan_version_ref=runtime_plan["runtime_plan_version_ref"],
        runtime_plan_digest=runtime_plan["runtime_plan_digest"],
        evidence_route_plan=evidence_plan,
    )
    assert payload["s3_financial_numeric_consumption_receipts"] == list(receipts)
    assert len(receipts) == 3
    assert pack.research_run_id == runtime_plan["research_run_id"]
    assert pack.financial_route_id == "local_gold_sql_financial_table"
    assert pack.local_financial_route_read_count == 1
    assert {
        pack.model_calls,
        pack.provider_calls,
        pack.execution_network_calls,
        pack.source_network_calls,
        pack.external_tool_calls,
        pack.live_business_writes,
        pack.runtime_evidence_promotions,
        pack.canonical_head_invalidations,
    } == {0}


def test_t04_rows_use_exact_cell_entity_segment_period_currency_unit_and_label(
    tmp_path: Path,
) -> None:
    pack = S3FinancialNumericAndFundamentalPackVersion.model_validate(
        _run_payload(tmp_path)["s3_financial_numeric_and_fundamental_pack"]
    )
    assert [row.selector.metric_family for row in pack.selected_financial_rows] == [
        "revenue",
        "gross_profit",
        "operating_income",
    ]
    assert {row.selector.entity_ref for row in pack.selected_financial_rows} == {
        "NVDA"
    }
    assert {row.selector.segment_ref for row in pack.selected_financial_rows} == {
        "__company_total__"
    }
    assert {row.selector.period for row in pack.selected_financial_rows} == {
        "FY2025-FY"
    }
    assert {row.selector.currency for row in pack.selected_financial_rows} == {
        "USD"
    }
    assert {row.selector.unit for row in pack.selected_financial_rows} == {"USD"}
    assert [row.selector.row_label for row in pack.selected_financial_rows] == [
        "Revenues",
        "Gross Profit",
        "Operating Income (Loss)",
    ]
    assert all(row.evidence_ref for row in pack.selected_financial_rows)


def test_t04_derived_metrics_persist_formula_inputs_evidence_rounding_and_boundary(
    tmp_path: Path,
) -> None:
    pack = S3FinancialNumericAndFundamentalPackVersion.model_validate(
        _run_payload(tmp_path)["s3_financial_numeric_and_fundamental_pack"]
    )
    metrics = {row.metric_family: row for row in pack.derived_metrics}
    assert metrics["gross_margin"].result_value == "74.99"
    assert metrics["operating_margin"].result_value == "62.42"
    assert metrics["gross_margin"].formula == "gross_profit/revenue*100"
    assert metrics["operating_margin"].formula == "operating_income/revenue*100"
    assert all(row.rounding_rule == "decimal_half_up_2dp" for row in metrics.values())
    assert all(len(row.inputs) == len(row.evidence_refs) == 2 for row in metrics.values())
    assert all(row.support_boundary and row.cannot_support for row in metrics.values())
    assert all(row.writer_citable is False for row in metrics.values())


def test_t04_unavailable_value_capture_is_typed_cannot_infer(tmp_path: Path) -> None:
    pack = S3FinancialNumericAndFundamentalPackVersion.model_validate(
        _run_payload(tmp_path)["s3_financial_numeric_and_fundamental_pack"]
    )
    cells = {row.program_cell_id: row for row in pack.fundamental_decision_cells}
    value = cells["value_and_profit_capture"]
    assert value.specialist_input_eligible is True
    assert value.availability == (
        "bounded_company_total_numeric_support_segment_profit_unattributed"
    )
    assert "data_center_or_accelerator_segment_margin_not_disclosed" in (
        value.typed_cannot_infer
    )
    assert all(
        row.narrative_fill_authorized is False
        for row in pack.fundamental_decision_cells
    )
    assert cells["demand_authenticity_and_sustainability"].selected_financial_row_refs == ()
    assert cells[
        "bottleneck_counterevidence_and_what_would_change"
    ].derived_metric_refs == ()


def test_t04_numeric_correction_invalidates_only_dependency_closure_and_tamper_fails(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    runtime_plan = payload["s3_runtime_plan"]
    evidence_plan = payload["s3_evidence_route_plan"]
    pack = S3FinancialNumericAndFundamentalPackVersion.model_validate(
        payload["s3_financial_numeric_and_fundamental_pack"]
    )
    impact = pack.correction_impact
    invalidated = {
        row.dependency_type for row in impact.invalidated_downstream_refs
    }
    preserved = {row.dependency_type for row in impact.preserved_downstream_refs}
    assert invalidated == preserved == {"claim", "judgment", "report"}
    assert len(impact.invalidated_derived_metric_refs) == 1
    assert len(impact.preserved_derived_metric_refs) == 1
    assert impact.invalidated_derived_metric_refs != impact.preserved_derived_metric_refs
    assert plan_s3_numeric_correction_invalidation(
        selected_rows=pack.selected_financial_rows,
        derived_metrics=pack.derived_metrics,
        corrected_financial_row_ref=impact.corrected_financial_row_ref,
    ) == impact

    tampered_metric = pack.derived_metrics[0].model_copy(update={"result_value": "99.99"})
    tampered = pack.model_copy(
        update={"derived_metrics": (tampered_metric, pack.derived_metrics[1])}
    )
    with pytest.raises(
        ParserNumericError, match="s3_financial_pack_digest_or_identity_mismatch"
    ):
        consume_s3_financial_numeric_and_fundamental_pack(
            tampered,
            runtime_plan_version_ref=runtime_plan["runtime_plan_version_ref"],
            runtime_plan_digest=runtime_plan["runtime_plan_digest"],
            evidence_route_plan=evidence_plan,
        )
