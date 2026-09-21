import copy
import sqlite3
import pytest

from test_industry_foundation import foundation
from test_counterparty_facts import setup, imported
from sec_agent.research_foundation import disclosure_register, disclosure_scope_reviews


def receipt(path, sid, pack):
    with sqlite3.connect(path) as db:
        digest=db.execute('SELECT digest FROM sources WHERE id=?',(sid,)).fetchone()[0]
    return dict(entity_id='NVIDIA',source_id=sid,source_digest=digest,category='suppliers',
        result='checked_no_explicit_fact',reviewed_sections=['Synthetic subsection'],
        scope_note='Synthetic narrow subsection only; not a real company review.',
        reviewer='test reviewer',reviewed_at='2026-09-21',evidence=pack['facts'][0]['evidence'])


def write(path, items):
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        return disclosure_scope_reviews.import_reviews(db,items)


def read(path,query='',as_of='2026-09-21',model=False):
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        return (disclosure_register.fact_page if model else disclosure_register.page)(db,'NVIDIA',query=query,as_of=as_of)


def test_scoped_absence_does_not_close_unreviewed_category_or_leak_earlier_date(foundation):
    path,_,sid,pack=setup(foundation)
    r=receipt(path,sid,pack);write(path,[r])
    result=read(path,query='suppliers')['items']
    assert len(result)==1 and result[0]['extraction_status']=='checked_no_explicit_fact'
    assert result[0]['structured_facts']==[] and result[0]['scope_review']['reviewed_sections']==['Synthetic subsection']
    assert all(x['extraction_status']=='extraction_pending' for x in read(path,query='customers')['items'])
    assert read(path,query='suppliers',as_of='2026-08-25')['total']==0
    model=read(path,query='suppliers',model=True)['items'][0]
    assert model['scope_review']['scope_note']==r['scope_note'] and 'evidence' not in model['scope_review']


@pytest.mark.parametrize('change',['digest','anchor','category_result','blank_section'])
def test_review_rejects_mismatched_source_and_contradictory_facts(foundation,change):
    path,_,sid,pack=setup(foundation);imported(path,pack)
    r=receipt(path,sid,pack)
    if change=='digest':r['source_digest']='different document'
    if change=='anchor':r['evidence']=copy.deepcopy(r['evidence']);r['evidence'][0]['quote']='not original'
    if change=='category_result':r['category']='customers'
    if change=='blank_section':r['reviewed_sections']=[' ']
    with pytest.raises(ValueError):write(path,[r])


def test_new_facts_survive_old_absence_receipt_and_changed_source_invalidates_receipt(foundation):
    path,w,sid,pack=setup(foundation)
    r=receipt(path,sid,pack);r['category']='customers';write(path,[r])
    # Duplicated old locator windows become one scoped result.
    assert read(path,query='customers')['total']==1
    imported(path,pack)
    row=read(path,query='customers')['items'][0]
    assert row['extraction_status']=='reviewed_facts_available' and len(row['structured_facts'])==1
    w.sql('UPDATE sources SET digest=? WHERE id=?',('changed',sid))
    assert 'scope_review' not in read(path,query='customers')['items'][0]
