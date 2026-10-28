"""Recognize requested evidence context, not an additional financial measure.

Unknown business nouns remain retrieval needs. In particular, units shipped,
business units, and an unqualified 'units' are not measurement instructions.
"""
import re


def assertion_request_view(query):
    """Mask a claim before an explicit evidence request, keeping source offsets.

    Only used to split independent retrieval needs. The complete claim remains
    in semantic/rerank input. Never assume its dates, labels or amounts are true.
    Without a following explicit request, retain the entire original statement.
    """
    start=re.match(r'^\s*(?:(?:a|the|this)\s+(?:summary|claim|report|note|analysis)|someone|an analyst)\s+'
        r'(?:says|states|claims|assigns|labels|asserts|treats)\b|^\s*(?:有人|摘要|总结|报告)(?:声称|称|表示|将|把)',query,re.I)
    if not start:return query,[]
    request=re.search(r'(?:[.!?。！？]\s*)(?P<request>(?:please\s+)?(?:find|retrieve|check|verify)\b|(?:请)?(?:核对|核查|验证|找出|查找))',query[start.end():],re.I)
    if not request:return query,[]
    end=start.end()+request.start('request')
    return ' '*end+query[end:],[{'start':0,'end':end,'text':query[:end],'role':'assertion_to_verify'}]


def is_assertion_context(topic,query):
    # Keep the full assertion in semantic/literal queries; it must not create
    # another must-cover need just because its clause has an unfamiliar noun.
    if not re.search(r'\b(?:find|retrieve|check|verify)\b|核对|核查|验证|找出',query,re.I):return False
    return bool(re.match(r'^(?:(?:a|the|this)\s+(?:summary|claim|report|note|analysis)|someone|an analyst)\s+'
                         r'(?:says|states|claims|assigns|labels|asserts)\b|^(?:有人|摘要|总结|报告)(?:声称|称|表示|将)',topic,re.I))


def context_requirements(text):
    from .fact_period_matching import DATE,FY
    residual=FY.sub(' ',DATE.sub(' ',text))
    found=[]
    patterns={
        'table_period_headers':r'\b(?:date|period) (?:columns?|headers?)\b|(?:两个|各个|对应)?(?:日期|期间)(?:列|表头)',
        'measurement_units':r'\b(?:stated|measurement|reporting|original|currency) units?\b|\bunits? of measurement\b|\b(?:measurement|reporting|stated) scale\b|\bthe scale(?=\s+to\s+(?:check|verify))|(?:原文)?(?:计量|货币)单位',
        'original_citations':r'\b(?:original |source )?(?:citations?|page references?)\b|原文引用|来源引用|页码',
    }
    for role,pattern in patterns.items():
        if re.search(pattern,residual,re.I):
            found.append(role);residual=re.sub(pattern,' ',residual,flags=re.I)
    if not found:return []
    residual=re.sub(r'\b(?:please|retrieve|find|show|include|provide|give|the|a|an|and|with|two|both|each|corresponding|their|its|stated|original|to|check|verify|these|claims)\b|请|找出|显示|提供|包括|及|和|与|以及|对应|各自|原文|的',' ',residual,flags=re.I)
    return found if not re.search(r'[A-Za-z\u3400-\u9fff]',residual) else []
