"""A narrow transport-quality check using DDGS's own token matching.

DDGS sorts its zero-overlap bucket last but still returns it when all engines
fail the query. Do not present that bucket as a successful research fallback.
This is not semantic relevance ranking; short/ambiguous queries are untouched.
"""
import re
from urllib.parse import unquote


def has_query_overlap(query, title, snippet, url):
    from ddgs.similarity import SimpleFilterRanker
    ranker = SimpleFilterRanker()
    query = re.sub(r'(?i)(?:^|\s)-?(?:site|filetype):\S+', ' ', query)
    tokens = {t for t in ranker._extract_tokens(query) if not t.isdecimal()}
    if len(tokens) < 2:
        return True
    return ranker._has_any_token(' '.join((title, snippet, unquote(url))), tokens)
