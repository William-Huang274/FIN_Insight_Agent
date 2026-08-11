from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import Field

from .facade import MissingDependency, RuntimeFacade
from .models import CommandEnvelope, ResultEnvelope, ScopedVersion, canonical_digest


REDACTED_KEYS = frozenset({"raw_reasoning", "reasoning", "prompt", "prompt_text", "secret", "password", "api_key", "token", "authorization"})


class RuntimeTraceSpan(ScopedVersion):
    span_id: str
    span_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    source_event_id: str
    source_event_type: str
    source_sequence_no: int = Field(ge=1)
    work_unit_id: str | None = None
    attempt_id: str | None = None
    source_payload_digest: str
    redacted_payload: dict[str, Any]
    redaction_applied: bool


class OperationsAlert(ScopedVersion):
    alert_id: str
    alert_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    alert_type: str
    threshold: int = Field(ge=1)
    observed_count: int = Field(ge=1)
    source_event_type: str
    trace_digest: str
    alert_status: str = "open"


class ObservabilityError(RuntimeError):
    pass


class ObservabilityOpsService:
    """M5.8 store-backed stream/trace/metric/alert control plane.

    The source of truth remains canonical events.  Trace records are durable
    projections, and stream cursors make reconnects deterministic.  This is not
    an OpenTelemetry collector, provider tracer, or raw-reasoning store.
    """

    def __init__(self, facade: RuntimeFacade):
        self.facade = facade

    def materialize(self, command: CommandEnvelope) -> ResultEnvelope:
        self.facade._authorize("point01_shadow_compiler")
        case_id = self.facade._require_case(command)
        self._reject_raw_reasoning(command.payload.get("trace_annotations"))
        alert_event_type = str(command.payload.get("alert_event_type") or "")
        alert_threshold = int(command.payload.get("alert_threshold") or 1)
        if not alert_event_type or alert_threshold < 1:
            raise ObservabilityError("observability_alert_policy_required")
        events = self._case_events(case_id)
        if not events:
            raise MissingDependency("observability_case_events_not_found")
        event_scope = {"work_unit_id": events[0].get("work_unit_id"), "attempt_id": events[0].get("attempt_id")}
        scope_key, payload_digest, _ = self.facade._idempotency(command, f"trace:{case_id}")
        with self.facade.store.transaction() as tx:
            existing = tx.get_idempotency(scope_key)
            if existing:
                return self.facade._reuse_or_conflict(existing, payload_digest)
            span_ids: list[str] = []
            redaction_count = 0
            for event in events:
                span_id = f"trace:{event['event_id']}"
                span_ids.append(span_id)
                if tx.get_latest("canonical_trace_span_versions", span_id):
                    continue
                redacted_payload, redacted = self._redact(event.get("payload") or {})
                redaction_count += int(redacted)
                source_command = command.model_copy(update={"correlation_id": str(event["correlation_id"]), "causation_event_id": event.get("causation_event_id")})
                span = RuntimeTraceSpan(
                    **self.facade._scope(source_command, case_id=case_id),
                    span_id=span_id,
                    span_version=1,
                    state_version=1,
                    source_event_id=str(event["event_id"]),
                    source_event_type=str(event["event_type"]),
                    source_sequence_no=int(event["sequence_no"]),
                    work_unit_id=event.get("work_unit_id"),
                    attempt_id=event.get("attempt_id"),
                    source_payload_digest=str(event["payload_digest"]),
                    redacted_payload=redacted_payload,
                    redaction_applied=redacted,
                    current_status="recorded",
                )
                tx.insert("canonical_trace_span_versions", span_id, 1, span.model_dump(mode="json"))
            observed_count = sum(1 for event in events if event["event_type"] == alert_event_type)
            alert_id = f"alert:{case_id}:{alert_event_type}"
            alert_created = False
            if observed_count >= alert_threshold and not tx.get_latest("canonical_operations_alert_versions", alert_id):
                alert = OperationsAlert(
                    **self.facade._scope(command, case_id=case_id),
                    alert_id=alert_id,
                    alert_version=1,
                    state_version=1,
                    alert_type="event_threshold_exceeded",
                    threshold=alert_threshold,
                    observed_count=observed_count,
                    source_event_type=alert_event_type,
                    trace_digest=canonical_digest(span_ids),
                    current_status="open",
                )
                tx.insert("canonical_operations_alert_versions", alert_id, 1, alert.model_dump(mode="json"))
                alert_created = True
            trace_event = self.facade._event(
                tx,
                command.model_copy(update={"expected_state_version": 0}),
                "OBSERVABILITY_TRACE_MATERIALIZED",
                {"case_id": case_id, "span_count": len(span_ids), "trace_digest": canonical_digest(span_ids), "redaction_count": redaction_count},
                **event_scope,
            )
            tx.append_event(trace_event)
            event_ids = [trace_event.event_id]
            if alert_created:
                alert_event = self.facade._event(
                    tx,
                    command.model_copy(update={"expected_state_version": 0}),
                    "OPERATIONS_ALERT_OPENED",
                    {"alert_id": alert_id, "source_event_type": alert_event_type, "observed_count": observed_count, "threshold": alert_threshold},
                    **event_scope,
                )
                tx.append_event(alert_event)
                event_ids.append(alert_event.event_id)
            result = ResultEnvelope(command_id=command.command_id, status="succeeded", state_version_before=0, state_version_after=1, event_ids=tuple(event_ids), projection_refs=tuple(span_ids + ([alert_id] if alert_created else [])))
            tx.put_idempotency(scope_key, payload_digest, result.model_dump(mode="json"))
        return result

    def stream(self, *, case_id: str, after_event_id: str | None = None) -> dict[str, Any]:
        events = self._case_events(case_id)
        start = 0
        if after_event_id is not None:
            positions = [index for index, event in enumerate(events) if event["event_id"] == after_event_id]
            if not positions:
                raise ObservabilityError("stream_cursor_not_found")
            start = positions[0] + 1
        page = events[start:]
        projected = [self._stream_event(event) for event in page]
        return {"scope": "Point01_M5_8_observability_operations_control_plane_only", "case_id": case_id, "after_event_id": after_event_id, "events": projected, "next_cursor_event_id": projected[-1]["event_id"] if projected else after_event_id, "stream_digest": canonical_digest([event["event_id"] for event in projected]), "worker_started": False, "model_call_count": 0, "external_call_count": 0}

    def admin_view(self, *, case_id: str) -> dict[str, Any]:
        events = self._case_events(case_id)
        spans = self.facade.store.list_latest("canonical_trace_span_versions", case_id=case_id)
        alerts = self.facade.store.list_latest("canonical_operations_alert_versions", case_id=case_id)
        spans.sort(key=lambda span: (int(span["source_sequence_no"]), span["span_id"]))
        alerts.sort(key=lambda alert: alert["alert_id"])
        event_counts = dict(sorted(Counter(str(event["event_type"]) for event in events).items()))
        return {"scope": "Point01_M5_8_observability_operations_control_plane_only", "case_id": case_id, "metrics": {"event_counts": event_counts, "trace_span_count": len(spans), "open_alert_count": sum(1 for alert in alerts if alert.get("alert_status") == "open"), "redacted_span_count": sum(1 for span in spans if span.get("redaction_applied"))}, "trace_spans": spans, "alerts": alerts, "admin_inspection_digest": canonical_digest({"event_counts": event_counts, "spans": [span["span_id"] for span in spans], "alerts": [alert["alert_id"] for alert in alerts]}), "raw_reasoning_persisted": False, "worker_started": False, "model_call_count": 0, "external_call_count": 0}

    def _case_events(self, case_id: str) -> list[Mapping[str, Any]]:
        work_units = {str(row["work_unit_id"]) for row in self.facade.store.list_latest("canonical_work_units", case_id=case_id)}
        attempts = {str(row["attempt_id"]) for row in self.facade.store.list_latest("canonical_attempts", case_id=case_id)}
        events = [event for event in self.facade.store.list_events() if event.get("work_unit_id") in work_units or event.get("attempt_id") in attempts]
        events.sort(key=lambda event: (str(event.get("recorded_at") or ""), int(event["sequence_no"]), str(event["event_id"])))
        return events

    @classmethod
    def _stream_event(cls, event: Mapping[str, Any]) -> dict[str, Any]:
        payload, redacted = cls._redact(event.get("payload") or {})
        return {"event_id": event["event_id"], "event_type": event["event_type"], "sequence_no": event["sequence_no"], "correlation_id": event["correlation_id"], "causation_event_id": event.get("causation_event_id"), "work_unit_id": event.get("work_unit_id"), "attempt_id": event.get("attempt_id"), "payload_digest": event["payload_digest"], "payload": payload, "redaction_applied": redacted}

    @classmethod
    def _redact(cls, value: Any) -> tuple[Any, bool]:
        if isinstance(value, Mapping):
            payload: dict[str, Any] = {}
            changed = False
            for key, child in value.items():
                normalized = str(key).lower()
                if normalized in REDACTED_KEYS or any(token in normalized for token in ("reasoning", "prompt", "secret", "password", "api_key", "authorization")):
                    payload[str(key)] = "<redacted>"
                    changed = True
                else:
                    redacted_child, child_changed = cls._redact(child)
                    payload[str(key)] = redacted_child
                    changed = changed or child_changed
            return payload, changed
        if isinstance(value, list):
            items = [cls._redact(item) for item in value]
            return [item[0] for item in items], any(item[1] for item in items)
        if isinstance(value, tuple):
            items = [cls._redact(item) for item in value]
            return [item[0] for item in items], any(item[1] for item in items)
        return value, False

    @classmethod
    def _reject_raw_reasoning(cls, value: Any) -> None:
        _, redacted = cls._redact(value or {})
        if redacted:
            raise ObservabilityError("raw_reasoning_or_secret_annotation_forbidden")


OBSERVABILITY_MODELS = (RuntimeTraceSpan, OperationsAlert)
