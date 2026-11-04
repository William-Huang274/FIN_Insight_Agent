"""Expose existing financial tools over MCP without copying their validators.

LangGraph's maintained ToolNode supplies ToolRuntime/Command handling and its
checkpointer stores financial tool artifacts. This graph has NO model node,
summary policy or research routing. ACP history can compact independently;
calculators and artifact readers retain exact successful observations.
"""
from __future__ import annotations

import ast
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
from .conversation_tools import SAVED_RESULT_TOOLS
from .source_result_view import source_result_view
from .source_references import present_references, expand_references


def model_receipt(result):
    """Presentation only; canonical ToolMessage/artifact remains in the ledger.

    The pinned native MCP client renders text content, not structuredContent.
    Put both the usable receipt key and projected result in that visible lane.
    """
    body = result.content
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            pass
    value = {'receipt_id': result.tool_call_id, 'status': result.status,
             'result': present_references(source_result_view(body)) if result.status == 'success' else body}
    if result.status == 'success' and result.name in SAVED_RESULT_TOOLS:
        value['original_readback'] = {'tool': 'read_saved_result',
            'arguments': {'tool_call_id': result.tool_call_id},
            'format': 'Exact canonical JSON; json_pointer and offsets address the original, not this presentation.'}
    return value


def restored_calculator_feedback(messages):
    """Explain a terminal rejected calculation from its saved call, without executing it."""
    if not messages:
        return None
    receipt = messages[-1]
    if (not isinstance(receipt, ToolMessage) or receipt.status != 'error'
            or receipt.name != 'calculate_research_metric'
            or 'formula_names_must_match_operands_no_unused_source_binding' not in str(receipt.content)):
        return None
    from sec_agent.research_foundation.source_bound_calculator import operand_binding_feedback
    for message in reversed(messages[:-1]):
        for call in getattr(message, 'tool_calls', ()):
            if call.get('id') != receipt.tool_call_id or call.get('name') != receipt.name:
                continue
            request = call['args'].get('request')
            if not isinstance(request, dict) or not isinstance(request.get('operands'), dict):
                return None
            try:
                parsed = ast.parse(request['expression'], mode='eval')
            except (SyntaxError, TypeError, KeyError, ValueError):
                return None
            feedback = operand_binding_feedback(parsed, request['operands'])
            if feedback:
                return {'kind':'saved_calculation_rejection', 'receipt_id':receipt.tool_call_id,
                        'tool':receipt.name, 'status':'error', 'feedback':feedback}
            return None
    return None


def failed_run_receipts(event_file):
    """Only terminal MCP failures recorded by this run identify its failed calls."""
    ids = set()
    if event_file.is_file():
        with event_file.open(encoding='utf8') as stream:
            for line in stream:
                event = json.loads(line).get('update', {})
                if event.get('sessionUpdate') != 'tool_call_update' or event.get('status') != 'failed':
                    continue
                for content in event.get('content') or []:
                    text = content.get('content', {}).get('text', '')
                    try:
                        value = json.loads(text.removeprefix('Error: '))
                    except ValueError:
                        continue
                    if isinstance(value, dict) and value.get('status') == 'error' and isinstance(value.get('receipt_id'), str):
                        ids.add(value['receipt_id'])
    return ids


def restored_batch_feedback(messages, ids):
    from .conversation_tools import calculator_observations, operand_source_feedback
    from sec_agent.research_foundation.source_bound_calculator import (
        OperandSourceError, SourceBoundCalculation, validate_operand_sources)
    calls, failures = {}, []
    for index, message in enumerate(messages):
        for call in getattr(message, 'tool_calls', ()):
            if call.get('id') in ids:
                calls[call['id']] = call
        if (not isinstance(message, ToolMessage) or message.status != 'error'
                or message.tool_call_id not in ids):
            continue
        failure = model_receipt(message)
        call = calls.get(message.tool_call_id, {})
        if call.get('name') == message.name == 'calculate_research_metric':
            args = call.get('args', {}).get('request', {})
            prior = messages[:index]
            try:
                request = SourceBoundCalculation.model_validate(args)
                validate_operand_sources(request, calculator_observations(prior).__getitem__)
            except OperandSourceError as exc:
                # Augment only a reproduced rejection, using the state at that call.
                if exc.code in str(message.content) or (exc.code == 'source_id_not_observed'
                        and exc.operand.source_id in str(message.content)):
                    failure['feedback'] = operand_source_feedback(exc, prior)
            except (ValueError, KeyError):
                pass
            if 'feedback' not in failure:
                formula = restored_calculator_feedback(messages[:index+1])
                if formula:
                    failure['feedback'] = formula['feedback']
        failures.append(failure)
    if failures:
        return {'kind':'saved_tool_rejections', 'failures':failures}


class HarnessBusinessState(OnDemandResearchState):
    harness_command_id: str
    harness_import_digest: str
    report_draft: dict | None
    report_draft_base_version: int | None


class HarnessBusinessTools:
    def __init__(self, *, grants, checkpointer, thread_id, check, scope=nullcontext, stop_on_tool_error=False):
        self.check, self.scope = check, scope
        self.lock = asyncio.Lock()
        self.stopped = False
        self.stop_on_tool_error = stop_on_tool_error
        self.failed_receipt = None
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

    def model_access(self):
        # An MCP client can time out before the server's tool task ends. The
        # upstream loop may then request another model turn. Do not turn an
        # unresolved tool effect into a paid opportunity to guess what happened.
        if self.failed_receipt:
            raise RuntimeError(f'harness_tool_failed_before_model_dispatch:{self.failed_receipt}')
        if self.lock.locked():
            self.stop()
            raise RuntimeError('harness_tool_effect_unresolved_before_model_dispatch')
        self.access()

    async def _checkpoint_call(self, method, *args, **kwargs):
        # MCP is served from inside the Agent Server's graph task. Its ambient
        # replay/checkpoint callbacks belong to that outer run, not this
        # independent, persistent tool ledger. Retain other ContextVars (notably
        # the finance authorization scope), replacing only Runnable context.
        with set_config_context(self.config) as context:
            return await asyncio.create_task(method(*args, **kwargs), context=context)

    async def initialize(self, admitted_state, *, recovering=False, failed_receipt_ids=None):
        """Import genuine old receipts once, never an old generated summary."""
        async with self.lock:
            await asyncio.to_thread(self.access)
            current = await self._checkpoint_call(self.graph.aget_state, self.config)
            feedback = (restored_batch_feedback(current.values.get('messages', []), failed_receipt_ids)
                        if recovering and failed_receipt_ids else None)
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
                return {'kind': 'recovered_read_receipt' if receipt.status == 'success' else 'recovered_read_feedback',
                        'status': receipt.status, 'feedback': model_receipt(receipt) if receipt.status == 'error' else None,
                        'tool': calls[0]['name'],
                        'receipt_id': receipt.tool_call_id,
                        'readback': 'read_saved_result',
                        'previous_error_retained_in_checkpoint_history': True,
                        **({'prior_run_feedback':feedback} if feedback else {})}
            if recovering and current.values:
                return feedback or restored_calculator_feedback(current.values.get('messages', []))
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
        try:
            result = await self.execute(params.name, params.arguments or {})
            if self.stop_on_tool_error and result.status == 'error':
                self.failed_receipt = self.failed_receipt or result.tool_call_id
            view = model_receipt(result)
            text = json.dumps(view, ensure_ascii=False, separators=(',', ':'))
            return types.CallToolResult(content=[types.TextContent(type='text', text=text)],
                is_error=result.status == 'error', structured_content=view)
        except BaseException:
            self.stop()
            raise

    async def execute(self, name, arguments):
        async with self.lock:
            await asyncio.to_thread(self.access)
            if name not in self.tools:
                raise ValueError('harness_tool_not_granted')
            call_id = 'fin-tool-' + str(uuid4())
            state = (await self._checkpoint_call(self.graph.aget_state, self.config)).values
            original_arguments = arguments
            try:
                arguments = expand_references(arguments, state)
            except ValueError as exc:
                receipt = ToolMessage(name=name, tool_call_id=call_id, status='error', content=str(exc))
                await self._checkpoint_call(self.graph.aupdate_state, self.config, {'messages': [
                    AIMessage(content='', tool_calls=[{'name': name, 'args': arguments, 'id': call_id, 'type': 'tool_call'}]), receipt]}, as_node='tools')
                return receipt
            try:
                with self.scope():
                    output = await self._checkpoint_call(self.graph.ainvoke, {'messages': [AIMessage(content='',
                        additional_kwargs={'original_tool_arguments': original_arguments} if original_arguments != arguments else {}, tool_calls=[
                        {'name': name, 'args': arguments, 'id': call_id, 'type': 'tool_call'}])]}, self.config)
                await asyncio.to_thread(self.access)
                return next(m for m in reversed(output['messages'])
                            if isinstance(m, ToolMessage) and m.tool_call_id == call_id)
            except BaseException:
                # A transport/authority/storage failure is not a missing fact.
                # Do not let ACP issue another provider request after it.
                self.stop()
                raise
