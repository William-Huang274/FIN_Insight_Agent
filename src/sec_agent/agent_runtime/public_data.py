"""Read-only AKTools MCP bridge; no FIN-owned financial website scrapers."""
import asyncio
from datetime import datetime, timezone
import json
import os
from typing import Literal
from urllib.parse import urlsplit

from langchain_core.tools import tool
from .conversation_agent import GrantedTool


def public_data_tool(*, research_as_of=None, endpoint=None, client_factory=None):
    endpoint = endpoint or os.environ.get('FIN_AKTOOLS_MCP_URL', '')
    if not endpoint and not client_factory:
        return None
    parsed = urlsplit(endpoint)
    if not client_factory and (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.query):
        raise ValueError('aktools_endpoint_invalid')

    @tool(response_format='content_and_artifact')
    async def query_public_data(operation: Literal['search', 'describe', 'data'],
                                query: str = '', interface: str = '',
                                parameters: dict[str, str] | None = None,
                                offset: int = 0, limit: int = 20):
        """Discover and call maintained AKShare interfaces through AKTools MCP.
        search: Chinese/English keywords such as 东方财富 新闻 or 同花顺 主营.
        describe: exact returned interface name, to read its parameters, source,
        units and coverage. data: that name and documented string parameters.
        Returned tables are current vendor responses, not archived financial
        disclosures. Data for historical-cutoff tasks is withheld: follow the
        original dated publication through read_public_source instead. A current
        data response is saved for read_saved_result, but is not automatically a
        verified citation or source-bound calculation input. No arbitrary URLs,
        credentials, code execution or trading operations are accepted.
        """
        now = datetime.now(timezone.utc)
        visible = {'provider': 'aktools', 'operation': operation,
                   'captured_at': now.isoformat(), 'research_as_of': research_as_of,
                   'writer_citable': False, 'numeric_fact_authority': False}
        if not 1 <= limit <= 100 or offset < 0:
            visible.update(status='invalid_parameters', detail='limit=1..100; offset>=0')
            return json.dumps(visible, ensure_ascii=False), visible
        historical = bool(research_as_of and str(research_as_of)[:10] < now.date().isoformat())
        if operation == 'data' and historical and interface != 'stock_news_em':
            visible.update(status='historical_vintage_unverified',
                detail='AKTools returns current vendor data. No historical publication vintage has been established; use a dated original. No remote data request made.')
            return json.dumps(visible, ensure_ascii=False), visible
        names = {'search': 'search_interfaces', 'describe': 'describe_interface', 'data': 'get_data'}
        args = ({'keyword': query} if operation == 'search' else {'name': interface})
        if operation == 'data':
            args.update(params=parameters or {}, offset=offset, max_rows=limit)
        try:
            from mcp import Client
            from mcp.client.streamable_http import streamable_http_client
            import httpx2
            token = os.environ.get('FIN_AKTOOLS_TOKEN', '')
            headers = {'Authorization': 'Bearer ' + token} if token else {}
            async with asyncio.timeout(45):
                async with httpx2.AsyncClient(headers=headers, timeout=40, trust_env=False) as http:
                    async with (client_factory() if client_factory else Client(
                            streamable_http_client(endpoint, http_client=http), read_timeout_seconds=40)) as client:
                        result = await client.call_tool(names[operation], args)
            if result.is_error:
                visible.update(status='provider_error', feedback=[b.text for b in result.content if getattr(b, 'type', '') == 'text'])
            else:
                data = result.structured_content
                if data is None:
                    data = [b.text for b in result.content if getattr(b, 'type', '') == 'text']
                # MCP v2 wraps non-object return annotations under `result`.
                if isinstance(data, dict) and set(data) == {'result'}:
                    data = data['result']
                if operation == 'data' and historical:
                    # AKShare documents 发布时间 as news publication time. This
                    # is a locator menu, not approval of article text/version.
                    rows = data.get('rows', []) if isinstance(data, dict) else []
                    total = data.get('total_rows', offset + len(rows)) if isinstance(data, dict) else 0
                    rows = [r for r in rows if r.get('发布时间') and
                            str(r['发布时间'])[:10] <= str(research_as_of)[:10]]
                    data = {'name': interface, 'rows': [
                        {k: r[k] for k in ('新闻标题', '新闻链接', '发布时间', '文章来源') if k in r}
                        for r in rows], 'returned_rows': len(rows),
                        'availability': 'publication-filtered candidate locators only; verify article version through read_public_source',
                        'next_offset': offset + limit if offset + limit < total else None,
                        'coverage': 'recent-news interface, not a complete archive'}
                # A search menu is bounded; data pagination belongs to AKTools.
                if operation == 'search' and isinstance(data, dict) and isinstance(data.get('items'), list):
                    data = {**data, 'items': data['items'][:limit]}
                visible.update(status='ok', result=data)
        except Exception as exc:
            # Do not echo transport exception strings containing credential URLs.
            visible.update(status='provider_unavailable', error_type=type(exc).__name__,
                           detail='AKTools request did not complete. This is not evidence of missing financial data; no automatic retry.')
        return json.dumps(visible, ensure_ascii=False, default=str), visible

    return GrantedTool(query_public_data, 'read', 'AKTools 原生 MCP：查找财经接口、查看参数和有界取数')
