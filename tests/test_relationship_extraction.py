import copy
import json
import sqlite3
import pytest
from test_industry_foundation import foundation, publish
from sec_agent.research_foundation.relationship_extraction import digest_json, import_job, prepare_job, assertion_page
from sec_agent.research_foundation.industry_data import company_detail
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def candidate(foundation):
    path,w,_=foundation
    w.sql('INSERT INTO entities VALUES(?,?,?)',('BUYER','company','Buyer'))
    text='We agreed to supply Buyer with processors next year. Two anonymous customers each represent 11% of FY2026 revenue.'
    sid=w.source('NVIDIA','https://example.org/relation','Issuer annual report','filing',text,published='2026-08-26')
    pid=w.sql('SELECT id FROM passages WHERE source_id=?',(sid,))[0]['id']
    relation=dict(subject_name='NVIDIA',subject_id='NVIDIA',object_name='Buyer',object_id='BUYER',predicate='supplies',status='planned',role='Processors',scope_note='Agreement for next year, not delivered.',source_id=sid,evidence=[dict(passage_id=pid,quote=text)])
    job=dict(version='relation_extraction.v1',job_id='test-job',model='synthetic',company_ids=['NVIDIA'],relations=[relation],disclosures=[],new_entities=[],coverage=[dict(entity_id='NVIDIA',sources_reviewed=[dict(source_id=sid,passage_ids=[pid],sections_checked=['Business'],method='Synthetic fixture review')],categories={k:dict(status='extracted',detail='Synthetic bounded source') for k in ('customers','suppliers','investment_control','cooperation')},remaining_source_ids=[],gaps=[])])
    return path,w,job


def review(job):
    return dict(job_digest=digest_json(job),reviewer='independent-fixture',reviewed_at='2026-09-21',relation_verdicts={str(i):dict(status='approved',reason='Synthetic fixture review') for i in range(len(job['relations']))},disclosure_verdicts={str(i):dict(status='approved',reason='Synthetic fixture review') for i in range(len(job['disclosures']))})


def connect(path):
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON');return db


def test_reviewed_facts_reach_tools_and_events_are_not_collapsed(foundation):
    path,w,job=candidate(foundation)
    second=copy.deepcopy(job['relations'][0]);second.update(role='Network cards',scope_note='Separate announced order',status='announced')
    job['relations'].append(second)
    with connect(path) as db:
        assert not prepare_job(db,job)['errors']
        assert import_job(db,job,review(job))['relations']==2
        import_job(db,job,review(job))
        assert assertion_page(db,'NVIDIA')['total']==2
        assert assertion_page(db,'NVIDIA',as_of='2026-08-25')['total']==0
    library=publish(path,w)
    assert len([e for e in library.graph_search('NVIDIA','2026-09-21')['edges'] if e['id'].startswith('RELATION::')])==2
    output=library.navigate(SourceDocumentRequest(source_space='library',operation='data',entity_id='NVIDIA',data_kind='relationships'),'2026-09-21').model_dump(mode='json')
    assert 'Agreement for next year' in str(output)
    assert company_detail(path,'NVIDIA')['relationship_processing']['jobs'][0]['entity_id']=='NVIDIA'


def test_modified_candidate_cannot_reuse_approval(foundation):
    path,_,job=candidate(foundation);receipt=review(job)
    job['relations'][0]['status']='completed'
    with connect(path) as db,pytest.raises(ValueError,match='review_not_bound'):
        import_job(db,job,receipt)


def test_undated_original_uses_capture_boundary_without_inventing_publication(foundation):
    path,_,job=candidate(foundation)
    with connect(path) as db:
        sid=job['relations'][0]['source_id']
        metadata=json.loads(db.execute('SELECT metadata FROM sources WHERE id=?',(sid,)).fetchone()[0])
        metadata['known_at']='2026-09-20T12:00:00Z'
        db.execute('UPDATE sources SET published_at=NULL,metadata=? WHERE id=?',(json.dumps(metadata),sid))
        import_job(db,job,review(job))
        assert assertion_page(db,'NVIDIA',as_of='2026-09-19')['total']==0
        row=assertion_page(db,'NVIDIA',as_of='2026-09-20')['items'][0]
        assert row['published_at'] is None and row['date_basis']=='captured'
        edge=db.execute("SELECT published_at,qualifiers FROM edges WHERE id LIKE 'RELATION::%'").fetchone()
        assert edge[0]=='2026-09-20' and json.loads(edge[1])['published_at'] is None


def test_issuer_can_retrieve_subsidiary_statement_without_becoming_contract_party(foundation):
    path,_,job=candidate(foundation)
    rel=job['relations'][0]
    rel.update(subject_name='Buyer',subject_id='BUYER',object_name='processors',object_id=None)
    with connect(path) as db:
        import_job(db,job,review(job))
        row=assertion_page(db,'NVIDIA')['items'][0]
        assert row['reporting_entity_id']=='NVIDIA'
        assert row['subject']=='BUYER' and row['object'] is None
        assert db.execute("SELECT count(*) FROM edges WHERE id LIKE 'RELATION::%'").fetchone()[0]==0


def test_revision_and_retired_parse_do_not_leak_through_relationship_query(foundation):
    path,_,job=candidate(foundation)
    with connect(path) as db:
        sid=job['relations'][0]['source_id']
        metadata=json.loads(db.execute('SELECT metadata FROM sources WHERE id=?',(sid,)).fetchone()[0])
        metadata['known_at']='2026-09-20T12:00:00Z'
        db.execute("UPDATE sources SET vintage='current_revision',metadata=? WHERE id=?",(json.dumps(metadata),sid))
        import_job(db,job,review(job))
        assert assertion_page(db,'NVIDIA',as_of='2026-09-19')['total']==0
        row=assertion_page(db,'NVIDIA',as_of='2026-09-20')['items'][0]
        assert row['published_at']=='2026-08-26' and row['known_as_of']=='2026-09-20'
        assert db.execute("SELECT published_at FROM edges WHERE id LIKE 'RELATION::%'").fetchone()[0]=='2026-09-20'
        db.execute("UPDATE sources SET access_state='superseded_parse' WHERE id=?",(sid,))
        assert assertion_page(db,'NVIDIA')['total']==0


def test_single_section_worker_label_is_normalized_for_ui(foundation):
    from sec_agent.research_foundation.relationship_extraction import coverage_page
    path,_,job=candidate(foundation)
    job['coverage'][0]['sources_reviewed'][0]['sections_checked']='Business'
    with connect(path) as db:
        import_job(db,job,review(job))
        assert coverage_page(db,'NVIDIA')['jobs'][0]['sources_reviewed'][0]['sections_checked']==['Business']


def test_unknown_scope_and_duplicate_identity_are_review_failures(foundation):
    path,_,job=candidate(foundation)
    wrong=copy.deepcopy(job)
    wrong['company_ids']=['LOCAL::issuer']
    wrong['coverage'][0]['entity_id']='LOCAL::issuer'
    relation=job['relations'][0]
    job['new_entities']=[dict(provisional_id='LOCAL::buyer',name='Buyer',kind='company',
        identity_evidence=[dict(source_id=relation['source_id'],**relation['evidence'][0])])]
    job['relations'][0]['object_id']='LOCAL::buyer'
    with connect(path) as db:
        assert any('coverage_unknown_entity' in e['error'] for e in prepare_job(db,wrong)['errors'])
        assert any('existing_identity_requires_resolution' in e['error'] for e in prepare_job(db,job)['errors'])
        with pytest.raises(ValueError,match='entity_or_coverage_validation_failed'):
            import_job(db,wrong,review(wrong))


@pytest.mark.parametrize('failure',['source','quote','coverage','counterparty'])
def test_invalid_source_or_scope_is_not_imported(foundation,failure):
    path,_,job=candidate(foundation)
    if failure=='source':job['relations'][0]['source_id']='unknown'
    if failure=='quote':job['relations'][0]['evidence'][0]['quote']='invented'
    if failure=='counterparty':job['relations'][0]['object_name']='Different company'
    if failure=='coverage':job['coverage'][0]['sources_reviewed'][0]['passage_ids']=['unknown']
    with connect(path) as db:
        assert prepare_job(db,job)['errors']
        with pytest.raises(ValueError):import_job(db,job,review(job))


def test_disclosure_validation_rolls_back_entire_job(foundation):
    path,_,job=candidate(foundation);rel=job['relations'][0]
    job['disclosures']=[dict(entity_id='NVIDIA',category='customers',source_id=rel['source_id'],counterparty_name='two customers',identity_kind='aggregate',relationship='customer',role='Sales',fiscal_year=2026,count=2,measurement_basis='each',measures=[dict(metric='revenue_share',value='22',unit='percent',operator='=',denominator='FY2026 revenue')],scope_note='Unsupported value intentional',evidence=rel['evidence'])]
    with connect(path) as db:
        with pytest.raises(ValueError,match='value_not_in_evidence'):import_job(db,job,review(job))
        assert db.execute('SELECT count(*) FROM relationship_assertions').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM relationship_extraction_jobs').fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM edges WHERE id LIKE 'RELATION::%'").fetchone()[0]==0


def test_unresolved_identity_stays_queryable_without_named_edge(foundation):
    path,_,job=candidate(foundation);job['relations'][0]['object_id']=None
    with connect(path) as db:
        import_job(db,job,review(job))
        row=assertion_page(db,'NVIDIA')['items'][0]
        assert row['review_status']=='identity_unresolved'
        assert row['object'] is None
        assert db.execute("SELECT count(*) FROM edges WHERE id LIKE 'RELATION::%'").fetchone()[0]==0


def test_candidate_approval_does_not_accept_source_coverage(foundation):
    path,_,job=candidate(foundation)
    with connect(path) as db:
        import_job(db,job,review(job))
        states=db.execute("SELECT status FROM data_gaps WHERE entity_id='NVIDIA' AND category LIKE 'relationship_processing:%'").fetchall()
        assert states and all(r[0]=='review_pending' for r in states)


def test_scope_cannot_be_accepted_with_pending_extraction(foundation):
    path,_,job=candidate(foundation)
    job['coverage'][0]['categories']['suppliers']['status']='processing_pending'
    receipt=review(job)
    receipt['coverage_verdicts']={'NVIDIA':dict(status='complete',reason='Intentionally inconsistent fixture')}
    with connect(path) as db,pytest.raises(ValueError,match='complete_scope_has_unfinished'):
        import_job(db,job,receipt)
