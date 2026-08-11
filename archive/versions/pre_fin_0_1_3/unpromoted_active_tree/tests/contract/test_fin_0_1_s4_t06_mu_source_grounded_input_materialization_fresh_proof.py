from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    build_s4_source_grounded_bounded_agent_input,
)
from sec_agent.s4_case_runtime import (  # noqa: E402
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


PROOF = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_source_grounded_input_materialization_and_fresh_proof_v1_0.json"
)
CURRENT_RUNTIME_IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_and_material_"
    "numeric_classifier_minimum_zero_call_implementation_v1_0.json"
)
CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _load() -> dict:
    return json.loads(PROOF.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = _sha256(ROOT / relative_path)
    if observed == historical_sha256:
        return
    identity_boundary = json.loads(
        CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION.read_text(
            encoding="utf-8"
        )
    )
    if (
        identity_boundary["exact_code_bindings"].get(relative_path)
        == observed
    ):
        return
    current = json.loads(
        CURRENT_RUNTIME_IMPLEMENTATION.read_text(encoding="utf-8")
    )
    current_digest = current["exact_code_bindings"].get(relative_path)
    if current_digest is not None:
        assert current_digest == observed
        return
    assert relative_path in current[
        "historical_exact_binding_supersession"
    ]["allowed_changed_paths"]


def test_proof_binds_current_pack_and_implementation() -> None:
    proof = _load()
    assert proof["status"].startswith(
        "pass_MU_source_pack_materialized_registered"
    )
    source = proof["source_pack"]
    assert _sha256(ROOT / source["ref"]) == source["sha256"]
    assert load_s4_source_grounded_input_pack(
        ROOT, "MU"
    ).source_pack_digest == source["source_pack_digest"]
    for relative_path, expected_sha256 in proof["code_bindings"].items():
        _assert_historical_or_current(relative_path, expected_sha256)


def test_exact_input_digest_is_recomputed_from_current_pack() -> None:
    proof = _load()
    source_pack = load_s4_source_grounded_input_pack(ROOT, "MU")
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    exact = proof["exact_input_fresh_proof"]
    compiled = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        case_id=exact["proof_case_id"],
        case_version=1,
        decision_surface_contract_ref=exact[
            "proof_decision_surface_contract_ref"
        ],
        query=(
            "Assess Micron HBM demand durability, value capture, cycle and "
            "bottleneck counterevidence under the frozen three-cell method."
        ),
    )
    assert compiled.input_digest == exact["input_digest"]
    assert compiled.company == "MU"
    assert len(compiled.cell_inputs) == 3


def test_proof_does_not_inflate_fixture_into_admission_or_live_status() -> None:
    proof = _load()
    assert proof["zero_call_full_fake_proof"]["nodes"] == 6
    assert proof["zero_call_full_fake_proof"]["artifacts"] == 9
    assert set(proof["hard_boundaries"].values()) == {False, 0}
    assert proof["stage_acceptance"]["MU_R2"] == "not_started"
    assert proof["next_action"] == (
        "S4-T06-MU-CANONICAL-CASE-SURFACE-AND-FRESH-EXACT-"
        "ADMISSION-PREPARATION-ZERO-CALL-PROOF"
    )
