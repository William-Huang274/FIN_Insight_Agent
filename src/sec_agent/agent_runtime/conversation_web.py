"""Ordinary conversation tool over existing Exa discovery/capture and SQLite records."""
from datetime import datetime, timezone
from collections import Counter
import json
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime

from sec_agent.research_foundation.contracts import canonical_sha256
from sec_agent.research_foundation.dated_web_discovery import SearchReadOrigin, is_url_query
from sec_agent.research_foundation.external_sources import (
    ConversationSourceScope, ExaHostedMCPProvider, ExaHostedMCPPageFetcher,
    ExternalSourceDiscovery, ExternalSourceCapture, ExternalSourceError, PublicURLGuard,
    DDGSDiagnosticProvider, StaticHTTPPageFetcher, ExaTaskQuota,
)
from sec_agent.research_foundation.source_capture_cache import ScopedSourceCaptureCache
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.web_source_navigation import WebSourceReader
from .conversation_agent import GrantedTool


def web_read_feedback(result):
    """Explain only recorded obstacles, without exposing excluded candidate data."""
    if result.get('items'):
        return []
    counts = Counter()
    codes = set()
    engines = {}
    returned = 0
    for attempt in (result.get('execution_receipt') or {}).get('attempts', []):
        counts.update(attempt.get('date_filter_counts', {}))
        codes.add(attempt.get('failure_code'))
        engines.update(attempt.get('engine_http', {}))
        returned += attempt.get('returned_hits', 0)
    feedback = []
    if returned and counts:
        feedback.append({'kind':'candidates_not_admitted', 'returned_hits':returned, 'reasons':dict(counts),
            'meaning':'检索找到了候选，当前没有可读的已核定版本。若已有公开 HTTPS 原件或出版页网址，可将完整网址作为 query 直接核查。'})
    if any(status != 200 for status in engines.values()):
        feedback.append({'kind':'search_engine_health', 'engine_http':engines,
            'meaning':'部分搜索引擎未提供正常结果。429 表示限流，202 表示请求被接受但未返回标准结果页。已知的公开网址可直接核查；已有材料仍可使用。'})
    if counts['after_cutoff']:
        feedback.append({'kind':'after_cutoff','count':counts['after_cutoff'],
            'meaning':'部分候选晚于研究截止日。按发布日历倒推当时最近已公布的一期，再找当期归档。',
            'method_readback':{'tool':'get_research_method','arguments':{
                'method_id':'macro_valuation','section':'数据版本与当前研究入口'}}})
    if counts['origin_403'] or 'capture_http_status_403' in codes:
        feedback.append({'kind':'origin_403','meaning':'原站拒绝了本次访问（HTTP 403）。可查同一发布者的其他公开原件或正式转载，核对版本和出处。'})
    origin_http = {key[7:]:n for key,n in counts.items() if key.startswith('origin_') and key[7:].isdigit() and key != 'origin_403'}
    if origin_http:
        feedback.append({'kind':'origin_http','http_status_counts':origin_http,
            'meaning':'原站读取返回以下 HTTP 状态。404 表示这个地址未找到，429 表示限流，5xx 表示服务故障。'})
    if counts['date_unverified'] or counts['date_lookup_unavailable'] or counts['origin_unavailable'] or counts['redirect']:
        feedback.append({'kind':'date_not_established','meaning':'有候选未能核定公开日期。可改查有明确发布日期的公告或历史归档。'})
    x_failures = {k:v for k,v in counts.items() if k.startswith('x_') or k.startswith('public_data_')}
    if x_failures:
        feedback.append({'kind':'public_post_access', 'outcomes':x_failures,
            'meaning':'公开帖读取未完成或版本不符合截止时点。不能据此认定作者未发言。可查该机构官网同步公告或准确注明来源的同期转述；蓝 V 不等于身份及内容已核实。',
            'method_readback':{'tool':'get_research_method','arguments':{'method_id':'event_policy','section':'发言原件与账号身份'}}})
    if 'exa_mcp_rate_limited' in codes:
        feedback.append({'kind':'search_rate_limited','meaning':'Exa 本次限流；备用通道的结果另计。'})
    if 'deepseek_query_exceeds_128_characters' in codes:
        feedback.append({'kind':'query_length','meaning':'DeepSeek Search 单次最多 128 个字符；本次未向它发送截短的查询，其余通道另计。'})
    if any(str(code).startswith('deepseek_') and code != 'deepseek_query_exceeds_128_characters' for code in codes):
        feedback.append({'kind':'search_backup_unavailable','meaning':'DeepSeek 搜索未成功，具体错误在通道回执里；DDGS 另行尝试。这不能证明有关资料不存在。'})
    if 'ddgs_reported_no_results' in codes:
        feedback.append({'kind':'fallback_empty','meaning':'DDGS 报告未返回结果，原因未明。可换资料产品或参考期间；本次未检得不能证明没有披露。'})
    elif 'ddgs_search_failed' in codes:
        feedback.append({'kind':'fallback_failed','meaning':'DDGS 搜索调用失败，本次没有完成备用检索。'})
    return feedback


def public_web_tool(*, thread_id, run_id, method_digest, cache_root: Path, reader=None, research_as_of=None, paid_search=None, sec_user_agent=None):
    from uuid import UUID
    thread_id, run_id = str(UUID(thread_id)), str(UUID(run_id))
    cutoff = datetime.fromisoformat(research_as_of.replace('Z', '+00:00')) if research_as_of else datetime.now(timezone.utc)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    body = dict(schema_version="fin_ia_conversation_source_scope_v1_0", case_id=thread_id,
        research_as_of=cutoff.replace(hour=0,minute=0,second=0,microsecond=0).isoformat(),
        data_snapshot_id="dated-public-sources-v2" if research_as_of else "conversation-public-sources-v1",
        method_sha256=method_digest, selected_branch_ids=["conversation"], execution_attempt_id=run_id,
        source_policy="public_web_locator_only")
    # Pydantic canonical datetime serialization uses Z; hash the same representation.
    body["research_as_of"] = body["research_as_of"].replace("+00:00", "Z")
    scope = ConversationSourceScope(**body, run_scope_digest=canonical_sha256(body))
    quota = None
    if reader is None:
        quota = ExaTaskQuota(Path(cache_root).resolve() / thread_id)
        guard = PublicURLGuard()
        origin = StaticHTTPPageFetcher(guard=guard)
        if research_as_of:
            from sec_agent.research_foundation.company_disclosures import CompanySources
            companies = CompanySources(sec_user_agent, origin)
            origin = SearchReadOrigin(companies)
        from sec_agent.research_foundation.public_posts import PublicPostFetcher
        from .market_prices import task_cutoff
        origin = SearchReadOrigin(PublicPostFetcher(origin, cutoff=task_cutoff(research_as_of)))
        capture = ExternalSourceCapture(guard=guard, static_fetcher=origin,
            hosted_fetcher=ExaHostedMCPPageFetcher(guard=guard,max_characters=200000,quota=quota))
        cached = ScopedSourceCaptureCache(root=cache_root,thread_id=thread_id,capture=capture,guard=guard)
        fallback = DDGSDiagnosticProvider()
        discovery = ExternalSourceDiscovery(primary=ExaHostedMCPProvider(quota=quota), diagnostic_fallback=None if research_as_of else fallback)
        if research_as_of:
            from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
            discovery = DatedWebDiscovery(discovery, ExaHostedMCPPageFetcher(guard=guard,max_characters=8000,quota=quota),
                fallback_discovery=ExternalSourceDiscovery(primary=fallback), origin_fetcher=origin,
                search_backup=ExternalSourceDiscovery(primary=paid_search) if paid_search else None, companies=companies)
        reader = WebSourceReader(discovery=discovery,capture=cached)

    restored = set()

    @tool(response_format="content_and_artifact")
    async def read_public_source(operation: Literal["search","read"], query: str = "",
            document_id: str | None = None, offset: int = 0, max_characters: int = 6000,
            runtime: ToolRuntime = None):
        """Search public web sources, then read an exact returned WEB document ID.
        A company name/ticker and earnings period can locate SEC filings. For issuer
        websites search the company name plus "official website" and topic. Website
        roots in receipts are navigation only. Read documents before citing them.
        For a Congress.gov bill URL or explicit Congress/type/number, use
        read_legislation for official metadata, actions and text-version links;
        then read its selected official rendition here. Topic searches still use
        this search tool; Congress metadata is not a full-text keyword search.
        Public X posts can be found with site:x.com and author/topic, or a complete
        post URL. Read returned documents to see original embed text, author and
        timestamp; search coverage is incomplete. A badge does not establish
        identity or factual truth. event_policy provides optional news methods.
        For a dated task, search with a complete public HTTPS URL as query to verify
        that original or its publisher's catalog page directly. Use the returned
        document ID and source URL; each accepted page has its own identity.
        To locate a section, search again with that document_id and keywords;
        this returns exact bounded passages from the captured original, which
        may be cited with their source locators. Only read adjacent character
        offsets if more context is needed. Global search previews are not verified evidence. Read original text before
        citing; assess publisher/date and preserve limitations. Only submit
        public search terms, never credentials or private uploaded content.
        Captures are cached within this thread; they are not automatically
        admitted to a shared knowledge base. A new round may need a new search.
        """
        try:
            # Discovery candidates belong to this task, not a transient run.
            # Restore only host-saved tool artifacts; the model cannot register URLs.
            if runtime is not None and hasattr(reader, 'restore_navigation'):
                from sec_agent.research_foundation.external_sources import DiscoveryReceipt
                from sec_agent.research.reviewed_evidence_pack import canonical_digest
                for message in runtime.state.get('messages', []):
                    if getattr(message, 'name', None) != 'read_public_source' or getattr(message, 'status', None) != 'success':
                        continue
                    for raw in (getattr(message, 'artifact', None) or {}).get('web_navigation_receipts', []):
                        receipt = DiscoveryReceipt.model_validate(raw)
                        if receipt.receipt_digest in restored:
                            continue
                        if receipt.case_id != thread_id:
                            raise ValueError('public_source_restore_task_mismatch')
                        if receipt.data_snapshot_id != scope.data_snapshot_id or receipt.research_as_of[:10] != cutoff.date().isoformat():
                            continue
                        rebound = receipt.model_dump(mode='json', exclude={'receipt_digest'})
                        rebound.update(execution_attempt_id=scope.execution_attempt_id,
                            run_scope_digest=scope.run_scope_digest, research_as_of=scope.research_as_of.astimezone(timezone.utc).isoformat(timespec='seconds'),
                            data_snapshot_id=scope.data_snapshot_id, method_sha256=scope.method_sha256)
                        lineage = {key: rebound[key] for key in ('execution_attempt_id', 'run_scope_digest',
                                   'research_as_of', 'data_snapshot_id', 'method_sha256')}
                        rebound['candidates'] = [{**candidate, **lineage} for candidate in rebound['candidates']]
                        reader.restore_navigation([{**rebound, 'receipt_digest': canonical_digest(rebound)}],
                            branch_id='conversation', run_scope=scope)
                        restored.add(receipt.receipt_digest)
            if operation == "read" and query:
                raise ValueError("read accepts document_id and character offset, not query. Use operation=search with document_id and query to locate a section, then read at character_start without query.")
            if max_characters > 24000:
                raise ValueError("Use at most 24000 characters and paginate with offset")
            previously_limited = quota and quota.limited
            result = await reader(request=SourceDocumentRequest(source_space="web",operation=operation,
                query=query,document_id=document_id,offset=offset,max_characters=max_characters,limit=5,
                **({'end_published_date': scope.research_as_of.date()} if operation == 'search' and not document_id else {})),
                branch_id="conversation",run_scope=scope)
            artifact = result.model_dump(mode="json")
            visible = dict(artifact)
            direct = bool(research_as_of and operation == 'search' and not document_id and is_url_query(query))
            attempts = (visible.get('execution_receipt') or {}).get('attempts', [])
            legislative = [nav for attempt in attempts for nav in attempt.get('legislation_navigation', [])]
            if legislative:
                visible['legislation_navigation'] = legislative
                visible['next_step'] = 'Official bill identities found; call the listed read_legislation entries to select dated versions and obtain full text. Empty WEB items does not mean no bills were found.'
            company_attempts = [a for a in attempts if a.get('issuer_navigation')]
            if company_attempts:
                # Take the latest site information (verified filings can supply new roots).
                nav = dict(company_attempts[-1]['issuer_navigation'])
                visible['issuer_navigation'] = nav
                from urllib.parse import urlsplit
                from sec_agent.research_foundation.external_sources import _host_in_domains
                domains = [urlsplit(root).hostname.removeprefix('www.') for root in nav['websites']]
                for item in visible.get('items',[]):
                    host = urlsplit(item.get('source_url','')).hostname or ''
                    item['discovery_channel'] = ('SEC EDGAR' if host == 'www.sec.gov' else
                        'issuer website' if _host_in_domains(host,domains) else 'other publisher')
                visible['official_source_attempts'] = [
                    {'channel':a['provider_id'], 'failure':a.get('failure_code'),
                     'outcomes':a.get('date_filter_counts',{}),
                     'failed_originals':a['issuer_navigation'].get('filing_attempts',[])}
                    for a in company_attempts
                    if a['provider_id']=='sec_edgar_filings' or a['provider_id'].startswith('issuer_site_')]
            feedback = web_read_feedback(visible)
            if legislative:
                feedback = [f for f in feedback if f['kind'] != 'candidates_not_admitted']
            rejected = sum(a.get('candidate_filter_counts',{}).get('outside_requested_domains',0) for a in attempts)
            if rejected:
                feedback.append({'kind':'provider_ignored_domain_constraint','count':rejected,
                    'meaning':'搜索通道返回了指定域名之外的网页，已排除；这些不算有效命中，也不能据此判断指定网站没有资料。可换搜索通道或使用已知官方入口。'})
            if quota and quota.limited and not direct:
                route = 'deepseek_search_then_ddgs' if paid_search and research_as_of else 'ddgs'
                visible['web_search_route'] = {'active_provider':route,'scope':'task','reason':'confirmed_exa_rate_limit'}
                if not previously_limited:
                    feedback = [hint for hint in feedback if hint['kind'] != 'search_rate_limited']
                    feedback.insert(0, {'kind':'search_route_changed','meaning':
                        f'Exa 已返回限流，本任务已切换至 {route}。后续搜索及恢复本任务时将跳过 Exa；继续使用 read_public_source 即可。'})
            if feedback:
                visible['read_feedback'] = feedback
            if operation == 'search':
                visible['search_coverage'] = {'space': 'public_web', 'research_as_of': body['research_as_of'],
                    'query': query, 'document_id': document_id,
                    'query_kind': ('captured_document_search' if document_id else
                                   'direct_public_url' if direct else 'provider_ranked_search'),
                    'issuer_non_disclosure_established': False,
                    'meaning': ('Dated discovery omits undated or post-cutoff results before display. '
                                'accepted_hits counts search candidates before date checks; date_filter_counts shows what passed and why others were omitted. '
                                if scope.data_snapshot_id == 'dated-public-sources-v2' else '') +
                               'Provider results/captured text only, not exhaustive public disclosure coverage.'}
            if hasattr(reader, 'export_navigation'):
                artifact['web_navigation_receipts'] = reader.export_navigation()
            return json.dumps(visible,ensure_ascii=False), artifact
        except (ValueError, ExternalSourceError) as exc:
            raise ToolException("公开来源读取未完成，不代表信息未披露：" + str(exc)) from exc
    read_public_source.handle_tool_error = True
    return GrantedTool(read_public_source,"read","公开网页搜索与原文读取；仅本对话缓存")
