from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Sequence


POLICY_SCHEMA = "fin_ia_0_1_3_material_numeric_program_policy_v1_0"
PROGRAM_SCHEMA = "fin_ia_0_1_3_material_numeric_program_v1_0"
PROGRAM_CONTRACT_REF = "fin_0_1_3.S1.material_numeric_program_formula_and_typed_gap:v1"
PROGRAM_CELL_ID = "value_and_profit_capture"

_ANNUAL_FLOW_METRICS = {
    "revenue",
    "gross_profit",
    "operating_income",
    "operating_cash_flow",
    "capital_expenditure_proxy",
}
_INSTANT_METRICS = {"inventory", "accounts_receivable", "accounts_payable"}
_INVENTORY_CONCEPTS = {"inventorynet", "inventorycurrent", "inventoriesnet"}
_ALLOWED_CASES = {"DELL", "MU", "NVDA"}


class MaterialNumericProgramError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_material_numeric_policy(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != POLICY_SCHEMA
        or payload.get("contract_ref") != PROGRAM_CONTRACT_REF
        or set(payload.get("case_profiles") or {}) != _ALLOWED_CASES
        or not isinstance(payload.get("formula_contracts"), Mapping)
    ):
        raise MaterialNumericProgramError("material_numeric_policy_invalid")
    return payload


def read_current_gold_numeric_rows(
    sqlite_path: str | Path,
    *,
    case_keys: Sequence[str],
) -> list[dict[str, Any]]:
    normalized_cases = tuple(sorted({str(value).upper() for value in case_keys}))
    if not normalized_cases or any(case not in _ALLOWED_CASES for case in normalized_cases):
        raise MaterialNumericProgramError("material_numeric_case_set_invalid")
    placeholders = ",".join("?" for _ in normalized_cases)
    query = f"""
        SELECT *
        FROM gold_fact_signal_mart
        WHERE ticker IN ({placeholders})
          AND exact_value_authority = 1
          AND metric_family IN (
              'revenue', 'gross_profit', 'operating_income',
              'operating_cash_flow', 'capital_expenditure_proxy',
              'inventory', 'accounts_receivable', 'accounts_payable'
          )
        ORDER BY ticker, metric_family, period_end, source_filed_at, gold_row_id
    """
    uri = Path(sqlite_path).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, normalized_cases)]


def read_comparative_staging_rows(
    staging_path: str | Path,
    *,
    target_dates: Mapping[str, str],
    source_filed_dates: Mapping[str, str],
) -> list[dict[str, Any]]:
    targets = {str(key).upper(): str(value) for key, value in target_dates.items()}
    filed = {str(key).upper(): str(value) for key, value in source_filed_dates.items()}
    if set(targets) != set(filed) or any(case not in _ALLOWED_CASES for case in targets):
        raise MaterialNumericProgramError("material_numeric_comparative_target_invalid")
    rows: list[dict[str, Any]] = []
    with Path(staging_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            candidate = json.loads(line)
            ticker = str(candidate.get("ticker") or "").upper()
            if ticker not in targets:
                continue
            concept = "".join(
                character
                for character in str(candidate.get("concept") or "").lower()
                if character.isalnum()
            )
            if (
                concept in _INVENTORY_CONCEPTS
                and str(candidate.get("period_end") or candidate.get("end_date") or "")
                == targets[ticker]
                and str(candidate.get("filed_date") or "") == filed[ticker]
                and str(candidate.get("form_type") or "").upper() == "10-K"
                and not str(candidate.get("start_date") or "").strip()
            ):
                rows.append(candidate)
    return rows


def compile_three_case_material_numeric_programs_from_files(
    *,
    policy_path: str | Path,
    gold_sqlite_path: str | Path,
    staging_path: str | Path,
) -> dict[str, Any]:
    policy = load_material_numeric_policy(policy_path)
    gold_rows = read_current_gold_numeric_rows(
        gold_sqlite_path,
        case_keys=tuple(policy["case_profiles"]),
    )
    anchors: dict[str, Mapping[str, Any]] = {}
    for case_key, profile in policy["case_profiles"].items():
        anchors[case_key] = _select_unique_gold_row(
            gold_rows,
            case_key=case_key,
            fiscal_year=int(profile["fiscal_year"]),
            metric_family="revenue",
            temporal_role="annual_current",
            as_of_date=str(profile["as_of_date"]),
            annual_anchor=None,
        )
    target_dates = {
        case_key: (
            date.fromisoformat(str(anchor["period_start"])) - timedelta(days=1)
        ).isoformat()
        for case_key, anchor in anchors.items()
    }
    source_filed_dates = {
        case_key: str(anchor["source_filed_at"]) for case_key, anchor in anchors.items()
    }
    comparative_rows = read_comparative_staging_rows(
        staging_path,
        target_dates=target_dates,
        source_filed_dates=source_filed_dates,
    )
    programs = [
        compile_material_numeric_program(
            policy=policy,
            case_key=case_key,
            gold_rows=gold_rows,
            comparative_staging_rows=comparative_rows,
        )
        for case_key in sorted(policy["case_profiles"])
    ]
    body = {
        "schema_version": "fin_ia_0_1_3_three_case_material_numeric_program_set_v1_0",
        "contract_ref": PROGRAM_CONTRACT_REF,
        "policy_digest": canonical_digest(policy),
        "case_programs": programs,
        "observed_counts": {
            "cases": len(programs),
            "available_base_facts": sum(len(row["base_facts"]) for row in programs),
            "available_derived_metrics": sum(len(row["derived_metrics"]) for row in programs),
            "typed_gaps": sum(len(row["typed_gaps"]) for row in programs),
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_runs": 0,
        },
    }
    result = {**body, "program_set_digest": canonical_digest(body)}
    validate_three_case_material_numeric_program_set(result, policy=policy)
    return result


def compile_material_numeric_program(
    *,
    policy: Mapping[str, Any],
    case_key: str,
    gold_rows: Sequence[Mapping[str, Any]],
    comparative_staging_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    case_key = case_key.upper()
    profile = deepcopy(dict((policy.get("case_profiles") or {}).get(case_key) or {}))
    if not profile or case_key not in _ALLOWED_CASES:
        raise MaterialNumericProgramError("material_numeric_case_profile_missing")
    fiscal_year = int(profile["fiscal_year"])
    as_of_date = str(profile["as_of_date"])
    annual_anchor = _select_unique_gold_row(
        gold_rows,
        case_key=case_key,
        fiscal_year=fiscal_year,
        metric_family="revenue",
        temporal_role="annual_current",
        as_of_date=as_of_date,
        annual_anchor=None,
    )

    base_facts: list[dict[str, Any]] = []
    base_by_slot: dict[str, dict[str, Any]] = {}
    typed_gaps: list[dict[str, Any]] = []
    for slot in profile.get("base_slots") or ():
        slot_id = str(slot["slot_id"])
        metric_family = str(slot["metric_family"])
        temporal_role = str(slot["temporal_role"])
        try:
            if temporal_role == "annual_begin_comparative_instant":
                source = _select_unique_comparative_row(
                    comparative_staging_rows,
                    case_key=case_key,
                    metric_family=metric_family,
                    annual_anchor=annual_anchor,
                    as_of_date=as_of_date,
                )
                fact = _staging_fact(
                    source,
                    case_key=case_key,
                    issuer_id=str(profile["issuer_id"]),
                    slot_id=slot_id,
                    as_of_date=as_of_date,
                )
            else:
                source = _select_unique_gold_row(
                    gold_rows,
                    case_key=case_key,
                    fiscal_year=fiscal_year,
                    metric_family=metric_family,
                    temporal_role=temporal_role,
                    as_of_date=as_of_date,
                    annual_anchor=annual_anchor,
                )
                fact = _gold_fact(
                    source,
                    case_key=case_key,
                    issuer_id=str(profile["issuer_id"]),
                    slot_id=slot_id,
                    as_of_date=as_of_date,
                )
        except MaterialNumericProgramError as exc:
            if exc.code not in {
                "material_numeric_required_row_missing",
                "material_numeric_comparative_row_missing",
            }:
                raise
            typed_gaps.append(
                _gap(
                    case_key=case_key,
                    slot_id=slot_id,
                    gap_code=exc.code,
                    cannot_infer=f"{slot_id} is unavailable from the current deterministic numeric inputs",
                    next_owner="013-S1-03",
                    gap_state="formula_input_unavailable_after_local_structured_lookup",
                )
            )
            continue
        base_facts.append(fact)
        base_by_slot[slot_id] = fact

    derived_metrics: list[dict[str, Any]] = []
    formula_contracts = policy.get("formula_contracts") or {}
    for formula_id in profile.get("formula_slots") or ():
        contract = formula_contracts.get(formula_id)
        if not isinstance(contract, Mapping):
            raise MaterialNumericProgramError("material_numeric_formula_contract_missing")
        required_inputs = tuple(str(value) for value in contract.get("required_inputs") or ())
        missing = [value for value in required_inputs if value not in base_by_slot]
        if missing:
            typed_gaps.append(
                _gap(
                    case_key=case_key,
                    slot_id=str(formula_id),
                    gap_code="material_numeric_formula_input_missing",
                    cannot_infer=f"{formula_id} because required inputs are missing: {', '.join(missing)}",
                    next_owner="013-S1-03",
                    gap_state="formula_input_unavailable_after_local_structured_lookup",
                    missing_inputs=missing,
                )
            )
            continue
        derived_metrics.append(
            _derive_formula(
                case_key=case_key,
                formula_id=str(formula_id),
                contract=contract,
                inputs={key: base_by_slot[key] for key in required_inputs},
                annual_anchor=annual_anchor,
                fiscal_year=fiscal_year,
                as_of_date=as_of_date,
            )
        )

    for gap_slot in profile.get("declared_gap_slots") or ():
        typed_gaps.append(
            _gap(
                case_key=case_key,
                slot_id=str(gap_slot["slot_id"]),
                gap_code=str(gap_slot["gap_code"]),
                cannot_infer=str(gap_slot["cannot_infer"]),
                next_owner=str(gap_slot["next_owner"]),
                gap_state="declared_material_requirement_not_source_exhaustion",
            )
        )

    requested_slots = (
        len(profile.get("base_slots") or ())
        + len(profile.get("formula_slots") or ())
        + len(profile.get("declared_gap_slots") or ())
    )
    governed_slots = len(base_facts) + len(derived_metrics) + len(typed_gaps)
    if requested_slots != governed_slots:
        raise MaterialNumericProgramError("material_numeric_coverage_not_exhaustive")
    body = {
        "schema_version": PROGRAM_SCHEMA,
        "contract_ref": PROGRAM_CONTRACT_REF,
        "case_key": case_key,
        "issuer_id": str(profile["issuer_id"]),
        "fiscal_year": fiscal_year,
        "as_of_date": as_of_date,
        "program_cell_ids": [PROGRAM_CELL_ID],
        "base_facts": sorted(base_facts, key=lambda row: row["slot_id"]),
        "derived_metrics": sorted(derived_metrics, key=lambda row: row["formula_id"]),
        "typed_gaps": sorted(typed_gaps, key=lambda row: row["slot_id"]),
        "claim_table_admission": {
            "status": "pass_all_material_slots_governed",
            "eligible_base_fact_refs": sorted(row["numeric_ref"] for row in base_facts),
            "eligible_derived_metric_refs": sorted(row["derived_metric_ref"] for row in derived_metrics),
            "typed_gap_refs": sorted(row["typed_gap_ref"] for row in typed_gaps),
            "free_numeric_narrative_authorized": False,
            "unknown_numeric_ref_behavior": "fail_closed",
        },
        "coverage": {
            "requested_material_slots": requested_slots,
            "available_base_facts": len(base_facts),
            "available_derived_metrics": len(derived_metrics),
            "typed_gaps": len(typed_gaps),
            "ungoverned_slots": 0,
        },
        "stage_boundary": {
            "S1_02_numeric_truth_ready": True,
            "S1_03_source_exhaustion_proven": False,
            "S1_04_graph_ready": False,
            "S2_S3_research_content_ready": False,
            "model_or_full_chain_run": False,
        },
    }
    result = {**body, "program_digest": canonical_digest(body)}
    validate_material_numeric_program(result, policy=policy)
    return result


def validate_three_case_material_numeric_program_set(
    program_set: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> dict[str, Any]:
    normalized = deepcopy(dict(program_set))
    digest = normalized.pop("program_set_digest", None)
    if (
        normalized.get("schema_version")
        != "fin_ia_0_1_3_three_case_material_numeric_program_set_v1_0"
        or normalized.get("contract_ref") != PROGRAM_CONTRACT_REF
        or digest != canonical_digest(normalized)
    ):
        raise MaterialNumericProgramError("material_numeric_program_set_invalid")
    programs = normalized.get("case_programs") or ()
    if {row.get("case_key") for row in programs} != _ALLOWED_CASES:
        raise MaterialNumericProgramError("material_numeric_program_set_case_invalid")
    for program in programs:
        validate_material_numeric_program(program, policy=policy)
    expected_counts = {
        "cases": len(programs),
        "available_base_facts": sum(len(row.get("base_facts") or ()) for row in programs),
        "available_derived_metrics": sum(
            len(row.get("derived_metrics") or ()) for row in programs
        ),
        "typed_gaps": sum(len(row.get("typed_gaps") or ()) for row in programs),
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_runs": 0,
    }
    if (
        normalized.get("policy_digest") != canonical_digest(policy)
        or normalized.get("observed_counts") != expected_counts
    ):
        raise MaterialNumericProgramError("material_numeric_program_set_summary_invalid")
    return deepcopy(dict(program_set))


def validate_material_numeric_program(
    program: Mapping[str, Any], *, policy: Mapping[str, Any]
) -> dict[str, Any]:
    normalized = deepcopy(dict(program))
    digest = normalized.pop("program_digest", None)
    case_key = str(normalized.get("case_key") or "")
    profile = (policy.get("case_profiles") or {}).get(case_key, {})
    if (
        normalized.get("schema_version") != PROGRAM_SCHEMA
        or normalized.get("contract_ref") != PROGRAM_CONTRACT_REF
        or case_key not in _ALLOWED_CASES
        or digest != canonical_digest(normalized)
        or normalized.get("issuer_id")
        != profile.get("issuer_id")
    ):
        raise MaterialNumericProgramError("material_numeric_program_invalid")
    expected_base_slots = {
        str(row["slot_id"]): dict(row) for row in profile.get("base_slots") or ()
    }
    expected_formula_slots = {str(value) for value in profile.get("formula_slots") or ()}
    expected_declared_gap_slots = {
        str(row["slot_id"]): dict(row) for row in profile.get("declared_gap_slots") or ()
    }
    expected_slots = (
        set(expected_base_slots) | expected_formula_slots | set(expected_declared_gap_slots)
    )
    base_refs: set[str] = set()
    by_slot: dict[str, Mapping[str, Any]] = {}
    for fact in normalized.get("base_facts") or ():
        slot_id = str(fact.get("slot_id") or "")
        slot_contract = expected_base_slots.get(slot_id)
        if slot_contract is None:
            raise MaterialNumericProgramError("material_numeric_base_fact_slot_invalid")
        _validate_base_fact(
            fact,
            case_key=case_key,
            issuer_id=str(profile["issuer_id"]),
            fiscal_year=int(profile["fiscal_year"]),
            as_of_date=str(profile["as_of_date"]),
            slot_contract=slot_contract,
        )
        ref = str(fact["numeric_ref"])
        if ref in base_refs or slot_id in by_slot:
            raise MaterialNumericProgramError("material_numeric_base_fact_duplicate")
        base_refs.add(ref)
        by_slot[slot_id] = fact
    _validate_program_temporal_alignment(by_slot)
    formula_refs: set[str] = set()
    formula_slots: set[str] = set()
    for derived in normalized.get("derived_metrics") or ():
        formula_id = str(derived.get("formula_id") or "")
        if formula_id not in expected_formula_slots:
            raise MaterialNumericProgramError("material_numeric_formula_slot_invalid")
        contract = (policy.get("formula_contracts") or {}).get(formula_id)
        if not isinstance(contract, Mapping):
            raise MaterialNumericProgramError("material_numeric_formula_contract_missing")
        _validate_derived_metric(
            derived,
            case_key=case_key,
            contract=contract,
            inputs=by_slot,
        )
        ref = str(derived["derived_metric_ref"])
        if ref in formula_refs or formula_id in formula_slots:
            raise MaterialNumericProgramError("material_numeric_derived_metric_duplicate")
        formula_refs.add(ref)
        formula_slots.add(formula_id)
    gap_refs: set[str] = set()
    gap_slots: set[str] = set()
    for gap in normalized.get("typed_gaps") or ():
        _validate_typed_gap(
            gap,
            case_key=case_key,
            expected_base_slots=set(expected_base_slots),
            expected_formula_slots=expected_formula_slots,
            expected_declared_gap_slots=expected_declared_gap_slots,
        )
        gap_ref = str(gap["typed_gap_ref"])
        gap_slot = str(gap["slot_id"])
        if gap_ref in gap_refs or gap_slot in gap_slots:
            raise MaterialNumericProgramError("material_numeric_typed_gap_duplicate")
        gap_refs.add(gap_ref)
        gap_slots.add(gap_slot)
    governed_slots = set(by_slot) | formula_slots | gap_slots
    if (
        governed_slots != expected_slots
        or (set(by_slot) & formula_slots)
        or (set(by_slot) & gap_slots)
        or (formula_slots & gap_slots)
    ):
        raise MaterialNumericProgramError("material_numeric_governed_slot_set_invalid")
    admission = normalized.get("claim_table_admission") or {}
    if (
        admission.get("status") != "pass_all_material_slots_governed"
        or set(admission.get("eligible_base_fact_refs") or ()) != base_refs
        or set(admission.get("eligible_derived_metric_refs") or ()) != formula_refs
        or set(admission.get("typed_gap_refs") or ()) != gap_refs
        or admission.get("free_numeric_narrative_authorized") is not False
        or admission.get("unknown_numeric_ref_behavior") != "fail_closed"
    ):
        raise MaterialNumericProgramError("material_numeric_admission_invalid")
    coverage = normalized.get("coverage") or {}
    if (
        int(coverage.get("requested_material_slots", -1))
        != len(base_refs) + len(formula_refs) + len(gap_refs)
        or int(coverage.get("available_base_facts", -1)) != len(base_refs)
        or int(coverage.get("available_derived_metrics", -1)) != len(formula_refs)
        or int(coverage.get("typed_gaps", -1)) != len(gap_refs)
        or int(coverage.get("ungoverned_slots", -1)) != 0
    ):
        raise MaterialNumericProgramError("material_numeric_coverage_invalid")
    expected_stage_boundary = {
        "S1_02_numeric_truth_ready": True,
        "S1_03_source_exhaustion_proven": False,
        "S1_04_graph_ready": False,
        "S2_S3_research_content_ready": False,
        "model_or_full_chain_run": False,
    }
    if normalized.get("stage_boundary") != expected_stage_boundary:
        raise MaterialNumericProgramError("material_numeric_stage_boundary_invalid")
    return deepcopy(dict(program))


def _select_unique_gold_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    case_key: str,
    fiscal_year: int,
    metric_family: str,
    temporal_role: str,
    as_of_date: str,
    annual_anchor: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if temporal_role == "annual_current":
        period_role = "annual"
        period_end = str(annual_anchor.get("period_end")) if annual_anchor else None
    elif temporal_role == "annual_end_instant":
        period_role = "instant"
        period_end = str((annual_anchor or {}).get("period_end") or "")
    else:
        raise MaterialNumericProgramError("material_numeric_temporal_role_invalid")
    candidates = [
        row
        for row in rows
        if str(row.get("ticker") or "").upper() == case_key
        and str(row.get("metric_family") or "") == metric_family
        and str(row.get("fiscal_year") or "") == str(fiscal_year)
        and str(row.get("period_role") or "") == period_role
        and (period_end is None or str(row.get("period_end") or "") == period_end)
        and str(row.get("source_filed_at") or "") <= as_of_date
    ]
    if not candidates:
        raise MaterialNumericProgramError("material_numeric_required_row_missing")
    _reject_conflicting_authorities(candidates)
    return sorted(
        candidates,
        key=lambda row: (
            str(row.get("source_filed_at") or ""),
            str(row.get("gold_row_id") or ""),
        ),
        reverse=True,
    )[0]


def _select_unique_comparative_row(
    rows: Sequence[Mapping[str, Any]],
    *,
    case_key: str,
    metric_family: str,
    annual_anchor: Mapping[str, Any],
    as_of_date: str,
) -> Mapping[str, Any]:
    if metric_family != "inventory":
        raise MaterialNumericProgramError("material_numeric_comparative_metric_invalid")
    target_date = (
        date.fromisoformat(str(annual_anchor["period_start"])) - timedelta(days=1)
    ).isoformat()
    source_filed_at = str(annual_anchor["source_filed_at"])
    candidates = [
        row
        for row in rows
        if str(row.get("ticker") or "").upper() == case_key
        and str(row.get("period_end") or row.get("end_date") or "") == target_date
        and str(row.get("filed_date") or "") == source_filed_at
        and str(row.get("filed_date") or "") <= as_of_date
        and str(row.get("form_type") or "").upper() == "10-K"
    ]
    if not candidates:
        raise MaterialNumericProgramError("material_numeric_comparative_row_missing")
    _reject_conflicting_authorities(candidates)
    return sorted(candidates, key=lambda row: str(row.get("fact_id") or ""))[0]


def _reject_conflicting_authorities(rows: Sequence[Mapping[str, Any]]) -> None:
    observed = {
        (
            str(row.get("value") or ""),
            str(row.get("unit") or ""),
            str(row.get("period_start") or row.get("start_date") or ""),
            str(row.get("period_end") or row.get("end_date") or ""),
        )
        for row in rows
    }
    if len(observed) != 1:
        raise MaterialNumericProgramError("material_numeric_authority_conflict")


def _gold_fact(
    row: Mapping[str, Any],
    *,
    case_key: str,
    issuer_id: str,
    slot_id: str,
    as_of_date: str,
) -> dict[str, Any]:
    payload = json.loads(str(row.get("payload_json") or "{}"))
    body = {
        "slot_id": slot_id,
        "case_key": case_key,
        "entity_ref": case_key,
        "issuer_id": issuer_id,
        "aggregation_scope": "consolidated_company_total",
        "metric_family": str(row["metric_family"]),
        "metric_name": str(row.get("metric_name") or row["metric_family"]),
        "raw_value": str(row["value"]),
        "normalized_value": str(row["value"]),
        "currency": "USD",
        "unit": str(row["unit"]),
        "scale_multiplier": "1",
        "fiscal_year": int(row["fiscal_year"]),
        "fiscal_period": str(row.get("fiscal_period") or ""),
        "period_role": str(row["period_role"]),
        "period_start": str(row.get("period_start") or ""),
        "period_end": str(row["period_end"]),
        "duration_days": int(row["duration_days"]) if str(row.get("duration_days") or "") else None,
        "source_filed_at": str(row["source_filed_at"]),
        "published_at": str(row["published_at"]),
        "as_of_date": as_of_date,
        "snapshot_at": str(row["snapshot_at"]),
        "source_ref": str(row["source_row_id"]),
        "source_locator": f"gold_fact_signal_mart:{row['gold_row_id']}",
        "source_url": str(row["source_url"]),
        "source_document_id": str(payload.get("source_document_id") or ""),
        "authority_role": "reported_exact",
        "formula": None,
        "program_cell_ids": [PROGRAM_CELL_ID],
        "core_claim_table_eligible": True,
    }
    ref_digest = canonical_digest(body)
    return {"numeric_ref": f"fin013_numeric_{ref_digest[:24]}", **body, "numeric_digest": ref_digest}


def _staging_fact(
    row: Mapping[str, Any],
    *,
    case_key: str,
    issuer_id: str,
    slot_id: str,
    as_of_date: str,
) -> dict[str, Any]:
    filed = str(row["filed_date"])
    body = {
        "slot_id": slot_id,
        "case_key": case_key,
        "entity_ref": case_key,
        "issuer_id": issuer_id,
        "aggregation_scope": "consolidated_company_total",
        "metric_family": "inventory",
        "metric_name": str(row.get("label") or row.get("concept") or "Inventory"),
        "raw_value": str(row["value"]),
        "normalized_value": str(row["value"]),
        "currency": "USD",
        "unit": str(row["unit"]),
        "scale_multiplier": "1",
        "fiscal_year": int(row["fiscal_year"]),
        "fiscal_period": str(row.get("fiscal_period") or "FY"),
        "period_role": "instant",
        "period_start": "",
        "period_end": str(row.get("period_end") or row.get("end_date")),
        "duration_days": None,
        "source_filed_at": filed,
        "published_at": filed,
        "as_of_date": as_of_date,
        "snapshot_at": str(row.get("snapshot_at") or row.get("generated_at") or filed),
        "source_ref": str(row["fact_id"]),
        "source_locator": f"sec_companyfacts_staging:{row['fact_id']}",
        "source_url": str(row["source_url"]),
        "source_document_id": str(row.get("accession_number") or ""),
        "authority_role": "reported_exact_comparative_instant",
        "formula": None,
        "program_cell_ids": [PROGRAM_CELL_ID],
        "core_claim_table_eligible": True,
    }
    ref_digest = canonical_digest(body)
    return {"numeric_ref": f"fin013_numeric_{ref_digest[:24]}", **body, "numeric_digest": ref_digest}


def _derive_formula(
    *,
    case_key: str,
    formula_id: str,
    contract: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
    annual_anchor: Mapping[str, Any],
    fiscal_year: int,
    as_of_date: str,
) -> dict[str, Any]:
    values = {key: _decimal(row["normalized_value"]) for key, row in inputs.items()}
    duration_days = int(annual_anchor["duration_days"])
    result = _calculate_formula(formula_id, values=values, duration_days=duration_days)
    places = int(contract["decimal_places"])
    quantizer = Decimal("1") if places == 0 else Decimal("1").scaleb(-places)
    rendered = format(result.quantize(quantizer, rounding=ROUND_HALF_UP), "f")
    input_refs = {key: str(inputs[key]["numeric_ref"]) for key in sorted(inputs)}
    source_refs = sorted({str(row["source_ref"]) for row in inputs.values()})
    body = {
        "formula_id": formula_id,
        "case_key": case_key,
        "entity_ref": case_key,
        "aggregation_scope": "consolidated_company_total",
        "metric_family": formula_id,
        "formula_expression": str(contract["expression"]),
        "formula_contract_ref": f"{PROGRAM_CONTRACT_REF}#{formula_id}",
        "required_scope": str(contract["required_scope"]),
        "input_numeric_refs": input_refs,
        "source_refs": source_refs,
        "result_value": rendered,
        "result_unit": str(contract["output_unit"]),
        "scale_multiplier": "1",
        "fiscal_year": fiscal_year,
        "fiscal_period": "FY",
        "period_role": "annual",
        "period_start": str(annual_anchor["period_start"]),
        "period_end": str(annual_anchor["period_end"]),
        "duration_days": duration_days,
        "as_of_date": as_of_date,
        "rounding_rule": f"decimal_half_up_{places}dp",
        "program_cell_ids": [PROGRAM_CELL_ID],
        "core_claim_table_eligible": True,
    }
    digest = canonical_digest(body)
    return {
        "derived_metric_ref": f"fin013_derived_{digest[:24]}",
        **body,
        "derived_metric_digest": digest,
    }


def _calculate_formula(
    formula_id: str,
    *,
    values: Mapping[str, Decimal],
    duration_days: int,
) -> Decimal:
    try:
        if formula_id == "gross_margin_percent":
            return values["gross_profit"] / values["revenue"] * Decimal("100")
        if formula_id == "operating_margin_percent":
            return values["operating_income"] / values["revenue"] * Decimal("100")
        if formula_id == "free_cash_flow":
            if values["capital_expenditure_proxy"] < 0:
                raise MaterialNumericProgramError("material_numeric_capex_sign_invalid")
            return values["operating_cash_flow"] - values["capital_expenditure_proxy"]
        if formula_id == "capital_intensity_percent":
            if values["capital_expenditure_proxy"] < 0:
                raise MaterialNumericProgramError("material_numeric_capex_sign_invalid")
            return values["capital_expenditure_proxy"] / values["revenue"] * Decimal("100")
        if formula_id == "inventory_days":
            cost_of_revenue = values["revenue"] - values["gross_profit"]
            if cost_of_revenue <= 0:
                raise MaterialNumericProgramError("material_numeric_cost_of_revenue_invalid")
            average_inventory = (
                values["beginning_inventory"] + values["ending_inventory"]
            ) / Decimal("2")
            return average_inventory / cost_of_revenue * Decimal(duration_days)
    except (InvalidOperation, ZeroDivisionError) as exc:
        raise MaterialNumericProgramError("material_numeric_formula_domain_invalid") from exc
    raise MaterialNumericProgramError("material_numeric_formula_unknown")


def _gap(
    *,
    case_key: str,
    slot_id: str,
    gap_code: str,
    cannot_infer: str,
    next_owner: str,
    gap_state: str,
    missing_inputs: Sequence[str] = (),
) -> dict[str, Any]:
    body = {
        "case_key": case_key,
        "slot_id": slot_id,
        "gap_code": gap_code,
        "cannot_infer": cannot_infer,
        "missing_inputs": list(missing_inputs),
        "gap_state": gap_state,
        "next_owner": next_owner,
        "source_exhaustion_proven": False,
        "program_cell_ids": [PROGRAM_CELL_ID],
        "narrative_fill_authorized": False,
    }
    digest = canonical_digest(body)
    return {
        "typed_gap_ref": f"fin013_numeric_gap_{digest[:24]}",
        **body,
        "typed_gap_digest": digest,
    }


def _validate_base_fact(
    fact: Mapping[str, Any],
    *,
    case_key: str,
    issuer_id: str,
    fiscal_year: int,
    as_of_date: str,
    slot_contract: Mapping[str, Any],
) -> None:
    body = {
        key: deepcopy(value)
        for key, value in fact.items()
        if key not in {"numeric_ref", "numeric_digest"}
    }
    expected_digest = canonical_digest(body)
    if (
        fact.get("case_key") != case_key
        or fact.get("entity_ref") != case_key
        or fact.get("issuer_id") != issuer_id
        or int(fact.get("fiscal_year", -1)) != fiscal_year
        or fact.get("as_of_date") != as_of_date
        or fact.get("metric_family") != slot_contract.get("metric_family")
        or fact.get("period_role")
        != (
            "annual"
            if slot_contract.get("temporal_role") == "annual_current"
            else "instant"
        )
        or fact.get("aggregation_scope") != "consolidated_company_total"
        or fact.get("currency") != "USD"
        or fact.get("unit") != "USD"
        or str(fact.get("scale_multiplier")) != "1"
        or fact.get("core_claim_table_eligible") is not True
        or fact.get("formula") is not None
        or fact.get("numeric_digest") != expected_digest
        or fact.get("numeric_ref") != f"fin013_numeric_{expected_digest[:24]}"
        or not fact.get("source_ref")
        or not fact.get("source_locator")
        or not str(fact.get("source_url") or "").startswith("https://")
        or str(fact.get("source_filed_at") or "") > str(fact.get("as_of_date") or "")
    ):
        raise MaterialNumericProgramError("material_numeric_base_fact_invalid")
    raw = _decimal(fact.get("raw_value"))
    normalized = _decimal(fact.get("normalized_value"))
    scale = _decimal(fact.get("scale_multiplier"))
    if raw * scale != normalized:
        raise MaterialNumericProgramError("material_numeric_scale_recalculation_invalid")
    role = fact.get("period_role")
    if role == "annual":
        start = date.fromisoformat(str(fact["period_start"]))
        end = date.fromisoformat(str(fact["period_end"]))
        duration = (end - start).days + 1
        if duration != fact.get("duration_days") or not 330 <= duration <= 380:
            raise MaterialNumericProgramError("material_numeric_annual_duration_invalid")
    elif role == "instant":
        if fact.get("period_start") not in {"", None} or fact.get("duration_days") is not None:
            raise MaterialNumericProgramError("material_numeric_instant_period_invalid")
    else:
        raise MaterialNumericProgramError("material_numeric_period_role_invalid")


def _validate_program_temporal_alignment(
    inputs: Mapping[str, Mapping[str, Any]],
) -> None:
    annual = [row for row in inputs.values() if row.get("period_role") == "annual"]
    if not annual:
        raise MaterialNumericProgramError("material_numeric_annual_anchor_missing")
    annual_keys = {
        (
            row.get("fiscal_year"),
            row.get("period_start"),
            row.get("period_end"),
            row.get("duration_days"),
            row.get("as_of_date"),
        )
        for row in annual
    }
    if len(annual_keys) != 1:
        raise MaterialNumericProgramError("material_numeric_annual_authority_misaligned")
    fiscal_year, period_start, period_end, _, as_of_date = next(
        iter(annual_keys)
    )
    for slot_id, row in inputs.items():
        if row.get("period_role") != "instant":
            continue
        if (
            row.get("fiscal_year") != fiscal_year
            or row.get("as_of_date") != as_of_date
        ):
            raise MaterialNumericProgramError("material_numeric_instant_authority_misaligned")
        expected_end = (
            (date.fromisoformat(str(period_start)) - timedelta(days=1)).isoformat()
            if slot_id == "beginning_inventory"
            else period_end
        )
        if row.get("period_end") != expected_end:
            raise MaterialNumericProgramError("material_numeric_instant_period_misaligned")


def _validate_derived_metric(
    derived: Mapping[str, Any],
    *,
    case_key: str,
    contract: Mapping[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
) -> None:
    body = {
        key: deepcopy(value)
        for key, value in derived.items()
        if key not in {"derived_metric_ref", "derived_metric_digest"}
    }
    expected_digest = canonical_digest(body)
    formula_id = str(derived.get("formula_id") or "")
    required = tuple(str(value) for value in contract.get("required_inputs") or ())
    if (
        derived.get("case_key") != case_key
        or derived.get("entity_ref") != case_key
        or derived.get("formula_expression") != contract.get("expression")
        or derived.get("result_unit") != contract.get("output_unit")
        or derived.get("core_claim_table_eligible") is not True
        or set(derived.get("input_numeric_refs") or {}) != set(required)
        or any(key not in inputs for key in required)
        or any(
            str((derived.get("input_numeric_refs") or {}).get(key))
            != str(inputs[key]["numeric_ref"])
            for key in required
        )
        or derived.get("derived_metric_digest") != expected_digest
        or derived.get("derived_metric_ref") != f"fin013_derived_{expected_digest[:24]}"
    ):
        raise MaterialNumericProgramError("material_numeric_derived_metric_invalid")
    values = {key: _decimal(inputs[key]["normalized_value"]) for key in required}
    annual_inputs = [inputs[key] for key in required if inputs[key].get("period_role") == "annual"]
    if not annual_inputs:
        raise MaterialNumericProgramError("material_numeric_derived_annual_anchor_missing")
    annual_anchor = annual_inputs[0]
    if any(
        (
            row.get("fiscal_year"),
            row.get("period_start"),
            row.get("period_end"),
            row.get("duration_days"),
            row.get("as_of_date"),
        )
        != (
            annual_anchor.get("fiscal_year"),
            annual_anchor.get("period_start"),
            annual_anchor.get("period_end"),
            annual_anchor.get("duration_days"),
            annual_anchor.get("as_of_date"),
        )
        for row in annual_inputs
    ):
        raise MaterialNumericProgramError("material_numeric_derived_input_period_misaligned")
    if (
        derived.get("fiscal_year") != annual_anchor.get("fiscal_year")
        or derived.get("fiscal_period") != "FY"
        or derived.get("period_role") != "annual"
        or derived.get("period_start") != annual_anchor.get("period_start")
        or derived.get("period_end") != annual_anchor.get("period_end")
        or derived.get("duration_days") != annual_anchor.get("duration_days")
        or derived.get("as_of_date") != annual_anchor.get("as_of_date")
        or derived.get("required_scope") != contract.get("required_scope")
        or derived.get("formula_contract_ref")
        != f"{PROGRAM_CONTRACT_REF}#{formula_id}"
        or set(derived.get("source_refs") or ())
        != {str(inputs[key]["source_ref"]) for key in required}
        or str(derived.get("scale_multiplier")) != "1"
    ):
        raise MaterialNumericProgramError("material_numeric_derived_temporal_or_scope_invalid")
    recalculated = _calculate_formula(
        formula_id,
        values=values,
        duration_days=int(derived["duration_days"]),
    )
    places = int(contract["decimal_places"])
    quantizer = Decimal("1") if places == 0 else Decimal("1").scaleb(-places)
    if recalculated.quantize(quantizer, rounding=ROUND_HALF_UP) != _decimal(
        derived.get("result_value")
    ):
        raise MaterialNumericProgramError("material_numeric_formula_recalculation_invalid")


def _validate_typed_gap(
    gap: Mapping[str, Any],
    *,
    case_key: str,
    expected_base_slots: set[str],
    expected_formula_slots: set[str],
    expected_declared_gap_slots: Mapping[str, Mapping[str, Any]],
) -> None:
    body = {
        key: deepcopy(value)
        for key, value in gap.items()
        if key not in {"typed_gap_ref", "typed_gap_digest"}
    }
    expected_digest = canonical_digest(body)
    slot_id = str(gap.get("slot_id") or "")
    declared = expected_declared_gap_slots.get(slot_id)
    if (
        gap.get("case_key") != case_key
        or gap.get("typed_gap_digest") != expected_digest
        or gap.get("typed_gap_ref") != f"fin013_numeric_gap_{expected_digest[:24]}"
        or gap.get("source_exhaustion_proven") is not False
        or gap.get("narrative_fill_authorized") is not False
        or gap.get("program_cell_ids") != [PROGRAM_CELL_ID]
        or gap.get("next_owner") != "013-S1-03"
        or slot_id
        not in (expected_base_slots | expected_formula_slots | set(expected_declared_gap_slots))
    ):
        raise MaterialNumericProgramError("material_numeric_typed_gap_invalid")
    if declared is not None:
        if (
            gap.get("gap_state") != "declared_material_requirement_not_source_exhaustion"
            or gap.get("gap_code") != declared.get("gap_code")
            or gap.get("cannot_infer") != declared.get("cannot_infer")
            or gap.get("missing_inputs") != []
        ):
            raise MaterialNumericProgramError("material_numeric_declared_gap_invalid")
    elif slot_id in expected_base_slots:
        if (
            gap.get("gap_state")
            != "formula_input_unavailable_after_local_structured_lookup"
            or gap.get("gap_code")
            not in {
                "material_numeric_required_row_missing",
                "material_numeric_comparative_row_missing",
            }
            or gap.get("missing_inputs") != []
        ):
            raise MaterialNumericProgramError("material_numeric_base_gap_invalid")
    else:
        missing_inputs = gap.get("missing_inputs") or []
        if (
            gap.get("gap_state")
            != "formula_input_unavailable_after_local_structured_lookup"
            or gap.get("gap_code") != "material_numeric_formula_input_missing"
            or not missing_inputs
            or any(value not in expected_base_slots for value in missing_inputs)
        ):
            raise MaterialNumericProgramError("material_numeric_formula_gap_invalid")


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MaterialNumericProgramError("material_numeric_decimal_invalid") from exc
