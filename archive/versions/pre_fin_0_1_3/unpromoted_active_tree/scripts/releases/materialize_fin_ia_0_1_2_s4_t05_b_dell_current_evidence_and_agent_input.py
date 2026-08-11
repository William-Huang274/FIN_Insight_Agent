from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (  # noqa: E402
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (  # noqa: E402
    compile_current_case_executable_requests,
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


LIVE_RESULT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_search_"
    "exact_live_result_and_acceptance_v1_0.json"
)
EVIDENCE_PACK_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_pack_v1_0.json"
)
AGENT_INPUT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_exact_input_v1_0.json"
)
MATERIALIZATION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_current_evidence_and_"
    "agent_exact_input_zero_call_materialization_v1_0.json"
)
COMPILER_REFS = (
    Path(
        "apps/workbench/backend/application/"
        "fin_0_1_2_s4_t04_current_evidence_research.py"
    ),
    Path(
        "apps/workbench/backend/application/"
        "fin_0_1_2_s4_t05_three_case_transfer.py"
    ),
    Path(
        "apps/workbench/backend/application/"
        "fin_0_1_2_s4_t05_b_current_product_identity.py"
    ),
    Path(
        "scripts/releases/"
        "materialize_fin_ia_0_1_2_s4_t05_b_dell_current_evidence_and_"
        "agent_input.py"
    ),
)
EXPECTED_OBSERVED_COUNTS = {
    "accepted_candidates": 18,
    "business_artifacts": 0,
    "fallbacks": 0,
    "live_source_network_calls": 1,
    "local_retrieval_or_tool_invocations": 6,
    "model_calls": 0,
    "paid_api_cost_usd": 0.0,
    "provider_calls": 0,
    "rejected_candidates": 12,
    "same_target_retries": 0,
    "source_calls": 1,
}
EXPECTED_GAPS = {
    (
        "demand_authenticity_and_sustainability",
        "current_issuer_evidence_does_not_prove_future_demand_sustainability",
    ),
    (
        "value_and_profit_capture",
        "company_total_numeric_does_not_attribute_AI_segment_profit_capture",
    ),
    (
        "bottleneck_counterevidence_and_what_would_change",
        "issuer_counterevidence_is_not_independent_external_corroboration",
    ),
}
EXPECTED_EVIDENCE_COVERAGE = {
    (
        "demand_authenticity_and_sustainability",
        "issuer_demand_or_order_signal",
    ): 6,
    ("value_and_profit_capture", "issuer_financial_statement"): 3,
    (
        "bottleneck_counterevidence_and_what_would_change",
        "issuer_counterevidence",
    ): 6,
}
NEXT_ACTION = (
    "FIN-0.1.2-S4-T05-B-DELL-AGENT-FRESH-ZERO-CALL-PROOF-"
    "CAPACITY-AND-ADMISSION-AUTHORITY-DECISION"
)


class DellCurrentEvidenceMaterializationError(ValueError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise DellCurrentEvidenceMaterializationError(code)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DellCurrentEvidenceMaterializationError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def _write_exact_atomic(path: Path, value: Mapping[str, Any]) -> str:
    raw = _json_bytes(value)
    if path.exists():
        _require(
            path.read_bytes() == raw,
            "s4_t05_b_dell_materialization_existing_output_mismatch",
        )
        return "exact_existing_reused"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return "created"


def _validate_terminal_and_captures(
    live_result: Mapping[str, Any],
) -> tuple[dict[str, Any], str, Path]:
    terminal_record = live_result.get("terminal") or {}
    execution = live_result.get("execution_binding") or {}
    terminal_digest = str(terminal_record.get("digest") or "")
    terminal_ref = Path(str(terminal_record.get("runtime_object_ref") or ""))
    runtime_ref = Path(str(execution.get("runtime_ref") or ""))
    _require(
        live_result.get("status")
        == "pass_live_current_evidence_candidate_pack_ready_agent_input_compilation_next",
        "s4_t05_b_dell_live_result_status_invalid",
    )
    _require(
        terminal_ref.as_posix().startswith(runtime_ref.as_posix() + "/objects/"),
        "s4_t05_b_dell_terminal_runtime_ref_invalid",
    )
    terminal_path = ROOT / terminal_ref
    try:
        terminal_raw = terminal_path.read_bytes()
        terminal = json.loads(terminal_raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise DellCurrentEvidenceMaterializationError(
            "s4_t05_b_dell_terminal_unreadable"
        ) from exc
    _require(
        _sha256_bytes(terminal_raw) == terminal_digest,
        "s4_t05_b_dell_terminal_digest_mismatch",
    )
    _require(
        terminal.get("run_id") == execution.get("run_id")
        and terminal.get("attempt_id") == execution.get("attempt_id")
        and terminal.get("admission_digest") == execution.get("admission_digest")
        and terminal.get("case_key") == "DELL"
        and terminal.get("status") == "success"
        and terminal.get("code")
        == "three_request_current_evidence_candidate_pack_ready"
        and terminal.get("T04_consumption_authorized") is True
        and terminal.get("writer_citable_in_T03") is False
        and terminal.get("domain_judgment_eligible_in_T03") is False,
        "s4_t05_b_dell_terminal_binding_invalid",
    )
    _require(
        terminal.get("observed_counts") == EXPECTED_OBSERVED_COUNTS,
        "s4_t05_b_dell_terminal_observed_counts_invalid",
    )
    expected_requests = {
        row.program_cell_id: row.request_digest
        for row in compile_current_case_executable_requests("DELL")
    }
    results = terminal.get("request_results") or []
    actual_requests = {
        str(row.get("request", {}).get("program_cell_id") or ""): str(
            row.get("request", {}).get("request_digest") or ""
        )
        for row in results
    }
    _require(
        actual_requests == expected_requests,
        "s4_t05_b_dell_terminal_request_digest_binding_invalid",
    )
    accepted_ids = {
        str(candidate.get("candidate_id") or "")
        for row in results
        for candidate in row.get("accepted_candidates") or []
    }
    rejected_ids = {
        str(candidate.get("candidate_id") or "")
        for row in results
        for candidate in row.get("rejected_candidates") or []
    }
    _require(
        len(accepted_ids) == 18 and accepted_ids.isdisjoint(rejected_ids),
        "s4_t05_b_dell_candidate_partition_invalid",
    )
    runtime_objects = ROOT / runtime_ref / "objects"
    capture_keys: set[str] = set()
    for capture in terminal.get("capture_objects") or []:
        object_key = str(capture.get("object_key") or "")
        digest = str(capture.get("digest") or "")
        path = runtime_objects / object_key
        _require(
            path.is_file() and _sha256(path) == digest,
            "s4_t05_b_dell_capture_content_address_invalid",
        )
        capture_keys.add(object_key)
    _require(
        len(capture_keys) == 8,
        "s4_t05_b_dell_capture_cardinality_invalid",
    )
    for row in results:
        for candidate in row.get("accepted_candidates") or []:
            _require(
                str(candidate.get("source_snapshot_ref") or "") in capture_keys,
                "s4_t05_b_dell_candidate_snapshot_not_captured",
            )
    return terminal, terminal_digest, terminal_path


def compile_bound_outputs(
    terminal: Mapping[str, Any], *, terminal_digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    entry = load_current_fin_0_1_2_s4_t01_case_entry("DELL")
    pack = validate_transfer_evidence_pack(
        compile_current_case_evidence_pack(
            terminal,
            terminal_digest=terminal_digest,
            t01_entry=entry,
            case_key="DELL",
        ),
        case_key="DELL",
    )
    evidence_coverage = Counter(
        (
            str(row["program_cell_ids"][0]),
            str(row["evidence_role"]),
        )
        for row in pack["evidence_rows"]
    )
    gap_set = {
        (str(row["program_cell_ids"][0]), str(row["gap_code"]))
        for row in pack["typed_gaps"]
    }
    _require(
        dict(evidence_coverage) == EXPECTED_EVIDENCE_COVERAGE,
        "s4_t05_b_dell_evidence_coverage_invalid",
    )
    _require(gap_set == EXPECTED_GAPS, "s4_t05_b_dell_typed_gap_set_invalid")
    _require(
        {str(row["metric_family"]) for row in pack["numeric_rows"]}
        == {"revenue", "gross_profit", "operating_income"},
        "s4_t05_b_dell_numeric_family_invalid",
    )
    baseline = compile_legacy_oracle_agent_input("DELL", repository_root=ROOT)
    agent = compile_t05_b_current_product_agent_input(
        baseline, pack, case_key="DELL"
    )
    agent_input = agent.model_dump(mode="json")
    expected_case_id = compile_current_product_case_identity(
        "DELL",
        t01_entry_digest=entry.receipt.entry_digest,
        evidence_pack_digest=str(pack["evidence_pack_digest"]),
    )
    _require(
        agent_input["case_id"] == expected_case_id
        and "oracle" not in str(agent_input["case_id"]),
        "s4_t05_b_dell_agent_current_case_identity_invalid",
    )
    _require(
        agent_input["input_digest"]
        == canonical_digest(
            {
                key: value
                for key, value in agent_input.items()
                if key != "input_digest"
            }
        ),
        "s4_t05_b_dell_agent_input_digest_invalid",
    )
    evidence_refs = {str(row["evidence_ref"]) for row in pack["evidence_rows"]}
    numeric_refs = {str(row["numeric_ref"]) for row in pack["numeric_rows"]}
    agent_evidence_refs = {
        str(ref)
        for cell in agent_input["cell_inputs"]
        for ref in cell["authority_refs"]["accepted_evidence_refs"]
    }
    agent_numeric_refs = {
        str(ref)
        for cell in agent_input["cell_inputs"]
        for ref in cell["authority_refs"]["numeric_refs"]
    }
    _require(
        agent_evidence_refs == evidence_refs and agent_numeric_refs == numeric_refs,
        "s4_t05_b_dell_agent_authority_ref_projection_invalid",
    )
    runtime = agent_input.get("s4_case_runtime") or {}
    hard = agent_input.get("hard_boundaries") or {}
    _require(
        runtime.get("paid_execution_authorized") is False
        and runtime.get("source_grounded_input", {}).get("source_pack_digest")
        == pack["evidence_pack_digest"]
        and agent_input["lineage"]["S4_T04_source_grounded_input"]["digest"]
        == pack["evidence_pack_digest"]
        and hard.get("source_network_calls_allowed") is False
        and hard.get("external_tool_calls_allowed") is False
        and hard.get("live_business_case_head_writes_allowed") is False
        and hard.get("cross_case_fact_reuse_allowed") is False,
        "s4_t05_b_dell_agent_hard_boundary_invalid",
    )
    return pack, agent_input


def build_materialization(recorded_at: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    live_result = _load_json(
        ROOT / LIVE_RESULT_REF,
        "s4_t05_b_dell_live_result_unreadable",
    )
    terminal, terminal_digest, terminal_path = _validate_terminal_and_captures(
        live_result
    )
    pack, agent_input = compile_bound_outputs(
        terminal, terminal_digest=terminal_digest
    )
    pack_raw = _json_bytes(pack)
    agent_raw = _json_bytes(agent_input)
    bindings = [
        {"ref": path.as_posix(), "sha256": _sha256(ROOT / path)}
        for path in (LIVE_RESULT_REF, *COMPILER_REFS)
    ]
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_current_evidence_and_agent_"
            "exact_input_zero_call_materialization_v1_0"
        ),
        "result_id": (
            "FIN-0.1.2-S4-T05-B-DELL-CURRENT-EVIDENCE-AND-AGENT-"
            "EXACT-INPUT-ZERO-CALL-MATERIALIZATION"
        ),
        "recorded_at": recorded_at,
        "status": "pass_compiled_current_evidence_and_agent_exact_input",
        "source_execution_binding": {
            "search_result_ref": LIVE_RESULT_REF.as_posix(),
            "search_result_sha256": _sha256(ROOT / LIVE_RESULT_REF),
            "terminal_runtime_ref": terminal_path.relative_to(ROOT).as_posix(),
            "terminal_digest": terminal_digest,
            "run_id": terminal["run_id"],
            "attempt_id": terminal["attempt_id"],
            "admission_digest": terminal["admission_digest"],
            "second_search_or_replay_performed": False,
        },
        "immutable_bindings": bindings,
        "compiled_outputs": {
            "evidence_pack_ref": EVIDENCE_PACK_REF.as_posix(),
            "evidence_pack_sha256": _sha256_bytes(pack_raw),
            "evidence_pack_digest": pack["evidence_pack_digest"],
            "agent_exact_input_ref": AGENT_INPUT_REF.as_posix(),
            "agent_exact_input_sha256": _sha256_bytes(agent_raw),
            "agent_input_digest": agent_input["input_digest"],
            "current_case_id": agent_input["case_id"],
            "current_case_version": agent_input["case_version"],
        },
        "evidence_gate": {
            "accepted_candidates": 18,
            "writer_citable_evidence": 15,
            "exact_numeric_authority": 3,
            "typed_gaps": 3,
            "evidence_by_cell": {
                "demand_authenticity_and_sustainability": 6,
                "value_and_profit_capture": 3,
                "bottleneck_counterevidence_and_what_would_change": 6,
            },
            "numeric_metric_families": [
                "gross_profit",
                "operating_income",
                "revenue",
            ],
            "rejected_candidate_promoted": False,
            "model_generated_evidence": False,
            "cross_case_fact_reuse": False,
        },
        "agent_input_boundary": {
            "program_cells": list(agent_input["program_cell_ids"]),
            "lineage_refs": list(agent_input["lineage"]),
            "research_profile_ref": agent_input["s4_case_runtime"]["binding"][
                "research_profile_ref"
            ],
            "legacy_oracle_case_identity_retained": False,
            "paid_execution_authorized": False,
            "source_network_calls_allowed": False,
            "external_tool_calls_allowed": False,
            "live_business_case_head_writes_allowed": False,
        },
        "observed_new_counts": {
            "source_network_calls": 0,
            "local_retrieval_or_tool_invocations": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "admissions": 0,
            "business_runs": 0,
            "business_artifacts": 0,
        },
        "stage_acceptance": {
            "S4_T05_B_DELL_Search": "pass_live_current_candidate_pack_ready",
            "S4_T05_B_DELL_Evidence_and_Agent_input": "engineering_pass_zero_call",
            "S4_T05_B_DELL_Agent_live": "not_started",
            "DELL_current_R2": False,
            "MU_current_R2": False,
            "post_transfer_NVDA_R2": False,
        },
        "next_action": NEXT_ACTION,
        "known_boundary": (
            "Compilation proves the exact current Evidence and Agent input surfaces. "
            "It is not Agent admission, DeepSeek execution, nine business Artifacts, "
            "L1-L4, paired assessment, Owner acceptance or DELL R2."
        ),
    }
    return pack, agent_input, {
        **body,
        "materialization_digest": canonical_digest(body),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--evidence-output", type=Path, default=ROOT / EVIDENCE_PACK_REF)
    parser.add_argument("--agent-input-output", type=Path, default=ROOT / AGENT_INPUT_REF)
    parser.add_argument("--result-output", type=Path, default=ROOT / MATERIALIZATION_REF)
    args = parser.parse_args()
    pack, agent_input, result = build_materialization(args.recorded_at)
    statuses = {
        "evidence_pack": _write_exact_atomic(args.evidence_output.resolve(), pack),
        "agent_exact_input": _write_exact_atomic(
            args.agent_input_output.resolve(), agent_input
        ),
        "materialization_result": _write_exact_atomic(
            args.result_output.resolve(), result
        ),
    }
    print(
        json.dumps(
            {
                "status": result["status"],
                "write_statuses": statuses,
                "evidence_pack_digest": result["compiled_outputs"][
                    "evidence_pack_digest"
                ],
                "agent_input_digest": result["compiled_outputs"][
                    "agent_input_digest"
                ],
                "current_case_id": result["compiled_outputs"]["current_case_id"],
                "materialization_digest": result["materialization_digest"],
                "next_action": result["next_action"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
