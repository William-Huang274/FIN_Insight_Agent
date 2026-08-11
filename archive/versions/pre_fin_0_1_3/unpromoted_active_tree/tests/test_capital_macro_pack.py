from __future__ import annotations

from sec_agent.capital_macro_pack import CAPITAL_MACRO_PACK_SCHEMA_VERSION, build_capital_macro_pack, validate_capital_macro_pack
from sec_agent.multi_agent_runtime import build_agent_data_view
from sec_agent.specialist_llm import build_specialist_request_from_state


def _capital_macro_state() -> dict:
    return {
        "run_id": "unit_capital_macro_run",
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["fundamental_analyst", "industry_supply_chain_analyst", "risk_counterevidence_analyst"],
        },
        "capital_ownership_rows": [
            {
                "evidence_ref": "nvda_debt_2030_note",
                "object_type": "DebtInstrument",
                "source_family": "primary_sec_filing",
                "company_id": "NVDA",
                "principal": "1.25",
                "currency": "USD billions",
                "maturity_date": "2030-04-01",
                "coupon": "2.85%",
                "interest_rate_type": "fixed",
                "source_id": "nvda_10k_debt_footnote",
            },
            {
                "evidence_ref": "nvda_vanguard_13f_2026q1",
                "form_type": "13F",
                "source_family": "public_source_context",
                "investor_id": "Vanguard",
                "company_id": "NVDA",
                "shares": "1000000",
                "value": "250000000",
                "filing_date": "2026-05-15",
                "report_period": "2026-03-31",
                "source_id": "sec_13f_bulk",
            },
            {
                "evidence_ref": "bad_realtime_13f_flow",
                "form_type": "13F",
                "source_family": "public_source_context",
                "investor_id": "FastFund",
                "company_id": "NVDA",
                "shares": "1000",
                "value": "250000",
                "filing_date": "2026-05-15",
                "report_period": "2026-03-31",
                "claim_scope": "realtime_flow",
                "source_id": "bad_13f_claim",
            },
        ],
        "industry_snapshot_rows": [
            {
                "evidence_ref": "fred_fedfunds_2026_05",
                "source_family": "industry_snapshot",
                "record_type": "macro_time_series_observation",
                "ticker": "JPM",
                "series_id": "FEDFUNDS",
                "variable_name": "Federal funds effective rate",
                "value": "4.33",
                "date": "2026-05-01",
                "frequency": "monthly",
                "source_id": "fred_api",
            }
        ],
        "macro_exposure_rows": [
            {
                "evidence_ref": "jpm_10k_nii_sensitivity",
                "object_type": "CompanyExposureToDriver",
                "source_family": "primary_sec_filing",
                "company_id": "JPM",
                "driver_id": "MacroDriver::FEDFUNDS",
                "exposure_type": "net_interest_income_rate_sensitivity",
                "source_id": "jpm_10k_rate_sensitivity",
            }
        ],
        "public_source_context_rows": [
            {
                "evidence_ref": "openfda_lly_product_status",
                "source_family": "public_source_context",
                "source_id": "openfda_api",
                "record_type": "fda_product_status_record",
                "company_id": "LLY",
                "event_or_status": "Drug approval status record.",
                "observed_at": "2026-06-11",
                "claim_scope": "regulatory_product_context_only",
            }
        ],
    }


def test_capital_macro_pack_enforces_13f_lag_and_macro_bridge_boundaries() -> None:
    pack = build_capital_macro_pack(_capital_macro_state())

    assert pack["schema_version"] == CAPITAL_MACRO_PACK_SCHEMA_VERSION
    assert pack["status"] == "pass"
    assert pack["summary"]["debt_instrument_count"] == 1
    assert pack["summary"]["ownership_position_count"] == 1
    assert pack["summary"]["macro_driver_count"] == 1
    assert pack["summary"]["company_exposure_edge_count"] == 1
    assert pack["summary"]["vertical_official_object_count"] == 1

    ownership = pack["ownership_positions"][0]
    assert ownership["claim_scope"] == "lagged_ownership_context_only"
    assert ownership["not_realtime_flag"] is True
    assert ownership["lag_days"] == "45"
    assert "realtime_flow" in ownership["forbidden_claims"]

    macro = pack["macro_drivers"][0]
    assert macro["claim_scope"] == "macro_or_industry_context_only"
    assert macro["exact_value_authority"] is False

    exposure = pack["company_exposure_edges"][0]
    assert exposure["claim_scope"] == "company_exposure_bridge_context_only"

    rejection_reasons = {row["reason"] for row in pack["rejected_objects"]}
    assert "ownership_realtime_flow_promotion_forbidden" in rejection_reasons
    assert "macro_driver_requires_company_exposure_bridge" in rejection_reasons


def test_capital_macro_pack_validation_blocks_realtime_ownership_promotion() -> None:
    pack = build_capital_macro_pack(_capital_macro_state())
    broken = dict(pack)
    broken["ownership_positions"] = [dict(pack["ownership_positions"][0], not_realtime_flag=False)]

    validation = validate_capital_macro_pack(broken)

    assert validation["status"] == "fail"
    assert any(error["type"] == "ownership_position_not_realtime_flag_required" for error in validation["errors"])


def test_capital_macro_pack_reaches_specialist_data_view_and_request() -> None:
    state = _capital_macro_state()

    view = build_agent_data_view("industry_supply_chain_analyst", state)
    request = build_specialist_request_from_state("industry_supply_chain_analyst", state)

    assert view["role_context"]["capital_macro_pack_allowed"] is True
    assert view["capital_macro_pack_ref"]["summary"]["macro_driver_count"] == 1
    assert request["capital_macro_pack"]["summary"]["ownership_position_count"] == 1
    assert "fred_fedfunds_2026_05" in request["known_evidence_refs"]
    assert "jpm_10k_nii_sensitivity" in request["known_evidence_refs"]
