"""Official hosted HiThink MCP integration; schemas and data stay vendor-owned."""
import asyncio
from datetime import datetime, timezone
import json
import os
from typing import Literal

from langchain_core.tools import tool
from .conversation_agent import GrantedTool

DOMAINS = {
    'meta': '标的名称/代码检索与消歧',
    'a-share': 'A股行情、历史K线、财务、估值、公司行动、竞价、特色数据',
    'a-share-index': '指数板块目录、成分和行情',
    'fund': '基金资料、财务、持仓、净值、收益、经理及资讯元数据',
    'futures': '公开期货品种、合约、持仓、仓单、基差、日程与行情',
    'options': '公开期权品种、合约与行情',
}


def openapi_nullable_schema(value):
    """Translate declared OpenAPI nullable to JSON Schema, preserving all constraints."""
    if isinstance(value, list):
        return [openapi_nullable_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    out = {k: openapi_nullable_schema(v) for k, v in value.items() if k != 'nullable'}
    if value.get('nullable') is True and 'type' in out:
        return {'anyOf': [out, {'type': 'null'}]}
    return out


def hithink_data_tool(*, research_as_of=None, client_factory=None):
    key = os.environ.get('HITHINK_FINANCE_API_KEY', '')
    if not key and not client_factory:
        return None
    catalogs = {}

    async def request(domain, action, name='', arguments=None):
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        async with asyncio.timeout(50):
            async with httpx2.AsyncClient(headers={'X-api-key': key}, timeout=40, trust_env=False) as http:
                from contextlib import asynccontextmanager
                @asynccontextmanager
                async def native():
                    class VendorSession(ClientSession):
                        async def validate_tool_result(self, tool_name, result):
                            # Vendor declares OpenAPI nullable in MCP outputSchema.
                            # Use the public SDK validation hook; never rewrite data/nulls.
                            if result.is_error:
                                return
                            from jsonschema import Draft202012Validator
                            schema = catalogs[domain][tool_name].get('output_schema')
                            if schema:
                                Draft202012Validator(openapi_nullable_schema(schema)).validate(result.structured_content)
                    async with streamable_http_client('https://fuyao.aicubes.cn/mcp/' + domain, http_client=http) as streams:
                        async with VendorSession(*streams, read_timeout_seconds=40) as session:
                            await session.initialize()
                            yield session
                async with (client_factory(domain) if client_factory else native()) as client:
                    if action == 'list':
                        result = await client.list_tools()
                        tools = list(result.tools)
                        while result.next_cursor:
                            result = await client.list_tools(cursor=result.next_cursor)
                            tools.extend(result.tools)
                        return {t.name: t.model_dump(mode='json') for t in tools if t.name.startswith('get_')}
                    return await client.call_tool(name, arguments or {})

    @tool(response_format='content_and_artifact')
    async def query_hithink(operation: Literal['catalog', 'describe', 'call'],
                           domain: Literal['meta', 'a-share', 'a-share-index', 'fund', 'futures', 'options'] = 'meta',
                           tool_name: str = '', arguments: dict | None = None,
                           offset: int = 0, limit: int = 20):
        """Query all six official HiThink/同花顺 Financial-API hosted MCP domains.
        catalog lists available read tools; describe returns the selected tool's live
        schema; call uses its exact name and arguments. Resolve names to thscode in
        meta first. Use vendor pagination and small date/symbol windows. Financial
        statements, funds, futures and options each have separate domains. No news
        article/report full text, HK/US quotes, trading or client-only data is promised.
        Historical-cutoff data requires a verified publication vintage; current
        responses cannot prove what was known at that time. Large raw results are
        preserved in the normal saved result, with a bounded preview here.
        """
        now = datetime.now(timezone.utc)
        out = dict(provider='hithink_official_mcp', operation=operation, domain=domain,
                   captured_at=now.isoformat(), research_as_of=research_as_of,
                   writer_citable=False, numeric_fact_authority=False)
        def finish():
            # Artifact is complete and goes through the existing result store.
            encoded = json.dumps(out, ensure_ascii=False, default=str)
            if len(encoded) <= 24000:
                return encoded, out
            preview = {k: v for k, v in out.items() if k != 'result'}
            preview.update(result_preview=json.dumps(out.get('result'), ensure_ascii=False)[:16000],
                           preview_truncated=True, full_result='read_saved_result for this tool call')
            return json.dumps(preview, ensure_ascii=False), out
        if domain not in DOMAINS or not 1 <= limit <= 100 or offset < 0:
            out.update(status='invalid_parameters', detail='Use a listed domain; limit 1..100, offset >= 0.')
            return finish()
        try:
            if domain not in catalogs:
                catalogs[domain] = await request(domain, 'list')
            catalog = catalogs[domain]
            if operation == 'catalog':
                entries = list(catalog.values())
                out.update(status='ok', domains=DOMAINS, total=len(entries),
                           result=[{k: t.get(k) for k in ('name', 'description')} for t in entries[offset:offset+limit]],
                           next_offset=offset+limit if offset+limit < len(entries) else None)
            elif tool_name not in catalog:
                out.update(status='unknown_tool', detail='Use catalog for this domain, then describe the returned name.')
            elif operation == 'describe':
                out.update(status='ok', result=catalog[tool_name])
            else:
                from jsonschema import Draft202012Validator
                schema = catalog[tool_name]['input_schema']
                errors = list(Draft202012Validator(schema).iter_errors(arguments or {}))
                if errors:
                    out.update(status='invalid_parameters', detail=[e.message for e in errors], schema=schema)
                    return finish()
                historical = bool(research_as_of and str(research_as_of)[:10] < now.date().isoformat())
                if historical and domain != 'meta':
                    out.update(status='historical_vintage_unverified', detail=
                        'This vendor integration has no publication-version contract yet. No data call made. '
                        'Read dated originals with read_public_source; report period alone does not establish public availability.')
                    return finish()
                result = await request(domain, 'call', tool_name, arguments)
                data = result.structured_content
                if data is None:
                    texts = [b.text for b in result.content if getattr(b, 'type', '') == 'text']
                    try: data = json.loads(texts[0]) if len(texts) == 1 else texts
                    except ValueError: data = texts
                if isinstance(data, dict) and set(data) == {'result'}:
                    data = data['result']
                code = data.get('code') if isinstance(data, dict) else None
                status = 'provider_error' if result.is_error or code != 0 else 'ok'
                if historical and domain == 'meta' and status == 'ok':
                    envelope = data.get('data') or {}
                    rows = envelope.get('item', [])
                    data = {**data, 'data': {'item': [{k: v for k, v in row.items() if k in
                            {'thscode', 'ticker', 'name', 'asset_type', 'exchange'}} for row in rows]}}
                    out['navigation_only'] = 'Current issuer identity; not historical company attributes.'
                out.update(status=status, tool_name=tool_name, arguments=arguments or {}, result=data,
                           availability='Current vendor response; retain field units, report dates and adjustment basis.')
        except Exception as exc:
            out.update(status='provider_unavailable', error_type=type(exc).__name__,
                       detail='Official MCP did not complete; not evidence of missing data. No automatic retry.')
        return finish()

    return GrantedTool(query_hithink, 'read', '同花顺官方六域 MCP：原生能力发现、schema 与只读取数')
