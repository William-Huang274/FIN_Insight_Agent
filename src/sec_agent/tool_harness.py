from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sec_agent.graph_nodes import state_resume_report
from sec_agent.graph_state import SecAgentState


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SESSION_ROOT = REPO_ROOT / "eval" / "sec_cases" / "session_harness"
SESSION_SCHEMA_VERSION = "sec_agent_session_state_v0.1"
TOOL_RESULT_SCHEMA_VERSION = "sec_agent_tool_result_v0.1"

ANALYSIS_ARTIFACT_KEYS = (
    "query_contract",
    "retrieved_context",
    "runtime_exact_value_ledger",
    "evidence_coverage_matrix",
    "judgment_plan",
    "evidence_pack",
    "memo_answer",
    "claim_verification",
    "deterministic_gates",
    "rendered_answer",
)

SCOPE_INVALIDATES = list(ANALYSIS_ARTIFACT_KEYS)
SYNTHESIS_INVALIDATES = [
    "evidence_pack",
    "memo_answer",
    "claim_verification",
    "deterministic_gates",
    "rendered_answer",
]
FORMAT_INVALIDATES = ["rendered_answer"]
KNOWN_TICKERS = (
    "MSFT",
    "AAPL",
    "NVDA",
    "GOOGL",
    "META",
    "AMZN",
    "AVGO",
    "CSCO",
    "INTC",
    "AMD",
    "QCOM",
    "TXN",
    "AMAT",
    "MU",
    "INTU",
    "ADP",
    "ADBE",
    "PANW",
    "CRWD",
    "SNOW",
    "JPM",
    "V",
    "JNJ",
    "LLY",
    "CAT",
    "GE",
    "WMT",
    "PG",
    "XOM",
    "CVX",
)


@dataclass
class ToolResult:
    tool_name: str
    status: str
    payload: dict[str, Any]
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TOOL_RESULT_SCHEMA_VERSION,
            "tool_name": self.tool_name,
            "status": self.status,
            "message": self.message,
            "payload": self.payload,
        }


class SecAgentToolHarness:
    """Session-aware tool harness for the SEC memo agent.

    This class exposes high-level tools for a model controller while preserving
    the current deterministic SEC memo DAG behind the harness boundary.
    """

    def __init__(
        self,
        *,
        session_root: str | Path = DEFAULT_SESSION_ROOT,
        python: str = sys.executable,
        repo_root: str | Path = REPO_ROOT,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.session_root = Path(session_root)
        self.python = str(python)
        self.session_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def tool_specs() -> list[dict[str, Any]]:
        return [
            _tool_spec(
                "start_memo_analysis",
                "Start a new SEC-only investment memo analysis using the existing graph/DAG.",
                {
                    "query": {"type": "string", "description": "User memo question."},
                    "user_id": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "session_id": {"type": "string"},
                    "years": {"type": "array", "items": {"type": "integer"}},
                    "source_policy": {"type": "string", "enum": ["SEC_ONLY_10K"]},
                    "preferred_output": {"type": "string"},
                    "execute": {"type": "boolean", "description": "Run the graph now instead of recording a plan only."},
                },
                required=["query"],
            ),
            _tool_spec(
                "revise_memo_scope",
                (
                    "Revise the active memo scope for a follow-up turn and rerun the graph when execute=true. "
                    "Use set_tickers when the user asks to focus, narrow, drill down, or compare only specific companies."
                ),
                {
                    "session_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "set_tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Replace the current ticker scope exactly. Use for 'focus on NVDA and AMD' or 'compare NVDA vs AMD'.",
                    },
                    "add_tickers": {"type": "array", "items": {"type": "string"}},
                    "remove_tickers": {"type": "array", "items": {"type": "string"}},
                    "years": {"type": "array", "items": {"type": "integer"}},
                    "preserve_output_style": {"type": "boolean"},
                    "execute": {"type": "boolean"},
                },
                required=["session_id"],
            ),
            _tool_spec(
                "explain_evidence",
                "Explain evidence for a prior memo driver or metric without rerunning retrieval/synthesis.",
                {
                    "session_id": {"type": "string"},
                    "answer_id": {"type": "string"},
                    "driver_index": {"type": "integer", "minimum": 1},
                    "section": {"type": "string", "description": "Optional memo section such as decision_drivers or why_it_matters."},
                    "item_index": {"type": "integer", "minimum": 1},
                    "claim_reference": {"type": "string", "description": "Natural-language reference to a claim, metric, or memo item."},
                    "metric_id": {"type": "string"},
                    "evidence_id": {"type": "string"},
                },
                required=["session_id"],
            ),
            _tool_spec(
                "inspect_coverage",
                "Inspect Evidence Coverage Matrix for the active or requested answer.",
                {
                    "session_id": {"type": "string"},
                    "answer_id": {"type": "string"},
                },
                required=["session_id"],
            ),
            _tool_spec(
                "reformat_answer",
                "Create a reformat request for an existing memo answer without invalidating evidence artifacts.",
                {
                    "session_id": {"type": "string"},
                    "answer_id": {"type": "string"},
                    "format": {"type": "string"},
                    "preserve_citations": {"type": "boolean"},
                    "execute": {"type": "boolean"},
                },
                required=["session_id", "format"],
            ),
            _tool_spec(
                "resume_analysis",
                "Inspect or resume an existing graph state from its first missing/invalid artifact.",
                {
                    "session_id": {"type": "string"},
                    "answer_id": {"type": "string"},
                    "state_path": {"type": "string"},
                    "execute": {"type": "boolean"},
                },
                required=["session_id"],
            ),
            _tool_spec(
                "get_session_state",
                "Read compact user/session context for controller routing.",
                {
                    "session_id": {"type": "string"},
                    "user_id": {"type": "string"},
                },
                required=["session_id"],
            ),
        ]

    def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        handlers = {
            "start_memo_analysis": self.start_memo_analysis,
            "revise_memo_scope": self.revise_memo_scope,
            "explain_evidence": self.explain_evidence,
            "inspect_coverage": self.inspect_coverage,
            "reformat_answer": self.reformat_answer,
            "resume_analysis": self.resume_analysis,
            "get_session_state": self.get_session_state,
        }
        handler = handlers.get(str(tool_name or ""))
        if handler is None:
            return ToolResult(tool_name=tool_name, status="error", message=f"unknown tool: {tool_name}", payload={})
        return handler(**dict(arguments or {}))

    def start_memo_analysis(
        self,
        *,
        query: str,
        user_id: str = "default_user",
        tenant_id: str = "default_tenant",
        session_id: str = "",
        years: list[int] | None = None,
        source_policy: str = "SEC_ONLY_10K",
        preferred_output: str = "investment_memo",
        execute: bool = False,
        graph_args: list[str] | None = None,
    ) -> ToolResult:
        query = str(query or "").strip()
        if not query:
            return ToolResult("start_memo_analysis", "error", {}, "query is required")
        if source_policy != "SEC_ONLY_10K":
            return ToolResult("start_memo_analysis", "error", {}, "only SEC_ONLY_10K is supported")

        session = self._load_or_create_session(
            session_id=session_id or _session_id(query),
            user_id=user_id,
            tenant_id=tenant_id,
        )
        answer_id = _answer_id(query)
        turn = self._new_turn(session, "start_memo_analysis", {"query": query, "execute": execute})
        session["preferences"]["preferred_output"] = preferred_output
        session["active_query"] = query
        session["active_scope"] = {
            "selected_tickers": _infer_tickers_from_query(query),
            "selected_years": [int(item) for item in (years or [2023, 2024, 2025])],
            "source_policy": source_policy,
        }
        analysis = {
            "answer_id": answer_id,
            "query": query,
            "status": "planned",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "source_policy": source_policy,
            "preferred_output": preferred_output,
            "artifact_refs": {},
            "invalidated_artifacts": [],
            "execution": {"execute": bool(execute), "command": []},
        }

        if execute:
            execution = self._run_graph_analysis(query, answer_id=answer_id, graph_args=graph_args or [])
            analysis.update(execution)
            session["active_answer_id"] = answer_id
            session["active_scope"].update(execution.get("scope") or {})
            turn["status"] = execution.get("status", "completed")
        else:
            turn["status"] = "planned"
            session["active_answer_id"] = answer_id

        session["analyses"][answer_id] = analysis
        self._save_session(session)
        return ToolResult(
            "start_memo_analysis",
            analysis["status"],
            {
                "session_id": session["session_id"],
                "answer_id": answer_id,
                "execute": bool(execute),
                "analysis": _compact_analysis(analysis),
                "session_path": str(self._session_path(session["session_id"]).resolve()),
            },
        )

    def revise_memo_scope(
        self,
        *,
        session_id: str,
        user_id: str = "",
        set_tickers: list[str] | None = None,
        add_tickers: list[str] | None = None,
        remove_tickers: list[str] | None = None,
        years: list[int] | None = None,
        preserve_output_style: bool = True,
        execute: bool = False,
        graph_args: list[str] | None = None,
    ) -> ToolResult:
        session = self._load_session_required(session_id)
        if user_id and session.get("user_id") not in {"", user_id}:
            return ToolResult("revise_memo_scope", "error", {}, "user_id does not match session owner")
        active_query = str(session.get("active_query") or "")
        if not active_query:
            return ToolResult("revise_memo_scope", "error", {}, "session has no active query")

        replacement = _upper_list(set_tickers or [])
        add = _upper_list(add_tickers or [])
        remove = set(_upper_list(remove_tickers or []))
        current = _upper_list((session.get("active_scope") or {}).get("selected_tickers") or [])
        base = replacement if replacement else current
        revised_tickers = sorted((set(base) | set(add)) - remove)
        revised_years = [int(item) for item in (years or (session.get("active_scope") or {}).get("selected_years") or [2023, 2024, 2025])]
        invalidated = SCOPE_INVALIDATES
        revised_query = _scope_revision_query(active_query, revised_tickers, revised_years)
        turn = self._new_turn(
            session,
            "revise_memo_scope",
            {
                "set_tickers": replacement,
                "add_tickers": add,
                "remove_tickers": sorted(remove),
                "years": revised_years,
                "execute": bool(execute),
            },
        )

        payload = {
            "session_id": session["session_id"],
            "base_answer_id": session.get("active_answer_id", ""),
            "set_tickers": replacement,
            "revised_tickers": revised_tickers,
            "revised_years": revised_years,
            "invalidated_artifacts": invalidated,
            "preserve_output_style": bool(preserve_output_style),
        }
        if execute:
            result = self.start_memo_analysis(
                query=revised_query,
                user_id=str(session.get("user_id") or "default_user"),
                tenant_id=str(session.get("tenant_id") or "default_tenant"),
                session_id=session["session_id"],
                years=revised_years,
                preferred_output=str((session.get("preferences") or {}).get("preferred_output") or "investment_memo"),
                execute=True,
                graph_args=graph_args or [],
            )
            turn["status"] = result.status
            payload["execution_result"] = result.payload
        else:
            session["active_scope"] = {
                **(session.get("active_scope") or {}),
                "selected_tickers": revised_tickers,
                "selected_years": revised_years,
            }
            turn["status"] = "planned"
            self._save_session(session)
        return ToolResult("revise_memo_scope", "planned" if not execute else "completed", payload)

    def explain_evidence(
        self,
        *,
        session_id: str,
        answer_id: str = "",
        driver_index: int | None = None,
        section: str = "",
        item_index: int | None = None,
        claim_reference: str = "",
        metric_id: str = "",
        evidence_id: str = "",
    ) -> ToolResult:
        session = self._load_session_required(session_id)
        analysis = self._analysis_for(session, answer_id)
        run_root = Path(str(analysis.get("run_root") or ""))
        if not run_root.exists():
            return ToolResult("explain_evidence", "error", {}, "analysis has no executable run_root")
        answer = _load_answer(run_root)
        ledger_rows = _load_ledger_rows(run_root)
        plan = _load_judgment_plan(run_root)
        target = _resolve_evidence_target(
            answer,
            driver_index=driver_index,
            section=section,
            item_index=item_index,
            claim_reference=claim_reference,
            metric_id=metric_id,
            evidence_id=evidence_id,
        )
        target_item = target.get("item") if isinstance(target.get("item"), dict) else {}
        metric_ids = _unique_strings(
            [metric_id]
            + (target.get("metric_ids") or [])
            + target_item.get("supporting_metric_ids", [])
            + target_item.get("metric_ids", [])
        )
        evidence_ids = _unique_strings(
            [evidence_id]
            + (target.get("evidence_ids") or [])
            + target_item.get("supporting_evidence_ids", [])
            + target_item.get("evidence_ids", [])
        )
        ledger_matches = [
            row
            for row in ledger_rows
            if str(row.get("metric_id") or "") in set(metric_ids)
            or str(row.get("source_evidence_id") or "") in set(evidence_ids)
            or str(row.get("object_id") or "") in set(evidence_ids)
        ]
        plan_matches = _matching_plan_drivers(plan, metric_ids, evidence_ids)
        self._append_turn_only(
            session,
            "explain_evidence",
            {
                "answer_id": analysis["answer_id"],
                "driver_index": driver_index,
                "section": section,
                "item_index": item_index,
                "claim_reference": claim_reference,
            },
        )
        return ToolResult(
            "explain_evidence",
            "completed",
            {
                "session_id": session["session_id"],
                "answer_id": analysis["answer_id"],
                "driver": target_item,
                "target": _compact_evidence_target(target),
                "metric_ids": metric_ids,
                "evidence_ids": evidence_ids,
                "ledger_matches": [_compact_ledger_row(row) for row in ledger_matches[:20]],
                "judgment_plan_matches": plan_matches[:10],
                "rerun_required": False,
            },
        )

    def inspect_coverage(self, *, session_id: str, answer_id: str = "") -> ToolResult:
        session = self._load_session_required(session_id)
        analysis = self._analysis_for(session, answer_id)
        run_root = Path(str(analysis.get("run_root") or ""))
        if not run_root.exists():
            return ToolResult("inspect_coverage", "error", {}, "analysis has no executable run_root")
        coverage = _read_json(run_root / "runtime_evidence_coverage_matrix.json")
        self._append_turn_only(session, "inspect_coverage", {"answer_id": analysis["answer_id"]})
        return ToolResult(
            "inspect_coverage",
            "completed",
            {
                "session_id": session["session_id"],
                "answer_id": analysis["answer_id"],
                "summary": coverage.get("summary") or {},
                "task_count": len(coverage.get("tasks") or []),
                "tasks": _compact_coverage_tasks(coverage.get("tasks") or []),
                "rerun_required": False,
            },
        )

    def reformat_answer(
        self,
        *,
        session_id: str,
        answer_id: str = "",
        format: str,
        preserve_citations: bool = True,
        execute: bool = False,
    ) -> ToolResult:
        session = self._load_session_required(session_id)
        analysis = self._analysis_for(session, answer_id)
        request = {
            "schema_version": "sec_agent_reformat_request_v0.1",
            "answer_id": analysis["answer_id"],
            "format": str(format),
            "preserve_citations": bool(preserve_citations),
            "invalidated_artifacts": FORMAT_INVALIDATES,
            "execute": bool(execute),
            "created_at": _utc_now(),
        }
        request_path = self._session_dir(session["session_id"]) / f"reformat_{_slug(format)}_{int(time.time())}.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._append_turn_only(session, "reformat_answer", request)
        return ToolResult(
            "reformat_answer",
            "planned",
            {
                "session_id": session["session_id"],
                "answer_id": analysis["answer_id"],
                "request_path": str(request_path.resolve()),
                "invalidated_artifacts": FORMAT_INVALIDATES,
                "execute_supported": False,
                "note": "v0 records the reformat request; synthesis-only execution is the next increment.",
            },
        )

    def resume_analysis(
        self,
        *,
        session_id: str,
        answer_id: str = "",
        state_path: str = "",
        execute: bool = False,
        graph_args: list[str] | None = None,
    ) -> ToolResult:
        session = self._load_session_required(session_id)
        analysis = self._analysis_for(session, answer_id)
        resolved_state_path = Path(state_path or analysis.get("state_path") or "")
        if not resolved_state_path.exists():
            return ToolResult("resume_analysis", "error", {}, "sec_agent_state.json not found")
        state = SecAgentState.read_json(resolved_state_path)
        report = state_resume_report(state)
        payload = {
            "session_id": session["session_id"],
            "answer_id": analysis["answer_id"],
            "state_path": str(resolved_state_path.resolve()),
            "resume_report": report,
            "execute": bool(execute),
        }
        if execute and report.get("next_ready_node"):
            command = [
                self.python,
                "scripts/cloud/sec_agent_graph_runner.py",
                "--resume-state",
                "--state-path",
                str(resolved_state_path),
                *(graph_args or []),
            ]
            proc = subprocess.run(command, cwd=self.repo_root, capture_output=True, text=True, check=False)
            payload["returncode"] = proc.returncode
            payload["stdout_tail"] = proc.stdout[-4000:]
            payload["stderr_tail"] = proc.stderr[-4000:]
        self._append_turn_only(session, "resume_analysis", {"answer_id": analysis["answer_id"], "execute": execute})
        return ToolResult("resume_analysis", "completed", payload)

    def get_session_state(self, *, session_id: str, user_id: str = "") -> ToolResult:
        session = self._load_session_required(session_id)
        if user_id and session.get("user_id") not in {"", user_id}:
            return ToolResult("get_session_state", "error", {}, "user_id does not match session owner")
        return ToolResult("get_session_state", "completed", _compact_session(session))

    def _run_graph_analysis(self, query: str, *, answer_id: str, graph_args: list[str]) -> dict[str, Any]:
        started = time.time()
        command = [
            self.python,
            "scripts/cloud/sec_agent_graph_runner.py",
            "--prompt",
            query,
            "--thread-id",
            answer_id,
            *graph_args,
        ]
        proc = subprocess.run(command, cwd=self.repo_root, capture_output=True, text=True, check=False)
        summary = _parse_last_json(proc.stdout)
        run_root_text = str(summary.get("run_root") or "").strip()
        run_root = Path(run_root_text) if run_root_text else None
        state_path = (run_root / "sec_agent_state.json") if run_root else None
        has_state = bool(run_root and run_root.exists() and state_path and state_path.exists())
        artifacts = _artifact_refs_from_state(state_path) if has_state and state_path else {}
        scope = {}
        if has_state and run_root and state_path:
            scope = _scope_from_query_contract(run_root)
            if not scope:
                state = SecAgentState.read_json(state_path)
                scope = {"selected_tickers": state.selected_tickers, "selected_years": state.selected_years}
        return {
            "status": "completed" if proc.returncode == 0 else "failed",
            "updated_at": _utc_now(),
            "run_root": str(run_root.resolve()) if has_state and run_root else "",
            "state_path": str(state_path.resolve()) if has_state and state_path else "",
            "artifact_refs": artifacts,
            "scope": scope,
            "execution": {
                "execute": True,
                "command": _redacted_command(command),
                "returncode": proc.returncode,
                "elapsed_sec": round(time.time() - started, 4),
                "stdout_tail": proc.stdout[-4000:],
                "stderr_tail": proc.stderr[-4000:],
            },
        }

    def _load_or_create_session(self, *, session_id: str, user_id: str, tenant_id: str) -> dict[str, Any]:
        path = self._session_path(session_id)
        if path.exists():
            session = _read_json(path)
            session.setdefault("preferences", {})
            session.setdefault("analyses", {})
            session.setdefault("turns", [])
            return session
        return {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "preferences": {
                "language": "zh",
                "default_source_policy": "SEC_ONLY_10K",
                "default_years": [2023, 2024, 2025],
                "preferred_output": "investment_memo",
                "risk_tone": "conservative",
            },
            "conversation_summary": "",
            "active_query": "",
            "active_scope": {},
            "active_answer_id": "",
            "analyses": {},
            "turns": [],
        }

    def _load_session_required(self, session_id: str) -> dict[str, Any]:
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"session not found: {session_id}")
        return _read_json(path)

    def _analysis_for(self, session: dict[str, Any], answer_id: str = "") -> dict[str, Any]:
        resolved = answer_id or str(session.get("active_answer_id") or "")
        analyses = session.get("analyses") or {}
        if resolved not in analyses:
            raise KeyError(f"analysis not found: {resolved}")
        return analyses[resolved]

    def _new_turn(self, session: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        turn = {
            "turn_id": f"turn_{len(session.get('turns') or []) + 1:04d}",
            "tool_name": tool_name,
            "arguments": arguments,
            "created_at": _utc_now(),
            "status": "running",
        }
        session.setdefault("turns", []).append(turn)
        session["updated_at"] = _utc_now()
        return turn

    def _append_turn_only(self, session: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> None:
        turn = self._new_turn(session, tool_name, arguments)
        turn["status"] = "completed"
        self._save_session(session)

    def _save_session(self, session: dict[str, Any]) -> Path:
        session["updated_at"] = _utc_now()
        path = self._session_path(str(session["session_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _session_dir(self, session_id: str) -> Path:
        return self.session_root / _safe_id(session_id)

    def _session_path(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session_state.json"


def _tool_spec(name: str, description: str, properties: dict[str, Any], *, required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _compact_session(session: dict[str, Any]) -> dict[str, Any]:
    analyses = session.get("analyses") or {}
    return {
        "schema_version": session.get("schema_version"),
        "session_id": session.get("session_id"),
        "user_id": session.get("user_id"),
        "tenant_id": session.get("tenant_id"),
        "preferences": session.get("preferences") or {},
        "conversation_summary": session.get("conversation_summary") or "",
        "active_query": session.get("active_query") or "",
        "active_scope": session.get("active_scope") or {},
        "active_answer_id": session.get("active_answer_id") or "",
        "analysis_count": len(analyses),
        "analyses": {key: _compact_analysis(value) for key, value in analyses.items()},
        "turn_count": len(session.get("turns") or []),
    }


def _compact_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer_id": analysis.get("answer_id"),
        "query": analysis.get("query"),
        "status": analysis.get("status"),
        "run_root": analysis.get("run_root", ""),
        "state_path": analysis.get("state_path", ""),
        "artifact_keys": sorted((analysis.get("artifact_refs") or {}).keys()),
        "invalidated_artifacts": analysis.get("invalidated_artifacts") or [],
        "execution": {
            "execute": (analysis.get("execution") or {}).get("execute"),
            "returncode": (analysis.get("execution") or {}).get("returncode"),
            "elapsed_sec": (analysis.get("execution") or {}).get("elapsed_sec"),
        },
    }


def _artifact_refs_from_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    state = SecAgentState.read_json(state_path)
    return {key: ref.to_dict() for key, ref in state.artifacts.items()}


def _load_answer(run_root: Path) -> dict[str, Any]:
    rows = _read_jsonl(run_root / "qwen" / "agent_outputs.jsonl")
    if not rows:
        return {}
    answer = rows[0].get("answer")
    return answer if isinstance(answer, dict) else {}


def _scope_from_query_contract(run_root: Path) -> dict[str, Any]:
    contract = _read_json(run_root / "query_contract.json")
    scope = contract.get("scope") if isinstance(contract.get("scope"), dict) else {}
    tickers = _upper_list(contract.get("focus_tickers") or scope.get("focus_tickers") or [])
    years = [int(item) for item in (contract.get("years") or scope.get("years") or []) if str(item).isdigit()]
    result: dict[str, Any] = {}
    if tickers:
        result["selected_tickers"] = tickers
    if years:
        result["selected_years"] = years
    return result


def _load_ledger_rows(run_root: Path) -> list[dict[str, Any]]:
    payload = _read_json(run_root / "runtime_exact_value_ledger.json")
    return [row for row in payload.get("rows") or [] if isinstance(row, dict)]


def _load_judgment_plan(run_root: Path) -> dict[str, Any]:
    payload = _read_json(run_root / "runtime_judgment_plan.json")
    plans = [item for item in payload.get("plans") or [] if isinstance(item, dict)]
    return plans[0] if plans else {}


def _resolve_evidence_target(
    answer: dict[str, Any],
    *,
    driver_index: int | None,
    section: str,
    item_index: int | None,
    claim_reference: str,
    metric_id: str,
    evidence_id: str,
) -> dict[str, Any]:
    targets = _memo_evidence_targets(answer)
    if not targets:
        return {}
    section_name = _safe_section_name(section)
    requested_index = item_index or driver_index
    if section_name and requested_index:
        target = _target_by_section_index(targets, section_name, requested_index)
        if target:
            return target
    if metric_id or evidence_id:
        direct = _target_by_id(targets, metric_id=metric_id, evidence_id=evidence_id)
        if direct:
            return direct
    if claim_reference and _has_specific_reference_terms(claim_reference):
        best = _best_reference_target(targets, claim_reference)
        if best:
            return best
    if driver_index:
        target = _target_by_section_index(targets, "decision_drivers", driver_index)
        if target:
            return target
        for fallback_section in ("why_it_matters", "what_changed", "key_points", "counterarguments", "watch_items", "peer_readthrough"):
            target = _target_by_section_index(targets, fallback_section, driver_index)
            if target:
                return target
    if item_index:
        for fallback_section in ("decision_drivers", "why_it_matters", "what_changed", "key_points", "counterarguments", "watch_items", "peer_readthrough"):
            target = _target_by_section_index(targets, fallback_section, item_index)
            if target:
                return target
    if claim_reference:
        best = _best_reference_target(targets, claim_reference)
        if best:
            return best
    return {}


def _memo_evidence_targets(answer: dict[str, Any]) -> list[dict[str, Any]]:
    sections = (
        "decision_drivers",
        "why_it_matters",
        "what_changed",
        "key_points",
        "counterarguments",
        "peer_readthrough",
        "watch_items",
    )
    targets: list[dict[str, Any]] = []
    for section in sections:
        items = answer.get(section) or []
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            metric_ids = _unique_strings(item.get("supporting_metric_ids") or item.get("metric_ids") or [])
            evidence_ids = _unique_strings(item.get("supporting_evidence_ids") or item.get("evidence_ids") or [])
            text = _memo_item_text(item)
            targets.append(
                {
                    "section": section,
                    "index": index,
                    "item": item,
                    "metric_ids": metric_ids,
                    "evidence_ids": evidence_ids,
                    "text": text,
                    "search_text": _searchable_text(section, item, metric_ids, evidence_ids, text),
                }
            )
    return targets


def _target_by_section_index(targets: list[dict[str, Any]], section: str, index: int | None) -> dict[str, Any]:
    if not section or not index:
        return {}
    ordinal = max(int(index), 1)
    for target in targets:
        if target.get("section") == section and int(target.get("index") or 0) == ordinal:
            return target
    return {}


def _target_by_id(targets: list[dict[str, Any]], *, metric_id: str, evidence_id: str) -> dict[str, Any]:
    metric = str(metric_id or "").strip()
    evidence = str(evidence_id or "").strip()
    for target in targets:
        if metric and metric in set(target.get("metric_ids") or []):
            return target
        if evidence and evidence in set(target.get("evidence_ids") or []):
            return target
    return {}


def _best_reference_target(targets: list[dict[str, Any]], reference: str) -> dict[str, Any]:
    terms = _reference_terms(reference)
    if not terms:
        return {}
    best_target: dict[str, Any] = {}
    best_score = 0
    for target in targets:
        text = str(target.get("search_text") or "")
        score = sum(1 for term in terms if term and term in text)
        if score > best_score:
            best_score = score
            best_target = target
    return best_target if best_score > 0 else {}


def _has_specific_reference_terms(reference: str) -> bool:
    return bool(_reference_terms(reference))


def _reference_terms(reference: str) -> list[str]:
    text = _normalize_reference_text(reference)
    terms: list[str] = []
    for ticker in KNOWN_TICKERS:
        if re.search(rf"(?<![a-z0-9]){re.escape(ticker.lower())}(?![a-z0-9])", text):
            terms.append(ticker.lower())
    synonym_groups = [
        ("gross_margin", ("毛利率", "gross margin", "margin", "profitability", "盈利")),
        ("cloud", ("云", "cloud", "azure", "aws")),
        ("advertising", ("广告", "advertising", "ad revenue", "ads")),
        ("data_center", ("数据中心", "data center", "compute", "networking")),
        ("operating_cash_flow", ("经营现金流", "operating cash flow", "cash flow", "ocf")),
        ("customer_concentration", ("客户集中", "customer concentration", "major customer", "direct customer")),
        ("capital_expenditure", ("资本开支", "capex", "capital expenditure")),
        ("rpo", ("rpo", "remaining performance")),
        ("research_development", ("研发", "r&d", "research and development")),
        ("risk", ("风险", "risk", "出口", "export", "geopolitical")),
    ]
    for canonical, aliases in synonym_groups:
        if any(_normalize_reference_text(alias) in text for alias in aliases):
            terms.append(canonical)
            terms.extend(_normalize_reference_text(alias) for alias in aliases)
    return _unique_strings(terms)


def _searchable_text(section: str, item: dict[str, Any], metric_ids: list[str], evidence_ids: list[str], text: str) -> str:
    raw_parts = [section, text, " ".join(metric_ids), " ".join(evidence_ids)]
    raw_parts.extend(str(value) for value in item.values() if isinstance(value, str))
    return _normalize_reference_text(" ".join(raw_parts))


def _memo_item_text(item: dict[str, Any]) -> str:
    text_keys = (
        "driver_claim",
        "why_it_matters",
        "claim",
        "insight",
        "business_implication",
        "point",
        "item",
        "readthrough",
        "role",
        "why_it_could_weaken_thesis",
        "metric_family",
        "caveat",
    )
    return " ".join(str(item.get(key) or "") for key in text_keys).strip()


def _compact_evidence_target(target: dict[str, Any]) -> dict[str, Any]:
    if not target:
        return {}
    return {
        "section": target.get("section"),
        "index": target.get("index"),
        "text_preview": str(target.get("text") or "")[:500],
        "metric_ids": target.get("metric_ids") or [],
        "evidence_ids": target.get("evidence_ids") or [],
    }


def _safe_section_name(section: str) -> str:
    text = str(section or "").strip().lower()
    aliases = {
        "drivers": "decision_drivers",
        "driver": "decision_drivers",
        "growth_drivers": "why_it_matters",
        "growth_driver": "why_it_matters",
        "why": "why_it_matters",
        "changed": "what_changed",
        "changes": "what_changed",
        "counterargument": "counterarguments",
        "watch": "watch_items",
    }
    return aliases.get(text, text)


def _normalize_reference_text(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _matching_plan_drivers(plan: dict[str, Any], metric_ids: list[str], evidence_ids: list[str]) -> list[dict[str, Any]]:
    metric_set = set(metric_ids)
    evidence_set = set(evidence_ids)
    matches = []
    for driver in plan.get("decision_drivers") or plan.get("drivers") or []:
        if not isinstance(driver, dict):
            continue
        driver_metric_ids = set(_unique_strings(driver.get("supporting_metric_ids") or driver.get("metric_ids") or []))
        driver_evidence_ids = set(_unique_strings(driver.get("supporting_evidence_ids") or driver.get("evidence_ids") or []))
        if driver_metric_ids & metric_set or driver_evidence_ids & evidence_set:
            matches.append(
                {
                    "driver_id": driver.get("driver_id"),
                    "driver_claim": driver.get("driver_claim") or driver.get("claim"),
                    "supporting_metric_ids": sorted(driver_metric_ids),
                    "supporting_evidence_ids": sorted(driver_evidence_ids),
                }
            )
    return matches


def _compact_ledger_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": row.get("metric_id"),
        "ticker": row.get("ticker") or row.get("object_ticker"),
        "fiscal_year": row.get("fiscal_year") or row.get("year"),
        "metric_name": row.get("metric_name") or row.get("label"),
        "value": row.get("value") or row.get("normalized_value") or row.get("raw_value"),
        "unit": row.get("unit") or row.get("normalized_unit"),
        "source_evidence_id": row.get("source_evidence_id"),
        "object_id": row.get("object_id"),
        "preview": row.get("preview") or row.get("text_preview"),
    }


def _compact_coverage_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for task in tasks[:20]:
        compact.append(
            {
                "task_id": task.get("task_id"),
                "required_tickers": task.get("required_tickers") or [],
                "peer_tickers": task.get("peer_tickers") or [],
                "covered_tickers": task.get("covered_tickers") or [],
                "covered_peer_tickers": task.get("covered_peer_tickers") or [],
                "missing_tickers": task.get("missing_tickers") or [],
                "missing_peer_tickers": task.get("missing_peer_tickers") or [],
                "coverage_complete": task.get("coverage_complete"),
                "answer_status": task.get("answer_status"),
            }
        )
    return compact


def _scope_revision_query(active_query: str, tickers: list[str], years: list[int]) -> str:
    topic_context = _strip_scope_terms(active_query)
    ticker_text = ", ".join(tickers) if tickers else "the current active company set"
    year_text = ", ".join(str(item) for item in years) if years else "the current active fiscal years"
    return (
        "请重新生成一版 SEC-only 10-K 投资备忘录，并把下面的 revised scope 作为唯一公司和年份约束。\n"
        f"- 目标公司: {ticker_text}\n"
        f"- 目标年份: {year_text}\n"
        "- 来源边界: 只使用 SEC 10-K；不要引入外部新闻、股价、分析师观点或当前市场数据。\n"
        "- Scope 规则: 不要继承上一轮里未列出的公司或年份；不要做同行对比，除非目标公司自己的 10-K 文本中作为背景出现。\n"
        f"- 保留的分析主题: {topic_context or 'AI/growth, margin/profitability changes, and key SEC-filed risks.'}"
    )


def _strip_scope_terms(text: str) -> str:
    result = str(text or "")
    for ticker in KNOWN_TICKERS:
        result = re.sub(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\b20\d{2}\s*[-–]\s*20\d{2}\b", "", result)
    result = re.sub(r"\b20\d{2}\b", "", result)
    result = re.sub(r"\s+", " ", result)
    return result.strip(" ,，。;；:-")


def _infer_tickers_from_query(query: str) -> list[str]:
    text = str(query or "").upper()
    result = []
    for ticker in KNOWN_TICKERS:
        if re.search(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])", text):
            result.append(ticker)
    return result


def _parse_last_json(text: str) -> dict[str, Any]:
    text = str(text or "").strip()
    if not text:
        return {}
    starts = [match.start() for match in re.finditer(r"\{", text)]
    for start in reversed(starts):
        try:
            value = json.loads(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _upper_list(values: list[Any]) -> list[str]:
    return _unique_strings(str(item).upper() for item in values if str(item or "").strip())


def _unique_strings(values: Any) -> list[str]:
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return text[:96] or "default"


def _slug(value: str) -> str:
    return _safe_id(value).lower()


def _session_id(query: str) -> str:
    digest = hashlib.sha1(query.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{digest}"


def _answer_id(query: str) -> str:
    digest = hashlib.sha1((query + _utc_now()).encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _redacted_command(command: list[str]) -> list[str]:
    redacted = []
    skip_next = False
    for item in command:
        if skip_next:
            redacted.append("<redacted>")
            skip_next = False
            continue
        redacted.append(item)
        if item in {"--api-key", "--password"}:
            skip_next = True
    return redacted


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Session-aware SEC agent tool harness.")
    parser.add_argument("--session-root", default=str(DEFAULT_SESSION_ROOT))
    parser.add_argument("--python", default=sys.executable)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-tools")

    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("--tool", required=True)
    dispatch.add_argument("--args-json", required=True)

    state = sub.add_parser("get-session-state")
    state.add_argument("--session-id", required=True)
    state.add_argument("--user-id", default="")

    start = sub.add_parser("start-memo-analysis")
    start.add_argument("--query", required=True)
    start.add_argument("--user-id", default="default_user")
    start.add_argument("--tenant-id", default="default_tenant")
    start.add_argument("--session-id", default="")
    start.add_argument("--years", default="2023,2024,2025")
    start.add_argument("--execute", action="store_true")

    revise = sub.add_parser("revise-memo-scope")
    revise.add_argument("--session-id", required=True)
    revise.add_argument("--add-tickers", default="")
    revise.add_argument("--remove-tickers", default="")
    revise.add_argument("--years", default="")
    revise.add_argument("--execute", action="store_true")

    explain = sub.add_parser("explain-evidence")
    explain.add_argument("--session-id", required=True)
    explain.add_argument("--answer-id", default="")
    explain.add_argument("--driver-index", type=int, default=0)
    explain.add_argument("--metric-id", default="")
    explain.add_argument("--evidence-id", default="")

    coverage = sub.add_parser("inspect-coverage")
    coverage.add_argument("--session-id", required=True)
    coverage.add_argument("--answer-id", default="")

    reformat = sub.add_parser("reformat-answer")
    reformat.add_argument("--session-id", required=True)
    reformat.add_argument("--answer-id", default="")
    reformat.add_argument("--format", required=True)
    reformat.add_argument("--preserve-citations", action="store_true", default=True)

    resume = sub.add_parser("resume-analysis")
    resume.add_argument("--session-id", required=True)
    resume.add_argument("--answer-id", default="")
    resume.add_argument("--state-path", default="")
    resume.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def cli_main(argv: list[str] | None = None) -> int:
    args = parse_cli_args(argv)
    harness = SecAgentToolHarness(session_root=args.session_root, python=args.python)
    if args.command == "list-tools":
        print(json.dumps(harness.tool_specs(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "dispatch":
        result = harness.dispatch(args.tool, json.loads(args.args_json))
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "get-session-state":
        result = harness.get_session_state(session_id=args.session_id, user_id=args.user_id)
    elif args.command == "start-memo-analysis":
        result = harness.start_memo_analysis(
            query=args.query,
            user_id=args.user_id,
            tenant_id=args.tenant_id,
            session_id=args.session_id,
            years=_parse_years(args.years),
            execute=args.execute,
        )
    elif args.command == "revise-memo-scope":
        result = harness.revise_memo_scope(
            session_id=args.session_id,
            add_tickers=_split_csv(args.add_tickers),
            remove_tickers=_split_csv(args.remove_tickers),
            years=_parse_years(args.years) if args.years else None,
            execute=args.execute,
        )
    elif args.command == "explain-evidence":
        result = harness.explain_evidence(
            session_id=args.session_id,
            answer_id=args.answer_id,
            driver_index=args.driver_index or None,
            metric_id=args.metric_id,
            evidence_id=args.evidence_id,
        )
    elif args.command == "inspect-coverage":
        result = harness.inspect_coverage(session_id=args.session_id, answer_id=args.answer_id)
    elif args.command == "reformat-answer":
        result = harness.reformat_answer(
            session_id=args.session_id,
            answer_id=args.answer_id,
            format=args.format,
            preserve_citations=args.preserve_citations,
        )
    elif args.command == "resume-analysis":
        result = harness.resume_analysis(
            session_id=args.session_id,
            answer_id=args.answer_id,
            state_path=args.state_path,
            execute=args.execute,
        )
    else:
        raise AssertionError(args.command)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _parse_years(value: str) -> list[int]:
    return [int(item) for item in _split_csv(value)]
