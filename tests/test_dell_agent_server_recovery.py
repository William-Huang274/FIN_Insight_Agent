from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from sec_agent.agent_runtime.dell_agent_server_recovery import (
    DellAgentServerRecoveryCase,
    DellAgentServerRecoveryError,
    create_interrupted_source_invocation,
    create_recovery_case,
    create_recovery_required_research_run,
    create_run_create_action_ambiguous,
    create_run_create_action_applied,
    create_run_create_action_dispatched,
    create_run_create_action_failed_before_dispatch,
    create_run_create_action_intent,
    require_runtime_supported_disposition,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    ResearchRun,
    create_agent_session_v1_2,
    create_recovery_disposition,
    create_research_run,
    create_run_invocation,
)


NOW = datetime(2026, 9, 4, 4, 0, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


def _contracts() -> tuple[ResearchRun, Any]:
    session = create_agent_session_v1_2(
        session_id="SESSION::RECOVERY::001",
        thread_id="THREAD::RECOVERY::001",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN_0_1_3",
        as_of_date=date(2026, 9, 4),
        objective_ref="objective://dell/recovery",
        objective_digest=DIGEST_A,
        data_snapshot_ref="snapshot://dell/recovery",
        data_snapshot_digest=DIGEST_B,
        runtime_policy_ref="policy://dell/recovery",
        runtime_policy_digest=DIGEST_C,
        authority_refs=("authority://owner/data-gate",),
        active_plan_ref="plan://dell/recovery",
        active_plan_digest=DIGEST_A,
        status="ACTIVE",
        created_at=NOW,
        updated_at=NOW,
    )
    run = create_research_run(
        run_id="RUN::RECOVERY::001",
        session_id=session.session_id,
        parent_run_id=None,
        origin_kind="INITIAL",
        legacy_paid_full_chain_execution_label=None,
        status="RUNNING",
        base_plan_ref=session.active_plan_ref,
        base_plan_digest=session.active_plan_digest,
        current_plan_ref=session.active_plan_ref,
        current_plan_digest=session.active_plan_digest,
        last_session_sequence=0,
        created_at=NOW,
        terminal_at=None,
    )
    invocation = create_run_invocation(
        invocation_id="INVOCATION::RECOVERY::001",
        session_id=session.session_id,
        run_id=run.run_id,
        ordinal=1,
        invocation_kind="START",
        status="RUNNING",
        trigger_ref="command://start/recovery",
        lease_ref="lease://agent-server/recovery",
        started_at=NOW,
        finished_at=None,
    )
    return run, invocation


def _case() -> DellAgentServerRecoveryCase:
    run, invocation = _contracts()
    intent = create_run_create_action_intent(
        research_run=run,
        source_invocation=invocation,
        launch_request_digest=DIGEST_A,
    )
    ambiguous = create_run_create_action_ambiguous(
        create_run_create_action_dispatched(intent),
        terminal_at=NOW + timedelta(seconds=1),
    )
    interrupted = create_interrupted_source_invocation(
        invocation,
        finished_at=NOW + timedelta(seconds=1),
    )
    return create_recovery_case(
        recovery_run=create_recovery_required_research_run(run),
        source_invocation=interrupted,
        ambiguous_action=ambiguous,
        lifecycle_event_digest=DIGEST_B,
        recovery_reason_code="remote_create_outcome_unknown",
        server_run_id=None,
        server_run_status=None,
        opened_at=NOW + timedelta(seconds=1),
    )


def _disposition(case: DellAgentServerRecoveryCase, decision: str) -> Any:
    return create_recovery_disposition(
        recovery_disposition_id=f"RECOVERY::{decision}",
        session_id=case.research_run.session_id,
        run_id=case.research_run.run_id,
        research_run_digest=case.research_run.run_digest,
        ambiguous_action_attempt_id=case.ambiguous_action.action_attempt_id,
        ambiguous_action_attempt_digest=case.ambiguous_action.action_attempt_digest,
        source_run_invocation_id=case.source_invocation.invocation_id,
        source_run_invocation_digest=case.source_invocation.invocation_digest,
        investigation_receipt_refs=("receipt://operator/recovery-review",),
        potentially_duplicate_cost=True,
        decision=decision,
        decision_authority_ref="authority://fin-runtime-operator/test",
        next_run_invocation_id=None,
        next_run_invocation_digest=None,
        replacement_action_attempt_id=None,
        replacement_action_attempt_digest=None,
        created_at=NOW + timedelta(seconds=2),
    )


def test_run_create_action_snapshots_cover_dispatch_and_both_terminal_paths() -> None:
    run, invocation = _contracts()
    intent = create_run_create_action_intent(
        research_run=run,
        source_invocation=invocation,
        launch_request_digest=DIGEST_A,
    )
    dispatched = create_run_create_action_dispatched(intent)
    failed = create_run_create_action_failed_before_dispatch(
        intent,
        terminal_at=NOW + timedelta(seconds=1),
    )
    applied = create_run_create_action_applied(
        dispatched,
        server_run_id="01a065aa-7091-7a93-8153-7956fb32f946",
        server_observation_digest=DIGEST_B,
        terminal_at=NOW + timedelta(seconds=1),
    )
    ambiguous = create_run_create_action_ambiguous(
        dispatched,
        terminal_at=NOW + timedelta(seconds=1),
    )

    assert intent.state == "INTENT_COMMITTED"
    assert dispatched.state == "DISPATCHED"
    assert failed.outcome == "FAILED_BEFORE_DISPATCH"
    assert failed.was_dispatched is False
    assert applied.outcome == "APPLIED"
    assert applied.receipt_digest == DIGEST_B
    assert ambiguous.outcome == "AMBIGUOUS_AFTER_DISPATCH"
    assert ambiguous.receipt_ref is None


def test_create_intent_rejects_cross_run_lineage() -> None:
    run, invocation = _contracts()
    foreign = create_run_invocation(
        **{
            **invocation.model_dump(
                exclude={"schema_version", "invocation_digest"}
            ),
            "run_id": "RUN::RECOVERY::FOREIGN",
        }
    )
    with pytest.raises(
        DellAgentServerRecoveryError,
        match="run_create_canonical_lineage_invalid",
    ):
        create_run_create_action_intent(
            research_run=run,
            source_invocation=foreign,
            launch_request_digest=DIGEST_A,
        )


def test_recovery_case_requires_revalidated_interrupted_source_snapshot() -> None:
    case = _case()
    forged_run = ResearchRun.model_construct(
        **{
            **case.research_run.model_dump(),
            "status": "RUNNING",
        }
    )

    with pytest.raises(
        DellAgentServerRecoveryError,
        match="recovery_case_canonical_snapshot_invalid",
    ):
        DellAgentServerRecoveryCase(
            recovery_case_id=case.recovery_case_id,
            research_run=forged_run,
            source_invocation=case.source_invocation,
            ambiguous_action=case.ambiguous_action,
            lifecycle_event_digest=case.lifecycle_event_digest,
            recovery_reason_code=case.recovery_reason_code,
            server_run_id=case.server_run_id,
            server_run_status=case.server_run_status,
            opened_at=case.opened_at,
            recovery_case_digest=case.recovery_case_digest,
        )


def test_recovery_case_cannot_open_before_source_invocation_finishes() -> None:
    run, invocation = _contracts()
    intent = create_run_create_action_intent(
        research_run=run,
        source_invocation=invocation,
        launch_request_digest=DIGEST_A,
    )
    ambiguous = create_run_create_action_ambiguous(
        create_run_create_action_dispatched(intent),
        terminal_at=NOW + timedelta(seconds=1),
    )
    interrupted = create_interrupted_source_invocation(
        invocation,
        finished_at=NOW + timedelta(seconds=2),
    )

    with pytest.raises(
        DellAgentServerRecoveryError,
        match="recovery_case_time_invalid",
    ):
        create_recovery_case(
            recovery_run=create_recovery_required_research_run(run),
            source_invocation=interrupted,
            ambiguous_action=ambiguous,
            lifecycle_event_digest=DIGEST_B,
            recovery_reason_code="remote_create_outcome_unknown",
            server_run_id=None,
            server_run_status=None,
            opened_at=NOW + timedelta(seconds=1, milliseconds=500),
        )


@pytest.mark.parametrize("decision", ["DO_NOT_RETRY", "ABANDON_RUN"])
def test_runtime_accepts_only_the_two_durable_slice_decisions(decision: str) -> None:
    case = _case()
    assert require_runtime_supported_disposition(
        _disposition(case, decision),
        recovery_case=case,
    ) == decision


def test_runtime_rejects_escalate_without_inventing_another_protocol() -> None:
    case = _case()
    with pytest.raises(
        DellAgentServerRecoveryError,
        match="recovery_disposition_not_runtime_supported",
    ):
        require_runtime_supported_disposition(
            _disposition(case, "ESCALATE_TO_HUMAN"),
            recovery_case=case,
        )
