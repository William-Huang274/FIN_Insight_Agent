import json
import sqlite3
from retrieval.library_chunks import MAX_BODY,build_chunks,split_parent,quote_spans


def test_long_section_offsets_and_heading_preserved():
    body='# Customers\n'+('A customer purchased capacity.\n'*700)+'\n# Suppliers\n'+('Supplier provides memory.\n'*500)
    p={'id':'P','source_id':'S','locator':'Item 8','body':body}
    chunks=list(split_parent(p,'Annual report'))
    assert max(len(c['body']) for c in chunks)<=MAX_BODY
    assert all(body[c['char_start']:c['char_end']]==c['body'] for c in chunks)
    covered=set()
    for c in chunks:covered.update(range(c['char_start'],c['char_end']))
    assert all(i in covered for i,v in enumerate(body) if not v.isspace())
    assert any('# Suppliers' in c['context'] for c in chunks)
    assert chunks==list(split_parent(p,'Annual report'))


def test_table_context_and_no_number_fuzzy_matching():
    body='|Customer|Revenue|\n|---|---|\n'+('|A|123|\n'*1500)
    chunks=list(split_parent({'id':'P','source_id':'S','locator':'Table','body':body},'Report'))
    assert any('table_header_in_context' in c['flags'] and '|Customer|Revenue|' in c['context'] for c in chunks[1:])
    assert quote_spans('A\n   123',{'quote':'A 123'})==[(0,8,'whitespace_quote')]
    assert quote_spans('A 124',{'quote':'A 123'})==[]


def test_graph_quote_crosses_chunks_and_unknown_stays_unknown(tmp_path):
    from sec_agent.research_foundation.research_snapshot import build_snapshot
    path=tmp_path/'library.sqlite'
    text=('Long introduction. '*290)+'KEY CUSTOMERS agreed 12 MW.'+(' Further details.'*300)
    quote='KEY CUSTOMERS agreed 12 MW.'
    build_snapshot(path,[dict(id='S',title='Report',url='https://example.org',published_at='2026-01-01',vintage='dated_original',access_state='readable',digest='x')],
      [dict(id='P',source_id='S',locator='Customers',body=text)],entities=[dict(id='A',kind='company',name='A'),dict(id='B',kind='company',name='B')],
      edges=[dict(id='E',subject='A',object='B',predicate='supplies',source_id='S',locator='Customers',published_at='2026-01-01',status='agreement'),
             dict(id='U',subject='B',object='A',predicate='invests',source_id='S',locator='unknown',published_at='2026-01-01',status='announced')])
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE relationship_assertions(id TEXT,payload TEXT)')
        db.execute('INSERT INTO relationship_assertions VALUES(?,?)',('E',json.dumps({'evidence':[{'passage_id':'P','quote':quote}]})))
    result=build_chunks(path)
    assert result['edge_binding']=={'quote_bound':1,'unresolved':1}
    with sqlite3.connect(path) as db:
        rows=db.execute("SELECT body FROM retrieval_chunks c JOIN edge_chunk_links l ON c.id=l.chunk_id WHERE edge_id='E'").fetchall()
        assert any(quote in r[0] for r in rows)
        assert db.execute('SELECT body FROM passages WHERE id="P"').fetchone()[0]==text


def test_runtime_child_search_read_and_graph_evidence(tmp_path):
    from test_research_library import publish
    from sec_agent.research_foundation.research_library import ResearchLibrary,digest_file
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    _,path,manifest=publish(tmp_path)
    build_chunks(path)
    manifest['sha256']=digest_file(path)
    path.with_suffix('.sqlite.manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    lib=ResearchLibrary(path)
    assert lib.search(['supply'],'2024-01-01')==[]
    found=lib.search(['supply'],'2025-02-01')
    assert found[0]['id'].startswith('CHUNK::')
    cid=found[0]['id']
    graph=lib.graph_search('A','2025-02-01')
    assert graph['edges'][0]['evidence'][0]['id']==cid
    assert graph['edges'][0]['chunk_binding']['status']=='parent_locator_bound'
    req=SourceDocumentRequest(source_space='library',operation='read',document_id='DOC',node_id=cid)
    read=lib.navigate(req,'2025-02-01')
    assert read.items[0]['parent_node_id']=='PASSAGE::p'
    assert read.items[0]['passage']==found[0]['body']
    old=lib.navigate(req.model_copy(update={'node_id':'PASSAGE::p'}),'2025-02-01')
    assert old.items[0]['passage']==found[0]['body']


def test_reviewed_supplement_requires_exact_parent_and_quote(tmp_path):
    from test_research_library import publish
    from retrieval.library_chunks import add_reviewed_bindings
    _,path,_=publish(tmp_path);build_chunks(path)
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        record=dict(edge_id='AB',source_id='DOC',evidence=[dict(passage_id='PASSAGE::p',quote='A announced supply to B.')])
        add_reviewed_bindings(db,[record],'reader')
        assert db.execute('SELECT status FROM edge_chunk_coverage').fetchone()[0]=='quote_bound'


def test_oversized_legacy_parent_offers_child_readbacks(tmp_path):
    from test_research_library import publish
    from sec_agent.research_foundation.research_library import ResearchLibrary,digest_file
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    _,path,manifest=publish(tmp_path)
    with sqlite3.connect(path) as db:db.execute('UPDATE passages SET body=?',('Annual report details. '*10000,))
    build_chunks(path);manifest['sha256']=digest_file(path)
    path.with_suffix('.sqlite.manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    lib=ResearchLibrary(path)
    request=SourceDocumentRequest(source_space='library',operation='read',document_id='DOC',node_id='PASSAGE::p',limit=2)
    result=lib.navigate(request,'2025-02-01')
    assert 'use_child_readbacks' in result.notice and result.next_offset==2
    assert all(r['result_state']=='retrieval_candidate' for r in result.items)
    child=lib.navigate(SourceDocumentRequest(**result.items[0]['readback']),'2025-02-01')
    assert child.items[0]['result_state']=='source_bound_passage' and len(child.items[0]['passage'])<=MAX_BODY
