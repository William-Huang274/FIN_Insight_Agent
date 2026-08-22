from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.research.multi_agent_report_authority import (
    compile_protected_report_messages,
    protected_report_draft_tool,
)
from sec_agent.research.report_boundary import (
    ReportBoundaryDispositionError,
    compile_evaluation_authority_supersession_view,
    compile_research_method_parameter_register,
    compile_report_boundary_disposition_register,
    compile_writer_successor_input_projection,
)


ROOT = Path(__file__).resolve().parents[1]


def _row() -> dict:
    return {
        "boundary_id": "BOUNDARY::S2-STALE-NUMERIC",
        "claim_area": "cash_conversion",
        "surface_paths": ["remaining_gaps[2]", "sections[3]"],
        "owner_plane": "data_infrastructure_and_tool",
        "owner_stage": "S2_to_S3",
        "information_state": "source_visible_numeric_authority_stale_downstream",
        "root_cause_zh": "数值已获权威，但旧底稿未消费新目录。",
        "artifact_refs": ["config://numeric-authority"],
        "customer_surface_disposition": "resolve_before_customer_report",
        "next_action_zh": "只重裁决受影响研究单元。",
        "true_information_boundary": False,
    }


def _compile(rows):
    return compile_report_boundary_disposition_register(
        case_key="DELL",
        source_report_ref="config://report",
        source_report_digest="a" * 64,
        rows=rows,
        recorded_at="2026-08-22T00:00:00+08:00",
    )


def test_operational_boundary_goes_to_remediation_not_customer_gap() -> None:
    result = _compile([_row()])

    assert result["summary"]["operations_remediation_count"] == 1
    assert result["summary"]["customer_boundary_count"] == 0
    assert result["summary"]["proved_information_boundary_count"] == 0
    assert result["summary"]["pre_report_blocker_count"] == 1
    assert result["summary"]["customer_report_ready"] is False


def test_unexecuted_external_route_is_current_run_uncertainty_not_true_gap() -> None:
    row = _row()
    row.update(
        {
            "boundary_id": "BOUNDARY::S1-EXTERNAL-NOT-EXHAUSTED",
            "owner_stage": "S1",
            "information_state": (
                "official_or_external_route_not_executed_or_not_terminal"
            ),
            "customer_surface_disposition": "concise_current_run_uncertainty",
            "true_information_boundary": False,
        }
    )

    result = _compile([row])

    assert result["summary"]["customer_boundary_count"] == 1
    assert result["summary"]["proved_information_boundary_count"] == 0


def test_operational_failure_cannot_be_relabelled_as_proved_gap() -> None:
    row = deepcopy(_row())
    row["customer_surface_disposition"] = "concise_proved_information_boundary"
    row["true_information_boundary"] = True

    with pytest.raises(
        ReportBoundaryDispositionError,
        match="report_boundary_true_information_state_mismatch",
    ):
        _compile([row])


def test_proved_non_disclosure_can_enter_concise_customer_register() -> None:
    row = _row()
    row.update(
        {
            "boundary_id": "BOUNDARY::TRUE-NON-DISCLOSURE",
            "owner_plane": "external_information_boundary",
            "owner_stage": "S1_GapEligibility",
            "information_state": "public_non_disclosure_proved",
            "customer_surface_disposition": "concise_proved_information_boundary",
            "true_information_boundary": True,
        }
    )

    result = _compile([row])

    assert result["summary"]["proved_information_boundary_count"] == 1


def test_current_dell_audit_separates_customer_uncertainty_from_operations() -> None:
    audit = json.loads(
        (
            ROOT
            / "configs"
            / "research"
            / "evals"
            / "fin_ia_0_1_3_dell_report_boundary_attribution_audit_v1_0.json"
        ).read_text(encoding="utf-8")
    )

    result = compile_report_boundary_disposition_register(
        case_key=audit["case_key"],
        source_report_ref=audit["source_report_ref"],
        source_report_digest=audit["source_report_digest"],
        rows=audit["rows"],
        recorded_at=audit["recorded_at"],
    )

    assert result["summary"] == {
        "boundary_statement_count": 8,
        "customer_boundary_count": 4,
        "operations_remediation_count": 4,
        "proved_information_boundary_count": 0,
        "pre_report_blocker_count": 4,
        "customer_report_ready": False,
    }


def test_current_dell_stale_balance_evaluation_is_superseded_without_agent_rerun() -> None:
    catalog = json.loads(
        (
            ROOT
            / "configs"
            / "research"
            / "fin_ia_0_1_3_s3_dell_multi_agent_report_authority_catalog_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    full_result = json.loads(
        (
            ROOT
            / "data"
            / "workbench_private"
            / "model_runs"
            / "fin_0_1_3_s3_dell_multi_agent_preview_writer_terminal_submission_successor_20260821"
            / "full_result.json"
        ).read_text(encoding="utf-8")
    )
    evaluation = full_result["evaluations"][0]

    refreshed = compile_evaluation_authority_supersession_view(
        authority_catalog=catalog,
        evaluation=evaluation,
        finding_claim_bindings={
            "NUM_REF_UNRESOLVED_BALANCES": [
                "WPCLAIM::E6BF4BA3210FFC734C43"
            ]
        },
    )

    assert refreshed["summary"]["superseded_finding_count"] == 1
    assert refreshed["summary"]["writer_visible_finding_count"] == (
        len(evaluation["findings"]) - 1
    )
    assert refreshed["superseded_findings"][0]["finding_code"] == (
        "NUM_REF_UNRESOLVED_BALANCES"
    )
    visible_codes = {
        row["finding_code"] for row in refreshed["writer_visible_findings"]
    }
    assert "NUM_REF_UNRESOLVED_ADJ_FCF" in visible_codes
    assert "NUM_REF_UNRESOLVED_NET_INCOME_AND_RECON" in visible_codes


def test_evaluation_supersession_rejects_claim_without_new_authority() -> None:
    catalog = json.loads(
        (
            ROOT
            / "configs"
            / "research"
            / "fin_ia_0_1_3_s3_dell_multi_agent_report_authority_catalog_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    full_result = json.loads(
        (
            ROOT
            / "data"
            / "workbench_private"
            / "model_runs"
            / "fin_0_1_3_s3_dell_multi_agent_preview_writer_terminal_submission_successor_20260821"
            / "full_result.json"
        ).read_text(encoding="utf-8")
    )

    with pytest.raises(
        ReportBoundaryDispositionError,
        match="evaluation_supersession_authority_missing",
    ):
        compile_evaluation_authority_supersession_view(
            authority_catalog=catalog,
            evaluation=full_result["evaluations"][0],
            finding_claim_bindings={
                "NUM_REF_UNRESOLVED_ADJ_FCF": [
                    "WPCLAIM::6989AE691B45DD961377"
                ]
            },
        )


def test_current_dell_writer_projection_removes_stale_state_and_method_gaps() -> None:
    catalog = json.loads(
        (
            ROOT
            / "configs"
            / "research"
            / "fin_ia_0_1_3_s3_dell_multi_agent_report_authority_catalog_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    full_result = json.loads(
        (
            ROOT
            / "data"
            / "workbench_private"
            / "model_runs"
            / "fin_0_1_3_s3_dell_multi_agent_preview_writer_terminal_submission_successor_20260821"
            / "full_result.json"
        ).read_text(encoding="utf-8")
    )
    evaluation = full_result["evaluations"][0]
    workpapers = full_result["final_workpapers"]
    supersession = compile_evaluation_authority_supersession_view(
        authority_catalog=catalog,
        evaluation=evaluation,
        finding_claim_bindings={
            "NUM_REF_UNRESOLVED_BALANCES": [
                "WPCLAIM::E6BF4BA3210FFC734C43"
            ]
        },
    )
    method_register = json.loads(
        (
            ROOT
            / "configs"
            / "research"
            / "fin_ia_0_1_3_s3_dell_research_method_parameter_register_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    assert method_register == compile_research_method_parameter_register(
        case_key=method_register["case_key"],
        research_as_of=method_register["research_as_of"],
        parameters=method_register["parameters"],
        recorded_at=method_register["recorded_at"],
    )

    projection = compile_writer_successor_input_projection(
        workpapers=workpapers,
        authority_catalog=catalog,
        evaluation_supersession_view=supersession,
        research_method_parameter_register=method_register,
    )

    visible_codes = {
        row["finding_code"]
        for row in projection["writer_visible_evaluation"]["findings"]
    }
    visible_gap_refs = {
        row["gap_ref"]
        for row in projection["writer_visible_authority_catalog"][
            "gap_authority"
        ]
    }
    counter = next(
        row
        for row in projection["writer_visible_workpapers"]
        if row["agent_id"] == "AGENT::COUNTEREVIDENCE"
    )
    counter_receipt = next(
        row
        for row in projection["workpaper_projection_receipts"]
        if row["agent_id"] == "AGENT::COUNTEREVIDENCE"
    )

    assert "NUM_REF_UNRESOLVED_BALANCES" not in visible_codes
    assert "NUM_REF_UNRESOLVED_ADJ_FCF" in visible_codes
    assert "NUM_REF_UNRESOLVED_NET_INCOME_AND_RECON" in visible_codes
    assert "GAP::04EDD7700A1409F8" not in visible_gap_refs
    assert "GAP::B070D38D076F342B" not in visible_gap_refs
    assert counter["remaining_gap_refs"] == []
    assert counter_receipt["source_research_artifact_mutated"] is False
    assert counter_receipt["writer_view_method_content_omitted"] is True
    assert projection["summary"] == {
        "source_workpaper_count": 6,
        "superseded_evaluation_finding_count": 1,
        "omitted_research_method_gap_count": 2,
        "omitted_research_method_evaluation_finding_count": 3,
        "omitted_research_method_claim_count": 1,
        "writer_visible_gap_count": 9,
        "agent_re_adjudication_required": False,
    }
    messages = compile_protected_report_messages(
        workpapers=projection["writer_visible_workpapers"],
        evaluation=projection["writer_visible_evaluation"],
        authority_catalog=projection["writer_visible_authority_catalog"],
    )
    tool = protected_report_draft_tool(
        authority_catalog=projection["writer_visible_authority_catalog"]
    )
    serialized_writer_input = json.dumps(
        [*messages, tool], ensure_ascii=False, sort_keys=True
    )
    assert "GAP::04EDD7700A1409F8" not in serialized_writer_input
    assert "GAP::B070D38D076F342B" not in serialized_writer_input
    assert "WPCLAIM::2F796E4F60AFD3F7D94D" not in serialized_writer_input
    assert "no invalidation thresholds have been frozen" not in serialized_writer_input
    assert workpapers[-1]["remaining_gap_refs"] == [
        "GAP::04EDD7700A1409F8",
        "GAP::B070D38D076F342B",
    ]
