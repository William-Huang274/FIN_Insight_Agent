"""Authenticated local MCP sidecar; Docker stays on the trusted host.

This is an operator-to-runtime credential, not end-user authentication. The
agent sees only code, never the credential, Docker socket or mount arguments.
"""
import asyncio
from dataclasses import asdict
import hmac
import os
from uuid import UUID

from mcp import Client
from mcp.server.mcpserver import MCPServer, Context
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings

from .docker_sandbox import DockerPythonSandbox


class LocalRuntimeToken:
    def __init__(self, secret):
        if not secret or len(secret) < 32:
            raise ValueError("sandbox_runtime_credential_required")
        self.secret = secret

    async def verify_token(self, token):
        if not hmac.compare_digest(token, self.secret):
            return None
        return AccessToken(token=token, client_id="finsight-local-runtime", scopes=["sandbox:execute"])


def sandbox_server(sandbox, *, token, port):
    origin = f"http://127.0.0.1:{port}"
    server = MCPServer("FinSight isolated Python", token_verifier=LocalRuntimeToken(token),
        auth=AuthSettings(issuer_url=origin, resource_server_url=origin + "/mcp", required_scopes=["sandbox:execute"]))

    @server.tool(structured_output=True)
    async def run_isolated_python(code: str, ctx: Context) -> dict[str, object]:
        """Run Python in an empty, disposable, offline container. No host files or credentials.
        Output is bounded; this is not the financial source-bound calculator."""
        request = ctx.request_context.request
        thread_id = str(UUID(request.headers.get("x-finsight-thread", "")))
        # Blocking Docker CLI stays outside the ASGI loop. Docker owns the hard
        # timeout and isolation, including when an HTTP caller disconnects.
        return asdict(await asyncio.to_thread(sandbox.execute, code, thread_id=thread_id))

    return server.streamable_http_app(stateless_http=True, json_response=True,
        max_request_body_size=20000, transport_security=TransportSecuritySettings(
            allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}", f"host.docker.internal:{port}"],
            allowed_origins=[]))


def remote_sandbox_tool(*, endpoint, token, thread_id):
    """Host-bound transport; no URL, headers, thread or effects in model schema."""
    from urllib.parse import urlsplit
    from langchain_core.tools import tool, ToolException
    from .conversation_agent import GrantedTool
    parts = urlsplit(endpoint)
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "host.docker.internal"} or parts.path != "/mcp" or parts.query or parts.username:
        raise ValueError("sandbox_local_endpoint_required")
    LocalRuntimeToken(token)
    bound_thread = str(UUID(thread_id))

    @tool
    async def run_isolated_python(code: str) -> dict:
        """Execute Python in an empty disposable /work container. No network,
        host files, credentials or package installation. Print results (bounded).
        Temporary files disappear after execution. Financial arithmetic still
        requires the supplied source-bound calculator, not this tool."""
        import httpx2
        from mcp.client.streamable_http import streamable_http_client
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token,
                "X-Finsight-Thread": bound_thread}, timeout=60, trust_env=False) as http:
            async with Client(streamable_http_client(endpoint, http_client=http), read_timeout_seconds=60) as client:
                result = await client.call_tool("run_isolated_python", {"code": code})
                if result.is_error:
                    raise ToolException("隔离执行未完成；不自动重试。请检查运行记录和操作范围。")
                return result.structured_content

    run_isolated_python.handle_tool_error = True
    return GrantedTool(run_isolated_python, "task_artifact_write",
        "新建的空白临时容器，禁网、无宿主文件挂载；仅返回文本，临时文件退出销毁")


def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18796)
    args = parser.parse_args()
    sandbox = DockerPythonSandbox(image_id=os.environ["FINSIGHT_SANDBOX_IMAGE"])
    app = sandbox_server(sandbox, token=os.environ["FINSIGHT_SANDBOX_TOKEN"], port=args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
