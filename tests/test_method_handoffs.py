from copy import deepcopy

import pytest

from sec_agent.research_foundation.method_handoffs import judgment_directory,select_judgments
from sec_agent.research_foundation.method_execution import MethodWorkResult
from test_method_review import output


def paper():
    row=output()
    row['result']['steps'][0]['finding']='Only distinct licenses; integrated service recognized over time.'
    row['result']['findings']=[dict(statement='Licenses recognized upfront.',kind='factual',source_ids=['S1:p1'],
        public_basis='See issuer policy.',assumptions=['Only distinct obligations.'],
        alternative='Integrated service.',would_change='Different contract terms.')]
    row['obligation']['as_of']='2025-06-01'
    row['review_evidence'][0]['source']={'id':'S1','digest':'v1','published_at':'2025-01-01','vintage':'dated_original'}
    return row


def test_legacy_claim_carries_qualifiers_and_backing_steps_without_rewriting():
    row=paper();before=deepcopy(row);directory=judgment_directory([row]);j=next(iter(directory.values()))
    assert j['finding']['statement']=='Licenses recognized upfront.'
    assert 'Only distinct' in j['basis_steps'][0]['finding']
    assert j['finding']['assumptions']==['Only distinct obligations.']
    assert j['source_pointers'][0]['source']['digest']=='v1'
    assert j['scope']['as_of']=='2025-06-01'
    assert j['review_status']=='not_reviewed_current_version'
    assert 'body' not in j['source_pointers'][0] and row==before
    parsed=MethodWorkResult.model_validate(row['result']).model_dump(mode='json')
    assert 'basis_step_ids' not in parsed['findings'][0]


def test_changed_author_conditions_invalidate_old_judgment_reference():
    row=paper();old=judgment_directory([row]);ref=next(iter(old))
    row['result']['findings'][0]['assumptions'].append('New term.')
    new=judgment_directory([row])
    with pytest.raises(ValueError,match='stale'):select_judgments([ref],new)


def test_explicit_step_selection_and_missing_basis_never_guessed():
    row=paper();row['result']['findings'][0]['basis_step_ids']=['F2']
    row['result']['steps'].append(dict(step_id='F5',finding='Other work.',status='completed',source_ids=['S1:p1']))
    directory=judgment_directory([row]);j=select_judgments(list(directory),directory)[0]
    assert [s['step_id'] for s in j['basis_steps']]==['F2']
    row['result']['findings'][0]['basis_step_ids']=['F9']
    directory=judgment_directory([row])
    with pytest.raises(ValueError,match='basis_step_missing'):select_judgments(list(directory),directory)


def test_native_dispatch_carries_selected_judgment_and_compact_review(tmp_path):
    import asyncio
    from test_method_diagnostic_graph import make_snapshot
    from test_method_review import decision,task,full_review
    from sec_agent.research_foundation.method_diagnostic_graph import compile_method_probe
    row=paper();row['obligation']['source_requirements']=['S1'];events=[];calls=[]
    async def call(actor,payload,schema):
        calls.append(actor)
        if actor=='lead':
            if len(payload['results'])>1:return decision('stop')
            judgment=payload['judgment_context'][0]
            result=decision('delegate',[task('next',dependency_ids=['first'],judgment_refs=[judgment['judgment_ref']])],full_review(row))
            for check,t in zip(result['review']['inspection_checks'],payload['submission_targets']):
                for key in ('paper_id','paper_digest','field_path','target_quote'):check.pop(key)
                check['target_ref']=t['target_ref']
            return result
        j=payload['judgment_context'][0]
        assert j['finding']['assumptions']==['Only distinct obligations.']
        assert 'Only distinct' in j['basis_steps'][0]['finding']
        assert j['review_status']=='checked'
        assert any(p['id']=='S1:p1' for r in payload['read_results'] for p in r.get('items',[]))
        return output('next')['result']
    graph=compile_method_probe(snapshot=make_snapshot(tmp_path),call=call,record=lambda k,v:events.append((k,v)),runtime_handoffs=True)
    state=asyncio.run(graph.ainvoke(dict(question='q',as_of='2025-06-01',catalog_ids=['S1'],results=[row],waves=0)))
    assert calls==['lead','next','lead'] and not state.get('submission_failures')
    assert any(k=='submission_parsed' and r['runtime_parsing'] for k,r in events)
