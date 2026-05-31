from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


SCHEMA_VERSION = "sec_agent_tool_call_ledger_v0.1"

VOLATILE_ARGUMENT_KEYS = {
    "api_key",
    "api_key_env",
    "created_at",
    "elapsed_ms",
    "finished_at",
    "output_dir",
    "output_root",
    "request_id",
    "run_id",
    "started_at",
    "timestamp",
    "trace_path",
    "updated_at",
}

UNORDERED_LIST_KEYS = {
    "analysis_tools",
    "fields",
    "filing_types",
    "metric_families",
    "object_ids",
    "period_roles",
    "sections",
    "source_families",
    "source_tiers",
    "tickers",
    "years",
}

UPPERCASE_VALUE_KEYS = {
    "filing_types",
    "form_type",
    "period_roles",
    "ticker",
    "tickers",
}

LOOP_BREAK_DUPLICATE_TOOL_CALL = "duplicate_tool_call_blocked"
LOOP_BREAK_TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED = "agent_tool_budget_exhausted"
LOOP_BREAK_SECOND_PASS_BUDGET_EXHAUSTED = "second_pass_budget_exhausted"
LOOP_BREAK_NO_INCREMENTAL_EVIDENCE = "no_incremental_evidence"
LOOP_BREAK_REPAIR_BUDGET_EXHAUSTED = "repair_budget_exhausted"
LOOP_BREAK_REPAIR_NO_PROGRESS = "repair_no_progress"
LOOP_BREAK_GRAPH_STEP_BUDGET_EXHAUSTED = "graph_step_budget_exhausted"


@dataclass
class ToolCallRecord:
    turn_id: str
    agent_id: str
    tool_name: str
    arguments_digest: str
    input_artifact_digests: list[str] = field(default_factory=list)
    output_artifact_digest: str = ""
    row_count: int = 0
    source_gap_count: int = 0
    coverage_delta: dict[str, int] = field(default_factory=dict)
    elapsed_ms: int = 0
    status: str = "ok"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolCallRecord":
        return cls(
            turn_id=str(payload.get("turn_id") or ""),
            agent_id=str(payload.get("agent_id") or ""),
            tool_name=str(payload.get("tool_name") or ""),
            arguments_digest=str(payload.get("arguments_digest") or ""),
            input_artifact_digests=[str(item) for item in payload.get("input_artifact_digests") or []],
            output_artifact_digest=str(payload.get("output_artifact_digest") or ""),
            row_count=_int_value(payload.get("row_count")),
            source_gap_count=_int_value(payload.get("source_gap_count")),
            coverage_delta={str(key): _int_value(value) for key, value in dict(payload.get("coverage_delta") or {}).items()},
            elapsed_ms=_int_value(payload.get("elapsed_ms")),
            status=str(payload.get("status") or "ok"),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass
class LoopBudget:
    max_graph_steps: int = 24
    max_tool_calls_total: int = 12
    max_tool_calls_per_agent: int = 4
    max_second_pass_rounds: int = 2
    max_repair_rounds: int = 2
    max_same_tool_same_args: int = 1

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "LoopBudget":
        payload = payload or {}
        return cls(
            max_graph_steps=_positive_int(payload.get("max_graph_steps"), default=24),
            max_tool_calls_total=_positive_int(payload.get("max_tool_calls_total"), default=12),
            max_tool_calls_per_agent=_positive_int(payload.get("max_tool_calls_per_agent"), default=4),
            max_second_pass_rounds=_positive_int(payload.get("max_second_pass_rounds"), default=2),
            max_repair_rounds=_positive_int(payload.get("max_repair_rounds"), default=2),
            max_same_tool_same_args=_positive_int(payload.get("max_same_tool_same_args"), default=1),
        )


@dataclass
class ToolCallLedger:
    budget: LoopBudget = field(default_factory=LoopBudget)
    records: list[ToolCallRecord] = field(default_factory=list)
    graph_steps: int = 0
    second_pass_rounds: int = 0
    repair_rounds: int = 0
    loop_break_reason: str = ""
    bounded_answer_allowed: bool = False

    def can_call_tool(
        self,
        *,
        turn_id: str,
        agent_id: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        arguments_digest: str = "",
    ) -> dict[str, Any]:
        digest = arguments_digest or stable_tool_arguments_digest(tool_name, arguments or {})
        if self._executed_tool_call_count() >= self.budget.max_tool_calls_total:
            return self._blocked(LOOP_BREAK_TOOL_BUDGET_EXHAUSTED, arguments_digest=digest)
        if self._executed_tool_call_count(agent_id=agent_id) >= self.budget.max_tool_calls_per_agent:
            return self._blocked(LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED, arguments_digest=digest)
        duplicate_count = self._same_tool_same_args_count(
            turn_id=turn_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments_digest=digest,
        )
        if duplicate_count >= self.budget.max_same_tool_same_args:
            return self._blocked(LOOP_BREAK_DUPLICATE_TOOL_CALL, arguments_digest=digest)
        return {
            "allowed": True,
            "status": "allowed",
            "arguments_digest": digest,
            "reason": "",
            "tool_call_count_total": self._executed_tool_call_count(),
            "tool_call_count_for_agent": self._executed_tool_call_count(agent_id=agent_id),
        }

    def record_tool_call(
        self,
        *,
        turn_id: str,
        agent_id: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
        arguments_digest: str = "",
        input_artifact_digests: list[str] | None = None,
        output_artifact_digest: str = "",
        row_count: int = 0,
        source_gap_count: int = 0,
        coverage_delta: Mapping[str, Any] | None = None,
        elapsed_ms: int = 0,
        status: str = "ok",
        metadata: Mapping[str, Any] | None = None,
    ) -> ToolCallRecord:
        digest = arguments_digest or stable_tool_arguments_digest(tool_name, arguments or {})
        record = ToolCallRecord(
            turn_id=str(turn_id),
            agent_id=str(agent_id),
            tool_name=str(tool_name),
            arguments_digest=digest,
            input_artifact_digests=[str(item) for item in input_artifact_digests or []],
            output_artifact_digest=str(output_artifact_digest or ""),
            row_count=max(0, int(row_count or 0)),
            source_gap_count=max(0, int(source_gap_count or 0)),
            coverage_delta={str(key): _int_value(value) for key, value in dict(coverage_delta or {}).items()},
            elapsed_ms=max(0, int(elapsed_ms or 0)),
            status=str(status or "ok"),
            metadata=dict(metadata or {}),
        )
        self.records.append(record)
        return record

    def can_enter_graph_step(self) -> dict[str, Any]:
        if self.graph_steps >= self.budget.max_graph_steps:
            return self._blocked(LOOP_BREAK_GRAPH_STEP_BUDGET_EXHAUSTED)
        return {"allowed": True, "status": "allowed", "reason": "", "graph_steps": self.graph_steps}

    def record_graph_step(self) -> dict[str, Any]:
        decision = self.can_enter_graph_step()
        if not decision["allowed"]:
            self.loop_break_reason = str(decision["reason"])
            return decision
        self.graph_steps += 1
        return {"allowed": True, "status": "recorded", "graph_steps": self.graph_steps}

    def can_start_second_pass(self) -> dict[str, Any]:
        if self.second_pass_rounds >= self.budget.max_second_pass_rounds:
            return self._blocked(LOOP_BREAK_SECOND_PASS_BUDGET_EXHAUSTED)
        return {
            "allowed": True,
            "status": "allowed",
            "reason": "",
            "second_pass_rounds": self.second_pass_rounds,
        }

    def record_second_pass_result(
        self,
        *,
        added_row_count: int,
        coverage_delta: Mapping[str, Any] | None = None,
        source_gap_delta: int = 0,
    ) -> dict[str, Any]:
        decision = self.can_start_second_pass()
        if not decision["allowed"]:
            self.loop_break_reason = str(decision["reason"])
            self.bounded_answer_allowed = True
            return {**decision, "bounded_answer_allowed": self.bounded_answer_allowed}
        self.second_pass_rounds += 1
        delta = {str(key): _int_value(value) for key, value in dict(coverage_delta or {}).items()}
        added_rows = max(0, int(added_row_count or 0))
        closed_gaps = max(0, int(delta.get("closed_gaps") or 0))
        if added_rows == 0 and closed_gaps == 0:
            self.loop_break_reason = LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
            self.bounded_answer_allowed = True
        return {
            "allowed": True,
            "status": "recorded",
            "second_pass_rounds": self.second_pass_rounds,
            "added_row_count": added_rows,
            "source_gap_delta": int(source_gap_delta or 0),
            "coverage_delta": delta,
            "loop_break_reason": self.loop_break_reason,
            "bounded_answer_allowed": self.bounded_answer_allowed,
        }

    def can_run_repair(self) -> dict[str, Any]:
        if self.repair_rounds >= self.budget.max_repair_rounds:
            return self._blocked(LOOP_BREAK_REPAIR_BUDGET_EXHAUSTED)
        return {"allowed": True, "status": "allowed", "reason": "", "repair_rounds": self.repair_rounds}

    def record_repair_result(self, *, previous_failure_count: int, new_failure_count: int) -> dict[str, Any]:
        decision = self.can_run_repair()
        if not decision["allowed"]:
            self.loop_break_reason = str(decision["reason"])
            return decision
        self.repair_rounds += 1
        previous = max(0, int(previous_failure_count or 0))
        new = max(0, int(new_failure_count or 0))
        if new >= previous:
            self.loop_break_reason = LOOP_BREAK_REPAIR_NO_PROGRESS
        return {
            "allowed": True,
            "status": "recorded",
            "repair_rounds": self.repair_rounds,
            "previous_failure_count": previous,
            "new_failure_count": new,
            "loop_break_reason": self.loop_break_reason,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "budget": self.budget.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "graph_steps": self.graph_steps,
            "second_pass_rounds": self.second_pass_rounds,
            "repair_rounds": self.repair_rounds,
            "loop_break_reason": self.loop_break_reason,
            "bounded_answer_allowed": self.bounded_answer_allowed,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolCallLedger":
        return cls(
            budget=LoopBudget.from_dict(payload.get("budget") if isinstance(payload.get("budget"), Mapping) else {}),
            records=[ToolCallRecord.from_dict(item) for item in payload.get("records") or [] if isinstance(item, Mapping)],
            graph_steps=_int_value(payload.get("graph_steps")),
            second_pass_rounds=_int_value(payload.get("second_pass_rounds")),
            repair_rounds=_int_value(payload.get("repair_rounds")),
            loop_break_reason=str(payload.get("loop_break_reason") or ""),
            bounded_answer_allowed=bool(payload.get("bounded_answer_allowed")),
        )

    def _blocked(self, reason: str, *, arguments_digest: str = "") -> dict[str, Any]:
        self.loop_break_reason = reason
        return {
            "allowed": False,
            "status": "blocked",
            "reason": reason,
            "arguments_digest": arguments_digest,
            "tool_call_count_total": self._executed_tool_call_count(),
        }

    def _executed_tool_call_count(self, *, agent_id: str | None = None) -> int:
        records = [record for record in self.records if record.status != "blocked"]
        if agent_id is None:
            return len(records)
        return sum(1 for record in records if record.agent_id == agent_id)

    def _same_tool_same_args_count(
        self,
        *,
        turn_id: str,
        agent_id: str,
        tool_name: str,
        arguments_digest: str,
    ) -> int:
        return sum(
            1
            for record in self.records
            if record.status != "blocked"
            and record.turn_id == turn_id
            and record.agent_id == agent_id
            and record.tool_name == tool_name
            and record.arguments_digest == arguments_digest
        )


def stable_tool_arguments_digest(tool_name: str, arguments: Mapping[str, Any] | None = None) -> str:
    payload = {
        "tool_name": str(tool_name or ""),
        "arguments": normalize_tool_arguments(arguments or {}),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def normalize_tool_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _normalize_value(arguments, key_context="")


def _normalize_value(value: Any, *, key_context: str) -> Any:
    key_lower = key_context.lower()
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in VOLATILE_ARGUMENT_KEYS:
                continue
            normalized = _normalize_value(item, key_context=key_text)
            if normalized in (None, "", [], {}):
                continue
            clean[key_text] = normalized
        return {key: clean[key] for key in sorted(clean)}
    if isinstance(value, (list, tuple, set)):
        items = [_normalize_value(item, key_context=key_context) for item in value]
        items = [item for item in items if item not in (None, "", [], {})]
        if key_lower in UNORDERED_LIST_KEYS:
            deduped = []
            seen: set[str] = set()
            for item in items:
                marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if marker in seen:
                    continue
                seen.add(marker)
                deduped.append(item)
            return sorted(deduped, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
        return items
    if isinstance(value, str):
        text = value.strip()
        if key_lower in UPPERCASE_VALUE_KEYS or "ticker" in key_lower:
            return text.upper()
        if key_lower in {"years", "year"} and text.isdigit():
            return int(text)
        return text
    if key_lower in {"years", "year"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)
