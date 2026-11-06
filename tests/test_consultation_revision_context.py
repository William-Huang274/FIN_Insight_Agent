import json

from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.revision_context import consultation_revision_context
from sec_agent.research_foundation.research_depth import depth_guidance
import pytest


def test_actual_review_links_unchanged_conclusion_but_does_not_decide_it():
    sentence='这一地区的仓库租金上涨已经证明新建限制是主要原因。'
    review=ToolMessage(name='read_research_agent_result',tool_call_id='actual',content=json.dumps({
        'status':'completed','purpose':'review','reviewed_report_digest':'original-version',
        'task_id':'a'*64,'opinion':'仓库租金上涨没有区分新建限制与需求增长，应检查需求变化。'}))
    result=consultation_revision_context([review],sentence,'租金原因需要核查。\n结尾：'+sentence)
    assert result['status']=='navigation_only_not_a_verdict'
    assert any(sentence in row['excerpt'] for row in result['related_wording'])
    assert result['review_receipt']=='actual'
    data=json.loads(review.content);data['purpose']='investigate';review.content=json.dumps(data)
    assert consultation_revision_context([review],sentence,sentence) is None


def test_depth_is_explicit_not_authority_or_loop_count():
    assert '快速追踪' in depth_guidance('brief')
    assert '合理可得公开资料' in depth_guidance('deep')
    assert '不增加权限或额度' in depth_guidance()
    with pytest.raises(ValueError): depth_guidance('unlimited')


def test_topic_acronym_does_not_route_election_results_to_issuer_filings():
    from sec_agent.research_foundation.company_disclosures import issuer_match
    rows=[{'title':'C3.ai, Inc.','ticker':'AI','cik_str':1}]
    assert issuer_match(rows, '2026 US midterm elections results AI policy November 5 2026') is None
    for query in ('AI', '$AI results', 'AI quarterly earnings', 'C3.ai results'):
        assert issuer_match(rows, query)==rows[0]
