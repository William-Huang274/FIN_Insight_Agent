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
        Background links preserve historical orientation and exact readback, without making that history
        a live premise. Adopted, qualified and challenged premises retain version-change checks.
        Only observed successful source/calculation receipt IDs can be evidence. Full papers and those
        receipts are saved atomically; this returns a small versioned readback, not the full body.
        For revisions, explain actual changes. Saving certifies neither completeness nor correctness.
        """
        workspace.archive_execution_observations(actor, runtime.state.get('messages', []))
        observations = {m.tool_call_id: messages_to_dict([m])[0] for m in runtime.state.get('messages', [])
                        if isinstance(m, ToolMessage) and m.status == 'success' and m.name in SAVED_RESULT_TOOLS
                        and m.name not in {'ReadWorkingNote','read_handoff_material','read_delegated_note','check_quantitative_changes'}}
        evidence = {key: observations[key] for key in workpaper.evidence_receipt_ids if key in observations}
        return guarded(workspace.publish, actor, base_revision, workpaper.model_dump(mode='json'), evidence,
                       actor+':'+runtime.tool_call_id, assignment=assignment)

    @tool
    def read_research_workpaper(topic_id: str, revision: int | None = None,
                               field: Literal['body', 'metadata', 'outline'] = 'body', offset: int = 0, max_characters: int = 12000):
        """Read an exact persisted research argument. Metadata preserves conditions, dissent, origin and
        dependencies; body returns a 1-24000-character window with next_offset. Follow relevant arguments
        and their evidence before adopting them. Old versions remain readable but are marked for reassessment.
        Metadata alone is navigation, not reading the full argument. No sibling private history is copied.
        outline returns headings and exact versioned windows, not a summary or a completed read.
        During authoring, body omits execution-history metadata; explicit metadata recalls it unchanged.
        """
        return guarded(read_paper, actor, topic_id, revision, field=field, offset=offset, max_characters=max_characters)

    @tool
    def research_updates(after_sequence: int = 0, limit: int = 8, include_catalog: bool = False):
        """Read bounded asynchronous workpaper update metadata and topic coverage. Use the returned cursor;
        important findings can change the scope or another topic. This does not wait or trigger models.
        Pending work is handled by the host; do independent work or wait through consultation tools,
        never repeatedly poll this tool in paid turns. Counts do not certify research completeness.
        """
        return guarded(workspace.catalog, after=after_sequence, limit=limit, include_catalog=include_catalog or after_sequence==0)

    @tool
    def read_research_execution(topic_id: str | None = None, offset: int = 0, limit: int = 8, query: str = ''):
        """Find archived public searches, candidates, reads and acquisition failures in this research workspace.
        Omit topic_id to browse all its topics. query filters original records by literal text (e.g. domain).
        Follow next_offset; limit is 1-20 records.
        Returns original request previews and exact receipt readbacks, not source evidence.
        Unknown historical IDs are not automatically matched to another observation.
        """
        return guarded(workspace.execution_catalog, topic_id, offset, limit, query)

    @tool
    def read_workpaper_evidence(receipt_id: str, runtime: ToolRuntime, offset: int = 0, max_characters: int = 12000):
        """Read an archived exact source/calculation receipt, or a failed acquisition and its original call.
        Failed acquisitions are execution records only: not citation/calculation evidence or absence of disclosure.
        Successful evidence retains its original
        identity and becomes available for the existing citation/calculation tools. Paginate JSON text;
        this is the saved observation, not a fresh web fetch or another independent source.
        """
        if offset < 0 or not 1 <= max_characters <= 24000:
            return {'error': 'invalid_evidence_window', 'max_characters': '1-24000', 'offset': '>=0'}
        try:
            value = workspace.evidence(receipt_id)
        except WorkpaperConflict:
            failed = guarded(workspace.execution_observation, receipt_id)
            if 'error' in failed:
                failed['execution_readback']={'tool':'read_research_execution','arguments':{}}
                return failed
            wire = json.dumps(failed, ensure_ascii=False)
            if offset >= len(wire):
                return {'error': 'offset_outside_evidence', 'total_characters': len(wire)}
            end = min(len(wire), offset + max_characters)
            result = {'receipt_id': receipt_id, 'record_kind': 'execution_observation',
                      'source_evidence': False, 'new_tool_dispatch': False,
                      'topic_id': failed['topic_id'], 'original_call': failed['call'],
                      'text': wire[offset:end], 'offset': offset,
                      'next_offset': end if end < len(wire) else None, 'total_characters': len(wire)}
            result['result_digest'] = canonical_sha256(result)
            return result
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

    @tool
    def read_authoring_context(section_ids: list[str] | None = None, revision: int | None = None,
                               include_history: bool = False, include_unplaced: bool = False):
        """Read current public judgments and related argument materials, or a historical judgment revision.
        Sections expand their own dependencies; the overall answer stays a short orientation. Read
        adopted findings first; inspect originals when the intended inference changes. include_history adds resolved issues
        and withdrawn explanations; old judgments do not imply old live issue status. This is read-only.
        """
        if (section_ids is None and revision is None and not include_history and not workspace.authoring_active()
                and workspace.organization_policy().get('root_investigations_require_topic_lead')):
            from .research_decision_context import lead_decision
            current = lead_decision(workspace.authoring.context(include_unplaced=True))
            return {**current,'result_digest':canonical_sha256(current)}
        return guarded(workspace.authoring.context, section_ids, revision, include_history, include_unplaced=include_unplaced)

    tools = [publish_research_workpaper, read_research_workpaper, research_updates, read_workpaper_evidence,
             read_research_execution, read_authoring_context]
    if actor == 'root':
        from .authoring_sections import AuthoringSections, MaterialUse
        chapters = AuthoringSections(workspace)

        @tool
        def authoring_section(section_id: str, action: Literal['open','save','read','assemble','select','release'], runtime: ToolRuntime,
                              prose: str = '', takeaway: str = '', receipt_ids: list[str] | None = None,
                              revision: int | None = None, base_revision: int | None = None,
                              section_ids: list[str] | None = None, material_uses: list[MaterialUse] | None = None,
                              reason: str = ''):
            """Write with durable chapter working sets. First define sections with update_research_understanding.
            Open one section for its current judgments and previous draft; read relevant saved arguments.
            Save its complete reader-facing prose, takeaway and successful material tool receipt IDs,
            using base_revision=0 for a new chapter. Saved materials can then leave active context while
            exact originals remain readable. Read retrieves an exact saved revision and source readbacks.
            Changed premises mark dependent chapters needs_update; reopen, reassess and save them.
            Assemble with section_id="" returns current chapter prose once and source readbacks for
            whole-report editing. Select, merge and reorder around the main answer, then save the report.
            Remove unused outline sections with update_research_understanding; archived chapters and
            judgments remain. There is no requirement to use every workpaper or a minimum edit amount.
            Select uses section_ids for a local working set without deleting the report outline;
            assemble accepts section_ids for local editing, omitted means the entire report.
            material_uses records the argumentative purpose of selected exact receipts when saving.
            Release explicitly shelves inspected, unused receipt_ids with a reason; originals remain
            readable. It cannot release materials adopted by saved chapters. Use related_sections in
            the outline for editorial dependencies; changed responsibilities then flag dependent drafts.
            """
            return guarded(chapters.act,section_id,action,prose=prose,takeaway=takeaway,
                           receipt_ids=receipt_ids,messages=runtime.state.get('messages',[]),
                           revision=revision,base_revision=base_revision,section_ids=section_ids,
                           material_uses=material_uses,reason=reason)

        @tool
        def reuse_adopted_judgment(section_id: str, judgment_id: str, judgment_digest: str, runtime: ToolRuntime,
                                   source_receipts: list[str] | None = None):
            """Use the lead's accepted finding, conditions and versioned citations in this chapter.
            Use the digest in current context. Optional exact receipt IDs select additional originals
            from its adopted workpapers. The versioned metadata readback contains their adoption history.
            Older findings may have no lead-selected originals. Open
            originals for new quantities, conflicting evidence or expanded claims. Save with this receipt ID.
            """
            from .adopted_judgments import reuse_judgment
            result = guarded(reuse_judgment,workspace,section_id,judgment_id,judgment_digest,source_receipts or [])
            if isinstance(result,dict):
                return result
            view, originals = result
            known = {m.tool_call_id:m for m in runtime.state.get('messages',[]) if isinstance(m,ToolMessage)}
            for m in originals:
                if m.tool_call_id in known and messages_to_dict([known[m.tool_call_id]]) != messages_to_dict([m]):
                    raise RuntimeError('imported_evidence_identity_collision')
            return Command(update={'messages':[*[m for m in originals if m.tool_call_id not in known],
                ToolMessage(name='reuse_adopted_judgment',tool_call_id=runtime.tool_call_id,
                            content=json.dumps(view,ensure_ascii=False))]})

        tools.extend([authoring_section,reuse_adopted_judgment])
        @tool
        def update_research_understanding(base_revision: int, patch: UnderstandingPatch, runtime: ToolRuntime):
            """Update only changed public judgments/argument sections; omitted entries retain their exact basis.
            Stable IDs connect conclusions, assumptions, counterevidence, workpaper versions and upstream
            judgments. Lead IDs identify the current overall answer. The outline is provisional: evidence
            can change its thesis, order and scope. A revised premise marks downstream judgments for your
            reassessment, never automatic reversal. Withdraw a judgment explicitly; do not silently erase it.
            No extra narrative plan required. Use read_authoring_context to recover the materialized current view.
            """
            value = guarded(workspace.authoring.update, base_revision, patch, actor+':'+runtime.tool_call_id)
            value['chapters'] = chapters.overview()
            return value

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
                                    explanation: str, result_workpapers: list[Adoption], report_version: int, runtime: ToolRuntime,
                                    prose_uses: list[SectionUse] | None = None, evidence_receipt_ids: list[str] | None = None):
            """After investigation/reassessment and prose revision, record your actual handling of an issue.
            Read the linked complete result, update affected judgments, and save the report first. Missing
            links/access failures require a linked workpaper OR successful original source/calculation
            receipt IDs you directly investigated. Supply prose_uses identifying the resolved passages;
            the surrounding paragraphs are tracked so unrelated edits do not reopen this issue. Without
            anchors the whole affected field is tracked conservatively. You may retain a supported judgment.
            Later changes to related judgments or result versions reopen the issue for reassessment.
            """
            if not runtime.state.get('report') or runtime.state.get('report_version') != report_version:
                return {'error': 'report_version_changed_read_current_report'}
            ids=evidence_receipt_ids or []
            observed={m.tool_call_id:messages_to_dict([m])[0] for m in runtime.state.get('messages',[])
                if isinstance(m,ToolMessage) and m.status=='success' and m.name in SAVED_RESULT_TOOLS
                and m.name not in {'ReadWorkingNote','read_handoff_material','read_delegated_note','check_quantitative_changes'}}
            if len(ids)>24 or len(ids)!=len(set(ids)) or any(k not in observed for k in ids):
                return {'saved':False,'error':'direct_evidence_must_be_successfully_observed_source_or_calculation'}
            return guarded(workspace.authoring.resolve, issue_id, base_revision, disposition, explanation,
                           result_workpapers, runtime.state['report'],prose_uses=prose_uses,
                           direct_evidence={k:observed[k] for k in ids})

        tools += [update_research_understanding, open_authoring_issue, resolve_authoring_issue]

        @tool
        def prepare_research_synthesis(topic_ids: list[str], scope_rationale: str, section_ids: list[str] | None = None):
            """Freeze the current research versions for authoring. Select substantive workpapers, explain
            their use for the original question and still-unfinished relationships. Select materials actually
            used; the catalog is not a mandatory coverage list. Transitive dependencies
            are included automatically. Stale adopted versions must be reassessed; unresolved views remain
            visible. This returns a version index, never concatenated child histories. Next read relevant
            complete arguments using read_synthesis_material as needed. Reuse same-version reads shown
            in the receipt; rebuilding a snapshot does not require reading them again.
            For local writing set section_ids: validates only these chapters' judgment dependencies,
            preserving the full outline. A chapter snapshot cannot bind a whole report. Omit section_ids
            for the final report snapshot covering the complete adopted outline and overall judgment.
            """
            result = guarded(workspace.prepare, actor, topic_ids, scope_rationale,section_ids)
            if section_ids and result.get('snapshot_id'):
                if result.pop('historical_inputs', None) or 'background_inputs' in result:
                    result.pop('background_inputs', None)
                    result['history_readback'] = {'tool':'read_synthesis_material', 'arguments':{
                        'snapshot_id':result['snapshot_id'], 'topic_id':topic_ids[0], 'view':'history'}}
            return result

        @tool
        def read_synthesis_material(snapshot_id: str, topic_id: str, offset: int | None = None,
                                    max_characters: int | None = None, view: Literal['argument','window','history'] | None = None):
            """For a chapter, omit window arguments for its finding, adoption terms, conditions and passage index.
            Select view=window with offset and max_characters for exact prose; view=history for revision decisions.
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
                chapter = bool(snapshot.get('section_ids'))
                if view == 'history':
                    return {k:snapshot.get(k,[]) for k in ('historical_inputs','background_inputs')} | {'snapshot_id':snapshot_id}
                if chapter and (view == 'argument' or view is None and offset is None and max_characters is None):
                    from .authoring_materials import chapter_argument
                    result = chapter_argument(workspace, snapshot_id, snapshot, topic_id)
                    return {**result, 'result_digest':canonical_sha256(result)}
                result = read_paper(actor, topic_id, snapshot['selected'][topic_id]['revision'],
                                    offset=0 if offset is None else offset, max_characters=12000 if max_characters is None else max_characters)
                if chapter:
                    result.update(snapshot_read_view='window', history_readback={'tool':'read_synthesis_material',
                        'arguments':{'snapshot_id':snapshot_id,'topic_id':topic_id,'view':'history'}})
                    if snapshot.get('historical_inputs'):
                        result['standalone_requires_reassessment'] = result.get('requires_reassessment', [])
                        result['requires_reassessment'] = []
                    result['result_digest'] = canonical_sha256({k:v for k,v in result.items() if k!='result_digest'})
                elif snapshot.get('historical_inputs'):
                    result['standalone_requires_reassessment'] = result.get('requires_reassessment', [])
                    result['requires_reassessment'] = []
                    result['adoption_context'] = {'snapshot_id':snapshot_id,
                        'historical_inputs':snapshot['historical_inputs'],
                        'meaning':'Current synthesis includes the revision that reassessed these earlier inputs; original versions remain readable.'}
                    result['result_digest'] = canonical_sha256({k:v for k,v in result.items() if k!='result_digest'})
                return result
            return guarded(read)

        @tool
        def bind_research_synthesis(snapshot_id: str, report_version: int, runtime: ToolRuntime,
                                   section_uses: list[SectionUse] | None = None):
            """After whole-report reading, bind the saved report to the research versions actually used.
            Check title, summary, cross-section explanations and important assumptions. This validates
            identities and version currency, not financial correctness. Changed research needs reassessment;
            it cannot be acknowledged away by citing an old snapshot. Existing report citations remain required.
            Revise the provisional outline to the sections actually used; remove_sections retains research
            and archived drafts. With that outline, bind each section to an exact unique passage through
            section_uses (field=title or narrative_markdown). A section can bind several distinct passages,
            including its summary and conclusion. Current judgments and workpaper versions bind automatically.
            """
            if not runtime.state.get('report') or report_version != runtime.state.get('report_version'):
                return {'error':'report_version_changed_read_current_report'}
            return guarded(workspace.bind, snapshot_id, canonical_sha256(runtime.state['report']),
                           report=runtime.state['report'], section_uses=section_uses)
        tools += [prepare_research_synthesis, read_synthesis_material, bind_research_synthesis]
    return [GrantedTool(t, 'task_artifact_write' if t.name in {'publish_research_workpaper','bind_research_synthesis',
        'update_research_understanding','open_authoring_issue','resolve_authoring_issue','authoring_section'} else 'read',
        'Versioned research delivery and scoped original readback') for t in tools]
