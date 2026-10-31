import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'/'engineering'))
from build_native_structure_coverage import coverage
from run_native_structure_qualification import route


def test_all_bindings_and_prior_artifact_selection_survive_partial_adaptation():
    bindings=[dict(document_id='a',original_id='one',artifact_path='prior'),
              dict(document_id='b',original_id='one',artifact_path='prior'),
              dict(document_id='c',original_id='two',artifact_path='untested'),
              dict(document_id='d',original_id=None,artifact_path='derived')]
    result=coverage(bindings,dict(rows=[dict(source_sha256='one',status='adapted_requires_quality_review')]))
    assert len(result)==4
    assert [r['artifact_path'] for r in result]==['prior','prior','untested','derived']
    assert result[2]['native_adaptation_state']=='native_adaptation_not_run'
    assert result[3]['native_adaptation_state']=='original_unavailable_existing_representation_retained'
    assert not any(r['native_quality_pass'] for r in result)


def test_unsupported_routes_do_not_masquerade_as_adapted_documents():
    assert route({'route':'edgartools'})==('edgartools',True)
    assert route({'route':'trafilatura_xml'})==('trafilatura',False)
    assert route({'route':'pypdf_text_diagnostic'})==(None,False)
