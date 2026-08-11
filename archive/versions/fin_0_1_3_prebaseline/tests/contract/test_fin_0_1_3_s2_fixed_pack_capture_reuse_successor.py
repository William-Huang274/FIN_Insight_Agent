from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest  # noqa: E402
from sec_agent.s2_fixed_pack_capture_reuse_successor import (  # noqa: E402
    S2FixedPackSuccessorError,
    SUCCESSOR_NODE_ORDER,
    compile_successor_case_input,
    load_predecessor_import_bundle,
    load_successor_contract,
)
from sec_agent.s2_fixed_pack_capture_reuse_successor_runtime import (  # noqa: E402
    S2FixedPackSuccessorRuntimeError,
    execute_successor_case,
    issue_successor_admission,
)
from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    COMPACT_VERIFIER_OUTPUT_SCHEMA,
    evaluate_final_output,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


BASE_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
SUCCESSOR_CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_dell_fixed_pack_capture_reuse_successor_contract_v1_0.json"
)
HASH = "1" * 64
GIT = "2" * 40
ISSUED = "2026-08-10T12:00:00Z"
EXPIRES = "2026-08-10T16:00:00Z"


@pytest.fixture(scope="module")
def material():
    base_contract = load_fixed_pack_contract(BASE_CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=base_contract, repo_root=ROOT)
    inputs, _result = compile_six_case_model_inputs(
        contract=base_contract, profile=profile, packs=packs
    )
    base = next(row for row in inputs if row["case_key"] == "DELL")
    contract = load_successor_contract(SUCCESSOR_CONTRACT_PATH, repo_root=ROOT)
    successor = compile_successor_case_input(
        base_case_input=base, contract=contract, profile=profile
    )
    predecessor = load_predecessor_import_bundle(
        contract=contract, repo_root=ROOT
    )
    return profile, contract, base, successor, predecessor


def _report() -> dict:
    return {
        "sections": [
            {
                "section_id": "executive_thesis",
                "points": [
                    {
                        "text": "AI服务器收入为161.32亿美元，占ISG收入55.6%，但仍有证据缺口。",
                        "epistemic_status": "bounded_inference",
                        "evidence_aliases": ["E002"],
                        "gap_aliases": ["G001"],
                        "numeric_refs": [
                            "PRES:DELL:FY2027_Q1:AI_SERVER_REVENUE:ZH_YI_USD",
                            "FORM:DELL:FY2027_Q1:AI_SERVER_REVENUE_SHARE_OF_ISG",
                        ],
                    }
                ],
            }
        ],
        "overall_confidence": "medium",
        "limitations": ["仍需独立需求和客户集中度证据。"],
    }


def _fake_content(node_key: str) -> dict:
    if node_key.startswith("specialist::"):
        return {
            "family": node_key.split("::", 1)[1],
            "findings": [
                {
                    "text": "冻结证据支持有边界的公司判断。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E002"],
                    "gap_aliases": ["G001"],
                    "numeric_refs": [],
                    "counterevidence": "缺口仍可能改变判断。",
                    "confidence": "medium",
                }
            ],
            "unresolved": ["需要补源。"],
        }
    if node_key == "cross_unit_synthesis":
        return {
            "cross_mechanism_findings": [
                {
                    "text": "需求与利润传导只能形成有限结论。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E002"],
                    "gap_aliases": ["G001"],
                    "numeric_refs": [],
                }
            ],
            "thesis": "有限支持",
            "antithesis": "利润归属和客户集中仍未闭合",
            "unresolved_conflicts": [],
        }
    if node_key in {"draft_writer", "final_writer"}:
        return _report()
    if node_key == "red_team_critic":
        return {
            "issues": [],
            "missing_counter_thesis": [],
            "rewrite_instructions": ["保留缺口。"],
        }
    if node_key == "verifier":
        return {
            "schema_version": COMPACT_VERIFIER_OUTPUT_SCHEMA,
            "claim_checks": [
                {
                    "claim_id": "CLM:DELL:001",
                    "status": "bounded",
                    "finding_codes": [],
                    "reason": "事实与公式引用受控。",
                }
            ],
            "global_finding_codes": [],
            "verdict": "pass_with_findings",
        }
    raise AssertionError(node_key)


def fake_provider(request: dict) -> dict:
    return {
        "status": "ok",
        "content": json.dumps(
            _fake_content(str(request["node_key"])), ensure_ascii=False
        ),
        "finish_reason": "stop",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "raw_response": {"fixture": True},
    }


def _admission(successor: dict, predecessor: dict, profile: dict, nonce: str):
    return issue_successor_admission(
        case_input=successor,
        predecessor_bundle=predecessor,
        profile=profile,
        execution_git_commit=GIT,
        runtime_sha256=HASH,
        runner_sha256=HASH,
        successor_contract_sha256=HASH,
        base_contract_sha256=HASH,
        profile_sha256=HASH,
        issued_at=ISSUED,
        expires_at=EXPIRES,
        run_nonce=nonce,
        credential_present=False,
        execution_mode="fixture",
    )


def test_real_predecessor_imports_only_five_usable_immutable_outputs(material) -> None:
    _profile, _contract, base, successor, predecessor = material
    assert predecessor["case_input_digest"] == base["model_visible_digest"]
    assert successor["base_model_visible_digest"] == base["model_visible_digest"]
    assert successor["model_visible_digest"] != base["model_visible_digest"]
    assert [row["node_key"] for row in predecessor["imported_outputs"]] == [
        "direct_baseline",
        "research_lead",
        "specialist::demand_authenticity_and_sustainability",
        "specialist::product_and_technology_position",
        "specialist::supply_capacity_and_competition",
    ]
    assert predecessor["failed_attempt_evidence"] == {
        **predecessor["failed_attempt_evidence"],
        "promoted_as_usable_output": False,
    }


def test_numeric_aliases_and_formula_traces_are_deterministic(material) -> None:
    _profile, _contract, _base, successor, _predecessor = material
    numeric = successor["numeric_authority"]
    facts = {row["numeric_ref"]: row for row in numeric["source_numeric_facts"]}
    ai = facts["NUM:DELL:FY2027_Q1:AI_SERVER_REVENUE"]
    assert any(
        row["rendered"] == "161.32 亿美元"
        and row["operation"] == "divide"
        and row["operand"] == "100"
        for row in ai["display_surfaces"]
    )
    formulas = {row["formula_ref"]: row for row in numeric["formula_traces"]}
    share = formulas[
        "FORM:DELL:FY2027_Q1:AI_SERVER_REVENUE_SHARE_OF_ISG"
    ]
    assert share["input_values"] == ["16132", "29009"]
    assert share["display_surfaces"][0]["rendered"] == "55.6%"


def test_formula_period_mutation_fails_closed(material) -> None:
    profile, contract, base, _successor, _predecessor = material
    changed = deepcopy(contract)
    changed["numeric_authority"]["source_numeric_facts"][2][
        "period_id"
    ] = "DELL_WRONG_PERIOD"
    with pytest.raises(S2FixedPackSuccessorError) as exc:
        compile_successor_case_input(
            base_case_input=base, contract=changed, profile=profile
        )
    assert exc.value.code == "fixed_pack_formula_unit_or_period_mismatch"


def test_numeric_surface_requires_matching_current_ref(material) -> None:
    _profile, _contract, _base, successor, _predecessor = material
    assert evaluate_final_output(final_output=_report(), case_input=successor) == []
    changed = _report()
    changed["sections"][0]["points"][0]["text"] = (
        "AI服务器收入为161.33亿美元，占ISG收入55.6%。"
    )
    findings = evaluate_final_output(final_output=changed, case_input=successor)
    assert any(
        row["code"] == "final_report_numeric_surface_not_authorized_by_refs"
        and "161.33" in row["numeric_tokens"]
        for row in findings
    )
    changed = _report()
    changed["sections"][0]["points"][0]["numeric_refs"] = []
    findings = evaluate_final_output(final_output=changed, case_input=successor)
    assert any(
        row["code"] == "final_report_material_numeric_ref_missing"
        for row in findings
    )


def test_successor_executes_only_eight_calls_and_preserves_combined_lineage(
    material, tmp_path
) -> None:
    profile, _contract, _base, successor, predecessor = material
    admission = _admission(successor, predecessor, profile, "successor-complete")
    terminal = execute_successor_case(
        admission=admission,
        case_input=successor,
        predecessor_bundle=predecessor,
        profile=profile,
        execution_git_commit=GIT,
        runtime_sha256=HASH,
        runner_sha256=HASH,
        successor_contract_sha256=HASH,
        base_contract_sha256=HASH,
        profile_sha256=HASH,
        runtime_root=tmp_path / "attempt",
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "ledger.sqlite"),
        provider_call=fake_provider,
        observed_at=ISSUED,
    )
    assert terminal["status"] == "completed"
    assert terminal["observed_counts"]["imported_usable_nodes"] == 5
    assert terminal["observed_counts"]["successor_provider_calls"] == 8
    assert terminal["observed_counts"]["combined_provider_attempts"] == 14
    assert terminal["observed_counts"]["logical_outputs_present"] == 13
    assert len(list((tmp_path / "attempt").glob("raw_model_only/calls/*/capture.json"))) == 8
    assert [row["logical_node_index"] for row in terminal["successor_call_receipts"]] == list(range(6, 14))
    assert terminal["same_evidence_pack_proven"] is True
    assert terminal["same_input_pair_proven"] is False
    assert terminal["paired_assessment_eligible"] is False
    assert terminal["semantic_retry"] is False


def test_successor_provider_failure_is_new_terminal_not_retry(material, tmp_path) -> None:
    profile, _contract, _base, successor, predecessor = material
    admission = _admission(successor, predecessor, profile, "successor-failure")

    def failing_provider(request: dict) -> dict:
        assert request["node_key"] == SUCCESSOR_NODE_ORDER[0]
        return {"status": "provider_error", "failure_reason": "fixture", "content": ""}

    terminal = execute_successor_case(
        admission=admission,
        case_input=successor,
        predecessor_bundle=predecessor,
        profile=profile,
        execution_git_commit=GIT,
        runtime_sha256=HASH,
        runner_sha256=HASH,
        successor_contract_sha256=HASH,
        base_contract_sha256=HASH,
        profile_sha256=HASH,
        runtime_root=tmp_path / "failed",
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "failed.sqlite"),
        provider_call=failing_provider,
        observed_at=ISSUED,
    )
    assert terminal["status"] == "failed"
    assert terminal["observed_counts"]["successor_provider_calls"] == 1
    assert terminal["observed_counts"]["retries"] == 0
    assert terminal["semantic_retry"] is False
    assert len(list((tmp_path / "failed").glob("raw_model_only/calls/*/capture.json"))) == 1


def test_admission_mutation_fails_closed(material) -> None:
    profile, _contract, _base, successor, predecessor = material
    admission = _admission(successor, predecessor, profile, "mutation")
    changed = deepcopy(admission)
    changed["successor_node_order"] = list(reversed(SUCCESSOR_NODE_ORDER))
    with pytest.raises(S2FixedPackSuccessorRuntimeError) as exc:
        from sec_agent.s2_fixed_pack_capture_reuse_successor_runtime import (
            validate_successor_admission,
        )

        validate_successor_admission(
            changed,
            case_input=successor,
            predecessor_bundle=predecessor,
            profile=profile,
            execution_git_commit=GIT,
            runtime_sha256=HASH,
            runner_sha256=HASH,
            successor_contract_sha256=HASH,
            base_contract_sha256=HASH,
            profile_sha256=HASH,
            observed_at=ISSUED,
        )
    assert exc.value.code == "fixed_pack_successor_admission_digest_or_state_invalid"
