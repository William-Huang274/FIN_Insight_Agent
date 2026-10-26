from hashlib import sha256
import pytest
from scripts.engineering.rerank_passage_windows import paired_windows


def candidate(text):
    return {'node_id':'original','content':text,'content_sha256':sha256(text.encode()).hexdigest(),
            'embedding_context':'Company / period','embedding_input_sha256':'original vector identity'}


@pytest.mark.parametrize('text',[' \n'+('A statement.\n'*80)+' \n','无空格的中文文本'*100,'x'*1500])
def test_every_original_character_survives_with_exact_offsets(text):
    row=candidate(text);views,spans=paired_windows([row],size=200)
    assert views[0]==row
    assert ''.join(v['content'] for v in views[1:])==text
    for view,span in zip(views,spans):
        assert view['content']==text[span['start']:span['end']]
        assert view['content_sha256']==span['sha256']
        assert view['embedding_context']==row['embedding_context']
        if not span['whole']:assert 'embedding_input_sha256' not in view


def test_short_passage_not_duplicated_and_original_mismatch_rejected():
    row=candidate('A self-contained short passage.')
    views,spans=paired_windows([row])
    assert views==[row] and len(spans)==1
    row['content']='changed'
    with pytest.raises(ValueError,match='digest_mismatch'):paired_windows([row])
