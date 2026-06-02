from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .artifacts import RunArtifactIndex


class RunJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_type: str
    status: str
    profile_id: str | None = None
    prompt: str | None = None
    run_dir: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunLogEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    sequence: int
    stream: str
    message: str
    created_at: str


class RunInspectionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: RunJob
    artifact_index: RunArtifactIndex
    native_checkpoint: dict[str, Any] | None = None


def new_saved_run_inspection_job(
    *,
    run_dir: str | Path,
    artifact_index: RunArtifactIndex,
    job_id: str | None = None,
    profile_id: str | None = None,
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    status = "failed" if artifact_index.status == "fail" else "completed"
    return RunJob(
        job_id=job_id or f"inspect_{uuid4().hex[:12]}",
        job_type="saved_run_inspection",
        status=status,
        profile_id=profile_id,
        run_dir=str(Path(run_dir).resolve()),
        created_at=now,
        updated_at=now,
        started_at=now,
        finished_at=now,
        error="; ".join(artifact_index.errors),
        metadata={
            "artifact_status": artifact_index.status,
            "artifact_count": len(artifact_index.artifacts),
            "missing_required": artifact_index.missing_required,
        },
    )


def new_local_smoke_job(*, job_id: str | None = None, profile_id: str | None = None) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"smoke_{uuid4().hex[:12]}",
        job_type="local_smoke",
        status="queued",
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
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"ask_{uuid4().hex[:12]}",
        job_type="agent_ask",
        status="queued",
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
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"session_{uuid4().hex[:12]}",
        job_type="agent_session_turn",
        status="queued",
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
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    checkpoint = Path(checkpoint_path).resolve()
    run_dir = checkpoint if checkpoint.is_dir() else checkpoint.parent
    return RunJob(
        job_id=job_id or f"native_resume_{uuid4().hex[:12]}",
        job_type="native_checkpoint_resume",
        status="queued",
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
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"eval_{uuid4().hex[:12]}",
        job_type="eval_run",
        status="queued",
        profile_id=profile_id,
        created_at=now,
        updated_at=now,
        metadata={
            "runner": "workbench_subprocess",
            "eval_id": eval_id,
            "output_path": str(Path(output_path)),
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
) -> RunJob:
    now = datetime.now().isoformat(timespec="seconds")
    return RunJob(
        job_id=job_id or f"data_build_{uuid4().hex[:12]}",
        job_type="data_build",
        status="queued",
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
