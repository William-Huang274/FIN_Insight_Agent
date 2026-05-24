from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.context_api import SecAgentContextRequestHandler  # noqa: E402
from sec_agent.context_manager import ContextBudget, SecAgentContextManager  # noqa: E402
from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import DEFAULT_SESSION_ROOT, SecAgentToolHarness  # noqa: E402


DEFAULT_CONTEXT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "context_store"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real ContextManager-backed SEC agent session from free-form prompts."
    )
    parser.add_argument("--prompt", action="append", default=[], help="Run one prompt. Repeat for a short scripted session.")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--tenant-id", default=os.environ.get("SEC_AGENT_TENANT_ID", "manual_tenant"))
    parser.add_argument("--user-id", default=os.environ.get("SEC_AGENT_USER_ID", "manual_user"))
    parser.add_argument("--session-root", default=str(DEFAULT_SESSION_ROOT))
    parser.add_argument("--context-root", default=str(DEFAULT_CONTEXT_ROOT))
    parser.add_argument("--turn-log", default="")
    parser.add_argument("--python", default=os.environ.get("PY", sys.executable))
    parser.add_argument("--no-execute", dest="execute", action="store_false", help="Route and record only; do not run the DAG.")
    parser.set_defaults(execute=True)
    parser.add_argument("--answer-preview-chars", type=int, default=8000)
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument(
        "--controller-backend",
        default=os.environ.get("TOOL_CONTROLLER_BACKEND", "deepseek"),
        choices=("deepseek", "openai_compatible", "qwen_vllm", "heuristic"),
    )
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("TEMPERATURE", "0.0")))
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=_env_int("CONTROLLER_MAX_TOKENS", _env_int("TOOL_CONTROLLER_MAX_TOKENS", 1024)),
        help="Max tokens for the one-step tool controller, not the SEC memo synthesis call.",
    )
    parser.add_argument(
        "--graph-max-tokens",
        type=int,
        default=_env_int("SYNTHESIS_MAX_TOKENS", _env_int("GRAPH_MAX_TOKENS", 8000)),
        help="Max tokens for the downstream SEC memo synthesis call.",
    )
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("TIMEOUT_S", "180")))
    parser.add_argument("--query-planner", default=os.environ.get("QUERY_PLANNER", "llm"), choices=("heuristic", "llm"))
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "cuda"))
    parser.add_argument("--graph-verbose", action="store_true", help="Do not pass --quiet to the graph runner.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.controller_backend != "heuristic" and args.api_key_env and not os.environ.get(args.api_key_env):
        print(f"{args.api_key_env} is not set in this shell.", file=sys.stderr)
        return 2

    session_id = args.session_id.strip() or _manual_session_id()
    session_root = _resolve(args.session_root)
    context_root = _resolve(args.context_root)
    turn_log = _resolve(args.turn_log) if args.turn_log else _default_turn_log(session_id)
    turn_log.parent.mkdir(parents=True, exist_ok=True)

    handler = _build_handler(args=args, session_root=session_root, context_root=context_root)
    graph_args = _graph_args(args)
    state = {
        "tenant_id": args.tenant_id,
        "user_id": args.user_id,
        "session_id": session_id,
        "turn_log": str(turn_log.resolve()),
    }

    _print_start_banner(args=args, state=state, session_root=session_root, context_root=context_root)
    prompts = [prompt for prompt in args.prompt if str(prompt or "").strip()]
    if prompts:
        for prompt in prompts:
            state["session_id"] = _run_turn(
                handler=handler,
                args=args,
                graph_args=graph_args,
                turn_log=turn_log,
                tenant_id=args.tenant_id,
                user_id=args.user_id,
                session_id=str(state["session_id"]),
                prompt=str(prompt),
            )
        return 0

    _print_help()
    while True:
        try:
            prompt = input("\nsec-session> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        if prompt in {"/exit", "/quit"}:
            return 0
        if prompt == "/help":
            _print_help()
            continue
        if prompt == "/state":
            _print_session_state(handler.harness, str(state["session_id"]), args.user_id)
            continue
        if prompt == "/context":
            _print_context(handler.context_manager, args.tenant_id, args.user_id, str(state["session_id"]))
            continue
        if prompt == "/answer":
            _print_latest_answer(handler.harness, str(state["session_id"]), args.user_id, args.answer_preview_chars)
            continue
        state["session_id"] = _run_turn(
            handler=handler,
            args=args,
            graph_args=graph_args,
            turn_log=turn_log,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            session_id=str(state["session_id"]),
            prompt=prompt,
        )


def _build_handler(
    *,
    args: argparse.Namespace,
    session_root: Path,
    context_root: Path,
) -> SecAgentContextRequestHandler:
    context_manager = SecAgentContextManager(
        session_root=session_root,
        context_root=context_root,
        budget=ContextBudget(
            target_controller_tokens=3000,
            caution_controller_tokens=6000,
            max_recent_turns=8,
            max_candidate_sessions=5,
        ),
    )
    harness = SecAgentToolHarness(session_root=session_root, python=args.python, repo_root=REPO_ROOT)
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(
            controller_backend=args.controller_backend,
            llm_backend=args.llm_backend,
            base_url=args.base_url,
            chat_completions_path=args.chat_completions_path,
            model=args.model,
            api_key_env=args.api_key_env,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_s=args.timeout_s,
            max_steps=1,
            execute_tools=False,
        ),
    )
    return SecAgentContextRequestHandler(
        context_manager=context_manager,
        controller=controller,
        harness=harness,
        lock_requests=True,
    )


def _run_turn(
    *,
    handler: SecAgentContextRequestHandler,
    args: argparse.Namespace,
    graph_args: list[str],
    turn_log: Path,
    tenant_id: str,
    user_id: str,
    session_id: str,
    prompt: str,
) -> str:
    handler.context_manager.ingest_sessions()
    started = time.time()
    result = handler.handle_turn(
        tenant_id=tenant_id,
        user_id=user_id,
        user_message=prompt,
        session_id=session_id,
        allow_new_session=True,
        execute_tools=bool(args.execute),
        graph_args=graph_args,
    )
    result["manual_session_cli"] = {
        "created_at": _utc_now(),
        "prompt": prompt,
        "elapsed_sec": round(time.time() - started, 4),
    }
    _append_jsonl(turn_log, result)
    resolved_session_id = _resolved_session_id(result) or session_id
    _print_turn_result(result, answer_preview_chars=args.answer_preview_chars, print_json=args.print_json)
    return resolved_session_id


def _graph_args(args: argparse.Namespace) -> list[str]:
    result = [
        "--llm-backend",
        args.llm_backend,
        "--base-url",
        args.base_url,
        "--chat-completions-path",
        args.chat_completions_path,
        "--model",
        args.model,
        "--query-planner",
        args.query_planner,
        "--max-tokens",
        str(args.graph_max_tokens),
        "--bge-first",
        "--bge-device",
        args.bge_device,
    ]
    if args.api_key_env:
        result.extend(["--api-key-env", args.api_key_env])
    if not args.graph_verbose:
        result.append("--quiet")
    return result


def _print_turn_result(result: dict[str, Any], *, answer_preview_chars: int, print_json: bool) -> None:
    tool_call = result.get("tool_call") if isinstance(result.get("tool_call"), dict) else {}
    tool_result = result.get("tool_result") if isinstance(result.get("tool_result"), dict) else {}
    payload = tool_result.get("payload") if isinstance(tool_result.get("payload"), dict) else {}
    post = result.get("post_context_snapshot") if isinstance(result.get("post_context_snapshot"), dict) else {}
    run_root = _find_key(payload, "run_root")
    state_path = _find_key(payload, "state_path")
    answer_id = str(post.get("active_answer_id") or _find_key(payload, "answer_id") or "")
    print("\n--- turn result ---")
    print(f"status: {result.get('status')} reason: {result.get('reason') or ''}")
    print(f"tool: {tool_call.get('name') or ''} tool_status: {tool_result.get('status') or ''}")
    print(f"session_id: {post.get('session_id') or _find_key(payload, 'session_id') or ''}")
    print(f"active_answer_id: {answer_id}")
    if post.get("active_scope"):
        print("active_scope: " + json.dumps(post.get("active_scope"), ensure_ascii=False, sort_keys=True))
    if run_root:
        print(f"run_root: {run_root}")
    if state_path:
        print(f"sec_agent_state: {state_path}")
    if post.get("artifact_state"):
        artifact_state = post.get("artifact_state") if isinstance(post.get("artifact_state"), dict) else {}
        print(
            "artifact_state: "
            + json.dumps(
                {
                    "complete": artifact_state.get("complete_artifacts") or [],
                    "missing": artifact_state.get("missing_artifacts") or [],
                    "invalidated": artifact_state.get("invalidated_artifacts") or [],
                },
                ensure_ascii=False,
            )
        )
    if result.get("status") == "tool_error":
        error_tail = _find_key(payload, "stderr_tail") or _find_key(payload, "stdout_tail")
        if error_tail:
            print("\n--- execution error tail ---")
            print(str(error_tail)[-2400:].rstrip())
    _print_tool_payload(str(tool_call.get("name") or ""), payload)
    if print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if run_root and answer_preview_chars > 0:
        _print_answer_preview(Path(str(run_root)), answer_preview_chars)


def _print_answer_preview(run_root: Path, max_chars: int) -> None:
    text = _answer_preview_text(run_root)
    if not text:
        print("answer_preview: not found")
        return
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    print("\n--- answer preview ---")
    print(text.rstrip())


def _answer_preview_text(run_root: Path) -> str:
    rendered_path = run_root / "qwen" / "rendered_answer.md"
    if rendered_path.exists():
        return rendered_path.read_text(encoding="utf-8", errors="replace")

    agent_path = run_root / "qwen" / "agent_outputs.jsonl"
    if agent_path.exists():
        rows = _read_jsonl(agent_path)
        for row in rows:
            answer = row.get("answer") if isinstance(row, dict) else None
            if isinstance(answer, dict):
                return _render_answer_markdown(answer)

    audit_path = run_root / "qwen" / "input_output.md"
    if audit_path.exists():
        return audit_path.read_text(encoding="utf-8", errors="replace")
    return ""


def _print_tool_payload(tool_name: str, payload: dict[str, Any]) -> None:
    if not payload:
        return
    if tool_name == "explain_evidence":
        _print_explain_evidence_payload(payload)
    elif tool_name == "inspect_coverage":
        _print_inspect_coverage_payload(payload)
    elif tool_name == "reformat_answer":
        print("\n--- tool output ---")
        print(f"reformat request: {payload.get('request_path') or ''}")
        if payload.get("note"):
            print(str(payload["note"]))
    elif tool_name == "revise_memo_scope":
        revised = payload.get("revised_tickers") or []
        years = payload.get("revised_years") or []
        if revised or years:
            print("\n--- tool output ---")
            print("revised_scope: " + json.dumps({"tickers": revised, "years": years}, ensure_ascii=False))


def _print_explain_evidence_payload(payload: dict[str, Any]) -> None:
    print("\n--- tool output: evidence ---")
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    driver = payload.get("driver") if isinstance(payload.get("driver"), dict) else {}
    target_text = _clean_display_text(target.get("text") or _memo_item_text(driver) or "")
    if target.get("section") or target.get("index"):
        print(f"target: {target.get('section') or ''} #{target.get('index') or ''}".rstrip())
    if target_text:
        print(f"claim: {target_text}")
    ledger = [row for row in (payload.get("ledger_matches") or []) if isinstance(row, dict)]
    if ledger:
        print("ledger:")
        for row in ledger[:8]:
            print(
                "  - "
                + " ".join(
                    part
                    for part in (
                        str(row.get("ticker") or ""),
                        str(row.get("fiscal_year") or ""),
                        str(row.get("metric_family") or ""),
                        "=",
                        str(row.get("display_value_zh") or row.get("value") or ""),
                    )
                    if part
                )
            )
    plan = [row for row in (payload.get("judgment_plan_matches") or []) if isinstance(row, dict)]
    if plan:
        print("judgment_plan:")
        for row in plan[:4]:
            text = _clean_display_text(row.get("driver_claim") or row.get("claim") or row.get("why_it_matters") or "")
            if text:
                print(f"  - {text}")
    metric_count = len(payload.get("metric_ids") or [])
    evidence_count = len(payload.get("evidence_ids") or [])
    if metric_count or evidence_count:
        print(f"support: {metric_count} metric refs, {evidence_count} evidence refs")
    if not target_text and not ledger:
        print("No specific evidence target was resolved. Ask for a numbered section item or a metric/company pair.")


def _print_inspect_coverage_payload(payload: dict[str, Any]) -> None:
    print("\n--- tool output: coverage ---")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary:
        print("summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    tasks = [task for task in (payload.get("tasks") or []) if isinstance(task, dict)]
    if tasks:
        print("tasks:")
        for task in tasks[:10]:
            status = task.get("status") or task.get("coverage_status") or ""
            question = _clean_display_text(task.get("question_zh") or task.get("task_id") or "")
            missing = task.get("missing_metric_families") or task.get("missing_years") or task.get("must_caveat") or []
            line = f"  - {status}: {question}" if status else f"  - {question}"
            if missing:
                line += " | gaps=" + json.dumps(missing, ensure_ascii=False)
            print(line)


def _memo_item_text(item: dict[str, Any]) -> str:
    parts = []
    for key in (
        "driver_claim",
        "claim",
        "point",
        "insight",
        "why_it_matters",
        "business_implication",
        "readthrough",
        "caveat",
    ):
        value = _clean_display_text(item.get(key) or "")
        if value:
            parts.append(value)
    return " ".join(parts)


def _render_answer_markdown(answer: dict[str, Any]) -> str:
    lines = ["# SEC Agent Answer", ""]
    direct = _clean_display_text(answer.get("direct_answer") or answer.get("summary") or "")
    thesis = _clean_display_text(answer.get("investment_thesis") or "")
    has_memo_fields = bool(
        direct
        or thesis
        or answer.get("what_changed")
        or answer.get("why_it_matters")
        or answer.get("peer_readthrough")
        or answer.get("counterarguments")
        or answer.get("watch_items")
    )
    if direct:
        lines.extend(["## Direct Answer", "", direct, ""])
    if thesis:
        lines.extend(["## Investment Thesis", "", thesis, ""])
    _append_answer_items(lines, "What Changed", answer.get("what_changed") or [], ("claim", "point", "insight"))
    _append_answer_items(lines, "Why It Matters", answer.get("why_it_matters") or [], ("insight", "business_implication", "claim"))
    if not has_memo_fields:
        _append_answer_items(lines, "Decision Drivers", answer.get("decision_drivers") or [], ("driver_claim", "why_it_matters", "caveat"))
        _append_answer_items(lines, "Key Points", answer.get("key_points") or [], ("point", "claim", "insight"))
    _append_answer_items(lines, "Peer Readthrough", answer.get("peer_readthrough") or [], ("peer_or_group", "role", "readthrough", "caveat"))
    _append_answer_items(lines, "Counterarguments And Risks", answer.get("counterarguments") or [], ("claim", "why_it_could_weaken_thesis", "caveat"))
    _append_answer_items(lines, "Watch Items", answer.get("watch_items") or [], ("item", "why_it_matters", "source_to_watch"))
    limitations = [
        _clean_display_text(item)
        for item in (answer.get("source_limitations") or answer.get("limitations") or [])
        if _clean_display_text(item)
    ]
    if limitations:
        lines.extend(["## Source Limits", ""])
        for item in limitations[:8]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _append_answer_items(lines: list[str], title: str, rows: list[Any], text_keys: tuple[str, ...]) -> None:
    items = [item for item in rows if isinstance(item, dict)]
    if not items:
        return
    lines.extend([f"## {title}", ""])
    for index, item in enumerate(items, start=1):
        parts = [_clean_display_text(item.get(key) or "") for key in text_keys]
        text = " ".join(part for part in parts if part)
        if text:
            lines.append(f"{index}. {text}")
        metric_ids = [str(value) for value in (item.get("metric_ids") or item.get("supporting_metric_ids") or []) if str(value or "").strip()]
        evidence_ids = [str(value) for value in (item.get("evidence_ids") or item.get("supporting_evidence_ids") or []) if str(value or "").strip()]
        if metric_ids or evidence_ids:
            lines.append(f"   - Support: {len(metric_ids)} metric refs, {len(evidence_ids)} evidence refs")
    lines.append("")


def _clean_display_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s*\(INTERACTIVE_[^)]+\)", "", text)
    text = re.sub(r"\bINTERACTIVE_\d{8}_\d{6}_[0-9a-f]+::[^\s,;，。)）]+", "", text)
    text = re.sub(r"\s+([,.;，。；])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _print_session_state(harness: SecAgentToolHarness, session_id: str, user_id: str) -> None:
    result = harness.get_session_state(session_id=session_id, user_id=user_id).to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _print_context(context_manager: SecAgentContextManager, tenant_id: str, user_id: str, session_id: str) -> None:
    context_manager.ingest_sessions()
    snapshot = context_manager.build_controller_context(
        tenant_id=tenant_id,
        user_id=user_id,
        session_id=session_id,
        user_message="",
        include_session_candidates=True,
    )
    lossless = snapshot.get("lossless_fields") if isinstance(snapshot.get("lossless_fields"), dict) else {}
    compact = {
        "status": snapshot.get("status"),
        "reason": snapshot.get("reason", ""),
        "identity": snapshot.get("identity") or {},
        "session_id": lossless.get("session_id") or "",
        "active_answer_id": lossless.get("active_answer_id") or "",
        "active_scope": lossless.get("active_scope") or {},
        "artifact_state": lossless.get("artifact_state") or {},
        "resume": lossless.get("resume") or {},
        "user_profile": snapshot.get("user_profile") or {},
        "session_candidates": snapshot.get("session_candidates") or [],
        "compression": snapshot.get("compression") or {},
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


def _print_latest_answer(harness: SecAgentToolHarness, session_id: str, user_id: str, max_chars: int) -> None:
    result = harness.get_session_state(session_id=session_id, user_id=user_id).to_dict()
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    answer_id = str(payload.get("active_answer_id") or "")
    analysis = (payload.get("analyses") or {}).get(answer_id) if isinstance(payload.get("analyses"), dict) else {}
    run_root = Path(str((analysis or {}).get("run_root") or ""))
    if not run_root.exists():
        print("No executable answer is available for the active session.")
        return
    _print_answer_preview(run_root, max_chars)


def _print_start_banner(*, args: argparse.Namespace, state: dict[str, str], session_root: Path, context_root: Path) -> None:
    print("SEC Agent real context session")
    print(f"session_id: {state['session_id']}")
    print(f"tenant_id/user_id: {state['tenant_id']} / {state['user_id']}")
    print(f"controller: {args.controller_backend} model: {args.model}")
    print(
        f"execute_dag: {bool(args.execute)} bge_device: {args.bge_device} "
        f"query_planner: {args.query_planner} synthesis_max_tokens: {args.graph_max_tokens}"
    )
    print(f"session_root: {session_root.resolve()}")
    print(f"context_root: {context_root.resolve()}")
    print(f"turn_log: {state['turn_log']}")


def _print_help() -> None:
    print(
        "Commands: /state | /context | /answer | /help | /exit\n"
        "First normal prompt starts a real SEC-only memo session. Follow-up prompts reuse ContextManager state."
    )


def _resolved_session_id(result: dict[str, Any]) -> str:
    post = result.get("post_context_snapshot") if isinstance(result.get("post_context_snapshot"), dict) else {}
    if post.get("session_id"):
        return str(post["session_id"])
    tool_result = result.get("tool_result") if isinstance(result.get("tool_result"), dict) else {}
    payload = tool_result.get("payload") if isinstance(tool_result.get("payload"), dict) else {}
    return str(_find_key(payload, "session_id") or "")


def _find_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value and value[key]:
            return value[key]
        for item in value.values():
            found = _find_key(item, key)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_key(item, key)
            if found:
                return found
    return ""


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _default_turn_log(session_id: str) -> Path:
    return REPO_ROOT / "reports" / "quality" / f"{session_id}_context_session_turns.jsonl"


def _manual_session_id() -> str:
    return "manual_session_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
