"""Operator entry point for the existing local Docker/MCP sandbox.

Default plan and check are read-only. Configure and serve are explicit operator
actions; this module does not start background jobs, restart other services,
change firewall/approval rules, pull images, or call a model.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
from uuid import uuid4

from sec_agent.agent_runtime.docker_sandbox import DockerPythonSandbox
from sec_agent.agent_runtime.sandbox_mcp import LocalRuntimeToken


FILES = {"host-settings.json": "127.0.0.1", "container-settings.json": "host.docker.internal"}
PORT = 18796


def settings_pair(directory):
    directory = directory.resolve(strict=True)
    result = {}
    for name in FILES:
        path = directory / name
        if path.is_symlink() or path.resolve().parent != directory:
            raise ValueError("settings_must_be_regular_files_in_selected_directory")
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("settings_must_be_objects")
        result[name] = (raw, data)
    return result


def connection(pair, *, allow_missing=False):
    tokens = []
    for name, host in FILES.items():
        data = pair[name][1]
        url, token = data.get("conversation_sandbox_url"), data.get("conversation_sandbox_token")
        if allow_missing and not url and not token:
            continue
        if url != f"http://{host}:{PORT}/mcp":
            raise ValueError("existing_sandbox_endpoint_conflict")
        LocalRuntimeToken(token)
        tokens.append(token)
    if tokens and (len(tokens) != 2 or tokens[0] != tokens[1]):
        raise ValueError("sandbox_settings_pair_inconsistent")
    if not tokens and not allow_missing:
        raise ValueError("sandbox_not_configured")
    return tokens[0] if tokens else None


def atomic_write(path, content):
    fd, temp = tempfile.mkstemp(prefix=".sandbox-config-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)  # Only our exact temporary file.


def configure(directory):
    pair = settings_pair(directory)
    existing = connection(pair, allow_missing=True)
    if existing:
        return {"configured": True, "changed": False}
    token = secrets.token_urlsafe(40)
    backup = directory / "sandbox-config-backups" / uuid4().hex
    backup.mkdir(parents=True, exist_ok=False)
    replacements = {}
    for name, host in FILES.items():
        raw, data = pair[name]
        (backup / name).write_bytes(raw)
        data.update(conversation_sandbox_url=f"http://{host}:{PORT}/mcp", conversation_sandbox_token=token)
        replacements[name] = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    # Detect intervening edits before replacing anything. Stop other config
    # writers while installing; this is a local operator action, not a lock service.
    if any((directory / name).read_bytes() != raw for name, (raw, _) in pair.items()):
        raise ValueError("settings_changed_during_configuration")
    written = []
    try:
        for name, content in replacements.items():
            atomic_write(directory / name, content)
            written.append(name)
    except Exception:
        for name in written:
            if (directory / name).read_bytes() == replacements[name]:
                atomic_write(directory / name, pair[name][0])
        raise
    (backup / "manifest.json").write_text(json.dumps({name: {
        "original_sha256": hashlib.sha256(pair[name][0]).hexdigest(),
        "installed_sha256": hashlib.sha256(content).hexdigest(),
    } for name, content in replacements.items()}, indent=2), encoding="utf-8")
    return {"configured": True, "changed": True, "backup": str(backup)}


def preflight(directory, image):
    DockerPythonSandbox(image_id=image)  # Validate the pinned-image contract.
    pair = settings_pair(directory)
    token = connection(pair, allow_missing=True)
    docker = shutil.which("docker")
    if not docker:
        raise ValueError("docker_cli_not_on_path")
    result = subprocess.run([docker, "image", "inspect", image, "--format", "{{.Id}}"],
                            capture_output=True, text=True, timeout=20, check=False)
    if result.returncode or result.stdout.strip() != image:
        raise ValueError("docker_unavailable_or_pinned_image_missing")
    with socket.socket() as probe:
        probe.settimeout(1)
        listening = probe.connect_ex(("127.0.0.1", PORT)) == 0
    return {"configured": bool(token), "port_listening": listening, "image_id": image,
            "changes": [] if token else [{"file": name, "endpoint": f"http://{host}:{PORT}/mcp",
            "credential": "new shared service credential; never printed"} for name, host in FILES.items()]}


async def check(directory):
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client
    token = connection(settings_pair(directory))
    endpoint = f"http://127.0.0.1:{PORT}/mcp"
    async with httpx2.AsyncClient(timeout=8, trust_env=False) as http:
        for headers in ({}, {"Authorization": "Bearer deliberately-invalid"}):
            response = await http.post(endpoint, json={}, headers=headers)
            if response.status_code != 401:
                raise ValueError("unauthorized_access_not_rejected")
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token,
            "X-Finsight-Thread": str(uuid4())}, timeout=8, trust_env=False) as http:
        async with Client(streamable_http_client(endpoint, http_client=http), read_timeout_seconds=8) as client:
            catalog = await client.list_tools()
            if {tool.name for tool in catalog.tools} != {"run_isolated_python"}:
                raise ValueError("unexpected_sandbox_tool_catalog")
    return {"authentication": "passed", "tool_catalog": "passed", "executions": 0,
            "boundary": "Host MCP only; container connectivity and product approval still require verification"}


def check_container(directory, container):
    """Read the runtime's mounted settings and list MCP tools from that runtime.

    Only a credential digest crosses stdout; the credential stays in the runtime.
    No sandbox tool is invoked and no files/process services are changed.
    """
    code = '''
import asyncio, hashlib, json, os
from pathlib import Path
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
async def main():
    data=json.loads(Path(os.environ['FINSIGHT_REPORT_SESSION_SETTINGS']).read_text(encoding='utf-8'))
    token=data['conversation_sandbox_token']
    endpoint=data['conversation_sandbox_url']
    if endpoint != 'http://host.docker.internal:18796/mcp':
        raise ValueError('unexpected_endpoint')
    async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+token},timeout=8,trust_env=False) as http:
        async with Client(streamable_http_client(endpoint,http_client=http),read_timeout_seconds=8) as client:
            catalog=await client.list_tools()
            assert {tool.name for tool in catalog.tools} == {'run_isolated_python'}
    print(json.dumps({'credential_sha256':hashlib.sha256(token.encode()).hexdigest(),'catalog':'passed'}))
asyncio.run(main())
'''
    result = subprocess.run([shutil.which("docker"), "exec", "-i", container, "python", "-"],
        input=code, text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("container_mcp_check_failed_verify_mounted_settings_and_host_connectivity")
    receipt = json.loads(result.stdout)
    token = connection(settings_pair(directory))
    if receipt["credential_sha256"] != hashlib.sha256(token.encode()).hexdigest():
        raise ValueError("container_has_different_configuration")
    return {"container_mcp": "passed", "mounted_credential_matches": True, "executions": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "configure", "serve", "check"], nargs="?", default="plan")
    parser.add_argument("--settings-dir", required=True, type=Path)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--container", help="For check only: existing native runtime container name/ID")
    args = parser.parse_args()
    status = preflight(args.settings_dir, args.image_id)
    if args.action == "configure":
        if status["port_listening"]:
            raise ValueError("stop_existing_service_before_configuration")
        status = configure(args.settings_dir)
    elif args.action == "serve":
        if status["port_listening"]:
            raise ValueError("port_already_in_use_no_process_was_stopped")
        import uvicorn
        from sec_agent.agent_runtime.sandbox_mcp import sandbox_server
        token = connection(settings_pair(args.settings_dir))
        app = sandbox_server(DockerPythonSandbox(image_id=args.image_id), token=token, port=PORT)
        print("Sandbox on 127.0.0.1:18796; keep this terminal open. Ctrl+C stops this service.", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=PORT, access_log=False)
        return
    elif args.action == "check":
        status = asyncio.run(check(args.settings_dir))
        if args.container:
            status.update(check_container(args.settings_dir, args.container))
            status["boundary"] = "Host/container MCP verified; product approval and real isolated execution still require verification"
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
