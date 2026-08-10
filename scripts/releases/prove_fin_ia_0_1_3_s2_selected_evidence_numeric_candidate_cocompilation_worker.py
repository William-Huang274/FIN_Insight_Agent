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
    SelectedEvidenceNumericCocompilationError,
    canonical_bytes,
    canonical_digest,
    compile_numeric_cocompilation_successor_input,
    compile_selected_evidence_numeric_cocompilation,
    evaluate_delivery_numeric_authority,
    load_numeric_cocompilation_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_policy_v1_0.json"
)
IMPLEMENTATION_RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_minimum_zero_call_implementation_v1_0.json"
)
INPUT_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_proof_input_v1_0"
)
WORKER_SCHEMA = (
    "fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_"
    "cocompilation_clean_worker_result_v1_0"
)
CASES = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")


class SelectedEvidenceNumericCocompilationWorkerError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SelectedEvidenceNumericCocompilationWorkerError(code)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectedEvidenceNumericCocompilationWorkerError(
            f"clean_worker_json_invalid:{path.name}"
        ) from exc
    _require(isinstance(value, dict), f"clean_worker_json_not_object:{path.name}")
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
        raise RuntimeError("clean_worker_network_forbidden")

    socket.socket.connect = blocked  # type: ignore[method-assign]
    socket.socket.connect_ex = blocked  # type: ignore[method-assign]
    socket.create_connection = blocked
    return attempts


def _expect_error(callable_object: object, code: str) -> bool:
    try:
        callable_object()  # type: ignore[operator]
    except SelectedEvidenceNumericCocompilationError as exc:
        return exc.code == code
    return False


def _summary(pack: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    candidates = list(result["candidate_inventory"]["candidates"])
    statuses: dict[str, int] = {}
    for row in candidates:
        status = str(row["adjudication_status"])
        statuses[status] = statuses.get(status, 0) + 1
    program = result["presentation_program"]
    program_summary = program["summary"]
    capacity = result["node_views"]["capacity_receipt"]
    return {
        "source_pack_digest": str(pack["pack_payload_digest"]),
        "result_digest": str(result["result_digest"]),
        "transaction_digest": str(result["co_compilation_transaction_digest"]),
        "candidates": len(candidates),
        "authorized": statuses.get("authorized_fact", 0)
        + statuses.get("authorized_formula_operand", 0),
        "context_only": statuses.get("context_only_do_not_output", 0),
        "forbidden": statuses.get("forbidden_or_ambiguous", 0),
        "ambiguity_downgraded": int(
            result["candidate_inventory"]["summary"]["ambiguity_downgraded_count"]
        ),
        "stable_facts": int(program_summary["stable_fact_count"]),
        "presentation_receipts": int(program_summary["presentation_receipt_count"]),
        "formula_traces": int(program_summary["formula_trace_count"]),
        "conflicts": int(program_summary["conflict_count"]),
        "view_chars": [
            int(capacity["view_char_counts"][key])
            for key in ("research_view", "writer_view", "verifier_view")
        ],
    }


def _metric_fact(result: Mapping[str, Any], metric: str) -> dict[str, Any]:
    rows = [
        row
        for row in result["presentation_program"]["stable_numeric_facts"]
        if row["semantic_metric_key"] == metric
    ]
    _require(len(rows) == 1, f"clean_worker_metric_fact_not_unique:{metric}")
    return dict(rows[0])


def _mutations(
    *,
    policy: Mapping[str, Any],
    packs: Mapping[str, Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
) -> dict[str, bool]:
    dell_pack = packs["DELL"]
    dell_result = results["DELL"]

    reordered = deepcopy(dell_pack)
    reordered["evidence_items"].reverse()
    reordered["source_materials"].reverse()
    reordered_result = compile_selected_evidence_numeric_cocompilation(
        pack=reordered,
        policy=policy,
    )

    cross_case = deepcopy(dell_pack)
    cross_case["evidence_items"][0]["case_key"] = "MU"

    missing_parent = deepcopy(packs["ORCL"])
    structured = next(
        row for row in missing_parent["evidence_items"] if row.get("structured_metric")
    )
    structured["structured_metric"].pop("table_path", None)

    total_revenue = _metric_fact(dell_result, "total_revenue")
    rendered = str(total_revenue["presentation_receipts"][0]["rendered"])
    good = evaluate_delivery_numeric_authority(
        delivery_text=f"本季净收入为 {rendered}。",
        used_numeric_refs=[str(total_revenue["numeric_ref"])],
        used_formula_refs=[],
        inventory=dell_result["candidate_inventory"],
        presentation_program=dell_result["presentation_program"],
        semantic_verifier_pass=True,
    )
    context_only = evaluate_delivery_numeric_authority(
        delivery_text="错误输出 $4.1 billion。",
        used_numeric_refs=[str(total_revenue["numeric_ref"])],
        used_formula_refs=[],
        inventory=dell_result["candidate_inventory"],
        presentation_program=dell_result["presentation_program"],
        semantic_verifier_pass=True,
    )
    unit_mutation = evaluate_delivery_numeric_authority(
        delivery_text="错误输出 $43,842 million。",
        used_numeric_refs=[str(total_revenue["numeric_ref"])],
        used_formula_refs=[],
        inventory=dell_result["candidate_inventory"],
        presentation_program=dell_result["presentation_program"],
        semantic_verifier_pass=True,
    )
    market_close = _metric_fact(dell_result, "raw_daily_close")
    target_price = evaluate_delivery_numeric_authority(
        delivery_text="目标价 $437.65。",
        used_numeric_refs=[str(market_close["numeric_ref"])],
        used_formula_refs=[],
        inventory=dell_result["candidate_inventory"],
        presentation_program=dell_result["presentation_program"],
        semantic_verifier_pass=True,
    )
    return {
        "candidate_order_is_digest_stable": (
            reordered_result["result_digest"] == dell_result["result_digest"]
            and reordered_result["co_compilation_transaction_digest"]
            == dell_result["co_compilation_transaction_digest"]
        ),
        "cross_case_identity_fails_closed": _expect_error(
            lambda: compile_selected_evidence_numeric_cocompilation(
                pack=cross_case,
                policy=policy,
            ),
            "numeric_cocompilation_selected_evidence_identity_invalid",
        ),
        "missing_structured_parent_fails_closed": _expect_error(
            lambda: compile_selected_evidence_numeric_cocompilation(
                pack=missing_parent,
                policy=policy,
            ),
            "numeric_cocompilation_structured_metric_authority_invalid",
        ),
        "bound_presentation_passes_local_guard": good["status"] == "pass",
        "context_only_surface_hard_fails_after_semantic_pass": (
            context_only["status"] == "hard_fail"
            and context_only["semantic_verifier_overrode_local_gate"] is False
        ),
        "unit_mutation_hard_fails_after_semantic_pass": (
            unit_mutation["status"] == "hard_fail"
            and unit_mutation["semantic_verifier_overrode_local_gate"] is False
        ),
        "pit_close_cannot_authorize_target_price": target_price["status"]
        == "hard_fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()

    credential_names = _credential_variable_names()
    _require(not credential_names, "clean_worker_credential_environment_not_scrubbed")
    network_attempts = _block_network()

    bundle = _load_json(args.input)
    _require(bundle.get("schema_version") == INPUT_SCHEMA, "clean_worker_input_schema_invalid")
    _require(bundle.get("case_order") == list(CASES), "clean_worker_case_order_invalid")
    _require(
        bundle.get("bundle_digest")
        == canonical_digest({key: value for key, value in bundle.items() if key != "bundle_digest"}),
        "clean_worker_input_digest_invalid",
    )
    packs = dict(bundle["packs"])
    _require(set(packs) == set(CASES), "clean_worker_case_set_invalid")

    policy = load_numeric_cocompilation_policy(POLICY_PATH)
    implementation_result = _load_json(IMPLEMENTATION_RESULT_PATH)
    expected_matrix = dict(implementation_result["case_matrix"])
    results = {
        case_key: compile_selected_evidence_numeric_cocompilation(
            pack=packs[case_key],
            policy=policy,
        )
        for case_key in CASES
    }
    summaries = {
        case_key: _summary(packs[case_key], results[case_key])
        for case_key in CASES
    }
    _require(summaries == expected_matrix, "clean_worker_case_matrix_drift")
    _require(
        all(
            result["model_calls"] == 0
            and result["provider_calls"] == 0
            and result["network_calls"] == 0
            and result["source_calls"] == 0
            for result in results.values()
        ),
        "clean_worker_nonzero_runtime_calls",
    )

    successor = compile_numeric_cocompilation_successor_input(
        base_case_input=bundle["dell_base_case_input"],
        pack=packs["DELL"],
        result=results["DELL"],
    )
    model_input_text = canonical_bytes(successor["model_input"]).decode("utf-8")
    successor_checks = {
        "raw_source_material_count": int(
            successor["private_audit_binding"]["raw_source_material_count"]
        ),
        "raw_source_content_in_model_input": bool(
            successor["private_audit_binding"][
                "raw_source_content_in_successor_model_input"
            ]
        ),
        "source_text_field_absent": '"source_text"' not in model_input_text,
        "known_raw_sentence_absent": "We booked $24.4 billion" not in model_input_text,
        "model_input_digest": canonical_digest(successor["model_input"]),
        "successor_digest": canonical_digest(successor),
    }
    _require(
        successor_checks["raw_source_material_count"] == 27
        and successor_checks["raw_source_content_in_model_input"] is False
        and successor_checks["source_text_field_absent"] is True
        and successor_checks["known_raw_sentence_absent"] is True,
        "clean_worker_successor_private_boundary_failed",
    )

    mutations = _mutations(policy=policy, packs=packs, results=results)
    _require(all(mutations.values()), "clean_worker_mutation_failed")
    _require(not network_attempts, "clean_worker_network_attempt_observed")

    body = {
        "schema_version": WORKER_SCHEMA,
        "status": "pass",
        "implementation_commit": args.implementation_commit,
        "input_bundle_digest": str(bundle["bundle_digest"]),
        "policy_digest": canonical_digest(policy),
        "implementation_result_digest": str(implementation_result["result_digest"]),
        "case_matrix": summaries,
        "successor": successor_checks,
        "mutations": mutations,
        "observed_calls": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": len(network_attempts),
            "source_calls": 0,
            "retries": 0,
        },
        "credential_environment_variables_present": len(credential_names),
    }
    output = {**body, "result_digest": canonical_digest(body)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(output) + b"\n")
    print(json.dumps({
        "status": output["status"],
        "result_digest": output["result_digest"],
        "case_count": len(summaries),
        "observed_calls": output["observed_calls"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
