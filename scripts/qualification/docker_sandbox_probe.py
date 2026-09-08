"""Opt-in real Docker isolation qualification, with no model/network calls."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from uuid import uuid4

from sec_agent.agent_runtime.docker_sandbox import DockerPythonSandbox


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sandbox = DockerPythonSandbox(image_id=args.image_id, timeout_seconds=3)
    code = '''import os, pathlib, socket, json
results = {"uid": os.getuid(), "temporary_write": False, "root_write_blocked": False, "network_blocked": False,
           "docker_socket_absent": not pathlib.Path("/var/run/docker.sock").exists(),
           "project_mount_absent": not pathlib.Path("/run/fin-insight").exists(),
           "credentials_absent": all(k not in os.environ for k in ("QWEN_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"))}
pathlib.Path("/work/task.txt").write_text("task-only")
results["temporary_write"] = pathlib.Path("/work/task.txt").read_text() == "task-only"
try: pathlib.Path("/etc/finsight-test").write_text("unauthorized")
except OSError: results["root_write_blocked"] = True
try: socket.create_connection(("1.1.1.1", 443), timeout=0.5).close()
except OSError: results["network_blocked"] = True
print(json.dumps(results))
assert results["uid"] == 65534 and all(v for k, v in results.items() if k != "uid")
'''
    try:
        first = sandbox.execute(code, thread_id=str(uuid4()))
    except Exception as exc:
        (args.output / "failure.json").write_text(json.dumps({"error": str(exc)}, ensure_ascii=False), encoding="utf-8")
        raise
    second = sandbox.execute('from pathlib import Path; assert not Path("/work/task.txt").exists(); print("new thread workspace empty")', thread_id=str(uuid4()))
    timeout = sandbox.execute("while True: pass", thread_id=str(uuid4()))
    receipts = {"first": asdict(first), "second_thread": asdict(second), "timeout": asdict(timeout)}
    (args.output / "result.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
    assert first.exit_code == second.exit_code == 0 and timeout.timed_out
    assert all(not r["isolation"]["bind_mounts"] for r in receipts.values())
    print(json.dumps({"status": "passed", "receipts": str(args.output / "result.json"), "model_calls": 0}))


if __name__ == "__main__":
    main()
