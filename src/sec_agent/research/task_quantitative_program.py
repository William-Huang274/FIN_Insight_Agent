from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.session import canonical_digest
from sec_agent.research.quantitative_authority import (
    QuantitativeAuthorityError,
    compile_quantitative_authority_state,
)


TASK_QUANTITATIVE_PROGRAM_SCHEMA_VERSION = (
    "fin_ia_s2_task_quantitative_program_v1_0"
)
TASK_QUANTITATIVE_PROJECTION_SCHEMA_VERSION = (
    "fin_ia_s2_task_quantitative_projection_v1_0"
)

_ALLOWED_GAP_OWNERS = {"S1", "S1_S2_boundary", "S2", "S3"}
_ALLOWED_GAP_DISPOSITIONS = {
    "retain_source_or_commercial_boundary",
    "retain_numeric_input_gap",
    "bounded_scenario_added_direct_gap_retained",
    "defer_threshold_authorship_to_S3",
    "await_market_PIT_input",
}


class TaskQuantitativeProgramError(ValueError):
    """Raised when a task-level S2 program crosses an authority boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise TaskQuantitativeProgramError(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return deepcopy(dict(value))


def _rows(value: object, code: str) -> list[dict[str, Any]]:
    _require(isinstance(value, list), code)
    rows = [_mapping(row, code) for row in value]
    return rows


def _strings(value: object, code: str) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(row).strip() for row in value]
    _require(bool(rows) and all(rows) and len(rows) == len(set(rows)), code)
    return rows


def _evidence_authority_ref(evidence_item_digest: str) -> str:
    return "EVIDENCE::" + evidence_item_digest[:24].upper()


def compile_task_quantitative_program(
    *,
    program: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    request_results: Sequence[Mapping[str, Any]],
    recorded_at: str,
) -> dict[str, Any]:
    """Compile facts, derivations, bounded scenarios and retained gaps for one task.

    Industry ranges remain analyst estimates/scenarios. They never become issuer
    NumericFacts and never close target-company ASP, unit, allocation or PVM gaps.
    """

    payload = deepcopy(dict(program))
    _require(
        payload.get("schema_version")
        == TASK_QUANTITATIVE_PROGRAM_SCHEMA_VERSION
        and payload.get("status")
        == "approved_zero_call_task_quantitative_program",
        "task_quantitative_program_header_invalid",
    )
    case_key = str(payload.get("case_key") or "").strip().upper()
    research_as_of = str(payload.get("research_as_of") or "")
    pack_binding = _mapping(
        payload.get("evidence_pack_binding"),
        "task_quantitative_pack_binding_missing",
    )
    _require(
        case_key
        and research_as_of
        and evidence_pack.get("case_key") == case_key
        and evidence_pack.get("research_as_of") == research_as_of
        and evidence_pack.get("pack_payload_digest")
        == pack_binding.get("pack_payload_digest")
        and pack_binding.get("case_key") == case_key,
        "task_quantitative_pack_binding_invalid",
    )

    materials = {
        str(row.get("material_ref") or ""): _mapping(
            row, "task_quantitative_source_material_invalid"
        )
        for row in evidence_pack.get("source_materials") or ()
        if isinstance(row, Mapping)
    }
    evidence_items = {
        str(row.get("target_id") or ""): _mapping(
            row, "task_quantitative_evidence_item_invalid"
        )
        for row in evidence_pack.get("evidence_items") or ()
        if isinstance(row, Mapping)
    }
    _require(evidence_items, "task_quantitative_evidence_pack_empty")

    support_catalog: list[dict[str, Any]] = []
    support_by_id: dict[str, dict[str, Any]] = {}
    for raw in _rows(
        payload.get("evidence_supports"),
        "task_quantitative_evidence_supports_invalid",
    ):
        support_id = str(raw.get("support_id") or "")
        target_id = str(raw.get("target_id") or "")
        expected_digest = str(raw.get("evidence_item_digest") or "")
        required_terms = _strings(
            raw.get("required_source_text_terms"),
            "task_quantitative_support_terms_invalid",
        )
        item = evidence_items.get(target_id)
        _require(
            support_id
            and support_id not in support_by_id
            and item is not None
            and item.get("evidence_item_digest") == expected_digest
            and item.get("case_key") == case_key
            and item.get("disposition")
            in {
                "accepted_direct_source_evidence",
                "accepted_bounded_context_evidence",
            }
            and item.get("claim_use") == raw.get("expected_claim_use"),
            "task_quantitative_evidence_support_binding_invalid",
        )
        material = materials.get(str(item.get("source_material_ref") or ""))
        source_text = str((material or {}).get("source_text") or "")
        _require(
            material is not None
            and material.get("source_tier") == raw.get("expected_source_tier")
            and material.get("publication_date")
            == raw.get("expected_publication_date")
            and all(term.casefold() in source_text.casefold() for term in required_terms),
            "task_quantitative_evidence_support_source_invalid",
        )
        authority_ref = _evidence_authority_ref(expected_digest)
        row = {
            "support_id": support_id,
            "authority_ref": authority_ref,
            "target_id": target_id,
            "evidence_item_digest": expected_digest,
            "source_material_ref": item.get("source_material_ref"),
            "source_url": material.get("source_url"),
            "source_tier": material.get("source_tier"),
            "publication_date": material.get("publication_date"),
            "claim_use": item.get("claim_use"),
            "target_company_numeric_fact_authority": False,
        }
        support_by_id[support_id] = row
        support_catalog.append(row)

    estimate_payloads: list[dict[str, Any]] = []
    estimate_binding_seed: dict[str, dict[str, Any]] = {}
    for raw in _rows(
        payload.get("research_estimates"),
        "task_quantitative_estimates_invalid",
    ):
        estimate_key = str(raw.get("estimate_key") or "")
        support_ids = _strings(
            raw.get("support_ids"), "task_quantitative_estimate_supports_invalid"
        )
        slots = _strings(
            raw.get("eligible_slot_ids"),
            "task_quantitative_estimate_slots_invalid",
        )
        _require(
            estimate_key
            and estimate_key not in estimate_binding_seed
            and set(support_ids).issubset(support_by_id)
            and raw.get("target_company_direct_metric") is False
            and bool(str(raw.get("claim_boundary_zh") or "")),
            "task_quantitative_estimate_binding_invalid",
        )
        estimate_payload = {
            key: deepcopy(raw[key])
            for key in (
                "metric_id",
                "period_label",
                "unit",
                "lower_bound",
                "central_value",
                "upper_bound",
                "method",
                "assumption_refs",
                "authored_by",
                "confidence",
            )
        }
        estimate_payload.update(
            {
                "case_key": case_key,
                "supporting_authority_refs": [
                    support_by_id[support_id]["authority_ref"]
                    for support_id in support_ids
                ],
            }
        )
        estimate_payloads.append(estimate_payload)
        estimate_binding_seed[estimate_key] = {
            "estimate_key": estimate_key,
            "support_ids": support_ids,
            "eligible_slot_ids": slots,
            "claim_boundary_zh": str(raw["claim_boundary_zh"]),
            "target_company_direct_metric": False,
        }

    try:
        preliminary = compile_quantitative_authority_state(
            case_key=case_key,
            request_results=request_results,
            recorded_at=recorded_at,
            research_estimates=estimate_payloads,
        )
    except QuantitativeAuthorityError as exc:
        raise TaskQuantitativeProgramError(str(exc)) from exc
    compiled_estimates = preliminary["research_estimates"]
    _require(
        len(compiled_estimates) == len(estimate_binding_seed),
        "task_quantitative_estimate_compilation_invalid",
    )
    estimate_id_by_key = {
        key: str(row["estimate_id"])
        for key, row in zip(estimate_binding_seed, compiled_estimates)
    }

    scenario_payloads: list[dict[str, Any]] = []
    scenario_binding_seed: dict[str, dict[str, Any]] = {}
    for raw in _rows(
        payload.get("scenarios"), "task_quantitative_scenarios_invalid"
    ):
        scenario_key = str(raw.get("scenario_key") or "")
        output_keys = _strings(
            raw.get("output_estimate_keys"),
            "task_quantitative_scenario_outputs_invalid",
        )
        slots = _strings(
            raw.get("eligible_slot_ids"),
            "task_quantitative_scenario_slots_invalid",
        )
        _require(
            scenario_key
            and scenario_key not in scenario_binding_seed
            and set(output_keys).issubset(estimate_id_by_key)
            and raw.get("target_company_direct_metric") is False
            and bool(str(raw.get("claim_boundary_zh") or "")),
            "task_quantitative_scenario_binding_invalid",
        )
        scenario_payloads.append(
            {
                "case_key": case_key,
                "scenario_name": str(raw.get("scenario_name") or ""),
                "scenario_type": str(raw.get("scenario_type") or ""),
                "time_horizon": str(raw.get("time_horizon") or ""),
                "assumption_refs": deepcopy(raw.get("assumption_refs") or []),
                "output_estimate_refs": [
                    estimate_id_by_key[key] for key in output_keys
                ],
                "authored_by": str(raw.get("authored_by") or ""),
            }
        )
        scenario_binding_seed[scenario_key] = {
            "scenario_key": scenario_key,
            "output_estimate_keys": output_keys,
            "eligible_slot_ids": slots,
            "claim_boundary_zh": str(raw["claim_boundary_zh"]),
            "target_company_direct_metric": False,
        }

    try:
        quantitative = compile_quantitative_authority_state(
            case_key=case_key,
            request_results=request_results,
            recorded_at=recorded_at,
            research_estimates=estimate_payloads,
            scenarios=scenario_payloads,
        )
    except QuantitativeAuthorityError as exc:
        raise TaskQuantitativeProgramError(str(exc)) from exc
    estimate_bindings = []
    for key, estimate in zip(estimate_binding_seed, quantitative["research_estimates"]):
        estimate_bindings.append(
            {
                **estimate_binding_seed[key],
                "estimate_id": estimate["estimate_id"],
                "estimate_digest": estimate["estimate_digest"],
            }
        )
    scenario_bindings = []
    for key, scenario in zip(scenario_binding_seed, quantitative["scenarios"]):
        scenario_bindings.append(
            {
                **scenario_binding_seed[key],
                "scenario_id": scenario["scenario_id"],
                "scenario_digest": scenario["scenario_digest"],
            }
        )

    residual_gaps = {
        str(row.get("gap_id") or ""): _mapping(
            row, "task_quantitative_residual_gap_invalid"
        )
        for row in evidence_pack.get("residual_gaps") or ()
        if isinstance(row, Mapping)
    }
    disposition_rows = _rows(
        payload.get("typed_gap_dispositions"),
        "task_quantitative_gap_dispositions_invalid",
    )
    _require(
        {str(row.get("gap_id") or "") for row in disposition_rows}
        == set(residual_gaps)
        and len(disposition_rows) == len(residual_gaps),
        "task_quantitative_gap_coverage_invalid",
    )
    typed_gap_dispositions = []
    for raw in disposition_rows:
        gap_id = str(raw.get("gap_id") or "")
        owner = str(raw.get("owning_stage") or "")
        disposition = str(raw.get("disposition") or "")
        _require(
            owner in _ALLOWED_GAP_OWNERS
            and disposition in _ALLOWED_GAP_DISPOSITIONS
            and raw.get("closed") is False
            and raw.get("public_information_gap_authority") is False
            and bool(str(raw.get("reason_zh") or "")),
            "task_quantitative_gap_disposition_invalid",
        )
        gap = residual_gaps[gap_id]
        typed_gap_dispositions.append(
            {
                "gap_id": gap_id,
                "slot_id": str(gap.get("slot_id") or ""),
                "facet_id": str(gap.get("facet_id") or ""),
                "gap_code": str(gap.get("gap_code") or ""),
                "owning_stage": owner,
                "disposition": disposition,
                "reason_zh": str(raw["reason_zh"]),
                "closed": False,
                "public_information_gap_authority": False,
            }
        )

    readiness = _mapping(
        payload.get("task_readiness"), "task_quantitative_readiness_invalid"
    )
    required_estimates = _strings(
        readiness.get("required_estimate_keys"),
        "task_quantitative_required_estimates_invalid",
    )
    required_scenarios = _strings(
        readiness.get("required_scenario_keys"),
        "task_quantitative_required_scenarios_invalid",
    )
    required_slots = _strings(
        readiness.get("required_slot_ids"),
        "task_quantitative_required_slots_invalid",
    )
    summary = quantitative["summary"]
    checks = {
        "minimum_reported_facts": int(summary["reported_fact_count"])
        >= int(readiness.get("minimum_reported_fact_count") or 0),
        "minimum_deterministic_derivations": int(
            summary["deterministic_derived_metric_count"]
        )
        >= int(readiness.get("minimum_deterministic_derived_metric_count") or 0),
        "required_estimates_present": set(required_estimates).issubset(
            estimate_binding_seed
        ),
        "required_scenarios_present": set(required_scenarios).issubset(
            scenario_binding_seed
        ),
        "required_slots_bound": set(required_slots).issubset(
            {
                slot
                for row in (*estimate_bindings, *scenario_bindings)
                for slot in row["eligible_slot_ids"]
            }
        ),
        "typed_conflicts_absent": int(summary["typed_conflict_count"]) == 0,
        "all_pack_gaps_explicit_and_open": all(
            row["closed"] is False for row in typed_gap_dispositions
        ),
        "industry_scenarios_do_not_close_target_company_gaps": all(
            row["closed"] is False
            for row in typed_gap_dispositions
            if row["gap_id"]
            in {
                "dell-gap-pricing-asp",
                "dell-gap-pricing-units",
                "dell-gap-price-volume-mix-bridge",
                "dell-gap-supplier-capacity-readthrough",
            }
        ),
    }
    task_ready = all(checks.values())
    _require(task_ready, "task_quantitative_readiness_failed")
    unsigned = {
        "schema_version": TASK_QUANTITATIVE_PROJECTION_SCHEMA_VERSION,
        "status": "ready_for_bounded_dynamic_single_unit_with_typed_gaps",
        "case_key": case_key,
        "research_as_of": research_as_of,
        "recorded_at": str(recorded_at),
        "evidence_pack_binding": {
            "case_key": case_key,
            "pack_payload_digest": evidence_pack.get("pack_payload_digest"),
        },
        "evidence_support_catalog": support_catalog,
        "quantitative_authority": quantitative,
        "research_estimate_bindings": estimate_bindings,
        "scenario_bindings": scenario_bindings,
        "typed_gap_dispositions": typed_gap_dispositions,
        "task_readiness": {
            "cell_id": str(readiness.get("cell_id") or ""),
            "required_slot_ids": required_slots,
            "checks": checks,
            "ready": True,
        },
        "authority": {
            "reported_facts_remain_source_bound_numeric_facts": True,
            "deterministic_derivations_require_formula_trace": True,
            "industry_estimates_and_scenarios_are_not_Dell_facts": True,
            "target_company_ASP_units_PVM_or_allocation_inferred": False,
            "public_information_gap_authority": False,
            "model_generated": False,
        },
        "known_boundary": str(payload.get("known_boundary") or ""),
    }
    return {
        **unsigned,
        "task_quantitative_projection_digest": canonical_digest(unsigned),
    }


__all__ = [
    "TASK_QUANTITATIVE_PROGRAM_SCHEMA_VERSION",
    "TASK_QUANTITATIVE_PROJECTION_SCHEMA_VERSION",
    "TaskQuantitativeProgramError",
    "compile_task_quantitative_program",
]
