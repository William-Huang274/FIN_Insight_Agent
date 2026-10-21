"""Bounded-memory input loading and local phase profiles for intake qualification.

Profiles are diagnostic instrumented wall times, never capacity/latency claims.
No authority, stored original, or retrieval implementation is substituted.
"""
from collections.abc import MutableMapping, Sequence
from contextlib import contextmanager
import cProfile
from hashlib import file_digest
import json
from pathlib import Path
import pstats
from time import perf_counter
import numpy as np


class SourceBundles(MutableMapping):
    """Keep file references, not all expanded corpus bodies, in the test driver."""
    def __init__(self, paths=()):
        self.paths = dict(paths)

    def __getitem__(self, key):
        return json.loads(self.paths[key].read_text(encoding='utf8'))

    def __setitem__(self, key, value):
        self.paths[key] = Path(value)

    def __delitem__(self, key):
        del self.paths[key]

    def __iter__(self):
        return iter(self.paths)

    def __len__(self):
        return len(self.paths)

    def subset(self, keys):
        return SourceBundles((key, self.paths[key]) for key in keys)


def file_sha256(path):
    with Path(path).open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


class SourceVectors(MutableMapping):
    """Only one source matrix is open; row returns own their small vector data."""
    def __init__(self):
        self.positions = {}
        self.path = self.matrix = None

    def __getitem__(self, key):
        path, position = self.positions[key]
        if path != self.path:
            self.matrix = None
            self.path = path
            self.matrix = np.load(path, mmap_mode='r', allow_pickle=False)
        return self.matrix[position].copy()

    def __setitem__(self, key, value):
        if key in self.positions:
            raise ValueError('duplicate_source_vector_identity')
        self.positions[key] = value

    def __delitem__(self, key):
        del self.positions[key]

    def __iter__(self):
        return iter(self.positions)

    def __len__(self):
        return len(self.positions)

    def projected(self, nodes):
        source = self
        class Rows(Sequence):
            def __len__(self):
                return len(nodes)
            def __getitem__(self, index):
                return source[nodes[index]['original_source']['id']]
        return Rows()


class PhaseDiagnostics:
    def __init__(self, save):
        self.save, self.rows = save, []

    @contextmanager
    def phase(self, name, *, profile=False):
        started = perf_counter()
        row = {'phase': name, 'status': 'running', 'instrumented': profile}
        self.rows.append(row)
        self.save('phase-diagnostics', self.rows)
        profiler = cProfile.Profile() if profile else None
        if profiler:
            profiler.enable()
        try:
            yield
            row['status'] = 'passed'
        except BaseException as exc:
            row.update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            if profiler:
                profiler.disable()
            row['wall_seconds'] = perf_counter() - started
            if profiler:
                stats = pstats.Stats(profiler).stats
                row['functions'] = [dict(file=Path(key[0]).name, line=key[1], function=key[2],
                    primitive_calls=value[0], calls=value[1], self_seconds=value[2], cumulative_seconds=value[3])
                    for key, value in stats.items() if any(part in key[0] for part in (
                        'organization_', 'asset_workspace', 'project_source_captures',
                        'source_document_navigation', 'source_hybrid', 'library_source_bundle', 'research_library'))]
            self.save('phase-diagnostics', self.rows)
