from scripts.engineering.qualify_unit_rerank import publication_rows


def test_compact_release_guard_rejects_any_partially_published_document():
    records=[{'node_id':'a1','document_id':'a'}, {'node_id':'a2','document_id':'a'},
             {'node_id':'b1','document_id':'b'}, {'node_id':'c1','document_id':'c'}]
    allowed={'a1','b1'}
    retained,incomplete=publication_rows(records,allowed)
    assert retained==[records[0],records[2]]
    assert incomplete=={'a','c'}
    for selected in [set(),{'a'},{'b'},{'c'},{'a','b'},{'b','c'},{'a','b','c'}]:
        previous={r['node_id'] for r in records if r['document_id'] in selected}-allowed
        assert bool(previous)==bool(selected&incomplete)
