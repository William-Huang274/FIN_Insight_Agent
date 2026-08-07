from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import SourceResponse, SourceTransport
from sec_agent.s1_08_candidate_generation_runtime import (
    CATALOG_SCHEMA_V3,
    CONTRACT_REF_V3 as CANDIDATE_CONTRACT_REF,
    CandidateGenerationInterrupted,
    load_source_catalog,
    run_candidate_generation,
)
from sec_agent.s1_08_official_discovery_adapter import CaptureFirstOfficialDiscoveryAdapter
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_08_dell_r3_search_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s1_08_dell_r3_search_terminal_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.DELL_current_search_R3:v1"
TERMINAL_NAMESPACE = "fin-0.1.3/s1-08/dell-current-search-r3"
SUCCESSOR_PREFLIGHT_SCHEMA = (
    "fin_ia_0_1_3_s1_08_v3_dell_r3_successor_clean_zero_call_preflight_v1_0"
)
_DECISION_SCHEMA = (
    "fin_ia_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision_v1_0"
)
_PROOF_SCHEMA = (
    "fin_ia_0_1_3_s1_08_v3_clean_independent_zero_call_proof_result_v1_0"
)
_R2_RESULT_SCHEMA = "fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0"
_R2_QUALITY_SCHEMA = (
    "fin_ia_0_1_3_s1_08_dell_current_search_r2_source_quality_evaluation_v1_0"
)
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
_EXPECTED_RESERVATIONS = {
    "issuer_and_regulatory_shared": 4,
    "customer_demand": 4,
    "supply_and_counterevidence": 5,
    "market_context": 0,
    "shared_contingency_after_first_round": 3,
}


class S108R3SuccessorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class R3AuthorityInputs:
    authority_decision: Mapping[str, Any]
    authority_decision_sha256: str
    v3_proof: Mapping[str, Any]
    v3_proof_sha256: str
    r2_result: Mapping[str, Any]
    r2_result_sha256: str
    r2_quality_evaluation: Mapping[str, Any]
    r2_quality_evaluation_sha256: str
    catalog: Mapping[str, Any]
    catalog_sha256: str
    v3_implementation_source_sha256: Mapping[str, str]

    @property
    def v3_implementation_binding_digest(self) -> str:
        return canonical_digest(dict(self.v3_implementation_source_sha256))


@dataclass(frozen=True)
class DellSearchR3Admission:
    schema_version: str
    contract_ref: str
    admission_id: str
    admission_digest: str
    authority_decision_digest: str
    authority_decision_sha256: str
    v3_proof_digest: str
    v3_proof_sha256: str
    r2_terminal_digest: str
    r2_result_sha256: str
    r2_quality_evaluation_digest: str
    r2_quality_evaluation_sha256: str
    catalog_digest: str
    catalog_sha256: str
    v3_implementation_binding_digest: str
    successor_preflight_digest: str
    successor_runtime_sha256: str
    successor_runner_sha256: str
    implementation_commit: str
    run_nonce: str
    issued_at: str
    expires_at: str
    network_call_ceiling: int
    maximum_document_fetches_per_attempt: int
    maximum_accepted_unique_documents_per_attempt: int
    slot_group_reservation_digest: str
    retry_ceiling: int
    model_call_ceiling: int
    provider_model_call_ceiling: int
    per_call_timeout_seconds: int
    overall_timeout_seconds: int

    @classmethod
    def issue(
        cls,
        *,
        bound_inputs: R3AuthorityInputs,
        successor_preflight: Mapping[str, Any],
        successor_runtime_sha256: str,
        successor_runner_sha256: str,
        implementation_commit: str,
        run_nonce: str,
        issued_at: str,
        expires_at: str,
    ) -> "DellSearchR3Admission":
        _validate_authority_sources(bound_inputs)
        _validate_successor_preflight(
            successor_preflight=successor_preflight,
            successor_runtime_sha256=successor_runtime_sha256,
            successor_runner_sha256=successor_runner_sha256,
            bound_inputs=bound_inputs,
            implementation_commit=implementation_commit,
        )
        authority = bound_inputs.authority_decision["replacement_authority"]
        reservations = dict(authority["slot_group_reservations"])
        r2_terminal = bound_inputs.r2_result["result"]
        body = {
            "schema_version": ADMISSION_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "authority_decision_digest": canonical_digest(bound_inputs.authority_decision),
            "authority_decision_sha256": bound_inputs.authority_decision_sha256,
            "v3_proof_digest": canonical_digest(bound_inputs.v3_proof),
            "v3_proof_sha256": bound_inputs.v3_proof_sha256,
            "r2_terminal_digest": str(r2_terminal["terminal_digest"]),
            "r2_result_sha256": bound_inputs.r2_result_sha256,
            "r2_quality_evaluation_digest": canonical_digest(
                bound_inputs.r2_quality_evaluation
            ),
            "r2_quality_evaluation_sha256": bound_inputs.r2_quality_evaluation_sha256,
            "catalog_digest": canonical_digest(bound_inputs.catalog),
            "catalog_sha256": bound_inputs.catalog_sha256,
            "v3_implementation_binding_digest": (
                bound_inputs.v3_implementation_binding_digest
            ),
            "successor_preflight_digest": canonical_digest(successor_preflight),
            "successor_runtime_sha256": successor_runtime_sha256,
            "successor_runner_sha256": successor_runner_sha256,
            "implementation_commit": implementation_commit,
            "run_nonce": run_nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "network_call_ceiling": int(authority["network_calls_max"]),
            "maximum_document_fetches_per_attempt": int(
                authority["maximum_document_fetches_per_attempt"]
            ),
            "maximum_accepted_unique_documents_per_attempt": int(
                authority["maximum_accepted_unique_documents_per_attempt"]
            ),
            "slot_group_reservation_digest": canonical_digest(reservations),
            "retry_ceiling": int(authority["retry_calls"]),
            "model_call_ceiling": int(authority["model_calls"]),
            "provider_model_call_ceiling": int(authority["provider_model_calls"]),
            "per_call_timeout_seconds": int(authority["per_call_timeout_seconds_max"]),
            "overall_timeout_seconds": int(authority["overall_timeout_seconds_max"]),
        }
        digest = canonical_digest(body)
        return cls(
            **body,
            admission_id=f"fin013_s1_08_dell_r3_admission_{digest[:20]}",
            admission_digest=digest,
        )

    def require_active(
        self,
        *,
        bound_inputs: R3AuthorityInputs,
        successor_preflight: Mapping[str, Any],
        successor_runtime_sha256: str,
        successor_runner_sha256: str,
        implementation_commit: str,
        observed_at: str,
    ) -> None:
        _validate_authority_sources(bound_inputs)
        _validate_successor_preflight(
            successor_preflight=successor_preflight,
            successor_runtime_sha256=successor_runtime_sha256,
            successor_runner_sha256=successor_runner_sha256,
            bound_inputs=bound_inputs,
            implementation_commit=implementation_commit,
        )
        authority = bound_inputs.authority_decision["replacement_authority"]
        body = self.as_dict()
        body.pop("admission_id")
        body.pop("admission_digest")
        valid = (
            self.schema_version == ADMISSION_SCHEMA
            and self.contract_ref == CONTRACT_REF
            and self.admission_digest == canonical_digest(body)
            and self.admission_id
            == f"fin013_s1_08_dell_r3_admission_{self.admission_digest[:20]}"
            and self.authority_decision_digest
            == canonical_digest(bound_inputs.authority_decision)
            and self.authority_decision_sha256
            == bound_inputs.authority_decision_sha256
            and self.v3_proof_digest == canonical_digest(bound_inputs.v3_proof)
            and self.v3_proof_sha256 == bound_inputs.v3_proof_sha256
            and self.r2_terminal_digest
            == str(bound_inputs.r2_result["result"]["terminal_digest"])
            and self.r2_result_sha256 == bound_inputs.r2_result_sha256
            and self.r2_quality_evaluation_digest
            == canonical_digest(bound_inputs.r2_quality_evaluation)
            and self.r2_quality_evaluation_sha256
            == bound_inputs.r2_quality_evaluation_sha256
            and self.catalog_digest == canonical_digest(bound_inputs.catalog)
            and self.catalog_sha256 == bound_inputs.catalog_sha256
            and self.v3_implementation_binding_digest
            == bound_inputs.v3_implementation_binding_digest
            and self.successor_preflight_digest == canonical_digest(successor_preflight)
            and self.successor_runtime_sha256 == successor_runtime_sha256
            and self.successor_runner_sha256 == successor_runner_sha256
            and self.implementation_commit == implementation_commit
            and self.network_call_ceiling == 16
            and self.maximum_document_fetches_per_attempt == 2
            and self.maximum_accepted_unique_documents_per_attempt == 1
            and self.slot_group_reservation_digest
            == canonical_digest(authority["slot_group_reservations"])
            and self.retry_ceiling == 0
            and self.model_call_ceiling == 0
            and self.provider_model_call_ceiling == 0
            and self.per_call_timeout_seconds == 30
            and self.overall_timeout_seconds == 300
        )
        if not valid:
            raise S108R3SuccessorError("s1_08_dell_r3_admission_invalid")
        observed = _time(observed_at)
        if not _time(self.issued_at) <= observed <= _time(self.expires_at):
            raise S108R3SuccessorError("s1_08_dell_r3_admission_not_active")

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class _OverallDeadlineTransport:
    live_network = True

    def __init__(
        self,
        *,
        delegate: SourceTransport,
        overall_timeout_seconds: int,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if delegate.live_network is not True:
            raise S108R3SuccessorError("s1_08_dell_r3_live_transport_required")
        self._delegate = delegate
        self._monotonic = monotonic
        self._deadline = monotonic() + overall_timeout_seconds

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        remaining = self._deadline - self._monotonic()
        if remaining <= 0:
            raise S108R3SuccessorError("s1_08_dell_r3_overall_timeout_exceeded")
        return self._delegate.fetch(
            url=url,
            headers=dict(headers),
            allowed_hosts=allowed_hosts,
            timeout_seconds=min(timeout_seconds, max(1, math.ceil(remaining))),
            byte_ceiling=byte_ceiling,
        )


def execute_dell_search_r3(
    *,
    admission: DellSearchR3Admission,
    bound_inputs: R3AuthorityInputs,
    catalog_path: str | Path,
    successor_preflight: Mapping[str, Any],
    successor_runtime_sha256: str,
    successor_runner_sha256: str,
    runtime_root: str | Path,
    shared_admission_ledger: SharedAdmissionConsumptionLedger,
    transport: SourceTransport,
    implementation_commit: str,
    research_objective: str,
    observed_at: str,
    market_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_catalog_path = Path(catalog_path)
    catalog = load_source_catalog(resolved_catalog_path)
    if (
        sha256_file(resolved_catalog_path) != bound_inputs.catalog_sha256
        or canonical_digest(catalog) != canonical_digest(bound_inputs.catalog)
    ):
        raise S108R3SuccessorError("s1_08_dell_r3_catalog_file_binding_invalid")
    admission.require_active(
        bound_inputs=bound_inputs,
        successor_preflight=successor_preflight,
        successor_runtime_sha256=successor_runtime_sha256,
        successor_runner_sha256=successor_runner_sha256,
        implementation_commit=implementation_commit,
        observed_at=observed_at,
    )
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not _EMAIL_RE.fullmatch(contact):
        raise S108R3SuccessorError("s1_08_dell_r3_sec_contact_identity_required")
    runtime_path = Path(runtime_root).resolve()
    if shared_admission_ledger.path == runtime_path or shared_admission_ledger.path.is_relative_to(
        runtime_path
    ):
        raise S108R3SuccessorError("s1_08_dell_r3_shared_ledger_inside_runtime")
    bounded_transport = _OverallDeadlineTransport(
        delegate=transport,
        overall_timeout_seconds=admission.overall_timeout_seconds,
    )
    store = FileCanonicalObjectStore(runtime_path / "terminal-objects")

    run_body = {
        "contract_ref": CONTRACT_REF,
        "admission_digest": admission.admission_digest,
        "authority_decision_digest": admission.authority_decision_digest,
        "v3_proof_digest": admission.v3_proof_digest,
        "r2_terminal_digest": admission.r2_terminal_digest,
        "r2_quality_evaluation_digest": admission.r2_quality_evaluation_digest,
        "catalog_digest": admission.catalog_digest,
        "case_key": "DELL",
        "attempt_label": "R3",
        "run_nonce": admission.run_nonce,
        "implementation_commit": implementation_commit,
    }
    run_digest = canonical_digest(run_body)
    run_id = f"fin013_s1_08_dell_r3_run_{run_digest[:20]}"
    attempt_id = f"fin013_s1_08_dell_r3_attempt_{canonical_digest({'run': run_id})[:20]}"
    shared_admission_ledger.reserve(
        admission_digest=admission.admission_digest,
        admission_id=admission.admission_id,
        scope=CONTRACT_REF,
        run_id=run_id,
        attempt_id=attempt_id,
        runtime_identity=str(runtime_path),
        reserved_at=observed_at,
    )
    status = "failed"
    phase = "candidate_generation"
    code = "unclassified_failure"
    candidate_result: dict[str, Any] | None = None
    adapter: CaptureFirstOfficialDiscoveryAdapter | None = None
    try:
        adapter = CaptureFirstOfficialDiscoveryAdapter(
            catalog=catalog,
            case_key="DELL",
            runtime_root=runtime_path / "adapter",
            transport=bounded_transport,
            network_call_ceiling=admission.network_call_ceiling,
            document_ceiling_per_query=admission.maximum_document_fetches_per_attempt,
            market_snapshot=market_snapshot,
        )
        candidate_result = run_candidate_generation(
            catalog=catalog,
            case_key="DELL",
            research_objective=research_objective,
            adapter=adapter,
        )
        status = "complete"
        phase = "terminalize"
        code = (
            "dell_current_search_r3_complete"
            if not candidate_result["typed_gaps"]
            else "dell_current_search_r3_complete_with_typed_gaps"
        )
    except CandidateGenerationInterrupted as exc:
        candidate_result = dict(exc.partial_result)
        code = exc.code
    except Exception as exc:
        code = getattr(exc, "code", f"unexpected_project_failure:{type(exc).__name__}")
    completed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    observed_network_calls = int(
        ((candidate_result or {}).get("observed_counts") or {}).get(
            "network_calls", getattr(adapter, "network_calls", 0)
        )
    )
    body = {
        "schema_version": TERMINAL_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "candidate_contract_ref": CANDIDATE_CONTRACT_REF,
        "run_id": run_id,
        "run_digest": run_digest,
        "attempt_id": attempt_id,
        "attempt_label": "R3",
        "admission_id": admission.admission_id,
        "admission_digest": admission.admission_digest,
        "authority_decision_digest": admission.authority_decision_digest,
        "v3_proof_digest": admission.v3_proof_digest,
        "r2_terminal_digest": admission.r2_terminal_digest,
        "r2_quality_evaluation_digest": admission.r2_quality_evaluation_digest,
        "catalog_digest": admission.catalog_digest,
        "v3_implementation_binding_digest": admission.v3_implementation_binding_digest,
        "successor_preflight_digest": admission.successor_preflight_digest,
        "successor_runtime_sha256": admission.successor_runtime_sha256,
        "successor_runner_sha256": admission.successor_runner_sha256,
        "case_key": "DELL",
        "status": status,
        "phase": phase,
        "code": code,
        "candidate_result": candidate_result,
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "retry_calls": 0,
            "network_calls": observed_network_calls,
        },
        "completed_at": completed_at,
        "ranking_admitted": False,
    }
    terminal = {**body, "terminal_digest": canonical_digest(body)}
    terminal_ref = store.put_json(
        terminal,
        namespace=TERMINAL_NAMESPACE,
        artifact_type="dell_current_search_r3_terminal",
    )
    shared_receipt = shared_admission_ledger.finalize(
        admission_digest=admission.admission_digest,
        run_id=run_id,
        attempt_id=attempt_id,
        terminal_status=status,
        terminal_phase=phase,
        terminal_code=code,
        terminal_result_digest=terminal["terminal_digest"],
        finalized_at=completed_at,
    ).as_dict()
    return {
        **terminal,
        "terminal_object": terminal_ref,
        "shared_admission_receipt": shared_receipt,
    }


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project_os_preflight_passed(preflight: Mapping[str, Any]) -> bool:
    blockers = preflight.get("open_full_chain_blockers") or []
    count = preflight.get("open_full_chain_blocker_count")
    if count is None:
        count = len(blockers)
    return preflight.get("status") == "pass" and int(count) == 0 and not blockers


def _validate_successor_preflight(
    *,
    successor_preflight: Mapping[str, Any],
    successor_runtime_sha256: str,
    successor_runner_sha256: str,
    bound_inputs: R3AuthorityInputs,
    implementation_commit: str,
) -> None:
    sources = successor_preflight.get("source_files") or {}
    bindings = successor_preflight.get("authority_bindings") or {}
    verification = successor_preflight.get("verification") or {}
    valid = (
        successor_preflight.get("schema_version") == SUCCESSOR_PREFLIGHT_SCHEMA
        and successor_preflight.get("status") == "pass"
        and successor_preflight.get("source_commit") == implementation_commit
        and (successor_preflight.get("project_os_preflight") or {}).get("status") == "pass"
        and sources.get("runtime_sha256") == successor_runtime_sha256
        and sources.get("runner_sha256") == successor_runner_sha256
        and bindings.get("authority_decision_sha256")
        == bound_inputs.authority_decision_sha256
        and bindings.get("v3_proof_sha256") == bound_inputs.v3_proof_sha256
        and bindings.get("r2_result_sha256") == bound_inputs.r2_result_sha256
        and bindings.get("r2_quality_evaluation_sha256")
        == bound_inputs.r2_quality_evaluation_sha256
        and bindings.get("catalog_sha256") == bound_inputs.catalog_sha256
        and bindings.get("v3_implementation_binding_digest")
        == bound_inputs.v3_implementation_binding_digest
        and bindings.get("authority_decision_digest")
        == canonical_digest(bound_inputs.authority_decision)
        and bindings.get("v3_proof_digest") == canonical_digest(bound_inputs.v3_proof)
        and bindings.get("r2_result_digest") == canonical_digest(bound_inputs.r2_result)
        and bindings.get("r2_quality_evaluation_digest")
        == canonical_digest(bound_inputs.r2_quality_evaluation)
        and bindings.get("catalog_digest") == canonical_digest(bound_inputs.catalog)
        and verification.get("clean_git_archive") is True
        and verification.get("fresh_python_process") is True
        and int(verification.get("tests_passed") or 0) > 0
        and int(verification.get("tests_failed") or 0) == 0
        and int(verification.get("tests_skipped") or 0) == 0
        and verification.get("external_calls") == 0
        and verification.get("admissions_issued") == 0
        and all(
            len(value) == 64
            for value in (successor_runtime_sha256, successor_runner_sha256)
        )
    )
    if not valid:
        raise S108R3SuccessorError("s1_08_dell_r3_successor_preflight_invalid")


def _validate_authority_sources(bound_inputs: R3AuthorityInputs) -> None:
    authority_decision = bound_inputs.authority_decision
    authority_decision_sha256 = bound_inputs.authority_decision_sha256
    v3_proof = bound_inputs.v3_proof
    v3_proof_sha256 = bound_inputs.v3_proof_sha256
    r2_result = bound_inputs.r2_result
    r2_result_sha256 = bound_inputs.r2_result_sha256
    r2_quality_evaluation = bound_inputs.r2_quality_evaluation
    r2_quality_evaluation_sha256 = bound_inputs.r2_quality_evaluation_sha256
    catalog = bound_inputs.catalog
    catalog_sha256 = bound_inputs.catalog_sha256
    v3_implementation_source_sha256 = bound_inputs.v3_implementation_source_sha256
    basis = authority_decision.get("immutable_basis") or {}
    authority = authority_decision.get("replacement_authority") or {}
    issuance = authority_decision.get("issuance_state") or {}
    r2_basis = basis.get("DELL_R2_terminal") or {}
    proof_basis = basis.get("v3_engineering_proof") or {}
    catalog_basis = basis.get("v3_catalog") or {}
    r2_terminal = r2_result.get("result") or {}
    r2_body = dict(r2_terminal)
    r2_digest = str(r2_body.pop("terminal_digest", ""))
    r2_body.pop("terminal_object", None)
    r2_body.pop("shared_admission_receipt", None)
    proof_bindings = (v3_proof.get("source_bindings") or {}).get(
        "implementation_files"
    ) or {}
    catalog_budgets = catalog.get("budgets") or {}
    valid = (
        authority_decision.get("schema_version") == _DECISION_SCHEMA
        and authority_decision.get("decision_status")
        == "approved_successor_entrypoint_required_before_issuance"
        and authority.get("case_key") == "DELL"
        and authority.get("attempt_label") == "R3"
        and authority.get("maximum_fresh_admissions") == 1
        and authority.get("maximum_exact_live_executions") == 1
        and authority.get("network_calls_max") == 16
        and authority.get("maximum_document_fetches_per_attempt") == 2
        and authority.get("maximum_accepted_unique_documents_per_attempt") == 1
        and authority.get("slot_group_reservations") == _EXPECTED_RESERVATIONS
        and authority.get("model_calls") == 0
        and authority.get("provider_model_calls") == 0
        and authority.get("retry_calls") == 0
        and authority.get("automatic_R4") is False
        and issuance.get("currently_issuable") is False
        and issuance.get("old_R2_reuse_forbidden") is True
        and len(authority_decision_sha256) == 64
        and v3_proof.get("schema_version") == _PROOF_SCHEMA
        and v3_proof.get("status")
        == "pass_two_clean_archives_two_fresh_processes_zero_call_reproducible"
        and (v3_proof.get("acceptance_boundary") or {}).get(
            "S1_08_v3_deterministic_engineering"
        )
        == "independently_proven"
        and v3_proof_sha256 == proof_basis.get("sha256")
        and r2_result.get("schema_version") == _R2_RESULT_SCHEMA
        and r2_result.get("status") == "complete"
        and r2_terminal.get("attempt_label") == "R2"
        and r2_terminal.get("status") == "complete"
        and r2_digest == canonical_digest(r2_body)
        and r2_result_sha256 == r2_basis.get("result_sha256")
        and r2_quality_evaluation.get("schema_version") == _R2_QUALITY_SCHEMA
        and r2_quality_evaluation.get("status")
        == "live_execution_complete_product_source_quality_failed"
        and (r2_quality_evaluation.get("source_result") or {}).get("sha256")
        == r2_result_sha256
        and (r2_quality_evaluation.get("source_result") or {}).get(
            "terminal_digest"
        )
        == r2_digest
        and (r2_quality_evaluation.get("decision") or {}).get(
            "automatic_R3"
        )
        is False
        and r2_quality_evaluation_sha256
        == r2_basis.get("quality_evaluation_sha256")
        and catalog.get("schema_version") == CATALOG_SCHEMA_V3
        and catalog.get("contract_ref") == CANDIDATE_CONTRACT_REF
        and catalog_sha256 == catalog_basis.get("sha256")
        and catalog_budgets.get("replacement_network_call_ceiling") == 16
        and catalog_budgets.get("maximum_document_fetches_per_attempt") == 2
        and catalog_budgets.get("maximum_accepted_unique_documents_per_attempt") == 1
        and catalog_budgets.get("slot_group_reservations") == _EXPECTED_RESERVATIONS
        and dict(v3_implementation_source_sha256) == proof_bindings
        and len(v3_implementation_source_sha256) >= 6
        and all(len(value) == 64 for value in v3_implementation_source_sha256.values())
    )
    if not valid:
        raise S108R3SuccessorError("s1_08_dell_r3_authority_source_invalid")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "ADMISSION_SCHEMA",
    "CONTRACT_REF",
    "DellSearchR3Admission",
    "R3AuthorityInputs",
    "S108R3SuccessorError",
    "SUCCESSOR_PREFLIGHT_SCHEMA",
    "TERMINAL_NAMESPACE",
    "TERMINAL_SCHEMA",
    "execute_dell_search_r3",
    "project_os_preflight_passed",
    "sha256_file",
]
