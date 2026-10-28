"""Query-local polarity and clause spans, without changing the original query.

Only explicit exclusion syntax is masked for positive constraint extraction.
Questions about exclusions remain questions; no source or answer IDs enter here.
Unknown syntax stays available in the unchanged literal/semantic query.
"""
import re


EXCLUSION = re.compile(
    r'\b(?:rather\s+than|instead\s+of|excluding|except(?:\s+for)?|without)\b'
    r'|\bnot\b(?!\s+(?:only|just|necessarily|sure|known)\b)'
    r'|而不是|而非|并非|不是|不要|不包括|不包含|排除(?!了?多少)', re.I)
BOUNDARY = re.compile(r'[,;!?，；。！？]|\bbut\b|\binstead\b|而是|但是|但要', re.I)


def positive_view(query):
    """Return same-length text plus explicit exclusions for audit, not rewriting."""
    excluded = []
    for match in EXCLUSION.finditer(query):
        if any(lo <= match.start() < hi for lo, hi in excluded):
            continue
        # "Does not include ...?" asks whether a claim is true. It does not
        # authorize excluding its evidence from recall.
        prefix = query[max(0, match.start()-48):match.start()]
        clause_prefix = re.split(r'[.;!?。；！？]', query[:match.start()])[-1].strip()
        if (re.search(r'\b(?:does|did|is|are|was|were|can|could|would)\s*$', prefix, re.I)
                or re.match(r'^(?:does|do|did|is|are|was|were|has|have|had|can|could|would)\b', clause_prefix, re.I)
                or re.search(r'是否|有无|多少', prefix)):
            continue
        end = BOUNDARY.search(query, match.end())
        excluded.append((match.start(), end.start() if end else len(query)))
    text = list(query)
    for lo, hi in excluded:
        text[lo:hi] = ' ' * (hi-lo)
    return ''.join(text), [dict(start=lo, end=hi, text=query[lo:hi], role='excluded_requirement')
                           for lo, hi in excluded]


def owner_clauses(query, mentions):
    """Retain owner-specific literal clauses even when their concepts are unknown.

    In "Alpha and Beta cash" the topic is shared. In "Alpha cash and Beta
    widgets" each owner has an explicit topic, even if widgets is not in a
    financial glossary. Do not spread Alpha's recognized topic to Beta.
    """
    unique = {}
    for mention in mentions:
        key = mention['start'], mention['end'], tuple(mention['issuer_ids'])
        unique[key] = mention
    spans = sorted(unique.values(), key=lambda m:(m['start'], m['end']))
    clauses = {}
    for i, mention in enumerate(spans):
        if len(mention['issuer_ids']) != 1:
            continue
        end = spans[i+1]['start'] if i+1 < len(spans) else len(query)
        text = query[mention['end']:end]
        meaningful = re.sub(r"(?:['’]s)|\b(?:and|or|with|versus|vs|compare|comparison|the|of)\b|[\s,;:.，；：、的和与及]", '', text, flags=re.I)
        if meaningful:
            clauses.setdefault(mention['issuer_ids'][0], []).append(text.strip())
    return clauses
