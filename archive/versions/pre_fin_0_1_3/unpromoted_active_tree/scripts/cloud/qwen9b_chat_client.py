from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request


SURROGATE_RE = re.compile("[\ud800-\udfff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive CLI for a local vLLM OpenAI-compatible chat server.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen9b")
    parser.add_argument("--system", default="你是一个严谨的中文财务分析助手。回答必须清晰、可核查，不确定时直接说明。")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--enable-thinking", action="store_true", help="Allow Qwen thinking output when the chat template supports it.")
    parser.add_argument("--no-history", action="store_true", help="Send each prompt as an independent single-turn request.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    messages = [{"role": "system", "content": args.system}]
    print("Qwen9B interactive chat. Type /exit to quit, /clear to reset history, /history to show turns.")
    print(f"Endpoint: {args.base_url}/v1/chat/completions  Model: {args.model}")
    while True:
        try:
            prompt = input("\nuser> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        prompt = _clean_text(prompt)
        if prompt in {"/exit", "/quit"}:
            return 0
        if prompt == "/clear":
            messages = [{"role": "system", "content": args.system}]
            print("history cleared")
            continue
        if prompt == "/history":
            for item in messages:
                if item["role"] != "system":
                    print(f"{item['role']}: {item['content'][:500]}")
            continue

        request_messages = [{"role": "system", "content": args.system}, {"role": "user", "content": prompt}]
        if not args.no_history:
            messages.append({"role": "user", "content": prompt})
            request_messages = messages

        payload = {
            "model": args.model,
            "messages": request_messages,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": bool(args.enable_thinking)},
        }
        try:
            content = _post_chat(args.base_url, _clean_json_value(payload))
        except RuntimeError as exc:
            print(f"request failed: {exc}", file=sys.stderr)
            if not args.no_history and messages and messages[-1]["role"] == "user":
                messages.pop()
            continue
        print(f"\nassistant> {content}")
        if not args.no_history:
            messages.append({"role": "assistant", "content": content})


def _post_chat(base_url: str, payload: dict[str, object]) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc)) from exc
    parsed = json.loads(raw)
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices: {raw[:500]}")
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _clean_json_value(value):
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return [_clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {_clean_text(str(key)): _clean_json_value(item) for key, item in value.items()}
    return value


def _clean_text(value: str) -> str:
    return SURROGATE_RE.sub("", str(value))


if __name__ == "__main__":
    raise SystemExit(main())
