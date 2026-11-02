import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts/engineering'))


def test_native_geometry_keeps_signs_and_rotation_mapping_without_ocr(monkeypatch):
    fitz=pytest.importorskip('pymupdf')
    from pdf_native_structure import describe_page
    def forbidden(*args,**kwargs):
        raise AssertionError('Implicit layout inference must not execute')
    monkeypatch.setattr(fitz,'_get_layout',forbidden,raising=False)
    document=fitz.open();page=document.new_page(width=400,height=500)
    page.insert_text((40,50),'Cash (12) USD')
    page.set_rotation(90)
    result=describe_page(page)
    assert result['width']==400 and result['height']==500
    assert result['rotation']==90
    assert '(12)' in ' '.join(w['text'] for w in result['panels']['words'])
    assert result['model_calls']==0 and result['ocr_calls']==0
    assert result['errors']==[]
    assert result['table_layout_model_enabled'] is False
    assert not result['quality_pass']
    assert result['rotation_matrix']!=result['derotation_matrix']
