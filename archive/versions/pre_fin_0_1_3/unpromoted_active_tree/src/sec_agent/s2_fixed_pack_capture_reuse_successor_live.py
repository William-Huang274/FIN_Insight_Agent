from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest, file_sha256
from sec_agent.s2_fixed_pack_capture_reuse_successor import SUCCESSOR_NODE_ORDER
from sec_agent.s2_fixed_pack_capture_reuse_successor_runtime import (
    SCOPE,
    validate_successor_admission,
)


AUTHORITY_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_capture_reuse_successor_authority_v1_0"
)
RESULT_SCHEMA = "fin_ia_0_1_3_s2_dell_capture_reuse_successor_result_v1_0"
PROOF_SCHEMA = (
    "fin_ia_0_1_3_s2_dell_capture_reuse_successor_clean_independent_proof_v1_0"
)
RUN_SCOPE = SCOPE


class S2FixedPackSuccessorLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackSuccessorLiveError(code)


def validate_clean_proof(proof: Mapping[str, Any]) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    terminal = dict(proof.get("terminal") or {})
    counts = dict(terminal.get("observed_counts") or {})
    observed = dict(proof.get("observed_counts_across_workers") or {})
    imported = [dict(row) for row in proof.get("predecessor_imported_nodes") or ()]
    failed = dict(proof.get("failed_predecessor_node") or {})
    _require(
        proof.get("schema_version") == PROOF_SCHEMA
        and proof.get("status")
        == "clean_independent_dell_capture_reuse_successor_zero_call_proof_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True
        and proof.get("credential_environment_scrubbed") is True
        and proof.get("socket_blocked_in_workers") is True,
        "fixed_pack_successor_live_clean_proof_invalid",
    )
    _require(
        len(imported) == 5
        and failed.get("promoted_as_usable_output") is False
        and terminal.get("status") == "completed"
        and counts.get("imported_usable_nodes") == 5
        and counts.get("successor_provider_calls") == len(SUCCESSOR_NODE_ORDER)
        and counts.get("combined_provider_attempts") == 14
        and counts.get("logical_outputs_present") == 13
        and terminal.get("logical_node_indices") == list(range(6, 14))
        and terminal.get("business_artifact_promoted") is False
        and observed.get("real_provider_calls") == 0
        and observed.get("model_calls") == 0
        and observed.get("network_calls") == 0
        and observed.get("retries") == 0,
        "fixed_pack_successor_live_clean_proof_population_invalid",
    )


def issue_successor_authority(
    *,
    admission: Mapping[str, Any],
    clean_proof: Mapping[str, Any],
    implementation_commit: str,
    implementation_bindings: Sequence[Mapping[str, Any]],
    project_os_preflight: Mapping[str, Any],
    user_authority: str,
    recorded_at: str,
) -> dict[str, Any]:
    validate_clean_proof(clean_proof)
    _require(
        admission.get("scope") == RUN_SCOPE
        and admission.get("case_key") == "DELL"
        and admission.get("execution_mode") == "live"
        and admission.get("credential_present") is True
        and admission.get("promotion_authority") is False
        and admission.get("semantic_retry") is False
        and admission.get("paired_baseline_same_input_proven") is False
        and admission.get("successor_node_order") == list(SUCCESSOR_NODE_ORDER),
        "fixed_pack_successor_live_admission_scope_invalid",
    )
    _require(
        project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == RUN_SCOPE,
        "fixed_pack_successor_live_project_os_preflight_invalid",
    )
    bindings = [deepcopy(dict(row)) for row in implementation_bindings]
    _require(
        bool(bindings)
        and all(
            str(row.get("ref") or "") and str(row.get("sha256") or "")
            for row in bindings
        ),
        "fixed_pack_successor_live_implementation_bindings_invalid",
    )
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "decision_id": (
            "FIN-0.1.3-S2-DELL-CAPTURE-REUSE-SUCCESSOR-R1-AUTHORITY"
        ),
        "recorded_at": recorded_at,
        "status": "issued_unconsumed",
        "run_scope": RUN_SCOPE,
        "case_key": "DELL",
        "user_authority": user_authority,
        "clean_proof_digest": clean_proof["proof_digest"],
        "implementation_commit": implementation_commit,
        "implementation_bindings": bindings,
        "project_os_preflight": {
            "status": project_os_preflight["status"],
            "run_scope": project_os_preflight["run_scope"],
            "open_full_chain_blocker_count": project_os_preflight[
                "open_full_chain_blocker_count"
            ],
        },
        "admission": deepcopy(dict(admission)),
        "execution_ceiling": {
            "cases": 1,
            "predecessor_imported_usable_nodes": 5,
            "successor_provider_calls": len(SUCCESSOR_NODE_ORDER),
            "successor_model_calls": len(SUCCESSOR_NODE_ORDER),
            "combined_provider_attempts": 14,
            "logical_node_outputs": 13,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_promotions": 0,
        },
        "maximum_executions": 1,
        "automatic_execution": False,
        "same_input_paired_acceptance_authorized": False,
        "known_boundary": (
            "This authority imports five immutable predecessor outputs and permits "
            "only the remaining eight DeepSeek nodes. It is not a semantic retry, "
            "does not authorize other cases or product promotion, and cannot establish "
            "strict same-input paired acceptance because the imported direct baseline "
            "did not see the augmented numeric authority."
        ),
    }
    return {**body, "authority_digest": canonical_digest(body)}


def validate_successor_authority(
    authority: Mapping[str, Any],
    *,
    clean_proof: Mapping[str, Any],
    case_input: Mapping[str, Any],
    predecessor_bundle: Mapping[str, Any],
    profile: Mapping[str, Any],
    repo_root: str | Path,
    observed_at: str,
) -> None:
    validate_clean_proof(clean_proof)
    body = deepcopy(dict(authority))
    digest = str(body.pop("authority_digest", ""))
    _require(
        authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "issued_unconsumed"
        and authority.get("run_scope") == RUN_SCOPE
        and authority.get("case_key") == "DELL"
        and digest == canonical_digest(body)
        and authority.get("clean_proof_digest") == proof_digest(clean_proof)
        and authority.get("automatic_execution") is False
        and authority.get("same_input_paired_acceptance_authorized") is False,
        "fixed_pack_successor_live_authority_digest_or_scope_invalid",
    )
    _require(
        authority.get("execution_ceiling")
        == {
            "cases": 1,
            "predecessor_imported_usable_nodes": 5,
            "successor_provider_calls": 8,
            "successor_model_calls": 8,
            "combined_provider_attempts": 14,
            "logical_node_outputs": 13,
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_promotions": 0,
        }
        and authority.get("maximum_executions") == 1,
        "fixed_pack_successor_live_authority_ceiling_invalid",
    )
    root = Path(repo_root).resolve()
    for binding in authority.get("implementation_bindings") or ():
        path = root / str(binding.get("ref") or "")
        _require(
            path.is_file() and file_sha256(path) == str(binding.get("sha256") or ""),
            "fixed_pack_successor_live_implementation_binding_drift",
        )
    admission = dict(authority.get("admission") or {})
    validate_successor_admission(
        admission,
        case_input=case_input,
        predecessor_bundle=predecessor_bundle,
        profile=profile,
        execution_git_commit=str(authority.get("implementation_commit") or ""),
        runtime_sha256=str(admission.get("runtime_sha256") or ""),
        runner_sha256=str(admission.get("runner_sha256") or ""),
        successor_contract_sha256=str(
            admission.get("successor_contract_sha256") or ""
        ),
        base_contract_sha256=str(admission.get("base_contract_sha256") or ""),
        profile_sha256=str(admission.get("profile_sha256") or ""),
        observed_at=observed_at,
    )


def proof_digest(proof: Mapping[str, Any]) -> str:
    return str(proof.get("proof_digest") or "")


def build_public_successor_result(
    *,
    authority: Mapping[str, Any],
    terminal: Mapping[str, Any],
    private_terminal_path: str | Path,
    recorded_at: str,
) -> dict[str, Any]:
    private_path = Path(private_terminal_path).resolve()
    _require(
        private_path.is_file(),
        "fixed_pack_successor_live_private_terminal_missing",
    )
    findings = [dict(row) for row in terminal.get("findings") or ()]
    receipts = [dict(row) for row in terminal.get("successor_call_receipts") or ()]
    predecessor = dict(terminal.get("predecessor") or {})
    body = {
        "schema_version": RESULT_SCHEMA,
        "recorded_at": recorded_at,
        "run_scope": RUN_SCOPE,
        "authority_digest": authority["authority_digest"],
        "admission_digest": authority["admission"]["admission_digest"],
        "run_id": terminal["run_id"],
        "attempt_id": terminal["attempt_id"],
        "case_key": terminal["case_key"],
        "base_case_input_digest": terminal["base_case_input_digest"],
        "successor_case_input_digest": terminal["successor_case_input_digest"],
        "numeric_authority_digest": terminal["numeric_authority_digest"],
        "source_pack_digest": terminal["source_pack_digest"],
        "predecessor": {
            "run_id": predecessor.get("run_id"),
            "attempt_id": predecessor.get("attempt_id"),
            "terminal_digest": predecessor.get("terminal_digest"),
            "import_bundle_digest": predecessor.get("import_bundle_digest"),
            "imported_node_count": len(
                predecessor.get("imported_node_lineage") or ()
            ),
            "failed_node": (
                predecessor.get("failed_attempt_evidence") or {}
            ).get("node_key"),
            "failed_capture_promoted": (
                predecessor.get("failed_attempt_evidence") or {}
            ).get("promoted_as_usable_output"),
            "usage": deepcopy(dict(predecessor.get("usage") or {})),
        },
        "status": terminal["status"],
        "terminal_phase": terminal["terminal_phase"],
        "terminal_code": terminal["terminal_code"],
        "observed_counts": deepcopy(dict(terminal["observed_counts"])),
        "successor_usage": deepcopy(dict(terminal["successor_usage"])),
        "cumulative_usage": deepcopy(dict(terminal["cumulative_usage"])),
        "successor_call_receipts": [
            {
                "call_id": row.get("call_id"),
                "logical_node_index": row.get("logical_node_index"),
                "node_key": row.get("node_key"),
                "capture_digest": row.get("capture_digest"),
                "request_digest": row.get("request_digest"),
                "status": row.get("status"),
                "finish_reason": row.get("finish_reason"),
            }
            for row in receipts
        ],
        "finding_summary": {
            "L1": sum(row.get("level") == "L1" for row in findings),
            "L2": sum(row.get("level") == "L2" for row in findings),
            "L3": sum(row.get("level") == "L3" for row in findings),
            "L4": sum(row.get("level") == "L4" for row in findings),
            "codes": sorted({str(row.get("code") or "") for row in findings}),
        },
        "same_evidence_pack_proven": terminal["same_evidence_pack_proven"],
        "same_input_pair_proven": terminal["same_input_pair_proven"],
        "paired_assessment_eligible": terminal["paired_assessment_eligible"],
        "paired_baseline_required_later": terminal[
            "paired_baseline_required_later"
        ],
        "business_artifact_promoted": terminal["business_artifact_promoted"],
        "qualified_human_acceptance_required": terminal[
            "qualified_human_acceptance_required"
        ],
        "raw_model_output_public": False,
        "raw_model_output_stored_private": True,
        "private_terminal": {
            "ref": private_path.relative_to(Path.cwd().resolve()).as_posix()
            if private_path.is_relative_to(Path.cwd().resolve())
            else private_path.as_posix(),
            "sha256": file_sha256(private_path),
            "terminal_digest": terminal["terminal_digest"],
        },
        "known_boundary": (
            "This result preserves the five imported outputs and eight successor calls. "
            "It is a raw candidate, not a promoted report. Content quality needs an "
            "independent audit; strict paired acceptance still requires a separate "
            "direct baseline that sees the same augmented input."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "AUTHORITY_SCHEMA",
    "PROOF_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S2FixedPackSuccessorLiveError",
    "build_public_successor_result",
    "issue_successor_authority",
    "validate_clean_proof",
    "validate_successor_authority",
]
