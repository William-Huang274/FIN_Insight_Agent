from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import (
    CanonicalRuntimeError,
    append_session_event,
    canonical_digest,
    compile_s1_feedback_receipts,
    compile_s2_feedback_receipt,
    compile_verifier_feedback_receipts,
    create_agent_session,
    create_context_checkpoint,
    resume_agent_session,
    validate_event_log,
    validate_runtime_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-19T12:00:00+08:00"


def _session_and_events() -> tuple[dict, list[dict]]:
    session = create_agent_session(
        session_id="SESSION::DELL::RUNTIME-R1",
        run_id="RUN::DELL::RUNTIME-R1",
        case_id="DELL",
        case_version="current-v1.4",
        as_of_date="2026-08-06",
        objective_ref="objective://dell/value-capture",
        active_plan_ref="plan://dell/r1",
        created_at=NOW,
    )
    events: list[dict] = []
    events.append(
        append_session_event(
            events,
            session_id=session["session_id"],
            event_type="session_created",
            actor_id="Harness",
            occurred_at=NOW,
            output_refs=(session["session_id"],),
        )
    )
    events.append(
        append_session_event(
            events,
            session_id=session["session_id"],
            event_type="tool_execution_completed",
            actor_id="S1",
            attempt_id="S1-LOOKUP-R1",
            occurred_at="2026-08-19T12:00:01+08:00",
            input_refs=("request://dell/value-capture",),
            output_refs=("readiness://dell/value-capture",),
        )
    )
    return session, events
