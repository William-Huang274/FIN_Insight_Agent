from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_t05_current_case_product_surface import (  # noqa: E402
    validate_current_case_pair_readiness,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_c_mu_agent_exact_live_result_and_assessment import (  # noqa: E402
    EXACT_RESULT,
    EXPECTED_RESULT_SHA256,
    OUTPUT as EXACT_ASSESSMENT,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t05_c_mu_verified_product_surface_and_paired_readiness import (  # noqa: E402
    BASELINE_RESULT,
    DEFAULT_OUTPUT as SURFACE_RESULT,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EXPECTED_SURFACE_RECORD_DIGEST = (
    "c9608e312fe7bf6e3b77ba86b50b533456461c45297060311cc3fc85dea15272"
)
EXPECTED_BASELINE_RESULT_DIGEST = (
    "ac739cdd5412d503c9b3bb77964a637d6673f3d73b95e047982c702bc497d6a1"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_formal_paired_"
    "assessment_and_owner_decision_request_v1_0.json"
)


class T05CMUFormalPairedAssessmentError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05CMUFormalPairedAssessmentError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_c_mu_paired_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_map(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["artifact_type"]): row["payload"]
        for row in result.get("artifacts", ())
        if isinstance(row, Mapping) and isinstance(row.get("payload"), Mapping)
    }


def assess() -> dict[str, Any]:
    _require(
        _sha256(EXACT_RESULT) == EXPECTED_RESULT_SHA256,
        "s4_t05_c_mu_paired_exact_result_drift",
    )
    exact = _load(EXACT_RESULT)
    exact_assessment = _load(EXACT_ASSESSMENT)
    surface_record = _load(SURFACE_RESULT)
    baseline = _load(BASELINE_RESULT)
    _require(
        surface_record.get("record_digest") == EXPECTED_SURFACE_RECORD_DIGEST,
        "s4_t05_c_mu_paired_surface_record_drift",
    )
    _require(
        baseline.get("result_digest") == EXPECTED_BASELINE_RESULT_DIGEST,
        "s4_t05_c_mu_paired_baseline_result_drift",
    )
    readiness = validate_current_case_pair_readiness(
        exact_result=exact,
        baseline_result=baseline,
        surface_result=surface_record["product_surface"],
        expected_case_ticker="MU",
    )
    _require(
        readiness.get("status") == "ready_for_formal_paired_assessment",
        "s4_t05_c_mu_paired_readiness_invalid",
    )
    artifacts = _artifact_map(exact)
    judgment = artifacts["bounded_agent_judgment"]
    specialists = judgment["specialist_outputs"]
    lead = judgment["cross_cell_lead"]
    tasks = [
        task
        for specialist in specialists
        for task in specialist.get("what_would_change", ())
    ]
    generic_tasks = sum(
        "绑定权威观察"
        in str(
            (task.get("decision_rule") or {}).get(
                "threshold_or_observation"
            )
            or ""
        )
        for task in tasks
    )
    qualification = surface_record["product_surface"][
        "fixture_evidence_qualification"
    ]
    preview = surface_record["product_surface"]["final_delivery_preview"]
    verifier = surface_record["product_surface"][
        "final_delivery_verification"
    ]
    agent_counts = [
        sum(len(row.get("judgment_layer") or ()) for row in specialists),
        len(lead.get("cross_cell_dependencies") or ()),
        len(lead.get("conflict_adjudications") or ()),
        len(lead.get("remaining_gaps") or ()),
        len(tasks),
    ]
    _require(
        agent_counts == [6, 1, 3, 4, 9] and generic_tasks == 9,
        "s4_t05_c_mu_paired_agent_gain_counts_drift",
    )
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_c_mu_formal_paired_assessment_and_"
            "owner_decision_request_v1_0"
        ),
        "recorded_at": "2026-08-05T15:30:00+08:00",
        "status": (
            "paired_L1_L4_pass_limited_gain_quality_findings_"
            "owner_decision_required"
        ),
        "pair_binding": {
            "same_input_digest": readiness["same_input_digest"],
            "same_input_head_digest": readiness["same_input_head_digest"],
            "agent_research_run_id": readiness["agent_research_run_id"],
            "deterministic_research_run_id": readiness[
                "deterministic_research_run_id"
            ],
            "runs_are_distinct": True,
            "agent_artifacts": 9,
            "deterministic_artifacts": 1,
            "baseline_output_body_exposed_to_agent": False,
        },
        "L1_deterministic_integrity": {
            "status": "pass",
            "basis": exact_assessment["independent_L1"],
        },
        "L2_evidence_reliability_and_coverage": {
            "status": "pass_bounded_authority_coverage",
            "evidence_cells": qualification["qualified_evidence_cells"],
            "authority_cells": qualification["qualified_authority_cells"],
            "basis": (
                "All three MU Cells are bound to approved current Evidence or "
                "exact company Numeric authority; candidate metadata and HBM "
                "profit attribution are not promoted beyond their authority."
            ),
        },
        "L3_agent_gain": {
            "status": "pass_limited_material_gain_with_quality_findings",
            "baseline_claim_dependency_conflict_gap_WWC": [0, 0, 0, 0, 0],
            "agent_claim_dependency_conflict_gap_WWC": agent_counts,
            "material_gain": (
                "The Agent adds six bounded Claim Cards, one cross-cell "
                "dependency, three explicit unresolved conflict cards, four "
                "typed gaps and nine claim-bound follow-up tasks over the "
                "authority-only baseline."
            ),
            "comparison_limitation": (
                "The deterministic baseline intentionally inventories authority "
                "without judgment. MU's gain is organizational and auditable, "
                "but the current memo does not yet provide a strong company-"
                "specific investment thesis or resolved cross-cell synthesis."
            ),
            "quality_findings": [
                {
                    "issue": "RC-P36-119",
                    "finding": (
                        "9/9 what-would-change tasks retain generic threshold "
                        "wording instead of measurable MU observations."
                    ),
                    "disposition": "nonblocking_deferred_T08_T10_S5",
                },
                {
                    "issue": "RC-P36-122",
                    "finding": (
                        "The single dependency, three conflicts and four gaps "
                        "mostly restate epistemic states and review status; all "
                        "conflicts remain unresolved and MU/HBM-specific "
                        "synthesis is weak."
                    ),
                    "disposition": "nonblocking_deferred_T08_T10_S5",
                },
            ],
        },
        "L4_final_delivery": {
            "status": "pass",
            "preview_digest": preview["final_delivery_preview_digest"],
            "local_verifier_digest": verifier["verification_digest"],
            "case_identity": verifier["checks"]["case_identity"],
            "internal_tokens_currency_duplication_or_unlocalized_limitation": 0,
        },
        "owner_decision_request": {
            "status": "awaiting_explicit_user_owner_decision",
            "recommended_decision": (
                "accept_current_MU_R2_with_RC_P36_119_and_RC_P36_122_deferred"
            ),
            "recommendation_rationale": (
                "Accept only as a bounded internal R2 transfer proof: L1, "
                "authority coverage and delivery integrity pass, while the "
                "limited research-quality findings remain explicit and are "
                "not used to claim R3, release or production quality."
            ),
            "material_gain_accepted": None,
            "owner_comment": None,
            "accept_effect": (
                "Close T05-C, set MU current R2=true, and authorize T05-D "
                "post-transfer NVDA entry while carrying RC-P36-119/122 to "
                "T08-T10/S5."
            ),
            "reject_effect": (
                "Keep MU R2=false and T05-D blocked; record the product reason "
                "without rerunning the successful MU Search or Agent chain."
            ),
        },
        "acceptance_boundary": {
            "S4_T05_C_MU_engineering": "pass",
            "S4_T05_C_MU_search_exact_live": "pass",
            "S4_T05_C_MU_agent_exact_live": "pass",
            "S4_T05_C_MU_final_delivery": "pass",
            "formal_paired_L1_L4": "pass_limited_gain_with_findings",
            "MU_current_R2": False,
            "S4_T05_C_closeout": "blocked_pending_owner_decision",
            "S4_T05_D_entry": "blocked_pending_owner_decision",
            "release": "not_qualified",
            "production": "not_qualified",
        },
        "observed_counts": {
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_execution_network_calls": 0,
            "new_source_network_calls": 0,
            "new_external_tool_calls": 0,
            "exact_live_reruns": 0,
            "deterministic_baseline_runs": 0,
            "formal_paired_assessments": 1,
            "owner_decisions": 0,
        },
        "source_refs": {
            "exact_result": EXACT_RESULT.relative_to(ROOT).as_posix(),
            "exact_result_sha256": _sha256(EXACT_RESULT),
            "exact_assessment": EXACT_ASSESSMENT.relative_to(ROOT).as_posix(),
            "exact_assessment_sha256": _sha256(EXACT_ASSESSMENT),
            "product_surface": SURFACE_RESULT.relative_to(ROOT).as_posix(),
            "product_surface_sha256": _sha256(SURFACE_RESULT),
            "deterministic_baseline": BASELINE_RESULT.relative_to(
                ROOT
            ).as_posix(),
            "deterministic_baseline_sha256": _sha256(BASELINE_RESULT),
        },
        "recommended_next": (
            "USER-OWNER-DECISION-ACCEPT-OR-REJECT-CURRENT-MU-R2-"
            "THEN-CLOSE-T05-C-OR-HOLD"
        ),
    }
    return validate_formal_paired_assessment(
        {**body, "assessment_digest": canonical_digest(body)}
    )


def validate_formal_paired_assessment(
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        key: value
        for key, value in assessment.items()
        if key != "assessment_digest"
    }
    _require(
        assessment.get("assessment_digest") == canonical_digest(body),
        "s4_t05_c_mu_paired_assessment_digest_mismatch",
    )
    owner = assessment.get("owner_decision_request") or {}
    boundary = assessment.get("acceptance_boundary") or {}
    counts = assessment.get("observed_counts") or {}
    _require(
        assessment.get("status")
        == (
            "paired_L1_L4_pass_limited_gain_quality_findings_"
            "owner_decision_required"
        )
        and (assessment.get("L1_deterministic_integrity") or {}).get("status")
        == "pass"
        and str(
            (assessment.get("L2_evidence_reliability_and_coverage") or {}).get(
                "status"
            )
            or ""
        ).startswith("pass_")
        and (assessment.get("L3_agent_gain") or {}).get("status")
        == "pass_limited_material_gain_with_quality_findings"
        and (assessment.get("L4_final_delivery") or {}).get("status") == "pass",
        "s4_t05_c_mu_paired_layer_status_invalid",
    )
    _require(
        owner.get("status") == "awaiting_explicit_user_owner_decision"
        and owner.get("material_gain_accepted") is None
        and owner.get("owner_comment") is None
        and boundary.get("MU_current_R2") is False
        and boundary.get("S4_T05_C_closeout")
        == "blocked_pending_owner_decision"
        and counts.get("owner_decisions") == 0,
        "s4_t05_c_mu_paired_owner_boundary_invalid",
    )
    gain = assessment.get("L3_agent_gain") or {}
    findings = gain.get("quality_findings") or ()
    _require(
        gain.get("baseline_claim_dependency_conflict_gap_WWC")
        == [0, 0, 0, 0, 0]
        and gain.get("agent_claim_dependency_conflict_gap_WWC")
        == [6, 1, 3, 4, 9]
        and [row.get("issue") for row in findings]
        == ["RC-P36-119", "RC-P36-122"],
        "s4_t05_c_mu_paired_agent_gain_or_finding_invalid",
    )
    return dict(assessment)


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == encoded:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    assessment = assess()
    _write_atomic(args.output.resolve(), assessment)
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "output": args.output.resolve().as_posix(),
                "assessment_digest": assessment["assessment_digest"],
                "recommended_owner_decision": assessment[
                    "owner_decision_request"
                ]["recommended_decision"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
