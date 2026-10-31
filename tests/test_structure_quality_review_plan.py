from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/engineering'))
from freeze_structure_quality_review import family,select


def test_forms_have_provenance_and_titles_do_not_override_known_forms():
    assert family({'form':'10-Q/A','title':'10-K comparison'},'edgartools')==('SEC_10-Q','catalog_form')
    assert family({'title':'Example 10-K 2025'},'edgartools')==('SEC_10-K','title_hint_requires_review')
    assert family({'title':'10-K and 10-Q'},'edgartools')[0]=='SEC_other'
    assert family({'form':'S-1','title':'10-K'},'edgartools')[0]=='SEC_other'
    assert family({'title':'10-K'},'structured_json')[0]=='structured_json'


def test_freeze_is_order_independent_and_keeps_clean_risk_samples_separate():
    rows=[{'original_id':str(i),'family':'html','diagnostic_stratum':'flagged' if i<8 else 'no_current_flags',
           'catalog_text_length_hint':i} for i in range(16)]
    a,strata=select(rows,'fixed',4);b,other=select(list(reversed(rows)),'fixed',4)
    assert a==b and strata==other
    assert len(a)==len({r['original_id'] for r in a})==9
    random=[r for r in a if r['selection']=='seeded_stratified_screening']
    assert sum(r['diagnostic_stratum']=='no_current_flags' for r in random)==4
    assert len(random)==8 and a[-1]['population_inference_allowed'] is False


def test_small_stratum_is_censused_without_duplicate_risk_supplement():
    rows=[{'original_id':'one','family':'pdf','diagnostic_stratum':'flagged','catalog_text_length_hint':1}]
    sample,strata=select(rows,'fixed',4)
    assert len(sample)==1 and strata[0]['population']==strata[0]['selected']==1
