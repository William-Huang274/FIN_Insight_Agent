"""Acceptance counts must not promote candidate scope to individual proof."""
import pytest

from tests.integration.source_intake_diagnostics import source_coverage, source_readback_targets


def rows(*ids):
    return [{'source_id': value} for value in ids]


def test_global_ranking_does_not_claim_each_source_was_read_back():
    eligible = [str(i) for i in range(1742)]
    result = source_coverage(rows(*eligible), eligible, rows('0', '1', '1741'),
                             [{'authorized_sources': 1742}])
    assert result == dict(published_sources=1742, eligible_sources=1742,
                         searched_sources=3, per_source_filtered_readback_count=3,
                         globally_ranked_sources=1742)


def test_date_exclusion_does_not_erase_successful_publication():
    result = source_coverage(rows('dated', 'unknown'), ['dated'], rows('dated'), [])
    assert result == dict(published_sources=2, eligible_sources=1,
                         searched_sources=1, per_source_filtered_readback_count=1,
                         globally_ranked_sources=0)


@pytest.mark.parametrize('captures,eligible,results,global_searches', [
    (rows('a', 'a'), ['a'], rows('a'), []),
    (rows('a'), ['a'], rows('a', 'a'), []),
    (rows('a'), ['a'], rows('outside'), []),
    (rows('a'), ['a', 'missing'], [], []),
    (rows('a', 'b'), ['a', 'b'], rows('a'), [{'authorized_sources': 1}]),
])
def test_inconsistent_evidence_cannot_emit_success_counts(captures, eligible, results, global_searches):
    with pytest.raises(ValueError, match='source_coverage_evidence_mismatch'):
        source_coverage(captures, eligible, results, global_searches)


def leaf(sid, number, end, indexed=False):
    return dict(node_kind='text', node_id=f'{sid}-{number}', parent_document_id=sid,
                content=f'exact body {number}', embedding_content='unneeded duplicated context',
                original_source={'source_id': sid, 'char_end': end,
                                 **({} if indexed else {'source_char_end': end + 1000})})


def test_compact_expectations_preserve_original_tail_ties_counts_and_identity():
    nodes = [leaf('text', 0, 4), leaf('node', 0, 8, True), leaf('text', 1, 20),
             leaf('node', 1, 8, True), leaf('text', 2, 6)]
    targets = source_readback_targets(iter(nodes))
    for sid, key in [('text', 'source_char_end'), ('node', 'char_end')]:
        old_leaves = [node for node in nodes if node['original_source']['source_id'] == sid]
        old_tail = max(old_leaves, key=lambda node: node['original_source'][key])
        assert targets[sid]['candidate_chunks'] == len(old_leaves)
        assert targets[sid]['position_key'] == key
        assert targets[sid]['tail'] == {field: old_tail[field] for field in
                                       ('node_id', 'parent_document_id', 'content', 'original_source')}
    assert targets['node']['tail']['node_id'] == 'node-0'


def test_compact_expectations_release_unneeded_node_and_embedding_references():
    import weakref
    class Node(dict):
        pass
    node = Node(leaf('source', 0, 10))
    reference = weakref.ref(node)
    targets = source_readback_targets([node])
    del node
    assert reference() is None
    assert 'embedding_content' not in targets['source']['tail']


def test_compact_expectations_reject_mixed_source_position_contracts():
    with pytest.raises(ValueError, match='position_basis_changed'):
        source_readback_targets([leaf('same', 0, 10), leaf('same', 1, 10, True)])


def test_compact_expectations_do_not_double_count_section_projections():
    with pytest.raises(ValueError, match='projected_leaves'):
        source_readback_targets([{**leaf('source', 0, 1), 'node_kind': 'section'}])
