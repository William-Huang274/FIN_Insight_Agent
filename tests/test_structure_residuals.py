import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'engineering'))
from diagnose_document_structure_residuals import diagnose


def test_unflagged_document_is_not_declared_correct():
    r=diagnose({'route':'structured_json','blocks':[],'issues':[]})
    assert r['recognition_correctness']=='not_established_by_diagnostic'
    assert r['finding_count']==0


def test_navigation_exclusion_and_unknown_levels_keep_evidence():
    d={'route':'trafilatura_xml','blocks':[{'kind':'heading','text':'Title','level':None}],
       'issues':[{'kind':'heading_level_unknown','block':0}],
       'source_containers':[{'id':'s','xpath':'/aside/h2','role':'heading','excluded_navigation':True}],
       'unmatched_explicit_headings':[{'xpath':'/aside/h2','text':'Related news','level':2}]}
    r=diagnose(d)
    assert r['unmatched_explicit_headings'][0]['excluded_navigation'] is True
    assert not r['findings'][0]['automatic_repair_authorized']
    assert r['original_explicit_heading_count']==0
