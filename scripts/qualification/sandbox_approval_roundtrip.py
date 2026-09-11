"""Real HTTP MCP + Docker + native persistent approval qualification, zero LLM calls.

Run as python -m scripts.qualification.sandbox_approval_roundtrip. Only disposable
empty containers are created. Scripted model decisions isolate infrastructure.
"""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import secrets
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
import uvicorn

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.docker_sandbox import DockerPythonSandbox
from sec_agent.agent_runtime.sandbox_mcp import remote_sandbox_tool, sandbox_server


class ScriptedModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = []
    executor = DockerPythonSandbox(image_id=args.image_id, timeout_seconds=5)

    class RecordedSandbox:
        def execute(self, code, *, thread_id):
            result = executor.execute(code, thread_id=thread_id)
            receipts.append({'thread_id': thread_id, **asdict(result)})
            return result

    secret = secrets.token_urlsafe(40)
    app = sandbox_server(RecordedSandbox(), token=secret, port=args.port)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=args.port, log_level='error'))
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError('qualification_http_not_started')
            await asyncio.sleep(.05)
        if not server.started:
            raise RuntimeError('qualification_http_timeout')
        cases = []
        for mode, decision in [('request_standard', 'reject'), ('request_standard', 'approve'),
                               ('approve_for_me', None), ('full_access', None)]:
            tid = str(uuid4())
            grant = remote_sandbox_tool(endpoint=f'http://127.0.0.1:{args.port}/mcp', token=secret, thread_id=tid)
            model = ScriptedModel(responses=[AIMessage(content='', tool_calls=[{'id': 'one',
                'name': 'run_isolated_python', 'args': {'code': 'from pathlib import Path; Path("/work/answer.txt").write_text("42"); print(42)'},
                'type': 'tool_call'}]), AIMessage(content='Operation handled.')])
            config = {'configurable': {'thread_id': tid}}
            before = len(receipts)
            async with AsyncSqliteSaver.from_conn_string(str(args.output/'checkpoints.sqlite')) as saver:
                agent = build_conversation_agent(model=model, grants=[grant], permission_mode=mode, checkpointer=saver)
                state = await agent.ainvoke({'messages': [HumanMessage(content='Calculate in the temporary sandbox.')]}, config)
                assert bool(state.get('__interrupt__')) == (decision is not None)
            if decision is not None:
                assert len(receipts) == before
                # Reopen persistence: approval survives agent/process lifecycle.
                async with AsyncSqliteSaver.from_conn_string(str(args.output/'checkpoints.sqlite')) as saver:
                    agent = build_conversation_agent(model=model, grants=[grant], permission_mode=mode, checkpointer=saver)
                    state = await agent.ainvoke(Command(resume={'decisions': [{'type': decision}]}), config)
            executed = len(receipts)-before
            assert executed == (0 if decision == 'reject' else 1)
            if executed:
                assert receipts[-1]['exit_code'] == 0 and receipts[-1]['output'].strip() == '42'
            cases.append({'mode': mode, 'decision': decision, 'executions': executed, 'passed': True})
        (args.output/'results.json').write_text(json.dumps({'cases': cases, 'receipts': receipts,
            'model_calls': 0, 'scope': 'Real native agent, SQLite reopen, HTTP MCP and Docker; scripted model, not browser acceptance'},
            ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'passed': len(cases), 'docker_executions': len(receipts), 'model_calls': 0}))
    finally:
        server.should_exit = True
        await task


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-id', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--port', type=int, default=18797)
    asyncio.run(run(parser.parse_args()))
