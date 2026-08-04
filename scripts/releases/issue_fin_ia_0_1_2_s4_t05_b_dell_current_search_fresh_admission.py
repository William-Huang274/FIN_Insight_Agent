from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    SearchAdmission,
    compile_current_case_executable_requests,
)
from run_fin_ia_0_1_2_s4_t05_current_search import load_exact_admission
from sec_agent.canonical_runtime.models import canonical_digest


AUTHORITY_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_zero_call_proof_"
    "and_admission_authority_decision_v1_0.json"
)
ADMISSION_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_admission_r1.json"
)
ISSUANCE_REF = Path(
    "configs/releases/"
    "fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_admission_"
    "issuance_v1_0.json"
)
RUNTIME_ROOT_REF = Path(".codex_runtime/fin012-s4-t05b-dell-current-search-r1")
BASE_COMMIT = "27eb4244eacf96fb922b53a95942e474d44b3ffb"
ISSUED_AT = "2026-08-04T17:01:00Z"
EXPIRES_AT = "2026-08-04T19:01:00Z"
RECORDED_AT = "2026-08-05T01:01:00+08:00"


class AdmissionIssuanceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise AdmissionIssuanceError(code)


def _load_authority() -> Mapping[str, Any]:
    path = ROOT / AUTHORITY_REF
    authority = json.loads(path.read_text(encoding="utf-8"))
    observed_digest = str(authority.get("decision_digest") or "")
    _require(
        observed_digest
        == canonical_digest(
            {key: value for key, value in authority.items() if key != "decision_digest"}
        ),
        "t05_b_dell_search_authority_digest_mismatch",
    )
    _require(
        authority.get("status")
        == "pass_DELL_current_search_admission_issuance_authorized_not_issued_no_live",
        "t05_b_dell_search_authority_status_invalid",
    )
    permissions = authority.get("authority") or {}
    _require(
        permissions.get("admission_issuance_authorized_next") is True
        and permissions.get("admission_issued") is False
        and permissions.get("source_live_authorized_this_decision") is False
        and permissions.get("agent_or_model_live_authorized") is False,
        "t05_b_dell_search_authority_boundary_invalid",
    )
    for binding in authority.get("immutable_bindings") or []:
        bound_path = ROOT / str(binding["ref"])
        _require(bound_path.is_file(), "t05_b_dell_search_authority_binding_missing")
        _require(
            _sha256(bound_path) == str(binding["sha256"]),
            "t05_b_dell_search_authority_binding_drift",
        )
    return authority


def compile_exact_admission() -> SearchAdmission:
    requests = compile_current_case_executable_requests("DELL")
    admission = SearchAdmission.create(
        case_key="DELL",
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
        request_digests=tuple(row.request_digest for row in requests),
    )
    admission.require_active(now=ISSUED_AT, requests=requests)
    return admission


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _current_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def issue(
    *,
    admission_output: Path,
    issuance_output: Path,
    runtime_root: Path,
) -> Mapping[str, Any]:
    authority = _load_authority()
    _require(_current_commit() == BASE_COMMIT, "t05_b_dell_search_base_commit_drift")
    _require(not runtime_root.exists(), "t05_b_dell_search_runtime_root_not_fresh")
    _require(
        not issuance_output.exists(),
        "t05_b_dell_search_issuance_already_exists",
    )
    admission = compile_exact_admission()
    expected_payload = admission.as_dict()
    recovered_exact_admission = False
    if admission_output.exists():
        existing = json.loads(admission_output.read_text(encoding="utf-8"))
        _require(
            existing == expected_payload,
            "t05_b_dell_search_existing_admission_not_exact",
        )
        recovered_exact_admission = True
    else:
        _write_json_atomic(admission_output, expected_payload)

    loaded = load_exact_admission(admission_output, case_key="DELL")
    loaded.require_active(
        now=ISSUED_AT,
        requests=compile_current_case_executable_requests("DELL"),
    )
    authority_path = ROOT / AUTHORITY_REF
    runner_path = ROOT / "scripts/releases/run_fin_ia_0_1_2_s4_t05_current_search.py"
    issuer_path = Path(__file__).resolve()
    issuance: dict[str, Any] = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_current_search_fresh_admission_"
            "issuance_v1_0"
        ),
        "issuance_id": (
            "FIN-0.1.2-S4-T05-B-DELL-CURRENT-SEARCH-FRESH-ADMISSION-ISSUANCE-R1"
        ),
        "recorded_at": RECORDED_AT,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority": {
            "user_instruction": "继续",
            "admission_issuance_authorized": True,
            "source_live_execution_authorized_this_issuance": False,
            "agent_or_model_execution_authorized": False,
            "automatic_retry_or_second_search_authorized": False,
        },
        "base_commit": BASE_COMMIT,
        "issued_admission": {
            "ref": str(admission_output.relative_to(ROOT)).replace("\\", "/")
            if admission_output.is_relative_to(ROOT)
            else str(admission_output),
            "sha256": _sha256(admission_output),
            "admission_id": loaded.admission_id,
            "admission_digest": loaded.admission_digest,
            "issued_at": loaded.issued_at,
            "expires_at": loaded.expires_at,
            "case_key": loaded.case_key,
            "request_digests": list(loaded.request_digests),
            "issued": True,
            "consumed": False,
            "execution_started": False,
        },
        "reserved_execution_boundary": {
            "runtime_root": str(runtime_root.relative_to(ROOT)).replace("\\", "/")
            if runtime_root.is_relative_to(ROOT)
            else str(runtime_root),
            "runtime_root_absent": True,
            "single_declared_runtime_root_only": True,
            "cross_runtime_global_lock_proven": False,
            "cross_runtime_boundary_issue": "RC-P36-115",
        },
        "exact_budget": {
            "source_network_calls": loaded.source_network_call_ceiling,
            "local_retrieval_or_tool_invocations": loaded.local_invocation_ceiling,
            "retry_budget": loaded.retry_ceiling,
            "fallback_budget": loaded.fallback_ceiling,
            "wall_clock_seconds": loaded.wall_clock_seconds,
            "model_calls": loaded.model_calls,
            "provider_calls": loaded.provider_calls,
            "paid_api_cost_usd": loaded.paid_api_cost_usd,
        },
        "atomic_issuance": {
            "admission_written_atomically": True,
            "recovered_from_exact_admission_without_issuance": recovered_exact_admission,
            "partial_admission_recovery_requires_exact_payload": True,
            "second_complete_issuance_fails_closed": True,
        },
        "immutable_bindings": [
            {
                "ref": str(AUTHORITY_REF).replace("\\", "/"),
                "sha256": _sha256(authority_path),
                "decision_digest": authority["decision_digest"],
            },
            {
                "ref": "scripts/releases/run_fin_ia_0_1_2_s4_t05_current_search.py",
                "sha256": _sha256(runner_path),
            },
            {
                "ref": str(issuer_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha256(issuer_path),
            },
        ],
        "observed_counts": {
            "new_admissions": 1,
            "admission_consumptions": 0,
            "source_network_calls": 0,
            "local_retrieval_or_tool_invocations": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "business_runs": 0,
            "business_artifacts": 0,
        },
        "stage_truth": {
            "S4_T05_B_DELL": "search_admission_issued_unconsumed",
            "DELL_current_R2": False,
            "MU_current_R2": False,
            "post_transfer_NVDA_R2": False,
        },
        "next_action": (
            "FIN-0.1.2-S4-T05-B-DELL-CURRENT-SEARCH-EXACT-LIVE-EXECUTION"
        ),
        "known_boundary": (
            "Issuance is not source live, current Evidence Pack, Agent exact input, "
            "DeepSeek execution, DELL R2, paired assessment, Owner acceptance, MU "
            "entry, release or production."
        ),
    }
    issuance["issuance_digest"] = canonical_digest(issuance)
    _write_json_atomic(issuance_output, issuance)
    readback = json.loads(issuance_output.read_text(encoding="utf-8"))
    observed_digest = str(readback.pop("issuance_digest"))
    _require(
        observed_digest == canonical_digest(readback),
        "t05_b_dell_search_issuance_readback_digest_mismatch",
    )
    return {**readback, "issuance_digest": observed_digest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission-output", type=Path, default=ROOT / ADMISSION_REF)
    parser.add_argument("--issuance-output", type=Path, default=ROOT / ISSUANCE_REF)
    parser.add_argument("--runtime-root", type=Path, default=ROOT / RUNTIME_ROOT_REF)
    args = parser.parse_args()
    try:
        result = issue(
            admission_output=args.admission_output.resolve(),
            issuance_output=args.issuance_output.resolve(),
            runtime_root=args.runtime_root.resolve(),
        )
    except (AdmissionIssuanceError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "code": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "admission_id": result["issued_admission"]["admission_id"],
                "admission_digest": result["issued_admission"]["admission_digest"],
                "issuance_digest": result["issuance_digest"],
                "consumed": result["issued_admission"]["consumed"],
                "source_network_calls": result["observed_counts"]["source_network_calls"],
                "model_calls": result["observed_counts"]["model_calls"],
                "runtime_root_absent": result["reserved_execution_boundary"][
                    "runtime_root_absent"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
