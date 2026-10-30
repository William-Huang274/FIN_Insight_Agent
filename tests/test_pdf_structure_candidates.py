from types import SimpleNamespace

from ingestion.pdf_structure_candidates import ruled_structure_candidates


def table(values, boxes):
    return SimpleNamespace(bbox=(0, 0, 100, 100), extract=lambda: values,
                           rows=[SimpleNamespace(cells=row) for row in boxes])


def page(*tables):
    return SimpleNamespace(find_tables=lambda settings: tables, lines=[], rect_edges=[{}] * 8,
                           curve_edges=[])


def test_merged_cells_keep_original_values_coordinates_and_absent_slot():
    box = (0, 0, 50, 50)
    result = ruled_structure_candidates(page(table(
        [['Owner', 'Share'], ['A', '85.29%'], [None, '14.71%']],
        [[box, box], [box, box], [None, box]])))
    item = result['candidates'][0]
    assert item['geometry_role'] == 'multirow_multicol_grid_candidate'
    assert item['rows'][2]['cells'][0] == {'column_index': 1, 'bbox': None, 'text': None}
    assert item['rows'][2]['cells'][1]['text'] == '14.71%'
    assert item['semantic_role'] == 'unknown'
    assert not item['may_suppress_source_text'] and not item['numeric_fact_authority']
    assert result['edge_inventory']['rect_edges'] == 8


def test_shadow_frame_and_single_column_are_not_promoted_to_repeated_grid():
    box = (0, 0, 50, 50)
    result = ruled_structure_candidates(page(
        table([['paragraph', None], [None, 'paragraph']], [[box, None], [None, box]]),
        table([['Issuer'], ['Year']], [[box], [box]])))
    assert all(r['geometry_role'] == 'layout_or_sparse_grid_unresolved'
               for r in result['candidates'])
    assert len(result['candidates']) == 2  # observations retained, not discarded


def test_text_only_grid_not_assumed_financial_and_empty_page_not_coverage_pass():
    box = (0, 0, 50, 50)
    result = ruled_structure_candidates(page(table(
        [['Person', 'Experience'], ['A', 'Engineering']], [[box, box], [box, box]])))
    assert result['candidates'][0]['semantic_role'] == 'unknown'
    assert ruled_structure_candidates(page())['candidates'] == []
    assert 'not_borderless' in result['coverage']
