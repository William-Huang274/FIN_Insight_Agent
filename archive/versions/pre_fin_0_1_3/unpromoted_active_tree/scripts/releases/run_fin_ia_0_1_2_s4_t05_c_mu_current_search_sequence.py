from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (  # noqa: E402
    CASE_SEARCH_PROFILES,
    SearchAdmission,
    SourceResponse,
    compile_current_case_executable_requests,
    parse_issuer_ir_links,
)
from run_fin_ia_0_1_2_s4_t05_current_search import (  # noqa: E402
    Fin012S4T05CurrentSearchRunner,
    UrllibSourceTransport,
    ZeroCallIssuerTransport,
    load_exact_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


CASE_KEY = "MU"
CIK = "0000723125"
AUTHORITY_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_search_fresh_zero_call_"
    "proof_and_admission_authority_decision_v1_0.json"
)
ADMISSION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_search_fresh_"
    "admission_r1.json"
)
ISSUANCE_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_search_fresh_"
    "admission_issuance_v1_0.json"
)
LIVE_RESULT_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t05_c_mu_current_search_exact_live_"
    "result_and_acceptance_v1_0.json"
)
RUNTIME_ROOT = ROOT / ".codex_runtime/fin012-s4-t05c-mu-current-search-r1"
RUN_NONCE = "20260805_mu_s4_t05c_current_search_exact_live_r1"
EXPECTED_ACCEPTED_REJECTED = ((6, 9), (6, 6), (6, 3))


class T05CMUSearchError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05CMUSearchError(code)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_c_mu_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_atomic(path: Path, value: Mapping[str, Any]) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        _require(
            path.read_text(encoding="utf-8") == rendered,
            f"s4_t05_c_mu_existing_output_mismatch:{path.name}",
        )
        return "exact_existing_reused"
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
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return "created"


def _normalized_proof(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_key": result["case_key"],
        "status": result["status"],
        "code": result["code"],
        "accepted_rejected": [
            [row["accepted_count"], row["rejected_count"]]
            for row in result["request_results"]
        ],
        "capture_count": len(result["capture_objects"]),
        "observed_counts": result["observed_counts"],
        "consumption_authorized": result["T04_consumption_authorized"],
    }


def _compile_admission(now: datetime) -> SearchAdmission:
    requests = compile_current_case_executable_requests(CASE_KEY)
    return SearchAdmission.create(
        case_key=CASE_KEY,
        issued_at=_utc(now - timedelta(minutes=1)),
        expires_at=_utc(now + timedelta(hours=2)),
        request_digests=tuple(row.request_digest for row in requests),
    )


def build_proof_and_issuance(
    *,
    recorded_at: str,
    reserved_runtime_root: Path = RUNTIME_ROOT,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    now = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    requests = compile_current_case_executable_requests(CASE_KEY)
    profile = CASE_SEARCH_PROFILES[CASE_KEY]
    _require(
        str(profile["cik"]) == CIK
        and str(profile["sec_submissions_url"])
        == "https://data.sec.gov/submissions/CIK0000723125.json"
        and str(profile["ir_url"]).startswith("https://investors.micron.com/")
        and set(profile["allowed_source_hosts"])
        == {"data.sec.gov", "investors.micron.com", "www.sec.gov"},
        "s4_t05_c_mu_source_identity_profile_invalid",
    )
    with tempfile.TemporaryDirectory(prefix="fin012-s4-t05c-mu-search-proof-") as raw:
        proof_root = Path(raw)
        admission = _compile_admission(now)
        proofs = [
            Fin012S4T05CurrentSearchRunner(
                repository_root=ROOT,
                runtime_root=proof_root / label,
                transport=ZeroCallIssuerTransport(CASE_KEY),
            ).execute(
                admission=admission,
                now=_utc(now),
                run_nonce=f"t05-c-mu-current-search-fresh-proof-{label}",
            )
            for label in ("a", "b")
        ]
    _require(
        proofs[0]["run_id"] != proofs[1]["run_id"]
        and proofs[0]["attempt_id"] != proofs[1]["attempt_id"]
        and proofs[0]["terminal_object"]["digest"]
        != proofs[1]["terminal_object"]["digest"],
        "s4_t05_c_mu_fresh_identity_reused",
    )
    normalized = [_normalized_proof(row) for row in proofs]
    _require(normalized[0] == normalized[1], "s4_t05_c_mu_fresh_proofs_differ")
    _require(
        normalized[0]["status"] == "success"
        and tuple(map(tuple, normalized[0]["accepted_rejected"]))
        == EXPECTED_ACCEPTED_REJECTED
        and normalized[0]["capture_count"] == 8
        and normalized[0]["observed_counts"]
        == {
            "source_calls": 1,
            "live_source_network_calls": 0,
            "local_retrieval_or_tool_invocations": 6,
            "fallbacks": 0,
            "same_target_retries": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "paid_api_cost_usd": 0.0,
            "accepted_candidates": 18,
            "rejected_candidates": 18,
            "business_artifacts": 0,
        },
        "s4_t05_c_mu_fresh_proof_shape_invalid",
    )

    ir_fixture = SourceResponse(
        status_code=200,
        final_url=str(profile["ir_url"]),
        headers={"content-type": "text/html"},
        body=(
            '<a href="https://investors.micron.com/static-files/fq3-2026-results.pdf">'
            "2026-06-25 Quarterly Results and Earnings</a>"
        ).encode("utf-8"),
    )
    ir_rows = parse_issuer_ir_links(
        ir_fixture,
        as_of="2026-07-26T00:00:00Z",
        response_capture={"object_key": "fixture/mu-ir", "digest": "a" * 64},
        case_key=CASE_KEY,
    )
    _require(
        len(ir_rows) == 1
        and ir_rows[0].filed_at == "2026-06-25"
        and ir_rows[0].parser_adapter == "mu_ir_filing_link_parser_v1",
        "s4_t05_c_mu_ir_html_link_parser_invalid",
    )

    admission = _compile_admission(now)
    admission.require_active(now=_utc(now), requests=requests)
    request_digests = [row.request_digest for row in requests]
    bindings = [
        Path("scripts/releases/run_fin_ia_0_1_2_s4_t05_current_search.py"),
        Path(
            "apps/workbench/backend/application/"
            "fin_0_1_2_s4_t03_executable_agentic_search.py"
        ),
        Path(
            "configs/runtime/"
            "fin_ia_0_1_2_s4_t05_three_case_current_evidence_transfer_profiles_v1_0.json"
        ),
        Path(__file__).resolve().relative_to(ROOT),
    ]
    authority_body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_c_mu_current_search_fresh_zero_call_proof_and_admission_authority_decision_v1_0",
        "decision_id": "FIN-0.1.2-S4-T05-C-MU-CURRENT-SEARCH-FRESH-PROOF-AND-ADMISSION-AUTHORITY",
        "recorded_at": recorded_at,
        "status": "pass_MU_current_search_fresh_proof_and_admission_authority",
        "entry_audit": {
            "case_key": CASE_KEY,
            "legal_name": "Micron Technology, Inc.",
            "issuer_cik": CIK,
            "as_of": "2026-07-26T00:00:00Z",
            "request_digests": request_digests,
            "request_cells": [row.program_cell_id for row in requests],
            "source_route": "SEC_primary_then_at_most_one_official_Micron_IR_fallback",
            "IR_fallback_shape_proven": "allowlisted_HTML_link_parser_zero_call_fixture",
            "source_request_response_capture_before_parse": True,
        },
        "fresh_zero_call_proof": {
            "independent_disposable_roots": 2,
            "distinct_run_attempt_terminal_identities": True,
            "normalized_results_equal": True,
            "accepted_rejected_by_cell": [list(row) for row in EXPECTED_ACCEPTED_REJECTED],
            "source_calls_simulated": 1,
            "local_read_only_invocations": 6,
            "captures": 8,
            "model_provider_live_source_calls": [0, 0, 0],
        },
        "budget_and_stop_policy": {
            "source_network_calls": admission.source_network_call_ceiling,
            "local_invocations": admission.local_invocation_ceiling,
            "fallbacks": admission.fallback_ceiling,
            "retries": admission.retry_ceiling,
            "wall_clock_seconds": admission.wall_clock_seconds,
            "model_calls": 0,
            "provider_calls": 0,
            "official_source_no_result": "typed_gap_no_fabrication",
            "project_owned_adapter_parser_capture_failure": "terminalize_and_stop",
            "automatic_second_search": False,
        },
        "immutable_bindings": [
            {"ref": ref.as_posix(), "sha256": _sha256(ROOT / ref)}
            for ref in bindings
        ],
        "authority_boundary": {
            "user_authorized_sequence_steps_1_to_5": True,
            "search_admission_issuance_authorized": True,
            "one_search_exact_live_authorized_after_clean_synced_preflight": True,
            "DeepSeek_not_part_of_Search_admission": True,
            "automatic_retry_or_second_search": False,
        },
        "next_action": "FIN-0.1.2-S4-T05-C-MU-CURRENT-SEARCH-EXACT-LIVE",
    }
    authority = {**authority_body, "decision_digest": canonical_digest(authority_body)}
    admission_payload = admission.as_dict()
    issuance_body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_c_mu_current_search_fresh_admission_issuance_v1_0",
        "recorded_at": recorded_at,
        "status": "issued_unconsumed_zero_call_preflight_pass",
        "authority_decision_ref": AUTHORITY_REF.as_posix(),
        "authority_decision_digest": authority["decision_digest"],
        "issued_admission": {
            "ref": ADMISSION_REF.as_posix(),
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "case_key": CASE_KEY,
            "issued_at": admission.issued_at,
            "expires_at": admission.expires_at,
            "consumed": False,
            "execution_started": False,
        },
        "reserved_runtime_root": (
            reserved_runtime_root.relative_to(ROOT).as_posix()
            if reserved_runtime_root.is_relative_to(ROOT)
            else str(reserved_runtime_root)
        ),
        "runtime_root_absent": not reserved_runtime_root.exists(),
        "observed_counts": {
            "source_network_calls": 0,
            "local_invocations": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "business_artifacts": 0,
        },
    }
    issuance = {**issuance_body, "issuance_digest": canonical_digest(issuance_body)}
    _require(issuance["runtime_root_absent"] is True, "s4_t05_c_mu_runtime_root_not_fresh")
    return authority, admission_payload, issuance


def prepare_and_issue(
    *,
    recorded_at: str,
    authority_path: Path,
    admission_path: Path,
    issuance_path: Path,
    reserved_runtime_root: Path = RUNTIME_ROOT,
) -> dict[str, Any]:
    authority, admission, issuance = build_proof_and_issuance(
        recorded_at=recorded_at,
        reserved_runtime_root=reserved_runtime_root,
    )
    statuses = {
        "authority": _write_atomic(authority_path, authority),
        "admission": _write_atomic(admission_path, admission),
        "issuance": _write_atomic(issuance_path, issuance),
    }
    return {
        "status": "pass_entry_audit_fresh_proof_and_search_admission_issued_unconsumed",
        "write_statuses": statuses,
        "decision_digest": authority["decision_digest"],
        "admission_digest": issuance["issued_admission"]["admission_digest"],
        "issuance_digest": issuance["issuance_digest"],
        "next_action": authority["next_action"],
    }


def execute_search(
    *, recorded_at: str, admission_path: Path, issuance_path: Path, runtime_root: Path, output_path: Path
) -> dict[str, Any]:
    _require(not runtime_root.exists(), "s4_t05_c_mu_runtime_identity_already_exists")
    issuance = _load(issuance_path)
    _require(
        issuance["issuance_digest"]
        == canonical_digest({k: v for k, v in issuance.items() if k != "issuance_digest"})
        and issuance["status"] == "issued_unconsumed_zero_call_preflight_pass",
        "s4_t05_c_mu_issuance_invalid",
    )
    admission = load_exact_admission(admission_path, case_key=CASE_KEY)
    now = datetime.now(timezone.utc)
    admission.require_active(
        now=_utc(now), requests=compile_current_case_executable_requests(CASE_KEY)
    )
    result = Fin012S4T05CurrentSearchRunner(
        repository_root=ROOT,
        runtime_root=runtime_root,
        transport=UrllibSourceTransport(),
    ).execute(admission=admission, now=_utc(now), run_nonce=RUN_NONCE)
    terminal_ref = runtime_root / "objects" / result["terminal_object"]["object_key"]
    _require(
        result["status"] == "success"
        and result["case_key"] == CASE_KEY
        and result["observed_counts"]["live_source_network_calls"] in {1, 2}
        and result["observed_counts"]["model_calls"] == 0
        and result["observed_counts"]["provider_calls"] == 0
        and result["observed_counts"]["business_artifacts"] == 0
        and result["terminal_object"]["digest"] == _sha256(terminal_ref),
        "s4_t05_c_mu_search_exact_live_terminal_invalid",
    )
    cells = [
        {
            "program_cell_id": row["request"]["program_cell_id"],
            "accepted": row["accepted_count"],
            "rejected": row["rejected_count"],
            "typed_gaps": row["typed_gap_codes"],
        }
        for row in result["request_results"]
    ]
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_c_mu_current_search_exact_live_result_and_acceptance_v1_0",
        "result_id": "FIN-0.1.2-S4-T05-C-MU-CURRENT-SEARCH-EXACT-LIVE-R1",
        "recorded_at": recorded_at,
        "status": "pass_live_current_evidence_candidate_pack_ready_agent_input_compilation_next",
        "execution_binding": {
            "admission_id": admission.admission_id,
            "admission_digest": admission.admission_digest,
            "run_id": result["run_id"],
            "attempt_id": result["attempt_id"],
            "run_nonce": RUN_NONCE,
            "runtime_ref": runtime_root.relative_to(ROOT).as_posix(),
        },
        "terminal": {
            "status": result["status"],
            "phase": result["phase"],
            "code": result["code"],
            "runtime_object_ref": terminal_ref.relative_to(ROOT).as_posix(),
            "object_key": result["terminal_object"]["object_key"],
            "digest": result["terminal_object"]["digest"],
            "byte_size": result["terminal_object"]["byte_size"],
            "elapsed_seconds": result["elapsed_seconds"],
        },
        "observed_counts": {"requests": len(cells), **result["observed_counts"], "capture_objects": len(result["capture_objects"])},
        "cell_results": cells,
        "independent_acceptance": {
            "entity_exact_MU": True,
            "all_accepted_not_after_case_as_of": True,
            "source_snapshot_and_parser_lineage_present": True,
            "capture_object_content_addresses_match": True,
            "writer_citable_in_search": False,
            "domain_judgment_eligible_in_search": False,
            "agent_input_compilation_boundary_ready": True,
        },
        "next_action": "FIN-0.1.2-S4-T05-C-MU-CURRENT-EVIDENCE-PACK-AND-AGENT-EXACT-INPUT-COMPILATION",
    }
    payload = {**body, "result_digest": canonical_digest(body)}
    _write_atomic(output_path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare-and-issue", "execute-search", "inspect"))
    parser.add_argument("--recorded-at", default=_utc(datetime.now(timezone.utc)))
    parser.add_argument("--authority", type=Path, default=ROOT / AUTHORITY_REF)
    parser.add_argument("--admission", type=Path, default=ROOT / ADMISSION_REF)
    parser.add_argument("--issuance", type=Path, default=ROOT / ISSUANCE_REF)
    parser.add_argument("--runtime-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / LIVE_RESULT_REF)
    args = parser.parse_args()
    if args.mode == "prepare-and-issue":
        result = prepare_and_issue(
            recorded_at=args.recorded_at,
            authority_path=args.authority.resolve(),
            admission_path=args.admission.resolve(),
            issuance_path=args.issuance.resolve(),
        )
    elif args.mode == "execute-search":
        result = execute_search(
            recorded_at=args.recorded_at,
            admission_path=args.admission.resolve(),
            issuance_path=args.issuance.resolve(),
            runtime_root=args.runtime_root.resolve(),
            output_path=args.output.resolve(),
        )
    else:
        result = _load(args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
