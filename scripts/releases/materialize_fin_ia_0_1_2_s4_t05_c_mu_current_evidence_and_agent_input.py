from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (  # noqa: E402
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (  # noqa: E402
    compile_current_case_evidence_pack,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_b_current_product_identity import (  # noqa: E402
    compile_current_product_case_identity,
    compile_t05_b_current_product_agent_input,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (  # noqa: E402
    compile_legacy_oracle_agent_input,
    validate_transfer_evidence_pack,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


CASE_KEY = "MU"
LIVE_RESULT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_search_exact_live_"
    "result_and_acceptance_v1_0.json"
)
EVIDENCE_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_evidence_pack_v1_0.json"
)
AGENT_INPUT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_agent_exact_input_v1_0.json"
)
MATERIALIZATION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_evidence_and_agent_"
    "exact_input_zero_call_materialization_v1_0.json"
)
EXPECTED_GAPS = {
    "current_issuer_evidence_does_not_prove_future_demand_sustainability",
    "company_total_numeric_does_not_attribute_AI_segment_profit_capture",
    "issuer_counterevidence_is_not_independent_external_corroboration",
}


class T05CMUMaterializationError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05CMUMaterializationError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_c_mu_materialization_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_atomic(path: Path, value: Mapping[str, Any]) -> str:
    raw = _canonical_bytes(value)
    if path.exists():
        _require(path.read_bytes() == raw, f"s4_t05_c_mu_existing_output_mismatch:{path.name}")
        return "exact_existing_reused"
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return "created"


def load_and_validate_terminal(live_result_path: Path) -> tuple[dict[str, Any], str, Path]:
    live = _load(live_result_path)
    terminal_ref = ROOT / str(live["terminal"]["runtime_object_ref"])
    terminal = _load(terminal_ref)
    digest = str(live["terminal"]["digest"])
    _require(
        live.get("status")
        == "pass_live_current_evidence_candidate_pack_ready_agent_input_compilation_next"
        and terminal.get("case_key") == CASE_KEY
        and terminal.get("status") == "success"
        and terminal.get("code") == "three_request_current_evidence_candidate_pack_ready"
        and terminal.get("T04_consumption_authorized") is True
        and terminal.get("writer_citable_in_T03") is False
        and terminal.get("domain_judgment_eligible_in_T03") is False
        and _sha256(terminal_ref) == digest,
        "s4_t05_c_mu_search_terminal_binding_invalid",
    )
    observed = terminal["observed_counts"]
    _require(
        observed["live_source_network_calls"] in {1, 2}
        and observed["local_retrieval_or_tool_invocations"] == 6
        and observed["model_calls"] == observed["provider_calls"] == 0
        and observed["accepted_candidates"] == 18
        and observed["business_artifacts"] == 0,
        "s4_t05_c_mu_search_terminal_counts_invalid",
    )
    runtime_objects = terminal_ref.parents[4]
    capture_keys: set[str] = set()
    for capture in terminal["capture_objects"]:
        path = runtime_objects / capture["object_key"]
        _require(
            path.is_file() and _sha256(path) == capture["digest"],
            "s4_t05_c_mu_capture_content_address_invalid",
        )
        capture_keys.add(str(capture["object_key"]))
    _require(len(capture_keys) in {8, 10}, "s4_t05_c_mu_capture_cardinality_invalid")
    for request in terminal["request_results"]:
        for candidate in request["accepted_candidates"]:
            _require(
                candidate["entity_ref"] == CASE_KEY
                and candidate["source_snapshot_ref"] in capture_keys,
                "s4_t05_c_mu_candidate_identity_or_capture_invalid",
            )
    return terminal, digest, terminal_ref


def compile_outputs(terminal: Mapping[str, Any], *, terminal_digest: str) -> tuple[dict[str, Any], dict[str, Any]]:
    entry = load_current_fin_0_1_2_s4_t01_case_entry(CASE_KEY)
    pack = validate_transfer_evidence_pack(
        compile_current_case_evidence_pack(
            terminal,
            terminal_digest=terminal_digest,
            t01_entry=entry,
            case_key=CASE_KEY,
        ),
        case_key=CASE_KEY,
    )
    coverage = Counter(
        (row["program_cell_ids"][0], row["evidence_role"])
        for row in pack["evidence_rows"]
    )
    _require(
        len(pack["evidence_rows"]) == 15
        and len(pack["numeric_rows"]) == 3
        and len(pack["typed_gaps"]) == 3
        and coverage
        == Counter(
            {
                ("demand_authenticity_and_sustainability", "issuer_demand_or_order_signal"): 6,
                ("value_and_profit_capture", "issuer_financial_statement"): 3,
                ("bottleneck_counterevidence_and_what_would_change", "issuer_counterevidence"): 6,
            }
        )
        and {row["gap_code"] for row in pack["typed_gaps"]} == EXPECTED_GAPS
        and {row["metric_family"] for row in pack["numeric_rows"]}
        == {"revenue", "gross_profit", "operating_income"},
        "s4_t05_c_mu_evidence_gate_shape_invalid",
    )
    baseline = compile_legacy_oracle_agent_input(CASE_KEY, repository_root=ROOT)
    agent = compile_t05_b_current_product_agent_input(baseline, pack, case_key=CASE_KEY)
    agent_input = agent.model_dump(mode="json")
    expected_case = compile_current_product_case_identity(
        CASE_KEY,
        t01_entry_digest=entry.receipt.entry_digest,
        evidence_pack_digest=pack["evidence_pack_digest"],
    )
    _require(
        agent_input["company"] == CASE_KEY
        and agent_input["case_id"] == expected_case
        and "oracle" not in agent_input["case_id"]
        and agent_input["input_digest"]
        == canonical_digest({k: v for k, v in agent_input.items() if k != "input_digest"})
        and agent_input["lineage"]["S4_T04_source_grounded_input"]["digest"]
        == pack["evidence_pack_digest"],
        "s4_t05_c_mu_agent_input_identity_or_lineage_invalid",
    )
    return pack, agent_input


def build_materialization(*, recorded_at: str, live_result_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    terminal, digest, terminal_ref = load_and_validate_terminal(live_result_path)
    pack, agent_input = compile_outputs(terminal, terminal_digest=digest)
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_c_mu_current_evidence_and_agent_exact_input_zero_call_materialization_v1_0",
        "result_id": "FIN-0.1.2-S4-T05-C-MU-CURRENT-EVIDENCE-AND-AGENT-EXACT-INPUT",
        "recorded_at": recorded_at,
        "status": "pass_compiled_current_evidence_and_agent_exact_input",
        "source_execution_binding": {
            "search_result_ref": live_result_path.relative_to(ROOT).as_posix(),
            "search_result_sha256": _sha256(live_result_path),
            "terminal_runtime_ref": terminal_ref.relative_to(ROOT).as_posix(),
            "terminal_digest": digest,
            "run_id": terminal["run_id"],
            "attempt_id": terminal["attempt_id"],
            "second_search_or_replay_performed": False,
        },
        "compiled_outputs": {
            "evidence_pack_ref": EVIDENCE_PACK_REF.as_posix(),
            "evidence_pack_sha256": hashlib.sha256(_canonical_bytes(pack)).hexdigest(),
            "evidence_pack_digest": pack["evidence_pack_digest"],
            "agent_exact_input_ref": AGENT_INPUT_REF.as_posix(),
            "agent_exact_input_sha256": hashlib.sha256(_canonical_bytes(agent_input)).hexdigest(),
            "agent_input_digest": agent_input["input_digest"],
            "current_case_id": agent_input["case_id"],
        },
        "evidence_gate": {
            "accepted_candidates": 18,
            "writer_citable_evidence": 15,
            "exact_numeric_authority": 3,
            "typed_gaps": 3,
            "evidence_by_cell": {"demand": 6, "value_and_profit": 3, "bottleneck": 6},
            "rejected_candidate_promoted": False,
            "model_generated_evidence": False,
            "cross_case_fact_reuse": False,
        },
        "known_quality_boundary": {
            "generic_AI_segment_gap_code_used_for_MU_HBM_scope": True,
            "classification": "L2_L4_wording_not_L1_authority_failure",
            "disposition": "preserve_typed_gap_and_review_in_T08_T10_S5_not_block_T05_C",
        },
        "observed_new_counts": {
            "source_network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "business_artifacts": 0,
        },
        "next_action": "FIN-0.1.2-S4-T05-C-MU-AGENT-FRESH-PROOF-CAPACITY-ADMISSION-AND-ONE-EXACT-LIVE",
    }
    return pack, agent_input, {**body, "materialization_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--live-result", type=Path, default=ROOT / LIVE_RESULT_REF)
    parser.add_argument("--evidence-output", type=Path, default=ROOT / EVIDENCE_PACK_REF)
    parser.add_argument("--agent-input-output", type=Path, default=ROOT / AGENT_INPUT_REF)
    parser.add_argument("--result-output", type=Path, default=ROOT / MATERIALIZATION_REF)
    args = parser.parse_args()
    pack, agent_input, result = build_materialization(
        recorded_at=args.recorded_at, live_result_path=args.live_result.resolve()
    )
    statuses = {
        "evidence_pack": _write_atomic(args.evidence_output.resolve(), pack),
        "agent_input": _write_atomic(args.agent_input_output.resolve(), agent_input),
        "result": _write_atomic(args.result_output.resolve(), result),
    }
    print(json.dumps({
        "status": result["status"],
        "write_statuses": statuses,
        "evidence_pack_digest": pack["evidence_pack_digest"],
        "agent_input_digest": agent_input["input_digest"],
        "evidence_numeric_gap_counts": [len(pack["evidence_rows"]), len(pack["numeric_rows"]), len(pack["typed_gaps"])],
        "next_action": result["next_action"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
