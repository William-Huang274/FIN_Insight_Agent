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
