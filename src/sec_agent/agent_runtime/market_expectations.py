"""Selected read-only forecast tools from the vendor's official hosted MCP."""
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Literal
from urllib.parse import urlencode

from langchain_core.tools import tool
from .conversation_agent import GrantedTool
from sec_agent.research_foundation.expectation_sources import alpha_response, expectation_passage
from sec_agent.research_foundation.public_provider_cache import PublicProviderCache


class _CredentialFilter(logging.Filter):
    def __init__(self, key):
        super().__init__()
        self.key = key

    def filter(self, record):
        record.msg = record.getMessage().replace(self.key, '[REDACTED]')
        record.args = ()
        return True


def market_expectations_tool(*, research_as_of=None, cache_root=None, client_factory=None):
    key = os.environ.get('ALPHAVANTAGE_API_KEY', '')
    if not key and not client_factory:
        return None
    root = Path(cache_root or os.environ.get('FIN_PUBLIC_DATA_CACHE_ROOT') or
                Path(tempfile.gettempdir()) / 'finsight-public-data')
    cache = PublicProviderCache(root, provider='alpha_vantage', credential=key)

    async def fetch(function, symbol):
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        filters = []
        # Official noninteractive transport uses an API-key query parameter.
        # Never retain it in our records or HTTP diagnostic logs.
        if key:
            for name in ('httpx', 'httpx2', 'mcp.client.streamable_http'):
                logger, filt = logging.getLogger(name), _CredentialFilter(key)
                logger.addFilter(filt)
                filters.append((logger, filt))
        try:
            async with asyncio.timeout(50):
                async with httpx2.AsyncClient(timeout=40, trust_env=False) as http:
                    endpoint = 'https://mcp.alphavantage.co/mcp?' + urlencode({'apikey': key})
                    async with (client_factory() if client_factory else Client(
                            streamable_http_client(endpoint, http_client=http), read_timeout_seconds=40)) as client:
                        result = await client.call_tool(function, {'symbol': symbol, 'return_full_data': True})
                        parsed = alpha_response(result)
                        if parsed['status'] == 'ok':
                            data = parsed['data']
                            field = 'estimates' if function == 'EARNINGS_ESTIMATES' else 'quarterlyEarnings'
                            if data.get('symbol') != symbol or not isinstance(data.get(field), list):
                                return {'status': 'provider_identity_or_shape_mismatch'}
                        return parsed
        except Exception as exc:
            return {'status': 'provider_unavailable', 'error_type': type(exc).__name__,
                    'detail': 'Official MCP did not complete; not evidence of missing forecasts. No retry made.'}
        finally:
            for logger, filt in filters:
                logger.removeFilter(filt)

    @tool(response_format='content_and_artifact')
    async def read_market_expectations(symbol: str,
            dataset: Literal['estimates', 'earnings_history'] = 'estimates', offset: int = 0, limit: int = 10):
        """Read Alpha Vantage official consensus EPS/revenue estimates and revisions,
        or historical quarterly actual/estimated EPS and surprises. Use the vendor
        ticker, e.g. MSFT. Date + horizon identify target fiscal periods, not the
        date this forecast became public. Revision windows are rolling, not an
        arbitrary historical-vintage archive. Current observations only: an earlier
        research cutoff is refused before fetching. Currency/accounting basis absent
        from the response remains unknown; do not assume comparability. Page with
        offset/limit (1..50); a shared one-hour cache avoids duplicate provider calls.
        Cite the returned passage_id; calculate_research_metric can bind exact quotes
        and literals in it. Use read_saved_result to revisit that exact snapshot.
        A/港股预测用 query_public_data 的东方财富/经济通接口；同花顺官方行情不等于一致预期。
        """
        out = {'operation': 'read', 'provider': 'alpha_vantage_official_mcp',
               'numeric_fact_authority': False, 'items': []}
        def finish():
            view = {k:v for k,v in out.items() if k != 'provider_snapshot'}
            return json.dumps(view, ensure_ascii=False), out
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.\-^]{0,29}', symbol) or offset < 0 or not 1 <= limit <= 50:
            out.update(status='invalid_parameters', detail='Use a vendor ticker; offset>=0; limit=1..50.')
            return finish()
        if research_as_of and str(research_as_of)[:10] < datetime.now(timezone.utc).date().isoformat():
            out.update(status='historical_vintage_unverified', request_dispatched=False,
                       detail='Current forecasts and old target periods do not establish past availability. Use a dated original.')
            return finish()
        function = 'EARNINGS_ESTIMATES' if dataset == 'estimates' else 'EARNINGS'
        response = await cache.get({'function': function, 'symbol': symbol}, lambda: fetch(function, symbol))
        out.update({k: v for k, v in response.items() if k != 'data'})
        if response['status'] != 'ok':
            return finish()
        data = response['data']
        # Full response is persisted once with the native receipt, so pagination
        # and later cache refresh cannot erase unread rows from this observation.
        out['provider_snapshot'] = data
        field = 'estimates' if dataset == 'estimates' else 'quarterlyEarnings'
        rows = data[field]
        page = rows[offset:offset+limit]
        metadata = dict(provider=out['provider'], symbol=data['symbol'], dataset=dataset,
            captured_at=response['captured_at'], forecast_published_at=None,
            currency=None, accounting_basis=None,
            value_units={'eps': 'currency/share; currency not supplied', 'revenue': 'currency; currency not supplied',
                         'analyst_count': 'analysts', 'surprisePercentage': 'percent'},
            availability='Current provider snapshot, not a complete historic consensus archive.',
            interpretation='Provider sample, not all investors. Null does not mean zero. Target period is not publication date.')
        out.update(metadata=metadata, total_matches=len(rows),
                   next_offset=offset+len(page) if offset+len(page)<len(rows) else None)
        if page:
            out['items'] = [expectation_passage(rows=page, metadata=metadata,
                source_url='https://www.alphavantage.co/query?' + urlencode({'function': function, 'symbol': symbol}),
                title=f'{symbol} {dataset} — Alpha Vantage',
                readback={'tool': 'read_saved_result', 'instruction': 'Use the receipt_id of this result; pagination calls may capture a newer snapshot after cache expiry.'})]
        return finish()
    return GrantedTool(read_market_expectations, 'read', '官方 MCP 市场预期、修订及历史盈利差异；保留期间与未知口径')
