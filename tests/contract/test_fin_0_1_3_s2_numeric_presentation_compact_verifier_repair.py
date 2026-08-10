from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_fixed_pack_capture_reuse_successor import (  # noqa: E402
    REPAIRED_NUMERIC_AUTHORITY_SCHEMA,
    REPAIRED_SUCCESSOR_INPUT_SCHEMA,
    compile_repaired_successor_case_input,
    compile_successor_case_input,
    load_numeric_verifier_repair_policy,
    load_successor_contract,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    COMPACT_VERIFIER_OUTPUT_SCHEMA,
    build_compact_verifier_projection,
    evaluate_final_output,
    perform_node_call,
    resolve_final_output_numeric_surfaces,
    validate_compact_verifier_output,
)


BASE_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
SUCCESSOR_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_numeric_presentation_compact_verifier_repair_policy_v1_0.json"
)


@pytest.fixture(scope="module")
def material():
    base_contract = load_fixed_pack_contract(BASE_CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=base_contract, repo_root=ROOT)
    inputs, _result = compile_six_case_model_inputs(
        contract=base_contract,
        profile=profile,
        packs=packs,
    )
    base = next(row for row in inputs if row["case_key"] == "DELL")
    successor_contract = load_successor_contract(
        SUCCESSOR_CONTRACT_PATH,
        repo_root=ROOT,
    )
    successor = compile_successor_case_input(
        base_case_input=base,
        contract=successor_contract,
        profile=profile,
    )
    policy = load_numeric_verifier_repair_policy(POLICY_PATH, repo_root=ROOT)
    repaired = compile_repaired_successor_case_input(
        successor_case_input=successor,
        repair_policy=policy,
        profile=profile,
    )
    return profile, inputs, successor, repaired


def _report() -> dict:
    return {
        "sections": [
            {
                "section_id": "demand_and_supply",
                "points": [
                    {
                        "text": "Q1 FY27 AI服务器收入为161.32亿美元，占ISG收入55.6%。",
                        "epistemic_status": "bounded_inference",
                        "evidence_aliases": ["E002"],
                        "gap_aliases": [],
                        "numeric_refs": [
                            "NUM:DELL:FY2027_Q1:AI_SERVER_REVENUE",
                            "FORM:DELL:FY2027_Q1:AI_SERVER_REVENUE_SHARE_OF_ISG",
                        ],
                    },
                    {
                        "text": "TSMC先进制程晶圆收入占比为77%，但不能证明Dell获得CoWoS分配。",
                        "epistemic_status": "bounded_inference",
                        "evidence_aliases": ["E015"],
                        "gap_aliases": ["G001"],
                        "numeric_refs": [],
                    },
                ],
            }
        ],
        "overall_confidence": "medium",
        "limitations": ["仍缺Dell特定供应分配。"],
    }


def _valid_verifier(projection: dict) -> dict:
    return {
        "schema_version": COMPACT_VERIFIER_OUTPUT_SCHEMA,
        "claim_checks": [
            {
                "claim_id": claim_id,
                "status": "bounded",
                "finding_codes": [],
                "reason": "证据支持方向，但明确保留归因边界。",
            }
            for claim_id in projection["expected_claim_ids"]
        ],
        "global_finding_codes": [],
        "verdict": "pass_with_findings",
    }


def test_repair_adds_tsmc_numeric_inventory_without_mutating_v1(material) -> None:
    _profile, _inputs, successor, repaired = material
    assert successor["schema_version"] != REPAIRED_SUCCESSOR_INPUT_SCHEMA
    assert repaired["schema_version"] == REPAIRED_SUCCESSOR_INPUT_SCHEMA
    numeric = repaired["numeric_authority"]
    assert numeric["schema_version"] == REPAIRED_NUMERIC_AUTHORITY_SCHEMA
    assert len(successor["numeric_authority"]["source_numeric_facts"]) == 13
    assert len(numeric["source_numeric_facts"]) == 14
    tsmc = next(
        row
        for row in numeric["source_numeric_facts"]
        if row["numeric_ref"].endswith("ADVANCED_TECH_WAFER_REVENUE_SHARE")
    )
    assert tsmc["source_token"] == "77%"
    assert tsmc["evidence_aliases"] == ["E015"]
    assert tsmc["display_surfaces"][0]["rendered"] == "77%"
    assert repaired["model_rules"]["presentation_ref_selection"] == "optional"


def test_num_ref_authorizes_linked_surface_and_fiscal_label_is_not_number(material) -> None:
    _profile, _inputs, _successor, repaired = material
    findings = evaluate_final_output(final_output=_report(), case_input=repaired)
    numeric_codes = {
        row["code"]
        for row in findings
        if row["code"].startswith("final_report_material_numeric")
        or row["code"].startswith("final_report_numeric_surface")
    }
    assert numeric_codes == set()
    receipts = resolve_final_output_numeric_surfaces(
        final_output=_report(),
        case_input=repaired,
    )
    assert not any(row["numeric_token"] == "7" for row in receipts)
    tsmc = next(row for row in receipts if row["numeric_token"] == "77%")
    assert tsmc["binding_mode"] == "deterministic_unique_source_surface"
    assert tsmc["matched_numeric_refs"] == [
        "NUM:DELL:READTHROUGH:TSMC_2026_Q2:ADVANCED_TECH_WAFER_REVENUE_SHARE"
    ]


def test_unrecognized_surface_still_fails_closed(material) -> None:
    _profile, _inputs, _successor, repaired = material
    changed = _report()
    changed["sections"][0]["points"][0]["text"] = (
        "Q1 FY27 AI服务器收入为161.33亿美元，占ISG收入55.6%。"
    )
    findings = evaluate_final_output(final_output=changed, case_input=repaired)
    assert any(
        row["code"] == "final_report_numeric_surface_not_authorized_by_refs"
        and "161.33" in row["numeric_tokens"]
        for row in findings
    )


def test_compact_projection_selects_source_text_and_requires_exact_claim_coverage(
    material,
) -> None:
    _profile, _inputs, _successor, repaired = material
    projection = build_compact_verifier_projection(
        case_input=repaired,
        final_report=_report(),
    )
    assert projection["expected_claim_ids"] == ["CLM:DELL:001", "CLM:DELL:002"]
    assert {row["evidence_alias"] for row in projection["selected_evidence"]} == {
        "E002",
        "E015",
    }
    assert {row["source_material_alias"] for row in projection["selected_source_materials"]} == {
        "M002",
        "M013",
    }
    assert all(
        row["captured_source_excerpt"]
        and row["excerpt_characters"] <= 2400
        and "source_text" not in row
        for row in projection["selected_source_materials"]
    )
    valid = _valid_verifier(projection)
    assert validate_compact_verifier_output(
        verifier_output=valid,
        projection=projection,
    ) == []

    missing = deepcopy(valid)
    missing["claim_checks"] = missing["claim_checks"][:-1]
    findings = validate_compact_verifier_output(
        verifier_output=missing,
        projection=projection,
    )
    assert any(
        row["code"] == "verification_incomplete_claim_coverage_invalid"
        and row["missing_claim_ids"] == ["CLM:DELL:002"]
        for row in findings
    )


def test_compact_projection_is_provider_neutral_across_primary_cases(material) -> None:
    _profile, inputs, _successor, _repaired = material
    for case_input in inputs[:3]:
        case_key = case_input["case_key"]
        report = deepcopy(_report())
        report["sections"][0]["points"] = [
            {
                "text": "冻结证据支持有限判断。",
                "epistemic_status": "bounded_inference",
                "evidence_aliases": ["E001"],
                "gap_aliases": ["G001"],
                "numeric_refs": [],
            }
        ]
        projection = build_compact_verifier_projection(
            case_input=case_input,
            final_report=report,
        )
        assert projection["expected_claim_ids"] == [f"CLM:{case_key}:001"]
        assert projection["selected_source_materials"][0][
            "captured_source_excerpt"
        ]


def test_verifier_length_and_invalid_json_are_hard_incomplete(tmp_path) -> None:
    request = {"node_key": "verifier", "messages": []}

    def length_provider(_request: dict) -> dict:
        return {
            "status": "ok",
            "content": '{"claim_checks":[',
            "finish_reason": "length",
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }

    receipt, _output, findings, fatal = perform_node_call(
        call_index=1,
        node_key="verifier",
        request=request,
        provider_call=length_provider,
        captures_root=tmp_path / "length",
        observed_at="2026-08-10T12:00:00Z",
    )
    assert receipt["finish_reason"] == "length"
    assert fatal == "verification_incomplete_finish_reason_length"
    assert findings[0]["level"] == "L1"
    assert (tmp_path / "length" / "call_01_verifier" / "capture.json").is_file()

    def invalid_provider(_request: dict) -> dict:
        return {
            "status": "ok",
            "content": '{"claim_checks":[',
            "finish_reason": "stop",
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }

    _receipt, _output, findings, fatal = perform_node_call(
        call_index=1,
        node_key="verifier",
        request=request,
        provider_call=invalid_provider,
        captures_root=tmp_path / "invalid",
        observed_at="2026-08-10T12:00:00Z",
    )
    assert fatal == "verification_incomplete_invalid_json"
    assert findings[0]["level"] == "L1"


def test_repair_policy_base_binding_mutation_fails_closed(tmp_path) -> None:
    changed = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    changed["base_successor_contract"]["sha256"] = "0" * 64
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Exception) as exc:
        load_numeric_verifier_repair_policy(path, repo_root=ROOT)
    assert "fixed_pack_repair_policy_identity_or_boundary_invalid" in str(exc.value)
