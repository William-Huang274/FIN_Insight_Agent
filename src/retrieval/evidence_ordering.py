"""Conservative document-role ordering, preserving every candidate identity.

This is an explicit experimental policy, not a source permission or relevance
classifier. It recognizes only SEC cover fragments at the original document
start. Risk factors, footnotes, tables and unknown fragments stay untouched.
"""
import re

POLICY = 'sec_cover_last.v1'


def is_sec_cover(row):
    original = row.get('original_source', {})
    if original.get('source_char_start') != 0:
        return False
    text = ' '.join(row.get('content', '').split())
    if not re.search(r'SECURITIES AND EXCHANGE COMMISSION', text[:400], re.I):
        return False
    if not re.search(r'\bFORM\s+(?:10-K|10-Q|8-K|20-F|40-F)\b', text[:800], re.I):
        return False
    if not all(re.search(pattern, text, re.I) for pattern in (
        r'exact name of registrant', r'Indicate by check mark',
        r'Securities registered pursuant to Section')):
        return False
    # A fragment may include both the cover and substantive material. Do not
    # move those merely because they begin on the first page.
    if re.search(r'\bItem\s+(?:1[AB]?|2|5\.02|7|8)\b|\bExplanatory Note\b|'
                 r'\bNotes to (?:the )?(?:Consolidated|Condensed)\b|'
                 r'\bConsolidated (?:Statements|Balance Sheets)\b', text, re.I):
        return False
    return True


def order_evidence(query, candidates):
    # These questions can legitimately be answered by the cover. An uncertain
    # query remains undemoted rather than removing a possible answer.
    requests_cover = bool(re.search(
        r'\b(?:cover|registrant|ticker|trading symbol|commission file|registered office|'
        r'principal executive|mailing address|telephone|accelerated filer|emerging growth|'
        r'stock exchange|par value|incorporat(?:ed|ion))\b|封面|交易代码|股票代码|'
        r'注册地|注册地址|总部地址|联系电话|上市交易所|加速申报|新兴成长', query, re.I))
    deferred = [] if requests_cover else [row['node_id'] for row in candidates if is_sec_cover(row)]
    deferred_set = set(deferred)
    ordered = [row for row in candidates if row['node_id'] not in deferred_set]
    ordered.extend(row for row in candidates if row['node_id'] in deferred_set)
    return ordered, {'policy': POLICY, 'cover_question': requests_cover,
                     'deferred_node_ids': deferred, 'dropped_candidates': 0}
