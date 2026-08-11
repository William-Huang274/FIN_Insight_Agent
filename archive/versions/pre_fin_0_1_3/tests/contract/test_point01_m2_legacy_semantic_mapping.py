from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.legacy_objective_adapter import (
    LegacyObjectiveAdapterError,
    LegacySemanticMapping,
    adapt_legacy_objective_semantically,
)


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_7_legacy_semantic_mapping_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_7_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_semantic_migration_preserves_legacy_identity_without_direct_equivalence() -> None:
    plan = adapt_legacy_objective_semantically(
        RUNNER._legacy_payload("ai_semis"),
        target_cells=RUNNER._target_cells(),
        mappings=RUNNER._mappings(),
        policy=RUNNER._policy(),
    )
    assert plan.legacy_identity_preserved is True
    assert plan.one_to_one_equivalence_count == 0
    assert {mapping.action for mapping in plan.mappings} == {"merge", "split", "downgrade"}
    assert len(plan.information_loss_review) == len(plan.legacy_required_item_ids) == 4
    assert plan.model_call_count == plan.external_call_count == 0


def test_semantic_migration_rejects_direct_equivalence_and_uncovered_legacy_items() -> None:
    with pytest.raises(LegacyObjectiveAdapterError, match="legacy_mapping_action_not_allowed"):
        adapt_legacy_objective_semantically(
            RUNNER._legacy_payload("invalid"),
            target_cells=RUNNER._target_cells(),
            mappings=(
                LegacySemanticMapping(
                    legacy_required_item_id="legacy_unit_economics",
                    action="direct_equivalence",
                    target_cell_keys=("demand_signal",),
                    information_loss_tags=("invalid_direct_equivalence",),
                ),
            )
            + RUNNER._mappings()[1:],
            policy=RUNNER._policy(),
        )
    with pytest.raises(LegacyObjectiveAdapterError, match="legacy_mapping_coverage_invalid"):
        adapt_legacy_objective_semantically(
            RUNNER._legacy_payload("missing"),
            target_cells=RUNNER._target_cells(),
            mappings=RUNNER._mappings()[:-1],
            policy=RUNNER._policy(),
        )


def test_m2_7_machine_fixture_is_four_case_replayable_and_model_free(tmp_path) -> None:
    output = tmp_path / "m2_7_legacy_semantic_mapping.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--output", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["four_case_parity"] is True
    assert result["checks"]["invalid_action_rejected"] is True
