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
from copy import deepcopy
import json
from uuid import uuid4

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables.config import set_config_context
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langsmith import tracing_context
from mcp.server import Server
from mcp import types

from .on_demand_research import OnDemandResearchState
from .conversation_tools import SAVED_RESULT_TOOLS, READABLE_RESULT_TOOLS
from .source_result_view import source_result_view
from .source_references import present_references, expand_references, reference_selection_feedback


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
    if result.status == 'success' and isinstance(body, dict) and body.get('quantitative_change_check'):
        from .research_feedback_view import quantitative_feedback_view
        value['result']['quantitative_change_check'] = quantitative_feedback_view(
            body['quantitative_change_check'], result.tool_call_id)
    if isinstance(value['result'], dict) and 'disposition_scope' in value['result']:
        scope = value['result'].pop('disposition_scope')
        value['result']['scope_binding'] = 'section_and_shared_wording' if scope else 'whole_report'
    if result.status == 'error':
        value['execution_stop'] = not actionable_tool_feedback(result)
        value['feedback_kind'] = 'correctable_selection' if not value['execution_stop'] else 'execution_failure'
    if result.status == 'success' and result.name in READABLE_RESULT_TOOLS:
        value['original_readback'] = {'tool': 'read_saved_result',
            'arguments': {'tool_call_id': result.tool_call_id},
            'format': 'Exact canonical JSON; json_pointer and offsets address the original, not this presentation.'}
    return value


def actionable_tool_feedback(result):
    """A rejected selection can be corrected; execution/authority faults cannot."""
    if result.status != 'error' or (getattr(result,'artifact',None) or {}).get('execution_stop'):
        return False
    text = str(result.content)
    try:
        value = json.loads(text)
    except ValueError:
        value = None
    if (result.name == 'calculate_research_metric' and isinstance(value, dict)
            and value.get('feedback_kind') == 'calculation_operand_validation'
            and value.get('code') in {'unsourced_operand_requires_literal_and_explicit_assumption',
                                     'observation_field_requires_observed_source',
                                     'source_operand_cannot_be_relabelled_assumption'}
            and value.get('calculation_executed') is False
            and value.get('request_modified') is False
            and isinstance(value.get('constraints'), dict)):
        return True
    if (result.name == 'read_market_prices' and isinstance(value, dict)
            and value.get('feedback_kind') == 'market_request_validation'
            and value.get('code') == 'invalid_market_window'
            and value.get('request_dispatched') is False
            and value.get('request_modified') is False
            and isinstance(value.get('constraints'), dict)):
        return True
    return (isinstance(value,dict) and any(k in value for k in ('readback','read_options','quote_comparison'))
            or text.startswith(('invalid_source_read_window:', 'source_not_observed_read_current_source_catalog'))
            or (text.startswith('Error invoking tool ') and text.endswith('Please fix the error and try again.')))


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
    """Recover this run's business rejections, even if MCP delivered them normally."""
    ids = set()
    if event_file.is_file():
        with event_file.open(encoding='utf8') as stream:
            for line in stream:
                event = json.loads(line).get('update', {})
                if (event.get('sessionUpdate') != 'tool_call_update'
                        or event.get('status') not in ('failed', 'completed')):
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


def completed_transport_reads(messages, event_file):
    """Reconcile a timed-out native read with its uniquely committed receipt.

    Use a successful receipt from this exact native run as a lower boundary.
    Never match the same arguments against arbitrary earlier research history,
    never replay a call, and never promote an uncommitted or ambiguous result.
    """
    if not event_file.is_file():
        return []
    positions = {m.tool_call_id: i for i, m in enumerate(messages) if isinstance(m, ToolMessage)}
    anchor, pending, recovered = None, {}, []
    delivered = set()
    for line in event_file.read_text(encoding='utf8').splitlines():
        update = json.loads(line).get('update', {})
        kind, identity = update.get('sessionUpdate'), update.get('toolCallId')
        if kind == 'tool_call':
            pending[identity] = (update.get('title', '').removeprefix('mcp__financial__'),
                                 update.get('rawInput'), anchor)
        elif kind == 'tool_call_update':
            for item in update.get('content') or []:
                try:
                    receipt = json.loads(item.get('content', {}).get('text', ''))
                except ValueError:
                    continue
                if isinstance(receipt, dict) and receipt.get('status') == 'success' and receipt.get('receipt_id') in positions:
                    anchor = positions[receipt['receipt_id']]
                if isinstance(receipt, dict) and receipt.get('receipt_id') in positions:
                    delivered.add(identity)
    for identity, (name, arguments, boundary) in pending.items():
        if identity in delivered or boundary is None or name not in SAVED_RESULT_TOOLS:
            continue
        matches = []
        for i, message in enumerate(messages[boundary + 1:], boundary + 1):
            for call in getattr(message, 'tool_calls', ()):
                original = message.additional_kwargs.get('original_tool_arguments', call.get('args'))
                if call.get('name') == name and original == arguments:
                    matches.extend(m for m in messages[i + 1:] if isinstance(m, ToolMessage)
                        and m.tool_call_id == call['id'] and m.name == name and m.status == 'success')
        if len(matches) == 1:
            recovered.append({'native_tool_call_id': identity, 'tool': name,
                'submitted_arguments': arguments, 'status': 'completed_before_transport_recovery',
                'receipt': model_receipt(matches[0]), 'original_transport_error_retained': True,
                'notice': 'Committed tool receipt was not delivered before interruption; reuse it without executing again.'})
    return recovered


def restored_batch_feedback(messages, ids):
    from .conversation_tools import calculator_observations, operand_source_feedback
    from sec_agent.research_foundation.source_bound_calculator import (
        OperandSourceError, SourceBoundCalculation, calculate_from_sources)
    calls, failures, revalidated = {}, [], []
    for index, message in enumerate(messages):
        for call in getattr(message, 'tool_calls', ()):
            if call.get('id') in ids:
                calls[call['id']] = call
        if (not isinstance(message, ToolMessage) or message.status != 'error'
                or message.tool_call_id not in ids):
            continue
        failure = model_receipt(message)
        call = calls.get(message.tool_call_id, {})
        if call.get('name') == message.name == 'read_public_source':
            from .conversation_web import public_web_request_feedback
            correction = public_web_request_feedback(call.get('args', {}))
            if correction and ('search_backend_and_language_require_global_search' in str(message.content)
                               or 'read accepts document_id' in str(message.content)):
                failure['current_selection_feedback'] = correction
        if call.get('name') == message.name == 'read_current_report' and str(message.content) == 'invalid_read_window':
            # Historical receipt stays unchanged. Today's schema gives an exact
            # correction path; the author still chooses the field and page.
            failure['read_options'] = {'tool':'read_current_report',
                'submitted_arguments':deepcopy(call.get('args',{})),
                'offset':{'minimum':0},'max_characters':{'minimum':1,'maximum':12000},
                'continuation':'Use next_offset from each successful page.'}
        if call.get('name') == message.name == 'read_saved_result':
            target_id = call.get('args', {}).get('tool_call_id')
            if any(isinstance(row, ToolMessage) and row.tool_call_id == target_id
                   and (row.status == 'error' or (row.name in READABLE_RESULT_TOOLS and row.status == 'success'))
                   for row in messages[:index]):
                failure['available_original'] = {'tool':'read_saved_result', 'arguments':{'tool_call_id':target_id}}
        if call.get('name') == message.name == 'calculate_research_metric':
            args = call.get('args', {}).get('request', {})
            prior = messages[:index]
            try:
                request = SourceBoundCalculation.model_validate(args)
                checked = calculate_from_sources(request, calculator_observations(prior).__getitem__)
            except OperandSourceError as exc:
                # Augment only a reproduced rejection, using the state at that call.
                if exc.code in str(message.content) or (exc.code == 'source_id_not_observed'
                        and exc.operand.source_id in str(message.content)):
                    failure['feedback'] = operand_source_feedback(exc, prior)
            except (ValueError, KeyError):
                pass
            else:
                # This is a new deterministic check, not a rewritten historical
                # receipt or a saved calculation. The exact original proposal
                # can now be executed by the normal tool without guessing edits.
                revalidated.append({'historical_failure': failure,
                    'current_status': 'original_proposal_revalidated_not_saved',
                    'check': checked,
                    'retry': {'tool': message.name, 'arguments': deepcopy(call['args'])}})
                continue
            if 'feedback' not in failure:
                formula = restored_calculator_feedback(messages[:index+1])
                if formula:
                    failure['feedback'] = formula['feedback']
        failures.append(failure)
    if revalidated:
        return {'kind': 'rechecked_tool_rejections', 'revalidated': revalidated, 'failures': failures}
    if failures:
        return {'kind':'saved_tool_rejections', 'failures':failures}


class HarnessBusinessState(OnDemandResearchState):
    harness_command_id: str
    active_report_review: dict | None
    harness_import_digest: str
    report_draft: dict | None
    report_draft_base_version: int | None


class HarnessBusinessTools:
    def __init__(self, *, grants, checkpointer, thread_id, check, scope=nullcontext, stop_on_tool_error=False, note_versions=None):
        self.check, self.scope = check, scope
        self.lock = asyncio.Lock()
        self.stopped = False
        self.stop_on_tool_error = stop_on_tool_error
        self.note_versions = note_versions
        self.failed_receipt = None
        self.config = {'configurable': {'thread_id': thread_id}, 'callbacks': []}
        self.tools = {g.tool.name: g.tool for g in grants}
        self.effects = {g.tool.name: g.effect for g in grants}
        self.checkpoint_only = {g.tool.name for g in grants
            if g.effect == 'task_artifact_write' and g.recovery_semantics == 'checkpoint_only'}
        if len(self.tools) != len(grants) or any(g.effect not in {'read', 'working_note_write', 'task_artifact_write', 'delegated_task_control'} for g in grants):
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
        # This inner graph is a durable receipt ledger, not another research
        # execution. Tracing each turn's entire accumulated state retains large
        # duplicate inputs/outputs under the long-lived outer run. The native
        # session events, paid-call ledger and ToolMessages remain the audit.
        # Clear both Runnable callbacks and ambient LangSmith parentage only
        # inside this call; authorization and the outer run's tracing survive.
        with tracing_context(enabled=False, parent=False):
            with set_config_context(self.config) as context:
                return await asyncio.create_task(method(*args, **kwargs), context=context)

    async def initialize(self, admitted_state, *, recovering=False, failed_receipt_ids=None):
        """Import genuine old receipts once, never an old generated summary."""
        async with self.lock:
            await asyncio.to_thread(self.access)
            current = await self._checkpoint_call(self.graph.aget_state, self.config)
            feedback = (restored_batch_feedback(current.values.get('messages', []), failed_receipt_ids)
                        if recovering and failed_receipt_ids else None)
            if feedback:
                for failure in feedback.get('failures', []):
                    correction = reference_selection_feedback(failure.get('result', ''), self.tools)
                    if correction:
                        # Preserve the historical failure; expose today's repair
                        # path without executing or rewriting the old proposal.
                        failure['current_selection_feedback'] = correction
            if current.next:
                calls = getattr(current.values.get('messages', [])[-1], 'tool_calls', [])
                # Reads and host-declared pure checkpoint updates can resume the
                # exact pending graph operation. LangGraph owns atomic receipt /
                # artifact persistence; external write effects remain blocked.
                if (not recovering or tuple(current.next) != ('tools',) or len(calls) != 1
                        or (self.effects.get(calls[0]['name']) != 'read'
                            and calls[0]['name'] not in self.checkpoint_only)):
                    raise RuntimeError('harness_business_tool_interrupted_reconcile_before_resume')
                with self.scope():
                    output = await self._checkpoint_call(self.graph.ainvoke, None, self.config)
                await asyncio.to_thread(self.access)
                receipt = next(m for m in reversed(output['messages'])
                    if isinstance(m, ToolMessage) and m.tool_call_id == calls[0]['id'])
                kind = 'artifact' if calls[0]['name'] in self.checkpoint_only else 'read'
                return {'kind': f'recovered_{kind}_receipt' if receipt.status == 'success' else f'recovered_{kind}_feedback',
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
            if imported.get('report') and current.values.get('report'):
                if any(current.values.get(k) != imported[k] for k in ('report','report_version')):
                    raise ValueError('harness_import_report_conflict')
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
                    changes['active_report_review'] = None
                await self._checkpoint_call(self.graph.aupdate_state, self.config, changes, as_node='tools')

    async def set_report_review(self, *, report_digest, reviewer, opinion):
        """Bind the actual host-accepted review, without fabricating a tool call."""
        async with self.lock:
            await asyncio.to_thread(self.access)
            current=(await self._checkpoint_call(self.graph.aget_state,self.config)).values
            value={'reviewed_report_digest':report_digest,'reviewer':reviewer,'opinion':opinion}
            prior=current.get('active_report_review') or {}
            if all(prior.get(k)==v for k,v in value.items()):
                return  # recovery keeps its original ordering relative to later consultations
            value['message_boundary']=len(current.get('messages',[]))
            await self._checkpoint_call(self.graph.aupdate_state,self.config,
                {'active_report_review':value},as_node='tools')

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
            if self.stop_on_tool_error and result.status == 'error' and not actionable_tool_feedback(result):
                self.failed_receipt = self.failed_receipt or result.tool_call_id
            if params.name == 'WriteWorkingNote' and self.note_versions:
                saved = json.loads(result.content)
                if isinstance(saved, dict) and saved.get('saved') and not saved.get('unchanged'):
                    from .conversation_tools import calculator_observations
                    from .quantitative_prose import audit_changes
                    args = params.arguments or {}
                    body = args.get('body', '')
                    if isinstance(body, str) and body.strip():
                        base_version = saved['version'] - 1
                        previous = ''
                        if base_version:
                            prior = await asyncio.to_thread(self.note_versions, saved['note_id'], base_version)
                            previous = prior.get('markdown', '')
                        messages = (await self.state()).get('messages', [])
                        report = audit_changes(previous if args.get('mode') != 'append' else '',
                            body, calculator_observations(messages), context=previous if args.get('mode') == 'append' else '')
                        if report['findings'] or report['linked_ratio_bases'] or report['cited_claim_context']:
                            # Save the exact advisory next to the successful note receipt.
                            # A projection alone is not an addressable readback target.
                            saved['quantitative_change_check'] = report
                            result = result.model_copy(update={'content': json.dumps(saved, ensure_ascii=False)})
                            await self._checkpoint_call(self.graph.aupdate_state, self.config,
                                {'messages': [result]}, as_node='tools')
            view = model_receipt(result)
            text = json.dumps(view, ensure_ascii=False, separators=(',', ':'))
            # A completed rejection with a usable repair path is a tool result,
            # not an MCP execution failure. Native ACP also gates failed events;
            # retaining isError here would bypass the shared classification.
            # The inner receipt remains error and the artifact is not accepted.
            return types.CallToolResult(content=[types.TextContent(type='text', text=text)],
                is_error=result.status == 'error' and not actionable_tool_feedback(result), structured_content=view)
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
                # The preview consumes the delivered manuscript verbatim, including
                # display handles in its edit anchors. It performs no source lookup.
                if name != 'check_quantitative_changes' or 'edits' not in arguments:
                    arguments = expand_references(arguments, state)
            except ValueError as exc:
                feedback = reference_selection_feedback(exc, self.tools)
                receipt = ToolMessage(name=name, tool_call_id=call_id, status='error',
                    content=json.dumps(feedback, ensure_ascii=False) if feedback else str(exc))
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
