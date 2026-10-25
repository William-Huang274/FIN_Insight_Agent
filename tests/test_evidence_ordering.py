from retrieval.evidence_ordering import is_sec_cover, order_evidence


def cover():
    return {'node_id':'cover', 'original_source':{'source_char_start':0},
            'content':'SECURITIES AND EXCHANGE COMMISSION\nFORM\n10-K\n'
            '(Exact name of registrant)\nSecurities registered pursuant to Section 12(b)\n'
            'Indicate by check mark whether the registrant has filed reports.'}


def test_cover_deferred_without_deleting_or_rewriting_candidates():
    first=cover(); business={'node_id':'business','content':'capital expenditure increased'}
    risk={'node_id':'risk','content':'Risk factors: trade restrictions could affect sales.'}
    rows, receipt=order_evidence('What caused capital expenditures to increase?', [first,business,risk])
    assert rows == [business,risk,first]
    assert rows[2] is first and receipt['dropped_candidates']==0
    assert receipt['deferred_node_ids']==['cover']


def test_cover_questions_and_mixed_body_are_preserved():
    first=cover(); other={'node_id':'other','content':'other'}
    for query in ('What is the trading symbol?', '公司的股票代码是什么？', 'Where was it incorporated?'):
        assert order_evidence(query,[first,other])[0] == [first,other]
    first['content'] += '\nItem 1. Business\nOur new product generated sales.'
    assert not is_sec_cover(first)


def test_unknown_offsets_and_quoted_cover_text_are_not_deferred():
    row=cover(); row['original_source']['source_char_start']=5000
    assert not is_sec_cover(row)
    row.pop('original_source')
    assert not is_sec_cover(row)
    assert order_evidence('Annual report operating cash flow', [row])[1]['deferred_node_ids']==[]
