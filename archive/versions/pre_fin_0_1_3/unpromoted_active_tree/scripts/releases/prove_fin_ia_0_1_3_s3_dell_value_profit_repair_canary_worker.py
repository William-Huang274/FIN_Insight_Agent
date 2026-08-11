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
from sec_agent.s3_dell_value_profit_repair_canary import (  # noqa: E402
    S3DellValueProfitRepairCanaryError,
    adjudicate_repair_canary_output,
    compile_repair_canary_material,
    execute_fixture_repair_canary,
    issue_fixture_admission,
    load_repair_canary_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
    "repair_canary_policy_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "minimum_zero_call_implementation_v1_0.json"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s3_dell_value_profit_current_pack_repair_canary_"
    "clean_worker_result_v1_0"
)
OBSERVED_AT = "2026-08-11T13:00:00Z"


class S3RepairCanaryCleanWorkerError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3RepairCanaryCleanWorkerError(code)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S3RepairCanaryCleanWorkerError(
            f"s3_repair_canary_clean_worker_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), "s3_repair_canary_clean_worker_json_not_object")
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
        raise RuntimeError("s3_repair_canary_clean_worker_network_forbidden")

    socket.socket.connect = blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked  # type: ignore[method-assign]
    socket.create_connection = blocked
    return attempts


def _row(
    cell_id: str,
    *,
    state: str,
    changed: bool,
    support: list[str],
    counter: list[str] | None = None,
    numeric: list[str] | None = None,
    mechanism: str,
    boundary: str,
    wwc: str = "",
) -> dict[str, Any]:
    return {
        "cell_id": cell_id,
        "judgment_state": state,
        "judgment_changed": changed,
        "support_refs": support,
        "counterevidence_refs": counter or [],
        "numeric_refs": numeric or [],
        "mechanism_atom": mechanism,
        "boundary_atom": boundary,
        "wwc_ref": wwc,
    }


def _valid_output() -> dict[str, Any]:
    required_num = "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
    return {
        "schema_version": (
            "fin_ia_0_1_3_s3_dell_value_profit_current_pack_"
            "repair_canary_output_v1_0"
        ),
        "case_key": "DELL",
        "node_id": "dell_value_profit_current_pack_repair_adjudicator_v1",
        "repair_request_id": "evidence_request_0eb73a1c4b81a05d96b7",
        "observation_outcome": "accepted",
        "repair_resolution": "accepted_partial_resolution",
        "accepted_evidence_refs": ["E021"],
        "boundary_evidence_refs": ["E002", "E008", "E023"],
        "evidence_semantics": {
            "e021_evidence_role": "issuer_direct_source",
            "operating_profitability_status": (
                "issuer_management_observed_in_line_with_target"
            ),
            "isg_profit_attribution_status": "forbidden_substitution",
            "gross_margin_status": "typed_gap",
            "cash_conversion_status": "typed_gap",
            "audited_product_profit_bridge_status": "typed_gap",
        },
        "retained_gap_components": [
            "audited_product_profit_bridge",
            "cash_conversion",
            "gross_margin",
        ],
        "affected_cell_readjudications": [
            _row(
                "bottleneck_counterevidence_and_what_would_change",
                state="supported_with_limits",
                changed=True,
                support=["E021"],
                mechanism=(
                    "Issuer profitability commentary narrows the monitoring "
                    "question to explicit product or segment attribution."
                ),
                boundary=(
                    "The observation does not establish audited product profit, "
                    "gross margin or cash conversion."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
            _row(
                "cross_chain_price_in_and_expectations",
                state="cannot_infer",
                changed=False,
                support=["E002"],
                mechanism=(
                    "Segment financial context does not establish how the market "
                    "prices the product economics."
                ),
                boundary=(
                    "No valuation or expectations conclusion follows from this "
                    "profitability evidence."
                ),
            ),
            _row(
                "value_and_profit_capture",
                state="supported_with_limits",
                changed=True,
                support=["E021"],
                counter=["E002", "E008"],
                numeric=[required_num],
                mechanism=(
                    "Issuer commentary supports bounded AI server operating "
                    "profitability while mix evidence limits the transmission from "
                    "revenue scale to profit."
                ),
                boundary=(
                    "Segment operating income cannot be substituted for product "
                    "profit, and product gross margin and cash conversion remain open."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
            _row(
                "writer_admission_boundary",
                state="supported_with_limits",
                changed=True,
                support=["E021", "E002"],
                mechanism=(
                    "The report may state the bounded issuer profitability "
                    "comparison and must keep the segment bridge separate."
                ),
                boundary=(
                    "The report cannot present audited product profit, gross margin, "
                    "cash conversion, valuation or a recommendation."
                ),
                wwc="DELL_W_AI_MARGIN",
            ),
        ],
        "used_numeric_refs": [required_num],
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
        "usage": {"input_tokens": 1200, "output_tokens": 320, "total_tokens": 1520},
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

    terminal = execute_fixture_repair_canary(
        admission=admission,
        material=material,
        provider_call=provider,
        runtime_root=proof_root / "attempts" / label,
        shared_ledger=ledger,
        observed_at=OBSERVED_AT,
    )
    return admission, terminal, len(calls)


def _expect_error(
    *, material: Mapping[str, Any], output: Mapping[str, Any], code: str
) -> bool:
    try:
        adjudicate_repair_canary_output(
            output=output,
            material=material,
            capture_ref="fixture://clean-worker/mutation",
            capture_digest="a" * 64,
        )
    except S3DellValueProfitRepairCanaryError as exc:
        return exc.code == code
    return False


def _mutations(material: Mapping[str, Any]) -> dict[str, bool]:
    valid = _valid_output()

    wrong_acceptance = deepcopy(valid)
    wrong_acceptance["accepted_evidence_refs"] = ["E002"]

    segment_proxy = deepcopy(valid)
    segment_proxy["evidence_semantics"]["isg_profit_attribution_status"] = (
        "allowed_product_profit_proxy"
    )

    dropped_gap = deepcopy(valid)
    dropped_gap["retained_gap_components"].remove("cash_conversion")

    incomplete_scope = deepcopy(valid)
    incomplete_scope["affected_cell_readjudications"].pop()

    numeric_surface = deepcopy(valid)
    numeric_surface["affected_cell_readjudications"][2]["mechanism_atom"] = (
        "Product margin was five percent."
    )

    price_in = deepcopy(valid)
    price_in["affected_cell_readjudications"][1].update(
        {
            "judgment_state": "supported_with_limits",
            "judgment_changed": True,
            "support_refs": ["E021"],
        }
    )

    return {
        "valid_partial_resolution_passes": (
            adjudicate_repair_canary_output(
                output=valid,
                material=material,
                capture_ref="fixture://clean-worker/pass",
                capture_digest="b" * 64,
            )["validation"]["status"]
            == "pass"
        ),
        "segment_evidence_cannot_replace_product_profit": _expect_error(
            material=material,
            output=wrong_acceptance,
            code="s3_repair_canary_evidence_or_gap_set_invalid",
        ),
        "isg_proxy_fails_closed": _expect_error(
            material=material,
            output=segment_proxy,
            code="s3_repair_canary_evidence_semantics_invalid",
        ),
        "cash_gap_cannot_be_dropped": _expect_error(
            material=material,
            output=dropped_gap,
            code="s3_repair_canary_evidence_or_gap_set_invalid",
        ),
        "affected_cell_scope_must_be_complete": _expect_error(
            material=material,
            output=incomplete_scope,
            code="s3_repair_canary_readjudication_coverage_invalid",
        ),
        "model_numeric_surface_fails_closed": _expect_error(
            material=material,
            output=numeric_surface,
            code="s3_repair_canary_model_numeric_surface_forbidden",
        ),
        "valuation_expectations_cell_cannot_be_falsely_reopened": _expect_error(
            material=material,
            output=price_in,
            code="s3_repair_canary_price_in_boundary_invalid",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()

    credentials = _credential_variable_names()
    _require(not credentials, "s3_repair_canary_clean_worker_credentials_not_scrubbed")
    network_attempts = _block_network()

    implementation = _load_json(IMPLEMENTATION_PATH)
    implementation_body = {
        key: value for key, value in implementation.items() if key != "result_digest"
    }
    _require(
        implementation.get("result_digest") == canonical_digest(implementation_body),
        "s3_repair_canary_clean_worker_implementation_digest_invalid",
    )
    policy = load_repair_canary_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_repair_canary_material(policy=policy, repo_root=ROOT)
    compiled = dict(material["compiled_input"])
    request = dict(material["provider_request"])
    request_characters = len(
        json.dumps(request, ensure_ascii=False, separators=(",", ":"))
    )
    _require(
        compiled.get("compiled_input_digest")
        == implementation["compiled_canary"]["compiled_input_digest"]
        and request.get("request_digest")
        == implementation["compiled_canary"]["request_digest"]
        and request_characters
        == implementation["compiled_canary"]["compiled_request_characters"],
        "s3_repair_canary_clean_worker_compilation_drift",
    )

    proof_root = ROOT / ".s3-repair-canary-clean-worker"
    _require(not proof_root.exists(), "s3_repair_canary_clean_worker_root_exists")
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
        "content": "partial private provider output",
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

    invalid_semantics_output = deepcopy(_valid_output())
    invalid_semantics_output["evidence_semantics"][
        "isg_profit_attribution_status"
    ] = "allowed_product_profit_proxy"
    _semantic_admission, invalid_semantics, calls = _run_fixture(
        label="invalid-semantics",
        material=material,
        response=_response(invalid_semantics_output),
        proof_root=proof_root,
        ledger=ledger,
    )
    fake_calls += calls

    duplicate_rejected = False
    try:
        execute_fixture_repair_canary(
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
        success.get("terminal_code") == "s3_repair_canary_pass"
        and transport.get("terminal_code")
        == "s3_repair_canary_provider_failure:provider_error"
        and length.get("terminal_code")
        == "s3_repair_canary_incomplete_finish_reason_length"
        and invalid_json.get("terminal_code") == "s3_repair_canary_invalid_json"
        and invalid_semantics.get("terminal_code")
        == "s3_repair_canary_evidence_semantics_invalid"
        and capture.get("provider_response") == transport_response
        and duplicate_rejected
        and all(mutations.values())
        and not network_attempts,
        "s3_repair_canary_clean_worker_proof_failed",
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
            "request_characters": request_characters,
            "evidence_aliases": [
                row["evidence_alias"] for row in compiled["current_pack_evidence"]
            ],
            "numeric_refs": [row["numeric_ref"] for row in compiled["numeric_facts"]],
            "affected_cell_ids": compiled["authoritative_affected_cell_ids"],
            "raw_source_text_in_model_input": compiled[
                "raw_source_text_in_model_input"
            ],
        },
        "runtime_outcomes": {
            "success": success["terminal_code"],
            "transport": transport["terminal_code"],
            "length": length["terminal_code"],
            "invalid_json": invalid_json["terminal_code"],
            "invalid_semantics": invalid_semantics["terminal_code"],
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
