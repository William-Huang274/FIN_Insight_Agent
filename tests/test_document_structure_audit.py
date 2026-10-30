"""Structure receipts preserve uncertainty and the existing lossless repairs."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'/'engineering'
sys.path.insert(0,str(SCRIPTS))
import document_structure_audit as audit
from probe_document_parsers import parse,resolve_form
from structured_web_blocks import normalize_web as normalize_fragment
from finalize_structure_prechunks import classify


def test_outline_parent_and_unknown_level():
    headings,issues=audit.outline([
        {'kind':'heading','text':'Chapter One','level':1},
        {'kind':'heading','text':'Subsection A','level':2},
        {'kind':'heading','text':'Subsection B','level':2},
        {'kind':'heading','text':'Unknown level','level':None},
        {'kind':'heading','text':'New branch','level':2}])
    assert [h['parent_block'] for h in headings]==[None,0,0,None,None]
    assert any(i['kind']=='heading_level_unknown' for i in issues)


def test_edgar_heading_children_do_not_destroy_title_or_level(monkeypatch):
    inline=SimpleNamespace(type=SimpleNamespace(name='TEXT'),children=[],text=lambda:'Half',path='inline',metadata={})
    heading=SimpleNamespace(type=SimpleNamespace(name='HEADING'),children=[inline],text=lambda:'Full title',level=2,path='h',metadata={})
    root=SimpleNamespace(type=SimpleNamespace(name='DOCUMENT'),children=[heading])
    document=SimpleNamespace(root=root,sections={},xbrl_facts=[],text=lambda:'Full title')
    edgar=ModuleType('edgar');documents=ModuleType('edgar.documents');documents.parse_html=lambda _,config:document
    documents.ParserConfig=lambda **kw:SimpleNamespace(**kw)
    monkeypatch.setitem(sys.modules,'edgar',edgar);monkeypatch.setitem(sys.modules,'edgar.documents',documents)
    result=parse(b'<h2>Full title</h2>','','edgartools')
    assert [(b['kind'],b['text'],b['level']) for b in result['blocks']]==[('heading','Full title',2)]


def test_form_resolution_prefers_original_and_marks_conflict():
    raw=b'<html><ix:nonNumeric name="dei:DocumentType">10-Q</ix:nonNumeric></html>'
    assert resolve_form(raw,'Unreliable title 10-K')['form']=='10-Q'
    assert resolve_form(raw,'Title','10-K')['status']=='conflict'
    assert resolve_form(b'<p>Text</p>','Annual report')['form'] is None


def test_prose_chunks_do_not_cross_chapter_and_keep_exact_offsets():
    text='# One\n\n'+('完整句子。'*1700)+'\n\n## Two\n\nTail sentence.\n'
    result=audit.inspect(text.encode(),{'capture':{'content_type':'text/plain'}})
    for i,b in enumerate(result['blocks']):
        if b['kind']=='heading':continue
        slices=[b['text'][c['start']:c['end']] for c in result['pre_chunks'] if c['block']==i]
        assert ''.join(slices)==b['text']
    second=next(i for i,b in enumerate(result['blocks']) if b['kind']=='heading' and b['text']=='Two')
    assert result['pre_chunks'][-1]['heading_path']==[0,second]


def test_json_retains_object_not_fake_prose():
    result=audit.inspect(b'{"unit":"USD","value":0}',{'capture':{'content_type':'application/json'}})
    assert result['structured_object']=={'unit':'USD','value':0}
    assert result['chapter_applicability']=='not_applicable'
    assert not result['pre_chunks']


def test_markdown_bracket_prefix_is_not_assumed_to_be_json():
    result=audit.inspect(b'[Annual report](report.pdf)\n\n# Results\n\nRevenue increased.',{'capture':{'content_type':'text/plain'}})
    assert result['route']=='markdown_or_plain_text'
    assert result['outline'][0]['title']=='Results'


def test_xml_web_heading_level_and_full_table():
    long='x'*700
    blocks=audit.normalize_web({'blocks':[
        {'kind':'head','text':'Subsection','xml':'<head rend="h2">Subsection</head>'},
        {'kind':'table','text':long,'xml':'<table><row><cell colspan="2">'+long+'</cell></row></table>'}]})
    assert blocks[0]['level']==2
    assert blocks[1]['rows'][0][0]['text']==long
    assert blocks[1]['rows'][0][0]['colspan']=='2'


def test_web_xml_tail_is_kept_not_discarded_to_parse_fragment():
    blocks=normalize_fragment({'blocks':[{'kind':'p','text':'First.','xml':'<p>First.</p> More text &amp; facts.'}]})
    assert [b['text'] for b in blocks]==['First.',' More text & facts.']


def test_finalization_reuses_structural_surface_without_hiding_nil_values():
    bodies=['\n\u200b','| |','0','—','USD','(1) Note.']
    doc={'blocks':[{'kind':'text','text':t} for t in bodies], 'outline':[],
         'pre_chunks':[{'kind':'prose','block':i,'start':0,'end':len(t),'heading_path':[]} for i,t in enumerate(bodies)]}
    result=classify(doc)
    assert [r['role'] for r in result['records']]==['retained_structure']*2+['prose_candidate']*4
    assert result['published'] is False
