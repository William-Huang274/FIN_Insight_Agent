"""On-demand read-only consultation over the existing metered reviewer.

MCP calls submit/read; they never hold a tool request open for a whole investigation.
The existing provider ledger and business checkpointer own paid replay and observations.
"""
import asyncio
import json
from pathlib import Path
from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from .answer_review import Challenge, version
from .answer_review_provider import independent_review, review_tool_names
from .conversation_agent import GrantedTool
from .harness_acp_session import _persist
from .harness_business_tools import HarnessBusinessTools
from .research_graph_contracts import canonical_sha256


class HarnessConsultations:
    def __init__(self, *, directory, saver, grants, tid, rid, check, scope, budget,
                 environment, model, basis, as_of, public_sink, research_depth='standard'):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.saver, self.grants, self.tid, self.rid = saver, grants, tid, rid
        self.check, self.scope, self.budget = check, scope, budget
        self.environment, self.model, self.basis = environment, model, basis
        self.as_of, self.public_sink = as_of, public_sink
        from sec_agent.research_foundation.research_depth import depth_guidance
        self.depth_content = depth_guidance(research_depth)
        self.tasks = {}
        self.parent = None

    def tools(self):
        @tool
        async def consult_research_agent(question: str, context: str, purpose: Literal['investigate', 'review'],
                                         runtime: ToolRuntime, use_current_report: bool = False,
                                         method_ids: list[str] | None = None):
            """Delegate one material research question to an independent Sol high agent with read-only sources,
            web/SEC/government/market/calculation tools and the same task budget. Use investigate for a relationship
            that needs separate evidence, review for an argument you want challenged; neither is mandatory.
            Explain the question's bearing on the main answer in context, include exact observed source handles.
            use_current_report=true attaches the exact saved report; false works before drafting.
            method_ids selects optional method-library IDs, not new permissions. Returns task_id promptly.
            Continue useful independent work, then read_research_agent_result; results are proposals, not verdicts.
            """
            return await self.submit(question, context, purpose, use_current_report, method_ids or [], runtime.state)

        @tool
        async def read_research_agent_result(task_id: str, runtime: ToolRuntime, wait_seconds: int = 0):
            """Read the delegated agent's status, opinion and exact source/compute readback handles.
            Calling this while pending yields execution to the host until the child finishes; no paid polling.
            After host wake-up read once to import the result. Legacy wait_seconds accepts 0-20 seconds.
            Continue independent work before calling this. Completed observations become
            usable in this author's source and calculation tools. Resolve a submitted consultation before delivery.
            """
            return await self.read(task_id, wait_seconds, runtime)

        return [GrantedTool(t, 'delegated_task_control', '同一预算内的按需只读调查及独立复核')
                for t in (consult_research_agent, read_research_agent_result)]

    async def submit(self, question, context, purpose, use_report, methods, state):
        from sec_agent.research_foundation.research_methods import preloaded_research_methods
        self.check()
        if not question.strip() or len(question) > 2500 or len(context) > 24000:
            raise ToolException('Provide a nonempty question up to 2500 characters and context up to 24000.')
        try:
            method_text = self.depth_content + preloaded_research_methods(methods)
        except (ValueError, KeyError) as exc:
            raise ToolException('Read get_research_method for available method IDs.') from exc
        report = state.get('report') if use_report else None
        if use_report and not report:
            raise ToolException('No saved report yet; use_current_report=false with current reasoning, or save a report first.')
        body = report['narrative_markdown'] if report else context
        request = dict(question=question, context=context, purpose=purpose, report=report,
                       methods=methods, method_text=method_text, as_of=self.as_of, model=self.model)
        key = canonical_sha256(request)
        path = self.directory / (key + '.json')
        if path.exists():
            record = json.loads(path.read_text(encoding='utf8'))
            # Never restart a lost or failed paid operation from a new tool call.
            if record['status'] == 'running' and key not in self.tasks:
                raise RuntimeError('consultation_interrupted_reconcile_provider_ledger_before_resume')
            if record['status'] == 'failed':
                raise RuntimeError('consultation_failed_requires_recovery:' + key)
            return dict(task_id=key, status=record['status'], reused=True,
                        read_tool='read_research_agent_result')
        record = dict(request=request, status='running', scope=self.tid+':'+self.rid)
        _persist(path, record)
        # Freeze only source/tool records; do not copy the author's argument history.
        source_messages = [m for m in state.get('messages', [])
                           if isinstance(m, ToolMessage) and m.status == 'success'
                           and m.name in review_tool_names([g.tool.name for g in self.grants])]
        initial = {'question':question, 'messages':source_messages}
        self.tasks[key] = asyncio.create_task(self.run(key, record, initial, body))
        return dict(task_id=key, status='running', read_tool='read_research_agent_result')

    def child(self, key):
        allowed = set(review_tool_names([g.tool.name for g in self.grants])) | {'read_saved_result'}
        return HarnessBusinessTools(grants=[g for g in self.grants if g.tool.name in allowed],
            checkpointer=self.saver, thread_id=self.tid+':consult:'+key,
            check=self.parent.access if self.parent else self.check,
            scope=self.scope, stop_on_tool_error=True)

    async def recover_cancelled(self, previous_run_id, audit_root):
        """Resume only an explicitly authorized cancelled consultation, with its exact request.

        The provider's existing recovery verifies each unknown call and wire fingerprint.
        This does not grant retries or transform a failed task into a fresh assignment.
        """
        from sec_agent.adapters.explicit_run_recovery import verified_permit, verified_preparation_recovery
        previous_scope = self.tid+':'+previous_run_id
        # A recovery can itself be interrupted before it reaches this method.
        # Follow only tasks present in this author's real saved tool receipts.
        pending_ids = set()
        if self.parent and hasattr(self.parent,'state'):
            for message in (await self.parent.state()).get('messages',[]):
                if isinstance(message,ToolMessage) and message.name=='consult_research_agent' and message.status=='success':
                    result=json.loads(message.content)
                    if isinstance(result,dict) and result.get('task_id'):
                        pending_ids.add(result['task_id'])
        candidates = [(p, json.loads(p.read_text(encoding='utf8'))) for p in self.directory.glob('*.json')]
        candidates = [(p,r) for p,r in candidates if (r['scope']==previous_scope or p.stem in pending_ids)
                      and r['status']!='completed']
        if not candidates:
            return
        for path, record in candidates:
            stopped_record = record
            # An explicit run recovery may retry a known failed read. Check the
            # actual saved receipt and granted effect, not just an error string.
            # Paid unknown requests still require their separate provider permit.
            code = record.get('failure_code', '')
            failed_read = False
            if code.startswith('answer_review_source_tool_failed:'):
                receipt_id = code.split(':', 1)[1]
                child = self.child(path.stem)
                history = (await child.state()).get('messages', [])
                failed_read = any(isinstance(m, ToolMessage) and m.tool_call_id == receipt_id
                    and m.status == 'error' and child.effects.get(m.name) == 'read'
                    for m in history)
            # A checked zero-dispatch recovery failure cannot replace the prior
            # paid checkpoint. Follow its immutable history, with both proofs.
            if record.get('error_type') != 'CancelledError' and not failed_read:
                thread, run = record['scope'].split(':')
                prepared = verified_preparation_recovery(audit_root,thread,run,
                    secret=self.environment['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'])
                prior_scope = record.get('previous_scope','')
                if not prepared or not prior_scope.startswith(self.tid+':'):
                    raise RuntimeError('consultation_failure_requires_separate_reconciliation')
                prior_run=prior_scope.split(':')[1]
                history=self.directory/'history'/path.stem/(prior_run+'.json')
                prior=json.loads(history.read_text(encoding='utf8'))
                if prior['scope'] != prior_scope or prior['request'] != record['request']:
                    raise RuntimeError('consultation_preparation_history_mismatch')
                record=prior
            previous_scope=record['scope']
            origin_thread,origin_run=previous_scope.split(':')
            if origin_thread!=self.tid:
                raise RuntimeError('consultation_recovery_execution_mismatch')
            permit = verified_permit(audit_root,self.tid,origin_run,
                                     secret=self.environment['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'])
            if not permit and not failed_read:
                raise RuntimeError('consultation_recovery_requires_explicit_paid_retry_authorization')
            if record.get('error_type') != 'CancelledError' and not failed_read:
                raise RuntimeError('consultation_failure_requires_separate_reconciliation')
            key=path.stem
            if not await self.child(key).state():
                raise RuntimeError('consultation_recovery_checkpoint_missing')
            # Preserve the stopped task independently from the mutable status pointer.
            _persist(self.directory/'history'/key/(origin_run+'.json'),record)
            if stopped_record is not record:
                _persist(self.directory/'history'/key/(stopped_record['scope'].split(':')[1]+'.json'),stopped_record)
            resumed={k:v for k,v in record.items() if k not in {'error_type', 'failure_code'}}
            resumed.update(status='running',scope=self.tid+':'+self.rid,previous_scope=previous_scope)
            _persist(path,resumed)
            request=record['request']
            body=request['report']['narrative_markdown'] if request['report'] else request['context']
            self.tasks[key]=asyncio.create_task(self.run(key,resumed,{},body,
                previous_scope=previous_scope,audit_root=audit_root))

    async def run(self, key, record, initial, body, *, previous_scope=None, audit_root=None):
        request = record['request']
        try:
            child = self.child(key)
            # A signed recovery may have stopped inside a read, between two
            # provider calls. The shared bridge resumes only that pending read;
            # completed reads stay in the checkpoint and writes remain blocked.
            await child.initialize(initial, recovering=previous_scope is not None)
            selected = Challenge(version=version(body), quote='', offset=0, question=request['question'])
            opinion = await independent_review(selected=selected,
                message=AIMessage(content=body), question=request['question']+'\n'+request['context'],
                bridge=child, budget=self.budget, environment=self.environment, model=self.model,
                scope=record['scope'], command_id='consult-'+key, authority=child.model_access,
                basis=self.basis, as_of=self.as_of, public_sink=self.public_sink,
                assignment_kind=request['purpose'], method_content=request['method_text'],
                dispatch_lane='consult:'+key,previous_scope=previous_scope,audit_root=audit_root)
            self.check()
            _persist(self.directory/(key+'.json'), {**record,'status':'completed','opinion':opinion})
        except BaseException as exc:
            _persist(self.directory/(key+'.json'), {**record,'status':'failed','error_type':type(exc).__name__,
                **({'failure_code':str(exc)} if isinstance(exc,(ValueError,RuntimeError))
                   and str(exc).startswith(('answer_review_','harness_business_tool_')) else {})})
            if self.parent:
                self.parent.failed_receipt = 'consult-'+key
            raise

    async def read(self, key, wait, runtime):
        self.check()
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key) or not 0 <= wait <= 20:
            raise ToolException('Use the returned task_id; wait_seconds must be 0-20.')
        path = self.directory/(key+'.json')
        if not path.exists():
            raise ToolException('Unknown task_id in this research workspace.')
        task = self.tasks.get(key)
        if task and not task.done():
            await asyncio.wait({task}, timeout=wait)
        if task and task.done():
            task.result()
        record = json.loads(path.read_text(encoding='utf8'))
        if record['status'] != 'completed':
            return dict(task_id=key, status=record['status'], host_wait_before_next_model=True,
                        next_action='After host completion, read this task once to import its result.')
        child_state = await self.child(key).state()
        existing = {m.id for m in runtime.state.get('messages', []) if m.id}
        messages = [m for m in child_state.get('messages', []) if m.id not in existing]
        result = dict(task_id=key,status='completed',opinion=record['opinion'],
                      purpose=record['request']['purpose'],
                      reviewed_report_digest=canonical_sha256(record['request']['report']) if record['request']['report'] else None,
                      target_digest=canonical_sha256(record['request']),
                      source_readback=[{'tool_call_id':m.tool_call_id,'tool':m.name}
                          for m in messages if isinstance(m, ToolMessage) and m.status=='success'])
        return Command(update={'messages':[*messages, ToolMessage(name='read_research_agent_result',
            tool_call_id=runtime.tool_call_id, content=json.dumps(result,ensure_ascii=False))]})

    async def dispatch_ready(self, timeout=20):
        """Wait outside model dispatch and its financial reservation.

        Only explicit result reads suspend the author, not task submission. Derive
        the wait from durable receipts so cancel/recovery cannot forget it. The
        private host endpoint long-polls small state, never the large LLM request.
        """
        self.check()
        waiting = {}
        if self.parent:
            for message in (await self.parent.state()).get('messages', []):
                if isinstance(message, ToolMessage) and message.name == 'read_research_agent_result' and message.status == 'success':
                    result = json.loads(message.content)
                    if isinstance(result, dict) and result.get('task_id'):
                        waiting[result['task_id']] = result.get('status') != 'completed'
        tasks = []
        for key, pending in waiting.items():
            if not pending:
                continue
            task = self.tasks.get(key)
            if task is None:
                record = json.loads((self.directory/(key+'.json')).read_text(encoding='utf8'))
                if record['status'] != 'completed':
                    raise RuntimeError('consultation_interrupted_reconcile_provider_ledger_before_resume')
            else:
                tasks.append(task)
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        self.check()
        for task in tasks:
            if task.done():
                task.result()  # failure closes admission; never a fake completion
        return {'status': 'waiting' if any(not t.done() for t in tasks) else 'ready'}

    async def ensure_finished(self):
        if any(not task.done() for task in self.tasks.values()):
            raise RuntimeError('consultation_pending_at_delivery')
        for task in self.tasks.values():
            task.result()

    async def close(self):
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
