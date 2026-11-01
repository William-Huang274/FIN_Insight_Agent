"""Versioned FIN artifact operations reused by the ACP tool host."""
import json

from langchain_core.tools import tool, ToolException
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from .conversation_agent import GrantedTool
from .report_synthesis_agent import bind_report_candidate, apply_report_edits, ReportTextEdit, report_model_view, patch_report_fields
from .research_graph_contracts import canonical_sha256
from .delegated_task_tools import saved_note_artifact


def artifact_tools(*, artifacts, memory, delivery_intent, require_review):
    def accepted(runtime, report):
        version = runtime.state.get('report_version', 0) + 1
        result = {'saved': True, 'report_version': version, 'digest': canonical_sha256(report),
                  'review_status': 'not_assessed_in_this_record'}
        return Command(update={'report': report, 'report_version': version, 'report_draft': None,
            'report_draft_base_version': None, 'delivery': None,
            'messages': [ToolMessage(tool_call_id=runtime.tool_call_id, content=json.dumps(result))]})

    def save_candidate(report, base_version, runtime):
        if base_version != runtime.state.get('report_version', 0):
            raise ToolException('report_version_changed_read_current_report')
        try:
            bound = bind_report_candidate(report, artifacts(runtime.state), runtime.state)
        except ValueError as exc:
            return Command(update={'report_draft': report, 'report_draft_base_version': base_version,
                'messages': [ToolMessage(tool_call_id=runtime.tool_call_id, status='error', content=json.dumps({
                    'status': 'draft_saved_needs_repair', 'error': str(exc), 'base_version': base_version,
                    'next_tool': 'repair_report_fields', 'remedy': 'Send changed fields only; original draft is saved, not accepted.'}))]})
        return accepted(runtime, bound)

    @tool
    def save_research_report(report: dict, base_version: int, runtime: ToolRuntime) -> Command:
        """Save report={title: string (5-250 chars), narrative_markdown: string (200-80000 chars), charts: optional array}.
        Use current base_version (0 for new); exact observed IDs in brackets retain citation bindings.
        Saving is not delivery or independent review. For later local edits use edit_research_report.
        """
        return save_candidate(report, base_version, runtime)

    @tool
    def repair_report_fields(fields: dict, base_version: int, runtime: ToolRuntime) -> Command:
        """Repair fields in the saved unaccepted draft (e.g. title or charts.0.unit). Do not resend unchanged prose."""
        draft = runtime.state.get('report_draft')
        if not draft or base_version != runtime.state.get('report_draft_base_version'):
            raise ToolException('no_pending_report_draft_at_this_base_version')
        try:
            candidate = patch_report_fields(draft, fields)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ToolException(str(exc)) from exc
        return save_candidate(candidate, base_version, runtime)

    @tool
    def read_current_report(runtime: ToolRuntime, offset: int = 0, max_characters: int = 6000):
        """Read current report prose and version in exact windows; no model-generated summary."""
        report = runtime.state.get('report')
        if not report:
            return {'found': False, 'report_version': 0}
        if offset < 0 or not 1 <= max_characters <= 12000:
            raise ToolException('invalid_read_window')
        text = json.dumps(report_model_view(report), ensure_ascii=False)
        return {'found': True, 'report_version': runtime.state['report_version'], 'digest': canonical_sha256(report),
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
            candidate = apply_report_edits(report_model_view(runtime.state['report']), edits)
            bound = bind_report_candidate(candidate, artifacts(runtime.state), runtime.state)
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
        """Deliver the saved current report; no prose resubmission and no claim of independent approval."""
        if delivery_intent != 'report':
            raise ToolException('requested_delivery_is_not_report')
        report = runtime.state.get('report')
        if not report or version != runtime.state.get('report_version'):
            raise ToolException('report_version_changed_read_current_report')
        if require_review:
            raise ToolException('independent_report_review_not_yet_qualified_in_harness_adapter')
        value = {'execution_status': 'submitted', 'artifact_kind': 'report', 'artifact_id': 'report',
                 'artifact_version': version, 'artifact_digest': canonical_sha256(report),
                 'review_status': 'not_assessed_in_this_record'}
        return Command(update={'delivery': value, 'messages': [ToolMessage(tool_call_id=runtime.tool_call_id,
            content=json.dumps(value))]})
    tools = [save_research_report, repair_report_fields, read_current_report, edit_research_report, deliver_working_note, deliver_current_report]
    for t in tools:
        t.handle_tool_error = True
    return [GrantedTool(t, 'read' if t is read_current_report else 'task_artifact_write',
                       '当前任务版本化成果；不代表独立复核') for t in tools]
