from copy import deepcopy
from hashlib import sha256

import pytest

from retrieval.source_structure import source_structure
from retrieval.source_table_periods import build_overlay, digest, MARKER
from retrieval.table_completion import complete_tables, read_span
from test_source_structure import bundle


def fixture():
    raw = b'''<html><body><table><tr><td>USD millions</td><td>2025</td><td>2024</td></tr>
    <tr><td>Cash (a)</td><td>120</td><td>90</td></tr></table>
    <table><tr><td>(a)</td><td>Restricted cash is excluded.</td></tr></table></body></html>'''
    text = MARKER+'\nUSD millions | 2025 | 2024\nCash (a) | 120 | 90\n[/TABLE]\n'+MARKER+'\n(a) | Restricted cash is excluded.\n[/TABLE]'
    b = bundle(text, text.index('Cash (a)'))
    b['table_period_context']=build_overlay(raw,raw_sha256=digest(raw),source_digest=digest(text))
    structures=source_structure(b)
    rows=[{'node_id':c['id'],'parent_document_id':'d','content':c['body'],
        'content_sha256':c['digest'],'original_source':{'source_id':'source','source_digest':b['source']['digest'],
        'source_char_start':c['source_char_start'],'source_char_end':c['source_char_end']},
        'source_structure':structures[c['id']]} for c in b['chunks']]
    by_id={r['node_id']:r for r in rows}
    calls=[]
    def load(anchor, span):
        calls.append(span['role'])
        return read_span(anchor,span,[(r['original_source']['source_char_start'],r['original_source']['source_char_end'],r['node_id']) for r in rows],by_id.__getitem__)
    return rows,load,calls


def test_late_ranked_data_row_gets_header_and_units_without_changing_rank():
    rows,load,calls=fixture()
    result,receipt=complete_tables([rows[1]],load)
    assert [r['node_id'] for r in result]==['1']
    c=result[0]['table_completion']
    assert c['status']=='context_complete'
    assert any('2025' in s['text'] for s in c['contexts'])
    assert any(s['role']=='unit_statement' for s in c['contexts'])
    assert receipt['top_k_unchanged'] and rows[1]['content']==result[0]['content']
    assert 'table_completion' not in rows[1]


def test_complete_original_does_not_load_duplicate_context():
    rows,load,calls=fixture()
    result,receipt=complete_tables(rows,load)
    assert not calls and receipt['unique_supplemental_spans']==0


def test_explicit_note_is_required_but_unmarked_note_is_not():
    rows,load,_=fixture()
    deps=rows[1]['source_structure']['table_dependencies'][0]
    notes=[s for s in deps['required'] if s['role']=='marked_footnote']
    assert len(notes)==1
    assert deps['unresolved']==[]
    # Simulate a chunk boundary before the note, retaining source identity.
    end=notes[0]['source_char_start']
    anchor=deepcopy(rows[1]);anchor['content']=anchor['content'][:end-anchor['original_source']['source_char_start']]
    anchor['original_source']['source_char_end']=end
    result,_=complete_tables([anchor],load)
    assert any('Restricted cash' in c['text'] for c in result[0]['table_completion']['contexts'])


def test_budget_exhaustion_and_missing_context_are_explicit():
    rows,load,_=fixture()
    result,_=complete_tables([rows[1]],load,maximum_characters=1)
    assert result[0]['table_completion']['status']=='incomplete'
    assert any('budget' in e for e in result[0]['table_completion']['unresolved'])
    result,_=complete_tables([rows[1]],lambda *_:None)
    assert any('unavailable' in e for e in result[0]['table_completion']['unresolved'])


@pytest.mark.parametrize('fault',['text','source_digest','document_id','source_char_start'])
def test_changed_context_fails_closed(fault):
    rows,load,_=fixture()
    def broken(anchor,span):
        value=load(anchor,span)
        value[fault]=0 if fault=='source_char_start' else 'changed'
        return value
    with pytest.raises(ValueError,match='table_completion_'):
        complete_tables([rows[1]],broken)


def test_missing_or_foreign_chunks_cannot_supply_context():
    rows,load,_=fixture();anchor=rows[1]
    span=anchor['source_structure']['table_dependencies'][0]['required'][0]
    assert read_span(anchor,span,[],lambda _:None) is None
    foreign=deepcopy(rows[0]);foreign['parent_document_id']='foreign'
    with pytest.raises(ValueError,match='identity_mismatch'):
        read_span(anchor,span,[(0,len(rows[0]['content']),'0')],lambda _:foreign)


def test_unverified_geometry_cannot_claim_complete():
    rows,_,_=fixture();rows[1]['source_structure']['status']='unknown'
    result,_=complete_tables([rows[1]],lambda *_:pytest.fail('must not load'))
    assert result[0]['table_completion']['status']=='unverified_structure'


def test_candidate_adapter_only_reads_scoped_chunks_and_rechecks_revocation(monkeypatch):
    import json,zlib
    from types import SimpleNamespace
    from sec_agent.research_foundation.organization_candidate_index import VerifiedCandidateIndex
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    rows,_,_=fixture(); by_id={r['node_id']:r for r in rows}; calls=[]; state={'active':True}
    def check(*_):
        if not state['active']:raise OrganizationExecutionUnavailable('revoked')
    proof=object.__new__(VerifiedCandidateIndex)
    proof.reader=SimpleNamespace(_grant=lambda:({'grant':True},{},{}),_after=check)
    proof.rows={r['node_id']:{'node_id':r['node_id'],'parent_document_id':'d'} for r in rows}
    proof.locations={'d':zlib.compress(json.dumps([['d',r['original_source']['source_char_start'],r['original_source']['source_char_end'],r['node_id']] for r in rows]).encode())}
    proof.check=check;proof.candidate_reads=0
    def materialize(identities,manifest):
        calls.extend(r['node_id'] for r in identities);proof.candidate_reads=len(identities)
        return [by_id[r['node_id']] for r in identities]
    proof.materialize=materialize
    result,_=proof.complete_tables([rows[1]],list(proof.rows.values()),{})
    assert calls==['0'] and result[0]['table_completion']['status']=='context_complete'
    calls.clear()
    result,_=proof.complete_tables([rows[1]],[proof.rows['1']],{})
    # Header lacks the business metric, but is in the SAME authorized original.
    assert calls==['0'] and result[0]['table_completion']['status']=='context_complete'
    calls.clear()
    original=proof.rows.pop('0')
    result,_=proof.complete_tables([rows[1]],[proof.rows['1']],{})
    assert not calls and result[0]['table_completion']['status']=='incomplete'
    proof.rows['0']=original
    def revoke(*args):
        value=materialize(*args);state['active']=False;return value
    proof.materialize=revoke
    with pytest.raises(OrganizationExecutionUnavailable):
        proof.complete_tables([rows[1]],list(proof.rows.values()),{})


def geometry_rows(rows, *, prefix='', status='original_geometry_verified'):
    text=prefix; cells=[]
    for i,values in enumerate(rows):
        for j,value in enumerate(values):
            start=len(text);text+=value
            cells.append({'row':i,'column':j,'text':value,'source_char_start':start,'source_char_end':len(text)})
            text+=' | '
        text+='\n'
    return text,{'status':status,'cells':cells,'source_char_start':len(prefix),'source_char_end':len(text),
                 'content_sha256':sha256(text[len(prefix):].encode()).hexdigest()}


def test_repeated_header_cannot_silently_reuse_first_period_or_unit():
    from retrieval.table_dependencies import dependencies
    text,t=geometry_rows([['USD millions','2025','2024'],['Cash','120','90'],
                          ['Other segment','2023','2022'],['Assets','30','40']])
    deps=dependencies(text,[t])
    assert len(deps)==2
    assert not deps[0]['unresolved']
    assert 'repeated_header_requires_column_binding' in deps[1]['unresolved']
    assert [s['role'] for s in deps[1]['required']]==['row_label']


@pytest.mark.parametrize('markers',['none','duplicate'])
def test_only_unique_explicit_matching_note_is_attached(markers):
    from retrieval.table_dependencies import dependencies
    text,t=geometry_rows([['USD millions','2025'],['Cash (a)','120']])
    text,n=geometry_rows([['(b)' if markers=='none' else '(a)','A note.']],prefix=text)
    tables=[t,n]
    if markers=='duplicate':
        text,n2=geometry_rows([['(a)','Different note.']],prefix=text);tables.append(n2)
    dep=dependencies(text,tables)[0]
    assert 'marked_footnote:a' in dep['unresolved']
    assert not any(s['role']=='marked_footnote' for s in dep['required'])


def test_intervening_table_prevents_attaching_later_matching_note():
    from retrieval.table_dependencies import dependencies
    text,t=geometry_rows([['USD millions','2025'],['Cash (a)','120']])
    text,other=geometry_rows([['EUR millions','2024'],['Debt','50']],prefix=text)
    text,n=geometry_rows([['(a)','Belongs to another table.']],prefix=text)
    dep=dependencies(text,[t,other,n])[0]
    assert 'marked_footnote:a' in dep['unresolved']
    assert not any(s['role']=='marked_footnote' for s in dep['required'])


def test_explicit_immediate_unit_caption_binds_but_surrounding_prose_does_not():
    from retrieval.table_dependencies import dependencies
    text,t=geometry_rows([['Description','2025'],['Cash','120']],prefix='USD millions\n')
    result=dependencies(text,[t])[0]
    assert not result['unresolved']
    assert any(s['role']=='unit_statement' for s in result['required'])
    text,t=geometry_rows([['Description','2025'],['Cash','120']],prefix='Other tables are in USD millions\n')
    assert dependencies(text,[t])[0]['unresolved']==['unit_not_explicitly_bound']


def test_contiguous_plain_marked_note_is_bound_to_referencing_row():
    from retrieval.table_dependencies import dependencies
    text,t=geometry_rows([['USD millions','2025'],['Cash (a)','120']])
    text+='\n(a) Restricted cash is excluded.\n'
    dep=dependencies(text,[t])[0]
    note=next(s for s in dep['required'] if s['role']=='marked_footnote')
    assert text[note['source_char_start']:note['source_char_end']]=='(a) Restricted cash is excluded.'
    assert not dep['unresolved']


def test_parenthesized_negative_values_are_not_footnote_markers():
    from retrieval.table_dependencies import dependencies
    text,t=geometry_rows([['USD millions','2025'],['Net cash used','(120)']])
    text,n=geometry_rows([['(120)','Unrelated numeric note.']],prefix=text)
    dep=dependencies(text,[t,n])[0]
    assert dep['unresolved']==[]
    assert not any(s['role']=='marked_footnote' for s in dep['required'])
