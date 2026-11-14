"""Role-scoped MCP tools over durable research workpapers and exact source receipts."""
import json
from typing import Literal
from langchain_core.messages import ToolMessage, messages_from_dict, messages_to_dict
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from .conversation_agent import GrantedTool
from .conversation_tools import SAVED_RESULT_TOOLS
from .research_graph_contracts import canonical_sha256
from .research_workpapers import ResearchWorkpaper, WorkpaperConflict, Adoption
from .research_authoring import UnderstandingPatch, AuthoringIssue, SectionUse


def workpaper_tools(workspace, actor='root', *, assignment=None):
    def guarded(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except WorkpaperConflict as exc:
            authoring = (getattr(fn, '__self__', None) is workspace.authoring or
                         any(word in str(exc) for word in ('understanding','judgment','outline','section','authoring')))
            return {'saved': False, 'error': str(exc),
                'readback': {'tool': 'read_authoring_context' if authoring and actor == 'root' else 'research_updates', 'arguments': {}},
                'notice': 'Correct the selection or reassess current evidence. No content was silently changed.'}

    def read_paper(*args, **kwargs):
        value = workspace.read(*args, **kwargs)
        return {**value, 'result_digest': canonical_sha256(value)}

    @tool
    def publish_research_workpaper(base_revision: int, workpaper: ResearchWorkpaper, runtime: ToolRuntime):
        """Save this role's complete research deliverable before handing off or retiring context.
        Include a supported current judgment, public argument, conditions, counterevidence and remaining
        relationships. State why to continue, stop this branch, await future evidence or repair access.
        A bounded answer retains the original question's unfinished remainder. Dependencies identify
        exact other workpaper revisions you read and how you use them; do not turn hypotheses into facts.
        Only observed successful source/calculation receipt IDs can be evidence. Full papers and those
        receipts are saved atomically; this returns a small versioned readback, not the full body.
        For revisions, explain actual changes. Saving certifies neither completeness nor correctness.
        """
        observations = {m.tool_call_id: messages_to_dict([m])[0] for m in runtime.state.get('messages', [])
                        if isinstance(m, ToolMessage) and m.status == 'success' and m.name in SAVED_RESULT_TOOLS
                        and m.name not in {'ReadWorkingNote','read_handoff_material','read_delegated_note','check_quantitative_changes'}}
        evidence = {key: observations[key] for key in workpaper.evidence_receipt_ids if key in observations}
        return guarded(workspace.publish, actor, base_revision, workpaper.model_dump(mode='json'), evidence,
                       actor+':'+runtime.tool_call_id, assignment=assignment)

    @tool
    def read_research_workpaper(topic_id: str, revision: int | None = None,
                               field: Literal['body', 'metadata'] = 'body', offset: int = 0, max_characters: int = 12000):
        """Read an exact persisted research argument. Metadata preserves conditions, dissent, origin and
        dependencies; body returns a 1-24000-character window with next_offset. Follow relevant arguments
        and their evidence before adopting them. Old versions remain readable but are marked for reassessment.
        Metadata alone is navigation, not reading the full argument. No sibling private history is copied.
        """
        return guarded(read_paper, actor, topic_id, revision, field=field, offset=offset, max_characters=max_characters)

    @tool
    def research_updates(after_sequence: int = 0, limit: int = 8):
        """Read bounded asynchronous workpaper update metadata and topic coverage. Use the returned cursor;
        important findings can change the scope or another topic. This does not wait or trigger models.
        Pending work is handled by the host; do independent work or wait through consultation tools,
        never repeatedly poll this tool in paid turns. Counts do not certify research completeness.
        """
        return guarded(workspace.catalog, after=after_sequence, limit=limit)

    @tool
    def read_workpaper_evidence(receipt_id: str, runtime: ToolRuntime, offset: int = 0, max_characters: int = 12000):
        """Read an archived exact source/calculation receipt underlying a workpaper. It retains its original
        identity and becomes available for the existing citation/calculation tools. Paginate JSON text;
        this is the saved observation, not a fresh web fetch or another independent source.
        """
        if offset < 0 or not 1 <= max_characters <= 24000:
            return {'error': 'invalid_evidence_window', 'max_characters': '1-24000', 'offset': '>=0'}
        value = guarded(workspace.evidence, receipt_id)
        if 'error' in value:
            return value
        original = messages_from_dict([value])[0]
        existing = [m for m in runtime.state.get('messages', []) if isinstance(m, ToolMessage) and m.tool_call_id == receipt_id]
        if existing and messages_to_dict([existing[-1]])[0] != value:
            raise RuntimeError('imported_evidence_identity_collision')
        wire = json.dumps(value, ensure_ascii=False)
        if offset >= len(wire):
            return {'error': 'offset_outside_evidence', 'total_characters': len(wire)}
        end = min(len(wire), offset + max_characters)
        result = {'receipt_id': receipt_id, 'text': wire[offset:end], 'offset': offset,
                  'next_offset': end if end < len(wire) else None, 'total_characters': len(wire)}
        result['result_digest'] = canonical_sha256(result)
        return Command(update={'messages': [*([original] if not existing else []),
            ToolMessage(name='read_workpaper_evidence', tool_call_id=runtime.tool_call_id, content=json.dumps(result,ensure_ascii=False))]})

    tools = [publish_research_workpaper, read_research_workpaper, research_updates, read_workpaper_evidence]
    if actor == 'root':
        @tool
        def update_research_understanding(base_revision: int, patch: UnderstandingPatch, runtime: ToolRuntime):
            """Update only changed public judgments/argument sections; omitted entries retain their exact basis.
            Stable IDs connect conclusions, assumptions, counterevidence, workpaper versions and upstream
            judgments. Lead IDs identify the current overall answer. The outline is provisional: evidence
            can change its thesis, order and scope. A revised premise marks downstream judgments for your
            reassessment, never automatic reversal. Withdraw a judgment explicitly; do not silently erase it.
            No extra narrative plan required. Use read_authoring_context to recover the materialized current view.
            """
            return guarded(workspace.authoring.update, base_revision, patch, actor+':'+runtime.tool_call_id)

        @tool
        def read_authoring_context(section_ids: list[str] | None = None, revision: int | None = None):
            """Read current understanding and the argument outline, or an exact historical revision.
            Select sections to include only their judgments and dependencies plus the overall thesis;
            complete workpapers and original evidence remain behind exact readbacks. This view contains
            assumptions, counterevidence, withdrawn explanations, open issues and affected sections.
            Read actual arguments as needed; do not treat this compact view as sufficient source material.
            """
            return guarded(workspace.authoring.context, section_ids, revision)

        @tool
        def open_authoring_issue(base_revision: int, issue: AuthoringIssue, report_version: int, runtime: ToolRuntime):
            """Record a concrete incoherence in saved prose with exact quote, sections and current basis.
            field selects title or narrative_markdown. Classify missing link, stale basis, expression, thesis conflict or access failure. For research
            pass its ID to consult_research_agent(authoring_issue_id=...); exact origin and related current
            judgments are attached automatically. Multiple issues remain independent; no full research restart.
            """
            if not runtime.state.get('report') or runtime.state.get('report_version') != report_version:
                return {'error': 'report_version_changed_read_current_report'}
            return guarded(workspace.authoring.open_issue, base_revision, issue, runtime.state['report'])

        @tool
        def resolve_authoring_issue(issue_id: str, base_revision: int,
                                    disposition: Literal['revised','retained','bounded_answer'],
                                    explanation: str, result_workpapers: list[Adoption], report_version: int, runtime: ToolRuntime):
            """After investigation/reassessment and prose revision, record your actual handling of an issue.
            Read the linked complete result, update affected judgments, and save the report first. Missing
            links/access failures require a workpaper from the linked investigation, even for a bounded
            answer. You may retain a supported judgment with reasons. This records your decision, not approval.
            Later changes to related judgments or result versions reopen the issue for reassessment.
            """
            if not runtime.state.get('report') or runtime.state.get('report_version') != report_version:
                return {'error': 'report_version_changed_read_current_report'}
            return guarded(workspace.authoring.resolve, issue_id, base_revision, disposition, explanation,
                           result_workpapers, runtime.state['report'])

        tools += [update_research_understanding, read_authoring_context, open_authoring_issue, resolve_authoring_issue]

        @tool
        def prepare_research_synthesis(topic_ids: list[str], scope_rationale: str):
            """Freeze the current research versions for authoring. Select substantive workpapers, explain
            original-question coverage, omissions and still-unfinished relationships. Transitive dependencies
            are included automatically. Stale adopted versions must be reassessed; unresolved views remain
            visible. This returns a version index, never concatenated child histories. Next read relevant
            complete arguments using read_synthesis_material, then compose and check the whole report.
            """
            return guarded(workspace.prepare, actor, topic_ids, scope_rationale)

        @tool
        def read_synthesis_material(snapshot_id: str, topic_id: str, offset: int = 0, max_characters: int = 12000):
            """Read a selected argument at the frozen authoring version with conditions and counterevidence.
            Follow next_offset when more of the argument is needed. A source can be read directly through
            read_workpaper_evidence without expanding layers of summaries. Changed topics require a new
            snapshot and reconsidering affected prose; never silently substitute a new version.
            """
            def read():
                snapshot = workspace.snapshot(snapshot_id)
                if snapshot['changed_topics']:
                    raise WorkpaperConflict('research_changed_refresh_synthesis')
                if snapshot['understanding_changed']:
                    raise WorkpaperConflict('understanding_changed_refresh_synthesis')
                if topic_id not in snapshot['selected']:
                    raise WorkpaperConflict('topic_not_selected_in_synthesis')
                return workspace.read(actor, topic_id, snapshot['selected'][topic_id]['revision'],
                                      offset=offset, max_characters=max_characters)
            return guarded(read)

        @tool
        def bind_research_synthesis(snapshot_id: str, report_version: int, runtime: ToolRuntime,
                                   section_uses: list[SectionUse] | None = None):
            """After whole-report reading, bind the saved report to the research versions actually used.
            Check title, summary, cross-section explanations and important assumptions. This validates
            identities and version currency, not financial correctness. Changed research needs reassessment;
            it cannot be acknowledged away by citing an old snapshot. Existing report citations remain required.
            With an argument outline, bind each section to an exact unique passage in saved prose through
            section_uses (field=title or narrative_markdown). A section can bind several distinct passages,
            including its summary and conclusion. Current judgments and workpaper versions bind automatically.
            """
            if not runtime.state.get('report') or report_version != runtime.state.get('report_version'):
                return {'error':'report_version_changed_read_current_report'}
            return guarded(workspace.bind, snapshot_id, canonical_sha256(runtime.state['report']),
                           report=runtime.state['report'], section_uses=section_uses)
        tools += [prepare_research_synthesis, read_synthesis_material, bind_research_synthesis]
    return [GrantedTool(t, 'task_artifact_write' if t.name in {'publish_research_workpaper','bind_research_synthesis',
        'update_research_understanding','open_authoring_issue','resolve_authoring_issue'} else 'read',
        'Versioned research delivery and scoped original readback') for t in tools]
