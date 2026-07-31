import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.s4_case_runtime import (  # noqa: E402
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


PROOF = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_deepseek_mainline_fresh_exact_admission_preparation_zero_call_proof_v1_0.json"
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


def _assert_historical_or_current(
    relative_path: str,
    historical_sha256: str,
) -> None:
    observed = hashlib.sha256(
        (ROOT / relative_path).read_bytes()
    ).hexdigest()
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
    assert relative_path in current[
        "historical_exact_binding_supersession"
    ]["allowed_changed_paths"]
    assert current["exact_code_bindings"][relative_path] == observed


def test_mu_binding_and_deepseek_pro_selection_are_exact() -> None:
    proof = _load()
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    asserted = proof["MU_contract_proof"]
    assert asserted["issuer_identifier"] == binding.issuer_identifier
    assert asserted["research_profile_ref"] == binding.research_profile_ref
    assert asserted["program_cell_ids"] == list(binding.program_cell_ids)
    assert asserted["runtime_binding_digest"] == binding.runtime_binding_digest
    assert proof["selected_mainline"]["model"] == "deepseek-v4-pro"
    assert proof["selected_mainline"]["model_tier"] == "pro_not_flash"
    assert proof["selected_mainline"]["base_url"].startswith("https://")


def test_mu_source_pack_was_the_exact_pre_admission_blocker() -> None:
    proof = _load()
    preflight = proof["exact_input_preflight"]
    assert not preflight["source_grounded_pack_registry_supports_MU"]
    assert preflight["exact_failure_code"] == (
        "s4_source_grounded_input_case_unsupported"
    )
    assert not preflight["exact_input_compiled"]
    assert not preflight["admission_issuance_admissible"]
    assert not preflight["exact_live_execution_admissible"]
    repaired = load_s4_source_grounded_input_pack(ROOT, "MU")
    assert repaired.case_ticker == "MU"
    assert repaired.issuer_identifier == "CIK0000723125"


def test_proof_is_zero_call_and_does_not_inflate_t06_or_mu() -> None:
    proof = _load()
    assert set(proof["observed_counts"].values()) == {0}
    stage = proof["stage_acceptance"]
    assert stage["S4_T06"] == (
        "in_progress_zero_call_pre_admission_blocked_by_MU_source_pack"
    )
    assert stage["MU_R2"] == "not_started"
    assert not stage["S4_pass"]
    assert proof["current_action_remains"].startswith(
        "S4-T06-MU-DEEPSEEK-MAINLINE"
    )


def test_current_mu_proof_binds_current_code_without_rewriting_history() -> None:
    proof = _load()
    historical_runtime = "src/sec_agent/s4_case_runtime.py"
    assert proof["code_bindings"][historical_runtime] == (
        "98ba0973765321b98a12bb092fbb007e7e5657179e1b5d7c0fe6fad6125350a2"
    )
    for relative_path, expected_sha256 in proof["code_bindings"].items():
        if relative_path == historical_runtime:
            continue
        _assert_historical_or_current(relative_path, expected_sha256)
