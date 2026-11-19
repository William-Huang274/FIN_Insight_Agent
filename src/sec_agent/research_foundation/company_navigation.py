"""Paginated agent menus; the full company detail remains available to the UI."""
from copy import deepcopy


def company_navigation(detail, request):
    detail = deepcopy(detail)
    card = detail.get('card', {})
    processing = detail.pop('relationship_processing', {})
    sections = {
        'sources': detail.pop('sources', []),
        'accounts': detail.pop('account_tree', []),
        'periods': detail.pop('reporting_periods', []),
        'coverage': processing.pop('jobs', []),
        'relationships': card.pop('relationship_navigation', []),
        'gaps': detail.pop('gaps', []),
        'macro_series': detail.pop('macro_series', []),
    }
    fields = {'accounts': 'account_tree', 'periods': 'reporting_periods',
              'relationships': 'relationship_navigation'}
    section = request.company_section
    detail['relationship_processing'] = processing
    rows = sections[section]
    total = len(rows)
    page = rows[request.offset:request.offset + request.limit]
    if section == 'sources':
        for source in page:
            source.get('metadata', {}).pop('routing_metadata_v1', None)
    if section == 'coverage':
        detail['relationship_processing'] = {**processing, 'jobs': page}
    else:
        detail[fields.get(section, section)] = page
    detail['result_state'] = 'retrieval_candidate'
    detail['company_section'] = section
    detail['section_total'] = total
    detail['sources_total'] = len(sections['sources'])
    detail['section_navigation'] = [
        {'section': name, 'total': len(items), 'readback': {
            'source_space': 'library', 'operation': 'company',
            'entity_id': request.entity_id, 'company_section': name,
            'offset': 0, 'limit': request.limit,
        }} for name, items in sections.items()
    ]
    return detail, total, request.offset + request.limit if request.offset + request.limit < total else None
