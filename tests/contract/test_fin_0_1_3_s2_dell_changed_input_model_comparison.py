from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.s1_six_case_local_evidence_pack import file_sha256
from sec_agent.s2_dell_changed_input_model_comparison import (
    NUMERIC_AUTHORITY_SCHEMA,
    S2DellChangedInputComparisonError,
    compile_changed_input_case,
    issue_changed_input_model_authority,
    load_changed_input_comparison_contract,
    rebind_numeric_declaration,
    validate_changed_input_clean_proof,
    validate_changed_input_model_authority,
)
from sec_agent.s2_fixed_pack_live import load_dell_fixed_pack_material
from sec_agent.s2_fixed_pack_research_runtime import issue_case_admission


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_contract_v1_0.json"
)
PROOF_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_dell_changed_input_model_comparison_clean_proof_v1_0.json"
)


def _material() -> dict[str, object]:
    contract = load_changed_input_comparison_contract(
        CONTRACT_PATH, repo_root=ROOT
    )
    return compile_changed_input_case(contract=contract, repo_root=ROOT)


def test_changed_input_case_compiles_corrected_pack_and_numeric_authority() -> None:
    material = _material()
    case_input = material["case_input"]
    numeric = case_input["numeric_authority"]

    assert case_input["source_pack_digest"] == (
        "5ba1091ddc71d0c8543f186e4331bf2caae7d10e365af0a0f7510a056b5e9984"
    )
    assert len(case_input["evidence_items"]) == 27
    assert len(case_input["source_materials"]) == 27
    assert len(case_input["residual_gaps"]) == 14
    assert numeric["schema_version"] == NUMERIC_AUTHORITY_SCHEMA
    assert len(numeric["source_numeric_facts"]) == 15
    assert len(numeric["formula_traces"]) == 4
    assert material["historical_case_input_digest"] != case_input[
        "model_visible_digest"
    ]


def test_numeric_authority_rebinds_stable_identities_not_old_aliases() -> None:
    material = _material()
    current = material["case_input"]
    contract = material["contract"]
    bindings = contract["immutable_bindings"]
    historical = load_dell_fixed_pack_material(
        repo_root=ROOT,
        contract_path=ROOT / bindings["fixed_pack_contract"]["ref"],
        profile_path=ROOT / bindings["provider_profile"]["ref"],
    )["case_input"]
    declaration = {
        "numeric_ref": "NUM:DELL:TEST",
        "exact_value": "43842",
        "unit": "USD_million",
        "period_id": "DELL_FY2027_Q1",
        "evidence_aliases": ["E002"],
        "source_material_alias": "M013",
        "source_token": "43,842",
    }
    rebound = rebind_numeric_declaration(
        declaration,
        historical_case_input=historical,
        current_case_input=current,
    )
    assert rebound["evidence_aliases"] == ["E002"]
    assert rebound["source_material_alias"] == "M024"
    assert rebound["stable_binding"]["source_record_id"].startswith(
        "8K_EARNINGS::DELL"
    )


def test_numeric_rebinding_fails_closed_when_stable_source_disappears() -> None:
    material = _material()
    current = deepcopy(material["case_input"])
    contract = material["contract"]
    bindings = contract["immutable_bindings"]
    historical = load_dell_fixed_pack_material(
        repo_root=ROOT,
        contract_path=ROOT / bindings["fixed_pack_contract"]["ref"],
        profile_path=ROOT / bindings["provider_profile"]["ref"],
    )["case_input"]
    current["source_materials"] = [
        row
        for row in current["source_materials"]
        if row["source_record_id"]
        != "8K_EARNINGS::DELL::000157199626000021::EXHIBIT991EARNINGS8KQ1FY27HTM::BLOCK_0003::PART_01_OF_02"
    ]
    with pytest.raises(
        S2DellChangedInputComparisonError,
        match="changed_input_stable_numeric_identity_missing",
    ):
        rebind_numeric_declaration(
            {
                "numeric_ref": "NUM:DELL:TEST",
                "evidence_aliases": ["E002"],
                "source_material_alias": "M013",
            },
            historical_case_input=historical,
            current_case_input=current,
        )


def test_contract_rejects_boundary_drift(tmp_path: Path) -> None:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    payload["execution_boundary"]["old_model_node_reuse"] = True
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        S2DellChangedInputComparisonError,
        match="changed_input_comparison_contract_identity_or_boundary_invalid",
    ):
        load_changed_input_comparison_contract(path, repo_root=ROOT)


def test_clean_proof_is_digest_bound_and_zero_call() -> None:
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    validate_changed_input_clean_proof(proof)
    assert proof["case_input_digest"] != proof["historical_case_input_digest"]
    assert proof["maximum_request_characters"] == 135111


def test_changed_input_authority_is_exact_once_and_fresh_only() -> None:
    material = _material()
    case_input = material["case_input"]
    profile = material["profile"]
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    admission = issue_case_admission(
        case_input=case_input,
        profile=profile,
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        contract_sha256="c" * 64,
        profile_sha256="d" * 64,
        issued_at="2026-08-10T20:00:00Z",
        expires_at="2026-08-11T20:00:00Z",
        run_nonce="authority-fixture",
        credential_present=True,
        execution_mode="live",
    )
    authority = issue_changed_input_model_authority(
        admission=admission,
        clean_proof=proof,
        implementation_commit="a" * 40,
        implementation_bindings=[
            {
                "ref": CONTRACT_PATH.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(CONTRACT_PATH),
            }
        ],
        project_os_preflight={
            "status": "pass",
            "run_scope": "FIN_0_1_3_S2_DELL_FIXED_PACK_MODEL_COMPARISON",
            "open_full_chain_blocker_count": 0,
        },
        user_authority="fixture authority",
        recorded_at="2026-08-10T20:00:00Z",
    )
    validate_changed_input_model_authority(
        authority,
        clean_proof=proof,
        case_input=case_input,
        profile=profile,
        repo_root=ROOT,
        observed_at="2026-08-10T21:00:00Z",
    )
    assert authority["execution_ceiling"]["provider_calls"] == 13
    assert authority["execution_ceiling"]["old_model_nodes_reused"] == 0
    assert authority["automatic_replacement"] is False
