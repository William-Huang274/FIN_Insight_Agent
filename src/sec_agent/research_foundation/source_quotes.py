"""Source-bound quote comparison, tolerating PDF layout whitespace only."""

import re

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256


def contains_source_quote(source: str, quote: str) -> bool:
    """Match a contiguous token span without rewriting either stored text.

    Word/number boundaries, case, punctuation, units and ordering stay exact.
    PDF line breaks, table padding and spaces around punctuation may differ.
    This proves text occurrence only, never that a quote supports a claim.
    """
    if not quote.strip():
        return False
    pattern = r"\w+|[^\w\s]"
    observed = re.findall(pattern, source)
    requested = re.findall(pattern, quote)
    size = len(requested)
    return bool(size) and any(
        observed[index:index + size] == requested
        for index in range(len(observed) - size + 1)
    )



def _parsing_record(method, original, normalized, **basis):
    return {"origin": "runtime_compatibility_parse", "method": method,
            "original_input": original, "normalized_result": normalized, "basis": basis,
            "financial_semantics_verified": False}


def resolve_quote(body, quote):
    """Only restore a unique contiguous table block with identical nonempty cells.

    No number/sign/unit/word changes, fuzzy matching or skipped rows. Empty cell
    layout may change; this does NOT establish column/period comparability.
    """
    if quote and quote in body:
        return quote, None
    tokens = list(re.finditer(r'\w+|[^\w\s]',body))
    requested_tokens = re.findall(r'\w+|[^\w\s]',quote)
    matches = [i for i in range(len(tokens)-len(requested_tokens)+1) if requested_tokens and
               [t.group() for t in tokens[i:i+len(requested_tokens)]]==requested_tokens]
    if len(matches)==1:
        start = tokens[matches[0]].start()
        end = tokens[matches[0]+len(requested_tokens)-1].end()
        return body[start:end], _parsing_record('unique_layout_whitespace_v1',quote,body[start:end],
                                               source_digest=canonical_sha256(body),start=start,end=end)
    requested = quote.strip().splitlines()
    lines = body.splitlines(keepends=True)
    if not requested or not all('|' in line for line in requested):
        return quote, None
    def cells(line):
        return tuple(cell.strip() for cell in line.strip().split('|') if cell.strip())
    target = [cells(line) for line in requested]
    # Require text row labels and numeric content; never repair bare values.
    if (any(not row or not re.search(r'[^\W\d_]',row[0]) for row in target)
            or not any(re.search(r'\d',cell) for row in target for cell in row[1:])):
        return quote, None
    matches = [i for i in range(len(lines) - len(target) + 1)
               if all('|' in lines[i+j] and cells(lines[i+j]) == row for j, row in enumerate(target))]
    if len(matches) != 1:
        return quote, None
    start = sum(len(line) for line in lines[:matches[0]])
    exact = ''.join(lines[matches[0]:matches[0]+len(target)]).rstrip('\r\n')
    return exact, _parsing_record('unique_table_nonempty_cells_v1', quote, exact,
        source_digest=canonical_sha256(body), start=start, end=start+len(exact),
        notice='Original table layout restored; column meaning must still be checked against original headings.')
