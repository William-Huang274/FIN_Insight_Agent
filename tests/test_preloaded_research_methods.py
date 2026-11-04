import pytest

from sec_agent.research_foundation.research_methods import get_research_method, preloaded_research_methods


def test_preload_is_exact_existing_teaching_and_default_changes_nothing():
    assert preloaded_research_methods([]) == ''
    ids = ['research_loop', 'counter', 'finance']
    content = preloaded_research_methods(ids)
    for key in ids:
        resource = get_research_method(key)
        assert content.count(resource['content']) == 1
        assert resource['resource_digest'] in content
    assert content.index('method_id=research_loop') < content.index('method_id=counter')


@pytest.mark.parametrize('selection', ['finance', ['unknown'], ['finance', 'finance'], [None]])
def test_bad_host_selection_fails_before_model_input(selection):
    with pytest.raises(ValueError):
        preloaded_research_methods(selection)


def test_section_entry_and_text_share_readable_locator_and_no_unrelated_chapters():
    from sec_agent.research_foundation.research_methods import section_guidance
    selected = [('survey_analysis', '调查总体、分母与跨期可比性')]
    card = section_guidance(selected)
    full = section_guidance(selected, include_text=True)
    assert 'section="调查总体、分母与跨期可比性"' in card
    assert card in full
    assert '步骤 S1：' in full and '步骤 S1：' not in card and '步骤 S3：' not in full
    assert section_guidance([]) == ''
