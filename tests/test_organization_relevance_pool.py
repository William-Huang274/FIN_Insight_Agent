from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from scripts.engineering.create_organization_relevance_pool import build
from scripts.engineering.diagnose_organization_retrieval_candidates import main
from test_organization_offline_recall import setup


def prepare(tmp_path, monkeypatch):
    output, _ = setup(tmp_path, monkeypatch, True)
    args = list(sys.argv); args[-1] = 'development'
    monkeypatch.setattr(sys, 'argv', args)
    main()
    return tmp_path/'questions.json', output/'result.json', Path(args[args.index('--index-directory')+1])/'index.json'


def test_pool_hides_rank_anchor_and_strategy_but_keeps_original_identity(tmp_path, monkeypatch):
    dataset, result, index = prepare(tmp_path, monkeypatch)
    before = sha256(dataset.read_bytes()).hexdigest()
    review, audit = build(dataset, [result, result], index)
    assert review['status'] == 'pending_review' and not audit['labels_changed']
    assert len(review['questions'][0]['passages']) == 1
    passage = review['questions'][0]['passages'][0]
    assert passage['judgment'] is None
    assert 'rank' not in passage and 'gold' not in passage and 'channel' not in passage
    assert sha256(passage['content'].encode()).hexdigest() == passage['content_sha256']
    assert sha256(dataset.read_bytes()).hexdigest() == before
    assert review == build(dataset, [result], index)[0]


@pytest.mark.parametrize('fault', ['dataset', 'index', 'failed', 'heldout', 'partial'])
def test_pool_rejects_mixed_or_unfinished_experiments(tmp_path, monkeypatch, fault):
    dataset, result, index = prepare(tmp_path, monkeypatch)
    report = json.loads(result.read_text())
    if fault == 'dataset': report['dataset_sha256'] = 'wrong'
    if fault == 'index': report['index_sha256'] = 'wrong'
    if fault == 'failed': report['status'] = 'failed'
    if fault == 'heldout': report['split'] = 'heldout'
    if fault == 'partial': report['samples'] = []
    result.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='complete_same_development'):
        build(dataset, [result], index)


def test_paid_rerank_rejects_changed_questions_before_preparing_requests(tmp_path, monkeypatch):
    from scripts.engineering.organization_rerank_comparison import prepare as prepare_rerank
    dataset, result, index = prepare(tmp_path, monkeypatch)
    data = json.loads(dataset.read_text())
    data['questions'][0]['query'] = 'A different paid request'
    dataset.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='original_query_dataset_mismatch'):
        prepare_rerank(result, dataset, index)
