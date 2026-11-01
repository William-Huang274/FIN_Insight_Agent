"""Expose existing financial tools over MCP without copying their validators.

LangGraph's maintained ToolNode supplies ToolRuntime/Command handling and its
checkpointer stores financial tool artifacts. This graph has NO model node,
summary policy or research routing. ACP history can compact independently;
calculators and artifact readers retain exact successful observations.
"""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
import json
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import set_config_context
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from mcp.server import Server
from mcp import types

from .on_demand_research import OnDemandResearchState


class HarnessBusinessState(OnDemandResearchState):
    harness_command_id: str
    harness_import_digest: str
    report_draft: dict | None
    report_draft_base_version: int | None


class HarnessBusinessTools:
    def __init__(self, *, grants, checkpointer, thread_id, check, scope=nullcontext):
        self.check, self.scope = check, scope
        self.lock = asyncio.Lock()
        self.stopped = False
        self.config = {'configurable': {'thread_id': thread_id}}
        self.tools = {g.tool.name: g.tool for g in grants}
        self.effects = {g.tool.name: g.effect for g in grants}
        if len(self.tools) != len(grants) or any(g.effect not in {'read', 'working_note_write', 'task_artifact_write'} for g in grants):
            raise ValueError('harness_business_grant_not_admitted')
        graph = StateGraph(HarnessBusinessState)
        graph.add_node('tools', ToolNode(list(self.tools.values())))
        graph.add_edge(START, 'tools')
        graph.add_edge('tools', END)
        self.graph = graph.compile(checkpointer=checkpointer, name='financial_tool_receipts')
        self.server = Server('finsight-business', version='1',
                             on_list_tools=self.list_tools, on_call_tool=self.call_tool)

    def stop(self):
        self.stopped = True

    def access(self):
        if self.stopped:
            raise RuntimeError('harness_execution_stopped')
        self.check()

    async def _checkpoint_call(self, method, *args, **kwargs):
        # MCP is served from inside the Agent Server's graph task. Its ambient
        # replay/checkpoint callbacks belong to that outer run, not this
        # independent, persistent tool ledger. Retain other ContextVars (notably
        # the finance authorization scope), replacing only Runnable context.
        with set_config_context(self.config) as context:
            return await asyncio.create_task(method(*args, **kwargs), context=context)

    async def initialize(self, admitted_state, *, recovering=False):
        """Import genuine old receipts once, never an old generated summary."""
        async with self.lock:
            await asyncio.to_thread(self.access)
            current = await self._checkpoint_call(self.graph.aget_state, self.config)
            if current.next:
                calls = getattr(current.values.get('messages', [])[-1], 'tool_calls', [])
                # Each bridge operation has one call. Only a signed recovery
                # may resume a read; unknown write effects remain blocked.
                if (not recovering or tuple(current.next) != ('tools',) or len(calls) != 1
                        or self.effects.get(calls[0]['name']) != 'read'):
                    raise RuntimeError('harness_business_tool_interrupted_reconcile_before_resume')
                with self.scope():
                    output = await self._checkpoint_call(self.graph.ainvoke, None, self.config)
                await asyncio.to_thread(self.access)
                receipt = next(m for m in reversed(output['messages'])
                    if isinstance(m, ToolMessage) and m.tool_call_id == calls[0]['id'])
                if receipt.status != 'success':
                    raise RuntimeError('harness_business_read_recovery_not_successful')
                return {'kind': 'recovered_read_receipt', 'tool': calls[0]['name'],
                        'receipt_id': receipt.tool_call_id,
                        'readback': 'read_saved_result',
                        'previous_error_retained_in_checkpoint_history': True}
            if not current.values:
                await self._checkpoint_call(self.graph.aupdate_state, self.config, admitted_state, as_node='tools')

    async def state(self):
        await asyncio.to_thread(self.access)
        return (await self._checkpoint_call(self.graph.aget_state, self.config)).values

    async def import_receipts(self, imported):
        """One explicit migration, with stable ids and no state replacement."""
        async with self.lock:
            await asyncio.to_thread(self.access)
            current = await self._checkpoint_call(self.graph.aget_state, self.config)
            prior = current.values.get('harness_import_digest')
            if prior:
                if prior != imported['harness_import_digest']:
                    raise ValueError('harness_legacy_import_identity_changed')
                return
            if current.next:
                raise RuntimeError('harness_business_tool_interrupted_reconcile_before_import')
            known = {m.id: m for m in current.values.get('messages', []) if m.id}
            for message in imported['messages']:
                if message.id in known and message != known[message.id]:
                    raise ValueError('harness_legacy_import_message_conflict')
            await self._checkpoint_call(self.graph.aupdate_state, self.config, imported, as_node='tools')

    async def begin_command(self, command_id, *, recovering=False):
        async with self.lock:
            await asyncio.to_thread(self.access)
            current = (await self._checkpoint_call(self.graph.aget_state, self.config)).values
            if current.get('harness_command_id') != command_id:
                changes = {'harness_command_id': command_id}
                if not recovering:
                    changes['delivery'] = None
                await self._checkpoint_call(self.graph.aupdate_state, self.config, changes, as_node='tools')

    async def list_tools(self, ctx, params):
        await asyncio.to_thread(self.access)
        return types.ListToolsResult(tools=[types.Tool(name=t.name, description=t.description,
            input_schema=t.tool_call_schema.model_json_schema()) for t in self.tools.values()])

    async def call_tool(self, ctx, params):
        # Connection-local MCP ids are not model/provider call ids. Generate a
        # host receipt id and return it for exact readback. Native ACP persists
        # the result; a recovery loads it instead of replaying successful calls.
        result = await self.execute(params.name, params.arguments or {})
        text = result.content if isinstance(result.content, str) else json.dumps(result.content, ensure_ascii=False)
        return types.CallToolResult(content=[types.TextContent(type='text', text=text)],
            is_error=result.status == 'error',
            structured_content={'receipt_id': result.tool_call_id, 'result': text})

    async def execute(self, name, arguments):
        async with self.lock:
            await asyncio.to_thread(self.access)
            if name not in self.tools:
                raise ValueError('harness_tool_not_granted')
            call_id = 'fin-tool-' + str(uuid4())
            try:
                with self.scope():
                    output = await self._checkpoint_call(self.graph.ainvoke, {'messages': [AIMessage(content='', tool_calls=[
                        {'name': name, 'args': arguments, 'id': call_id, 'type': 'tool_call'}])]}, self.config)
                await asyncio.to_thread(self.access)
                return next(m for m in reversed(output['messages'])
                            if isinstance(m, ToolMessage) and m.tool_call_id == call_id)
            except BaseException:
                # A transport/authority/storage failure is not a missing fact.
                # Do not let ACP issue another provider request after it.
                self.stop()
                raise
