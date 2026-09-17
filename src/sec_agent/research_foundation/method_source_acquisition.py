"""Bounded source acquisition for method qualification using the production reader.

The native graph checkpoints returned observations; this adapter neither owns a
crawler nor mutates the frozen input snapshot. Provider dates remain unverified.
"""
from datetime import date, datetime
import json

from pydantic import Field, model_validator
from typing import Annotated

from .method_execution import Contract
from .source_document_navigation import SourceDocumentRequest


class SourceAcquisition(Contract):
    acquisition_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=600)
    unresolved_question: str = Field(min_length=1)
    why_existing_sources_insufficient: str = Field(min_length=1)
    max_results: int = Field(default=2, ge=1, le=3)
    include_domains: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    start_published_date: date | None = None
    end_published_date: date | None = None
    section_queries: list[Annotated[str,Field(min_length=1,max_length=600)]] = Field(default_factory=list, max_length=3,
        description='Terms to search inside each captured original, e.g. an exact note title. Returns original windows beyond the opening prefix; not web snippets.')

    @model_validator(mode='after')
    def validate_discovery_request(self):
        SourceDocumentRequest(source_space='web',operation='search',query=self.query,
            include_domains=self.include_domains,start_published_date=self.start_published_date,
            end_published_date=self.end_published_date)
        return self


class MethodSourceAcquirer:
    def __init__(self, *, reader, branch_id, run_scope, record):
        self.reader, self.branch_id, self.run_scope, self.record = reader, branch_id, run_scope, record

    async def __call__(self, request: SourceAcquisition, as_of: str):
        if date.fromisoformat(as_of) != self.run_scope.research_as_of.date():
            raise ValueError('acquisition_as_of_scope_mismatch')
        receipts, reads, exclusions, adjustments = [], [], [], []

        async def invoke(selection):
            self.record('source_request', selection.model_dump(mode='json'))
            result = await self.reader(request=selection, branch_id=self.branch_id, run_scope=self.run_scope)
            self.record('source_result', result.model_dump(mode='json'))
            if result.execution_receipt:
                receipts.append(result.execution_receipt.model_dump(mode='json'))
            return result

        found = await invoke(SourceDocumentRequest(source_space='web', operation='search',
            query=request.query, limit=request.max_results, include_domains=request.include_domains,
            start_published_date=request.start_published_date, end_published_date=request.end_published_date))
        if (found.execution_receipt and found.execution_receipt.status=='zero_results'
                and (request.start_published_date or request.end_published_date)):
            # Some original filing pages have no provider publication metadata.
            # One explicit, recorded filter relaxation is a different query scope,
            # not a retry of a failed paid request or permission to use future facts.
            adjustments.append({'origin':'runtime_retrieval_adjustment',
                'reason':'zero_results_with_provider_date_filter; date metadata may be missing',
                'change':'remove_provider_date_filters_once_preserve_query_domains_and_research_cutoff',
                'historical_evidence_policy_relaxed':False})
            found=await invoke(SourceDocumentRequest(source_space='web',operation='search',
                query=request.query,limit=request.max_results,include_domains=request.include_domains))
        for candidate in found.items:
            # Search snippets never become financial evidence. Read every bounded
            # candidate in provider order, without host selection of a desired answer.
            published = candidate.get('publication_date')
            try:
                future = published and date.fromisoformat(published[:10]) > date.fromisoformat(as_of)
            except ValueError:
                future = False
            if future:
                exclusions.append({'document_id': candidate['document_id'],
                    'reason': 'provider_date_after_cutoff_not_read', 'publication_date': published})
                continue
            result = await invoke(SourceDocumentRequest(source_space='web', operation='read',
                document_id=candidate['document_id'], max_characters=8000 if request.section_queries else 80000))
            if not result.items:
                continue
            item = result.items[0]
            passages={p['passage_id']:p for p in result.items}
            for query in request.section_queries:
                matched=await invoke(SourceDocumentRequest(source_space='web',operation='search',
                    document_id=candidate['document_id'],query=query,limit=8,max_characters=24000))
                passages.update({p['passage_id']:p for p in matched.items})
            captured = datetime.fromisoformat(str(item['source_locator']['captured_at']).replace('Z', '+00:00')).date()
            eligible = captured <= date.fromisoformat(as_of)
            # A current capture proves current availability, not historical
            # publication. Do not promote the search provider's date to an archive.
            source = {'id': item['document_id'], 'title': item['title'], 'url': item['source_url'],
                'published_at': published[:10] if published else None,
                'known_at': captured.isoformat(), 'vintage': 'known_as_of',
                'access_state': 'readable', 'eligible': eligible,
                'metadata': {'provider_publication_date_unverified': True,
                    'temporal_basis': 'actual_capture_available_at',
                    'capture_receipt_digest': item['source_locator']['capture_receipt_digest']}}
            reads.append({'status': 'readable' if eligible else 'ineligible_vintage_or_date',
                'source': source, 'items': [{'id': p['passage_id'], 'source_id': p['document_id'],
                    'body': p['passage'], 'digest': p['content_sha256'],
                    'locator': json.dumps(p['source_locator'], ensure_ascii=False, default=str)} for p in passages.values()] if eligible else [],
                'next_start': result.next_offset,
                'coverage': {'complete_document': False, 'captured_body_window_complete': not item['truncated'],
                    'returned_passages': len(passages) if eligible else 0,
                    'unread_scope': 'linked documents and source completeness unverified; '+
                        ('remaining captured text' if item['truncated'] else 'captured body fully returned')}})
        return {'request': request.model_dump(mode='json'), 'reads': reads,
                'execution_receipts': receipts, 'exclusions': exclusions,'runtime_adjustments':adjustments}
