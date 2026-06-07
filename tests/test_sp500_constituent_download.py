from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "download_sp500_constituents.py"
SPEC = importlib.util.spec_from_file_location("download_sp500_constituents", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
parse_sp500_constituents_html = MODULE.parse_sp500_constituents_html


def test_parse_sp500_constituents_html_normalizes_symbols_and_cik() -> None:
    html = """
    <table id="constituents">
      <tr>
        <th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th><th>Headquarters Location</th><th>Date added</th><th>CIK</th><th>Founded</th>
      </tr>
      <tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td><td>Multi-Sector Holdings</td><td>Omaha, Nebraska</td><td>2010-02-16</td><td>106798</td><td>1839</td></tr>
      <tr><td>MSFT</td><td>Microsoft</td><td>Information Technology</td><td>Systems Software</td><td>Redmond, Washington</td><td>1994-06-01</td><td>0000789019</td><td>1975</td></tr>
    </table>
    """

    rows = parse_sp500_constituents_html(html, source_url="https://example.test", downloaded_at_utc="2026-06-05T00:00:00+00:00")

    assert rows[0]["ticker"] == "BRK-B"
    assert rows[0]["raw_symbol"] == "BRK.B"
    assert rows[0]["cik"] == "0000106798"
    assert rows[1]["ticker"] == "MSFT"
    assert rows[1]["sector"] == "Information Technology"
