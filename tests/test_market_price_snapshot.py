import sqlite3
import pytest
from scripts.data_retrieval.materialize_market_price_snapshot import materialize, price_rows


def body(close='12.00', day='Sep 10, 2026'):
    headers=['Date','Open','High','Low','Close','Adj. Close','Change','Volume']
    cells=[day,'11.00','13.00','10.00',close,'6.00','9.09%','1,200']
    return ('<table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody><tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr></tbody></table>').encode()


ARGS={'ticker':'MU','source_url':'https://stockanalysis.com/stocks/mu/history/','captured_at':'2026-09-11T10:00:00Z'}


def test_original_and_adjusted_prices_have_distinct_columns_and_exact_lineage(tmp_path):
    p=tmp_path/'market.sqlite';assert materialize(body(),p,**ARGS)==1
    with sqlite3.connect(p) as db:
        row=db.execute('select close_decimal,adjusted_close_decimal,volume,trade_date,locator from market_prices').fetchone()
    assert row[:4]==('12.00','6.00',1200,'2026-09-10')
    assert 'Sep 10, 2026' in row[4]
    with pytest.raises(FileExistsError):materialize(body(),p,**ARGS)


@pytest.mark.parametrize('payload',[body('99.00'),body(day='Sep 11, 2026'),b'<html>No data</html>'])
def test_bad_or_incomplete_market_data_is_rejected(payload):
    with pytest.raises(ValueError):price_rows(payload,**ARGS)
