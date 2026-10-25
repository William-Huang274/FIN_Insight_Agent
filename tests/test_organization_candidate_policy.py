from copy import deepcopy
import sqlite3

import pytest

from retrieval.candidate_policy import candidate_limits
from sec_agent.research_foundation.organization_hybrid_retrieval import OrganizationHybridRetrieval
from test_organization_hybrid_retrieval import setup, prepare


def test_expanded_policy_is_bounded_and_retains_graph_quota():
    assert candidate_limits() == {'dense':24, 'lexical':12, 'graph':0}
    assert candidate_limits('dense_expanded.v1') == {'dense':36, 'lexical':12, 'graph':0}
    assert candidate_limits('dense_expanded.v1', has_graph=True) == {'dense':24, 'lexical':12, 'graph':12}
    with pytest.raises(ValueError, match='candidate_policy_invalid'):
        candidate_limits('unbounded')


def test_policy_has_separate_rank_cache_and_still_rechecks_current_access(tmp_path, monkeypatch):
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    reader, state, org, nodes = setup(tmp_path/'source')
    rows = [{**deepcopy(nodes[0]), 'node_id':'node-'+str(i)} for i in range(40)]
    prepare(tmp_path/'index', org, rows)
    snapshot = reader._grant()[0]['manifest_digest'][7:]
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY', raising=False)
    balanced = OrganizationHybridRetrieval(reader, tmp_path/'index')
    a, receipt = balanced.rank(rows, 'revenue', snapshot, [])
    assert len(a) == 24 and 'candidate_policy' not in receipt
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY', 'dense_expanded.v1')
    expanded = OrganizationHybridRetrieval(reader, tmp_path/'index')
    b, receipt = expanded.rank(rows, 'revenue', snapshot, [])
    assert len(b) == 36 and not receipt['cache_hit']
    assert receipt['candidate_limits']['dense'] == 36
    assert expanded.rank(rows, 'revenue', snapshot, [])[1]['cache_hit']
    assert len(balanced.rank(rows, 'revenue', snapshot, [])[0]) == 24
    with sqlite3.connect(tmp_path/'index'/org/'rank-cache.sqlite') as db:
        assert db.execute('SELECT count(*) FROM ranks').fetchone()[0] == 2
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        expanded.rank(rows, 'revenue', snapshot, [])
