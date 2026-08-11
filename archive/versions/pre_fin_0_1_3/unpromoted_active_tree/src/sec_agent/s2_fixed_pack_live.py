from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest, file_sha256
from sec_agent.s2_fixed_pack_research import (
    compile_six_case_model_inputs,
    load_fixed_pack_contract,
    load_fixed_pack_profile,
    load_frozen_local_packs,
)
from sec_agent.s2_fixed_pack_research_runtime import (
    NODE_ORDER,
    validate_case_admission,
)


AUTHORITY_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_dell_canary_authority_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_dell_canary_result_v1_0"
PROOF_SCHEMAS = {
    "fin_ia_0_1_3_s2_fixed_pack_clean_independent_proof_v1_0",
    "fin_ia_0_1_3_s2_fixed_pack_clean_independent_proof_v1_1",
}
RUN_SCOPE = "FIN_0_1_3_S2_FIXED_PACK_DELL_CANARY"


class S2FixedPackLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackLiveError(code)


def _read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S2FixedPackLiveError(code) from exc
    _require(isinstance(value, dict), code)
    return value


def load_dell_fixed_pack_material(
    *,
    repo_root: str | Path,
    contract_path: str | Path,
    profile_path: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    contract = load_fixed_pack_contract(contract_path, repo_root=root)
    profile = load_fixed_pack_profile(profile_path)
    packs = load_frozen_local_packs(contract=contract, repo_root=root)
    inputs, compilation = compile_six_case_model_inputs(
        contract=contract,
        profile=profile,
        packs=packs,
    )
    dell = next(row for row in inputs if row["case_key"] == "DELL")
    return {
        "contract": contract,
        "profile": profile,
        "case_input": dell,
        "compilation_result_digest": compilation["result_digest"],
    }


def validate_clean_proof(proof: Mapping[str, Any]) -> None:
    body = deepcopy(dict(proof))
    digest = str(body.pop("proof_digest", ""))
    case_results = [dict(row) for row in body.get("case_results") or ()]
    _require(
        proof.get("schema_version") in PROOF_SCHEMAS
        and proof.get("status")
        == "clean_independent_six_case_zero_call_proof_passed"
        and digest == canonical_digest(body)
        and proof.get("fresh_worker_count") == 2
        and proof.get("workers_byte_equivalent") is True,
        "fixed_pack_live_clean_proof_invalid",
    )
    _require(
        len(case_results) == 6
        and all(
            row.get("status") == "completed"
            and row.get("request_captures") == len(NODE_ORDER)
            and row.get("response_captures") == len(NODE_ORDER)
            and row.get("business_artifact_promoted") is False
            for row in case_results
        )
        and (proof.get("observed_counts") or {}).get("real_provider_calls") == 0
        and (proof.get("observed_counts") or {}).get("model_calls") == 0,
        "fixed_pack_live_clean_proof_population_invalid",
    )


def issue_dell_canary_authority(
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
        admission.get("case_key") == "DELL"
        and admission.get("execution_mode") == "live"
        and admission.get("credential_present") is True
        and admission.get("promotion_authority") is False
        and admission.get("node_order") == list(NODE_ORDER),
        "fixed_pack_live_admission_scope_invalid",
    )
    _require(
        project_os_preflight.get("status") == "pass"
        and project_os_preflight.get("run_scope") == RUN_SCOPE,
        "fixed_pack_live_project_os_preflight_invalid",
    )
    bindings = [deepcopy(dict(row)) for row in implementation_bindings]
    _require(
        bindings
        and all(
            str(row.get("ref") or "") and str(row.get("sha256") or "")
            for row in bindings
        ),
        "fixed_pack_live_implementation_bindings_invalid",
    )
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "decision_id": "FIN-0.1.3-S2-DELL-FIXED-PACK-CANARY-R1-AUTHORITY",
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
            "provider_calls": len(NODE_ORDER),
            "model_calls": len(NODE_ORDER),
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_promotions": 0,
        },
        "maximum_executions": 1,
        "automatic_execution": False,
        "known_boundary": (
            "This authority permits one DELL fixed-pack DeepSeek canary. It does not "
            "authorize the other five cases, dynamic search, product promotion or release."
        ),
    }
    return {**body, "authority_digest": canonical_digest(body)}


def validate_dell_canary_authority(
    authority: Mapping[str, Any],
    *,
    clean_proof: Mapping[str, Any],
    case_input: Mapping[str, Any],
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
        and authority.get("clean_proof_digest") == clean_proof.get("proof_digest")
        and authority.get("automatic_execution") is False,
        "fixed_pack_live_authority_digest_or_scope_invalid",
    )
    ceiling = dict(authority.get("execution_ceiling") or {})
    _require(
        ceiling
        == {
            "cases": 1,
            "provider_calls": len(NODE_ORDER),
            "model_calls": len(NODE_ORDER),
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "business_promotions": 0,
        }
        and authority.get("maximum_executions") == 1,
        "fixed_pack_live_authority_ceiling_invalid",
    )
    root = Path(repo_root).resolve()
    for binding in authority.get("implementation_bindings") or ():
        path = root / str(binding.get("ref") or "")
        _require(
            path.is_file() and file_sha256(path) == str(binding.get("sha256") or ""),
            "fixed_pack_live_implementation_binding_drift",
        )
    admission = dict(authority.get("admission") or {})
    validate_case_admission(
        admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=str(authority.get("implementation_commit") or ""),
        runner_sha256=str(admission.get("runner_sha256") or ""),
        contract_sha256=str(admission.get("contract_sha256") or ""),
        profile_sha256=str(admission.get("profile_sha256") or ""),
        observed_at=observed_at,
    )


def build_public_dell_canary_result(
    *,
    authority: Mapping[str, Any],
    terminal: Mapping[str, Any],
    private_terminal_path: str | Path,
    recorded_at: str,
) -> dict[str, Any]:
    private_path = Path(private_terminal_path).resolve()
    _require(private_path.is_file(), "fixed_pack_live_private_terminal_missing")
    findings = [dict(row) for row in terminal.get("findings") or ()]
    receipts = [dict(row) for row in terminal.get("call_receipts") or ()]
    body = {
        "schema_version": RESULT_SCHEMA,
        "recorded_at": recorded_at,
        "run_scope": RUN_SCOPE,
        "authority_digest": authority["authority_digest"],
        "admission_digest": authority["admission"]["admission_digest"],
        "run_id": terminal["run_id"],
        "attempt_id": terminal["attempt_id"],
        "case_key": terminal["case_key"],
        "case_input_digest": terminal["case_input_digest"],
        "source_pack_digest": terminal["source_pack_digest"],
        "status": terminal["status"],
        "terminal_phase": terminal["terminal_phase"],
        "terminal_code": terminal["terminal_code"],
        "observed_counts": deepcopy(dict(terminal["observed_counts"])),
        "usage": {
            "input_tokens": sum(int(row.get("input_tokens") or 0) for row in receipts),
            "output_tokens": sum(int(row.get("output_tokens") or 0) for row in receipts),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in receipts),
        },
        "call_receipts": [
            {
                "call_id": row.get("call_id"),
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
        "same_input_pair_proven": terminal["same_input_pair_proven"],
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
            "This is a raw fixed-pack canary result. Content quality requires separate "
            "L1/L2 and Q1-Q8 assessment; dynamic research and product release remain false."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "AUTHORITY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "S2FixedPackLiveError",
    "build_public_dell_canary_result",
    "issue_dell_canary_authority",
    "load_dell_fixed_pack_material",
    "validate_clean_proof",
    "validate_dell_canary_authority",
]
