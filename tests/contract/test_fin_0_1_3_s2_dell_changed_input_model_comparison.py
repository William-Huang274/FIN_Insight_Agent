from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.s2_dell_changed_input_model_comparison import (
    NUMERIC_AUTHORITY_SCHEMA,
    S2DellChangedInputComparisonError,
    compile_changed_input_case,
    load_changed_input_comparison_contract,
    rebind_numeric_declaration,
    validate_changed_input_clean_proof,
)
from sec_agent.s2_fixed_pack_live import load_dell_fixed_pack_material


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
