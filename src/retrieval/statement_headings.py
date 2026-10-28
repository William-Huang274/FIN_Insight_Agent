"""Explicit statement titles embedded in original table header rows."""
import re


def statement_kind(title):
    value=' '.join(re.sub(r'[\u200b\ufeff]',' ',title).split())
    value=re.sub(r'\((?:unaudited|audited|continued)\)','',value,flags=re.I).strip(' :—–-*')
    value=re.sub(r'^(?:condensed\s+)?(?:(?:consolidated|combined)(?:\s+and\s+(?:consolidated|combined))?\s+)?','',value,flags=re.I)
    patterns={'balance_sheet':r'(?:balance sheets?|statements? of financial position)',
        'cash_flow':r'statements? of cash flows?',
        'income_statement':r'(?:income statements?|statements? of (?:income|operations|earnings|comprehensive (?:income|loss)))',
        'equity_statement':r'statements? of (?:changes in )?(?:(?:stockholders|shareholders|partners)[\x27’]?\s+)?(?:equity|capital)'}
    return next((kind for kind,pattern in patterns.items() if re.fullmatch(pattern,value,re.I)),None)


def embedded_statement_regions(text,tables):
    result=[]
    for start,end in tables:
        # A title must be a single populated cell before numeric data. Do not
        # classify from a paragraph mentioning a statement or a later row label.
        lines=text[start:end].splitlines()[1:]
        for line in lines[:8]:
            cells=[re.sub(r'[\u200b\ufeff]','',c).strip() for c in line.split('|')]
            cells=[c for c in cells if c]
            if not cells:continue
            if any(re.search(r'\d',c) for c in cells):break
            if len(cells)!=1:continue
            title=cells[0];kind=statement_kind(title)
            if kind:
                attrs={'statement_type':kind,'statement_role':'primary'}
                if re.search(r'\bconsolidated\b',title,re.I):attrs['consolidation']='consolidated'
                result.append((start,end,attrs,'explicit_statement_title_in_original_table_header'))
                break
    return result
