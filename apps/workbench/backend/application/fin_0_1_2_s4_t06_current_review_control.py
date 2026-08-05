from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import read_registered_runtime_json

from .fin_0_1_2_s4_t06_current_product_projection import (
    CURRENT_PRODUCT_CASE_KEYS,
    CURRENT_PRODUCT_READ_PERMISSION,
    CurrentProductPrincipal,
    CurrentProductProjectionError,
    CurrentProductProjectionService,
)


CURRENT_REVIEW_CONTROL_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s4_t06_current_product_review_control_"
    "runtime_resource_registry_v1_0.json"
)
CURRENT_REVIEW_CONTROL_RESOURCE_ID = (
    "fin_0_1_2.s4.t06.current_product_review_control_contract"
)
CURRENT_REVIEW_CONTROL_CONTRACT_SCHEMA = (
    "fin_ia_0_1_2_s4_t06_c_current_review_control_contract_v1_0"
)
CURRENT_REVIEW_CONTROL_API_SCHEMA = (
    "fin_ia_0_1_2_s4_t06_c_current_review_control_api_v1_0"
)


@dataclass(frozen=True)
class CurrentReviewControlPrincipal:
    mode: str
    actor_id: str
    permissions: frozenset[str]


@dataclass(frozen=True)
class CurrentReturnForRepairDraft:
    expected_manifest_digest: str
    expected_case_projection_digest: str
    target_surface: str
    expected_target_view_digest: str
    target_ref: str
    reason_code: str
    reviewer_note: str
    actor_ref: str
    idempotency_key: str


class CurrentReviewControlError(RuntimeError):
    def __init__(self, error_code: str, status_code: int = 409, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class CurrentProductReviewControlService:
    """Append-only control plane over immutable current product projections.

    Return requests never rewrite accepted R2 business truth. The service rebuilds
    its read model from a hash-chained local event log and emits an exact T07
    handoff packet; it does not perform repair, qualified review, or NVDA R3.
    """

    def __init__(
        self,
        projection: CurrentProductProjectionService,
        db_path: str | Path,
        *,
        contract: Mapping[str, Any],
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._projection = projection
        self._db_path = Path(db_path)
        self._contract = deepcopy(dict(contract))
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
        )
        self._configure()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @classmethod
    def from_repository(
        cls,
        repository_root: str | Path,
        projection: CurrentProductProjectionService,
        db_path: str | Path,
    ) -> "CurrentProductReviewControlService":
        contract = read_registered_runtime_json(
            repository_root,
            CURRENT_REVIEW_CONTROL_RESOURCE_ID,
            registry_ref=CURRENT_REVIEW_CONTROL_REGISTRY_REF,
        )
        return cls(projection, db_path, contract=contract)

    def get_state(
        self, case_key: str, principal: CurrentReviewControlPrincipal
    ) -> dict[str, Any]:
        self._require_read(principal)
        normalized = self._normalize_case(case_key)
        case_view = self._surface(normalized, "case")
        events = self._replay(normalized)
        requests = [deepcopy(event["payload"]) for event in events]
        head = events[-1]["event_digest"] if events else None
        replay_body = {
            "case_key": normalized,
            "manifest_digest": self._projection.manifest_digest,
            "case_projection_digest": case_view["case_projection_digest"],
            "event_count": len(events),
            "head_event_digest": head,
            "return_requests": requests,
        }
        replay_digest = canonical_digest(replay_body)
        handoff = self._handoff(normalized, case_view, requests, replay_digest)
        return {
            "schema_version": CURRENT_REVIEW_CONTROL_API_SCHEMA,
            "projection_mode": "current",
            **replay_body,
            "replay_integrity": "pass",
            "replay_digest": replay_digest,
            "T07_handoff": handoff,
            "hard_boundaries": deepcopy(self._contract["hard_boundaries"]),
        }

    def request_return_for_repair(
        self,
        case_key: str,
        draft: CurrentReturnForRepairDraft,
        principal: CurrentReviewControlPrincipal,
    ) -> dict[str, Any]:
        self._require_request(principal, draft)
        normalized = self._normalize_case(case_key)
        case_view = self._surface(normalized, "case")
        target_view = self._surface(normalized, draft.target_surface)
        self._require_exact_bindings(case_view, target_view, draft)
        reason = self._reason(draft.reason_code, draft.target_surface)
        note = draft.reviewer_note.strip()
        max_length = int(self._contract["wire_contract"]["reviewer_note_max_length"])
        if not note or len(note) > max_length:
            raise CurrentReviewControlError(
                "current_review_reviewer_note_invalid", 422, max_length=max_length
            )
        if draft.target_ref != f"surface:{draft.target_surface}":
            raise CurrentReviewControlError(
                "current_review_target_ref_invalid", 422
            )
        command = {
            "case_key": normalized,
            **draft.__dict__,
            "reviewer_note": note,
        }
        command_digest = canonical_digest(command)
        scope_key = f"{normalized}:{draft.actor_ref}:{draft.idempotency_key}"

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            reused = conn.execute(
                """
                SELECT command_digest
                FROM current_product_review_idempotency
                WHERE scope_key = ?
                """,
                (scope_key,),
            ).fetchone()
            if reused is not None:
                if reused["command_digest"] != command_digest:
                    raise CurrentReviewControlError(
                        "current_review_idempotency_conflict", 409
                    )
                conn.commit()
                return self.get_state(normalized, principal)

            previous = conn.execute(
                """
                SELECT case_sequence, event_digest
                FROM current_product_review_events
                WHERE case_key = ?
                ORDER BY case_sequence DESC
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            case_sequence = int(previous["case_sequence"]) + 1 if previous else 1
            previous_digest = str(previous["event_digest"]) if previous else None
            request_id = "current_return_" + canonical_digest(
                {
                    "case_key": normalized,
                    "actor_ref": draft.actor_ref,
                    "idempotency_key": draft.idempotency_key,
                    "command_digest": command_digest,
                }
            )[:24]
            payload = {
                "request_id": request_id,
                "request_version": 1,
                "action_type": self._contract["action_type"],
                "status": "repair_requested",
                "case_key": normalized,
                "manifest_digest": self._projection.manifest_digest,
                "case_projection_digest": case_view["case_projection_digest"],
                "target_surface": draft.target_surface,
                "target_view_digest": target_view["view_digest"],
                "target_ref": draft.target_ref,
                "reason_code": draft.reason_code,
                "reviewer_note": note,
                "repair_owner": reason["repair_owner"],
                "requested_resolution": reason["requested_resolution"],
                "actor_ref": draft.actor_ref,
                "requested_at": self._clock(),
                "qualified_human_review": False,
                "automatic_repair_execution": False,
            }
            payload_digest = canonical_digest(payload)
            event_body = {
                "event_type": "CURRENT_PRODUCT_RETURN_FOR_REPAIR_REQUESTED",
                "case_key": normalized,
                "case_sequence": case_sequence,
                "previous_event_digest": previous_digest,
                "payload_digest": payload_digest,
                "payload": payload,
            }
            event_digest = canonical_digest(event_body)
            conn.execute(
                """
                INSERT INTO current_product_review_events (
                    case_key, case_sequence, event_type, previous_event_digest,
                    payload_digest, payload_json, event_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized,
                    case_sequence,
                    event_body["event_type"],
                    previous_digest,
                    payload_digest,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    event_digest,
                ),
            )
            conn.execute(
                """
                INSERT INTO current_product_review_idempotency (
                    scope_key, command_digest, request_id, event_digest
                ) VALUES (?, ?, ?, ?)
                """,
                (scope_key, command_digest, request_id, event_digest),
            )
            conn.commit()
        return self.get_state(normalized, principal)

    def _replay(self, case_key: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT case_sequence, event_type, previous_event_digest,
                       payload_digest, payload_json, event_digest
                FROM current_product_review_events
                WHERE case_key = ?
                ORDER BY case_sequence ASC
                """,
                (case_key,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        previous_digest: str | None = None
        for expected_sequence, row in enumerate(rows, start=1):
            try:
                payload = json.loads(str(row["payload_json"]))
            except json.JSONDecodeError as exc:
                raise CurrentReviewControlError(
                    "current_review_event_payload_invalid"
                ) from exc
            if (
                row["case_sequence"] != expected_sequence
                or row["event_type"]
                != "CURRENT_PRODUCT_RETURN_FOR_REPAIR_REQUESTED"
                or row["previous_event_digest"] != previous_digest
                or row["payload_digest"] != canonical_digest(payload)
            ):
                raise CurrentReviewControlError(
                    "current_review_event_chain_invalid"
                )
            event_body = {
                "event_type": row["event_type"],
                "case_key": case_key,
                "case_sequence": row["case_sequence"],
                "previous_event_digest": row["previous_event_digest"],
                "payload_digest": row["payload_digest"],
                "payload": payload,
            }
            if row["event_digest"] != canonical_digest(event_body):
                raise CurrentReviewControlError(
                    "current_review_event_digest_invalid"
                )
            self._validate_replayed_payload(case_key, payload)
            event_body["event_digest"] = row["event_digest"]
            events.append(event_body)
            previous_digest = str(row["event_digest"])
        return events

    def _validate_replayed_payload(
        self, case_key: str, payload: Mapping[str, Any]
    ) -> None:
        surface = str(payload.get("target_surface") or "")
        target = self._surface(case_key, surface)
        case_view = self._surface(case_key, "case")
        valid = (
            payload.get("case_key") == case_key
            and payload.get("manifest_digest") == self._projection.manifest_digest
            and payload.get("case_projection_digest")
            == case_view["case_projection_digest"]
            and payload.get("target_view_digest") == target["view_digest"]
            and payload.get("target_ref") == f"surface:{surface}"
            and payload.get("qualified_human_review") is False
            and payload.get("automatic_repair_execution") is False
        )
        if not valid:
            raise CurrentReviewControlError(
                "current_review_event_current_binding_invalid"
            )
        reason = self._reason(str(payload.get("reason_code") or ""), surface)
        if (
            payload.get("repair_owner") != reason["repair_owner"]
            or payload.get("requested_resolution")
            != reason["requested_resolution"]
        ):
            raise CurrentReviewControlError(
                "current_review_event_disposition_invalid"
            )

    def _handoff(
        self,
        case_key: str,
        case_view: Mapping[str, Any],
        requests: list[dict[str, Any]],
        replay_digest: str,
    ) -> dict[str, Any]:
        open_requests = [row for row in requests if row["status"] == "repair_requested"]
        view_digests = {
            surface: self._surface(case_key, surface)["view_digest"]
            for surface in (
                "case",
                "run",
                "evidence",
                "numeric",
                "graph",
                "gaps",
                "workpaper",
                "report",
                "trace",
                "quality",
            )
        }
        status = (
            self._contract["T07_handoff_contract"]["blocked_status"]
            if open_requests
            else self._contract["T07_handoff_contract"]["ready_status"]
        )
        body = {
            "status": status,
            "case_key": case_key,
            "manifest_digest": self._projection.manifest_digest,
            "case_projection_digest": case_view["case_projection_digest"],
            "view_digests": view_digests,
            "review_control_replay_digest": replay_digest,
            "open_return_request_ids": [row["request_id"] for row in open_requests],
            "required_permission": self._contract["permissions"][
                "qualified_review_T07"
            ],
            "allowed_T07_actions": deepcopy(
                self._contract["T07_handoff_contract"]["allowed_T07_actions"]
            ),
            "qualified_review_executed": False,
            "NVDA_R3_executed": False,
        }
        return {**body, "handoff_digest": canonical_digest(body)}

    def _surface(self, case_key: str, surface: str) -> dict[str, Any]:
        try:
            return self._projection.get_surface(
                case_key,
                surface,
                CurrentProductPrincipal(
                    mode="current",
                    permissions=frozenset({CURRENT_PRODUCT_READ_PERMISSION}),
                ),
            )
        except CurrentProductProjectionError as exc:
            raise CurrentReviewControlError(
                "current_review_target_surface_invalid", 422, surface=surface
            ) from exc

    def _reason(self, reason_code: str, surface: str) -> Mapping[str, Any]:
        reason = self._contract["reason_contract"].get(reason_code)
        if not isinstance(reason, Mapping):
            raise CurrentReviewControlError(
                "current_review_reason_code_invalid", 422
            )
        if surface not in reason["allowed_surfaces"]:
            raise CurrentReviewControlError(
                "current_review_reason_surface_mismatch", 422
            )
        return reason

    def _require_exact_bindings(
        self,
        case_view: Mapping[str, Any],
        target_view: Mapping[str, Any],
        draft: CurrentReturnForRepairDraft,
    ) -> None:
        if draft.expected_manifest_digest != self._projection.manifest_digest:
            raise CurrentReviewControlError(
                "current_review_manifest_digest_stale", 409
            )
        if (
            draft.expected_case_projection_digest
            != case_view["case_projection_digest"]
        ):
            raise CurrentReviewControlError(
                "current_review_case_projection_digest_stale", 409
            )
        if draft.expected_target_view_digest != target_view["view_digest"]:
            raise CurrentReviewControlError(
                "current_review_target_view_digest_stale", 409
            )

    def _require_read(self, principal: CurrentReviewControlPrincipal) -> None:
        if principal.mode != "current":
            raise CurrentReviewControlError("current_product_mode_required", 403)
        required = self._contract["permissions"]["read"]
        if required not in principal.permissions:
            raise CurrentReviewControlError(
                "current_product_read_permission_required", 403
            )

    def _require_request(
        self,
        principal: CurrentReviewControlPrincipal,
        draft: CurrentReturnForRepairDraft,
    ) -> None:
        self._require_read(principal)
        required = self._contract["permissions"]["request_repair"]
        if required not in principal.permissions:
            raise CurrentReviewControlError(
                "current_product_request_repair_permission_required", 403
            )
        if not principal.actor_id or draft.actor_ref != principal.actor_id:
            raise CurrentReviewControlError(
                "current_review_actor_scope_mismatch", 403
            )
        if not draft.idempotency_key.strip():
            raise CurrentReviewControlError(
                "current_review_idempotency_key_required", 422
            )

    @staticmethod
    def _normalize_case(case_key: str) -> str:
        normalized = str(case_key).upper()
        if normalized not in CURRENT_PRODUCT_CASE_KEYS:
            raise CurrentReviewControlError(
                "current_product_case_not_found", 404, case_key=case_key
            )
        return normalized

    def _configure(self) -> None:
        if (
            self._contract.get("schema_version")
            != CURRENT_REVIEW_CONTROL_CONTRACT_SCHEMA
            or self._contract.get("action_type") != "return_for_repair"
        ):
            raise ValueError("current_review_control_contract_invalid")
        boundaries = self._contract.get("hard_boundaries") or {}
        required_false = (
            "accepted_R2_business_truth_mutation",
            "raw_capture_product_exposure",
            "fixture_fallback",
            "automatic_repair_execution",
            "authenticated_reviewer_identity",
            "qualified_human_review",
            "NVDA_R3",
        )
        if any(boundaries.get(key) is not False for key in required_false):
            raise ValueError("current_review_control_boundary_open")
        if boundaries.get("model_provider_network_source_calls") != 0:
            raise ValueError("current_review_control_external_calls_not_zero")

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS current_product_review_events (
                    case_key TEXT NOT NULL,
                    case_sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    previous_event_digest TEXT,
                    payload_digest TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    event_digest TEXT NOT NULL UNIQUE,
                    PRIMARY KEY (case_key, case_sequence)
                );
                CREATE TABLE IF NOT EXISTS current_product_review_idempotency (
                    scope_key TEXT PRIMARY KEY,
                    command_digest TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    event_digest TEXT NOT NULL UNIQUE
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
