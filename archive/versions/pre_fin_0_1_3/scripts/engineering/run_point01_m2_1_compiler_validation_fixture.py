from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.planning_service import (
    CompilerInputContract,
    CompilerInputValidationPolicy,
    DecisionCellSeed,
    DecisionSurfacePlanningService,
    EvidenceSlotSeed,
    PackSelectionDecision,
)


POLICY_PATH = ROOT / "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_1_compiler_validation_fixture_result_v1_0.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> CompilerInputValidationPolicy:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return CompilerInputValidationPolicy.model_validate(
        {key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}}
    )


def _scope() -> dict[str, Any]:
    now = datetime(2026, 7, 12, tzinfo=timezone.utc).isoformat()
    return {
        "tenant_id": "tenant-m2-1-fixture",
        "project_id": "project-m2-1-fixture",
        "case_id": "case-m2-1-fixture",
        "created_at": now,
        "recorded_at": now,
        "actor_snapshot_ref": "actor-m2-1-fixture",
        "permission_snapshot_ref": "permission-m2-1-fixture",
        "correlation_id": "correlation-m2-1-fixture",
    }


def _input(policy: CompilerInputValidationPolicy, *, cell_count: int = 10) -> CompilerInputContract:
    cells: list[DecisionCellSeed] = []
    for index in range(cell_count):
        cells.append(
            DecisionCellSeed(
                cell_key=f"cell_{index}",
                decision_question=f"Material decision question {index}",
                origin_type="m2_1_fixture",
                owner_role=policy.allowed_owner_roles[index % len(policy.allowed_owner_roles)],
                materiality="high",
                stop_rule="accepted primary route or typed gap",
                dependency_cell_keys=(f"cell_{index - 1}",) if index else (),
                evidence_slots=(
                    EvidenceSlotSeed(
                        evidence_role="issuer_metric",
                        entity_scope=("AAA",),
                        period_scope="latest_fiscal_period",
                        metric_scope=(f"metric_{index}",),
                        source_policy_ref=policy.allowed_source_policy_refs[index % len(policy.allowed_source_policy_refs)],
                        forbidden_substitutions=("unbounded_proxy",),
                        acceptance_role="primary",
                    ),
                ),
            )
        )
    return CompilerInputContract(
        tenant_id="tenant-m2-1-fixture",
        project_id="project-m2-1-fixture",
        case_id="case-m2-1-fixture",
        query="Compile a material DecisionSurface without model execution.",
        as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
        universe=("AAA",),
        language="en",
        compiler_policy_ref=policy.policy_ref,
        pack_selection=PackSelectionDecision(universal_pack_refs=("universal-v1",)),
        required_cells=tuple(cells),
    )


def build_result() -> dict[str, Any]:
    policy = _policy()
    service = DecisionSurfacePlanningService(None)  # type: ignore[arg-type]
    positive_input = _input(policy)
    positive_input_report = service.validate_compiler_input_full(positive_input, policy=policy)
    positive_bundle = service.compile_deterministic_fixture(positive_input, audit_scope=_scope())
    positive_bundle_report = service.validate_decision_surface_bundle_full("case-m2-1-fixture", positive_bundle, policy=policy)

    short_report = service.validate_compiler_input_full(_input(policy, cell_count=9), policy=policy)
    bad_cells = list(positive_input.required_cells)
    bad_cells[0] = bad_cells[0].model_copy(update={"dependency_cell_keys": ("cell_1",), "owner_role": "memo_writer"})
    bad_cells[1] = bad_cells[1].model_copy(update={"dependency_cell_keys": ("cell_0",)})
    bad_slot = bad_cells[2].evidence_slots[0].model_copy(update={"source_policy_ref": "unapproved_source", "forbidden_substitutions": ()})
    bad_cells[2] = bad_cells[2].model_copy(update={"evidence_slots": (bad_slot,)})
    bad_cells[9] = bad_cells[9].model_copy(update={"cell_key": "cell_8", "dependency_cell_keys": ("missing_cell",)})
    negative_report = service.validate_compiler_input_full(
        positive_input.model_copy(update={"required_cells": tuple(bad_cells)}), policy=policy
    )
    negative_expected = {
        "dependency_cycle",
        "duplicate_cell_key",
        "unknown_cell_dependency:cell_8",
        "owner_role_not_allowed:cell_0",
        "source_policy_not_allowed:cell_2:1",
        "forbidden_substitutions_required:cell_2:1",
    }
    bad_gap_bundle = dict(positive_bundle)
    first_cell = positive_bundle["cells"][0]
    bad_gap_bundle["gaps"] = [
        {
            **_scope(),
            "case_id": "case-m2-1-fixture",
            "cell_version_id": first_cell["cell_version_id"],
            "gap_id": "gap-invalid",
            "gap_version_id": "gap-invalid:v1",
            "gap_version": 1,
            "gap_type": "parser_gap",
            "reason": " ",
            "materiality": "high",
            "owner_suggestion": "fundamental_analyst",
            "next_action": "repair parser route",
            "current_status": "shadow_created",
        }
    ]
    negative_gap_report = service.validate_decision_surface_bundle_full(
        "case-m2-1-fixture", bad_gap_bundle, policy=policy
    )
    checks = {
        "positive_input": positive_input_report.status == "pass",
        "positive_bundle": positive_bundle_report["status"] == "pass",
        "negative_cell_count": "material_cell_count_out_of_range:9" in short_report.errors,
        "negative_policy_and_cycle": negative_expected.issubset(set(negative_report.errors)),
        "negative_gap": "gap_reason_blank:gap-invalid" in negative_gap_report["errors"],
        "external_calls": positive_input_report.external_call_count == 0 and positive_bundle_report["external_call_count"] == 0,
    }
    return {
        "result_version": "finsight_point01_m2_1_compiler_validation_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M2_1_compiler_input_cell_slot_gap_full_validation",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "checks": checks,
        "positive": {
            "input": positive_input_report.model_dump(mode="json"),
            "bundle": positive_bundle_report,
        },
        "negative": {
            "short_input_errors": list(short_report.errors),
            "policy_cycle_errors": list(negative_report.errors),
            "gap_errors": negative_gap_report["errors"],
        },
        "authority_boundary": {
            "legacy_task_run": "authoritative",
            "canonical_lane": "shadow_only",
            "model_call_count": 0,
            "external_call_count": 0,
        },
        "fixed_input_sha256": {
            "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json": _sha256(POLICY_PATH),
            "scripts/engineering/run_point01_m2_1_compiler_validation_fixture.py": _sha256(Path(__file__).resolve()),
            "src/sec_agent/canonical_runtime/planning_service.py": _sha256(ROOT / "src/sec_agent/canonical_runtime/planning_service.py"),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture validates compiler input and assembled Cell/Slot/Gap shape only. It does not select a pack, call a model, retrieve evidence, write legacy state or change authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Point 01 M2.1 compiler validation fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "checks": result["checks"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
