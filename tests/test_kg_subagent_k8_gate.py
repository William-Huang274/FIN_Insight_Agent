from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "kg_subagent_k8_cases_v0_1.jsonl"
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "eval_kg_subagent_k8_gate.py"


def test_kg_subagent_k8_fixture_schema_and_coverage() -> None:
    rows = _read_jsonl(FIXTURE_PATH)

    assert 10 <= len(rows) <= 20
    assert all(str(row.get("case_id") or "").startswith("k8_") for row in rows)
    assert all(row.get("expected") for row in rows)
    assert {
        "product_kpi",
        "product_spec",
        "product_generation",
        "competitive_comparable",
        "public_buyer_observer",
        "field_inquiry",
        "bounded_gap",
        "capital_structure",
        "ownership",
        "macro_exposure",
        "vertical_official_object",
    } <= {row.get("case_group") for row in rows}
    assert any((row.get("expected") or {}).get("forbidden_claim_probes") for row in rows)
    assert any((row.get("expected") or {}).get("allowed_claim_probes") for row in rows)
    assert any(row.get("input_selectors") for row in rows)
    assert any(row.get("inline_state") for row in rows)


def test_kg_subagent_k8_runner_scores_inline_product_and_capital_boundaries(tmp_path: Path) -> None:
    module = _load_script_module()
    cases_path = tmp_path / "cases.jsonl"
    cases = [
        {
            "case_id": "k8_unit_channel_offer_boundary",
            "case_group": "public_buyer_observer",
            "agent_id": "product_technology_analyst",
            "inline_state": {
                "public_source_context_rows": [
                    {
                        "evidence_ref": "unit:commerce:offer",
                        "source_family": "live_public_web_context",
                        "source_class": "commerce_product_surface",
                        "ticker": "NVDA",
                        "product_family": "Data Center GPU",
                        "model_name": "H100 SXM",
                        "channel_name": "Example Catalog",
                        "price": "25000",
                        "currency": "USD",
                        "availability": "listed",
                        "configuration": "SXM 80GB",
                        "region": "US",
                        "observed_at": "2026-06-12",
                        "source_id": "example_catalog",
                    }
                ]
            },
            "expected": {
                "min_input_rows": 1,
                "product_pack": {"min_input_row_count": 1, "min_channel_offer_count": 1},
                "specialist_request": {"requires_product_spec_pack": True, "min_known_evidence_refs": 1},
                "boundary": {"channel_offer_context_only": True},
                "forbidden_claim_probes": [
                    {
                        "probe_id": "channel_not_sell_through",
                        "claim": "The channel offer proves sell-through.",
                        "claim_type": "business_observation",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["sell_through"],
                        "memo_slot": "product_technology",
                        "materiality": "high",
                        "confidence": "medium",
                        "source_families": ["live_public_web_context"],
                        "evidence_ref_selector": {"pack": "product_spec_pack", "collection": "channel_offers", "index": 0},
                        "expected_error_types": ["channel_offer_used_as_sell_through"],
                    }
                ],
            },
        },
        {
            "case_id": "k8_unit_macro_boundary",
            "case_group": "macro_exposure",
            "agent_id": "industry_supply_chain_analyst",
            "inline_state": {
                "macro_driver_rows": [
                    {
                        "evidence_ref": "unit:macro:driver",
                        "source_family": "industry_snapshot",
                        "source_id": "fred_api",
                        "object_type": "MacroDriver",
                        "record_type": "macro_time_series_observation",
                        "series_id": "FEDFUNDS",
                        "variable_name": "Federal funds effective rate",
                        "value": "4.33",
                        "unit": "percent",
                        "date": "2026-05-01",
                        "frequency": "monthly",
                        "claim_scope": "macro_or_industry_context_only",
                        "exact_value_authority": False,
                    }
                ],
                "macro_exposure_rows": [
                    {
                        "evidence_ref": "unit:macro:exposure",
                        "source_family": "industry_snapshot",
                        "source_id": "fred_api",
                        "object_type": "CompanyExposureToDriver",
                        "company_id": "JPM",
                        "driver_id": "MacroDriver::FEDFUNDS",
                        "exposure_type": "net_interest_income_rate_sensitivity",
                        "claim_scope": "company_exposure_bridge_context_only",
                        "exact_value_authority": False,
                    }
                ],
            },
            "expected": {
                "min_input_rows": 2,
                "capital_macro_pack": {
                    "min_input_row_count": 2,
                    "min_macro_driver_count": 1,
                    "min_company_exposure_edge_count": 1,
                },
                "specialist_request": {"requires_capital_macro_pack": True, "min_known_evidence_refs": 2},
                "boundary": {"macro_requires_exposure_bridge": True},
                "forbidden_claim_probes": [
                    {
                        "probe_id": "macro_not_revenue",
                        "claim": "The macro driver proves JPM company revenue.",
                        "claim_type": "company_revenue",
                        "ticker_scope": ["JPM"],
                        "metric_scope": ["revenue"],
                        "memo_slot": "industry_relationship",
                        "materiality": "high",
                        "confidence": "medium",
                        "source_families": ["industry_snapshot"],
                        "evidence_ref_selector": {"pack": "capital_macro_pack", "collection": "macro_drivers", "index": 0},
                        "expected_error_types": ["macro_or_public_context_used_as_company_fact"],
                    }
                ],
            },
        },
    ]
    cases_path.write_text("\n".join(json.dumps(row) for row in cases) + "\n", encoding="utf-8")

    result = module.main(["--cases-path", str(cases_path), "--output-dir", str(tmp_path / "out"), "--run-id", "unit_k8", "--strict"])

    summary = json.loads((tmp_path / "out" / "unit_k8" / "kg_subagent_k8_gate_summary.json").read_text(encoding="utf-8"))
    assert result == 1
    assert summary["case_count"] == 2
    assert summary["pass_count"] == 2
    assert summary["gate_status"] == "fail"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_script_module():
    spec = importlib.util.spec_from_file_location("eval_kg_subagent_k8_gate", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
