"""Ordinary conversation tool over existing Exa discovery/capture and DiskCache."""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool, ToolException

from sec_agent.research_foundation.contracts import canonical_sha256
from sec_agent.research_foundation.external_sources import (
    ConversationSourceScope, ExaHostedMCPProvider, ExaHostedMCPPageFetcher,
    ExternalSourceDiscovery, ExternalSourceCapture, ExternalSourceError, PublicURLGuard,
)
from sec_agent.research_foundation.source_capture_cache import ScopedSourceCaptureCache
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.web_source_navigation import WebSourceReader
from .conversation_agent import GrantedTool


def public_web_tool(*, thread_id, run_id, method_digest, cache_root: Path, reader=None):
    from uuid import UUID
    thread_id, run_id = str(UUID(thread_id)), str(UUID(run_id))
    body = dict(schema_version="fin_ia_conversation_source_scope_v1_0", case_id=thread_id,
        research_as_of=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).isoformat(), data_snapshot_id="conversation-public-sources-v1",
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
        reader = WebSourceReader(discovery=ExternalSourceDiscovery(primary=ExaHostedMCPProvider()),capture=cached)

    @tool(response_format="content_and_artifact")
    async def read_public_source(operation: Literal["search","read"], query: str = "",
            document_id: str | None = None, offset: int = 0, max_characters: int = 6000):
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
            if operation == "read" and query:
                raise ValueError("read accepts document_id and character offset, not query. Use operation=search with document_id and query to locate a section, then read at character_start without query.")
            if max_characters > 24000:
                raise ValueError("Use at most 24000 characters and paginate with offset")
            result = await reader(request=SourceDocumentRequest(source_space="web",operation=operation,
                query=query,document_id=document_id,offset=offset,max_characters=max_characters,limit=5),
                branch_id="conversation",run_scope=scope)
            artifact = result.model_dump(mode="json")
            return json.dumps(artifact,ensure_ascii=False), artifact
        except (ValueError, ExternalSourceError) as exc:
            raise ToolException("公开来源读取未完成，不代表信息未披露：" + str(exc)) from exc
    read_public_source.handle_tool_error = True
    return GrantedTool(read_public_source,"read","公开网页搜索与原文读取；仅本对话缓存")
