import pytest
from scripts.engineering.retrieval_review_locators import locate_reviewed_span


def test_repeated_unit_header_cannot_silently_include_previous_statement():
    text='Income\n(In Millions) Revenue 50\nBalance sheet\n(In Millions) Cash 10\nDebt'
    with pytest.raises(ValueError,match='ambiguous'):
        locate_reviewed_span(text,'(In Millions)','Cash 10')
    lo,hi=locate_reviewed_span(text,'(In Millions)','Cash 10',
                              section_start='Balance sheet',section_end='Debt')
    assert text[lo:hi]=='(In Millions) Cash 10'


def test_ambiguous_section_or_end_is_rejected():
    with pytest.raises(ValueError,match='ambiguous'):
        locate_reviewed_span('Sheet start end Sheet start end','start','end',section_start='Sheet')
    with pytest.raises(ValueError,match='ambiguous'):
        locate_reviewed_span('start end footnote end','start','end')


def test_whitespace_offsets_and_explicit_table_boundaries_are_preserved():
    text='prefix\n[TABLE: cash]\nCash\xa010\n[/TABLE]\n[TABLE: debt]Debt 20[/TABLE]'
    a,b=locate_reviewed_span(text,'[TABLE: cash]','[/TABLE]',closing_table=True)
    assert text[a:b]=='[TABLE: cash]\nCash\xa010\n[/TABLE]'
    with pytest.raises(ValueError,match='explicit_table'):
        locate_reviewed_span(text,'Cash','[/TABLE]',closing_table=True)
