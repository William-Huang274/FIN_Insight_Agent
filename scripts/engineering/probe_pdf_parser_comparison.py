"""Bounded offline comparison of optional PDF parsers on captured originals.

Run one document/backend per process, with dependencies outside the service
environment. This produces review artifacts, never financial facts or indexes.
"""
import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--pages', type=int, nargs='+', required=True)
    p.add_argument('--backend', choices=['camelot', 'pymupdf_layout', 'pymupdf_text'], required=True)
    p.add_argument('--flavor', choices=['stream', 'network'], default='network')
    p.add_argument('--rotation', type=int, choices=[0, 90, 180, 270], default=0)
    p.add_argument('--flatten-rotation', action='store_true')
    p.add_argument('--derivation-directory', type=Path)
    p.add_argument('--direct-original-page', action='store_true')
    p.add_argument('--table-layout-artifact', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raw = a.source.read_bytes()
    if sha256(raw).hexdigest() != a.sha256:
        raise ValueError('source_digest_mismatch')
    if not a.pages or min(a.pages) < 1:
        raise ValueError('invalid_page_selection')
    if a.backend == 'camelot' and (a.rotation or a.flatten_rotation):
        raise ValueError('rotation_variant_requires_pymupdf_layout')
    if a.direct_original_page and (a.backend != 'pymupdf_text' or a.rotation or a.flatten_rotation):
        raise ValueError('direct_original_only_for_unmodified_native_text')
    a.output.mkdir(parents=True, exist_ok=False)

    def denied(*args, **kwargs):
        raise RuntimeError('offline_parser_probe_network_denied')

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    import psutil

    names = (['camelot-py', 'playa-pdf'] if a.backend == 'camelot' else
             ['pymupdf'] if a.backend == 'pymupdf_text' else
             ['pymupdf', 'pymupdf4llm', 'onnxruntime'])
    identity = {'raw_sha256': a.sha256, 'source': str(a.source), 'pages': a.pages,
                'backend': a.backend, 'flavor': a.flavor if a.backend == 'camelot' else None,
                'clockwise_rotation': a.rotation,
                'flatten_rotation': a.flatten_rotation,
                'direct_original_page': a.direct_original_page,
                'implementation_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                'panel_adapter_sha256': sha256((ROOT / 'src/ingestion/pdf_panel_candidates.py').read_bytes()).hexdigest(),
                'packages': {n: version(n) for n in names},
                'provider_calls': 0, 'production_enabled': False,
                'TokenBudgetBasis': {
                    'purpose': 'same-page borderless/card/reading-order/rotation comparison',
                    'input_scale': {'pages': a.pages, 'source_sha256': a.sha256},
                    'required_output': 'source-grounded regions, cell text, order and render',
                    'quality_risk': 'candidate models may merge cells or drop punctuation; no SQL promotion',
                    'reasoning_profile': 'local specialized layout model' if a.backend == 'pymupdf_layout' else 'deterministic geometry',
                    'limits': 'selected pages, one process, no OCR/network/embeddings',
                    'stop_behavior': 'record page failure, no automatic retry or provider substitution'}}
    if a.derivation_directory:
        parent_identity = json.loads((a.derivation_directory / 'identity.json').read_bytes())
        matches = [json.loads(line) for line in (a.derivation_directory / 'results.jsonl').read_text().splitlines()
                   if json.loads(line).get('derived_input_sha256') == a.sha256]
        if len(matches) != 1 or not matches[0].get('native_text_nonspace_character_multiset_preserved'):
            raise ValueError('derived_source_lineage_unverified')
        identity['source_lineage'] = {'original_sha256': parent_identity['raw_sha256'],
            'source_page': matches[0]['page'], 'coordinate_mapping': matches[0]['coordinate_mapping'],
            'parent_identity_sha256': sha256((a.derivation_directory / 'identity.json').read_bytes()).hexdigest()}
    layout = None
    if a.table_layout_artifact:
        if a.backend != 'camelot':
            raise ValueError('table_layout_requires_camelot')
        layout = json.loads(a.table_layout_artifact.read_bytes())
        layout_identity = json.loads((a.table_layout_artifact.parent / 'identity.json').read_bytes())
        expected = identity.get('source_lineage', {}).get('original_sha256', a.sha256)
        if layout_identity['TokenBudgetBasis']['input_scale']['document_id'] != expected:
            raise ValueError('table_layout_original_mismatch')
        identity['table_layout_artifact_sha256'] = sha256(a.table_layout_artifact.read_bytes()).hexdigest()
    (a.output / 'identity.json').write_text(json.dumps(identity, indent=2), encoding='utf8')
    rows = []
    for number in a.pages:
        start = time.perf_counter()
        row = {'page': number}
        try:
            if a.backend == 'camelot':
                import camelot
                kwargs = {}
                if layout is not None:
                    source_number = identity.get('source_lineage', {}).get('source_page', number)
                    layout_page = next(pg for pg in layout['pages'] if pg['page_number'] == source_number)
                    height = layout_page['height']
                    areas = [f"{b['x0']},{height-b['y0']},{b['x1']},{height-b['y1']}"
                             for b in layout_page['boxes'] if b.get('table')]
                    if not areas:
                        raise ValueError('no_layout_table_region')
                    kwargs['table_areas'] = areas
                    row['table_areas_from_layout'] = areas
                tables = camelot.read_pdf(str(a.source), pages=str(number), flavor=a.flavor, **kwargs)
                result = {'tables': [{'bbox': list(t._bbox), 'data': t.data,
                           'parsing_report': t.parsing_report,
                           'cells': [[{'text': c.text, 'bbox': [c.x1, c.y1, c.x2, c.y2]}
                                      for c in r] for r in t.cells]} for t in tables],
                          'coordinate_system': 'PDF bottom-left; original page retained'}
            else:
                import pymupdf
                with pymupdf.open(a.source) as original, pymupdf.open() as selected:
                    selected.insert_pdf(original, from_page=number-1, to_page=number-1)
                    page = original[number-1] if a.direct_original_page else selected[0]
                    if not a.direct_original_page:
                        page.set_rotation((page.rotation + a.rotation) % 360)
                    forward = list(page.rotation_matrix)
                    inverse = list(page.derotation_matrix)
                    before_text = original[number-1].get_text()
                    row['source_permissions'] = original.permissions
                    if a.flatten_rotation:
                        page.remove_rotation()
                        page = selected.reload_page(page)
                    derived = a.output / f'page-{number}-input.pdf'
                    if not a.direct_original_page:
                        selected.save(derived)
                    page.get_pixmap(matrix=pymupdf.Matrix(1, 1)).save(str(a.output / f'page-{number}.png'))
                    if a.backend == 'pymupdf_text':
                        result = page.get_text('dict', flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)
                        from ingestion.pdf_panel_candidates import source_panel_candidates
                        result['source_panel_candidates'] = source_panel_candidates(page)
                    else:
                        import pymupdf4llm
                        result = json.loads(pymupdf4llm.to_json(selected, pages=[0],
                                   use_ocr=False, force_text=True, show_progress=False))
                    after_text = page.get_text()
                    row['native_text_nonspace_character_multiset_preserved'] = (
                        Counter(c for c in before_text if not c.isspace()) ==
                        Counter(c for c in after_text if not c.isspace()))
                    if not a.direct_original_page:
                        row['derived_input_sha256'] = sha256(derived.read_bytes()).hexdigest()
                    else:
                        row['input_is_original_page'] = True
                    row['coordinate_mapping'] = {'source_page': number, 'derived_page': number if a.direct_original_page else 1,
                        'source_rect': list(original[number-1].rect),
                        'rotation_matrix': forward, 'derotation_matrix': inverse,
                        'derived_page_rotation': page.rotation}
            path = a.output / f'page-{number}.json'
            path.write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
            row.update(status='executed_not_quality_qualified', artifact=path.name,
                       artifact_sha256=sha256(path.read_bytes()).hexdigest())
        except Exception as exc:
            row.update(status='failed', error=type(exc).__name__, detail=str(exc)[:600])
        mem = psutil.Process().memory_info()
        row.update(elapsed_seconds=time.perf_counter()-start,
                   peak_working_set_bytes=getattr(mem, 'peak_wset', mem.rss))
        rows.append(row)
        with (a.output / 'results.jsonl').open('a', encoding='utf8') as f:
            f.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)
    (a.output / 'summary.json').write_text(json.dumps({'pages': len(rows),
        'failed': sum(r['status'] == 'failed' for r in rows)}), encoding='utf8')


if __name__ == '__main__':
    main()
