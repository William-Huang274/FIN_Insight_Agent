"""Literal reading context around selected quotes, with explicit continuation."""
import re

from .evidence_resolution import resolve_quote
from .research_graph_contracts import canonical_sha256


def reading_windows(artifacts, source_id, quotes, *, max_characters=6000):
    source = artifacts.source_item(source_id)
    text = artifacts._source_text(source)
    if not text:
        return {'windows': [], 'notice': '归档正文为空，请按来源定位检查获取情况。'}
    spans, missing = [], []
    for quote in quotes or ['']:
        exact, _ = resolve_quote(text, quote) if quote else ('', None)
        start = text.find(exact) if exact else 0
        if start < 0:
            missing.append(quote)
            continue
        stop = start + len(exact)
        if len(text) <= max_characters:
            spans.append((0, len(text), False))
            continue
        # Include explanatory context on both sides, then expand to paragraph
        # boundaries. In long PDF/table blocks the cap is labelled, not hidden.
        left = max(0, start - 450)
        prior = list(re.finditer(r'\n\s*\n', text[:left]))
        left = prior[-1].end() if prior else 0
        right = min(len(text), stop + 1000)
        after = re.search(r'\n\s*\n', text[right:])
        right = right + after.start() if after else len(text)
        clipped = right - left > max_characters
        if clipped:
            left = max(left, start - 450)
            right = min(right, left + max_characters)
        spans.append((left, right, clipped))
    merged = []
    for left, right, clipped in sorted(set(spans)):
        if merged and left <= merged[-1][1] and right - merged[-1][0] <= max_characters:
            a, b, flag = merged.pop()
            merged.append((a, max(b, right), flag or clipped))
        else:
            merged.append((left, right, clipped))
    windows = [{'text': text[left:right], 'offset': left, 'end_offset': right,
        'context_truncated': clipped, 'source_capture_characters': len(text),
        'read_more': {'tool': 'read_current_source', 'arguments': {
            'source_id': source_id, 'offset': max(0, right - 200), 'max_characters': 6000}}
            if right < len(text) else None}
        for left, right, clipped in merged]
    return {'windows': windows, 'source_text_sha256': canonical_sha256(text),
        **({'unlocated_quotes': missing, 'notice': '这些旧引文未在归档正文中定位；不可视为已核对，请按来源回读。'} if missing else {}),
        'coverage_notice': '这是相关归档句段，不代表完整文件覆盖；表格跨页或上下文截断时继续回读。'}
