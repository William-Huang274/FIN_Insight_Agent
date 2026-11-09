import asyncio

import pytest

from sec_agent.research_foundation.public_page_access import check_access_challenge
from sec_agent.research_foundation.external_sources import DDGSDiagnosticProvider, ExternalSourceDiscovery, ExternalSearchRequest, ExternalSourceError
from sec_agent.agent_runtime.conversation_web import web_read_feedback
from test_external_sources import _run_scope


def test_challenge_is_access_failure_not_metadata_and_article_quote_survives():
    script='<script>document.cookie="EO_Bot_Ssid=x"; location.reload()</script>'
    with pytest.raises(ExternalSourceError,match='capture_access_challenge'):
        check_access_challenge(script)
    check_access_challenge('<article><h1>How challenges work</h1><p>Explanation</p>'+script+'</article>')
    check_access_challenge('<html><body><p>An undated normal product page</p></body></html>')
    feedback=web_read_feedback({'execution_receipt':{'attempts':[{'date_filter_counts':{'origin_access_challenge':1}}]}})
    assert feedback[0]['kind']=='origin_access_challenge'


def test_ddgs_zero_overlap_bucket_does_not_count_as_successful_fallback():
    query='coding agent user experience limitations workflow GitHub 2026'
    def fixture(*a,**kw):
        return [{'title':'Orlando City roster 2026','href':'https://football.example/2026','body':'Football players'},
                {'title':'Coding agent workflow study','href':'https://study.example/paper','body':'User feedback'}]
    request=ExternalSearchRequest(query=query,branch_id='Q4_ARCHITECTURE_RAMP',run_scope=_run_scope('Q4_ARCHITECTURE_RAMP'),purpose='Diagnostic',max_results=5)
    receipt=asyncio.run(ExternalSourceDiscovery(primary=DDGSDiagnosticProvider(search_callable=fixture)).search(request))
    assert len(receipt.candidates)==1 and receipt.candidates[0].canonical_url=='https://study.example/paper'
    assert receipt.attempted_providers[0].returned_hits==2
    assert receipt.attempted_providers[0].candidate_filter_counts=={'no_query_term_overlap':1}
    from sec_agent.research_foundation.search_result_quality import has_query_overlap
    assert has_query_overlap('AI','artificial intelligence','', 'https://study.example')
    assert has_query_overlap('site:study.example coding workflow','A report','', 'https://study.example/coding')
    feedback=web_read_feedback({'execution_receipt':{'attempts':[{'candidate_filter_counts':{'no_query_term_overlap':5}}]}})
    assert feedback[0]['kind']=='fallback_query_mismatch'
