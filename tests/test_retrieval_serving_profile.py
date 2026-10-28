import pytest
from retrieval.serving_profile import configured_profile
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def test_server_profile_applies_to_ordinary_request_without_enabling_provider(monkeypatch):
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_SEARCH_PROFILE','research.v1')
    profile=configured_profile()
    request=SourceDocumentRequest(source_space='organization',operation='search',query='cash')
    effective=profile.apply_request(request)
    assert effective.organization_query_planning=='conservative.v5'
    assert effective.organization_metadata_policy=='sec_cover.v2'
    assert 'organization_query_planning' not in request.model_dump()
    assert not profile.receipt(effective,False)['remote_rerank_enabled']
    explicit=SourceDocumentRequest(source_space='organization',operation='search',query='cash',organization_filter={'form':'10-K'})
    assert profile.apply_request(explicit).organization_query_planning is None


def test_explicit_legacy_requests_remain_explicit_and_conflicting_deployment_fails(monkeypatch):
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_SEARCH_PROFILE','research.v1')
    request=SourceDocumentRequest(source_space='organization',operation='search',query='cash',organization_query_planning=None)
    assert configured_profile().apply_request(request).organization_query_planning is None
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY','balanced.v1')
    with pytest.raises(ValueError,match='conflicting_override'):configured_profile()


def test_research_profile_runs_actual_navigation_and_rechecks_revocation(tmp_path,monkeypatch):
    from test_organization_candidate_index import prepared,query
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_SEARCH_PROFILE','research.v1')
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_RERANK',raising=False)
    nav,reader,state,_,_=prepared(tmp_path,monkeypatch)
    result=nav.navigate(query())
    assert result.organization_query_plan['policy']=='conservative.v5'
    assert result.items[0]['retrieval']['serving_profile']['name']=='research.v1'
    assert not result.items[0]['retrieval']['serving_profile']['remote_rerank_enabled']
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):nav.navigate(query())
