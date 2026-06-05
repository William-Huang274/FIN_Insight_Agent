from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .artifacts import RunArtifactIndex
from .runtime_ids import new_trace_id


ACTIVE_RUN_STATUSES = {"queued", "running"}
TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "interrupted", "timed_out"}


class RunJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_type: str
    status: str
    trace_id: str = Field(default_factory=new_trace_id)
    profile_id: str | None = None
    prompt: str | None = None
    run_dir: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: int | None = None
    error: str = ""
    error_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunLogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    sequence: int
    trace_id: str = ""
    stream: str
    message: str
    created_at: str


class RunInspectionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: RunJob
    artifact_index: RunArtifactIndex
    native_checkpoint: dict[str, Any] | None = None


class RunStatusReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_type: str
    status: str
    trace_id: str
    profile_id: str | None = None
    run_dir: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: int | None = None
    error_message: str = ""
    is_terminal: bool
    event_count: int = 0
    latest_event: RunLogEvent | None = None


class RunCancelReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    cancelled: bool
    message: str
    job: RunJob | None = None


def run_status_report_from_job(
    job: RunJob,
    *,
    event_count: int = 0,
    latest_event: RunLogEvent | None = None,
) -> RunStatusReport:
    return RunStatusReport(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        trace_id=job.trace_id,
        profile_id=job.profile_id,
        run_dir=job.run_dir,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        elapsed_ms=job.elapsed_ms,
        error_message=job.error_message or job.error,
        is_terminal=job.status in TERMINAL_RUN_STATUSES,
        event_count=event_count,
        latest_event=latest_event,
    )


def new_saved_run_inspection_job(
    *,
    run_dir: str | Path,
    artifact_index: RunArtifactIndex,
    job_id: str | None = None,
    profile_id: str | None = None,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    status = "failed" if artifact_index.status == "fail" else "completed"
    return RunJob(
        job_id=job_id or f"inspect_{uuid4().hex[:12]}",
        job_type="saved_run_inspection",
        status=status,
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        run_dir=str(Path(run_dir).resolve()),
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=now,
        elapsed_ms=0,
        error="; ".join(artifact_index.errors),
        error_message="; ".join(artifact_index.errors),
        metadata={
            "artifact_status": artifact_index.status,
            "artifact_count": len(artifact_index.artifacts),
            "missing_required": artifact_index.missing_required,
        },
    )


def new_local_smoke_job(*, job_id: str | None = None, profile_id: str | None = None, trace_id: str | None = None) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"smoke_{uuid4().hex[:12]}",
        job_type="local_smoke",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        created_at=now,
        updated_at=now,
        metadata={"runner": "workbench_subprocess"},
    )


def new_agent_ask_job(
    *,
    prompt: str,
    command_mode: str,
    job_id: str | None = None,
    profile_id: str | None = None,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"ask_{uuid4().hex[:12]}",
        job_type="agent_ask",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        prompt=prompt,
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "command_mode": command_mode,
            "prompt_chars": len(prompt),
        },
    )


def new_agent_session_turn_job(
    *,
    prompt: str,
    command_mode: str,
    session_id: str,
    tenant_id: str,
    user_id: str,
    job_id: str | None = None,
    profile_id: str | None = None,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"session_{uuid4().hex[:12]}",
        job_type="agent_session_turn",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        prompt=prompt,
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "command_mode": command_mode,
            "prompt_chars": len(prompt),
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
        },
    )


def new_native_checkpoint_resume_job(
    *,
    checkpoint_path: str | Path,
    profile_id: str | None = None,
    job_id: str | None = None,
    stop_after_node: str | None = None,
    include_synthesis: bool = True,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    checkpoint = Path(checkpoint_path).resolve()
    run_dir = checkpoint if checkpoint.is_dir() else checkpoint.parent
    return RunJob(
        job_id=job_id or f"native_resume_{uuid4().hex[:12]}",
        job_type="native_checkpoint_resume",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        run_dir=str(run_dir),
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "checkpoint_path": str(checkpoint),
            "stop_after_node": stop_after_node or "",
            "include_synthesis": include_synthesis,
        },
    )


def new_eval_run_job(
    *,
    eval_id: str,
    output_path: str | Path,
    job_id: str | None = None,
    profile_id: str | None = None,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"eval_{uuid4().hex[:12]}",
        job_type="eval_run",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "eval_id": eval_id,
            "output_path": str(Path(output_path)),
        },
    )


def new_maintenance_job(
    *,
    action_id: str,
    action_label: str,
    category: str,
    job_id: str | None = None,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"maintenance_{uuid4().hex[:12]}",
        job_type="maintenance",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "action_id": action_id,
            "action_label": action_label,
            "category": category,
        },
    )


def new_data_build_job(
    *,
    step_id: str,
    step_label: str,
    command_preview: list[str],
    bundle_id: str | None = None,
    bundle_artifact_updates: dict[str, str] | None = None,
    bundle_field_updates: dict[str, str] | None = None,
    job_id: str | None = None,
    profile_id: str | None = None,
    trace_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"data_build_{uuid4().hex[:12]}",
        job_type="data_build",
        status="queued",
        trace_id=trace_id or new_trace_id(),
        profile_id=profile_id,
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "step_id": step_id,
            "step_label": step_label,
            "command_preview": command_preview,
            "bundle_id": bundle_id or "",
            "bundle_artifact_updates": bundle_artifact_updates or {},
            "bundle_field_updates": bundle_field_updates or {},
        },
    )
