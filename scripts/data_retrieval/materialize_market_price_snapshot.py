"""Normalize a captured Stock Analysis daily table into an immutable SQLite file.

The original HTML remains the authority. Prices are vendor observations, not
issuer financial facts or forecasts. No network request and no model call.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import sqlite3

from bs4 import BeautifulSoup


def price_rows(body, *, ticker, source_url, captured_at):
    soup = BeautifulSoup(body, 'lxml')
    header = ['Date', 'Open', 'High', 'Low', 'Close', 'Adj. Close', 'Change', 'Volume']
    tables = [t for t in soup.find_all('table') if [c.get_text(' ', strip=True) for c in t.select('thead th')] == header]
    if len(tables) != 1:
        raise ValueError('daily_price_table_schema_changed')
    digest = sha256(body).hexdigest()
    rows, dates = [], set()
    for index, tr in enumerate(tables[0].select('tbody tr')):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all('td')]
        if len(cells) != 8:
            raise ValueError('daily_price_row_shape_changed')
        day = datetime.strptime(cells[0], '%b %d, %Y').date().isoformat()
        if day >= captured_at[:10] or day in dates:
            raise ValueError('daily_price_incomplete_or_duplicate_session')
        prices = [Decimal(x.replace(',', '')) for x in cells[1:6]]
        op, high, low, close, adjusted = prices
        if not all(p.is_finite() and p > 0 for p in prices) or not low <= min(op,close) <= max(op,close) <= high:
            raise ValueError('daily_price_ohlc_invalid')
        volume = int(cells[7].replace(',', ''))
        if volume < 0:
            raise ValueError('daily_price_volume_invalid')
        rows.append((ticker, day, *map(str, prices), volume, 'USD', 'America/New_York',
                     source_url, digest, captured_at, f'HTML daily history table / row {index+1} / {cells[0]}'))
        dates.add(day)
    if not rows:
        raise ValueError('daily_price_table_empty')
    return rows


def materialize(body, output, *, ticker, source_url, captured_at):
    rows = price_rows(body, ticker=ticker, source_url=source_url, captured_at=captured_at)
    output = Path(output)
    with output.open('xb'):
        pass
    with sqlite3.connect(output) as db:
        db.execute('''CREATE TABLE market_prices (
            ticker TEXT NOT NULL, trade_date TEXT NOT NULL, open_decimal TEXT NOT NULL,
            high_decimal TEXT NOT NULL, low_decimal TEXT NOT NULL, close_decimal TEXT NOT NULL,
            adjusted_close_decimal TEXT NOT NULL, volume INTEGER NOT NULL,
            currency TEXT NOT NULL, exchange_timezone TEXT NOT NULL, source_url TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, captured_at TEXT NOT NULL, locator TEXT NOT NULL,
            PRIMARY KEY(ticker,trade_date,source_sha256))''')
        db.executemany('INSERT INTO market_prices VALUES('+','.join('?' for _ in range(14))+')', rows)
    return len(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--html',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ticker',required=True);p.add_argument('--source-url',required=True)
    a=p.parse_args()
    print(materialize(a.html.read_bytes(),a.output,ticker=a.ticker,source_url=a.source_url,
                      captured_at=datetime.now(timezone.utc).isoformat()))


if __name__=='__main__':main()
