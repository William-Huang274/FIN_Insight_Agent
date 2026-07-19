from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest, utc_now

from .case_service import CasePrincipal, CaseService, CaseServiceError
from .local_research_service import LocalResearchServiceError, P36LocalResearchService


@dataclass(frozen=True)
class AnalystBaselineSubmission:
    strongest_source: str
    material_limitation: str
    numeric_verification: str
    weakest_judgment: str
    required_modification: str
    writer_usefulness_score: int
    writer_usefulness_reason: str
    time_to_find_source_seconds: int
    time_to_verify_numeric_seconds: int
    time_to_identify_weakest_judgment_seconds: int
    time_to_review_writer_seconds: int
    repeated_work_count: int
    blocking_ui_issue: str
    idempotency_key: str


@dataclass(frozen=True)
class SeniorReviewSubmission:
    reviewer_ref: str
    reviewer_role: str
    decision: str
    research_quality_score: int
    evidence_quality_score: int
    senior_reviewability_score: int
    numeric_reproducibility_confirmed: bool
    gap_boundaries_preserved: bool
    exact_digest_confirmed: bool
    review_comment: str
    bounded_follow_up: tuple[str, ...]
    idempotency_key: str


class HumanBaselineServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class HumanBaselineService:
    """Persist exact-digest human product baselines outside the business Case store."""

    SCHEMA_VERSION = "fin_ia_0_1_human_baseline_store_v1_0"

    def __init__(
        self,
        store_path: str | Path,
        case_service: CaseService,
        research_service: P36LocalResearchService,
    ) -> None:
        self._store_path = Path(store_path).resolve()
        self._case_service = case_service
        self._research_service = research_service
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._configure()

    @classmethod
    def from_services(
        cls,
        case_service: CaseService,
        research_service: P36LocalResearchService,
        *,
        repo_root: str | Path,
    ) -> "HumanBaselineService":
        default_path = Path(repo_root).resolve() / ".codex_runtime" / "internal-alpha" / "human-baseline.sqlite3"
        return cls(os.environ.get("FINSIGHT_HUMAN_BASELINE_STORE", str(default_path)), case_service, research_service)

    def start_session(
        self,
        case_id: str,
        principal: CasePrincipal,
        *,
        participant_ref: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "baseline:write")
        if not participant_ref.strip() or not idempotency_key.strip():
            raise HumanBaselineServiceError("request_validation_error", 422)
        binding = self._current_binding(case_id, principal)
        payload = {
            "case_id": case_id,
            "participant_ref": participant_ref.strip(),
            "binding": binding,
        }
        payload_digest = canonical_digest(payload)
        session_id = "human_baseline_" + canonical_digest(
            {
                "tenant_id": principal.tenant_id,
                "project_id": principal.project_id,
                "case_id": case_id,
                "idempotency_key": idempotency_key,
            }
        )[:24]
        now = utc_now().isoformat()
        with self._connect() as connection:
            existing = self._event_for_key(connection, principal, idempotency_key)
            if existing:
                self._require_same_payload(existing, payload_digest)
                return self._session(connection, session_id, principal)
            connection.execute(
                """
                INSERT INTO human_baseline_sessions (
                    session_id, tenant_id, project_id, case_id, participant_ref,
                    status, artifact_binding_json, artifact_binding_digest,
                    analyst_submission_json, senior_review_json, final_review_digest,
                    started_at, analyst_submitted_at, senior_reviewed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, ?)
                """,
                (
                    session_id,
                    principal.tenant_id,
                    principal.project_id,
                    case_id,
                    participant_ref.strip(),
                    "in_progress",
                    self._json(binding),
                    binding["artifact_binding_digest"],
                    now,
                    now,
                ),
            )
            self._append_event(
                connection,
                session_id=session_id,
                principal=principal,
                event_type="baseline_started",
                idempotency_key=idempotency_key,
                payload=payload,
                payload_digest=payload_digest,
                created_at=now,
            )
            connection.commit()
            return self._session(connection, session_id, principal)

    def submit_analyst_baseline(
        self,
        case_id: str,
        session_id: str,
        principal: CasePrincipal,
        submission: AnalystBaselineSubmission,
    ) -> dict[str, Any]:
        self._require_permission(principal, "baseline:write")
        self._validate_analyst_submission(submission)
        with self._connect() as connection:
            session = self._session(connection, session_id, principal, expected_case_id=case_id)
            existing = self._event_for_key(connection, principal, submission.idempotency_key)
            payload = self._analyst_payload(submission)
            payload_digest = canonical_digest(payload)
            if existing:
                self._require_same_payload(existing, payload_digest)
                return session
            if session["status"] not in {"in_progress", "analyst_submitted"}:
                raise HumanBaselineServiceError(
                    "baseline_state_conflict", 409, session_id=session_id, current_status=session["status"]
                )
            self._require_current_binding(session, principal)
            now = utc_now().isoformat()
            connection.execute(
                """
                UPDATE human_baseline_sessions
                   SET status = ?, analyst_submission_json = ?, analyst_submitted_at = ?, updated_at = ?
                 WHERE session_id = ?
                """,
                ("analyst_submitted", self._json(payload), now, now, session_id),
            )
            self._append_event(
                connection,
                session_id=session_id,
                principal=principal,
                event_type="analyst_baseline_submitted",
                idempotency_key=submission.idempotency_key,
                payload=payload,
                payload_digest=payload_digest,
                created_at=now,
            )
            connection.commit()
            return self._session(connection, session_id, principal)

    def submit_senior_review(
        self,
        case_id: str,
        session_id: str,
        principal: CasePrincipal,
        submission: SeniorReviewSubmission,
    ) -> dict[str, Any]:
        self._require_permission(principal, "baseline:review")
        self._validate_senior_submission(submission)
        with self._connect() as connection:
            session = self._session(connection, session_id, principal, expected_case_id=case_id)
            payload = self._senior_payload(submission)
            payload_digest = canonical_digest(payload)
            existing = self._event_for_key(connection, principal, submission.idempotency_key)
            if existing:
                self._require_same_payload(existing, payload_digest)
                return session
            if session["status"] not in {"analyst_submitted", "exact_human_senior_review_recorded"}:
                raise HumanBaselineServiceError(
                    "analyst_baseline_required", 409, session_id=session_id, current_status=session["status"]
                )
            self._require_current_binding(session, principal)
            if not submission.exact_digest_confirmed:
                raise HumanBaselineServiceError("exact_digest_confirmation_required", 422)
            final_review_digest = canonical_digest(
                {
                    "artifact_binding_digest": session["artifact_binding_digest"],
                    "analyst_submission": session["analyst_submission"],
                    "senior_review": payload,
                }
            )
            now = utc_now().isoformat()
            connection.execute(
                """
                UPDATE human_baseline_sessions
                   SET status = ?, senior_review_json = ?, final_review_digest = ?,
                       senior_reviewed_at = ?, updated_at = ?
                 WHERE session_id = ?
                """,
                (
                    "exact_human_senior_review_recorded",
                    self._json(payload),
                    final_review_digest,
                    now,
                    now,
                    session_id,
                ),
            )
            self._append_event(
                connection,
                session_id=session_id,
                principal=principal,
                event_type="exact_human_senior_review_recorded",
                idempotency_key=submission.idempotency_key,
                payload={**payload, "final_review_digest": final_review_digest},
                payload_digest=payload_digest,
                created_at=now,
            )
            connection.commit()
            return self._session(connection, session_id, principal)

    def list_sessions(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "baseline:read")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id FROM human_baseline_sessions
                 WHERE tenant_id = ? AND project_id = ? AND case_id = ?
                 ORDER BY started_at DESC
                """,
                (principal.tenant_id, principal.project_id, case_id),
            ).fetchall()
            sessions = [self._session(connection, str(row["session_id"]), principal) for row in rows]
        return {
            "schema_version": self.SCHEMA_VERSION,
            "case_id": case_id,
            "sessions": sessions,
            "counts": {
                "session_count": len(sessions),
                "completed_review_count": sum(
                    item["status"] == "exact_human_senior_review_recorded" for item in sessions
                ),
            },
            "boundary": self._boundary(),
        }

    def get_session(
        self,
        case_id: str,
        session_id: str,
        principal: CasePrincipal,
    ) -> dict[str, Any]:
        self._require_permission(principal, "baseline:read")
        with self._connect() as connection:
            return self._session(connection, session_id, principal, expected_case_id=case_id)

    def _current_binding(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        try:
            workspace = self._case_service.get_case(case_id, principal)
            preview = self._research_service.preview(case_id, principal)
            analysis = self._research_service.analysis_preview(case_id, principal)
        except (CaseServiceError, LocalResearchServiceError) as exc:
            status_code = getattr(exc, "status_code", 409)
            detail = getattr(exc, "detail", {})
            raise HumanBaselineServiceError(
                "exact_candidate_unavailable", status_code, case_id=case_id, cause=detail
            ) from exc
        payload = {
            "case_id": case_id,
            "case_version": int(workspace["case_version"]),
            "research_preview_digest": str(preview["preview_digest"]),
            "analysis_digest": str(analysis["analysis_digest"]),
            "workpaper_digest": str(analysis["workpaper"]["content_digest"]),
            "writer_digest": str(analysis["writer"]["content_digest"]),
        }
        return {**payload, "artifact_binding_digest": canonical_digest(payload)}

    def _require_current_binding(self, session: Mapping[str, Any], principal: CasePrincipal) -> None:
        current = self._current_binding(str(session["case_id"]), principal)
        if current["artifact_binding_digest"] != session["artifact_binding_digest"]:
            raise HumanBaselineServiceError(
                "exact_candidate_drift",
                409,
                session_id=session["session_id"],
                recorded_digest=session["artifact_binding_digest"],
                current_digest=current["artifact_binding_digest"],
            )

    def _configure(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS human_baseline_sessions (
                    session_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    participant_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_binding_json TEXT NOT NULL,
                    artifact_binding_digest TEXT NOT NULL,
                    analyst_submission_json TEXT,
                    senior_review_json TEXT,
                    final_review_digest TEXT,
                    started_at TEXT NOT NULL,
                    analyst_submitted_at TEXT,
                    senior_reviewed_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_human_baseline_case
                    ON human_baseline_sessions (tenant_id, project_id, case_id, started_at);
                CREATE TABLE IF NOT EXISTS human_baseline_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    actor_ref TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (tenant_id, project_id, idempotency_key)
                );
                """
            )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self._store_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _session(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        principal: CasePrincipal,
        *,
        expected_case_id: str | None = None,
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT * FROM human_baseline_sessions
             WHERE session_id = ? AND tenant_id = ? AND project_id = ?
            """,
            (session_id, principal.tenant_id, principal.project_id),
        ).fetchone()
        if not row or (expected_case_id and row["case_id"] != expected_case_id):
            raise HumanBaselineServiceError("baseline_session_not_found", 404, session_id=session_id)
        events = connection.execute(
            """
            SELECT event_id, event_type, actor_ref, payload_digest, created_at
              FROM human_baseline_events WHERE session_id = ? ORDER BY created_at, event_id
            """,
            (session_id,),
        ).fetchall()
        return {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": str(row["session_id"]),
            "case_id": str(row["case_id"]),
            "participant_ref": str(row["participant_ref"]),
            "status": str(row["status"]),
            "artifact_binding": json.loads(str(row["artifact_binding_json"])),
            "artifact_binding_digest": str(row["artifact_binding_digest"]),
            "analyst_submission": self._json_or_none(row["analyst_submission_json"]),
            "senior_review": self._json_or_none(row["senior_review_json"]),
            "final_review_digest": row["final_review_digest"],
            "started_at": str(row["started_at"]),
            "analyst_submitted_at": row["analyst_submitted_at"],
            "senior_reviewed_at": row["senior_reviewed_at"],
            "updated_at": str(row["updated_at"]),
            "events": [dict(event) for event in events],
            "execution_counts": {
                "case_mutations": 0,
                "network_calls": 0,
                "model_calls": 0,
                "commercial_data_spend": 0,
                "release_admissions": 0,
            },
            "boundary": self._boundary(),
        }

    @staticmethod
    def _analyst_payload(submission: AnalystBaselineSubmission) -> dict[str, Any]:
        return {
            "strongest_source": submission.strongest_source.strip(),
            "material_limitation": submission.material_limitation.strip(),
            "numeric_verification": submission.numeric_verification.strip(),
            "weakest_judgment": submission.weakest_judgment.strip(),
            "required_modification": submission.required_modification.strip(),
            "writer_usefulness_score": submission.writer_usefulness_score,
            "writer_usefulness_reason": submission.writer_usefulness_reason.strip(),
            "time_to_find_source_seconds": submission.time_to_find_source_seconds,
            "time_to_verify_numeric_seconds": submission.time_to_verify_numeric_seconds,
            "time_to_identify_weakest_judgment_seconds": submission.time_to_identify_weakest_judgment_seconds,
            "time_to_review_writer_seconds": submission.time_to_review_writer_seconds,
            "repeated_work_count": submission.repeated_work_count,
            "blocking_ui_issue": submission.blocking_ui_issue.strip(),
        }

    @staticmethod
    def _senior_payload(submission: SeniorReviewSubmission) -> dict[str, Any]:
        return {
            "reviewer_ref": submission.reviewer_ref.strip(),
            "reviewer_role": submission.reviewer_role,
            "decision": submission.decision,
            "research_quality_score": submission.research_quality_score,
            "evidence_quality_score": submission.evidence_quality_score,
            "senior_reviewability_score": submission.senior_reviewability_score,
            "numeric_reproducibility_confirmed": submission.numeric_reproducibility_confirmed,
            "gap_boundaries_preserved": submission.gap_boundaries_preserved,
            "exact_digest_confirmed": submission.exact_digest_confirmed,
            "review_comment": submission.review_comment.strip(),
            "bounded_follow_up": [item.strip() for item in submission.bounded_follow_up if item.strip()],
            "attestation": "real_human_input_recorded_by_product_ui",
        }

    @staticmethod
    def _validate_analyst_submission(submission: AnalystBaselineSubmission) -> None:
        required = (
            submission.strongest_source,
            submission.material_limitation,
            submission.numeric_verification,
            submission.weakest_judgment,
            submission.required_modification,
            submission.writer_usefulness_reason,
            submission.idempotency_key,
        )
        timings = (
            submission.time_to_find_source_seconds,
            submission.time_to_verify_numeric_seconds,
            submission.time_to_identify_weakest_judgment_seconds,
            submission.time_to_review_writer_seconds,
            submission.repeated_work_count,
        )
        if any(not item.strip() for item in required) or not 1 <= submission.writer_usefulness_score <= 5:
            raise HumanBaselineServiceError("request_validation_error", 422)
        if any(value < 0 for value in timings):
            raise HumanBaselineServiceError("request_validation_error", 422, field="timing")

    @staticmethod
    def _validate_senior_submission(submission: SeniorReviewSubmission) -> None:
        if submission.reviewer_role not in {"senior_analyst", "domain_reviewer"}:
            raise HumanBaselineServiceError("request_validation_error", 422, field="reviewer_role")
        if submission.decision not in {"approve", "conditional_approve", "return_for_follow_up"}:
            raise HumanBaselineServiceError("request_validation_error", 422, field="decision")
        scores = (
            submission.research_quality_score,
            submission.evidence_quality_score,
            submission.senior_reviewability_score,
        )
        if (
            not submission.reviewer_ref.strip()
            or not submission.review_comment.strip()
            or not submission.idempotency_key.strip()
            or any(not 1 <= score <= 5 for score in scores)
            or len(submission.bounded_follow_up) > 3
        ):
            raise HumanBaselineServiceError("request_validation_error", 422)

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        session_id: str,
        principal: CasePrincipal,
        event_type: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        payload_digest: str,
        created_at: str,
    ) -> None:
        event_id = "baseline_event_" + canonical_digest(
            {"session_id": session_id, "event_type": event_type, "idempotency_key": idempotency_key}
        )[:24]
        connection.execute(
            """
            INSERT INTO human_baseline_events (
                event_id, session_id, tenant_id, project_id, actor_ref, event_type,
                idempotency_key, payload_json, payload_digest, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                session_id,
                principal.tenant_id,
                principal.project_id,
                principal.actor_id,
                event_type,
                idempotency_key,
                self._json(payload),
                payload_digest,
                created_at,
            ),
        )

    @staticmethod
    def _event_for_key(
        connection: sqlite3.Connection,
        principal: CasePrincipal,
        idempotency_key: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT * FROM human_baseline_events
             WHERE tenant_id = ? AND project_id = ? AND idempotency_key = ?
            """,
            (principal.tenant_id, principal.project_id, idempotency_key),
        ).fetchone()

    @staticmethod
    def _require_same_payload(event: Mapping[str, Any], payload_digest: str) -> None:
        if event["payload_digest"] != payload_digest:
            raise HumanBaselineServiceError("idempotency_conflict", 409)

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if (
            not principal.tenant_id
            or not principal.project_id
            or not principal.actor_id
            or permission not in principal.permissions
        ):
            raise HumanBaselineServiceError("permission_denied", 403, required_permission=permission)

    @staticmethod
    def _json(value: Mapping[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _json_or_none(value: Any) -> dict[str, Any] | None:
        return json.loads(str(value)) if value else None

    @staticmethod
    def _boundary() -> str:
        return (
            "Human baseline records are internal product-evaluation evidence bound to exact read-only "
            "research artifacts. They do not mutate the business Case, authorize RG1, or admit a release."
        )
