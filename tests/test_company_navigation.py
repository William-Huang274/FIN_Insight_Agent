from copy import deepcopy

import pytest

from sec_agent.research_foundation.company_navigation import company_navigation
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def test_default_company_does_not_spill_unrequested_large_sections():
    detail = {'card': {'name': 'Issuer', 'relationship_navigation': [{'id': str(i)} for i in range(200)]},
              'sources': [{'id': str(i), 'metadata': {'routing_metadata_v1': 'cache'}} for i in range(7)],
              'account_tree': [{'path': str(i)} for i in range(150)],
              'reporting_periods': list(range(20)), 'gaps': ['not processed'],
              'relationship_processing': {'status': 'partial', 'jobs': [{'source_id': 'source', 'evidence': 'retained'}]}}
    original = deepcopy(detail)
    request = SourceDocumentRequest(source_space='library', operation='company', entity_id='COMPANY::issuer', limit=3)
    result, total, next_offset = company_navigation(detail, request)
    assert total == 7 and next_offset == 3
    assert len(result['sources']) == 3
    assert 'account_tree' not in result and 'relationship_navigation' not in result['card']
    assert result['relationship_processing']['status'] == 'partial'
    assert detail == original
    menus = {item['section']: item for item in result['section_navigation']}
    assert menus['relationships']['total'] == 200
    for section, key in [('accounts', 'account_tree'), ('relationships', 'relationship_navigation')]:
        args = menus[section]['readback']
        args['offset'] = menus[section]['total'] - 2
        selected, count, more = company_navigation(detail, SourceDocumentRequest(**args))
        assert len(selected[key]) == 2 and more is None
        assert count == menus[section]['total']
    coverage, _, _ = company_navigation(detail, SourceDocumentRequest(**menus['coverage']['readback']))
    assert coverage['relationship_processing']['jobs'] == original['relationship_processing']['jobs']


def test_company_section_is_opt_in_wire_field_and_not_valid_for_other_operations():
    request = SourceDocumentRequest(operation='catalog')
    assert 'company_section' not in request.model_dump()
    with pytest.raises(ValueError, match='company_section_requires_library_company'):
        SourceDocumentRequest(source_space='library', operation='catalog', company_section='accounts')
