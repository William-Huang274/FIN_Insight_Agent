"""Explicit announcement subject in a query; no issuer/date/answer rules."""
import re
from .query_requirements import positive_view


def event_requirements(query):
    text,_=positive_view(query)
    release=bool(re.search(r'新闻稿|\bpress release\b',text,re.I))
    earnings=bool(re.search(r'业绩(?:发布|公告)|财报发布|\bearnings (?:release|announcement|8-k)\b',text,re.I))
    financing=bool(re.search(r'融资(?:发布|公告)|\bfinancing (?:release|announcement)\b',text,re.I))
    if release:
        earnings |= bool(re.search(r'业绩|财报季度|财务结果|\b(?:earnings|financial results|financial quarter|reporting quarter)\b',text,re.I))
        financing |= bool(re.search(r'融资|\b(?:financing|credit facility|notes? offering|bond issuance)\b',text,re.I))
    if earnings==financing:return []
    return ['earnings_release' if earnings else 'financing']
