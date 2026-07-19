from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.model_admission import (  # noqa: E402
    CompilerModelAdmissionService,
    ModelAdmissionPolicy,
    ModelAdmissionRequest,
)
from sec_agent.canonical_runtime.models import CommandEnvelope  # noqa: E402
from sec_agent.canonical_runtime.shadow_orchestration import ShadowCompilerOrchestrator  # noqa: E402


MODEL_POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_8_model_admission_policy_v1_0.json"
POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_9_shadow_orchestration_policy_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_9_shadow_orchestration_fixture_result_v1_0.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M2_2 = _load("point01_m2_2_for_m2_9", ROOT / "scripts/engineering/run_point01_m2_2_full_serializer_fixture.py")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_policy() -> ModelAdmissionPolicy:
    raw = json.loads(MODEL_POLICY_PATH.read_text(encoding="utf-8"))
    return ModelAdmissionPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _command(request, command_type: str, *, payload: dict[str, Any], expected: int, key: str) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-m2-9-{key}",
        command_type=command_type,
        tenant_id=request.scope.tenant_id,
        project_id=request.scope.project_id,
        case_id=request.scope.case_id,
        actor_snapshot_ref=request.scope.actor_snapshot_ref,
        permission_snapshot_ref=request.scope.permission_snapshot_ref,
        policy_config_refs=request.scope.policy_config_refs,
        idempotency_key=f"m2-9-{key}",
        expected_state_version=expected,
        correlation_id=request.scope.correlation_id,
        requested_at=request.scope.created_at,
        payload=payload,
    )


def _create_case_and_attempt(facade, request, suffix: str) -> tuple[str, str]:
    facade.create_research_case(
        _command(
            request,
            "CREATE_RESEARCH_CASE",
            payload={"query": request.compiler_input.query, "accountable_owner_ref": "lead-m2-9"},
            expected=0,
            key=f"case-{suffix}",
        )
    )
    work_unit_id = f"wu-m2-9-{suffix}"
    attempt_id = f"attempt-m2-9-{suffix}"
    facade.create_work_unit(
        _command(
            request,
            "CREATE_WORK_UNIT",
            payload={"work_unit_id": work_unit_id, "input_version_refs": (f"m2-9-envelope-input-{suffix}",)},
            expected=0,
            key=f"wu-{suffix}",
        )
    )
    facade.start_attempt(
        _command(
            request,
            "START_ATTEMPT",
            payload={"work_unit_id": work_unit_id, "attempt_id": attempt_id},
            expected=0,
            key=f"attempt-{suffix}",
        )
    )
    return work_unit_id, attempt_id


def _proposal(request, envelope):
    service = CompilerModelAdmissionService(_model_policy())
    return service.propose(
        ModelAdmissionRequest(
            envelope=envelope,
            provider_family="deepseek",
            feature_flag_enabled=True,
            explicit_approved_scoped_node=True,
            provider_preflight_status="pass",
            budget_preflight_status="pass",
            permission_snapshot_ref=request.scope.permission_snapshot_ref,
        )
    )[0]


def build_result(work_root: Path) -> dict[str, Any]:
    case_specs = (
        ("ai_semis", "case-ai-semiconductor"),
        ("saas", "case-saas"),
        ("healthcare", "case-healthcare"),
        ("banks", "case-banks"),
    )
    results = {}
    for sector, case_id in case_specs:
        request, assembler, serializer_policy = M2_2._context(sector=sector, case_id=case_id)
        assembly = assembler.assemble(request)
        facade = M2_2._facade(work_root / sector)
        work_unit_id, attempt_id = _create_case_and_attempt(facade, request, sector)
        proposal = _proposal(request, assembly.envelope)
        result = ShadowCompilerOrchestrator(serializer_policy).execute(
            facade,
            _command(
                request,
                "COMMIT_DECISION_SURFACE_BUNDLE",
                payload={"work_unit_id": work_unit_id, "attempt_id": attempt_id},
                expected=1,
                key=f"commit-{sector}",
            ),
            assembly,
            proposal,
            artifact_id=f"artifact-m2-9-{sector}",
        )
        results[sector] = result

    off_request, off_assembler, off_policy = M2_2._context()
    off_assembly = off_assembler.assemble(off_request)
    off_facade = M2_2._facade(work_root / "flag-off")
    off_facade.mode = "off"
    off_result = ShadowCompilerOrchestrator(off_policy).execute(
        off_facade,
        _command(off_request, "COMMIT_DECISION_SURFACE_BUNDLE", payload={"work_unit_id": "not-created", "attempt_id": "not-created"}, expected=0, key="flag-off"),
        off_assembly,
        _proposal(off_request, off_assembly.envelope),
        artifact_id="artifact-m2-9-flag-off",
    )
    first_request, first_assembler, first_policy = M2_2._context()
    first_assembly = first_assembler.assemble(first_request)
    admission_violation = _proposal(first_request, first_assembly.envelope).model_copy(
        update={"admission_decision": _proposal(first_request, first_assembly.envelope).admission_decision.model_copy(update={"status": "admitted", "model_execution_permitted": True})}
    )
    violation_facade = M2_2._facade(work_root / "admission-violation")
    violation_result = ShadowCompilerOrchestrator(first_policy).execute(
        violation_facade,
        _command(first_request, "COMMIT_DECISION_SURFACE_BUNDLE", payload={"work_unit_id": "not-created", "attempt_id": "not-created"}, expected=0, key="admission-violation"),
        first_assembly,
        admission_violation,
        artifact_id="artifact-m2-9-admission-violation",
    )
    checks = {
        "four_sector_shadow_compilations_pass": set(results) == {"ai_semis", "saas", "healthcare", "banks"} and all(result.status == "pass" for result in results.values()),
        "workunit_attempt_artifact_and_replay_integrated": all(
            result.attempt_trace.artifact_version_id
            and result.replay_report
            and result.replay_report.work_unit_state == "succeeded"
            and result.replay_report.attempt_state == "succeeded"
            and result.readback_report
            and result.readback_report.status == "pass"
            for result in results.values()
        ),
        "feature_flag_off_skips_all_writes": off_result.status == "skipped_feature_flag_off"
        and off_facade.store.list_latest("canonical_artifact_versions") == [],
        "admitted_model_boundary_rejected_before_write": violation_result.status == "fail"
        and violation_result.attempt_trace.error_code == "model_admission_boundary_violation"
        and violation_facade.store.list_latest("canonical_artifact_versions") == [],
        "model_free": all(result.model_call_count == 0 and result.external_call_count == 0 for result in results.values()),
    }
    return {
        "result_version": "finsight_point01_m2_9_shadow_orchestration_fixture_result_v1_0",
        "scope": "Point01_M2_9_shadow_orchestration_four_sector_replay",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "sector_results": {sector: result.model_dump(mode="json") for sector, result in results.items()},
        "feature_flag_off_result": off_result.model_dump(mode="json"),
        "model_admission_violation_result": violation_result.model_dump(mode="json"),
        "authority_boundary": {"legacy_task_run": "authoritative", "canonical_lane": "shadow_only", "model_call_count": 0, "external_call_count": 0, "runtime_cutover": False},
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_9_shadow_orchestration_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_9_shadow_orchestration_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/shadow_orchestration.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/shadow_orchestration.py"),
            "src/sec_agent/canonical_runtime/full_serializer.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/full_serializer.py"),
            "src/sec_agent/canonical_runtime/model_admission.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/model_admission.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(PLAN_PATH),
        },
        "boundary": "M2.9 composes deterministic shadow-only M1/M2 artifacts. Feature flag off prevents writes; denied model admission prevents model calls; no legacy authority change, Evidence/Writer, paid/full-chain or cutover occurs.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.9 shadow orchestration fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--work-root", type=Path, default=ROOT / ".tmp_point01_m2_9_shadow_orchestration")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    work_root = args.work_root if args.work_root.is_absolute() else ROOT / args.work_root
    result = build_result(work_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
