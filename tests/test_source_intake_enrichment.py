"""Service expectations must consume the capture's bound original overlay."""
import json
import pytest
from scripts.engineering import source_intake_batches as batches
from tests.integration.source_intake_diagnostics import (
    SourceBundles, configured_source_enrichment, reserve_index_output)
from test_source_structure import bundle
from test_source_table_periods import fixture, catalog_at
from retrieval.source_table_periods import build_overlay, digest


def test_lazy_enrichment_survives_subset_and_does_not_change_original(tmp_path, monkeypatch):
    raw, text = fixture()
    original = bundle(text)
    original['format'] = 'library-source-bundle.v1'
    original['library_sha256'] = 'fixed-library'
    original['source']['id'] = 'source'
    source = tmp_path/'source.json'
    source.write_text(json.dumps(original), encoding='utf8')
    before = source.read_bytes()
    overlay = build_overlay(raw, raw_sha256=digest(raw), source_digest=digest(text))
    catalog, expected = catalog_at(tmp_path/'catalog', original, overlay)
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG', str(catalog))
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256', expected)
    ordinary = SourceBundles([('source', source)])
    enriched = SourceBundles([('source', source)], enrich=configured_source_enrichment)
    assert ordinary['source'] == original
    assert enriched['source'] == {**original, 'table_period_context': overlay}
    assert enriched.subset(['source'])['source'] == enriched['source']
    assert source.read_bytes() == before
    catalog.write_text('{}', encoding='utf8')
    with pytest.raises(ValueError, match='catalog_digest_mismatch'):
        enriched['source']


def test_external_index_storage_never_reuses_existing_directory(tmp_path):
    attempt = tmp_path/'attempt'
    assert reserve_index_output(attempt) == attempt/'indices'
    other = tmp_path/'separate-disk'/'new-index'
    assert reserve_index_output(attempt, other) == other.resolve()
    marker = other/'belongs-to-existing-attempt'
    marker.write_text('keep')
    with pytest.raises(FileExistsError): reserve_index_output(attempt, other)
    assert marker.read_text() == 'keep'


def test_overlay_changes_checkpoint_identity_but_absent_option_keeps_legacy(tmp_path, monkeypatch):
    monkeypatch.setattr(batches.subprocess, 'check_output',
        lambda args, **kwargs: '' if args[1] == 'status' else 'fixed-head')
    jar = tmp_path/'service.jar'; jar.write_bytes(b'jar')
    monkeypatch.setenv('FINSIGHT_INTAKE_TEST_JAR', str(jar))
    for key in ('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG', 'FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256',
                'FIN_COMPLETE_SOURCE_QUESTIONS', 'FINSIGHT_LIBRARY_NODE_CATALOG', 'FINSIGHT_LIBRARY_RECOVERY_CATALOG'):
        monkeypatch.delenv(key, raising=False)
    legacy = batches.baseline()
    assert 'FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG' not in legacy['configuration']
    catalog = tmp_path/'catalog.json'; catalog.write_bytes(b'{}')
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG', str(catalog))
    with pytest.raises(ValueError, match='catalog_configuration_mismatch'): batches.baseline()
    monkeypatch.setenv('FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG_SHA256', digest(catalog.read_bytes()))
    current = batches.baseline()
    assert current != legacy
    assert current['configuration_files']['FINSIGHT_LIBRARY_TABLE_PERIOD_CATALOG'] == digest(catalog.read_bytes())
    catalog.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError, match='catalog_configuration_mismatch'): batches.baseline()
