"""Versioned FIN artifact operations reused by the ACP tool host."""
import json
from typing import Literal, Annotated
from pydantic import Field

from langchain_core.tools import tool, ToolException
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from .conversation_agent import GrantedTool
from .report_synthesis_agent import bind_report_candidate, apply_report_edits, ReportTextEdit, ReportEditMatchError, report_model_view, patch_report_fields
from .research_graph_contracts import canonical_sha256
from .delegated_task_tools import saved_note_artifact
from .report_synthesis_agent import CaseReport


def artifact_tools(*, artifacts, memory, delivery_intent, require_review):
    def accepted(runtime, report):
        version = runtime.state.get('report_version', 0) + 1
        result = {'saved': True, 'report_version': version, 'digest': canonical_sha256(report),
                  'review_status': 'not_assessed_in_this_record'}
        from .conversation_tools import calculator_observations
        from .quantitative_prose import audit_changes, sentence_edits
        def wording(value):
            return '\n'.join([value.get('title', ''), value.get('narrative_markdown', ''),
                *[chart.get('interpretation', '') for chart in value.get('charts', [])]])
        previous = wording(runtime.state.get('report') or {})
        current = wording(report)
        check = audit_changes(previous, current, calculator_observations(runtime.state.get('messages', [])))
        check['coverage'] = {'report_version':version, 'report_digest':result['digest'],
            'basis':'actual_saved_version_diff',
            'changed_sentences':len(list(sentence_edits(previous, current))),
            'financial_semantics_verified':False}
        result['quantitative_change_check'] = check
        from .revision_context import consultation_revision_context
        context = consultation_revision_context(runtime.state.get('messages', []),
            runtime.state.get('report', {}).get('narrative_markdown', ''), report['narrative_markdown'],
            runtime.state.get('active_report_review'),
            original_title=runtime.state.get('report', {}).get('title',''), candidate_title=report['title'])
        if context:
            result['revision_context'] = context
        from .research_actions import research_action_view
        actions = research_action_view({**runtime.state, 'report':report, 'report_version':version})
        if actions['actions'] or actions['unstructured_results']:
            result['research_actions'] = {'pending_material':actions['pending_material'],
                'readback':actions['readback'], 'status':'saving_does_not_resolve_research_issues'}
        return Command(update={'report': report, 'report_version': version, 'report_draft': None,
            'report_draft_base_version': None, 'delivery': None,
            'messages': [ToolMessage(tool_call_id=runtime.tool_call_id, content=json.dumps(result, ensure_ascii=False))]})

    def save_candidate(report, base_version, runtime):
        if base_version != runtime.state.get('report_version', 0):
            raise ToolException('report_version_changed_read_current_report')
        try:
            bound = bind_report_candidate(report, artifacts(runtime.state), runtime.state)
        except ValueError as exc:
            return Command(update={'report_draft': report, 'report_draft_base_version': base_version,
                'messages': [ToolMessage(tool_call_id=runtime.tool_call_id, status='error', content=json.dumps({
                    'status': 'draft_saved_needs_repair', 'error': str(exc), 'base_version': base_version,
                    'next_tool': 'repair_report_fields',
                    'readback': {'tool': 'read_current_report', 'arguments': {'view': 'draft'}},
                    'schema_readback': {'tool': 'read_current_report', 'arguments': {'field': 'schema'}},
                    'remedy': 'Send changed fields only; original draft is saved, not accepted.'}))]})
        return accepted(runtime, bound)

    @tool
    def save_research_report(report: dict, base_version: int, runtime: ToolRuntime) -> Command:
        """Save report={title: string (5-250 chars), narrative_markdown: string (200-80000 chars), charts: optional array}.
        Use current base_version (0 for new); exact observed IDs in brackets retain citation bindings.
        Use Markdown tables for comparisons and blockquotes for short explanatory notes beside
        the relevant discussion. Choose charts when a visual comparison or trend clarifies the
        answer; charts are optional, not a quota. after_heading selects the exact section heading
        text (without #) after whose content the chart appears, instead of collecting all charts
        at the end. Charts use title, kind (bar/line), unit, scale_divisor (1/1000/1000000/1000000000),
        interpretation, points [{label, series?, source:{source_id, literal?, quote?}}].
        Prose sources require a decimal literal and its exact contiguous quote; structured numeric
        facts or saved calculations need only source_id. Values are resolved by the host, not a
        caller-supplied value or parallel sources array. read_current_report(field="schema") gives
        the full contract. Saving is not delivery or independent review. Use edit_research_report
        for local text changes; repair_report_fields for structured fields of the current report.
        """
        return save_candidate(report, base_version, runtime)

    @tool
    def repair_report_fields(fields: dict, base_version: int, runtime: ToolRuntime) -> Command:
        """Change field paths (e.g. title, charts, charts.0.unit) at current base_version.
        Uses the pending unaccepted draft if present, otherwise the accepted current report.
        Unchanged prose and source bindings remain; all schema and source checks run again.
        Invalid candidates are retained as drafts, not accepted or delivered. Read the current
        fields with read_current_report, or field="schema" for the full chart/source contract.
        Do not resend unchanged prose.
        """
        if base_version != runtime.state.get('report_version', 0):
            raise ToolException('report_version_changed_read_current_report')
        draft = runtime.state.get('report_draft')
        if draft:
            if base_version != runtime.state.get('report_draft_base_version'):
                raise ToolException('report_draft_version_changed_read_current_report')
        elif runtime.state.get('report'):
            current = report_model_view(runtime.state['report'])
            draft = {key: current[key] for key in ('title', 'narrative_markdown', 'charts') if key in current}
        else:
            raise ToolException('no_saved_report_or_draft_use_save_research_report')
        try:
            candidate = patch_report_fields(draft, fields)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ToolException(str(exc)) from exc
        return save_candidate(candidate, base_version, runtime)

    @tool
    def read_current_report(runtime: ToolRuntime, offset: Annotated[int, Field(ge=0, description='Character offset; follow next_offset to continue.')] = 0,
                            max_characters: Annotated[int, Field(ge=1, le=12000, description='Read 1–12000 characters per page; follow next_offset for remaining text.')] = 6000,
                            view: Literal['accepted', 'draft'] = 'accepted',
                            field: Literal['narrative_markdown', 'title', 'charts', 'all', 'schema', 'review', 'revision_context', 'research_actions', 'synthesis_context'] = 'narrative_markdown'):
        """Read exact report fields for editing. Default is unescaped narrative prose.

        view=draft reads the saved but unaccepted proposal for repair_report_fields;
        view=accepted reads the saved version for text or structured field changes. A draft is
        not accepted or delivered. field=all returns the serialized author fields;
        field=schema returns the full submission contract, including chart point sources.
        field=review reads the actual current version-bound independent opinion and target digest.
        field=revision_context reads saved change batches and possible related current wording,
        including untouched headings/conclusions, with opinion readback. Paginated navigation,
        not semantic approval; historical batches can be superseded by later edits.
        field=research_actions reads imported research gaps, concrete next actions and author
        dispositions at the current version. Missing assessment is not scope clearance.
        field=synthesis_context works before and after drafting: current question/version,
        current note pointers, investigation findings, action dispositions, exact repeated reads
        and evidence/revision readback. Use it at a handoff or synthesis decision, not after
        every read. Counts are not research adequacy; it does not certify the author's thesis.
        """
        if field in ('research_actions', 'synthesis_context'):
            from .research_actions import research_action_view, synthesis_working_view
            value = (synthesis_working_view(runtime.state) if field == 'synthesis_context'
                     else research_action_view(runtime.state))
            text = json.dumps(value, ensure_ascii=False)
            return {'field':field, 'report_version':runtime.state.get('report_version',0),
                'text':text[offset:offset+max_characters], 'offset':offset,'total_characters':len(text),
                'next_offset':offset+max_characters if offset+max_characters<len(text) else None}
        if field == 'revision_context':
            if view != 'accepted': raise ToolException('revision_context_requires_accepted_view')
            from .revision_context import current_revision_view
            value=current_revision_view(runtime.state)
            text=json.dumps(value,ensure_ascii=False)
            return {'field':field,'found':value['found'],'report_version':runtime.state.get('report_version',0),
                'text':text[offset:offset+max_characters],'offset':offset,'total_characters':len(text),
                'next_offset':offset+max_characters if offset+max_characters<len(text) else None}
        if field == 'schema':
            return {'schema': CaseReport.model_json_schema(),
                    'report_version': runtime.state.get('report_version', 0),
                    'chart_source_rule': 'Each point binds its own source. Prose requires literal and exact quote; structured numeric facts or saved calculations can omit them. The host resolves values; never submit display values as source bindings.'}
        if field == 'review':
            review=runtime.state.get('active_report_review')
            if not review:return {'found':False,'field':'review'}
            text=review['opinion']
            return {'found':True,'field':'review','reviewer':review['reviewer'],
                'reviewed_report_digest':review['reviewed_report_digest'],'text':text[offset:offset+max_characters],
                'total_characters':len(text),'offset':offset,
                'next_offset':offset+max_characters if offset+max_characters<len(text) else None,
                'status':'independent_opinion_not_approval_of_current_revision'}
        report = runtime.state.get('report_draft' if view == 'draft' else 'report')
        if not report:
            return {'found': False, 'view': view, 'report_version': runtime.state.get('report_version', 0)}
        fields = report if view == 'draft' else report_model_view(report)
        value = fields if field == 'all' else fields.get(field, '')
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return {'found': True, 'view': view, 'field': field, 'accepted': view == 'accepted',
                'report_version': runtime.state.get('report_version', 0),
                'base_version': runtime.state.get('report_draft_base_version') if view == 'draft' else runtime.state.get('report_version', 0),
                'digest': canonical_sha256(report), 'total_characters': len(text),
                'text': text[offset:offset+max_characters], 'offset': offset,
                'next_offset': offset+max_characters if offset+max_characters < len(text) else None}

    @tool
    def edit_research_report(base_version: int, edits: list[ReportTextEdit], runtime: ToolRuntime) -> Command:
        """Apply local old_str/new_str edits to current report version; unchanged prose and sources remain.
        Read exact current text first. Ambiguous text or a changed version returns feedback, never guesses.
        """
        if base_version != runtime.state.get('report_version', 0) or not runtime.state.get('report'):
            raise ToolException('report_version_changed_read_current_report')
        try:
            candidate = apply_report_edits(runtime.state['report'], edits)
            bound = bind_report_candidate(candidate, artifacts(runtime.state), runtime.state)
        except ReportEditMatchError as exc:
            feedback = {**exc.feedback, 'report_version': base_version,
                'readback': {'tool': 'read_current_report', 'arguments': {
                    'field': 'charts' if exc.feedback['chart_index'] is not None else 'narrative_markdown',
                    'offset': 0 if exc.feedback['chart_index'] is not None else next(
                        (c['offset'] for c in exc.feedback['candidates']), 0), 'max_characters': 3000}}}
            # Expected edit conflict, not a provider/storage failure. The saved
            # proposal remains in the tool ledger; no artifact or version changes.
            return Command(update={'messages': [ToolMessage(tool_call_id=runtime.tool_call_id,
                content=json.dumps(feedback, ensure_ascii=False))]})
        except ValueError as exc:
            raise ToolException(str(exc)) from exc
        return accepted(runtime, bound)

    @tool
    def deliver_working_note(note_id: str, version: int, runtime: ToolRuntime) -> Command:
        """Deliver an already saved working note at its current version. Do not resend the body."""
        if delivery_intent != 'workpaper':
            raise ToolException('requested_delivery_is_not_workpaper')
        artifact = saved_note_artifact(memory, note_id, version)
        value = {'execution_status': 'submitted', 'artifact_kind': 'workpaper', 'artifact_id': note_id,
                 'artifact_version': version, 'artifact_digest': artifact['digest'], 'review_status': 'not_assessed_in_this_record'}
        return Command(update={'delivery': value, 'messages': [ToolMessage(tool_call_id=runtime.tool_call_id,
            content=json.dumps(value))]})

    @tool
    def deliver_current_report(version: int, runtime: ToolRuntime) -> Command:
        """Deliver the saved current report. Imported material research actions need current-version
        author dispositions through respond_research_action; this is not independent approval.
        Unresolved issues can be disclosed, or reasoned rebuttals retained; no automatic research loop.
        """
        if delivery_intent != 'report':
            raise ToolException('requested_delivery_is_not_report')
        report = runtime.state.get('report')
        if not report or version != runtime.state.get('report_version'):
            raise ToolException('report_version_changed_read_current_report')
        if require_review:
            raise ToolException('independent_report_review_not_yet_qualified_in_harness_adapter')
        from .research_actions import research_action_view
        actions = research_action_view(runtime.state)
        if actions['pending_material']:
            return Command(update={'messages':[ToolMessage(tool_call_id=runtime.tool_call_id,
                content=json.dumps({'delivered':False, 'status':'research_actions_need_disposition',
                    'pending_material':actions['pending_material'], 'readback':actions['readback'],
                    'next_tool':'respond_research_action',
                    'meaning':'Resolve, rebut or disclose actual remaining limits in the report. No financial verdict or mandatory new search.'}))]})
        value = {'execution_status': 'submitted', 'artifact_kind': 'report', 'artifact_id': 'report',
                 'artifact_version': version, 'artifact_digest': canonical_sha256(report),
                 'review_status': 'not_assessed_in_this_record'}
        value['research_action_status'] = {'recorded':len(actions['actions']),
            'unstructured_results':len(actions['unstructured_results']),
            'independent_clearance':False,
            'awaiting_independent_resolution':actions['awaiting_independent_resolution'],
            'unresolved':[a['action_id'] for a in actions['actions']
                if (a['author_response'] or {}).get('disposition') == 'unresolved']}
        # Only this exact version's save receipt is relevant. An earlier manual
        # preview does not certify edits performed after it.
        for message in reversed(runtime.state.get('messages', [])):
            if not isinstance(message, ToolMessage) or message.status != 'success':
                continue
            try:
                receipt = json.loads(message.content)
            except (ValueError, TypeError):
                continue
            if (isinstance(receipt, dict) and receipt.get('saved') is True
                    and receipt.get('report_version') == version
                    and receipt.get('digest') == value['artifact_digest']):
                check = receipt.get('quantitative_change_check')
                if check:
                    value['quantitative_change_check'] = {
                        'coverage':check['coverage'], 'findings':check['findings'],
                        'status':'advisory_not_financial_approval'}
                break
        if runtime.state.get('active_report_review'):
            value['revision_context_readback']={'tool':'read_current_report','arguments':{'field':'revision_context'}}
            value['reviewed_report_digest']=runtime.state['active_report_review']['reviewed_report_digest']
        return Command(update={'delivery': value, 'messages': [ToolMessage(tool_call_id=runtime.tool_call_id,
            content=json.dumps(value))]})
    tools = [save_research_report, repair_report_fields, read_current_report, edit_research_report]
    if delivery_intent == 'workpaper':
        tools.append(deliver_working_note)
    elif delivery_intent == 'report' and not require_review:
        tools.append(deliver_current_report)
    for t in tools:
        t.handle_tool_error = True
    from .research_actions import author_action_tool
    return [author_action_tool(), *[GrantedTool(t, 'read' if t is read_current_report else 'task_artifact_write',
                       '当前任务版本化成果；不代表独立复核',
                       recovery_semantics='checkpoint_only' if t in (
                           save_research_report, repair_report_fields, edit_research_report, deliver_current_report) else 'manual')
            for t in tools]]
