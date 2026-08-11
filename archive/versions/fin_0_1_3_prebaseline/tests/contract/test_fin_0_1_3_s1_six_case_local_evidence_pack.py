from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    CASES,
    SixCaseLocalEvidencePackError,
    canonical_digest,
    compile_six_case_local_evidence_packs,
    file_sha256,
    load_six_case_local_evidence_pack_policy,
    materialize_six_case_local_evidence_packs,
    validate_local_evidence_pack,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_six_case_local_evidence_pack_policy_v1_0.json"
)


@pytest.fixture(scope="module")
def compiled():
    policy = load_six_case_local_evidence_pack_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    packs, result = compile_six_case_local_evidence_packs(
        policy=policy,
        repo_root=ROOT,
    )
    return policy, packs, result


def _pack(packs: list[dict], case_key: str) -> dict:
    return next(row for row in packs if row["case_key"] == case_key)


def _rehash(pack: dict) -> dict:
    body = deepcopy(pack)
    body.pop("pack_payload_digest", None)
    return {**body, "pack_payload_digest": canonical_digest(body)}


def test_dell_is_first_and_all_93_plus_19_candidates_are_adjudicated(compiled) -> None:
    _policy, packs, result = compiled
    assert tuple(row["case_key"] for row in packs) == CASES
    assert result["materialization_order"] == list(CASES)
    assert result["observed_counts"]["manifest_candidates_adjudicated"] == 93
    assert result["observed_counts"]["narrative_queue_items_adjudicated"] == 19
    assert result["observed_counts"]["network_calls"] == 0
    assert result["observed_counts"]["model_calls"] == 0
    assert all(row["status"].endswith("with_declared_residual_gaps") for row in packs)
    assert all(row["residual_gaps"] for row in packs)


def test_known_cases_preserve_full_source_text_and_bounded_readthrough(compiled) -> None:
    _policy, packs, _result = compiled
    dell = _pack(packs, "DELL")
    cash_item = next(
        row
        for row in dell["evidence_items"]
        if row["source_record_id"].endswith("BLOCK_0007::CHUNK_0001")
    )
    material = next(
        row
        for row in dell["source_materials"]
        if row["material_ref"] == cash_item["source_material_ref"]
    )
    assert "Change in cash from operating activities | 4,081" in material["source_text"]
    assert material["source_text_digest"] == cash_item["source_content_digest"]

    nvda = _pack(packs, "NVDA")
    dell_readthrough = next(
        row for row in nvda["evidence_items"] if row["target_id"].startswith("8K_EARNINGS::DELL")
    )
    assert dell_readthrough["disposition"] == "accepted_bounded_context_evidence"
    assert dell_readthrough["causal_attribution_authorized"] is False
    assert any(
        "NVIDIA" in binding["claim_boundary_zh"]
        for binding in dell_readthrough["slot_bindings"]
    )


def test_content_gate_rejects_true_but_business_wrong_surfaces(compiled) -> None:
    _policy, packs, _result = compiled
    orcl = _pack(packs, "ORCL")
    rejected_orcl = {row["target_id"]: row for row in orcl["rejected_items"]}
    debt_rate = next(key for key in rejected_orcl if key.endswith("METRIC_TABLE_0192315B"))
    fx_sensitivity = next(key for key in rejected_orcl if key.endswith("METRIC_TABLE_1065F757"))
    assert rejected_orcl[debt_rate]["reason_code"] == "debt_detail_not_valuation_basis"
    assert rejected_orcl[fx_sensitivity]["reason_code"] == "hypothetical_sensitivity_not_actual_balance"

    anet = _pack(packs, "ANET")
    land = next(row for row in anet["rejected_items"] if row["target_id"].endswith("METRIC_TABLE_6633E64F"))
    assert land["reason_code"] == "generic_ppe_not_supply_capacity"
    assert "供应" in land["business_reason_zh"]

    asml = _pack(packs, "ASML")
    safe_harbor = next(row for row in asml["rejected_items"] if row["object_type"] == "claim")
    assert safe_harbor["reason_code"] == "safe_harbor_word_list_not_risk_evidence"


def test_content_gate_corrects_candidate_slot_without_rewriting_retrieval_history(compiled) -> None:
    _policy, packs, _result = compiled
    orcl = _pack(packs, "ORCL")
    capex = next(row for row in orcl["evidence_items"] if row["target_id"].endswith("METRIC_TABLE_442F4960"))
    assert capex["candidate_slot_ids"] == ["capacity_inputs_execution"]
    assert capex["slot_bindings"] == [
        {
            "slot_id": "cash_conversion_balance_sheet",
            "facet_ids": ["capital_expenditure"],
            "business_meaning_zh": "ORCL 在 2026 披露“Capital expenditures”为 (55,663)。",
            "claim_boundary_zh": "括号代表现金流出；资本开支不能自动等同已投产云容量。",
        }
    ]


@pytest.mark.parametrize(
    ("case_key", "mutation", "expected_code"),
    [
        (
            "ORCL",
            "metric_table_removed",
            "local_evidence_pack_metric_authority_invalid",
        ),
        (
            "NVDA",
            "context_boundary_removed",
            "local_evidence_pack_context_boundary_invalid",
        ),
        (
            "ANET",
            "rejected_promoted",
            "local_evidence_pack_rejection_or_gap_boundary_invalid",
        ),
        (
            "ASML",
            "future_publication",
            "local_evidence_pack_evidence_boundary_invalid",
        ),
    ],
)
def test_mutations_fail_closed(compiled, case_key, mutation, expected_code) -> None:
    _policy, packs, _result = compiled
    changed = deepcopy(_pack(packs, case_key))
    if mutation == "metric_table_removed":
        target = next(row for row in changed["evidence_items"] if row["object_type"] == "metric")
        target["structured_metric"].pop("table_path")
    elif mutation == "context_boundary_removed":
        target = next(
            row
            for row in changed["evidence_items"]
            if row["disposition"] == "accepted_bounded_context_evidence"
        )
        target["slot_bindings"][0]["claim_boundary_zh"] = ""
    elif mutation == "rejected_promoted":
        changed["rejected_items"][0]["writer_citable"] = True
    elif mutation == "future_publication":
        changed["evidence_items"][0]["publication_date"] = "2099-01-01"
    changed = _rehash(changed)
    with pytest.raises(SixCaseLocalEvidencePackError) as exc:
        validate_local_evidence_pack(changed)
    assert exc.value.code == expected_code


def test_materializer_writes_content_addressed_readable_packs(compiled, tmp_path) -> None:
    policy, _packs, _result = compiled
    output = tmp_path / "result.json"
    artifact_root = tmp_path / "objects"
    result = materialize_six_case_local_evidence_packs(
        policy=policy,
        repo_root=ROOT,
        artifact_root=artifact_root,
        output_path=output,
    )
    assert output.is_file()
    assert set(result["pack_artifacts"]) == set(CASES)
    for ref in result["pack_artifacts"].values():
        path = artifact_root / ref["object_key"]
        assert path.is_file()
        assert file_sha256(path) == ref["digest"]
        validate_local_evidence_pack(json.loads(path.read_text(encoding="utf-8")))
