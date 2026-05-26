from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sec_agent.context_store import JsonContextStore
from sec_agent.graph_nodes import state_resume_report
from sec_agent.graph_state import ARTIFACT_KEYS, OPTIONAL_ARTIFACT_KEYS, SecAgentState
from sec_agent.tool_harness import DEFAULT_SESSION_ROOT


CONTEXT_SNAPSHOT_SCHEMA_VERSION = "sec_agent_context_snapshot_v0.1"
RECENT_TURN_LIMIT_DEFAULT = 5
CANDIDATE_SESSION_LIMIT_DEFAULT = 3


@dataclass(frozen=True)
class ContextBudget:
    """Controller-context budget guard.

    Token estimates are intentionally approximate. The manager uses them to
    keep the routing prompt small and deterministic before any LLM sees it.
    """

    target_controller_tokens: int = 3000
    caution_controller_tokens: int = 6000
    max_recent_turns: int = RECENT_TURN_LIMIT_DEFAULT
    max_candidate_sessions: int = CANDIDATE_SESSION_LIMIT_DEFAULT
    max_summary_chars: int = 1200


class SecAgentContextManager:
    """Build compact, permission-scoped controller context from JSON state.

    The manager treats identity, active answer, scope, artifact refs, resume
    cursor, and source policy as lossless fields. Conversation summary and
    recent turns are bounded hints only and must not override those fields.
    """

    def __init__(
        self,
        *,
        session_root: str | Path = DEFAULT_SESSION_ROOT,
        context_root: str | Path | None = None,
        budget: ContextBudget | None = None,
    ) -> None:
        self.session_root = Path(session_root)
        self.context_root = Path(context_root) if context_root else self.session_root.parent / "context_store"
        self.store = JsonContextStore(self.context_root)
        self.budget = budget or ContextBudget()

    def ingest_sessions(self) -> dict[str, Any]:
        """Index currently available session files into user profiles."""

        count = 0
        for session in self._iter_sessions():
            self._touch_profile_from_session(session)
            count += 1
        return {
            "schema_version": "sec_agent_context_ingest_result_v0.1",
            "session_root": str(self.session_root),
            "context_root": str(self.context_root),
            "indexed_session_count": count,
        }

    def set_active_session(self, *, tenant_id: str, user_id: str, session_id: str) -> dict[str, Any]:
        session = self._load_session_required(session_id)
        self._enforce_owner(session, tenant_id=tenant_id, user_id=user_id)
        profile = self.store.load_user_profile(tenant_id=tenant_id, user_id=user_id)
        profile["active_session_id"] = str(session_id)
        profile["recent_session_ids"] = _dedupe([str(session_id), *(profile.get("recent_session_ids") or [])])[
            : self.budget.max_candidate_sessions
        ]
        self.store.save_user_profile(profile)
        return self.build_controller_context(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            user_message="",
        )

    def clear_active_session(self, *, tenant_id: str, user_id: str) -> dict[str, Any]:
        profile = self.store.load_user_profile(tenant_id=tenant_id, user_id=user_id)
        profile["active_session_id"] = ""
        self.store.save_user_profile(profile)
        return profile

    def list_user_sessions(self, *, tenant_id: str, user_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        sessions = []
        for session in self._iter_sessions():
            if str(session.get("tenant_id") or "") != str(tenant_id or ""):
                continue
            if str(session.get("user_id") or "") != str(user_id or ""):
                continue
            sessions.append(_compact_session_candidate(session))
        sessions.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return sessions[: int(limit or self.budget.max_candidate_sessions)]

    def build_controller_context(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str = "",
        user_message: str = "",
        include_session_candidates: bool | None = None,
    ) -> dict[str, Any]:
        profile = self.store.load_user_profile(tenant_id=tenant_id, user_id=user_id)
        session_candidates = self.list_user_sessions(
            tenant_id=tenant_id,
            user_id=user_id,
            limit=self.budget.max_candidate_sessions,
        )
        requested_session_id = str(session_id or "").strip()
        resolved_session_id = requested_session_id or str(profile.get("active_session_id") or "").strip()
        status = "ready"
        reason = ""

        if not resolved_session_id:
            if _looks_ambiguous_reference(user_message) and len(session_candidates) != 1:
                return self._snapshot(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    status="clarification_required",
                    reason="ambiguous_session_reference",
                    user_message=user_message,
                    profile=profile,
                    active_session={},
                    session_candidates=session_candidates,
                )
            if len(session_candidates) == 1:
                resolved_session_id = str(session_candidates[0].get("session_id") or "")
            elif session_candidates:
                return self._snapshot(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    status="clarification_required",
                    reason="multiple_candidate_sessions_without_active_session",
                    user_message=user_message,
                    profile=profile,
                    active_session={},
                    session_candidates=session_candidates,
                )
            else:
                return self._snapshot(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    status="error",
                    reason="no_sessions_for_user",
                    user_message=user_message,
                    profile=profile,
                    active_session={},
                    session_candidates=[],
                )

        try:
            session = self._load_session_required(resolved_session_id)
            self._enforce_owner(session, tenant_id=tenant_id, user_id=user_id)
        except PermissionError as exc:
            return self._snapshot(
                tenant_id=tenant_id,
                user_id=user_id,
                status="access_denied",
                reason=str(exc),
                user_message=user_message,
                profile=profile,
                active_session={},
                session_candidates=[],
            )
        except FileNotFoundError as exc:
            return self._snapshot(
                tenant_id=tenant_id,
                user_id=user_id,
                status="error",
                reason=str(exc),
                user_message=user_message,
                profile=profile,
                active_session={},
                session_candidates=session_candidates,
            )

        self._touch_profile_from_session(session)
        profile = self.store.load_user_profile(tenant_id=tenant_id, user_id=user_id)
        active_session = self._compact_active_session(session)
        expose_candidates = bool(include_session_candidates)
        if include_session_candidates is None:
            expose_candidates = not requested_session_id and _looks_ambiguous_reference(user_message)
        return self._snapshot(
            tenant_id=tenant_id,
            user_id=user_id,
            status=status,
            reason=reason,
            user_message=user_message,
            profile=profile,
            active_session=active_session,
            session_candidates=session_candidates if expose_candidates else [],
        )

    def apply_tool_result(self, *, tool_call: dict[str, Any] | None = None, tool_result: dict[str, Any]) -> dict[str, Any]:
        payload = tool_result.get("payload") if isinstance(tool_result.get("payload"), dict) else {}
        session_id = str(payload.get("session_id") or (tool_call or {}).get("session_id") or "")
        if not session_id and isinstance(tool_call, dict):
            arguments = tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {}
            session_id = str(arguments.get("session_id") or "")
        if not session_id:
            return {"status": "ignored", "reason": "tool_result_has_no_session_id"}
        session = self._load_session_required(session_id)
        profile = self._touch_profile_from_session(session)

        tool_name = str(tool_result.get("tool_name") or (tool_call or {}).get("name") or "")
        references = dict(profile.get("last_references") or {})
        if tool_name == "explain_evidence":
            references.update(_last_reference_from_explain_payload(payload))
        if tool_name == "reformat_answer":
            references["last_invalidated_artifacts"] = payload.get("invalidated_artifacts") or []
            references["last_reformat_answer_id"] = payload.get("answer_id") or ""
        if tool_name == "resume_analysis":
            report = payload.get("resume_report") if isinstance(payload.get("resume_report"), dict) else {}
            references["last_resume_next_ready_node"] = report.get("next_ready_node")
        profile["last_references"] = references
        self.store.save_user_profile(profile)
        return {"status": "updated", "session_id": session_id, "tool_name": tool_name}

    def validate_snapshot(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        errors = []
        lossless = snapshot.get("lossless_fields") if isinstance(snapshot.get("lossless_fields"), dict) else {}
        required = [
            "tenant_id",
            "user_id",
            "session_id",
            "active_answer_id",
            "active_scope",
            "artifact_state",
            "resume",
            "source_policy",
        ]
        for key in required:
            if key not in lossless:
                errors.append({"field": key, "message": "missing lossless field"})
        compression = snapshot.get("compression") if isinstance(snapshot.get("compression"), dict) else {}
        if int(compression.get("recent_turn_count") or 0) > self.budget.max_recent_turns:
            errors.append({"field": "recent_turns", "message": "recent turn budget exceeded"})
        if int(compression.get("candidate_session_count") or 0) > self.budget.max_candidate_sessions:
            errors.append({"field": "session_candidates", "message": "candidate session budget exceeded"})
        return errors

    def _snapshot(
        self,
        *,
        tenant_id: str,
        user_id: str,
        status: str,
        reason: str,
        user_message: str,
        profile: dict[str, Any],
        active_session: dict[str, Any],
        session_candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        identity = {"tenant_id": str(tenant_id or ""), "user_id": str(user_id or "")}
        active_answer = active_session.get("active_answer") if isinstance(active_session.get("active_answer"), dict) else {}
        artifact_state = active_answer.get("artifact_state") if isinstance(active_answer.get("artifact_state"), dict) else {}
        resume = active_answer.get("resume") if isinstance(active_answer.get("resume"), dict) else {}
        source_policy = str((active_session.get("active_scope") or {}).get("source_policy") or "")
        lossless_fields = {
            "tenant_id": identity["tenant_id"],
            "user_id": identity["user_id"],
            "session_id": active_session.get("session_id") or "",
            "active_answer_id": active_session.get("active_answer_id") or "",
            "active_scope": active_session.get("active_scope") or {},
            "artifact_state": artifact_state,
            "resume": resume,
            "source_policy": source_policy,
        }
        summary = _bounded_summary(
            active_session=active_session,
            user_message=user_message,
            max_chars=self.budget.max_summary_chars,
        )
        snapshot: dict[str, Any] = {
            "schema_version": CONTEXT_SNAPSHOT_SCHEMA_VERSION,
            "status": status,
            "reason": reason,
            "created_at": _utc_now(),
            "identity": identity,
            "user_profile": {
                "preferences": profile.get("preferences") or {},
                "active_session_id": profile.get("active_session_id") or "",
                "recent_session_ids": (profile.get("recent_session_ids") or [])[: self.budget.max_candidate_sessions],
                "last_references": profile.get("last_references") or {},
            },
            "active_session": active_session,
            "session_candidates": session_candidates[: self.budget.max_candidate_sessions],
            "lossless_fields": lossless_fields,
            "summary": summary,
        }
        snapshot["compression"] = self._compression_report(snapshot)
        snapshot["validation_errors"] = self.validate_snapshot(snapshot) if status == "ready" else []
        return snapshot

    def _compact_active_session(self, session: dict[str, Any]) -> dict[str, Any]:
        analyses = session.get("analyses") if isinstance(session.get("analyses"), dict) else {}
        active_answer_id = str(session.get("active_answer_id") or "")
        active_analysis = analyses.get(active_answer_id) if isinstance(analyses.get(active_answer_id), dict) else {}
        turns = [turn for turn in (session.get("turns") or []) if isinstance(turn, dict)]
        active_answer = self._compact_analysis(active_analysis)
        _merge_turn_invalidations(active_answer, turns=turns, active_answer_id=active_answer_id)
        return {
            "session_id": session.get("session_id") or "",
            "tenant_id": session.get("tenant_id") or "",
            "user_id": session.get("user_id") or "",
            "updated_at": session.get("updated_at") or "",
            "active_query": session.get("active_query") or "",
            "active_scope": session.get("active_scope") or {},
            "active_answer_id": active_answer_id,
            "conversation_summary": str(session.get("conversation_summary") or "")[: self.budget.max_summary_chars],
            "recent_turns": _compact_recent_turns(turns, limit=self.budget.max_recent_turns),
            "active_answer": active_answer,
            "analysis_count": len(analyses),
        }

    def _compact_analysis(self, analysis: dict[str, Any]) -> dict[str, Any]:
        if not analysis:
            return {}
        state_path_text = str(analysis.get("state_path") or "").strip()
        state_path = Path(state_path_text) if state_path_text else None
        resume_report = {}
        if state_path and state_path.is_file():
            resume_report = state_resume_report(SecAgentState.read_json(state_path))
        artifact_state = _artifact_state_from_analysis(analysis, resume_report)
        return {
            "answer_id": analysis.get("answer_id") or "",
            "query": analysis.get("query") or "",
            "status": analysis.get("status") or "",
            "run_root": analysis.get("run_root") or "",
            "state_path": str(state_path) if state_path else "",
            "artifact_state": artifact_state,
            "resume": {
                "next_ready_node": resume_report.get("next_ready_node"),
                "ready_nodes": resume_report.get("ready_nodes") or [],
                "missing_artifacts": resume_report.get("missing_artifacts") or [],
                "digest_mismatch_artifacts": resume_report.get("digest_mismatch_artifacts") or [],
            },
            "execution": {
                "execute": (analysis.get("execution") or {}).get("execute"),
                "returncode": (analysis.get("execution") or {}).get("returncode"),
                "elapsed_sec": (analysis.get("execution") or {}).get("elapsed_sec"),
            },
        }

    def _compression_report(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        estimated_tokens = max(1, len(text) // 4)
        if estimated_tokens > self.budget.caution_controller_tokens:
            risk = "high"
        elif estimated_tokens > self.budget.target_controller_tokens:
            risk = "moderate"
        else:
            risk = "low"
        active_session = snapshot.get("active_session") if isinstance(snapshot.get("active_session"), dict) else {}
        return {
            "strategy": "structured_lossless_fields_with_bounded_summary",
            "estimated_tokens": estimated_tokens,
            "target_controller_tokens": self.budget.target_controller_tokens,
            "caution_controller_tokens": self.budget.caution_controller_tokens,
            "attention_risk": risk,
            "recent_turn_limit": self.budget.max_recent_turns,
            "recent_turn_count": len(active_session.get("recent_turns") or []),
            "candidate_session_limit": self.budget.max_candidate_sessions,
            "candidate_session_count": len(snapshot.get("session_candidates") or []),
            "summary_chars": len(str(snapshot.get("summary") or "")),
        }

    def _touch_profile_from_session(self, session: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str(session.get("tenant_id") or "")
        user_id = str(session.get("user_id") or "")
        session_id = str(session.get("session_id") or "")
        profile = self.store.load_user_profile(tenant_id=tenant_id, user_id=user_id)
        recent = _dedupe([session_id, *(profile.get("recent_session_ids") or [])])
        profile["recent_session_ids"] = recent[: self.budget.max_candidate_sessions]
        if not profile.get("active_session_id"):
            profile["active_session_id"] = session_id
        self.store.save_user_profile(profile)
        return profile

    def _iter_sessions(self) -> list[dict[str, Any]]:
        sessions = []
        if not self.session_root.exists():
            return sessions
        for path in self.session_root.glob("*/session_state.json"):
            try:
                payload = _read_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if payload:
                sessions.append(payload)
        return sessions

    def _load_session_required(self, session_id: str) -> dict[str, Any]:
        path = self.session_root / _safe_id(session_id) / "session_state.json"
        if not path.exists():
            raise FileNotFoundError(f"session not found: {session_id}")
        return _read_json(path)

    @staticmethod
    def _enforce_owner(session: dict[str, Any], *, tenant_id: str, user_id: str) -> None:
        if str(session.get("tenant_id") or "") != str(tenant_id or ""):
            raise PermissionError("tenant_id does not match session owner")
        if str(session.get("user_id") or "") != str(user_id or ""):
            raise PermissionError("user_id does not match session owner")


def _artifact_state_from_analysis(analysis: dict[str, Any], resume_report: dict[str, Any]) -> dict[str, Any]:
    refs = analysis.get("artifact_refs") if isinstance(analysis.get("artifact_refs"), dict) else {}
    complete = set(resume_report.get("complete_artifacts") or [])
    missing = set(resume_report.get("missing_artifacts") or [])
    digest_mismatch = set(resume_report.get("digest_mismatch_artifacts") or [])
    invalidated = set(analysis.get("invalidated_artifacts") or [])
    for turn in reversed(analysis.get("turns") or []):
        if isinstance(turn, dict):
            invalidated.update(turn.get("invalidated_artifacts") or [])
    by_key = {}
    for key in ARTIFACT_KEYS:
        if key in invalidated:
            status = "invalidated"
        elif key in complete:
            status = "complete"
        elif key in digest_mismatch:
            status = "digest_mismatch"
        elif key in missing:
            status = "missing"
        elif key in refs:
            status = "complete"
        elif key in OPTIONAL_ARTIFACT_KEYS:
            status = "not_required"
        else:
            status = "missing"
        ref = refs.get(key) if isinstance(refs.get(key), dict) else {}
        by_key[key] = {
            "status": status,
            "path": ref.get("path", ""),
            "digest": ref.get("digest", ""),
        }
    return {
        "complete_artifacts": [key for key, value in by_key.items() if value["status"] == "complete"],
        "missing_artifacts": [key for key, value in by_key.items() if value["status"] == "missing"],
        "optional_artifacts": [key for key, value in by_key.items() if value["status"] == "not_required"],
        "invalidated_artifacts": sorted(invalidated),
        "digest_mismatch_artifacts": sorted(digest_mismatch),
        "by_key": by_key,
    }


def _merge_turn_invalidations(active_answer: dict[str, Any], *, turns: list[dict[str, Any]], active_answer_id: str) -> None:
    artifact_state = active_answer.get("artifact_state") if isinstance(active_answer.get("artifact_state"), dict) else {}
    if not artifact_state:
        return
    invalidated = set(artifact_state.get("invalidated_artifacts") or [])
    for turn in turns:
        if str(turn.get("tool_name") or "") != "reformat_answer":
            continue
        args = turn.get("arguments") if isinstance(turn.get("arguments"), dict) else {}
        answer_id = str(args.get("answer_id") or "")
        if answer_id and active_answer_id and answer_id != active_answer_id:
            continue
        invalidated.update(str(item) for item in (args.get("invalidated_artifacts") or []) if str(item or "").strip())
    if not invalidated:
        return
    by_key = artifact_state.get("by_key") if isinstance(artifact_state.get("by_key"), dict) else {}
    for key in invalidated:
        if key in by_key:
            by_key[key]["status"] = "invalidated"
    artifact_state["invalidated_artifacts"] = sorted(invalidated)
    artifact_state["complete_artifacts"] = [key for key, value in by_key.items() if value.get("status") == "complete"]
    artifact_state["missing_artifacts"] = [key for key, value in by_key.items() if value.get("status") == "missing"]


def _compact_session_candidate(session: dict[str, Any]) -> dict[str, Any]:
    scope = session.get("active_scope") if isinstance(session.get("active_scope"), dict) else {}
    return {
        "session_id": session.get("session_id") or "",
        "tenant_id": session.get("tenant_id") or "",
        "user_id": session.get("user_id") or "",
        "updated_at": session.get("updated_at") or "",
        "active_answer_id": session.get("active_answer_id") or "",
        "active_query_preview": str(session.get("active_query") or "")[:220],
        "tickers": scope.get("selected_tickers") or [],
        "years": scope.get("selected_years") or [],
        "source_policy": scope.get("source_policy") or "",
    }


def _compact_recent_turns(turns: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    compact = []
    for turn in turns[-max(int(limit), 0) :]:
        arguments = turn.get("arguments") if isinstance(turn.get("arguments"), dict) else {}
        compact.append(
            {
                "turn_id": turn.get("turn_id") or "",
                "tool_name": turn.get("tool_name") or "",
                "status": turn.get("status") or "",
                "created_at": turn.get("created_at") or "",
                "argument_keys": sorted(str(key) for key in arguments.keys()),
                "answer_id": arguments.get("answer_id") or arguments.get("active_answer_id") or "",
                "claim_reference": str(arguments.get("claim_reference") or "")[:240],
                "invalidated_artifacts": arguments.get("invalidated_artifacts") or [],
            }
        )
    return compact


def _bounded_summary(*, active_session: dict[str, Any], user_message: str, max_chars: int) -> str:
    if not active_session:
        text = f"No active session resolved. User message: {user_message}"
    else:
        scope = active_session.get("active_scope") if isinstance(active_session.get("active_scope"), dict) else {}
        text = (
            f"Active SEC-only session {active_session.get('session_id')} / answer "
            f"{active_session.get('active_answer_id')} covers tickers={scope.get('selected_tickers') or []}, "
            f"years={scope.get('selected_years') or []}. User message: {user_message}"
        )
    return text[: max(int(max_chars), 0)]


def _last_reference_from_explain_payload(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    return {
        "last_answer_id": payload.get("answer_id") or "",
        "last_section": target.get("section") or "",
        "last_item_index": target.get("index"),
        "last_metric_ids": payload.get("metric_ids") or [],
        "last_evidence_ids": payload.get("evidence_ids") or [],
    }


def _looks_ambiguous_reference(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(
        marker in normalized
        for marker in (
            "刚才",
            "上次",
            "这个",
            "那个",
            "继续",
            "previous",
            "last",
            "that session",
            "active memo",
        )
    )


def _dedupe(values: list[Any]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text[:120] or "default"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
