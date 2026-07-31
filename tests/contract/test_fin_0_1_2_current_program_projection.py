from __future__ import annotations

import json
from pathlib import Path

from sec_agent.hermetic_test_runner import (
    validate_host_current_program_projection,
)


ROOT = Path(__file__).resolve().parents[2]
CURRENT_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_3_current_program_projection_v1_0.json"
)
FROZEN_S0C_TERMINAL_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v1_1.json"
)
FROZEN_T03_PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v1_0.json"
)
MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s0c_t03_corrective_"
    "hermetic_proof_manifest_v1_0.json"
)
HOST_ONLY_TEST = (
    "tests/contract/test_fin_0_1_2_current_program_projection.py"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_program_projection_is_the_single_host_state_owner() -> None:
    projection = validate_host_current_program_projection(
        ROOT,
        CURRENT_PROJECTION_REF,
    )
    assert projection == Path(CURRENT_PROJECTION_REF)


def test_host_state_sources_and_host_only_test_are_not_disposable_inputs() -> None:
    projection = _load(ROOT / CURRENT_PROJECTION_REF)
    manifest = _load(MANIFEST)
    policy = manifest["hermetic_package_policy"]
    selected_paths = {
        path
        for suite in manifest["suites"]
        if suite["selected"]
        for path in suite["test_paths"]
    }
    seeds = set(policy["repository_seed_paths"])
    assert policy["host_current_program_projection_ref"] == (
        FROZEN_T03_PROJECTION_REF
    )
    assert CURRENT_PROJECTION_REF != FROZEN_T03_PROJECTION_REF
    assert CURRENT_PROJECTION_REF != FROZEN_S0C_TERMINAL_PROJECTION_REF
    assert HOST_ONLY_TEST not in selected_paths
    assert not set(projection["source_paths"].values()).intersection(seeds)
    assert projection["package_governance"]["host_sources_packaged"] is False
    assert projection["package_governance"]["disposable_git_required"] is False
