from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PACK = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_source_grounded_input_pack_v1_0.json"
)
PLANNING_PROFILE = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_canonical_planning_profile_v1_0.json"
)
DECISION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_source_grounded_input_materialization_"
    "and_fresh_proof_decision_v1_0.json"
)
PROSPECTIVE_ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t04_dell_fresh_exact_admission_v1_0.json"
)
CANONICAL_DATABASE = (
    ROOT
    / ".codex_runtime"
    / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
    / "canonical-runtime"
    / "canonical.sqlite"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_rows(table: str, case_id: str) -> list[dict]:
    connection = sqlite3.connect(CANONICAL_DATABASE)
    try:
        return [
            json.loads(payload_json)
            for (payload_json,) in connection.execute(
                f"select payload_json from {table} where case_id = ?",
                (case_id,),
            )
        ]
    finally:
        connection.close()


def test_all_dell_routes_executed_and_only_issuer_bound_rows_promoted() -> None:
    pack = _load(SOURCE_PACK)
    receipts = pack["route_execution_receipts"]
    assert pack["case_ticker"] == "DELL"
    assert pack["issuer_identifier"] == "CIK0001571996"
    assert len(receipts) == 11
    assert len({row["route_id"] for row in receipts}) == 11
    assert all(
        row["route_execution_status"] != "planned_not_executed"
        and row["fetch_status"] == "success"
        and row["source_snapshot_ref"]
        and row["route_receipt_ref"]
        for row in receipts
    )
    assert all(
        row["entity_ref"] == "DELL"
        and row["source_url"]
        and row["citation"]
        and row["parser_lineage"]["source_snapshot_ref"]
        for row in pack["evidence_rows"]
    )
    assert all(
        row["entity_ref"] == "DELL"
        and row["exact_value_authority"] is True
        and row["source_coordinate"]
        and row["period"]
        and row["unit"]
        for row in pack["numeric_rows"]
    )


def test_graph_is_context_only_and_product_profit_remains_typed_gap() -> None:
    pack = _load(SOURCE_PACK)
    assert len(pack["graph_edges"]) == 4
    assert all(
        row["graph_edge_is_direct_evidence"] is False
        for row in pack["graph_edges"]
    )
    gap_codes = {row["gap_code"] for row in pack["typed_gaps"]}
    assert {
        "cannot_infer_AI_or_server_specific_gross_or_operating_profit",
        "cannot_infer_order_or_backlog_to_revenue_conversion",
        "cannot_infer_independent_counterevidence",
    }.issubset(gap_codes)
    assert all(
        "AI_server" in row["cannot_support"]
        or "customer_allocation" in row["cannot_support"]
        for row in pack["numeric_rows"]
    )


def test_pdf_snapshots_bind_full_document_hash_and_page_locators() -> None:
    snapshots = {
        row["source_id"]: row for row in _load(SOURCE_PACK)["source_snapshots"]
    }
    assert snapshots["dell_fy26_results_pdf"]["full_document_sha256"] == (
        "17be3981929167a2c6033a75abe24159e4de624bbbb7261b66fd8b189680e2f9"
    )
    assert snapshots["dell_q1_fy27_earnings_exhibit_pdf"][
        "full_document_sha256"
    ] == "e8e41fb7b68d730f9c966f1213adb1838cd30aaf3a4a6ad745b57f7e9e30cb9e"
    assert "PDF pages" in snapshots["dell_fy26_results_pdf"]["locator"]
    assert "PDF pages" in snapshots[
        "dell_q1_fy27_earnings_exhibit_pdf"
    ]["locator"]


def test_canonical_case_surface_and_input_head_are_materialized_without_run() -> None:
    decision = _load(DECISION)
    materialized = decision["canonical_materialization"]
    historical_counts = materialized["logical_counts"]
    case_id = materialized["case_id"]
    assert decision["status"] == (
        "pass_source_grounded_exact_input_head_materialized_"
        "fresh_proof_frozen_admission_issuance_pending"
    )
    assert materialized["planning_checkpoint_status"] == "accepted"
    assert materialized["planning_cell_count"] == 3
    assert materialized["idempotent_second_materialization"] is True
    assert (
        materialized["logical_digest_after_first_materialization"]
        == materialized["logical_digest_after_second_materialization"]
    )
    assert len(_latest_rows("canonical_research_cases", case_id)) == 1
    assert len(
        _latest_rows("canonical_decision_surface_contract_versions", case_id)
    ) == 1
    assert len(
        _latest_rows("canonical_decision_surface_cell_versions", case_id)
    ) == 3
    assert historical_counts["canonical_work_units"] == 0
    assert historical_counts["canonical_attempts"] == 0
    assert historical_counts["canonical_research_run_versions"] == 0
    assert historical_counts["canonical_artifact_versions"] == 0
    assert _latest_rows("canonical_artifact_versions", case_id) == []


def test_fresh_proof_froze_an_unissued_unconsumed_exact_binding() -> None:
    decision = _load(DECISION)
    proof = decision["fresh_agent_proof"]
    prospective = proof["prospective_admission"]
    assert proof["decision"] == "frozen_unissued_unconsumed"
    assert proof["double_prepare_parity"] is True
    assert all(proof["freshness_and_nonreuse"].values())
    assert prospective["payload"]["company"] == "DELL"
    assert prospective["payload"]["case_id"] == decision[
        "canonical_materialization"
    ]["case_id"]
    assert prospective["payload"]["input_digest"] == proof["input_digest"]
    assert prospective["issued"] is False
    assert prospective["consumed"] is False
    assert prospective["execution_started"] is False
    assert prospective["prospective_admission_file_absent"] is True
    assert decision["hard_boundaries"]["model_calls"] == 0
    assert decision["hard_boundaries"]["provider_calls"] == 0
    assert decision["hard_boundaries"]["paid_calls"] == 0


def test_frozen_files_and_next_action_are_bound() -> None:
    decision = _load(DECISION)
    profile = _load(PLANNING_PROFILE)
    assert decision["source_execution"]["source_pack_sha256"] == _sha256(
        SOURCE_PACK
    )
    assert profile["planning_profile"]["exact_cell_count"] == 3
    assert decision["root_cause_disposition"]["new_status"] == (
        "closed_source_grounded_input_and_fresh_proof_repaired"
    )
    assert decision["next_action"] == (
        "S4-T04-DELL-FRESH-EXACT-ADMISSION-ISSUANCE"
    )
