from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .jobs import ACTIVE_RUN_STATUSES, TERMINAL_RUN_STATUSES, RunJob, RunLogEvent, RunStatusReport, run_status_report_from_job
from .profiles import WorkbenchProfile
from .runtime_config import runtime_limits_from_env
from .source_bundles import SourceBundle


WORKBENCH_SCHEMA_VERSION = 3


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
    trace_id: str = ""
    profile_id: str | None = None
    run_dir: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_ms: int | None = None
    error_message: str = ""
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


class StoredSourceBundleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    display_name: str
    market: str
    coverage_theme: str
    ticker_count: int
    as_of_date: str | None = None
    status: str
    updated_at: str


class TraceInspectionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    jobs: list[StoredRunJobSummary]
    events: list[RunLogEvent]
    job_count: int
    event_count: int
    status_counts: dict[str, int]
    first_event_at: str | None = None
    latest_event_at: str | None = None


class StoreHealthReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    db_path: str
    db_exists: bool
    db_parent_exists: bool
    db_parent_writable: bool
    db_size_bytes: int
    wal_size_bytes: int
    journal_mode: str
    schema_version: int
    migration_count: int
    profile_count: int
    source_bundle_count: int
    run_job_count: int
    run_event_count: int
    error_message: str = ""


class RunPruneReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool
    terminal_only: bool
    keep_latest: int
    max_age_days: int | None = None
    cutoff_before: str | None = None
    trace_id: str | None = None
    status: str | None = None
    job_type: str | None = None
    candidate_job_ids: list[str]
    deleted_job_count: int
    deleted_event_count: int


class RunRecoveryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reason: str
    interrupted_job_ids: list[str]
    interrupted_job_count: int


class StoreBackupReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    source_path: str
    backup_path: str
    backup_size_bytes: int


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

    def list_source_bundles(self) -> list[StoredSourceBundleSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select bundle_id, display_name, market, coverage_theme, ticker_count, as_of_date, status, updated_at
                from source_bundles
                order by updated_at desc, bundle_id asc
                """
            ).fetchall()
        return [
            StoredSourceBundleSummary(
                bundle_id=row["bundle_id"],
                display_name=row["display_name"],
                market=row["market"],
                coverage_theme=row["coverage_theme"],
                ticker_count=row["ticker_count"],
                as_of_date=row["as_of_date"],
                status=row["status"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_source_bundle(self, bundle_id: str) -> SourceBundle | None:
        with self._connect() as conn:
            row = conn.execute("select payload_json from source_bundles where bundle_id = ?", (bundle_id,)).fetchone()
        if row is None:
            return None
        return SourceBundle.model_validate(json.loads(row["payload_json"]))

    def upsert_source_bundle(self, bundle: SourceBundle) -> StoredSourceBundleSummary:
        timestamp = datetime.now().isoformat(timespec="seconds")
        payload_json = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            existing = conn.execute("select created_at from source_bundles where bundle_id = ?", (bundle.bundle_id,)).fetchone()
            created_at = existing["created_at"] if existing else timestamp
            conn.execute(
                """
                insert into source_bundles (
                    bundle_id, display_name, market, coverage_theme, ticker_count, as_of_date,
                    status, payload_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(bundle_id) do update set
                    display_name = excluded.display_name,
                    market = excluded.market,
                    coverage_theme = excluded.coverage_theme,
                    ticker_count = excluded.ticker_count,
                    as_of_date = excluded.as_of_date,
                    status = excluded.status,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    bundle.bundle_id,
                    bundle.display_name,
                    bundle.market,
                    bundle.coverage_theme,
                    bundle.ticker_count,
                    bundle.as_of_date,
                    bundle.build.status,
                    payload_json,
                    created_at,
                    timestamp,
                ),
            )
        return StoredSourceBundleSummary(
            bundle_id=bundle.bundle_id,
            display_name=bundle.display_name,
            market=bundle.market,
            coverage_theme=bundle.coverage_theme,
            ticker_count=bundle.ticker_count,
            as_of_date=bundle.as_of_date,
            status=bundle.build.status,
            updated_at=timestamp,
        )

    def list_run_jobs(
        self,
        *,
        trace_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 200,
    ) -> list[StoredRunJobSummary]:
        where: list[str] = []
        values: list[object] = []
        if _clean_filter(trace_id):
            where.append("trace_id = ?")
            values.append(_clean_filter(trace_id))
        if _clean_filter(status):
            where.append("status = ?")
            values.append(_clean_filter(status))
        if _clean_filter(job_type):
            where.append("job_type = ?")
            values.append(_clean_filter(job_type))
        values.append(_bounded_limit(limit, default=200, maximum=1000))
        where_sql = f"where {' and '.join(where)}" if where else ""
        with self._connect() as conn:
            sql = f"""
                select job_id, job_type, status, trace_id, profile_id, run_dir,
                       started_at, finished_at, elapsed_ms, error_message, updated_at
                from run_jobs
                {where_sql}
                order by updated_at desc, job_id asc
                limit ?
                """
            rows = conn.execute(sql, tuple(values)).fetchall()
        return [
            StoredRunJobSummary(
                job_id=row["job_id"],
                job_type=row["job_type"],
                status=row["status"],
                trace_id=row["trace_id"] or "",
                profile_id=row["profile_id"],
                run_dir=row["run_dir"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                elapsed_ms=row["elapsed_ms"],
                error_message=row["error_message"] or "",
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

    def get_run_status(self, job_id: str) -> RunStatusReport | None:
        with self._connect() as conn:
            row = conn.execute("select payload_json from run_jobs where job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            count_row = conn.execute(
                "select count(*) as event_count from run_job_events where job_id = ?",
                (job_id,),
            ).fetchone()
            latest_row = conn.execute(
                """
                select job_id, sequence, trace_id, stream, message, created_at
                from run_job_events
                where job_id = ?
                order by sequence desc
                limit 1
                """,
                (job_id,),
            ).fetchone()
        latest_event = (
            RunLogEvent(
                job_id=latest_row["job_id"],
                sequence=latest_row["sequence"],
                trace_id=latest_row["trace_id"] or "",
                stream=latest_row["stream"],
                message=latest_row["message"],
                created_at=latest_row["created_at"],
            )
            if latest_row is not None
            else None
        )
        return run_status_report_from_job(
            RunJob.model_validate(json.loads(row["payload_json"])),
            event_count=int(count_row["event_count"] or 0),
            latest_event=latest_event,
        )

    def upsert_run_job(self, job: RunJob) -> StoredRunJobSummary:
        payload_json = json.dumps(job.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            existing = conn.execute("select created_at from run_jobs where job_id = ?", (job.job_id,)).fetchone()
            created_at = existing["created_at"] if existing else job.created_at
            conn.execute(
                """
                insert into run_jobs (
                    job_id, job_type, status, trace_id, profile_id, run_dir,
                    started_at, finished_at, elapsed_ms, error_message,
                    payload_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(job_id) do update set
                    job_type = excluded.job_type,
                    status = excluded.status,
                    trace_id = excluded.trace_id,
                    profile_id = excluded.profile_id,
                    run_dir = excluded.run_dir,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at,
                    elapsed_ms = excluded.elapsed_ms,
                    error_message = excluded.error_message,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    job.job_id,
                    job.job_type,
                    job.status,
                    job.trace_id,
                    job.profile_id,
                    job.run_dir,
                    job.started_at,
                    job.finished_at,
                    job.elapsed_ms,
                    job.error_message or job.error,
                    payload_json,
                    created_at,
                    job.updated_at,
                ),
            )
        return StoredRunJobSummary(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            trace_id=job.trace_id,
            profile_id=job.profile_id,
            run_dir=job.run_dir,
            started_at=job.started_at,
            finished_at=job.finished_at,
            elapsed_ms=job.elapsed_ms,
            error_message=job.error_message or job.error,
            updated_at=job.updated_at,
        )

    def append_run_event(self, job_id: str, *, stream: str, message: str, trace_id: str | None = None) -> RunLogEvent:
        timestamp = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                resolved_trace_id = trace_id or self._run_job_trace_id(conn, job_id)
                row = conn.execute(
                    "select coalesce(max(sequence), 0) as last_sequence from run_job_events where job_id = ?",
                    (job_id,),
                ).fetchone()
                sequence = int(row["last_sequence"]) + 1
                conn.execute(
                    """
                    insert into run_job_events (job_id, sequence, trace_id, stream, message, created_at)
                    values (?, ?, ?, ?, ?, ?)
                    """,
                    (job_id, sequence, resolved_trace_id, stream, message, timestamp),
                )
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return RunLogEvent(
            job_id=job_id,
            sequence=sequence,
            trace_id=resolved_trace_id,
            stream=stream,
            message=message,
            created_at=timestamp,
        )

    def list_run_events(self, job_id: str, *, after_sequence: int = 0, limit: int = 500) -> list[RunLogEvent]:
        after_sequence = _non_negative_int(after_sequence, default=0)
        limit = _bounded_limit(limit, default=500, maximum=runtime_limits_from_env().event_page_max)
        with self._connect() as conn:
            rows = conn.execute(
                """
                select job_id, sequence, trace_id, stream, message, created_at
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
                trace_id=row["trace_id"] or "",
                stream=row["stream"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_trace_events(self, trace_id: str, *, limit: int = 1000) -> list[RunLogEvent]:
        trace = _clean_filter(trace_id)
        if not trace:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                select job_id, sequence, trace_id, stream, message, created_at
                from run_job_events
                where trace_id = ?
                order by created_at asc, job_id asc, sequence asc
                limit ?
                """,
                (trace, _bounded_limit(limit, default=1000, maximum=runtime_limits_from_env().event_page_max)),
            ).fetchall()
        return [
            RunLogEvent(
                job_id=row["job_id"],
                sequence=row["sequence"],
                trace_id=row["trace_id"] or "",
                stream=row["stream"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def inspect_trace(self, trace_id: str, *, event_limit: int = 1000) -> TraceInspectionReport:
        trace = _clean_filter(trace_id)
        jobs = self.list_run_jobs(trace_id=trace, limit=1000) if trace else []
        events = self.list_trace_events(trace, limit=event_limit) if trace else []
        status_counts: dict[str, int] = {}
        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
        event_times = [event.created_at for event in events]
        return TraceInspectionReport(
            trace_id=trace,
            jobs=jobs,
            events=events,
            job_count=len(jobs),
            event_count=len(events),
            status_counts=status_counts,
            first_event_at=event_times[0] if event_times else None,
            latest_event_at=event_times[-1] if event_times else None,
        )

    def inspect_health(self) -> StoreHealthReport:
        parent = self.db_path.parent
        db_exists = self.db_path.exists()
        wal_path = self.db_path.with_name(f"{self.db_path.name}-wal")
        parent_writable = _is_writable_dir(parent)
        try:
            with self._connect() as conn:
                journal_row = conn.execute("pragma journal_mode").fetchone()
                counts = {
                    "profile_count": _count_rows(conn, "profiles"),
                    "source_bundle_count": _count_rows(conn, "source_bundles"),
                    "run_job_count": _count_rows(conn, "run_jobs"),
                    "run_event_count": _count_rows(conn, "run_job_events"),
                }
                schema_version = _schema_version(conn)
                migration_count = _count_rows(conn, "workbench_schema_migrations")
            status = "ok" if parent_writable else "degraded"
            return StoreHealthReport(
                status=status,
                db_path=str(self.db_path),
                db_exists=db_exists,
                db_parent_exists=parent.exists(),
                db_parent_writable=parent_writable,
                db_size_bytes=self.db_path.stat().st_size if self.db_path.exists() else 0,
                wal_size_bytes=wal_path.stat().st_size if wal_path.exists() else 0,
                journal_mode=str(journal_row[0] or "") if journal_row else "",
                schema_version=schema_version,
                migration_count=migration_count,
                error_message="" if status == "ok" else "database_parent_not_writable",
                **counts,
            )
        except sqlite3.Error as exc:
            return StoreHealthReport(
                status="fail",
                db_path=str(self.db_path),
                db_exists=self.db_path.exists(),
                db_parent_exists=parent.exists(),
                db_parent_writable=parent_writable,
                db_size_bytes=self.db_path.stat().st_size if self.db_path.exists() else 0,
                wal_size_bytes=wal_path.stat().st_size if wal_path.exists() else 0,
                journal_mode="",
                schema_version=0,
                migration_count=0,
                profile_count=0,
                source_bundle_count=0,
                run_job_count=0,
                run_event_count=0,
                error_message=str(exc),
            )

    def interrupt_active_run_jobs(self, *, reason: str = "workbench service restarted") -> RunRecoveryReport:
        jobs = [
            job
            for job in self._list_jobs_by_statuses(ACTIVE_RUN_STATUSES)
            if job.status in ACTIVE_RUN_STATUSES
        ]
        interrupted_ids: list[str] = []
        for job in jobs:
            interrupted = _job_model_update(
                job,
                status="interrupted",
                finished_at=datetime.now().isoformat(timespec="seconds"),
                error=reason,
                metadata={
                    **job.metadata,
                    "recovery": {
                        "status": "interrupted_after_service_start",
                        "reason": reason,
                    },
                },
            )
            self.upsert_run_job(interrupted)
            self.append_run_event(
                interrupted.job_id,
                stream="system",
                message=reason,
                trace_id=interrupted.trace_id,
            )
            interrupted_ids.append(interrupted.job_id)
        return RunRecoveryReport(
            status="ok",
            reason=reason,
            interrupted_job_ids=interrupted_ids,
            interrupted_job_count=len(interrupted_ids),
        )

    def backup_database(self, backup_dir: str | Path | None = None) -> StoreBackupReport:
        target_dir = Path(backup_dir) if backup_dir else self.db_path.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = target_dir / f"{self.db_path.stem}_{timestamp}.sqlite"
        with self._connect() as source:
            with sqlite3.connect(backup_path) as target:
                source.backup(target)
        return StoreBackupReport(
            status="ok",
            source_path=str(self.db_path),
            backup_path=str(backup_path),
            backup_size_bytes=backup_path.stat().st_size if backup_path.exists() else 0,
        )

    def prune_run_jobs(
        self,
        *,
        keep_latest: int = 200,
        max_age_days: int | None = None,
        terminal_only: bool = True,
        dry_run: bool = True,
        trace_id: str | None = None,
        status: str | None = None,
        job_type: str | None = None,
    ) -> RunPruneReport:
        keep_latest = max(0, min(int(keep_latest), 10000))
        max_age_days = None if max_age_days is None else max(0, min(int(max_age_days), 3650))
        cutoff_before = None
        if max_age_days is not None:
            cutoff = datetime.now() - timedelta(days=max_age_days)
            cutoff_before = cutoff.isoformat(timespec="seconds")
        with self._connect() as conn:
            where: list[str] = []
            values: list[object] = []
            if _clean_filter(trace_id):
                where.append("trace_id = ?")
                values.append(_clean_filter(trace_id))
            if _clean_filter(status):
                where.append("status = ?")
                values.append(_clean_filter(status))
            if _clean_filter(job_type):
                where.append("job_type = ?")
                values.append(_clean_filter(job_type))
            where_sql = f"where {' and '.join(where)}" if where else ""
            rows = conn.execute(
                f"""
                select job_id, status, updated_at
                from run_jobs
                {where_sql}
                order by updated_at desc, job_id desc
                """,
                tuple(values),
            ).fetchall()
            candidate_ids: list[str] = []
            for index, row in enumerate(rows):
                beyond_keep = index >= keep_latest
                older_than_cutoff = cutoff_before is not None and str(row["updated_at"]) < cutoff_before
                if not beyond_keep and not older_than_cutoff:
                    continue
                if terminal_only and str(row["status"]) not in TERMINAL_RUN_STATUSES:
                    continue
                candidate_ids.append(str(row["job_id"]))
            event_count = 0
            if candidate_ids:
                placeholders = ",".join("?" for _ in candidate_ids)
                event_row = conn.execute(
                    f"select count(*) as event_count from run_job_events where job_id in ({placeholders})",
                    tuple(candidate_ids),
                ).fetchone()
                event_count = int(event_row["event_count"] or 0)
                if not dry_run:
                    conn.execute("begin immediate")
                    try:
                        conn.execute(f"delete from run_jobs where job_id in ({placeholders})", tuple(candidate_ids))
                    except Exception:
                        conn.rollback()
                        raise
                    else:
                        conn.commit()
        return RunPruneReport(
            dry_run=dry_run,
            terminal_only=terminal_only,
            keep_latest=keep_latest,
            max_age_days=max_age_days,
            cutoff_before=cutoff_before,
            trace_id=_clean_filter(trace_id) or None,
            status=_clean_filter(status) or None,
            job_type=_clean_filter(job_type) or None,
            candidate_job_ids=candidate_ids,
            deleted_job_count=0 if dry_run else len(candidate_ids),
            deleted_event_count=0 if dry_run else event_count,
        )

    def _list_jobs_by_statuses(self, statuses: set[str]) -> list[RunJob]:
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select payload_json
                from run_jobs
                where status in ({placeholders})
                order by updated_at desc, job_id desc
                """,
                tuple(sorted(statuses)),
            ).fetchall()
        return [RunJob.model_validate(json.loads(row["payload_json"])) for row in rows]

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
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma busy_timeout = 30000")
        conn.execute("pragma journal_mode = wal")
        conn.execute("pragma synchronous = normal")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists workbench_schema_migrations (
                    version integer primary key,
                    description text not null,
                    applied_at text not null
                )
                """
            )
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
                    trace_id text not null default '',
                    profile_id text,
                    run_dir text,
                    started_at text,
                    finished_at text,
                    elapsed_ms integer,
                    error_message text not null default '',
                    payload_json text not null,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists source_bundles (
                    bundle_id text primary key,
                    display_name text not null,
                    market text not null,
                    coverage_theme text not null,
                    ticker_count integer not null,
                    as_of_date text,
                    status text not null,
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
                    trace_id text not null default '',
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
            self._ensure_column(conn, "run_jobs", "trace_id", "text not null default ''")
            self._ensure_column(conn, "run_jobs", "started_at", "text")
            self._ensure_column(conn, "run_jobs", "finished_at", "text")
            self._ensure_column(conn, "run_jobs", "elapsed_ms", "integer")
            self._ensure_column(conn, "run_jobs", "error_message", "text not null default ''")
            self._ensure_column(conn, "run_job_events", "trace_id", "text not null default ''")
            self._backfill_legacy_trace_ids(conn)
            conn.execute(
                """
                create index if not exists idx_run_jobs_trace_id
                on run_jobs(trace_id)
                """
            )
            conn.execute(
                """
                create index if not exists idx_run_jobs_status
                on run_jobs(status)
                """
            )
            conn.execute(
                """
                create index if not exists idx_run_jobs_job_type
                on run_jobs(job_type)
                """
            )
            conn.execute(
                """
                create index if not exists idx_run_job_events_trace_id
                on run_job_events(trace_id)
                """
            )
            self._record_schema_migration(conn, 1, "initial workbench store schema")
            self._record_schema_migration(conn, 2, "run trace status fields and event trace indexes")
            self._record_schema_migration(conn, 3, "stable legacy run trace backfill")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f"pragma table_info({table})").fetchall()
        if column in {row["name"] for row in rows}:
            return
        conn.execute(f"alter table {table} add column {column} {definition}")

    @staticmethod
    def _record_schema_migration(conn: sqlite3.Connection, version: int, description: str) -> None:
        conn.execute(
            """
            insert or ignore into workbench_schema_migrations (version, description, applied_at)
            values (?, ?, ?)
            """,
            (version, description, datetime.now().isoformat(timespec="seconds")),
        )

    @staticmethod
    def _backfill_legacy_trace_ids(conn: sqlite3.Connection) -> None:
        rows = conn.execute("select job_id, trace_id, payload_json from run_jobs").fetchall()
        for row in rows:
            job_id = str(row["job_id"])
            column_trace = _clean_filter(row["trace_id"])
            payload_json = str(row["payload_json"] or "{}")
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = None
            payload_trace = _clean_filter(payload.get("trace_id")) if isinstance(payload, dict) else ""
            trace_id = payload_trace or column_trace or _legacy_trace_id(job_id)
            if isinstance(payload, dict):
                payload["trace_id"] = trace_id
                updated_payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if column_trace != trace_id or payload_trace != trace_id or updated_payload_json != payload_json:
                    conn.execute(
                        "update run_jobs set trace_id = ?, payload_json = ? where job_id = ?",
                        (trace_id, updated_payload_json, job_id),
                    )
            elif column_trace != trace_id:
                conn.execute("update run_jobs set trace_id = ? where job_id = ?", (trace_id, job_id))
        conn.execute(
            """
            update run_job_events
            set trace_id = coalesce((select trace_id from run_jobs where run_jobs.job_id = run_job_events.job_id), '')
            where trace_id is null or trace_id = ''
            """
        )

    @staticmethod
    def _run_job_trace_id(conn: sqlite3.Connection, job_id: str) -> str:
        row = conn.execute("select trace_id from run_jobs where job_id = ?", (job_id,)).fetchone()
        return str(row["trace_id"] or "") if row else ""


def default_store_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / "data" / "workbench_private" / "workbench.sqlite"


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_filter(value: object) -> str:
    return str(value or "").strip()


def _bounded_limit(value: object, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _non_negative_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _legacy_trace_id(job_id: str) -> str:
    digest = hashlib.sha256(job_id.encode("utf-8", errors="replace")).hexdigest()[:24]
    return f"trace_legacy_{digest}"


def _job_model_update(job: RunJob, **changes: object) -> RunJob:
    updates = {"updated_at": datetime.now().isoformat(timespec="seconds"), **changes}
    if "error" in updates and "error_message" not in updates:
        updates["error_message"] = str(updates.get("error") or "")
    updated = job.model_copy(update=updates)
    elapsed_ms = _elapsed_ms(updated.started_at, updated.finished_at)
    if elapsed_ms is not None and updated.elapsed_ms != elapsed_ms:
        updated = updated.model_copy(update={"elapsed_ms": elapsed_ms})
    return updated


def _elapsed_ms(started_at: str | None, finished_at: str | None) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, int(round((finished - started).total_seconds() * 1000)))


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"select count(*) as row_count from {table}").fetchone()
    return int(row["row_count"] or 0)


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("select coalesce(max(version), 0) as schema_version from workbench_schema_migrations").fetchone()
    return int(row["schema_version"] or 0)


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".workbench_write_check_{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
