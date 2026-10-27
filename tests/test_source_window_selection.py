from retrieval.source_window_candidates import POLICY
from retrieval.source_window_selection import select_context_companions
import pytest


def rows(count=30):
    return [{'node_id':str(i),'parent_document_id':'doc','score':1/(i+1)} for i in range(count)]


def proof(links):
    return {'policy':POLICY,'links':[{'seed':a,'neighbor':b} for a,b in links]}


def test_core_keeps_order_and_all_eight_nodes_with_many_neighbor_links():
    original=rows()
    links=[(str(i),str(20+i)) for i in range(6)]
    result,receipt=select_context_companions(original,proof(links))
    ids=[r['node_id'] for r in result]
    assert ids[:10]==['0','20','1','21','2','3','4','5','6','7']
    assert [n for n in ids if int(n)<8]==[str(i) for i in range(8)]
    assert len(receipt['promotions'])==2 and len(ids)==len(set(ids))==30
    assert all(next(r for r in result if r['node_id']==old['node_id']) is old for old in original)


def test_choose_best_neighbor_without_replacing_a_core_neighbor_with_a_weaker_one():
    original=rows()
    result,receipt=select_context_companions(original,proof([('0','29'),('0','10'),('2','25'),('2','3')]))
    assert [r['node_id'] for r in result[:5]]==['0','10','1','2','3']
    assert receipt['promotions']==[{'anchor':'0','companion':'10'}]


def test_small_population_stays_unchanged_and_tail_anchors_cannot_displace_core():
    original=rows(5)
    result,receipt=select_context_companions(original,proof([('0','4')]))
    assert result==original and not receipt['promotions']
    original=rows()
    assert select_context_companions(original,proof([('20','29')]))[0]==original


def test_unverified_or_cross_version_companion_is_rejected():
    original=rows()
    with pytest.raises(ValueError,match='unverified_companion'):
        select_context_companions(original,proof([('0','missing')]))
    original[20]['parent_document_id']='other-version'
    with pytest.raises(ValueError,match='unverified_companion'):
        select_context_companions(original,proof([('0','20')]))


@pytest.mark.parametrize('graph',[False,True])
@pytest.mark.parametrize('lexical',[None,'organization-financial-needs.v2'])
def test_window_selection_upgrade_does_not_change_candidate_channel_limits(graph,lexical):
    from retrieval.candidate_policy import candidate_limits
    assert candidate_limits('needs_window.v3',has_graph=graph,lexical_policy=lexical)==candidate_limits(
        'needs_window.v2',has_graph=graph,lexical_policy=lexical)
