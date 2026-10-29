import json
from hashlib import sha256

import pytest

from retrieval.indexed_source_metadata import node_metadata, merge_metadata
from sec_agent.research_foundation.organization_source_filter import source_metadata
from sec_agent.research_foundation.research_library import publish_library, ResearchLibrary


def nodes():
    return [dict(node_id=f'n{i}', parent_document_id='DOC', title='Unrelated title',
        stable_url='https://example.test/original', publication_date='2026-01-01',
        raw_body_sha256='a'*64, content=body, content_sha256=sha256(body.encode()).hexdigest(),
        company='Example Corporation', issuer_id='XYZ', ticker='XYZ',
        source_role='issuer_earnings_release') for i, body in enumerate(('Results', 'Counterparty Other Corp.'))]


def source():
    return dict(id='DOC', url='https://example.test/original', digest='a'*64,
                metadata=json.dumps({'import_origin':'existing_public_library'}))


def test_new_publication_and_old_capture_use_same_document_metadata(tmp_path):
    path = tmp_path/'library.sqlite'
    publish_library(path, [], public_sources_confirmed=True, public_nodes=nodes())
    stored = ResearchLibrary(path)._query('SELECT * FROM sources')[0]
    new = source_metadata({'source':stored})
    old = source_metadata({'source':source(), 'node_recovery':{'nodes':nodes()}})
    assert new['company_name'] == old['company_name'] == 'Example Corporation'
    assert new['indexed_source_metadata'] == old['indexed_source_metadata']
    assert new['issuer_id'] is None and old['issuer_id'] is None
    assert old['indexed_source_metadata']['values']['issuer_id'] == 'XYZ'
    assert 'fact_entity_identifiers' not in old
    assert 'verified_company_names' not in old


@pytest.mark.parametrize('field,value', [('parent_document_id','OTHER'), ('stable_url','https://other.test'),
                                      ('raw_body_sha256','b'*64)])
def test_nodes_cannot_lend_metadata_to_a_different_original(field, value):
    rows=nodes();rows[1][field]=value
    with pytest.raises(ValueError, match='binding_mismatch'):
        source_metadata({'source':source(), 'node_recovery':{'nodes':rows}})


def test_joint_or_conflicting_companies_remain_unknown_and_order_independent():
    rows=nodes();rows[1]['company']='Other Corporation'
    a=node_metadata(source(), rows);b=node_metadata(source(), list(reversed(rows)))
    assert a == b and 'company' not in a['values']
    value=source_metadata({'source':source(), 'node_recovery':{'nodes':rows}})
    assert value['company_name'] is None
    assert value['metadata_conflicts'] == ['company_name']


def test_source_and_node_conflict_does_not_silently_prefer_first():
    s=source();s['metadata']=json.dumps(dict(import_origin='existing_public_library',
                                           company='Different Company', entity_id='COMPANY::different'))
    value=source_metadata({'source':s, 'node_recovery':{'nodes':nodes()}})
    assert value['company_name'] is None and value['issuer_id'] is None
    evidence=merge_metadata(json.loads(s['metadata']), node_metadata(s,nodes()))
    assert evidence['indexed_company_conflict']['source_company']=='Different Company'
    assert evidence['indexed_company_conflict']['node_companies']==['Example Corporation']


def test_partial_or_missing_metadata_is_not_inferred_from_title_body_or_ticker():
    rows=nodes();del rows[1]['company']
    assert 'company' in node_metadata(source(), rows)['incomplete']
    assert source_metadata({'source':source(), 'node_recovery':{'nodes':rows}})['company_name'] is None
    for row in rows:row.pop('company',None)
    assert source_metadata({'source':source(), 'node_recovery':{'nodes':rows}})['company_name'] is None


def test_recovered_company_filters_other_issuer_without_hiding_matching_source():
    from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
    descriptor=source_metadata({'source':source(), 'node_recovery':{'nodes':nodes()}})
    from sec_agent.research_foundation.organization_source_filter import select_documents, OrganizationSourceFilter
    metadata={'restored':descriptor, 'unknown':{'company_name':None},
              'other':{'company_name':'Other Corporation','issuer_id':'COMPANY::other'},
              'canonical':{'company_name':'Example Corporation','issuer_id':'COMPANY::example'}}
    assert select_documents(metadata,OrganizationSourceFilter(company_name='Other Corporation'))[0]=={'other'}
    assert select_documents(metadata,OrganizationSourceFilter(company_name='Example Corporation'))[0]=={'restored','canonical'}
    matching=plan_query('Example Corporation results',metadata,policy='conservative.v5')
    assert select_planned(metadata,matching)[0]=={'restored','canonical','unknown'}
    other=plan_query('Other Corporation results',metadata,policy='conservative.v5')
    assert select_planned(metadata,other)[0]=={'other','unknown'}
