from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from threading import Barrier

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts" / "releases")]

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (  # noqa: E402
    SearchAdmission,
    compile_current_case_executable_requests,
)
from apps.workbench.backend.application.fin_0_1_3_shared_admission_guarded_search import (  # noqa: E402
    Fin013SharedAdmissionGuardedSearchRunner,
)
from run_fin_ia_0_1_2_s4_t05_current_search import ZeroCallIssuerTransport  # noqa: E402
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    detect_repo_relative_runtime_resource_literals,
    load_runtime_resource_registry,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_02_"
    "shared_runtime_admission_replay_and_historical_proof_debt_v1_0.json"
)
ACTIVE_SUITE_REF = Path(
    "configs/releases/fin_ia_0_1_3_repair_closeout_s0_02_"
    "active_test_suite_successor_v1_0.json"
)
SUCCESSOR_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_3_repair_closeout_"
    "runtime_resource_registry_v1_0.json"
)


def _load(ref: Path) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _sha(ref: Path) -> str:
    return hashlib.sha256((ROOT / ref).read_bytes()).hexdigest()


def _admission(case_key: str = "NVDA") -> SearchAdmission:
    now = datetime(2026, 8, 6, tzinfo=timezone.utc)
    requests = compile_current_case_executable_requests(case_key)
    return SearchAdmission.create(
        case_key=case_key,
        issued_at=(now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        request_digests=tuple(row.request_digest for row in requests),
    )


def test_shared_ledger_reservation_survives_reopen_and_blocks_crash_replay(
    tmp_path: Path,
) -> None:
    path = tmp_path / "shared-control-plane" / "admissions.sqlite3"
    admission = _admission()
    first = SharedAdmissionConsumptionLedger(path).reserve(
        admission_digest=admission.admission_digest,
        admission_id=admission.admission_id,
        scope="fin_0_1_3.test",
        run_id="run-a",
        attempt_id="attempt-a",
        runtime_identity="runtime-a",
        reserved_at="2026-08-06T00:00:00Z",
    )
    assert first.state == "reserved"
    with pytest.raises(
        SharedAdmissionLedgerError,
        match="shared_admission_already_consumed:reserved",
    ):
        SharedAdmissionConsumptionLedger(path).reserve(
            admission_digest=admission.admission_digest,
            admission_id=admission.admission_id,
            scope="fin_0_1_3.test",
            run_id="run-b",
            attempt_id="attempt-b",
            runtime_identity="runtime-b",
            reserved_at="2026-08-06T00:01:00Z",
        )


def test_concurrent_reservation_race_has_exactly_one_winner(tmp_path: Path) -> None:
    path = tmp_path / "shared-control-plane" / "admissions.sqlite3"
    admission = _admission()
    barrier = Barrier(2)

    def reserve(index: int) -> str:
        barrier.wait()
        try:
            return SharedAdmissionConsumptionLedger(path).reserve(
                admission_digest=admission.admission_digest,
                admission_id=admission.admission_id,
                scope="fin_0_1_3.concurrent_test",
                run_id=f"run-{index}",
                attempt_id=f"attempt-{index}",
                runtime_identity=f"runtime-{index}",
                reserved_at="2026-08-06T00:00:00Z",
            ).state
        except SharedAdmissionLedgerError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(reserve, (1, 2)))
    assert outcomes == ["reserved", "shared_admission_already_consumed:reserved"]


def test_current_guarded_runner_denies_same_admission_across_runtime_roots(
    tmp_path: Path,
) -> None:
    admission = _admission()
    ledger_path = tmp_path / "shared-control-plane" / "admissions.sqlite3"
    first_root = tmp_path / "runtime-a"
    second_root = tmp_path / "runtime-b"
    first = Fin013SharedAdmissionGuardedSearchRunner(
        repository_root=ROOT,
        runtime_root=first_root,
        transport=ZeroCallIssuerTransport("NVDA"),
        shared_admission_ledger=SharedAdmissionConsumptionLedger(ledger_path),
    ).execute(
        admission=admission,
        now="2026-08-06T00:00:00Z",
        run_nonce="s0-02-first-runtime",
    )
    assert first["status"] == "success"
    assert first["shared_admission_receipt"]["state"] == "terminal"
    assert first["shared_admission_receipt"]["terminal_result_digest"] == (
        first["terminal_object"]["digest"]
    )
    with pytest.raises(
        SharedAdmissionLedgerError,
        match="shared_admission_already_consumed:terminal",
    ):
        Fin013SharedAdmissionGuardedSearchRunner(
            repository_root=ROOT,
            runtime_root=second_root,
            transport=ZeroCallIssuerTransport("NVDA"),
            shared_admission_ledger=SharedAdmissionConsumptionLedger(ledger_path),
        ).execute(
            admission=admission,
            now="2026-08-06T00:00:00Z",
            run_nonce="s0-02-second-runtime",
        )
    assert ledger_path.is_relative_to(tmp_path / "shared-control-plane")
    assert not ledger_path.is_relative_to(first_root)
    assert not ledger_path.is_relative_to(second_root)


def test_current_guarded_runner_rejects_ledger_inside_disposable_runtime(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    with pytest.raises(
        ValueError,
        match="fin_0_1_3_shared_admission_ledger_inside_disposable_runtime",
    ):
        Fin013SharedAdmissionGuardedSearchRunner(
            repository_root=ROOT,
            runtime_root=runtime_root,
            transport=ZeroCallIssuerTransport("NVDA"),
            shared_admission_ledger=SharedAdmissionConsumptionLedger(
                runtime_root / "control-plane" / "admissions.sqlite3"
            ),
        )


def test_terminal_binding_and_receipt_digest_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.sqlite3"
    admission = _admission()
    ledger = SharedAdmissionConsumptionLedger(path)
    ledger.reserve(
        admission_digest=admission.admission_digest,
        admission_id=admission.admission_id,
        scope="fin_0_1_3.test",
        run_id="run-a",
        attempt_id="attempt-a",
        runtime_identity="runtime-a",
        reserved_at="2026-08-06T00:00:00Z",
    )
    with pytest.raises(
        SharedAdmissionLedgerError,
        match="shared_admission_execution_binding_mismatch",
    ):
        ledger.finalize(
            admission_digest=admission.admission_digest,
            run_id="run-b",
            attempt_id="attempt-a",
            terminal_status="failed",
            terminal_phase="preflight",
            terminal_code="mutation",
            terminal_result_digest="a" * 64,
            finalized_at="2026-08-06T00:02:00Z",
        )
    receipt = ledger.finalize(
        admission_digest=admission.admission_digest,
        run_id="run-a",
        attempt_id="attempt-a",
        terminal_status="success",
        terminal_phase="terminalize",
        terminal_code="complete",
        terminal_result_digest="b" * 64,
        finalized_at="2026-08-06T00:03:00Z",
    )
    assert receipt.state == "terminal"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE admission_consumptions SET terminal_code = 'tampered' "
            "WHERE admission_digest = ?",
            (admission.admission_digest,),
        )
    with pytest.raises(
        SharedAdmissionLedgerError,
        match="shared_admission_receipt_digest_mismatch",
    ):
        ledger.read(admission.admission_digest)


def test_candidate_revalidation_promotes_only_semantically_current_assets() -> None:
    decision = _load(DECISION_REF)
    rows = {row["ref"]: row for row in decision["candidate_revalidation"]}
    assert len(rows) == 8
    assert rows[
        "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_0.json"
    ]["disposition"] == "rejected_superseded_by_v1_1"
    assert rows[
        "configs/runtime/fin_ia_0_1_3_reference_role_registry_v1_1.json"
    ]["disposition"] == "reused_by_exact_digest"
    assert rows[
        "configs/runtime/fin_ia_0_1_3_runtime_resource_registry_v1_0.json"
    ]["disposition"] == "rejected_incomplete_then_successor_materialized"
    for ref, row in rows.items():
        assert row["sha256"] == _sha(Path(ref))


def test_successor_resource_registry_closes_detector_gap_without_rewriting_old() -> None:
    registry = load_runtime_resource_registry(ROOT, SUCCESSOR_REGISTRY_REF)
    assert len(registry.resources) == 31
    assert (
        "fin_0_1_2.s4.current_evidence_fact_candidate_pool_profiles"
        in registry.by_id()
    )
    detected = detect_repo_relative_runtime_resource_literals(ROOT, registry)
    assert len(detected) == 30
    assert set(detected).issubset(registry.by_path())
    decision = _load(DECISION_REF)
    assert decision["successor_runtime_resource_registry"]["sha256"] == _sha(
        Path(SUCCESSOR_REGISTRY_REF)
    )


def test_historical_proof_policy_keeps_old_receipts_immutable() -> None:
    decision = _load(DECISION_REF)
    policy = decision["historical_proof_policy"]
    assert policy["old_decisions_and_receipts_are_never_rewritten_to_match_today"] is True
    assert policy["one_time_fresh_issuance_tests_use_disposable_unconsumed_roots"] is True
    assert policy["fixed_consumed_runtime_root_is_not_a_replayable_test_fixture"] is True
    assert decision["observed_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "network_or_source_calls": 0,
        "business_runs": 0,
        "business_artifacts": 0,
        "historical_receipts_rewritten": 0,
    }


def test_decision_and_active_suite_are_digest_bound_and_do_not_promote_old_names() -> None:
    decision = _load(DECISION_REF)
    assert decision["decision_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "decision_digest"}
    )
    for binding in decision["source_bindings"]:
        assert binding["sha256"] == _sha(Path(binding["ref"]))
    assert decision["root_cause_disposition"] == {
        "RC-P36-115": "closed_by_current_mandatory_shared_exact_once_ledger",
        "RC-P36-128": "closed_by_historical_receipt_role_and_disposable_issuance_policy",
        "new_product_or_research_pass_created": False,
    }
    suite = _load(ACTIVE_SUITE_REF)
    assert suite["suite_digest"] == canonical_digest(
        {key: value for key, value in suite.items() if key != "suite_digest"}
    )
    assert suite["decision_sha256"] == _sha(DECISION_REF)
    assert len(suite["selected_tests"]) == 2
    assert suite["historical_FIN_0_1_3_test_names_establish_current_authority"] is False
    assert decision["next_action"] == (
        "FIN-0.1.3-013-S0-03-FINANCIAL-SEMANTIC-TRUTH-ORACLE-CLASSIFICATION"
    )
