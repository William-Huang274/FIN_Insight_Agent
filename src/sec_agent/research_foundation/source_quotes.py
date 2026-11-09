"""Source-bound quote comparison, tolerating PDF layout whitespace only."""

from difflib import SequenceMatcher
import re

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256


def _prose_spans(line, quote, literal):
    """Locate a short excerpt around the submitted literal without searching other sources."""
    if quote.count(literal) != 1:
        return [(0, len(line))]
    anchor = quote.index(literal)
    spans = set()
    for occurrence in re.finditer(re.escape(literal), line):
        estimate = occurrence.start() - anchor
        lo = max(0, estimate-4)
        hi = min(len(line), estimate+len(quote)+4)
        if hi-lo < len(quote)-4:
            continue
        blocks = SequenceMatcher(None, quote, line[lo:hi], autojunk=False).get_matching_blocks()[:-1]
        if not blocks:
            continue
        first, last = blocks[0], blocks[-1]
        start = max(0, lo+first.b-first.a)
        end = min(len(line), lo+last.b+len(quote)-last.a)
        if start <= occurrence.start() and occurrence.end() <= end:
            spans.add((start,end))
    return sorted(spans)


def quote_comparison(body, quote, literal):
    """Advisory text from this passage only. Never substitute a candidate into an operand."""
    quote = (quote or '').strip()
    if not literal or not 8 <= len(quote) <= 512 or len(quote.splitlines()) != 1:
        return None
    candidates = []
    pipe_count = quote.count('|') if quote.startswith('|') and quote.endswith('|') else 0
    lines = body.splitlines()
    headers = []
    for number, line in enumerate(lines):
        if not line.lstrip().startswith('|'):
            headers = []
        elif re.fullmatch(r'[|:\s-]+', line) and '---' in line:
            headers = [s for s in lines[max(0, number-2):number] if s.lstrip().startswith('|') and len(s) <= 512]
            if number+1 < len(lines) and re.match(r'^\s*\|\s*\|', lines[number+1]) and len(lines[number+1]) <= 512:
                headers.append(lines[number+1])
        if literal not in line or len(line) > 1024:
            continue
        pipes = [i for i, ch in enumerate(line) if ch == '|']
        spans = (zip(pipes, (i+1 for i in pipes[pipe_count-1:])) if pipe_count >= 2
                 else _prose_spans(line, quote, literal))
        for start, end in spans:
            exact = line[start:end]
            if literal not in exact or abs(len(exact)-len(quote)) > 4:
                continue
            matcher = SequenceMatcher(None, quote, exact, autojunk=False)
            if matcher.ratio() < 0.9:
                continue
            changes = [{'submitted':quote[i:j], 'source':exact[k:l], 'at':i}
                       for tag,i,j,k,l in matcher.get_opcodes() if tag != 'equal']
            if not changes or sum(max(len(c['submitted']),len(c['source'])) for c in changes) > 4:
                continue
            candidates.append({'passage_line':number+1, 'column_offset':start, 'original_line':line,
                               'aligned_text':exact, 'differences':changes, 'table_headings':headers})
    if candidates:
        return {'candidate_count':len(candidates),'candidates':candidates[:3],
                'status':'author_selection_required', 'applied':False}
    return None


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


def literal_contexts(body, literal):
    """All bounded exact-number neighborhoods, never an automatic operand repair."""
    if not literal:
        return []
    matches = list(re.finditer(r'(?<![\w.,])' + re.escape(literal) + r'(?![\w]|[.,]\d)', body))
    return [{'start': max(0, m.start()-700), 'end': min(len(body), m.end()+350),
             'text': body[max(0, m.start()-700):min(len(body), m.end()+350)],
             'total_matches': len(matches), 'selection_required': True} for m in matches[:8]]


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
