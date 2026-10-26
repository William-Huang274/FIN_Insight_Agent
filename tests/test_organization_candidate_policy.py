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
    assert candidate_limits('needs_balanced.v1') == candidate_limits('dense_expanded.v1')
    assert candidate_limits('needs_balanced.v1',lexical_policy='organization-financial-needs.v2') == {'dense':24, 'lexical':24, 'graph':0}
    assert candidate_limits('needs_balanced.v1', has_graph=True,lexical_policy='organization-financial-needs.v2') == {'dense':12, 'lexical':24, 'graph':12}
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


def test_needs_budget_has_distinct_cache_same_total_cap_and_rechecks_access(tmp_path, monkeypatch):
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    reader,state,org,nodes=setup(tmp_path/'source')
    rows=[{**deepcopy(nodes[0]),'node_id':'node-'+str(i).zfill(3)} for i in range(60)]
    prepare(tmp_path/'index',org,rows)
    snapshot=reader._grant()[0]['manifest_digest'][7:]
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY','needs_balanced.v1')
    search=OrganizationHybridRetrieval(reader,tmp_path/'index')
    kw={'lexical_policy':'organization-financial-needs.v2'}
    selected,receipt=search.rank(rows,'revenue',snapshot,list(reversed(rows)),**kw)
    assert len(selected)==48
    assert len(receipt['lexical_node_ids'])==24 and len(receipt['dense_node_ids'])==24
    assert search.rank(rows,'revenue',snapshot,list(reversed(rows)),**kw)[1]['cache_hit']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):search.rank(rows,'revenue',snapshot,list(reversed(rows)),**kw)
