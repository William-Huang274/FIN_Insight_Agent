"""Frozen v2.8 lifecycle core and non-human operational-proof fixture.

The production JIT entry owns approval parsing and exact package preflight.  It
then delegates its post-preflight lifecycle to this module.  The only test
adapter below is deliberately labelled ``synthetic_nonhuman_fixture``: it uses
an isolated temporary SQLite ledger, never creates a HumanJITWindowApproval,
and never reads a fixed store or constructs a network/model/tool provider.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from .m2_a1_audit_oracle import M2A1OracleEvaluation, evaluate_independent_oracle
from .m2_a1_audit_result import M2A1ImmutableActualResult
from .m2_a1_audit_reviewer_gate import M2A1ReviewerGateResult, review_future_actual
from .m2_a1_execution_receipt import (
    M2A1ConsumptionGrant,
    M2A1ExecutionReceipt,
    M2A1ExternalPackageAdmission,
    M2A1ReceiptAuthorityError,
    M2A1ReceiptLedger,
    V2_8_ADMISSION_SCHEMA,
    V2_8_RECEIPT_SCHEMA,
)
from .models import StrictModel, canonical_digest


class M2A1SyntheticNonhumanFixtureAuthority(StrictModel):
    """A package-bound test artifact, explicitly not a human approval."""

    schema_version: Literal["finsight_point01_m2_a1_synthetic_nonhuman_fixture_authority_v1"]
    fixture_kind: Literal["synthetic_nonhuman_fixture"]
    fixture_id: str
    package_digest: str
    scenario_id: str
    fixture_digest: str

    @classmethod
    def create(cls, *, package_digest: str, scenario_id: str) -> "M2A1SyntheticNonhumanFixtureAuthority":
        payload = {
            "schema_version": "finsight_point01_m2_a1_synthetic_nonhuman_fixture_authority_v1",
            "fixture_kind": "synthetic_nonhuman_fixture",
            "fixture_id": "point01-m2-a1-v2-8-operational-proof",
            "package_digest": package_digest,
            "scenario_id": scenario_id,
        }
        return cls(**payload, fixture_digest=canonical_digest(payload))

    def verify_digest(self) -> bool:
        return self.fixture_digest == canonical_digest(self.model_dump(mode="json", exclude={"fixture_digest"}))


@dataclass(frozen=True)
class M2A1OperationalProofResult:
    state: str
    receipt_id: str
    admission: M2A1ExternalPackageAdmission
    receipt: M2A1ExecutionReceipt
    grant: M2A1ConsumptionGrant
    terminal_digest: str | None
    actual: M2A1ImmutableActualResult | None
    oracle: M2A1OracleEvaluation | None
    reviewer: M2A1ReviewerGateResult | None
    ledger_path: Path
    failure_reason: str | None = None


def _synthetic_oracle() -> dict[str, Any]:
    return {
        "oracle_case_id": "m2-a1-v2-8-synthetic-oracle",
        "input_case_ref": "m2-a1-v2-8-synthetic-case",
        "expected_selection": {"required_pack_version_ids": ["synthetic-pack:v1"], "forbidden_pack_version_ids": []},
        "required_cells": [{"cell_key": "synthetic.revenue", "owner_role": "EvidenceOperator", "required_evidence_roles": ["issuer_financial"], "forbidden_evidence_roles": []}],
        "forbidden_cells": [],
        "cell_count_range": {"minimum": 1, "maximum": 1},
        "legacy_semantic_loss_expectations": [{"legacy_required_item_id": "legacy-synthetic", "allowed_actions": ["mapped"], "required_information_loss_tags": ["synthetic"]}],
        "must_not_assert": ["synthetic_forbidden_claim"],
    }


def _synthetic_scenario() -> dict[str, Any]:
    return {
        "scenario_id": "p01-synthetic-operational-proof",
        "input_ref": "m2-a1-v2-8-synthetic-case",
        "mutation": "none",
        "expected_typed_stop": "none",
        "actual_assertions": [],
    }


def _synthetic_package(package_digest: str) -> dict[str, Any]:
    return {
        "package_ref": "point01-m2-a1-v2-8-synthetic-operational-proof-only",
        "package_digest": package_digest,
        "scope": "M2_A1_v2_8_synthetic_nonhuman_fixture_only",
        "authority_boundary": "temporary_sqlite_no_fixed_store_network_model_tool_provider_or_business_case",
        "execution_mode": "external_admission_gated",
    }


def _issue_fixture_authority(
    fixture: M2A1SyntheticNonhumanFixtureAuthority,
    *,
    namespace_id: str,
    now: datetime,
) -> tuple[M2A1ExternalPackageAdmission, M2A1ExecutionReceipt]:
    if not fixture.verify_digest() or fixture.fixture_kind != "synthetic_nonhuman_fixture":
        raise M2A1ReceiptAuthorityError("synthetic_nonhuman_fixture_authority_invalid")
    admission = M2A1ExternalPackageAdmission.create(
        admission_ref="synthetic_nonhuman_fixture_only",
        admission_id=f"{fixture.fixture_id}:admission:v1",
        admission_version=1,
        reviewer_identity="synthetic/nonhuman-fixture",
        package_ref="point01-m2-a1-v2-8-synthetic-operational-proof-only",
        executable_package_digest=fixture.package_digest,
        scope="M2_A1_v2_8_synthetic_nonhuman_fixture_only",
        authority_boundary="temporary_sqlite_no_fixed_store_network_model_tool_provider_or_business_case",
        execution_staging_namespace_id=namespace_id,
        expires_at=now + timedelta(minutes=10),
        schema_version=V2_8_ADMISSION_SCHEMA,
        human_approval_digest=fixture.fixture_digest,
    )
    receipt = M2A1ExecutionReceipt.create(
        receipt_id=f"{fixture.fixture_id}:receipt:v1",
        receipt_version=1,
        approval_id=fixture.fixture_id,
        package_ref=admission.package_ref,
        executable_package_digest=fixture.package_digest,
        scope=admission.scope,
        admission_digest=admission.admission_digest,
        nonce_sha256=canonical_digest({"synthetic_fixture": fixture.fixture_digest, "kind": "nonce_digest_only"}),
        expires_at=now + timedelta(minutes=5),
        reviewer_identity=admission.reviewer_identity,
        execution_staging_namespace_id=namespace_id,
        scenario_id=fixture.scenario_id,
        schema_version=V2_8_RECEIPT_SCHEMA,
        human_approval_digest=fixture.fixture_digest,
    )
    return admission, receipt


def _common(admission: M2A1ExternalPackageAdmission, receipt: M2A1ExecutionReceipt, fixture: M2A1SyntheticNonhumanFixtureAuthority) -> dict[str, Any]:
    return {
        "package_ref": admission.package_ref,
        "executable_package_digest": admission.executable_package_digest,
        "scope": admission.scope,
        "authority_boundary": admission.authority_boundary,
        "execution_staging_namespace_id": admission.execution_staging_namespace_id,
        "scenario_id": receipt.scenario_id,
        "expected_admission_schema_version": V2_8_ADMISSION_SCHEMA,
        "expected_receipt_schema_version": V2_8_RECEIPT_SCHEMA,
        "expected_human_approval_digest": fixture.fixture_digest,
    }


def _run_child(child: Path, *, output: Path, admission: M2A1ExternalPackageAdmission, grant: M2A1ConsumptionGrant, scenario_id: str, mode: str) -> int:
    result = subprocess.run(
        [
            sys.executable,
            str(child),
            "--synthetic-nonhuman-fixture",
            "--output",
            str(output),
            "--package-digest",
            admission.executable_package_digest,
            "--admission-digest",
            admission.admission_digest,
            "--receipt-digest",
            grant.consumed_receipt_digest,
            "--scenario-id",
            scenario_id,
            "--mode",
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode


def execute_synthetic_nonhuman_fixture(
    *,
    temporary_root: Path,
    child: Path,
    package_digest: str,
    mode: Literal["happy", "corrupt", "reviewer_fail", "exit_after_consume"] = "happy",
    leave_consumed_for_restart: bool = False,
) -> M2A1OperationalProofResult:
    """Run the frozen v2.8 lifecycle through real ledger/oracle/reviewer code.

    This is a test entry only.  Its authority object is not a HumanJITWindow
    approval, it writes only under ``temporary_root``, and its child process is
    a local deterministic JSON emitter.
    """

    scenario = _synthetic_scenario()
    fixture = M2A1SyntheticNonhumanFixtureAuthority.create(package_digest=package_digest, scenario_id=scenario["scenario_id"])
    now = datetime.now(timezone.utc)
    run_root = temporary_root / "synthetic_nonhuman_fixture_run"
    authority_root = run_root / "authority"
    authority_root.mkdir(parents=True, exist_ok=False)
    admission, receipt = _issue_fixture_authority(fixture, namespace_id="synthetic_nonhuman_fixture_namespace", now=now)
    ledger = M2A1ReceiptLedger.create_for_registration(authority_root / "m2_a1_execution_receipts.sqlite", approved_authority_root=authority_root)
    common = _common(admission, receipt, fixture)
    ledger.register(receipt, admission=admission, **common)
    grant = ledger.consume_before_run(
        receipt.receipt_id,
        admission=admission,
        preflight_digest=canonical_digest({"fixture": fixture.fixture_digest, "stage": "preflight"}),
        run_root=run_root,
        **common,
    )
    output = run_root / "output" / "actual.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    child_rc = _run_child(child, output=output, admission=admission, grant=grant, scenario_id=receipt.scenario_id, mode=mode)
    if child_rc != 0:
        if leave_consumed_for_restart:
            return M2A1OperationalProofResult("consumed_pending_restart_reconciliation", receipt.receipt_id, admission, receipt, grant, None, None, None, None, ledger.db_path, "synthetic_child_exit_after_consume")
        terminal = ledger.recover_consumed_without_terminal(receipt.receipt_id)
        return M2A1OperationalProofResult("outcome_unknown", receipt.receipt_id, admission, receipt, grant, terminal, None, None, None, ledger.db_path, "synthetic_child_nonzero")
    try:
        actual = M2A1ImmutableActualResult.model_validate(json.loads(output.read_text(encoding="utf-8")))
        state = ledger.state(receipt.receipt_id)
        if state is None or not actual.verify_immutable_digest() or actual.executable_package_digest != package_digest or actual.scenario_id != receipt.scenario_id or actual.admission_digest != admission.admission_digest or actual.consumed_receipt_digest != state["receipt_digest"]:
            raise ValueError("synthetic_actual_binding_invalid")
        consumed = ledger.verify_consumption_grant(
            grant,
            admission=admission,
            run_root=run_root,
            preflight_digest=grant.preflight_digest,
            **common,
        )
        oracle = evaluate_independent_oracle(actual, _synthetic_oracle(), scenario)
        reviewer = review_future_actual(
            package=_synthetic_package(package_digest),
            actual_results=(actual,),
            oracle_evaluations=(oracle,),
            expected_scenario_ids=(receipt.scenario_id,),
            admission=admission,
            consumed_receipt=consumed,
            receipt_ledger_state=ledger.state(receipt.receipt_id),
            receipt_terminal_event_digest=None,
            require_terminal_event=False,
            expected_human_approval_digest=fixture.fixture_digest,
        )
        if reviewer.status != "pass":
            raise ValueError("synthetic_real_reviewer_fail_closed")
    except (ValueError, OSError, M2A1ReceiptAuthorityError) as exc:
        terminal = ledger.recover_consumed_without_terminal(receipt.receipt_id)
        return M2A1OperationalProofResult("outcome_unknown", receipt.receipt_id, admission, receipt, grant, terminal, None, None, None, ledger.db_path, str(exc))
    terminal = ledger.record_terminal_event(
        receipt.receipt_id,
        terminal_status="succeeded" if actual.actual_status == "succeeded" else "typed_stop",
        actual_result_digest=actual.actual_result_digest,
        oracle_evaluation_digest=oracle.evaluation_digest,
        reviewer_gate_digest=reviewer.gate_digest,
        expected_human_approval_digest=fixture.fixture_digest,
    )
    ledger.verify_terminal_event(
        receipt.receipt_id,
        expected_human_approval_digest=fixture.fixture_digest,
        expected_actual_result_digest=actual.actual_result_digest,
        expected_oracle_evaluation_digest=oracle.evaluation_digest,
        expected_reviewer_gate_digest=reviewer.gate_digest,
    )
    return M2A1OperationalProofResult("succeeded", receipt.receipt_id, admission, receipt, grant, terminal, actual, oracle, reviewer, ledger.db_path)


def execute_v2_8_frozen_lifecycle_core(
    *,
    synthetic_nonhuman_fixture: bool,
    temporary_root: Path,
    child: Path,
    package_digest: str,
    mode: Literal["happy", "corrupt", "reviewer_fail", "exit_after_consume"] = "happy",
    leave_consumed_for_restart: bool = False,
) -> M2A1OperationalProofResult:
    """The package-bound v2.8 core used by the operational-proof subprocess.

    Production entry points must inject their already-validated external
    authority and exact preflight.  B0.5 intentionally only exposes the
    explicitly labelled non-human fixture adapter; any attempt to call it as a
    human execution path fails before authority materialisation.
    """

    if not synthetic_nonhuman_fixture:
        raise M2A1ReceiptAuthorityError("v2_8_production_authority_adapter_required")
    return execute_synthetic_nonhuman_fixture(
        temporary_root=temporary_root,
        child=child,
        package_digest=package_digest,
        mode=mode,
        leave_consumed_for_restart=leave_consumed_for_restart,
    )


def reconcile_synthetic_nonhuman_fixture(result: M2A1OperationalProofResult) -> str:
    """Reopen a post-consume crash ledger; it can only append outcome_unknown."""

    ledger = M2A1ReceiptLedger.open_existing(result.ledger_path, approved_authority_root=result.ledger_path.parent)
    return ledger.recover_consumed_without_terminal(result.receipt_id)
