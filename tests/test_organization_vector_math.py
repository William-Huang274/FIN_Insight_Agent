"""Cross-block equivalence and late corrupt rows, without allocating a full corpus."""
import numpy as np
import pytest

from sec_agent.research_foundation.organization_vector_math import BLOCK_ROWS, unit_vectors, cosine_scores


def test_permuted_subset_matches_full_cosine_and_never_reads_unselected_rows():
    rng=np.random.default_rng(713)
    values=rng.normal(size=(BLOCK_ROWS+19,17)).astype(np.float32)
    values/=np.linalg.norm(values.astype(np.float64),axis=1)[:,None]
    positions=list(range(len(values)-1,0,-1))  # Row zero is unauthorized.
    query=rng.normal(size=17).astype(np.float32)
    query/=np.linalg.norm(query.astype(np.float64))
    expected=values[positions] @ query
    class SelectedOnly:
        def __getitem__(self, rows):
            assert len(rows)<=BLOCK_ROWS and 0 not in rows
            return values[rows]
    matrix=SelectedOnly()
    assert unit_vectors(matrix,positions)
    actual=cosine_scores(matrix,positions,query)
    np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=1e-7)
    assert np.argsort(-actual)[:24].tolist()==np.argsort(-expected)[:24].tolist()
    # Unselected corrupt rows cannot enter scoring or affect candidate validation.
    values[0]=float('nan')
    assert unit_vectors(matrix,positions)
    np.testing.assert_array_equal(cosine_scores(matrix,positions,query),actual)


@pytest.mark.parametrize('bad',[0.,float('nan'),float('inf'),2.])
def test_final_block_corruption_rejects_validation_and_scoring(bad):
    values=np.zeros((BLOCK_ROWS+1,2),dtype=np.float32)
    values[:,0]=1.
    assert unit_vectors(values)
    values[-1,0]=bad
    assert not unit_vectors(values)
    with pytest.raises(ValueError,match='invalid_prepared_vectors'):
        cosine_scores(values,list(range(len(values))),np.array([1.,0.],dtype=np.float32))


def test_readonly_mapping_blocks_own_data_and_match_original_arithmetic(tmp_path, monkeypatch):
    import weakref
    import sec_agent.research_foundation.organization_vector_math as math
    rng = np.random.default_rng(913)
    values = rng.normal(size=(BLOCK_ROWS + 17, 23)).astype(np.float32)
    values /= np.linalg.norm(values.astype(np.float64), axis=1)[:, None]
    np.save(tmp_path/'vectors.npy', values, allow_pickle=False)
    matrix = np.load(tmp_path/'vectors.npy', mmap_mode='r', allow_pickle=False)
    positions = list(range(len(values)-1, 0, -1))
    query = values[0].copy()
    refs = []
    original = math._mapped_block
    def counted(*args):
        block = original(*args)
        refs.append(weakref.ref(block))
        assert not np.shares_memory(block, matrix)
        assert not isinstance(block, np.memmap)
        return block
    monkeypatch.setattr(math, '_mapped_block', counted)
    actual = cosine_scores(matrix, positions, query)
    np.testing.assert_array_equal(actual, cosine_scores(values, positions, query))
    assert unit_vectors(matrix) and all(ref() is None for ref in refs)
    # A sliced memmap retains the parent's offset: don't reopen it as a root.
    np.testing.assert_array_equal(cosine_scores(matrix[5:], [2, 0], query),
                                  cosine_scores(values[5:], [2, 0], query))


def test_readonly_mapping_keeps_full_scope_and_rejects_last_corrupt_row(tmp_path):
    values = np.zeros((BLOCK_ROWS + 1, 3), dtype=np.float32)
    values[:, 0] = 1.
    values[-1, 0] = float('nan')
    np.save(tmp_path/'bad.npy', values, allow_pickle=False)
    matrix = np.load(tmp_path/'bad.npy', mmap_mode='r', allow_pickle=False)
    assert not unit_vectors(matrix)
    with pytest.raises(ValueError, match='invalid_prepared_vectors'):
        cosine_scores(matrix, list(range(len(values))), np.array([1., 0., 0.], dtype=np.float32))


@pytest.mark.parametrize('corrupt_late',[False,True])
def test_offline_replay_preserves_successful_sources_on_late_failure(tmp_path,corrupt_late):
    import json
    from scripts.engineering.qualify_organization_vector_blocks import qualify,digest
    intake=tmp_path/'intake';intake.mkdir()
    query=tmp_path/'query'/'index.json';query.parent.mkdir()
    query.write_text(json.dumps({'queries':{'query-hash':[1.]+[0.]*1023}}),encoding='utf8')
    sources=[]
    for i in range(2):
        directory=intake/str(i);directory.mkdir()
        values=np.zeros((3,1024),dtype=np.float32);values[:,0]=1.
        if i==1 and corrupt_late:values[-1,0]=float('nan')
        np.save(directory/'vectors.npy',values,allow_pickle=False)
        (directory/'vector-map.json').write_text(json.dumps([
            {'vector_index':j,'chunk_id':str(j)} for j in [2,0,1]]),encoding='utf8')
        sources.append({'source_id':str(i),'status':'verified','directory':str(i),
            'files':{name:digest(directory/name) for name in ['vectors.npy','vector-map.json']}})
    (intake/'result.json').write_text(json.dumps({'status':'verified','sources':sources}),encoding='utf8')
    output=tmp_path/'output'
    if corrupt_late:
        with pytest.raises(ValueError,match='not_normalized'):
            qualify(intake,query,digest(query),output)
    else:
        qualify(intake,query,digest(query),output)
    result=json.loads((output/'result.json').read_text(encoding='utf8'))
    assert result['status']==('failed' if corrupt_late else 'passed')
    assert len(result['sources'])==(1 if corrupt_late else 2)
    assert result['provider_calls']==0
