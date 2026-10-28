"""Explicit standalone table captions; arbitrary prose never binds a table."""
import re

UNIT_CAPTION = re.compile(
    r'(?:amounts?\s+|figures?\s+|dollars?\s+)?(?:in\s+)?(?:USD\s+|US\$\s+|EUR\s+|GBP\s+)?'
    r'(?:thousands|millions|billions)(?:\s+of\s+(?:dollars|USD|EUR|GBP))?'
    r'(?:\s*[,;]\s*(?:except|excluding)\s+(?:per[- ]share|share(?:\s+and\s+per[- ]share)?)\s+(?:amounts|data))?'
    r'|(?:USD|EUR|GBP|US\$)\s*(?:in\s+)?(?:thousands|millions|billions)?'
    r'|单位\s*[:：]\s*(?:千元|百万元|亿元|元)', re.I)


def is_unit_caption(text):
    return bool(UNIT_CAPTION.fullmatch(text.strip().strip('()（）').strip()))


def is_table_caption(text):
    stripped=text.strip().strip('()（）').strip()
    return not stripped or is_unit_caption(stripped) or stripped.casefold() in {'unaudited','audited','未经审计'}
