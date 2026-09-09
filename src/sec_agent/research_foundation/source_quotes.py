"""Source-bound quote comparison, tolerating PDF layout whitespace only."""

import re


def contains_source_quote(source: str, quote: str) -> bool:
    """Match a contiguous token span without rewriting either stored text.

    Word/number boundaries, case, punctuation, units and ordering stay exact.
    PDF line breaks, table padding and spaces around punctuation may differ.
    This proves text occurrence only, never that a quote supports a claim.
    """
    if not quote.strip():
        return False
    if quote in source:
        return True
    pattern = r"\w+|[^\w\s]"
    observed = re.findall(pattern, source)
    requested = re.findall(pattern, quote)
    size = len(requested)
    return bool(size) and any(
        observed[index:index + size] == requested
        for index in range(len(observed) - size + 1)
    )
