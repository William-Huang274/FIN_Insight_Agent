from copy import deepcopy
import json
import pytest
from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.confirmation_reading import missing_reads, with_reading_targets
from sec_agent.agent_runtime.workpaper_changes import workpaper_changes, paper_versions
from sec_agent.agent_runtime.review_inspection import read_location, read_structured_location
from sec_agent.agent_runtime.case_review_agent import CaseReview, validate_case_review
from test_research_convergence import artifact_fixture


def fixture():
    base = artifact_fixture()
    before = base.read_paper('P01')
    after = deepcopy(before)
    after['narrative_markdown'] = '# Example\n\nUnits: million; period Q2.\n\n## Cash\n\n| Year | Value |\n|---|---|\n| Q2 | 53 |\n\nFootnote: derived.\n\n## Unchanged\n\n' + 'Other research. ' * 100
    before['narrative_markdown'] = after['narrative_markdown'].replace('| Q2 | 53 |', '| Q2 | 24 |')
    after['claims'][0]['statement'] += ' Corrected value.'
    current = base.with_revisions({'P01': {'status':'revision_submitted','workpaper':after,'finding_responses':[],'sources':{}}})
    context = {'paper_version_digests':paper_versions(current), 'findings_to_confirm': {'P01':[{'finding_id':'fix','claim_ids':[]}]},
        'changes': {'P01':workpaper_changes(before,after)}}
    return current, context


def read_all_missing(artifacts, context, messages):
    for item in missing_reads(artifacts, context, 'P01', messages):
        a=item['arguments']
        if item['tool']=='read_review_location':
            reader=read_structured_location if a.get('view')=='json' else read_location
            result=reader(artifacts,a['paper_id'],a['field_path'],a['offset'],a['max_characters'])
        else:
            result={**a,'content':[c for c in artifacts.read_paper('P01','claims') if c['claim_id'] in a['claim_ids']]}
        messages.append(ToolMessage(content=json.dumps(result),artifact=result,name=item['tool'],tool_call_id=str(len(messages))))
    return messages


def test_quote_reads_count_only_their_exact_coverage_not_candidate_previews():
    from sec_agent.agent_runtime.review_inspection import read_quoted_location
    artifacts, context = fixture()
    reads = read_all_missing(artifacts, context, [])
    window = next(m for m in reads if m.name == 'read_review_location')
    v = window.artifact
    selected = read_quoted_location(artifacts, 'P01', v['field_path'], v['text'])
    window.artifact = selected
    assert missing_reads(artifacts, context, 'P01', reads) == []
    window.artifact = {**selected, 'text': selected['text'][:-1]}
    assert missing_reads(artifacts, context, 'P01', reads)
    window.artifact = read_quoted_location(artifacts, 'P01', v['field_path'], '|')
    assert window.artifact['status'] == 'multiple_quote_matches'
    assert missing_reads(artifacts, context, 'P01', reads)


def test_local_read_coverage_keeps_headers_notes_and_accepts_real_windows():
    artifacts, context=fixture()
    view=with_reading_targets(artifacts,context)
    assert 'current_reading_targets' not in context
    reads=read_all_missing(artifacts,context,[])
    text=''.join(m.artifact.get('text','') for m in reads)
    assert all(x in text for x in ['Units: million','| Year |','Footnote: derived.'])
    assert 'Other research.' not in text
    assert missing_reads(artifacts,context,'P01',reads)==[]
    assert with_reading_targets(artifacts,context,reads)['current_reading_targets']['P01']==[]
    review=CaseReview(summary='Synthetic scope only.', assessments=[{'paper_id':'P01','assessment':'Synthetic reading coverage check only.'}])
    validate_case_review(review,artifacts,reads,paper_ids=['P01'],confirmation=context)
    with pytest.raises(ValueError,match='read_missing_papers'):
        validate_case_review(review,artifacts,reads,paper_ids=['P01'])


def test_claim_only_stale_partial_and_forged_reads_do_not_close_local_gate():
    artifacts,context=fixture()
    reads=read_all_missing(artifacts,context,[])
    only_claims=[m for m in reads if m.name=='read_research_artifact']
    assert missing_reads(artifacts,context,'P01',only_claims)
    for mutate in ('digest','text','directory'):
        bad=deepcopy(reads)
        window=next(m for m in bad if m.name=='read_review_location')
        if mutate=='digest':window.artifact['paper_digest']='old'
        elif mutate=='text':window.artifact['text']='not current text'
        else:window.artifact.pop('text')
        assert missing_reads(artifacts,context,'P01',bad)
    # A numeric row without its section/header/footnote is insufficient.
    text=artifacts.read_paper('P01')['narrative_markdown'];start=text.index('| Q2 |')
    narrow=read_location(artifacts,'P01','/narrative_markdown',start,13)
    assert missing_reads(artifacts,context,'P01',only_claims+[ToolMessage(content='',artifact=narrow,name='read_review_location',tool_call_id='row')])


def test_pagination_joins_current_windows_and_changed_claims_invalidate_old_content():
    artifacts,context=fixture();reads=read_all_missing(artifacts,context,[])
    window=next(m for m in reads if m.name=='read_review_location');v=window.artifact;half=len(v['text'])//2
    parts=[read_location(artifacts,'P01',v['field_path'],0,half), read_location(artifacts,'P01',v['field_path'],half,len(v['text'])-half)]
    claims=[m for m in reads if m.name=='read_research_artifact']
    messages=claims+[ToolMessage(content='',artifact=p,name='read_review_location',tool_call_id=str(i)) for i,p in enumerate(parts)]
    assert not missing_reads(artifacts,context,'P01',messages)
    claims[0].artifact['content'][0]['statement']='obsolete'
    assert missing_reads(artifacts,context,'P01',messages)[0]['tool']=='read_research_artifact'


def test_legacy_or_invalid_change_metadata_keeps_full_read_requirement():
    artifacts,context=fixture()
    context['changes']['P01']['current_digest']='old'
    assert missing_reads(artifacts,context,'P01',[]) is None


def test_save_partial_finding_after_exact_read_without_claiming_whole_confirmation():
    artifacts,context=fixture()
    window=read_location(artifacts,'P01','/narrative_markdown',0,150)
    messages=[ToolMessage(content='',artifact=window,name='read_review_location',tool_call_id='one-window')]
    review=CaseReview(summary='Synthetic partial finding only.',assessments=[{'paper_id':'P01','assessment':'This only records the observed local issue.'}],
        findings=[{'finding_id':'test','paper_id':'P01','severity':'advisory','problematic_quote':'Footnote: derived.',
            'diagnosis':'Synthetic reading boundary verification.', 'requested_change':'Synthetic instruction; no financial conclusion.'}])
    validate_case_review(review,artifacts,messages,paper_ids=['P01'],require_full_workpaper=False)
    with pytest.raises(ValueError,match='read_current_revision_before_review'):
        validate_case_review(review,artifacts,messages,paper_ids=['P01'],confirmation=context)


def test_structured_completion_note_is_grouped_and_paginated_not_leaf_chore():
    artifacts,context=fixture()
    # Extend the synthetic accepted revision through the normal artifact projection.
    before=artifacts.read_paper('P01');after=deepcopy(before)
    after['task_note']={'summary':'Completion claim, not independent proof.',
        'changes':[{'field':'row-'+str(i),'description':'x'*180} for i in range(50)]}
    revised=artifacts.with_revisions({'P01':{'status':'revision_submitted','workpaper':after,'finding_responses':[],'sources':{}}})
    context['changes']['P01']=workpaper_changes(before,after)
    pending=missing_reads(revised,context,'P01',[])
    assert len(pending)==1 and pending[0]['arguments']['view']=='json'
    assert pending[0]['arguments']['field_path']=='/task_note'
    directory=read_location(revised,'P01','/task_note')
    messages=[ToolMessage(content='',artifact=directory,name='read_review_location',tool_call_id='directory')]
    assert missing_reads(revised,context,'P01',messages)
    for _ in range(10):
        messages=read_all_missing(revised,context,messages)
        if not missing_reads(revised,context,'P01',messages):break
    else:raise AssertionError('Pagination failed')
    assert len(messages)<6  # No per-field / per-ID calls.
    assert all('location_id' not in m.artifact for m in messages)
