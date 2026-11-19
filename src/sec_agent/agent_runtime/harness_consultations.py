"""On-demand read-only consultation over the existing metered reviewer.

MCP calls submit/read; they never hold a tool request open for a whole investigation.
The existing provider ledger and business checkpointer own paid replay and observations.
"""
import asyncio
from contextvars import copy_context
import json
from pathlib import Path
from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from .answer_review import Challenge, version
from .assessment_evidence import Counterexample, record_counterexamples
from .research_workpapers import WorkpaperConflict
from .answer_review_provider import independent_review, review_tool_names
from .conversation_agent import GrantedTool
from .harness_acp_session import _persist
from .harness_business_tools import HarnessBusinessTools
from .research_graph_contracts import canonical_sha256
from sec_agent.adapters.model_dispatch_store import DispatchBlocked


class HarnessConsultations:
    def __init__(self, *, directory, saver, grants, tid, rid, check, scope, budget,
                 environment, model, basis, as_of, public_sink, research_depth='standard', research_question=None,
                 native_delegate=None, workspace=None, actor='root', topic_delegate=None,
                 depth=0, family=None, hold_submissions=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.saver, self.grants, self.tid, self.rid = saver, grants, tid, rid
        self.check, self.scope, self.budget = check, scope, budget
        self.environment, self.model, self.basis = environment, model, basis
        self.as_of, self.public_sink = as_of, public_sink
        self.research_question = research_question
        self.native_delegate = native_delegate
        self.workspace, self.actor, self.topic_delegate = workspace, actor, topic_delegate
        self.depth, self.family, self.nested = depth, family if family is not None else [], {}
        self.family.append(self)
        from sec_agent.research_foundation.research_depth import depth_guidance
        self.depth_content = depth_guidance(research_depth)
        self.research_depth = research_depth
        self.tasks = {}
        self.hold_submissions = hold_submissions
        self.parent = None
        # A child outlives the individual MCP tool invocation. Keep the admitted
        # run context, not that invocation's soon-expired memory permission guard.
        self.execution_context = copy_context()

    def tools(self):
        @tool
        async def consult_research_agent(question: str, context: str, purpose: Literal['investigate', 'review', 'draft'],
                                         runtime: ToolRuntime, use_current_report: bool = False,
                                         method_ids: list[str] | None = None, topic_lead: bool = False,
                                         topic_id: str | None = None, authoring_issue_id: str | None = None):
            """Delegate one material research question to the configured research agent with read-only sources,
            web/SEC/government/market/calculation tools and the same task budget. Use investigate for a relationship
            that needs separate evidence, review for an argument you want challenged; neither is mandatory.
            Explain the target relationship and its bearing on the main answer in context; include existing
            evidence handles and unresolved alternatives when known. No separate plan or template is required.
            Choose an assignment for the observation that could change your answer: a customer's
            purchase/renewal decision, competitors' supply response, cash conversion or a forecast assumption.
            A company summary is useful only when it resolves that question. Ask for the resulting
            change in understanding, not a predetermined conclusion or a chapter to paste.
            For forecasts ask why one conditional outlook is favored, not only which claims are
            too strong. A useful review can identify supported judgments the author failed to make.
            Proposed formulas/comparisons are hypotheses: the investigator may revise them if they answer
            a different question. Draft assignments return an evidence-backed draft for your audit, not a final publication.
            use_current_report=true attaches the exact saved report; false works before drafting.
            After material reconstruction, review the actual replacement explanation with
            purpose=review and use_current_report=true; a pre-draft opinion cannot clear final prose.
            Give the reviewer the original decision and unresolved relationships, not a requested verdict.
            For an investigation, define the material relationship and how its answer could change the
            decision; request evidence, analysis and a conditional finding, not proof of your hypothesis.
            If the assignment narrows an earlier question, retain the answer-changing remainder in context
            and say who will pursue it. A counterexample can disprove a universal claim without answering
            the original question about the most likely outcome.
            Check each returned result before relying on it and update your working understanding.
            A locally checked result does not certify the whole question or authorize history deletion.
            The host separately supplies the original research question; your focus does not replace it.
            method_ids selects optional method-library IDs, not new permissions. Returns task_id promptly.
            Continue useful independent work, then read_research_agent_result; results are proposals, not verdicts.
            For a saved writing discontinuity, pass authoring_issue_id: the host attaches its exact original
            passage, current affected judgments, section purpose and source versions. No need to paste history.
            """
            return await self.submit(question, context, purpose, use_current_report, method_ids or [], runtime.state,
                                     topic_lead=topic_lead, topic_id=topic_id, authoring_issue_id=authoring_issue_id)

        if self.workspace and self.topic_delegate:
            consult_research_agent.description += ('\nUse topic_lead=true for a substantial relationship requiring ongoing '
                'local decisions and worker delegation. The topic lead uses the root decision model in an isolated '
                'native context and shared budget. Return topic_id for a later assignment to the same durable topic; '
                'its current workpaper, not full old conversations, is the continuity record. Independent tasks run '
                'asynchronously; read_next_research_result consumes whichever finishes first. Topic depth <=3, '
                'shared active-task admission <=8; do not create a layer for a simple lookup. A topic result must '
                'persist a complete workpaper; parent adoption does not settle remaining original-question duties.')
        if self.workspace and self.actor=='root' and self.workspace.organization_policy().get('root_investigations_require_topic_lead'):
            consult_research_agent.description += ('\nThis research uses topic leads: root investigations require topic_lead=true. '
                'Continue existing topics with their topic_id. Root owns cross-topic understanding; '
                'each topic lead owns local worker supervision and the complete argument.')

        consult_research_agent.description += ('\nConfigured delegate: '+self.model+' high. '+
            ('purpose=draft is available for investigation and drafting; you retain final research and publication responsibility.'
             if self.native_delegate else 'purpose=draft is unavailable; use investigate or review.'))
        if self.hold_submissions:
            consult_research_agent.description += ('\nThis user-requested preparation stage saves assignments as queued; '
                'workers do not start. Submit your chosen assignments, then report the proposed division of work. '
                'Do not poll queued assignments or claim their investigation is complete.')

        @tool
        async def start_queued_research_task(task_id: str, execution_context: str,
                                            research_question: str, runtime: ToolRuntime):
            """Start a saved, never-executed assignment after the host lifts its preparation hold.
            Read the queued assignment first. Supply its updated execution context and the current
            full research question, replacing preparation-only stop instructions. Preserve research
            scope, source handles, assumptions and dependencies; do not silently narrow the task.
            The original assignment question, task identity and preparation record remain saved.
            This cannot retry failed or interrupted paid work. Repeating an identical release is
            idempotent; a different release requires a new explicit assignment.
            """
            return self.start_queued(task_id, execution_context, research_question, runtime.state)

        @tool
        async def read_research_agent_result(task_id: str, runtime: ToolRuntime, wait_seconds: int = 0):
            """Read the delegated agent's status, opinion and exact source/compute readback handles.
            Calling this while pending yields execution to the host until the child finishes; no paid polling.
            After host wake-up read once to import the result. Legacy wait_seconds accepts 0-20 seconds.
            Continue independent work before calling this. Completed observations become
            usable in this author's source and calculation tools. Resolve a submitted consultation before delivery.
            """
            return await self.read(task_id, wait_seconds, runtime)

        @tool
        async def read_next_research_result(task_ids: list[str], runtime: ToolRuntime):
            """Import one completed result among explicit pending task IDs, without a wave barrier.
            If none is complete the host waits for the first completion before another model call.
            Remove returned task_id from your pending set; do independent work when useful.
            """
            if not task_ids or len(task_ids) > 8:
                raise ToolException('Choose 1-8 pending task IDs.')
            for key in task_ids:
                if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                    raise ToolException('Use returned task IDs.')
                path = self.directory/(key+'.json')
                if not path.exists():
                    return self.result_selection(key)
                record = json.loads(path.read_text(encoding='utf8'))
                if record['status'] == 'failed':
                    raise RuntimeError('consultation_failed_requires_recovery:'+key)
                if record['status'] == 'completed':
                    return await self.read(key, 0, runtime)
            return {'status':'waiting', 'pending_task_ids':list(dict.fromkeys(task_ids)),
                    'host_wait_before_next_model':True}

        @tool
        async def assess_research_result(task_id: str, result_digest: str,
                disposition: Literal['accepted', 'needs_work', 'reopened'], finding: str,
                scope_and_conditions: str, counterevidence: str, unresolved: str,
                evidence_receipt_ids: list[str], runtime: ToolRuntime, decisive_passages: list[Counterexample] | None = None):
            """Record your judgment after reading a specific delegated result. Accept only after
            checking the assigned relationship, evidence and conditional finding. Preserve period,
            units, scope, assumptions, strongest countercase and remaining unknowns in concise prose;
            explain explicitly when no counterevidence or unresolved issue was found. Bind key
            evidence using returned tool_call_id handles. When a concrete counterexample changes the
            judgment, select its exact original in decisive_passages for the chapter author and editor.
            Accepted results leave active native
            context as this summary plus exact readback; originals remain saved. This is your
            bounded research judgment, not runtime certification or clearance of report review
            actions. Use needs_work/reopened when further investigation is material; commission
            that work separately. In finding/unresolved compare the assigned question with the actual answer:
            say whether remaining uncertainty changes direction, magnitude, timing or only precision,
            and whether a feasible comparison could change your choice. Accepting a scoped result does
            not close the broader question; keep its material remainder in current working understanding.
            Do not accept merely to reduce tokens. Changed results require
            a fresh read and decision. Never suppress an unresolved condition in the summary.
            """
            return self.assess(task_id, result_digest, disposition, finding, scope_and_conditions,
                               counterevidence, unresolved, evidence_receipt_ids, runtime.state, decisive_passages)

        return [GrantedTool(t, 'read' if t.name in {'read_research_agent_result','read_next_research_result'}
                            else 'delegated_task_control', '同一预算内的按需只读调查及独立复核')
                for t in (consult_research_agent, start_queued_research_task, read_research_agent_result, read_next_research_result, assess_research_result)]

    def public_workpaper_readback(self, key):
        """Cross-role navigation to a published argument, never another role's journal."""
        if not self.workspace or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            return None
        for service in self.family:
            if service.workspace is not self.workspace:
                continue
            path=service.directory/(key+'.json')
            if path.exists():
                row=json.loads(path.read_text(encoding='utf8'))
                ref=row.get('workpaper_ref')
                if row['status']=='completed' and ref:
                    self.workspace.read(self.actor,ref['topic_id'],ref['revision'],field='metadata')
                    return {'tool':'read_research_workpaper','arguments':{
                        'topic_id':ref['topic_id'],'revision':ref['revision']}}
        return None

    def scoped_observations(self, value):
        if isinstance(value,list):
            return [self.scoped_observations(v) for v in value]
        if not isinstance(value,dict):
            return value
        if value.get('tool')=='read_research_agent_result':
            key=value.get('arguments',{}).get('task_id','')
            return self.public_workpaper_readback(key) or {
                'tool':'research_updates','arguments':{},'origin_task_id':key,
                'notice':'Origin task belongs to the delegating role; navigate published workpapers.'}
        return {k:self.scoped_observations(v) for k,v in value.items()}

    def result_selection(self, key):
        self.check()
        return {'status':'selection_required','code':'consultation_result_selection_required',
            'requested_task_id':key,'readback':self.public_workpaper_readback(key) or {
                'tool':'research_updates','arguments':{}},
            'notice':'This task is outside the local task scope or unknown. Read the published argument; no task started or resumed.'}

    def start_queued(self, key, context, research_question, state):
        self.check()
        if self.hold_submissions:
            raise ToolException('Preparation hold remains active; no worker started.')
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ToolException('Use the exact queued task_id.')
        path = self.directory/(key+'.json')
        if not path.exists():
            raise ToolException('Queued assignment not found.')
        if not context.strip() or len(context) > 24000 or not research_question.strip() or len(research_question) > 24000:
            raise ToolException('Supply current execution context and original research scope, each up to 24000 characters.')
        record = json.loads(path.read_text(encoding='utf8'))
        if (self.workspace and self.actor=='root' and record['request']['purpose']=='investigate'
                and self.workspace.organization_policy().get('root_investigations_require_topic_lead')
                and not record['request'].get('workpaper_assignment',{}).get('topic_lead')):
            return {'submitted':False,'status':'topic_lead_required',
                    'next_action':'Keep this original assignment; submit a topic lead with the same topic_id to take responsibility.'}
        transition = {'execution_context': context, 'research_question': research_question}
        if record['status'] != 'queued':
            if (record.get('stage_transition') == transition and record['status'] == 'completed') or (
                    record.get('stage_transition') == transition and key in self.tasks and record['status'] == 'running'):
                return {'task_id':key, 'status':record['status'], 'reused':True}
            raise ToolException('Only never-dispatched queued work can start here; paid recovery uses its separate authorization path.')
        active = [(s,k,t) for s in self.family for k,t in s.tasks.items() if not t.done()]
        if len(active) >= 8:
            return {'submitted':False, 'status':'capacity_wait', 'host_wait_before_next_model':True}
        if record['request'].get('workpaper_assignment',{}).get('topic_lead'):
            count = sum(bool(json.loads((s.directory/(k+'.json')).read_text(encoding='utf8'))
                        ['request'].get('workpaper_assignment',{}).get('topic_lead')) for s,k,_ in active)
            if count >= 3:
                return {'submitted':False, 'status':'topic_capacity_unavailable'}
        _persist(self.directory/'history'/key/'queued.json', record)
        request = {**record['request'], 'context':context,
            'research_task': {**record['request'].get('research_task',{}), 'question':research_question}}
        record = {**record, 'request':request, 'stage_transition':transition,
            'preparation_request_digest':canonical_sha256(record['request']),
            'status':'running', 'scope':self.tid+':'+self.rid}
        _persist(path, record)
        self._dispatch(key, record, state)
        return {'task_id':key, 'status':'running', 'read_tool':'read_research_agent_result',
                'preparation_record_preserved':True}

    def _dispatch(self, key, record, state):
        from .conversation_tools import SAVED_AUDIT_TOOLS, SAVED_RESULT_TOOLS
        inherited = SAVED_RESULT_TOOLS if self.workspace else set(review_tool_names([g.tool.name for g in self.grants])) | SAVED_AUDIT_TOOLS
        source_messages = [m for m in state.get('messages', [])
                           if isinstance(m, ToolMessage) and m.status == 'success' and m.name in inherited]
        request = record['request']
        initial = {'question':request['question'], 'messages':source_messages}
        body = request['report']['narrative_markdown'] if request['report'] else request['context']
        self.tasks[key] = asyncio.create_task(self.run(key, record, initial, body),
                                             context=self.execution_context.copy())

    def assess(self, key, digest, disposition, finding, conditions, counterevidence, unresolved, evidence, state, decisive_passages=None):
        from .research_result_acceptance import result_version
        self.check()
        feedback = {'decision_recorded': False, 'readback': {'tool': 'read_research_agent_result',
                     'arguments': {'task_id': key}}}
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            return {**feedback, 'error': 'Use the returned task_id.'}
        path = self.directory/(key+'.json')
        record = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        if record.get('status') != 'completed' or result_version(record) != digest:
            return {**feedback, 'error': 'Result unavailable or changed; read the current completed result first.'}
        if disposition == 'accepted' and self.workspace and record.get('workpaper_ref'):
            ref = record['workpaper_ref']
            current = self.workspace.read(self.actor, ref['topic_id'], ref['revision'], field='metadata')
            if current['current_revision'] != ref['revision'] or current['requires_reassessment']:
                return {**feedback, 'error': 'Research premises changed; reassess current workpaper before accepting.'}
            if not self.workspace.observed(self.actor,ref['topic_id'],ref['revision']):
                return {**feedback, 'error':'Read the underlying argument before accepting; result metadata is navigation.'}
        messages = state.get('messages', [])
        observed = [json.loads(m.content) for m in messages if isinstance(m, ToolMessage)
                    and m.name == 'read_research_agent_result' and m.status == 'success']
        if not any(b.get('task_id') == key and b.get('result_digest') == digest for b in observed):
            return {**feedback, 'error': 'Read this exact result before assessing it.'}
        texts = [finding, conditions, counterevidence, unresolved]
        if (disposition not in {'accepted', 'needs_work', 'reopened'}
                or any(not s.strip() for s in texts) or sum(map(len, texts)) > 10000):
            return {**feedback, 'error': 'Provide a concise finding, scope/conditions, counterevidence and unresolved state (total <=10000 characters).'}
        from .conversation_tools import READABLE_RESULT_TOOLS
        available = {m.tool_call_id for m in messages if isinstance(m, ToolMessage) and m.status == 'success'
                     and m.name in READABLE_RESULT_TOOLS}
        if not evidence or len(evidence) > 24 or any(e not in available for e in evidence):
            return {**feedback, 'error': 'Bind 1-24 successfully read evidence/result receipt IDs; no invented handles.'}
        ref = record.get('workpaper_ref')
        if decisive_passages and (not ref or not self.workspace):
            return {**feedback, 'error':'Selecting exact passages requires a versioned workpaper.'}
        quotes = []
        if ref and self.workspace:
            try:
                quotes = record_counterexamples(self.workspace,self.actor,ref,digest,disposition,counterevidence,
                                                decisive_passages or [],evidence,messages)
            except WorkpaperConflict as exc:
                return {**feedback,'error':str(exc)}
        return dict(decision_recorded=True, task_id=key, result_digest=digest, disposition=disposition,
                    **({'decisive_passages':quotes} if quotes else {}),
                    finding=finding, scope_and_conditions=conditions, counterevidence=counterevidence,
                    unresolved=unresolved, evidence_readback=[{'tool':'read_saved_result',
                        'arguments':{'tool_call_id':e}} for e in dict.fromkeys(evidence)])

    async def context_projection(self, candidates):
        """Authenticated host projection; never trust a model's invented acceptance marker."""
        await asyncio.to_thread(self.check)
        if not self.parent:
            return {'replacements': []}
        messages = (await self.parent.state()).get('messages', [])
        # SQLite reads and authorization HTTP calls are synchronous. Multiple
        # restored topics must not block each other's local HTTP/MCP service.
        # to_thread retains the admitted ContextVars; every access check remains.
        return await asyncio.to_thread(self._project_context, candidates, messages)

    def _project_context(self, candidates, messages):
        from .research_decision_context import inspected_window, resolved_feedback
        from .research_result_acceptance import (latest_decisions, result_version, accepted_projection,
                                                workpaper_conditions, acceptance_reference)
        from .harness_business_tools import model_receipt
        self.check()
        decisions = latest_decisions(messages)
        positions = {m.tool_call_id:i for i,m in enumerate(messages) if isinstance(m,ToolMessage)}
        accepted_reads = {}
        shared_conditions = bool(self.workspace and self.workspace.organization_policy().get('root_investigations_require_topic_lead'))
        research_view = shared_conditions and not self.workspace.authoring_active()
        if self.workspace:
            for key,(decision,decision_id) in decisions.items():
                path = self.directory/(key+'.json')
                if decision.get('disposition') != 'accepted' or not path.exists():
                    continue
                record = json.loads(path.read_text(encoding='utf8'))
                if (record.get('status') != 'completed' or not record.get('workpaper_ref')
                        or result_version(record) != decision.get('result_digest')):
                    continue
                ref = record['workpaper_ref']
                paper = self.workspace.read(self.actor,ref['topic_id'],ref['revision'],field='metadata')
                if paper['current_revision'] != ref['revision'] or paper['requires_reassessment']:
                    continue
                # Do not retire a root's accepted argument until its adoption is
                # durably represented in current understanding (not just a chat).
                if (self.actor == 'root' and self.workspace.organization_policy().get('root_investigations_require_topic_lead')):
                    view = self.workspace.authoring.context(include_unplaced=True, include_history=True)
                    refs = [d for k,j in view['judgments'].items() if j['status']=='active'
                            and k not in view['requires_reassessment'] for d in j['workpapers']]
                    adopted=set()
                    with self.workspace.connection() as db:
                        while refs:
                            d=refs.pop()
                            identity=(d['topic_id'],d['revision'],d['digest'])
                            if identity in adopted:
                                continue
                            for current in self.workspace.dependency_walk(db,
                                    self.workspace._get(db,d['topic_id'],d['revision'])):
                                adopted.add((current['topic_id'],current['revision'],current['digest']))
                    if (ref['topic_id'],ref['revision'],ref['digest']) not in adopted:
                        continue
                with self.workspace.connection() as db:
                    for p in self.workspace.dependency_walk(db,paper):
                        accepted_reads[(p['topic_id'],p['revision'],p['digest'])]=(decision,decision_id,p)
                        for receipt_id in p['evidence_receipt_ids']:
                            accepted_reads[receipt_id]=(decision,decision_id,p)
        originals = {m.tool_call_id:m for m in messages if isinstance(m, ToolMessage)
                     and m.name in {'read_research_agent_result','read_research_workpaper','read_synthesis_material','read_workpaper_evidence'} and m.status == 'success'}
        replacements = []
        authoring_ids = {m.tool_call_id for m in messages if isinstance(m,ToolMessage) and m.name=='read_authoring_context'}
        if self.workspace and self.actor == 'root' and any(c.get('receipt_id') in authoring_ids for c in candidates):
            from .research_authoring import authoring_context_replacements
            views={}
            def current_view(sections,history,include_unplaced=False):
                key=(None if sections is None else tuple(sorted(sections)),history,include_unplaced)
                if key not in views:
                    views[key]=self.workspace.authoring.context(sections,include_history=history,include_unplaced=include_unplaced)
                return views[key]
            replacements = authoring_context_replacements(messages, candidates, current_view)
        from .research_authoring import material_context_replacements
        # Restore-time projection also covers old search receipts. This removes
        # duplicate packaging through the native surface API, not log rewriting.
        from .conversation_web import compact_search_navigation
        source_messages = {m.tool_call_id:m for m in messages if isinstance(m,ToolMessage)
                           and m.name=='read_public_source' and m.status=='success'}
        for candidate in candidates:
            message = source_messages.get(candidate.get('receipt_id'))
            if message is None:
                continue
            receipt = model_receipt(message)
            body = receipt.get('result')
            if research_view and (candidate.get('inspected') or candidate.get('context_state') == 'inspected_research_window'):
                replacement = inspected_window(message.name,message.tool_call_id,body)
                if replacement:
                    replacements.append({'receipt_id':message.tool_call_id,
                        'result_digest':replacement['result']['result_digest'],'receipt':replacement})
                    continue
            if not isinstance(body,dict) or body.get('operation') != 'search' or not body.get('source_snapshot_sha256'):
                continue
            compact = compact_search_navigation(body)
            if len(json.dumps(compact)) >= len(json.dumps(body)):
                continue
            compact['context_state']='deduplicated_search_navigation'
            replacements.append({'receipt_id':message.tool_call_id,
                'result_digest':body.get('result_digest') or body['source_snapshot_sha256'],
                'receipt':{**receipt,'result':compact}})
        handled = {r['receipt_id'] for r in replacements}
        handled.update(key for r in replacements for key in r['receipt'].get('result',{}).get('active_window_receipts',[]))
        if research_view:
            resolved = resolved_feedback(messages)
            for item in candidates:
                key = item['receipt_id']
                if key in handled or key not in positions:
                    continue
                replacement = resolved.get(key)
                if (replacement is None and item.get('context_state') != 'accepted_result_summary'
                        and (item.get('inspected') or item.get('context_state') == 'inspected_research_window')):
                    original = messages[positions[key]]
                    if original.status == 'success' and original.name in (
                            'read_saved_result','read_workpaper_evidence','read_research_workpaper','read_authoring_context'):
                        body = json.loads(original.content)
                        identity = ((body.get('topic_id'),body.get('revision'),body.get('digest'))
                                    if original.name == 'read_research_workpaper' else body.get('receipt_id'))
                        accepted_id = accepted_reads.get(identity,({},None,{}))[1]
                        if not accepted_id or positions[accepted_id] < positions[key]:
                            replacement = inspected_window(original.name,key,body)
                if replacement:
                    replacements.append({'receipt_id':key, 'result_digest':replacement['result']['result_digest'],
                                         'receipt':replacement})
                    handled.add(key)
        for item in candidates:
            if item.get('receipt_id') in handled:
                continue
            if item.get('context_state') in {'inspected_research_window','resolved_research_feedback'}:
                # Saved historical readback stays valid across phase switches and compaction.
                # It carries no claim of current acceptance.
                continue
            original = originals.get(item.get('receipt_id'))
            if original is None:
                if item.get('receipt_id') in authoring_ids:
                    continue
                if item.get('retired'):
                    raise RuntimeError('accepted_result_original_receipt_missing')
                continue
            body = json.loads(original.content)
            if original.name != 'read_research_agent_result':
                identity = ((body.get('topic_id'),body.get('revision'),body.get('digest'))
                            if original.name in {'read_research_workpaper','read_synthesis_material'} else body.get('receipt_id'))
                decision,decision_id,paper=accepted_reads.get(identity,({},None,{}))
                # A deliberate new read after acceptance stays visible until a later assessment.
                if decision and positions[decision_id] > positions[original.tool_call_id]:
                    replacement={'receipt_id':original.tool_call_id,'status':'success','result':{
                        'result_digest':body['result_digest'],'context_state':'accepted_result_summary',
                        'argument_identity':identity,
                        **({'acceptance_ref':acceptance_reference(decision,decision_id),
                            'workpaper_ref':{k:paper[k] for k in ('topic_id','revision','digest')}}
                           if shared_conditions else {'acceptance':decision,'workpaper_conditions':workpaper_conditions(paper)}),
                        'original_readback':{'tool':'read_saved_result','arguments':{'tool_call_id':original.tool_call_id}}}}
                elif item.get('retired'):
                    replacement=model_receipt(original)
                    replacement['context_notice']='Acceptance reopened or premises changed; reassess the original argument.'
                else:
                    continue
                replacements.append({'receipt_id':original.tool_call_id,'result_digest':body['result_digest'],'receipt':replacement})
                continue
            key, digest = body.get('task_id'), body.get('result_digest')
            if not key or not digest:
                continue  # Legacy results need a fresh version-bound read.
            decision, decision_id = decisions.get(key, ({}, None))
            path = self.directory/(key+'.json')
            if not path.exists():
                raise RuntimeError('accepted_result_task_record_missing')
            record = json.loads(path.read_text(encoding='utf8'))
            accepted = (decision.get('disposition') == 'accepted' and decision.get('result_digest') == digest
                        and record.get('status') == 'completed' and result_version(record) == digest)
            if accepted and self.workspace and record.get('workpaper_ref'):
                ref=record['workpaper_ref']
                accepted=(ref['topic_id'],ref['revision'],ref['digest']) in accepted_reads
            if accepted:
                replacement = accepted_projection(original, decision, decision_id, shared_conditions=shared_conditions)
            elif item.get('retired'):
                replacement = model_receipt(original)
                replacement['context_notice'] = 'Acceptance is no longer current. Reassess before relying on this historical result.'
            else:
                continue
            replacements.append({'receipt_id': original.tool_call_id, 'result_digest': digest, 'receipt': replacement})
        # Accepted arguments take precedence over overlapping read-window deduplication.
        # Otherwise its retained active window keeps the full accepted paper alive.
        handled = {r['receipt_id'] for r in replacements}
        replacements.extend(material_context_replacements(messages,
            [c for c in candidates if c.get('receipt_id') not in handled]))
        self.check()
        control = self.control_state(decisions=decisions, accepted_papers={
            (p['topic_id'],p['revision'],p['digest']):p for _,_,p in accepted_reads.values()})
        return {'replacements': replacements, **({'control_state':control} if control else {})}

    def control_state(self, *, decisions=None, accepted_papers=None):
        """Exact durable public state, never an LLM-generated replacement summary."""
        if not self.workspace or not self.workspace.organization_policy().get('root_investigations_require_topic_lead'):
            return None
        from .research_decision_context import lead_decision, paper_decision
        policy = self.workspace.organization_policy()
        if self.actor == 'root':
            current = self.workspace.authoring.context(include_unplaced=True)
            if not self.workspace.authoring_active():
                current = lead_decision(current)
        else:
            with self.workspace.connection() as db:
                revision=self.workspace._latest(db).get(self.actor)
            current=(self.workspace.read(self.actor,self.actor,revision,field='metadata') if revision else
                {'topic_id':self.actor,'state':'not_published','readback':{'tool':'research_updates','arguments':{}}})
            if revision and not self.workspace.authoring_active():
                current = paper_decision(current)
        tasks=[]
        completed={}
        records={}
        for path in sorted(self.directory.glob('*.json')):
            row=json.loads(path.read_text(encoding='utf8'))
            records[path.stem]=row
            task={'task_id':path.stem, 'status':row['status'],
                'topic_id':row.get('workpaper_actor'), 'result':row.get('workpaper_ref'),
                'topic_lead':row['request'].get('workpaper_assignment',{}).get('topic_lead',False),
                'readback':{'tool':'read_research_agent_result','arguments':{'task_id':path.stem}}}
            if task['status']=='completed' and task['topic_id'] and task['result']:
                key=task['topic_id']
                old=completed.get(key)
                if old is None or task['result']['revision']>old['result']['revision']:
                    completed[key]=task
            else:
                tasks.append(task)
        tasks.extend(completed[k] for k in sorted(completed))
        topics=self.workspace.catalog(include_catalog=True)['topics']
        if self.actor != 'root':
            topics=[t for t in topics if t['topic_id']==self.actor or t['parent_topic']==self.actor]
        assessments={}
        current_versions={t['topic_id']:t['current_revision'] for t in topics}
        for task_id,(decision,receipt_id) in (decisions or {}).items():
            row=records.get(task_id,{})
            ref=row.get('workpaper_ref') or {}
            key=ref.get('topic_id') or task_id
            assessment={k:decision[k] for k in ('task_id','result_digest','disposition','finding',
                'scope_and_conditions','counterevidence','decisive_passages','unresolved') if k in decision}
            assessment.update(workpaper=ref,
                reviewed_version_is_current=bool(ref and ref['revision']==current_versions.get(ref['topic_id'])),
                readback={'tool':'read_saved_result','arguments':{'tool_call_id':receipt_id}})
            # A new paper does not silently resolve an old disagreement. Keep the
            # last assessment until the coordinator actually assesses its update.
            previous=assessments.get(key)
            if previous is None or ref.get('revision',0)>=previous['workpaper'].get('revision',0):
                assessments[key]=assessment
        from .research_result_acceptance import accepted_argument
        value={'actor':self.actor,'organization':policy,'current_understanding':current,'tasks':tasks,'topics':topics,
            'accepted_arguments':[accepted_argument(p) for p in (accepted_papers or {}).values()],
            'topic_assessments':list(assessments.values()),
            'instruction':'Runtime recovery state from durable public research records, not a new user request or source evidence. '
                'Use current versions and pending disagreements after compaction. Update only affected judgments. '
                'Accepted receipt references share the exact conditions here; reread their original when needed. '
                'Current understanding is the maintained judgment state. No parallel copy in a working note is required; '
                'use notes only for additional working material, not another version of the same judgments. '
                'Compare the working explanation with its strongest alternative. Prioritize the next observation by its effect '
                'on the decision. Read versioned originals, search candidates and acquisition failures on demand. '
                'Root delegates sustained investigation to topic leads; topic leads supervise workers. '
                'Historical conversation and compaction summaries do not supersede these versioned records.'}
        if accepted_papers:
            # A child lead may have registered the only decisive observation. Its
            # review lives in SQLite even when the child's read receipt is gone.
            from .assessment_evidence import current_counterexamples
            with self.workspace.connection() as db:
                observations = current_counterexamples(self.workspace,db,accepted_papers,descend=False)
            carried = [o for o in observations if not any(
                a.get('result_digest') == o['result_digest'] and a.get('decisive_passages') == o['observations']
                for a in assessments.values())]
            if carried:
                value['reviewed_counterexamples'] = carried
        return {'generation':canonical_sha256(value),'state':value,
                'characters':len(json.dumps(value,ensure_ascii=False))}

    async def submit(self, question, context, purpose, use_report, methods, state, *, topic_lead=False, topic_id=None, authoring_issue_id=None):
        from sec_agent.research_foundation.research_methods import preloaded_research_methods
        self.check()
        if (self.workspace and self.actor == 'root' and purpose == 'investigate'
                and self.workspace.organization_policy().get('root_investigations_require_topic_lead')
                and not topic_lead):
            return {'submitted':False, 'status':'topic_lead_required',
                'next_action':'This task uses independent topic decision leads. Resubmit with topic_lead=true; '
                    'keep topic_id to continue its exact workpaper history. A topic lead delegates Flash and '
                    'owns local investigation and acceptance. Root retains cross-topic judgment. '
                    'Simple direct source reads remain available without delegation.'}
        if purpose not in {'investigate', 'review', 'draft'} or (purpose == 'draft' and not self.native_delegate):
            raise ToolException('Use an admitted purpose: investigate/review; draft requires a configured native delegate.')
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
        selected_model = getattr(self.topic_delegate,'options',{}).get('model',self.model) if topic_lead else self.model
        request = dict(question=question, context=context, purpose=purpose, report=report,
                       methods=methods, method_text=method_text, as_of=self.as_of, model=selected_model,
                       assessment_contract=1)
        if authoring_issue_id:
            if not self.workspace or self.actor != 'root':
                raise ToolException('Authoring issue delegation requires the root workspace.')
            from .research_workpapers import WorkpaperConflict
            try:
                request['authoring_issue'] = self.workspace.authoring.handoff(authoring_issue_id)
            except WorkpaperConflict as exc:
                return {'submitted': False, 'error': str(exc), 'readback': {'tool':'read_authoring_context','arguments':{}}}
        if topic_lead and (not self.workspace or not self.topic_delegate or self.depth >= 3):
            raise ToolException('Topic delegation unavailable or depth reached; use a scoped investigator.')
        if topic_id and not self.workspace:
            raise ToolException('Topic workspace unavailable.')
        if self.workspace:
            request['workpaper_assignment'] = {'parent_topic': self.actor, 'topic_id': topic_id,
                'topic_lead': topic_lead, 'depth': self.depth+1}
            if topic_lead and self.actor == 'root':
                from .research_decision_context import lead_decision
                view = self.workspace.authoring.context(include_unplaced=True, include_history=True)
                compact = lead_decision(view)
                related = {k:compact['judgments'][k] for k,v in view['judgments'].items()
                    if topic_id and any(d['topic_id'] == topic_id for d in v['workpapers'])}
                request['lead_handoff'] = {'understanding_revision':view['revision'],
                    'context_generation':view['context_generation'], 'judgments':related,
                    'original_question':view['question'], 'as_of':view['as_of'], 'readback':compact['readback'],
                    'responsibility':'Own this relationship, delegate investigation, test explanations and save a complete versioned workpaper. '
                        'Existing judgments are revisable. Explain what changed, why, implications and remaining work. '
                        'Do not repeat parent investigation or inherit the entire parent transcript.'}
        original = self.research_question or state.get('question')
        if original:
            request['research_task'] = dict(question=original, as_of=self.as_of,
                review_scope='current_report' if purpose == 'review' and use_report else 'delegated_question')
        if self.workspace and purpose=='review':
            current=self.workspace.authoring.review_handoff()
            previous=[json.loads(p.read_text(encoding='utf8')) for p in self.directory.glob('*.json')]
            since=max((r['request'].get('current_understanding',{}).get('understanding_revision',0)
                for r in previous if r.get('status')=='completed' and r.get('request',{}).get('purpose')=='review'
                and r['request'].get('current_understanding',{}).get('understanding_revision',0)<(current or {}).get('understanding_revision',0)),default=0)
            if since:
                current=self.workspace.authoring.review_handoff(since)
            if current:
                request['current_understanding']=current
        key = canonical_sha256(request)
        path = self.directory / (key + '.json')
        if path.exists():
            record = json.loads(path.read_text(encoding='utf8'))
            # Never restart a lost or failed paid operation from a new tool call.
            if record['status'] == 'running' and key not in self.tasks:
                raise RuntimeError('consultation_interrupted_reconcile_provider_ledger_before_resume')
            if record['status'] == 'failed':
                raise RuntimeError('consultation_failed_requires_recovery:' + key)
            if record['status'] != 'queued' or self.hold_submissions:
                return dict(task_id=key, status=record['status'], reused=True,
                            read_tool='read_research_agent_result',
                            **({'topic_id':record['workpaper_actor']} if record.get('workpaper_actor') else {}))
            return dict(task_id=key, status='queued', worker_started=False,
                next_action='Use start_queued_research_task with current execution context and research question; preparation-only instructions must be replaced before dispatch.')
        active = [(service,k,t) for service in self.family for k,t in service.tasks.items() if not t.done()]
        active_leads = sum(bool(json.loads((service.directory/(k+'.json')).read_text(encoding='utf8'))
                              ['request'].get('workpaper_assignment',{}).get('topic_lead')) for service,k,_ in active)
        if topic_lead and active_leads >= 3:
            return {'submitted':False,'status':'topic_capacity_unavailable',
                    'next_action':'Read a completed topic or wait for an existing topic lead; do not bypass the required decision layer.',
                    'limits':{'active_topic_leads':3}}
        if len(active) >= 8:
            return {'submitted':False, 'status':'capacity_wait', 'host_wait_before_next_model':True,
                    'next_action':'Host waits for active work to finish; then reconsider this assignment or read its completed results.',
                    'limits':{'active_tasks':8,'active_topic_leads':3}}
        if self.workspace:
            actor = topic_id or key
            try:
                self.workspace.register(actor, self.actor, question, reuse=bool(topic_id))
            except ValueError as exc:
                raise ToolException(str(exc)) from exc
            if topic_id and any(not t.done() and json.loads((service.directory/(k+'.json')).read_text(encoding='utf8'))
                    .get('workpaper_actor') == actor for service in self.family for k,t in service.tasks.items()):
                raise ToolException('Topic already running; wait for its current result before continuing.')
        from .source_acquisition_view import acquisition_snapshot
        from .research_actions import research_action_view, research_working_view
        # Freeze observations beside the request, not in its identity: rereading
        # a task result must not create a fresh paid investigation.
        record = dict(request=request, status='queued' if self.hold_submissions else 'running', scope=self.tid+':'+self.rid,
            observations={'acquisition': acquisition_snapshot(state.get('messages', [])),
                          'current_research': research_working_view(state),
                          'prior_actions': research_action_view(state)})
        if self.workspace:
            record['workpaper_actor'] = actor
            record['base_workpaper_revision'] = next(t['current_revision'] or 0 for t in self.workspace.catalog()['topics'] if t['topic_id']==actor)
            # The durable catalog is current; historical adoption prose may predate a changed premise.
            # Keep current note navigation, not copies of every old judgment in the new assignment.
            record['observations']['current_research'] = {
                'workpapers':self.workspace.catalog(),
                'working_notes':record['observations']['current_research']['working_notes'],
                'notice':'Read current complete workpapers and their premises; old task completion or adoption is not current scope clearance.'}
        _persist(path, record)
        if self.hold_submissions:
            return dict(task_id=key, status='queued', worker_started=False,
                        notice='Assignment saved for user inspection. No worker execution; do not poll.',
                        **({'topic_id':actor} if self.workspace else {}))
        self._dispatch(key, record, state)
        return dict(task_id=key, status='running', read_tool='read_research_agent_result',
                    **({'topic_id':actor} if self.workspace else {}))

    def child(self, key):
        allowed = set(review_tool_names([g.tool.name for g in self.grants])) | {'read_saved_result'}
        grants = [g for g in self.grants if g.tool.name in allowed]
        path = self.directory / (key + '.json')
        record = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        request = record.get('request', {})
        if request.get('assessment_contract') == 1 and (not record.get('workpaper_actor') or request.get('purpose')=='review'):
            from .research_actions import assessment_tool
            grants.append(assessment_tool(key, request,
                record.get('observations', {}).get('prior_actions', {}).get('actions', [])))
        if self.workspace and record.get('workpaper_actor'):
            from .research_workpaper_tools import workpaper_tools
            grants.extend(workpaper_tools(self.workspace, record['workpaper_actor'], assignment={
                'task_id':key, 'question':request['question'], 'purpose':request['purpose'],
                **({'authoring_issue_id':request['authoring_issue']['issue']['id']} if request.get('authoring_issue') else {})}))
            if request.get('workpaper_assignment', {}).get('topic_lead'):
                if key not in self.nested:
                    self.nested[key] = HarnessConsultations(directory=self.directory/'topics'/key,
                        saver=self.saver, grants=self.grants, tid=self.tid, rid=self.rid, check=self.check,
                        scope=self.scope, budget=self.budget, environment=self.environment, model=self.model,
                        basis=self.basis, as_of=self.as_of, public_sink=self.public_sink,
                        research_depth=self.research_depth,
                        research_question=self.research_question, native_delegate=self.native_delegate,
                        workspace=self.workspace, actor=record['workpaper_actor'], topic_delegate=self.topic_delegate,
                        depth=self.depth+1, family=self.family)
                grants.extend(self.nested[key].tools())
        bridge = HarnessBusinessTools(grants=grants,
            checkpointer=self.saver, thread_id=self.tid+':consult:'+key,
            check=self.parent.access if self.parent else self.check,
            scope=self.scope, stop_on_tool_error=True)
        if key in self.nested:
            self.nested[key].parent = bridge
        return bridge

    def settled_scope_failure(self, key, record):
        """Explicit recovery may replay received output after a host-scope fault.

        This never authorizes a failed paid request; any unknown/pending usage
        still requires its separate signed recovery. Live grants are rechecked.
        """
        # A pre-dispatch refusal can be replayed on explicit recovery when every
        # existing response in this lane is settled. This grants no dispatch:
        # the provider still checks saved fingerprints and reserve() rechecks
        # current funds, authority and unresolved calls before the next request.
        allowed = {'WorkingMemoryAccessDenied', 'CancelledError', 'DispatchBlocked'}
        executor = self.topic_delegate if record.get('request',{}).get('workpaper_assignment',{}).get('topic_lead') else self.native_delegate
        proof = getattr(executor, 'undispatched_scope', None)
        undispatched = bool(callable(proof) and proof(key, record['scope']))
        if undispatched:
            allowed.add('RuntimeError')
        unstarted = (record.get('error_type') in {'KeyError', 'CancelledError', 'ExceptionGroup', 'BaseExceptionGroup'}
            and record.get('request', {}).get('workpaper_assignment', {}).get('topic_lead')
            and callable(getattr(self.topic_delegate, 'unstarted_scope', None))
            and self.topic_delegate.unstarted_scope(key, record['scope']))
        if unstarted:
            allowed.add(record['error_type'])
        if self.native_delegate:
            # MCP/AnyIO teardown wraps a cancelled native child in a group.
            # Explicit recovery still requires every child dispatch settled;
            # a parent's unknown call is separately gated by run admission.
            allowed |= {'ExceptionGroup', 'BaseExceptionGroup'}
        if record.get('error_type') == 'RuntimeError' and self.native_delegate:
            executor = self.topic_delegate if record.get('request',{}).get('workpaper_assignment',{}).get('topic_lead') else self.native_delegate
            completed = getattr(executor, 'completed_result', None)
            if (callable(completed) and record['scope'].startswith(self.tid+':')
                    and completed(key, record['scope'])):
                allowed.add('RuntimeError')
        if record.get('error_type') not in allowed:
            return False
        if getattr(self.budget, 'store', None) is None:
            return False
        self.check()
        with self.budget.store.connection() as db:
            rows = db.execute('''SELECT status, actual_micros, response FROM fin_model_dispatch
                WHERE owner_id=%s AND budget_id=%s AND basis->>'harness_execution_scope'=%s
                AND basis->>'harness_dispatch_lane'=%s''',
                (self.budget.owner, self.budget.budget, record['scope'], 'consult:'+key)).fetchall()
        if unstarted:
            return not rows
        if undispatched:
            return not rows
        if not rows and self.native_delegate:
            executor = self.topic_delegate if record.get('request',{}).get('workpaper_assignment',{}).get('topic_lead') else self.native_delegate
            check = getattr(executor, 'unreserved_scope', None)
            return bool(callable(check) and check(key, record['scope']))
        return bool(rows) and all(r['status']=='received' and type(r['actual_micros']) is int
            and isinstance(r['response'], dict) and not r['response'].get('stop_required', True) for r in rows)

    def authorized_provider_failure(self, key, record, permit):
        """Admit a stopped transport failure only against its signed unknown-call set.

        The provider replay still checks the exact saved request before retrying.
        This does not settle the unknown charge or admit an in-flight request.
        """
        errors = {
                'ConnectError', 'ConnectTimeout', 'ReadTimeout', 'WriteTimeout',
                'PoolTimeout', 'ReadError', 'WriteError', 'RemoteProtocolError', 'HTTPStatusError'}
        if self.native_delegate:
            errors |= {'ExceptionGroup', 'BaseExceptionGroup'}
        if (not permit or record.get('error_type') not in errors
                or getattr(self.budget, 'store', None) is None):
            return False
        self.check()
        with self.budget.store.connection() as db:
            rows = db.execute('''SELECT call_id, call_key, status, actual_micros, response FROM fin_model_dispatch
                WHERE owner_id=%s AND budget_id=%s AND basis->>'harness_execution_scope'=%s
                AND basis->>'harness_dispatch_lane'=%s''',
                (self.budget.owner, self.budget.budget, record['scope'], 'consult:'+key)).fetchall()
        authorized = set(permit.get('unknown_call_ids', []))
        def authorized_unknown(row):
            if row['actual_micros'] is not None:
                return False
            if row['status'] == 'unknown':
                return str(row['call_id']) in authorized
            # Native ACP records a terminal partial response as received with
            # NULL cost. Its public audit identifies the native request UUID,
            # while the ledger's call_id is a different database UUID.
            prefix = record['scope'] + ':'
            call_key = row.get('call_key', '')
            return bool(self.native_delegate and row['status'] == 'received'
                and isinstance(row['response'], dict) and row['response'].get('stop_required') is True
                and call_key.startswith(prefix) and call_key[len(prefix):] in authorized)
        return any(authorized_unknown(r) for r in rows) and all(
            authorized_unknown(r)
            or (r['status'] == 'received' and type(r['actual_micros']) is int
                and isinstance(r['response'], dict) and not r['response'].get('stop_required', True))
            for r in rows)

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
                      and r['status'] not in {'completed', 'queued'}]
        if not candidates:
            return
        for path, record in candidates:
            stopped_record = record
            scope_replay = await asyncio.to_thread(self.settled_scope_failure, path.stem, record)
            origin_thread, origin_run = record['scope'].split(':')
            permit = verified_permit(audit_root,origin_thread,origin_run,
                secret=self.environment['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'])
            provider_retry = await asyncio.to_thread(self.authorized_provider_failure, path.stem, record, permit)
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
            if record.get('error_type') != 'CancelledError' and not failed_read and not scope_replay and not provider_retry:
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
            if not permit and not failed_read and not scope_replay:
                raise RuntimeError('consultation_recovery_requires_explicit_paid_retry_authorization')
            provider_retry = await asyncio.to_thread(self.authorized_provider_failure, path.stem, record, permit)
            if record.get('error_type') != 'CancelledError' and not failed_read and not scope_replay and not provider_retry:
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
                previous_scope=previous_scope,audit_root=audit_root), context=self.execution_context.copy())

    async def run(self, key, record, initial, body, *, previous_scope=None, audit_root=None):
        request = record['request']
        try:
            child = self.child(key)
            # A signed recovery may have stopped inside a read, between two
            # provider calls. The shared bridge resumes only that pending read;
            # completed reads stay in the checkpoint and writes remain blocked.
            failed_ids = None
            if previous_scope and self.native_delegate:
                from .harness_business_tools import failed_run_receipts
                executor = self.topic_delegate if request.get('workpaper_assignment',{}).get('topic_lead') else self.native_delegate
                directory = getattr(executor,'directory',None)
                if directory is not None:
                    failed_ids = failed_run_receipts(Path(directory)/key/previous_scope.split(':',1)[1]/'events.private.jsonl')
            recovery = await child.initialize(initial, recovering=previous_scope is not None,
                                             **({'failed_receipt_ids':failed_ids} if failed_ids else {}))
            if previous_scope and key in self.nested:
                await self.nested[key].recover_cancelled(previous_scope.split(':',1)[1], audit_root)
            selected = Challenge(version=version(body), quote='', offset=0, question=request['question'])
            # Old paid recovery keeps its original protocol. New assignments
            # receive actual acquisition/disposition state, not a guessed scope score.
            input_request = {**request}
            if 'observations' in record:
                input_request['research_task'] = {**request.get('research_task', {}),
                    'observations': self.scoped_observations(record['observations']) if self.workspace else record['observations']}
            if self.native_delegate:
                executor = self.topic_delegate if request.get('workpaper_assignment',{}).get('topic_lead') else self.native_delegate
                input_request['current_topic_id'] = record.get('workpaper_actor')
                opinion = await executor(key=key, request=input_request, bridge=child,
                    previous_scope=previous_scope, audit_root=audit_root, recovery_receipt=recovery,
                    consultations=self.nested.get(key))
            else:
                opinion = await independent_review(selected=selected,
                message=AIMessage(content=body), question=request['question']+'\n'+request['context'],
                bridge=child, budget=self.budget, environment=self.environment, model=self.model,
                scope=record['scope'], command_id='consult-'+key, authority=child.model_access,
                basis=self.basis, as_of=self.as_of, public_sink=self.public_sink,
                assignment_kind=request['purpose'], method_content=request['method_text'], method_options=request,
                **({'research_task':input_request['research_task']} if 'research_task' in input_request else {}),
                dispatch_lane='consult:'+key,previous_scope=previous_scope,audit_root=audit_root)
            self.check()
            from .research_actions import latest_assessment
            # Native process teardown stops its bridge. Read its durable journal
            # through a fresh host reader with current parent authority; never
            # reopen the stopped process's model/tool admission.
            final_messages = (await self.child(key).state()).get('messages', [])
            assessment = latest_assessment(final_messages, key)
            if self.workspace and record.get('workpaper_actor'):
                self.workspace.archive_execution_observations(record['workpaper_actor'], final_messages)
                # Native final text is also durably retained below. Explicit published analysis is
                # required for topic handoff; a short terminal reply cannot stand in for a workpaper.
                current = self.workspace.catalog()['topics']
                revision = next(t['current_revision'] or 0 for t in current if t['topic_id']==record['workpaper_actor'])
                if revision <= record.get('base_workpaper_revision',0):
                    record = {**record, 'unpublished_opinion':opinion}
                    raise RuntimeError('research_workpaper_missing_before_handoff')
                published = self.workspace.read(self.actor, record['workpaper_actor'], revision, field='metadata')
                record = {**record, 'workpaper_ref':{k:published[k] for k in ('topic_id','revision','digest')},
                          'execution_archive_version':2}
            _persist(self.directory/(key+'.json'), {**record,'status':'completed','opinion':opinion,
                **({'assessment':assessment} if assessment else {})})
        except BaseException as exc:
            _persist(self.directory/(key+'.json'), {**record,'status':'failed','error_type':type(exc).__name__,
                **({'failure_code':str(exc)} if isinstance(exc,DispatchBlocked) or
                   (isinstance(exc,(ValueError,RuntimeError))
                    and str(exc).startswith(('answer_review_','harness_business_tool_')) or
                    isinstance(exc, RuntimeError) and str(exc) == 'harness_execution_stopped') else {})})
            if self.parent:
                self.parent.failed_receipt = 'consult-'+key
            raise

    async def archive_task_execution(self, key, state=None):
        """Backfill legacy completed descendants from their scoped checkpoints, without rerunning tools."""
        self.check()
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('invalid_task_identity')
        record = json.loads((self.directory/(key+'.json')).read_text(encoding='utf8'))
        if not self.workspace or record['status'] != 'completed' or not record.get('workpaper_actor'):
            return []
        child = self.child(key)
        if record.get('execution_archive_version',0) < 2:
            state = state if state is not None else await child.state()
            self.workspace.archive_execution_observations(record['workpaper_actor'], state.get('messages', []))
            _persist(self.directory/(key+'.json'), {**record, 'execution_archive_version':2})
        entries = self.workspace.execution_readbacks(record['workpaper_actor'])
        if key in self.nested:
            nested = self.nested[key]
            for path in sorted(nested.directory.glob('*.json')):
                row = json.loads(path.read_text(encoding='utf8'))
                if row.get('status') == 'completed':
                    entries.extend(await nested.archive_task_execution(path.stem))
        self.check()
        return list({e['receipt_id']: e for e in entries}.values())

    async def read(self, key, wait, runtime):
        self.check()
        if len(key) != 64 or any(c not in '0123456789abcdef' for c in key) or not 0 <= wait <= 20:
            raise ToolException('Use the returned task_id; wait_seconds must be 0-20.')
        path = self.directory/(key+'.json')
        if not path.exists():
            return self.result_selection(key)
        task = self.tasks.get(key)
        if task and not task.done():
            await asyncio.wait({task}, timeout=wait)
        if task and task.done():
            task.result()
        record = json.loads(path.read_text(encoding='utf8'))
        if record['status'] == 'queued':
            return dict(task_id=key, status='queued', worker_started=False,
                        assignment={k:record['request'].get(k) for k in ('question','context','research_task','purpose','methods')},
                        next_action=('Await user inspection; no worker is running. Do not poll.' if self.hold_submissions else
                            'Use start_queued_research_task to replace preparation-only context with the current execution assignment.'))
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
        if self.workspace and record.get('workpaper_actor'):
            execution = await self.archive_task_execution(key, child_state)
            result['execution_readback'] = {'archived_records':len(execution),
                'tool':'read_research_execution','arguments':{},
                'notice':'Acquisition records include nested tasks; use topic_id to narrow. Not financial evidence.'}
            actor = record['workpaper_actor']
            ref = record['workpaper_ref']
            current = self.workspace.read(self.actor, actor, ref['revision'], field='metadata')
            if current['digest'] != ref['digest']:
                raise RuntimeError('consultation_workpaper_identity_mismatch')
            result.pop('opinion')
            result['workpaper'] = current
            result['workpaper_readback'] = {'tool':'read_research_workpaper', 'arguments':{'topic_id':actor,'revision':current['revision']}}
            # Full child journal stays in its checkpoint. Evidence is imported only when requested.
            messages = []
            result['source_readback'] = [{'tool':'read_workpaper_evidence','arguments':{'receipt_id':e}}
                                       for e in current['evidence_receipt_ids']]
            if self.workspace.organization_policy().get('root_investigations_require_topic_lead') and not self.workspace.authoring_active():
                from .research_decision_context import paper_decision
                from .assessment_evidence import current_counterexamples
                result['workpaper'] = paper_decision(current)
                # Existing callers can still select a source directly by its receipt ID.
                # Only the expanded per-source navigation moves behind the metadata read.
                result['workpaper']['evidence_receipt_ids'] = current['evidence_receipt_ids']
                with self.workspace.connection() as db:
                    result['reviewed_counterexamples'] = current_counterexamples(self.workspace, db,
                        [(actor,current['revision'],current['digest'])],descend=True)
                result['assigned_relationship'] = record['request'].get('question') or current['original_task']['question']
                result['original_question'] = current['original_task']['root_question']
                result['source_readback'] = [result['workpaper']['readback']]
        result['assessment'] = record.get('assessment')
        from .research_result_acceptance import result_version
        result['result_digest'] = result_version(record)
        result['acceptance_tool'] = 'assess_research_result'
        result['assessment_status'] = 'recorded_model_judgment' if result['assessment'] else 'not_recorded_no_scope_clearance'
        if result['assessment']:
            result['action_readback'] = {'tool':'read_current_report','arguments':{'field':'research_actions'}}
            result['next_action'] = ('Investigate material issues, then decide the current answer. Save the report and '
                'use respond_research_action to bind each disposition to actual wording. A rebuttal is allowed; '
                'unresolved gaps must remain explicit. Returning an opinion or saving prose does not resolve an issue.')
        if record['request']['purpose'] == 'review':
            from .answer_review import report_revision_task
            result['author_task'] = report_revision_task()
        return Command(update={'messages':[*messages, ToolMessage(name='read_research_agent_result',
            tool_call_id=runtime.tool_call_id, content=json.dumps(result,ensure_ascii=False))]})

    async def dispatch_ready(self, timeout=20, *, parent_dispatch=None):
        """Wait outside model dispatch and its financial reservation.

        Explicit result reads suspend the author. Near the shared budget limit,
        also wait for active native children instead of cancelling paid work
        when the next author reservation fails. Derive
        the wait from durable receipts so cancel/recovery cannot forget it. The
        private host endpoint long-polls small state, never the large LLM request.
        """
        await asyncio.to_thread(self.check)
        waiting = {}
        any_wait = []
        capacity_wait = False
        if self.parent:
            for message in (await self.parent.state()).get('messages', []):
                if isinstance(message,ToolMessage) and message.name=='consult_research_agent' and message.status=='success':
                    capacity_wait=json.loads(message.content).get('status')=='capacity_wait'
                if isinstance(message, ToolMessage) and message.name == 'read_next_research_result' and message.status == 'success':
                    any_wait = json.loads(message.content).get('pending_task_ids', [])
                if isinstance(message, ToolMessage) and message.name == 'read_research_agent_result' and message.status == 'success':
                    result = json.loads(message.content)
                    if isinstance(result, dict) and result.get('task_id'):
                        waiting[result['task_id']] = result.get('status') != 'completed'
        tasks = []
        if capacity_wait:
            active=[t for service in self.family for t in service.tasks.values() if not t.done()]
            # The caller is itself a task in its parent's service. Waiting for all would deadlock.
            active=[t for t in active if t is not asyncio.current_task()]
            if len(active) >= 8:
                done,_=await asyncio.wait(active,timeout=timeout,return_when=asyncio.FIRST_COMPLETED)
                for t in done:
                    t.result()
                if not done:
                    return {'status':'waiting'}
        if any_wait:
            pending = [self.tasks[k] for k in any_wait if k in self.tasks]
            completed_saved = False
            for key in any_wait:
                if key in self.tasks:
                    continue
                # Successful predecessors are not spawned again on recovery.
                # Their durable completion can satisfy an old wait-any receipt.
                if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
                    raise RuntimeError('consultation_interrupted_reconcile_provider_ledger_before_resume')
                path = self.directory/(key+'.json')
                record = json.loads(path.read_text(encoding='utf8')) if path.is_file() else {}
                if record.get('status') != 'completed' or not record.get('scope','').startswith(self.tid+':'):
                    raise RuntimeError('consultation_interrupted_reconcile_provider_ledger_before_resume')
                completed_saved = True
            if not completed_saved and not any(t.done() for t in pending):
                await asyncio.wait(pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                if t.done():
                    t.result()
            if not completed_saved and not any(t.done() for t in pending):
                return {'status':'waiting'}
        for key, pending in waiting.items():
            if not pending:
                continue
            task = self.tasks.get(key)
            if task is None:
                record = json.loads((self.directory/(key+'.json')).read_text(encoding='utf8'))
                # Reading a saved assignment precedes start_queued. Lifting
                # the hold does not turn that never-started task into an
                # interrupted paid worker; the author must remain runnable.
                if record['status'] == 'queued':
                    continue
                if record['status'] != 'completed':
                    raise RuntimeError('consultation_interrupted_reconcile_provider_ledger_before_resume')
            else:
                tasks.append(task)
        active = [task for task in self.tasks.values() if not task.done()]
        if active and parent_dispatch is not None and self.native_delegate is not None:
            snapshot = await asyncio.to_thread(parent_dispatch.store.snapshot,
                parent_dispatch.owner, parent_dispatch.budget)
            # A child can settle and reserve between ready and reserve. Leave
            # room for each active child's next request, not just current holds.
            child_reservations = 0
            for key, task in self.tasks.items():
                if task.done():
                    continue
                record = json.loads((self.directory/(key+'.json')).read_text(encoding='utf8'))
                executor = self.topic_delegate if record['request'].get('workpaper_assignment',{}).get('topic_lead') else self.native_delegate
                child_reservations += executor.options['reservation_micros']
            required = (parent_dispatch.reservation + child_reservations
                        + snapshot['delivery_floor_micros'])
            if snapshot['available_micros'] < required:
                tasks.extend(task for task in active if task not in tasks)
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        await asyncio.to_thread(self.check)
        for task in tasks:
            if task.done():
                task.result()  # failure closes admission; never a fake completion
        return {'status': 'waiting' if any(not t.done() for t in tasks) else 'ready'}

    async def ensure_finished(self):
        if any(not task.done() for task in self.tasks.values()):
            raise RuntimeError('consultation_pending_at_delivery')
        for task in self.tasks.values():
            task.result()
        # Restarted services may have durable jobs without in-memory asyncio tasks.
        allowed = {'completed', 'queued'} if self.hold_submissions else {'completed'}
        if any(json.loads(p.read_text(encoding='utf8'))['status'] not in allowed
               for p in self.directory.glob('*.json')):
            raise RuntimeError('consultation_unfinished_persisted_at_delivery')

    async def close(self):
        for service in self.nested.values():
            await service.close()
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
