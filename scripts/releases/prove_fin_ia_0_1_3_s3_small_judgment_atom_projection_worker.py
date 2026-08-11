from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s2_selected_evidence_numeric_cocompilation import (  # noqa: E402
    canonical_bytes,
)
from sec_agent.s3_dell_value_profit_repair_canary import (  # noqa: E402
    compile_repair_canary_material,
    execute_fixture_repair_canary,
    issue_fixture_admission,
    load_repair_canary_policy,
)
from sec_agent.s3_small_judgment_atom_projection import (  # noqa: E402
    S3SmallJudgmentAtomProjectionError,
    audit_failed_legacy_output,
    compile_portfolio_shape_receipts,
    compile_small_judgment_material,
    load_small_judgment_projection_policy,
    project_small_judgment_output,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_policy_v1_0.json"
)
IMPLEMENTATION_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_minimum_zero_call_"
    "implementation_v1_0.json"
)
LEGACY_CAPTURE_PATH = ROOT / (
    "data/workbench_private/fin_0_1_3_s3_dell_value_profit_repair_canary/"
    "live/attempts/fin013_s3_dell_value_profit_repair_canary_"
    "11a8bc7aa03045f7803a/raw_model_only/calls/call_01/capture.json"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s3_small_judgment_atom_projection_clean_worker_result_v1_0"
)
OBSERVED_AT = "2026-08-11T15:00:00Z"


class CleanWorkerError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CleanWorkerError(code)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanWorkerError(f"clean_worker_json_invalid:{path.name}") from exc
    _require(isinstance(value, dict), "clean_worker_json_object_required")
    return value


def _credential_names() -> list[str]:
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
        raise RuntimeError("s3_small_atom_clean_worker_network_forbidden")

    socket.socket.connect = blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked  # type: ignore[method-assign]
    socket.create_connection = blocked
    return attempts


def _valid_output() -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_0_1_3_s3_small_judgment_atom_output_v1_0",
        "case_key": "DELL",
        "node_id": "dell_value_profit_small_judgment_atom_v1",
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
        "used_numeric_refs": [
            "NUM:DELL:OPERATING_MARGIN_TARGET:2894219F450D"
        ],
        "profitability_direction": (
            "management_target_consistent_product_profit_unproven"
        ),
        "attribution_boundary": "segment_profit_not_product_profit",
        "mechanism_atom": (
            "E021 supports bounded operating profitability while E008 limits "
            "transmission to product profit."
        ),
        "boundary_atom": (
            "E002 prevents segment income from replacing product profit; cash "
            "conversion remains open."
        ),
    }


def _expect_error(
    *, material: Mapping[str, Any], output: Mapping[str, Any], code: str
) -> bool:
    try:
        project_small_judgment_output(
            output=output,
            material=material,
            capture_ref="fixture://clean-worker/mutation",
            capture_digest="d" * 64,
        )
    except S3SmallJudgmentAtomProjectionError as exc:
        return exc.code == code
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()

    credentials = _credential_names()
    _require(not credentials, "s3_small_atom_clean_worker_credentials_not_scrubbed")
    network_attempts = _block_network()

    implementation = _load(IMPLEMENTATION_PATH)
    implementation_body = {
        key: value for key, value in implementation.items() if key != "result_digest"
    }
    _require(
        implementation.get("result_digest") == canonical_digest(implementation_body),
        "s3_small_atom_clean_worker_implementation_digest_invalid",
    )
    policy = load_small_judgment_projection_policy(POLICY_PATH, repo_root=ROOT)
    material = compile_small_judgment_material(policy=policy, repo_root=ROOT)
    output = _valid_output()
    projected = project_small_judgment_output(
        output=output,
        material=material,
        capture_ref="fixture://clean-worker/small-output",
        capture_digest="c" * 64,
    )

    numeric = deepcopy(output)
    numeric["mechanism_atom"] = "Profitability reached a mid-single-digit band."
    wrong_direction = deepcopy(output)
    wrong_direction["profitability_direction"] = "cannot_infer"
    state_surface = deepcopy(output)
    state_surface["judgment_state"] = "supported_with_limits"
    cross_case = deepcopy(output)
    cross_case["case_key"] = "MU"
    mutations = {
        "model_cell_state_surface_rejected": _expect_error(
            material=material,
            output=state_surface,
            code="s3_small_atom_output_fields_invalid",
        ),
        "financial_numeric_surface_rejected": _expect_error(
            material=material,
            output=numeric,
            code="s3_small_atom_financial_numeric_surface_forbidden",
        ),
        "wrong_profitability_direction_rejected": _expect_error(
            material=material,
            output=wrong_direction,
            code="s3_small_atom_financial_boundary_invalid",
        ),
        "cross_case_identity_rejected": _expect_error(
            material=material,
            output=cross_case,
            code="s3_small_atom_output_identity_invalid",
        ),
    }

    legacy_capture = _load(LEGACY_CAPTURE_PATH)
    legacy_response = dict(legacy_capture["provider_response"])
    legacy_output = json.loads(str(legacy_response["content"]))
    legacy_audit = audit_failed_legacy_output(legacy_output)

    predecessor_policy_path = ROOT / policy["immutable_bindings"][
        "predecessor_canary_policy"
    ]["ref"]
    predecessor_policy = load_repair_canary_policy(
        predecessor_policy_path, repo_root=ROOT
    )
    predecessor_material = compile_repair_canary_material(
        policy=predecessor_policy, repo_root=ROOT
    )
    replay_root = ROOT / ".s3-small-atom-clean-replay"
    _require(not replay_root.exists(), "s3_small_atom_clean_replay_root_exists")
    admission = issue_fixture_admission(
        material=predecessor_material,
        run_id="clean-legacy-capture-replay",
        attempt_id="clean-legacy-capture-replay-attempt",
        observed_at=OBSERVED_AT,
    )
    callback_count = 0

    def replay_provider(_request: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal callback_count
        callback_count += 1
        return legacy_response

    terminal = execute_fixture_repair_canary(
        admission=admission,
        material=predecessor_material,
        provider_call=replay_provider,
        runtime_root=replay_root / "attempt",
        shared_ledger=SharedAdmissionConsumptionLedger(replay_root / "ledger.sqlite"),
        observed_at=OBSERVED_AT,
    )
    terminal_materialization = {
        "terminal_code": terminal["terminal_code"],
        "parsed_output_ref": terminal["parsed_output_ref"],
        "parsed_output_exists": (
            replay_root / "attempt/parsed/repair_output.json"
        ).is_file(),
        "validated_output_ref": terminal["validated_output_ref"],
        "validated_output_exists": (
            replay_root / "attempt/validated/repair_output.json"
        ).exists(),
        "raw_capture_exists": (
            replay_root / "attempt/raw_model_only/calls/call_01/capture.json"
        ).is_file(),
        "business_artifact_promotion": terminal["business_artifact_promotion"],
    }
    shutil.rmtree(replay_root)
    terminal_materialization["temporary_replay_root_removed"] = (
        not replay_root.exists()
    )
    portfolio = compile_portfolio_shape_receipts(policy)
    _require(
        projected["status"] == "pass"
        and len(projected["readjudication_receipt_digests"]) == 4
        and projected["deterministic_cell_rows"][1]["judgment_state"]
        == "cannot_infer"
        and projected["deterministic_cell_rows"][1]["judgment_changed"] is False
        and projected["validation"]["normalized_atoms"]["mechanism_atom"][
            "removed_alias_tokens"
        ]
        == ["E021", "E008"]
        and all(mutations.values())
        and legacy_audit["target_changed_flag_valid"] is False
        and legacy_audit["price_in_boundary_valid"] is False
        and legacy_audit["failed_output_promotable"] is False
        and terminal_materialization["parsed_output_exists"] is True
        and terminal_materialization["validated_output_ref"] is None
        and terminal_materialization["validated_output_exists"] is False
        and terminal_materialization["raw_capture_exists"] is True
        and terminal_materialization["temporary_replay_root_removed"] is True
        and len(portfolio) == 3
        and callback_count == 1
        and not network_attempts,
        "s3_small_atom_clean_worker_proof_failed",
    )

    body = {
        "schema_version": WORKER_SCHEMA,
        "status": "pass",
        "implementation_commit": args.implementation_commit,
        "implementation_result_digest": implementation["result_digest"],
        "compiled_input_digest": material["compiled_input"]["compiled_input_digest"],
        "request_digest": material["provider_request"]["request_digest"],
        "compiled_request_characters": material["compiled_request_characters"],
        "projection_digest": projected["projection_digest"],
        "successor_program_digest": projected["successor_program_digest"],
        "deterministic_cell_states": {
            row["cell_id"]: [row["judgment_state"], row["judgment_changed"]]
            for row in projected["deterministic_cell_rows"]
        },
        "alias_normalization": projected["validation"]["normalized_atoms"],
        "legacy_capture_audit": legacy_audit,
        "legacy_terminal_materialization": terminal_materialization,
        "portfolio_shape_receipts": portfolio,
        "mutations": mutations,
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": len(network_attempts),
            "source_calls": 0,
            "retries": 0,
            "fixture_capture_replay_callbacks": callback_count,
        },
        "credential_environment_variables_present": len(credentials),
        "business_artifact_promotion": False,
    }
    result = {**body, "result_digest": canonical_digest(body)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(result) + b"\n")
    print(
        json.dumps(
            {
                "status": "pass",
                "result_digest": result["result_digest"],
                "request_characters": result["compiled_request_characters"],
                "external_calls": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
