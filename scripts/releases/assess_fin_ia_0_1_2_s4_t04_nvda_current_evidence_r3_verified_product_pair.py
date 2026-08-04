from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (  # noqa: E402
    validate_verified_product_surface,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_capacity_reproof_exact_live import (  # noqa: E402
    ADMISSION,
    EXECUTION_IDENTITY,
    EXPECTED_ADMISSION_DIGEST,
    EXPECTED_ISSUANCE_DIGEST,
    ISSUANCE,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t04_nvda_current_evidence_exact_live import (  # noqa: E402
    load_exact_target_for,
    prepare_exact_current_input,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EXACT_RESULT = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t04-nvda-current-evidence-capacity-reproof-exact-live-r3/"
    "execution-result.json"
)
SURFACE_RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
    "verified_product_surface_and_read_only_assessment_v1_0.json"
)
BASELINE_RUNTIME = ROOT / (
    ".codex_runtime/"
    "fin012-s4-t04-nvda-current-evidence-deterministic-baseline-r1"
)
BASELINE_RESULT = BASELINE_RUNTIME / "execution-result.json"
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
    "formal_paired_assessment_and_owner_decision_request_v1_0.json"
)


class S4T04PairedAssessmentError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S4T04PairedAssessmentError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t04_paired_json_object_required")
    return value


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        existing = _load(path)
        _require(
            existing.get("schema_version") == value.get("schema_version"),
            "s4_t04_paired_output_schema_mismatch",
        )
        if path.read_text(encoding="utf-8") == encoded:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def _prepared_input() -> dict[str, Any]:
    admission, issuance = load_exact_target_for(
        admission_path=ADMISSION,
        issuance_path=ISSUANCE,
        expected_admission_digest=EXPECTED_ADMISSION_DIGEST,
        expected_issuance_digest=EXPECTED_ISSUANCE_DIGEST,
        execution_identity=EXECUTION_IDENTITY,
    )
    with tempfile.TemporaryDirectory(
        prefix="fin012-s4-t04-r3-paired-baseline-"
    ) as temporary:
        prepared = prepare_exact_current_input(
            Path(temporary),
            admission,
            issuance,
            execution_identity=EXECUTION_IDENTITY,
        )
    return prepared.input_pack.model_dump(mode="json")


def materialize_deterministic_baseline(
    input_pack: Mapping[str, Any],
) -> dict[str, Any]:
    input_digest = str(input_pack.get("input_digest") or "")
    _require(input_digest != "", "s4_t04_baseline_input_digest_required")
    identity_seed = canonical_digest(
        {
            "contract_ref": (
                "fin_0_1_2.s4_t04.current_evidence_deterministic_baseline:v1"
            ),
            "input_digest": input_digest,
            "execution_profile": "zero_call_authority_projection_only",
        }
    )
    cells = []
    for row in input_pack.get("cell_inputs", ()):
        authority = row.get("authority_refs") or {}
        cells.append(
            {
                "program_cell_id": str(row.get("program_cell_id") or ""),
                "decision_question": str(
                    (row.get("runtime_branch") or {}).get("decision_question")
                    or ""
                ),
                "accepted_evidence_refs": sorted(
                    str(ref)
                    for ref in authority.get("accepted_evidence_refs", ())
                ),
                "numeric_refs": sorted(
                    str(ref) for ref in authority.get("numeric_refs", ())
                ),
                "candidate_refs_not_evidence": sorted(
                    str(ref)
                    for ref in authority.get(
                        "candidate_refs_not_evidence", ()
                    )
                ),
                "deterministic_output_boundary": (
                    "authority_inventory_only_no_claim_or_causal_inference"
                ),
            }
        )
    artifact_body = {
        "contract_ref": (
            "fin_0_1_2.s4_t04.current_evidence_deterministic_baseline:v1"
        ),
        "input_digest": input_digest,
        "input_head_digest": str(input_pack.get("input_head_digest") or ""),
        "case_id": str(input_pack.get("case_id") or ""),
        "case_version": int(input_pack.get("case_version") or 0),
        "as_of": str(input_pack.get("as_of") or ""),
        "program_cells": cells,
        "claims": [],
        "cross_cell_dependencies": [],
        "conflict_adjudications": [],
        "remaining_gaps": [],
        "what_would_change": [],
        "hard_boundary": (
            "The baseline inventories approved authority only and does not "
            "manufacture judgment, causal synthesis or delivery prose."
        ),
    }
    artifact = {
        "artifact_type": "bounded_deterministic_baseline",
        "payload": {
            **artifact_body,
            "artifact_digest": canonical_digest(artifact_body),
        },
    }
    result_body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t04_current_evidence_"
            "deterministic_baseline_result_v1_0"
        ),
        "status": "success",
        "business_promotable": False,
        "execution_identity": (
            "fin012-s4-t04-nvda-current-evidence-deterministic-baseline-r1"
        ),
        "work_unit_id": f"wu_s4_t04_baseline_{identity_seed[:20]}",
        "attempt_id": f"attempt_s4_t04_baseline_{identity_seed[20:40]}",
        "research_run_id": f"research_run_s4_t04_baseline_{identity_seed[40:60]}",
        "input_digest": input_digest,
        "input_head_digest": str(input_pack.get("input_head_digest") or ""),
        "artifacts": [artifact],
        "terminal": {
            "status": "success",
            "phase": "complete",
            "code": "s4_t04_zero_call_deterministic_baseline_success",
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "business_writes": 0,
            "artifacts": 1,
        },
    }
    return {**result_body, "result_digest": canonical_digest(result_body)}


def validate_pair_binding(
    *,
    exact_result: Mapping[str, Any],
    baseline_result: Mapping[str, Any],
    surface_record: Mapping[str, Any],
) -> None:
    baseline_body = {
        key: value
        for key, value in baseline_result.items()
        if key != "result_digest"
    }
    _require(
        baseline_result.get("result_digest") == canonical_digest(baseline_body),
        "s4_t04_baseline_result_digest_mismatch",
    )
    artifacts = {
        str(row["artifact_type"]): row["payload"]
        for row in exact_result.get("artifacts", ())
    }
    manifest = artifacts["bounded_agent_manifest"]
    comparison = artifacts["agent_fallback_comparison"]
    _require(
        exact_result.get("status") == "success"
        and exact_result.get("business_promotable") is True
        and baseline_result.get("status") == "success",
        "s4_t04_pair_terminal_success_required",
    )
    _require(
        manifest.get("input_digest") == baseline_result.get("input_digest")
        == comparison.get("paired_input_digest"),
        "s4_t04_pair_input_digest_mismatch",
    )
    shared_head = (comparison.get("paired_baseline_contract") or {}).get(
        "shared_input_head_digest"
    )
    _require(
        shared_head == baseline_result.get("input_head_digest"),
        "s4_t04_pair_input_head_digest_mismatch",
    )
    _require(
        str(baseline_result.get("research_run_id") or "")
        != "research_run_fin01_26d57efecdc53fbf28847a1f",
        "s4_t04_pair_runs_must_be_distinct",
    )
    _require(
        len(exact_result.get("artifacts") or ()) == 9
        and len(baseline_result.get("artifacts") or ()) == 1,
        "s4_t04_pair_artifacts_must_be_distinct",
    )
    validate_verified_product_surface(surface_record["product_surface"])


def assess() -> tuple[dict[str, Any], dict[str, Any]]:
    input_pack = _prepared_input()
    exact_result = _load(EXACT_RESULT)
    surface_record = _load(SURFACE_RESULT)
    baseline = materialize_deterministic_baseline(input_pack)
    validate_pair_binding(
        exact_result=exact_result,
        baseline_result=baseline,
        surface_record=surface_record,
    )
    artifacts = {
        str(row["artifact_type"]): row["payload"]
        for row in exact_result["artifacts"]
    }
    judgment = artifacts["bounded_agent_judgment"]
    specialists = judgment["specialist_outputs"]
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
    lead = judgment["cross_cell_lead"]
    qualification = surface_record["product_surface"][
        "fixture_evidence_qualification"
    ]
    assessment_body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t04_nvda_current_evidence_r3_"
            "formal_paired_assessment_and_owner_decision_request_v1_0"
        ),
        "status": "paired_L1_L4_pass_owner_decision_required",
        "pair_binding": {
            "same_input_digest": str(baseline["input_digest"]),
            "same_input_head_digest": str(baseline["input_head_digest"]),
            "agent_research_run_id": (
                "research_run_fin01_26d57efecdc53fbf28847a1f"
            ),
            "deterministic_research_run_id": baseline["research_run_id"],
            "runs_are_distinct": True,
            "agent_artifacts": 9,
            "deterministic_artifacts": 1,
        },
        "L1_deterministic_integrity": {
            "status": "pass",
            "basis": (
                "R3 independent integrity, numeric, lineage and capture audit"
            ),
        },
        "L2_evidence_reliability_and_coverage": {
            "status": "pass_bounded_authority_coverage",
            "evidence_cells": qualification["qualified_evidence_cells"],
            "authority_cells": qualification["qualified_authority_cells"],
            "basis": (
                "Demand and bottleneck use promoted Evidence; value/profit uses "
                "exact Numeric authority with an explicit causal limitation."
            ),
        },
        "L3_agent_gain": {
            "status": "pass_limited_material_gain_with_quality_finding",
            "baseline_claim_dependency_conflict_gap_WWC": [0, 0, 0, 0, 0],
            "agent_claim_dependency_conflict_gap_WWC": [
                sum(len(row.get("judgment_layer") or ()) for row in specialists),
                len(lead.get("cross_cell_dependencies") or ()),
                len(lead.get("conflict_adjudications") or ()),
                len(lead.get("remaining_gaps") or ()),
                len(tasks),
            ],
            "material_gain": (
                "bounded claim synthesis, cross-cell dependency/conflict/gap "
                "organization and reviewable follow-up structure"
            ),
            "quality_finding": (
                f"{generic_tasks}/{len(tasks)} WWC tasks retain generic "
                "threshold wording; record for T08-T10/S5 calibration and do "
                "not reopen the successful T04 model chain."
            ),
        },
        "L4_final_delivery": {
            "status": "pass",
            "preview_digest": surface_record["product_surface"][
                "final_delivery_preview"
            ]["final_delivery_preview_digest"],
            "local_verifier_digest": surface_record["product_surface"][
                "final_delivery_verification"
            ]["verification_digest"],
            "internal_tokens_currency_duplication_or_unlocalized_limitation": 0,
        },
        "owner_decision_request": {
            "status": "awaiting_explicit_user_owner_decision",
            "recommended_decision": "accept_current_NVDA_R2_with_L3_finding",
            "material_gain_accepted": None,
            "owner_comment": None,
        },
        "acceptance_boundary": {
            "RC_P36_118": "closed_zero_call_R3_replay_and_paired_L4_positive",
            "S4_T04_engineering": "pass",
            "S4_T04_exact_live": "pass",
            "formal_paired_L1_L4": "pass",
            "current_source_grounded_NVDA_R2": False,
            "S4_T05_entry": "blocked_pending_owner_decision",
        },
        "observed_counts": {
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_execution_network_calls": 0,
            "new_source_network_calls": 0,
            "new_external_tool_calls": 0,
            "exact_live_reruns": 0,
            "R4_attempts": 0,
            "deterministic_baseline_runs": 1,
            "paired_assessments": 1,
            "owner_decisions": 0,
        },
        "source_refs": {
            "exact_result": EXACT_RESULT.relative_to(ROOT).as_posix(),
            "exact_result_sha256": hashlib.sha256(
                EXACT_RESULT.read_bytes()
            ).hexdigest(),
            "product_surface": SURFACE_RESULT.relative_to(ROOT).as_posix(),
            "product_surface_sha256": hashlib.sha256(
                SURFACE_RESULT.read_bytes()
            ).hexdigest(),
            "deterministic_baseline": BASELINE_RESULT.relative_to(
                ROOT
            ).as_posix(),
        },
        "recommended_next": (
            "USER-OWNER-DECISION-ACCEPT-OR-REJECT-CURRENT-NVDA-R2-"
            "THEN-S4-T05-ENTRY"
        ),
    }
    return baseline, {
        **assessment_body,
        "assessment_digest": canonical_digest(assessment_body),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    baseline, assessment = assess()
    _write_atomic(BASELINE_RESULT, baseline)
    _write_atomic(args.output.resolve(), assessment)
    print(
        json.dumps(
            {
                "status": assessment["status"],
                "baseline_result": BASELINE_RESULT.as_posix(),
                "assessment_output": args.output.resolve().as_posix(),
                "assessment_digest": assessment["assessment_digest"],
                "recommended_owner_decision": assessment[
                    "owner_decision_request"
                ]["recommended_decision"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
