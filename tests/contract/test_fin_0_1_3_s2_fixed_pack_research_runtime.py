from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_fixed_pack_research import (  # noqa: E402
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.s2_fixed_pack_research_runtime import (  # noqa: E402
    COMPACT_VERIFIER_OUTPUT_SCHEMA,
    NODE_ORDER,
    S2FixedPackRuntimeError,
    evaluate_final_output,
    execute_case,
    issue_case_admission,
    validate_case_admission,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


CONTRACT_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_fixed_pack_research_contract_v1_0.json"
)
PROFILE_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s2_deepseek_v4_pro_fixed_pack_profile_v1_0.json"
)
HASH = "1" * 64
GIT = "2" * 40
ISSUED = "2026-08-10T08:00:00Z"
EXPIRES = "2026-08-10T12:00:00Z"


@pytest.fixture(scope="module")
def inputs():
    contract = load_fixed_pack_contract(CONTRACT_PATH, repo_root=ROOT)
    profile = load_fixed_pack_profile(PROFILE_PATH)
    packs = load_frozen_local_packs(contract=contract, repo_root=ROOT)
    compiled, _result = compile_six_case_model_inputs(
        contract=contract,
        profile=profile,
        packs=packs,
    )
    return profile, compiled


def _fake_content(request: dict) -> dict:
    node = request["node_key"]
    if node == "direct_baseline" or node in {"draft_writer", "final_writer"}:
        return {
            "sections": [
                {
                    "section_id": "executive_thesis",
                    "points": [
                        {
                            "text": "冻结证据支持一个有边界的初步判断。",
                            "epistemic_status": "bounded_inference",
                            "evidence_aliases": ["E001"],
                            "gap_aliases": ["G001"],
                        }
                    ],
                }
            ],
            "overall_confidence": "medium",
            "limitations": ["仍存在已声明的证据缺口。"],
        }
    if node == "research_lead":
        return {
            "thesis_hypotheses": ["检验证据是否支持持续性。"],
            "research_units": [],
        }
    if node.startswith("specialist::"):
        return {
            "family": node.split("::", 1)[1],
            "findings": [
                {
                    "text": "该研究家族形成有限证据支持。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E001"],
                    "gap_aliases": ["G001"],
                    "counterevidence": "证据缺口仍然存在。",
                    "confidence": "medium",
                }
            ],
            "unresolved": ["需要补源。"],
        }
    if node == "cross_unit_synthesis":
        return {
            "cross_mechanism_findings": [
                {
                    "text": "需求与财务传导只能形成有边界的综合判断。",
                    "epistemic_status": "bounded_inference",
                    "evidence_aliases": ["E001"],
                    "gap_aliases": ["G001"],
                }
            ],
            "thesis": "有限支持",
            "antithesis": "关键缺口可能改变判断",
            "unresolved_conflicts": [],
        }
    if node == "red_team_critic":
        return {
            "issues": [],
            "missing_counter_thesis": [],
            "rewrite_instructions": ["保留缺口边界。"],
        }
    if node == "verifier":
        return {
            "schema_version": COMPACT_VERIFIER_OUTPUT_SCHEMA,
            "claim_checks": [
                {
                    "claim_id": f"CLM:{request['case_key']}:001",
                    "status": "bounded",
                    "finding_codes": [],
                    "reason": "存在引用但仍有缺口。",
                }
            ],
            "global_finding_codes": [],
            "verdict": "pass_with_findings",
        }
    raise AssertionError(node)


def fake_provider(request: dict) -> dict:
    return {
        "status": "ok",
        "content": json.dumps(_fake_content(request), ensure_ascii=False),
        "finish_reason": "stop",
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "raw_response": {"fixture": True, "node_key": request["node_key"]},
    }


def _admission(case_input: dict, profile: dict, nonce: str) -> dict:
    return issue_case_admission(
        case_input=case_input,
        profile=profile,
        execution_git_commit=GIT,
        runner_sha256=HASH,
        contract_sha256=HASH,
        profile_sha256=HASH,
        issued_at=ISSUED,
        expires_at=EXPIRES,
        run_nonce=nonce,
        credential_present=True,
    )


def test_six_case_full_fake_chain_is_exact_same_input_and_capture_first(
    inputs, tmp_path
) -> None:
    profile, cases = inputs
    for case_input in cases:
        case_key = case_input["case_key"]
        admission = _admission(case_input, profile, f"fake-{case_key}")
        ledger = SharedAdmissionConsumptionLedger(tmp_path / f"{case_key}.sqlite")
        runtime_root = tmp_path / case_key
        terminal = execute_case(
            admission=admission,
            case_input=case_input,
            profile=profile,
            execution_git_commit=GIT,
            runner_sha256=HASH,
            contract_sha256=HASH,
            profile_sha256=HASH,
            runtime_root=runtime_root,
            shared_ledger=ledger,
            provider_call=fake_provider,
            observed_at=ISSUED,
        )
        assert terminal["status"] == "completed"
        assert terminal["observed_counts"]["provider_calls"] == 13
        assert terminal["observed_counts"]["retries"] == 0
        assert terminal["same_input_pair_proven"] is True
        assert terminal["business_artifact_promoted"] is False
        assert len(list(runtime_root.glob("raw_model_only/calls/*/request.json"))) == 13
        assert len(list(runtime_root.glob("raw_model_only/calls/*/capture.json"))) == 13
        assert ledger.read(admission["admission_digest"]).state == "terminal"


def test_provider_failure_is_captured_and_terminalized_without_retry(
    inputs, tmp_path
) -> None:
    profile, cases = inputs
    case_input = cases[0]
    admission = _admission(case_input, profile, "provider-failure")

    def failing_provider(request: dict) -> dict:
        if request["node_key"] == "specialist::product_and_technology_position":
            return {
                "status": "provider_error",
                "failure_reason": "fixture disconnect",
                "content": "",
            }
        return fake_provider(request)

    runtime_root = tmp_path / "failure"
    terminal = execute_case(
        admission=admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=GIT,
        runner_sha256=HASH,
        contract_sha256=HASH,
        profile_sha256=HASH,
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "failure.sqlite"),
        provider_call=failing_provider,
        observed_at=ISSUED,
    )
    assert terminal["status"] == "failed"
    assert terminal["terminal_phase"] == (
        "specialist::product_and_technology_position"
    )
    assert terminal["observed_counts"]["provider_calls"] == 4
    assert terminal["observed_counts"]["retries"] == 0
    assert len(list(runtime_root.glob("raw_model_only/calls/*/capture.json"))) == 4
    failed_capture = json.loads(
        next(
            runtime_root.glob(
                "raw_model_only/calls/call_04_specialist__product_and_technology_position/capture.json"
            )
        ).read_text(encoding="utf-8")
    )
    assert failed_capture["provider_response"]["failure_reason"] == "fixture disconnect"


def test_exact_once_admission_cannot_be_reused(inputs, tmp_path) -> None:
    profile, cases = inputs
    case_input = cases[0]
    admission = _admission(case_input, profile, "exact-once")
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "exact.sqlite")
    execute_case(
        admission=admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=GIT,
        runner_sha256=HASH,
        contract_sha256=HASH,
        profile_sha256=HASH,
        runtime_root=tmp_path / "first",
        shared_ledger=ledger,
        provider_call=fake_provider,
        observed_at=ISSUED,
    )
    with pytest.raises(SharedAdmissionLedgerError) as exc:
        execute_case(
            admission=admission,
            case_input=case_input,
            profile=profile,
            execution_git_commit=GIT,
            runner_sha256=HASH,
            contract_sha256=HASH,
            profile_sha256=HASH,
            runtime_root=tmp_path / "second",
            shared_ledger=ledger,
            provider_call=fake_provider,
            observed_at=ISSUED,
        )
    assert exc.value.code.startswith("shared_admission_already_consumed")


def test_cumulative_budget_failure_is_captured_before_stop(inputs, tmp_path) -> None:
    profile, cases = inputs
    case_input = cases[0]
    admission = _admission(case_input, profile, "budget-stop")

    def oversized_provider(request: dict) -> dict:
        response = fake_provider(request)
        response["input_tokens"] = 600_000
        response["total_tokens"] = 600_050
        return response

    runtime_root = tmp_path / "budget"
    terminal = execute_case(
        admission=admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=GIT,
        runner_sha256=HASH,
        contract_sha256=HASH,
        profile_sha256=HASH,
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "budget.sqlite"),
        provider_call=oversized_provider,
        observed_at=ISSUED,
    )
    assert terminal["status"] == "failed"
    assert terminal["terminal_code"] == (
        "fixed_pack_runtime_cumulative_budget_exceeded_after_capture"
    )
    assert terminal["observed_counts"]["provider_calls"] == 1
    assert len(list(runtime_root.glob("raw_model_only/calls/*/capture.json"))) == 1


def test_admission_mutations_fail_closed(inputs) -> None:
    profile, cases = inputs
    case_input = cases[0]
    admission = _admission(case_input, profile, "mutation")
    changed = deepcopy(admission)
    changed["case_input_digest"] = "9" * 64
    with pytest.raises(S2FixedPackRuntimeError) as exc:
        validate_case_admission(
            changed,
            case_input=case_input,
            profile=profile,
            execution_git_commit=GIT,
            runner_sha256=HASH,
            contract_sha256=HASH,
            profile_sha256=HASH,
            observed_at=ISSUED,
        )
    assert exc.value.code == "fixed_pack_admission_digest_or_state_invalid"


def test_unknown_alias_and_numeric_mutation_are_l1_l2_findings(inputs) -> None:
    _profile, cases = inputs
    report = {
        "sections": [
            {
                "section_id": "executive_thesis",
                "points": [
                    {
                        "text": "不存在的数字为 987654321。",
                        "epistemic_status": "fact",
                        "evidence_aliases": ["E999"],
                        "gap_aliases": [],
                    }
                ],
            }
        ]
    }
    findings = evaluate_final_output(final_output=report, case_input=cases[0])
    assert any(row["code"] == "final_report_unknown_alias" for row in findings)
    assert any(
        row["code"] == "final_report_numeric_surface_not_in_cited_evidence"
        and row["level"] == "L1"
        for row in findings
    )
