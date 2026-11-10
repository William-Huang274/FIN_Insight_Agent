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


def public_web_request_feedback(arguments):
    """Describe a correctable operation/parameter mismatch without executing it."""
    operation, document = arguments.get('operation'), arguments.get('document_id')
    fields = []
    if operation == 'read' and arguments.get('query'):
        fields.append('query')
    if operation != 'search' or document:
        fields += [key for key in ('search_language', 'start_published_date', 'end_published_date')
                   if arguments.get(key) is not None]
        if arguments.get('search_backend', 'auto') != 'auto':
            fields.append('search_backend')
    if not fields:
        return None
    return {'feedback_kind': 'public_source_request_validation',
        'code': 'parameters_not_applicable_to_operation', 'request_dispatched': False,
        'request_modified': False, 'submitted_arguments': dict(arguments),
        'inapplicable_fields': fields,
        'read_options': [{'tool': 'read_public_source', 'operation': operation,
            'document_id': document, 'remove_fields': fields}],
        'next_step': 'Resubmit your intended operation without these fields. '
            'Search backend, language and publication filters apply only to global search '
            '(operation=search without document_id). Read uses document_id, offset and max_characters. '
            'To search inside this document use operation=search, document_id and query. '
            'No source selection or research judgment was changed.'}


def search_execution_faults(result):
    """Metering/dispatch faults must not masquerade as a researched absence."""
    fatal = {'deepseek_web_response_unconfirmed', 'deepseek_web_prior_call_unresolved',
             'deepseek_web_dispatch_blocked'}
    found = set()
    for attempt in (result.get('execution_receipt') or {}).get('attempts', []):
        code = attempt.get('failure_code')
        if code in fatal:
            found.add(code)
        for failure in attempt.get('verification_failures', {}):
            code = failure.split(':', 1)[-1]
            if code in fatal:
                found.add(code)
    return sorted(found)


def web_read_feedback(result):
    """Explain only recorded obstacles, without exposing excluded candidate data."""
    verification = Counter()
    for attempt in (result.get('execution_receipt') or {}).get('attempts', []):
        verification.update(attempt.get('verification_failures', {}))
    details = ([{'kind':'source_verification_failures','stages':dict(verification),
        'meaning':'搜索与读取分开计。original_read 是原站访问；deepseek_fetch 是 DS 网页抓取；date_verification 是日期核验/备用读取。这些失败不表示 DS Search 没有返回候选，也不表示信息不存在。'}]
        if verification else [])
    if result.get('items'):
        return details
    counts = Counter()
    codes = set()
    engines = {}
    returned = 0
    no_overlap = 0
    for attempt in (result.get('execution_receipt') or {}).get('attempts', []):
        counts.update(attempt.get('date_filter_counts', {}))
        codes.add(attempt.get('failure_code'))
        engines.update(attempt.get('engine_http', {}))
        returned += attempt.get('returned_hits', 0)
        no_overlap += attempt.get('candidate_filter_counts', {}).get('no_query_term_overlap', 0)
    feedback = []
    if no_overlap:
        feedback.append({'kind':'fallback_query_mismatch','count':no_overlap,
            'meaning':'备用搜索返回的这些候选与查询词没有可见对应，未当作有效结果。此检查不是语义相关性判断，也不证明资料不存在；可改用产品名、同义表达或明确发布者的站内查询。'})
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
    if counts['origin_access_challenge']:
        feedback.append({'kind':'origin_access_challenge','meaning':'原站返回安全验证页（可能是 HTTP 200），没有取得原文；这不是日期缺失或未披露。可查同发布者的产品文档、官方 API 或同版原件，不要把挑战脚本当正文。'})
    if counts['scholarly_metadata_unavailable']:
        feedback.append({'kind':'scholarly_metadata_unavailable','meaning':'论文官方版本元数据尚未取得，不能据此认定论文不存在。可用准确 arXiv ID/版本链接核查；版本日期与全文读取分别计。'})
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
    if any(str(code).startswith('searxng_') for code in codes):
        feedback.append({'kind':'regional_search_fault', 'codes':sorted(str(c) for c in codes if str(c).startswith('searxng_')),
            'meaning':'所选检索通道未正常完成。not_configured 是部署未配置，CAPTCHA 是访问验证，timeout/TLS 是连接问题；均不表示没有资料。可选其他已配置通道或已知原件网址，不自动重复故障请求。'})
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
    return details + feedback


def public_web_tool(*, thread_id, run_id, method_digest, cache_root: Path, reader=None, research_as_of=None, paid_search=None, sec_user_agent=None, imported_navigation=None):
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
        from sec_agent.research_foundation.government_sources import GovernmentSourceFetcher
        origin = GovernmentSourceFetcher(origin, paid_search)
        if research_as_of:
            from sec_agent.research_foundation.company_disclosures import CompanySources
            companies = CompanySources(sec_user_agent, origin)
            origin = SearchReadOrigin(companies)
        from sec_agent.research_foundation.public_posts import PublicPostFetcher
        from .market_prices import task_cutoff
        origin = SearchReadOrigin(PublicPostFetcher(origin, cutoff=task_cutoff(research_as_of)))
        from sec_agent.research_foundation.scholarly_sources import ArxivSources
        scholarly = ArxivSources(origin)
        origin = scholarly
        capture = ExternalSourceCapture(guard=guard, static_fetcher=origin,
            hosted_fetcher=ExaHostedMCPPageFetcher(guard=guard,max_characters=200000,quota=quota))
        cached = ScopedSourceCaptureCache(root=cache_root,thread_id=thread_id,capture=capture,guard=guard)
        from sec_agent.research_foundation.regional_search import SearxNGProvider, SelectedSearchDiscovery
        regional_provider = SearxNGProvider()
        regional = ExternalSourceDiscovery(primary=regional_provider)
        fallback = DDGSDiagnosticProvider()
        discovery = ExternalSourceDiscovery(primary=ExaHostedMCPProvider(quota=quota), diagnostic_fallback=None if research_as_of else fallback)
        if research_as_of:
            from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
            discovery = DatedWebDiscovery(discovery, ExaHostedMCPPageFetcher(guard=guard,max_characters=8000,quota=quota),
                fallback_discovery=ExternalSourceDiscovery(primary=fallback), origin_fetcher=origin,
                search_backup=ExternalSourceDiscovery(primary=paid_search) if paid_search else None, companies=companies,
                scholarly=scholarly, regional_discovery=regional if regional_provider.endpoint else None)
        else:
            discovery = SelectedSearchDiscovery(discovery, regional)
        reader = WebSourceReader(discovery=discovery,capture=cached)

    restored = set()
    # Exact receipts from a host-verified import, never model-supplied task IDs.
    imported_navigation = dict(imported_navigation or {})

    @tool(response_format="content_and_artifact")
    async def read_public_source(operation: Literal["search","read"], query: str = "",
            document_id: str | None = None, offset: int = 0, max_characters: int = 6000,
            start_published_date: str | None = None, end_published_date: str | None = None,
            search_backend: Literal['auto','bing','bing_china','baidu','github','bilibili'] = 'auto',
            search_language: str | None = None, runtime: ToolRuntime = None):
        """Search public web sources, then read an exact returned WEB document ID.
        Global discovery accepts search_backend=bing (international), bing_china,
        baidu (opt-in), github (repository search), bilibili (video discovery),
        or auto (existing providers plus configured regional fallback).
        search_language selects a locale such as zh-CN, zh-TW, ja-JP, ko-KR,
        en-US or ru-RU. Use local product names and native-language queries;
        Backend, language and publication filters apply only to global search,
        without document_id. Omit them when reading or searching inside a document.
        a site's location or a search result does not establish market coverage.
        site: can scope searches to zhihu.com, douyin.com, jimeng.jianying.com,
        eastmoney.com or 10jqka.com.cn. This is web discovery, not authenticated
        community search, video transcription or a financial database API.
        Engine availability is deployment-dependent; faults are reported, not
        silently replaced with a different paid engine. Search previews are not
        customer evidence until the actual content has been read and assessed.
        A company name/ticker and earnings period can locate SEC filings, including
        6-K/20-F/40-F and amendments. An explicit SEC form selects that form from
        the issuer's inventory. Use YYYY-MM-DD start_published_date/end_published_date
        for publication dates (not financial reporting periods), on global search only.
        Filing indexes expose separate document/exhibit URLs; read a selected URL
        through search then its returned document ID. A 6-K is not always earnings.
        If the issuer site is blocked, use the returned regulatory_readback entry.
        For issuer
        websites search the company name plus "official website" and topic. Website
        roots in receipts are navigation only. Read documents before citing them.
        For a Congress.gov bill URL or explicit Congress/type/number, use
        read_legislation for official metadata, actions and text-version links;
        then read its selected official rendition here. Topic searches still use
        this search tool; Congress metadata is not a full-text keyword search.
        For government originals use site: with the issuing institution (e.g.
        gov.texas.gov, tceq.texas.gov, ercot.com, whitehouse.gov). Search receipts
        offer these scoped entries when the query names an institution. Read a
        release's observed links to find its directive or attachment; each linked
        document still needs its own date check. ERCOT notices may use a labelled
        hosted Fetch transcription when direct HTTP is unavailable.
        Public X posts can be found with site:x.com and author/topic, or a complete
        post URL. Read returned documents to see original embed text, author and
        timestamp; search coverage is incomplete. A badge does not establish
        identity or factual truth. event_policy provides optional news methods.
        arXiv abstract URLs resolve through its official versioned API record.
        The returned abstract is not the full paper: follow its versioned PDF
        or HTML link through search/read to inspect methods and results. A newer
        revision is not admitted under the original submission date.
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
        feedback = public_web_request_feedback(dict(operation=operation, query=query,
            document_id=document_id, offset=offset, max_characters=max_characters,
            search_backend=search_backend, search_language=search_language,
            start_published_date=start_published_date, end_published_date=end_published_date))
        if feedback:
            raise ToolException(json.dumps(feedback, ensure_ascii=False))
        try:
            # Discovery candidates belong to this task, not a transient run.
            # Restore only host-saved tool artifacts; the model cannot register URLs.
            if runtime is not None and hasattr(reader, 'restore_navigation'):
                from sec_agent.research_foundation.external_sources import DiscoveryReceipt
                from sec_agent.research.reviewed_evidence_pack import canonical_digest
                for message in runtime.state.get('messages', []):
                    saved_artifact = getattr(message, 'artifact', None) or {}
                    if (getattr(message, 'name', None) != 'read_public_source'
                            or (getattr(message, 'status', None) != 'success'
                                and not saved_artifact.get('execution_stop'))):
                        continue
                    for raw in (getattr(message, 'artifact', None) or {}).get('web_navigation_receipts', []):
                        # These are immutable host-saved receipts. Each later
                        # observation may carry the same directory again; only
                        # validate/restore each identity once in this reader.
                        if raw.get('receipt_digest') in restored:
                            continue
                        receipt = DiscoveryReceipt.model_validate(raw)
                        if receipt.receipt_digest in restored:
                            continue
                        if (receipt.case_id != thread_id and
                                imported_navigation.get(receipt.receipt_digest) != receipt.case_id):
                            raise ValueError('public_source_restore_task_mismatch')
                        if receipt.data_snapshot_id != scope.data_snapshot_id or receipt.research_as_of[:10] != cutoff.date().isoformat():
                            continue
                        rebound = receipt.model_dump(mode='json', exclude={'receipt_digest'})
                        rebound.update(case_id=thread_id, execution_attempt_id=scope.execution_attempt_id,
                            run_scope_digest=scope.run_scope_digest, research_as_of=scope.research_as_of.astimezone(timezone.utc).isoformat(timespec='seconds'),
                            data_snapshot_id=scope.data_snapshot_id, method_sha256=scope.method_sha256)
                        lineage = {key: rebound[key] for key in ('case_id', 'execution_attempt_id', 'run_scope_digest',
                                   'research_as_of', 'data_snapshot_id', 'method_sha256')}
                        rebound['candidates'] = [{**candidate, **lineage} for candidate in rebound['candidates']]
                        reader.restore_navigation([{**rebound, 'receipt_digest': canonical_digest(rebound)}],
                            branch_id='conversation', run_scope=scope)
                        restored.add(receipt.receipt_digest)
            # SourceDocumentRequest owns the shared read-window bounds. Do not
            # impose an undisclosed, narrower limit in the conversation wrapper.
            previously_limited = quota and quota.limited
            date_filters = ({'end_published_date': scope.research_as_of.date()}
                            if operation == 'search' and not document_id else {})
            if search_backend != 'auto' or search_language:
                date_filters.update(search_backend=search_backend, search_language=search_language)
            if start_published_date is not None:
                date_filters['start_published_date'] = start_published_date
            if end_published_date is not None:
                date_filters['end_published_date'] = end_published_date
            result = await reader(request=SourceDocumentRequest(source_space="web",operation=operation,
                query=query,document_id=document_id,offset=offset,max_characters=max_characters,limit=5,
                **date_filters),
                branch_id="conversation",run_scope=scope)
            artifact = result.model_dump(mode="json")
            visible = dict(artifact)
            # Keep complete directory receipts in the artifact; disclose a single
            # navigable directory view, not the same entries in every attempt.
            receipt = dict(visible.get('execution_receipt') or {})
            visible_attempts = []
            for attempt in receipt.get('attempts',[]):
                entry = dict(attempt)
                if entry.get('issuer_navigation'):
                    entry['issuer_navigation'] = {k:v for k,v in entry['issuer_navigation'].items()
                                                 if k not in {'filing_documents','filing_indexes'}}
                visible_attempts.append(entry)
            receipt['attempts'] = visible_attempts
            visible['execution_receipt'] = receipt
            direct = bool(research_as_of and operation == 'search' and not document_id and is_url_query(query))
            attempts = (visible.get('execution_receipt') or {}).get('attempts', [])
            legislative = [nav for attempt in attempts for nav in attempt.get('legislation_navigation', [])]
            if legislative:
                visible['legislation_navigation'] = legislative
                visible['next_step'] = 'Official bill identities or version catalogs found; use the tool and arguments in each listed read entry to select a dated version and read its text. Empty WEB items does not mean no bills were found.'
            company_attempts = [a for a in attempts if a.get('issuer_navigation')]
            if company_attempts:
                # Take the latest site information (verified filings can supply new roots).
                nav = dict(company_attempts[-1]['issuer_navigation'])
                original_attempts = (artifact.get('execution_receipt') or {}).get('attempts',[])
                documents = {d['url']:d for a in original_attempts
                             for d in a.get('issuer_navigation',{}).get('filing_documents',[])}
                if documents:
                    nav['filing_documents'] = list(documents.values())[:24]
                    nav['filing_documents_available'] = len(documents)
                    nav['filing_documents_windowed'] = len(documents) > 24
                indexes = {d['url']:d for a in original_attempts
                           for d in a.get('issuer_navigation',{}).get('filing_indexes',[])}
                if indexes:
                    nav['filing_indexes'] = list(indexes.values())
                    nav['directory_readback'] = 'For any additional document, search the complete filing index URL, read it, then search the selected document URL. Directory entries are not read evidence.'
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
            unresolved = [row for attempt in attempts for row in attempt.get('unresolved_originals', [])]
            if unresolved:
                visible['unresolved_originals'] = list({row['url']:row for row in unresolved}.values())
                feedback.append({'kind':'unresolved_original_navigation',
                    'meaning':'这些网址尚未取得符合截止日的正文，不能引用。可用出版者检索入口寻找有日期的公告、归档或同版原件；路径文字和网址日期不是已核实事实。晚于截止日的候选不在此列表。'})
            if operation == 'search' and not document_id:
                from sec_agent.research_foundation.government_sources import official_search_entries
                entries = official_search_entries(query)
                if entries:
                    visible['official_source_navigation'] = entries
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
            faults = search_execution_faults(artifact)
            if faults:
                visible['execution_stop'] = artifact['execution_stop'] = {
                    'codes': faults, 'reason': 'Search dispatch or usage is unresolved; host recovery is required. '
                    'Successful candidates remain recorded. Do not infer source absence from this failure.'}
                if runtime is not None and getattr(runtime, 'tool_call_id', None):
                    from langchain_core.messages import ToolMessage
                    # BaseTool validates content_and_artifact before formatting
                    # ToolOutputMixin. Preserve the error ToolMessage in the
                    # declared tuple, rather than returning a rejected Command.
                    return (ToolMessage(name='read_public_source',
                        tool_call_id=runtime.tool_call_id, status='error',
                        content=json.dumps(visible, ensure_ascii=False), artifact=artifact), artifact)
                raise ToolException(json.dumps(visible, ensure_ascii=False))
            return json.dumps(visible,ensure_ascii=False), artifact
        except (ValueError, ExternalSourceError) as exc:
            if str(exc) == 'web_document_not_discovered_in_this_scope_search_first':
                # A model-selected locator is not an execution/authority failure.
                # Point back to observed directories; never guess a replacement ID
                # or admit a URL that has not passed dated discovery.
                options = []
                messages = runtime.state.get('messages', []) if runtime is not None else []
                for message in reversed(messages):
                    artifact = getattr(message, 'artifact', None) or {}
                    if (getattr(message, 'name', None) == 'read_public_source'
                            and getattr(message, 'status', None) == 'success'
                            and artifact.get('operation') == 'search'
                            and getattr(message, 'tool_call_id', None)):
                        options.append({'tool': 'read_saved_result', 'arguments': {
                            'tool_call_id': message.tool_call_id}})
                        if len(options) == 3:
                            break
                raise ToolException(json.dumps({
                    'feedback_kind': 'public_source_selection', 'code': str(exc),
                    'submitted_document_id': document_id, 'request_dispatched': False,
                    'request_modified': False, 'read_options': options,
                    'next_step': 'This document ID is not in the current authorized discovery directory. '
                        'Reopen an observed search receipt and select its exact document_id. '
                        'Alternatively search using your public query or a known public HTTPS URL; '
                        'a failed locator does not establish source absence.',
                }, ensure_ascii=False)) from exc
            raise ToolException("公开来源读取未完成，不代表信息未披露：" + str(exc)) from exc
    read_public_source.handle_tool_error = True
    return GrantedTool(read_public_source,"read","公开网页搜索与原文读取；仅本对话缓存")
