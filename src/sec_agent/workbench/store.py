from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .jobs import RunJob, RunLogEvent
from .profiles import WorkbenchProfile


class StoredProfileSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    display_name: str
    source_policy: str
    model_name: str | None = None
    updated_at: str


class StoredRunJobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    job_type: str
    status: str
    profile_id: str | None = None
    run_dir: str | None = None
    updated_at: str


class StoredSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    tenant_id: str | None = None
    user_id: str | None = None
    profile_id: str | None = None
    turn_count: int
    latest_job_id: str
    latest_status: str
    updated_at: str


class WorkbenchStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def list_profiles(self) -> list[StoredProfileSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select profile_id, display_name, source_policy, model_name, updated_at
                from profiles
                order by updated_at desc, profile_id asc
                """
            ).fetchall()
        return [
            StoredProfileSummary(
                profile_id=row["profile_id"],
                display_name=row["display_name"],
                source_policy=row["source_policy"],
                model_name=row["model_name"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_profile(self, profile_id: str) -> WorkbenchProfile | None:
        with self._connect() as conn:
            row = conn.execute("select payload_json from profiles where profile_id = ?", (profile_id,)).fetchone()
        if row is None:
            return None
        return WorkbenchProfile.model_validate(json.loads(row["payload_json"]))

    def upsert_profile(self, profile: WorkbenchProfile) -> StoredProfileSummary:
        timestamp = datetime.now().isoformat(timespec="seconds")
        payload = profile.model_dump(mode="json")
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            existing = conn.execute("select created_at from profiles where profile_id = ?", (profile.profile_id,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            conn.execute(
                """
                insert into profiles (
                    profile_id, display_name, source_policy, model_name, payload_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                on conflict(profile_id) do update set
                    display_name = excluded.display_name,
                    source_policy = excluded.source_policy,
                    model_name = excluded.model_name,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.profile_id,
                    profile.display_name,
                    profile.sources.source_policy,
                    profile.model_route.model_name,
                    payload_json,
                    created_at,
                    timestamp,
                ),
            )
        return StoredProfileSummary(
            profile_id=profile.profile_id,
            display_name=profile.display_name,
            source_policy=profile.sources.source_policy,
            model_name=profile.model_route.model_name,
            updated_at=timestamp,
        )

    def list_run_jobs(self) -> list[StoredRunJobSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select job_id, job_type, status, profile_id, run_dir, updated_at
                from run_jobs
                order by updated_at desc, job_id asc
                """
            ).fetchall()
        return [
            StoredRunJobSummary(
                job_id=row["job_id"],
                job_type=row["job_type"],
                status=row["status"],
                profile_id=row["profile_id"],
                run_dir=row["run_dir"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def list_sessions(self) -> list[StoredSessionSummary]:
        jobs = self._list_jobs_by_type("agent_session_turn")
        grouped: dict[str, dict[str, Any]] = {}
        for job in jobs:
            session_id = str(job.metadata.get("session_id") or "").strip()
            if not session_id:
                continue
            item = grouped.get(session_id)
            if item is None:
                grouped[session_id] = {
                    "session_id": session_id,
                    "tenant_id": _string_or_none(job.metadata.get("tenant_id")),
                    "user_id": _string_or_none(job.metadata.get("user_id")),
                    "profile_id": job.profile_id,
                    "turn_count": 1,
                    "latest_job_id": job.job_id,
                    "latest_status": job.status,
                    "updated_at": job.updated_at,
                }
                continue
            item["turn_count"] = int(item["turn_count"]) + 1
            if job.updated_at >= str(item["updated_at"]):
                item.update(
                    {
                        "tenant_id": _string_or_none(job.metadata.get("tenant_id")),
                        "user_id": _string_or_none(job.metadata.get("user_id")),
                        "profile_id": job.profile_id,
                        "latest_job_id": job.job_id,
                        "latest_status": job.status,
                        "updated_at": job.updated_at,
                    }
                )
        return [
            StoredSessionSummary.model_validate(item)
            for item in sorted(grouped.values(), key=lambda row: (str(row["updated_at"]), str(row["session_id"])), reverse=True)
        ]

    def list_session_turn_jobs(self, session_id: str) -> list[RunJob]:
        target = session_id.strip()
        if not target:
            return []
        jobs = self._list_jobs_by_type("agent_session_turn")
        return [
            job
            for job in jobs
            if str(job.metadata.get("session_id") or "").strip() == target
        ]

    def get_run_job(self, job_id: str) -> RunJob | None:
        with self._connect() as conn:
            row = conn.execute("select payload_json from run_jobs where job_id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return RunJob.model_validate(json.loads(row["payload_json"]))

    def upsert_run_job(self, job: RunJob) -> StoredRunJobSummary:
        payload_json = json.dumps(job.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            existing = conn.execute("select created_at from run_jobs where job_id = ?", (job.job_id,)).fetchone()
            created_at = existing["created_at"] if existing else job.created_at
            conn.execute(
                """
                insert into run_jobs (
                    job_id, job_type, status, profile_id, run_dir, payload_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(job_id) do update set
                    job_type = excluded.job_type,
                    status = excluded.status,
                    profile_id = excluded.profile_id,
                    run_dir = excluded.run_dir,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    job.job_id,
                    job.job_type,
                    job.status,
                    job.profile_id,
                    job.run_dir,
                    payload_json,
                    created_at,
                    job.updated_at,
                ),
            )
        return StoredRunJobSummary(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            profile_id=job.profile_id,
            run_dir=job.run_dir,
            updated_at=job.updated_at,
        )

    def append_run_event(self, job_id: str, *, stream: str, message: str) -> RunLogEvent:
        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            row = conn.execute(
                "select coalesce(max(sequence), 0) as last_sequence from run_job_events where job_id = ?",
                (job_id,),
            ).fetchone()
            sequence = int(row["last_sequence"]) + 1
            conn.execute(
                """
                insert into run_job_events (job_id, sequence, stream, message, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (job_id, sequence, stream, message, timestamp),
            )
        return RunLogEvent(
            job_id=job_id,
            sequence=sequence,
            stream=stream,
            message=message,
            created_at=timestamp,
        )

    def list_run_events(self, job_id: str, *, after_sequence: int = 0, limit: int = 500) -> list[RunLogEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select job_id, sequence, stream, message, created_at
                from run_job_events
                where job_id = ? and sequence > ?
                order by sequence asc
                limit ?
                """,
                (job_id, after_sequence, limit),
            ).fetchall()
        return [
            RunLogEvent(
                job_id=row["job_id"],
                sequence=row["sequence"],
                stream=row["stream"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _list_jobs_by_type(self, job_type: str) -> list[RunJob]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select payload_json
                from run_jobs
                where job_type = ?
                order by updated_at desc, job_id desc
                """,
                (job_type,),
            ).fetchall()
        return [RunJob.model_validate(json.loads(row["payload_json"])) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists profiles (
                    profile_id text primary key,
                    display_name text not null,
                    source_policy text not null,
                    model_name text,
                    payload_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists run_jobs (
                    job_id text primary key,
                    job_type text not null,
                    status text not null,
                    profile_id text,
                    run_dir text,
                    payload_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists run_job_events (
                    job_id text not null,
                    sequence integer not null,
                    stream text not null,
                    message text not null,
                    created_at text not null,
                    primary key (job_id, sequence),
                    foreign key (job_id) references run_jobs(job_id) on delete cascade
                )
                """
            )
            conn.execute(
                """
                create index if not exists idx_run_job_events_job_sequence
                on run_job_events(job_id, sequence)
                """
            )


def default_store_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / "data" / "workbench_private" / "workbench.sqlite"


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
