import pytest
from scripts.engineering import prepare_source_table_periods as producer
from retrieval.source_table_periods import digest


def test_large_xml_without_html_tables_never_builds_dom(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('HTML DOM must not be built')
    monkeypatch.setattr(producer, 'build_overlay', forbidden)
    raw = b'<informationTable>' + b'<infoTable><value>12</value></infoTable>'*20000 + b'</informationTable>'
    with pytest.raises(ValueError, match='source_original_has_no_html_tables'):
        producer.build_compatible_overlay(raw, raw_sha256=digest(raw), source_digest='unchanged-source')
    with pytest.raises(ValueError, match='source_raw_digest_mismatch'):
        producer.build_compatible_overlay(raw, raw_sha256='wrong', source_digest='unchanged-source')


@pytest.mark.parametrize('raw', [b'<html><TABLE class="x"><tr></tr></TABLE></html>',
    b'<table/>', '<html><table></table></html>'.encode('utf-16')])
def test_supported_or_unknown_encoding_keeps_existing_parser(raw, monkeypatch):
    seen=[]
    def parse(actual, **kwargs):
        seen.append((actual,kwargs));return {'original':'result'}
    monkeypatch.setattr(producer, 'build_overlay', parse)
    result=producer.build_compatible_overlay(raw,raw_sha256=digest(raw),source_digest='fixed')
    assert result=={'original':'result'}
    assert seen==[(raw,{'raw_sha256':digest(raw),'source_digest':'fixed'})]
