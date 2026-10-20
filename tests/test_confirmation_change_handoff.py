"""Change identity and history navigation, never financial verdicts."""
from copy import deepcopy
import json
from sec_agent.agent_runtime.workpaper_changes import workpaper_changes, confirmation_context
from sec_agent.agent_runtime.confirmation_reading import with_reading_targets
from sec_agent.agent_runtime.review_context import confirmation_navigation, handoff_page
from sec_agent.agent_runtime.review_inspection import read_location, read_structured_location
from test_research_convergence import artifact_fixture


def setup():
    artifacts = artifact_fixture()
    before = artifacts.read_paper('P01')
    after = deepcopy(before)
    after['claims'][0]['statement'] += ' Updated condition.'
    response = lambda fid: {'finding_id': fid, 'disposition': 'corrected', 'explanation': 'Author statement only.'}
    revisions = {'P01': {'paper_id':'P01','status':'revision_submitted','workpaper':after,'sources':{},
        'finding_responses':[response('old'),response('current')], 'runtime_changes':workpaper_changes(before,after)}}
    feedback = {'P01':[{'finding_id':'current','claim_ids':[after['claims'][0]['claim_id']]}]}
    return artifacts,before,after,revisions,feedback


def test_field_diff_distinguishes_text_binding_changes_additions_and_removals():
    before={'claims':[{'claim_id':'A','statement':'旧条件 abc 旧条件','source_ids':['S1'],'kind':'inference'},
                      {'claim_id':'R','statement':'removed'}]}
    after={'claims':[{'claim_id':'A','statement':'旧条件 xyz 旧条件','source_ids':['S2'],'kind':'inference'},
                     {'claim_id':'N','statement':'added'}]}
    result=workpaper_changes(before,after)
    assert result['position_unit']=='unicode_characters_zero_based_half_open'
    a=next(r for r in result['claim_changes'] if r['claim_id']=='A')
    assert {f['field'] for f in a['fields']}=={'statement','source_ids'}
    assert 'kind' in a['unchanged_fields']
    edit=next(f for f in a['fields'] if f['field']=='statement')['edits'][0]
    assert edit['before_text']=='abc' and edit['after_text']=='xyz'
    assert before['claims'][0]['statement'][slice(*edit['before_span'])]=='abc'
    assert after['claims'][0]['statement'][slice(*edit['after_span'])]=='xyz'
    assert {r['change_kind'] for r in result['claim_changes']}=={'modified','added','removed'}


def test_current_and_old_answers_separate_without_changing_or_resolving_them():
    artifacts,before,after,revisions,feedback=setup(); original=deepcopy(revisions)
    context=confirmation_context(artifacts,revisions,feedback)
    assert context['author_responses']['P01']==[revisions['P01']['finding_responses'][1]]
    assert context['historical_author_responses']['P01']==[revisions['P01']['finding_responses'][0]]
    nav=confirmation_navigation(context)
    assert nav==confirmation_navigation(nav)
    args=nav['historical_author_responses']['P01']['readback']['arguments']
    page=handoff_page(artifacts,context,**args)
    assert json.loads(page['text'])==context['historical_author_responses']['P01']
    assert revisions==original and context['findings_to_confirm']==feedback


def test_legacy_change_detail_requires_exact_baseline_not_original_paper():
    artifacts,before,after,revisions,feedback=setup()
    prior=deepcopy(before);prior['claims'][0]['statement']+=' Earlier change.'
    latest=deepcopy(prior);latest['claims'][0]['statement']+=' Latest change.'
    observed=workpaper_changes(prior,latest);observed.pop('claim_changes')
    revisions['P01'].update(workpaper=latest,runtime_changes=observed)
    unavailable=confirmation_context(artifacts,revisions,feedback)
    assert unavailable['changes']['P01']['claim_change_detail_status']=='exact_baseline_unavailable'
    history=[{'output':{'paper_id':'P01','workpaper':prior}}]
    restored=confirmation_context(artifacts,revisions,feedback,artifact_history=history)
    assert restored['changes']['P01']['claim_changes']==workpaper_changes(prior,latest)['claim_changes']
    assert 'Earlier change.' not in json.dumps(restored['changes']['P01']['claim_changes'][0]['fields'][0]['edits'][0]['after_text'])


def test_changed_field_readbacks_are_current_and_allow_unchanged_related_reads():
    artifacts,before,after,revisions,feedback=setup()
    current=artifacts.with_revisions(revisions)
    context=confirmation_context(artifacts,revisions,feedback)
    view=with_reading_targets(current,context)
    field=view['changes']['P01']['claim_changes'][0]['fields'][0]
    a=field['current_read']['arguments'];reader=read_structured_location if a.get('view')=='json' else read_location
    result=reader(current,a['paper_id'],a['field_path'],a['offset'],a['max_characters'])
    assert result['text']==after['claims'][0]['statement']
    assert read_location(current,'P01','/thesis')['text']==after['thesis']
    assert artifacts.read_paper('P01')==before


def test_history_preserves_exact_reviewer_verdict_and_version_without_promoting_it():
    artifacts,before,after,revisions,feedback=setup()
    past={'context':{'paper_version_digests':{'P01':'oldversion'},'findings_to_confirm':{'P01':[{'finding_id':'old'}]}},
        'review':{'phase':'incomplete','verifier':{'status':'incomplete_review','review':{
            'finding_checks':[{'finding_id':'old','status':'unresolved'}], 'unresolved_data_requests':['Need source header.']}}}}
    context=confirmation_context(artifacts,revisions,feedback,confirmation_history=[past])
    nav=confirmation_navigation(context)
    assert nav['historical_reviews'][0]['paper_version_digests']['P01']=='oldversion'
    page=handoff_page(artifacts,context,section='historical_reviews',paper_id='P01')
    assert json.loads(page['text'])[0]['roles']['verifier']['review']==past['review']['verifier']['review']
    assert context['findings_to_confirm']==feedback


def test_calc_readbacks_preserve_alias_and_unknown_binding_without_selection():
    artifacts,*_=setup()
    ref='CALC::test'
    artifacts._sources[ref]={'result_state':'non_authoritative_metric','calculation_id':ref}
    claims=[{'source_ids':[ref,ref,'CALC::missing']}]
    nav=artifacts.calculation_readbacks(claims)
    assert len(nav)==1 and nav[0]['arguments']['source_id']==ref
    assert claims[0]['source_ids'][-1]=='CALC::missing'


def test_local_confirmation_uses_contract_boundary_and_keeps_original_readback():
    import asyncio
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from sec_agent.agent_runtime.case_review_agent import build_case_reviewer

    class Audit:
        context_summary = None
        source_access_check = None
        def __init__(self): self.extra_middlewares = []
        def middlewares(self): return self.extra_middlewares

    class Capture(BaseChatModel):
        seen: list = []
        @property
        def _llm_type(self): return 'offline-contract-transition'
        def bind_tools(self, tools, **kwargs):
            assert {'read_review_history','read_saved_review_checks','read_review_handoff'} <= {t.name for t in tools}
            return self
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.seen = list(messages)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='',tool_calls=[{
                'name':'read_review_history','args':{'index':2},'id':'reread','type':'tool_call'}]))])

    artifacts,_,_,revisions,feedback=setup()
    context=confirmation_context(artifacts,revisions,feedback)
    old=ToolMessage(name='read_research_source',tool_call_id='old',content='EXACT_PRIOR_RECEIPT')
    history=[HumanMessage(content=json.dumps({'question':'Original research question'})),
        AIMessage(content='OLD_PLAN',additional_kwargs={'reasoning_content':'OLD_REASONING'},tool_calls=[{
            'name':'read_research_source','args':{'source_id':'S1'},'id':'old','type':'tool_call'}]),old,
        HumanMessage(content='review_handoff_contract_v2'),
        HumanMessage(content=json.dumps({'retained_observation':'EXACT_PRIOR_RECEIPT'}))]
    model=Capture()
    agent=build_case_reviewer(role='verifier',model=model,artifacts=artifacts.with_revisions(revisions),
        tools=[],confirmation=context,audit=Audit(),max_model_calls=1)
    result=asyncio.run(agent.ainvoke({'messages':history}))
    projected=str([m.model_dump() for m in model.seen])
    assert 'OLD_PLAN' not in projected and 'OLD_REASONING' not in projected
    assert 'EXACT_PRIOR_RECEIPT' in projected and 'Original research question' in projected
    assert old in result['messages']
    receipt=next(m for m in result['messages'] if isinstance(m,ToolMessage) and m.tool_call_id=='reread')
    assert receipt.status=='success' and 'EXACT_PRIOR_RECEIPT' in receipt.content
