"""Restore parser inline fragments only against exact original DOM paragraphs."""
from collections import defaultdict
from hashlib import sha256
import re


def normalize(text):
    return re.sub(r'\s+', ' ', text).strip()


def restore(blocks, raw):
    from lxml import html
    try:
        raw.decode('utf-8-sig')
        tree = html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8'))
    except UnicodeDecodeError: tree = html.fromstring(raw)
    candidates = defaultdict(list)
    short_candidates = defaultdict(list)
    # Leaf paragraph containers may contain spans, links and iXBRL tags, but
    # never another paragraph/table. No nearest-neighbor semantic inference.
    for element in tree.xpath('//p|//div'):
        if element.xpath('.//p|.//div|.//table|.//ul|.//ol'):
            continue
        if element.xpath('ancestor::*[local-name()="header" or local-name()="hidden"]'):
            continue
        text = normalize(''.join(element.itertext()))
        if len(text) < 24:
            continue
        candidates[text[:24]].append((text, tree.getroottree().getpath(element)))
        short_candidates[text[0]].append((text, tree.getroottree().getpath(element)))
    output, receipts = [], []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        first = normalize(block['text'])
        possibilities = []
        if first and block['kind'] in {'text', 'heading'}:
            possibilities = candidates.get(first[:24], []) if len(first) >= 24 else short_candidates.get(first[0], [])
        proofs = []
        for original, xpath in possibilities:
            if not original.startswith(first) or original == first:
                continue
            current = first
            for end in range(i + 1, min(i + 64, len(blocks))):
                following = blocks[end]
                if following['kind'] not in {'text', 'heading'}:
                    break
                tail = normalize(following['text'])
                options = list(dict.fromkeys([normalize(current + tail), normalize(current + ' ' + tail)]))
                options = [v for v in options if original.startswith(v)]
                if len(options) != 1:
                    break
                current = options[0]
                if current == original:
                    # Ambiguous repeated containers have equal content, but no
                    # unique original location, so they remain explicitly open.
                    if sum(t == original for t, _ in possibilities) == 1:
                        proofs.append((end, original, xpath))
                    break
        # A short fragment is only a lookup hint. Accept solely a unique,
        # complete original paragraph, never a best-prefix guess.
        if len(proofs) == 1:
            end, original, xpath = proofs[0]
            receipt = {'original_xpath': xpath, 'original_normalized_sha256': sha256(original.encode()).hexdigest(),
                       'parser_block_start': i, 'parser_block_end': end + 1,
                       'native_container_ids': [b.get('native_container_id') for b in blocks[i:end+1]],
                       'basis': 'complete_exact_original_leaf_paragraph'}
            output.append({'kind': 'text', 'text': original, 'restoration': receipt})
            receipts.append(receipt); i = end + 1
        else:
            output.append({**block, 'original_parser_block': i}); i += 1
    return output, receipts
