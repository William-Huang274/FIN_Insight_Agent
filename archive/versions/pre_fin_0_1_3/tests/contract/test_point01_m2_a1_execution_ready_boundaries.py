"""Contract tests for the M2-A1 v2 execution-ready harness.

These tests intentionally use synthetic immutable terminal projections.  They
exercise admission, receipt, instrumentation, oracle and reviewer-gate
contracts without invoking the M2 compiler/shadow runtime.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import socket
import sqlite3
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m2_a1_audit_canary import (
    M2A1AuditCanary,
    M2A1ModelAdmissionError,
    M2A1OracleLeakageError,
    M2A1StoreAccessError,
    M2A1TransportAccessError,
)
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.m2_a1_audit_harness import (
    M2A1ActualExecutionNotAdmitted,
    M2A1ActualRunner,
)
from sec_agent.canonical_runtime.m2_a1_audit_oracle import evaluate_independent_oracle
from sec_agent.canonical_runtime.m2_a1_audit_result import (
    M2A1ActualCellProjection,
    M2A1ArtifactReplayProjection,
    M2A1ImmutableActualResult,
    M2A1PackLineageProjection,
    M2A1SemanticLossProjection,
)
from sec_agent.canonical_runtime.m2_a1_audit_reviewer_gate import review_future_actual
from sec_agent.canonical_runtime.m2_a1_execution_receipt import (
    M2A1ExecutionPreflightError,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    preflight_exact_execution,
)
from sec_agent.canonical_runtime import m2_a1_execution_receipt as receipt_module


PACKAGE_DIGEST = "a" * 64
AUTHORITY_BOUNDARY = "temporary_sqlite_only_no_fixed_store_or_network"
PACKAGE = {
    "package_ref": "point01-m2-a1-execution-ready-adversarial-audit-package-v2",
    "package_digest": PACKAGE_DIGEST,
    "scope": "M2_A1_exact_admission_gated_future_actual_only",
    "authority_boundary": AUTHORITY_BOUNDARY,
    "execution_mode": "external_admission_gated",
}
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_3"
SCENARIO_ID = "p01-baseline-separated-input"
PREFLIGHT_DIGEST = "f" * 64


def _admission() -> M2A1ExternalPackageAdmission:
    return M2A1ExternalPackageAdmission.create(
        admission_ref="point01-m2-a1-total-reviewer-execution-ready-package-admission:v1",
        admission_id="m2-a1-test-admission",
        admission_version=1,
        reviewer_identity="william/003/total_reviewer",
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        authority_boundary=AUTHORITY_BOUNDARY,
        execution_staging_namespace_id=NAMESPACE_ID,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )


def _receipt(admission: M2A1ExternalPackageAdmission) -> M2A1ExecutionReceipt:
    return M2A1ExecutionReceipt.create(
        receipt_id="m2-a1-test-receipt",
        receipt_version=1,
        approval_id="m2-a1-test-approval",
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        admission_digest=admission.admission_digest,
        nonce_sha256=hashlib.sha256(b"test nonce only").hexdigest(),
        expires_at=admission.expires_at,
        reviewer_identity=admission.reviewer_identity,
        execution_staging_namespace_id=NAMESPACE_ID,
        scenario_id=SCENARIO_ID,
    )


def _canary_counts(**overrides: int) -> dict[str, object]:
    counts = {
        "oracle_path_resolution_attempt_count": 0,
        "oracle_read_attempt_count": 0,
        "oracle_hash_attempt_count": 0,
        "oracle_import_attempt_count": 0,
        "store_open_attempt_count": 0,
        "store_open_success_count": 0,
        "store_read_open_count": 0,
        "store_write_open_count": 0,
        "object_store_constructor_attempt_count": 0,
        "object_store_constructor_success_count": 0,
        "ambient_resolution_attempt_count": 0,
        "provider_constructor_attempt_count": 0,
        "transport_module_loaded_count": 0,
        "preloaded_transport_alias_count": 0,
        "network_transport_constructor_attempt_count": 0,
        "transport_constructor_attempt_count": 0,
        "tool_transport_constructor_attempt_count": 0,
        "network_request_attempt_count": 0,
        "network_request_success_count": 0,
        "socket_connect_attempt_count": 0,
        "http_client_connect_attempt_count": 0,
        "preloaded_transport_module_attempt_count": 0,
        "feature_flag_read_count": 0,
        "admission_lookup_count": 0,
        "model_constructor_attempt_count": 0,
    }
    counts.update(overrides)
    return {"counts": counts, "events": [], "instrumentation_active": False}


def _baseline_result() -> M2A1ImmutableActualResult:
    required = (
        ("ai-demand", "fundamental_analyst", ("issuer_metric",)),
        ("ai-supply", "product_industry_analyst", ("issuer_metric", "relationship_signal")),
        ("ai-margin", "fundamental_analyst", ("issuer_metric",)),
        ("ai-counterevidence", "risk_counterevidence_analyst", ("issuer_metric",)),
    )
    filler = tuple((f"ai-fixture-{index}", "fundamental_analyst", ("issuer_metric",)) for index in range(1, 7))
    cells = tuple(
        M2A1ActualCellProjection(
            cell_key=key,
            owner_role=owner,
            evidence_roles=roles,
            forbidden_substitutions=("commercial_proxy_as_exact_fact",),
            acceptance_roles=("primary_or_bounded_context",),
        )
        for key, owner, roles in required + filler
    )
    return M2A1ImmutableActualResult.terminalize(
        execution_scope="synthetic_unit_only",
        scenario_id="p01-baseline-separated-input",
        case_id="m2-a1-ai-semis-input",
        executable_package_digest=PACKAGE_DIGEST,
        admission_digest="b" * 64,
        consumed_receipt_digest="c" * 64,
        actual_status="succeeded",
        pack_lineage=M2A1PackLineageProjection(
            selection_digest="selection-v1",
            resolution_digest="resolution-v1",
            registry_snapshot_digest="registry-v1",
            selected_pack_version_ids=(
                "pack-universal-research:v1",
                "pack-sector-ai-semis:v3",
                "pack-report-initiation:v2",
            ),
        ),
        cells=cells,
        semantic_loss=(
            M2A1SemanticLossProjection(
                legacy_required_item_id="ai-hbm",
                action="downgrade",
                target_cell_keys=("ai-supply",),
                information_loss_tags=("relationship_context_not_exact_issuer_fact",),
            ),
            M2A1SemanticLossProjection(
                legacy_required_item_id="ai-counterevidence",
                action="split",
                target_cell_keys=("ai-counterevidence",),
                information_loss_tags=("counterevidence_route_preserved",),
            ),
        ),
        artifact_replay=M2A1ArtifactReplayProjection(
            envelope_digest="envelope-v1",
            replay_digest="replay-v1",
            artifact_version_id="artifact-v1",
        ),
        canary_snapshot=_canary_counts(),
    )


def _ai_oracle() -> dict[str, object]:
    return {
        "oracle_case_id": "m2-a1-ai-semis-oracle",
        "input_case_ref": "m2-a1-ai-semis-input",
        "expected_selection": {
            "required_pack_version_ids": [
                "pack-universal-research:v1",
                "pack-sector-ai-semis:v3",
                "pack-report-initiation:v2",
            ],
            "forbidden_pack_version_ids": ["pack-sector-saas:v3"],
        },
        "required_cells": [
            {"cell_key": "ai-demand", "owner_role": "fundamental_analyst", "required_evidence_roles": ["issuer_metric"], "forbidden_evidence_roles": []},
            {"cell_key": "ai-supply", "owner_role": "product_industry_analyst", "required_evidence_roles": ["issuer_metric", "relationship_signal"], "forbidden_evidence_roles": []},
            {"cell_key": "ai-margin", "owner_role": "fundamental_analyst", "required_evidence_roles": ["issuer_metric"], "forbidden_evidence_roles": []},
            {"cell_key": "ai-counterevidence", "owner_role": "risk_counterevidence_analyst", "required_evidence_roles": ["issuer_metric"], "forbidden_evidence_roles": []},
        ],
        "forbidden_cells": ["bank-credit"],
        "cell_count_range": {"minimum": 10, "maximum": 20},
        "legacy_semantic_loss_expectations": [
            {"legacy_required_item_id": "ai-hbm", "allowed_actions": ["downgrade"], "required_information_loss_tags": ["relationship_context_not_exact_issuer_fact"]},
            {"legacy_required_item_id": "ai-counterevidence", "allowed_actions": ["split"], "required_information_loss_tags": ["counterevidence_route_preserved"]},
        ],
        "must_not_assert": ["planning_authority_is_canonical"],
    }


def test_missing_admission_stops_before_runtime_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = M2A1ActualRunner(
        corpus_case={"case_id": "m2-a1-ai-semis-input"},
        compiler_policy_ref="policy",
        pack_registry_policy_ref="registry",
        temporary_root=tmp_path / "runtime",
        canary=M2A1AuditCanary(allowed_temporary_roots=(tmp_path,)),
    )
    monkeypatch.setattr("sec_agent.canonical_runtime.m2_a1_audit_harness.importlib.import_module", lambda *_args, **_kwargs: pytest.fail("runtime import must not occur"))
    with pytest.raises(M2A1ActualExecutionNotAdmitted, match="m2_a1_receipt_lifecycle_requires_consumed_executor"):
        runner.execute_admitted_scenario(
            scenario={"scenario_id": "p01-baseline-separated-input"},
            package=PACKAGE,
            admission=None,
            receipt_ledger=None,
            receipt_id=None,
            execution_preflight=None,
        )


def test_instrumentation_blocks_real_path_sqlite_oracle_network_and_tool_access(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    fixed = tmp_path / "fixed.sqlite"
    oracle = tmp_path / "oracle.json"
    oracle.write_text("reviewer-only", encoding="utf-8")
    canary = M2A1AuditCanary(allowed_temporary_roots=(allowed,), fixed_paths=(fixed,), oracle_paths=(oracle,))
    with canary.instrument():
        with pytest.raises(M2A1StoreAccessError):
            sqlite3.connect(fixed)
        with pytest.raises(M2A1StoreAccessError):
            FileCanonicalObjectStore(tmp_path / "ambient-objects")
        with pytest.raises(M2A1OracleLeakageError):
            oracle.read_text(encoding="utf-8")
        with pytest.raises(M2A1TransportAccessError):
            socket.create_connection(("127.0.0.1", 1))
        with pytest.raises(M2A1TransportAccessError):
            socket.socket().connect(("127.0.0.1", 1))
        with pytest.raises(M2A1StoreAccessError):
            os.getenv(canary.ambient_resolver_env_var)
        with pytest.raises(M2A1TransportAccessError):
            subprocess.Popen(["cmd", "/c", "exit", "0"])
        with pytest.raises(M2A1ModelAdmissionError):
            importlib.import_module("openai")
    counts = canary.snapshot()["counts"]
    assert counts["store_open_attempt_count"] == 1
    assert counts["store_open_success_count"] == 0
    assert counts["oracle_read_attempt_count"] == 1
    assert counts["network_request_attempt_count"] == 2
    assert counts["network_request_success_count"] == 0
    assert counts["transport_constructor_attempt_count"] == 0
    assert counts["socket_connect_attempt_count"] == 1
    assert counts["tool_transport_constructor_attempt_count"] == 1
    assert counts["object_store_constructor_attempt_count"] == 1
    assert counts["object_store_constructor_success_count"] == 0
    assert counts["model_constructor_attempt_count"] == 1


def test_preloaded_transport_alias_and_ledger_reparse_escape_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    canary = M2A1AuditCanary(allowed_temporary_roots=(tmp_path,))
    requests_module = types.ModuleType("requests")

    class SyntheticSession:
        def __init__(self) -> None:
            return None

    requests_module.Session = SyntheticSession  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "requests", requests_module)
    aliases = canary.observe_transport_module_presence()
    assert "requests" in aliases
    context_counts = canary.snapshot()["counts"]
    assert context_counts["transport_module_loaded_count"] >= 1
    assert context_counts["transport_constructor_attempt_count"] == 0
    assert context_counts["network_request_attempt_count"] == 0
    with canary.instrument():
        with pytest.raises(M2A1TransportAccessError, match="shadow_scope_violation"):
            SyntheticSession()
    assert canary.snapshot()["counts"]["transport_constructor_attempt_count"] == 1

    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    ledger_path = authority_root / "m2_a1_execution_receipts.sqlite"
    ledger_path.touch()
    # A platform may prohibit creating a real Windows symlink in the test
    # account; exercise the same pre-mkdir reparse branch deterministically.
    monkeypatch.setattr(receipt_module, "_is_reparse_or_symlink", lambda path: path == ledger_path)
    with pytest.raises((M2A1ReceiptAuthorityError, M2A1ExecutionPreflightError), match="reparse_or_symlink|path_not_preflight_bound"):
        M2A1ReceiptLedger.open_existing(ledger_path, approved_authority_root=authority_root)


def test_authoritative_receipt_is_registered_consumed_and_not_replayable(tmp_path: Path) -> None:
    admission = _admission()
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    ledger = M2A1ReceiptLedger.create_for_registration(authority_root / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority_root)
    receipt = _receipt(admission)
    ledger.register(
        receipt,
        admission=admission,
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        authority_boundary=AUTHORITY_BOUNDARY,
        execution_staging_namespace_id=NAMESPACE_ID,
        scenario_id=SCENARIO_ID,
    )
    consumed = ledger.consume_before_run(
        receipt.receipt_id,
        admission=admission,
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        authority_boundary=AUTHORITY_BOUNDARY,
        preflight_digest=PREFLIGHT_DIGEST,
        run_root=authority_root.parent,
        execution_staging_namespace_id=NAMESPACE_ID,
        scenario_id=SCENARIO_ID,
    )
    assert consumed.state == "consumed_before_run"
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_already_consumed|receipt_binding_mismatch"):
        ledger.consume_before_run(
            receipt.receipt_id,
            admission=admission,
            package_ref=PACKAGE["package_ref"],
            executable_package_digest=PACKAGE_DIGEST,
            scope=PACKAGE["scope"],
            authority_boundary=AUTHORITY_BOUNDARY,
            preflight_digest=PREFLIGHT_DIGEST,
            run_root=authority_root.parent,
            execution_staging_namespace_id=NAMESPACE_ID,
            scenario_id=SCENARIO_ID,
        )
    terminal_digest = ledger.record_terminal_event(receipt.receipt_id, terminal_status="typed_stop", actual_result_digest="d" * 64)
    assert len(terminal_digest) == 64
    with pytest.raises(M2A1ReceiptAuthorityError, match="receipt_terminal_already_recorded"):
        ledger.record_terminal_event(receipt.receipt_id, terminal_status="typed_stop", actual_result_digest="d" * 64)


def test_oracle_mutation_cannot_change_actual_digest_and_gate_rejects_unscored_stop(tmp_path: Path) -> None:
    result = _baseline_result()
    scenario = {"scenario_id": "p01-baseline-separated-input", "expected_typed_stop": "none", "actual_assertions": []}
    oracle = _ai_oracle()
    evaluation = evaluate_independent_oracle(result, oracle, scenario)
    assert evaluation.status == "pass"
    actual_digest = result.actual_result_digest
    mutated_oracle = {**oracle, "forbidden_cells": ["ai-demand"]}
    assert evaluate_independent_oracle(result, mutated_oracle, scenario).status == "mismatch"
    assert result.actual_result_digest == actual_digest

    admission = _admission()
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    ledger = M2A1ReceiptLedger.create_for_registration(authority_root / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority_root)
    active = _receipt(admission)
    ledger.register(
        active,
        admission=admission,
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        authority_boundary=AUTHORITY_BOUNDARY,
        execution_staging_namespace_id=NAMESPACE_ID,
        scenario_id=SCENARIO_ID,
    )
    consumed = ledger.consume_before_run(
        active.receipt_id,
        admission=admission,
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        authority_boundary=AUTHORITY_BOUNDARY,
        preflight_digest=PREFLIGHT_DIGEST,
        run_root=authority_root.parent,
        execution_staging_namespace_id=NAMESPACE_ID,
        scenario_id=SCENARIO_ID,
    )
    consumed_receipt = ledger.verify_consumption_grant(
        consumed,
        admission=admission,
        package_ref=PACKAGE["package_ref"],
        executable_package_digest=PACKAGE_DIGEST,
        scope=PACKAGE["scope"],
        authority_boundary=AUTHORITY_BOUNDARY,
        execution_staging_namespace_id=NAMESPACE_ID,
        scenario_id=SCENARIO_ID,
        run_root=authority_root.parent,
        preflight_digest=PREFLIGHT_DIGEST,
    )
    terminal_digest = ledger.record_terminal_event(active.receipt_id, terminal_status="succeeded", actual_result_digest=result.actual_result_digest)
    gate = review_future_actual(
        package=PACKAGE,
        actual_results=(result,),
        oracle_evaluations=(evaluation,),
        expected_scenario_ids=(result.scenario_id,),
        admission=admission,
        consumed_receipt=consumed_receipt,
        receipt_ledger_state=ledger.state(active.receipt_id),
        receipt_terminal_event_digest=terminal_digest,
    )
    assert gate.status == "pass"
    unscored = evaluation.model_copy(update={"status": "typed_stop_not_scored"})
    rejected = review_future_actual(
        package=PACKAGE,
        actual_results=(result,),
        oracle_evaluations=(unscored,),
        expected_scenario_ids=(result.scenario_id,),
        admission=admission,
        consumed_receipt=consumed_receipt,
        receipt_ledger_state=ledger.state(active.receipt_id),
        receipt_terminal_event_digest=terminal_digest,
    )
    assert rejected.status == "fail_closed"
    assert any("oracle_status_not_accepted" in error for error in rejected.errors)
