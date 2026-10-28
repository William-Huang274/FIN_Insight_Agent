import json
from hashlib import sha256
from types import SimpleNamespace
import pytest
from retrieval.relevance_boundary import fit,validate
from retrieval.relevance_boundary_runtime import ResultBoundary,configured_boundary,pipeline_identity


def artifact(pipeline):
    def samples(prefix):
        return [dict(query_sha256=sha256(f'{prefix}-q{i%12}'.encode()).hexdigest(),
            content_sha256=sha256(f'{prefix}-b{i}'.encode()).hexdigest(),
            source_document_sha256=sha256(f'{prefix}-d{i%12}'.encode()).hexdigest(),
            score=.95 if i<100 else .2,grade=3 if i<100 else 0,review_reason='Synthetic contract fixture')
            for i in range(120)]
    calibration=fit(samples('train'),pipeline=pipeline,minimum_precision=.9,minimum_results=40,minimum_questions=8)
    return dict(calibration=calibration,validation=validate(calibration,samples('holdout'),pipeline=pipeline))


def test_serving_artifact_frozen_and_input_drift_rejected(tmp_path,monkeypatch):
    pipeline=pipeline_identity('research.v2','qwen3.7-text-rerank','task','bounded.v1')
    path=tmp_path/'boundary.json';path.write_text(json.dumps(artifact(pipeline)))
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RELEVANCE_BOUNDARY',str(path))
    provider=SimpleNamespace(model='qwen3.7-text-rerank',instruction='task')
    boundary=configured_boundary('research.v2',provider,'bounded.v1')
    path.write_text('{}')
    rows=[{'node_id':x} for x in ['a','b','c']]
    receipt={'model':provider.model,'scores':[['a',.96],['b',.3],['c',.98]]}
    selected,note=boundary.apply(rows,receipt,limit=10)
    assert selected==[rows[0],rows[2]] and note['uncertain_candidate_ids']==['b']
    assert note['result_state']=='fewer_supported_candidates_than_requested'
    path.write_text(json.dumps(artifact(pipeline)))
    provider.instruction='different task'
    with pytest.raises(ValueError,match='independent_validation'):
        configured_boundary('research.v2',provider,'bounded.v1')
    with pytest.raises(ValueError,match='requires_configured_reranker'):
        configured_boundary('research.v2',None,'bounded.v1')


def test_provider_and_duplicate_score_cannot_bypass_boundary():
    pipeline={'model':'provider'};boundary=ResultBoundary(artifact(pipeline),pipeline)
    with pytest.raises(ValueError,match='provider_mismatch'):
        boundary.apply([],{'model':'other','scores':[]},limit=10)
    with pytest.raises(ValueError,match='duplicate_score'):
        boundary.apply([],{'model':'provider','scores':[['a',.1],['a',.9]]},limit=10)


@pytest.mark.parametrize('score',[True,False,'0.99',None,float('nan')])
def test_invalid_provider_score_cannot_become_supported_evidence(score):
    pipeline={'model':'provider'};boundary=ResultBoundary(artifact(pipeline),pipeline)
    with pytest.raises(ValueError,match='missing_valid_score'):
        boundary.apply([{'node_id':'a'}],{'model':'provider','scores':[['a',score]]},limit=10)


def test_instruction_is_explicit_server_owned_and_model_bound(monkeypatch):
    from retrieval.relevance_instruction import configured_instruction,TEXT
    from retrieval.scoped_reranking import ConfiguredReranker
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_RERANK_INSTRUCTION',raising=False)
    assert configured_instruction('qwen3.7-text-rerank') is None
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RERANK_INSTRUCTION','financial-evidence.v1')
    assert configured_instruction('qwen3.7-text-rerank')==TEXT
    with pytest.raises(ValueError,match='configuration_invalid'):configured_instruction('qwen3-rerank')
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_RERANK_MODEL','qwen3.7-text-rerank')
    monkeypatch.setenv('QWEN_API_KEY','fixture-only')
    ranker=ConfiguredReranker('unused-fixture-path')
    with pytest.raises(ValueError,match='server_owned'):
        ranker.rank('query',[],instruct='caller override')


@pytest.mark.parametrize('accepted_count',[0,1])
def test_real_navigation_keeps_short_result_receipt_cache_and_revocation(tmp_path,monkeypatch,accepted_count):
    from test_organization_source_filter import scoped_fixture,query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    nav,reader,state,_,_=scoped_fixture(tmp_path,monkeypatch,queries=['Acme cash'])
    calls=[]
    def rank(text,rows,**kwargs):
        kwargs['check_access']();calls.append(text)
        return rows,{'model':'fixture','provider_calls':0,
            'scores':[[r['node_id'],.99 if i<accepted_count else .1] for i,r in enumerate(rows)]}
    nav.hybrid.reranker=SimpleNamespace(rank=rank)
    pipeline={'model':'fixture'}
    nav.result_boundary=ResultBoundary(artifact(pipeline),pipeline)
    request=query(query='Acme cash',limit=10)
    result=nav.navigate(request)
    assert len(result.items)==accepted_count and result.total_matches==accepted_count
    assert result.next_offset is None
    assert result.organization_relevance_boundary['result_state']=='fewer_supported_candidates_than_requested'
    assert result.organization_relevance_boundary['unknown_or_absent_disclosure'] is False
    again=nav.navigate(request)
    assert len(calls)==1 and again.organization_relevance_boundary==result.organization_relevance_boundary
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(request)
