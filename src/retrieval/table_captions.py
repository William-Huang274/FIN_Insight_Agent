"""Explicit standalone table captions; arbitrary prose never binds a table."""
import re

UNIT_CAPTION = re.compile(
    r'(?:amounts?\s+|figures?\s+|dollars?\s+)?(?:in\s+)?(?:USD\s+|US\$\s+|EUR\s+|GBP\s+)?'
    r'(?:thousands|millions|billions)(?:\s+of\s+(?:[A-Za-z.]+\s+){0,8}'
    r'(?:dollars|rubles|roubles|yen|yuan|renminbi|euros|pounds)(?:\s*[$€£¥])?)?'
    r'|(?:USD|EUR|GBP|US\$|\$|€|£|¥)(?:\s*(?:in\s+)?(?:thousands|millions|billions))?'
    r'|\$\s*0{3,9}|单位\s*[:：]\s*(?:千元|百万元|亿元|元)', re.I)


def _normalized(text):
    text=re.sub(r'[\u200b\ufeff()（）“”"\u2018\u2019]', ' ', text)
    text=' '.join(text.split()).strip(' ,;')
    text=re.sub(r'^(?:unaudited|audited|continued)\s*[,;]?\s*','',text,flags=re.I)
    return re.sub(r'\s*[,;]?\s*(?:unaudited|audited|continued(?: on (?:the )?next page)?)$','',text,flags=re.I).strip()


def is_unit_caption(text):
    text=_normalized(text)
    parts=re.split(r'[,;]?\s*\b(?:except|excluding)\b\s*(?:for\s+)?',text,maxsplit=1,flags=re.I)
    if len(parts)>1:
        # Exceptions describe presentation units, not arbitrary bracketed prose.
        tokens=re.findall(r'[a-z]+',parts[1].casefold())
        if not tokens or set(tokens)-{'par','value','per','share','shares','unit','units','and','or',
            'number','of','information','data','amount','amounts','dollar','dollars','stock','net','income','loss','earnings','percentages','percent'}:
            return False
    return bool(UNIT_CAPTION.fullmatch(parts[0].strip(' ,;')))


def is_table_caption(text):
    stripped=_normalized(text)
    return not stripped or is_unit_caption(stripped) or stripped.casefold() in {'continued','未经审计'}
