from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(relative: str) -> dict[str, object]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_business_residual_disposition_binds_immutable_audit_and_all_facets() -> None:
    disposition = _load(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_business_residual_disposition_v1_0.json"
    )
    bound = disposition["bound_result"]
    summary = _load(bound["summary_ref"])
    full_path = ROOT / bound["full_result_ref"]

    assert summary["result_digest"] == bound["summary_result_digest"]
    assert hashlib.sha256(full_path.read_bytes()).hexdigest() == bound["full_result_sha256"]
    assert {row["facet_id"] for row in disposition["request_dispositions"]} == {
        "orders_and_backlog",
        "conversion_and_durability",
        "reported_results",
        "margin_and_incremental_profit",
        "cash_generation",
        "working_capital_risk",
        "issuer_counterevidence",
        "upstream_or_demand_counterevidence",
    }


def test_only_two_bounded_official_documents_enter_s1d() -> None:
    disposition = _load(
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_business_residual_disposition_v1_0.json"
    )
    scope = disposition["s1d_authorized_scope"]

    assert scope["official_documents"] == [
        "DELL_Q1_FY2027_EARNINGS_CALL_TRANSCRIPT",
        "TSM_Q2_2026_EARNINGS_CALL_TRANSCRIPT",
    ]
    assert scope["micron_prepared_remarks_deferred"] is True
    assert scope["valuation_deferred"] is True
    assert scope["broad_web_search_forbidden"] is True
    assert disposition["gate_decision"] == {
        "s1c_engineering_slice": "closed_with_recorded_role_and_ranking_residuals",
        "s1_product_gate": "open",
        "s1d_next": True,
        "s2_regression_required_after_new_evidence": True,
        "s3_planner_rerun_authorized": False,
        "s3_saved_atoms_reuse_required": True,
    }
