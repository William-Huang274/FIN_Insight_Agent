from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (  # noqa: E402
    SelectedEvidenceNumericNaturalNodeCanaryError,
    ZERO_CALL_SCOPE,
    compile_canary_material,
    execute_canary,
    issue_fixture_admission,
    load_canary_policy,
    validate_canary_output,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "policy_v1_0.json"
)
OBSERVED_AT = "2026-08-11T08:00:00Z"


@pytest.fixture(scope="module")
def material():
    policy = load_canary_policy(POLICY_PATH, repo_root=ROOT)
    return compile_canary_material(policy=policy, repo_root=ROOT)


def _valid_output() -> dict:
    return {
        "schema_version": (
            "fin_ia_0_1_3_s2_demand_authenticity_numeric_view_atom_"
            "canary_output_v1_0"
        ),
        "case_key": "DELL",
        "node_id": "dell_demand_authenticity_numeric_view_atom_canary_v1",
        "judgment": "supported_with_limits",
        "support_atom": {
            "text": (
                "Dell在FY2027 Q1披露AI服务器收入$16.1 billion，"
                "customer count surpassed 5,000，并披露AI订单$24.4 billion；"
                "这些是当前AI服务器需求存在和客户覆盖扩大的直接指标。"
            ),
            "epistemic_state": "fact_supported",
            "evidence_refs": ["E022"],
            "numeric_refs": [
                "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
                "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
                "NUM:DELL:AI_ORDERS:66F359E8F5E4",
            ],
        },
        "counterevidence_atom": {
            "text": (
                "E018显示竞争对手客户仍在消化此前订单，E023显示内存不确定性"
                "可能推动客户提前锁定基础设施；二者只构成时点与pull-forward风险，"
                "不能当成Dell的直接量化需求证明。"
            ),
            "epistemic_state": "bounded_inference",
            "evidence_refs": ["E018", "E023"],
            "numeric_refs": [],
        },
        "boundary_atom": {
            "text": (
                "这些披露不足以证明订单会持续转化，也不能证明客户集中度、"
                "产品毛利或终端需求的可持续性。"
            ),
            "epistemic_state": "cannot_infer",
            "evidence_refs": ["E022", "E018", "E023"],
            "numeric_refs": [],
        },
        "used_numeric_refs": [
            "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
            "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
            "NUM:DELL:AI_ORDERS:66F359E8F5E4",
        ],
    }


def _response(output: dict | str, *, finish_reason: str = "stop") -> dict:
    content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
    return {
        "status": "ok",
        "content": content,
        "finish_reason": finish_reason,
        "input_tokens": 1200,
        "output_tokens": 220,
        "total_tokens": 1420,
    }


def _execute(tmp_path: Path, material: dict, response: dict, suffix: str = "r1"):
    admission = issue_fixture_admission(
        material=material,
        run_id=f"fixture-run-{suffix}",
        attempt_id=f"fixture-attempt-{suffix}",
        observed_at=OBSERVED_AT,
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    calls: list[dict] = []

    def provider(request):
        calls.append(dict(request))
        return response

    terminal = execute_canary(
        admission=admission,
        material=material,
        provider_call=provider,
        runtime_root=tmp_path / f"attempt-{suffix}",
        shared_ledger=ledger,
        observed_at=OBSERVED_AT,
    )
    return admission, ledger, calls, terminal


def test_compiler_uses_only_three_bounded_evidence_and_four_numeric_facts(material) -> None:
    compiled = material["compiled_input"]
    request = material["provider_request"]
    assert [row["evidence_alias"] for row in compiled["evidence"]] == [
        "E022",
        "E018",
        "E023",
    ]
    assert len(compiled["numeric_facts"]) == 4
    assert {row["numeric_ref"] for row in compiled["numeric_facts"]} == {
        "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
        "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
        "NUM:DELL:AI_ORDERS:66F359E8F5E4",
        "NUM:DELL:AI_BACKLOG:A82BF565C064",
    }
    serialized = json.dumps(compiled, ensure_ascii=False)
    assert '"source_text"' not in serialized
    assert compiled["raw_source_text_in_model_input"] is False
    assert len(json.dumps(request, ensure_ascii=False, separators=(",", ":"))) <= 24000
    assert request["max_tokens"] == 1800


def test_valid_atom_passes_local_role_boundary_and_numeric_gates(material) -> None:
    receipt = validate_canary_output(output=_valid_output(), material=material)
    assert receipt["status"] == "pass"
    assert receipt["business_artifact_promotion"] is False
    assert {"conversion", "concentration", "margin", "durability"} <= set(
        receipt["boundary_topic_groups"]
    )


def test_unbound_material_amount_still_fails_the_local_numeric_gate(material) -> None:
    output = deepcopy(_valid_output())
    output["support_atom"]["text"] += " 另有未经绑定的金额$17.2 billion。"
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryError) as exc:
        validate_canary_output(output=output, material=material)
    assert exc.value.code == "natural_node_canary_local_numeric_gate_failed"


def test_fake_success_is_exactly_one_call_capture_first_and_no_promotion(
    material, tmp_path
) -> None:
    admission, ledger, calls, terminal = _execute(
        tmp_path, material, _response(_valid_output()), "success"
    )
    assert len(calls) == 1
    assert terminal["status"] == "completed"
    assert terminal["terminal_code"] == "natural_node_canary_completed_no_promotion"
    assert terminal["observed_counts"] == {
        "provider_calls": 1,
        "model_calls": 1,
        "source_calls": 0,
        "network_tool_calls": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    assert terminal["business_artifact_promotion"] is False
    assert (tmp_path / "attempt-success/raw_model_only/calls/call_01/capture.json").is_file()
    assert (tmp_path / "attempt-success/validated/atom_output.json").is_file()
    assert ledger.read(admission["admission_digest"]).state == "terminal"


def test_same_admission_cannot_be_consumed_twice(material, tmp_path) -> None:
    admission, ledger, _calls, _terminal = _execute(
        tmp_path, material, _response(_valid_output()), "once"
    )
    with pytest.raises(SharedAdmissionLedgerError) as exc:
        execute_canary(
            admission=admission,
            material=material,
            provider_call=lambda _request: _response(_valid_output()),
            runtime_root=tmp_path / "different-attempt-root",
            shared_ledger=ledger,
            observed_at=OBSERVED_AT,
        )
    assert exc.value.code.startswith("shared_admission_already_consumed")


def test_transport_failure_preserves_full_capture_and_terminalizes(material, tmp_path) -> None:
    response = {
        "status": "provider_error",
        "failure_reason": "simulated transport timeout",
        "content": "partial private provider output 123",
        "finish_reason": None,
    }
    _admission, _ledger, calls, terminal = _execute(
        tmp_path, material, response, "transport"
    )
    assert len(calls) == 1
    assert terminal["status"] == "failed"
    assert terminal["terminal_phase"] == "provider_transport"
    capture = json.loads(
        (tmp_path / "attempt-transport/raw_model_only/calls/call_01/capture.json").read_text(
            encoding="utf-8"
        )
    )
    assert capture["provider_response"] == response
    assert "partial private provider output" not in json.dumps(terminal)


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (
            _response(_valid_output(), finish_reason="length"),
            "natural_node_canary_incomplete_finish_reason_length",
        ),
        (
            _response("not-json"),
            "natural_node_canary_output_json_invalid",
        ),
    ],
)
def test_truncation_and_invalid_json_fail_after_capture(
    material, tmp_path, response, expected_code
) -> None:
    suffix = expected_code.rsplit("_", 1)[-1]
    _admission, _ledger, calls, terminal = _execute(
        tmp_path, material, response, suffix
    )
    assert len(calls) == 1
    assert terminal["status"] == "failed"
    assert terminal["terminal_code"] == expected_code
    assert (tmp_path / f"attempt-{suffix}/raw_model_only/calls/call_01/capture.json").is_file()


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda row: row.update({"extra": "forbidden"}),
            "natural_node_canary_output_fields_invalid",
        ),
        (
            lambda row: row.update({"case_key": "MU"}),
            "natural_node_canary_output_identity_invalid",
        ),
        (
            lambda row: row["support_atom"].update({"evidence_refs": ["E018"]}),
            "natural_node_canary_support_role_invalid",
        ),
        (
            lambda row: row["counterevidence_atom"].update(
                {"evidence_refs": ["E022"]}
            ),
            "natural_node_canary_counterevidence_role_invalid",
        ),
        (
            lambda row: row["counterevidence_atom"].update(
                {"numeric_refs": ["NUM:DELL:AI_ORDERS:66F359E8F5E4"]}
            ),
            "natural_node_canary_counterevidence_role_invalid",
        ),
        (
            lambda row: row["support_atom"].update(
                {
                    "numeric_refs": [
                        "NUM:DELL:AI_SERVER_REVENUE:C4947C75D942",
                        "NUM:DELL:CUSTOMER_COUNT:8C7F5A41CBF9",
                    ]
                }
            ),
            "natural_node_canary_numeric_ref_requirements_failed",
        ),
        (
            lambda row: row["support_atom"].update(
                {"text": row["support_atom"]["text"].replace("$16.1 billion", "$16.1 million")}
            ),
            "natural_node_canary_required_presentations_missing",
        ),
        (
            lambda row: row["support_atom"].update(
                {"text": row["support_atom"]["text"] + " 目标价为$200。"}
            ),
            "natural_node_canary_report_or_recommendation_forbidden",
        ),
        (
            lambda row: row["boundary_atom"].update(
                {"text": "这些披露存在一些一般性限制。"}
            ),
            "natural_node_canary_boundary_semantics_missing",
        ),
    ],
)
def test_role_ref_numeric_and_boundary_mutations_fail_closed(
    material, mutator, expected_code
) -> None:
    output = deepcopy(_valid_output())
    mutator(output)
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryError) as exc:
        validate_canary_output(output=output, material=material)
    assert exc.value.code == expected_code


def test_unknown_numeric_ref_fails_before_numeric_guard(material) -> None:
    output = deepcopy(_valid_output())
    output["support_atom"]["numeric_refs"].append("NUM:DELL:FAKE:0000")
    output["used_numeric_refs"].append("NUM:DELL:FAKE:0000")
    with pytest.raises(SelectedEvidenceNumericNaturalNodeCanaryError) as exc:
        validate_canary_output(output=output, material=material)
    assert exc.value.code == "natural_node_canary_support_atom_unknown_ref"


def test_policy_does_not_register_or_issue_live_scope(material) -> None:
    assert material["policy"]["zero_call_run_scope"] == ZERO_CALL_SCOPE
    assert material["policy"]["hard_boundaries"]["live_authority_issued_by_this_policy"] is False
    registry = json.loads(
        (ROOT / "configs/runtime/fin_ia_project_os_run_scope_registry_v1_0.json").read_text(
            encoding="utf-8"
        )
    )
    scopes = registry["scopes"]
    assert ZERO_CALL_SCOPE in scopes
    assert (
        material["policy"]["live_run_scope_reserved_not_registered_or_authorized"]
        not in scopes
    )
