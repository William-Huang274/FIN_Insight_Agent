from copy import deepcopy
import pytest
from scripts.data_retrieval.combine_financial_snapshots import combine


def policy(ticker, digest):
    return dict(schema_version='fixture',minimum_period_end='2020-01-01',allowed_forms=['10-K'],
        metric_definitions=[{'id':'cash','unit':'USD'}],authority={'read':True},
        research_as_of='2026-09-02',recorded_at='2026-09-02T00:00:00Z',
        source_bindings=[{'ticker':ticker,'companyfacts_sha256':digest}],acceptance_qrels=['old'])


def test_union_preserves_inputs_and_rejects_conflicting_snapshots():
    a,b=policy('A','one'),policy('B','two');before=deepcopy([a,b])
    result=combine([a,b,a])
    assert result['source_bindings']==a['source_bindings']+b['source_bindings']
    assert [a,b]==before and result['acceptance_qrels']==[]
    with pytest.raises(ValueError,match='conflicting_issuer_snapshot'):
        combine([a,policy('A','different')])
    b['metric_definitions'][0]['unit']='EUR'
    with pytest.raises(ValueError,match='incompatible_financial_snapshot:metric_definitions'):
        combine([a,b])
