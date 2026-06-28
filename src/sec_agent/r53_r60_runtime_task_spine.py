"""S1 runtime task spine for the R53-R60 program.

This module creates the SQL-final research task ledger that later slices use
for tool calls, retrieval, Workpaper events, deliverables, and eval traces.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4


SCHEMA_VERSION = "r53_r60_s1_runtime_task_spine_v0_1"

TASK_STATUSES = (
    "pending",
    "running",
    "paused",
    "repairing",
    "failed",
    "succeeded",
    "cancelled",
)
TERMINAL_STATUSES = {"failed", "succeeded", "cancelled"}
LEGAL_TRANSITIONS = {
    "pending": {"running", "failed", "cancelled"},
    "running": {"paused", "repairing", "failed", "succeeded", "cancelled"},
    "paused": {"running", "failed", "cancelled"},
    "repairing": {"running", "failed", "succeeded", "cancelled"},
    "failed": set(),
    "succeeded": set(),
    "cancelled": set(),
}
GATEWAY_STATUS_MAP = {
    "PENDING": "pending",
    "RUNNING": "running",
    "SUCCESS": "succeeded",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
    "CANCEL_REQUESTED": "cancelled",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, parts: Iterable[Any]) -> str:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def digest_payload(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def json_loads(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


class RuntimeSpineError(RuntimeError):
    """Base runtime spine error."""


class IllegalStatusTransition(RuntimeSpineError):
    """Raised when a task transition would violate the state machine."""


@dataclass(frozen=True)
class RuntimeSpinePaths:
    db_path: Path
    schema_path: Path
    gate_rows_path: Path
    summary_path: Path
    report_path: Path


def default_s1_paths(root: Path) -> RuntimeSpinePaths:
    return RuntimeSpinePaths(
        db_path=root / "data" / "workbench_private" / "research_data" / "r53_r60_runtime_task_spine_v0_1.sqlite",
        schema_path=root / "configs" / "r53_r60" / "s1_runtime_task_spine_schema_v0_1.json",
        gate_rows_path=root / "data" / "manifests" / "r53_r60_s1_runtime_task_spine_gate_rows_v0_1.jsonl",
        summary_path=root / "data" / "manifests" / "r53_r60_s1_runtime_task_spine_summary_v0_1.json",
        report_path=root / "docs" / "internal" / "vnext_20260610" / "r53_r60_s1_runtime_task_spine_l4_scope_pass.zh-CN.md",
    )


class RuntimeTaskSpineStore:
    """SQLite-backed SQL-final ledger for research task runtime state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def migrate(self) -> None:
        with self._connect() as conn:
            create_runtime_spine_schema(conn)
            set_metadata(conn, "schema_version", SCHEMA_VERSION)
            set_metadata(conn, "status_values", list(TASK_STATUSES))
            set_metadata(conn, "closeout_level", "L4_scope_pass")

    def create_task(
        self,
        *,
        query: str,
        task_id: str | None = None,
        trace_id: str | None = None,
        user_id: str = "local_user",
        case_id: str = "",
        mode: str = "local_smoke",
        objective: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        actor: str = "runtime_facade",
    ) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("query_required")
        now = utc_now_iso()
        task_id = task_id or f"task_{uuid4().hex[:16]}"
        trace_id = trace_id or f"trace_{uuid4().hex[:16]}"
        run_id = stable_id("run", [task_id, "1", now])
        objective_payload = dict(objective or {})
        metadata_payload = dict(metadata or {})
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                conn.execute(
                    """
                    insert into research_tasks (
                        task_id, trace_id, query_text, user_id, case_id, mode,
                        status, progress, objective_json, metadata_json, created_at,
                        updated_at, current_run_id, resume_count, error_message
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        trace_id,
                        query,
                        user_id,
                        case_id,
                        mode,
                        "pending",
                        0,
                        json_dumps(objective_payload),
                        json_dumps(metadata_payload),
                        now,
                        now,
                        run_id,
                        0,
                        "",
                    ),
                )
                conn.execute(
                    """
                    insert into task_runs (
                        run_id, task_id, run_sequence, status, input_digest,
                        payload_json, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        task_id,
                        1,
                        "pending",
                        digest_payload({"query": query, "objective": objective_payload, "metadata": metadata_payload}),
                        json_dumps({"mode": mode, "created_by": actor}),
                        now,
                        now,
                    ),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    actor=actor,
                    event_type="task_created",
                    message="research task created",
                    status_before="",
                    status_after="pending",
                    payload={"objective": objective_payload, "metadata": metadata_payload},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_task_state(task_id)

    def import_gateway_task(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        metadata = dict(payload.get("metadata") or {}) if isinstance(payload.get("metadata"), Mapping) else {}
        task_id = str(payload.get("task_id") or "").strip() or None
        trace_id = str(payload.get("trace_id") or "").strip() or None
        return self.create_task(
            query=str(payload.get("query") or ""),
            task_id=task_id,
            trace_id=trace_id,
            user_id=str(payload.get("user_id") or "gateway_user"),
            case_id=str(payload.get("case_id") or ""),
            mode=str(payload.get("mode") or "gateway_import"),
            objective={"source": "java_gateway_payload"},
            metadata={**metadata, "gateway_payload_digest": digest_payload(payload)},
            actor="java_gateway_import",
        )

    def transition_task(
        self,
        task_id: str,
        status: str,
        *,
        actor: str = "runtime_facade",
        message: str = "",
        progress: int | None = None,
        event_type: str = "status_transition",
        payload: Mapping[str, Any] | None = None,
        error_message: str = "",
    ) -> dict[str, Any]:
        status = normalize_status(status)
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                before = str(task["status"])
                if status not in LEGAL_TRANSITIONS[before]:
                    raise IllegalStatusTransition(f"illegal_transition:{before}->{status}")
                run_id = str(task["current_run_id"])
                next_progress = int(progress if progress is not None else task["progress"])
                if status == "running" and before == "pending":
                    conn.execute(
                        "update task_runs set status = ?, started_at = coalesce(started_at, ?), updated_at = ? where run_id = ?",
                        (status, now, now, run_id),
                    )
                elif status in TERMINAL_STATUSES:
                    started_row = conn.execute("select started_at from task_runs where run_id = ?", (run_id,)).fetchone()
                    elapsed_ms = elapsed_from_iso(started_row["started_at"], now) if started_row else None
                    conn.execute(
                        """
                        update task_runs
                        set status = ?, finished_at = ?, elapsed_ms = ?, output_digest = ?, updated_at = ?
                        where run_id = ?
                        """,
                        (
                            status,
                            now,
                            elapsed_ms,
                            digest_payload({"task_id": task_id, "status": status, "progress": next_progress}),
                            now,
                            run_id,
                        ),
                    )
                else:
                    conn.execute("update task_runs set status = ?, updated_at = ? where run_id = ?", (status, now, run_id))
                conn.execute(
                    """
                    update research_tasks
                    set status = ?, progress = ?, updated_at = ?, error_message = ?
                    where task_id = ?
                    """,
                    (status, max(0, min(100, next_progress)), now, error_message, task_id),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    actor=actor,
                    event_type=event_type,
                    message=message or f"status {before} -> {status}",
                    status_before=before,
                    status_after=status,
                    payload=dict(payload or {}),
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_task_state(task_id)

    def resume_task(
        self,
        task_id: str,
        *,
        actor: str = "runtime_facade",
        reason: str = "resume requested",
        checkpoint_ref_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                previous_status = str(task["status"])
                current_count = int(task["resume_count"] or 0)
                run_sequence = int(self._max_run_sequence(conn, task_id)) + 1
                run_id = stable_id("run", [task_id, str(run_sequence), now])
                conn.execute(
                    """
                    insert into task_runs (
                        run_id, task_id, run_sequence, status, checkpoint_ref_id,
                        input_digest, payload_json, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        task_id,
                        run_sequence,
                        "pending",
                        checkpoint_ref_id or "",
                        digest_payload({"task_id": task_id, "resume_from": previous_status, "checkpoint_ref_id": checkpoint_ref_id or ""}),
                        json_dumps({"resume_reason": reason, "previous_status": previous_status}),
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    update research_tasks
                    set status = ?, progress = ?, updated_at = ?, current_run_id = ?,
                        resume_count = ?, error_message = ?
                    where task_id = ?
                    """,
                    ("pending", 0, now, run_id, current_count + 1, "", task_id),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    actor=actor,
                    event_type="resume_requested",
                    message=reason,
                    status_before=previous_status,
                    status_after="pending",
                    payload={"checkpoint_ref_id": checkpoint_ref_id or ""},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_task_state(task_id)

    def import_gateway_worker_update(
        self,
        task_id: str,
        update: Mapping[str, Any],
        *,
        actor: str = "python_worker",
    ) -> dict[str, Any]:
        state = self.get_task_state(task_id)
        current_status = state["task"]["status"]
        gateway_status = str(update.get("status") or current_status).upper()
        target_status = GATEWAY_STATUS_MAP.get(gateway_status, normalize_status(gateway_status))
        progress = int(update.get("progress") or state["task"].get("progress") or 0)
        if current_status == "pending" and target_status != "running":
            self.transition_task(task_id, "running", actor=actor, message="worker update opened run", progress=min(progress, 99))
        elif current_status in {"paused", "repairing"} and target_status not in {current_status, "failed", "cancelled", "succeeded"}:
            self.transition_task(task_id, "running", actor=actor, message="worker update resumed run", progress=min(progress, 99))
        if "memo" in update or "evidence" in update:
            self.record_artifact_ref(
                task_id,
                artifact_type="gateway_worker_update_payload",
                uri=f"inline://gateway_worker_update/{digest_payload(update)}",
                payload={"memo": update.get("memo", ""), "evidence": update.get("evidence", [])},
                actor=actor,
            )
        for event in update.get("events") or []:
            if isinstance(event, Mapping):
                self.append_event(
                    task_id,
                    actor=actor,
                    event_type="worker_event",
                    message=str(event.get("message") or ""),
                    payload=dict(event),
                    stream=str(event.get("stream") or "worker"),
                )
        if target_status == "running":
            return self.get_task_state(task_id)
        return self.transition_task(
            task_id,
            target_status,
            actor=actor,
            message=f"worker status={gateway_status} progress={progress}",
            progress=progress,
            event_type="worker_status_update",
            payload=dict(update),
            error_message=str(update.get("error_message") or ""),
        )

    def append_event(
        self,
        task_id: str,
        *,
        actor: str,
        event_type: str,
        message: str,
        payload: Mapping[str, Any] | None = None,
        stream: str = "runtime",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                resolved_run_id = run_id or str(task["current_run_id"])
                event = self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=resolved_run_id,
                    actor=actor,
                    event_type=event_type,
                    message=message,
                    status_before=str(task["status"]),
                    status_after=str(task["status"]),
                    payload={**dict(payload or {}), "stream": stream},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return event

    def record_node_execution(
        self,
        task_id: str,
        *,
        node: str,
        status: str,
        input_payload: Mapping[str, Any] | None = None,
        output_payload: Mapping[str, Any] | None = None,
        artifact_ref_ids: list[str] | None = None,
        actor: str = "runtime_node",
        error_message: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        node_execution_id = stable_id("node", [task_id, node, now, uuid4().hex[:8]])
        status = normalize_node_status(status)
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                resolved_run_id = run_id or str(task["current_run_id"])
                conn.execute(
                    """
                    insert into node_executions (
                        node_execution_id, task_id, run_id, node, status, started_at,
                        finished_at, elapsed_ms, input_digest, output_digest,
                        artifact_ref_ids_json, error_message, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_execution_id,
                        task_id,
                        resolved_run_id,
                        node,
                        status,
                        now,
                        now,
                        0,
                        digest_payload(input_payload or {}),
                        digest_payload(output_payload or {}),
                        json_dumps(artifact_ref_ids or []),
                        error_message,
                        json_dumps({"input": dict(input_payload or {}), "output": dict(output_payload or {}), "actor": actor}),
                        now,
                    ),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=resolved_run_id,
                    actor=actor,
                    event_type="node_execution_recorded",
                    message=f"node {node} status={status}",
                    status_before=str(task["status"]),
                    status_after=str(task["status"]),
                    payload={"node_execution_id": node_execution_id, "node": node, "status": status},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_node_execution(node_execution_id)

    def record_artifact_ref(
        self,
        task_id: str,
        *,
        artifact_type: str,
        uri: str,
        payload: Mapping[str, Any] | None = None,
        sha256: str | None = None,
        byte_size: int | None = None,
        actor: str = "runtime_facade",
        run_id: str | None = None,
        node_execution_id: str = "",
    ) -> dict[str, Any]:
        now = utc_now_iso()
        payload_dict = dict(payload or {})
        artifact_ref_id = stable_id("artifact", [task_id, artifact_type, uri, sha256 or digest_payload(payload_dict)])
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                resolved_run_id = run_id or str(task["current_run_id"])
                conn.execute(
                    """
                    insert or replace into artifact_refs (
                        artifact_ref_id, task_id, run_id, node_execution_id, artifact_type,
                        uri, sha256, byte_size, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_ref_id,
                        task_id,
                        resolved_run_id,
                        node_execution_id,
                        artifact_type,
                        uri,
                        sha256 or digest_payload(payload_dict),
                        int(byte_size if byte_size is not None else len(json_dumps(payload_dict).encode("utf-8"))),
                        json_dumps(payload_dict),
                        now,
                    ),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=resolved_run_id,
                    actor=actor,
                    event_type="artifact_ref_recorded",
                    message=f"artifact {artifact_type} recorded",
                    status_before=str(task["status"]),
                    status_after=str(task["status"]),
                    payload={"artifact_ref_id": artifact_ref_id, "artifact_type": artifact_type, "uri": uri},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_artifact_ref(artifact_ref_id)

    def append_workpaper_event(
        self,
        task_id: str,
        *,
        actor: str,
        event_type: str,
        section_id: str,
        payload: Mapping[str, Any],
        claim_id: str = "",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                resolved_run_id = run_id or str(task["current_run_id"])
                sequence = self._next_sequence(conn, "workpaper_events", task_id)
                workpaper_event_id = stable_id("wpe", [task_id, sequence, event_type, section_id])
                conn.execute(
                    """
                    insert into workpaper_events (
                        workpaper_event_id, task_id, run_id, sequence, actor, event_type,
                        section_id, claim_id, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workpaper_event_id,
                        task_id,
                        resolved_run_id,
                        sequence,
                        actor,
                        event_type,
                        section_id,
                        claim_id,
                        json_dumps(dict(payload)),
                        now,
                    ),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=resolved_run_id,
                    actor=actor,
                    event_type="workpaper_event_appended",
                    message=f"workpaper {event_type} section={section_id}",
                    status_before=str(task["status"]),
                    status_after=str(task["status"]),
                    payload={"workpaper_event_id": workpaper_event_id, "section_id": section_id, "claim_id": claim_id},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_workpaper_event(workpaper_event_id)

    def save_checkpoint(
        self,
        task_id: str,
        *,
        checkpoint_kind: str,
        checkpoint_uri: str,
        state_payload: Mapping[str, Any],
        recoverable_node: str = "",
        actor: str = "runtime_facade",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        state_digest = digest_payload(state_payload)
        checkpoint_ref_id = stable_id("ckpt", [task_id, checkpoint_kind, checkpoint_uri, state_digest])
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                resolved_run_id = run_id or str(task["current_run_id"])
                conn.execute(
                    """
                    insert or replace into checkpoint_refs (
                        checkpoint_ref_id, task_id, run_id, checkpoint_kind, checkpoint_uri,
                        state_digest, recoverable_node, payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        checkpoint_ref_id,
                        task_id,
                        resolved_run_id,
                        checkpoint_kind,
                        checkpoint_uri,
                        state_digest,
                        recoverable_node,
                        json_dumps(dict(state_payload)),
                        now,
                    ),
                )
                conn.execute(
                    "update task_runs set checkpoint_ref_id = ?, updated_at = ? where run_id = ?",
                    (checkpoint_ref_id, now, resolved_run_id),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=resolved_run_id,
                    actor=actor,
                    event_type="checkpoint_saved",
                    message=f"checkpoint {checkpoint_kind} saved",
                    status_before=str(task["status"]),
                    status_after=str(task["status"]),
                    payload={"checkpoint_ref_id": checkpoint_ref_id, "recoverable_node": recoverable_node},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_checkpoint_ref(checkpoint_ref_id)

    def record_trace_span(
        self,
        task_id: str,
        *,
        span_kind: str,
        name: str,
        status: str,
        actor: str = "runtime_facade",
        parent_span_id: str = "",
        node_execution_id: str = "",
        latency_ms: int = 0,
        token_count: int = 0,
        cost_amount: float = 0.0,
        model_name: str = "",
        provider: str = "",
        payload: Mapping[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_iso()
        span_id = stable_id("span", [task_id, span_kind, name, now, uuid4().hex[:8]])
        with self._connect() as conn:
            conn.execute("begin immediate")
            try:
                task = self._task_row(conn, task_id)
                resolved_run_id = run_id or str(task["current_run_id"])
                conn.execute(
                    """
                    insert into trace_spans (
                        span_id, task_id, run_id, parent_span_id, node_execution_id,
                        actor, span_kind, name, status, started_at, finished_at,
                        latency_ms, token_count, cost_amount, model_name, provider,
                        payload_json, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        span_id,
                        task_id,
                        resolved_run_id,
                        parent_span_id,
                        node_execution_id,
                        actor,
                        span_kind,
                        name,
                        status,
                        now,
                        now,
                        int(latency_ms),
                        int(token_count),
                        float(cost_amount),
                        model_name,
                        provider,
                        json_dumps(dict(payload or {})),
                        now,
                    ),
                )
                self._append_event_in_tx(
                    conn,
                    task_id=task_id,
                    run_id=resolved_run_id,
                    actor=actor,
                    event_type="trace_span_recorded",
                    message=f"trace {span_kind}:{name} status={status}",
                    status_before=str(task["status"]),
                    status_after=str(task["status"]),
                    payload={"span_id": span_id, "span_kind": span_kind, "name": name},
                    created_at=now,
                )
                self._refresh_projection_in_tx(conn, task_id)
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()
        return self.get_trace_span(span_id)

    def get_task_state(self, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            task = row_to_dict(self._task_row(conn, task_id))
            projection = row_to_dict(
                conn.execute("select * from task_progress_projection where task_id = ?", (task_id,)).fetchone()
            )
            current_run = row_to_dict(
                conn.execute("select * from task_runs where run_id = ?", (task["current_run_id"],)).fetchone()
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "task": decode_task_row(task),
            "current_run": decode_run_row(current_run),
            "progress_projection": decode_json_fields(projection),
        }

    def replay_task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            task = row_to_dict(self._task_row(conn, task_id))
            runs = rows_to_dicts(conn.execute("select * from task_runs where task_id = ? order by run_sequence asc", (task_id,)).fetchall())
            events = rows_to_dicts(conn.execute("select * from task_events where task_id = ? order by sequence asc", (task_id,)).fetchall())
            nodes = rows_to_dicts(conn.execute("select * from node_executions where task_id = ? order by created_at asc", (task_id,)).fetchall())
            artifacts = rows_to_dicts(conn.execute("select * from artifact_refs where task_id = ? order by created_at asc", (task_id,)).fetchall())
            workpaper_events = rows_to_dicts(conn.execute("select * from workpaper_events where task_id = ? order by sequence asc", (task_id,)).fetchall())
            checkpoints = rows_to_dicts(conn.execute("select * from checkpoint_refs where task_id = ? order by created_at asc", (task_id,)).fetchall())
            spans = rows_to_dicts(conn.execute("select * from trace_spans where task_id = ? order by created_at asc", (task_id,)).fetchall())
            projection = row_to_dict(conn.execute("select * from task_progress_projection where task_id = ?", (task_id,)).fetchone())
        return {
            "schema_version": SCHEMA_VERSION,
            "task": decode_task_row(task),
            "runs": [decode_run_row(row) for row in runs],
            "events": [decode_json_fields(row) for row in events],
            "node_executions": [decode_json_fields(row) for row in nodes],
            "artifact_refs": [decode_json_fields(row) for row in artifacts],
            "workpaper_events": [decode_json_fields(row) for row in workpaper_events],
            "checkpoint_refs": [decode_json_fields(row) for row in checkpoints],
            "trace_spans": [decode_json_fields(row) for row in spans],
            "progress_projection": decode_json_fields(projection),
            "replay_status": "replayable",
        }

    def table_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {
                table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
                for table in [
                    "research_tasks",
                    "task_runs",
                    "task_events",
                    "node_executions",
                    "artifact_refs",
                    "workpaper_events",
                    "checkpoint_refs",
                    "trace_spans",
                    "task_progress_projection",
                ]
            }

    def get_node_execution(self, node_execution_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from node_executions where node_execution_id = ?", (node_execution_id,)).fetchone()
        if row is None:
            raise KeyError(node_execution_id)
        return decode_json_fields(row_to_dict(row))

    def get_artifact_ref(self, artifact_ref_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from artifact_refs where artifact_ref_id = ?", (artifact_ref_id,)).fetchone()
        if row is None:
            raise KeyError(artifact_ref_id)
        return decode_json_fields(row_to_dict(row))

    def get_workpaper_event(self, workpaper_event_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from workpaper_events where workpaper_event_id = ?", (workpaper_event_id,)).fetchone()
        if row is None:
            raise KeyError(workpaper_event_id)
        return decode_json_fields(row_to_dict(row))

    def get_checkpoint_ref(self, checkpoint_ref_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from checkpoint_refs where checkpoint_ref_id = ?", (checkpoint_ref_id,)).fetchone()
        if row is None:
            raise KeyError(checkpoint_ref_id)
        return decode_json_fields(row_to_dict(row))

    def get_trace_span(self, span_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from trace_spans where span_id = ?", (span_id,)).fetchone()
        if row is None:
            raise KeyError(span_id)
        return decode_json_fields(row_to_dict(row))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        conn.execute("pragma busy_timeout = 30000")
        conn.execute("pragma journal_mode = wal")
        conn.execute("pragma synchronous = normal")
        return conn

    def _task_row(self, conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = conn.execute("select * from research_tasks where task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"task_not_found:{task_id}")
        return row

    def _max_run_sequence(self, conn: sqlite3.Connection, task_id: str) -> int:
        row = conn.execute("select coalesce(max(run_sequence), 0) as max_sequence from task_runs where task_id = ?", (task_id,)).fetchone()
        return int(row["max_sequence"] or 0)

    def _next_sequence(self, conn: sqlite3.Connection, table: str, task_id: str) -> int:
        row = conn.execute(f"select coalesce(max(sequence), 0) as last_sequence from {table} where task_id = ?", (task_id,)).fetchone()
        return int(row["last_sequence"] or 0) + 1

    def _append_event_in_tx(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        run_id: str,
        actor: str,
        event_type: str,
        message: str,
        status_before: str,
        status_after: str,
        payload: Mapping[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        sequence = self._next_sequence(conn, "task_events", task_id)
        event_id = stable_id("event", [task_id, sequence, event_type])
        conn.execute(
            """
            insert into task_events (
                event_id, task_id, run_id, sequence, actor, event_type,
                status_before, status_after, message, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                task_id,
                run_id,
                sequence,
                actor,
                event_type,
                status_before,
                status_after,
                message,
                json_dumps(dict(payload)),
                created_at,
            ),
        )
        return {
            "event_id": event_id,
            "task_id": task_id,
            "run_id": run_id,
            "sequence": sequence,
            "actor": actor,
            "event_type": event_type,
            "status_before": status_before,
            "status_after": status_after,
            "message": message,
            "payload": dict(payload),
            "created_at": created_at,
        }

    def _refresh_projection_in_tx(self, conn: sqlite3.Connection, task_id: str) -> None:
        task = self._task_row(conn, task_id)
        event_count = scalar_count(conn, "task_events", task_id)
        run_count = scalar_count(conn, "task_runs", task_id)
        node_count = scalar_count(conn, "node_executions", task_id)
        artifact_count = scalar_count(conn, "artifact_refs", task_id)
        workpaper_event_count = scalar_count(conn, "workpaper_events", task_id)
        checkpoint_count = scalar_count(conn, "checkpoint_refs", task_id)
        trace_span_count = scalar_count(conn, "trace_spans", task_id)
        latest_event = conn.execute(
            "select created_at from task_events where task_id = ? order by sequence desc limit 1",
            (task_id,),
        ).fetchone()
        payload = {
            "run_count": run_count,
            "event_count": event_count,
            "node_count": node_count,
            "artifact_count": artifact_count,
            "workpaper_event_count": workpaper_event_count,
            "checkpoint_count": checkpoint_count,
            "trace_span_count": trace_span_count,
            "is_terminal": str(task["status"]) in TERMINAL_STATUSES,
        }
        conn.execute(
            """
            insert into task_progress_projection (
                task_id, run_id, status, progress, event_count, node_count,
                artifact_count, workpaper_event_count, checkpoint_count,
                trace_span_count, latest_event_at, updated_at, payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(task_id) do update set
                run_id = excluded.run_id,
                status = excluded.status,
                progress = excluded.progress,
                event_count = excluded.event_count,
                node_count = excluded.node_count,
                artifact_count = excluded.artifact_count,
                workpaper_event_count = excluded.workpaper_event_count,
                checkpoint_count = excluded.checkpoint_count,
                trace_span_count = excluded.trace_span_count,
                latest_event_at = excluded.latest_event_at,
                updated_at = excluded.updated_at,
                payload_json = excluded.payload_json
            """,
            (
                task_id,
                task["current_run_id"],
                task["status"],
                task["progress"],
                event_count,
                node_count,
                artifact_count,
                workpaper_event_count,
                checkpoint_count,
                trace_span_count,
                latest_event["created_at"] if latest_event else None,
                utc_now_iso(),
                json_dumps(payload),
            ),
        )


class FinSightResearchRuntimeFacade:
    """Stable Python facade for S1 and later Java/Workbench adapters."""

    def __init__(self, db_path: str | Path):
        self.store = RuntimeTaskSpineStore(db_path)

    def create_task(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.create_task(query=query, **kwargs)

    def import_gateway_task(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.store.import_gateway_task(payload)

    def get_task_state(self, task_id: str) -> dict[str, Any]:
        return self.store.get_task_state(task_id)

    def resume_task(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.resume_task(task_id, **kwargs)

    def replay_task(self, task_id: str) -> dict[str, Any]:
        return self.store.replay_task(task_id)

    def record_worker_update(self, task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
        return self.store.import_gateway_worker_update(task_id, update)

    def record_node_result(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.record_node_execution(task_id, **kwargs)

    def record_artifact_ref(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.record_artifact_ref(task_id, **kwargs)

    def append_workpaper_event(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.append_workpaper_event(task_id, **kwargs)

    def save_checkpoint(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.save_checkpoint(task_id, **kwargs)

    def record_trace_span(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.store.record_trace_span(task_id, **kwargs)


def create_runtime_spine_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists runtime_spine_metadata (
            key text primary key,
            value_json text not null,
            updated_at text not null
        );
        create table if not exists research_tasks (
            task_id text primary key,
            trace_id text not null,
            query_text text not null,
            user_id text not null default '',
            case_id text not null default '',
            mode text not null default '',
            status text not null,
            progress integer not null default 0,
            objective_json text not null default '{}',
            metadata_json text not null default '{}',
            created_at text not null,
            updated_at text not null,
            current_run_id text not null default '',
            resume_count integer not null default 0,
            error_message text not null default '',
            check (status in ('pending','running','paused','repairing','failed','succeeded','cancelled'))
        );
        create table if not exists task_runs (
            run_id text primary key,
            task_id text not null,
            run_sequence integer not null,
            status text not null,
            started_at text,
            finished_at text,
            elapsed_ms integer,
            checkpoint_ref_id text not null default '',
            input_digest text not null default '',
            output_digest text not null default '',
            code_commit text not null default '',
            data_snapshot_id text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            updated_at text not null,
            unique(task_id, run_sequence),
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            check (status in ('pending','running','paused','repairing','failed','succeeded','cancelled'))
        );
        create table if not exists task_events (
            event_id text primary key,
            task_id text not null,
            run_id text not null,
            sequence integer not null,
            actor text not null,
            event_type text not null,
            status_before text not null default '',
            status_after text not null default '',
            message text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            unique(task_id, sequence),
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade
        );
        create table if not exists node_executions (
            node_execution_id text primary key,
            task_id text not null,
            run_id text not null,
            node text not null,
            status text not null,
            started_at text not null,
            finished_at text,
            elapsed_ms integer,
            input_digest text not null default '',
            output_digest text not null default '',
            artifact_ref_ids_json text not null default '[]',
            error_message text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade
        );
        create table if not exists artifact_refs (
            artifact_ref_id text primary key,
            task_id text not null,
            run_id text not null,
            node_execution_id text not null default '',
            artifact_type text not null,
            uri text not null,
            sha256 text not null default '',
            byte_size integer not null default 0,
            payload_json text not null default '{}',
            created_at text not null,
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade
        );
        create table if not exists workpaper_events (
            workpaper_event_id text primary key,
            task_id text not null,
            run_id text not null,
            sequence integer not null,
            actor text not null,
            event_type text not null,
            section_id text not null default '',
            claim_id text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            unique(task_id, sequence),
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade
        );
        create table if not exists checkpoint_refs (
            checkpoint_ref_id text primary key,
            task_id text not null,
            run_id text not null,
            checkpoint_kind text not null,
            checkpoint_uri text not null,
            state_digest text not null,
            recoverable_node text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade
        );
        create table if not exists trace_spans (
            span_id text primary key,
            task_id text not null,
            run_id text not null,
            parent_span_id text not null default '',
            node_execution_id text not null default '',
            actor text not null default '',
            span_kind text not null,
            name text not null,
            status text not null,
            started_at text not null,
            finished_at text,
            latency_ms integer not null default 0,
            token_count integer not null default 0,
            cost_amount real not null default 0,
            model_name text not null default '',
            provider text not null default '',
            payload_json text not null default '{}',
            created_at text not null,
            foreign key (task_id) references research_tasks(task_id) on delete cascade,
            foreign key (run_id) references task_runs(run_id) on delete cascade
        );
        create table if not exists task_progress_projection (
            task_id text primary key,
            run_id text not null,
            status text not null,
            progress integer not null,
            event_count integer not null default 0,
            node_count integer not null default 0,
            artifact_count integer not null default 0,
            workpaper_event_count integer not null default 0,
            checkpoint_count integer not null default 0,
            trace_span_count integer not null default 0,
            latest_event_at text,
            updated_at text not null,
            payload_json text not null default '{}',
            foreign key (task_id) references research_tasks(task_id) on delete cascade
        );
        create index if not exists idx_task_events_task_sequence on task_events(task_id, sequence);
        create index if not exists idx_task_events_run on task_events(run_id);
        create index if not exists idx_task_runs_task on task_runs(task_id, run_sequence);
        create index if not exists idx_node_executions_task on node_executions(task_id, run_id);
        create index if not exists idx_artifact_refs_task on artifact_refs(task_id, run_id);
        create index if not exists idx_checkpoint_refs_task on checkpoint_refs(task_id, run_id);
        create index if not exists idx_trace_spans_task on trace_spans(task_id, run_id);
        create trigger if not exists workpaper_events_no_update
        before update on workpaper_events
        begin
            select raise(abort, 'workpaper_events_append_only_update_forbidden');
        end;
        create trigger if not exists workpaper_events_no_delete
        before delete on workpaper_events
        begin
            select raise(abort, 'workpaper_events_append_only_delete_forbidden');
        end;
        """
    )


def set_metadata(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        insert into runtime_spine_metadata(key, value_json, updated_at)
        values (?, ?, ?)
        on conflict(key) do update set value_json = excluded.value_json, updated_at = excluded.updated_at
        """,
        (key, json_dumps(value), utc_now_iso()),
    )


def runtime_spine_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "closeout_level": "L4_scope_pass",
        "status_values": list(TASK_STATUSES),
        "terminal_statuses": sorted(TERMINAL_STATUSES),
        "legal_transitions": {key: sorted(value) for key, value in LEGAL_TRANSITIONS.items()},
        "tables": [
            "research_tasks",
            "task_runs",
            "task_events",
            "node_executions",
            "artifact_refs",
            "workpaper_events",
            "checkpoint_refs",
            "trace_spans",
            "task_progress_projection",
        ],
        "append_only_tables": ["workpaper_events"],
        "facade_methods": [
            "create_task",
            "import_gateway_task",
            "get_task_state",
            "resume_task",
            "replay_task",
            "record_worker_update",
            "record_node_result",
            "record_artifact_ref",
            "append_workpaper_event",
            "save_checkpoint",
            "record_trace_span",
        ],
    }


def build_s1_gate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    paths = default_s1_paths(root)
    paths.schema_path.parent.mkdir(parents=True, exist_ok=True)
    paths.gate_rows_path.parent.mkdir(parents=True, exist_ok=True)
    paths.report_path.parent.mkdir(parents=True, exist_ok=True)
    if paths.db_path.exists():
        paths.db_path.unlink()
    facade = FinSightResearchRuntimeFacade(paths.db_path)

    first = facade.create_task(
        "Analyze NVDA AI infrastructure product and capital signal readiness",
        task_id="s1_scope_task_nvda_ai_infra",
        trace_id="trace_s1_scope_nvda_ai_infra",
        user_id="s1_gate",
        case_id="s1_runtime_spine_dogfood",
        mode="runtime_spine_dogfood",
        objective={"required_dimensions": ["fundamental", "product", "capital", "market"], "minimum_evidence": "ledgered"},
        metadata={"source_slice": "S1", "closeout_level": "L4_scope_pass"},
    )
    task_id = first["task"]["task_id"]
    facade.store.transition_task(task_id, "running", actor="research_lead", message="start S1 dogfood run", progress=10)
    artifact = facade.record_artifact_ref(
        task_id,
        artifact_type="retrieval_plan",
        uri="inline://s1/retrieval_plan",
        payload={"routes": ["sql_exact", "graph", "object_bm25", "milvus_semantic"], "budget": "diagnostic"},
        actor="research_lead",
    )
    node = facade.record_node_result(
        task_id,
        node="research_lead_objective_contract",
        status="pass",
        input_payload={"query": first["task"]["query_text"]},
        output_payload={"objective_contract": "created", "artifact_ref_id": artifact["artifact_ref_id"]},
        artifact_ref_ids=[artifact["artifact_ref_id"]],
        actor="research_lead",
    )
    facade.append_workpaper_event(
        task_id,
        actor="product_specialist",
        event_type="section_claim_added",
        section_id="product_intelligence",
        claim_id="claim_product_graph_available",
        payload={"claim": "Product intelligence graph is available for downstream inspection.", "evidence_ref": artifact["artifact_ref_id"]},
    )
    checkpoint = facade.save_checkpoint(
        task_id,
        checkpoint_kind="langgraph_node_checkpoint",
        checkpoint_uri="inline://s1/checkpoint/research_lead_objective_contract",
        state_payload={"latest_node": node["node"], "artifact_ref_id": artifact["artifact_ref_id"]},
        recoverable_node="dimension_evidence_portfolio",
        actor="runtime_facade",
    )
    facade.record_trace_span(
        task_id,
        span_kind="model_call",
        name="lead_review_smoke",
        status="pass",
        actor="research_lead",
        node_execution_id=node["node_execution_id"],
        latency_ms=12,
        token_count=0,
        cost_amount=0.0,
        model_name="deterministic",
        provider="local",
        payload={"purpose": "S1 trace baseline"},
    )
    facade.store.transition_task(task_id, "succeeded", actor="verifier", message="S1 dogfood task complete", progress=100)
    resumed = facade.resume_task(task_id, actor="human_reviewer", reason="resume replay check", checkpoint_ref_id=checkpoint["checkpoint_ref_id"])
    facade.store.transition_task(task_id, "running", actor="research_lead", message="resumed task running", progress=20)
    facade.store.transition_task(task_id, "succeeded", actor="verifier", message="resumed task complete", progress=100)
    replay = facade.replay_task(task_id)

    gateway_task = facade.import_gateway_task(
        {
            "task_id": "s1_gateway_compat_task",
            "trace_id": "trace_s1_gateway_compat",
            "query": "Check Java gateway payload compatibility",
            "user_id": "gateway_user",
            "case_id": "gateway_compat",
            "mode": "local_smoke",
            "metadata": {"gateway": "java"},
        }
    )
    facade.record_worker_update(
        gateway_task["task"]["task_id"],
        {
            "status": "SUCCESS",
            "progress": 100,
            "memo": "Gateway compatibility update succeeded.",
            "evidence": [{"source_family": "runtime_bridge_smoke"}],
            "events": [{"stream": "worker", "message": "gateway worker update imported"}],
        },
    )

    gate_rows = evaluate_s1_gates(facade.store, replay)
    summary = build_s1_summary(root, paths, gate_rows, facade.store)
    write_json(paths.schema_path, runtime_spine_schema_contract())
    write_jsonl(paths.gate_rows_path, gate_rows)
    write_json(paths.summary_path, summary)
    paths.report_path.write_text(render_s1_report(summary, gate_rows), encoding="utf-8")
    return summary


def evaluate_s1_gates(store: RuntimeTaskSpineStore, replay: dict[str, Any]) -> list[dict[str, Any]]:
    counts = store.table_counts()
    schema_tables = set(counts)
    required_tables = set(runtime_spine_schema_contract()["tables"])
    with store._connect() as conn:
        metadata_schema = json_loads(
            conn.execute("select value_json from runtime_spine_metadata where key = 'schema_version'").fetchone()["value_json"],
            "",
        )
        workpaper_update_blocked = trigger_blocks_statement(
            conn,
            "update workpaper_events set actor = actor where workpaper_event_id = (select workpaper_event_id from workpaper_events limit 1)",
        )
    try:
        store.transition_task("s1_scope_task_nvda_ai_infra", "running", actor="test")
    except IllegalStatusTransition:
        illegal_transition_blocked = True
    except Exception:
        illegal_transition_blocked = False
    else:
        illegal_transition_blocked = False
    checks = [
        ("schema_tables_present", required_tables.issubset(schema_tables), "All required SQL-final runtime spine tables exist.", sorted(required_tables - schema_tables)),
        ("schema_metadata_version", metadata_schema == SCHEMA_VERSION, "Runtime spine metadata records schema version.", metadata_schema),
        ("state_machine_status_values", set(TASK_STATUSES) == set(runtime_spine_schema_contract()["status_values"]), "Status values are frozen in schema contract.", runtime_spine_schema_contract()["status_values"]),
        ("illegal_transition_blocked", illegal_transition_blocked, "Terminal task cannot transition back to running except through explicit resume.", {}),
        ("task_run_event_counts", counts["research_tasks"] >= 2 and counts["task_runs"] >= 3 and counts["task_events"] >= 12, "Dogfood and gateway tasks created enough task/run/event rows.", counts),
        ("artifact_node_checkpoint_trace_rows", all(counts[key] >= 1 for key in ["node_executions", "artifact_refs", "checkpoint_refs", "trace_spans"]), "Node, artifact, checkpoint, and trace rows exist.", counts),
        ("workpaper_append_only", counts["workpaper_events"] >= 1 and workpaper_update_blocked, "WorkpaperEvent ledger is append-only and has rows.", {"workpaper_events": counts["workpaper_events"], "update_blocked": workpaper_update_blocked}),
        ("resume_replay_reconstructs_state", replay["replay_status"] == "replayable" and len(replay["runs"]) >= 2 and replay["progress_projection"]["status"] == "succeeded", "Resume/replay reconstructs runs, events, and current projection.", {"run_count": len(replay["runs"]), "event_count": len(replay["events"]), "status": replay["progress_projection"]["status"]}),
        ("gateway_compatibility_rows", gateway_task_compat_pass(store), "Java gateway-style task payload and worker update are imported into the S1 ledger.", {}),
        ("projection_parity", projection_parity_pass(store), "Progress projection counts match underlying ledgers.", counts),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "slice_id": "S1",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in checks
    ]


def gateway_task_compat_pass(store: RuntimeTaskSpineStore) -> bool:
    state = store.get_task_state("s1_gateway_compat_task")
    replay = store.replay_task("s1_gateway_compat_task")
    return (
        state["task"]["status"] == "succeeded"
        and state["task"]["trace_id"] == "trace_s1_gateway_compat"
        and any(row["artifact_type"] == "gateway_worker_update_payload" for row in replay["artifact_refs"])
        and any(row["event_type"] == "worker_event" for row in replay["events"])
    )


def projection_parity_pass(store: RuntimeTaskSpineStore) -> bool:
    with store._connect() as conn:
        rows = conn.execute("select task_id from research_tasks").fetchall()
        for row in rows:
            task_id = row["task_id"]
            projection = conn.execute("select * from task_progress_projection where task_id = ?", (task_id,)).fetchone()
            if projection is None:
                return False
            checks = {
                "event_count": scalar_count(conn, "task_events", task_id),
                "node_count": scalar_count(conn, "node_executions", task_id),
                "artifact_count": scalar_count(conn, "artifact_refs", task_id),
                "workpaper_event_count": scalar_count(conn, "workpaper_events", task_id),
                "checkpoint_count": scalar_count(conn, "checkpoint_refs", task_id),
                "trace_span_count": scalar_count(conn, "trace_spans", task_id),
            }
            for key, expected in checks.items():
                if int(projection[key] or 0) != expected:
                    return False
    return True


def trigger_blocks_statement(conn: sqlite3.Connection, sql: str) -> bool:
    try:
        conn.execute(sql)
    except sqlite3.DatabaseError as exc:
        return "append_only" in str(exc) or "forbidden" in str(exc)
    return False


def build_s1_summary(root: Path, paths: RuntimeSpinePaths, gate_rows: list[dict[str, Any]], store: RuntimeTaskSpineStore) -> dict[str, Any]:
    failed = [row for row in gate_rows if row["status"] != "pass"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "status": "pass" if not failed else "fail",
        "release_decision": "S1_L4_scope_pass" if not failed else "S1_blocked",
        "closeout_level": "L4_scope_pass" if not failed else "blocked",
        "counts": {**store.table_counts(), "gate_count": len(gate_rows), "gate_fail_count": len(failed)},
        "outputs": {
            "schema": rel_path(paths.schema_path, root),
            "sqlite_store": rel_path(paths.db_path, root),
            "gate_rows": rel_path(paths.gate_rows_path, root),
            "summary": rel_path(paths.summary_path, root),
            "closeout_report": rel_path(paths.report_path, root),
        },
        "failed_gates": failed,
        "next_slice_unlocked": "S2" if not failed else None,
        "boundary": "S1 closes the runtime task spine scope only; it does not claim full-product production readiness.",
    }


def render_s1_report(summary: dict[str, Any], gate_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R53-R60 S1 Runtime Task Spine L4 Scope Closeout",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Status: `{summary['status']}`",
        f"Release decision: `{summary['release_decision']}`",
        f"Closeout level: `{summary['closeout_level']}`",
        "",
        "## Counts",
        "",
    ]
    for key, value in summary["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate Rows", ""])
    for row in gate_rows:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Boundary", "", summary["boundary"], ""])
    return "\n".join(lines)


def normalize_status(status: str) -> str:
    value = str(status or "").strip()
    upper = value.upper()
    if upper in GATEWAY_STATUS_MAP:
        value = GATEWAY_STATUS_MAP[upper]
    else:
        value = value.lower()
    if value not in TASK_STATUSES:
        raise ValueError(f"invalid_task_status:{status}")
    return value


def normalize_node_status(status: str) -> str:
    value = str(status or "").strip().lower()
    if value in {"ok", "success", "succeeded"}:
        return "pass"
    if value in {"fail", "failed", "error"}:
        return "fail"
    return value or "unknown"


def scalar_count(conn: sqlite3.Connection, table: str, task_id: str) -> int:
    return int(conn.execute(f"select count(*) from {table} where task_id = ?", (task_id,)).fetchone()[0])


def elapsed_from_iso(started_at: str | None, finished_at: str) -> int | None:
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((finish - start).total_seconds() * 1000))


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def decode_json_fields(row: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(row)
    for key in list(decoded):
        if key.endswith("_json"):
            decoded[key[:-5]] = json_loads(decoded.pop(key), {})
    return decoded


def decode_task_row(row: dict[str, Any]) -> dict[str, Any]:
    decoded = decode_json_fields(row)
    if "objective" not in decoded:
        decoded["objective"] = {}
    if "metadata" not in decoded:
        decoded["metadata"] = {}
    return decoded


def decode_run_row(row: dict[str, Any]) -> dict[str, Any]:
    return decode_json_fields(row)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
