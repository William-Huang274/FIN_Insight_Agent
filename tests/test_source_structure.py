from hashlib import sha256
import pytest
from retrieval.source_structure import source_structure


def bundle(text, cut=None):
    positions=[0,cut,len(text)] if cut else [0,len(text)]
    return {'source':{'digest':sha256(text.encode()).hexdigest()},'text':text,
        'chunks':[{'id':str(i),'source_char_start':a,'source_char_end':b,'body':text[a:b],
            'digest':sha256(text[a:b].encode()).hexdigest(),'kind':'text','flags':'["inherited_parent_locator"]'}
            for i,(a,b) in enumerate(zip(positions,positions[1:]))]}


def test_explicit_footnote_binding_crosses_chunk_boundary_not_section():
    text='ITEM 2. Properties\n[TABLE: original]\nCost (1) | USD millions\n100 | 200\n[/TABLE]\n[TABLE: layout]\n | | \n[/TABLE]\n(1) Estimates may change.\nITEM 3. Legal Proceedings\nLitigation.'
    value=bundle(text,text.index('(1) Estimates'))
    result=source_structure(value)
    assert result['1']['original_flags']==['inherited_parent_locator']
    note=result['1']['footnotes'][0]
    assert note['table_chunk_ids']==['0'] and note['table_chunk_count']==1
    assert text[note['table']['source_char_start']:note['table']['source_char_end']].startswith('[TABLE: original]')
    assert 'Legal' not in text[note['table']['source_char_start']:note['table']['source_char_end']]
    assert result['1']['section']['heading']=='ITEM 2. Properties'


@pytest.mark.parametrize('between,marker', [('Unrelated section\n','1'),('\n','2'),('ITEM 3. Legal Proceedings\n','1')])
def test_abstains_without_explicit_adjacent_matching_marker(between,marker):
    text='[TABLE: original]\nCost (1) | 100\n[/TABLE]\n'+between+'('+marker+') Estimates.'
    assert source_structure(bundle(text))['0']['footnotes']==[]


def test_corrupted_chunk_is_rejected():
    value=bundle('original text');value['chunks'][0]['body']='changed'
    with pytest.raises(ValueError,match='chunk_mismatch'):source_structure(value)


def test_nested_or_unclosed_table_does_not_manufacture_binding():
    text='[TABLE: outer]\nCost (1) | 100\n[TABLE: inner]\nCost (1) | 200\n[/TABLE]\n(1) Estimates.'
    assert source_structure(bundle(text))['0']['footnotes']==[]


def test_organization_search_overlay_preserves_frozen_payload_and_revocation(tmp_path,monkeypatch):
    from test_organization_candidate_index import prepared, query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    nav, reader, state, directory, grant=prepared(tmp_path,monkeypatch)
    before={p.name:sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.name in ('index.json','vectors.npy','navigation.sqlite')}
    result=nav.navigate(query(organization_query_planning='conservative.v2'))
    assert all('source_structure' in r for r in result.items)
    assert before=={p.name:sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.name in before}
    cached=nav.navigate(query(organization_query_planning='conservative.v2'))
    assert cached.items[0]['retrieval']['response_cache_hit']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(query(organization_query_planning='conservative.v2'))
