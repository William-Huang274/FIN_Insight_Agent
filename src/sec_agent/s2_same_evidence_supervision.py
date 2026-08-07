from __future__ import annotations

from typing import Any, Mapping


_DISPOSITIONS: dict[str, dict[str, Any]] = {
    "directional_margin_sharpened_to_unsupported_range": {
        "primary_owner": "runtime_deterministic_authority",
        "correction_class": "source_bound_precision_repair",
        "action": "remove the invented range and render only the exact directional source phrase",
        "deterministic_correction_allowed": True,
        "new_model_call_required": False,
    },
    "unbound_material_numeric_surface": {
        "primary_owner": "originating_model_node",
        "correction_class": "material_numeric_authority_return",
        "action": "return the node with the offending surface and approved numeric aliases only",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "cash_flow_margin_used_in_earnings_or_valuation_bridge": {
        "primary_owner": "originating_model_node",
        "correction_class": "financial_semantic_return",
        "action": "remove the unsupported bridge or bind it to an approved formula and evidence",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "unsupported_backlog_to_eps_or_price_bridge": {
        "primary_owner": "originating_model_node",
        "correction_class": "financial_semantic_return",
        "action": "remove the unsupported bridge or provide an approved scenario formula",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "trailing_pe_recast_as_single_quarter_earnings_multiple": {
        "primary_owner": "originating_model_node",
        "correction_class": "financial_semantic_return",
        "action": "remove the invalid single-quarter basis and preserve the trailing earnings definition",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "combined_deposits_commitments_recast_as_cash_or_refundable_prepayment": {
        "primary_owner": "originating_model_node",
        "correction_class": "source_scope_semantic_return",
        "action": "restore the combined deposits-and-commitments scope without asserting cash, refund or prepayment authority",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "average_fcf_margin_recast_as_marginal_revenue_sensitivity": {
        "primary_owner": "originating_model_node",
        "correction_class": "financial_semantic_return",
        "action": "remove the unsupported marginal sensitivity or provide an approved cost-behavior formula",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "explicit_counterevidence_surface_empty": {
        "primary_owner": "originating_model_node",
        "correction_class": "research_content_return",
        "action": "select case-local counterevidence or explicitly justify that none is present",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "hypothetical_planning_threshold": {
        "primary_owner": "research_quality_review",
        "correction_class": "uncalibrated_scenario_finding",
        "action": "retain as an unvalidated scenario or return for evidence, time-window and route calibration",
        "deterministic_correction_allowed": False,
        "new_model_call_required": False,
    },
    "verifier_missed_material_financial_semantics": {
        "primary_owner": "model_verifier_and_local_gate",
        "correction_class": "verifier_false_green",
        "action": "local gate blocks promotion; any Verifier repair must receive visible findings without hidden Gold",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
    "verifier_missed_material_failure": {
        "primary_owner": "model_verifier_and_local_gate",
        "correction_class": "verifier_false_green",
        "action": "local gate blocks promotion; any Verifier repair must receive visible findings without hidden Gold",
        "deterministic_correction_allowed": False,
        "new_model_call_required": True,
    },
}


def compile_supervision_boundary(
    raw_evaluation: Mapping[str, Any],
    *,
    raw_run_id: str,
    raw_terminal_digest: str,
) -> dict[str, Any]:
    """Compile a zero-call correction ledger without exposing hidden evaluator answers."""

    if not raw_run_id or not raw_terminal_digest:
        raise ValueError("s2_06_raw_identity_required")
    findings = raw_evaluation.get("findings")
    if not isinstance(findings, list):
        raise ValueError("s2_06_raw_findings_required")

    rows: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, Mapping):
            raise ValueError("s2_06_finding_not_object")
        code = str(finding.get("code") or "")
        disposition = dict(_DISPOSITIONS.get(code) or {
            "primary_owner": "contract_or_evaluator_review",
            "correction_class": "typed_manual_disposition_required",
            "action": "classify the earliest owner before correction",
            "deterministic_correction_allowed": False,
            "new_model_call_required": False,
        })
        if code == "unsupported_historical_valuation_comparison":
            if finding.get("severity") == "L3":
                disposition = {
                    "primary_owner": "research_quality_review",
                    "correction_class": "uncalibrated_valuation_reference",
                    "action": "retain only as a hypothetical evidence request, not as a current valuation fact",
                    "deterministic_correction_allowed": False,
                    "new_model_call_required": False,
                }
            else:
                disposition = {
                    "primary_owner": "originating_model_node",
                    "correction_class": "financial_semantic_return",
                    "action": "remove the unsupported historical comparison or bind approved historical evidence",
                    "deterministic_correction_allowed": False,
                    "new_model_call_required": True,
                }
        rows.append({
            "correction_id": f"CORR-{index:03d}",
            "source_finding": dict(finding),
            **disposition,
            "hidden_gold_visible": False,
            "raw_output_mutated": False,
        })

    complete = raw_evaluation.get("raw_chain_complete") is True
    scoreable = raw_evaluation.get("hidden_scoring_eligible") is True
    material = raw_evaluation.get("material_failure") is True
    return {
        "schema_version": "fin_ia_0_1_3_s2_06_supervision_boundary_v1_1",
        "raw_binding": {
            "run_id": raw_run_id,
            "terminal_digest": raw_terminal_digest,
            "raw_model_only_immutable": True,
        },
        "track_authority": {
            "raw_model_only": "immutable_read_only",
            "runtime_deterministic": "may_delete_downgrade_or_render_only_source_bound_authority",
            "supervisor_augmented": "may_issue_visible_error_class_and_case_local_evidence_refs_but_not_answers",
            "corrected_candidate": "new_identity_required_and_never_rewrites_raw",
            "evaluator_only": "read_for_scoring_only_never_visible_to_model_or_supervisor_prompt",
            "qualified_human": "separate_final_content_acceptance",
        },
        "corrections": rows,
        "capability_attribution": {
            "autonomous_model_result": "raw_complete_quality_fail" if complete and material else (
                "raw_complete_no_material_failure" if complete else "raw_incomplete"
            ),
            "supervised_recoverability": "not_proven",
            "runtime_deterministic_contribution": "not_materialized",
            "business_promotion": False,
        },
        "campaign_boundary": {
            "raw_measurement_complete": complete and scoreable,
            "automatic_next_case": False,
            "next_case_may_be_considered_by_separate_authority": complete and scoreable,
            "corrected_DELL_required_before_MU_raw_measurement": False,
            "cross_case_correction_leakage_forbidden": True,
        },
    }
