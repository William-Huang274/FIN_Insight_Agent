"""Offline ruled-cell comparison on a frozen, explicitly selected page plan.

Reads captured local PDFs without OCR, models or publication. Keeps raw cell
observations for visual review; a geometry candidate is not a financial table.
"""
import argparse
from hashlib import sha256
from importlib.metadata import version
import json
import math
from collections import Counter
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes)
    args.output.mkdir(parents=True, exist_ok=False)

    def denied(*_args, **_kwargs):
        raise RuntimeError('offline_probe_network_denied')

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    import pdfplumber
    import psutil
    from ingestion.pdf_structure_candidates import ruled_structure_candidates

    identity = {'plan_sha256': sha256(plan_bytes).hexdigest(), 'plan': plan,
                'implementation_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                'adapter_sha256': sha256((ROOT / 'src/ingestion/pdf_structure_candidates.py').read_bytes()).hexdigest(),
                'packages': {name: version(name) for name in ['pdfplumber', 'pdfminer.six']},
                'ocr_calls': 0, 'model_calls': 0, 'production_enabled': False}
    (args.output / 'identity.json').write_text(json.dumps(identity, indent=2), encoding='utf8')
    rows = []
    for doc in plan['documents']:
        path = Path(doc['path'])
        if sha256(path.read_bytes()).hexdigest() != doc['sha256']:
            raise ValueError('original_digest_mismatch')
        with pdfplumber.open(path) as pdf:
            for selection in doc['selections']:
                number = selection['page']
                started = time.perf_counter()
                row = {'id': doc['sha256'], **selection}
                try:
                    page = pdf.pages[number - 1]
                    output = ruled_structure_candidates(page)
                    output.update(raw_sha256=doc['sha256'], page=number)
                    output['source_profile'] = {
                        'native_character_count': len(page.chars),
                        'non_upright_character_count': sum(not c.get('upright', True) for c in page.chars),
                        'native_word_count': len(page.extract_words()),
                        'embedded_image_count': len(page.images),
                        'rotation_metadata': page.rotation,
                        # Some PDFs contain tiny floating-point values where
                        # zero is expected. The backend upright flag alone
                        # did not expose a visibly rotated diagnostic page.
                        'character_matrix_angles_degrees': dict(Counter(
                            round(math.degrees(math.atan2(c['matrix'][1], c['matrix'][0])), 1)
                            for c in page.chars if c.get('matrix'))),
                        'ocr_need': 'not_inferred_from_word_count_alone',
                    }
                    artifact = args.output / f"{doc['sha256']}-page-{number}.json"
                    artifact.write_text(json.dumps(output, ensure_ascii=False), encoding='utf8')
                    row.update(status='executed_not_semantically_qualified',
                               artifact=artifact.name, artifact_sha256=sha256(artifact.read_bytes()).hexdigest(),
                               candidates=len(output['candidates']),
                               repeated_grids=sum(c['geometry_role'] == 'multirow_multicol_grid_candidate'
                                                  for c in output['candidates']))
                    page.close()
                except Exception as exc:
                    row.update(status='failed', error=type(exc).__name__, detail=str(exc)[:400])
                memory = psutil.Process().memory_info()
                row.update(elapsed_seconds=time.perf_counter() - started,
                           peak_working_set_bytes=getattr(memory, 'peak_wset', memory.rss))
                rows.append(row)
                with (args.output / 'results.jsonl').open('a', encoding='utf8') as stream:
                    stream.write(json.dumps(row) + '\n')
                print(json.dumps(row), flush=True)
    (args.output / 'summary.json').write_text(json.dumps({'pages': len(rows),
        'failed': sum(r['status'] == 'failed' for r in rows),
        'candidates': sum(r.get('candidates', 0) for r in rows),
        'repeated_grids': sum(r.get('repeated_grids', 0) for r in rows)}), encoding='utf8')


if __name__ == '__main__':
    main()
