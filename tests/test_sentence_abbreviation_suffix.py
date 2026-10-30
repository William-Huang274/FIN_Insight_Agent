import random
import re
from retrieval.object_view_compiler_v2 import (
    _period_is_nonterminal_abbreviation as current,
    _COMMON_NONTERMINAL_ABBREVIATIONS as ABBREVIATIONS,
    _abbreviation_aware_sentence_spans as spans,
)


def old(text,index):
    prefix=text[:index+1]
    if re.search(r'([A-Za-z](?:\.[A-Za-z])+\.)$',prefix):return True
    word=re.search(r'([A-Za-z]+(?:\.[A-Za-z]+)*)\.$',prefix)
    return bool(word is not None and word.group(1).casefold() in ABBREVIATIONS)


def test_suffix_preserves_previous_matching_semantics():
    rng=random.Random(27)
    cases=['U.S.','Mr.','INC.','abc.U.S.','1.2.','A'*1500+'.','A.'*300,'中文Inc.','??..St.']
    cases += [''.join(rng.choice('abCD.iNcu012. 中文-\n') for _ in range(rng.randrange(1,240)))+'.' for _ in range(300)]
    for token in cases:
        text='Prior text. More background. '+token
        assert current(text,len(text)-1)==old(text,len(text)-1)


def test_long_flattened_document_keeps_every_sentence():
    sentence='The reported total is unchanged. '
    text=sentence*20000
    result=spans(text)
    assert len(result)==20001  # Final whitespace is retained separately.
    assert ''.join(text[a:b] for a,b in result)==text
    assert result[0]==(0,len(sentence)-1)
