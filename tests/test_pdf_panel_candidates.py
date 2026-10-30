from types import SimpleNamespace
from ingestion.pdf_panel_candidates import source_panel_candidates


def rect(box):
    return {'rect': box, 'fill': (1, 1, 1), 'items': [('re', box, 1)]}


def test_adjacent_cards_keep_numbers_separate_and_all_words_accounted_for():
    words = [(1, 1, 5, 5, 'A', 0, 0, 0), (11, 1, 15, 5, '89.5', 1, 0, 0),
             (25, 1, 30, 5, 'outside', 2, 0, 0)]
    page = SimpleNamespace(get_text=lambda *a, **k: words,
        get_drawings=lambda: [rect((0, 0, 10, 10)), rect((10, 0, 20, 10))])
    result = source_panel_candidates(page)
    assert [w['panel_index'] for w in result['words']] == [0, 1, None]
    assert [w['text'] for w in result['words']] == ['A', '89.5', 'outside']


def test_background_nesting_and_shadow_overlap_do_not_duplicate_words():
    words = [(2, 2, 3, 3, 'value', 0, 0, 0)]
    page = SimpleNamespace(get_text=lambda *a, **k: words,
        get_drawings=lambda: [rect((0, 0, 100, 100)), rect((1, 1, 10, 10)), rect((0, 2, 9, 11))])
    result = source_panel_candidates(page)
    assert result['words'][0]['assignment'] == 'ambiguous_overlap'
    assert all(not p['owned_word_indices'] for p in result['panels'])
