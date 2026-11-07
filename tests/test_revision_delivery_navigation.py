import json
from copy import deepcopy

from langchain_core.messages import AIMessage,ToolMessage
from sec_agent.agent_runtime.revision_context import revision_wording,current_revision_view
from sec_agent.agent_runtime.source_acquisition_view import acquisition_history
from sec_agent.agent_runtime.context_records import browse_checkpoint
from sec_agent.agent_runtime.context_observation import observe_context


def test_revision_exposes_unchanged_heading_and_conclusion_without_verdict():
    title='# 新建限制已经证明是租金上涨的主要原因'
    closing='结尾：仓库租金上涨已经证明新建限制是主要原因。'
    before=title+'\n仓库租金上涨排除了需求变化。\n'+closing
    after=title+'\n仓库租金上涨可能涉及需求变化。\n'+closing
    opinion='仓库租金上涨没有区分新建限制与需求变化，不能认定主要原因。'
    view=revision_wording(before,after,opinion,'旧题','新题')
    assert view['title']['changed']
    assert view['delivery_anchors']['headings'][0]['text']==title
    assert view['delivery_anchors']['opening_and_closing'][-1]['text']==closing
    assert view['total_changes']==1
    assert any(r['kind']=='heading' and r['verbatim_in_base'] for r in view['related_wording'])
    assert any(closing in r['excerpt'] and r['possible_change_indices']==[0] for r in view['related_wording'])
    for row in view['related_wording']:
        assert after[row['offset']:].startswith(row['excerpt'])
    assert 'passed' not in view


def test_revision_batches_are_version_bound_and_old_text_not_current():
    state={'report':{'title':'当前标题','narrative_markdown':'仓库租金上涨可能涉及需求变化。'},'report_version':3,
        'active_report_review':{'reviewer':'checker','reviewed_report_digest':'base','opinion':'仓库租金上涨不能单独排除需求变化，需要比较真实供需。','message_boundary':0},'messages':[]}
    for version,digest in [(1,'other'),(2,'base'),(3,'base')]:
        state['messages'].append(ToolMessage(name='edit_research_report',tool_call_id=f'v{version}',
            content=json.dumps({'saved':True,'report_version':version,'digest':str(version),
                'revision_context':{'reviewed_report_digest':digest,'changes':[{'before':'仓库租金上涨排除需求变化','after':'仓库租金上涨可能涉及需求变化'}]}})))
    original=deepcopy(state)
    result=current_revision_view(state)
    assert [b['report_version'] for b in result['saved_batches']]==[2,3]
    assert result['report_version']==3 and result['status']=='navigation_only_not_a_verdict'
    assert [r['report_version'] for r in result['related_wording'][0]['possible_saved_changes']]==[2,3]
    assert state==original


def test_acquisition_history_preserves_failures_and_distinguishes_partial_reads():
    url='https://publisher.test/report'
    messages=[]
    def emit(i,args,value,status='success'):
        messages.extend([AIMessage(content='',tool_calls=[{'id':i,'name':'read_public_source','args':args}]),
            ToolMessage(name='read_public_source',tool_call_id=i,status=status,content=json.dumps(value))])
    emit('blocked',{'query':url},{'unresolved_originals':[{'url':url,'reason':'HTTP403'}]})
    emit('candidate',{}, {'items':[{'source_url':url,'result_state':'retrieval_candidate'}]})
    emit('read',{}, {'items':[{'source_url':url,'result_state':'source_bound_passage','document_id':'doc',
        'content_sha256':'version1','truncated':True,'source_document_completeness_verified':False}]})
    emit('other',{}, {'items':[{'source_url':url+'/v2','result_state':'retrieval_candidate'}]})
    first=acquisition_history(messages)
    assert first[0]['read_after_obstacle'] and not first[0]['unresolved_after_latest_read']
    assert first[0]['research_gap_status']=='not_inferred_from_tool_history'
    assert not first[1]['has_read_passage']
    emit('later',{'document_id':'doc'},{'error':'permission_denied'},'error')
    row=acquisition_history(messages)[0]
    assert row['unresolved_after_latest_read'] and row['has_read_passage']
    assert row['events'][2]['content_sha256']=='version1' and row['events'][2]['truncated']
    assert row['events'][-1]['retry_authorized'] is False
    for i in range(14): emit(f'page{i}',{}, {'items':[{'source_url':url,'result_state':'retrieval_candidate'}]})
    page=browse_checkpoint(messages,'acquisition')
    assert len(page['items'])==12 and page['next_offset']==12
    second=browse_checkpoint(messages,'acquisition',offset=12)
    assert any(x['event']['receipt_id']=='blocked' for x in second['items'])


def test_context_observation_separates_pagination_changed_results_and_identical_reads():
    messages=[]
    for i,(offset,result) in enumerate([(0,'old'),(0,'old'),(100,'page2'),(0,'changed')]):
        messages.extend([{'role':'assistant','tool_calls':[{'id':str(i),'function':{'name':'read','arguments':json.dumps({'offset':offset})}}]},
            {'role':'tool','tool_call_id':str(i),'content':result}])
    body={'messages':messages,'tools':[]}
    original=deepcopy(body)
    observed=observe_context(body)
    assert observed['total_repeated_argument_groups']==1
    group=observed['repeated_argument_groups'][0]
    assert group['calls']==3 and group['result_variants']==2 and group['identical_result_repeats']==1
    assert body==original
    assert 'stop' not in observed and 'tokens' not in observed


def test_context_observation_native_anthropic_blocks_are_counted_without_reasoning_text():
    messages=[]
    for i in range(3):
        messages.extend([{'role':'assistant','content':[{'type':'thinking','thinking':'private trace'},
            {'type':'tool_use','id':str(i),'name':'read','input':{'offset':0}}]},
            {'role':'user','content':[{'type':'tool_result','tool_use_id':str(i),'content':'same result'}]}])
    value=observe_context({'messages':messages,'system':'instruction'})
    assert value['observed_tool_calls']==3
    assert value['repeated_argument_groups'][0]['identical_result_repeats']==2
    assert value['content_block_characters_by_type']['thinking']>0
    assert 'private trace' not in json.dumps(value)
