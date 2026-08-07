from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.official_source_attempt_program import SourceResponse
from sec_agent.s1_08_candidate_generation_runtime import CONTRACT_REF_V3, load_source_catalog
from sec_agent.s1_08_r3_successor import (
    CONTRACT_REF,
    DellSearchR3Admission,
    R3AuthorityInputs,
    S108R3SuccessorError,
    SUCCESSOR_PREFLIGHT_SCHEMA,
    execute_dell_search_r3,
    project_os_preflight_passed,
    sha256_file,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_relationship_budget_policy_v3_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_fresh_live_authority_decision_v1_0.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_clean_independent_zero_call_proof_result_v1_0.json"
R2_RESULT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_result_v1_0.json"
R2_QUALITY_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_current_search_r2_source_quality_evaluation_v1_0.json"
RUNTIME_PATH = ROOT / "src/sec_agent/s1_08_r3_successor.py"
RUNNER_PATH = ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_v3_dell_current_search_r3.py"
OLD_R2_RUNTIME_PATH = ROOT / "src/sec_agent/s1_08_r2_successor.py"
OLD_R2_RUNNER_PATH = ROOT / "scripts/releases/run_fin_ia_0_1_3_s1_08_dell_current_search_r2.py"
OLD_R2_PREFLIGHT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_r2_successor_clean_zero_call_preflight_v1_1.json"
COMMIT = "c" * 40
ISSUED = "2026-08-08T08:00:00Z"
EXPIRES = "2026-08-08T09:00:00Z"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bindings() -> dict[str, str]:
    proof = _load(PROOF_PATH)
    expected = dict(proof["source_bindings"]["implementation_files"])
    assert {ref: sha256_file(ROOT / ref) for ref in expected} == expected
    return expected


def _bound_inputs(
    *,
    decision: dict | None = None,
    proof: dict | None = None,
    r2_result: dict | None = None,
    r2_quality: dict | None = None,
    catalog: dict | None = None,
) -> R3AuthorityInputs:
    return R3AuthorityInputs(
        authority_decision=decision or _load(DECISION_PATH),
        authority_decision_sha256=sha256_file(DECISION_PATH),
        v3_proof=proof or _load(PROOF_PATH),
        v3_proof_sha256=sha256_file(PROOF_PATH),
        r2_result=r2_result or _load(R2_RESULT_PATH),
        r2_result_sha256=sha256_file(R2_RESULT_PATH),
        r2_quality_evaluation=r2_quality or _load(R2_QUALITY_PATH),
        r2_quality_evaluation_sha256=sha256_file(R2_QUALITY_PATH),
        catalog=catalog or load_source_catalog(CATALOG_PATH),
        catalog_sha256=sha256_file(CATALOG_PATH),
        v3_implementation_source_sha256=_bindings(),
    )


def _preflight(
    *,
    decision: dict | None = None,
    proof: dict | None = None,
    r2_result: dict | None = None,
    r2_quality: dict | None = None,
    catalog: dict | None = None,
) -> dict:
    decision = decision or _load(DECISION_PATH)
    proof = proof or _load(PROOF_PATH)
    r2_result = r2_result or _load(R2_RESULT_PATH)
    r2_quality = r2_quality or _load(R2_QUALITY_PATH)
    catalog = catalog or load_source_catalog(CATALOG_PATH)
    bindings = _bindings()
    return {
        "schema_version": SUCCESSOR_PREFLIGHT_SCHEMA,
        "status": "pass",
        "source_commit": COMMIT,
        "project_os_preflight": {"status": "pass"},
        "source_files": {
            "runtime_sha256": sha256_file(RUNTIME_PATH),
            "runner_sha256": sha256_file(RUNNER_PATH),
        },
        "authority_bindings": {
            "authority_decision_sha256": sha256_file(DECISION_PATH),
            "v3_proof_sha256": sha256_file(PROOF_PATH),
            "r2_result_sha256": sha256_file(R2_RESULT_PATH),
            "r2_quality_evaluation_sha256": sha256_file(R2_QUALITY_PATH),
            "catalog_sha256": sha256_file(CATALOG_PATH),
            "v3_implementation_binding_digest": canonical_digest(bindings),
            "authority_decision_digest": canonical_digest(decision),
            "v3_proof_digest": canonical_digest(proof),
            "r2_result_digest": canonical_digest(r2_result),
            "r2_quality_evaluation_digest": canonical_digest(r2_quality),
            "catalog_digest": canonical_digest(catalog),
        },
        "verification": {
            "clean_git_archive": True,
            "fresh_python_process": True,
            "tests_passed": 1,
            "tests_failed": 0,
            "tests_skipped": 0,
            "external_calls": 0,
            "admissions_issued": 0,
        },
    }


def _admission() -> DellSearchR3Admission:
    return DellSearchR3Admission.issue(
        bound_inputs=_bound_inputs(),
        successor_preflight=_preflight(),
        successor_runtime_sha256=sha256_file(RUNTIME_PATH),
        successor_runner_sha256=sha256_file(RUNNER_PATH),
        implementation_commit=COMMIT,
        run_nonce="test-dell-r3",
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )


class _EmptyOfficialTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append((url, timeout_seconds))
        if "data.sec.gov/submissions" in url:
            entity = next(
                row
                for row in load_source_catalog(CATALOG_PATH)["entities"]
                if url in row["official_landing_pages"]
            )
            body = json.dumps(
                {
                    "cik": entity["cik"],
                    "filings": {
                        "recent": {
                            "accessionNumber": [],
                            "filingDate": [],
                            "form": [],
                            "primaryDocument": [],
                        }
                    },
                }
            ).encode()
            content_type = "application/json"
        else:
            body = b"<html><body>No matching current official document links.</body></html>"
            content_type = "text/html"
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


class _NonLiveTransport:
    live_network = False

    def fetch(self, **kwargs):  # pragma: no cover - validation must reject first
        raise AssertionError("non-live transport must never fetch")


def _execute(tmp_path: Path, monkeypatch, *, ledger=None, transport=None):
    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "operator@example.com")
    admission = _admission()
    ledger = ledger or SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    transport = transport or _EmptyOfficialTransport()
    result = execute_dell_search_r3(
        admission=admission,
        bound_inputs=_bound_inputs(),
        catalog_path=CATALOG_PATH,
        successor_preflight=_preflight(),
        successor_runtime_sha256=sha256_file(RUNTIME_PATH),
        successor_runner_sha256=sha256_file(RUNNER_PATH),
        runtime_root=tmp_path / "runtime",
        shared_admission_ledger=ledger,
        transport=transport,
        implementation_commit=COMMIT,
        research_objective="Evaluate Dell current AI infrastructure evidence.",
        observed_at="2026-08-08T08:30:00Z",
        market_snapshot={"ticker": "DELL", "as_of": "2026-08-06", "context_only": True},
    )
    return admission, ledger, transport, result


def test_R3_admission_binds_decision_R2_v3_sources_and_budget_without_secret() -> None:
    admission = _admission()
    admission.require_active(
        bound_inputs=_bound_inputs(),
        successor_preflight=_preflight(),
        successor_runtime_sha256=sha256_file(RUNTIME_PATH),
        successor_runner_sha256=sha256_file(RUNNER_PATH),
        implementation_commit=COMMIT,
        observed_at="2026-08-08T08:30:00Z",
    )
    assert admission.contract_ref == CONTRACT_REF
    assert admission.network_call_ceiling == 16
    assert admission.maximum_document_fetches_per_attempt == 2
    assert admission.maximum_accepted_unique_documents_per_attempt == 1
    assert admission.model_call_ceiling == 0
    assert admission.retry_ceiling == 0
    assert "@" not in json.dumps(admission.as_dict())


def test_R3_admission_or_bound_source_mutation_fails_closed(
    tmp_path, monkeypatch
) -> None:
    mutated = _load(R2_QUALITY_PATH)
    mutated["observed_counts"]["network_calls"] = 15
    with pytest.raises(S108R3SuccessorError) as exc:
        DellSearchR3Admission.issue(
            bound_inputs=_bound_inputs(r2_quality=mutated),
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            implementation_commit=COMMIT,
            run_nonce="mutated-r2-quality",
            issued_at=ISSUED,
            expires_at=EXPIRES,
        )
    assert exc.value.code == "s1_08_dell_r3_successor_preflight_invalid"

    with pytest.raises(S108R3SuccessorError) as exc:
        replace(_admission(), catalog_sha256="0" * 64).require_active(
            bound_inputs=_bound_inputs(),
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            implementation_commit=COMMIT,
            observed_at="2026-08-08T08:30:00Z",
        )
    assert exc.value.code == "s1_08_dell_r3_admission_invalid"

    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "operator@example.com")
    drifted_catalog_path = tmp_path / "catalog-with-byte-drift.json"
    drifted_catalog_path.write_text(
        CATALOG_PATH.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    with pytest.raises(S108R3SuccessorError) as exc:
        execute_dell_search_r3(
            admission=_admission(),
            bound_inputs=_bound_inputs(),
            catalog_path=drifted_catalog_path,
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            runtime_root=tmp_path / "runtime",
            shared_admission_ledger=ledger,
            transport=_EmptyOfficialTransport(),
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell current AI infrastructure evidence.",
            observed_at="2026-08-08T08:30:00Z",
        )
    assert exc.value.code == "s1_08_dell_r3_catalog_file_binding_invalid"
    with pytest.raises(SharedAdmissionLedgerError):
        ledger.read(_admission().admission_digest)


def test_R3_successor_preflight_source_drift_fails_before_issuance() -> None:
    preflight = _preflight()
    preflight["source_files"]["runner_sha256"] = "0" * 64
    with pytest.raises(S108R3SuccessorError) as exc:
        DellSearchR3Admission.issue(
            bound_inputs=_bound_inputs(),
            successor_preflight=preflight,
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            implementation_commit=COMMIT,
            run_nonce="drifted-preflight",
            issued_at=ISSUED,
            expires_at=EXPIRES,
        )
    assert exc.value.code == "s1_08_dell_r3_successor_preflight_invalid"


def test_missing_contact_stops_before_R3_ledger_consumption(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FINSIGHT_SEC_CONTACT_EMAIL", raising=False)
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    transport = _EmptyOfficialTransport()
    with pytest.raises(S108R3SuccessorError) as exc:
        execute_dell_search_r3(
            admission=admission,
            bound_inputs=_bound_inputs(),
            catalog_path=CATALOG_PATH,
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            runtime_root=tmp_path / "runtime",
            shared_admission_ledger=ledger,
            transport=transport,
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell current AI infrastructure evidence.",
            observed_at="2026-08-08T08:30:00Z",
        )
    assert exc.value.code == "s1_08_dell_r3_sec_contact_identity_required"
    assert transport.calls == []
    with pytest.raises(SharedAdmissionLedgerError):
        ledger.read(admission.admission_digest)


def test_non_live_transport_stops_before_R3_ledger_consumption(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FINSIGHT_SEC_CONTACT_EMAIL", "operator@example.com")
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared/ledger.sqlite")
    with pytest.raises(S108R3SuccessorError) as exc:
        execute_dell_search_r3(
            admission=admission,
            bound_inputs=_bound_inputs(),
            catalog_path=CATALOG_PATH,
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            runtime_root=tmp_path / "runtime",
            shared_admission_ledger=ledger,
            transport=_NonLiveTransport(),
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell current AI infrastructure evidence.",
            observed_at="2026-08-08T08:30:00Z",
        )
    assert exc.value.code == "s1_08_dell_r3_live_transport_required"
    with pytest.raises(SharedAdmissionLedgerError):
        ledger.read(admission.admission_digest)


def test_R3_exact_once_terminal_uses_v3_candidate_contract_and_fair_scheduler(
    tmp_path, monkeypatch
) -> None:
    admission, ledger, transport, result = _execute(tmp_path, monkeypatch)
    assert result["status"] == "complete"
    assert result["attempt_label"] == "R3"
    assert result["candidate_contract_ref"] == CONTRACT_REF_V3
    assert result["candidate_result"]["slot_budget_summary"]["slot_starvation_count"] == 0
    assert result["observed_counts"]["network_calls"] == len(transport.calls)
    assert result["observed_counts"]["network_calls"] <= 16
    assert all(timeout <= 30 for _, timeout in transport.calls)
    assert result["shared_admission_receipt"]["state"] == "terminal"
    assert result["ranking_admitted"] is False
    with pytest.raises(SharedAdmissionLedgerError):
        execute_dell_search_r3(
            admission=admission,
            bound_inputs=_bound_inputs(),
            catalog_path=CATALOG_PATH,
            successor_preflight=_preflight(),
            successor_runtime_sha256=sha256_file(RUNTIME_PATH),
            successor_runner_sha256=sha256_file(RUNNER_PATH),
            runtime_root=tmp_path / "runtime-2",
            shared_admission_ledger=ledger,
            transport=_EmptyOfficialTransport(),
            implementation_commit=COMMIT,
            research_objective="Evaluate Dell current AI infrastructure evidence.",
            observed_at="2026-08-08T08:31:00Z",
        )


def test_R3_runner_is_zero_call_until_explicit_main_and_cannot_reuse_R2(
    monkeypatch,
) -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_result_v1_0.json" in source
    assert "S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AND_EXECUTION" in source
    assert "current_source_catalog_relationship_budget_policy_v3_0.json" in source
    assert "current_source_catalog_and_query_revision_policy_v2_0.json" not in source
    assert "successor_clean_zero_call_preflight_v1_0.json" in source
    assert "socket.getaddrinfo" not in source
    assert 'if __name__ == "__main__"' in source
    assert "implementation_commit=proven_source_commit" in source
    assert not (ROOT / "configs/releases/fin_ia_0_1_3_s1_08_v3_dell_current_search_r3_result_v1_0.json").exists()

    spec = importlib.util.spec_from_file_location("r3_runner_contract_test", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    proven = "1" * 40
    execution = "2" * 40

    def clean_runtime_tree(*args):
        if args[0] == "merge-base":
            return ""
        if args[0] == "diff":
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git", clean_runtime_tree)
    runner._assert_proven_source_ancestry_and_runtime_tree(
        proven_source_commit=proven,
        execution_commit=execution,
    )

    def drifted_runtime_tree(*args):
        if args[0] == "merge-base":
            return ""
        if args[0] == "diff":
            return "src/sec_agent/shared_admission_ledger.py"
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git", drifted_runtime_tree)
    with pytest.raises(SystemExit, match="Runtime tree drift"):
        runner._assert_proven_source_ancestry_and_runtime_tree(
            proven_source_commit=proven,
            execution_commit=execution,
        )

    def unrelated_execution_commit(*args):
        if args[0] == "merge-base":
            raise subprocess.CalledProcessError(1, args)
        raise AssertionError(args)

    monkeypatch.setattr(runner, "_git", unrelated_execution_commit)
    with pytest.raises(SystemExit, match="must descend"):
        runner._assert_proven_source_ancestry_and_runtime_tree(
            proven_source_commit=proven,
            execution_commit=execution,
        )

    old_preflight = _load(OLD_R2_PREFLIGHT_PATH)
    assert sha256_file(OLD_R2_RUNTIME_PATH) == old_preflight["source_files"]["runtime_sha256"]
    assert sha256_file(OLD_R2_RUNNER_PATH) == old_preflight["source_files"]["runner_sha256"]
    assert _load(DECISION_PATH)["issuance_state"]["old_R2_reuse_forbidden"] is True
    assert project_os_preflight_passed(
        {"status": "pass", "open_full_chain_blockers": []}
    )
    assert not project_os_preflight_passed(
        {"status": "pass", "open_full_chain_blockers": [{"issue_id": "blocked"}]}
    )
