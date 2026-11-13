from sec_agent.agent_runtime.synthesis_guidance import final_author_guidance
from sec_agent.research_foundation.research_methods import get_research_method


def test_lead_entry_is_scoped_and_method_section_is_actually_readable():
    text = final_author_guidance({'research_delegate': {'model': 'deepseek-flash'}})
    assert text.count('本次分工：') == 1
    assert 'purpose="investigate"' in text
    assert '不把全部读取、检查与综合积累到最后成稿' in text
    assert 'assess_research_result' in text and '不要为省上下文而验收' in text
    section = get_research_method('lead', '重要研究关系的完整调查与验收')
    assert section['content_version'] == 15
    assert section['grants_authority'] is False
    for concept in ['最强反证', '未通过', '真实依赖', '子助手', '开业批次']:
        assert concept in section['content']
    # Native takeover without a configured delegate must not disclose that role.
    assert '本次分工：' not in final_author_guidance({'native_model_transition': { 'to_model': 'sol'}})


def test_native_takeover_and_lead_receive_final_ownership_without_changing_ordinary_role():
    assert final_author_guidance({}) == ''
    for options in ({'native_model_transition': {'from_model':'flash','to_model':'sol'}},
                    {'research_delegate': {'model':'flash'}}):
        text = final_author_guidance(options)
        assert 'synthesis_context' in text
        assert '不预设保留旧故事' in text
        assert '不再转交原作者' in text
        assert '替代解释必须独立' in text


def test_native_method_resources_teach_actual_manuscript_closure_and_replacement_reasoning():
    writer = str(get_research_method('writer'))
    verifier = str(get_research_method('verifier'))
    assert '替代解释须单独验证' in writer
    assert 'resolved_action_ids' in verifier
    assert '若只是看到了笔记或前一版，不确认最终稿' in verifier
