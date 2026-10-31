"""Real immutable artifacts, fresh permissions, and bounded read-only caches."""
import logging
import json
import sqlite3

import pytest

from tests.test_organization_retrieval_lifecycle import lifecycle
from tests.test_organization_candidate_index import query, items
from sec_agent.research_foundation.organization_retrieval_lifecycle import OrganizationRetrievalLifecycle
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.source_verification_cache import SourceVerificationCache, _receipt_rows


def test_stage_creation_is_lazy_and_next_run_reuses_release_not_authority(tmp_path, monkeypatch, caplog):
    manager, reader, state, _, _ = lifecycle(tmp_path, monkeypatch)
    calls=[];original=reader._read_storage
    monkeypatch.setattr(reader,'_read_storage',lambda *a: (calls.append(a[0]),original(*a))[1])
    caplog.set_level(logging.INFO)
    stage=manager.navigation()
    assert manager.status()['state']=='unprepared' and not calls
    expected=stage.navigate(query())
    release=manager._navigation.hybrid.release_cache
    manager.close()
    import sec_agent.research_foundation.organization_index_release as releases
    monkeypatch.setattr(releases,'_load_release',lambda *a,**kw:pytest.fail('unchanged release reloaded'))
    other=OrganizationRetrievalLifecycle(reader,workbench_url='http://localhost',
        retrieval_root=tmp_path/'indices',grant=reader._grant()[0])
    try:
        calls.clear()
        fresh=other.navigation()
        assert not calls and items(fresh.navigate(query()))==items(expected)
        assert other._navigation.hybrid.release_cache is release
        assert fresh.observed is not stage.observed
        assert not calls
        state['status']=404
        with pytest.raises(OrganizationExecutionUnavailable):fresh.navigate(query())
    finally:other.close()
    finished=[r for r in caplog.records if getattr(r,'event',None)=='organization_preparation_finished']
    phases={r.phase for r in finished}
    assert all(json.loads(r.getMessage())['elapsed_ms']==r.elapsed_ms for r in finished)
    assert {'retrieval_prepare','release_load','candidate_prepare','source_version_batch','proof_cache_read'} <= phases
    assert all(not hasattr(r,'source_text') for r in caplog.records)


def test_proof_byte_cache_returns_fresh_objects_and_invalidates_file_mutation(tmp_path):
    cache=SourceVerificationCache(tmp_path)
    cache.put('v1',{'nodes':['original'], 'metadata':{'period':'FY2026'}})
    _receipt_rows.cache_clear()
    first=list(cache.iter_get(['v1']))[0][1]
    first['nodes'].append('caller change')
    again=list(cache.iter_get(['v1']))[0][1]
    assert again['nodes']==['original'] and _receipt_rows.cache_info().hits==1
    cache.put('v2',{'nodes':['new period']})
    assert list(cache.iter_get(['v2']))[0][1]['nodes']==['new period']
    with sqlite3.connect(cache.path) as db:
        db.execute('UPDATE receipts SET digest=? WHERE key=?',('bad','v1'))
    with pytest.raises(ValueError,match='receipt_corrupt'):list(cache.iter_get(['v1']))
