import copy
from hashlib import sha256
import json

import pytest

from retrieval.rank_fusion import reciprocal_rank_fusion
from scripts.engineering.organization_ranking_ablation import compare, main, variants


def fixture():
    records = [dict(node_id=n, document_id=d, content_sha256=b, embedding_input_sha256=c)
               for n, d, b, c in [('a', 'd1', 'body', 'context'), ('copy', 'd1', 'body', 'context'),
                                  ('period', 'd2', 'body', 'context'), ('header', 'd1', 'body', 'other')]]
    dense, lexical = ['a', 'copy', 'period'], ['copy', 'header']
    ranks = dict(dense_candidates=dense, lexical_candidates=lexical,
                 fused_candidates=reciprocal_rank_fusion([dense, lexical]))
    result = dict(status='completed', expected_questions=1, evaluation_role='source_first', split='development',
                  candidate_chunks=4, candidate_sources=2, samples=[dict(id='q1', family='f1',
                  split='development', status='completed', gold=['a'], rankings=ranks)])
    return result, {'records': records}


def test_dedup_keeps_other_document_revision_and_context_and_trace():
    result, index = fixture()
    ranked, aliases = variants(result['samples'][0]['rankings'], {r['node_id']: r for r in index['records']})
    assert aliases['copy'] == ['copy', 'a']
    assert set(ranked['exact_context_dedup_rrf']) == {'copy', 'period', 'header'}
    report = compare(result, index)
    assert report['samples'][0]['strict_metrics']['exact_context_dedup_rrf']['known_hit@10'] == 0
    assert report['samples'][0]['dedup_equivalent_hit10'] is True
    assert not report['S2_passed'] and not report['serving_policy_changed']


@pytest.mark.parametrize('change,error', [
    (lambda r: r.update(split='heldout'), 'development_only'),
    (lambda r: r['samples'][0].update(split='heldout'), 'development_only'),
    (lambda r: r.update(expected_questions=2), 'complete_results'),
    (lambda r: r['samples'][0].update(status='failed'), 'failed_sample'),
    (lambda r: r['samples'][0]['rankings']['fused_candidates'].reverse(), 'baseline_order'),
    (lambda r: r['samples'][0]['rankings']['dense_candidates'].append('unknown'), 'candidate_identity'),
    (lambda r: r['samples'][0]['rankings']['dense_candidates'].append('a'), 'candidate_identity'),
])
def test_rejects_invalid_or_evaluation_inputs(change, error):
    result, index = fixture(); change(result)
    with pytest.raises(ValueError, match=error):
        compare(result, index)


def test_labels_do_not_change_ranking_and_graph_is_separate():
    result, index = fixture()
    ranks = result['samples'][0]['rankings']
    ranks['graph_candidates'] = ['header']
    ranks['graph_fused_candidates'] = reciprocal_rank_fusion([
        ranks['dense_candidates'], ranks['lexical_candidates'], ranks['graph_candidates']])
    other = copy.deepcopy(result); other['samples'][0]['gold'] = ['header']
    before, after = compare(result, index), compare(other, index)
    assert [s['rankings'] for s in before['samples']] == [s['rankings'] for s in after['samples']]
    assert set(before['summary']) == {'hybrid', 'graph'}


@pytest.mark.parametrize('corrupt', [False, True])
def test_cli_checks_frozen_index_and_preserves_failure(tmp_path, monkeypatch, corrupt):
    result, index = fixture()
    index_path = tmp_path/'index.json'
    index_path.write_text(json.dumps(index), encoding='utf8')
    result['index_sha256'] = 'bad' if corrupt else sha256(index_path.read_bytes()).hexdigest()
    input_path = tmp_path/'input.json'; input_path.write_text(json.dumps(result), encoding='utf8')
    output = tmp_path/'output'
    monkeypatch.setattr('sys.argv', ['audit', '--result', str(input_path), '--index', str(index_path), '--output', str(output)])
    if corrupt:
        with pytest.raises(ValueError, match='index_hash_mismatch'):
            main()
    else:
        main()
    saved = json.loads((output/'result.json').read_text(encoding='utf8'))
    assert saved['status'] == ('failed' if corrupt else 'completed')
    assert not saved['S2_passed'] and saved['provider_calls'] == 0
    with pytest.raises(FileExistsError):
        main()
