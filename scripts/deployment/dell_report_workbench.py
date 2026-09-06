"""Start the local review deployment with Docker Compose / uvicorn only.

This helper does NOT create threads, invoke graphs, call models, retry runs or
manage checkpoints. Those are exclusively native Agent Server operations.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "up", "serve"])
    parser.add_argument("--settings-directory", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=18165)
    parser.add_argument("--ui-port", type=int, default=8766)
    parser.add_argument("--no-build", action="store_true", help="Use the already built image; no source change implied.")
    parser.add_argument("--enable-research", action="store_true", help="Enable the approved fresh research entry; does not start a model run.")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    settings_root = args.settings_directory.resolve(strict=True)
    os.environ["FIN_REPO_ROOT"] = str(repo)
    os.environ["FINSIGHT_RESEARCH_SESSION_ENABLED"] = "1" if args.enable_research else "0"
    if args.action == "serve":
        os.environ["FINSIGHT_REPORT_SESSION_SETTINGS"] = str(settings_root / "host-settings.json")
        os.environ["FINSIGHT_REPORT_SESSION_API_URL"] = f"http://127.0.0.1:{args.api_port}"
        import uvicorn
        uvicorn.run("apps.workbench.backend.app:app", host="127.0.0.1", port=args.ui_port, access_log=False)
        return
    from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
    env = {**os.environ, **_dotenv()}
    env["FINSIGHT_RESEARCH_SESSION_ENABLED"] = "1" if args.enable_research else "0"
    secret = env["FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"].encode()
    for role, key in (("bootstrap", "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"),
            ("langgraph", "FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD"),
            ("fin-runtime", "FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"),
            ("operator", "FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD")):
        # Stable deployment-scoped DB credentials, not per-question credentials.
        env[key] = hmac.new(secret, f"dell-report-workbench:{role}".encode(), hashlib.sha256).hexdigest()
    settings = json.loads((settings_root / "host-settings.json").read_text(encoding="utf-8"))
    env.update(FINSIGHT_AGENT_SERVER_HOST_PORT=str(args.api_port),
        FINSIGHT_REPORT_SESSION_SETTINGS_HOST_PATH=str(settings_root / "container-settings.json"),
        FINSIGHT_REPORT_SESSION_BUNDLE_HOST_PATH=settings["bundle_path"],
        FINSIGHT_REPORT_SESSION_REPORT_HOST_PATH=settings["report_path"],
        FINSIGHT_REPORT_SESSION_CALLS_HOST_PATH=str(settings_root / "calls"))
    (settings_root / "attachments").mkdir(exist_ok=True)
    env["FINSIGHT_TASK_ATTACHMENTS_HOST_ROOT"] = str(settings_root / "attachments")
    env["FINSIGHT_TASK_VISION_ENABLED"] = "1" if args.enable_research else "0"
    docker = shutil.which("docker") or "Z:/Docker/Docker/resources/bin/docker.exe"
    if not Path(docker).is_file():
        raise FileNotFoundError("Docker CLI not found; add the installed Docker CLI to PATH")
    command = [str(docker), "compose", "--env-file", str(repo / ".env"), "-p", "finsight-dell-report-workbench",
        "-f", "deploy/dell_agent_server/compose.yaml", "-f", "deploy/dell_agent_server/compose.report-session.yaml"]
    subprocess.run([*command, "config", "--quiet"], cwd=repo, env=env, check=True)
    if args.action == "build":
        subprocess.run([*command, "build", "langgraph-api"], cwd=repo, env=env, check=True)
        return  # Build does not stop/recreate a running paid task.
    subprocess.run([*command, "up", "-d", "--no-build" if args.no_build else "--build"], cwd=repo, env=env, check=True)


if __name__ == "__main__":
    main()
