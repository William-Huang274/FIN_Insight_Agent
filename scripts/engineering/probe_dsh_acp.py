"""Opt-in full upstream ACP process qualification; loopback inference only.

No user credentials, research records, or paid models are used. The subprocess
MCP fixture deliberately reuses FIN's calculator and versioned working memory.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, calculate_from_sources
from sec_agent.agent_runtime.harness_usage import WireUsage


SOURCE = {"numeric_fact_id": "NUMFACT::fixture_revenue", "result_state": "numeric_fact",
          "numeric_fact_authority": True, "value_decimal": "120", "unit": "USD million",
          "ticker": "SYNTHETIC", "fiscal_period": "FY2025", "period_start": "2025-01-01",
          "period_end": "2025-12-31", "source_observation_ids": ["fixture:1"]}


def mcp_fixture(output: Path):
    memory = WorkingMemory(output / "notes.sqlite", owner="fixture-owner", workspace="fixture-project", actor="lead")
    schemas = {
        "read_source": {"type": "object", "properties": {}},
        "calculate": SourceBoundCalculation.model_json_schema(),
        "save": {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}, "base_version": {"type": "integer"}, "mode": {"type": "string"}}, "required": ["title", "body", "base_version"]},
        "read_note": {"type": "object", "properties": {"note_id": {"type": "string"}}, "required": ["note_id"]},
    }
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method, params = request["method"], request.get("params", {})
        try:
            if method == "initialize":
                result = {"protocolVersion": params["protocolVersion"], "capabilities": {"tools": {}}, "serverInfo": {"name": "fin-fixture", "version": "1"}}
            elif method == "tools/list":
                result = {"tools": [{"name": name, "description": "Synthetic qualification " + name, "inputSchema": schema} for name, schema in schemas.items()]}
            elif method == "tools/call":
                name, args = params["name"], params.get("arguments", {})
                if name == "read_source":
                    value = SOURCE
                elif name == "calculate":
                    value = calculate_from_sources(SourceBoundCalculation.model_validate(args), lambda ref: SOURCE if ref == SOURCE["numeric_fact_id"] else {})
                elif name == "save":
                    value = memory.save(**args)
                elif name == "read_note":
                    value = memory.read(**args)
                else:
                    raise ValueError("Unknown tool")
                with (output / "tool-results.jsonl").open("a", encoding="utf8") as log:
                    log.write(json.dumps({"name": name, "args": args, "result": value}) + "\n")
                result = {"content": [{"type": "text", "text": json.dumps(value)}], "isError": False}
            elif method == "ping":
                result = {}
            else:
                raise ValueError("Unsupported fixture method: " + method)
            response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32602, "message": str(exc)}}
        print(json.dumps(response), flush=True)


def run(binary: str, output: Path, protocol: str = "deepseek", fail_compaction=False):
    output.mkdir(parents=True, exist_ok=False)
    work = output / "workspace"
    work.mkdir()
    state = {"step": 0, "summaries": 0, "hold": False, "fail": False}
    requests, events, accounting = [], [], []
    arrived, release = threading.Event(), threading.Event()

    def tool_rows():
        p = output / "tool-results.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf8").splitlines()] if p.exists() else []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path.startswith("/calls/"):
                assert self.headers.get("Authorization") == "Bearer synthetic-dispatch-only"
                accounting.append({"path": self.path, "body": body})
                (output / "accounting.json").write_text(json.dumps(accounting, indent=2), encoding="utf8")
                data = json.dumps({"status": "reserved" if self.path == "/calls/reserve" else "saved"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            requests.append({"path": self.path, "body": body})
            (output / "requests.json").write_text(json.dumps(requests, indent=2), encoding="utf8")
            if state["fail"]:
                self.send_response(402)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":{"message":"synthetic exhausted balance"}}')
                return
            is_summary = "acting as a compaction engine" in json.dumps(body.get("messages", [])[-1:])
            if state["hold"]:
                arrived.set()
                release.wait(30)
            if is_summary:
                state["summaries"] += 1
                name, args = None, None
                text = "Synthetic checkpoint. Original fixture intent: preserve calculation and saved note, then read it. Note and CALC identifiers are recoverable via tools. No research quality certified."
            else:
                step = state["step"]
                state["step"] += 1
                rows = tool_rows()
                if step == 0:
                    name, args = "read_source", {}
                elif step == 1:
                    name, args = "calculate", {"expression": "revenue / 2", "operands": {"revenue": {"source_id": SOURCE["numeric_fact_id"]}}, "result_unit": "USD million", "rationale": "Synthetic arithmetic"}
                elif step == 2:
                    calc = next(r["result"]["calculation_id"] for r in rows if r["name"] == "calculate")
                    name, args = "save", {"title": "Fixture", "body": calc + " = 60 USD million", "base_version": 0}
                elif step in (4, 7, 9, 11):
                    note = next(r["result"]["note_id"] for r in rows if r["name"] == "save")
                    name, args = "read_note", {"note_id": note}
                elif step == 5:
                    name, args = "save", {"title": "Fixture", "body": "Fixture clarification", "base_version": 1, "mode": "append"}
                else:
                    name, args = None, None
                text = "Fixture step complete."
            if name:
                declared = [t.get("function", t) for t in body["tools"]]
                full_name = next(t["name"] for t in declared if t["name"].endswith(name))
                block = {"type": "tool_use", "id": "call_" + str(len(requests)), "name": full_name, "input": {}}
                delta = {"type": "input_json_delta", "partial_json": json.dumps(args)}
            else:
                block = {"type": "text", "text": ""}
                delta = {"type": "text_delta", "text": text}
            rows = [
                {"type": "message_start", "message": {"id": "msg_"+str(len(requests)), "type": "message", "role": "assistant", "model": body["model"], "content": [], "usage": {"input_tokens": 100, "output_tokens": 0}}},
                {"type": "content_block_start", "index": 0, "content_block": block},
                {"type": "content_block_delta", "index": 0, "delta": delta},
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "tool_use" if name else "end_turn"}, "usage": {"output_tokens": 20}},
                {"type": "message_stop"},
            ]
            for row in rows[1:4]:
                row["index"] = 1
            rows[1:1] = [
                {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "Synthetic reasoning marker."}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "fixture-signature"}},
                {"type": "content_block_stop", "index": 0},
            ]
            data = "".join("event: "+r["type"]+"\ndata: "+json.dumps(r)+"\n\n" for r in rows).encode()
            if protocol == "qwen":
                delta = {"tool_calls": [{"index": 0, "id": block["id"], "type": "function", "function": {"name": full_name, "arguments": json.dumps(args)}}]} if name else {"content": text}
                def chunk(delta, finish=None):
                    return {"id": "chat_"+str(len(requests)), "object": "chat.completion.chunk", "created": 1, "model": body["model"], "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                chunks = [chunk({"role": "assistant", "reasoning_content": "Fixture reasoning marker; not a research conclusion."}), chunk(delta), chunk({}, "tool_calls" if name else "stop"),
                          {"id": "usage_"+str(len(requests)), "object": "chat.completion.chunk", "model": body["model"], "choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, "prompt_tokens_details": {"cached_tokens": 25}, "completion_tokens_details": {"reasoning_tokens": 5}}}]
                data = ("".join("data: "+json.dumps(r)+"\n\n" for r in chunks)+"data: [DONE]\n\n").encode()
            if not state["hold"]:
                meter = WireUsage("qwen_chat" if protocol == "qwen" else "deepseek_messages")
                for event in chunks if protocol == "qwen" else rows:
                    meter.observe(event)
                if protocol == "qwen":
                    meter.done()
                assert meter.reported() is not None
                with (output / "fixture-usage.jsonl").open("a", encoding="utf8") as log:
                    log.write(json.dumps({"purpose": "compaction" if is_summary else "research", **meter.receipt()})+"\n")
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    diagnostic = output / "diagnostic.mjs"
    diagnostic.write_text("import {inspect} from 'node:util'; export function apply(ctx) {ctx.logger.exporter({export(m) {process.stderr.write(inspect(m,{depth:8})+'\\n')}})}", encoding="utf8")
    disabled = ["sdk-app-startup", "sdk-jsonrpc-server", "session-log-deepseek", "plugin-package-inventory-deepseek", "tool-fs", "tool-working-directory", "persistent-bash", "persistent-pwsh", "llm-retry"]
    patch = [{"id": x, "disabled": True} for x in disabled]
    patch += [{"id": "llm-deepseek", "config": {"apiKeyEnv": "FIN_FIXTURE_KEY", "baseURL": f"http://127.0.0.1:{server.server_port}/v1", "models": [{"id": "fixture-model", "contextWindow": 16000}], "maxTokens": 2048, "retryPolicy": {"mode": "normal", "maxRetries": 0}}},
              {"id": "compaction-basic", "config": {"thresholdRatio": .8, "headroomTokens": 2048, "retainTokens": 256, "maxTokens": 2048, "compactionRetries": 0, "maxOverflowRetries": 0}},
              {"id": "system-prompt", "config": {"includeHarnessIdentity": False, "includeRuntimeContext": False, "personaPrefix": "Synthetic FIN runtime qualification."}},
              {"insert": [{"id": "fin-diagnostics", "name": str(diagnostic)},
                          {"id": "fin-dispatch", "name": str(Path(__file__).resolve().parents[2] / "integrations/deepseek-harness/dispatch.mjs"), "config": {"endpoint": f"http://127.0.0.1:{server.server_port}", "tokenEnv": "FIN_DISPATCH_FIXTURE"}},
                          {"id": "fin-acp", "name": "@deepseek-ai/dsh-acp", "config": {"provider": "deepseek-official", "model": "fixture-model"}}]}]
    patch_file = output / "profile.patch.json"
    if protocol == "qwen":
        patch += [{"id": "llm-deepseek", "disabled": True},
                  {"insert": [{"id": "fin-pi-ai", "name": "@deepseek-ai/dsh-llm-pi-ai", "config": {"providers": {"fin-qwen": {
                      "api": "openai-completions", "apiKeyEnv": "FIN_FIXTURE_KEY", "baseURL": f"http://127.0.0.1:{server.server_port}/v1",
                      "reasoning": "high", "retryPolicy": {"mode": "normal", "maxRetries": 0},
                      "compat": {"thinkingFormat": "qwen", "supportsDeveloperRole": False, "supportsReasoningEffort": False, "maxTokensField": "max_tokens"},
                      "models": [{"id": "fixture-model", "contextWindow": 16000, "maxTokens": 2048, "reasoningEfforts": {"off": None, "high": "high"}}]
                  }}}}]}, {"id": "fin-acp", "config": {"provider": "fin-qwen", "model": "fixture-model"}}]
    patch_file.write_text(json.dumps(patch, indent=2), encoding="utf8")
    # Minimal allowlist: never expose real provider keys or default user homes.
    env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"}}
    env.update(DSH_HOME=str(output / "home"), FIN_FIXTURE_KEY="local-fixture-not-a-key", FIN_DISPATCH_FIXTURE="synthetic-dispatch-only", NO_PROXY="127.0.0.1,localhost")
    proc, err, serial = None, None, 0
    inbox = queue.Queue()

    def start():
        nonlocal proc, err, inbox
        inbox = queue.Queue()
        err = (output / f"process-{serial}.log").open("w", encoding="utf8")
        proc = subprocess.Popen([binary, "--profile", "sdk-minimal", "--patch", str(patch_file)], cwd=work, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf8")
        def reader(stream, target):
            for line in stream:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                events.append(value)
                target.put(value)
        threading.Thread(target=reader, args=(proc.stdout, inbox), daemon=True).start()

    def send(method, params, notification=False):
        nonlocal serial
        serial += 1
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            msg["id"] = serial
        proc.stdin.write(json.dumps(msg)+"\n")
        proc.stdin.flush()
        return serial

    def receive(request_id, timeout=45):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            event = inbox.get(timeout=max(.1, deadline-time.monotonic()))
            if "method" in event and "id" in event:
                raise AssertionError("Unexpected client request: " + event["method"])
            if event.get("id") == request_id:
                if "error" in event:
                    raise RuntimeError(event["error"])
                return event["result"]
        raise TimeoutError(request_id)

    def rpc(method, params):
        return receive(send(method, params))

    def stop():
        if proc and proc.poll() is None:
            proc.stdin.close()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=10)
        if err:
            err.close()

    mcp = [{"name": "fin", "command": sys.executable, "args": [str(Path(__file__).resolve()), "--mcp", str(output)], "env": []}]
    init = {"protocolVersion": 1, "clientCapabilities": {}, "clientInfo": {"name": "fin-probe", "version": "1"}}
    try:
        start()
        initialized = rpc("initialize", init)
        session = rpc("session/new", {"cwd": str(work), "mcpServers": mcp})["sessionId"]
        def prompt(text):
            return rpc("session/prompt", {"sessionId": session, "prompt": [{"type": "text", "text": text}]})
        prompt("Read fixture, calculate and save v1.")
        stop()
        start()
        rpc("initialize", init)
        rpc("session/resume", {"sessionId": session, "cwd": str(work), "mcpServers": mcp})
        prompt("Read saved note and append clarification as v2.")
        if fail_compaction:
            prompt("Synthetic disposable context. " * 2500 + " Read saved note.")
            before_failure = len(requests)
            state["fail"] = True
            try:
                prompt("Synthetic disposable context. " * 2500)
            except RuntimeError:
                pass
            else:
                raise AssertionError("compaction failure did not stop execution")
            assert len(requests) == before_failure + 1
            assert "acting as a compaction engine" in json.dumps(requests[-1]["body"]["messages"][-1:])
            assert accounting[-1]["body"]["stopRequired"] is True
            assert [r["result"]["version"] for r in tool_rows() if r["name"] == "save"] == [1, 2]
            result = {"passed": True, "scenario": "failed_compaction", "protocol": protocol,
                      "provider_failure_requests": 1, "fallback_provider_requests": 0, "saved_versions": [1, 2], "paid_calls": 0}
            (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf8")
            print(json.dumps(result))
            return
        for i in range(3):
            prompt(("Synthetic disposable context. " * 2500) + f" Read note v2. Cycle {i}.")
        assert state["summaries"] >= 3, state
        state["hold"] = True
        pending = send("session/prompt", {"sessionId": session, "prompt": [{"type": "text", "text": "Cancellation fixture"}]})
        assert arrived.wait(20)
        send("session/cancel", {"sessionId": session}, notification=True)
        cancelled = receive(pending)
        assert cancelled["stopReason"] == "cancelled", cancelled
        release.set()
        # Cancellation is unresolved: another session in this execution must not
        # reach the provider. Resume admission belongs to the host, not a prompt.
        state["hold"], state["fail"] = False, True
        failure_session = rpc("session/new", {"cwd": str(work), "mcpServers": mcp})["sessionId"]
        before_failure = len(requests)
        try:
            rpc("session/prompt", {"sessionId": failure_session, "prompt": [{"type": "text", "text": "Synthetic failure fixture"}]})
        except RuntimeError:
            pass
        else:
            raise AssertionError("stopped execution admitted another request")
        assert len(requests) == before_failure
        rows = tool_rows()
        assert sum(r["name"] == "read_source" for r in rows) == 1
        assert sum(r["name"] == "calculate" for r in rows) == 1
        assert [r["result"]["version"] for r in rows if r["name"] == "save"] == [1, 2]
        assert all(not any(key in r["body"] for key in ("session_log", "session_logs")) for r in requests)
        if protocol == "qwen":
            assert all(r["body"].get("enable_thinking") is True for r in requests)
            assert any(m.get("reasoning_content") for r in requests for m in r["body"]["messages"] if m["role"] == "assistant")
        else:
            assert any(b.get("signature") == "fixture-signature" for r in requests for m in r["body"]["messages"] for b in m["content"] if b["type"] == "thinking")
        reserves = [r for r in accounting if r["path"] == "/calls/reserve"]
        settled = [r for r in accounting if r["path"] == "/calls/settle"]
        unknown = [r for r in accounting if r["path"] == "/calls/unknown"]
        assert len(reserves) == len(requests) == len(settled) + len(unknown)
        assert len({r["body"]["requestId"] for r in reserves}) == len(requests)
        summary = {"passed": True, "protocol": protocol, "initialize": initialized, "session": session, "provider_requests": len(requests), "compaction_requests_started": state["summaries"], "tool_calls": len(rows), "paid_calls": 0, "cancel": cancelled, "dispatch_reservations": len(reserves), "dispatch_settlements": len(settled), "dispatch_unknown": len(unknown), "post_cancel_provider_requests": len(requests)-before_failure}
        (output / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
        print(json.dumps(summary))
    finally:
        release.set()
        stop()
        server.shutdown()
        (output / "events.json").write_text(json.dumps(events, indent=2), encoding="utf8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mcp", type=Path)
    parser.add_argument("--protocol", choices=["deepseek", "qwen"], default="deepseek")
    parser.add_argument("--fail-compaction", action="store_true")
    args = parser.parse_args()
    if args.mcp:
        mcp_fixture(args.mcp)
    else:
        if not args.binary or not args.output:
            parser.error("--binary and --output are required")
        run(args.binary, args.output.resolve(), args.protocol, args.fail_compaction)
