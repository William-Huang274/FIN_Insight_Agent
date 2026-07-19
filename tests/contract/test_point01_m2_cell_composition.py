from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.cell_composition import CellCompositionEngine, CellCompositionError, CellCompositionPolicy
from sec_agent.canonical_runtime.planning_service import CompilerInputContract, CompilerInputValidationPolicy, DecisionSurfacePlanningService, PackSelectionDecision


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_5_cell_composition_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m2_5_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _composition_policy() -> CellCompositionPolicy:
    raw = json.loads((ROOT / "configs/engineering_handoff/point01_m2_5_cell_composition_policy_v1_0.json").read_text(encoding="utf-8"))
    return CellCompositionPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def _validation_policy() -> CompilerInputValidationPolicy:
    raw = json.loads((ROOT / "configs/engineering_handoff/point01_m2_1_compiler_input_validation_policy_v1_0.json").read_text(encoding="utf-8"))
    return CompilerInputValidationPolicy.model_validate({key: value for key, value in raw.items() if key not in {"policy_version", "authority_boundary"}})


def test_composition_merges_splits_dedupes_and_preserves_fact_to_slot_mapping() -> None:
    result = CellCompositionEngine(_composition_policy()).compose(
        case_id="case-ai",
        selected_pack_refs=("universal-core:v1", "sector-ai_semis:v1"),
        archetypes=RUNNER.build_archetypes("ai_semis"),
    )
    assert len(result.cells) == 10
    assert result.merged_archetype_ids
    assert result.split_cell_keys == ("ai_semis_4__demand", "ai_semis_4__monetization")
    assert all(cell.fact_to_slot_keys for cell in result.cells)
    assert result.model_call_count == 0


def test_composed_cells_satisfy_m2_1_full_input_validator() -> None:
    result = CellCompositionEngine(_composition_policy()).compose(
        case_id="case-saas",
        selected_pack_refs=("universal-core:v1", "sector-saas:v1"),
        archetypes=RUNNER.build_archetypes("saas"),
    )
    inputs = CompilerInputContract(
        tenant_id="tenant",
        project_id="project",
        case_id="case-saas",
        query="Subscription software composition",
        as_of=datetime(2026, 7, 12, tzinfo=timezone.utc),
        universe=("AAA",),
        language="en",
        compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        pack_selection=PackSelectionDecision(universal_pack_refs=("universal-core:v1",), sector_pack_refs=("sector-saas:v1",)),
        required_cells=tuple(cell.seed for cell in result.cells),
    )
    assert DecisionSurfacePlanningService(None).validate_compiler_input_full(inputs, policy=_validation_policy()).status == "pass"  # type: ignore[arg-type]


def test_composition_rejects_unselected_pack_and_merge_contract_conflict() -> None:
    engine = CellCompositionEngine(_composition_policy())
    with pytest.raises(CellCompositionError, match="archetype_pack_not_selected"):
        engine.compose(case_id="case", selected_pack_refs=("universal-core:v1",), archetypes=RUNNER.build_archetypes("banks"))
    archetypes = list(RUNNER.build_archetypes("healthcare"))
    archetypes[5] = archetypes[5].model_copy(update={"decision_question": "conflict"})
    with pytest.raises(CellCompositionError, match="merge_contract_conflict:core_0"):
        engine.compose(case_id="case", selected_pack_refs=("universal-core:v1", "sector-healthcare:v1"), archetypes=tuple(archetypes))


def test_m2_5_machine_fixture_has_four_positive_and_adversarial_cases(tmp_path) -> None:
    output = tmp_path / "m2_5_composition.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["four_positive_cases"] is True
    assert result["checks"]["adversarial_merge_conflict"] is True
