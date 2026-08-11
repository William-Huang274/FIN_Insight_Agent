from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.material_numeric_program import (
    MaterialNumericProgramError,
    canonical_digest,
    compile_material_numeric_program,
    load_material_numeric_policy,
    validate_material_numeric_program,
    validate_three_case_material_numeric_program_set,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    REPO_ROOT
    / "configs/runtime/fin_ia_0_1_3_repair_closeout_material_numeric_program_v1_0.json"
)
RELEASE_PATH = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_02_material_numeric_program_formula_recalculation_and_typed_gap_coverage_v1_0.json"
)
ACTIVE_SUITE_PATH = (
    REPO_ROOT
    / "configs/releases/fin_ia_0_1_3_repair_closeout_s1_02_active_test_suite_successor_v1_0.json"
)


def _policy() -> dict:
    return load_material_numeric_policy(POLICY_PATH)


def _gold_row(
    *,
    ticker: str,
    metric_family: str,
    value: int,
    role: str,
    start: str,
    end: str,
    duration: int | None,
    row_id: str,
) -> dict:
    issuer = {"DELL": "0001571996", "MU": "0000723125", "NVDA": "0001045810"}[ticker]
    filed = {"DELL": "2025-03-25", "MU": "2025-10-03", "NVDA": "2025-02-26"}[ticker]
    source_row_id = f"sec_financial_statement_metric:{row_id}"
    return {
        "gold_row_id": row_id,
        "ticker": ticker,
        "metric_family": metric_family,
        "metric_name": metric_family.replace("_", " ").title(),
        "value": str(value),
        "unit": "USD",
        "fiscal_year": "2025",
        "fiscal_period": "FY",
        "period_role": role,
        "period_start": start,
        "period_end": end,
        "duration_days": "" if duration is None else str(duration),
        "source_filed_at": filed,
        "published_at": filed,
        "snapshot_at": "2026-08-06T01:41:27Z",
        "source_row_id": source_row_id,
        "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{issuer}.json",
        "payload_json": json.dumps(
            {"issuer_id": issuer, "source_document_id": f"{issuer}-25-000001"}
        ),
    }


def _dell_inputs() -> tuple[list[dict], list[dict]]:
    end = "2025-01-31"
    start = "2024-02-03"
    annual = {
        "revenue": 95_567_000_000,
        "gross_profit": 21_250_000_000,
        "operating_income": 6_237_000_000,
        "operating_cash_flow": 4_521_000_000,
        "capital_expenditure_proxy": 2_652_000_000,
    }
    rows = [
        _gold_row(
            ticker="DELL",
            metric_family=metric,
            value=value,
            role="annual",
            start=start,
            end=end,
            duration=364,
            row_id=f"dell_{metric}",
        )
        for metric, value in annual.items()
    ]
    for metric, value in {
        "inventory": 6_716_000_000,
        "accounts_receivable": 10_298_000_000,
        "accounts_payable": 20_832_000_000,
    }.items():
        rows.append(
            _gold_row(
                ticker="DELL",
                metric_family=metric,
                value=value,
                role="instant",
                start="",
                end=end,
                duration=None,
                row_id=f"dell_{metric}",
            )
        )
    comparative = [
        {
            "ticker": "DELL",
            "fiscal_year": 2025,
            "fiscal_period": "FY",
            "start_date": "",
            "period_end": "2024-02-02",
            "filed_date": "2025-03-25",
            "form_type": "10-K",
            "value": 3_622_000_000,
            "unit": "USD",
            "concept": "InventoryNet",
            "label": "Inventory, Net",
            "accession_number": "0001571996-25-000034",
            "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0001571996.json",
            "fact_id": "SECFACT::DELL::INVENTORY::BEGIN",
            "snapshot_at": "2026-08-06T01:41:27Z",
        }
    ]
    return rows, comparative


def test_policy_freezes_bounded_formula_and_stage_scope() -> None:
    policy = _policy()
    assert set(policy["formula_contracts"]) == {
        "gross_margin_percent",
        "operating_margin_percent",
        "free_cash_flow",
        "inventory_days",
        "capital_intensity_percent",
    }
    assert policy["case_profiles"]["DELL"]["formula_slots"] == [
        "gross_margin_percent",
        "operating_margin_percent",
        "free_cash_flow",
        "inventory_days",
    ]
    assert any("013-S1-03" in item for item in policy["non_goals"])
    assert any("No model" in item for item in policy["non_goals"])


def test_dell_material_program_recalculates_current_truth_and_governs_every_slot() -> None:
    gold_rows, comparative = _dell_inputs()
    program = compile_material_numeric_program(
        policy=_policy(),
        case_key="DELL",
        gold_rows=gold_rows,
        comparative_staging_rows=comparative,
    )
    validate_material_numeric_program(program, policy=_policy())
    facts = {row["slot_id"]: row for row in program["base_facts"]}
    formulas = {row["formula_id"]: row for row in program["derived_metrics"]}
    assert facts["revenue"]["normalized_value"] == "95567000000"
    assert facts["beginning_inventory"]["normalized_value"] == "3622000000"
    assert formulas["gross_margin_percent"]["result_value"] == "22.2357"
    assert formulas["operating_margin_percent"]["result_value"] == "6.5263"
    assert formulas["free_cash_flow"]["result_value"] == "1869000000"
    assert formulas["inventory_days"]["result_value"] == "25.32"
    assert program["coverage"] == {
        "requested_material_slots": 16,
        "available_base_facts": 9,
        "available_derived_metrics": 4,
        "typed_gaps": 3,
        "ungoverned_slots": 0,
    }
    assert all(row["source_exhaustion_proven"] is False for row in program["typed_gaps"])


def test_missing_beginning_inventory_becomes_typed_input_and_formula_gaps() -> None:
    gold_rows, _ = _dell_inputs()
    program = compile_material_numeric_program(
        policy=_policy(),
        case_key="DELL",
        gold_rows=gold_rows,
        comparative_staging_rows=[],
    )
    gaps = {row["slot_id"]: row for row in program["typed_gaps"]}
    assert gaps["beginning_inventory"]["gap_state"] == (
        "formula_input_unavailable_after_local_structured_lookup"
    )
    assert gaps["inventory_days"]["missing_inputs"] == ["beginning_inventory"]
    assert program["coverage"]["ungoverned_slots"] == 0


def test_conflicting_authority_and_wrong_unit_fail_closed() -> None:
    gold_rows, comparative = _dell_inputs()
    conflict = deepcopy(next(row for row in gold_rows if row["metric_family"] == "revenue"))
    conflict["gold_row_id"] = "dell_revenue_conflict"
    conflict["value"] = "1"
    with pytest.raises(MaterialNumericProgramError, match="material_numeric_authority_conflict"):
        compile_material_numeric_program(
            policy=_policy(),
            case_key="DELL",
            gold_rows=[*gold_rows, conflict],
            comparative_staging_rows=comparative,
        )

    wrong_unit = deepcopy(gold_rows)
    next(row for row in wrong_unit if row["metric_family"] == "gross_profit")["unit"] = "EUR"
    with pytest.raises(MaterialNumericProgramError, match="material_numeric_base_fact_invalid"):
        compile_material_numeric_program(
            policy=_policy(),
            case_key="DELL",
            gold_rows=wrong_unit,
            comparative_staging_rows=comparative,
        )


def test_formula_and_identity_mutations_fail_closed() -> None:
    gold_rows, comparative = _dell_inputs()
    program = compile_material_numeric_program(
        policy=_policy(),
        case_key="DELL",
        gold_rows=gold_rows,
        comparative_staging_rows=comparative,
    )
    tampered = deepcopy(program)
    tampered["derived_metrics"][0]["result_value"] = "999"
    body = {key: value for key, value in tampered.items() if key != "program_digest"}
    tampered["program_digest"] = canonical_digest(body)
    with pytest.raises(
        MaterialNumericProgramError, match="material_numeric_derived_metric_invalid"
    ):
        validate_material_numeric_program(tampered, policy=_policy())

    crossed = deepcopy(program)
    crossed["base_facts"][0]["entity_ref"] = "MU"
    body = {key: value for key, value in crossed.items() if key != "program_digest"}
    crossed["program_digest"] = canonical_digest(body)
    with pytest.raises(MaterialNumericProgramError, match="material_numeric_base_fact_invalid"):
        validate_material_numeric_program(crossed, policy=_policy())

    shifted = deepcopy(program)
    derived = shifted["derived_metrics"][0]
    old_ref = derived["derived_metric_ref"]
    derived["period_end"] = "2025-01-30"
    derived_body = {
        key: value
        for key, value in derived.items()
        if key not in {"derived_metric_ref", "derived_metric_digest"}
    }
    derived_digest = canonical_digest(derived_body)
    derived["derived_metric_digest"] = derived_digest
    derived["derived_metric_ref"] = f"fin013_derived_{derived_digest[:24]}"
    shifted["claim_table_admission"]["eligible_derived_metric_refs"] = [
        derived["derived_metric_ref"] if value == old_ref else value
        for value in shifted["claim_table_admission"]["eligible_derived_metric_refs"]
    ]
    shifted_body = {key: value for key, value in shifted.items() if key != "program_digest"}
    shifted["program_digest"] = canonical_digest(shifted_body)
    with pytest.raises(
        MaterialNumericProgramError,
        match="material_numeric_derived_temporal_or_scope_invalid",
    ):
        validate_material_numeric_program(shifted, policy=_policy())

    gap_tampered = deepcopy(program)
    gap = gap_tampered["typed_gaps"][0]
    old_gap_ref = gap["typed_gap_ref"]
    gap["cannot_infer"] = "fabricated gap narrative"
    gap_body = {
        key: value
        for key, value in gap.items()
        if key not in {"typed_gap_ref", "typed_gap_digest"}
    }
    gap_digest = canonical_digest(gap_body)
    gap["typed_gap_digest"] = gap_digest
    gap["typed_gap_ref"] = f"fin013_numeric_gap_{gap_digest[:24]}"
    gap_tampered["claim_table_admission"]["typed_gap_refs"] = [
        gap["typed_gap_ref"] if value == old_gap_ref else value
        for value in gap_tampered["claim_table_admission"]["typed_gap_refs"]
    ]
    gap_program_body = {
        key: value for key, value in gap_tampered.items() if key != "program_digest"
    }
    gap_tampered["program_digest"] = canonical_digest(gap_program_body)
    with pytest.raises(MaterialNumericProgramError, match="material_numeric_declared_gap_invalid"):
        validate_material_numeric_program(gap_tampered, policy=_policy())


def test_materialized_three_case_release_has_real_formula_values_and_honest_boundaries() -> None:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    record_digest = release.pop("record_digest")
    assert record_digest == canonical_digest(release)
    program_set = release["program_set"]
    validate_three_case_material_numeric_program_set(program_set, policy=_policy())
    assert program_set["observed_counts"] == {
        "cases": 3,
        "available_base_facts": 23,
        "available_derived_metrics": 14,
        "typed_gaps": 8,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_runs": 0,
    }
    by_case = {row["case_key"]: row for row in program_set["case_programs"]}
    expected = {
        "DELL": {
            "gross_margin_percent": "22.2357",
            "operating_margin_percent": "6.5263",
            "free_cash_flow": "1869000000",
            "inventory_days": "25.32",
        },
        "MU": {
            "gross_margin_percent": "39.7908",
            "operating_margin_percent": "26.1384",
            "free_cash_flow": "1668000000",
            "inventory_days": "139.34",
            "capital_intensity_percent": "42.4234",
        },
        "NVDA": {
            "gross_margin_percent": "74.9887",
            "operating_margin_percent": "62.4175",
            "free_cash_flow": "60853000000",
            "inventory_days": "85.66",
            "capital_intensity_percent": "2.4798",
        },
    }
    for case_key, values in expected.items():
        observed = {
            row["formula_id"]: row["result_value"]
            for row in by_case[case_key]["derived_metrics"]
        }
        assert observed == values
        assert by_case[case_key]["coverage"]["ungoverned_slots"] == 0
    assert release["stage_boundary"]["S1_03_source_exhaustion"] == "next_not_started"
    assert release["stage_boundary"]["S2_to_S5"] == "not_started"
    assert release["acceptance"]["old_FIN_0_1_2_evidence_packs_or_acceptances_rewritten"] is False

    count_tampered = deepcopy(program_set)
    count_tampered["observed_counts"]["typed_gaps"] = 999
    count_body = {
        key: value for key, value in count_tampered.items() if key != "program_set_digest"
    }
    count_tampered["program_set_digest"] = canonical_digest(count_body)
    with pytest.raises(
        MaterialNumericProgramError, match="material_numeric_program_set_summary_invalid"
    ):
        validate_three_case_material_numeric_program_set(
            count_tampered, policy=_policy()
        )


def test_active_suite_is_digest_bound_to_current_s1_02_authority() -> None:
    suite = json.loads(ACTIVE_SUITE_PATH.read_text(encoding="utf-8"))
    suite_digest = suite.pop("suite_digest")
    assert suite_digest == canonical_digest(suite)
    assert suite["decision_sha256"] == hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest()
    assert suite["material_numeric_counts"] == {
        "available_base_facts": 23,
        "available_derived_metrics": 14,
        "typed_gaps": 8,
        "ungoverned_slots": 0,
    }
    assert str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/") in suite[
        "selected_test_files"
    ]
    assert suite["model_or_full_chain_authorized"] is False
