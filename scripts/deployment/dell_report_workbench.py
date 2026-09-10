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


def configured_key(name):
    from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
    value=os.environ.get(name) or _dotenv().get(name)
    if not value and os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as reg:
            try: value=winreg.QueryValueEx(reg,name)[0]
            except FileNotFoundError: pass
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "build", "up", "serve"])
    parser.add_argument("--settings-directory", type=Path, required=True)
    parser.add_argument("--api-port", type=int, default=18165)
    parser.add_argument("--ui-port", type=int, default=8766)
    parser.add_argument("--no-build", action="store_true", help="Use the already built image; no source change implied.")
    parser.add_argument("--enable-research", action="store_true", help="Enable the approved fresh research entry; does not start a model run.")
    parser.add_argument("--fresh-only", action="store_true", help="Run only new research without mounting an archived answer bundle or report.")
    parser.add_argument("--working-memory", action="store_true", help="Enable persistent task working papers in this deployment.")
    parser.add_argument("--semantic-memory", action="store_true", help="Enable authorized Qwen working-paper retrieval; implies working-memory.")
    parser.add_argument('--hermes',action='store_true',help='Use the configured local Hermes native API for opt-in threads.')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    settings_root = args.settings_directory.resolve(strict=True)
    settings = json.loads((settings_root / "host-settings.json").read_text(encoding="utf-8"))
    if args.hermes:
        args.working_memory=True
        connection=json.loads((settings_root/'hermes-connection.json').read_text(encoding='utf-8'))
        os.environ.update(FINSIGHT_HERMES_URL=connection['host_url'],FINSIGHT_HERMES_CONTAINER_URL=connection['container_url'],FINSIGHT_HERMES_TOKEN=connection['token'])
    if args.fresh_only and (settings.get("bundle_path") or settings.get("report_path")):
        raise ValueError("fresh_only_settings_must_not_reference_legacy_answers")
    os.environ["FIN_REPO_ROOT"] = str(repo)
    os.environ["FINSIGHT_RESEARCH_SESSION_ENABLED"] = "1" if args.enable_research else "0"
    if args.working_memory or args.semantic_memory:
        memory_root = settings_root / "working-memory"
        memory_root.mkdir(exist_ok=True)
        os.environ["FINSIGHT_WORKING_MEMORY_PATH"] = str(memory_root / "notes.sqlite")
        os.environ["FINSIGHT_WORKING_MEMORY_SEMANTIC"] = "1" if args.semantic_memory else "0"
    if args.action == "serve":
        if args.semantic_memory:
            from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
            key = configured_key('QWEN_API_KEY')
            if not key:
                raise ValueError("QWEN_API_KEY_required_for_semantic_memory")
            os.environ["QWEN_API_KEY"] = key
        os.environ["FINSIGHT_REPORT_SESSION_SETTINGS"] = str(settings_root / "host-settings.json")
        os.environ["FINSIGHT_REPORT_SESSION_API_URL"] = f"http://127.0.0.1:{args.api_port}"
        import uvicorn
        uvicorn.run("apps.workbench.backend.app:app", host="127.0.0.1", port=args.ui_port, access_log=False)
        return
    from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
    env = {**os.environ, **_dotenv()}
    if args.semantic_memory:
        env['QWEN_API_KEY']=configured_key('QWEN_API_KEY') or ''
        if not env['QWEN_API_KEY']:raise ValueError('QWEN_API_KEY_required_for_semantic_memory')
    env["FINSIGHT_RESEARCH_SESSION_ENABLED"] = "1" if args.enable_research else "0"
    secret = env["FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"].encode()
    for role, key in (("bootstrap", "FINSIGHT_AGENT_SERVER_POSTGRES_PASSWORD"),
            ("langgraph", "FINSIGHT_LANGGRAPH_POSTGRES_PASSWORD"),
            ("fin-runtime", "FINSIGHT_FIN_RUNTIME_POSTGRES_PASSWORD"),
            ("operator", "FINSIGHT_FIN_RUNTIME_OPERATOR_POSTGRES_PASSWORD")):
        # Stable deployment-scoped DB credentials, not per-question credentials.
        env[key] = hmac.new(secret, f"dell-report-workbench:{role}".encode(), hashlib.sha256).hexdigest()
    env.update(FINSIGHT_AGENT_SERVER_HOST_PORT=str(args.api_port),
        FINSIGHT_REPORT_SESSION_SETTINGS_HOST_PATH=str(settings_root / "container-settings.json"),
        FINSIGHT_REPORT_SESSION_CALLS_HOST_PATH=str(settings_root / "calls"))
    if not args.fresh_only:
        env.update(FINSIGHT_REPORT_SESSION_BUNDLE_HOST_PATH=settings["bundle_path"],
            FINSIGHT_REPORT_SESSION_REPORT_HOST_PATH=settings["report_path"])
    (settings_root / "calls").mkdir(exist_ok=True)
    (settings_root / "attachments").mkdir(exist_ok=True)
    env["FINSIGHT_TASK_ATTACHMENTS_HOST_ROOT"] = str(settings_root / "attachments")
    env["FINSIGHT_TASK_VISION_ENABLED"] = "1" if args.enable_research else "0"
    docker = shutil.which("docker") or "Z:/Docker/Docker/resources/bin/docker.exe"
    if not Path(docker).is_file():
        raise FileNotFoundError("Docker CLI not found; add the installed Docker CLI to PATH")
    command = [str(docker), "compose", "--env-file", str(repo / ".env"), "-p", "finsight-dell-report-workbench",
        "-f", "deploy/dell_agent_server/compose.yaml", "-f", "deploy/dell_agent_server/compose.research-session.yaml" if args.fresh_only else "deploy/dell_agent_server/compose.report-session.yaml"]
    if settings.get("conversation_fact_mart"):
        mart = Path(settings["conversation_fact_mart"]).resolve(strict=True)
        if not mart.is_file():
            raise ValueError("conversation_fact_mart_must_be_file")
        container_settings = json.loads((settings_root / "container-settings.json").read_text(encoding="utf-8"))
        if container_settings.get("conversation_fact_mart") != "/run/fin-insight/conversation/financial-facts.sqlite":
            raise ValueError("conversation_fact_mart_container_binding_mismatch")
        env["FINSIGHT_CONVERSATION_FACT_MART_HOST_PATH"] = str(mart)
        command.extend(["-f", "deploy/dell_agent_server/compose.conversation-data.yaml"])
    if args.working_memory or args.semantic_memory:
        env["FINSIGHT_WORKING_MEMORY_HOST_ROOT"] = str(memory_root)
        env["FINSIGHT_WORKING_MEMORY_SEMANTIC"] = "1" if args.semantic_memory else "0"
        command.extend(["-f", "deploy/dell_agent_server/compose.working-memory.yaml"])
    subprocess.run([*command, "config", "--quiet"], cwd=repo, env=env, check=True)
    if args.action == "check":
        return
    if args.action == "build":
        subprocess.run([*command, "build", "langgraph-api"], cwd=repo, env=env, check=True)
        return  # Build does not stop/recreate a running paid task.
    subprocess.run([*command, "up", "-d", "--no-build" if args.no_build else "--build"], cwd=repo, env=env, check=True)


if __name__ == "__main__":
    main()
