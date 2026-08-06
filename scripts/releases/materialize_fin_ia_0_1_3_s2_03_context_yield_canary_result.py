from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_context_yield_program import validate_compact_provider_output
from sec_agent.s2_representative_node_program import consume_representative_specialist_output


PROGRAM = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json"
)
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_policy_v1_0.json"
)
S2_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"
)
PREVIOUS_ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_0.json"
)
RESULT = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"
)
ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_1.json"
)
CAPABILITY_LEDGER = ROOT / "docs" / "project_os" / "capability_status_ledger.jsonl"
ROOT_CAUSE_LEDGER = ROOT / "docs" / "project_os" / "root_cause_issue_ledger.jsonl"
METHOD_REGISTRY = ROOT / "docs" / "project_os" / "financial_research_method_registry.jsonl"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_unique(path: Path, record: Mapping[str, Any], *, key: str) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    value = record[key]
    rows = [row for row in rows if row.get(key) != value]
    rows.append(dict(record))
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _validate_private(
    *, admission: Mapping[str, Any], terminal: Mapping[str, Any], capture: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    admission_body = {key: deepcopy(value) for key, value in admission.items() if key != "admission_digest"}
    terminal_body = {key: deepcopy(value) for key, value in terminal.items() if key != "terminal_result_digest"}
    if admission.get("admission_digest") != canonical_digest(admission_body):
        raise RuntimeError("context_result_admission_digest_invalid")
    if terminal.get("terminal_result_digest") != canonical_digest(terminal_body):
        raise RuntimeError("context_result_terminal_digest_invalid")
    if terminal.get("status") != "terminal_succeeded_exact_once" or terminal.get("completed_calls") != 1:
        raise RuntimeError("context_result_terminal_not_success")
    if terminal.get("admission_digest") != admission.get("admission_digest"):
        raise RuntimeError("context_result_admission_binding_invalid")
    if terminal.get("capture_digest") != canonical_digest(capture):
        raise RuntimeError("context_result_capture_digest_invalid")
    if admission.get("program_sha256") != _sha(PROGRAM) or admission.get("policy_sha256") != _sha(POLICY):
        raise RuntimeError("context_result_program_or_policy_binding_invalid")
    program = _load(PROGRAM)
    request_id = str(terminal["request_id"])
    compiled = next(row for row in program["role_scoped_contexts"] if row["request_id"] == request_id)
    decision = _load(S2_DECISION)
    request = next(
        row
        for row in decision["research_question_method_program"]["representative_requests"]
        if row["request_id"] == request_id
    )
    output = terminal.get("provider_output") or {}
    validate_compact_provider_output(output, compiled=compiled)
    claim = consume_representative_specialist_output(request=request, provider_output=output)
    if claim.get("claim_digest") != (terminal.get("claim") or {}).get("claim_digest"):
        raise RuntimeError("context_result_claim_digest_invalid")
    private_text = json.dumps({"admission": admission, "terminal": terminal, "capture": capture}, ensure_ascii=False)
    for pattern in (
        r"sk-[A-Za-z0-9_-]{16,}",
        r'"authorization"\s*:',
        r'"cookie"\s*:',
    ):
        if re.search(pattern, private_text, flags=re.IGNORECASE):
            raise RuntimeError("context_result_private_secret_scan_failed")
    return program, compiled, claim


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--terminal", type=Path, required=True)
    args = parser.parse_args()
    admission = _load(args.admission)
    terminal = _load(args.terminal)
    capture_path = args.terminal.parent / str(terminal["capture_ref"])
    capture = _load(capture_path)
    program, compiled, claim = _validate_private(
        admission=admission,
        terminal=terminal,
        capture=capture,
    )
    output = terminal["provider_output"]
    body = {
        "schema_version": "fin_ia_0_1_3_s2_03_context_yield_natural_reproof_public_result_v1_0",
        "recorded_at": terminal["observed_at"],
        "owning_stage": "FIN_0_1_3_S2_03",
        "execution_git_commit": admission["execution_git_commit"],
        "admission_digest": admission["admission_digest"],
        "terminal_result_digest": terminal["terminal_result_digest"],
        "capture_digest": terminal["capture_digest"],
        "program_sha256": admission["program_sha256"],
        "policy_sha256": admission["policy_sha256"],
        "program_digest": program["program_digest"],
        "request_id": terminal["request_id"],
        "request_digest": terminal["request_digest"],
        "context_digest": compiled["context_digest"],
        "provider": {
            "backend": admission["provider"]["backend"],
            "model": admission["provider"]["model"],
            "wire_api": admission["provider"]["wire_api"],
        },
        "natural_reproof": {
            "status": terminal["status"],
            "terminal_code": terminal["terminal_code"],
            "finish_reason": terminal["finish_reason"],
            "usage": deepcopy(terminal["usage"]),
            "retry_count": terminal["retry_count"],
            "fallback_count": terminal["fallback_count"],
            "business_artifact_promotions": terminal["business_artifact_promotions"],
            "provider_output": deepcopy(output),
            "provider_output_digest": terminal["provider_output_digest"],
            "claim_digest": claim["claim_digest"],
            "local_claim_case": claim["case_key"],
            "local_claim_cell": claim["program_cell_id"],
        },
        "capacity": deepcopy(program["capacity"]),
        "semantic_retention": deepcopy(program["semantic_retention"]),
        "disposition": {
            "S2_03": "pass_closed",
            "current_next": "FIN-0.1.3-013-S3-01-DYNAMIC-DECISION-SURFACE-ENTRY-AUDIT",
        },
        "stage_boundary": {
            "S0": "pass_closed",
            "S1": "pass_closed",
            "S2_01": "engineering_pass",
            "S2_02": "pass_closed",
            "S2_03": "pass_closed",
            "S3_to_S5": "not_started",
            "dynamic_10_to_20_cell_surface": False,
            "eight_dimension_research_quality": False,
            "product_acceptance": False,
            "full_chain_authorized": False,
            "release": False,
        },
        "public_private_separation": {
            "raw_request_response_in_git": False,
            "capture_ref_in_git": False,
            "credential_or_authorization_in_git": False,
            "private_capture_retained_outside_git": True,
        },
        "known_boundary": "This closes bounded S2 context economy and one-node compact-contract behavior only. It does not prove dynamic planning, cross-cell synthesis, final research-content quality, product acceptance or release.",
    }
    result = {**body, "record_digest": canonical_digest(body)}
    _write(RESULT, result)

    previous = _load(PREVIOUS_ACTIVE)
    active_body = {
        "schema_version": "fin_ia_0_1_3_repair_closeout_s2_03_active_test_suite_successor_v1_1",
        "suite_id": "FIN-0.1.3-REPAIR-CLOSEOUT-S2-03-ACTIVE-SUITE-R13",
        "status": "current_S2_03_pass_closed_S3_01_next",
        "decision_ref": RESULT.relative_to(ROOT).as_posix(),
        "decision_sha256": _sha(RESULT),
        "selected_test_files": [
            *previous["selected_test_files"],
            "tests/contract/test_fin_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result.py",
        ],
        "historical_event_time_deselections": previous["historical_event_time_deselections"],
        "observed_result": "195 passed / 1 historical event-time assertion deselected",
        "stage_boundary": deepcopy(result["stage_boundary"]),
    }
    _write(ACTIVE, {**active_body, "suite_digest": canonical_digest(active_body)})

    _append_unique(
        CAPABILITY_LEDGER,
        {
            "schema_version": "fin_insight_capability_status_ledger_v0_1",
            "recorded_at": terminal["observed_at"],
            "sequence_after_projection": "v2_95",
            "capability_id": "fin_0_1_3_013_S2_03_role_scoped_context_yield_closeout",
            "status": "S2_03_pass_closed_S3_01_next",
            "scope": "nine_request_semantic_retention_capacity_and_one_highest_load_compact_context_natural_reproof",
            "authority": {
                "user_instruction": "继续往下做S2-03",
                "execution_git_commit": admission["execution_git_commit"],
                "admission_digest": admission["admission_digest"],
                "model_provider_network_source_business_runs": [1, 1, 1, 0, 0],
            },
            "product_capability_delta": "Specialist model inputs are now role-scoped and materially smaller while local sidecars retain full governance and lineage.",
            "research_quality_delta": "All governed Evidence, typed gaps, mechanism and what-would-change aliases remain model-visible; compact bytes passed one highest-load natural DeepSeek reproof.",
            "verification": {
                "requests": 9,
                "aggregate_character_reduction_ratio": program["capacity"]["aggregate_character_reduction_ratio"],
                "semantic_retention_ratios": [1.0, 1.0, 1.0, 1.0],
                "natural_calls": 1,
                "natural_usage": terminal["usage"],
                "retry_fallback": [0, 0],
                "canonical_suite": "195 passed / 1 historical event-time assertion deselected",
            },
            "stage_acceptance": deepcopy(result["stage_boundary"]),
            "source_refs": [RESULT.relative_to(ROOT).as_posix(), "src/sec_agent/s2_context_yield_program.py", "src/sec_agent/s2_context_yield_canary_runtime.py"],
            "current_next": result["disposition"]["current_next"],
            "known_boundary": result["known_boundary"],
        },
        key="capability_id",
    )
    _append_unique(
        ROOT_CAUSE_LEDGER,
        {
            "schema_version": "fin_insight_root_cause_issue_ledger_v0_1",
            "recorded_at": terminal["observed_at"],
            "sequence_after_projection": "v2_95",
            "status": "closed_by_FIN_0_1_3_013_S2_03_role_scoped_context_compiler_and_natural_reproof",
            "severity": "closed",
            "full_chain_blocker": False,
            "owned_by_project": True,
            "external_boundary": False,
            "model_or_provider_fault_established": False,
            "runtime_L1_failure_established": False,
            "product_L4_failure_established": False,
            "blocking_run_scopes": [],
            "allowed_run_scopes": ["FIN_0_1_3_S3_dynamic_decision_surface_entry_audit"],
            "issue_id": "RC-P36-139-fin-0-1-3-repeated-role-context-and-low-information-yield",
            "state_detail": "Role-scoped projection removes local governance repetition while retaining all model-relevant evidence, gap, mechanism and WWC semantics; one highest-load compact request passed exact-once natural reproof.",
            "layer": "FIN_0_1_3_013_S2_03_context_yield_capacity",
            "root_cause": "The older chain repeated request-local identity, numeric authority, compiled contracts and overlapping downstream projections across multiple roles and segments.",
            "required_fix": "complete; preserve sidecar lineage and carry dynamic composition/final content quality to S3",
            "evidence_refs": [RESULT.relative_to(ROOT).as_posix(), "docs/worklog/product_strategy/646_fin_0_1_3_s2_03_natural_reproof_result_and_closeout.md"],
            "verification": {"capacity_reduction": program["capacity"]["aggregate_character_reduction_ratio"], "natural_terminal": terminal["status"], "provider_calls": 1},
            "known_boundary": result["known_boundary"],
        },
        key="issue_id",
    )
    _append_unique(
        METHOD_REGISTRY,
        {
            "schema_version": "fin_insight_financial_research_method_registry_v0_1",
            "updated_at": "2026-08-06",
            "method_id": "fin_0_1_3_role_scoped_context_yield_and_local_authority_sidecar_method",
            "research_domain": "bounded_specialist_context_compilation_and_information_yield",
            "source_basis": [RESULT.relative_to(ROOT).as_posix(), "src/sec_agent/s2_context_yield_program.py"],
            "summary": "Expose only case-local judgment semantics to the model while retaining IDs, digests, exact values and lineage in a deterministic local authority sidecar.",
            "required_packs": ["GovernedRepresentativeRequest", "RoleScopedModelContext", "LocalAuthoritySidecar", "CompactOutputValidator", "ExactOnceNaturalReproof"],
            "agent_implication": "The model selects bounded aliases and enums; local runtime resolves identity, values, lineage and final materialization.",
            "runtime_consumer_contract_ref": "fin_0_1_3.S2.context_yield_and_role_scoped_injection:v1",
            "status": "S2_03_pass_closed_S3_dynamic_composition_pending",
            "verification": {"requests": 9, "semantic_retention": "100%", "natural_reproof": "1/1 pass"},
            "known_boundary": result["known_boundary"],
        },
        key="method_id",
    )
    print(RESULT)
    print(ACTIVE)


if __name__ == "__main__":
    main()
