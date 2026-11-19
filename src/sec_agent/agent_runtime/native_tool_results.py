"""Persist completed tool results before the enclosing parallel task exits.

LangGraph owns the receipts, namespace and retry boundary. No secondary tool
cache, automatic retry, audit-log reconstruction or cross-task reuse is added.
Outer grant/access middleware still runs when a native receipt is reused.
"""
from contextvars import ContextVar
from hashlib import sha256
import json

from langchain.agents.middleware import AgentMiddleware
from langgraph.func import task


tool_result_reused = ContextVar('native_tool_result_reused', default=False)


class NativeToolResultMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        identity = sha256(json.dumps(request.tool_call, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        executed = False

        @task(name='execute_admitted_tool', retry_policy=())
        def execute_admitted_tool(proposal):
            nonlocal executed
            executed = True
            return {'identity': identity, 'result': handler(request)}

        saved = execute_admitted_tool(request.tool_call).result()
        if saved['identity'] != identity:
            raise ValueError('native_tool_receipt_proposal_mismatch')
        tool_result_reused.set(not executed)
        return saved['result']

    async def awrap_tool_call(self, request, handler):
        identity = sha256(json.dumps(request.tool_call, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        executed = False

        @task(name='execute_admitted_tool', retry_policy=())
        async def execute_admitted_tool(proposal):
            nonlocal executed
            executed = True
            return {'identity': identity, 'result': await handler(request)}

        saved = await execute_admitted_tool(request.tool_call)
        if saved['identity'] != identity:
            raise ValueError('native_tool_receipt_proposal_mismatch')
        tool_result_reused.set(not executed)
        return saved['result']
