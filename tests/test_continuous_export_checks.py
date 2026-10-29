import pytest

from tests.integration.continuous_export_checks import check_export_texts, quoted_source_window


def report():
    return {'narrative_markdown': '## 原文摘录\n\nselected middle window [source-1]\n\n## 使用说明',
            'citations': {'source-1': {'sources': [{'text': 'unquoted start selected middle window unquoted end'}]}}}


def test_exports_preserve_complete_selected_window_not_unquoted_capture_start():
    assert quoted_source_window(report()) == 'selected middle window'
    assert check_export_texts(report(), {'pdf': '服务验证 selected\nmiddle window'})['pdf']['original']
    assert not check_export_texts(report(), {'pdf': '服务验证 selected middle'})['pdf']['original']


def test_window_must_be_bound_to_actual_original():
    value = report()
    value['citations']['source-1']['sources'][0]['text'] = 'different original'
    with pytest.raises(AssertionError, match='quote_not_in_bound_source'):
        quoted_source_window(value)


def test_short_preview_requires_same_identity_full_read():
    value = report()
    value['citations']['source-1']['sources'][0]['text'] = 'unquoted start'
    row = {'passage_id': 'source-1', 'passage': 'unquoted start selected middle window unquoted end'}
    assert quoted_source_window(value, [row]) == 'selected middle window'
    with pytest.raises(AssertionError, match='quote_not_in_bound_source'):
        quoted_source_window(value, [dict(row, passage_id='another-source')])
