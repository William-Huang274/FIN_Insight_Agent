import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from sec_agent.agent_runtime.docker_sandbox import SandboxResult
from sec_agent.agent_runtime.sandbox_mcp import sandbox_server, remote_sandbox_tool


def test_authenticated_mcp_uses_bound_thread_and_rejects_missing_token():
    calls=[]; thread=str(uuid4()); secret="qualification-credential-not-real-"*2
    def execute(code, *, thread_id):
        calls.append((code,thread_id));return SandboxResult("fake",0,False,"2",True,{"network":"none"})
    app=sandbox_server(SimpleNamespace(execute=execute),token=secret,port=18796)
    async def run():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),base_url="http://127.0.0.1:18796") as http:
                assert (await http.post("/mcp",json={})).status_code==401 and not calls
                http.headers.update({"Authorization":"Bearer "+secret,"X-Finsight-Thread":thread})
                async with Client(streamable_http_client("http://127.0.0.1:18796/mcp",http_client=http)) as client:
                    catalog=await client.list_tools()
                    assert set(catalog.tools[0].input_schema["properties"])=={"code"}
                    result=await client.call_tool("run_isolated_python",{"code":"print(1+1)"})
                    assert not result.is_error and result.structured_content["output"]=="2"
    asyncio.run(run())
    assert calls==[("print(1+1)",thread)]
    grant=remote_sandbox_tool(endpoint="http://127.0.0.1:18796/mcp",token=secret,thread_id=thread)
    assert set(grant.tool.args)=={"code"} and grant.effect=="task_artifact_write"
