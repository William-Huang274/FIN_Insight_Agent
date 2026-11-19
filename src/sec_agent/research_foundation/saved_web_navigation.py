"""Read bounded web originals already admitted to this composition's source view.

This is navigation over host-restored receipts, not discovery, capture, or source
admission. Unknown documents still go through the normal scoped web reader.
"""
from copy import deepcopy
from datetime import date
from hashlib import sha256

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from .source_document_navigation import SourceDocumentResult
from .web_source_navigation import _execution_receipt


def read_saved_web_window(request, sources, *, research_as_of):
    if request.source_space != 'web' or request.operation != 'read':
        return None
    rows = {}
    for item in sources:
        if (item.get('result_state') != 'source_bound_passage'
                or item.get('document_id') != request.document_id
                or item.get('writer_citable') is not True
                or item.get('numeric_fact_authority') is not False):
            continue
        locator = item.get('source_locator') or {}
        start, end = locator.get('character_start'), locator.get('character_end')
        text = item.get('passage')
        if (type(start) is not int or type(end) is not int or start < 0 or end <= start
                or not isinstance(text, str) or len(text) != end - start
                or locator.get('document_id') != request.document_id):
            raise ValueError('saved_web_original_locator_invalid')
        digest = sha256(text.encode('utf-8')).hexdigest()
        identity = f'PASSAGE::{request.document_id}::{start}::{digest[:16]}'
        if (item.get('passage_id') != identity or item.get('content_sha256') != digest
                or locator.get('content_sha256') != digest
                or not locator.get('capture_receipt_digest')):
            raise ValueError('saved_web_original_identity_invalid')
        published = item.get('publication_date')
        if published:
            try:
                after_cutoff = date.fromisoformat(published[:10]) > research_as_of.date()
            except ValueError:
                after_cutoff = False  # Unknown date retains its original qualifier.
            if after_cutoff:
                raise ValueError('web_source_publication_after_research_as_of')
        if identity in rows and rows[identity] != item:
            raise ValueError('saved_web_original_identity_conflict')
        rows[identity] = item
    if not rows:
        return None
    rows = sorted(rows.values(), key=lambda row: row['source_locator']['character_start'])
    captures = {row['source_locator']['capture_receipt_digest'] for row in rows}
    if len(captures) != 1:
        raise ValueError('saved_web_document_has_multiple_captures_use_source_id_readback')
    snapshot = canonical_digest(rows)
    selected = [r for r in rows if r['source_locator']['character_start'] <= request.offset
                < r['source_locator']['character_end']]
    if not selected:
        windows = tuple({'result_state': 'retrieval_candidate', 'writer_citable': False,
            'numeric_fact_authority': False, 'document_id': request.document_id,
            'saved_passage_id': r['passage_id'], 'readback': {
                'source_space': 'web', 'operation': 'read', 'document_id': request.document_id,
                'offset': r['source_locator']['character_start'],
                'max_characters': min(len(r['passage']), request.max_characters)}} for r in rows)
        return SourceDocumentResult(operation='read', items=windows, next_offset=None,
            total_matches=0, source_snapshot_sha256=snapshot,
            execution_receipt=_execution_receipt(request, snapshot, 'coverage_boundary'),
            notice='Requested offset is outside the saved windows. Read one of these exact saved ranges '
                   'or search for a fresh document locator. No network request was made; this is not non-disclosure.')
    row = max(selected, key=lambda r: r['source_locator']['character_end'])
    start = row['source_locator']['character_start']
    end = min(row['source_locator']['character_end'], request.offset + request.max_characters)
    result = deepcopy(row)
    if request.offset != start or end != row['source_locator']['character_end']:
        text = row['passage'][request.offset-start:end-start]
        digest = sha256(text.encode('utf-8')).hexdigest()
        result.update(passage=text, content_sha256=digest,
            passage_id=f'PASSAGE::{request.document_id}::{request.offset}::{digest[:16]}',
            saved_parent_passage_id=row['passage_id'], truncated=True)
        result['source_locator'].update(character_start=request.offset, character_end=end, content_sha256=digest)
    return SourceDocumentResult(operation='read', items=(result,),
        next_offset=end if any(r['source_locator']['character_start'] <= end
                              < r['source_locator']['character_end'] for r in rows) else None,
        total_matches=1, source_snapshot_sha256=snapshot,
        execution_receipt=_execution_receipt(request, snapshot, 'ok'),
        notice='Read from the authorized saved original, without web search or capture. '
               'Only the saved character windows are available, not the whole document. '
               'Original capture, publication qualifiers and citation authority are retained.')
