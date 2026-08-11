from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import SourceTransport
from sec_agent.s1_08_candidate_generation_runtime import (
    CandidateGenerationInterrupted,
    CONTRACT_REF as CANDIDATE_CONTRACT_REF,
    load_source_catalog,
    run_candidate_generation,
)
from sec_agent.s1_08_official_discovery_adapter import (
    CaptureFirstOfficialDiscoveryAdapter,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s1_08_dell_current_search_canary_admission_v2_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s1_08_dell_current_search_canary_terminal_v2_0"
CANARY_CONTRACT_REF = "fin_0_1_3.S1_08.DELL_current_search_canary:v2"
TERMINAL_NAMESPACE = "fin-0.1.3/s1-08/dell-current-search-canary"
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


class S108LiveCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class DellSearchCanaryAdmission:
    schema_version: str
    contract_ref: str
    admission_id: str
    admission_digest: str
    catalog_digest: str
    implementation_commit: str
    run_nonce: str
    issued_at: str
    expires_at: str
    network_call_ceiling: int
    document_ceiling_per_query: int
    retry_ceiling: int
    model_call_ceiling: int

    @classmethod
    def issue(
        cls,
        *,
        catalog: Mapping[str, Any],
        implementation_commit: str,
        run_nonce: str,
        issued_at: str,
        expires_at: str,
        network_call_ceiling: int = 16,
        document_ceiling_per_query: int = 1,
    ) -> "DellSearchCanaryAdmission":
        body = {
            "schema_version": ADMISSION_SCHEMA,
            "contract_ref": CANARY_CONTRACT_REF,
            "catalog_digest": canonical_digest(catalog),
            "implementation_commit": implementation_commit,
            "run_nonce": run_nonce,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "network_call_ceiling": int(network_call_ceiling),
            "document_ceiling_per_query": int(document_ceiling_per_query),
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
        }
        digest = canonical_digest(body)
        return cls(
            **body,
            admission_id=f"fin013_s1_08_dell_search_admission_{digest[:20]}",
            admission_digest=digest,
        )

    def require_active(
        self, *, catalog: Mapping[str, Any], observed_at: str, implementation_commit: str
    ) -> None:
        body = self.as_dict()
        body.pop("admission_id")
        body.pop("admission_digest")
        if (
            self.schema_version != ADMISSION_SCHEMA
            or self.contract_ref != CANARY_CONTRACT_REF
            or self.admission_digest != canonical_digest(body)
            or self.admission_id != f"fin013_s1_08_dell_search_admission_{self.admission_digest[:20]}"
            or self.catalog_digest != canonical_digest(catalog)
            or self.implementation_commit != implementation_commit
            or self.retry_ceiling != 0
            or self.model_call_ceiling != 0
            or not 1 <= self.network_call_ceiling <= 16
            or self.document_ceiling_per_query != 1
        ):
            raise S108LiveCanaryError("s1_08_dell_canary_admission_invalid")
        observed = _time(observed_at)
        if not _time(self.issued_at) <= observed <= _time(self.expires_at):
            raise S108LiveCanaryError("s1_08_dell_canary_admission_not_active")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_ref": self.contract_ref,
            "admission_id": self.admission_id,
            "admission_digest": self.admission_digest,
            "catalog_digest": self.catalog_digest,
            "implementation_commit": self.implementation_commit,
            "run_nonce": self.run_nonce,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "network_call_ceiling": self.network_call_ceiling,
            "document_ceiling_per_query": self.document_ceiling_per_query,
            "retry_ceiling": self.retry_ceiling,
            "model_call_ceiling": self.model_call_ceiling,
        }


def execute_dell_search_canary(
    *,
    admission: DellSearchCanaryAdmission,
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
        catalog=catalog,
        observed_at=observed_at,
        implementation_commit=implementation_commit,
    )
    if transport.live_network is not True:
        raise S108LiveCanaryError("s1_08_dell_canary_live_transport_required")
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not _EMAIL_RE.fullmatch(contact):
        raise S108LiveCanaryError("s1_08_dell_canary_sec_contact_identity_required")
    runtime_path = Path(runtime_root).resolve()
    if shared_admission_ledger.path == runtime_path or shared_admission_ledger.path.is_relative_to(runtime_path):
        raise S108LiveCanaryError("s1_08_dell_canary_shared_ledger_inside_runtime")
    run_body = {
        "contract_ref": CANARY_CONTRACT_REF,
        "admission_digest": admission.admission_digest,
        "case_key": "DELL",
        "run_nonce": admission.run_nonce,
        "implementation_commit": implementation_commit,
    }
    run_digest = canonical_digest(run_body)
    run_id = f"fin013_s1_08_dell_search_run_{run_digest[:20]}"
    attempt_id = f"fin013_s1_08_dell_search_attempt_{canonical_digest({'run': run_id})[:20]}"
    shared_admission_ledger.reserve(
        admission_digest=admission.admission_digest,
        admission_id=admission.admission_id,
        scope=CANARY_CONTRACT_REF,
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
            transport=transport,
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
            "dell_current_search_candidate_run_complete"
            if not candidate_result["typed_gaps"]
            else "dell_current_search_candidate_run_complete_with_typed_gaps"
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
        "contract_ref": CANARY_CONTRACT_REF,
        "candidate_contract_ref": CANDIDATE_CONTRACT_REF,
        "run_id": run_id,
        "run_digest": run_digest,
        "attempt_id": attempt_id,
        "admission_id": admission.admission_id,
        "admission_digest": admission.admission_digest,
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
        artifact_type="dell_current_search_canary_terminal",
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
    return {**terminal, "terminal_object": terminal_ref, "shared_admission_receipt": shared_receipt}


def load_admission(path: str | Path) -> DellSearchCanaryAdmission:
    return DellSearchCanaryAdmission(**json.loads(Path(path).read_text(encoding="utf-8")))


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "ADMISSION_SCHEMA",
    "CANARY_CONTRACT_REF",
    "DellSearchCanaryAdmission",
    "S108LiveCanaryError",
    "execute_dell_search_canary",
    "load_admission",
]
