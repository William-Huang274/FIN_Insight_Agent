from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPT_ROOT))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE,
    BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE,
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
    build_bounded_agent_input_pack,
)
from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.execution_service import VT1_WORK_UNIT_TYPE
from apps.workbench.backend.application.local_research_service import P36LocalResearchService
from apps.workbench.backend.application.research_runtime import (
    FIN01_DETERMINISTIC_ARTIFACT_TYPE,
    FIN01_DETERMINISTIC_PROFILE_REF,
)
from run_fin_ia_0_1_s2_t04_validate_live_artifacts import (
    load_exact_run_artifacts,
    validate_t04_artifacts,
)
from sec_agent.canonical_runtime.models import canonical_digest


TENANT_ID = "tenant-fin01-s2-t03-eval"
PROJECT_ID = "project-fin01-s2-t03-eval"
ACTOR_ID = "analyst-fin01-s2-t03-eval"
PERMISSIONS = frozenset(
    (
        "case:create",
        "case:read",
        "planning:write",
        "planning:review",
        "planning:read",
        "execution:write",
        "execution:read",
        "activity:read",
        "evidence:read",
    )
)
T05_DETERMINISTIC_WORK_UNIT_KEY = (
    "fin01-s2-t05-exact-paired-deterministic-baseline-r1"
)


class T05ValidationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05ValidationError(code)


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=PERMISSIONS,
    )


def _artifact_identity_snapshot(
    facade: Any, *, attempt_id: str
) -> dict[str, tuple[str, str]]:
    rows = [
        row
        for row in facade.store.list_latest("canonical_artifact_versions")
        if row.get("producer_attempt_id") == attempt_id
    ]
    return {
        str(row["artifact_version_id"]): (
            str(row.get("object_digest") or ""),
            str(row.get("content_digest") or ""),
        )
        for row in rows
    }


def _derive_baseline_from_analysis(analysis: Mapping[str, Any]) -> dict[str, Any]:
    judgments = [
        row
        for row in analysis.get("judgments", ())
        if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
    ]
    sections = [
        row
        for row in (analysis.get("workpaper") or {}).get("sections", ())
        if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
    ]
    writer_sections = [
        row
        for row in (analysis.get("writer") or {}).get("sections", ())
        if isinstance(row, Mapping) and row.get("evidence_role") == "demand_signal"
    ]
    _require(len(judgments) == 1, "t05_one_deterministic_judgment_required")
    _require(len(sections) == 1, "t05_one_deterministic_workpaper_section_required")
    return {
        "run_kind": "deterministic_paired_baseline",
        "analysis_digest": analysis["analysis_digest"],
        "judgment": dict(judgments[0]),
        "workpaper_section": dict(sections[0]),
        "writer_sections": [dict(row) for row in writer_sections],
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "external_tool_calls": 0,
        },
    }


def _wait_for_profile_run(
    client: TestClient,
    *,
    case_id: str,
    profile_ref: str,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        response = client.get(
            f"/api/v1/cases/{case_id}/execution-projection", headers=_headers()
        )
        _require(response.status_code == 200, "t05_execution_projection_failed")
        runs = [
            row
            for row in response.json().get("runs", ())
            if row.get("execution_profile_version_ref") == profile_ref
        ]
        _require(len(runs) <= 1, "t05_profile_run_cardinality_violation")
        if runs and runs[0].get("state") in {"succeeded", "failed", "cancelled"}:
            return dict(runs[0])
        time.sleep(0.1)
    raise T05ValidationError("t05_deterministic_run_terminal_timeout")


def materialize_exact_deterministic_run(
    runtime_root: Path,
    *,
    expected_agent_run_id: str,
    expected_agent_attempt_id: str,
    expected_input_digest: str,
) -> dict[str, Any]:
    """Create exactly one zero-call baseline Run in the T03 evaluation store."""

    case_service = CaseService.for_fixture_root(
        runtime_root / "canonical-runtime", repo_root=ROOT
    )
    facade = case_service._facade
    agent_runs = [
        row
        for row in facade.store.list_latest("canonical_research_run_versions")
        if row.get("research_run_id") == expected_agent_run_id
    ]
    _require(len(agent_runs) == 1, "t05_exact_agent_run_required")
    _require(agent_runs[0].get("state") == "succeeded", "t05_agent_run_not_succeeded")
    _require(
        agent_runs[0].get("attempt_id") == expected_agent_attempt_id,
        "t05_agent_attempt_binding_mismatch",
    )
    agent_artifacts_before = _artifact_identity_snapshot(
        facade, attempt_id=expected_agent_attempt_id
    )
    _require(len(agent_artifacts_before) == 9, "t05_exact_agent_artifact_set_required")

    local = P36LocalResearchService.from_case_service(case_service, repo_root=ROOT)
    pack = build_bounded_agent_input_pack(
        local, str(agent_runs[0]["case_id"]), _principal()
    )
    _require(pack.input_digest == expected_input_digest, "t05_exact_input_digest_mismatch")
    planning = [
        row
        for row in facade.store.list_latest(
            "canonical_planning_checkpoint_versions", case_id=pack.case_id
        )
        if row.get("review_status") == "accepted"
    ]
    _require(len(planning) == 1, "t05_exact_accepted_planning_checkpoint_required")

    deterministic_runs = [
        row
        for row in facade.store.list_latest(
            "canonical_research_run_versions", case_id=pack.case_id
        )
        if row.get("execution_profile_version_ref") == FIN01_DETERMINISTIC_PROFILE_REF
    ]
    created = False
    if not deterministic_runs:
        app = create_app(
            runtime_root / "workbench.sqlite",
            p02_case_service=case_service,
            p36_local_research_service=local,
        )
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/cases/{pack.case_id}/work-units",
                headers=_headers(),
                json={
                    "work_unit_type": VT1_WORK_UNIT_TYPE,
                    "expected_case_version": pack.case_version,
                    "input_head_digest": canonical_digest(
                        (planning[0]["contract_version_id"],)
                    ),
                    "actor_ref": ACTOR_ID,
                    "idempotency_key": T05_DETERMINISTIC_WORK_UNIT_KEY,
                },
            )
            _require(response.status_code == 202, "t05_deterministic_work_unit_failed")
            terminal = _wait_for_profile_run(
                client,
                case_id=pack.case_id,
                profile_ref=FIN01_DETERMINISTIC_PROFILE_REF,
            )
        _require(terminal.get("state") == "succeeded", "t05_deterministic_run_failed")
        created = True

    deterministic_runs = [
        row
        for row in facade.store.list_latest(
            "canonical_research_run_versions", case_id=pack.case_id
        )
        if row.get("execution_profile_version_ref") == FIN01_DETERMINISTIC_PROFILE_REF
    ]
    _require(len(deterministic_runs) == 1, "t05_exact_one_deterministic_run_required")
    deterministic_run = deterministic_runs[0]
    _require(
        deterministic_run.get("state") == "succeeded",
        "t05_deterministic_run_not_succeeded",
    )
    _require(
        deterministic_run.get("research_run_id") != expected_agent_run_id,
        "t05_agent_and_baseline_runs_must_be_distinct",
    )
    baseline_work_unit = facade.store.get_latest(
        "canonical_work_units", str(deterministic_run["work_unit_id"])
    )
    _require(
        baseline_work_unit is not None
        and baseline_work_unit.get("idempotency_key") == T05_DETERMINISTIC_WORK_UNIT_KEY,
        "t05_exact_baseline_work_unit_identity_required",
    )
    baseline_attempt_id = str(deterministic_run["attempt_id"])
    baseline_rows = [
        row
        for row in facade.store.list_latest(
            "canonical_artifact_versions", case_id=pack.case_id
        )
        if row.get("producer_attempt_id") == baseline_attempt_id
    ]
    _require(len(baseline_rows) == 1, "t05_one_baseline_artifact_required")
    _require(
        baseline_rows[0].get("artifact_type") == FIN01_DETERMINISTIC_ARTIFACT_TYPE,
        "t05_baseline_artifact_type_mismatch",
    )
    baseline_artifact = facade.get_artifact_version(
        str(baseline_rows[0]["artifact_version_id"]), include_payload=True
    )
    baseline_payload = baseline_artifact["payload"]
    analysis = baseline_payload.get("result")
    _require(isinstance(analysis, Mapping), "t05_baseline_analysis_required")
    reconstructed_baseline = _derive_baseline_from_analysis(analysis)
    _require(
        canonical_digest(reconstructed_baseline)
        == canonical_digest(pack.deterministic_baseline),
        "t05_embedded_and_canonical_baseline_mismatch",
    )
    hard_boundaries = analysis.get("hard_boundaries") or {}
    execution_counts = analysis.get("execution_counts") or {}
    for field in ("case_mutations", "canonical_store_writes", "network_calls"):
        _require(hard_boundaries.get(field) == 0, f"t05_baseline_boundary_failed:{field}")
    for field in ("model_calls", "provider_calls", "network_calls", "external_tool_calls"):
        _require(execution_counts.get(field) == 0, f"t05_baseline_call_boundary_failed:{field}")

    agent_artifacts_after = _artifact_identity_snapshot(
        facade, attempt_id=expected_agent_attempt_id
    )
    _require(
        agent_artifacts_before == agent_artifacts_after,
        "t05_agent_artifact_identity_or_digest_changed",
    )
    return {
        "created_in_this_execution": created,
        "input_pack": pack.model_dump(mode="json"),
        "run": deterministic_run,
        "artifact_metadata": baseline_rows[0],
        "artifact_payload": baseline_payload,
        "reconstructed_baseline": reconstructed_baseline,
        "agent_artifacts_unchanged": True,
    }


def assess_exact_pair(
    agent_artifacts: Mapping[str, Mapping[str, Any]],
    baseline: Mapping[str, Any],
    *,
    expected_agent_run_id: str,
    expected_agent_attempt_id: str,
    expected_input_digest: str,
) -> dict[str, Any]:
    t04 = validate_t04_artifacts(
        agent_artifacts,
        expected_input_digest=expected_input_digest,
        expected_research_run_id=expected_agent_run_id,
        expected_attempt_id=expected_agent_attempt_id,
    )
    payloads = {key: row["payload"] for key, row in agent_artifacts.items()}
    comparison = payloads[BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE]
    evidence = payloads[BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE]
    judgment = payloads[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE]
    report = payloads[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]["report"]
    verification = payloads[BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE]
    baseline_run = baseline["run"]
    baseline_payload = baseline["artifact_payload"]
    reconstructed = baseline["reconstructed_baseline"]

    _require(
        comparison.get("paired_input_digest") == expected_input_digest,
        "t05_comparison_input_digest_mismatch",
    )
    _require(
        canonical_digest(comparison.get("deterministic_baseline"))
        == canonical_digest(reconstructed),
        "t05_comparison_baseline_payload_mismatch",
    )
    baseline_run_id = str(baseline_run.get("research_run_id") or "")
    _require(baseline_run_id != "", "t05_baseline_run_id_required")
    _require(
        baseline_run_id != expected_agent_run_id,
        "t05_agent_and_baseline_runs_must_be_distinct",
    )
    _require(
        baseline_payload.get("case_id") == baseline["input_pack"]["case_id"],
        "t05_baseline_case_binding_mismatch",
    )
    _require(
        verification["deterministic_integrity"]["status"] == "pass",
        "t05_agent_hard_integrity_regression",
    )

    deterministic_judgment = reconstructed["judgment"]
    agent_specialist = judgment["specialist_judgment"]
    agent_lead = judgment["lead_adjudication"]
    baseline_refs = set(deterministic_judgment.get("evidence_refs") or ())
    promoted_refs = set(evidence.get("candidate_refs") or ())
    agent_refs = set(agent_lead.get("evidence_refs") or ())
    _require(
        baseline_refs == promoted_refs == agent_refs,
        "t05_pair_evidence_surface_mismatch",
    )
    baseline_gaps = list(deterministic_judgment.get("remaining_gaps") or ())
    agent_gaps = list(agent_lead.get("remaining_gaps") or ())
    baseline_wwc = [deterministic_judgment.get("what_would_change_en")]
    baseline_wwc = [item for item in baseline_wwc if item]
    agent_wwc = list(agent_lead.get("what_would_change") or ())
    agent_findings = list(agent_specialist.get("evidence_findings") or ())
    baseline_writer_sections = list(reconstructed.get("writer_sections") or ())
    agent_sections = list(report.get("sections") or ())
    limitations = list(report.get("limitations_zh_cn") or ())

    _require(len(agent_gaps) > len(baseline_gaps), "t05_gap_granularity_gain_required")
    _require(len(agent_wwc) > len(baseline_wwc), "t05_wwc_granularity_gain_required")
    _require(
        len(agent_sections) > len(baseline_writer_sections),
        "t05_report_structure_gain_required",
    )
    _require(
        len(agent_findings) == len(promoted_refs)
        and all(str(row.get("boundary") or "").strip() for row in agent_findings),
        "t05_evidence_boundary_gain_required",
    )
    _require(bool(limitations), "t05_report_limitations_required")

    dimensions = {
        "direct_answer": {
            "result": "tie_both_answer_the_cell",
            "basis": "deterministic judgment and Agent thesis both answer authenticity and durability",
        },
        "evidence_authority": {
            "result": "tie_same_exact_local_official_candidate_set",
            "evidence_ref_count": len(promoted_refs),
        },
        "numeric_bridge": {
            "result": "no_new_numeric_gain_agent_has_clearer_typed_gap",
            "unsupported_precision": False,
        },
        "mechanism_depth": {
            "result": "agent_material_gain",
            "basis": "Agent separates capacity/energy, supply-constraint, and one-time-versus-secular durability mechanisms",
        },
        "counterevidence": {
            "result": "agent_material_gain_in_evidence_bounded_counter_thesis",
            "finding_count": len(agent_findings),
        },
        "boundary_and_cannot_infer": {
            "result": "agent_material_gain",
            "baseline_gap_count": len(baseline_gaps),
            "agent_gap_count": len(agent_gaps),
        },
        "what_would_change": {
            "result": "agent_material_gain",
            "baseline_count": len(baseline_wwc),
            "agent_count": len(agent_wwc),
        },
        "workpaper_reconstructability": {
            "result": "agent_material_gain",
            "basis": "Agent output has an exact nine-ArtifactVersion manifest; baseline has one deterministic result ArtifactVersion",
        },
        "report_review_burden": {
            "result": "agent_material_gain",
            "baseline_section_count": len(baseline_writer_sections),
            "agent_section_count": len(agent_sections),
            "agent_limitation_count": len(limitations),
        },
    }
    return {
        "status": "technical_comparison_pass_owner_review_required",
        "lineage": {
            "same_case_id": True,
            "same_case_version": True,
            "same_as_of": True,
            "same_input_digest": expected_input_digest,
            "agent_research_run_id": expected_agent_run_id,
            "deterministic_research_run_id": baseline_run_id,
            "runs_are_distinct": True,
            "agent_artifact_count": t04["artifact_count"],
            "agent_artifact_manifest": t04["artifact_manifest"],
            "deterministic_artifact_version_id": baseline["artifact_metadata"][
                "artifact_version_id"
            ],
        },
        "hard_integrity": {
            "status": "pass_no_regression",
            "agent_four_layer_verifier": t04["four_layer_verifier"],
            "agent_artifacts_unchanged_after_baseline_run": baseline[
                "agent_artifacts_unchanged"
            ],
            "baseline_model_provider_network_external_tool_calls": [0, 0, 0, 0],
        },
        "dimensions": dimensions,
        "independent_product_review": {
            "reviewer": "Codex_independent_review_not_owner_signoff",
            "disposition": "material_gain_candidate",
            "material_gain_scope": (
                "reasoning granularity, explicit evidence boundaries, actionable gaps/WWC, "
                "and review-ready report structure"
            ),
            "not_gained": [
                "new source evidence",
                "supported numeric bridge",
                "proof of long-term demand durability",
            ],
            "recommendation": "accept_S2_material_gain_only_if_owner_values_the_reviewability_gain_as_material",
        },
        "owner_product_review": {
            "status": "awaiting_user_owner_decision",
            "material_gain_accepted": None,
            "owner_comment": None,
        },
        "boundary": {
            "new_agent_model_provider_network_calls": [0, 0, 0],
            "new_deterministic_model_provider_network_calls": [0, 0, 0],
            "consumed_agent_admission_rerun": False,
            "live_business_case_head_writes": 0,
            "S3_release_or_production_entered": False,
        },
    }


def run_t05(
    runtime_root: Path,
    *,
    agent_run_id: str,
    agent_attempt_id: str,
    input_digest: str,
) -> dict[str, Any]:
    baseline = materialize_exact_deterministic_run(
        runtime_root,
        expected_agent_run_id=agent_run_id,
        expected_agent_attempt_id=agent_attempt_id,
        expected_input_digest=input_digest,
    )
    agent_artifacts = load_exact_run_artifacts(
        runtime_root,
        expected_research_run_id=agent_run_id,
        expected_attempt_id=agent_attempt_id,
    )
    result = assess_exact_pair(
        agent_artifacts,
        baseline,
        expected_agent_run_id=agent_run_id,
        expected_agent_attempt_id=agent_attempt_id,
        expected_input_digest=input_digest,
    )
    result = {
        "schema_version": "fin_ia_0_1_s2_t05_exact_agent_fallback_review_v1_0",
        "result_id": "S2-T05-EXACT-AGENT-FALLBACK-TECHNICAL-COMPARISON-R1",
        "reviewed_at": "2026-07-21",
        "authority": {
            "S2_T05_technical_comparison_authorized": True,
            "deterministic_baseline_execution_authorized": True,
            "agent_admission_rerun_authorized": False,
            "owner_acceptance_may_be_imputed": False,
            "S3_release_or_production_authorized": False,
        },
        "input_binding": {
            "runtime_root": str(runtime_root.as_posix()),
            "agent_research_run_id": agent_run_id,
            "agent_attempt_id": agent_attempt_id,
            "input_digest": input_digest,
        },
        **result,
    }
    result["baseline_materialization"] = {
        "created_in_this_execution": baseline["created_in_this_execution"],
        "work_unit_idempotency_key": T05_DETERMINISTIC_WORK_UNIT_KEY,
        "research_run_id": baseline["run"]["research_run_id"],
        "attempt_id": baseline["run"]["attempt_id"],
        "artifact_version_id": baseline["artifact_metadata"]["artifact_version_id"],
        "canonical_execution_writes_only": True,
    }
    result["stage_acceptance"] = {
        "S2_T05_technical_comparison": "pass",
        "S2_T05_owner_product_review": "awaiting_user_owner_decision",
        "S2": "in_progress",
        "S3": "blocked_by_S2",
        "release": "not_admitted",
        "production": "not_admitted",
    }
    result["next_action"] = "S2-T05-OWNER-PRODUCT-MATERIAL-GAIN-ACCEPTANCE-DECISION"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--agent-run-id", required=True)
    parser.add_argument("--agent-attempt-id", required=True)
    parser.add_argument("--input-digest", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_t05(
        args.runtime_root,
        agent_run_id=args.agent_run_id,
        agent_attempt_id=args.agent_attempt_id,
        input_digest=args.input_digest,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
