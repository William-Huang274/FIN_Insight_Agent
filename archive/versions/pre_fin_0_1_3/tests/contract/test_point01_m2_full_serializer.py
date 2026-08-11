from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.full_serializer import DecisionSurfaceSerializationError


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_2_full_serializer_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_2_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_full_serializer_assembles_case_delta_lineage_and_typed_gap() -> None:
    request, assembler, _ = RUNNER._context()
    assembly = assembler.assemble(request)
    assert assembly.input_validation_status == assembly.bundle_validation_status == "pass"
    assert assembly.cell_count == 10
    assert assembly.gap_count == 1
    assert assembly.envelope.pack_resolution_snapshot.case_delta_pack_refs == ("case-ai-semiconductor:v1",)
    assert assembly.envelope.legacy_migration_plan.one_to_one_equivalence_count == 0
    assert assembly.model_call_count == assembly.external_call_count == 0


def test_full_serializer_rejects_lineage_loss_before_commit() -> None:
    request, assembler, _ = RUNNER._context()
    with pytest.raises(DecisionSurfaceSerializationError, match="typed_gap_lineage_dropped_or_unexpected"):
        assembler.assemble(request.model_copy(update={"evidence_policy": request.evidence_policy.model_copy(update={"gaps": ()})}))
    with pytest.raises(DecisionSurfaceSerializationError, match="legacy_direct_equivalence_forbidden"):
        assembler.assemble(request.model_copy(update={"legacy_migration": request.legacy_migration.model_copy(update={"one_to_one_equivalence_count": 1})}))


def test_full_serializer_machine_fixture_commits_and_replays_versions(tmp_path) -> None:
    result = RUNNER.build_result(tmp_path / "work")
    assert result["status"] == "pass"
    assert result["checks"]["atomic_commit_and_readback"] is True
    assert result["checks"]["multi_version_snapshot_replay"] is True
    assert result["checks"]["object_store_failure_leaves_no_canonical_artifact"] is True


def test_full_serializer_runner_cli_is_replayable(tmp_path) -> None:
    output = tmp_path / "m2_2_full_serializer.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--output", str(output), "--work-root", str(tmp_path / "runner-work")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["selection_mismatch_rejected"] is True
