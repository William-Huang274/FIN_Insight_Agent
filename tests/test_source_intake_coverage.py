"""Acceptance counts must not promote candidate scope to individual proof."""
import pytest

from tests.integration.source_intake_diagnostics import source_coverage


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
