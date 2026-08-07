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
    CandidateGenerationInterrupted,
    CONTRACT_REF as CANDIDATE_CONTRACT_REF,
    load_source_catalog,
    run_candidate_generation,
)
from sec_agent.s1_08_official_discovery_adapter import CaptureFirstOfficialDiscoveryAdapter
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_08_dell_r2_search_admission_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s1_08_dell_r2_search_terminal_v1_0"
CONTRACT_REF = "fin_0_1_3.S1_08.DELL_current_search_R2:v1"
TERMINAL_NAMESPACE = "fin-0.1.3/s1-08/dell-current-search-r2"
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


class S108R2SuccessorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DellSearchR2Admission:
    schema_version: str
    contract_ref: str
    admission_id: str
    admission_digest: str
    authority_decision_digest: str
    independent_proof_digest: str
    independent_proof_sha256: str
    r1_terminal_digest: str
    catalog_digest: str
    implementation_commit: str
    run_nonce: str
    issued_at: str
    expires_at: str
    network_call_ceiling: int
    document_ceiling_per_query: int
    retry_ceiling: int
    model_call_ceiling: int
    provider_model_call_ceiling: int
    per_call_timeout_seconds: int
    overall_timeout_seconds: int

    @classmethod
    def issue(
        cls,
        *,
        authority_decision: Mapping[str, Any],
        independent_proof: Mapping[str, Any],
        independent_proof_sha256: str,
        r1_result: Mapping[str, Any],
        catalog: Mapping[str, Any],
        implementation_commit: str,
        run_nonce: str,
        issued_at: str,
        expires_at: str,
    ) -> "DellSearchR2Admission":
        _validate_authority_sources(
            authority_decision=authority_decision,
            independent_proof=independent_proof,
            independent_proof_sha256=independent_proof_sha256,
            r1_result=r1_result,
        )
        authority = authority_decision["replacement_authority"]
        body = {
            "schema_version": ADMISSION_SCHEMA,
            "contract_ref": CONTRACT_REF,
            "authority_decision_digest": canonical_digest(authority_decision),
            "independent_proof_digest": canonical_digest(independent_proof),
            "independent_proof_sha256": independent_proof_sha256,
            "r1_terminal_digest": str(r1_result["result"]["terminal_digest"]),
            "catalog_digest": canonical_digest(catalog),
            "implementation_commit": implementation_commit,
            "run_nonce": run_nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "network_call_ceiling": int(authority["network_calls_max"]),
            "document_ceiling_per_query": int(authority["document_ceiling_per_query"]),
            "retry_ceiling": int(authority["retry_calls"]),
            "model_call_ceiling": int(authority["model_calls"]),
            "provider_model_call_ceiling": int(authority["provider_model_calls"]),
            "per_call_timeout_seconds": int(authority["per_call_timeout_seconds_max"]),
            "overall_timeout_seconds": int(authority["overall_timeout_seconds_max"]),
        }
        digest = canonical_digest(body)
        return cls(
            **body,
            admission_id=f"fin013_s1_08_dell_r2_admission_{digest[:20]}",
            admission_digest=digest,
        )

    def require_active(
        self,
        *,
        authority_decision: Mapping[str, Any],
        independent_proof: Mapping[str, Any],
        independent_proof_sha256: str,
        r1_result: Mapping[str, Any],
        catalog: Mapping[str, Any],
        observed_at: str,
        implementation_commit: str,
    ) -> None:
        _validate_authority_sources(
            authority_decision=authority_decision,
            independent_proof=independent_proof,
            independent_proof_sha256=independent_proof_sha256,
            r1_result=r1_result,
        )
        body = self.as_dict()
        body.pop("admission_id")
        body.pop("admission_digest")
        valid = (
            self.schema_version == ADMISSION_SCHEMA
            and self.contract_ref == CONTRACT_REF
            and self.admission_digest == canonical_digest(body)
            and self.admission_id
            == f"fin013_s1_08_dell_r2_admission_{self.admission_digest[:20]}"
            and self.authority_decision_digest == canonical_digest(authority_decision)
            and self.independent_proof_digest == canonical_digest(independent_proof)
            and self.independent_proof_sha256 == independent_proof_sha256
            and self.r1_terminal_digest == str(r1_result["result"]["terminal_digest"])
            and self.catalog_digest == canonical_digest(catalog)
            and self.implementation_commit == implementation_commit
            and self.network_call_ceiling == 16
            and self.document_ceiling_per_query == 1
            and self.retry_ceiling == 0
            and self.model_call_ceiling == 0
            and self.provider_model_call_ceiling == 0
            and self.per_call_timeout_seconds == 30
            and self.overall_timeout_seconds == 300
        )
        if not valid:
            raise S108R2SuccessorError("s1_08_dell_r2_admission_invalid")
        observed = _time(observed_at)
        if not _time(self.issued_at) <= observed <= _time(self.expires_at):
            raise S108R2SuccessorError("s1_08_dell_r2_admission_not_active")

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
            raise S108R2SuccessorError("s1_08_dell_r2_live_transport_required")
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
            raise S108R2SuccessorError("s1_08_dell_r2_overall_timeout_exceeded")
        bounded_timeout = min(timeout_seconds, max(1, math.ceil(remaining)))
        return self._delegate.fetch(
            url=url,
            headers=dict(headers),
            allowed_hosts=allowed_hosts,
            timeout_seconds=bounded_timeout,
            byte_ceiling=byte_ceiling,
        )


def execute_dell_search_r2(
    *,
    admission: DellSearchR2Admission,
    authority_decision: Mapping[str, Any],
    independent_proof: Mapping[str, Any],
    independent_proof_sha256: str,
    r1_result: Mapping[str, Any],
    catalog_path: str | Path,
    runtime_root: str | Path,
    shared_admission_ledger: SharedAdmissionConsumptionLedger,
    transport: SourceTransport,
    implementation_commit: str,
    research_objective: str,
    observed_at: str,
    market_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = load_source_catalog(catalog_path)
    admission.require_active(
        authority_decision=authority_decision,
        independent_proof=independent_proof,
        independent_proof_sha256=independent_proof_sha256,
        r1_result=r1_result,
        catalog=catalog,
        observed_at=observed_at,
        implementation_commit=implementation_commit,
    )
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not _EMAIL_RE.fullmatch(contact):
        raise S108R2SuccessorError("s1_08_dell_r2_sec_contact_identity_required")
    runtime_path = Path(runtime_root).resolve()
    if shared_admission_ledger.path == runtime_path or shared_admission_ledger.path.is_relative_to(
        runtime_path
    ):
        raise S108R2SuccessorError("s1_08_dell_r2_shared_ledger_inside_runtime")
    bounded_transport = _OverallDeadlineTransport(
        delegate=transport,
        overall_timeout_seconds=admission.overall_timeout_seconds,
    )
    run_body = {
        "contract_ref": CONTRACT_REF,
        "admission_digest": admission.admission_digest,
        "authority_decision_digest": admission.authority_decision_digest,
        "independent_proof_digest": admission.independent_proof_digest,
        "r1_terminal_digest": admission.r1_terminal_digest,
        "case_key": "DELL",
        "attempt_label": "R2",
        "run_nonce": admission.run_nonce,
        "implementation_commit": implementation_commit,
    }
    run_digest = canonical_digest(run_body)
    run_id = f"fin013_s1_08_dell_r2_run_{run_digest[:20]}"
    attempt_id = f"fin013_s1_08_dell_r2_attempt_{canonical_digest({'run': run_id})[:20]}"
    shared_admission_ledger.reserve(
        admission_digest=admission.admission_digest,
        admission_id=admission.admission_id,
        scope=CONTRACT_REF,
        run_id=run_id,
        attempt_id=attempt_id,
        runtime_identity=str(runtime_path),
        reserved_at=observed_at,
    )
    store = FileCanonicalObjectStore(runtime_path / "terminal-objects")
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
            document_ceiling_per_query=admission.document_ceiling_per_query,
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
            "dell_current_search_r2_complete"
            if not candidate_result["typed_gaps"]
            else "dell_current_search_r2_complete_with_typed_gaps"
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
        "attempt_label": "R2",
        "admission_id": admission.admission_id,
        "admission_digest": admission.admission_digest,
        "authority_decision_digest": admission.authority_decision_digest,
        "independent_proof_digest": admission.independent_proof_digest,
        "r1_terminal_digest": admission.r1_terminal_digest,
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
        artifact_type="dell_current_search_r2_terminal",
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


def _validate_authority_sources(
    *,
    authority_decision: Mapping[str, Any],
    independent_proof: Mapping[str, Any],
    independent_proof_sha256: str,
    r1_result: Mapping[str, Any],
) -> None:
    authority = authority_decision.get("replacement_authority") or {}
    proof_decision = independent_proof.get("decision") or {}
    r1_terminal = r1_result.get("result") or {}
    expected_proof_sha = str(
        (authority_decision.get("basis") or {}).get("independent_proof_sha256") or ""
    )
    engineering_proof = independent_proof.get("source_engineering_proof") or {}
    r1_body = dict(r1_terminal)
    r1_digest = str(r1_body.pop("terminal_digest", ""))
    r1_body.pop("terminal_object", None)
    r1_body.pop("shared_admission_receipt", None)
    valid = (
        authority_decision.get("schema_version")
        == "fin_ia_0_1_3_s1_08q_h_dell_r2_replacement_authority_decision_v1_1"
        and authority_decision.get("decision_status")
        == "approved_successor_entrypoint_required_before_issuance"
        and authority.get("case_key") == "DELL"
        and authority.get("attempt_label") == "R2"
        and authority.get("maximum_fresh_admissions") == 1
        and authority.get("maximum_exact_live_executions") == 1
        and independent_proof.get("status") == "independent_fresh_zero_call_proof_pass"
        and proof_decision.get("S1_08Q_A_to_G_engineering") == "independently_proven"
        and engineering_proof.get("sha256")
        == (authority_decision.get("basis") or {}).get("engineering_proof_sha256")
        and expected_proof_sha == independent_proof_sha256
        and len(independent_proof_sha256) == 64
        and r1_result.get("status") == "failed"
        and r1_terminal.get("status") == "failed"
        and r1_terminal.get("case_key") == "DELL"
        and r1_digest == canonical_digest(r1_body)
        and r1_digest
        == "9a52845388f09a72e84bc12969bb90389964409481a360eee78c28cf9562d57b"
    )
    if not valid:
        raise S108R2SuccessorError("s1_08_dell_r2_authority_source_invalid")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "ADMISSION_SCHEMA",
    "CONTRACT_REF",
    "DellSearchR2Admission",
    "S108R2SuccessorError",
    "TERMINAL_NAMESPACE",
    "TERMINAL_SCHEMA",
    "execute_dell_search_r2",
    "sha256_file",
]
