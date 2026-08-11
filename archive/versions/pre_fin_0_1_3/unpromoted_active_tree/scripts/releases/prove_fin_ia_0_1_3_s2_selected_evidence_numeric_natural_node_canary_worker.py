from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import socket
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_bytes,
    canonical_digest,
)
from sec_agent.s2_selected_evidence_numeric_natural_node_canary import (  # noqa: E402
    SelectedEvidenceNumericNaturalNodeCanaryError,
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
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "minimum_zero_call_implementation_v1_0.json"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_natural_node_canary_"
    "clean_worker_result_v1_0"
)
OBSERVED_AT = "2026-08-11T08:00:00Z"


class NaturalNodeCanaryCleanWorkerError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise NaturalNodeCanaryCleanWorkerError(code)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NaturalNodeCanaryCleanWorkerError(
            f"natural_node_canary_clean_worker_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), "natural_node_canary_clean_worker_json_not_object")
    return value


def _credential_variable_names() -> list[str]:
    pattern = re.compile(
        r"(?:API_KEY|SECRET_KEY|ACCESS_KEY|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|"
        r"DEEPSEEK|OPENAI|ANTHROPIC|TENCENT|ALPHAVANTAGE)",
        re.IGNORECASE,
    )
    return sorted(name for name in os.environ if pattern.search(name))


def _block_network() -> list[str]:
    attempts: list[str] = []

    def blocked(*_args: object, **_kwargs: object) -> None:
        attempts.append("socket")
        raise RuntimeError("natural_node_canary_clean_worker_network_forbidden")

    socket.socket.connect = blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked  # type: ignore[method-assign]
    socket.create_connection = blocked
    return attempts


def _valid_output() -> dict[str, Any]:
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


def _response(
    output: Mapping[str, Any] | str, *, finish_reason: str = "stop"
) -> dict[str, Any]:
    content = (
        str(output)
        if isinstance(output, str)
        else json.dumps(output, ensure_ascii=False)
    )
    return {
        "status": "ok",
        "content": content,
        "finish_reason": finish_reason,
        "input_tokens": 1200,
        "output_tokens": 220,
        "total_tokens": 1420,
    }


def _run_fixture(
    *,
    label: str,
    material: Mapping[str, Any],
    response: Mapping[str, Any],
    proof_root: Path,
    ledger: SharedAdmissionConsumptionLedger,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    admission = issue_fixture_admission(
        material=material,
        run_id=f"clean-fixture-run-{label}",
        attempt_id=f"clean-fixture-attempt-{label}",
        observed_at=OBSERVED_AT,
    )
    calls: list[dict[str, Any]] = []

    def provider(request: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append(dict(request))
        return response

    terminal = execute_canary(
        admission=admission,
        material=material,
        provider_call=provider,
        runtime_root=proof_root / "attempts" / label,
        shared_ledger=ledger,
        observed_at=OBSERVED_AT,
    )
    return admission, terminal, len(calls)


def _expect_output_error(
    *, material: Mapping[str, Any], output: Mapping[str, Any], code: str
) -> bool:
    try:
        validate_canary_output(output=output, material=material)
    except SelectedEvidenceNumericNaturalNodeCanaryError as exc:
        return exc.code == code
    return False


def _mutations(material: Mapping[str, Any]) -> dict[str, bool]:
    valid = _valid_output()

    extra = deepcopy(valid)
    extra["extra"] = "forbidden"

    support_role = deepcopy(valid)
    support_role["support_atom"]["evidence_refs"] = ["E018"]

    counter_role = deepcopy(valid)
    counter_role["counterevidence_atom"]["evidence_refs"] = ["E022"]

    unknown_ref = deepcopy(valid)
    unknown_ref["support_atom"]["numeric_refs"].append("NUM:DELL:FAKE:0000")
    unknown_ref["used_numeric_refs"].append("NUM:DELL:FAKE:0000")

    unit = deepcopy(valid)
    unit["support_atom"]["text"] = unit["support_atom"]["text"].replace(
        "$16.1 billion", "$16.1 million"
    )

    unbound = deepcopy(valid)
    unbound["support_atom"]["text"] += " 另有未经绑定的金额$17.2 billion。"

    boundary = deepcopy(valid)
    boundary["boundary_atom"]["text"] = "这些披露存在一些一般性限制。"

    return {
        "valid_fy2027_prose_passes": validate_canary_output(
            output=valid, material=material
        )["status"]
        == "pass",
        "unknown_top_level_field_fails_closed": _expect_output_error(
            material=material,
            output=extra,
            code="natural_node_canary_output_fields_invalid",
        ),
        "competitor_readthrough_as_direct_support_fails_closed": _expect_output_error(
            material=material,
            output=support_role,
            code="natural_node_canary_support_role_invalid",
        ),
        "counterevidence_omission_fails_closed": _expect_output_error(
            material=material,
            output=counter_role,
            code="natural_node_canary_counterevidence_role_invalid",
        ),
        "unknown_numeric_ref_fails_closed": _expect_output_error(
            material=material,
            output=unknown_ref,
            code="natural_node_canary_support_atom_unknown_ref",
        ),
        "unit_mutation_fails_closed": _expect_output_error(
            material=material,
            output=unit,
            code="natural_node_canary_required_presentations_missing",
        ),
        "unbound_material_money_fails_local_guard": _expect_output_error(
            material=material,
            output=unbound,
            code="natural_node_canary_local_numeric_gate_failed",
        ),
        "missing_durability_boundary_fails_closed": _expect_output_error(
            material=material,
            output=boundary,
            code="natural_node_canary_boundary_semantics_missing",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()

    credentials = _credential_variable_names()
    _require(not credentials, "natural_node_canary_clean_worker_credentials_not_scrubbed")
    network_attempts = _block_network()

    implementation = _load_json(IMPLEMENTATION_PATH)
    implementation_body = {
        key: value for key, value in implementation.items() if key != "result_digest"
    }
    _require(
        implementation.get("result_digest") == canonical_digest(implementation_body),
        "natural_node_canary_clean_worker_implementation_digest_invalid",
    )
    policy = load_canary_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_canary_material(policy=policy, repo_root=ROOT)
    compiled = dict(material["compiled_input"])
    request = dict(material["provider_request"])
    _require(
        compiled.get("compiled_input_digest")
        == implementation["compiled_canary"]["compiled_input_digest"]
        and len(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
        == implementation["compiled_canary"]["compiled_request_characters"],
        "natural_node_canary_clean_worker_compilation_drift",
    )

    proof_root = ROOT / ".natural-node-canary-clean-worker"
    _require(not proof_root.exists(), "natural_node_canary_clean_worker_root_exists")
    ledger = SharedAdmissionConsumptionLedger(proof_root / "shared/ledger.sqlite")
    fake_calls = 0

    success_admission, success, calls = _run_fixture(
        label="success",
        material=material,
        response=_response(_valid_output()),
        proof_root=proof_root,
        ledger=ledger,
    )
    fake_calls += calls

    transport_response = {
        "status": "provider_error",
        "failure_reason": "simulated transport timeout",
        "content": "partial private provider output 123",
        "finish_reason": None,
    }
    _transport_admission, transport, calls = _run_fixture(
        label="transport",
        material=material,
        response=transport_response,
        proof_root=proof_root,
        ledger=ledger,
    )
    fake_calls += calls

    _length_admission, length, calls = _run_fixture(
        label="length",
        material=material,
        response=_response(_valid_output(), finish_reason="length"),
        proof_root=proof_root,
        ledger=ledger,
    )
    fake_calls += calls

    _json_admission, invalid_json, calls = _run_fixture(
        label="invalid-json",
        material=material,
        response=_response("not-json"),
        proof_root=proof_root,
        ledger=ledger,
    )
    fake_calls += calls

    duplicate_rejected = False
    try:
        execute_canary(
            admission=success_admission,
            material=material,
            provider_call=lambda _request: _response(_valid_output()),
            runtime_root=proof_root / "attempts/duplicate-root",
            shared_ledger=ledger,
            observed_at=OBSERVED_AT,
        )
    except SharedAdmissionLedgerError as exc:
        duplicate_rejected = exc.code.startswith("shared_admission_already_consumed")

    capture = _load_json(
        proof_root / "attempts/transport/raw_model_only/calls/call_01/capture.json"
    )
    mutations = _mutations(material)
    _require(
        success.get("status") == "completed"
        and transport.get("terminal_code")
        == "natural_node_canary_provider_failure:provider_error"
        and length.get("terminal_code")
        == "natural_node_canary_incomplete_finish_reason_length"
        and invalid_json.get("terminal_code")
        == "natural_node_canary_output_json_invalid"
        and capture.get("provider_response") == transport_response
        and duplicate_rejected
        and all(mutations.values())
        and not network_attempts,
        "natural_node_canary_clean_worker_proof_failed",
    )

    body = {
        "schema_version": WORKER_SCHEMA,
        "status": "pass",
        "implementation_commit": args.implementation_commit,
        "implementation_result_digest": implementation["result_digest"],
        "policy_digest": canonical_digest(
            {key: value for key, value in policy.items() if not key.startswith("_")}
        ),
        "compiled_canary": {
            "compiled_input_digest": compiled["compiled_input_digest"],
            "request_digest": request["request_digest"],
            "request_characters": len(
                json.dumps(request, ensure_ascii=False, separators=(",", ":"))
            ),
            "evidence_aliases": [
                row["evidence_alias"] for row in compiled["evidence"]
            ],
            "numeric_refs": [row["numeric_ref"] for row in compiled["numeric_facts"]],
            "raw_source_text_in_model_input": compiled[
                "raw_source_text_in_model_input"
            ],
        },
        "runtime_outcomes": {
            "success": success["terminal_code"],
            "transport": transport["terminal_code"],
            "length": length["terminal_code"],
            "invalid_json": invalid_json["terminal_code"],
            "full_transport_response_capture_preserved": (
                capture["provider_response"] == transport_response
            ),
            "same_admission_second_consumption_rejected": duplicate_rejected,
            "business_artifact_promotion": False,
        },
        "mutations": mutations,
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": len(network_attempts),
            "source_calls": 0,
            "retries": 0,
            "fixture_provider_invocations": fake_calls,
        },
        "credential_environment_variables_present": len(credentials),
    }
    result = {**body, "result_digest": canonical_digest(body)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result) + b"\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "fixture_provider_invocations": fake_calls,
                "network_calls": len(network_attempts),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
