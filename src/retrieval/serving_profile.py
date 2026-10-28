"""Server-owned retrieval policy; Agent requests do not assemble experiments.

Legacy is explicit migration compatibility. A profile selects deterministic
behavior and a reranker model, but never enables a paid provider by itself.
"""
from dataclasses import dataclass,asdict
import os


@dataclass(frozen=True)
class ServingProfile:
    name:str
    query_planning:str|None
    metadata_policy:str
    candidate_policy:str
    table_completion:str
    rerank_model:str

    def apply_request(self,request):
        if self.name=='legacy.v1' or request.source_space!='organization' or request.operation not in {'catalog','search'}:
            return request
        updates={}
        if 'organization_metadata_policy' not in request.model_fields_set:
            updates['organization_metadata_policy']=self.metadata_policy
        if request.operation=='search' and request.organization_filter is None and 'organization_query_planning' not in request.model_fields_set:
            updates['organization_query_planning']=self.query_planning
        return request.model_copy(update=updates)

    def receipt(self,request,provider_enabled):
        return {**asdict(self),'effective_query_planning':request.organization_query_planning,
            'effective_metadata_policy':request.organization_metadata_policy,
            'remote_rerank_enabled':provider_enabled,
            'paid_provider_requires_separate_configuration':True}


PROFILES={
    'legacy.v1':ServingProfile('legacy.v1',None,'original.v1','balanced.v1','','qwen3-rerank'),
    'research.v1':ServingProfile('research.v1','conservative.v5','sec_cover.v2','needs_window.v4','bounded.v1','qwen3.7-text-rerank'),
}


def configured_profile():
    name=os.getenv('FINSIGHT_ORGANIZATION_SEARCH_PROFILE','legacy.v1')
    if name not in PROFILES:raise ValueError('organization_search_profile_invalid')
    profile=PROFILES[name]
    if name!='legacy.v1':
        for variable,expected in [('FINSIGHT_ORGANIZATION_CANDIDATE_POLICY',profile.candidate_policy),
                                  ('FINSIGHT_ORGANIZATION_TABLE_COMPLETION',profile.table_completion),
                                  ('FINSIGHT_ORGANIZATION_RERANK_MODEL',profile.rerank_model)]:
            if variable in os.environ and os.environ[variable]!=expected:
                raise ValueError('organization_profile_conflicting_override:'+variable)
    return profile
