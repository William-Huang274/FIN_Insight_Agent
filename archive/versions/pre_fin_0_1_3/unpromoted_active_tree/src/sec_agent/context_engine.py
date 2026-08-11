from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


CONTEXT_ENGINE_SCHEMA_VERSION = "finsight_context_engine_v0_1"
MEMORY_STATES = {"candidate", "reviewed", "active", "stale", "superseded", "revoked"}


@dataclass(frozen=True)
class ContextEngineConfig:
    max_prompt_context_items: int = 12
    max_prompt_chars: int = 12000
    default_token_budget: int = 6000


class ContextEngine:
    def __init__(self, *, config: ContextEngineConfig | None = None) -> None:
        self.config = config or ContextEngineConfig()

    def resolve(self, state: Mapping[str, Any]) -> dict[str, Any]:
        snapshots = []
        for context_type, value in _context_candidates(state):
            if isinstance(value, Mapping) and value:
                snapshots.append(_snapshot(context_type, dict(value)))
            elif isinstance(value, list) and value:
                items = [item for item in value if isinstance(item, Mapping)]
                if context_type == "role_context":
                    snapshots.extend(_snapshot(context_type, dict(item)) for item in items)
                else:
                    snapshots.append(_snapshot(context_type, {"items": items}))
        return {
            "schema_version": CONTEXT_ENGINE_SCHEMA_VERSION,
            "operation": "resolve",
            "snapshot_count": len(snapshots),
            "snapshots": snapshots,
        }

    def select(
        self,
        snapshots: Iterable[Mapping[str, Any]],
        *,
        target_node: str,
        role: str = "",
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        budget = int(token_budget or self.config.default_token_budget)
        selected = []
        used_chars = 0
        for snapshot in snapshots:
            if not _visible_to_node(snapshot, target_node=target_node, role=role):
                continue
            payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), Mapping) else {}
            serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
            next_chars = len(serialized)
            if len(selected) >= self.config.max_prompt_context_items:
                break
            if used_chars + next_chars > self.config.max_prompt_chars:
                selected.append(_compressed_snapshot(snapshot, reason="char_budget"))
                used_chars += len(json.dumps(selected[-1], ensure_ascii=False, default=str))
                break
            selected.append(dict(snapshot))
            used_chars += next_chars
        return {
            "schema_version": "finsight_context_selection_v0_1",
            "target_node": target_node,
            "role": role,
            "token_budget": budget,
            "selected_count": len(selected),
            "selected_snapshots": selected,
            "selection_policy": "visibility_then_budget_no_source_boundary_loss_v0_1",
        }

    def compress(self, selection: Mapping[str, Any]) -> dict[str, Any]:
        snapshots = [dict(item) for item in selection.get("selected_snapshots") or [] if isinstance(item, Mapping)]
        compressed = [_compressed_snapshot(item, reason="prompt_pack") for item in snapshots]
        return {
            "schema_version": "finsight_context_compression_v0_1",
            "source_selection_digest": _digest(selection),
            "compressed_count": len(compressed),
            "snapshots": compressed,
            "must_preserve_fields": ["source_boundary", "period", "unit", "citation", "gap_type", "evidence_refs"],
        }

    def inject(self, selection: Mapping[str, Any], *, target_node: str) -> dict[str, Any]:
        compressed = self.compress(selection)
        prompt_pack = {
            "schema_version": "finsight_context_injection_plan_v0_1",
            "plan_id": f"context_injection:{target_node}:{_digest(compressed)[:16]}",
            "target_node": target_node,
            "token_budget": int(selection.get("token_budget") or self.config.default_token_budget),
            "context_snapshot_ids": [str(item.get("snapshot_id") or "") for item in compressed["snapshots"]],
            "prompt_context": compressed["snapshots"],
            "input_digest": _digest(selection),
            "output_digest": _digest(compressed),
            "policy": "replayable_context_injection_no_private_chain_leak_v0_1",
        }
        return prompt_pack

    def write_memory(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        state = str(entry.get("state") or "candidate")
        if state not in MEMORY_STATES:
            state = "candidate"
        payload = dict(entry)
        payload["state"] = state
        return {
            "schema_version": "finsight_research_memory_entry_v0_1",
            "memory_id": str(entry.get("memory_id") or f"memory:{_digest(payload)[:20]}"),
            "state": state,
            "claim_refs": _list(entry.get("claim_refs")),
            "gap_refs": _list(entry.get("gap_refs")),
            "derived_metric_refs": _list(entry.get("derived_metric_refs")),
            "evidence_refs": _list(entry.get("evidence_refs")),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "governance": validate_memory_entry(payload),
        }


def validate_memory_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    state = str(entry.get("state") or "candidate")
    if state not in MEMORY_STATES:
        errors.append({"type": "invalid_memory_state", "state": state})
    if not any(_list(entry.get(key)) for key in ("claim_refs", "gap_refs", "derived_metric_refs", "evidence_refs")):
        errors.append({"type": "memory_without_drilldown_refs"})
    if entry.get("supports_financial_claim") is True and not _list(entry.get("claim_refs")):
        errors.append({"type": "memory_cannot_directly_support_financial_claim_without_claim_ref"})
    return {
        "schema_version": "finsight_memory_governance_gate_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "policy": "memory_is_planning_context_not_direct_fact_authority_v0_1",
    }


def _context_candidates(state: Mapping[str, Any]) -> list[tuple[str, Any]]:
    return [
        ("run_objective", state.get("research_objective_contract") or state.get("query_contract")),
        ("source_inventory", state.get("project_inventory")),
        ("source_capability", state.get("source_capability_router")),
        ("retrieval_audit", state.get("retrieval_budget_audit")),
        ("claim_gap_gate", {"claims": state.get("verified_judgment_plan"), "gaps": state.get("source_gaps"), "gates": state.get("claim_verification")}),
        ("research_memory", state.get("analyst_view_research_memory") or state.get("research_memory_entries")),
        ("role_context", state.get("agent_data_views")),
        ("artifact_refs", state.get("artifact_refs")),
    ]


def _snapshot(context_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    visibility = _visibility(context_type, payload)
    snapshot = {
        "schema_version": "finsight_context_snapshot_v0_1",
        "snapshot_id": f"{context_type}:{_digest(payload)[:20]}",
        "context_type": context_type,
        "visibility_scope": visibility,
        "payload": dict(payload),
        "source_boundary": _source_boundary(payload),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return snapshot


def _visibility(context_type: str, payload: Mapping[str, Any]) -> str:
    if context_type == "role_context":
        return "specialist_role_private"
    if context_type == "artifact_refs":
        return "lead_and_verifier"
    if context_type == "claim_gap_gate":
        return "memo_writer_verified_only"
    return str(payload.get("visibility_scope") or "global")


def _visible_to_node(snapshot: Mapping[str, Any], *, target_node: str, role: str) -> bool:
    scope = str(snapshot.get("visibility_scope") or "")
    if target_node == "memo_writer":
        return scope in {"memo_writer_verified_only", "global", "lead_and_verifier"}
    if target_node == "specialist":
        return scope in {"global", "specialist_role_private"} and (not role or role in json.dumps(snapshot.get("payload") or {}, ensure_ascii=False))
    if target_node in {"research_lead", "lead_review_checkpoint"}:
        return scope != "specialist_private_chain"
    return True


def _compressed_snapshot(snapshot: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), Mapping) else {}
    keep = {
        key: payload.get(key)
        for key in ("source_boundary", "period", "unit", "citation", "gap_type", "evidence_refs", "claim_refs", "summary", "status")
        if key in payload
    }
    if not keep:
        keep = {"summary": str(payload)[:1200]}
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "context_type": snapshot.get("context_type"),
        "visibility_scope": snapshot.get("visibility_scope"),
        "source_boundary": snapshot.get("source_boundary"),
        "payload": keep,
        "compression_reason": reason,
    }


def _source_boundary(payload: Mapping[str, Any]) -> str:
    return str(payload.get("source_boundary") or payload.get("claim_boundary") or payload.get("authority") or "")


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
