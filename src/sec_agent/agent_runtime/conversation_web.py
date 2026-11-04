"""Ordinary conversation tool over existing Exa discovery/capture and SQLite records."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime

from sec_agent.research_foundation.contracts import canonical_sha256
from sec_agent.research_foundation.external_sources import (
    ConversationSourceScope, ExaHostedMCPProvider, ExaHostedMCPPageFetcher,
    ExternalSourceDiscovery, ExternalSourceCapture, ExternalSourceError, PublicURLGuard,
)
from sec_agent.research_foundation.source_capture_cache import ScopedSourceCaptureCache
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.web_source_navigation import WebSourceReader
from .conversation_agent import GrantedTool


def public_web_tool(*, thread_id, run_id, method_digest, cache_root: Path, reader=None, research_as_of=None):
    from uuid import UUID
    thread_id, run_id = str(UUID(thread_id)), str(UUID(run_id))
    cutoff = datetime.fromisoformat(research_as_of.replace('Z', '+00:00')) if research_as_of else datetime.now(timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    body = dict(schema_version="fin_ia_conversation_source_scope_v1_0", case_id=thread_id,
        research_as_of=cutoff.replace(hour=0,minute=0,second=0,microsecond=0).isoformat(),
        data_snapshot_id="dated-public-sources-v2" if research_as_of else "conversation-public-sources-v1",
        method_sha256=method_digest, selected_branch_ids=["conversation"], execution_attempt_id=run_id,
        source_policy="public_web_locator_only")
    # Pydantic canonical datetime serialization uses Z; hash the same representation.
    body["research_as_of"] = body["research_as_of"].replace("+00:00", "Z")
    scope = ConversationSourceScope(**body, run_scope_digest=canonical_sha256(body))
    if reader is None:
        guard = PublicURLGuard()
        capture = ExternalSourceCapture(guard=guard,
            hosted_fetcher=ExaHostedMCPPageFetcher(guard=guard,max_characters=200000))
        cached = ScopedSourceCaptureCache(root=cache_root,thread_id=thread_id,capture=capture,guard=guard)
        discovery = ExternalSourceDiscovery(primary=ExaHostedMCPProvider())
        if research_as_of:
            from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
            discovery = DatedWebDiscovery(discovery, ExaHostedMCPPageFetcher(guard=guard,max_characters=8000))
        reader = WebSourceReader(discovery=discovery,capture=cached)

    restored = set()

    @tool(response_format="content_and_artifact")
    async def read_public_source(operation: Literal["search","read"], query: str = "",
            document_id: str | None = None, offset: int = 0, max_characters: int = 6000,
            runtime: ToolRuntime = None):
        """Search public web sources, then read an exact returned WEB document ID.
        To locate a section, search again with that document_id and keywords;
        this returns exact bounded passages from the captured original, which
        may be cited with their source locators. Only read adjacent character
        offsets if more context is needed. Global search previews are not verified evidence. Read original text before
        citing; assess publisher/date and preserve limitations. Only submit
        public search terms, never credentials or private uploaded content.
        Captures are cached within this thread; they are not automatically
        admitted to a shared knowledge base. A new round may need a new search.
        """
        try:
            # Discovery candidates belong to this task, not a transient run.
            # Restore only host-saved tool artifacts; the model cannot register URLs.
            if runtime is not None and hasattr(reader, 'restore_navigation'):
                from sec_agent.research_foundation.external_sources import DiscoveryReceipt
                from sec_agent.research.reviewed_evidence_pack import canonical_digest
                for message in runtime.state.get('messages', []):
                    if getattr(message, 'name', None) != 'read_public_source' or getattr(message, 'status', None) != 'success':
                        continue
                    for raw in (getattr(message, 'artifact', None) or {}).get('web_navigation_receipts', []):
                        receipt = DiscoveryReceipt.model_validate(raw)
                        if receipt.receipt_digest in restored:
                            continue
                        if receipt.case_id != thread_id:
                            raise ValueError('public_source_restore_task_mismatch')
                        if receipt.data_snapshot_id != scope.data_snapshot_id or receipt.research_as_of[:10] != cutoff.date().isoformat():
                            continue
                        rebound = receipt.model_dump(mode='json', exclude={'receipt_digest'})
                        rebound.update(execution_attempt_id=scope.execution_attempt_id,
                            run_scope_digest=scope.run_scope_digest, research_as_of=scope.research_as_of.astimezone(timezone.utc).isoformat(timespec='seconds'),
                            data_snapshot_id=scope.data_snapshot_id, method_sha256=scope.method_sha256)
                        lineage = {key: rebound[key] for key in ('execution_attempt_id', 'run_scope_digest',
                                   'research_as_of', 'data_snapshot_id', 'method_sha256')}
                        rebound['candidates'] = [{**candidate, **lineage} for candidate in rebound['candidates']]
                        reader.restore_navigation([{**rebound, 'receipt_digest': canonical_digest(rebound)}],
                            branch_id='conversation', run_scope=scope)
                        restored.add(receipt.receipt_digest)
            if operation == "read" and query:
                raise ValueError("read accepts document_id and character offset, not query. Use operation=search with document_id and query to locate a section, then read at character_start without query.")
            if max_characters > 24000:
                raise ValueError("Use at most 24000 characters and paginate with offset")
            result = await reader(request=SourceDocumentRequest(source_space="web",operation=operation,
                query=query,document_id=document_id,offset=offset,max_characters=max_characters,limit=5,
                **({'end_published_date': scope.research_as_of.date()} if operation == 'search' and not document_id else {})),
                branch_id="conversation",run_scope=scope)
            artifact = result.model_dump(mode="json")
            visible = dict(artifact)
            if operation == 'search':
                visible['search_coverage'] = {'space': 'public_web', 'research_as_of': body['research_as_of'],
                    'query': query, 'document_id': document_id,
                    'query_kind': 'captured_document_search' if document_id else 'provider_ranked_search',
                    'issuer_non_disclosure_established': False,
                    'meaning': ('Dated discovery omits undated or post-cutoff results before display. Try another dated primary release if needed. '
                                if scope.data_snapshot_id == 'dated-public-sources-v2' else '') +
                               'Provider results/captured text only, not exhaustive public disclosure coverage.'}
            if hasattr(reader, 'export_navigation'):
                artifact['web_navigation_receipts'] = reader.export_navigation()
            return json.dumps(visible,ensure_ascii=False), artifact
        except (ValueError, ExternalSourceError) as exc:
            raise ToolException("公开来源读取未完成，不代表信息未披露：" + str(exc)) from exc
    read_public_source.handle_tool_error = True
    return GrantedTool(read_public_source,"read","公开网页搜索与原文读取；仅本对话缓存")
