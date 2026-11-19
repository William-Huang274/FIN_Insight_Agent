"""Describe the actual query scope, not an inferred disclosure absence verdict."""


def search_scope(result, request, *, public_web=False):
    if request.operation not in {'catalog', 'outline', 'search'}:
        return result
    body = dict(result)
    body['search_coverage'] = {
        'space': request.source_space, 'snapshot': body.get('source_snapshot_sha256'),
        'operation': request.operation, 'query': request.query,
        'document_id': request.document_id, 'offset': request.offset,
        'returned_items': len(body.get('items', [])), 'total_matches': body.get('total_matches'),
        'next_offset': body.get('next_offset'),
        'query_kind': 'ranked_passage_retrieval' if request.operation == 'search' else 'filtered_metadata_listing',
        'unfiltered_catalog_returned_in_full': request.operation == 'catalog' and not request.query.strip()
            and request.offset == 0 and not request.document_id and not getattr(request, 'organization_filter', None)
            and body.get('next_offset') is None,
        'issuer_non_disclosure_established': False,
        'meaning': 'Describes this query only. No match is not proof of library absence or issuer non-disclosure.',
        'available_followup_tools': ['read_source_document'] + (['read_public_source'] if public_web else []),
    }
    return body
