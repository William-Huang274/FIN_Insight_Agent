"""Native fields survive before any FIN projection; no live source/provider use."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'engineering'))
from native_document_capture import NativeEncoder, capture_native, datamule_table_compatibility, read_capture, validate_capture


def test_encoder_never_silently_stringifies_unsupported_fields():
    with pytest.raises(TypeError, match='unsupported_native_field'):
        NativeEncoder().encode(object())
    result = NativeEncoder().encode({'zero': Decimal('0.00'), 'large': Decimal('100000000000000000.01')})
    assert result['zero'] == {'$decimal': '0.00'}
    assert result['large']['$decimal'].endswith('.01')


def test_complete_node_graph_and_long_cells_preserve_public_fields():
    pytest.importorskip('edgar.documents')
    from edgar.documents.nodes import DocumentNode, HeadingNode, LinkNode
    from edgar.documents.table_nodes import TableNode, Cell, Row
    root = DocumentNode()
    heading = HeadingNode(content='Annual results', level=2)
    heading.metadata['evidence'] = 'original heading'
    root.add_child(heading)
    nested = LinkNode(href='https://example.test/source', content='Reference')
    table = TableNode(headers=[[Cell('Unit', is_header=True)]],
                      rows=[Row([Cell('X' * 1200, colspan=2, rowspan=3, align='right'), Cell(nested)])],
                      footer=[Row([Cell('Amounts in millions')])], caption='Reported values')
    root.add_child(table)
    encoder = NativeEncoder(type(root).__mro__[1])
    ref = encoder.encode(root)
    encoded = {'schema': 'fin_native_document_v1', 'route': 'edgartools',
               'native': {'root': ref, 'nodes': encoder.nodes}}
    assert validate_capture(encoded)
    tables = [n for n in encoder.nodes if n['class'] == 'TableNode']
    cell = tables[0]['fields']['rows'][0]['fields']['cells'][0]['fields']
    assert cell['content'] == 'X' * 1200
    assert (cell['rowspan'], cell['colspan'], cell['align']) == (3, 2, 'right')
    assert any(n['class'] == 'LinkNode' for n in encoder.nodes)
    assert tables[0]['fields']['parent'] == ref
    assert len(json.dumps(encoded)) > 1200
    broken = copy.deepcopy(encoded)
    broken['native']['root'] = {'$node': 'absent'}
    with pytest.raises(ValueError, match='dangling_native_node'):
        validate_capture(broken)


def test_markdown_native_front_matter_table_and_source_positions():
    pytest.importorskip('mdit_py_plugins')
    raw = b'---\nlicense: apache-2.0\n---\n\n## Results\n\n| Name | Value |\n|---|---|\n| A\\|B | (12.50) |\n'
    result = capture_native(raw, 'markdown')
    assert validate_capture(result)
    tokens = result['native']['tokens']
    assert tokens[0]['type'] == 'front_matter' and tokens[0]['hidden']
    assert tokens[0]['map'] == [0, 3]
    assert [t['tag'] for t in tokens if t['type'] == 'heading_open'] == ['h2']
    assert sum(t['type'] == 'td_open' for t in tokens) == 2
    assert next(t for t in tokens if t['type'] == 'table_open')['map'] == [6, 9]
    assert result['native']['source_text'].encode() == raw
    assert '(12.50)' in [t['content'] for t in tokens if t['type'] == 'inline']
    assert result['loaded_parser_module_sha256']


def test_markdown_keeps_original_when_display_grammar_drops_extra_column():
    pytest.importorskip('mdit_py_plugins')
    raw = b'| A | B |\n|---|---|\n| 1 | 2 | 999 |\n'
    result = capture_native(raw, 'markdown')
    assert sum(t['type'] == 'td_open' for t in result['native']['tokens']) == 2
    assert '999' in result['native']['source_text']
    assert result['quality_status'] == 'native_output_not_independently_qualified'


def test_markdown_code_block_is_not_reparsed_as_table_or_metadata():
    pytest.importorskip('mdit_py_plugins')
    raw = b'```text\n---\nkey: value\n---\n| A | B |\n|---|---|\n```\n'
    result = capture_native(raw, 'markdown')
    assert [t['type'] for t in result['native']['tokens']] == ['fence']


def test_web_native_keeps_every_document_slot_and_empty_result(monkeypatch):
    trafilatura = pytest.importorskip('trafilatura')
    from lxml import etree
    values = {'title': 'Article', 'body': etree.fromstring(b'<body><p>Text <ref target="/original">source</ref> tail.</p></body>'),
              'commentsbody': etree.fromstring(b'<body><p>Comment</p></body>'), 'new_upstream_field': ['kept']}
    class Document:
        def as_dict(self): return values
    seen = {}
    def extract(raw, **options):
        seen.update(options)
        return Document()
    monkeypatch.setattr(trafilatura, 'bare_extraction', extract)
    result = capture_native(b'<p>Original</p>', 'trafilatura')
    doc = result['native']['document']
    assert set(doc) == set(values)
    assert 'target="/original"' in doc['body']['$xml']
    assert ' tail.' in doc['body']['$xml']
    assert seen['include_links'] and seen['include_comments'] and seen['include_images']
    monkeypatch.setattr(trafilatura, 'bare_extraction', lambda *a, **k: None)
    result = capture_native(b'<p>Original</p>', 'trafilatura', web_focus='precision')
    assert result['native']['status'] == 'empty_extraction'
    assert validate_capture(result)


def test_sec_actual_public_sections_and_immutable_source():
    pytest.importorskip('edgar.documents')
    raw = b'<html><body><h1>FORM 8-K</h1><h2>Item 2.02 Results of Operations</h2><p>Results were announced.</p><h2>Signature</h2><p>Signed.</p></body></html>'
    result = capture_native(raw, 'edgartools', form='8-K')
    assert validate_capture(result)
    assert result['native']['sections']
    assert all('native_text' in s and 'native_tables' in s for s in result['native']['sections'].values())
    assert result['native']['metadata']['fields']['original_html'].encode() == raw
    assert result['fin_adaptation_applied'] is False


def test_datamule_retains_hierarchy_when_native_table_api_is_incompatible():
    pytest.importorskip('datamule')
    raw = b'<html><body><h1>Results</h1><p>Amounts in millions.</p><table><tr><th>Year</th><th>Cash</th></tr><tr><td>2025</td><td>12</td></tr></table><p>Restricted amounts excluded.</p></body></html>'
    result = capture_native(raw, 'datamule', form='8-K')
    native = result['native']
    assert native['data'] and native['data_tuples'] and native['data_tuples_columnar']
    # Installed pairing emits six-element tuples, but tables expects four.
    # Preserve this failure and the full tuples, rather than silently trim them.
    assert native['tables'] is None
    assert native['capability_errors'][0]['capability'] == 'tables'
    assert native['capability_errors'][0]['error'] == 'ValueError'
    adapted = result['compatibility_adaptations']['tables']
    assert adapted['tables'] and 'data_raw' in adapted['tables'][0]
    assert 'footnotes_raw' in adapted['tables'][0] and 'preamble_raw' in adapted['tables'][0]
    assert adapted['tuple_provenance'] == native['data_tuples']
    assert native['document_fields']['content'].encode() == raw
    assert validate_capture(result)


def test_frozen_output_reused_only_with_matching_artifact_and_source(tmp_path):
    pytest.importorskip('mdit_py_plugins')
    import gzip
    from hashlib import sha256
    result = capture_native(b'# Title\n\nBody.\n', 'markdown')
    packed = gzip.compress(json.dumps(result).encode())
    path = tmp_path / 'native.json.gz'
    path.write_bytes(packed)
    digest = sha256(packed).hexdigest()
    assert read_capture(path, expected_sha256=digest,
                        expected_source_sha256=result['source_sha256']) == result
    with pytest.raises(ValueError, match='native_source_identity_mismatch'):
        read_capture(path, expected_sha256=digest, expected_source_sha256='wrong')
    path.write_bytes(packed + b'changed')
    with pytest.raises(ValueError, match='native_artifact_digest_mismatch'):
        read_capture(path, expected_sha256=digest, expected_source_sha256=result['source_sha256'])


def test_datamule_compatibility_keeps_descriptions_and_extra_provenance():
    pytest.importorskip('datamule')
    from types import SimpleNamespace
    tuples = [(4, 'table_data', [['Year', 'Cash'], ['2025', '12']], 2, 'table', [10, 20]),
              (4, 'table_preamble', 'Amounts in millions.', 2, 'unit', [8, 10]),
              (4, 'table_footnote', '(a) Restricted amounts excluded.', 2, 'note', [20, 22])]
    before = copy.deepcopy(tuples)
    doc = SimpleNamespace(type='8-K', content='', filename='original.htm', accession=None,
                          filing_date=None, data_tuples=tuples)
    result = datamule_table_compatibility(doc)
    assert result['tables'][0]['preamble'] == 'Amounts in millions.'
    assert result['tables'][0]['footnotes_raw'] == [{'text': '(a) Restricted amounts excluded.'}]
    assert tuples == before
    assert result['tuple_provenance'] == NativeEncoder().encode(before)
    doc.data_tuples = [(4, 'table_data', [], 2, 'unknown_shape')]
    with pytest.raises(ValueError, match='unsupported_datamule_tuple_compatibility'):
        datamule_table_compatibility(doc)
