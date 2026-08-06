from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_retrieval_evidence_readiness import (
    load_current_fin_0_1_2_s4_t02_readiness,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    ExactValueSqlSearchAdapter,
    LocalCaptureWriter,
    compile_executable_search_request,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (
    Fin012S4T04EvidenceError,
    _numeric_projection,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.gold_fact_signal_mart import (
    GOLD_FACT_SIGNAL_MART_SCHEMA_VERSION,
    write_gold_fact_signal_mart_sqlite,
)


ORACLE = ROOT / "tests/fixtures/fin_0_1_3/financial_semantic_truth_oracle_three_case_v1.json"
DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_financial_temporal_"
    "truth_and_time_role_repair_v1_0.json"
)
ACTIVE_SUITE = ROOT / (
    "configs/releases/fin_ia_0_1_3_repair_closeout_s1_01_active_test_suite_"
    "successor_v1_0.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reviewed_rows() -> list[dict]:
    return json.loads(ORACLE.read_text(encoding="utf-8"))["reviewed_truth_rows"]


def test_s1_01_decision_and_active_suite_are_current_digest_bound() -> None:
    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    suite = json.loads(ACTIVE_SUITE.read_text(encoding="utf-8"))
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    assert suite["suite_digest"] == canonical_digest(
        {key: value for key, value in suite.items() if key != "suite_digest"}
    )
    assert suite["decision_sha256"] == _sha(DECISION)
    for binding in decision["source_bindings"]:
        assert binding["sha256"] == _sha(ROOT / binding["ref"])
        assert binding["bytes"] == (ROOT / binding["ref"]).stat().st_size
    assert decision["root_cause_disposition"]["RC-P36-130"].startswith("closed_by_S1_01")
    assert decision["stage_truth"] == {
        "FIN_0_1_3_S1_01": "engineering_pass",
        "FIN_0_1_3_S1": "in_progress_S1_02_next",
        "FIN_0_1_3_S2_to_S5": "not_started",
        "old_FIN_0_1_2_product_acceptance_inherited": False,
        "model_or_full_chain_authorized": False,
        "release_qualified": False,
    }
    assert suite["focused_result"] == "46 passed / 1 deselected"
    assert suite["current_DELL_financial_temporal_truth_pass"] is True


def _gold_row(reviewed: dict, *, suffix: str = "reviewed") -> dict:
    case_key = str(reviewed["case_key"])
    return {
        "gold_row_id": f"fin013:s1-01:{case_key}:revenue:{suffix}",
        "schema_version": GOLD_FACT_SIGNAL_MART_SCHEMA_VERSION,
        "generated_at": "2026-08-06T00:00:00Z",
        "source_rowset_path": "fin_0_1_3_s1_01_reviewed_runtime_rows.jsonl",
        "source_row_id": str(reviewed["source_ref"]),
        "ticker": case_key,
        "company_name": case_key,
        "fact_domain": "financial_statement_fact",
        "fact_type": "revenue",
        "authority_mode": "exact_company_fact_authority",
        "can_enter_evidence_bundle": True,
        "exact_value_authority": True,
        "can_support_company_exact_fact": True,
        "source_layer": "L1",
        "source_id": "sec_companyfacts_api",
        "metric_family": "revenue",
        "metric_name": "Revenue",
        "canonical_metric_id": "financial_metric:revenue",
        "value": str(reviewed["normalized_value"]),
        "unit": str(reviewed["unit"]),
        "period": f"FY{reviewed['fiscal_year']}-{reviewed['fiscal_period']}",
        "period_role": "annual",
        "period_start": str(reviewed["period_start"]),
        "period_end": str(reviewed["period_end"]),
        "duration_days": str(reviewed["duration_days"]),
        "fiscal_year": str(reviewed["fiscal_year"]),
        "fiscal_period": str(reviewed["fiscal_period"]),
        "raw_fiscal_period": str(reviewed["fiscal_period"]),
        "source_filed_at": str(reviewed["source_filed_at"]),
        "published_at": str(reviewed["published_at"]),
        "as_of_date": "",
        "snapshot_at": str(reviewed["snapshot_at"]),
        "claim_boundary": "consolidated annual company fact only",
        "citation_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{reviewed['issuer_id']}.json",
        "citation_span": f"Reviewed {case_key} annual revenue fact",
        "evidence_ref": str(reviewed["source_ref"]),
        "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{reviewed['issuer_id']}.json",
    }


def _value_request(case_key: str):
    readiness = load_current_fin_0_1_2_s4_t02_readiness(case_key)
    parent = next(
        row
        for row in readiness.evidence_requests
        if row.program_cell_id == "value_and_profit_capture"
    )
    return compile_executable_search_request(parent)


def test_three_case_sql_to_numeric_projection_preserves_financial_truth_and_four_time_roles(
    tmp_path: Path,
) -> None:
    database = tmp_path / "gold.sqlite"
    write_gold_fact_signal_mart_sqlite(
        database,
        [_gold_row(row) for row in _reviewed_rows()],
    )
    capture = LocalCaptureWriter(FileCanonicalObjectStore(tmp_path / "objects"))
    adapter = ExactValueSqlSearchAdapter(database=database, capture=capture)

    expected = {str(row["case_key"]): row for row in _reviewed_rows()}
    for case_key in ("DELL", "MU", "NVDA"):
        request = _value_request(case_key)
        candidates = adapter.search(request)
        assert len(candidates) == 1
        projected = _numeric_projection(candidates[0].as_dict(), entity_ref=case_key)
        reviewed = expected[case_key]
        assert projected["value"] == str(reviewed["normalized_value"])
        assert projected["period_role"] == "annual"
        assert projected["period_start"] == reviewed["period_start"]
        assert projected["period_end"] == reviewed["period_end"]
        assert int(projected["duration_days"]) == reviewed["duration_days"]
        assert projected["source_filed_at"] == reviewed["source_filed_at"]
        assert projected["published_at"] == reviewed["published_at"]
        assert projected["as_of_date"] == request.as_of[:10]
        assert projected["snapshot_at"] == reviewed["snapshot_at"]
        assert projected["source_filed_at"] != projected["snapshot_at"]


def test_sql_adapter_excludes_q4_disguised_as_fy_and_post_cutoff_annual_fact(tmp_path: Path) -> None:
    oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
    annual = _gold_row(oracle["reviewed_truth_rows"][0])
    q4_truth = dict(oracle["known_current_failure"]["reviewed_truth"])
    q4 = _gold_row(q4_truth, suffix="q4")
    q4.update(
        {
            "value": "23931000000",
            "period": "FY2025-Q4",
            "period_role": "qtd",
            "fiscal_period": "Q4",
            "raw_fiscal_period": "FY",
        }
    )
    future = dict(annual)
    future.update(
        {
            "gold_row_id": "fin013:s1-01:DELL:revenue:future",
            "source_row_id": "future:DELL:revenue",
            "value": "999999999999",
            "fiscal_year": "2026",
            "period": "FY2026-FY",
            "period_start": "2025-02-01",
            "period_end": "2026-01-30",
            "source_filed_at": "2027-03-01",
            "published_at": "2027-03-01",
        }
    )
    database = tmp_path / "gold.sqlite"
    write_gold_fact_signal_mart_sqlite(database, [q4, future, annual])
    adapter = ExactValueSqlSearchAdapter(
        database=database,
        capture=LocalCaptureWriter(FileCanonicalObjectStore(tmp_path / "objects")),
    )

    candidates = adapter.search(_value_request("DELL"))

    assert len(candidates) == 1
    assert candidates[0].structured_numeric["value"] == "95567000000"
    assert candidates[0].structured_numeric["period"] == "FY2025-FY"
    assert candidates[0].structured_numeric["source_filed_at"] == "2025-03-25"


def test_legacy_text_only_numeric_candidate_cannot_launder_time_roles() -> None:
    with pytest.raises(
        Fin012S4T04EvidenceError,
        match="s4_t04_legacy_unstructured_numeric_candidate_not_current_authority",
    ):
        _numeric_projection(
            {
                "excerpt": "Revenues: 23931000000 USD; for FY2025-FY; filed=2025-03-25",
            },
            entity_ref="DELL",
        )
