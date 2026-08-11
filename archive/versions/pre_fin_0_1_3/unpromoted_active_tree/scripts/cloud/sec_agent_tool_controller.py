from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import DEFAULT_SESSION_ROOT, SecAgentToolHarness  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek/OpenAI-compatible SEC agent tool controller.")
    parser.add_argument("--message", required=True, help="User turn to route through the controller.")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--user-id", default="")
    parser.add_argument("--tenant-id", default="")
    parser.add_argument("--active-answer-id", default="")
    parser.add_argument("--runtime-context-json", default="{}")
    parser.add_argument("--route-only", action="store_true", help="Select tool calls without dispatching them.")
    parser.add_argument("--execute-tools", action="store_true", help="Allow execute=True tool calls to run the DAG.")
    parser.add_argument("--session-root", default=str(DEFAULT_SESSION_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--controller-backend",
        default=os.environ.get("TOOL_CONTROLLER_BACKEND", "deepseek"),
        choices=("deepseek", "openai_compatible", "qwen_vllm", "heuristic"),
    )
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument(
        "--chat-completions-path",
        default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
    )
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--max-steps", type=int, default=3)
    return parser.parse_args(argv)


def cli_main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runtime_context = _parse_json_object(args.runtime_context_json)
    harness = SecAgentToolHarness(session_root=args.session_root, python=args.python)
    config = ControllerConfig(
        controller_backend=args.controller_backend,
        llm_backend=args.llm_backend,
        base_url=args.base_url,
        chat_completions_path=args.chat_completions_path,
        model=args.model,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        max_steps=args.max_steps,
        execute_tools=bool(args.execute_tools),
    )
    controller = DeepSeekToolController(harness=harness, config=config)
    result = controller.run_turn(
        user_message=args.message,
        session_id=args.session_id,
        user_id=args.user_id,
        tenant_id=args.tenant_id,
        active_answer_id=args.active_answer_id,
        runtime_context=runtime_context,
        route_only=args.route_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _parse_json_object(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("--runtime-context-json must decode to an object")
    return parsed


if __name__ == "__main__":
    raise SystemExit(cli_main())
