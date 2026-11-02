from structured_source_contract import describe


def view(value):
    return describe({'route':'structured_json','structured_object':value})


def test_sql_reference_is_not_actual_rows():
    r=view({'data_table':'institution_positions','filed_at':'2026-08-01','period_end':'2026-06-30','rows':2242})
    assert r['kind']=='sql_table_reference' and r['record_count']==0 and r['declared_rows']==2242


def test_saved_observations_do_not_claim_historical_vintage():
    r=view({'metadata':{'id':'X','units':'Percent'},'observations':[{'date':'2026-01-01','value':'1.2'}]})
    assert r['record_count']==1 and not r['numeric_coercion']


def test_market_parallel_columns_detect_missing_values():
    r=view({'meta':{},'timestamp':[1,2],'indicators':{'quote':[{'close':[10]}]}})
    assert r['column_lengths_consistent'] is False


def test_registration_is_not_filing():
    r=view({'cik':'123','name':'Example','addresses':{}})
    assert r['kind']=='sec_entity_profile' and r['content_scope']=='entity_registration_not_filing_body'


def test_financial_api_failure_does_not_become_success():
    assert view({'list':[],'message':'none','status':'013'})['success'] is False


def test_empty_split_review_is_valid_zero_events():
    r=view({'meta':{},'splits':{},'requested_range':'2y','reviewed_through':'2026-01-01'})
    assert r['kind']=='split_event_review' and r['record_count']==0
