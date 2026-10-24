"""Isolated read-only component memory probes, never service/recall acceptance.

Run each variant in a fresh process. Windows peak counters include short peaks
that the sampling thread can miss while a JSON encoder holds the GIL. RSS is
not private commit, nor is either an exclusive physical-memory measurement.
"""
import argparse
from contextlib import contextmanager
import gc
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import sys
import threading
import time
import weakref

import numpy as np
import psutil

from sec_agent.research_foundation.organization_index_release import canonical_digest
from sec_agent.research_foundation.organization_vector_math import unit_vectors, cosine_scores


def baseline_vectors(matrix, positions, query=None):
    """Pre-change 4096-row validation/dot arithmetic with one resident mapping."""
    scores = None if query is None else np.empty(len(positions), dtype=np.float32)
    for start in range(0, len(positions), 4096):
        block = matrix[positions[start:start+4096]]
        valid = (np.isfinite(block).all() and np.allclose(
            np.linalg.norm(block.astype(np.float64), axis=1), 1., rtol=1e-5, atol=1e-6))
        if not valid:
            raise ValueError('baseline_invalid_vector')
        if scores is not None:
            scores[start:start+len(block)] = block @ query
    return True if scores is None else scores


class Probe:
    def __init__(self, output):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.process = psutil.Process()
        self.report = {'status': 'running', 'scope': 'read-only component probe; no current authority or services',
                       'provider_calls': 0, 'phases': [], 'python': sys.version,
                       'numpy': np.__version__, 'threads': {k: os.getenv(k) for k in
                           ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS')}}
        self.save()

    def snapshot(self):
        info = self.process.memory_info()
        return {'rss': info.rss, 'private': getattr(info, 'private', info.vms),
                'process_peak_rss': getattr(info, 'peak_wset', None),
                'process_peak_commit': getattr(info, 'peak_pagefile', None),
                'available': psutil.virtual_memory().available}

    def save(self):
        (self.output/'result.json').write_text(json.dumps(self.report, indent=2), encoding='utf8')

    @contextmanager
    def phase(self, name):
        before = self.snapshot()
        if before['available'] < 800 * 2**20:
            raise RuntimeError('component_memory_floor')
        row = {'name': name, 'before': before, 'status': 'running'}
        self.report['phases'].append(row)
        self.save()
        samples = [before]
        stop = threading.Event()
        def monitor():
            low = 0
            while not stop.wait(.1):
                sample = self.snapshot()
                samples.append(sample)
                low = low + 1 if sample['available'] < 800 * 2**20 else 0
                if low >= 3:
                    import _thread
                    _thread.interrupt_main()
                    return
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        start = time.perf_counter()
        try:
            yield row
            row['status'] = 'passed'
        except BaseException as exc:
            row.update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            stop.set()
            thread.join()
            row.update(seconds=time.perf_counter()-start, after=self.snapshot(),
                       sampled_peak_rss=max(s['rss'] for s in samples),
                       sampled_peak_private=max(s['private'] for s in samples),
                       minimum_available=min(s['available'] for s in samples))
            self.save()


def profile(index_path, matrix_path, output, *, variant, component='all'):
    probe = Probe(output)
    signature = lambda p: (p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ino)
    paths = [Path(index_path), Path(matrix_path)]
    before = [signature(p) for p in paths]
    probe.report.update(variant=variant, component=component, files=[str(p) for p in paths])
    try:
        # Reserve for the full manifest object and mapped vector working set;
        # this probe starts no Java/BFF/database processes.
        reserve = {'all': 1000, 'manifest': 512, 'vectors': 640}[component] * 2**20
        probe.report['startup'] = probe.snapshot()
        probe.report['required_available'] = 800 * 2**20 + reserve
        if probe.snapshot()['available'] < probe.report['required_available']:
            raise RuntimeError('component_startup_headroom')
        with probe.phase('manifest_parse'):
            index = json.loads(paths[0].read_bytes())
        probe.report['records'] = len(index['records'])
        probe.report['documents'] = len({r['document_id'] for r in index['records'] if 'document_id' in r})
        with probe.phase('canonical_digest') as row:
            if variant == 'baseline':
                digest = sha256(json.dumps(index, sort_keys=True, ensure_ascii=False,
                                          separators=(',', ':')).encode()).hexdigest()
            else:
                digest = canonical_digest(index)
            row['digest'] = digest
        with probe.phase('query_digest_repeat') as row:
            if variant == 'baseline':
                encoded = json.dumps(index, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
                repeated = sha256(encoded).hexdigest()
            else:
                # The production frozen loader returns this already verified
                # canonical digest. This component probe does not grant trust.
                repeated = digest
            assert repeated == digest
            row['digest'] = repeated
        if component == 'manifest':
            with probe.phase('release_query_temporaries'):
                if variant == 'baseline':
                    del encoded
                gc.collect()
            with probe.phase('release_manifest'):
                del index
                gc.collect()
            assert before == [signature(p) for p in paths]
            probe.report['status'] = 'passed'
            return probe.report
        positions = [r['vector_index'] for r in index['records']]
        node_ids = [r['node_id'] for r in index['records']]
        dimensions = index['dimensions']
        expected_matrix_digest = index['matrix_sha256']
        query = np.asarray(next(iter(index['queries'].values())), dtype=np.float32)
        if component == 'vectors':
            with probe.phase('release_manifest_before_vectors'):
                del index
                if variant == 'baseline':
                    del encoded
                gc.collect()
        with probe.phase('matrix_file_integrity'):
            with paths[1].open('rb') as stream:
                assert file_digest(stream, 'sha256').hexdigest() == expected_matrix_digest
        with probe.phase('matrix_mapping'):
            matrix = np.load(paths[1], mmap_mode='r', allow_pickle=False)
            assert matrix.shape == (len(positions), dimensions) and matrix.dtype == np.float32
            mapping_ref = weakref.ref(matrix)
        with probe.phase('vector_validation'):
            assert (baseline_vectors(matrix, positions) if variant == 'baseline' else unit_vectors(matrix, positions))
        with probe.phase('vector_scoring') as row:
            scores = (baseline_vectors(matrix, positions, query) if variant == 'baseline' else
                      cosine_scores(matrix, positions, query))
            row['scores_sha256'] = sha256(scores.tobytes()).hexdigest()
            row['top24'] = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), node_ids[i]))[:24]
        with probe.phase('release_query_temporaries') as row:
            del matrix, positions, scores, query
            if variant == 'baseline' and component == 'all':
                del encoded
            gc.collect()
            row['mapping_released'] = mapping_ref() is None
            assert row['mapping_released']
        with probe.phase('release_manifest'):
            if component == 'all':
                del index
            del node_ids
            gc.collect()
        assert before == [signature(p) for p in paths], 'component_input_changed'
        probe.report['status'] = 'passed'
    except BaseException as exc:
        probe.report.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        probe.save()
    return probe.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=('baseline', 'optimized'), required=True)
    parser.add_argument('--component', choices=('all', 'manifest', 'vectors'), default='all')
    args = parser.parse_args()
    profile(args.index, args.matrix, args.output, variant=args.variant, component=args.component)


if __name__ == '__main__':
    main()
