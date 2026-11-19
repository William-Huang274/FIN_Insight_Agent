"""Preserve forecast table headers via the existing guarded original reader.

AKShare may rename away currency/scale. Never restore those by guessing from
the ticker: expose the independently captured original table, not a false join.
"""
from datetime import datetime, timezone
from hashlib import sha256
import re

from .external_sources import PublicURLGuard, StaticHTTPPageFetcher, trafilatura_extract_text


FORECAST_INTERFACES = {'stock_profit_forecast_em', 'stock_hk_profit_forecast_et'}


def original_url(interface, parameters):
    if interface == 'stock_profit_forecast_em':
        return 'https://data.eastmoney.com/report/profitforecast.jshtml'
    symbol = parameters.get('symbol', '09999')
    if interface == 'stock_hk_profit_forecast_et' and re.fullmatch(r'\d{1,5}', symbol):
        return 'https://www.etnet.com.hk/www/sc/stocks/realtime/quote_profit.php?code=' + str(int(symbol))
    return None


async def read_forecast_original(interface, parameters, *, fetcher=None):
    url = original_url(interface, parameters)
    if not url:
        return {'status': 'original_locator_unresolved'}
    fetcher = fetcher or StaticHTTPPageFetcher(guard=PublicURLGuard())
    try:
        page = await fetcher.fetch(url, timeout_seconds=25)
        text = page.extracted_text if page.extracted_text is not None else trafilatura_extract_text(page.html)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(page.html, 'html.parser')
        # Original labels are kept verbatim, including currency and scale. Do not
        # match renamed columns or silently substitute a newer original's values.
        headings = [[cell.get_text(' ', strip=True) for cell in table.select('tr')[0].find_all(['td', 'th'])]
                    for table in soup.find_all('table') if table.select('tr')]
        if not headings:
            return {'status': 'original_table_unavailable', 'source_url': page.final_url,
                    'detail': 'The original contains no readable table; page shell or disclaimer is not forecast evidence. Normalized data remains available with unknown units.'}
        if len(text.strip()) < 100:
            return {'status': 'original_text_unavailable', 'source_url': url}
        captured = datetime.now(timezone.utc).isoformat()
        digest = sha256(text.encode()).hexdigest()
        doc = 'WEB::FORECAST::' + digest
        item = dict(result_state='source_bound_passage', passage_id=f'PASSAGE::{doc}::0::{digest[:16]}',
            document_id=doc, passage=text, content_sha256=digest, source_url=page.final_url,
            title='盈利预测原件与原始表头', source_kind='forecast_original',
            source_role='external_public_source_unverified', source_read_method='guarded_original_http',
            writer_citable=True, numeric_fact_authority=False,
            source_locator=dict(source_url=page.final_url, captured_at=captured, document_id=doc,
                content_sha256=digest, character_start=0, character_end=len(text)),
            readback={'tool': 'read_saved_result', 'instruction': 'Use this result receipt_id to read this exact captured original.'})
        return {'status': 'ok', 'captured_at': captured, 'source_url': page.final_url,
                'raw_table_headers': headings, 'item': item,
                'relationship': 'Independent original snapshot; not automatically row-joined to AKShare data. Use the original header, period and value together.'}
    except Exception as exc:
        return {'status': 'original_unavailable', 'source_url': url, 'error_type': type(exc).__name__,
                'detail': 'Original read failed; normalized table units remain unknown. Not missing information; no retry made.'}
