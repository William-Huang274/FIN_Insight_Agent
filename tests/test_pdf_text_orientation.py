from ingestion.pdf_text_orientation import character_orientation_profile


def chars(matrix, count=30):
    return [{'text': 'a', 'matrix': matrix, 'upright': True}] * count


def test_quarter_turn_uses_matrix_even_when_backend_upright_is_true():
    result = character_orientation_profile(chars([-1.5e-16, 0.83, -0.83, 0, 0, 0]))
    assert result['suggested_clockwise_view_rotation'] == 90
    assert not result['automatic_original_rewrite']


def test_mixed_directions_and_unknowns_are_not_silently_normalized():
    result = character_orientation_profile(chars([0, 1], 20) + chars([1, 0], 20))
    assert result['suggested_clockwise_view_rotation'] is None
    assert result['matrix_direction_counts'] == {'0': 20, '90': 20}
    result = character_orientation_profile(chars([0, 1], 30) + [{'text': 'x'}] * 10)
    assert result['suggested_clockwise_view_rotation'] is None
    assert result['matrix_direction_counts']['unknown'] == 10


def test_minor_other_direction_preserved_and_invalid_transforms_not_fabricated():
    result = character_orientation_profile(chars([0, 1], 99) + chars([1, 0], 1))
    assert result['suggested_clockwise_view_rotation'] == 90
    assert result['matrix_direction_counts']['0'] == 1
    for matrix in [None, [0, 0], [float('nan'), 1], []]:
        result = character_orientation_profile(chars(matrix))
        assert result['matrix_direction_counts'] == {'unknown': 30}
        assert result['suggested_clockwise_view_rotation'] is None


def test_skew_and_sparse_text_do_not_trigger_quarter_turn():
    assert character_orientation_profile(chars([1, 1]))['suggested_clockwise_view_rotation'] is None
    assert character_orientation_profile(chars([0, -1], 3))['suggested_clockwise_view_rotation'] is None
    assert character_orientation_profile(chars([-1, 0]))['suggested_clockwise_view_rotation'] == 180
    assert character_orientation_profile(chars([0, -1]))['suggested_clockwise_view_rotation'] == 270
