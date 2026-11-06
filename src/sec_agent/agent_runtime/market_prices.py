"""Timestamped public intraday observations; no trading or causal attribution."""
import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Literal
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from langchain_core.tools import tool, ToolException

from .conversation_agent import GrantedTool
from sec_agent.research_foundation.external_sources import ExternalSourceError
from sec_agent.research_foundation.public_posts import public_json


INTERVALS = {'1m': 60, '5m': 300, '15m': 900, '60m': 3600}


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('time_requires_explicit_timezone; e.g. 2026-01-05T09:30:00-05:00')
    return result.astimezone(timezone.utc)


def task_cutoff(value):
    if not value:
        return None
    stamp = instant(value if 'T' in value else value + 'T00:00:00Z')
    # Existing research contracts use midnight UTC for an inclusive research day.
    return stamp + timedelta(days=1) if stamp.time() == datetime.min.time() else stamp


def market_snapshot(payload, *, symbol, start, end, interval, captured_at, source_url):
    chart = payload.get('chart') or {}
    if chart.get('error') or not chart.get('result'):
        raise ExternalSourceError('market_provider_no_series; requested range may exceed intraday retention')
    result = chart['result'][0]
    meta = result.get('meta') or {}
    if meta.get('symbol', '').upper() != symbol:
        raise ExternalSourceError('market_symbol_mismatch')
    tz_name = meta.get('exchangeTimezoneName')
    if not tz_name or not meta.get('currency') or meta.get('dataGranularity') != interval:
        raise ExternalSourceError('market_identity_or_interval_missing')
    zone = ZoneInfo(tz_name)
    values = ((result.get('indicators') or {}).get('quote') or [{}])[0]
    periods = meta.get('tradingPeriods') or {}
    def session(stamp):
        for name, groups in periods.items() if isinstance(periods, dict) else []:
            for group in groups:
                for p in group if isinstance(group, list) else [group]:
                    if isinstance(p, dict) and p.get('start', math.inf) <= stamp < p.get('end', -math.inf):
                        return name
        return 'unknown_from_provider'
    bars, excluded, missing = [], 0, 0
    for i, raw in enumerate(result.get('timestamp') or []):
        stamp = datetime.fromtimestamp(raw, timezone.utc)
        bar_end = stamp + timedelta(seconds=INTERVALS[interval])
        if stamp < start or bar_end > min(end, captured_at):
            excluded += 1
            continue
        row = {}
        for field in ('open', 'high', 'low', 'close', 'volume'):
            series = values.get(field) or []
            v = series[i] if i < len(series) else None
            row[field] = v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None
        if any(row[k] is None for k in ('open', 'high', 'low', 'close')):
            missing += 1
            continue
        bars.append(dict(start_utc=stamp.isoformat(), end_utc=bar_end.isoformat(),
                         exchange_time=stamp.astimezone(zone).isoformat(), session=session(raw), **row))
    bars.sort(key=lambda r: r['start_utc'])
    if len({b['start_utc'] for b in bars}) != len(bars):
        raise ExternalSourceError('market_duplicate_bar_time')
    return dict(symbol=symbol, currency=meta['currency'], exchange=meta.get('exchangeName'),
        instrument_type=meta.get('instrumentType'), exchange_timezone=tz_name, interval=interval,
        requested_start=start.isoformat(), requested_end=end.isoformat(), captured_at=captured_at.isoformat(),
        source_url=source_url, provider='yahoo_finance_chart_unofficial',
        price_basis='provider_OHLC; no local adjustment or repair; not certified as-traded archival data',
        realtime_status='not_guaranteed', delay_seconds=None,
        availability='current_provider_response_for_historical_interval; not an as-of-vintage archive',
        excluded_partial_or_outside_window=excluded, missing_price_bars=missing, bars=bars)


def market_price_tool(*, thread_id, cache_root, research_as_of=None, transport=public_json, clock=None):
    from uuid import UUID
    thread_id = str(UUID(thread_id))
    root = Path(cache_root) / thread_id
    cutoff = task_cutoff(research_as_of)
    now = clock or (lambda: datetime.now(timezone.utc))

    @tool(response_format='content_and_artifact')
    async def read_market_prices(symbol: str, start: str, end: str,
            interval: Literal['1m', '5m', '15m', '60m'] = '5m',
            include_extended_hours: bool = False, offset: int = 0, limit: int = 100):
        """Read intraday OHLCV for one explicit Yahoo symbol (e.g. SPY or ^GSPC).
        start/end are timezone-aware ISO timestamps; end is exclusive and must be
        no later than both the research deadline and the current elapsed time.
        Do not request the close of a trading day that has not ended. Only complete
        bars before the task cutoff are returned. 1m supports up to 7 days; other
        intervals up to 60 days per request, subject to provider retention. Page via
        offset/limit (1..200); the exact request reuses its captured snapshot.
        Data delay is unverified: this is not a guaranteed real-time consolidated
        tape. Currency, time zone, sessions and basis accompany each source. ETFs
        are not their benchmark indices. For news timing and policy transmission,
        get_research_method(method_id='event_policy') provides optional methods.
        Use calculate_research_metric for returns with the returned passage_id and
        exact row quotations; retrieved prices alone do not attribute a move to news.
        """
        try:
            ticker = symbol.strip().upper()
            if not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=\-]{0,24}', ticker):
                raise ValueError('invalid_symbol; pass a ticker, not a company name or URL')
            left, right = instant(start), instant(end)
            if interval not in INTERVALS or not 1 <= limit <= 200 or offset < 0:
                raise ValueError('invalid_interval_or_page; limit=1..200, offset>=0')
            if not left < right or right-left > timedelta(days=7 if interval == '1m' else 60):
                raise ValueError('invalid_market_window; use <=7 days for 1m, <=60 days otherwise')
            current = now()
            latest = min(current, cutoff) if cutoff else current
            if right > latest:
                code = ('market_window_after_task_cutoff' if cutoff and right > cutoff
                        else 'market_window_in_future')
                detail = dict(code=code, requested_start_utc=left.isoformat(),
                    requested_end_utc=right.isoformat(), current_time_utc=current.isoformat(),
                    configured_task_cutoff_utc=cutoff.isoformat() if cutoff else None,
                    latest_allowed_end_utc=latest.isoformat(), request_dispatched=False,
                    request_modified=False,
                    next_action='Choose timezone-aware start < end <= latest_allowed_end_utc; '
                        'also respect any earlier deadline in the research question. '
                        'This upper bound does not choose the intended trading session.')
                raise ValueError(json.dumps(detail, ensure_ascii=False))
            request = dict(symbol=ticker, start=left.isoformat(), end=right.isoformat(),
                           interval=interval, include_extended_hours=include_extended_hours)
            key = sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            path = root / (key + '.json')
            def capture_once():
                from filelock import FileLock
                root.mkdir(parents=True, exist_ok=True)
                with FileLock(str(path) + '.lock', timeout=30):
                    if path.exists():
                        saved = json.loads(path.read_text(encoding='utf8'))
                        if saved['request'] != request:
                            raise ValueError('market_snapshot_request_mismatch')
                        return saved['snapshot']
                    url = 'https://query1.finance.yahoo.com/v8/finance/chart/' + quote(ticker, safe='')
                    params = dict(period1=int(left.timestamp()), period2=int(right.timestamp()), interval=interval,
                                  includePrePost=str(include_extended_hours).lower())
                    payload = transport(url, params, 15)
                    captured = market_snapshot(payload, symbol=ticker, start=left, end=right, interval=interval,
                                               captured_at=now(), source_url=url + '?' + urlencode(params))
                    temp = path.with_suffix('.tmp')
                    temp.write_text(json.dumps({'request':request, 'snapshot':captured}, ensure_ascii=False), encoding='utf8')
                    temp.replace(path)
                    return captured
            snapshot = await asyncio.to_thread(capture_once)
            metadata = {k:v for k,v in snapshot.items() if k != 'bars'}
            page = snapshot['bars'][offset:offset+limit]
            text = json.dumps(metadata, ensure_ascii=False, sort_keys=True) + '\n' + '\n'.join(json.dumps(row, sort_keys=True) for row in page)
            digest = sha256(text.encode()).hexdigest()
            doc = 'WEB::MARKET::' + digest
            sid = f'PASSAGE::{doc}::0::{digest[:16]}'
            item = dict(result_state='source_bound_passage', passage_id=sid, passage=text, document_id=doc,
                content_sha256=digest, source_url=snapshot['source_url'], title=f'{ticker} {interval} observed prices',
                source_role='external_public_source_unverified', source_kind='market_observations',
                source_read_method='yahoo_chart_snapshot', writer_citable=True, numeric_fact_authority=False,
                source_locator=dict(source_url=snapshot['source_url'], captured_at=snapshot['captured_at'],
                    document_id=doc, content_sha256=digest, character_start=0, character_end=len(text),
                    capture_receipt_digest=sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
                    request=request, offset=offset, limit=limit),
                readback={'tool':'read_market_prices', 'arguments':dict(symbol=ticker, start=start, end=end,
                    interval=interval, include_extended_hours=include_extended_hours, offset=offset, limit=limit)})
            body = dict(operation='read', items=[item] if page else [], total_matches=len(snapshot['bars']),
                next_offset=offset+len(page) if offset+len(page)<len(snapshot['bars']) else None,
                market_metadata=metadata, evidence_admission_performed=False,
                notice='No price interpolation, causal attribution or complete-session guarantee. Empty observations do not establish no trading.')
            return json.dumps(body, ensure_ascii=False), body
        except (ValueError, ExternalSourceError) as exc:
            raise ToolException('行情读取未完成：' + str(exc)) from exc
    read_market_prices.handle_tool_error = True
    return GrantedTool(read_market_prices, 'read', '公开盘中行情及准确时点；非实时全市场报价保证')
