import pytest
from financial_facts.source_links import match_original_fact


def pair():
    row={'id':'sql1','cik':'0000000001','accession':'0000000001-24-000001',
         'taxonomy':'us-gaap','concept':'Cash','unit':'USD','period_start':None,
         'period_end':'2024-12-31','dimensions':{},'value_decimal':'1000000'}
    return row,{**row,'value_decimal':'1000000.0','source_sha256':'a'*64,
                'locator':{'context_id':'c1','xpath':'/html/body/table/tr/td'}}


def test_exact_decimal_link():
    a,b=pair();assert match_original_fact(a,b)['status']=='matched'


@pytest.mark.parametrize('field,value',[('cik','2'),('accession','amended'),('concept','RestrictedCash'),
    ('unit','EUR'),('period_end','2023-12-31'),('dimensions',{'segment':'fund'})])
def test_equal_value_does_not_override_identity(field,value):
    a,b=pair();b[field]=value
    assert match_original_fact(a,b)['status']=='different_fact'


def test_unknown_dimension_is_not_group_scope():
    a,b=pair();del b['dimensions']
    assert match_original_fact(a,b)['status']=='unresolved'


def test_conflicting_value_not_silently_overwritten():
    a,b=pair();b['value_decimal']='999999'
    assert match_original_fact(a,b)['status']=='conflict'


def test_float_and_absent_locator_rejected():
    a,b=pair();b['value_decimal']=1000000.0
    assert match_original_fact(a,b)['status']=='unresolved'
    a,b=pair();del b['locator']
    assert match_original_fact(a,b)['status']=='unresolved'
