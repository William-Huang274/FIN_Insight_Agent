from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest  # noqa: E402
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    CASES,
    S2FixedPackResearchError,
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
    materialize_six_case_model_inputs,
    validate_case_model_input,
)


CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)


@pytest.fixture(scope="module")
def compiled():
    contract = load_fixed_pack_contract(CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=contract, repo_root=ROOT)
    inputs, result = compile_six_case_model_inputs(
        contract=contract,
        profile=profile,
        packs=packs,
    )
    return contract, profile, packs, inputs, result


def _rehash(value: dict) -> dict:
    body = deepcopy(value)
    body.pop("model_visible_digest", None)
    return {**body, "model_visible_digest": canonical_digest(body)}


def test_six_case_inputs_preserve_full_reviewed_population(compiled) -> None:
    _contract, profile, _packs, inputs, result = compiled
    assert tuple(row["case_key"] for row in inputs) == CASES
    assert result["observed_counts"] == {
        "cases": 6,
        "evidence_items": 84,
        "source_materials": 44,
        "residual_gaps": 126,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
    }
    assert all(
        row["input_density"]["accepted_evidence_count"]
        == len(row["evidence_items"])
        and row["input_density"]["residual_gap_count"]
        == len(row["residual_gaps"])
        for row in inputs
    )
    assert all(
        len(json.dumps(row, ensure_ascii=False))
        <= profile["maximum_input_characters_per_call"]
        for row in inputs
    )


def test_known_and_held_out_density_difference_is_explicit(compiled) -> None:
    _contract, _profile, _packs, inputs, _result = compiled
    index = {row["case_key"]: row for row in inputs}
    for case_key in ("DELL", "MU", "NVDA"):
        assert index[case_key]["input_density"]["class"] == (
            "raw_source_text_and_review_boundaries"
        )
        assert index[case_key]["source_materials"]
    for case_key in ("ORCL", "ASML", "ANET"):
        assert index[case_key]["input_density"]["class"] == (
            "reviewed_structured_metrics_and_claims_without_raw_source_text"
        )
        assert index[case_key]["source_materials"] == []


def test_rejections_never_enter_model_visible_input(compiled) -> None:
    _contract, _profile, packs, inputs, _result = compiled
    for row in inputs:
        assert "rejected_items" not in row
        visible_targets = {item["target_id"] for item in row["evidence_items"]}
        rejected_targets = {
            item["target_id"] for item in packs[row["case_key"]]["rejected_items"]
        }
        assert visible_targets.isdisjoint(rejected_targets)


def test_source_bound_numbers_remain_visible_to_model(compiled) -> None:
    _contract, _profile, _packs, inputs, _result = compiled
    dell = next(row for row in inputs if row["case_key"] == "DELL")
    assert any(
        "Change in cash from operating activities | 4,081" in row["source_text"]
        for row in dell["source_materials"]
    )
    orcl = next(row for row in inputs if row["case_key"] == "ORCL")
    assert any(
        item.get("structured_metric", {}).get("raw_value") == "(55,663)"
        for item in orcl["evidence_items"]
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("cross_case", "fixed_pack_input_digest_or_identity_invalid"),
        ("future_date", "fixed_pack_input_evidence_boundary_invalid"),
        ("missing_material", "fixed_pack_input_source_material_binding_invalid"),
        ("forbidden_rejections", "fixed_pack_input_forbidden_surface_visible"),
        ("capacity", "fixed_pack_input_capacity_exceeded"),
    ],
)
def test_input_mutations_fail_closed(compiled, mutation, expected_code) -> None:
    _contract, profile, _packs, inputs, _result = compiled
    changed = deepcopy(inputs[0])
    changed_profile = deepcopy(profile)
    if mutation == "cross_case":
        changed["case_key"] = "FAKE"
    elif mutation == "future_date":
        changed["evidence_items"][0]["publication_date"] = "2099-01-01"
    elif mutation == "missing_material":
        changed["evidence_items"][0]["source_material_alias"] = "M999"
    elif mutation == "forbidden_rejections":
        changed["rejected_items"] = [{"target_id": "forbidden"}]
    elif mutation == "capacity":
        changed_profile["maximum_input_characters_per_call"] = 10
    changed = _rehash(changed)
    with pytest.raises(S2FixedPackResearchError) as exc:
        validate_case_model_input(changed, profile=changed_profile)
    assert exc.value.code == expected_code


def test_materializer_writes_content_addressed_private_inputs(compiled, tmp_path) -> None:
    contract, profile, _packs, _inputs, _result = compiled
    result = materialize_six_case_model_inputs(
        contract=contract,
        profile=profile,
        repo_root=ROOT,
        artifact_root=tmp_path / "objects",
        output_path=tmp_path / "result.json",
    )
    assert set(result["input_artifacts"]) == set(CASES)
    assert result["observed_counts"]["model_calls"] == 0
    for ref in result["input_artifacts"].values():
        path = tmp_path / "objects" / ref["object_key"]
        assert path.is_file()
        assert path.stat().st_size == ref["byte_size"]
