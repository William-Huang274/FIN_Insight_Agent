from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.observability_ops import ObservabilityError, ObservabilityOpsService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 17, 0, tzinfo=timezone.utc)


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(command_type: str, payload: dict, *, idem: str, expected: int = 0, at: datetime = BASE_TIME) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=command_type, tenant_id="tenant-m5-8", project_id="project-m5-8", case_id="case-m5-8", actor_snapshot_ref="actor-m5-8", permission_snapshot_ref="permission-m5-8", policy_config_refs=("policy-m5-8",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-8", requested_at=at, payload=payload)


def _runtime(tmp_path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.8 fixture", "accountable_owner_ref": "lead-m5-8"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-ops", "input_version_refs": ["summary-v1"], "queue_name": "ops-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "ops-shadow", "work_unit_id": "wu-ops", "worker_ref": "worker-ops", "attempt_id": "attempt-ops-1", "lease_duration_seconds": 120}, idem="claim"))
    return facade


def test_stream_reconnect_trace_alert_and_admin_view_are_store_backed(tmp_path) -> None:
    facade = _runtime(tmp_path)
    ops = ObservabilityOpsService(facade)
    initial = ops.stream(case_id="case-m5-8")
    assert [event["sequence_no"] for event in initial["events"]] == sorted(event["sequence_no"] for event in initial["events"])
    assert initial["events"]
    result = ops.materialize(_command("OBS_MATERIALIZE", {"alert_event_type": "WORK_UNIT_STARTED", "alert_threshold": 1}, idem="materialize", at=BASE_TIME + timedelta(seconds=1)))
    assert result.status == "succeeded"
    reused = ops.materialize(_command("OBS_MATERIALIZE", {"alert_event_type": "WORK_UNIT_STARTED", "alert_threshold": 1}, idem="materialize", at=BASE_TIME + timedelta(seconds=1)))
    assert reused.reused_idempotent_result is True
    reconnect = ops.stream(case_id="case-m5-8", after_event_id=initial["next_cursor_event_id"])
    assert reconnect["events"]
    assert not {event["event_id"] for event in initial["events"]}.intersection(event["event_id"] for event in reconnect["events"])
    admin = ops.admin_view(case_id="case-m5-8")
    assert admin["metrics"]["trace_span_count"] >= len(initial["events"])
    assert admin["metrics"]["open_alert_count"] == 1
    assert admin["alerts"][0]["source_event_type"] == "WORK_UNIT_STARTED"
    assert admin["raw_reasoning_persisted"] is False
    assert all("correlation_id" in span for span in admin["trace_spans"])


def test_raw_reasoning_annotation_is_rejected_and_stream_cursor_is_fail_closed(tmp_path) -> None:
    facade = _runtime(tmp_path)
    ops = ObservabilityOpsService(facade)
    with pytest.raises(ObservabilityError, match="raw_reasoning_or_secret_annotation_forbidden"):
        ops.materialize(_command("OBS_MATERIALIZE", {"alert_event_type": "WORK_UNIT_STARTED", "alert_threshold": 1, "trace_annotations": {"raw_reasoning": "hidden chain"}}, idem="reasoning"))
    assert facade.store.list_latest("canonical_trace_span_versions", case_id="case-m5-8") == []
    with pytest.raises(ObservabilityError, match="stream_cursor_not_found"):
        ops.stream(case_id="case-m5-8", after_event_id="unknown-event")
    redacted, changed = ops._redact({"nested": {"prompt_text": "do not retain"}, "safe": "ok"})
    assert changed is True
    assert redacted == {"nested": {"prompt_text": "<redacted>"}, "safe": "ok"}
