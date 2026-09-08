"""Thin source-reader adapter over existing Exa MCP discovery/capture.

Not an index, crawler, Evidence admission service, or persistence engine. Run
composition owns the short-lived discovered locators. Disclosed source windows
and capture identifiers remain in the normal MCP/tool observations. A fresh
lifecycle discovers locators again; the supplied capture adapter may reuse a
scoped persisted capture. This is not cross-thread memory or evidence admission.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from urllib.parse import urlsplit

from .external_sources import ExternalCaptureRequest, ExternalSearchRequest
from .source_document_navigation import SourceDocumentRequest, SourceDocumentResult, navigate_source_nodes


class WebSourceReader:
    def __init__(self, *, discovery, capture):
        self.discovery, self.capture = discovery, capture
        self._candidates = {}
        self._captures = {}

    async def __call__(self, *, request: SourceDocumentRequest, branch_id, run_scope):
        if request.source_space != "web" or branch_id not in run_scope.selected_branch_ids:
            raise ValueError("web_source_scope_invalid")
        key = (run_scope.run_scope_digest, branch_id)
        if request.operation == "search" and not request.document_id:
            receipt = await self.discovery.search(ExternalSearchRequest(
                query=request.query, branch_id=branch_id, run_scope=run_scope,
                purpose="Agent-selected public source research; no Evidence or NumericFact promotion",
                max_results=min(request.limit, 8)))
            items = []
            for candidate in receipt.candidates:
                doc_id = "WEB::" + candidate.candidate_id
                self._candidates[(*key, doc_id)] = (receipt, candidate)
                items.append({"result_state": "retrieval_candidate", "document_id": doc_id,
                    "candidate_id": doc_id, "title": candidate.title, "source_url": candidate.canonical_url,
                    "publication_date": candidate.published_at, "preview": candidate.snippet,
                    "writer_citable": False, "numeric_fact_authority": False,
                    "publication_date_status": "search_provider_metadata_not_independently_verified"})
            return SourceDocumentResult(operation="search", items=tuple(items), next_offset=None,
                total_matches=len(items), source_snapshot_sha256=receipt.receipt_digest,
                notice="Live Exa search. Snippets are not citations. Read a WEB document_id in this branch; an empty result or tool failure is not a public-information gap. "
                       + str([attempt.model_dump() for attempt in receipt.attempted_providers]))
        stored = self._candidates.get((*key, request.document_id))
        if stored is None:
            raise ValueError("web_document_not_discovered_in_this_scope_search_first")
        discovery, candidate = stored
        published = None
        if candidate.published_at:
            try:
                published = date.fromisoformat(candidate.published_at[:10])
            except ValueError:
                pass
        if published is not None and published > run_scope.research_as_of.date():
            raise ValueError("web_source_publication_after_research_as_of")
        capture_key = (*key, request.document_id)
        result = self._captures.get(capture_key)
        if result is None:
            result = await self.capture.capture(ExternalCaptureRequest(
                discovery_receipt=discovery, candidate_id=candidate.candidate_id,
                branch_id=branch_id, run_scope=run_scope, render_policy="hosted",
                max_characters=200000, timeout_seconds=30))
            if result.status != "captured":
                return SourceDocumentResult(operation="read", items=(), next_offset=None, total_matches=0,
                    source_snapshot_sha256=result.receipt_digest,
                    notice="Source fetch failed, not public non-disclosure: " + str([a.model_dump() for a in result.attempts]))
            self._captures[capture_key] = result
        if request.operation == "search":
            # Reuse the existing chunker/BM25 navigator inside one captured
            # source; no second index, full-document prompt or new ranking rules.
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            chunks = RecursiveCharacterTextSplitter(chunk_size=1800,chunk_overlap=180,add_start_index=True).create_documents([result.text])
            nodes=[{"node_id":str(chunk.metadata["start_index"]),"parent_document_id":request.document_id,
                "node_kind":"paragraph","title":candidate.title,"stable_url":result.final_url,
                "content":chunk.page_content,"document_kind":"html"} for chunk in chunks]
            matches=navigate_source_nodes(nodes,request,snapshot=result.receipt_digest,allowed_space="web")
            # These matches are already inside the captured original. Return
            # exact bounded passages rather than a prefix preview that may cut
            # off the matching paragraph and induce repeated searching.
            passages = []
            for item in matches.items:
                start = int(item["node_id"])
                read = await self(request=request.model_copy(update={"operation":"read", "query":"",
                    "offset":start, "max_characters":item["content_characters"]}), branch_id=branch_id, run_scope=run_scope)
                passages.extend(read.items)
            return matches.model_copy(update={"items":tuple(passages),
                "notice":"Matched bounded passages read verbatim from the captured original, with exact character locators. These are not complete-document or financial-quality verification. Read adjacent offsets only if the passage ends before the needed context."})
        end = min(len(result.text), request.offset + request.max_characters)
        passage = result.text[request.offset:end]
        if not passage:
            return SourceDocumentResult(operation="read", items=(), next_offset=None, total_matches=0,
                source_snapshot_sha256=result.receipt_digest,
                notice=f"Captured text ends at character {len(result.text)}; requested offset {request.offset}. "
                    f"Host capture truncated={result.truncated}. This is the captured-text boundary, NOT verified "
                    "document completeness or public non-disclosure. Read an earlier offset or search for the relevant "
                    "section/alternate public source; do not repeat an out-of-range offset.")
        digest = sha256(passage.encode("utf-8")).hexdigest()
        url = result.final_url
        if not url:
            raise ValueError("web_capture_final_url_missing")
        # One evidenced site-specific distinction: a research store landing page
        # is not its linked paid report. Do not bypass that boundary or auto-buy.
        parsed = urlsplit(url)
        commercial_preview = (parsed.hostname in {"trendforce.com", "www.trendforce.com"}
                              and parsed.path.startswith("/research/download/"))
        locator = {"source_url": url, "document_id": request.document_id,
                   "capture_receipt_digest": result.receipt_digest, "captured_at": result.captured_at,
                   "character_start": request.offset, "character_end": end, "content_sha256": digest}
        item = {"result_state": "source_bound_passage", "document_id": request.document_id,
            "passage_id": f"PASSAGE::{request.document_id}::{request.offset}::{digest[:16]}",
            "passage": passage, "content_sha256": digest, "source_url": url, "source_locator": locator,
            "title": candidate.title, "publication_date": candidate.published_at,
            "publication_date_status": "provider_metadata_only" if published else "unknown_must_resolve_for_time_sensitive_claims",
            "source_role": "external_public_source_unverified", "source_read_method": result.capture_method,
            "access_scope": "commercial_report_landing_page_only" if commercial_preview else "requested_url_body_only",
            "writer_citable": True, "numeric_fact_authority": False,
            "truncated": end < len(result.text) or result.truncated,
            "source_document_completeness_verified": False,
            "captured_characters": len(result.text),
            "host_capture_truncated": result.truncated,
            "authority_note": "Exact fetched public-source window, not Reviewed Evidence or S2 NumericFact. "
                "Cite what this URL actually says, assess publisher/reliability/date and distinguish reported fact, forecast, opinion and inference. "
                "Search dates are not independently verified; capture date is not publication date. Linked reports/PDFs are not implicitly read. "
                + ("This is a commercial report sales/preview page, NOT the paid report or its numeric tables; no access bypass."
                   if commercial_preview else "News, posts and self-media may be used with explicit source limitations; do not present them as authoritative numbers.")}
        return SourceDocumentResult(operation="read", items=(item,), next_offset=end if end < len(result.text) else None,
            total_matches=1, source_snapshot_sha256=result.receipt_digest,
            notice="Web read uses character offsets, not PDF pages. Exact quotes remain required; citation eligibility is not factual, temporal or completeness verification.")
