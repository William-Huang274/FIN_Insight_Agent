from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.bounded_sec_document_execution import BoundedSecDocumentExecutionError, BoundedSecDocumentExecutor, SecDocumentTransportError, SingleCallSecDocumentClient
from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalError, M6GlobalOneShotApprovalReceipt, M6GlobalOneShotApprovalService, build_m6_pilot_scope
from sec_agent.canonical_runtime.m6_pilot_package import compute_m6_pilot_package
from sec_agent.canonical_runtime.models import canonical_digest, utc_now
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_positive_sec_document_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


HTML_SENTINEL = "M6_3_5_RAW_DOCUMENT_MUST_NEVER_BE_PERSISTED"
ACTUAL_SHAPE_FIXTURE = ROOT / "tests/fixtures/point01_m6_3_5_nvda_10k_actual_shape_sanitized.html"
INCIDENT_ISOLATION_FIXTURE = ROOT / "tests/fixtures/point01_m6_3_5_incident_transport_isolation_fixture.json"
POSITIVE_HTML = ACTUAL_SHAPE_FIXTURE.read_text(encoding="utf-8").replace("</body>", f"<div>{HTML_SENTINEL}</div></body>")


class _Response:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text


class _Session:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return _Response(self.text)


def _fake_client(policy, session: _Session) -> SingleCallSecDocumentClient:
    return SingleCallSecDocumentClient(
        user_agent="FINInsight-Agent/1.0 compliance@finsight.test",
        timeout_seconds=policy.timeout_seconds,
        user_agent_min_length=policy.user_agent_min_length,
        forbidden_user_agent_values=policy.forbidden_user_agent_values,
        session=session,
    )


def _approved_executor(tmp_path: Path, *, html: str = POSITIVE_HTML, after_send_started_hook=None, after_http_send_hook=None):
    policy = RUNNER._policy()
    facade, security, budgets, command, reservation = RUNNER._runtime(tmp_path / "local", policy)
    request = RUNNER._request()
    plan = RUNNER._plan(request, policy)
    package = compute_m6_pilot_package(root=ROOT, manifest_path=RUNNER.PACKAGE_MANIFEST_PATH)
    authority_store = SQLiteCanonicalStore(tmp_path / "approval" / "canonical.sqlite")
    scope = build_m6_pilot_scope(
        command=command,
        request=request,
        plan=plan,
        approval_ref=policy.approval_ref,
        approved_execution_scope=policy.approved_execution_scope,
        tool_id=policy.tool_id,
        route_id=policy.route_id,
        network_host=policy.allowed_network_host,
        target_cik=policy.allowed_cik,
        endpoint_path=policy.exact_path,
        execution_policy_digest=canonical_digest(policy),
    )
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="global",
        project_id="point01",
        case_id=None,
        actor_snapshot_ref="reviewer-william-003",
        permission_snapshot_ref="reviewer-permission-snapshot",
        policy_config_refs=("point01-m6-3-5-test",),
        correlation_id="point01-m6-3-5-test-approval",
        current_status="active",
        approval_id="approval-point01-m6-3-5-test",
        approval_version=1,
        state_version=1,
        approval_state="active",
        approval_nonce="m6-3-5-test-new-one-shot-nonce",
        scope_digest=scope.scope_digest,
        package_ref=package.package_ref,
        package_digest=package.package_digest,
        package_manifest_digest=package.manifest_digest,
        reviewer_name="william",
        reviewer_employee_id="003",
        reviewer_role="total_reviewer",
        expires_at=utc_now() + timedelta(minutes=10),
        authority_store_identity=authority_store.store_identity(),
    )
    approval_service = M6GlobalOneShotApprovalService(
        store=authority_store,
        required_reviewer_name="william",
        required_reviewer_employee_id="003",
        required_reviewer_role="total_reviewer",
    )
    approval_service.register_authoritative_receipt(receipt)
    session = _Session(html)
    client = _fake_client(policy, session)
    executor = BoundedSecDocumentExecutor(
        facade=facade,
        security=security,
        budgets=budgets,
        policy=policy,
        global_approval_service=approval_service,
        global_approval_id=receipt.approval_id,
        pilot_package=package,
        after_send_started_hook=after_send_started_hook,
        after_http_send_hook=after_http_send_hook,
    )
    return executor, facade, command, request, plan, reservation, client, session


def _registered_authority(
    tmp_path: Path,
    *,
    approval_id: str | None = None,
    reviewer_name: str = "william",
    reviewer_employee_id: str = "003",
    expires_at=None,
):
    policy = RUNNER._policy()
    _, _, _, command, _ = RUNNER._runtime(tmp_path / "local", policy)
    request = RUNNER._request()
    plan = RUNNER._plan(request, policy)
    package = compute_m6_pilot_package(root=ROOT, manifest_path=RUNNER.PACKAGE_MANIFEST_PATH)
    scope = build_m6_pilot_scope(
        command=command,
        request=request,
        plan=plan,
        approval_ref=policy.approval_ref,
        approved_execution_scope=policy.approved_execution_scope,
        tool_id=policy.tool_id,
        route_id=policy.route_id,
        network_host=policy.allowed_network_host,
        target_cik=policy.allowed_cik,
        endpoint_path=policy.exact_path,
        execution_policy_digest=canonical_digest(policy),
    )
    authority_store = SQLiteCanonicalStore(tmp_path / "approval" / "canonical.sqlite")
    service = M6GlobalOneShotApprovalService(
        store=authority_store,
        required_reviewer_name="william",
        required_reviewer_employee_id="003",
        required_reviewer_role="total_reviewer",
    )
    receipt = M6GlobalOneShotApprovalReceipt.create(
        tenant_id="global",
        project_id="point01",
        case_id=None,
        actor_snapshot_ref="reviewer-william-003",
        permission_snapshot_ref="reviewer-permission-snapshot",
        policy_config_refs=("point01-m6-3-5-boundary-test",),
        correlation_id="point01-m6-3-5-boundary-test-approval",
        current_status="active",
        approval_id=approval_id or str(RUNNER._authority_policy()["approval_id"]),
        approval_version=1,
        state_version=1,
        approval_state="active",
        approval_nonce="m6-3-5-boundary-test-new-one-shot-nonce",
        scope_digest=scope.scope_digest,
        package_ref=package.package_ref,
        package_digest=package.package_digest,
        package_manifest_digest=package.manifest_digest,
        reviewer_name=reviewer_name,
        reviewer_employee_id=reviewer_employee_id,
        reviewer_role="total_reviewer",
        expires_at=expires_at or (utc_now() + timedelta(minutes=10)),
        authority_store_identity=authority_store.store_identity(),
    )
    return service, receipt, scope, package


def test_importable_package_freeze_never_resolves_production_authority_or_constructs_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    def _production_authority_access_forbidden() -> Path:
        raise AssertionError("importable_package_freeze_must_not_resolve_production_authority")

    def _transport_construction_forbidden(*args, **kwargs):
        raise AssertionError("importable_package_freeze_must_not_construct_transport")

    monkeypatch.setattr(RUNNER, "_authority_store_root", _production_authority_access_forbidden)
    monkeypatch.setattr(RUNNER, "SingleCallSecDocumentClient", _transport_construction_forbidden)
    result = RUNNER.build_result()
    assert result["status"] == "artifact_contract_remediated_refrozen_pending_total_reviewer"
    assert result["approval_package"]["package_digest"]
    assert result["approval_package"]["manifest_digest"]
    assert result["scope_digest"]
    assert result["external_call_count"] == result["parser_execution_count"] == 0
    assert result["package_authority_boundary"]["reviewer_blind_oracle_runtime_input"] is False
    assert "global_approval_store_path" not in result
    assert result["reason"] == "deterministic_package_freeze_no_authority_store_or_transport_access"


def test_no_active_exact_receipt_denies_execute_live_before_local_store_or_send(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    policy = RUNNER._policy()
    authority_store = SQLiteCanonicalStore(tmp_path / "temporary-authority" / "canonical.sqlite")
    approval_service = M6GlobalOneShotApprovalService(store=authority_store)
    session = _Session(POSITIVE_HTML)
    monkeypatch.setattr(RUNNER, "_authority_store_root", lambda: (_ for _ in ()).throw(AssertionError("production_authority_must_not_be_touched")))
    result = RUNNER.execute_with_injected_dependencies(
        store_root=tmp_path / "must-not-exist",
        approval_service=approval_service,
        client=_fake_client(policy, session),
        process_local_user_agent_scope_confirmed=True,
    )
    assert result["status"] == "fail_closed"
    assert result["reason"] == "global_approval_receipt_not_registered"
    assert result["external_call_count"] == result["store_write_count"] == 0
    assert not session.calls
    assert not (tmp_path / "must-not-exist").exists()


def test_missing_injected_authority_or_client_fails_before_receipt_or_runtime_access(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service, receipt, _, _ = _registered_authority(tmp_path / "canary")
    service.register_authoritative_receipt(receipt)
    policy = RUNNER._policy()
    session = _Session(POSITIVE_HTML)
    monkeypatch.setattr(RUNNER, "_authority_store_root", lambda: (_ for _ in ()).throw(AssertionError("production_authority_must_not_be_touched")))

    missing_client = RUNNER.execute_with_injected_dependencies(
        store_root=tmp_path / "must-not-exist-client",
        approval_service=service,
        client=None,
        process_local_user_agent_scope_confirmed=True,
    )
    missing_authority = RUNNER.execute_with_injected_dependencies(
        store_root=tmp_path / "must-not-exist-authority",
        approval_service=None,
        client=_fake_client(policy, session),
        process_local_user_agent_scope_confirmed=True,
    )

    assert missing_client["reason"] == "injected_non_network_or_explicit_cli_client_required_before_receipt_or_runtime_access"
    assert missing_authority["reason"] == "injected_authority_service_required_before_receipt_or_runtime_access"
    assert service.store.get_latest(service.table, receipt.approval_id)["approval_state"] == "active"
    assert not session.calls
    assert not (tmp_path / "must-not-exist-client").exists()
    assert not (tmp_path / "must-not-exist-authority").exists()


def test_active_canary_receipt_uses_only_injected_temporary_authority_and_fake_transport(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service, receipt, _, _ = _registered_authority(tmp_path / "canary")
    service.register_authoritative_receipt(receipt)
    policy = RUNNER._policy()
    session = _Session(POSITIVE_HTML)
    production_accesses: list[str] = []

    def _production_authority_access_forbidden() -> Path:
        production_accesses.append("attempted")
        raise AssertionError("production_authority_must_not_be_touched")

    monkeypatch.setattr(RUNNER, "_authority_store_root", _production_authority_access_forbidden)
    result = RUNNER.execute_with_injected_dependencies(
        store_root=tmp_path / "canary-runtime",
        approval_service=service,
        client=_fake_client(policy, session),
        process_local_user_agent_scope_confirmed=True,
    )

    assert result["status"] == "pass"
    assert result["external_call_count"] == result["tool_invocation_count"] == 1
    assert len(session.calls) == 1
    assert production_accesses == []
    assert service.store.get_latest(service.table, receipt.approval_id)["approval_state"] == "consumed"
    assert result["result_version"] == "finsight_point01_m6_3_5_live_terminal_result_v1_0"
    assert result["execution_state"] == "approved_single_live_pilot_succeeded"
    assert "authority_boundary" not in result
    assert result["package_authority_boundary"]["live_send_requires_separate_exact_receipt"] is True
    assert result["execution_authorization_snapshot"]["live_send_authorized_by_exact_receipt"] is True
    assert result["execution_authorization_snapshot"]["receipt_state"] == "consumed"
    assert '"global_approval_nonce":' not in json.dumps(result, sort_keys=True)


def test_default_document_transport_is_fail_closed_without_an_injected_session() -> None:
    policy = RUNNER._policy()
    client = SingleCallSecDocumentClient(
        user_agent="FINInsight-Agent/1.0 compliance@finsight.test",
        timeout_seconds=policy.timeout_seconds,
        user_agent_min_length=policy.user_agent_min_length,
        forbidden_user_agent_values=policy.forbidden_user_agent_values,
    )
    with pytest.raises(SecDocumentTransportError, match="sec_document_network_transport_must_be_explicitly_injected"):
        client.fetch(exact_url=policy.exact_url)


def test_incident_transport_isolation_fixture_requires_temporary_authority_and_fake_transport() -> None:
    fixture = json.loads(INCIDENT_ISOLATION_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["production_authority"] == "must_not_be_resolved_by_importable_builder_or_contract_fixture"
    assert fixture["default_transport"] == "fail_closed_no_network"
    assert fixture["canary_contract"]["authority_store"] == "temporary_injected_store_only"
    assert fixture["canary_contract"]["transport"] == "fake_non_network_client_only"


def test_positive_chain_persists_only_unpromoted_lineage_and_not_raw_html(tmp_path: Path) -> None:
    executor, facade, command, request, plan, reservation, client, session = _approved_executor(tmp_path)
    result = executor.execute(command=command, request=request, plan=plan, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation, client=client)
    assert result.status == "positive_chain_persisted"
    assert len(session.calls) == result.external_call_count == 1
    assert result.candidate and result.parser and result.fact and result.trace
    assert result.candidate.promotion_status == result.fact.promotion_status == result.trace.promotion_status == "unpromoted"
    assert result.candidate.writer_citable is result.trace.writer_citable is False
    assert result.fact.normalized_value == "130497"
    assert result.fact.unit == "USD_millions"
    assert result.fact.scale_multiplier == 1000000
    assert result.fact.period == "2025-01-26"
    assert result.candidate.financial_statement_role == "consolidated_primary_financial_statement"
    persisted = {
        table: facade.store.list_versions(table)
        for table in (
            executor.receipt_table,
            executor.candidate_table,
            executor.parser_table,
            executor.fact_table,
            executor.trace_table,
        )
    }
    assert all(len(rows) >= 1 for rows in persisted.values())
    assert HTML_SENTINEL not in json.dumps(persisted, ensure_ascii=False)
    assert "global_approval_nonce" not in result.receipt.model_dump(mode="json")
    assert len(result.receipt.global_approval_nonce_sha256) == 64
    assert all(
        item.execution_instance_id == result.receipt.invocation_id
        for item in (result.candidate, result.parser, result.fact, result.trace)
    )
    source_received_receipt = next(
        row
        for row in persisted[executor.receipt_table]
        if row["downstream_status"] == "source_received"
    )
    expected_receipt_ref = f"{source_received_receipt['invocation_id']}:v{source_received_receipt['invocation_version']}"
    assert all(
        item.receipt_version_ref == expected_receipt_ref
        and item.receipt_content_digest == source_received_receipt["content_digest"]
        for item in (result.candidate, result.parser, result.fact, result.trace)
    )


def test_execution_instance_identity_distinguishes_same_request_plan_across_receipts_and_attempts(tmp_path: Path) -> None:
    first, _, command_one, request_one, plan_one, reservation_one, client_one, _ = _approved_executor(tmp_path / "first")
    second, _, command_two, request_two, plan_two, reservation_two, client_two, _ = _approved_executor(tmp_path / "second")

    first_result = first.execute(command=command_one, request=request_one, plan=plan_one, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation_one, client=client_one)
    second_result = second.execute(command=command_two, request=request_two, plan=plan_two, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation_two, client=client_two)

    assert first_result.receipt.request_digest == second_result.receipt.request_digest
    assert first_result.receipt.tool_selection_plan_digest == second_result.receipt.tool_selection_plan_digest
    assert first_result.receipt.invocation_id != second_result.receipt.invocation_id
    assert first_result.receipt.global_approval_activation_digest != second_result.receipt.global_approval_activation_digest


def test_missing_approved_table_becomes_zero_attempt_terminal_stop_without_sourcehunter(tmp_path: Path) -> None:
    html = "<html><body><div>CONSOLIDATED STATEMENTS OF INCOME</div><table><tr><td>Revenue</td><td>9</td></tr></table></body></html>"
    executor, _, command, request, plan, reservation, client, session = _approved_executor(tmp_path, html=html)
    result = executor.execute(command=command, request=request, plan=plan, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation, client=client)
    assert result.status == "typed_terminal_stop"
    assert len(session.calls) == 1
    assert result.terminal_stop and result.terminal_stop.attempt_budget == 0
    assert result.terminal_stop.sourcehunter_admission == "not_admitted"


def test_send_started_crash_reconciles_without_a_second_get(tmp_path: Path) -> None:
    def _crash() -> None:
        raise SystemExit("simulated_process_exit_after_durable_send_started")

    executor, _, command, request, plan, reservation, client, session = _approved_executor(tmp_path, after_send_started_hook=_crash)
    with pytest.raises(SystemExit):
        executor.execute(command=command, request=request, plan=plan, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation, client=client)
    assert not session.calls
    result = executor.reconcile(command=command, request=request, plan=plan, reservation=reservation)
    assert result.status == "outcome_unknown"
    assert not session.calls


def test_missing_new_global_receipt_fails_before_any_get(tmp_path: Path) -> None:
    policy = RUNNER._policy()
    facade, security, budgets, command, reservation = RUNNER._runtime(tmp_path / "local", policy)
    request = RUNNER._request()
    plan = RUNNER._plan(request, policy)
    session = _Session(POSITIVE_HTML)
    client = SingleCallSecDocumentClient(user_agent="FINInsight-Agent/1.0 compliance@finsight.test", timeout_seconds=20, user_agent_min_length=20, forbidden_user_agent_values=policy.forbidden_user_agent_values, session=session)
    executor = BoundedSecDocumentExecutor(
        facade=facade,
        security=security,
        budgets=budgets,
        policy=policy,
        global_approval_service=M6GlobalOneShotApprovalService(store=SQLiteCanonicalStore(tmp_path / "empty-approval" / "canonical.sqlite")),
        global_approval_id="missing-new-approval",
        pilot_package=compute_m6_pilot_package(root=ROOT, manifest_path=RUNNER.PACKAGE_MANIFEST_PATH),
    )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_receipt_not_registered"):
        executor.execute(command=command, request=request, plan=plan, capability_grant_id="grant-point01-m6-positive-sec-document", reservation=reservation, client=client)
    assert not session.calls


def test_package_digest_is_stable_before_and_after_package_external_receipt_registration(tmp_path: Path) -> None:
    before = compute_m6_pilot_package(root=ROOT, manifest_path=RUNNER.PACKAGE_MANIFEST_PATH)
    service, receipt, _, _ = _registered_authority(tmp_path)
    service.register_authoritative_receipt(receipt)
    after = compute_m6_pilot_package(root=ROOT, manifest_path=RUNNER.PACKAGE_MANIFEST_PATH)
    assert before.model_dump(mode="json") == after.model_dump(mode="json")


def test_receipt_preflight_rejects_wrong_package_scope_reviewer_and_expiry(tmp_path: Path) -> None:
    service, receipt, scope, package = _registered_authority(tmp_path / "exact")
    service.register_authoritative_receipt(receipt)
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_package_digest_mismatch"):
        service.verify_active_exact_receipt(
            scope=scope,
            package_ref=package.package_ref,
            package_digest="0" * 64,
            package_manifest_digest=package.manifest_digest,
            approval_id=receipt.approval_id,
        )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_scope_digest_mismatch"):
        service.verify_active_exact_receipt(
            scope=scope.model_copy(update={"endpoint_path": "/Archives/edgar/data/1045810/wrong.htm"}),
            package_ref=package.package_ref,
            package_digest=package.package_digest,
            package_manifest_digest=package.manifest_digest,
            approval_id=receipt.approval_id,
        )
    wrong_reviewer_service, wrong_reviewer_receipt, _, _ = _registered_authority(
        tmp_path / "wrong-reviewer", reviewer_name="not-william", reviewer_employee_id="999"
    )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_reviewer_mismatch"):
        wrong_reviewer_service.register_authoritative_receipt(wrong_reviewer_receipt)
    expired_service, expired_receipt, _, _ = _registered_authority(
        tmp_path / "expired", expires_at=utc_now() - timedelta(seconds=1)
    )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_initial_receipt_expired"):
        expired_service.register_authoritative_receipt(expired_receipt)


def test_copied_approval_store_cannot_restore_the_original_receipt(tmp_path: Path) -> None:
    service, receipt, scope, package = _registered_authority(tmp_path / "source")
    service.register_authoritative_receipt(receipt)
    copied_db = tmp_path / "copied" / "canonical.sqlite"
    copied_db.parent.mkdir(parents=True)
    shutil.copy2(service.store.db_path, copied_db)
    copied_store = SQLiteCanonicalStore(copied_db)
    copied_service = M6GlobalOneShotApprovalService(
        store=copied_store,
        required_reviewer_name="william",
        required_reviewer_employee_id="003",
        required_reviewer_role="total_reviewer",
    )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_receipt_store_identity_mismatch"):
        copied_service.verify_active_exact_receipt(
            scope=scope,
            package_ref=package.package_ref,
            package_digest=package.package_digest,
            package_manifest_digest=package.manifest_digest,
            approval_id=receipt.approval_id,
        )


def test_only_an_active_exact_receipt_reaches_the_executor_send_gate(tmp_path: Path) -> None:
    executor, _, command, request, plan, reservation, client, session = _approved_executor(tmp_path)
    package = executor.pilot_package.model_copy(update={"package_digest": "f" * 64})
    blocked = BoundedSecDocumentExecutor(
        facade=executor.facade,
        security=executor.security,
        budgets=executor.budgets,
        policy=executor.policy,
        global_approval_service=executor.global_approval_service,
        global_approval_id=executor.global_approval_id,
        pilot_package=package,
    )
    with pytest.raises(M6GlobalOneShotApprovalError, match="global_approval_package_digest_mismatch"):
        blocked.execute(
            command=command,
            request=request,
            plan=plan,
            capability_grant_id="grant-point01-m6-positive-sec-document",
            reservation=reservation,
            client=client,
        )
    assert not session.calls
