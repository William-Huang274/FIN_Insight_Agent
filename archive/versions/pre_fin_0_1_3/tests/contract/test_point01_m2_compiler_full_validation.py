from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.planning_service import (
    CompilerInputContract,
    CompilerInputValidationPolicy,
    DecisionCellSeed,
    DecisionSurfacePlanningService,
    EvidenceSlotSeed,
    PackSelectionDecision,
)


pytestmark = pytest.mark.fast_contract


def _policy() -> CompilerInputValidationPolicy:
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json").read_text(encoding="utf-8"))
    return CompilerInputValidationPolicy.model_validate({key: value for key, value in raw.items() if key != "policy_version" and key != "authority_boundary"})


def _scope() -> dict:
    now = datetime(2026, 7, 12, tzinfo=timezone.utc).isoformat()
    return {
        "tenant_id": "tenant-test",
        "project_id": "project-test",
        "case_id": "case-m2-1",
        "created_at": now,
        "recorded_at": now,
        "actor_snapshot_ref": "actor-1",
        "permission_snapshot_ref": "permission-1",
        "correlation_id": "correlation-m2-1",
    }


def _input(cell_count: int = 10) -> CompilerInputContract:
    policy = _policy()
    roles = policy.allowed_owner_roles
    sources = policy.allowed_source_policy_refs
    cells = []
    for index in range(cell_count):
        cells.append(
            DecisionCellSeed(
                cell_key=f"cell_{index}",
                decision_question=f"Decision question {index}",
                origin_type="compiler_policy",
                owner_role=roles[index % len(roles)],
                materiality="high",
                stop_rule="accepted primary route or typed gap",
                dependency_cell_keys=(f"cell_{index - 1}",) if index else (),
                evidence_slots=(
                    EvidenceSlotSeed(
                        evidence_role="issuer_metric",
                        entity_scope=("AAA",),
                        period_scope="latest_fiscal_period",
                        metric_scope=(f"metric_{index}",),
                        source_policy_ref=sources[index % len(sources)],
                        forbidden_substitutions=("unbounded_proxy",),
                        acceptance_role="primary",
                    ),
                ),
            )
        )
    return CompilerInputContract(
        tenant_id="tenant-test",
        project_id="project-test",
        case_id="case-m2-1",
        query="Assess durable demand with explicit counterevidence.",
        as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
        universe=("AAA",),
        language="en",
        compiler_policy_ref=policy.policy_ref,
        pack_selection=PackSelectionDecision(universal_pack_refs=("universal-v1",)),
        required_cells=tuple(cells),
    )


def test_m2_1_full_validator_accepts_ten_cell_dag_and_assembled_bundle() -> None:
    service = DecisionSurfacePlanningService(None)  # type: ignore[arg-type]
    inputs = _input()
    report = service.validate_compiler_input_full(inputs, policy=_policy())
    assert report.status == "pass"
    assert report.cell_count == 10
    bundle = service.compile_deterministic_fixture(inputs, audit_scope=_scope())
    validation = service.validate_decision_surface_bundle_full("case-m2-1", bundle, policy=_policy())
    assert validation["status"] == "pass"
    assert validation["validation_mode"] == "full"
    assert validation["external_call_count"] == 0


def test_m2_1_full_validator_rejects_count_cycle_owner_source_and_forbidden_gaps() -> None:
    service = DecisionSurfacePlanningService(None)  # type: ignore[arg-type]
    inputs = _input(cell_count=9)
    cells = list(inputs.required_cells)
    cells[0] = cells[0].model_copy(update={"dependency_cell_keys": ("cell_1",), "owner_role": "memo_writer"})
    cells[1] = cells[1].model_copy(update={"dependency_cell_keys": ("cell_0",)})
    bad_slot = cells[2].evidence_slots[0].model_copy(update={"source_policy_ref": "unknown_source", "forbidden_substitutions": ()})
    cells[2] = cells[2].model_copy(update={"evidence_slots": (bad_slot,)})
    cells[8] = cells[8].model_copy(update={"cell_key": "cell_7", "dependency_cell_keys": ("missing_cell",)})
    report = service.validate_compiler_input_full(inputs.model_copy(update={"required_cells": tuple(cells)}), policy=_policy())
    assert report.status == "fail"
    assert "material_cell_count_out_of_range:9" in report.errors
    assert "dependency_cycle" in report.errors
    assert "duplicate_cell_key" in report.errors
    assert "unknown_cell_dependency:cell_7" in report.errors
    assert "owner_role_not_allowed:cell_0" in report.errors
    assert "source_policy_not_allowed:cell_2:1" in report.errors
    assert "forbidden_substitutions_required:cell_2:1" in report.errors


def test_m2_1_bundle_validator_rejects_invalid_compile_time_gap_without_breaking_fixture_mode() -> None:
    service = DecisionSurfacePlanningService(None)  # type: ignore[arg-type]
    fixture = _input(cell_count=1)
    fixture_bundle = service.compile_deterministic_fixture(fixture, audit_scope=_scope())
    assert service.validate_decision_surface_bundle("case-m2-1", fixture_bundle)["status"] == "pass"
    assert service.validate_decision_surface_bundle_full("case-m2-1", fixture_bundle, policy=_policy())["status"] == "fail"

    bundle = service.compile_deterministic_fixture(_input(), audit_scope=_scope())
    cell = bundle["cells"][0]
    bundle["gaps"] = [
        {
            **_scope(),
            "case_id": "case-m2-1",
            "cell_version_id": cell["cell_version_id"],
            "gap_id": "gap-1",
            "gap_version_id": "gap-1:v1",
            "gap_version": 1,
            "gap_type": "parser_gap",
            "reason": " ",
            "materiality": "high",
            "owner_suggestion": "fundamental_analyst",
            "next_action": "repair parser route",
            "current_status": "shadow_created",
        }
    ]
    validation = service.validate_decision_surface_bundle_full("case-m2-1", bundle, policy=_policy())
    assert validation["status"] == "fail"
    assert "gap_reason_blank:gap-1" in validation["errors"]


def test_m2_1_machine_fixture_runner_is_replayable_and_model_free(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "m2_1_fixture.json"
    completed = subprocess.run(
        [sys.executable, str(root / "scripts/engineering/run_point01_m2_1_compiler_validation_fixture.py"), "--output", str(output)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["authority_boundary"]["model_call_count"] == 0
