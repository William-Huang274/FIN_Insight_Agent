"""Distinguish known HTTP-200 access interstitials from missing metadata."""
from bs4 import BeautifulSoup

from .external_sources import ExternalSourceError


def check_access_challenge(html):
    markers = ('EO_Bot_Ssid', '__tst_status', '/cdn-cgi/challenge-platform/', 'cf-chl-')
    if not any(marker in html for marker in markers):
        return
    soup = BeautifulSoup(html, 'html.parser')
    # Challenge snippets quoted in real articles must remain readable.
    for tag in soup.select('script,style,noscript'):
        tag.decompose()
    if len(soup.get_text(' ', strip=True)) < 240 and not soup.select('article,main p'):
        raise ExternalSourceError('capture_access_challenge')
