from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sec_agent.canonical_runtime.session import canonical_digest, validate_event_log

from .actionable_research_state import ACTIONABLE_RESEARCH_STATE_SCHEMA_VERSION
from .quantitative_authority import QUANTITATIVE_AUTHORITY_SCHEMA_VERSION


ACTIONABLE_RESEARCH_EVALUATION_SCHEMA_VERSION = (
    "fin_ia_actionable_research_state_evaluation_v1_0"
)


class ActionableResearchEvaluationError(ValueError):
    """Raised when an evaluation input is not a current runtime artifact."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ActionableResearchEvaluationError(code)


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | {
            key for item in value.values() for key in _all_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def evaluate_actionable_research_state(
    *,
    state: Mapping[str, Any],
    quantitative_authority: Mapping[str, Any],
) -> dict[str, Any]:
    current = deepcopy(dict(state))
    quant = deepcopy(dict(quantitative_authority))
    _require(
        current.get("schema_version")
        == ACTIONABLE_RESEARCH_STATE_SCHEMA_VERSION
        and quant.get("schema_version") == QUANTITATIVE_AUTHORITY_SCHEMA_VERSION
        and current.get("case_key") == quant.get("case_key"),
        "actionable_evaluation_input_invalid",
    )
    uncertainties = list(current.get("actionable_uncertainties") or ())
    actions = list(current.get("research_actions") or ())
    feedback = list(current.get("feedback_receipts") or ())
    uncertainty_ids = [str(row.get("uncertainty_id") or "") for row in uncertainties]
    action_uncertainty_refs = [
        str(row.get("uncertainty_ref") or "") for row in actions
    ]
    feedback_ids = [str(row.get("feedback_id") or "") for row in feedback]
    action_ids = [str(row.get("action_id") or "") for row in actions]
    plan_delta = dict(current.get("accepted_plan_delta") or {})
    accepted_plan = dict(current.get("accepted_plan") or {})
    session = dict(current.get("session") or {})
    checkpoint = dict(current.get("context_checkpoint") or {})
    resume = dict(current.get("resume_receipt") or {})
    stop = dict(current.get("stop_decision") or {})
    token_basis = dict(current.get("next_natural_node_token_budget_basis") or {})
    events = list(current.get("session_events") or ())
    source_portfolio = dict(current.get("source_portfolio_snapshot") or {})

    gates = {
        "uncertainty_has_action": bool(uncertainties)
        and set(uncertainty_ids) == set(action_uncertainty_refs),
        "identity_unique": (
            bool(uncertainty_ids)
            and len(uncertainty_ids) == len(set(uncertainty_ids))
            and len(action_ids) == len(set(action_ids))
            and len(feedback_ids) == len(set(feedback_ids))
        ),
        "no_false_public_gap": (
            all(
                row.get("public_information_gap_authority") is False
                and row.get("information_boundary_state") == "not_proved"
                for row in uncertainties
            )
            and current.get("summary", {}).get(
                "public_information_gap_authorized_count"
            )
            == 0
            and current.get("authority", {}).get(
                "public_information_gap_authority"
            )
            is False
        ),
        "source_rights_separated": (
            source_portfolio.get("rights_axes")
            == ["discovery", "internal_analysis", "citation", "redistribution"]
            and all(
                set((row.get("rights") or {}).keys())
                == {"discovery", "internal_analysis", "citation", "redistribution"}
                for row in source_portfolio.get("sources") or ()
            )
        ),
        "candidate_not_promoted": (
            current.get("authority", {}).get("candidate_auto_promotion") is False
            and all(row.get("candidate_promotion_authority") is False for row in actions)
            and not {
                "candidate_text",
                "private_source_material",
                "source_capture_ref",
            }.intersection(_all_keys(current))
        ),
        "quantitative_kinds_separated": (
            all(
                row.get("quantitative_kind") == "reported_fact"
                and row.get("numeric_fact_authority") is True
                for row in quant.get("reported_facts") or ()
            )
            and all(
                row.get("quantitative_kind") == "deterministic_derived_metric"
                and row.get("numeric_fact_authority") is False
                and row.get("input_authority_refs")
                and row.get("formula")
                for row in quant.get("deterministic_derived_metrics") or ()
            )
            and all(
                row.get("quantitative_kind") == "research_estimate"
                and row.get("numeric_fact_authority") is False
                for row in quant.get("research_estimates") or ()
            )
            and all(
                row.get("quantitative_kind") == "scenario"
                and row.get("numeric_fact_authority") is False
                for row in quant.get("scenarios") or ()
            )
        ),
        "feedback_changes_plan": (
            plan_delta.get("validation_status") == "accepted"
            and set(plan_delta.get("reason_feedback_refs") or ()) == set(feedback_ids)
            and set(accepted_plan.get("pending_action_ids") or ()) == set(action_ids)
            and plan_delta.get("base_plan_digest") != accepted_plan.get("plan_digest")
            and session.get("active_plan_ref") == accepted_plan.get("plan_ref")
        ),
        "checkpoint_resume_preserves_open_state": (
            set(checkpoint.get("open_gap_refs") or ()) == set(uncertainty_ids)
            and set(checkpoint.get("unresolved_feedback_refs") or ())
            == set(feedback_ids)
            and set(checkpoint.get("agent_local_state_refs") or ()) == set(action_ids)
            and resume.get("status") == "resume_replay_verified"
            and resume.get("checkpoint_digest") == checkpoint.get("checkpoint_digest")
        ),
        "stop_semantics_honest": (
            (not actions and stop.get("decision") == "stop_sufficient")
            or (
                bool(actions)
                and stop.get("decision") == "continue"
                and "actionable_research_actions_pending"
                in set(stop.get("reason_codes") or ())
            )
        ),
        "token_budget_basis_complete": bool(
            token_basis.get("execution_authority") is False
            and token_basis.get("cost_and_latency_are_secondary_constraints")
            is True
            and token_basis.get("node_purpose")
            and token_basis.get("input_scale")
            and token_basis.get("required_outputs")
            and token_basis.get("schema_burden")
            and token_basis.get("materiality_and_quality_risk")
            and token_basis.get("comparable_run_evidence")
            and token_basis.get("reasoning_profile")
            and token_basis.get("stop_or_truncation_behavior")
        ),
        "event_log_valid": False,
        "natural_agent_not_falsely_claimed": (
            current.get("authority", {}).get("natural_model_calls") == 0
            and current.get("authority", {}).get("natural_agent_consumption_proven")
            is False
        ),
    }
    try:
        validate_event_log(events, expected_session_id=str(session.get("session_id") or ""))
        gates["event_log_valid"] = True
    except ValueError:
        gates["event_log_valid"] = False
    failures = [key for key, passed in gates.items() if not passed]
    unsigned = {
        "schema_version": ACTIONABLE_RESEARCH_EVALUATION_SCHEMA_VERSION,
        "status": "pass" if not failures else "fail",
        "case_key": current["case_key"],
        "actionable_state_digest": current.get("actionable_state_digest"),
        "quantitative_authority_digest": quant.get(
            "quantitative_authority_digest"
        ),
        "gates": gates,
        "failed_gates": failures,
        "summary": {
            "gate_count": len(gates),
            "passed_gate_count": sum(bool(value) for value in gates.values()),
            "failed_gate_count": len(failures),
            "actionable_uncertainty_count": len(uncertainties),
            "research_action_count": len(actions),
            "reported_fact_count": len(quant.get("reported_facts") or ()),
            "derived_metric_count": len(
                quant.get("deterministic_derived_metrics") or ()
            ),
        },
        "authority": {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "S1_qualification_claimed": False,
            "S3_acceptance_claimed": False,
            "release_claimed": False,
        },
    }
    return {**unsigned, "evaluation_digest": canonical_digest(unsigned)}


__all__ = [
    "ACTIONABLE_RESEARCH_EVALUATION_SCHEMA_VERSION",
    "ActionableResearchEvaluationError",
    "evaluate_actionable_research_state",
]
