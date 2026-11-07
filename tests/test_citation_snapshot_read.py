from copy import deepcopy

import pytest

from apps.workbench.backend.citation_snapshot_read import resolve_citation_snapshot
from sec_agent.agent_runtime.case_artifacts import read_source_window
from sec_agent.agent_runtime.source_references import answer_citations
from test_organization_source_restore import public_calculation_fixture


def projected_pair():
    passage, calculation, _ = public_calculation_fixture()
    original = {**passage, 'title':'Quarterly disclosure'}
    preview = read_source_window(passage['passage_id'], original, 0, 100)
    # Use a real shorter window projection (same saved source identity).
    preview.update(text=preview['text'][:10], next_offset=10)
    full = answer_citations({'REF-fixture':{'source_id':passage['passage_id'],
                                           'source':original}})['REF-fixture']['sources'][0]
    return preview, full, calculation


def test_passage_preview_and_answer_binding_resolve_to_same_complete_window():
    preview, full, _ = projected_pair()
    before = deepcopy([preview, full])
    resolved = resolve_citation_snapshot([preview, full])
    assert resolved['text'] == full['passage']
    assert resolved['next_offset'] is None
    assert [preview, full] == before


@pytest.mark.parametrize('change', ['text','publication_date','source_locator','source_id'])
def test_different_original_cannot_hide_behind_projection_compatibility(change):
    preview, full, _ = projected_pair()
    if change=='text': preview['text']='not the original'
    elif change=='source_locator': preview[change]['character_start']=1
    else: preview[change]='different'
    with pytest.raises(ValueError):resolve_citation_snapshot([preview, full])


def test_calculation_payload_not_display_title_establishes_identity():
    _, _, calc = projected_pair()
    preview = read_source_window(calc['calculation_id'], calc, 0, 100)
    preview['calculation']=deepcopy(calc)
    full = answer_citations({'REF-fixture':{'source_id':calc['calculation_id'],
                                           'source':calc}})['REF-fixture']['sources'][0]
    assert resolve_citation_snapshot([preview, full])['calculation']==calc
    full['calculation']['value_decimal']='0'
    with pytest.raises(ValueError):resolve_citation_snapshot([preview, full])


def test_unknown_projection_remains_strict():
    row={'source_id':'ORG:S1','text':'original'}
    assert resolve_citation_snapshot([row,row])==row
    with pytest.raises(ValueError):resolve_citation_snapshot([row,{**row,'text':'other'}])
