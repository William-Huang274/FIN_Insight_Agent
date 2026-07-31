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

from sec_agent.memo_llm import (
    S3ThreeCellPresentationPackVersion,
    consume_s3_three_cell_presentation_pack,
)
from tests.contract.test_fin_0_1_s3_t04_financial_numeric_fundamental_pack import (
    _run_payload,
)


RELEASES = ROOT / "configs" / "releases"
T07 = (
    RELEASES
    / "fin_ia_0_1_s3_t07_three_cell_workpaper_report_trace_review_surface_v1_0.json"
)
BACKLOG = RELEASES / "fin_ia_0_1_program_release_backlog_v2_0.json"
FRONTEND = ROOT / "apps" / "workbench" / "frontend" / "vite" / "src"


def _pack(payload: dict[str, Any]) -> S3ThreeCellPresentationPackVersion:
    return S3ThreeCellPresentationPackVersion.model_validate(
        payload["s3_three_cell_presentation_pack"]
    )


def _consume(
    payload: dict[str, Any], pack: S3ThreeCellPresentationPackVersion
) -> tuple[dict[str, Any], ...]:
    return consume_s3_three_cell_presentation_pack(
        pack,
        runtime_plan=payload["s3_runtime_plan"],
        evidence_route_plan=payload["s3_evidence_route_plan"],
        financial_pack=payload["s3_financial_numeric_and_fundamental_pack"],
        graph_pack=payload["s3_bounded_graph_product_market_risk_pack"],
        judgment_pack=payload["s3_specialist_lead_cross_cell_pack"],
    )


def test_t07_contract_advances_only_to_unapproved_t08() -> None:
    contract = json.loads(T07.read_text(encoding="utf-8"))
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert contract["status"] == (
        "pass_after_independent_review_T08_ready_pending_separate_authorization"
    )
    assert contract["authority"]["S3_T07_zero_call_deterministic_presentation_authorized"] is True
    assert contract["authority"]["S3_T08_execution_authorized"] is False
    assert contract["acceptance"]["human_review_status"] == "not_performed"
    assert backlog["next_action"]["item_id"] == (
        "S3-T09-EXACT-THREE-CELL-DEEPSEEK-LIVE-EXECUTION"
    )
    assert backlog["next_action"]["S3_T08_repair_execution_authorized"] is True
    assert backlog["next_action"]["S3_T09_execution_authorized"] is False


def test_t07_runtime_commits_three_exact_presentation_artifacts_on_same_run(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    pack = _pack(payload)
    manifest = payload["artifact_manifest"]
    assert set(manifest) == {
        "deterministic_research_result",
        "s3_three_cell_workpaper",
        "s3_three_cell_report",
        "s3_three_cell_trace_review",
    }
    assert pack.research_run_id == payload["research_run_id"]
    assert pack.workpaper.artifact_ref == manifest["s3_three_cell_workpaper"]
    assert pack.report.artifact_ref == manifest["s3_three_cell_report"]
    assert pack.trace_review.artifact_ref == manifest["s3_three_cell_trace_review"]
    assert pack.report.workpaper_artifact_ref == pack.workpaper.artifact_ref
    assert pack.trace_review.workpaper_artifact_ref == pack.workpaper.artifact_ref
    assert pack.trace_review.report_artifact_ref == pack.report.artifact_ref


def test_t07_workpaper_exposes_exact_cell_claim_judgment_and_business_semantics(
    tmp_path: Path,
) -> None:
    pack = _pack(_run_payload(tmp_path))
    assert len(pack.surface_claims) == len(pack.workpaper.cell_sections) == 3
    by_claim = {row.surface_claim_version_ref: row for row in pack.surface_claims}
    for cell in pack.workpaper.cell_sections:
        claim = by_claim[cell.surface_claim_ref]
        assert cell.program_cell_id == claim.program_cell_id
        assert cell.specialist_judgment_ref == claim.specialist_judgment_ref
        assert cell.evidence_refs == claim.evidence_refs
        assert cell.numeric_refs == claim.numeric_refs
        assert cell.graph_drilldown.graph_status == "context_only_not_evidence"
        assert cell.graph_drilldown.automatic_new_research is False
        assert cell.gaps and cell.what_would_change and cell.repair_ticket_refs
        assert cell.stop_semantic.startswith("typed_stop_")
    demand, value, risk = pack.surface_claims
    assert demand.evidence_refs == risk.evidence_refs == ()
    assert len(value.numeric_refs) == 2
    assert "incremental_profit_attribution_unavailable" in value.stop_semantic


def test_t07_writer_consumes_only_adjudicated_heads_and_preserves_gaps(
    tmp_path: Path,
) -> None:
    pack = _pack(_run_payload(tmp_path))
    report = pack.report
    assert len(report.sections) == 3
    assert len(report.adjudicated_input_refs) == 4
    assert report.presentation_gaps
    assert report.writer_source_authority is False
    assert report.writer_retrieval_authority is False
    assert report.writer_external_tool_authority is False
    assert report.raw_candidate_consumption is False
    assert report.model_writer_executed is False
    assert report.release_claim_authorized is False
    assert all(row.surface_claim_ref for row in report.sections)
    assert all(row.specialist_judgment_ref for row in report.sections)


def test_t07_trace_verifier_and_human_review_bind_exact_identity_without_signing(
    tmp_path: Path,
) -> None:
    pack = _pack(_run_payload(tmp_path))
    trace = pack.trace_review
    binding = trace.review_binding
    assert len(trace.nodes) == 13
    assert len(trace.edges) == 14
    assert len(binding.artifact_refs) == len(binding.bound_content_digests) == 3
    assert binding.execution_profile_version_ref == pack.execution_profile_version_ref
    assert binding.analysis_as_of
    assert binding.input_head_digest and binding.verifier_input_digest
    assert {row.layer for row in binding.findings} == {
        "deterministic_integrity",
        "semantic",
        "financial",
        "visual",
    }
    assert len(binding.review_targets) == 3
    assert all(len(row.allowed_review_actions) == 6 for row in binding.review_targets)
    assert binding.human_review_status == binding.human_decision == "not_performed"
    assert binding.exact_digest_confirmation is False
    assert binding.machine_verifier_is_human_acceptance is False


def test_t07_consumer_recompiles_nested_pack_and_rejects_tamper(
    tmp_path: Path,
) -> None:
    payload = _run_payload(tmp_path)
    pack = _pack(payload)
    assert payload["s3_presentation_consumption_receipts"] == list(
        _consume(payload, pack)
    )
    assert {row["target_node"] for row in _consume(payload, pack)} == {
        "memo_writer",
        "verifier",
        "workbench",
    }
    tampered = deepcopy(pack.model_dump(mode="json"))
    tampered["workpaper"]["cell_sections"][0]["direct_answer"] = (
        "Candidate context proves durable demand."
    )
    with pytest.raises(ValueError, match="s3_presentation_pack_recompile_mismatch"):
        _consume(payload, S3ThreeCellPresentationPackVersion.model_validate(tampered))


def test_t07_workbench_source_consumes_exact_pack_and_exposes_review_semantics() -> None:
    source = (FRONTEND / "app" / "WorkbenchNext.tsx").read_text(encoding="utf-8")
    api = (FRONTEND / "api" / "execution.ts").read_text(encoding="utf-8")
    css = (FRONTEND / "app" / "workbench-next.css").read_text(encoding="utf-8")
    for token in (
        "s3_three_cell_presentation_pack",
        "S3ExactWorkpaperSurface",
        "Graph drill-down",
        "automatic_new_research",
        "repair_ticket_refs",
        "stop_semantic",
        "S3ExactReportSurface",
        "S3ExactReviewSurface",
        "human_review_status",
        "Machine verification is not human acceptance",
    ):
        assert token in source or token in api
    assert ".next-s3-binding-strip" in css
    assert ".next-s3-review-targets" in css
