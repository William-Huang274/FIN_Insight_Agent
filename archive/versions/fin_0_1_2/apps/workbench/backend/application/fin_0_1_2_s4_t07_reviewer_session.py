from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Callable, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import read_registered_runtime_json

from .fin_0_1_2_s4_t06_current_product_projection import CurrentProductPrincipal
from .fin_0_1_2_s4_t07_reviewer_packet import CurrentProductReviewerPacketService


T07_B_SESSION_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t07_b_reviewer_session_"
    "runtime_resource_registry_v1_0.json"
)
T07_B_SESSION_RESOURCE_ID = "fin_0_1_2.s4.t07_b.reviewer_session_contract"
T07_B_SESSION_SCHEMA = "fin_ia_0_1_2_s4_t07_b_reviewer_session_contract_v1_0"
T07_B_SESSION_API_SCHEMA = "fin_ia_0_1_2_s4_t07_b_reviewer_session_api_v1_0"


@dataclass(frozen=True)
class IssuedReviewerSession:
    session_id: str
    credential: str
    reviewer_ref: str
    reviewer_role: str
    expires_at: str
    case_key: str
    packet_digest: str


@dataclass(frozen=True)
class AuthenticatedReviewer:
    session_id: str
    reviewer_ref: str
    reviewer_role: str
    permission: str
    case_key: str
    manifest_digest: str
    case_projection_digest: str
    handoff_digest: str
    packet_digest: str


@dataclass(frozen=True)
class QualifiedReviewDecisionDraft:
    action: str
    reviewer_note: str
    idempotency_key: str
    target_surface: str | None = None
    expected_target_view_digest: str | None = None
    reason_code: str | None = None


class ReviewerSessionError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 409, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


def _require(condition: bool, code: str, status_code: int = 409) -> None:
    if not condition:
        raise ReviewerSessionError(code, status_code)


class CurrentProductReviewerSessionService:
    """Digest-only internal reviewer authentication and decision control."""

    def __init__(
        self,
        packet_service: CurrentProductReviewerPacketService,
        db_path: str | Path,
        contract: Mapping[str, Any],
        *,
        clock: Callable[[], datetime] | None = None,
        credential_factory: Callable[[], str] | None = None,
    ) -> None:
        self._packet_service = packet_service
        self._db_path = Path(db_path)
        self._contract = dict(contract)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        prefix = str(self._contract.get("session_policy", {}).get("credential_prefix") or "")
        self._credential_factory = credential_factory or (
            lambda: prefix + secrets.token_urlsafe(32)
        )
        self._validate_contract()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @classmethod
    def from_repository(
        cls,
        repository_root: str | Path,
        packet_service: CurrentProductReviewerPacketService,
        db_path: str | Path,
        **kwargs: Any,
    ) -> "CurrentProductReviewerSessionService":
        contract = read_registered_runtime_json(
            repository_root,
            T07_B_SESSION_RESOURCE_ID,
            registry_ref=T07_B_SESSION_REGISTRY_REF,
        )
        return cls(packet_service, db_path, contract, **kwargs)

    def issue_session(
        self,
        *,
        admin_actor_ref: str,
        reviewer_ref: str,
        reviewer_role: str,
        ttl_seconds: int,
    ) -> IssuedReviewerSession:
        _require(
            admin_actor_ref in self._contract["offline_admin_allowlist"],
            "t07_reviewer_session_offline_admin_required",
            403,
        )
        allowed_roles = self._contract["qualified_identity_allowlist"].get(
            reviewer_ref, []
        )
        _require(
            reviewer_role in allowed_roles,
            "t07_reviewer_identity_or_role_not_qualified",
            403,
        )
        maximum = int(self._contract["session_policy"]["maximum_ttl_seconds"])
        _require(
            isinstance(ttl_seconds, int) and 0 < ttl_seconds <= maximum,
            "t07_reviewer_session_ttl_invalid",
            422,
        )
        packet = self._packet_service.get_packet("NVDA", self._read_principal())
        binding = packet["exact_binding"]
        now = self._now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        credential = self._credential_factory()
        prefix = self._contract["session_policy"]["credential_prefix"]
        _require(
            isinstance(credential, str)
            and credential.startswith(prefix)
            and len(credential.encode("utf-8")) >= len(prefix) + 32,
            "t07_reviewer_session_credential_factory_invalid",
        )
        credential_digest = self._credential_digest(credential)
        session_id = "review_session_" + canonical_digest(
            {
                "credential_digest": credential_digest,
                "reviewer_ref": reviewer_ref,
                "case_key": "NVDA",
                "handoff_digest": binding["T07_handoff_digest"],
            }
        )[:24]
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                """
                SELECT session_id FROM t07_reviewer_sessions
                WHERE reviewer_ref = ? AND case_key = ? AND handoff_digest = ?
                  AND revoked_at IS NULL AND expires_at > ?
                """,
                (
                    reviewer_ref,
                    "NVDA",
                    binding["T07_handoff_digest"],
                    self._iso(now),
                ),
            ).fetchone()
            _require(active is None, "t07_reviewer_active_session_exists")
            conn.execute(
                """
                INSERT INTO t07_reviewer_sessions (
                    session_id, credential_digest, reviewer_ref, reviewer_role,
                    permission, case_key, manifest_digest, case_projection_digest,
                    handoff_digest, packet_digest, issued_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    session_id,
                    credential_digest,
                    reviewer_ref,
                    reviewer_role,
                    self._contract["session_policy"]["required_permission"],
                    "NVDA",
                    binding["projection_manifest_digest"],
                    binding["case_projection_digest"],
                    binding["T07_handoff_digest"],
                    packet["packet_digest"],
                    self._iso(now),
                    self._iso(expires_at),
                ),
            )
            self._append_event(
                conn,
                "REVIEW_SESSION_ISSUED",
                session_id,
                {
                    "session_id": session_id,
                    "reviewer_ref": reviewer_ref,
                    "reviewer_role": reviewer_role,
                    "case_key": "NVDA",
                    "packet_digest": packet["packet_digest"],
                    "issued_at": self._iso(now),
                    "expires_at": self._iso(expires_at),
                    "credential_plaintext_persisted": False,
                },
            )
            conn.commit()
        return IssuedReviewerSession(
            session_id=session_id,
            credential=credential,
            reviewer_ref=reviewer_ref,
            reviewer_role=reviewer_role,
            expires_at=self._iso(expires_at),
            case_key="NVDA",
            packet_digest=packet["packet_digest"],
        )

    def authenticate(self, credential: str, *, expected_case_key: str) -> AuthenticatedReviewer:
        digest = self._credential_digest(credential) if credential else ""
        now = self._now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM t07_reviewer_sessions WHERE credential_digest = ?",
                (digest,),
            ).fetchone()
            reason: str | None = None
            if row is None:
                reason = "credential_not_recognized"
            elif not hmac.compare_digest(str(row["credential_digest"]), digest):
                reason = "credential_not_recognized"
            elif row["revoked_at"] is not None:
                reason = "session_revoked"
            elif self._parse(str(row["expires_at"])) <= now:
                reason = "session_expired"
            elif str(row["case_key"]) != str(expected_case_key).upper():
                reason = "session_case_scope_mismatch"
            if reason is not None:
                self._append_event(
                    conn,
                    "REVIEW_SESSION_AUTHENTICATION_REJECTED",
                    str(row["session_id"]) if row is not None else None,
                    {"rejected_at": self._iso(now), "reason_code": reason},
                )
                conn.commit()
                raise ReviewerSessionError("t07_reviewer_authentication_failed", 401)
            packet = self._packet_service.get_packet("NVDA", self._read_principal())
            if (
                row["manifest_digest"] != packet["exact_binding"]["projection_manifest_digest"]
                or row["case_projection_digest"] != packet["exact_binding"]["case_projection_digest"]
                or row["handoff_digest"] != packet["exact_binding"]["T07_handoff_digest"]
                or row["packet_digest"] != packet["packet_digest"]
            ):
                self._append_event(
                    conn,
                    "REVIEW_SESSION_AUTHENTICATION_REJECTED",
                    str(row["session_id"]),
                    {"rejected_at": self._iso(now), "reason_code": "exact_scope_drift"},
                )
                conn.commit()
                raise ReviewerSessionError("t07_reviewer_session_exact_scope_drift", 409)
            self._append_event(
                conn,
                "REVIEW_SESSION_AUTHENTICATED",
                str(row["session_id"]),
                {
                    "session_id": str(row["session_id"]),
                    "case_key": str(row["case_key"]),
                    "authenticated_at": self._iso(now),
                },
            )
            conn.commit()
        return self._authenticated(row)

    def revoke_session(self, *, admin_actor_ref: str, session_id: str) -> None:
        _require(
            admin_actor_ref in self._contract["offline_admin_allowlist"],
            "t07_reviewer_session_offline_admin_required",
            403,
        )
        now = self._iso(self._now())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT revoked_at FROM t07_reviewer_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            _require(row is not None, "t07_reviewer_session_not_found", 404)
            if row["revoked_at"] is None:
                conn.execute(
                    "UPDATE t07_reviewer_sessions SET revoked_at = ? WHERE session_id = ?",
                    (now, session_id),
                )
                self._append_event(
                    conn,
                    "REVIEW_SESSION_REVOKED",
                    session_id,
                    {"session_id": session_id, "revoked_at": now},
                )
            conn.commit()

    def get_review_state(self, credential: str) -> dict[str, Any]:
        reviewer = self.authenticate(credential, expected_case_key="NVDA")
        return self._state(reviewer.session_id, reviewer)

    def record_decision(
        self, credential: str, draft: QualifiedReviewDecisionDraft
    ) -> dict[str, Any]:
        reviewer = self.authenticate(credential, expected_case_key="NVDA")
        policy = self._contract["decision_policy"]
        _require(draft.action in policy["allowed_actions"], "t07_review_action_invalid", 422)
        note = draft.reviewer_note.strip()
        _require(
            bool(note) and len(note) <= int(policy["reviewer_note_max_length"]),
            "t07_review_note_invalid",
            422,
        )
        _require(bool(draft.idempotency_key.strip()), "t07_review_idempotency_required", 422)
        packet = self._packet_service.get_packet("NVDA", self._read_principal())
        if draft.action == "return_for_repair":
            view_digests = packet["exact_binding"]["view_digests"]
            _require(
                draft.target_surface in view_digests
                and draft.expected_target_view_digest == view_digests[draft.target_surface]
                and bool((draft.reason_code or "").strip()),
                "t07_review_return_scope_invalid",
                422,
            )
        else:
            _require(
                draft.target_surface is None
                and draft.expected_target_view_digest is None
                and draft.reason_code is None,
                "t07_review_accept_must_not_carry_return_scope",
                422,
            )
        command = {
            "session_id": reviewer.session_id,
            "packet_digest": reviewer.packet_digest,
            **draft.__dict__,
            "reviewer_note": note,
        }
        command_digest = canonical_digest(command)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT command_digest FROM t07_reviewer_decisions WHERE idempotency_scope = ?",
                (f"{reviewer.session_id}:{draft.idempotency_key}",),
            ).fetchone()
            if existing is not None:
                _require(
                    existing["command_digest"] == command_digest,
                    "t07_review_idempotency_conflict",
                )
                conn.commit()
                return self._state(reviewer.session_id, reviewer)
            terminal = conn.execute(
                "SELECT decision_id FROM t07_reviewer_decisions WHERE session_id = ?",
                (reviewer.session_id,),
            ).fetchone()
            _require(terminal is None, "t07_review_terminal_decision_exists")
            now = self._iso(self._now())
            payload = {
                "decision_id": "qualified_review_" + command_digest[:24],
                "session_id": reviewer.session_id,
                "reviewer_ref": reviewer.reviewer_ref,
                "reviewer_role": reviewer.reviewer_role,
                "case_key": "NVDA",
                "manifest_digest": reviewer.manifest_digest,
                "case_projection_digest": reviewer.case_projection_digest,
                "handoff_digest": reviewer.handoff_digest,
                "packet_digest": reviewer.packet_digest,
                "action": draft.action,
                "reviewer_note": note,
                "target_surface": draft.target_surface,
                "target_view_digest": draft.expected_target_view_digest,
                "reason_code": draft.reason_code,
                "decided_at": now,
                "authenticated_reviewer_identity": True,
                "qualified_human_review": True,
                "bounded_NVDA_R3": draft.action == "accept_exact_version",
                "release_qualified": False,
            }
            event_digest = self._append_event(
                conn,
                "QUALIFIED_REVIEW_DECISION_RECORDED",
                reviewer.session_id,
                payload,
            )
            conn.execute(
                """
                INSERT INTO t07_reviewer_decisions (
                    decision_id, session_id, idempotency_scope, command_digest,
                    payload_json, event_digest
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["decision_id"],
                    reviewer.session_id,
                    f"{reviewer.session_id}:{draft.idempotency_key}",
                    command_digest,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    event_digest,
                ),
            )
            conn.commit()
        return self._state(reviewer.session_id, reviewer)

    def _state(self, session_id: str, reviewer: AuthenticatedReviewer) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, event_digest FROM t07_reviewer_decisions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            events = conn.execute(
                "SELECT * FROM t07_reviewer_security_events ORDER BY event_sequence"
            ).fetchall()
        previous = None
        for expected, event in enumerate(events, start=1):
            payload = json.loads(str(event["payload_json"]))
            body = {
                "event_sequence": expected,
                "event_type": event["event_type"],
                "session_id": event["session_id"],
                "previous_event_digest": previous,
                "payload_digest": canonical_digest(payload),
                "payload": payload,
            }
            _require(
                event["event_sequence"] == expected
                and event["previous_event_digest"] == previous
                and event["payload_digest"] == body["payload_digest"]
                and event["event_digest"] == canonical_digest(body),
                "t07_reviewer_event_chain_invalid",
            )
            previous = str(event["event_digest"])
        decision = json.loads(str(row["payload_json"])) if row else None
        body = {
            "schema_version": T07_B_SESSION_API_SCHEMA,
            "case_key": "NVDA",
            "session": {
                "session_id": reviewer.session_id,
                "reviewer_ref": reviewer.reviewer_ref,
                "reviewer_role": reviewer.reviewer_role,
                "permission": reviewer.permission,
                "authenticated": True,
                "credential_plaintext_persisted": False,
            },
            "exact_binding": {
                "manifest_digest": reviewer.manifest_digest,
                "case_projection_digest": reviewer.case_projection_digest,
                "handoff_digest": reviewer.handoff_digest,
                "packet_digest": reviewer.packet_digest,
            },
            "decision": decision,
            "event_replay": {
                "integrity": "pass",
                "event_count": len(events),
                "head_event_digest": previous,
            },
            "acceptance": {
                "authenticated_reviewer_identity": True,
                "qualified_human_review": decision is not None,
                "NVDA_R3": bool(decision and decision["bounded_NVDA_R3"]),
                "release_qualified": False,
            },
        }
        return {**body, "state_digest": canonical_digest(body)}

    def _append_event(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        session_id: str | None,
        payload: Mapping[str, Any],
    ) -> str:
        allowed = self._contract["event_policy"]["event_types"]
        _require(event_type in allowed, "t07_reviewer_event_type_invalid")
        previous = conn.execute(
            "SELECT event_sequence, event_digest FROM t07_reviewer_security_events ORDER BY event_sequence DESC LIMIT 1"
        ).fetchone()
        sequence = int(previous["event_sequence"]) + 1 if previous else 1
        previous_digest = str(previous["event_digest"]) if previous else None
        payload_body = dict(payload)
        payload_digest = canonical_digest(payload_body)
        body = {
            "event_sequence": sequence,
            "event_type": event_type,
            "session_id": session_id,
            "previous_event_digest": previous_digest,
            "payload_digest": payload_digest,
            "payload": payload_body,
        }
        event_digest = canonical_digest(body)
        conn.execute(
            """
            INSERT INTO t07_reviewer_security_events (
                event_sequence, event_type, session_id, previous_event_digest,
                payload_digest, payload_json, event_digest
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sequence,
                event_type,
                session_id,
                previous_digest,
                payload_digest,
                json.dumps(payload_body, ensure_ascii=False, sort_keys=True),
                event_digest,
            ),
        )
        return event_digest

    def _validate_contract(self) -> None:
        body = {
            key: item for key, item in self._contract.items() if key != "contract_digest"
        }
        boundary = self._contract.get("hard_boundaries") or {}
        _require(
            self._contract.get("schema_version") == T07_B_SESSION_SCHEMA
            and self._contract.get("contract_digest") == canonical_digest(body),
            "t07_reviewer_session_contract_invalid",
        )
        _require(
            boundary.get("public_session_issuance_API") is False
            and boundary.get("credential_plaintext_persisted") is False
            and boundary.get("model_provider_network_financial_source_calls") == 0
            and boundary.get("automatic_repair_execution_or_T06_queue_mutation") is False
            and boundary.get("real_human_review_executed") is False
            and boundary.get("NVDA_R3") is False,
            "t07_reviewer_session_boundary_invalid",
        )

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS t07_reviewer_sessions (
                    session_id TEXT PRIMARY KEY,
                    credential_digest TEXT NOT NULL UNIQUE,
                    reviewer_ref TEXT NOT NULL,
                    reviewer_role TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    case_key TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL,
                    case_projection_digest TEXT NOT NULL,
                    handoff_digest TEXT NOT NULL,
                    packet_digest TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS t07_reviewer_security_events (
                    event_sequence INTEGER PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    session_id TEXT,
                    previous_event_digest TEXT,
                    payload_digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    event_digest TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS t07_reviewer_decisions (
                    decision_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL UNIQUE,
                    idempotency_scope TEXT NOT NULL UNIQUE,
                    command_digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    event_digest TEXT NOT NULL UNIQUE
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _credential_digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _read_principal() -> CurrentProductPrincipal:
        return CurrentProductPrincipal(
            mode="current", permissions=frozenset({"current_product:read"})
        )

    @staticmethod
    def _parse(value: str) -> datetime:
        return datetime.fromisoformat(value).astimezone(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")

    def _now(self) -> datetime:
        value = self._clock()
        _require(value.tzinfo is not None, "t07_reviewer_clock_must_be_timezone_aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _authenticated(row: sqlite3.Row) -> AuthenticatedReviewer:
        return AuthenticatedReviewer(
            session_id=str(row["session_id"]),
            reviewer_ref=str(row["reviewer_ref"]),
            reviewer_role=str(row["reviewer_role"]),
            permission=str(row["permission"]),
            case_key=str(row["case_key"]),
            manifest_digest=str(row["manifest_digest"]),
            case_projection_digest=str(row["case_projection_digest"]),
            handoff_digest=str(row["handoff_digest"]),
            packet_digest=str(row["packet_digest"]),
        )
